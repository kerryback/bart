"""Endpoint tests. The Anthropic call is stubbed, so nothing here hits the network."""

import anthropic
import pytest
from fastapi.testclient import TestClient

from main import app, get_client


class FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeBlock(text)]


class FakeMessages:
    def __init__(self, reply=None, error=None):
        self.reply, self.error = reply, error
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self.error:
            raise self.error
        return FakeResponse(self.reply)


class FakeClient:
    def __init__(self, reply=None, error=None):
        self.messages = FakeMessages(reply, error)


def client_for(fake):
    app.dependency_overrides[get_client] = lambda: fake
    test_client = TestClient(app)
    test_client.fake = fake
    return test_client


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


# The anthropic SDK vendors its own httpx as `httpx2`; its exception constructors
# expect that module's Request/Response. Fall back to plain httpx for SDK versions
# that don't vendor one.
try:
    import httpx2 as sdk_httpx
except ImportError:  # pragma: no cover
    import httpx as sdk_httpx


def rate_limit_error():
    request = sdk_httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = sdk_httpx.Response(429, request=request)
    return anthropic.RateLimitError("rate limited", response=response, body=None)


def connection_error():
    request = sdk_httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIConnectionError(request=request)


def test_normal_exchange_returns_the_reply():
    client = client_for(FakeClient(reply="  Eat my shorts, man.  "))
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 200
    assert response.json()["reply"] == "Eat my shorts, man."


def test_the_bart_system_prompt_is_sent():
    client = client_for(FakeClient(reply="yeah"))
    client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert "Bart Simpson" in client.fake.messages.last_kwargs["system"]


def test_empty_message_list_is_rejected():
    client = client_for(FakeClient(reply="unused"))
    assert client.post("/api/chat", json={"messages": []}).status_code == 400


def test_a_bad_role_is_rejected():
    client = client_for(FakeClient(reply="unused"))
    response = client.post("/api/chat", json={"messages": [{"role": "captain", "content": "hi"}]})
    assert response.status_code == 422


def test_rate_limiting_maps_to_429():
    client = client_for(FakeClient(error=rate_limit_error()))
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 429


def test_an_upstream_failure_maps_to_502():
    client = client_for(FakeClient(error=connection_error()))
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 502


def test_healthz():
    assert TestClient(app).get("/healthz").status_code == 200


def test_index_serves_the_page():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "The Bart Chatbot" in response.text
