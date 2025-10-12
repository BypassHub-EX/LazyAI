import discord
from discord import app_commands
from discord.ext import commands
import os
import aiohttp
from dotenv import load_dotenv
import json
from langdetect import detect

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

API_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL_NAME = "deepseek-ai/DeepSeek-V3.2-Exp:novita"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

tree = bot.tree

# In-memory stores
user_memory = {}  # {user_id: [messages]}
prefixes = {}      # {guild_id: "hey lazy"}
auto_reply_channels = set()  # channel IDs

HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}"
}

async def query_hf(messages):
    payload = {
        "messages": messages,
        "model": MODEL_NAME,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, headers=HEADERS, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                err = await resp.text()
                print(f"[ERROR] HuggingFace API status: {resp.status} - {err}")
                return "⚠️ Lazy.AI is sleepy. Try again later."

def detect_language(text):
    try:
        return detect(text)
    except:
        return "en"

@bot.event
async def on_ready():
    print(f"🧠 Lazy.AI is online as {bot.user}.")
    try:
        synced = await tree.sync()
        print(f"[INFO] Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"[ERROR] Command sync failed: {e}")

@tree.command(name="ask", description="Ask Lazy.AI anything.")
@app_commands.describe(prompt="Your question or message")
async def ask(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    lang = detect_language(prompt)

    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append({"role": "user", "content": prompt})

    response = await query_hf(user_memory[user_id])
    user_memory[user_id].append({"role": "assistant", "content": response})

    await interaction.followup.send(f"🧠 {response}")

@tree.command(name="set-prefix", description="Set a custom prefix like 'hey lazy'")
@app_commands.describe(prefix="Text prefix to trigger the bot")
async def set_prefix(interaction: discord.Interaction, prefix: str):
    prefixes[interaction.guild_id] = prefix.lower()
    await interaction.response.send_message(f"✅ Prefix set to: `{prefix}`")

@tree.command(name="set-autoreply-channel", description="Enable auto-reply in this channel")
async def set_autoreply(interaction: discord.Interaction):
    auto_reply_channels.add(interaction.channel_id)
    await interaction.response.send_message("✅ Auto-reply enabled for this channel.")

@tree.command(name="clear-memory", description="Clear your chat memory with Lazy.AI")
async def clear_memory(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_memory.pop(user_id, None)
    await interaction.response.send_message("🧠 Memory cleared!")

@tree.command(name="help", description="Show all Lazy.AI commands")
async def help_cmd(interaction: discord.Interaction):
    msg = """
**Lazy.AI Slash Commands**
> Talk to Lazy.AI, set up your preferences, and more:

`/ask [prompt]` — Ask Lazy.AI anything  
`/set-prefix [text]` — Set a custom prefix like "hey lazy"  
`/set-autoreply-channel` — Enable replies in this channel without calling it  
`/clear-memory` — Forget chat history with you  
`/help` — Show this message
"""
    await interaction.response.send_message(msg)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    guild_id = message.guild.id if message.guild else None
    channel_id = message.channel.id
    content = message.content.strip()

    # Auto-reply in channel
    if channel_id in auto_reply_channels:
        await handle_message(message)
        return

    # Prefix-based reply
    prefix = prefixes.get(guild_id, None)
    if prefix and content.lower().startswith(prefix.lower()):
        stripped = content[len(prefix):].strip()
        await handle_message(message, stripped)

async def handle_message(message, prompt_override=None):
    prompt = prompt_override if prompt_override else message.content
    user_id = str(message.author.id)
    lang = detect_language(prompt)

    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append({"role": "user", "content": prompt})

    response = await query_hf(user_memory[user_id])
    user_memory[user_id].append({"role": "assistant", "content": response})

    await message.channel.send(f"🧠 {response}")

bot.run(DISCORD_TOKEN)
