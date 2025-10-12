import discord
import aiohttp
import os
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

HF_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

@bot.event
async def on_ready():
    print(f"🧠 Lazy.AI is online as {bot.user}.")

@bot.command()
async def lazy(ctx, *, prompt: str):
    await ctx.send("🤔 Thinking...")
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 256, "temperature": 0.7}
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(HF_API_URL, headers=headers, json=payload) as resp:
            if resp.status == 200:
                result = await resp.json()
                try:
                    text = result[0]["generated_text"]
                    reply = text.replace(prompt, "").strip()
                    await ctx.send(f"🧠 {reply}")
                except Exception:
                    await ctx.send("⚠️ Lazy.AI got confused. Try again later.")
            else:
                await ctx.send("⚠️ Lazy.AI is sleepy. Try again later.")

@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

bot.run(DISCORD_TOKEN)
