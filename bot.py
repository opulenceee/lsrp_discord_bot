import discord
import json
from discord.ext import commands
import os
import asyncio
import subprocess
from dotenv import load_dotenv
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from forum_monitor import fetch_total_pages, fetch_forum_replies, save_replies_to_file
from discord.ui import Button, View
from discord import app_commands
from collections import defaultdict
import requests
import logging
import sys
import aiohttp
import threading
import queue
import time




load_dotenv()  # Load environment variables from .env file
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
LOG_WEBHOOK_URL = os.getenv('LOG_WEBHOOK_URL')  # Add this to your .env file
BOT_OWNER_ID = int(os.getenv('BOT_OWNER_ID', '804688024704253986'))  # Your Discord user ID
FORUMS = 749      # Forums parameter (fixed)
PER_PAGE = 15     # Number of replies per page (fixed)
CONFIG_FILE = 'bot_config.json'
DATA_DIR = 'data'

# Configure logging
class DiscordWebhookHandler(logging.Handler):
    def __init__(self, webhook_url, log_queue):
        super().__init__()
        self.webhook_url = webhook_url
        self.log_queue = log_queue

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put(msg)
        except Exception:
            self.handleError(record)

async def discord_log_worker(webhook_url, log_queue):
    session = aiohttp.ClientSession()
    while True:
        msg = await asyncio.get_event_loop().run_in_executor(None, log_queue.get)
        try:
            # Split message if it's too long
            if len(msg) > 2000:
                chunks = [msg[i:i+1990] for i in range(0, len(msg), 1990)]
                for chunk in chunks:
                    await session.post(
                        webhook_url,
                        json={"content": f"```{chunk}```"}
                    )
            else:
                await session.post(
                    webhook_url,
                    json={"content": f"```{msg}```"}
                )
        except Exception as e:
            print(f"Error sending log to Discord webhook: {e}")
        finally:
            log_queue.task_done()

# Setup logging configuration
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    
    # Discord webhook handler
    log_queue = queue.Queue()
    if LOG_WEBHOOK_URL:
        discord_handler = DiscordWebhookHandler(LOG_WEBHOOK_URL, log_queue)
        discord_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(discord_handler)
        # Start the async log worker after the event loop is running (see on_ready)
        logger.discord_log_queue = log_queue
    else:
        print("Warning: LOG_WEBHOOK_URL not set in .env file. Discord logging disabled.")
    
    return logger

# Initialize logger
logger = setup_logging()



intents = discord.Intents.default()
intents.messages = True  
intents.message_content = True
intents.guilds = True  # Enable guilds intent

class CustomBot(commands.Bot):
    async def setup_hook(self) -> None:
        self.owner_id = BOT_OWNER_ID

bot = CustomBot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    try:
        # Force sync commands
        logger.info("Starting command tree sync...")
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands globally")
        
        # Start Discord log worker if needed
        if LOG_WEBHOOK_URL and hasattr(logger, 'discord_log_queue'):
            if not hasattr(bot, '_discord_log_worker_started'):
                bot.loop.create_task(discord_log_worker(LOG_WEBHOOK_URL, logger.discord_log_queue))
                bot._discord_log_worker_started = True
        
        # Log number of configured guilds
        settings = load_config()
        guild_count = len(settings)
        
        logger.info(f'Bot is ready! Logged in as {bot.user.name}')
        logger.info(f"Bot owner ID: {bot.owner_id}")
        logger.info(f"Bot is configured in {guild_count} guilds:")
        
        # Get all guilds the bot is actually in
        bot_guilds = {str(g.id): g.name for g in bot.guilds}
        


        # Log each configured guild with its status
        for guild_id, config in settings.items():
            guild_name = config.get('guild_name', 'Unknown')
            if guild_id in bot_guilds:
                logger.info(f"- {guild_name} (Active)")
            else:
                logger.info(f"- {guild_name} (Bot not in server)")
        

            
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
        print(f"Failed to sync commands: {e}")

    # Check if config exists on startup
    settings = load_config()
    if settings:
        bot.loop.create_task(update_player_list_and_forum_comments())
        bot.loop.create_task(monitor_replies())  # RE-ENABLED - reads JSON files updated by forum_monitor.py
        bot.loop.create_task(check_watchlists())
        # bot.loop.create_task(they_gotta_go())  # DISABLED - using watchlist instead

# Loading blocked guilds from file
def load_blocked_guilds():
    blocked_guilds_file_path = os.path.join(DATA_DIR, 'blocked_guilds.json')
    try:
        with open(blocked_guilds_file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):  # Handle file errors
        return []

# Initialize blocked guilds globally
blocked_guilds = load_blocked_guilds()

# Debugging: print blocked guilds after loading
print(f"Blocked Guilds: {blocked_guilds}")

# Save blocked guilds to a file
def save_blocked_guilds():
    blocked_guilds_file_path = os.path.join(DATA_DIR, 'blocked_guilds.json')
    with open(blocked_guilds_file_path, 'w') as f:
        json.dump(blocked_guilds, f)

# Debugging: check if the list updates after blocking/unblocking
print(f"Blocked Guilds after change: {blocked_guilds}")


# Slash command to block a guild
@bot.tree.command(name="block_guild", description="Block a guild by its ID.")
@commands.is_owner()  # Restricts this command to the bot owner
async def block_guild(interaction: discord.Interaction, guild_id: str):
    try:
        guild_id = int(guild_id)  # Ensure that guild_id is an integer
    except ValueError:
        await interaction.response.send_message("Invalid guild ID.")
        return
    
    if guild_id not in blocked_guilds:
        blocked_guilds.append(guild_id)
        save_blocked_guilds()
        await interaction.response.send_message(f"Guild {guild_id} has been blocked.")
    else:
        await interaction.response.send_message("This guild is already blocked.")

@bot.tree.command(name="unblock_guild", description="Unblock a guild by its ID.")
@commands.is_owner()  # Restrict this command to the bot owner
async def unblock_guild(interaction: discord.Interaction, guild_id: str):
    # Ensure guild_id is an integer
    guild_id = int(guild_id)  # Make sure we're working with an int

    # Check if the command is run in a blocked guild but still allow execution
    if interaction.guild and interaction.guild.id in blocked_guilds:
        await interaction.response.send_message("You are unblocking this server despite it being blocked.")

    # Proceed with unblocking
    if guild_id in blocked_guilds:
        blocked_guilds.remove(guild_id)
        save_blocked_guilds()
        
        # Use followup.send instead of response.send_message to avoid "InteractionResponded"
        await interaction.followup.send(f"Guild {guild_id} has been unblocked.")
    else:
        await interaction.response.send_message(f"This guild {guild_id} is not blocked.")

    # Debugging step to confirm guilds after unblocking
    await interaction.followup.send(f"Blocked guilds after unblocking: {blocked_guilds}")

# Global check to prevent commands in blocked guilds and enforce channel restrictions
async def check_guild(interaction: discord.Interaction) -> bool:
    # Check if guild is blocked
    if interaction.guild and interaction.guild.id in blocked_guilds:
        await interaction.response.send_message(
            f"Commands are disabled for **{interaction.guild.name}**. "
            "Please contact the bot owner if you think this is an error."
        ) 
        return False  # Block this guild
    
    # Check if command is in the correct channel (skip for setup and remove commands)
    if interaction.command and interaction.command.name not in ["setup", "remove"]:
        guild_id = str(interaction.guild.id)
        settings = load_config()
        
        # If guild is configured, check if command is in the right channel
        if guild_id in settings:
            configured_channel_id = settings[guild_id].get("notification_channel_id")
            if configured_channel_id and interaction.channel.id != configured_channel_id:
                await interaction.response.send_message(
                    f"This command can only be used in <#{configured_channel_id}>.",
                    ephemeral=True
                )
                return False
        # If guild is not configured and it's not setup/remove command, block it
        else:
            await interaction.response.send_message(
                "This bot is not configured for this server. Please use `/setup` to configure it first.",
                ephemeral=True
            )
            return False
    
    return True  # Allow the command


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}  # Return an empty dict if the file doesn't exist.

    try:
        with open(CONFIG_FILE, 'r') as f:
            content = f.read()
            if not content:  # Check if the file is empty.
                return {}
            return json.loads(content)
    except json.JSONDecodeError:
        print("Failed to decode JSON. Returning empty config.")
        return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as config_file:
        json.dump(config, config_file, indent=4)  # Use indent for readability


def is_configured(server_id):
    server_settings = load_config()
    return server_id in server_settings

@bot.tree.command(name="setup", description="Configure bot settings for this server")
@app_commands.check(check_guild)
async def setup(interaction: discord.Interaction, channel_id: str, topic_id: str = None):
    if not interaction.user.guild_permissions.administrator:
        logger.warning(f"User {interaction.user} attempted to use setup command without admin permissions")
        await interaction.response.send_message("You must have administrator permissions to use this command.", ephemeral=True)
        return

    settings = load_config()
    guild_id = str(interaction.guild_id)
    guild_name = interaction.guild.name  # Get the guild name
    logger.info(f"Setting up bot for guild {guild_name} ({guild_id}) with channel {channel_id}")

    if guild_id not in settings:
        settings[guild_id] = {}

    try:
        channel_id = int(channel_id)
        settings[guild_id]["notification_channel_id"] = channel_id
        settings[guild_id]["guild_name"] = guild_name  # Store the guild name
        if topic_id:
            settings[guild_id]["topic_id"] = topic_id

        save_config(settings)
        logger.info(f"Successfully configured bot for guild {guild_name} ({guild_id})")

        msg_parts = []
        msg_parts.append(f"Notification channel set to <#{channel_id}>.")
        if topic_id:
            msg_parts.append(f"Topic ID set to `{topic_id}`.")

        await interaction.response.send_message(" ".join(msg_parts))

    except ValueError:
        logger.error(f"Invalid channel ID format provided: {channel_id}")
        await interaction.response.send_message("Invalid channel ID format. Please provide a valid number.", ephemeral=True)


@bot.tree.command(name="remove", description="Remove bot configuration for this server")
@app_commands.check(check_guild)
async def remove(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You must have administrator permissions to use this command.", ephemeral=True)
        return

    server_id = str(interaction.guild_id)
    server_settings = load_config()

    if server_id in server_settings:
        del server_settings[server_id]
        save_config(server_settings)
        await interaction.response.send_message("Configuration removed for this server.")
    else:
        await interaction.response.send_message("No configuration found for this server.")


def load_forum_data(topic_id):
    json_file_path = os.path.join(DATA_DIR, f"forum_{topic_id}.json")  # Generate path based on topic_id
    if os.path.exists(json_file_path):
        with open(json_file_path, "r") as forum_file:
            return json.load(forum_file)
    return {}

def load_player_data():
    player_list_path = os.path.join(DATA_DIR, 'player_list.json')
    player_data = {}

    # Load player_list.json
    if os.path.exists(player_list_path):
        with open(player_list_path, "r") as file:
            player_data = json.load(file)
    else:
        print("player_list.json does not exist.")

    return player_data

def load_last_seen():
    last_seen_path = os.path.join(DATA_DIR, 'last_seen.json')
    last_seen_data = {}

    # Load last_seen.json
    if os.path.exists(last_seen_path):
        with open(last_seen_path, "r") as file:
            last_seen_data = json.load(file)
    else:
        print("last_seen.json does not exist.")

    return last_seen_data


def format_date(date_str):
    """Convert ISO 8601 date string to a more readable format."""
    # Parse the ISO date
    dt = datetime.fromisoformat(date_str[:-1])  # Remove the 'Z' and convert
    return dt.strftime("%B %d, %Y at %I:%M %p")  # Format date

def clean_html(raw_html):
    """Strip HTML tags and extract information about images or videos from the given HTML string."""
    print("Raw HTML:", raw_html)  # Debug: print the raw HTML
    soup = BeautifulSoup(raw_html, 'html.parser')

    # Extract the text
    text = soup.get_text(strip=True)
    print("Extracted Text:", text)  # Debug: print the extracted text

    # Initialize media presence flags
    contains_images = False
    contains_videos = False

    # Check for images
    for img in soup.find_all('img'):
        if img.get('src'):
            contains_images = True  # Set flag if any image is found

    # Check for videos
    for video in soup.find_all('iframe'):
        if video.get('src'):
            contains_videos = True  # Set flag if any video is found

    # Prepare the response content
    media_message = ""
    if contains_images and contains_videos:
        media_message = "**This reply contains images and videos.**"
    elif contains_images:
        media_message = "**This reply contains images.**"
    elif contains_videos:
        media_message = "**This reply contains videos.**"

    # Return both text and media message
    return text, media_message  # Ensure both values are returned



@bot.tree.command(name="info", description="Displays the bot functionality guide.")
@app_commands.check(check_guild)
async def info(interaction: discord.Interaction):
    embed = discord.Embed(title="Bot Functionality Guide", color=discord.Color.red())

    helpMessage = """
1. **/setup** - Admin command to set or update the bot configuration. Usage:
   - `/setup CHANNEL_ID` - Set the notification channel only (enables UCP monitoring).
   - `/setup CHANNEL_ID TOPIC_ID` - Set both the channel and topic (enables UCP and forum monitoring).
2. **/remove** - Admin command to delete the current bot configuration for this server, disabling all functionalities.
3. **/online** - Displays a list of all logged-in players.
4. **/admins** - Shows a list of currently online admins.
5. **/testers** - Lists all logged-in testers.
6. **/check FirstName_LastName** - Checks if the specified player is currently online.
7. **/latest** - Displays the last reply on our forum thread and its author.
8. **/thread** - Shows how many replies are left for the next page.
9. **/show_settings** - Shows the current configuration of the bot.
10. **/last_online FirstName_LastName** - Displays the last online status of the specified player.
"""

    embed.description = helpMessage
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="show_settings", description="Displays the current configuration of the bot.")
@app_commands.check(check_guild)
async def show_settings(interaction: discord.Interaction):
    """Displays the channel and topic for notifications based on existing settings."""
    guild_id = str(interaction.guild.id)
    settings = load_config()  # Load existing settings

    # Check if settings exist for the guild
    if guild_id in settings:
        notification_channel_id = settings[guild_id].get("notification_channel_id")
        topic_id = settings[guild_id].get("topic_id")

        if notification_channel_id and topic_id:
            await interaction.response.send_message(f"Notification channel is set to <#{notification_channel_id}> for topic ID `{topic_id}`.")
        else:
            await interaction.response.send_message("Notification channel ID or topic ID is not set.")
    else:
        await interaction.response.send_message("No settings found for this server. Please set them using the appropriate command.")

@bot.tree.command(name="latest", description="Displays the last reply and its author, date.")
@app_commands.check(check_guild)
async def latest(interaction: discord.Interaction):
    """Displays the last reply and its author, date."""
    settings = load_config()
    guild_id = str(interaction.guild.id)
    
    if guild_id in settings and settings[guild_id]["topic_id"]:
        topic_id = settings[guild_id]["topic_id"]
        replies = load_forum_data(topic_id)  # Load replies for the specific topic_id
        
        if replies:
            last_reply = replies[-1]  # Get the last reply
            author_name = last_reply['author']['formattedName']
            content, media_message = clean_html(last_reply.get("content", "No content available."))
            url = last_reply['url']
            date = format_date(last_reply['date'])

            if media_message:
                content += "\n" + media_message 

            if len(content) > 1024:
                content = content[:1021] + '...'  # Truncate long content

            embed = discord.Embed(title="Last Reply", color=discord.Color.red())
            embed.add_field(name="Author", value=author_name, inline=True)
            embed.add_field(name="Content", value=content, inline=False)
            embed.add_field(name="Link", value=url, inline=False)
            embed.add_field(name="Date", value=date, inline=True)

            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("No replies found.")
    else:
        await interaction.response.send_message("Please set up a topic ID first using `/setup channel_id topic_id`.")

@bot.tree.command(name="thread", description="Displays the current number of replies and how many are left for the next page.")
@app_commands.check(check_guild)
async def thread(interaction: discord.Interaction):
    """Displays the current number of replies and how many are left for the next page."""
    settings = load_config()
    guild_id = str(interaction.guild.id)

    if guild_id in settings and settings[guild_id]["topic_id"]:
        topic_id = settings[guild_id]["topic_id"]
        replies = load_forum_data(topic_id)  # Load replies for the specific topic_id

        if replies:
            current_replies = len(replies)
            replies_left = 15 - current_replies  # Assuming 15 replies per page

            embed = discord.Embed(title="Replies Status", color=discord.Color.red())
            embed.add_field(name="Current Replies", value=current_replies, inline=False)
            embed.add_field(name="Replies Left for New Page", value=replies_left, inline=False)

            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("No replies found.")
    else:
        await interaction.response.send_message("Please set up a topic ID first using `/setup channel_id topic_id`.")


@bot.tree.command(name="admins", description="Show online administrators")
@app_commands.check(check_guild)
async def admins(interaction: discord.Interaction):
    player_data = load_player_data()
    embed = discord.Embed(title="Online Admins", color=discord.Color.red())
    
    if not player_data or "players" not in player_data:
        await interaction.response.send_message("No player data available.")
        return

    admin_names = []
    for player in player_data["players"]:
        if player.get("isAdmin", False):
            character_name = player.get("characterName", "Unknown")
            account_name = player.get("accountName", "Unknown")
            admin_names.append(f"{character_name} **({account_name})**")

    embed.description = "\n".join(admin_names) if admin_names else "No admins are currently logged in."
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="testers", description="Show online testers")
@app_commands.check(check_guild)
async def testers(interaction: discord.Interaction):
    player_data = load_player_data()
    embed = discord.Embed(title="Online Testers", color=discord.Color.red())

    if not player_data or "players" not in player_data:
        await interaction.response.send_message("No player data available.")
        return

    tester_names = []
    for player in player_data["players"]:
        if player.get("isTester", False):
            character_name = player.get("characterName", "Unknown")
            account_name = player.get("accountName", "Unknown")
            tester_names.append(f"{character_name} **({account_name})**")

    embed.description = "\n".join(tester_names) if tester_names else "No testers are currently logged in."
    await interaction.response.send_message(embed=embed)


    
@bot.tree.command(name="online", description="Display all online players")
@app_commands.check(check_guild)
async def online(interaction: discord.Interaction):
    try:
        # Check if interaction is still valid before any response
        if interaction.response.is_done():
            logger.debug("Interaction already responded to in /online")
            return

        # Defer the interaction to prevent timeout
        try:
            await interaction.response.defer()
        except discord.NotFound:
            logger.debug("Interaction expired before defer() in /online")
            return
        except discord.errors.InteractionResponded:
            logger.debug("Interaction already responded to before defer() in /online")
            return

        player_data = load_player_data()
        if not player_data or "players" not in player_data:
            try:
                await interaction.followup.send("No player data available.")
            except discord.NotFound:
                logger.debug("Interaction expired before followup.send() in /online [no data]")
            except discord.errors.WebhookTokenMissing:
                logger.debug("Webhook token missing - interaction likely expired")
            return

        player_names = [player["characterName"] for player in player_data["players"]]
        player_count = len(player_names)
        response = "\n".join(player_names)
        embed = discord.Embed(title=f"Online Players ({player_count})", color=discord.Color.red())

        try:
            if len(response) > 4096:
                chunks = [response[i:i + 4096] for i in range(0, len(response), 4096)]
                embed.description = chunks[0]
                await interaction.followup.send(embed=embed)
                for chunk in chunks[1:]:
                    embed_chunk = discord.Embed(description=chunk, color=discord.Color.red())
                    await interaction.followup.send(embed=embed_chunk)
            else:
                embed.description = response if response else "No players online."
                await interaction.followup.send(embed=embed)
        except discord.NotFound:
            logger.debug("Interaction expired before final followup.send() in /online")
        except discord.errors.WebhookTokenMissing:
            logger.debug("Webhook token missing - interaction likely expired")

    except Exception as e:
        logger.error(f"Unhandled error in /online: {e}")
        # Try to send error message if interaction hasn't been responded to
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("An error occurred while processing your request.", ephemeral=True)
            else:
                await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)
        except:
            pass  # Silently fail if we can't send error message



@bot.tree.command(name="check", description="Check if a player is logged in.")
@app_commands.check(check_guild)
@app_commands.describe(name="The player's full name in the format Firstname_Lastname")
async def check(interaction: discord.Interaction, name: str = None):
    player_data = load_player_data()
    embed = discord.Embed(title="Player Status Check", color=discord.Color.red())

    # Check if name was provided
    if name is None:
        await interaction.response.send_message("Please provide a name in the format Firstname_Lastname.")
        return
    
    characters = [player["characterName"] for player in player_data.get("players", [])]

    if "_" not in name:  # Check if name contains '_'
        await interaction.response.send_message("Wrong format. Use Firstname_Lastname if you want the bot to work.")
        return
    
    if name in characters:
        response = f"{name} is currently logged in!"
    else:
        response = f"{name} is not logged in."

    embed.description = response  # Set the response in the embed description
    await interaction.response.send_message(embed=embed)  # Send the embed message

@bot.tree.command(name="last_online", description="Check the last seen time of a player.")
@app_commands.check(check_guild)
@app_commands.describe(full_name="The full name of the player (Firstname_Lastname).")
async def last_online(interaction: discord.Interaction, full_name: str):
    try:
        # Validate input BEFORE any interaction response
        if not full_name or "_" not in full_name:
            await interaction.response.send_message("Please provide a name in the format Firstname_Lastname.", ephemeral=True)
            return
        
        # Check if interaction is still valid before deferring
        if interaction.response.is_done():
            logger.debug("Interaction already responded to in /last_online")
            return
            
        try:
            await interaction.response.defer()
        except discord.NotFound:
            logger.debug("Interaction expired before defer() in /last_online")
            return
        except discord.errors.InteractionResponded:
            logger.debug("Interaction already responded to before defer() in /last_online")
            return

        last_seen_data = load_last_seen()
        last_seen_time = last_seen_data.get(full_name)

        try:
            if last_seen_time:
                last_seen_dt = datetime.strptime(last_seen_time, "%Y-%m-%dT%H:%M:%S.%fZ")
                readable_time = last_seen_dt.strftime("%Y-%m-%d %I:%M %p")

                embed = discord.Embed(title="Player Status", color=discord.Color.red())
                embed.add_field(name="Character Name", value=full_name, inline=False)
                embed.add_field(name="Last Seen", value=f"**{readable_time}**", inline=False)

                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"The player **{full_name}** does not appear to have a recorded last seen time.")
        except discord.NotFound:
            logger.debug("Interaction expired before followup.send() in /last_online")
        except discord.errors.WebhookTokenMissing:
            logger.debug("Webhook token missing - interaction likely expired")

    except Exception as e:
        logger.error(f"Unhandled error in /last_online: {e}")
        # Try to send error message if interaction hasn't been responded to
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("An error occurred while processing your request.", ephemeral=True)
            else:
                await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)
        except:
            pass  # Silently fail if we can't send error message


# Watchlist Management (Per-Guild)
def load_watchlists():
    """Load all guilds' watchlists from file."""
    watchlists_file = os.path.join(DATA_DIR, 'watchlists.json')
    if os.path.exists(watchlists_file):
        with open(watchlists_file, 'r') as f:
            return json.load(f)
    return {}

def save_watchlists(watchlists):
    """Save all guilds' watchlists to file."""
    watchlists_file = os.path.join(DATA_DIR, 'watchlists.json')
    with open(watchlists_file, 'w') as f:
        json.dump(watchlists, f, indent=4)

def get_guild_watchlist(guild_id):
    watchlists = load_watchlists()
    return watchlists.get(str(guild_id), [])

def set_guild_watchlist(guild_id, watchlist):
    watchlists = load_watchlists()
    watchlists[str(guild_id)] = watchlist
    save_watchlists(watchlists)

async def check_watchlists():
    """Check all guilds' watchlists and send notifications to their channels."""
    # Global status tracking like "They Gotta Go" system
    global watchlist_last_online_status
    
    while True:
        try:
            watchlists = load_watchlists()
            player_data = load_player_data()
            online_players = [player["characterName"] for player in player_data.get("players", [])]
            settings = load_config()
            
            for guild_id, watchlist in watchlists.items():
                # Initialize status tracking for this guild if not exists
                if guild_id not in watchlist_last_online_status:
                    watchlist_last_online_status[guild_id] = {}
                
                # Initialize status for new players in watchlist
                for player in watchlist:
                    if player not in watchlist_last_online_status[guild_id]:
                        watchlist_last_online_status[guild_id][player] = False
                
                channel_id = None
                if guild_id in settings:
                    channel_id = settings[guild_id].get('notification_channel_id')
                if not channel_id:
                    continue
                    
                channel = bot.get_channel(int(channel_id))
                if not channel:
                    continue
                
                # Use exact same logic as "They Gotta Go"
                for player in watchlist:
                    # Check if player is online AND was not online before
                    if player in online_players and not watchlist_last_online_status[guild_id][player]:
                        try:
                            await channel.send(f"@everyone **{player}** is now online!")
                            logger.info(f"Watchlist notification sent for {player} in guild {guild_id}")
                        except Exception as e:
                            logger.error(f"Error sending watchlist notification: {e}")
                        # Set status to True (online)
                        watchlist_last_online_status[guild_id][player] = True
                    # If player is not online anymore, set status to False
                    elif player not in online_players and watchlist_last_online_status[guild_id][player]:
                        watchlist_last_online_status[guild_id][player] = False
                    
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Error checking watchlists: {e}")
            await asyncio.sleep(30)

# Watchlist Global Status Tracking (like "They Gotta Go" system)
watchlist_last_online_status = {}  # Format: {guild_id: {player_name: is_online}}

# They Gotta Go Monitoring - DISABLED (using watchlist feature instead)
# they_gotta_go_names = []
# THEY_GOTTA_GO_CHANNEL = ''
# THEY_GOTTA_GO_GUILD_ID = ''
# last_online_status = {}

# async def they_gotta_go():
#     """Monitor specific players and send notifications when they come online."""
#     print("they_gotta_go has been started")
#     global last_online_status

#     while True:
#         if not last_online_status:
#             last_online_status.update({about_to_die.replace(" ", "_"): False for about_to_die in they_gotta_go_names})

#         player_data = load_player_data()
#         online_players = [player["characterName"] for player in player_data.get("players", [])]

#         if THEY_GOTTA_GO_CHANNEL:
#             try:
#                 channel = bot.get_channel(int(THEY_GOTTA_GO_CHANNEL))
#             except ValueError:
#                 print(f"Invalid channel ID: {THEY_GOTTA_GO_CHANNEL}")
#                 await asyncio.sleep(30)
#                 continue
#         else:
#             # Only log this once per hour to avoid spam
#             if not hasattr(they_gotta_go, '_last_empty_warning') or \
#                (time.time() - they_gotta_go._last_empty_warning) > 3600:
#                 print("THEY_GOTTA_GO_CHANNEL is empty! Configure it to enable this feature.")
#                 they_gotta_go._last_empty_warning = time.time()
#             await asyncio.sleep(30)
#             continue

#         if channel is None:
#             print(f"Failed to retrieve channel with ID {THEY_GOTTA_GO_CHANNEL}")
#             await asyncio.sleep(30)
#             continue

#         if channel.guild.id != int(THEY_GOTTA_GO_GUILD_ID):
#             print(f"Channel does not belong to the specified guild ID {THEY_GOTTA_GO_GUILD_ID}")
#             await asyncio.sleep(30)
#             continue

#         for about_to_die in they_gotta_go_names:
#             about_to_die_formatted = about_to_die.replace(" ", "_")
#             print(f"Checking player: {about_to_die_formatted}")

#             if about_to_die_formatted in online_players and not last_online_status[about_to_die_formatted]:
#                 await channel.send(f"@everyone {about_to_die} has just logged in!")
#                 last_online_status[about_to_die_formatted] = True
#             elif about_to_die_formatted not in online_players and last_online_status[about_to_die_formatted]:
#                 last_online_status[about_to_die_formatted] = False

#         await asyncio.sleep(30)





def is_owner(interaction: discord.Interaction) -> bool:
    """Check if the user is the bot owner."""
    return interaction.user.id == bot.owner_id

@bot.tree.command(name="watch", description="Manage your player watchlist")
@app_commands.check(is_owner)  # Only bot owner can use this command
@app_commands.check(check_guild)
@app_commands.describe(
    action="Action to perform: add, remove, edit, or list",
    player="Player name(s), comma or space separated (optional for edit/list)"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove"),
        app_commands.Choice(name="edit", value="edit"),
        app_commands.Choice(name="list", value="list"),
    ]
)
async def watch(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    player: str = None
):
    try:
        # Make list action public, others ephemeral
        is_ephemeral = action.value != "list"
        await interaction.response.defer(ephemeral=is_ephemeral)
    except discord.errors.NotFound:
        return  # Interaction expired or already responded to
    guild_id = str(interaction.guild_id)
    watchlist = get_guild_watchlist(guild_id)
    action_value = action.value
    if action_value == "add" and player:
        names = [n.strip() for n in player.replace(",", " ").split() if n.strip()]
        added = []
        already = []
        invalid_format = []
        
        for name in names:
            # Validate name format (must contain exactly one underscore)
            if "_" not in name or name.count("_") != 1:
                invalid_format.append(name)
                continue
                
            if name not in watchlist:
                watchlist.append(name)
                added.append(name)
            else:
                already.append(name)
                
        set_guild_watchlist(guild_id, watchlist)
        msg = []
        if added:
            msg.append(f"Added to this server's watchlist: {', '.join(added)}.")
        if already:
            msg.append(f"Already in watchlist: {', '.join(already)}.")
        if invalid_format:
            msg.append(f"Invalid format (use FirstName_LastName): {', '.join(invalid_format)}.")
        if not msg:
            msg = ["No valid names provided."]
        await interaction.followup.send(" ".join(msg), ephemeral=True)
    elif action_value == "remove" and player:
        # Normalize both input and stored names for robust matching
        input_names = [n.strip() for n in player.replace(",", " ").split() if n.strip()]
        # Create a mapping of normalized name -> original name in watchlist
        normalized_watchlist = {n.strip().lower(): n for n in watchlist}
        removed = []
        not_found = []
        for name in input_names:
            norm = name.strip().lower()
            if norm in normalized_watchlist:
                # Remove the original name from the watchlist
                watchlist.remove(normalized_watchlist[norm])
                removed.append(normalized_watchlist[norm])
            else:
                not_found.append(name)
        set_guild_watchlist(guild_id, watchlist)
        msg = []
        if removed:
            msg.append(f"Removed from this server's watchlist: {', '.join(removed)}.")
        if not_found:
            msg.append(f"Not in watchlist: {', '.join(not_found)}.")
        if not msg:
            msg = ["No valid names provided."]
        await interaction.followup.send(" ".join(msg), ephemeral=True)
    elif action_value == "edit":
        if not player:
            # Show current list and instructions
            if watchlist:
                embed = discord.Embed(title="Edit Watchlist", color=discord.Color.orange())
                embed.description = ("Current watchlist:\n" + "\n".join(watchlist) +
                    "\n\nTo replace the list, use:\n`/watch edit Name1 Name2 ...` or `/watch edit Name1,Name2,...`\n" +
                    "This will replace the entire watchlist with the names you provide.")
            else:
                embed = discord.Embed(title="Edit Watchlist", color=discord.Color.orange())
                embed.description = ("The watchlist is currently empty.\n" +
                    "To set a new list, use:\n`/watch edit Name1 Name2 ...` or `/watch edit Name1,Name2,...`")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            # Replace the list
            names = [n.strip() for n in player.replace(",", " ").split() if n.strip()]
            unique_names = []
            seen = set()
            for name in names:
                if name not in seen:
                    unique_names.append(name)
                    seen.add(name)
            set_guild_watchlist(guild_id, unique_names)
            embed = discord.Embed(title="Watchlist Updated", color=discord.Color.green())
            if unique_names:
                embed.description = "New watchlist:\n" + "\n".join(unique_names)
            else:
                embed.description = "The watchlist is now empty."
            await interaction.followup.send(embed=embed, ephemeral=True)
    elif action_value == "list":
        if watchlist:
            # Get current online players to show status
            player_data = load_player_data()
            online_players = [player["characterName"] for player in player_data.get("players", [])]
            
            # Format watchlist with online status
            formatted_list = []
            for name in watchlist:
                if name in online_players:
                    formatted_list.append(f"{name} **(online)**")
                else:
                    formatted_list.append(name)
            
            embed = discord.Embed(title=f"Watchlist for this server", color=discord.Color.red())
            embed.description = "\n".join(formatted_list)
        else:
            embed = discord.Embed(title="Watchlist is Empty", color=discord.Color.red())
        await interaction.followup.send(embed=embed, ephemeral=False)  # Make it public
    else:
        await interaction.followup.send("Invalid action. Use 'add', 'remove', 'edit', or 'list'.", ephemeral=True)


@bot.event
async def on_message(message):
    await bot.process_commands(message)  

@bot.event
async def on_app_command(interaction: discord.Interaction):
    """Log all slash command executions"""
    command_name = interaction.command.name if interaction.command else "Unknown"
    user = interaction.user
    guild = interaction.guild
    channel = interaction.channel
    
    log_message = (
        f"Command: /{command_name}\n"
        f"User: {user} ({user.id})\n"
        f"Guild: {guild.name if guild else 'DM'} ({guild.id if guild else 'N/A'})\n"
        f"Channel: #{channel.name if channel else 'DM'} ({channel.id if channel else 'N/A'})"
    )
    
    logger.info(log_message)

@bot.event
async def on_command(ctx):
    """Log all prefix command executions"""
    command_name = ctx.command.name if ctx.command else "Unknown"
    user = ctx.author
    guild = ctx.guild
    channel = ctx.channel
    
    log_message = (
        f"Command: !{command_name}\n"
        f"User: {user} ({user.id})\n"
        f"Guild: {guild.name if guild else 'DM'} ({guild.id if guild else 'N/A'})\n"
        f"Channel: #{channel.name if channel else 'DM'} ({channel.id if channel else 'N/A'})"
    )
    
    logger.info(log_message)

@bot.event
async def on_command_error(ctx, error):
    """Log command errors"""
    logger.error(f"Command error: {str(error)}")
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    else:
        await ctx.send(f"An error occurred: {str(error)}")

async def monitor_replies():
    """Monitor forum replies and send notifications based on files updated by forum_monitor.py."""
    # Track last seen reply IDs per topic to avoid duplicate notifications
    last_seen_file = os.path.join(DATA_DIR, 'last_seen_replies.json')
    
    # Load previously seen reply IDs from file (survives bot restarts)
    def load_last_seen():
        if os.path.exists(last_seen_file):
            try:
                with open(last_seen_file, 'r') as f:
                    data = json.load(f)
                    # Convert lists back to sets and ensure IDs are integers
                    return {topic_id: set(int(reply_id) for reply_id in reply_ids) for topic_id, reply_ids in data.items()}
            except (json.JSONDecodeError, Exception):
                pass
        return {}
    
    # Save seen reply IDs to file
    def save_last_seen(last_seen_reply_ids):
        try:
            # Convert sets to lists for JSON serialization, ensure integers
            data = {topic_id: list(reply_ids) for topic_id, reply_ids in last_seen_reply_ids.items()}
            with open(last_seen_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Error saving last seen replies: {e}")
    
    last_seen_reply_ids = load_last_seen()
    
    while True:
        try:
            settings = load_config()
            if not settings:
                await asyncio.sleep(60)
                continue

            for server_id, config in settings.items():
                if 'topic_id' in config and 'notification_channel_id' in config:
                    topic_id = config['topic_id']
                    channel_id = config['notification_channel_id']
                    
                    # Initialize tracking for this topic
                    if topic_id not in last_seen_reply_ids:
                        last_seen_reply_ids[topic_id] = set()
                    
                    # Load current replies from file (updated by forum_monitor.py)
                    current_replies = load_forum_data(topic_id)
                    if not current_replies:
                        continue
                    
                    # Check for new replies by comparing IDs
                    current_reply_ids = {int(reply.get('id')) for reply in current_replies if reply.get('id') and str(reply.get('id')).isdigit()}
                    new_reply_ids = current_reply_ids - last_seen_reply_ids[topic_id]
                    
                    # Send notifications for new replies
                    for reply in current_replies:
                        reply_id = reply.get('id')
                        if reply_id and str(reply_id).isdigit() and int(reply_id) in new_reply_ids:
                            await send_notification(reply, channel_id)
                    
                    # Update tracking
                    last_seen_reply_ids[topic_id] = current_reply_ids
            
            # Save the updated tracking to file
            save_last_seen(last_seen_reply_ids)

            await asyncio.sleep(60)  # Check every minute for file updates
        except Exception as e:
            logger.error(f"Error in monitor_replies: {e}")
            await asyncio.sleep(60)  # Wait before retrying

async def send_notification(new_reply, channel_id):
    """Send a notification to the specified channel when a new reply is detected."""
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return
    
    content, media_message = clean_html(new_reply.get("content", "No content available."))
    date_str = format_date(new_reply.get("date", "Unknown date"))

    if media_message:
        content += "\n" + media_message  # Append media message to content
    
    # Truncate if content exceeds the character limit
    if len(content) > 1024:
        content = content[:1021] + '...'

    embed = discord.Embed(title="New Reply Posted!", color=discord.Color.red())

    # Extract the author information
    author = new_reply.get("author", {})
    author_name = author.get("formattedName", "Unknown Author")[:256]  # Truncate if necessary
    author_name, _ = clean_html(author_name) # Cleaning any html tags.
    link = new_reply.get("url", "No link available")[:256]

    # Add fields to the embed
    embed.add_field(name="Author", value=author_name, inline=False)
    embed.add_field(name="Content", value=content, inline=False)
    embed.add_field(name="Date", value=str(date_str)[:256], inline=False)
    embed.add_field(name="Link", value=link, inline=False)

    await channel.send(embed=embed)

process = None
forum_process = None  # RE-ENABLED - using separate forum_monitor.py for better architecture

async def update_player_list_and_forum_comments():
    """Update player list and forum comments periodically."""
    global process
    global forum_process  # RE-ENABLED - using separate forum_monitor.py for better architecture
    
    while True:
        try:
            # Check and manage setup_db process
            if process is None or process.poll() is not None:
                # Clean up the old process if it exists
                if process is not None:
                    try:
                        process.terminate()
                        process.wait(timeout=5)
                    except:
                        pass
                
                # Kill any existing setup_db processes to prevent duplicates
                try:
                    subprocess.run(['pkill', '-f', 'setup_db.py'], capture_output=True, timeout=10)
                    await asyncio.sleep(2)  # Wait for cleanup
                except:
                    pass
                
                # Start new process
                logger.info("Starting setup_db.py process")
                process = subprocess.Popen(['/opt/lsrp/venv/bin/python', 'setup_db.py'])
            
            # Check and manage forum_monitor process
            if forum_process is None or forum_process.poll() is not None:
                # Clean up the old process if it exists
                if forum_process is not None:
                    try:
                        forum_process.terminate()
                        forum_process.wait(timeout=5)
                    except:
                        pass
                
                # Kill any existing forum_monitor processes to prevent duplicates
                try:
                    subprocess.run(['pkill', '-f', 'forum_monitor.py'], capture_output=True, timeout=10)
                    await asyncio.sleep(2)  # Wait for cleanup
                except:
                    pass
                
                # Start new process
                logger.info("Starting forum_monitor.py process")
                forum_process = subprocess.Popen(['/opt/lsrp/venv/bin/python', 'forum_monitor.py'])
            
            await asyncio.sleep(300)  # Keep 5-minute check interval
            
        except Exception as e:
            logger.error(f"Error in update_player_list_and_forum_comments: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying on error

async def cleanup_processes():
    """Clean up subprocess when bot shuts down."""
    global process, forum_process
    
    logger.info("Cleaning up processes...")
    
    # Clean up setup_db process
    if process is not None:
        try:
            process.terminate()
            process.wait(timeout=5)
            logger.info("setup_db.py process terminated")
        except:
            try:
                process.kill()
                logger.info("setup_db.py process killed")
            except:
                pass
    
    # Clean up forum_monitor process
    if forum_process is not None:
        try:
            forum_process.terminate()
            forum_process.wait(timeout=5)
            logger.info("forum_monitor.py process terminated")
        except:
            try:
                forum_process.kill()
                logger.info("forum_monitor.py process killed")
            except:
                pass

@bot.event
async def on_disconnect():
    """Handle bot disconnect."""
    logger.info("Bot disconnected")
    await cleanup_processes()

# Run the bot
try:
    bot.run(DISCORD_TOKEN)
except KeyboardInterrupt:
    logger.info("Bot stopped by user")
    asyncio.run(cleanup_processes())
except Exception as e:
    logger.error(f"Bot crashed: {e}")
    asyncio.run(cleanup_processes())
finally:
    asyncio.run(cleanup_processes())