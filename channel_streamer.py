import aiohttp
import os
import discord
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import logging
import asyncio
from logging.handlers import TimedRotatingFileHandler
import glob

load_dotenv()

# Configure logging with rotating file handler
def setup_channel_logger():
    """Setup a rotating logger for channel streaming with daily files"""
    logger = logging.getLogger(__name__)
    
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure the rotating file handler
    log_file = os.path.join(log_dir, "channel_stream.log")
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",  # Rotate at midnight
        interval=1,       # Every 1 day
        backupCount=7,    # Keep 7 days of logs
        encoding="utf-8"
    )
    
    # Set log format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)
    
    # Also add console handler if not already present
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

# Initialize the logger
logger = setup_channel_logger()

def cleanup_old_logs(days_to_keep=7):
    """Manually clean up log files older than specified days"""
    try:
        log_dir = "logs"
        if not os.path.exists(log_dir):
            return
            
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        pattern = os.path.join(log_dir, "channel_stream.log.*")
        
        deleted_count = 0
        for log_file in glob.glob(pattern):
            try:
                file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
                if file_time < cutoff_date:
                    os.remove(log_file)
                    deleted_count += 1
                    logger.info(f"Deleted old log file: {log_file}")
            except Exception as e:
                logger.error(f"Error deleting log file {log_file}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old log files")
    except Exception as e:
        logger.error(f"Error during log cleanup: {e}")

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

def stream_message_to_cli(message, channel_name):
    """Stream a live message to CLI with formatted output"""
    timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
    author = message.author.display_name
    content = message.content.strip() or "*[Image/File/Embed]*"
    
    # Truncate very long messages for CLI display
    if len(content) > 200:
        content = content[:200] + "... (truncated)"
    
    # Format the output with colors/styling for better visibility
    cli_message = f"\n{'='*60}\n[{timestamp}] #{channel_name}\n{author}: {content}\nMessage ID: {message.id}\n{'='*60}"
    
    print(cli_message)
    logger.info(f"📨 LIVE MESSAGE | #{channel_name} | {author}: {content[:50]}{'...' if len(content) > 50 else ''}")

async def handle_log_message(message):
    # Handle messages from configured channels
    channel_id = message.channel.id
    if channel_id in CHANNEL_CONFIGS:
        config = CHANNEL_CONFIGS[channel_id]
        
        # Stream to CLI immediately for live messages
        stream_message_to_cli(message, config['name'])
        
        # Send to webhook if configured
        if config['webhook']:
            try:
                await send_to_webhook(message, config['webhook'])
                # Save latest message ID for this channel
                with open(config['last_file'], "w") as f:
                    f.write(str(message.id))
            except Exception as e:
                logger.error(f"❌ Failed to send message {message.id} to webhook: {e}")
    else:
        # Optional: Log messages from other channels for debugging
        # Skip DM channels as they don't have a name attribute
        if hasattr(message.channel, 'name') and message.channel.name:
            logger.debug(f"Message from non-monitored channel #{message.channel.name} ({channel_id}): {message.content[:50]}...")





async def stream_log_history(bot, limit=None, time_limit_hours=24):
    logger.info("🚀 Starting channel streamer service...")
    logger.info(f"📊 Configuration: {len(CHANNEL_CONFIGS)} channels configured")
    
    # Clean up old logs first
    cleanup_old_logs(days_to_keep=7)
    logger.info("🧹 Log cleanup completed")
    
    # Log which channels are active
    active_channels = [config['name'] for config in CHANNEL_CONFIGS.values() if config['webhook']]
    inactive_channels = [config['name'] for config in CHANNEL_CONFIGS.values() if not config['webhook']]
    
    if active_channels:
        logger.info(f"✅ Active channels: {', '.join(active_channels)}")
    if inactive_channels:
        logger.info(f"⚠️  Inactive channels (no webhook): {', '.join(inactive_channels)}")
    
    # Stream history from all configured channels
    for channel_id, config in CHANNEL_CONFIGS.items():
        if config['webhook']:  # Only stream if webhook is configured
            logger.info(f"📡 Starting stream for #{config['name']} channel...")
            await stream_channel_history(bot, channel_id, config['last_file'], config['webhook'], limit, time_limit_hours)
        else:
            logger.info(f"⏭️  Skipping #{config['name']} - no webhook configured")
    
    logger.info("✨ Channel streamer service initialization completed!")


async def stream_channel_history(bot, channel_id, last_id_file, webhook_url, limit=None, time_limit_hours=24):
    channel = bot.get_channel(channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            logger.error(f"❌ Failed to fetch channel with ID {channel_id}: {e}")
            return

    logger.info(f"🔗 Connected to #{channel.name} in {channel.guild.name}")

    # Check basic permissions
    permissions = channel.permissions_for(channel.guild.me)
    if not permissions.read_message_history or not permissions.read_messages:
        logger.error(f"❌ Bot lacks required permissions in #{channel.name}")
        return
    
    logger.info(f"✅ Permissions verified for #{channel.name}")

    # Set time filter based on time_limit_hours parameter
    after_time = None
    if time_limit_hours is not None and time_limit_hours > 0:
        after_time = datetime.now(timezone.utc) - timedelta(hours=time_limit_hours)
        logger.info(f"📅 Fetching messages from last {time_limit_hours} hours")
    else:
        logger.info(f"📅 Fetching ALL message history")

    message_count = 0
    async with aiohttp.ClientSession() as session:
        try:
            logger.info(f"🔄 Starting message processing for #{channel.name}...")
            async for message in channel.history(limit=None, oldest_first=True, after=after_time):
                if limit and message_count >= limit:
                    logger.info(f"🛑 Reached message limit of {limit}")
                    break
                
                # Send to webhook
                await send_to_webhook(message, webhook_url, session)
                
                # Add delay to prevent rate limiting
                await asyncio.sleep(1.0)  # 1 second between messages
                
                with open(last_id_file, "w") as f:
                    f.write(str(message.id))
                message_count += 1

            logger.info(f"✅ Completed streaming {message_count} messages from #{channel.name}")
        except Exception as e:
            logger.error(f"❌ Error streaming messages from #{channel.name}: {e}")


async def debug_channel_config(bot):
    """Debug function to check channel configurations and webhook status"""
    logger.info("=== CHANNEL CONFIGURATION DEBUG ===")
    
    for channel_id, config in CHANNEL_CONFIGS.items():
        logger.info(f"\nChannel: {config['name']} (ID: {channel_id})")
        logger.info(f"Webhook configured: {bool(config['webhook'])}")
        if config['webhook']:
            logger.info(f"Webhook URL: {config['webhook'][:50]}...")
        else:
            logger.info("Webhook URL: None")
        
        # Try to get the channel
        try:
            channel = bot.get_channel(channel_id)
            if channel:
                logger.info(f"Channel found: #{channel.name} in {channel.guild.name}")
                
                # Check bot permissions
                permissions = channel.permissions_for(channel.guild.me)
                logger.info(f"Bot permissions:")
                logger.info(f"  - read_messages: {permissions.read_messages}")
                logger.info(f"  - read_message_history: {permissions.read_message_history}")
                logger.info(f"  - view_channel: {permissions.view_channel}")
                
                # Get recent message count for testing
                try:
                    recent_messages = []
                    async for msg in channel.history(limit=5):
                        recent_messages.append(msg)
                    logger.info(f"Recent messages found: {len(recent_messages)}")
                    if recent_messages:
                        latest = recent_messages[0]
                        logger.info(f"Latest message: {latest.id} from {latest.author.display_name} at {latest.created_at}")
                except Exception as e:
                    logger.error(f"Error fetching recent messages: {e}")
            else:
                logger.error(f"Channel not found or bot doesn't have access")
                
        except Exception as e:
            logger.error(f"Error accessing channel: {e}")
    
    logger.info("=== END DEBUG ===\n")

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

        logger.debug(f"Sending webhook payload for message {message.id}: {payload}")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with session.post(webhook_url, json=payload) as response:
                    response_text = await response.text()
                    
                    if response.status == 429:
                        # Rate limited - wait longer
                        retry_after = int(response.headers.get('Retry-After', 5))
                        logger.warning(f"Rate limited! Waiting {retry_after} seconds (attempt {attempt + 1})")
                        await asyncio.sleep(retry_after)
                        continue
                    elif response.status in (200, 204):
                        logger.debug(f"Successfully sent message {message.id} to webhook")
                        break
                    else:
                        logger.error(f"Webhook response {response.status} for message {message.id}")
                        logger.error(f"Response text: {response_text}")
                        logger.error(f"Response headers: {dict(response.headers)}")
                        break
            except aiohttp.ClientError as e:
                logger.error(f"Network error sending message {message.id} to webhook (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise
        else:
            logger.error(f"Failed to send message {message.id} after {max_retries} attempts")

    except Exception as e:
        logger.error(f"Error sending message {message.id} to webhook: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        if created_here:
            await session.close()
