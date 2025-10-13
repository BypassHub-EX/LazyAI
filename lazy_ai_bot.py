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
import base64
from discord.ui import View, Button

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# ==== Hugging Face Router Models ====
CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL_NAME = "deepseek-ai/DeepSeek-V3.2-Exp:novita"
IMAGE_URL = "https://api-inference.huggingface.co/models/SG161222/Realistic_Vision_V5.1"
TTS_URL = "https://api-inference.huggingface.co/models/suno/bark"
SPEECH_TO_TEXT_URL = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"

HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

MEMORY_FILE = "memory.json"
user_memory = {}
prefixes = {}
auto_reply_channels = set()
personalities = {}

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
        print(f"[ERROR] Failed to load memory: {e}")

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
        print(f"[ERROR] Failed to save memory: {e}")

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
                content = content.replace("DeepSeek", "LazyAI")
                return content
            else:
                print(f"[ERROR] query_hf {resp.status} - {await resp.text()}")
                return "⚠️ LazyAI is sleepy."

async def generate_image(prompt):
    async with aiohttp.ClientSession() as session:
        async with session.post(IMAGE_URL, headers=HEADERS, json={"inputs": prompt}) as resp:
            if resp.status == 200:
                return await resp.read()
            else:
                print(f"[ERROR] generate_image {resp.status}")
                return None

async def text_to_speech(prompt):
    async with aiohttp.ClientSession() as session:
        async with session.post(TTS_URL, headers=HEADERS, json={"inputs": prompt}) as resp:
            if resp.status == 200:
                return await resp.read()
            else:
                print(f"[ERROR] tts {resp.status}")
                return None

async def speech_to_text(audio_bytes):
    encoded = base64.b64encode(audio_bytes).decode()
    async with aiohttp.ClientSession() as session:
        async with session.post(SPEECH_TO_TEXT_URL, headers=HEADERS, json={"inputs": encoded}) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("text") or ""
            else:
                print(f"[ERROR] stt {resp.status}")
                return ""

async def web_search(query):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.duckduckgo.com/", params={"q": query, "format": "json", "no_redirect": 1}) as resp:
            try:
                data = await resp.json()
                return data.get("AbstractText") or "🔍 No summary found."
            except:
                return "🔍 Error fetching search."

class LazyResponseActions(View):
    def __init__(self, prompt, user_id, memory_snapshot):
        super().__init__(timeout=None)
        self.prompt = prompt
        self.user_id = user_id
        self.memory_snapshot = memory_snapshot

    @discord.ui.button(label="🔄 Regenerate", style=discord.ButtonStyle.primary)
    async def regenerate(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("❌ Not your message.", ephemeral=True)
        await interaction.response.defer()
        msgs = list(self.memory_snapshot)
        msgs.append({"role": "user", "content": self.prompt})
        reply = await query_hf(msgs)
        await interaction.followup.send(f"🧠 {reply}", view=LazyResponseActions(self.prompt, self.user_id, msgs))

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("❌ Not your message.", ephemeral=True)
        await interaction.message.delete()

@bot.event
async def on_ready():
    print(f"🧠 LazyAI is online as {bot.user}.")
    try:
        synced = await tree.sync()
        print(f"[DEBUG] Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"[ERROR] Sync failed: {e}")

@tree.command(name="ask")
@app_commands.describe(prompt="Ask LazyAI anything")
async def ask(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    uid = str(interaction.user.id)
    if uid not in user_memory:
        user_memory[uid] = []
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

@tree.command(name="image")
@app_commands.describe(prompt="Describe the image")
async def image(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    img = await generate_image(prompt)
    if img:
        await interaction.followup.send(file=discord.File(io.BytesIO(img), filename="lazy_image.png"))
    else:
        await interaction.followup.send("⚠️ Image generation failed.")

@tree.command(name="say")
@app_commands.describe(text="What should LazyAI say?")
async def say(interaction: discord.Interaction, text: str):
    await interaction.response.defer()
    audio = await text_to_speech(text)
    if audio:
        await interaction.followup.send(file=discord.File(io.BytesIO(audio), filename="lazy_voice.wav"))
    else:
        await interaction.followup.send("⚠️ Voice generation failed.")

@tree.command(name="search")
@app_commands.describe(query="Search this")
async def search(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    result = await web_search(query)
    await interaction.followup.send(f"🔍 {result}")

@tree.command(name="set-prefix")
@app_commands.describe(prefix="Trigger phrase")
async def set_prefix(interaction: discord.Interaction, prefix: str):
    prefixes[interaction.guild_id] = prefix.lower()
    save_memory()
    await interaction.response.send_message(f"✅ Prefix set: `{prefix}`")

@tree.command(name="set-autoreply-channel")
async def auto_reply(interaction: discord.Interaction):
    auto_reply_channels.add(interaction.channel_id)
    save_memory()
    await interaction.response.send_message("✅ Auto-reply enabled.")

@tree.command(name="clear-memory")
async def clear_memory(interaction: discord.Interaction):
    user_memory.pop(str(interaction.user.id), None)
    save_memory()
    await interaction.response.send_message("🧠 Memory cleared!")

@tree.command(name="change-personality")
@app_commands.describe(personality="Describe personality LazyAI should use")
async def change_personality(interaction: discord.Interaction, personality: str):
    personalities[str(interaction.user.id)] = personality
    save_memory()
    await interaction.response.send_message(f"✅ Personality set: *{personality}*")

@tree.command(name="help")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("""
**LazyAI Slash Commands**
/ask — Ask me anything  
/image — Generate image from text  
/say — Convert text to voice  
/search — Web search  
/set-prefix — Custom prefix  
/set-autoreply-channel — Auto reply in this channel  
/clear-memory — Clear your chat memory  
/change-personality — Set how I speak  
/help — Show this list
""")

@bot.event
async def on_message(message):
    if message.author.bot: return
    uid = str(message.author.id)
    gid = message.guild.id if message.guild else None
    cid = message.channel.id
    if message.attachments:
        for att in message.attachments:
            if att.content_type and att.content_type.startswith("audio"):
                audio_bytes = await att.read()
                text = await speech_to_text(audio_bytes)
                if text:
                    print(f"[DEBUG] Speech input: {text}")
                    await handle_message(message, prompt_override=text)
                    return
    prefix = prefixes.get(gid)
    if cid in auto_reply_channels:
        await handle_message(message)
    elif prefix and message.content.lower().startswith(prefix.lower()):
        await handle_message(message, prompt_override=message.content[len(prefix):].strip())

async def handle_message(message, prompt_override=None):
    prompt = prompt_override or message.content
    uid = str(message.author.id)
    msgs = []
    if uid not in user_memory:
        user_memory[uid] = []
    personality = personalities.get(uid)
    if personality:
        msgs.append({"role": "system", "content": f"Adopt this personality: {personality}"})
    msgs.extend(user_memory[uid][-10:])
    msgs.append({"role": "user", "content": prompt})
    reply = await query_hf(msgs)
    user_memory[uid].append({"role": "user", "content": prompt})
    user_memory[uid].append({"role": "assistant", "content": reply})
    save_memory()
    await message.channel.send(f"🧠 {reply}", view=LazyResponseActions(prompt, uid, msgs))

bot.run(DISCORD_TOKEN)
