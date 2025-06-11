import aiohttp
import os
import discord
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import logging
import asyncio

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Channel configurations
BELLA_WH_LOG_CHANNEL_STREAM_WEBHOOK = os.getenv('BELLA_WH_LOG_CHANNEL_STREAM_WEBHOOK')
BELLA_WH_LOG_CHANNEL_STREAM_ID = int(os.getenv('BELLA_WH_LOG_CHANNEL_STREAM_ID', '0'))

# Second channel configuration
UPPER_ECHELON_CHANNEL_STREAM_WEBHOOK = os.getenv('UPPER_ECHELON_CHANNEL_STREAM_WEBHOOK')
UPPER_ECHELON_CHANNEL_ID = int(os.getenv('UPPER_ECHELON_CHANNEL_ID'))

# Last message ID files
LAST_LOG_FILE = "last_log_id.txt"
SECOND_CHANNEL_LAST_FILE = "last_second_channel_id.txt"

# Channel configurations mapping
CHANNEL_CONFIGS = {
    BELLA_WH_LOG_CHANNEL_STREAM_ID: {
        'webhook': BELLA_WH_LOG_CHANNEL_STREAM_WEBHOOK,
        'last_file': LAST_LOG_FILE,
        'name': 'wh-log'
    },
    UPPER_ECHELON_CHANNEL_ID: {
        'webhook': UPPER_ECHELON_CHANNEL_STREAM_WEBHOOK,
        'last_file': SECOND_CHANNEL_LAST_FILE,
        'name': 'upper-echelon'
    }
}

async def handle_log_message(message):
    # Handle messages from configured channels
    channel_id = message.channel.id
    if channel_id in CHANNEL_CONFIGS:
        config = CHANNEL_CONFIGS[channel_id]
        
        # Send to webhook if configured
        if config['webhook']:
            logger.info(f"Handling message from {config['name']} channel: {message.id}")
            await send_to_webhook(message, config['webhook'])
            # Save latest message ID for this channel
            with open(config['last_file'], "w") as f:
                f.write(str(message.id))
        else:
            logger.warning(f"No webhook configured for channel {config['name']} ({channel_id})")


async def test_webhooks():
    """Test both webhooks by sending test messages"""
    logger.info("Testing webhooks...")
    
    test_messages = [
        {
            "embeds": [{
                "title": "🔧 Webhook Test #1",
                "description": "**System**: Testing wh-log channel webhook",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "color": 65280,  # Green color
                "footer": {"text": "Test Message - wh-log channel"}
            }]
        },
        {
            "embeds": [{
                "title": "🔧 Webhook Test #2", 
                "description": "**System**: Testing upper-echelon channel webhook",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "color": 255,  # Blue color
                "footer": {"text": "Test Message - upper-echelon channel"}
            }]
        }
    ]
    
    webhooks_to_test = [
        ("wh-log", BELLA_WH_LOG_CHANNEL_STREAM_WEBHOOK),
        ("upper-echelon", UPPER_ECHELON_CHANNEL_STREAM_WEBHOOK)
    ]
    
    async with aiohttp.ClientSession() as session:
        for i, (channel_name, webhook_url) in enumerate(webhooks_to_test):
            if not webhook_url:
                logger.error(f"❌ No webhook URL configured for {channel_name}")
                continue
                
            try:
                logger.info(f"🧪 Testing {channel_name} webhook...")
                async with session.post(webhook_url, json=test_messages[i]) as response:
                    if response.status in (200, 204):
                        logger.info(f"✅ {channel_name} webhook test successful!")
                    else:
                        logger.error(f"❌ {channel_name} webhook test failed with status {response.status}")
                        
            except Exception as e:
                logger.error(f"❌ Error testing {channel_name} webhook: {e}")
            
            # Small delay between tests
            await asyncio.sleep(1)
    
    logger.info("Webhook testing completed!")


async def stream_log_history(bot, limit=None, time_limit_hours=24):
    logger.info("Starting to stream log history from all configured channels")
    
    # Test webhooks first
    await test_webhooks()
    
    # Stream history from all configured channels
    for channel_id, config in CHANNEL_CONFIGS.items():
        if config['webhook']:  # Only stream if webhook is configured
            logger.info(f"Streaming history from {config['name']} channel ({channel_id})")
            await stream_channel_history(bot, channel_id, config['last_file'], config['webhook'], limit, time_limit_hours)
        else:
            logger.info(f"Skipping {config['name']} channel - no webhook configured")


async def stream_channel_history(bot, channel_id, last_id_file, webhook_url, limit=None, time_limit_hours=24):
    channel = bot.get_channel(channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            logger.error(f"Failed to fetch channel with ID {channel_id}: {e}")
            return

    # Check bot permissions in detail
    permissions = channel.permissions_for(channel.guild.me)
    logger.info(f"Bot permissions in channel {channel.name}:")
    logger.info(f"  - read_messages: {permissions.read_messages}")
    logger.info(f"  - read_message_history: {permissions.read_message_history}")
    logger.info(f"  - view_channel: {permissions.view_channel}")
    
    # Check when bot joined the server
    bot_member = channel.guild.get_member(bot.user.id)
    if bot_member and bot_member.joined_at:
        logger.info(f"Bot joined server at: {bot_member.joined_at}")
    else:
        logger.warning("Could not determine when bot joined the server")
    
    if not permissions.read_message_history:
        logger.error(f"Bot does not have permission to read message history in channel {channel.name}")
        return
    
    if not permissions.read_messages:
        logger.error(f"Bot does not have permission to read messages in channel {channel.name}")
        return

    # Set time filter based on time_limit_hours parameter
    after_time = None
    if time_limit_hours is not None and time_limit_hours > 0:
        after_time = datetime.now(timezone.utc) - timedelta(hours=time_limit_hours)
        logger.info(f"Fetching messages after {after_time} from channel {channel.name} ({channel_id})")
    else:
        logger.info(f"Fetching ALL messages from channel {channel.name} ({channel_id})")

    # Try to get the oldest message to see if there are any messages at all
    try:
        oldest_messages = []
        async for msg in channel.history(limit=1, oldest_first=True):
            oldest_messages.append(msg)
        
        if oldest_messages:
            oldest_msg = oldest_messages[0]
            logger.info(f"Oldest message found: ID {oldest_msg.id}, created at {oldest_msg.created_at}")
            logger.info(f"Oldest message year: {oldest_msg.created_at.year}")
        else:
            logger.warning("No messages found when checking for oldest message")
            
        # Also check newest message
        newest_messages = []
        async for msg in channel.history(limit=1, oldest_first=False):
            newest_messages.append(msg)
            
        if newest_messages:
            newest_msg = newest_messages[0]
            logger.info(f"Newest message found: ID {newest_msg.id}, created at {newest_msg.created_at}")
            logger.info(f"Newest message year: {newest_msg.created_at.year}")
            
            # Check if dates make sense
            if oldest_messages and newest_messages:
                if oldest_msg.created_at > newest_msg.created_at:
                    logger.error("WARNING: Oldest message is newer than newest message! This indicates a problem.")
        else:
            logger.warning("No messages found when checking for newest message")
            
    except Exception as e:
        logger.error(f"Error checking for messages in channel: {e}")
        return

    message_count = 0
    async with aiohttp.ClientSession() as session:
        try:
            async for message in channel.history(limit=None, oldest_first=True, after=after_time):
                if limit and message_count >= limit:
                    logger.info(f"Reached message limit {limit} for channel {channel.name}")
                    break

                logger.info(f"Processing message {message.id} from {message.created_at}")
                
                # Send to webhook
                await send_to_webhook(message, webhook_url, session)
                
                # Add delay to prevent rate limiting
                await asyncio.sleep(1.0)  # 1 second between messages
                
                with open(last_id_file, "w") as f:
                    f.write(str(message.id))
                message_count += 1

            logger.info(f"Finished streaming {message_count} messages from channel {channel.name}")
        except Exception as e:
            logger.error(f"Error streaming messages from channel {channel.name}: {e}")


async def send_to_webhook(message, webhook_url, session=None):
    created_here = False
    if session is None:
        session = aiohttp.ClientSession()
        created_here = True

    try:
        author = f"{message.author.display_name}"  # Cleaner display name
        timestamp = message.created_at.strftime("%H:%M:%S")
        content = message.content.strip() or "*[Image/File/Embed]*"
        
        # Truncate very long messages
        if len(content) > 1500:
            content = content[:1500] + "... (truncated)"

        payload = {
            "embeds": [{
                "title": f"#{message.channel.name}",
                "description": f"**{author}**: {content}",
                "timestamp": message.created_at.isoformat(),
                "color": 3066993,  # Green color
                "footer": {"text": f"ID: {message.id}"}
            }]
        }

        max_retries = 3
        for attempt in range(max_retries):
            async with session.post(webhook_url, json=payload) as response:
                if response.status == 429:
                    # Rate limited - wait longer
                    retry_after = int(response.headers.get('Retry-After', 5))
                    logger.warning(f"Rate limited! Waiting {retry_after} seconds (attempt {attempt + 1})")
                    await asyncio.sleep(retry_after)
                    continue
                elif response.status in (200, 204):
                    logger.debug(f"Successfully sent message {message.id}")
                    break
                else:
                    logger.warning(f"Webhook response {response.status} for message {message.id}")
                    break
        else:
            logger.error(f"Failed to send message {message.id} after {max_retries} attempts")

    except Exception as e:
        logger.error(f"Error sending message {message.id} to webhook: {e}")
    finally:
        if created_here:
            await session.close()
