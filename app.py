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
@app.route("/chat", methods=["POST"])
def chat():
    token = request.headers.get("X-Token", "")
    if token != JARVIS_TOKEN:
        return jsonify({"error": "Invalid token"}), 401

    data = request.get_json()
    user_message = data.get("message", "")

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Mock or AI response (use DeepSeek/OpenAI later)
    reply = f"Jarvis says: {user_message}"

    return jsonify({"reply": reply})

# Run app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
