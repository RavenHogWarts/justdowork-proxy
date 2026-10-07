# Copyright (c) 2026 abdurrehmandaudi
# Required Notice: Copyright (c) 2026 abdurrehmandaudi -- justdowork-proxy
# Licensed under the PolyForm Noncommercial License 1.0.0 -- commercial
# use is not permitted without a separate written commercial license.
# See LICENSE or https://polyformproject.org/licenses/noncommercial/1.0.0
r"""test_branch.py -- offline tests for the docker-branch additions.

test_offline.py covers the upstream behaviour; this file covers what the
docker branch added, still fully offline (its own mock upstream, no real
relay, no API key needed):

  * client_key_passthrough: client key preferred, dummy falls back after 401,
    no key uses the configured key
  * optional CCPROXY_TOKEN auth: 401 without/wrong token, Bearer carries the
    proxy token (never the relay key), /health stays open, dashboard gated
  * keyless startup + GET/POST /api/key (+ .env writeback into a temp dir)
  * .env loading and keyless mode in a real isolated subprocess
  * UI_LANG override and ui_lang in /stats.json; bilingual dashboard page
  * read-timeout is NOT retried, connection errors ARE; narrow retry set
  * count_tokens at bytes/3.3
  * Edit routed natively (re-verified against the relay 2026-10-07)
  * usage sanitize: cache double-count + phantom block + honest passthrough
  * JSON repair: truncated-body prefix salvage, required-field backfill

Run:  python test_branch.py     (expects 40 pass, 0 fail)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import requests
from flask import Flask, request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

os.environ.setdefault("UPSTREAM_API_KEY", "sk-config-key")
os.environ.setdefault("TARGET_URL", "http://127.0.0.1:8799")
os.environ.setdefault("UI_LANG", "zh")

import ccproxy  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra else ""))


# --------------------------------------------------------------------------- #
# 1. usage sanitize (unit) -- the relay's two accounting failures
# --------------------------------------------------------------------------- #
print("\n=== 1. usage sanitize ===")

u, ch = ccproxy._sanitize_usage(
    {"input_tokens": 10966, "cache_creation_input_tokens": 10964,
     "cache_read_input_tokens": 0, "output_tokens": 40}, 40000)
check("cache double-count: residual input + byte-plausible cc trusted",
      ch and u["input_tokens"] == 2 and u["cache_creation_input_tokens"] == 10964
      and u["cache_read_input_tokens"] == 0, str(u))

u, ch = ccproxy._sanitize_usage(
    {"input_tokens": 10957, "cache_creation_input_tokens": 10955,
     "cache_read_input_tokens": 0, "output_tokens": 4}, 2000)
check("phantom block relocated into cc (10955 claimed on 2KB) capped to est",
      ch and u["input_tokens"] == 2 and u["cache_creation_input_tokens"] == 606, str(u))

u, ch = ccproxy._sanitize_usage(
    {"input_tokens": 17900, "cache_creation_input_tokens": 17888,
     "cache_read_input_tokens": 0, "output_tokens": 9}, 21170)
check("denser-but-plausible cc (1.2 B/tok backend) left alone",
      ch and u["cache_creation_input_tokens"] == 17888 and u["input_tokens"] == 12, str(u))

u, ch = ccproxy._sanitize_usage(
    {"input_tokens": 11818, "output_tokens": 230}, 2000)
check("phantom block: 11.8k claimed on a 2KB payload capped to bytes/3.3",
      ch and u["input_tokens"] == 606, str(u))

u, ch = ccproxy._sanitize_usage({"input_tokens": 900, "output_tokens": 5}, 2900)
check("honest small usage passes through untouched", not ch)
u, ch = ccproxy._sanitize_usage({"input_tokens": 50000, "output_tokens": 5}, 160000)
check("honest big context NOT hidden (client must compact)", not ch)

# --------------------------------------------------------------------------- #
# 2. JSON repair additions (unit)
# --------------------------------------------------------------------------- #
print("\n=== 2. JSON repair additions ===")

obj = ccproxy.loads_tool_json('{"name":"Edit","input":{"file_path":"a.txt","old_string":"alp')
check("truncated body salvaged (prefix + closers)",
      obj is not None and obj.get("name") == "Edit"
      and "old_string" not in obj.get("input", {}), repr(obj))

obj = ccproxy.loads_tool_json('{"name":"Ask","input":{"options":[{"label":"a"},{"label":"b"},{"lab')
kept = (obj or {}).get("input", {}).get("options")
check("mid-string truncation keeps only finished rows (nothing fabricated)",
      obj is not None and kept == [{"label": "a"}, {"label": "b"}], repr(kept))

todo_schema = {"type": "object", "properties": {"todos": {"type": "array", "items": {
    "type": "object",
    "properties": {"content": {"type": "string"}, "activeForm": {"type": "string"}},
    "required": ["content", "activeForm"]}}}}
blocks = ccproxy.parse_assistant_text(
    '<tool_call name="TodoWrite">{"todos":[{"content":"fix the bug"}]}</tool_call>',
    valid_names={"TodoWrite"}, strict=True, schemas={"TodoWrite": todo_schema})
tu = [b for b in blocks if b.get("type") == "tool_use"]
check("required array-item field backfilled from a sibling (TodoWrite activeForm)",
      tu and tu[0]["input"]["todos"][0].get("activeForm") == "fix the bug",
      repr(tu[0]["input"] if tu else None))

# --------------------------------------------------------------------------- #
# 3. retry / timeout policy (monkeypatched transport)
# --------------------------------------------------------------------------- #
print("\n=== 3. retry & timeout policy ===")

calls = {"n": 0}
real_post = ccproxy.requests.post


def count_post(fn):
    def wrapped(*a, **k):
        calls["n"] += 1
        return fn(*a, **k)
    return wrapped


class FakeResp:
    def __init__(self, code):
        self.status_code, self.text = code, '{"e":1}'

    def json(self):
        return {"error": {"type": "x", "message": "m"}}


def raise_read_timeout(*a, **k):
    calls["n"] += 1
    raise ccproxy.requests.exceptions.ReadTimeout("read timed out")


def raise_conn(*a, **k):
    calls["n"] += 1
    raise ccproxy.requests.exceptions.ConnectionError("refused")


ccproxy.requests.post = raise_read_timeout
calls["n"] = 0
status, data = ccproxy.call_upstream({"messages": []})
check("read timeout: exactly ONE attempt (no double billing)",
      calls["n"] == 1 and status == 0
      and "double billing" in data["error"]["message"], f"calls={calls['n']}")

ccproxy.requests.post = raise_conn
calls["n"] = 0
ccproxy.call_upstream({"messages": []})
check("connection error still retried (2 attempts)", calls["n"] == 2)

ccproxy.requests.post = count_post(lambda *a, **k: FakeResp(524))
calls["n"] = 0
ccproxy.call_upstream({"messages": []})
check("524 (payload too big here) NOT retried", calls["n"] == 1)

ccproxy.requests.post = count_post(lambda *a, **k: FakeResp(503))
calls["n"] = 0
ccproxy.call_upstream({"messages": []})
check("503 still retried", calls["n"] == 2)
ccproxy.requests.post = real_post

# --------------------------------------------------------------------------- #
# 4. config-level bits
# --------------------------------------------------------------------------- #
print("\n=== 4. config: native map, count_tokens, ui_lang ===")

req_native = {"model": "m", "max_tokens": 100, "stream": False, "system": "s",
              "tools": [{"name": "Edit", "description": "d", "input_schema":
                         {"type": "object", "properties": {"file_path": {"type": "string"}}}}],
              "messages": [{"role": "user", "content": "hi"}]}
pl = ccproxy.build_payload(req_native, ccproxy.FEATS)
check("Edit IS sent natively (re-verified ARGS INTACT 2026-10-07)",
      "edit" in [t["name"] for t in (pl.get("tools") or [])])

with ccproxy.app.test_client() as tc:
    r = tc.post("/v1/messages/count_tokens",
                json={"messages": [{"role": "user", "content": "x" * 330}]})
    check("count_tokens at bytes/3.3 (330 chars -> 100)", r.get_json().get("input_tokens") == 100)

    check("UI_LANG env override reached config", ccproxy.CONFIG.get("ui_lang") == "zh")
    ccproxy.CONFIG["ui_lang"] = "en"
    r = tc.get("/stats.json").get_json()
    check("ui_lang exposed in /stats.json", r.get("ui_lang") == "en")
    ccproxy.CONFIG["ui_lang"] = "zh"

    page = tc.get("/").get_data(as_text=True)
    check("dashboard page ships the i18n dictionaries + toggle",
          "ccproxy_lang" in page and "data-i18n" in page and "I18N" in page)

# --------------------------------------------------------------------------- #
# 5. mock upstream + live proxy: passthrough, fallback, sanitize, /api/key
# --------------------------------------------------------------------------- #
print("\n=== 5. integration (mock upstream) ===")

SEEN_KEYS = []
GOOD_KEYS = {"sk-config-key", "sk-client-valid", "sk-from-envfile", "sk-set-via-api"}
PHANTOM_USAGE = {"input_tokens": 11818, "output_tokens": 77}

mock = Flask("mock-upstream")


@mock.route("/v1/messages", methods=["POST"])
def mock_messages():
    k = (request.headers.get("x-api-key") or "").strip()
    SEEN_KEYS.append(k)
    if k not in GOOD_KEYS:
        return Flask.response_class(
            json.dumps({"type": "error", "error": {"type": "authentication_error",
                                                   "message": "bad key"}}),
            401, content_type="application/json")
    return Flask.response_class(
        json.dumps({"id": "msg_mock", "type": "message", "role": "assistant",
                    "model": "m", "content": [{"type": "text", "text": "ok"}],
                    "stop_reason": "end_turn", "usage": PHANTOM_USAGE}),
        200, content_type="application/json")


threading.Thread(target=lambda: mock.run(port=8799, threaded=True, debug=False),
                 daemon=True).start()
threading.Thread(target=lambda: ccproxy.app.run(port=8798, threaded=True, debug=False),
                 daemon=True).start()
time.sleep(2.0)

PROXY = "http://127.0.0.1:8798"
BODY = {"model": "m", "max_tokens": 64, "stream": False,
        "messages": [{"role": "user", "content": "hi"}]}

h = requests.get(PROXY + "/health", timeout=30).json()
check("/health: key_set + client_key_passthrough",
      h.get("key_set") and h.get("client_key_passthrough") is True)

mark = len(SEEN_KEYS)
r = requests.post(PROXY + "/v1/messages", json=BODY,
                  headers={"x-api-key": "sk-client-valid"}, timeout=30)
check("client key preferred (mock saw the client key)",
      r.status_code == 200 and SEEN_KEYS[-1] == "sk-client-valid",
      f"seen={SEEN_KEYS[mark:]}")

mark = len(SEEN_KEYS)
r = requests.post(PROXY + "/v1/messages", json=BODY,
                  headers={"x-api-key": "dummy"}, timeout=30)
check("dummy key -> 401 -> configured key fallback -> 200",
      r.status_code == 200 and SEEN_KEYS[mark:] == ["dummy", "sk-config-key"],
      f"seen={SEEN_KEYS[mark:]}")

mark = len(SEEN_KEYS)
r = requests.post(PROXY + "/v1/messages", json=BODY, timeout=30)
check("no client key -> configured key used",
      r.status_code == 200 and SEEN_KEYS[-1] == "sk-config-key")

r = requests.post(PROXY + "/v1/messages", json=BODY,
                  headers={"x-api-key": "sk-client-valid"}, timeout=30)
check("phantom usage corrected on the client response (11818 -> ~payload/3.3)",
      r.status_code == 200 and 0 < r.json()["usage"]["input_tokens"] < 2000,
      f"client saw {r.json()['usage']['input_tokens']} (relay claimed 11818)")

st = requests.get(PROXY + "/stats.json", timeout=30).json()
_last = (st.get("recent") or [{}])[-1]
check("recent rows record which key source served them",
      _last.get("key_src") in ("client", "config"), f"key_src={_last.get('key_src')!r}")

# --- keyless mode + /api/key (writeback isolated into a temp dir) ----------
print("\n=== 6. keyless mode + /api/key ===")

saved_key = ccproxy.CONFIG["api_key"]
saved_env_path = ccproxy.ENV_PATH
tmpdir = tempfile.mkdtemp(prefix="ccproxy-branch-test-")
try:
    ccproxy.CONFIG["api_key"] = ""
    k = requests.get(PROXY + "/api/key", timeout=30).json()
    check("/api/key GET in keyless mode: key_set false, passthrough true",
          k.get("key_set") is False and k.get("passthrough") is True, str(k))

    env_file = os.path.join(tmpdir, ".env")
    ccproxy.ENV_PATH = env_file       # .env writeback goes to the temp dir
    r = requests.post(PROXY + "/api/key", json={"api_key": "sk-set-via-api"}, timeout=30).json()
    check("/api/key POST: applied + persisted to .env",
          r.get("ok") and r.get("persisted") and
          open(env_file, encoding="utf-8").read().strip().endswith("sk-set-via-api"))

    r = requests.post(PROXY + "/api/key", json={"api_key": ""}, timeout=30)
    check("/api/key POST with an empty key -> 400", r.status_code == 400)

    mark = len(SEEN_KEYS)
    r = requests.post(PROXY + "/v1/messages", json=BODY,
                      headers={"x-api-key": "dummy"}, timeout=30)
    check("after dashboard save, dummy falls back to the saved key",
          r.status_code == 200 and SEEN_KEYS[mark:] == ["dummy", "sk-set-via-api"],
          f"seen={SEEN_KEYS[mark:]}")
finally:
    ccproxy.ENV_PATH = saved_env_path
    ccproxy.CONFIG["api_key"] = saved_key
    shutil.rmtree(tmpdir, ignore_errors=True)

# --------------------------------------------------------------------------- #
# 7. optional proxy-token auth (CCPROXY_TOKEN)
# --------------------------------------------------------------------------- #
print("\n=== 7. proxy-token auth (CCPROXY_TOKEN) ===")

os.environ["CCPROXY_TOKEN"] = "sekrit-token"
try:
    r = requests.post(PROXY + "/v1/messages", json=BODY, timeout=30)
    check("no token -> 401", r.status_code == 401)
    r = requests.post(PROXY + "/v1/messages", json=BODY,
                      headers={"X-Proxy-Token": "wrong"}, timeout=30)
    check("wrong token -> 401", r.status_code == 401)
    r = requests.get(PROXY + "/stats.json", timeout=30)
    check("dashboard endpoints also gated", r.status_code == 401)
    r = requests.get(PROXY + "/health", timeout=30)
    check("/health stays open (docker HEALTHCHECK)", r.status_code == 200
          and r.json().get("auth_required") is True)

    mark = len(SEEN_KEYS)
    r = requests.post(PROXY + "/v1/messages", json=BODY,
                      headers={"X-Proxy-Token": "sekrit-token",
                               "x-api-key": "sk-client-valid"}, timeout=30)
    check("X-Proxy-Token accepted; relay key still passthrough",
          r.status_code == 200 and SEEN_KEYS[-1] == "sk-client-valid")

    mark = len(SEEN_KEYS)
    r = requests.post(PROXY + "/v1/messages", json=BODY,
                      headers={"Authorization": "Bearer sekrit-token"}, timeout=30)
    check("Bearer carrying the PROXY token accepted; Bearer NOT used as relay key",
          r.status_code == 200 and SEEN_KEYS[-1] == "sk-config-key",
          f"upstream saw {SEEN_KEYS[-1]}")
finally:
    del os.environ["CCPROXY_TOKEN"]

r = requests.get(PROXY + "/health", timeout=30).json()
check("auth off again after unsetting CCPROXY_TOKEN",
      r.get("auth_required") is False)

# --------------------------------------------------------------------------- #
# 8. isolated subprocess: .env loading, keyless startup, waitress + SSE
# --------------------------------------------------------------------------- #
print("\n=== 8. isolated subprocess (.env load, keyless start, waitress+SSE) ===")

iso = tempfile.mkdtemp(prefix="ccproxy-iso-")
for fn in ("ccproxy.py", "dashboard.py", "config.json"):
    shutil.copy2(os.path.join(HERE, fn), iso)
runner = os.path.join(iso, "run_iso.py")
open(runner, "w", encoding="utf-8").write(
    "import os, sys\n"
    "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
    "os.environ['TARGET_URL'] = 'http://127.0.0.1:8799'\n"
    "os.environ['PORT'] = '8797'\n"
    "os.environ.pop('UPSTREAM_API_KEY', None)\n"
    "import ccproxy\n"
    "ccproxy.serve_app(ccproxy.app, '127.0.0.1', 8797)\n")

env = {k: v for k, v in os.environ.items()
       if k.upper() not in ("UPSTREAM_API_KEY", "TARGET_URL", "PORT", "UI_LANG",
                            "LISTEN_HOST", "CCPROXY_TOKEN", "CCPROXY_SERVER")}
ISO = "http://127.0.0.1:8797"


def start_iso():
    p = subprocess.Popen([sys.executable, runner], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        time.sleep(0.25)
        try:
            requests.get(ISO + "/health", timeout=2)
            return p
        except Exception:
            pass
    return p


try:
    p = start_iso()      # phase A: no .env at all
    h = requests.get(ISO + "/health", timeout=10).json()
    check("subprocess starts KEYLESS (no env, no .env)",
          h.get("ok") and h.get("key_set") is False
          and h.get("client_key_passthrough") is True, str(h))
    mark = len(SEEN_KEYS)
    r = requests.post(ISO + "/v1/messages", json=BODY,
                      headers={"x-api-key": "sk-client-valid"}, timeout=30)
    check("keyless subprocess serves via client-supplied key",
          r.status_code == 200 and SEEN_KEYS[-1] == "sk-client-valid")
    p.terminate()
    p.wait(timeout=10)

    open(os.path.join(iso, ".env"), "w", encoding="utf-8").write(
        "UPSTREAM_API_KEY=sk-from-envfile\n")
    p = start_iso()      # phase B: key from .env
    h = requests.get(ISO + "/health", timeout=10).json()
    check("subprocess loads the key from .env", h.get("key_set") is True, str(h))
    mark = len(SEEN_KEYS)
    r = requests.post(ISO + "/v1/messages", json=BODY, timeout=30)
    check("no client key -> the .env key reaches upstream",
          r.status_code == 200 and SEEN_KEYS[-1] == "sk-from-envfile")

    r = requests.post(ISO + "/v1/messages", json=dict(BODY, stream=True),
                      headers={"x-api-key": "sk-from-envfile"}, timeout=30, stream=True)
    sse_text = "".join(chunk.decode("utf-8", "replace") for chunk in r.iter_content(chunk_size=None))
    check("SSE stream complete through serve_app (waitress when installed)",
          "event: message_start" in sse_text and "event: message_stop" in sse_text
          and "event: ping" in sse_text,
          "waitress" if not os.environ.get("CCPROXY_SERVER") else "flask")
    r.close()
    p.terminate()
    p.wait(timeout=10)
finally:
    shutil.rmtree(iso, ignore_errors=True)

# --------------------------------------------------------------------------- #
print("\n" + "=" * 60)
print(f"RESULT:  {len(PASS)} pass, {len(FAIL)} fail")
if FAIL:
    print("Failed:")
    for f in FAIL:
        print("   -", f)
print("=" * 60)
sys.exit(1 if FAIL else 0)
