# justdowork-proxy

**English** · [简体中文](README.zh-CN.md)

Run **Claude Code** against an OpenAI/Anthropic-compatible relay that isn't a
faithful Anthropic endpoint.

The relay this was built for is `https://api.justwoker.icu`, but the messy
parts it fixes are generic: relays that drop tool calls, ignore the `tools`
array, mangle streaming, or hand back empty `403`s at random.

**You point Claude Code at this proxy instead of at the relay.** The proxy
translates both ways, repairs the model's JSON, runs web search itself, and
hands Claude Code a clean, standards-shaped stream.

> **License:** free for personal, hobby, educational, research, non-profit and
> government use. **Commercial use — including reselling or hosting it as a
> paid service — requires a separate written license.** See [License](#license).

---

## This fork and the `docker` branch

This is [RavenHogWarts/justdowork-proxy](https://github.com/RavenHogWarts/justdowork-proxy),
a fork of [abdurrehmandaudi/justdowork-proxy](https://github.com/abdurrehmandaudi/justdowork-proxy).
The fork's default branch is **`docker`**: it carries upstream's code —
including the **v3.0.0** changes (smarter history trimming, adaptive extended
thinking, concurrent web tools) — and adds on top:

| Addition | What it gives you |
|---|---|
| Docker packaging | `docker compose up -d --build` on any Docker host; a multi-arch (amd64 + arm64) image is published to GHCR on every `v*` tag |
| `client_key_passthrough` (default on) | upstream calls **use the key each client sends**, so cc-switch stays the single manager of provider keys; an optional fallback key takes over on 401/403 |
| Dashboard key panel | save or replace the fallback key from the browser — effective immediately, no restart, persisted across container re-creation |
| Access token (`CCPROXY_TOKEN`) | optional auth when the proxy is reachable past loopback |
| Bilingual dashboard | English / 简体中文 UI, switchable per browser, `UI_LANG` sets the default |
| Volume-friendly runtime data | the saved key, logs and dumps all live in one `CCPROXY_DATA_DIR` |
| CI | both test suites and the Dockerfile build run on every push |

Changes to upstream files are kept minimal (a `LISTEN_HOST` env override,
`.env` loading, the client-key passthrough and the key endpoints in
`ccproxy.py`, the key panel in `dashboard.py`); everything else is additive
files. The `main` branch tracks upstream unchanged.

**Docker in depth:** [DOCKER.md](DOCKER.md) · [DOCKER.zh-CN.md](DOCKER.zh-CN.md)

---

## What it fixes

| Problem at the relay | What the proxy does |
|---|---|
| Only honours tools literally named `read`/`write`/`edit`/`bash` | Sends those four natively with real schemas; every other tool goes through a `<tool_call>` text protocol |
| Model writes JSON with literal newlines and bad escapes, call is dropped | 4-step repair: strict parse → control chars → escape repair → bracket balancing |
| Streaming drops text and tool blocks (thinking deltas only) | Synthesises the SSE stream itself, with a ping every 3 s so nothing times out |
| Cannot run `WebSearch` / `WebFetch` | The proxy runs DuckDuckGo / opens the page itself and loops until the model answers; several searches in one reply run concurrently |
| Huge histories cause 524 timeouts | Fits the conversation into a char budget — keeping a reserved slice for the human's own turns |
| The model "forgets" the task after a few turns | Never drops history silently: a marker where the cut happened plus a `Context notice` in the system prompt, so the model says "I've lost that" instead of guessing |
| The model edits a file it cannot see the end of | Tool output is no longer capped at 4 000 chars — a large `Read` reaches the model whole up to `max_tool_result_chars` (`32000`) |
| ~26% of requests come back as an empty `403`/`503` at random | Retries **immediately** (measured: the relay rejects with no cooldown, so a 0-second retry returns 200); `403` counts as retryable |
| Thinking is supported but never requested | Adaptive extended thinking: the budget goes to the turn that *plans* (a fresh user message); mechanical turns stay fast |
| Adds ~10.4k phantom input tokens to every request | `usage_baseline_tokens` corrects the reported number (the real cost stays — that's the relay's) |

---

## Quick start: Docker

No Python, no config file, and — thanks to client-key passthrough — **no key
needed to start**:

```sh
# 1. get the code (the docker branch only exists in this fork)
git clone https://github.com/RavenHogWarts/justdowork-proxy.git
cd justdowork-proxy
git checkout docker

# 2. build and start
docker compose up -d --build
```

First build takes a minute or two; later starts are seconds. The proxy
publishes on **<http://127.0.0.1:18181>** (loopback by default).

Verify:

```sh
curl http://127.0.0.1:18181/health
# {"ok": true, ..., "key_set": false, "client_key_passthrough": true}
```

`key_set: false` is expected — no fallback key configured yet. Three ways to
bring one (they combine):

1. **cc-switch mode (recommended)** — put the real relay key in your
   [cc-switch](https://github.com/farion1231/cc-switch) provider entry; Claude
   Code sends it with every request and the proxy uses it for upstream calls.
2. **Dashboard** — open <http://127.0.0.1:18181/>, save a key in the
   **API key** panel at the bottom; applies immediately and persists.
3. **Environment** — seed a fallback key before first start via `.env`
   (see [DOCKER.md](DOCKER.md#the-optional-env)).

Skip the clone entirely with the published image (CI builds amd64 + arm64 on
every `v*` tag):

```sh
docker run -d --name justdowork-proxy --restart unless-stopped \
  -p 127.0.0.1:18181:8181 ghcr.io/ravenhogwarts/justdowork-proxy
```

Then connect Claude Code as in [Running Claude Code through it](#running-claude-code-through-it).
Ports, volumes, custom `config.json`, Windows data-drive placement, the access
token — all covered in [DOCKER.md](DOCKER.md).

---

## Quick start: native Python

No Docker needed either — this is two pure-Python dependencies in a local
`.venv`.

**Requirements:** [Python 3.9+](https://www.python.org/downloads/) and an API
key for your relay. On Windows, tick *Add python.exe to PATH* in the installer's
first screen.

```sh
# macOS / Linux
git clone https://github.com/RavenHogWarts/justdowork-proxy.git
cd justdowork-proxy
git checkout docker
export UPSTREAM_API_KEY='sk-...'
sh start.sh          # first run creates .venv and installs flask + requests
```

```bat
:: Windows (Command Prompt / PowerShell)
git clone https://github.com/RavenHogWarts/justdowork-proxy.git
cd justdowork-proxy
git checkout docker
setx UPSTREAM_API_KEY "sk-..."    :: takes effect in NEW terminals only
start.bat
```

The proxy starts on `http://127.0.0.1:8181` (native default; the Docker setup
publishes 18181). Leave it running; for the key see
[Getting an API key](#getting-an-api-key).

---

## Getting an API key

The key is the **relay's** key, not an Anthropic key. For the relay this was
built against, sign up at [api.justwoker.icu](https://api.justwoker.icu) and
copy the `sk-...` key from the dashboard.

Where to put it, in order of convenience:

| Where | Notes |
|---|---|
| cc-switch provider entry | the key travels with every request (`client_key_passthrough`); nothing stored on the proxy side |
| Dashboard **API key** panel | saved as the fallback key; immediate, persisted (Docker volume or local `.env`) |
| `UPSTREAM_API_KEY` env var | `export` it, or `setx` on Windows (new terminals only) |
| `config.json` → `"api_key"` | works too — **never commit it**; the repo ships with `""` |

Precedence inside the proxy: real environment variables > `.env` >
`config.json`. With no fallback key at all, the proxy runs in client-key mode
and relies on the keys clients send; on 401/403 from upstream it retries once
with the fallback if one exists. The per-request log line shows which source
was used (`key=client` / `key=config`).

---

## Check that it works

Open **<http://127.0.0.1:18181/>** (Docker) or **<http://127.0.0.1:8181/>**
(native) in a browser. You get a live dashboard showing where your tokens are
going: requests, input/output tokens, the relay's phantom tokens, tool calls,
dropped calls, retries, and a bar per request. It refreshes every 2 seconds.

`/health` is the machine-readable check:

```json
{"ok": true, "upstream": "https://api.justwoker.icu", "model": "claude-opus-4-8", "key_set": true, "client_key_passthrough": true}
```

`"key_set": false` only means there is no *fallback* key — in cc-switch mode
that's fine.

You can also run the offline test suites — they need **no** API key, because
they start their own mock upstream:

```sh
sh run_tests.sh          # test_offline.py — macOS / Linux
run-tests.bat            :: Windows
python test_branch.py    # the docker-branch suite (both need Python, not Docker)
```

Expected: `RESULT: 70 pass, 0 fail` and `RESULT: 40 pass, 0 fail`.

---

## Running Claude Code through it

The easy way — `run-claude.sh` / `run-claude.bat` check the proxy is
answering, point Claude Code at it via a throwaway `--settings` file (your
global `~/.claude/settings.json` is **not** modified), set
`ENABLE_TOOL_SEARCH=false`, and pass any extra flags through. They default to
port 8181, so under Docker set `PROXY`:

```sh
PROXY=http://127.0.0.1:18181 sh run-claude.sh          # Docker
sh run-claude.sh --continue --model claude-opus-4-8    # native default port
```

By hand:

```sh
export ANTHROPIC_BASE_URL='http://127.0.0.1:18181'   # or :8181 native
export ANTHROPIC_API_KEY='sk-your-relay-key'         # real key (preferred) or dummy
export ENABLE_TOOL_SEARCH='false'
claude
```

With `client_key_passthrough` on (default), the key you set here is what the
proxy sends upstream — put the **real relay key**. `dummy` also works provided
a fallback key exists; a 401 then falls back to it automatically.

**With cc-switch:** add the proxy as a custom provider (endpoint
`http://127.0.0.1:18181`, API key = the real relay key, model as you like) and
put `"ENABLE_TOOL_SEARCH": "false"` in Claude Code's global `env` block once —
full walkthrough in [DOCKER.md](DOCKER.md#using-cc-switch-provider-switcher).

---

## What works

| Feature | How it works |
|---|---|
| `Read` `Write` `Edit` `Bash` | the relay's **native** tools (`read`/`write`/`edit`/`bash`) |
| `Agent` (subagents, parallel), `Monitor`, `Task*`, `TodoWrite`, MCP tools | the `<tool_call>` text protocol |
| `WebSearch` | the **proxy itself** searches DuckDuckGo — concurrent when a reply asks for several |
| `WebFetch` | the **proxy itself** opens the page |
| `fetch_image` | the **proxy itself** fetches the image |
| `/v1/messages/count_tokens` | local estimate (the relay returns 404) |
| `/v1/models` | available |
| Streaming | SSE + a **ping every 3 seconds** (no dead air, no timeout) |

Verified by running real Claude Code through the proxy: four `Agent` subagents
launched in parallel in one message, each ran its own live web search, each
wrote a separate standalone HTML file. All four files landed on disk, all four
well-formed and different.

---

## Configuration

Everything lives under `features` in `config.json`; environment variables
override the file. The knobs that matter most:

```jsonc
"max_history_chars": 220000,   // history budget, ~55k tokens. THE big lever.
"max_tool_result_chars": 32000,// how much of a large bash/file output to forward
"compact_tools": true,         // false = full tool descriptions (many more tokens)
"upstream_retries": 2,         // every retry re-sends the whole payload = tokens!
"usage_baseline_tokens": 0,    // set to 10380 to hide this relay's phantom tokens
"dump_requests": false,        // true = save every request to debug_dump/ (uses disk)
```

**The biggest lever is `max_history_chars`.** Claude Code sends the entire
session on every request. Going from `220000` (~55k tokens) to `120000`
(~30k tokens) roughly halves the cost — at the price of the model remembering
less of the earlier conversation (it will be told what was trimmed).

Environment variables (Docker-friendly; same names work natively):

| Variable | Overrides | Notes |
|---|---|---|
| `UPSTREAM_API_KEY` | `api_key` | fallback relay key |
| `TARGET_URL` | `upstream_base_url` | point at another relay without editing the file |
| `PORT` / `LISTEN_HOST` | `listen_port` / `listen_host` | container defaults: `8181` / `0.0.0.0` |
| `UI_LANG` | `ui_lang` | dashboard default language, `en` or `zh` |
| `CCPROXY_TOKEN` | `proxy_token` | require `X-Proxy-Token` / `Bearer` on every route except `/health` — use it whenever the port is reachable past loopback |
| `CCPROXY_DATA_DIR` | — | where the saved key, log and dumps live (`/app/data` in the image) |
| `CCPROXY_SERVER` | — | `flask` forces the dev server instead of waitress |

**Security default:** the proxy has no authentication of its own, so the
Docker setup binds `127.0.0.1` on the host. To serve other machines, set
`CCPROXY_TOKEN` and `CCPROXY_BIND=0.0.0.0` (plus firewall rules) — details in
[DOCKER.md](DOCKER.md#the-optional-env).

---

## Troubleshooting

**`UPSTREAM_API_KEY is not set`**
Only raised when `client_key_passthrough` is off and no key exists anywhere.
Set one (cc-switch / dashboard / env), or leave passthrough on. On Windows,
`setx` applies to **new** terminals only.

**`ccproxy is not answering on http://…`**
The proxy isn't running, or it's on another port. Start it (`docker compose
up -d`, or `sh start.sh` / `start.bat`) and leave it running.

**Claude Code says a tool doesn't exist (Agent, WebSearch, …)**
Check the model isn't talking about the relay's own default tools
(`read_tabular`, `system_todo_write`, …). Those are not this session's tools.
Restart the proxy so the tool preamble is rebuilt, and start a **fresh** Claude
Code session — a long contaminated history can keep the model confused.

**Getting `Upstream 524` timeouts**
The payload is too big. In `config.json` lower `max_history_chars` (e.g.
`220000` → `120000`) and set `max_tool_result_chars` to `2000`.

**Getting `Upstream 400`**
The proxy already retries with a slim payload (system as a plain string, no
`cache_control`). If it still fails, check the log — `docker logs
justdowork-proxy` under Docker, `ccproxy_log.txt` natively.

**A tool call is being dropped**
Search the log for `DROP tool_call` or `BAD JSON tool_call`. The JSON on that
line is the case to add to the repair.

**Port already taken**
Docker: `CCPROXY_PORT=28181 docker compose up -d`. Native: change
`listen_port` in `config.json`, then `PROXY=http://127.0.0.1:<port>` before
`run-claude.sh` / `run-claude.bat`.

**Edits start losing `old_string`/`new_string` arguments**
The relay's native `edit` has broken and healed before (last verified working
2026-10-07 via `edit_probe.py`). Re-run `python edit_probe.py` (needs
`UPSTREAM_API_KEY`), and if it fails, remove `"Edit": "edit"` from
`native_tool_map` — Edit then goes through the text protocol.

---

## Files

| File | Purpose |
|---|---|
| `ccproxy.py` | the proxy — **this is the one you run** |
| `dashboard.py` | the dashboard served at `/` (imported by ccproxy) |
| `config.json` | settings; env vars and `.env` override it |
| `Dockerfile` / `docker-compose.yml.example` / `.dockerignore` | the Docker packaging |
| `DOCKER.md` / `DOCKER.zh-CN.md` | the full Docker instructions (EN / 中文) |
| `requirements.txt` | flask + requests |
| `start.sh` / `start.bat` | start the proxy natively (macOS/Linux · Windows) |
| `run-claude.sh` / `run-claude.bat` | start Claude Code against the proxy (`PROXY`, `MODEL` env vars) |
| `run_tests.sh` / `run-tests.bat` | run the offline suite (test_offline.py) |
| `test_offline.py` | upstream's test suite, with its own mock upstream — 70 checks |
| `test_branch.py` | the docker-branch suite (passthrough, token, persistence) — 40 checks |
| `edit_probe.py` / `names_probe.py` | probes: is the relay's `edit` intact / which tool names exist natively |
| `agent_proxy.py` | **old version — kept for reference only, use `ccproxy.py`** |
| `ccproxy_log.txt` | the live log (created at runtime; rotates at 2 MB) |

---

## License

**PolyForm Noncommercial License 1.0.0** — the full text is in [LICENSE](LICENSE).

**Free to use for:** personal use, hobby projects, study, research, experiment,
teaching, and by charitable, educational, public research, public safety/health,
environmental and government organizations.

**Not permitted without a separate written commercial license:**

* reselling, sublicensing or rebranding this software, or a modified copy of it
* running it as a hosted or paid service (SaaS, paid API, managed deployment)
* embedding it in a commercial product
* using it internally at a for-profit company in support of revenue-generating work
* monetising it with ads or subscriptions

Anyone who receives a copy from you must also receive the license terms and the
`Required Notice:` line — see the [Notices](LICENSE#notices) section.

For a **commercial license**, open an issue or contact
[@abdurrehmandaudi](https://github.com/abdurrehmandaudi).

This project is **source-available, not open source**. The source is public on
purpose: so you can read it, audit it, and check for yourself that a proxy
sitting between you and your API key isn't doing anything hidden.

The Docker packaging and related modifications in this fork are contributed by
RavenHogwarts and remain under the same PolyForm Noncommercial License 1.0.0;
they do not relicense the project or lift its noncommercial restriction. The
upstream copyright and `Required Notice:` line are preserved.

---

## Notes

* Everything is local. Natively the proxy binds `127.0.0.1`; under Docker,
  compose publishes on the host's loopback. Your relay key never leaves your
  machine except in requests to the relay you configured.
* `agent_proxy.py` is the earlier, simpler proxy. It works for
  `Read`/`Write`/`Edit`/`Bash` but drops many other tool calls and cannot run
  web search. `ccproxy.py` replaces it.
* The model name in `ANTHROPIC_MODEL` is passed through to the relay as-is. Set
  it to whatever model string your relay expects.
* Under Docker the proxy is served by **waitress** (production WSGI);
  `CCPROXY_SERVER=flask` forces the dev-server fallback. Natively it uses
  Flask's dev server.
