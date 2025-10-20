import os
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# Load environment variables
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
JARVIS_TOKEN = os.getenv("JARVIS_TOKEN", "")
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")


# Serve the chat UI
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


# Chat endpoint (AJAX call from frontend)
@app.route("/chat", methods=["POST"])
def chat():
    token = request.headers.get("X-Token", "")
    if token != JARVIS_TOKEN:
        return jsonify({"error": "Invalid token"}), 401

    data = request.get_json()
    user_message = data.get("message", "")

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Call DeepSeek API
    try:
        response = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are Jarvis, an AI assistant with a butler-like personality. Call the user 'Boss'."},
                    {"role": "user", "content": user_message}
                ]
            },
            timeout=30
        )

        if response.status_code != 200:
            return jsonify({"error": f"DeepSeek request failed: {response.text}"}), 500

        result = response.json()
        reply = result["choices"][0]["message"]["content"]
        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Render requires this
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    if not DEEPSEEK_API_KEY:
        print("WARNING: DEEPSEEK_API_KEY is empty. Set it in Render > Environment.")
    print(f"Starting Jarvis on port {port}...")
    app.run(host="0.0.0.0", port=port)
