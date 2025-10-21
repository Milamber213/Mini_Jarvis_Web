from flask import Flask, request, jsonify, render_template
import os

app = Flask(__name__)

# Replace with your real JARVIS_TOKEN
JARVIS_TOKEN = os.environ.get("JARVIS_TOKEN", "YOUR_JARVIS_TOKEN")

# Homepage route — serves the chat UI
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

# Chat endpoint — called by the frontend

import requests

@app.route("/chat", methods=["POST"])
def chat():
    token = request.headers.get("X-Token", "")
    if token != JARVIS_TOKEN:
        return jsonify({"error": "Invalid token"}), 401

    data = request.get_json()
    user_message = data.get("message", "")

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if not deepseek_key:
        return jsonify({"error": "DeepSeek key missing"}), 500

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {deepseek_key}",
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are Jarvis, an intelligent AI assistant with a witty, respectful tone. Always call the user 'Boss'."},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.7,
            "max_tokens": 200,
        }

        response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload)
        result = response.json()

        reply = result["choices"][0]["message"]["content"]
        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# Run app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
