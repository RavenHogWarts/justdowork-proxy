import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
from flask import Flask, request, jsonify, Response, stream_with_context
import requests
import json
from datetime import datetime

config = {
    "target_url": "https://api.justwoker.icu",
    "api_key": "",
    "port": 8181,
    "is_running": False
}

app = Flask(__name__)

@app.route('/v1/messages', methods=['POST'])
def proxy_messages():
    body = request.get_json() or {}
    client_wants_stream = body.get('stream', False)
    
    log_message(f"📥 Входящий запрос:")
    log_message(f"   Модель: {body.get('model')}")
    log_message(f"   Stream (от клиента): {client_wants_stream}")
    log_message(f"   Messages count: {len(body.get('messages', []))}")
    
    if body.get('messages'):
        first_msg = body['messages'][0]
        log_message(f"   First msg role: {first_msg.get('role')}")
        log_message(f"   First msg content type: {type(first_msg.get('content')).__name__}")
        if isinstance(first_msg.get('content'), list) and first_msg['content']:
            log_message(f"   First content block: {first_msg['content'][0]}")
    
    # Target server pe stream=false bhejte hain
    body['stream'] = False
    
    headers = {
        "x-api-key": config["api_key"],
        "anthropic-version": request.headers.get("anthropic-version", "2023-06-01"),
        "content-type": "application/json"
    }
    
    log_message(f"📤 Отправка на {config['target_url']} (stream=false)")
    
    try:
        response = requests.post(
            f"{config['target_url']}/v1/messages",
            json=body,
            headers=headers,
            timeout=120
        )
        
        log_message(f"✅ Ответ от сервера: {response.status_code}")
        
        if response.status_code != 200:
            log_message(f"❌ Ошибка от сервера: {response.text[:500]}")
            return Response(response.text, status=response.status_code, mimetype='application/json')
        
        response_data = response.json()
        log_message(f"   Response keys: {list(response_data.keys())}")
        log_message(f"   Content blocks: {len(response_data.get('content', []))}")
        
        if client_wants_stream:
            log_message("🔄 Конвертация в SSE-стрим")
            return Response(
                stream_with_context(generate_sse_stream(response_data)),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Connection': 'keep-alive',
                    'Transfer-Encoding': 'chunked'
                }
            )
        else:
            return jsonify(response_data), 200
            
    except Exception as e:
        log_message(f"❌ Ошибка прокси: {e}")
        import traceback
        log_message(f"   Traceback: {traceback.format_exc()}")
        return jsonify({"error": {"message": str(e)}}), 500

def generate_sse_stream(response_data):
    """Anthropic SSE Stream Generator (Text & Tool Call Compatible)"""
    
    # 1. message_start
    message_start = {
        "type": "message_start",
        "message": {
            "id": response_data.get("id", "msg_proxy"),
            "type": "message",
            "role": response_data.get("role", "assistant"),
            "content": [],
            "model": response_data.get("model", "claude-opus-4-8"),
            "stop_reason": None,
            "stop_sequence": None,
            "usage": response_data.get("usage", {"input_tokens": 0, "output_tokens": 0})
        }
    }
    yield f"event: message_start\ndata: {json.dumps(message_start)}\n\n"
    
    # 2. Process content blocks (text + tool_use)
    content = response_data.get('content', [])
    for i, block in enumerate(content):
        block_type = block.get("type", "text")
        
        if block_type == "text":
            # --- Text Block ---
            block_start = {
                "type": "content_block_start",
                "index": i,
                "content_block": {
                    "type": "text",
                    "text": ""
                }
            }
            yield f"event: content_block_start\ndata: {json.dumps(block_start)}\n\n"
            
            if block.get('text'):
                block_delta = {
                    "type": "content_block_delta",
                    "index": i,
                    "delta": {
                        "type": "text_delta",
                        "text": block['text']
                    }
                }
                yield f"event: content_block_delta\ndata: {json.dumps(block_delta)}\n\n"

        elif block_type == "tool_use":
            # --- Tool Call Block ---
            block_start = {
                "type": "content_block_start",
                "index": i,
                "content_block": {
                    "type": "tool_use",
                    "id": block.get("id", f"toolu_{i}"),
                    "name": block.get("name", ""),
                    "input": {}
                }
            }
            yield f"event: content_block_start\ndata: {json.dumps(block_start)}\n\n"
            
            input_data = block.get("input", {})
            input_json_str = json.dumps(input_data) if isinstance(input_data, dict) else str(input_data)
            
            if input_json_str:
                block_delta = {
                    "type": "content_block_delta",
                    "index": i,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": input_json_str
                    }
                }
                yield f"event: content_block_delta\ndata: {json.dumps(block_delta)}\n\n"

        else:
            # Fallback for unknown block types
            block_start = {
                "type": "content_block_start",
                "index": i,
                "content_block": block
            }
            yield f"event: content_block_start\ndata: {json.dumps(block_start)}\n\n"

        # Stop block for current index
        block_stop = {
            "type": "content_block_stop",
            "index": i
        }
        yield f"event: content_block_stop\ndata: {json.dumps(block_stop)}\n\n"
    
    # 3. message_delta
    message_delta = {
        "type": "message_delta",
        "delta": {
            "stop_reason": response_data.get("stop_reason", "end_turn"),
            "stop_sequence": response_data.get("stop_sequence", None)
        },
        "usage": {
            "output_tokens": response_data.get("usage", {}).get("output_tokens", 0)
        }
    }
    yield f"event: message_delta\ndata: {json.dumps(message_delta)}\n\n"
    
    # 4. message_stop
    message_stop = {
        "type": "message_stop"
    }
    yield f"event: message_stop\ndata: {json.dumps(message_stop)}\n\n"

def log_message(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    log_text.config(state=tk.NORMAL)
    log_text.insert(tk.END, f"[{ts}] {msg}\n")
    log_text.see(tk.END)
    log_text.config(state=tk.DISABLED)

def run_server():
    if config["is_running"]:
        return
    config["is_running"] = True
    log_message("🚀 Сервер запущен")
    app.run(host='127.0.0.1', port=config["port"], debug=False, use_reloader=False)

def toggle_key_visibility():
    if show_key_var.get():
        key_entry.config(show="")
    else:
        key_entry.config(show="*")

def paste_key():
    try:
        clipboard = root.clipboard_get()
        key_entry.delete(0, tk.END)
        key_entry.insert(0, clipboard.strip())
        log_message("📋 Ключ вставлен из буфера")
    except tk.TclError:
        messagebox.showwarning("Буфер пуст", "В буфере обмена нет текста")

def start_server_gui():
    target_url = url_entry.get().strip()
    api_key = key_entry.get().strip()
    port_str = port_entry.get().strip()
    
    if not target_url:
        messagebox.showerror("Ошибка", "Введите Target URL")
        return
    if not api_key:
        messagebox.showerror("Ошибка", "Введите API Key!")
        return
    if not port_str.isdigit():
        messagebox.showerror("Ошибка", "Порт должен быть числом")
        return
        
    config["target_url"] = target_url.rstrip('/')
    config["api_key"] = api_key
    config["port"] = int(port_str)
    
    log_text.config(state=tk.NORMAL)
    log_text.delete(1.0, tk.END)
    log_text.config(state=tk.DISABLED)
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    start_btn.config(state=tk.DISABLED)
    stop_btn.config(state=tk.NORMAL)
    status_label.config(text=f"✅ Запущен на http://127.0.0.1:{config['port']}", foreground="green")
    log_message(f"Конфиг: URL={config['target_url']}, порт={config['port']}, ключ_длина={len(api_key)}")

def stop_server_gui():
    config["is_running"] = False
    start_btn.config(state=tk.NORMAL)
    stop_btn.config(state=tk.DISABLED)
    status_label.config(text="⏹️ Остановлен", foreground="red")
    log_message("⏹️ Сервер остановлен")

# GUI Setup
root = tk.Tk()
root.title("Anthropic Proxy Server")
root.geometry("700x600")
root.configure(padx=15, pady=15)

ttk.Label(root, text="Настройка прокси-сервера", font=('Segoe UI', 12, 'bold')).pack(pady=(0, 10))

ttk.Label(root, text="Target URL:").pack(anchor=tk.W)
url_entry = ttk.Entry(root, width=80)
url_entry.insert(0, "https://api.justwoker.icu")
url_entry.pack(pady=(0, 5), fill=tk.X)

ttk.Label(root, text="API Key:").pack(anchor=tk.W)

key_frame = ttk.Frame(root)
key_frame.pack(fill=tk.X, pady=(0, 5))

key_entry = ttk.Entry(key_frame, width=70, show="*")
key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

paste_btn = ttk.Button(key_frame, text="📋 Вставить", command=paste_key)
paste_btn.pack(side=tk.LEFT, padx=(5, 0))

show_key_var = tk.BooleanVar(value=False)
show_cb = ttk.Checkbutton(key_frame, text="Показать", variable=show_key_var, command=toggle_key_visibility)
show_cb.pack(side=tk.LEFT, padx=(5, 0))

key_entry.bind('<Control-v>', lambda e: paste_key())
key_entry.bind('<Control-V>', lambda e: paste_key())

ttk.Label(root, text="Local Port:").pack(anchor=tk.W)
port_entry = ttk.Entry(root, width=80)
port_entry.insert(0, "8181")
port_entry.pack(pady=(0, 10), fill=tk.X)

btn_frame = ttk.Frame(root)
btn_frame.pack(fill=tk.X, pady=5)

start_btn = ttk.Button(btn_frame, text="🚀 Запустить", command=start_server_gui)
start_btn.pack(side=tk.LEFT, padx=(0, 5))

stop_btn = ttk.Button(btn_frame, text="⏹️ Остановить", command=stop_server_gui, state=tk.DISABLED)
stop_btn.pack(side=tk.LEFT)

status_label = ttk.Label(root, text="⏹️ Не запущен", font=('Segoe UI', 9))
status_label.pack(pady=(5, 0))

ttk.Label(root, text="Лог запросов:", font=('Segoe UI', 9, 'bold')).pack(anchor=tk.W, pady=(10, 5))
log_text = scrolledtext.ScrolledText(root, height=15, font=('Consolas', 9))
log_text.pack(fill=tk.BOTH, expand=True)
log_text.config(state=tk.DISABLED)

if __name__ == "__main__":
    root.mainloop()