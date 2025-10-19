# jarvis_app.py
import os
import requests
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

# Load local .env (for local testing)
load_dotenv()

# Config
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")  # set this in .env or Railway env
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
SECRET_TOKEN = os.getenv("JARVIS_TOKEN", "changeme123")  # simple token auth for the client

app = Flask(__name__)

# Simple mobile-friendly chat UI served from the same file (no static files)
INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Jarvis (Web)</title>
  <style>
    body{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial; margin:0;padding:0;background:#f2f4f7}
    .wrap{max-width:700px;margin:22px auto;padding:12px}
    #chat{background:#fff;border-radius:8px;padding:12px;height:60vh;overflow:auto;border:1px solid #e1e4e8}
    .msg{margin:8px 0}
    .user{color:#0b4; text-align:right}
    .bot{color:#036; text-align:left}
    #controls{display:flex;margin-top:12px;gap:8px}
    input[type=text]{flex:1;padding:10px;border-radius:6px;border:1px solid #cfd6dc}
    button{padding:10px 14px;border-radius:6px;border:none;background:#1f6feb;color:white}
    small{color:#666}
  </style>
</head>
<body>
  <div class="wrap">
    <h2>Jarvis (Web) — Mobile Ready</h2>
    <div id="chat"></div>
    <div id="controls">
      <input id="cmd" type="text" placeholder="Type message to Jarvis (Phone or Desktop)">
      <button id="send">Send</button>
    </div>
    <p><small>Tip: set your token in the JS below before using (dev only). For production, set server env variable JARVIS_TOKEN and Railway env var.</small></p>
  </div>

<script>
const chat = document.getElementById('chat');
const cmd = document.getElementById('cmd');
const send = document.getElementById('send');

// For convenience during local test only: paste your token here (NOT recommended for production)
const CLIENT_TOKEN = "sk-8cd22412779a428ca19c3112fcf335bc";

function addMessage(text, cls){
  const d = document.createElement('div');
  d.className = 'msg ' + cls;
  d.textContent = text;
  chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight;
}

send.onclick = async () => {
  const value = cmd.value.trim();
  if (!value) return;
  addMessage("You: " + value, 'user');
  cmd.value = '';
  addMessage("Jarvis is thinking...", 'bot');

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ token: CLIENT_TOKEN, message: value })
    });
    const data = await res.json();
    // remove the "thinking..."
    chat.lastChild && chat.lastChild.remove();
    if (data.error) {
      addMessage("Error: " + data.error, 'bot');
    } else {
      addMessage("Jarvis: " + data.reply, 'bot');
    }
  } catch (e) {
    chat.lastChild && chat.lastChild.remove();
    addMessage("Network error: " + e.message, 'bot');
  }
};
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/chat", methods=["POST"])
def chat():
    """
    Expects JSON: { "token": "<client token>", "message": "Hello Jarvis" }
    Returns JSON: { "reply": "..." } or { "error": "..." }
    """
    data = request.get_json(force=True)
    token = data.get("token", "")
    if token != SECRET_TOKEN:
        return jsonify({"error": "Unauthorized (invalid token)"}), 401

    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    # Build messages payload for DeepSeek (system + user)
    messages = [
        {"role": "system", "content": "You are Jarvis, a witty, helpful AI butler who calls the user 'Boss'."},
        {"role": "user", "content": message}
    ]

    # Prepare request to DeepSeek
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",   # recommended chat model name from docs
        "messages": messages,
        "max_tokens": 512,
        "temperature": 0.7,
        "stream": False
    }

    # Send to DeepSeek
    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        return jsonify({"error": f"DeepSeek request failed: {e}"}), 502

    try:
        j = resp.json()
        # DeepSeek returns choices similar to chat completion APIs
        # try to read the assistant text from choices[0].message.content or choices[0].text
        reply = None
        if isinstance(j, dict):
            choices = j.get("choices", [])
            if choices and isinstance(choices, list):
                # try typical shapes
                first = choices[0]
                # case: choice has "message" with "content"
                if isinstance(first.get("message"), dict) and "content" in first["message"]:
                    reply = first["message"]["content"]
                # case: choice has "delta" stream object with "content" pieces -> join (fallback)
                elif "text" in first:
                    reply = first.get("text")
                elif "delta" in first and isinstance(first["delta"], dict):
                    # stream-chunk style — gather content fields if present
                    reply = first["delta"].get("content") or first["delta"].get("text")
        if not reply:
            # fallback: stringify the whole response
            reply = j.get("choices", [{}])[0].get("message", {}).get("content") or str(j)
    except Exception as e:
        return jsonify({"error": f"Failed parsing DeepSeek response: {e}"}), 502

    return jsonify({"reply": reply})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # For local testing, ensure DEEPSEEK_API_KEY and JARVIS_TOKEN env vars set
    if not DEEPSEEK_API_KEY:
        print("WARNING: DEEPSEEK_API_KEY is empty. Set env var DEEPSEEK_API_KEY or use .env")
    app.run(host="0.0.0.0", port=port)
