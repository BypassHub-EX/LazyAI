import discord
from discord import app_commands
from discord.ext import commands
import os
import aiohttp
from dotenv import load_dotenv
from langdetect import detect
import json
import io
import shutil
from discord.ui import View, Button

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# ===== Model / API endpoints (you may need to adjust) =====
CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL_NAME = "deepseek-ai/DeepSeek-V3.2-Exp:novita"

IMAGE_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2"
TTS_URL = "https://api-inference.huggingface.co/models/suno/bark"
SPEECH_TO_TEXT_URL = "https://api-inference.huggingface.co/models/openai/whisper-1"

HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}"
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

MEMORY_FILE = "memory.json"

# In‑memory state loaded from JSON
user_memory = {}
prefixes = {}
auto_reply_channels = set()
personalities = {}  # {user_id: personality instruction}

def load_memory():
    global user_memory, prefixes, auto_reply_channels, personalities
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        user_memory = data.get("user_memory", {})
        prefixes = data.get("prefixes", {})
        auto_reply_channels = set(data.get("auto_reply_channels", []))
        personalities = data.get("personalities", {})
        print("[DEBUG] Memory loaded.")
    except Exception as e:
        print(f"⚠️ Failed to load memory: {e}")
        user_memory = {}
        prefixes = {}
        auto_reply_channels = set()
        personalities = {}

def save_memory():
    data = {
        "user_memory": user_memory,
        "prefixes": prefixes,
        "auto_reply_channels": list(auto_reply_channels),
        "personalities": personalities
    }
    tmp = MEMORY_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.move(tmp, MEMORY_FILE)
        print("[DEBUG] Memory saved.")
    except Exception as e:
        print(f"⚠️ Failed to save memory: {e}")

# Load memory on startup
load_memory()

def detect_language(text):
    try:
        return detect(text)
    except:
        return "en"

async def query_hf(messages):
    payload = {
        "model": MODEL_NAME,
        "messages": messages
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(CHAT_URL, headers=HEADERS, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                # Replace model identity
                content = content.replace("DeepSeek", "LazyAI")
                return content
            else:
                err = await resp.text()
                print(f"[ERROR] query_hf status {resp.status}: {err}")
                return "⚠️ LazyAI is sleepy. Try again later."

async def generate_image(prompt):
    async with aiohttp.ClientSession() as session:
        async with session.post(IMAGE_URL, headers=HEADERS, json={"inputs": prompt}) as resp:
            if resp.status == 200:
                return await resp.read()
            else:
                print(f"[ERROR] generate_image status {resp.status}")
                return None

async def text_to_speech(prompt):
    async with aiohttp.ClientSession() as session:
        async with session.post(TTS_URL, headers=HEADERS, json={"inputs": prompt}) as resp:
            if resp.status == 200:
                return await resp.read()
            else:
                print(f"[ERROR] text_to_speech status {resp.status}")
                return None

async def speech_to_text(audio_bytes):
    async with aiohttp.ClientSession() as session:
        payload = {"inputs": base64.b64encode(audio_bytes).decode()}  # may need adjusting
        async with session.post(SPEECH_TO_TEXT_URL, headers=HEADERS, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                text = data.get("text") or ""
                return text
            else:
                print(f"[ERROR] speech_to_text status {resp.status}")
                return ""

async def web_search(query: str):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.duckduckgo.com/", params={"q": query, "format": "json", "no_redirect": 1}) as resp:
            try:
                data = await resp.json()
            except:
                text = await resp.text()
                print(f"[ERROR] web_search parse JSON: {text}")
                return "🔍 Couldn't fetch search."
            return data.get("AbstractText") or "🔍 No summary found."

# === Buttons for regenerate & delete ===
class LazyResponseActions(View):
    def __init__(self, prompt, user_id, memory_snapshot):
        super().__init__(timeout=None)
        self.prompt = prompt
        self.user_id = user_id
        self.memory_snapshot = memory_snapshot  # copy of messages before reply

    @discord.ui.button(label="🔄 Regenerate", style=discord.ButtonStyle.primary)
    async def regenerate(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("❌ You can’t regenerate for someone else.", ephemeral=True)
        await interaction.response.defer()
        # Use snapshot + prompt to regenerate
        msgs = list(self.memory_snapshot)
        msgs.append({"role": "user", "content": self.prompt})
        reply = await query_hf(msgs)
        await interaction.followup.send(f"🧠 {reply}", view=LazyResponseActions(self.prompt, self.user_id, msgs))

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("❌ You can’t delete this.", ephemeral=True)
        await interaction.message.delete()

@bot.event
async def on_ready():
    print(f"🧠 LazyAI is online as {bot.user}.")
    try:
        synced = await tree.sync()
        print(f"[DEBUG] Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"[ERROR] Command sync failed: {e}")

# --- Slash commands ---

@tree.command(name="ask", description="Ask LazyAI anything.")
@app_commands.describe(prompt="Your question")
async def slash_ask(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    uid = str(interaction.user.id)
    if uid not in user_memory:
        user_memory[uid] = []
    # Add system message if user has personality
    msgs = []
    personality = personalities.get(uid)
    if personality:
        msgs.append({"role": "system", "content": f"Adopt this personality: {personality}"})
    msgs.extend(user_memory[uid][-10:])
    msgs.append({"role": "user", "content": prompt})

    reply = await query_hf(msgs)
    user_memory[uid].append({"role": "user", "content": prompt})
    user_memory[uid].append({"role": "assistant", "content": reply})
    save_memory()

    await interaction.followup.send(f"🧠 {reply}", view=LazyResponseActions(prompt, uid, msgs))

@tree.command(name="image", description="Generate image from text")
@app_commands.describe(prompt="Describe the image")
async def slash_image(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    img = await generate_image(prompt)
    if img:
        await interaction.followup.send(file=discord.File(io.BytesIO(img), filename="lazy_image.png"))
    else:
        await interaction.followup.send("⚠️ Image generation failed.")

@tree.command(name="say", description="Convert text to voice")
@app_commands.describe(text="What should LazyAI say?")
async def slash_say(interaction: discord.Interaction, text: str):
    await interaction.response.defer()
    audio = await text_to_speech(text)
    if audio:
        await interaction.followup.send(file=discord.File(io.BytesIO(audio), filename="lazy_voice.wav"))
    else:
        await interaction.followup.send("⚠️ Voice generation failed.")

@tree.command(name="search", description="Web search result")
@app_commands.describe(query="Search this")
async def slash_search(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    result = await web_search(query)
    await interaction.followup.send(f"🔍 {result}")

@tree.command(name="set-prefix", description="Set a custom prefix")
@app_commands.describe(prefix="Trigger prefix, e.g. 'hey lazy'")
async def slash_set_prefix(interaction: discord.Interaction, prefix: str):
    prefixes[interaction.guild_id] = prefix.lower()
    save_memory()
    await interaction.response.send_message(f"✅ Prefix set to `{prefix}`")

@tree.command(name="set-autoreply-channel", description="Enable auto reply in this channel")
async def slash_auto(interaction: discord.Interaction):
    auto_reply_channels.add(interaction.channel_id)
    save_memory()
    await interaction.response.send_message("✅ Auto-reply enabled.")

@tree.command(name="clear-memory", description="Clear your memory")
async def slash_clear(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    user_memory.pop(uid, None)
    save_memory()
    await interaction.response.send_message("🧠 Memory cleared!")

@tree.command(name="change-personality", description="Change how LazyAI speaks to you")
@app_commands.describe(personality="Describe the personality you want")
async def slash_personality(interaction: discord.Interaction, personality: str):
    uid = str(interaction.user.id)
    personalities[uid] = personality
    save_memory()
    await interaction.response.send_message(f"✅ Personality set: *{personality}*")

@tree.command(name="help", description="Show commands")
async def slash_help(interaction: discord.Interaction):
    await interaction.response.send_message("""
**LazyAI Commands**

/ask — Ask LazyAI  
/image — Generate image  
/say — Convert text to speech  
/search — Web search  
/set-prefix — Custom prefix  
/set-autoreply-channel — Enable auto replies in this channel  
/clear-memory — Forget chat history  
/change-personality — Set how I talk to you  
/help — This message  
""")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = str(message.author.id)
    content = message.content.strip()
    gid = message.guild.id if message.guild else None
    cid = message.channel.id

    # Detect audio attachments
    if message.attachments:
        for att in message.attachments:
            if att.content_type and att.content_type.startswith("audio"):
                audio_bytes = await att.read()
                text = await speech_to_text(audio_bytes)
                if text:
                    print(f"[DEBUG] Got speech input: {text}")
                    await handle_message(message, prompt_override=text)
                    return

    # Auto-reply in channel
    if cid in auto_reply_channels:
        await handle_message(message)
        return

    # Prefix-based trigger
    prefix = prefixes.get(gid)
    if prefix and content.lower().startswith(prefix.lower()):
        stripped = content[len(prefix):].strip()
        await handle_message(message, prompt_override=stripped)

async def handle_message(message, prompt_override=None):
    prompt = prompt_override if prompt_override else message.content
    uid = str(message.author.id)
    msgs = []
    personality = personalities.get(uid)
    if personality:
        msgs.append({"role": "system", "content": f"Adopt this personality: {personality}"})
    msgs.extend(user_memory.get(uid, [])[-10:])
    msgs.append({"role": "user", "content": prompt})

    reply = await query_hf(msgs)

    # Save memory
    if uid not in user_memory:
        user_memory[uid] = []
    user_memory[uid].append({"role": "user", "content": prompt})
    user_memory[uid].append({"role": "assistant", "content": reply})
    save_memory()

    sent = await message.channel.send(f"🧠 {reply}", view=LazyResponseActions(prompt, uid, msgs))
    return sent

bot.run(DISCORD_TOKEN)
