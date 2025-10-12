import os
import requests
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load tokens from .env file
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# Hugging Face router endpoint and headers
API_URL = "https://router.huggingface.co/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type": "application/json"
}

# Initialize bot with message content intent
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Function to call Hugging Face model
def query_huggingface(prompt):
    payload = {
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "model": "deepseek-ai/DeepSeek-V3.2-Exp:novita",
        "max_tokens": 512,
        "temperature": 0.7
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            print(f"[ERROR] HuggingFace API status: {response.status_code} - {response.text}")
            return "⚠️ Lazy.AI is sleepy. Try again later."
    except Exception as e:
        print(f"[ERROR] Failed to call API: {e}")
        return "⚠️ An unexpected error occurred."

# Bot event when ready
@bot.event
async def on_ready():
    print(f"🧠 Lazy.AI is online as {bot.user}.")

# Main !lazy command
@bot.command()
async def lazy(ctx, *, prompt: str):
    await ctx.send("🤔 Thinking...")
    reply = query_huggingface(prompt)
    await ctx.send(f" {reply}")

# Optional ping command
@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

# Run the bot
bot.run(DISCORD_TOKEN)
