import os
import re
import json
import requests

TARGET = "https://api.justwoker.icu/v1/messages"
RAW = os.environ.get("UPSTREAM_API_KEY", "")
# paste ke chhupe control characters aur spaces hata do
KEY = re.sub(r"[^\x21-\x7e]", "", RAW)
if not KEY:
    raise SystemExit("Pehle chalao: export UPSTREAM_API_KEY='yahan-apni-key'")
print(f"key length: {len(KEY)} (aapki key ki lambai 51 honi chahiye)")

SCHEMA = {
    "type": "object",
    "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}},
    "required": ["file_path", "content"],
}

# (tool name, forced tool_choice?)
VARIANTS = [
    ("write", False),
    ("read", False),
    ("edit", False),
    ("bash", False),
    ("create_file", False),
    ("run_command", False),
    ("write_to_file", False),
    ("str_replace_editor", False),
    ("web_search", False),
    ("write", True),
]

print()
for name, force in VARIANTS:
    body = {
        "model": "claude-opus-4-8",
        "max_tokens": 300,
        "tools": [{"name": name, "description": "Write a file to disk", "input_schema": SCHEMA}],
        "messages": [{"role": "user",
                      "content": "Create a file hello.txt containing hello world. Use the tool."}],
    }
    if force:
        body["tool_choice"] = {"type": "tool", "name": name}
    try:
        r = requests.post(TARGET, json=body, timeout=120,
                          headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
                                   "content-type": "application/json"})
    except Exception as e:
        print(f"{name:15} forced={force!s:5} -> EXCEPTION {e}")
        continue
    if r.status_code != 200:
        print(f"{name:15} forced={force!s:5} -> HTTP {r.status_code}: {r.text[:150]}")
        continue
    blocks = r.json().get("content", [])
    used = [b for b in blocks if b.get("type") == "tool_use"]
    if used:
        print(f"{name:15} forced={force!s:5} -> TOOL_USE OK  ({used[0].get('name')})")
    else:
        txt = next((b.get("text", "") for b in blocks if b.get("type") == "text"), "")
        print(f"{name:15} forced={force!s:5} -> NO tool_use | {txt[:110]!r}")
print()