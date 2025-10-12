import discord
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Hugging Face inference API call
def generate_lazy_reply(prompt):
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 200,
            "temperature": 0.7
        }
    }

    response = requests.post(
        "https://api-inference.huggingface.co/models/Qwen/Qwen3-Omni-30B-A3B-Instruct",
        headers=headers,
        json=payload
    )

    if response.status_code == 200:
        result = response.json()
        return result[0]["generated_text"][len(prompt):].strip()
    else:
        return "⚠️ Lazy.AI is sleepy. Try again later."

@client.event
async def on_ready():
    print(f"🧠 Lazy.AI is online as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("!lazy"):
        prompt = message.content[len("!lazy"):].strip()
        if not prompt:
            await message.reply("😴 You forgot to ask something.")
            return

        await message.channel.typing()
        reply = generate_lazy_reply(prompt)
        await message.reply(reply[:2000])  # Limit to Discord's max

client.run(DISCORD_TOKEN)
