import os
import json
from datetime import datetime
import requests
from flask import Flask, request, Response, stream_with_context

app = Flask(__name__)

TARGET = os.environ.get("TARGET_URL", "https://api.justwoker.icu").rstrip("/")
KEY = os.environ.get("UPSTREAM_API_KEY", "")
PORT = int(os.environ.get("PORT", "8181"))
LOG = "debug_log.txt"
DUMP_DIR = "debug_dump"
os.makedirs(DUMP_DIR, exist_ok=True)
counter = {"n": 0}


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def head(x, n=300):
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
    return s[:n].replace("\n", "\\n")


@app.route("/v1/messages", methods=["POST"])
def proxy():
    counter["n"] += 1
    n = counter["n"]
    body = request.get_json(silent=True) or {}
    wants_stream = bool(body.get("stream"))

    tools = body.get("tools") or []
    msgs = body.get("messages", [])
    last = msgs[-1] if msgs else {}

    log(f"===== REQUEST #{n} =====")
    log(f"client user-agent : {request.headers.get('user-agent')}")
    log(f"anthropic-beta    : {request.headers.get('anthropic-beta')}")
    log(f"model / stream    : {body.get('model')} / {wants_stream}")
    log(f"top-level keys    : {list(body.keys())}")
    log(f"tools count       : {len(tools)}")
    log(f"tool names        : {[t.get('name') for t in tools][:30]}")
    log(f"system (first 300): {head(body.get('system', ''))}")
    log(f"messages count    : {len(msgs)} | last role: {last.get('role')}")
    log(f"last msg (first 200): {head(last.get('content', ''), 200)}")

    with open(f"{DUMP_DIR}/req_{n}.json", "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)

    # thinking/context fields hata do, tools ko jaisa hai waisa rehne do
    for k in ("thinking", "thinking_budget", "output_config",
              "context_management", "mcp_servers"):
        body.pop(k, None)
    body["stream"] = False

    headers = {
        "x-api-key": KEY,
        "anthropic-version": request.headers.get("anthropic-version", "2023-06-01"),
        "content-type": "application/json",
    }

    try:
        r = requests.post(f"{TARGET}/v1/messages", json=body, headers=headers, timeout=600)
    except Exception as e:
        log(f"PROXY ERROR: {e}")
        return Response(json.dumps({"error": {"message": str(e)}}), status=500,
                        content_type="application/json")

    log(f"upstream status   : {r.status_code}")
    if r.status_code != 200:
        log(f"upstream error    : {r.text[:500]}")
        return Response(r.text, status=r.status_code, content_type="application/json")

    msg = r.json()
    blocks = msg.get("content", [])
    log(f"response blocks   : {[b.get('type') for b in blocks]}")
    log(f"stop_reason       : {msg.get('stop_reason')}")
    log(f"usage             : {msg.get('usage')}")
    for b in blocks:
        if b.get("type") == "tool_use":
            log(f"TOOL_USE          : {b.get('name')} {head(b.get('input'), 200)}")
        elif b.get("type") == "text":
            log(f"text (first 300)  : {head(b.get('text', ''))}")
    with open(f"{DUMP_DIR}/resp_{n}.json", "w", encoding="utf-8") as f:
        json.dump(msg, f, ensure_ascii=False, indent=2)

    if not wants_stream:
        return Response(r.text, status=200, content_type="application/json")

    def gen():
        usage = msg.get("usage", {})
        start = dict(msg)
        start["content"] = []
        start["stop_reason"] = None
        start["usage"] = {"input_tokens": usage.get("input_tokens", 0), "output_tokens": 0}
        yield sse("message_start", {"type": "message_start", "message": start})
        i = 0
        for b in blocks:
            t = b.get("type")
            if t == "text":
                yield sse("content_block_start", {"type": "content_block_start", "index": i,
                          "content_block": {"type": "text", "text": ""}})
                yield sse("content_block_delta", {"type": "content_block_delta", "index": i,
                          "delta": {"type": "text_delta", "text": b.get("text", "")}})
            elif t == "tool_use":
                yield sse("content_block_start", {"type": "content_block_start", "index": i,
                          "content_block": {"type": "tool_use", "id": b.get("id"),
                                            "name": b.get("name"), "input": {}}})
                yield sse("content_block_delta", {"type": "content_block_delta", "index": i,
                          "delta": {"type": "input_json_delta",
                                    "partial_json": json.dumps(b.get("input", {}))}})
            else:
                continue
            yield sse("content_block_stop", {"type": "content_block_stop", "index": i})
            i += 1
        yield sse("message_delta", {"type": "message_delta",
                  "delta": {"stop_reason": msg.get("stop_reason") or "end_turn", "stop_sequence": None},
                  "usage": {"output_tokens": usage.get("output_tokens", 0)}})
        yield sse("message_stop", {"type": "message_stop"})

    return Response(stream_with_context(gen()), status=200,
                    content_type="text/event-stream; charset=utf-8",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    if not KEY:
        raise SystemExit("Pehle: export UPSTREAM_API_KEY='...'")
    open(LOG, "w").close()
    log(f"Debug proxy on http://127.0.0.1:{PORT} -> {TARGET}")
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)