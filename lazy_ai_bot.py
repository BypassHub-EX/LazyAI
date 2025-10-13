import os
import discord
import aiohttp
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import json
from langdetect import detect

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

API_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL_NAME = "deepseek-ai/DeepSeek-V3.2-Exp:novita"
MEMORY_FILE = "memory.json"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

# =====================================
# MEMORY LOAD / SAVE
# =====================================
def load_memory():
    global user_memory, prefixes, auto_reply_channels
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        user_memory = data.get("user_memory", {})
        prefixes = data.get("prefixes", {})
        auto_reply_channels = set(data.get("auto_reply_channels", []))
        print("[INFO] Memory loaded successfully.")
    except Exception as e:
        print(f"[WARN] Memory load failed: {e}")
        user_memory, prefixes = {}, {}
        auto_reply_channels = set()

def save_memory():
    try:
        data = {
            "user_memory": user_memory,
            "prefixes": prefixes,
            "auto_reply_channels": list(auto_reply_channels),
        }
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("[INFO] Memory saved.")
    except Exception as e:
        print(f"[ERROR] Failed to save memory: {e}")

# Load memory at startup
load_memory()

# =====================================
# UTILITIES
# =====================================
def detect_language(text):
    try:
        return detect(text)
    except:
        return "en"

def clean_response(raw, prompt):
    try:
        response = raw["choices"][0]["message"]["content"]
        return response.replace(prompt, "").replace("DeepSeek", "LazyAI").strip()
    except:
        return "⚠️ LazyAI couldn’t understand the reply."

# =====================================
# CORE HF QUERY
# =====================================
async def query_hf(messages):
    payload = {"model": MODEL_NAME, "messages": messages}
    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, headers=HEADERS, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                reply = data["choices"][0]["message"]["content"].replace("DeepSeek", "LazyAI")
                return reply
            else:
                err = await resp.text()
                print(f"[ERROR] HuggingFace API status: {resp.status} - {err}")
                return "⚠️ LazyAI is sleepy. Try again later."

# =====================================
# EVENTS
# =====================================
@bot.event
async def on_ready():
    print(f"🧠 LazyAI is online as {bot.user}.")
    try:
        synced = await tree.sync()
        print(f"[INFO] Synced {len(synced)} commands.")
    except Exception as e:
        print(f"[ERROR] Command sync failed: {e}")

# =====================================
# COMMANDS
# =====================================
@tree.command(name="ask", description="Ask LazyAI anything.")
@app_commands.describe(prompt="Your question or message")
async def ask(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append({"role": "user", "content": prompt})
    response = await query_hf(user_memory[user_id][-10:])
    user_memory[user_id].append({"role": "assistant", "content": response})
    save_memory()

    await interaction.followup.send(f"🧠 {response}")

@tree.command(name="set-prefix", description="Set custom prefix like 'hey lazy'")
@app_commands.describe(prefix="Text prefix")
async def set_prefix(interaction: discord.Interaction, prefix: str):
    prefixes[str(interaction.guild_id)] = prefix.lower()
    save_memory()
    await interaction.response.send_message(f"✅ Prefix set to `{prefix}`")

@tree.command(name="set-autoreply-channel", description="Enable auto-reply in this channel")
async def set_auto(interaction: discord.Interaction):
    auto_reply_channels.add(interaction.channel_id)
    save_memory()
    await interaction.response.send_message("✅ Auto-reply enabled in this channel.")

@tree.command(name="clear-memory", description="Clear your chat history with LazyAI")
async def clear_memory(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_memory.pop(user_id, None)
    save_memory()
    await interaction.response.send_message("🧠 Your memory has been cleared.")

@tree.command(name="help", description="Show LazyAI command list")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("""
**LazyAI Slash Commands**
🔹 `/ask` — Ask LazyAI a question  
🔹 `/set-prefix` — Set a custom call phrase like 'hey lazy'  
🔹 `/set-autoreply-channel` — Enable auto-reply in this channel  
🔹 `/clear-memory` — Reset your conversation history  
🔹 `/help` — Show this message
""")

# =====================================
# MESSAGE HANDLING
# =====================================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    guild_id = str(message.guild.id) if message.guild else None
    channel_id = message.channel.id
    content = message.content.strip()
    user_id = str(message.author.id)

    if channel_id in auto_reply_channels:
        await handle_message(message)
        return

    prefix = prefixes.get(guild_id)
    if prefix and content.lower().startswith(prefix):
        stripped = content[len(prefix):].strip()
        await handle_message(message, stripped)

async def handle_message(message, prompt_override=None):
    prompt = prompt_override if prompt_override else message.content
    user_id = str(message.author.id)

    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append({"role": "user", "content": prompt})
    response = await query_hf(user_memory[user_id][-10:])
    user_memory[user_id].append({"role": "assistant", "content": response})
    save_memory()

    await message.channel.send(f"🧠 {response}")

# =====================================
# LEGACY COMMANDS
# =====================================
@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("🏓 Pong! LazyAI is alive.")

@bot.command(name="lazy")
async def lazy(ctx, *, prompt: str):
    user_id = str(ctx.author.id)
    await ctx.send("🤔 LazyAI is thinking...")
    if user_id not in user_memory:
        user_memory[user_id] = []
    user_memory[user_id].append({"role": "user", "content": prompt})
    reply = await query_hf(user_memory[user_id][-10:])
    user_memory[user_id].append({"role": "assistant", "content": reply})
    save_memory()
    await ctx.send(reply)

@bot.command(name="sayto")
async def say_to(ctx, user: discord.User, *, message: str):
    mention = f"<@{user.id}>"
    uid = str(ctx.author.id)
    if uid not in user_memory:
        user_memory[uid] = []
    user_memory[uid].append({"role": "user", "content": message})
    reply = await query_hf(user_memory[uid][-10:])
    user_memory[uid].append({"role": "assistant", "content": reply})
    save_memory()
    await ctx.send(f"{mention} 🧠 LazyAI says:\n{reply}")

bot.run(DISCORD_TOKEN)
