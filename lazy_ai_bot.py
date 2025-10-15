import os
import discord
import aiohttp
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select
from dotenv import load_dotenv
import json

# ===============================
# CONFIG
# ===============================
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
API_URL = "https://router.huggingface.co/v1/chat/completions"
MEMORY_FILE = "memory.json"

HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

# ===============================
# DISCORD SETUP
# ===============================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ===============================
# MEMORY
# ===============================
user_memory = {}
prefixes = {}
auto_reply_channels = set()
coding_reply_channels = set()
user_models = {}
default_model = "LazyV.----"

MODEL_FEATURES = {
    "LazyV.----": {
        "title": "LazyV.---- (Original)",
        "description": "**Default** personality by Xohus Interactive LLC\nCasual, human-like, friendly\nMinimal emoji use\nAdaptive tone\nSends spontaneous messages like 'who wants to chat?'"
    },
    "LazyV..---": {
        "title": "LazyV..--- (LazyV2)",
        "description": "Smarter reasoning, better long replies\nEmotionally aware\nAdds slight humor or sarcasm"
    },
    "LazyV...--": {
        "title": "LazyV...-- (LazyV3)",
        "description": "Near-human flow\nChecks in on users\nMemory linking + reflections\nFeels like a real friend"
    },
    "LazyV..-.-": {
        "title": "LazyV..-.- (Unrestricted)",
        "description": "Blunt, edgy, unfiltered\nCan be inappropriate if pushed\nFewer behavior filters\nStill obeys Discord ToS"
    }
}

# ===============================
# STORAGE
# ===============================
def load_memory():
    global user_memory, prefixes, auto_reply_channels, coding_reply_channels, user_models
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        user_memory = data.get("user_memory", {})
        prefixes = data.get("prefixes", {})
        auto_reply_channels = set(data.get("auto_reply_channels", []))
        coding_reply_channels = set(data.get("coding_reply_channels", []))
        user_models = data.get("user_models", {})
        print("[INFO] Memory loaded.")
    except Exception as e:
        print(f"[WARN] Could not load memory: {e}")

def save_memory():
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "user_memory": user_memory,
                "prefixes": prefixes,
                "auto_reply_channels": list(auto_reply_channels),
                "coding_reply_channels": list(coding_reply_channels),
                "user_models": user_models
            }, f, indent=2)
        print("[INFO] Memory saved.")
    except Exception as e:
        print(f"[ERROR] Failed to save memory: {e}")

load_memory()

# ===============================
# CORE
# ===============================
async def query_hf(messages, model):
    system_prompt = {
        "role": "system",
        "content": f"You are LazyAI, a smart and casual Discord bot developed by Xohus Interactive LLC. "
                   f"Your model is {model}. Do not reference Claude, DeepSeek, or Hugging Face. "
                   f"Keep a natural tone. Use minimal emojis."
    }
    payload = {
        "model": "deepseek-ai/DeepSeek-V3.2-Exp:novita",
        "messages": [system_prompt] + messages[-10:]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, headers=HEADERS, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                return content.replace("DeepSeek", "LazyAI")
            else:
                return "⚠️ LazyAI is sleepy."

# ===============================
# VIEW
# ===============================
class LazyAIButtons(View):
    def __init__(self, user_id, prompt):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.prompt = prompt

    @discord.ui.button(label="🔁 Regenerate", style=discord.ButtonStyle.primary)
    async def regenerate(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("❌ Not yours.", ephemeral=True)
        uid = str(interaction.user.id)
        msgs = user_memory.get(uid, [])
        msgs.append({"role": "user", "content": self.prompt})
        model = user_models.get(uid, default_model)
        reply = await query_hf(msgs, model)
        msgs.append({"role": "assistant", "content": reply})
        user_memory[uid] = msgs
        save_memory()
        await interaction.message.edit(content=f"🧠 {reply}", view=self)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) == self.user_id:
            await interaction.message.delete()

# ===============================
# EVENTS
# ===============================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"🧠 LazyAI (Xohus) is online as {bot.user}")

@bot.event
async def on_message(msg):
    if msg.author.bot:
        return
    uid = str(msg.author.id)
    gid = str(msg.guild.id) if msg.guild else None
    prompt = msg.content.strip()
    if msg.channel.id in auto_reply_channels or msg.channel.id in coding_reply_channels:
        await handle_message(msg, prompt)
    elif gid in prefixes and prompt.lower().startswith(prefixes[gid]):
        await handle_message(msg, prompt[len(prefixes[gid]):].strip())

async def handle_message(msg, prompt):
    uid = str(msg.author.id)
    if uid not in user_memory:
        user_memory[uid] = []
    user_memory[uid].append({"role": "user", "content": prompt})
    model = user_models.get(uid, default_model)
    reply = await query_hf(user_memory[uid], model)
    user_memory[uid].append({"role": "assistant", "content": reply})
    save_memory()
    await msg.channel.send(f"🧠 {reply}", view=LazyAIButtons(uid, prompt))

# ===============================
# SLASH COMMANDS
# ===============================
@tree.command(name="ask", description="Ask LazyAI something.")
@app_commands.describe(prompt="Your message or question")
async def ask(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    uid = str(interaction.user.id)
    model = user_models.get(uid, default_model)
    if uid not in user_memory:
        user_memory[uid] = []
    user_memory[uid].append({"role": "user", "content": prompt})
    reply = await query_hf(user_memory[uid], model)
    user_memory[uid].append({"role": "assistant", "content": reply})
    save_memory()
    await interaction.followup.send(f"🧠 {reply}", view=LazyAIButtons(uid, prompt))

@tree.command(name="set-prefix", description="Set trigger prefix.")
@app_commands.describe(prefix="Like 'hey lazy'")
async def set_prefix(interaction: discord.Interaction, prefix: str):
    prefixes[str(interaction.guild_id)] = prefix.lower()
    save_memory()
    await interaction.response.send_message(f"✅ Prefix set to `{prefix}`")

@tree.command(name="set-autoreply-channel", description="Auto-reply in this channel")
async def set_autoreply(interaction: discord.Interaction):
    auto_reply_channels.add(interaction.channel_id)
    save_memory()
    await interaction.response.send_message("✅ Auto-reply enabled here.")

@tree.command(name="set-auto-reply-coding", description="Enable coding auto-reply here")
async def set_coding(interaction: discord.Interaction):
    coding_reply_channels.add(interaction.channel_id)
    save_memory()
    await interaction.response.send_message("✅ Coding replies enabled in this channel.")

@tree.command(name="clear-memory", description="Clear chat history")
async def clear_memory(interaction: discord.Interaction):
    user_memory.pop(str(interaction.user.id), None)
    save_memory()
    await interaction.response.send_message("🧠 Chat history cleared.")

@tree.command(name="help", description="Show help")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("""
**LazyAI Commands**
• `/ask` – Ask LazyAI  
• `/set-prefix` – Trigger prefix  
• `/set-autoreply-channel` – Chatbot mode  
• `/set-auto-reply-coding` – For code channels  
• `/clear-memory` – Forget history  
• `/set-model` – Choose AI model
""")

@tree.command(name="set-model", description="Choose LazyAI model")
async def set_model(interaction: discord.Interaction):
    uid = str(interaction.user.id)

    class ModelSelector(View):
        def __init__(self):
            super().__init__(timeout=60)
            self.add_item(ModelDropdown())

        @discord.ui.button(label="✅ Use This Model", style=discord.ButtonStyle.success)
        async def use_model(self, interaction2: discord.Interaction, button: Button):
            selected = self.children[0].values[0]
            user_models[uid] = selected
            save_memory()
            await interaction2.response.edit_message(content=f"✅ Model set to `{selected}`", embed=None, view=None)

    class ModelDropdown(Select):
        def __init__(self):
            options = [discord.SelectOption(label=m, description=f"View {m} features") for m in MODEL_FEATURES]
            super().__init__(placeholder="Choose a model to preview...", options=options)

        async def callback(self, interaction2: discord.Interaction):
            selected = self.values[0]
            feat = MODEL_FEATURES[selected]
            embed = discord.Embed(title=feat["title"], description=feat["description"], color=0x2ecc71)
            embed.set_footer(text="Provided by Xohus Interactive LLC — https://xohus.me")
            await interaction2.response.edit_message(embed=embed, view=self.view)

    initial_model = "LazyV.----"
    desc = MODEL_FEATURES[initial_model]
    embed = discord.Embed(title=desc["title"], description=desc["description"], color=0x2ecc71)
    embed.set_footer(text="Provided by Xohus Interactive LLC — https://xohus.me")

    await interaction.response.send_message(
        "Use the dropdown to explore models. Click the button to select one.",
        ephemeral=True,
        embed=embed,
        view=ModelSelector()
    )

# ===============================
# RUN
# ===============================
bot.run(DISCORD_TOKEN)
