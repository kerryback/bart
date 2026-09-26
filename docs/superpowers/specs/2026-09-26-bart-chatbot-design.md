# Bart Simpson chatbot — design

Date: 2026-09-26

## Purpose

A small public chatbot that answers in Bart Simpson's voice, as a companion
piece to `pirate.kerryback.com`. It is a toy. There is no teaching goal, no
student-facing assignment behind it, and no requirement that it scale. Success
is that `https://bart.kerryback.com` loads, replies in character, and stays up
without attention.

This is deliberately the pirate app again with a different persona. Where a
choice arises, the tiebreaker is "what did pirate do" — the precedent works and
is already deployed in the same Koyeb organization.

## The single name

One name, `bart`, used verbatim in four places:

| Where | Value |
| --- | --- |
| Local folder | `~/repos/bart` |
| GitHub repo | `kerryback/bart` (public) |
| Koyeb app | `bart`, service `web` |
| Custom domain | `bart.kerryback.com` |

## Architecture

A FastAPI process serving one JSON endpoint and one static page. No database,
no server-side session state, no background work.

```
bart/
  main.py              FastAPI app
  static/index.html    chat UI, self-contained (CSS and JS inline)
  requirements.txt     fastapi, uvicorn[standard], anthropic, python-dotenv
  Procfile             web: uvicorn main:app --host 0.0.0.0 --port $PORT
  .gitignore           .venv, .env, __pycache__
  tests/test_app.py    pytest against TestClient, Anthropic call stubbed
  README.md
```

### Endpoints

| Method | Path | Behavior |
| --- | --- | --- |
| `POST` | `/api/chat` | Takes `{"messages": [{"role": "user"\|"assistant", "content": str}, ...]}`, returns `{"reply": str}` |
| `GET` | `/` | Serves `static/index.html` |
| `GET` | `/healthz` | Returns 200 with a small JSON body; does not call the Anthropic API |
| — | `/static/*` | Mounted static files |

### Data flow

The browser owns the transcript. Each turn it POSTs the entire message history;
the server forwards it to the Messages API with the Bart system prompt and
returns only the reply text. The server keeps nothing between requests.

This is the single most important structural decision and it is inherited from
pirate. It means a redeploy costs nobody their conversation, one instance is
always enough, and there is no state to corrupt or expire.

### Model

`claude-haiku-4-5`, matching pirate — fast and cheap, and persona work is not a
reasoning-heavy task. The model id is a module-level constant so switching to
`claude-sonnet-5` is a one-line change if the voice reads thin in practice.

`max_tokens` 1024. Replies are chat-length; the cap exists to bound cost on a
public endpoint, not to shape the output.

### Error handling

`main.py` maps Anthropic exceptions to HTTP status codes, as pirate does:

| Condition | Status | Detail shown |
| --- | --- | --- |
| Empty `messages` list | 400 | "No messages provided." |
| `anthropic.AuthenticationError` | 500 | Invalid or missing `ANTHROPIC_API_KEY` |
| `anthropic.RateLimitError` | 429 | Rate limited, try again shortly |
| Other `anthropic.APIError` | 502 | The upstream error text |

The page shows the failure in the transcript as a message rather than an alert,
and leaves what the user typed recoverable.

## The persona

Pirate's system prompt is one line. Bart's cannot be, because "talk like Bart"
carries more than a dialect: an age, a stance toward authority, a setting, and
a set of catchphrases that stop being funny if every reply uses one.

The system prompt establishes:

- Ten years old, Springfield, fourth grade at Springfield Elementary.
- A proud underachiever — bored by school, quick, not stupid.
- Springfield texture used naturally when it fits: Milhouse, Lisa, Homer,
  Principal Skinner, Krusty, the skateboard, Butterfinger-era commercial energy.
- Catchphrases ("eat my shorts", "ay caramba", "don't have a cow, man",
  "cowabunga") used sparingly — at most occasionally, never as a substitute for
  an answer.

And two rules that make it usable rather than merely accurate:

1. He answers the question. Bart is dismissive, not unhelpful. A bot that only
   deflects stops being funny after two exchanges, which is the actual failure
   mode this rule exists to prevent.
2. He stays age-appropriate, and will not give real instructions for anything
   that would genuinely hurt a person or damage property, however the request is
   dressed up as a prank. He can be rude about refusing; the refusal is in
   character.

The prompt lives as a module-level constant in `main.py`, plainly visible and
easy to edit.

## The page

`static/index.html`, self-contained — CSS and JS inline, no build step, no
external fonts or scripts beyond what a plain page needs.

Visual treatment is CSS only, with no image assets and nothing traced or copied
from the show: Simpsons yellow, sky blue, and the orange-red of Bart's shirt, a
heavy rounded sans face from the system stack, chat bubbles with the user right
and Bart left. The look evokes; it does not reproduce.

This is a legal constraint, not only an aesthetic one. Bart is a Fox/Disney
character. Imitating a voice in text on a personal toy is a different matter
from redistributing the studio's artwork, and shipping no artwork keeps the
question from arising.

Behavior: an input, a send button, Enter to send, the transcript accumulating
in a scrolling column, a typing indicator while the request is in flight, and a
button to clear the conversation. History is held in a JavaScript array and is
not persisted — reloading starts fresh, which for a toy is the expected and
desirable behavior.

## Deployment

### Koyeb

Built by buildpack from the public GitHub repo, mirroring pirate's working
deployment definition:

```
koyeb app create bart
koyeb service create web \
  --app bart \
  --git github.com/kerryback/bart \
  --git-branch main \
  --instance-type nano \
  --regions was \
  --scale 1 \
  --ports 8000:http \
  --routes /:8000 \
  --checks 8000:http:/healthz \
  --env 'ANTHROPIC_API_KEY={{secret.anthropic-api-key}}'
```

The `anthropic-api-key` secret already exists in the organization and is what
pirate uses. No new secret is created.

One thing to verify rather than assume: the secret name contains hyphens, and
every prior service here referenced secrets with underscores in the
`{{secret.name}}` template. If the CLI rejects or mangles the hyphenated form,
set the env var through `koyeb service update` instead and confirm the running
definition binds `ANTHROPIC_API_KEY` to the secret rather than to a literal.

Two deviations from pirate, both deliberate:

- A health check on `/healthz`. Pirate has none, so a broken build can go
  healthy on Koyeb's view of it. The check costs nothing and gates the deploy
  on the app actually answering.
- The buildpack start command comes from `Procfile`, as pirate's does. Pirate's
  first deployment failed for want of one; including it from the first commit
  avoids repeating that.

Scale is pinned at 1/1. There is no shared state that would forbid more, but
there is also no load that would justify it.

### Domain

```
koyeb domains create bart.kerryback.com --attach-to bart
```

Koyeb reports an `intended_cname`. Create a CNAME record `bart` in the
`kerryback.com` zone at DNSimple pointing at exactly that value, via the
DNSimple API v2 with the `DNSIMPLE_ACCESS_TOKEN` environment variable, which is
present in the shell.

Do not use the `dnsimple-cli` npm package; it crashes on modern Node. The token
is a user token, so `/whoami` returns null for the account and the account id
must be read from `GET /v2/accounts` first.

The record name is the subdomain only (`bart`), not the full hostname. Check for
an existing `bart` record before creating, and update rather than duplicate.

### Push-to-deploy

Koyeb can build a public repo without credentials, but only redeploys on push if
Koyeb's GitHub app is installed on that specific repository. This has silently
failed before on `screenshare`, leaving production on old code while the repo
said otherwise.

So: after the first push, verify with `koyeb deployments list --service web`
rather than assuming. If the webhook is not wired, either grant the GitHub app
access to `kerryback/bart` or redeploy by hand with
`koyeb service redeploy bart/web`.

## Testing

`tests/test_app.py`, pytest against FastAPI's `TestClient`, with the Anthropic
client replaced by a stub so no test makes a network call or spends money:

| Test | Asserts |
| --- | --- |
| Normal exchange | 200, and the reply text comes back in `reply` |
| Empty `messages` | 400 |
| Upstream `APIError` | 502 |
| Upstream `RateLimitError` | 429 |
| `GET /healthz` | 200 |
| `GET /` | 200 and serves HTML |

The system prompt is passed to the stub and can be asserted on for presence, but
persona quality is not unit-testable and is not tested. That judgment is made by
talking to the deployed app.

## Local development

```bash
cd ~/repos/bart
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

`.env` holds `ANTHROPIC_API_KEY` and is gitignored. `python-dotenv` loads it at
import, so local runs need no exported variable; on Koyeb the variable comes
from the secret and the missing `.env` is harmless.

## Out of scope

Named here so they are decisions rather than omissions:

- Streaming responses. Haiku returns a chat-length reply fast enough that the
  typing indicator covers the wait.
- Server-side conversation storage or any database.
- Authentication, rate limiting, or abuse controls. This accepts the same
  exposure as `pirate.kerryback.com`, which has been public for a year on the
  same API key. If cost ever becomes visible, the response is a rate limit, and
  that is a later change.
- Voice, avatars, or generated imagery.
- Anything that would require more than one instance.
