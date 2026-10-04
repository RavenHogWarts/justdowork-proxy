# justdowork-proxy

A small Anthropic-compatible API proxy that forwards requests to an upstream endpoint. It lets you run Claude Code (`claude`) through your own proxy.

- `agent_proxy.py` — Flask proxy server (`http://127.0.0.1:8181`) that forwards `/v1/messages` requests to the upstream, with tool-name mapping and streaming support.
- `names_probe.py` — a script to check which tool names are allowed on the upstream.

## Requirements

- Python 3.8+
- Libraries: `flask`, `requests`

## Setup

First, create a virtual environment and install the required libraries:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install flask requests
```

Set your upstream API key (it is read from the environment, not hardcoded):

```bash
export UPSTREAM_API_KEY='your-key'
```

## Steps

1. Activate the virtual environment:

   ```bash
   source .venv/bin/activate
   ```

2. Export your API key:

   ```bash
   export UPSTREAM_API_KEY='your-key'
   ```

3. (Optional) First check which tool names are allowed on the upstream:

   ```bash
   python names_probe.py
   ```

4. Start the proxy server (listens on `http://127.0.0.1:8181`):

   ```bash
   python agent_proxy.py
   ```

5. In another terminal, run Claude Code through the proxy. Add the following to your Claude Code settings (e.g. `~/.claude/settings.json`):

   ```json
   {
     "env": {
       "ANTHROPIC_BASE_URL": "http://127.0.0.1:8181",
       "ANTHROPIC_MODEL": "claude-opus-4-8",
       "ANTHROPIC_API_KEY": "your-key",
       "ENABLE_TOOL_SEARCH": "false"
     }
   }
   ```

   > **Important:** Keep `ENABLE_TOOL_SEARCH` set to `"false"` — the proxy relies on this and it must not be enabled.

   Then run:

   ```bash
   claude
   ```

## Config (optional env vars)

| Variable | Default | Description |
| --- | --- | --- |
| `UPSTREAM_API_KEY` | *(required)* | Upstream API key |
| `TARGET_URL` | `https://api.justwoker.icu` | Upstream endpoint |
| `PORT` | `8181` | Local proxy port |
