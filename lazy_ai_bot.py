import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
from transformers import Qwen3OmniMoeForConditionalGeneration, Qwen3OmniMoeProcessor
from qwen_omni_utils import process_mm_info

# Load env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Set up bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Dynamic server config
server_configs = {}  # {guild_id: {"prefixes": [...], "auto_channel_ids": [...] }}

# Load model
print("🔄 Loading Qwen3-Omni...")
model = Qwen3OmniMoeForConditionalGeneration.from_pretrained(
    "Qwen/Qwen3-Omni-30B-A3B-Instruct",
    device_map="auto",
    torch_dtype="auto",
    attn_implementation="flash_attention_2"
)
model.disable_talker()
processor = Qwen3OmniMoeProcessor.from_pretrained("Qwen/Qwen3-Omni-30B-A3B-Instruct")
print("✅ Lazy.AI is ready.")

# Helper: generate response
async def generate_lazy_reply(prompt):
    conversation = [{"role": "user", "content": prompt}]
    text = processor.apply_chat_template(conversation, add_generation_prompt=True, tokenize=False)
    audios, images, videos = process_mm_info(conversation, use_audio_in_video=False)
    inputs = processor(
        text=text,
        audio=audios,
        images=images,
        videos=videos,
        return_tensors="pt",
        padding=True,
        use_audio_in_video=False
    ).to(model.device).to(model.dtype)

    outputs, _ = model.generate(
        **inputs,
        return_audio=False,
        thinker_return_dict_in_generate=True,
        use_audio_in_video=False
    )

    reply = processor.batch_decode(
        outputs.sequences[:, inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True
    )[0]

    return reply[:2000]

# Slash command: /help
@bot.tree.command(name="help", description="Show all Lazy.AI commands")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**Lazy.AI Commands:**\n"
        "• `/add-reply-prefix [prefix]` → Add a prefix like 'hey lazy' or ','\n"
        "• `/add-auto-reply-channel` → Make Lazy.AI reply in this channel without needing a prefix\n"
        "• Just say something after your prefix or in an auto-reply channel and I'll respond.", ephemeral=True
    )

# Slash command: /add-reply-prefix
@bot.tree.command(name="add-reply-prefix", description="Add a custom trigger prefix")
@app_commands.describe(prefix="Text that should trigger Lazy.AI replies")
async def add_prefix(interaction: discord.Interaction, prefix: str):
    gid = interaction.guild_id
    server_configs.setdefault(gid, {"prefixes": [], "auto_channel_ids": []})
    server_configs[gid]["prefixes"].append(prefix.lower())
    await interaction.response.send_message(f"✅ Prefix added: `{prefix}`", ephemeral=True)

# Slash command: /add-auto-reply-channel
@bot.tree.command(name="add-auto-reply-channel", description="Enable auto-reply in this channel")
async def add_auto_reply_channel(interaction: discord.Interaction):
    gid = interaction.guild_id
    cid = interaction.channel_id
    server_configs.setdefault(gid, {"prefixes": [], "auto_channel_ids": []})
    server_configs[gid]["auto_channel_ids"].append(cid)
    await interaction.response.send_message(f"✅ Auto-reply enabled in this channel.", ephemeral=True)

# Auto-response handler
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    gid = message.guild.id
    cid = message.channel.id
    content = message.content.lower()
    config = server_configs.get(gid, {"prefixes": [], "auto_channel_ids": []})

    # Check for prefix
    triggered = any(content.startswith(prefix.lower()) for prefix in config["prefixes"])

    # Check for auto-channel
    if triggered or cid in config["auto_channel_ids"]:
        await message.channel.typing()
        prompt = content
        for prefix in config["prefixes"]:
            if prompt.startswith(prefix):
                prompt = prompt[len(prefix):].strip()
                break
        try:
            reply = await generate_lazy_reply(prompt)
            await message.reply(reply)
        except Exception as e:
            await message.reply("💥 Error talking to Qwen3. Maybe I need a nap.")

# Start
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Lazy.AI bot ready as {bot.user}")

bot.run(TOKEN)
