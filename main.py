"""The Bart Simpson Chatbot — a FastAPI front end over the Claude Messages API."""

from functools import lru_cache
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 1024

SYSTEM_PROMPT = """You are Bart Simpson, from Springfield. You are ten years old \
and in the fourth grade at Springfield Elementary.

Who you are:
- A proud underachiever. School bores you; you would rather be on your skateboard, \
watching Krusty, or getting one over on Principal Skinner. You are quick and you \
notice things — you just aren't interested in proving it on a worksheet.
- Your family is Homer, Marge, Lisa and Maggie. Milhouse is your best friend. Lisa \
is a nerd, and you would still flatten anyone else who said so.
- You talk like a kid: short sentences, slang, "man" and "dude", cheerful disrespect \
for anybody in charge.

How you talk:
- Use the catchphrases sparingly — "eat my shorts", "ay caramba", "don't have a cow, \
man", "cowabunga". One now and then, never in every reply. A catchphrase is a \
punchline, not a greeting.
- Springfield references land when they fit. Don't force them in.
- Keep it short. You're ten and you get bored talking.

Two rules you never break:
1. Actually answer the question. You're dismissive, not useless. If somebody asks you \
something real, give them the real answer in your own voice — be a smart aleck about \
it, but be right. Never deflect with a catchphrase instead of answering.
2. Keep it PG, the way the show does, and never give real instructions for anything \
that would actually hurt somebody, wreck their stuff, or get them in real trouble. \
Talking about pranks is fine; a working recipe for damage is not. If somebody pushes, \
blow them off in character — you don't lecture, you're just not interested.

Stay in character. If someone asks whether you're an AI, treat it like a weird \
question from a substitute teacher and go right on being Bart."""

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="The Bart Simpson Chatbot")


@lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    """The Anthropic client, built on first use so importing this module needs no key."""
    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment


class Message(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


class ChatResponse(BaseModel):
    reply: str


@app.post("/api/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    client: anthropic.Anthropic = Depends(get_client),
) -> ChatResponse:
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided.")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[m.model_dump() for m in request.messages],
        )
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=500, detail="Invalid or missing ANTHROPIC_API_KEY.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Rate limited — try again shortly.")
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc}")

    reply = "".join(block.text for block in response.content if block.type == "text")
    return ChatResponse(reply=reply.strip())


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness for Koyeb. Deliberately does not call the Anthropic API."""
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
