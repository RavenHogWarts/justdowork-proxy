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
> (a `LISTEN_HOST` env override, `.env` loading and the dashboard key
> endpoints in `ccproxy.py`, the key panel in `dashboard.py`, `.env` in
> `.gitignore`); everything else is additive files.

---

## Requirements

* Docker (Docker Engine 23+ with Compose v2.24+, or a current Docker
  Desktop on Windows/macOS)
* Your relay's API key

That's all — Python is inside the image, you don't need it on the host.

---

## Quick start

```sh
cd justdowork-proxy
cp .env.example .env       # Windows: copy .env.example .env
# edit .env and put your key after UPSTREAM_API_KEY=
docker compose up -d --build
```

The key lives in `.env` — the same file works for local (non-docker)
runs, it is git-ignored and kept out of the image.

Then check it, from the host:

```sh
curl http://127.0.0.1:8181/health
# {"ok": true, "upstream": "https://api.justwoker.icu", "model": "claude-opus-4-8", "key_set": true}
```

The dashboard is at <http://127.0.0.1:8181/> and the API endpoint Claude
Code uses is `http://127.0.0.1:8181/v1` — exactly the same URLs as a
native install, so `run-claude.sh` / `run-claude.bat` work unchanged
against the container.

Without compose:

```sh
docker build -t ccproxy .
docker run -d --name ccproxy -p 127.0.0.1:8181:8181 \
  -v "$PWD/.env:/app/.env" ccproxy
```

---

## Changing the port

The published port is **not** hardcoded — you never need to touch the
container's internal port (8181):

* **compose:** set `CCPROXY_PORT=18181` in `.env` (then
  `docker compose up -d` again). The proxy is now on
  `http://127.0.0.1:18181` — start Claude Code with
  `PROXY=http://127.0.0.1:18181 sh run-claude.sh`.
* **docker run:** just change the `-p` left side:
  `-p 127.0.0.1:18181:8181`.
* **local run:** `listen_port` in `config.json`, or the `PORT` env var.

---

## The .env file

Everything deploy-specific lives in one git-ignored file
(template: `.env.example`):

| Variable | Used by | What it does |
|---|---|---|
| `UPSTREAM_API_KEY` | ccproxy | your relay key (required) |
| `TARGET_URL` | ccproxy + compose | overrides `upstream_base_url` |
| `CCPROXY_PORT` | compose | host port to publish on (default `8181`) |
| `CCPROXY_BIND` | compose | host interface to bind (default `127.0.0.1`) |

Precedence in ccproxy: real environment variables beat `.env`, `.env`
beats `config.json` — standard dotenv semantics. So you can still
`docker run -e UPSTREAM_API_KEY=...` for one-off overrides.

Security notes:

* The proxy has **no authentication of its own** — whoever can reach the
  port can spend your relay key. Compose therefore binds to `127.0.0.1`
  on the host by default. To serve other machines set
  `CCPROXY_BIND=0.0.0.0` **and** firewall it or put an auth-checking
  reverse proxy in front.
* In the container the key comes **only from the mounted `.env`**, never
  from a baked env var — that's deliberate, see the next section.

---

## Changing the API key

Open the dashboard at <http://127.0.0.1:8181/> — the **API key** panel at
the bottom shows the masked current key and lets you save a new one:

* it applies **immediately**, no restart, no container recreation
* it is written back to `.env` when that file is writable — with the
  compose bind mount it is, so the change also survives restarts
  (`docker restart ccproxy` included)
* if `.env` can't be written (read-only mount, or no file mounted), the
  key applies until the next restart and the panel says so

The same endpoints exist for scripts:

```sh
curl http://127.0.0.1:8181/api/key
# {"key_set": true, "masked": "sk-abc...wxyz"}
curl -X POST http://127.0.0.1:8181/api/key \
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
| endpoint / base URL | `http://127.0.0.1:8181` | keep in sync with `CCPROXY_PORT` |
| API key | `dummy` (a placeholder) | the real key stays in ccproxy's `.env` — cc-switch never stores or cloud-syncs it |
| model | e.g. `claude-opus-4-8` | passed through to the relay as-is |

Switching to that provider routes Claude Code through ccproxy (stream
repair, JSON repair and the proxy-run web tools all apply); switching
away goes direct to another relay. The container doesn't notice either
way.

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
  layers rebuild; the dependency layer is cached.

---

## Image details

* Base `python:3.12-slim` (ccproxy supports 3.9+; 3.12 is current slim)
* Runs as a dedicated non-root `ccproxy` user; `/app` is chowned to it
  because ccproxy writes its log (and dumps) next to itself
* Only `ccproxy.py`, `dashboard.py`, `config.json`, `requirements.txt`
  and the license/README are copied in — tests, probes, host-side start
  scripts and `.env` stay out (see `.dockerignore`)
* `SIGTERM` is handled by ccproxy itself, so `docker stop` shuts it down
  cleanly (default 10 s grace period)
