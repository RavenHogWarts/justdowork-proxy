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
3. **Optional `.env` file** — only to *seed* a fallback key before the
   first start, or for compose variable substitution. A key you save in
   the dashboard already persists via the `/app/data` volume. See
   [Data persistence](#data-persistence) and
   [The optional .env](#the-optional-env).

Without compose:

```sh
docker build -t justdowork-proxy .
docker run -d --name justdowork-proxy --restart unless-stopped \
  -p 127.0.0.1:18181:8181 justdowork-proxy
```

Or skip the clone entirely with the published image: GitHub Actions
builds an amd64 + arm64 image on every `v*` tag and pushes it to GHCR
(CI also runs both test suites and validates the Dockerfile on every
push):

```sh
docker run -d --name justdowork-proxy --restart unless-stopped \
  -p 127.0.0.1:18181:8181 \
  ghcr.io/ravenhogwarts/justdowork-proxy
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
language follows the `ui_lang` field of `config.json` (`en` or `zh`), which
the `UI_LANG` environment variable overrides — compose passes it through:

```sh
UI_LANG=zh docker compose up -d
```

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

2. **A fallback key set before first start** — put the key in the file
   and mount it into the data dir (the folder is created for you):

   ```ini
   UPSTREAM_API_KEY=sk-...
   ```

   ```yaml
       volumes:
         - ./.env:/app/data/.env
   ```

   This is only needed to seed a key *before* you ever open the
   dashboard; once you save a key there it is written into the
   `/app/data` volume anyway (see [Data persistence](#data-persistence)).

Precedence inside ccproxy: real environment variables > `.env` >
`config.json`.

Security note: by default the proxy has **no authentication of its own**
— whoever can reach the port can spend your (fallback) key. Compose
therefore binds to `127.0.0.1` on the host by default. To serve other
machines, enable the access token:

* set `CCPROXY_TOKEN=<random-string>` (compose passes it through, e.g.
  `CCPROXY_TOKEN=x1y2z3 docker compose up -d`)
* every route except `/health` then requires an `X-Proxy-Token: <token>`
  header (or `Authorization: Bearer <token>`); `/health` stays open for
  the container healthcheck — it exposes status only, never the key
* the Bearer value is then the PROXY token and is never forwarded as
  the relay key — the relay key comes from `x-api-key` or the fallback
  (for Claude Code use `ANTHROPIC_API_KEY=<token>` so it is sent as
  Bearer, plus a fallback key)
* the dashboard asks for the token once and remembers it in the browser

Still combine the token with `CCPROXY_BIND` / firewall rules. An `.env`
file, if you create one, is git-ignored and kept out of the image. Keys
only ever go to the relay configured in `config.json` / `TARGET_URL`.

---

## Changing the API key

Open the dashboard at <http://127.0.0.1:18181/> — the **API key** panel at
the bottom shows the masked fallback key (or a "client-supplied keys in
use" tag) and lets you save one:

* it applies **immediately**, no restart
* persistence: the saved key is written to `.env` inside the `/app/data`
  volume, so it now survives both a `docker restart` **and** a
  re-creation (`docker compose up -d --build` / `down` + `up`). See
  [Data persistence](#data-persistence).
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

**Native tool map:** the shipped `native_tool_map` routes
Read/Write/**Edit**/Bash natively. Edit was reported broken on 2026-10-06
(dropping `old_string`/`new_string`), but a 2026-10-07 re-run of
`edit_probe.py` measured ARGS INTACT 3/3 (the relay likely fixed it). If
edits start losing arguments again: verify with
`python edit_probe.py` (needs `UPSTREAM_API_KEY`, one small model call),
then remove `"Edit": "edit"` from `native_tool_map` via a mounted
`config.json` — Edit falls back to the `<tool_call>` text protocol.

---

## Logs

`log()` mirrors every line to stdout, so:

```sh
docker logs -f justdowork-proxy
```

shows the same content as `ccproxy_log.txt` would on a native install.
To get the actual file out of a running container:

```sh
docker cp justdowork-proxy:/app/data/ccproxy_log.txt .
```

The file lives in the `/app/data` volume (see
[Data persistence](#data-persistence)), so it survives container
re-creation. If you enable `dump_requests: true`, the dumps go to
`/app/data/debug_dump/` in the same volume.

---

## Data persistence

ccproxy keeps its mutable runtime data in one directory,
`CCPROXY_DATA_DIR` (the image sets it to `/app/data`):

| file | what it is |
|---|---|
| `.env` | the fallback API key saved from the dashboard |
| `ccproxy_log.txt` (+ `.1`) | the request log, rotated at ~2 MB |
| `debug_dump/` | request dumps, only when `dump_requests: true` |

`config.json` is **not** here — it is read-only, baked next to the code
at `/app`, and overridden by environment variables.

**compose** mounts a named volume `ccproxy-data` over `/app/data`, so
everything above persists across `up --build`, `down` + `up`, and
upgrades. Inspect or back it up:

```sh
docker volume inspect justdowork-proxy_ccproxy-data   # where it lives on the host
docker run --rm -v justdowork-proxy_ccproxy-data:/d -v "$PWD":/out \
  busybox tar czf /out/ccproxy-data.tgz -C /d .       # back it up
```

**plain `docker run`**: the `Dockerfile` declares `VOLUME /app/data`, so
even without `-v` Docker persists it to an anonymous volume. To put it
somewhere you choose, mount your own:

```sh
docker run -d --name justdowork-proxy --restart unless-stopped \
  -p 127.0.0.1:18181:8181 \
  -v ccproxy-data:/app/data \
  ghcr.io/ravenhogwarts/justdowork-proxy
```

### Putting the data on another drive (Windows)

Yes — the data directory can live anywhere, including another drive.
The clean way is a **named volume with a custom location**, which avoids
the uid-mismatch problems a Windows bind-mount can cause:

```sh
docker volume create --driver local \
  --opt type=none --opt o=bind \
  --opt device=D:/docker-data/ccproxy \
  ccproxy-data
```

then run compose as usual (it reuses the existing `ccproxy-data` volume).
A direct **bind mount** also works if you prefer a plain folder:

```sh
docker run -d --name justdowork-proxy --restart unless-stopped \
  -p 127.0.0.1:18181:8181 \
  -v D:/docker-data/ccproxy:/app/data \
  ghcr.io/ravenhogwarts/justdowork-proxy
```

or in compose, replace the named volume with the host path:

```yaml
    volumes:
      - D:/docker-data/ccproxy:/app/data
```

Notes for Windows:

* On **Docker Desktop (WSL2)** the drive must be shared with Docker
  (Settings → Resources → File sharing, or it just works under WSL2 for
  most paths). Use forward slashes: `D:/docker-data/ccproxy`.
* The container runs as uid 1000. Named volumes get the right ownership
  automatically; a **bind mount** to an NTFS folder is presented through
  the WSL2 layer and is normally world-writable, so the saved key still
  persists. If a bind mount ever shows `could not persist ... to .env`
  in the log, switch to the named-volume-with-`device` form above.
* The folder is created on first run; you don't need to pre-create the
  `.env` file (unlike the old single-file mount).

---

## Health, restart, stopping

* The image ships a `HEALTHCHECK` polling `/health` every 30 s
  (`docker ps` shows `healthy`).
* `docker compose down` stops and removes the container. With the
  default `restart: unless-stopped`, the proxy also comes back after a
  reboot / Docker daemon restart.
* To upgrade: `git pull`, `docker compose up -d --build` — only the code
  layers rebuild; the dependency layer is cached. The `/app/data` volume
  persists across the re-creation, so the dashboard-saved fallback key is
  kept (see [Data persistence](#data-persistence)).

---

## Image details

* Base `python:3.12-slim` (ccproxy supports 3.9+; 3.12 is current slim)
* Served by **waitress** (production WSGI); falls back to Flask's dev
  server when missing (`CCPROXY_SERVER=flask` forces the fallback);
  SSE events flush immediately
* Runs as a dedicated non-root `ccproxy` user; runtime data goes to the
  `/app/data` volume (chowned to that user), kept separate from the code
* Only `ccproxy.py`, `dashboard.py`, `config.json`, `requirements.txt`
  and the license/README are copied in — tests, probes, host-side start
  scripts stay out (see `.dockerignore`)
* `SIGTERM` is handled by ccproxy itself, so `docker stop` shuts it down
  cleanly (default 10 s grace period)
