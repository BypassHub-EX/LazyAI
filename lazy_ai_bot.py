import os
import discord
import aiohttp
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
from dotenv import load_dotenv
import json
from langdetect import detect

# ===============================
# LOAD TOKENS AND CONFIG
# ===============================
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

API_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL_NAME = "deepseek-ai/DeepSeek-V3.2-Exp:novita"
MEMORY_FILE = "memory.json"

HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

# ===============================
# DISCORD CLIENT SETUP
# ===============================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ===============================
# MEMORY MANAGEMENT
# ===============================
user_memory = {}
prefixes = {}
auto_reply_channels = set()

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
        print(f"[WARN] Could not load memory: {e}")
        user_memory, prefixes = {}, {}
        auto_reply_channels = set()

def save_memory():
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "user_memory": user_memory,
                "prefixes": prefixes,
                "auto_reply_channels": list(auto_reply_channels)
            }, f, ensure_ascii=False, indent=2)
        print("[INFO] Memory saved.")
    except Exception as e:
        print(f"[ERROR] Failed to save memory: {e}")

load_memory()

# ===============================
# UTILITIES
# ===============================
def detect_language(text):
    try:
        return detect(text)
    except:
        return "en"

async def query_hf(messages, lang="en"):
    system_prompt = {
        "role": "system",
        "content": f"You are LazyAI, a smart, casual Discord bot. "
                   f"Always reply in {lang}, and sound natural and conversational."
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [system_prompt] + messages[-10:]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, headers=HEADERS, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                content = data["choices"][0]["message"]["content"].replace("DeepSeek", "LazyAI")
                return content
            else:
                err = await resp.text()
                print(f"[ERROR] query_hf {resp.status}: {err}")
                return "⚠️ LazyAI is sleepy. Try again later."

# ===============================
# BUTTON VIEW
# ===============================
class LazyAIButtons(View):
    def __init__(self, user_id, prompt):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.prompt = prompt

    @discord.ui.button(label="🔁 Regenerate", style=discord.ButtonStyle.primary)
    async def regenerate(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("❌ Not your message.", ephemeral=True)
        lang = detect_language(self.prompt)
        msgs = user_memory.get(self.user_id, [])
        msgs.append({"role": "user", "content": self.prompt})
        reply = await query_hf(msgs[-10:], lang)
        msgs.append({"role": "assistant", "content": reply})
        user_memory[self.user_id] = msgs
        save_memory()
        await interaction.message.edit(content=f"🧠 {reply}", view=self)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("❌ You can’t delete this.", ephemeral=True)
        await interaction.message.delete()

# ===============================
# DISCORD EVENTS
# ===============================
@bot.event
async def on_ready():
    print(f"🧠 LazyAI is online as {bot.user}.")
    try:
        synced = await tree.sync()
        print(f"[INFO] Synced {len(synced)} commands.")
    except Exception as e:
        print(f"[ERROR] Command sync failed: {e}")

# ===============================
# SLASH COMMANDS
# ===============================
@tree.command(name="ask", description="Ask LazyAI anything.")
@app_commands.describe(prompt="Your question or message")
async def ask(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    lang = detect_language(prompt)

    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append({"role": "user", "content": prompt})
    reply = await query_hf(user_memory[user_id][-10:], lang)
    user_memory[user_id].append({"role": "assistant", "content": reply})
    save_memory()

    await interaction.followup.send(f"🧠 {reply}", view=LazyAIButtons(user_id, prompt))

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
    uid = str(interaction.user.id)
    user_memory.pop(uid, None)
    save_memory()
    await interaction.response.send_message("🧠 Your memory has been cleared.")

@tree.command(name="help", description="Show LazyAI command list")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("""
**LazyAI Slash Commands**
🔹 `/ask` — Ask LazyAI anything  
🔹 `/set-prefix` — Set a custom prefix like 'hey lazy'  
🔹 `/set-autoreply-channel` — Enable auto-reply in this channel  
🔹 `/clear-memory` — Forget chat history  
🔹 `/help` — Show this message
""")

# ===============================
# MESSAGE HANDLER
# ===============================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = str(message.author.id)
    gid = str(message.guild.id) if message.guild else None
    cid = message.channel.id
    text = message.content.strip()

    # Auto-reply in enabled channels
    if cid in auto_reply_channels:
        await handle_message(message)
        return

    # Prefix trigger
    prefix = prefixes.get(gid)
    if prefix and text.lower().startswith(prefix.lower()):
        stripped = text[len(prefix):].strip()
        await handle_message(message, stripped)

async def handle_message(message, prompt_override=None):
    prompt = prompt_override if prompt_override else message.content
    uid = str(message.author.id)
    lang = detect_language(prompt)

    if uid not in user_memory:
        user_memory[uid] = []

    user_memory[uid].append({"role": "user", "content": prompt})
    reply = await query_hf(user_memory[uid][-10:], lang)
    user_memory[uid].append({"role": "assistant", "content": reply})
    save_memory()

    await message.channel.send(f"🧠 {reply}", view=LazyAIButtons(uid, prompt))

# ===============================
# LEGACY PREFIX COMMANDS
# ===============================
@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("🏓 Pong! LazyAI is alive.")

@bot.command(name="lazy")
async def lazy(ctx, *, prompt: str):
    uid = str(ctx.author.id)
    lang = detect_language(prompt)
    await ctx.send("🤔 LazyAI is thinking...")
    if uid not in user_memory:
        user_memory[uid] = []
    user_memory[uid].append({"role": "user", "content": prompt})
    reply = await query_hf(user_memory[uid][-10:], lang)
    user_memory[uid].append({"role": "assistant", "content": reply})
    save_memory()
    await ctx.send(reply, view=LazyAIButtons(uid, prompt))

@bot.command(name="sayto")
async def say_to(ctx, user: discord.User, *, message: str):
    mention = f"<@{user.id}>"
    uid = str(ctx.author.id)
    lang = detect_language(message)
    if uid not in user_memory:
        user_memory[uid] = []
    user_memory[uid].append({"role": "user", "content": message})
    reply = await query_hf(user_memory[uid][-10:], lang)
    user_memory[uid].append({"role": "assistant", "content": reply})
    save_memory()
    await ctx.send(f"{mention} 🧠 LazyAI says:\n{reply}", view=LazyAIButtons(uid, message))

# ===============================
# RUN BOT
# ===============================
bot.run(DISCORD_TOKEN)
