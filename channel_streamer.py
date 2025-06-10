import aiohttp
import os
import discord
from dotenv import load_dotenv

load_dotenv()

# Bella specific webhooks and channels
BELLA_WH_LOG_CHANNEL_STREAM_WEBHOOK = os.getenv('BELLA_WH_LOG_CHANNEL_STREAM_WEBHOOK')
BELLA_WH_LOG_CHANNEL_STREAM_ID = int(os.getenv('BELLA_WH_LOG_CHANNEL_STREAM_ID', '0'))
BELLA_UPPER_ECHELON_WEBHOOK = os.getenv('BELLA_UPPER_ECHELON_WEBHOOK')
BELLA_UPPER_ECHELON_ID = int(os.getenv('BELLA_UPPER_ECHELON_ID', '0'))

LAST_LOG_FILE = "last_log_id.txt"
LAST_UPPER_ECHELON_FILE = "last_upper_echelon_id.txt"

async def handle_log_message(message):
    # Handle messages from both channels
    if message.channel.id == BELLA_WH_LOG_CHANNEL_STREAM_ID:
        await send_to_webhook(message, BELLA_WH_LOG_CHANNEL_STREAM_WEBHOOK)
        # Save latest message ID for log channel
        with open(LAST_LOG_FILE, "w") as f:
            f.write(str(message.id))
    elif message.channel.id == BELLA_UPPER_ECHELON_ID:
        await send_to_webhook(message, BELLA_UPPER_ECHELON_WEBHOOK)
        # Save latest message ID for upper echelon channel
        with open(LAST_UPPER_ECHELON_FILE, "w") as f:
            f.write(str(message.id))


async def stream_log_history(bot, limit=100):
    # Stream history from both channels
    await stream_channel_history(bot, BELLA_WH_LOG_CHANNEL_STREAM_ID, LAST_LOG_FILE, BELLA_WH_LOG_CHANNEL_STREAM_WEBHOOK, limit)
    await stream_channel_history(bot, BELLA_UPPER_ECHELON_ID, LAST_UPPER_ECHELON_FILE, BELLA_UPPER_ECHELON_WEBHOOK, limit)


async def stream_channel_history(bot, channel_id, last_id_file, webhook_url, limit=100):
    channel = bot.get_channel(channel_id)
    if not channel:
        print(f"Cannot find channel with ID {channel_id}")
        return

    after_id = None
    if os.path.exists(last_id_file):
        with open(last_id_file, "r") as f:
            after_id = int(f.read().strip())

    after = discord.Object(id=after_id) if after_id else None

    async with aiohttp.ClientSession() as session:
        async for message in channel.history(limit=limit, oldest_first=True, after=after):
            await send_to_webhook(message, webhook_url, session)
            with open(last_id_file, "w") as f:
                f.write(str(message.id))


async def send_to_webhook(message, webhook_url, session=None):
    created_here = False
    if session is None:
        session = aiohttp.ClientSession()
        created_here = True

    author = f"{message.author.name}#{message.author.discriminator}"
    timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
    content = message.content.strip() or "*[No text content]*"

    payload = {
        "content": f"**{author}** at `{timestamp}`:\n{content}"
    }

    await session.post(webhook_url, json=payload)

    if created_here:
        await session.close()