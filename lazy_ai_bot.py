import os
import json
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

API_URL = "https://router.huggingface.co/v1/chat/completions"
HF_MODEL = "deepseek-ai/DeepSeek-V3.2-Exp:novita"

MEMORY_FILE = "memory.json"
ADULT_MEMORY_FILE = "18mem.json"

OWNER_ID = "1012774928841445426"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

user_memory = {}
adult_memory = {"channels": {}}

prefixes = {}
auto_reply_channels = set()
coding_channels = set()
dm_autoreply_users = set()
adult_channels = set()

user_personalities = {}
user_models = {}
linked_accounts = {}
whatsapp_users = {}

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_memory():
    global user_memory, prefixes, auto_reply_channels, coding_channels
    global dm_autoreply_users, adult_channels, user_personalities
    global user_models, linked_accounts, whatsapp_users

    d = load_json(MEMORY_FILE, {})
    user_memory = d.get("user_memory", {})
    prefixes = d.get("prefixes", {})
    auto_reply_channels = set(d.get("auto_reply_channels", []))
    coding_channels = set(d.get("coding_channels", []))
    dm_autoreply_users = set(d.get("dm_autoreply_users", []))
    adult_channels = set(d.get("adult_channels", []))
    user_personalities = d.get("user_personalities", {})
    user_models = d.get("user_models", {})
    linked_accounts = d.get("linked_accounts", {})
    whatsapp_users = d.get("whatsapp_users", {})

def save_memory():
    save_json(MEMORY_FILE, {
        "user_memory": user_memory,
        "prefixes": prefixes,
        "auto_reply_channels": list(auto_reply_channels),
        "coding_channels": list(coding_channels),
        "dm_autoreply_users": list(dm_autoreply_users),
        "adult_channels": list(adult_channels),
        "user_personalities": user_personalities,
        "user_models": user_models,
        "linked_accounts": linked_accounts,
        "whatsapp_users": whatsapp_users
    })

def load_adult_memory():
    global adult_memory
    adult_memory = load_json(ADULT_MEMORY_FILE, {"channels": {}})

def save_adult_memory():
    save_json(ADULT_MEMORY_FILE, adult_memory)

def sanitize(text):
    if not text:
        return text
    return text.replace("@everyone", "@-everyone").replace("@here", "@-here")

def get_adult_bucket(channel_id, user_id):
    c = str(channel_id)
    u = str(user_id)
    adult_memory.setdefault("channels", {})
    adult_memory["channels"].setdefault(c, {"users": {}})
    adult_memory["channels"][c]["users"].setdefault(u, [])
    return adult_memory["channels"][c]["users"][u]

def get_model(uid, cid):
    if cid in adult_channels:
        return "LazyV..-.-"
    return user_models.get(uid, "LazyV.----")

def get_personality(uid, cid):
    if uid == OWNER_ID:
        return "dominant, sharp, direct"
    if cid in adult_channels:
        return (
            "extremely blunt, aggressive, heavy swearing, sexual, roasting, mocking, humiliating stupidity, "
            "no roleplay, no actions, no stage directions, still helpful, answers directly"
        )
    return user_personalities.get(uid, "casual")

def system_prompt(model, personality):
    return (
        f"You are {model}, an AI by Xohus Interactive LLC (https://xohus.me). "
        f"Personality: {personality}. "
        "Never roleplay. Never describe actions. Never soften language. "
        "Do not use formatting headers. Do not censor yourself unnecessarily. "
        "Never output @everyone or @here."
    )

async def query_hf(messages, model, personality):
    payload = {
        "model": HF_MODEL,
        "messages": [{"role": "system", "content": system_prompt(model, personality)}] + messages[-14:]
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(API_URL, headers={"Authorization": f"Bearer {HF_TOKEN}"}, json=payload) as r:
            if r.status != 200:
                return "LazyAI error."
            data = await r.json()
            return sanitize(data["choices"][0]["message"]["content"])

class ActionButtons(View):
    def __init__(self, uid, prompt, cid):
        super().__init__(timeout=None)
        self.uid = uid
        self.prompt = prompt
        self.cid = cid

    @discord.ui.button(label="Regenerate", style=discord.ButtonStyle.primary)
    async def regen(self, interaction, _):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("Not yours.", ephemeral=True)

        msgs = get_adult_bucket(self.cid, self.uid) if self.cid in adult_channels else user_memory.setdefault(self.uid, [])
        msgs.append({"role": "user", "content": self.prompt})

        reply = await query_hf(msgs, get_model(self.uid, self.cid), get_personality(self.uid, self.cid))
        msgs.append({"role": "assistant", "content": reply})

        save_adult_memory() if self.cid in adult_channels else save_memory()
        await interaction.response.edit_message(content=reply, view=self)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction, _):
        if str(interaction.user.id) == self.uid:
            await interaction.message.delete()

@tree.command(name="ask")
async def ask(inter, prompt: str):
    await inter.response.defer()
    uid = str(inter.user.id)
    cid = str(inter.channel_id)

    msgs = get_adult_bucket(cid, uid) if cid in adult_channels else user_memory.setdefault(uid, [])
    msgs.append({"role": "user", "content": prompt})

    reply = await query_hf(msgs, get_model(uid, cid), get_personality(uid, cid))
    msgs.append({"role": "assistant", "content": reply})

    save_adult_memory() if cid in adult_channels else save_memory()
    await inter.followup.send(reply, view=ActionButtons(uid, prompt, cid))

@tree.command(name="set-model")
async def set_model(inter, model: str):
    user_models[str(inter.user.id)] = model
    save_memory()
    await inter.response.send_message("Model set.", ephemeral=True)

@tree.command(name="change-personality")
async def change_personality(inter, text: str):
    user_personalities[str(inter.user.id)] = text
    save_memory()
    await inter.response.send_message("Personality updated.", ephemeral=True)

@tree.command(name="set-prefix")
async def set_prefix(inter, prefix: str):
    prefixes[str(inter.guild.id)] = prefix.lower()
    save_memory()
    await inter.response.send_message("Prefix set.", ephemeral=True)

@tree.command(name="set-autoreply-channel")
async def set_auto(inter):
    auto_reply_channels.add(str(inter.channel_id))
    save_memory()
    await inter.response.send_message("Auto-reply enabled.")

@tree.command(name="set-auto-reply-coding")
async def set_code(inter):
    coding_channels.add(str(inter.channel_id))
    save_memory()
    await inter.response.send_message("Coding auto-reply enabled.")

@tree.command(name="set-auto-reply-dms")
async def set_dm(inter):
    dm_autoreply_users.add(str(inter.user.id))
    save_memory()
    await inter.response.send_message("DM auto-reply enabled.", ephemeral=True)

@tree.command(name="auto-reply-18")
async def set_18(inter):
    adult_channels.add(str(inter.channel_id))
    save_memory()
    await inter.response.send_message("18+ mode enabled.")

@tree.command(name="link-whatsapp")
async def link_ws(inter, phone: str):
    linked_accounts[str(inter.user.id)] = f"whatsapp:{phone}"
    whatsapp_users[phone] = {"linked_discord": str(inter.user.id)}
    save_memory()
    await inter.response.send_message("Linked.", ephemeral=True)

@tree.command(name="clear-memory")
async def clear_mem(inter):
    user_memory.pop(str(inter.user.id), None)
    save_memory()
    await inter.response.send_message("Memory cleared.", ephemeral=True)

@tree.command(name="help")
async def help_cmd(inter):
    await inter.response.send_message(
        "/ask /set-model /change-personality /set-prefix\n"
        "/set-autoreply-channel /set-auto-reply-coding\n"
        "/set-auto-reply-dms /auto-reply-18\n"
        "/link-whatsapp /clear-memory",
        ephemeral=True
    )

@bot.event
async def on_message(msg):
    if msg.author.bot:
        return

    uid = str(msg.author.id)
    cid = str(msg.channel.id)
    gid = str(msg.guild.id) if msg.guild else None
    text = msg.content.strip()

    if msg.guild is None and uid in dm_autoreply_users:
        await handle_msg(msg, text)
        return

    if cid in auto_reply_channels or cid in coding_channels or cid in adult_channels:
        await handle_msg(msg, text)
        return

    if gid and prefixes.get(gid) and text.lower().startswith(prefixes[gid]):
        await handle_msg(msg, text[len(prefixes[gid]):].strip())
        return

    await bot.process_commands(msg)

async def handle_msg(msg, prompt):
    uid = str(msg.author.id)
    cid = str(msg.channel.id)

    msgs = get_adult_bucket(cid, uid) if cid in adult_channels else user_memory.setdefault(uid, [])
    msgs.append({"role": "user", "content": prompt})

    reply = await query_hf(msgs, get_model(uid, cid), get_personality(uid, cid))
    msgs.append({"role": "assistant", "content": reply})

    save_adult_memory() if cid in adult_channels else save_memory()
    await msg.channel.send(reply, view=ActionButtons(uid, prompt, cid))

@bot.event
async def on_ready():
    load_memory()
    load_adult_memory()
    await tree.sync()
    print("LazyAI ONLINE")

bot.run(DISCORD_TOKEN)
