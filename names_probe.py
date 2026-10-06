# Copyright (c) 2026 abdurrehmandaudi
# Required Notice: Copyright (c) 2026 abdurrehmandaudi -- justdowork-proxy
# Licensed under the PolyForm Noncommercial License 1.0.0 -- commercial
# use is not permitted without a separate written commercial license.
# See LICENSE or https://polyformproject.org/licenses/noncommercial/1.0.0
import os
import re
import requests

TARGET = "https://api.justwoker.icu/v1/messages"
KEY = re.sub(r"[^\x21-\x7e]", "", os.environ.get("UPSTREAM_API_KEY", ""))
if not KEY:
    raise SystemExit("Pehle chalao: export UPSTREAM_API_KEY=''")

CANDIDATES = [
    "read", "write", "edit", "bash", "grep", "glob", "ls", "list", "find", "search",
    "web_search", "websearch", "web_fetch", "webfetch", "fetch", "fetch_url", "browse",
    "todo_write", "todowrite", "task", "multi_edit", "multiedit", "notebook_edit", "view",
    "cat", "run", "shell", "exec", "python", "str_replace", "create", "delete", "mkdir",
    "open", "search_web", "google", "http_get", "curl", "web", "internet_search",
    "agent", "ask_user", "system_todo_write", "read_tabular",
]

schema = {"type": "object", "properties": {"input": {"type": "string"}}}
body = {
    "model": "claude-opus-4-8",
    "max_tokens": 600,
    "tools": [{"name": n, "description": f"tool {n}", "input_schema": schema} for n in CANDIDATES],
    "messages": [{"role": "user", "content":
                  "List the exact names of every tool available to you, comma separated, nothing else."}],
}
r = requests.post(TARGET, json=body, timeout=180,
                  headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
                           "content-type": "application/json"})
print("HTTP", r.status_code)
if r.status_code != 200:
    print(r.text[:400])
    raise SystemExit
text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
print("\nModel ka jawab:\n", text)
tokens = {t.strip(" `*-.\n\t") for t in re.split(r"[,\n]", text)}
passed = [n for n in CANDIDATES if n in tokens]
print("\nPass hue naam:", passed)