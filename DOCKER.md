# Running ccproxy in Docker

ccproxy is a single Python process with two pure-Python dependencies
(`flask`, `requests`), so it containers cleanly: no compiler, no system
packages, no venv juggling. This file covers everything Docker-specific —
for what the proxy *does* and how to configure the relay, read the
[README](README.md) first. 中文文档：[DOCKER.zh-CN.md](DOCKER.zh-CN.md)。

> The Docker support lives on the `docker` branch of
> [RavenHogWarts/justdowork-proxy](https://github.com/RavenHogWarts/justdowork-proxy)
> (clone **that** fork — upstream has no such branch); `main`
> tracks upstream unchanged. The upstream-file changes are kept minimal
> (a `LISTEN_HOST` env override, `.env` loading, client-key passthrough
> and the dashboard key endpoints in `ccproxy.py`, the key panel in
> `dashboard.py`, `.env` in `.gitignore`); everything else is additive
> files.

---

## Requirements

* Docker (Docker Engine 23+ with Compose v2.20+, or a current Docker
  Desktop on Windows/macOS)
* Your relay's API key — or none to start with: it can come from
  cc-switch or the dashboard later

That's all — Python is inside the image, and **no config file needs to
exist on the host**.

---

## Quick start

```sh
git clone https://github.com/RavenHogWarts/justdowork-proxy.git
cd justdowork-proxy
git checkout docker
docker compose up -d --build
```

First build takes a minute or two; later starts are seconds. The proxy
publishes on **<http://127.0.0.1:18181>** (host side, loopback by
default).

Verify and bring a key:

```sh
curl http://127.0.0.1:18181/health
# {"ok": true, ..., "key_set": false, "client_key_passthrough": true}
```

`key_set: false` is expected — no fallback key configured yet. Three ways
to bring one (they combine):

1. **cc-switch mode (recommended)** — put the real relay key in the
   cc-switch provider entry; Claude Code sends it with every request and
   ccproxy uses it for upstream calls. See
   [Using cc-switch](#using-cc-switch-provider-switcher).
2. **Dashboard** — open <http://127.0.0.1:18181/>, save a key in the
   **API key** panel at the bottom; applies immediately and persists.
3. **Optional `.env` file** — for a file-based fallback key that
   survives container re-creation. See
   [The optional .env](#the-optional-env).

Without compose:

```sh
docker build -t ccproxy .
docker run -d --name ccproxy -p 127.0.0.1:18181:8181 ccproxy
```

---

## Connecting Claude Code

The proxy answers on `http://127.0.0.1:18181` (the compose default):

```sh
PROXY=http://127.0.0.1:18181 sh run-claude.sh   # scripts default to 8181, so set PROXY
```

or by hand:

```sh
export ANTHROPIC_BASE_URL='http://127.0.0.1:18181'
export ANTHROPIC_API_KEY='sk-your-relay-key'   # or dummy, see below
export ENABLE_TOOL_SEARCH='false'
claude
```

Key source: with `client_key_passthrough` (default on) the key you set
here is what ccproxy sends upstream — put the **real relay key**. `dummy`
also works, provided a fallback key exists (dashboard or `.env`); a 401
then falls back to it automatically.

---

## Changing the port

The default host port is **18181**; the container's internal port (8181)
never needs to change:

* **compose:** `CCPROXY_PORT=28181 docker compose up -d` (or put
  `CCPROXY_PORT` in an optional `.env`). Point Claude Code at the new
  port (cc-switch endpoint, or `PROXY=http://127.0.0.1:28181`).
* **docker run:** change the `-p` left side: `-p 127.0.0.1:28181:8181`.

### Dashboard language

The dashboard is bilingual (English / 简体中文): the button in the header
switches language and the choice is remembered per browser. The default
language follows the `ui_lang` field of `config.json` (`en` or `zh`; in
Docker, change it via a mounted `config.json`).

---

## The optional .env

An `.env` file is **not required**. Create one (git-ignored, kept out of
the image) only if you want either of:

1. **compose substitution only** — `CCPROXY_PORT`, `CCPROXY_BIND`,
   `TARGET_URL`. Compose reads `.env` automatically; the key variable
   does not reach the container in this usage.

   ```ini
   CCPROXY_PORT=28181
   TARGET_URL=https://another-relay
   ```

2. **A fallback key that survives container re-creation** — put the key
   in the file and mount it (the file must exist first):

   ```ini
   UPSTREAM_API_KEY=sk-...
   ```

   ```yaml
       volumes:
         - ./.env:/app/.env
   ```

Precedence inside ccproxy: real environment variables > `.env` >
`config.json`.

Security note: the proxy has **no authentication of its own** — whoever
can reach the port can spend your (fallback) key. Compose therefore
binds to `127.0.0.1` on the host by default. To serve other machines set
`CCPROXY_BIND=0.0.0.0` **and** firewall it or put an auth-checking
reverse proxy in front.

---

## Changing the API key

Open the dashboard at <http://127.0.0.1:18181/> — the **API key** panel at
the bottom shows the masked fallback key (or a "client-supplied keys in
use" tag) and lets you save one:

* it applies **immediately**, no restart
* persistence: a `docker restart` keeps it; a re-creation
  (`docker compose up -d --build` / `down` + `up`) loses it — mount an
  `.env` if that matters, or just save it again
* without any fallback key the proxy runs in client-key mode (cc-switch
  supplies the key per request)

The same endpoints exist for scripts:

```sh
curl http://127.0.0.1:18181/api/key
# {"key_set": true, "masked": "sk-abc...wxyz", "passthrough": true}
curl -X POST http://127.0.0.1:18181/api/key \
  -H "Content-Type: application/json" -d '{"api_key": "sk-new..."}'
# {"ok": true, "key_set": true, "persisted": true}
```

(Any client that can reach the dashboard can change the key — that's the
same trust model as the proxy itself, i.e. keep the port on loopback.)

---

## Using cc-switch (provider switcher)

[cc-switch](https://github.com/farion1231/cc-switch) is an open-source
desktop app that switches Claude Code (and Codex, and other tools)
between API providers by rewriting the endpoint / key / model in Claude
Code's own `~/.claude/settings.json`; with Claude Code v2.0.69+ the
switch is hot — no terminal restart. To ccproxy it is just another
Anthropic-compatible endpoint, so add it as a **custom provider**:

| cc-switch field | value | note |
|---|---|---|
| endpoint / base URL | `http://127.0.0.1:18181` | keep in sync with `CCPROXY_PORT` |
| API key | **the real relay key** | ccproxy uses it directly for upstream calls (see below) |
| model | e.g. `claude-opus-4-8` | passed through to the relay as-is |

Switching to that provider routes Claude Code through ccproxy (stream
repair, JSON repair and the proxy-run web tools all apply); switching
away goes direct to another relay. The container doesn't notice either
way.

**Key source (client_key_passthrough):** ccproxy enables
`client_key_passthrough` by default — upstream calls **prefer the key
the client sent**, i.e. the real key cc-switch configured, so cc-switch
stays the single manager of provider keys. Fallback: if upstream
answers 401/403 (e.g. the client key expired), ccproxy retries once
with the fallback key (dashboard or `.env`). The per-request log line
shows which source was used (`key=client` / `key=config`).

**Pure cc-switch mode:** no fallback key at all — ccproxy starts fine
and relies on the client-supplied keys; the dashboard header shows the
key as `client-supplied`, and the API key panel offers to save a
fallback any time.

**Prerequisite: `ENABLE_TOOL_SEARCH=false`.** ccproxy depends on it.
The `run-claude` scripts set it; cc-switch has no such wrapper, so put
it in Claude Code's global `env` block once — cc-switch preserves
user-added environment variables across switches. In
`~/.claude/settings.json` (Windows: `%USERPROFILE%\.claude\settings.json`):

```json
{
  "env": {
    "ENABLE_TOOL_SEARCH": "false"
  }
}
```

Notes:

* **No double proxying**: cc-switch also has a routing/aggregation mode
  (a local forwarder on `127.0.0.1:15721`). Use its **Direct** mode
  pointing straight at ccproxy; don't chain Claude Code → cc-switch
  router → ccproxy → relay — it can work, but failures become hard to
  attribute and it buys nothing.
* **vs. the run-claude scripts**: cc-switch edits the global settings
  while the scripts launch with a throwaway `--settings` file. They can
  coexist, but pick one per session so the two pointings don't override
  each other confusingly.
* **Remote proxy**: when the container runs on a server and Claude Code
  runs locally, point cc-switch at `http://<server>:<port>` and open
  `CCPROXY_BIND` / the firewall per the security notes above.

---

## Using your own `config.json`

The image bakes in the repo's `config.json` (with an empty `api_key`).
To change settings without rebuilding — history budget, model, feature
flags — mount your own copy read-only:

```yaml
    volumes:
      - ./config.json:/app/config.json:ro
```

Environment variables and `.env` always win over the file.

---

## Logs

`log()` mirrors every line to stdout, so:

```sh
docker logs -f ccproxy
```

shows the same content as `ccproxy_log.txt` would on a native install.
To get the actual file out of a running container:

```sh
docker cp ccproxy:/app/ccproxy_log.txt .
```

The file lives inside the container's writable layer and disappears with
it, which is fine for a personal proxy — stdout has everything. If you
enable `dump_requests: true`, the same applies to `debug_dump/`
(use `docker cp` before removing the container, or mount a volume over
`/app/debug_dump`).

---

## Health, restart, stopping

* The image ships a `HEALTHCHECK` polling `/health` every 30 s
  (`docker ps` shows `healthy`).
* `docker compose down` stops and removes the container. With the
  default `restart: unless-stopped`, the proxy also comes back after a
  reboot / Docker daemon restart.
* To upgrade: `git pull`, `docker compose up -d --build` — only the code
  layers rebuild; the dependency layer is cached. Note this re-creates
  the container, so a dashboard-saved fallback key is lost (cc-switch
  mode is unaffected) — save it again or mount an `.env`.

---

## Image details

* Base `python:3.12-slim` (ccproxy supports 3.9+; 3.12 is current slim)
* Runs as a dedicated non-root `ccproxy` user; `/app` is chowned to it
  because ccproxy writes its log (and dumps) next to itself
* Only `ccproxy.py`, `dashboard.py`, `config.json`, `requirements.txt`
  and the license/README are copied in — tests, probes, host-side start
  scripts stay out (see `.dockerignore`)
* `SIGTERM` is handled by ccproxy itself, so `docker stop` shuts it down
  cleanly (default 10 s grace period)
