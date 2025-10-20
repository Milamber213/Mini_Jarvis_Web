import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Load environment variables
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
JARVIS_TOKEN = os.getenv("JARVIS_TOKEN", "")

# Test route to verify the server works
@app.route("/", methods=["GET"])
def home():
    return "✅ Jarvis is running on Render!", 200

# Main Chat endpoint
@app.route("/chat", methods=["POST"])
def chat():
    # Check access token
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
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are Jarvis."},
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

# IMPORTANT: Render requires this run block
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render assigns PORT here
    if not DEEPSEEK_API_KEY:
        print("WARNING: DEEPSEEK_API_KEY is empty. Set it in Render > Environment.")
    app.run(host="0.0.0.0", port=port)
