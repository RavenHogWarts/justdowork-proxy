# Copyright (c) 2026 abdurrehmandaudi
# Required Notice: Copyright (c) 2026 abdurrehmandaudi -- justdowork-proxy
# Licensed under the PolyForm Noncommercial License 1.0.0 -- commercial
# use is not permitted without a separate written commercial license.
# See LICENSE or https://polyformproject.org/licenses/noncommercial/1.0.0
r"""edit_probe.py -- does the relay's NATIVE `edit` tool keep its arguments?

Why: the default native_tool_map no longer routes Edit natively. On 2026-10-06
a forced-call measurement against api.justwoker.icu showed the relay's native
`edit` filling its OWN arguments (read_tabular / pandas_operations) and
dropping old_string/new_string every time -- so Edit goes through the
<tool_call> text protocol instead, where the model fills the real schema.

This script re-runs that measurement so you can decide for your relay:
it forces one `edit` tool call (with Edit's real schema) and prints the
arguments that actually came back.

    export UPSTREAM_API_KEY='sk-...'        # required
    export TARGET_URL='https://...'         # optional, default = this relay
    export ANTHROPIC_MODEL='claude-opus-4-8'  # optional
    python edit_probe.py

Costs one small model call. Verdict meanings:

  ARGS INTACT   -> native edit echoes old_string/new_string; you can put
                   "Edit": "edit" back into native_tool_map (config.json)
  ARGS MANGLED  -> relay filled its own args / dropped yours: keep Edit on
                   the text protocol (the shipped default)
  NO TOOL CALL  -> the relay ignored the forced call; run once more, then
                   treat as ARGS MANGLED (a relay that cannot echo a forced
                   call cannot be trusted with native Edit either)
"""
import json
import os
import re
import sys

import requests

TARGET = (os.environ.get("TARGET_URL") or "https://api.justwoker.icu").rstrip("/") + "/v1/messages"
KEY = re.sub(r"[^\x21-\x7e]", "", os.environ.get("UPSTREAM_API_KEY", ""))
MODEL = os.environ.get("ANTHROPIC_MODEL") or "claude-opus-4-8"

if not KEY:
    raise SystemExit("Set the relay key first:  export UPSTREAM_API_KEY='sk-...'")

SCHEMA = {"type": "object",
          "properties": {"file_path": {"type": "string"},
                         "old_string": {"type": "string"},
                         "new_string": {"type": "string"}},
          "required": ["file_path", "old_string", "new_string"]}


def forced_edit_call(tool_name):
    body = {
        "model": MODEL,
        "max_tokens": 800,
        "tools": [{"name": tool_name, "description": "Edit a file.", "input_schema": SCHEMA}],
        "tool_choice": {"type": "tool", "name": tool_name},
        "messages": [{"role": "user", "content":
                      "Call the " + tool_name + " tool now, exactly once, with "
                      "file_path=notes.txt, old_string=alpha, new_string=beta. "
                      "Do not write any prose."}],
    }
    r = requests.post(TARGET, json=body, timeout=300,
                      headers={"x-api-key": KEY, "Authorization": f"Bearer {KEY}",
                               "anthropic-version": "2023-06-01",
                               "content-type": "application/json"})
    if r.status_code != 200:
        print(f"  HTTP {r.status_code}: {r.text[:300]}")
        return None
    for b in r.json().get("content") or []:
        if isinstance(b, dict) and b.get("type") == "tool_use":
            return b
    return None


def verdict(block):
    inp = block.get("input") or {}
    keys = sorted(inp.keys())
    print(f"  tool_use name: {block.get('name')}")
    print(f"  input keys   : {keys}")
    print(f"  input        : {json.dumps(inp, ensure_ascii=False)[:400]}")
    if "old_string" in inp and "new_string" in inp:
        print("  -> ARGS INTACT  (native edit keeps old_string/new_string)")
        return "intact"
    print("  -> ARGS MANGLED (old_string/new_string missing or relay filled its own)")
    return "mangled"


print(f"edit_probe -> {TARGET}   model={MODEL}")
print("\n[1/2] native lowercase name 'edit' (the name native_tool_map would send):")
block = forced_edit_call("edit")
result = "no-call" if block is None else verdict(block)

if result == "no-call":
    print("\n[2/2] one retry (the relay sometimes skips a forced call):")
    block = forced_edit_call("edit")
    result = "no-call" if block is None else verdict(block)

print("\nVerdict:", {
    "intact":  'native edit looks fine -- you may re-add "Edit": "edit" to '
               'native_tool_map in config.json',
    "mangled": 'keep Edit on the <tool_call> text protocol (the shipped default)',
    "no-call": 'inconclusive: the relay would not echo a forced edit call at all '
               '-- keep Edit on the text protocol',
}[result])
sys.exit(0 if result == "intact" else 1)
