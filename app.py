from flask import Flask, request, jsonify, render_template, send_file
import os
import requests
from io import BytesIO
import re

app = Flask(__name__)

# 🔑 Environment keys
JARVIS_TOKEN = os.environ.get("JARVIS_TOKEN", "YOUR_JARVIS_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
ELEVEN_KEY = os.environ.get("ELEVENLABS_API_KEY")

# 🧠 Short-term memory and web mode flag
conversation = []
WEB_MODE = True  # Default: web access ON


# -------------------------
# Helper Functions
# -------------------------

def needs_web_search(text):
    """Detect if a message likely needs real-time info"""
    keywords = ["latest", "today", "current", "news", "update", "price", "recent", "trend", "who won", "when is"]
    return any(k in text.lower() for k in keywords)


def get_web_results(query):
    """Fetch summary info from DuckDuckGo (no API key required)"""
    try:
        clean_q = re.sub(r"[^a-zA-Z0-9 ]", "", query)
        url = f"https://api.duckduckgo.com/?q={clean_q}&format=json"
        resp = requests.get(url, timeout=8)
        data = resp.json()

        # Priority 1: abstract text
        if data.get("AbstractText"):
            return data["AbstractText"]

        # Priority 2: related topics
        elif data.get("RelatedTopics"):
            snippets = [t.get("Text", "") for t in data["RelatedTopics"] if isinstance(t, dict)]
            if snippets:
                return " ".join(snippets[:3])

        # Nothing found
        return "I couldn’t find much about that online, Boss."

    except Exception as e:
        print("Web search error:", e)
        return "Apologies, Boss — I had trouble reaching the web service."


# -------------------------
# Routes
# -------------------------

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    global conversation, WEB_MODE
    token = request.headers.get("X-Token", "")
    if token != JARVIS_TOKEN:
        return jsonify({"error": "Invalid token"}), 401

    data = request.get_json()
    user_message = data.get("message", "")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # 🧠 Record user message
    conversation.append({"role": "user", "content": user_message})

    # 🎚️ Handle toggle commands
    if "disable web" in user_message.lower():
        WEB_MODE = False
        return jsonify({"reply": "Understood, Boss. Web access disabled."})
    elif "enable web" in user_message.lower():
        WEB_MODE = True
        return jsonify({"reply": "Web access re-enabled, Boss. I’m back online."})

    # 🌐 Web access if enabled and needed
    web_summary = ""
    if WEB_MODE and needs_web_search(user_message):
        web_summary = get_web_results(user_message)
        conversation.append({
            "role": "system",
            "content": f"Fresh web information: {web_summary}"
        })

    try:
        # Choose which brain to use
        use_openai = (needs_web_search(user_message) or WEB_MODE) and OPENAI_KEY

        if use_openai:
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_KEY}"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": (
                    [{"role": "system", "content": "You are Jarvis, a witty, intelligent AI assistant who calls the user 'Boss'."}]
                    + conversation[-10:]
                ),
                "temperature": 0.7,
            }
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        else:
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_KEY}"}
            payload = {
                "model": "deepseek-chat",
                "messages": (
                    [{"role": "system", "content": "You are Jarvis, a witty, intelligent AI assistant who calls the user 'Boss'."}]
                    + conversation[-10:]
                ),
                "temperature": 0.7,
            }
            response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload)

        result = response.json()

        # Graceful fallback if API fails
        if "choices" not in result or not result["choices"]:
            reply = "I encountered an issue processing that, Boss. Please try again."
        else:
            reply = result["choices"][0]["message"]["content"]

        conversation.append({"role": "assistant", "content": reply})
        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"error": f"System error: {str(e)}"}), 500


# 🔊 ElevenLabs Voice route
@app.route("/voice", methods=["POST"])
def voice():
    data = request.get_json()
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "No text provided"}), 400

    if not ELEVEN_KEY:
        return jsonify({"error": "Missing ElevenLabs API key"}), 500

    try:
        voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel (default)
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVEN_KEY,
        }
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }

        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers=headers,
            json=payload,
        )

        # 🔎 Check ElevenLabs result
        if response.status_code != 200:
            print("TTS failed:", response.text)
            # 👇 Edge-TTS fallback (sync version)
            try:
                import edge_tts
                import asyncio

                async def generate_fallback():
                    communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
                    await communicate.save("fallback.mp3")

                asyncio.run(generate_fallback())
                return send_file("fallback.mp3", mimetype="audio/mpeg")

            except Exception as e:
                print("Fallback TTS failed:", e)
                return jsonify({"error": "TTS failed", "details": str(e)}), 500

        audio_bytes = BytesIO(response.content)
        return send_file(audio_bytes, mimetype="audio/mpeg")

    except Exception as e:
        print("Voice route error:", e)
        return jsonify({"error": str(e)}), 500


# 🧩 Server Start
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
