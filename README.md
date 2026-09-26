# The Bart Chatbot

A small FastAPI chatbot that answers in Bart Simpson's voice, using the Claude
Messages API. A companion piece to [pirate.kerryback.com](https://pirate.kerryback.com).

Live at <https://bart.kerryback.com>.

## Setup

```bash
cd ~/repos/bart
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

`.env` holds `ANTHROPIC_API_KEY` and is gitignored.

## Run

```bash
uvicorn main:app --reload
```

Then open <http://127.0.0.1:8000>.

## Test

```bash
pytest
```

The Anthropic call is stubbed, so the suite makes no network calls and spends
nothing. Persona quality is not unit-tested — that judgment comes from talking
to it.

## Layout

- `main.py` — the app. `POST /api/chat` takes the whole conversation and returns
  the reply; `GET /healthz` is Koyeb's health check. The system prompt is a
  constant near the top. Model: `claude-haiku-4-5`.
- `static/index.html` — the chat UI, self-contained. History lives in the
  browser, so the server holds no state and a redeploy costs nobody anything.
- `docs/superpowers/specs/` — the design spec.

No artwork from the show is used or shipped; the look is CSS only.

## Deployment

Koyeb, buildpack from this repo, app `bart` service `web`, `nano` in `was`,
scale pinned 1/1. `ANTHROPIC_API_KEY` comes from the `anthropic-api-key` Koyeb
secret. The custom domain is a CNAME in the kerryback.com zone at DNSimple
pointing at the target `koyeb domains create` reports.

Push-to-deploy only fires if Koyeb's GitHub app is installed on this repository.
Verify after pushing:

```bash
koyeb deployments list --service web --app bart
koyeb service redeploy bart/web   # if the webhook didn't fire
```
