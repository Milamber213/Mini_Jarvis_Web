from flask import Flask, request, jsonify, send_file, render_template
import requests
import os
from io import BytesIO
from dotenv import load_dotenv
import asyncio
import edge_tts

load_dotenv()
app = Flask(__name__)

# =========================
# ENVIRONMENT VARIABLES
# =========================
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
JARVIS_TOKEN = os.getenv("JARVIS_TOKEN", "12345")

# Jarvis memory state
conversation_history = []
web_access = True  # default ON

# =========================
# HOME PAGE
# =========================
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


# =========================
# CHAT ENDPOINT
# =========================
@app.route("/chat", methods=["POST"])
def chat():
    global conversation_history, web_access

    token = request.headers.get("X-Token", "")
    if token != JARVIS_TOKEN:
        return jsonify({"error": "Invalid token"}), 401

    try:
        data = request.get_json()
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        # -------------------------
        # Command toggles
        # -------------------------
        if "enable web" in user_message.lower():
            web_access = True
            return jsonify({"reply": "Web access re-enabled, Boss."})
        elif "disable web" in user_message.lower():
            web_access = False
            return jsonify({"reply": "Web access disabled, Boss."})
        elif "clear memory" in user_message.lower():
            conversation_history = []
            return jsonify({"reply": "Memory cleared, Boss."})

        # -------------------------
        # Prepare conversation
        # -------------------------
        conversation_history.append({"role": "user", "content": user_message})

        # -------------------------
        # DuckDuckGo (if web ON)
        # -------------------------
        web_summary = ""
        if web_access:
            try:
                search_res = requests.get(
                    "https://api.duckduckgo.com/",
                    params={"q": user_message, "format": "json"},
                    headers={"User-Agent": "JarvisAI/1.0"},
                    timeout=10
                )
                if search_res.status_code == 200:
                    data = search_res.json()
                    if data.get("AbstractText"):
                        web_summary = data["AbstractText"]
            except Exception as e:
                print("DuckDuckGo error:", e)

        # -------------------------
        # DeepSeek Chat
        # -------------------------
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are Jarvis, a witty AI butler who helps Boss with info and tasks."},
            ] + conversation_history + (
                [{"role": "assistant", "content": f"Context from the web: {web_summary}"}] if web_summary else []
            )
        }

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_KEY}",
            "Content-Type": "application/json",
        }

        ds_response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )

        if ds_response.status_code != 200:
            print("DeepSeek Error:", ds_response.text)
            return jsonify({"reply": "I encountered an issue contacting DeepSeek, Boss."})

        answer = ds_response.json()["choices"][0]["message"]["content"]
        conversation_history.append({"role": "assistant", "content": answer})

        return jsonify({"reply": answer})

    except Exception as e:
        print("Chat error:", e)
        return jsonify({"reply": "I encountered an issue processing that, Boss."}), 500


# =========================
# ELEVENLABS + EDGE-TTS VOICE
# =========================
@app.route("/voice", methods=["POST"])
def voice():
    data = request.get_json()
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "No text provided"}), 400

    print("🎧 Incoming voice request...")
    print("🔑 ELEVEN_KEY loaded:", bool(ELEVEN_KEY))

    # -------------------------
    # 1️⃣ Try ElevenLabs first
    # -------------------------
    try:
        if ELEVEN_KEY:
            voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel
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

            res = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers=headers,
                json=payload,
                timeout=20,
            )

            if res.status_code == 200 and res.content:
                print("✅ ElevenLabs voice OK")
                audio_bytes = BytesIO(res.content)
                return send_file(audio_bytes, mimetype="audio/mpeg")
            else:
                print("⚠️ ElevenLabs failed:", res.status_code, res.text)
        else:
            print("⚠️ ELEVENLABS_API_KEY not set")
    except Exception as e:
        print("⚠️ ElevenLabs voice error:", e)

    # -------------------------
    # 2️⃣ Auto-fallback to Edge-TTS
    # -------------------------
    try:
        print("🎙️ Switching to Edge-TTS fallback...")
        async def generate():
            communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
            await communicate.save("fallback.mp3")

        asyncio.run(generate())
        return send_file("fallback.mp3", mimetype="audio/mpeg")

    except Exception as e:
        print("❌ Fallback voice error:", e)
        return jsonify({"error": "Voice generation failed", "details": str(e)}), 500


# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)