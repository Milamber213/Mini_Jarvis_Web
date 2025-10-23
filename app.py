from flask import Flask, request, jsonify, render_template, Response, send_file
import requests
import os
from io import BytesIO
from dotenv import load_dotenv
import asyncio
import edge_tts

# ====================================
# ENVIRONMENT & INITIALIZATION
# ====================================
load_dotenv()
app = Flask(__name__)

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
JARVIS_TOKEN = os.getenv("JARVIS_TOKEN", "12345")

conversation_history = []
web_access = True  # default ON

# ====================================
# HOME ROUTE
# ====================================
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

# ====================================
# CHAT ROUTE
# ====================================
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

        # Command toggles
        if "enable web" in user_message.lower():
            web_access = True
            return jsonify({"reply": "Web access re-enabled, Boss."})
        elif "disable web" in user_message.lower():
            web_access = False
            return jsonify({"reply": "Web access disabled, Boss."})
        elif "clear memory" in user_message.lower():
            conversation_history = []
            return jsonify({"reply": "Memory cleared, Boss."})

        conversation_history.append({"role": "user", "content": user_message})

        # DuckDuckGo search if enabled
        web_summary = ""
        if web_access:
            try:
                res = requests.get(
                    "https://api.duckduckgo.com/",
                    params={"q": user_message, "format": "json"},
                    headers={"User-Agent": "JarvisAI/1.0"},
                    timeout=10,
                )
                if res.status_code == 200:
                    data = res.json()
                    if data.get("AbstractText"):
                        web_summary = data["AbstractText"]
            except Exception as e:
                print("DuckDuckGo error:", e)

        # DeepSeek API call
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are Jarvis, a witty AI butler who assists Boss with tasks and info."},
            ] + conversation_history + (
                [{"role": "assistant", "content": f"Context from the web: {web_summary}"}] if web_summary else []
            )
        }

        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=25,
        )

        if response.status_code != 200:
            print("DeepSeek Error:", response.text)
            return jsonify({"reply": "I encountered an issue contacting DeepSeek, Boss."})

        reply = response.json()["choices"][0]["message"]["content"]
        conversation_history.append({"role": "assistant", "content": reply})

        return jsonify({"reply": reply})

    except Exception as e:
        print("Chat error:", e)
        return jsonify({"reply": "I encountered an issue processing that, Boss."}), 500

# ====================================
# VOICE ROUTE (RENDER-SAFE)
# ====================================
@app.route("/voice", methods=["POST"])
def voice():
    data = request.get_json()
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "No text provided"}), 400

    print("🎧 Incoming voice request...")
    print("🔑 ELEVEN_KEY loaded:", bool(ELEVEN_KEY))

    # --- ElevenLabs Primary ---
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
                timeout=25,
            )

            if res.status_code == 200 and res.content:
                print("✅ ElevenLabs voice OK")

                audio_data = res.content
                resp = Response(audio_data, mimetype="audio/mpeg")
                resp.headers["Content-Length"] = str(len(audio_data))
                resp.headers["Cache-Control"] = "no-cache"
                resp.headers["Accept-Ranges"] = "bytes"
                resp.headers["Content-Disposition"] = "inline; filename=jarvis.mp3"
                return resp
            else:
                print("⚠️ ElevenLabs failed:", res.status_code, res.text)
        else:
            print("⚠️ ELEVENLABS_API_KEY not set")
    except Exception as e:
        print("⚠️ ElevenLabs voice error:", e)

    # --- Edge-TTS Fallback ---
    try:
        print("❌ Skipping Edge-TTS fallback on Render (network restricted)")
        return jsonify({"error": "Voice unavailable. ElevenLabs failed and Edge-TTS blocked."}), 500

        async def generate():
            communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
            await communicate.save("fallback.mp3")

        asyncio.run(generate())

        with open("fallback.mp3", "rb") as f:
            audio_data = f.read()

        resp = Response(audio_data, mimetype="audio/mpeg")
        resp.headers["Content-Length"] = str(len(audio_data))
        resp.headers["Cache-Control"] = "no-cache"
        resp.headers["Accept-Ranges"] = "bytes"
        resp.headers["Content-Disposition"] = "inline; filename=fallback.mp3"
        print("✅ Edge-TTS fallback ready")
        return resp

    except Exception as e:
        print("❌ Fallback voice error:", e)
        return jsonify({"error": "Voice generation failed", "details": str(e)}), 500

# ====================================
# TEST VOICE ROUTE
# ====================================
@app.route("/test-voice", methods=["GET"])
def test_voice():
    """Quick browser-based voice test for diagnostics."""
    try:
        text = "Hello Boss. This is Jarvis voice system online."
        if ELEVEN_KEY:
            print("🎧 Running test voice via ElevenLabs...")
            voice_id = "21m00Tcm4TlvDq8ikWAM"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": ELEVEN_KEY,
            }
            payload = {"text": text, "model_id": "eleven_monolingual_v1"}
            res = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers=headers,
                json=payload,
                timeout=25,
            )
            if res.status_code == 200 and res.content:
                print("✅ ElevenLabs test OK")
                resp = Response(res.content, mimetype="audio/mpeg")
                resp.headers["Content-Disposition"] = "inline; filename=test.mp3"
                return resp
            else:
                print("⚠️ ElevenLabs test failed:", res.status_code, res.text)
        print("🎙️ Falling back to Edge-TTS for test...")
        async def generate():
            communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
            await communicate.save("test_fallback.mp3")
        asyncio.run(generate())
        with open("test_fallback.mp3", "rb") as f:
            data = f.read()
        resp = Response(data, mimetype="audio/mpeg")
        resp.headers["Content-Disposition"] = "inline; filename=test_fallback.mp3"
        print("✅ Edge-TTS test fallback ready")
        return resp
    except Exception as e:
        print("❌ Test voice error:", e)
        return jsonify({"error": str(e)}), 500

# ====================================
# RUN APP
# ====================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
