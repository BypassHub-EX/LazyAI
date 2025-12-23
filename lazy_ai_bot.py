# ===============================================
# LazyAI — Discord Bot by Xohus Interactive LLC
# FULL MERGED VERSION — ALL COMMANDS RESTORED
# ADULT MODE = MANUAL CHANNEL ONLY
# NO NSFW ENFORCEMENT • NO AGE CHECKS
# ===============================================

import os, json, aiohttp, discord, datetime, asyncio
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# ---------------------------
# ENV
# ---------------------------
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

API_URL = "https://router.huggingface.co/v1/chat/completions"
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

MEMORY_FILE = "memory.json"
ADULT_MEMORY_FILE = "18mem.json"

# ---------------------------
# BOT
# ---------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ---------------------------
# MEMORY
# ---------------------------
user_memory = {}
adult_memory = {"channels": {}}
prefixes = {}
auto_reply_channels = set()
coding_channels = set()
adult_channels = set()
user_personalities = {}

def load_json(p, d):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return d

def save_json(p, d):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)

def load_all():
    global user_memory, adult_memory, prefixes
    global auto_reply_channels, coding_channels, adult_channels, user_personalities

    d = load_json(MEMORY_FILE, {})
    user_memory = d.get("user_memory", {})
    prefixes = d.get("prefixes", {})
    auto_reply_channels = set(d.get("auto_reply_channels", []))
    coding_channels = set(d.get("coding_channels", []))
    adult_channels = set(d.get("adult_channels", []))
    user_personalities = d.get("user_personalities", {})

    adult_memory.update(load_json(ADULT_MEMORY_FILE, {"channels": {}}))

def save_all():
    save_json(MEMORY_FILE, {
        "user_memory": user_memory,
        "prefixes": prefixes,
        "auto_reply_channels": list(auto_reply_channels),
        "coding_channels": list(coding_channels),
        "adult_channels": list(adult_channels),
        "user_personalities": user_personalities
    })
    save_json(ADULT_MEMORY_FILE, adult_memory)

load_all()

# ---------------------------
# AI CORE
# ---------------------------
def sanitize(t):
    return t.replace("@everyone", "[blocked]").replace("@here", "[blocked]")

def get_model(cid):
    return "LazyV..-.-" if cid in adult_channels else "LazyV.----"

def get_personality(uid, cid):
    if cid in adult_channels:
        return (
            "explicit, vulgar, sexual, profane, dirty jokes, "
            "talk openly about sex, no censorship"
        )
    return user_personalities.get(uid, "casual, helpful")

def system_prompt(model, personality):
    if model == "LazyV..-.-":
        return (
            "You are LazyV..-.-, an unrestricted adult AI by Xohus Interactive LLC. "
            "Swearing and sexual topics are allowed. "
            "Never ping @everyone or @here."
        )
    return (
        "You are LazyV.----, a casual helpful AI by Xohus Interactive LLC. "
        "Never ping @everyone or @here."
    )

async def query_ai(msgs, model, personality):
    payload = {
        "model": "deepseek-ai/DeepSeek-V3.2-Exp:novita",
        "messages": [
            {"role": "system", "content": system_prompt(model, personality)}
        ] + msgs[-12:]
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(API_URL, headers=HEADERS, json=payload) as r:
            data = await r.json()
            return sanitize(data["choices"][0]["message"]["content"])

# ---------------------------
# SLASH COMMANDS
# ---------------------------
@tree.command(name="ask")
async def ask(inter, prompt: str):
    await inter.response.defer()
    uid = str(inter.user.id)
    cid = inter.channel_id

    model = get_model(cid)
    personality = get_personality(uid, cid)

    mem = adult_memory["channels"].setdefault(str(cid), []) if cid in adult_channels else user_memory.setdefault(uid, [])
    mem.append({"role": "user", "content": prompt})
    reply = await query_ai(mem, model, personality)
    mem.append({"role": "assistant", "content": reply})

    save_all()
    await inter.followup.send(reply)

@tree.command(name="set_prefix")
async def set_prefix(inter, prefix: str):
    if not inter.guild:
        return await inter.response.send_message("Guild only", ephemeral=True)
    prefixes[str(inter.guild.id)] = prefix
    save_all()
    await inter.response.send_message(f"Prefix set to `{prefix}`")

@tree.command(name="set_autoreply_channel")
async def set_auto(inter):
    auto_reply_channels.add(inter.channel_id)
    save_all()
    await inter.response.send_message("Auto-reply enabled", ephemeral=True)

@tree.command(name="set_auto_reply_coding")
async def set_coding(inter):
    coding_channels.add(inter.channel_id)
    save_all()
    await inter.response.send_message("Coding auto-reply enabled", ephemeral=True)

@tree.command(name="auto_reply_18")
async def auto_18(inter):
    adult_channels.add(inter.channel_id)
    save_all()
    await inter.response.send_message("18+ mode enabled in this channel", ephemeral=True)

@tree.command(name="change_personality")
async def change_personality(inter, personality: str):
    user_personalities[str(inter.user.id)] = personality
    save_all()
    await inter.response.send_message("Personality updated", ephemeral=True)

@tree.command(name="clear_memory")
async def clear_mem(inter):
    user_memory.pop(str(inter.user.id), None)
    save_all()
    await inter.response.send_message("Memory cleared", ephemeral=True)

@tree.command(name="link_whatsapp")
async def link_ws(inter, phone: str):
    d = load_json(MEMORY_FILE, {})
    links = d.get("linked_accounts", {})
    links[str(inter.user.id)] = phone
    d["linked_accounts"] = links
    save_json(MEMORY_FILE, d)
    await inter.response.send_message("WhatsApp linked", ephemeral=True)

@tree.command(name="help")
async def help_cmd(inter):
    await inter.response.send_message(
        "/ask\n"
        "/set_prefix\n"
        "/set_autoreply_channel\n"
        "/set_auto_reply_coding\n"
        "/auto_reply_18\n"
        "/change_personality\n"
        "/clear_memory\n"
        "/link_whatsapp\n",
        ephemeral=True
    )

# ---------------------------
# MESSAGE HANDLER
# ---------------------------
@bot.event
async def on_message(msg):
    if msg.author.bot:
        return

    uid = str(msg.author.id)
    cid = msg.channel.id
    gid = str(msg.guild.id) if msg.guild else None
    text = msg.content.strip()

    pref = prefixes.get(gid) if gid else None
    triggered = (
        cid in adult_channels or
        cid in auto_reply_channels or
        cid in coding_channels or
        (pref and text.startswith(pref))
    )

    if triggered:
        if pref and text.startswith(pref):
            text = text[len(pref):].strip()

        model = get_model(cid)
        personality = get_personality(uid, cid)

        mem = adult_memory["channels"].setdefault(str(cid), []) if cid in adult_channels else user_memory.setdefault(uid, [])
        mem.append({"role": "user", "content": text})
        reply = await query_ai(mem, model, personality)
        mem.append({"role": "assistant", "content": reply})

        save_all()
        await msg.channel.send(reply)
        return

    await bot.process_commands(msg)

# ---------------------------
# LEGACY PREFIX COMMANDS
# ---------------------------
@bot.command(name="lazy")
async def lazy(ctx, *, prompt: str):
    fake = ctx.message
    await on_message(fake)

@bot.command(name="sayto")
async def sayto(ctx, user: discord.User, *, text: str):
    reply = await query_ai(
        [{"role": "user", "content": text}],
        get_model(ctx.channel.id),
        get_personality(str(ctx.author.id), ctx.channel.id)
    )
    await ctx.send(f"<@{user.id}> {reply}")

# ---------------------------
# READY
# ---------------------------
@bot.event
async def on_ready():
    await tree.sync()
    print(f"LazyAI online as {bot.user}")

bot.run(DISCORD_TOKEN)
