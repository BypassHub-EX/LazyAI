# ==========================================
# LazyAI WhatsApp Bot (Infobip Integration)
# Developed by Xohus Interactive LLC
# Shared memory + personality system with Discord
# ==========================================

import os
import json
import logging
import aiohttp
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import asyncio

# ===============================
# LOAD ENVIRONMENT
# ===============================
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
INFOBIP_API_KEY = os.getenv("INFOBIP_API_KEY")
INFOBIP_URL = os.getenv("INFOBIP_URL")  # e.g. https://4e6qy8.api.infobip.com
WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER")  # e.g. 447860088970
MEMORY_FILE = "memory.json"

# ===============================
# CONFIGURE LOGGING
# ===============================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ===============================
# APP & CONFIG
# ===============================
app = Flask(__name__)
API_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL_NAME = "deepseek-ai/DeepSeek-V3.2-Exp:novita"
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

# ===============================
# MEMORY SYSTEM
# ===============================
if not os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "w") as f:
        json.dump({"user_memory": {}, "user_personalities": {}}, f, indent=2)

def load_memory():
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_memory(data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ===============================
# QUERY HUGGINGFACE ROUTER
# ===============================
async def query_lazyai(messages, model="LazyV.----", personality="default"):
    system_prompt = {
        "role": "system",
        "content": (
            f"You are LazyAI (model {model}), a casual, human-like AI assistant "
            f"developed by Xohus Interactive LLC (xohus.me). "
            f"Respond naturally, without changing languages. Personality: {personality}. "
            f"Be conversational and adaptive."
        )
    }

    payload = {"model": MODEL_NAME, "messages": [system_prompt] + messages[-10:]}

    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, headers=HEADERS, json=payload) as resp:
            if resp.status == 200:
                result = await resp.json()
                try:
                    return result["choices"][0]["message"]["content"]
                except Exception:
                    return "⚠️ LazyAI had a small hiccup while thinking."
            else:
                err = await resp.text()
                logging.error(f"[HF ERROR] {resp.status}: {err}")
                return "⚠️ LazyAI couldn’t reach the model right now."

# ===============================
# SEND MESSAGE VIA INFOBIP
# ===============================
async def send_whatsapp_message(to, text):
    message_data = {
        "messages": [{
            "from": WHATSAPP_NUMBER,
            "to": to,
            "content": {"text": text}
        }]
    }

    headers = {
        "Authorization": f"App {INFOBIP_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{INFOBIP_URL}/whatsapp/1/message/text", headers=headers, json=message_data) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logging.error(f"[INFOBIP ERROR] {resp.status}: {error_text}")
            else:
                logging.info(f"[SENT] Message sent to {to}")

# ===============================
# HANDLE INCOMING WEBHOOK
# ===============================
@app.route("/whatsapp-webhook", methods=["POST"])
def whatsapp_webhook():
    data = request.json
    logging.info(f"[RECEIVED] {json.dumps(data, indent=2)}")

    try:
        # Extract sender info
        message = data["results"][0]["message"]["text"]["body"]
        phone = data["results"][0]["from"]
        asyncio.run(handle_message(phone, message))
    except Exception as e:
        logging.error(f"[ERROR] Failed to process message: {e}")

    return jsonify({"status": "received"}), 200

# ===============================
# HANDLE MESSAGE LOGIC
# ===============================
async def handle_message(phone, text):
    memory = load_memory()
    user_key = f"whatsapp:{phone}"

    user_memory = memory.get("user_memory", {})
    user_personalities = memory.get("user_personalities", {})

    if user_key not in user_memory:
        user_memory[user_key] = []

    personality = user_personalities.get(user_key, "LazyV.---- Default Personality")

    user_memory[user_key].append({"role": "user", "content": text})
    reply = await query_lazyai(user_memory[user_key], model="LazyV.----", personality=personality)
    user_memory[user_key].append({"role": "assistant", "content": reply})

    memory["user_memory"] = user_memory
    save_memory(memory)

    await send_whatsapp_message(phone, reply)
    logging.info(f"[REPLY] {phone} → {reply[:120]}...")

# ===============================
# START FLASK APP
# ===============================
if __name__ == "__main__":
    logging.info("🚀 LazyAI WhatsApp Bot by Xohus Interactive LLC is now running.")
    app.run(host="0.0.0.0", port=8080)
