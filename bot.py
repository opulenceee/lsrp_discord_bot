import discord
import json
from discord.ext import commands
import os
import asyncio
import subprocess
from dotenv import load_dotenv
from datetime import datetime
from bs4 import BeautifulSoup
from forum_monitor import fetch_total_pages, fetch_forum_replies, save_replies_to_file


load_dotenv()  # Load environment variables from .env file
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
FORUMS = 749      # Forums parameter (fixed)
PER_PAGE = 15     # Number of replies per page (fixed)
CONFIG_FILE = 'bot_config.json'
DATA_DIR = 'data'

intents = discord.Intents.default()
intents.messages = True  
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Load blocked guilds from a file
def load_blocked_guilds():
    blocked_guilds_file_path = os.path.join(DATA_DIR, 'blocked_guilds.json')  # Define path here
    try:
        with open(blocked_guilds_file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):  # Handle JSON decode errors
        return []

# Initialize blocked guilds globally
blocked_guilds = load_blocked_guilds()

# Save blocked guilds to a file
def save_blocked_guilds():
    blocked_guilds_file_path = os.path.join(DATA_DIR, 'blocked_guilds.json')  # Define path here
    with open(blocked_guilds_file_path, 'w') as f:
        json.dump(blocked_guilds, f)

@bot.command()
@commands.is_owner()  # Restricts the command to the bot owner
async def block_guild(ctx, guild_id: int):
    if guild_id not in blocked_guilds:
        blocked_guilds.append(guild_id)
        save_blocked_guilds()
        await ctx.send(f"Guild {guild_id} has been blocked.")
    else:
        await ctx.send("This guild is already blocked.")

@bot.command()
@commands.is_owner()  # Restricts the command to the bot owner
async def unblock_guild(ctx, guild_id: int):
    # Ensure guild_id is an integer
    guild_id = int(guild_id)  # Make sure we're working with an int

    # Check if the command is run in a blocked guild but still allow execution
    if ctx.guild and ctx.guild.id in blocked_guilds:
        await ctx.send("You are unblocking this server despite it being blocked.")

    if guild_id in blocked_guilds:
        blocked_guilds.remove(guild_id)
        save_blocked_guilds()
        await ctx.send(f"Guild {guild_id} has been unblocked.")
    else:
        await ctx.send(f"This guild {guild_id} is not blocked.")

    # Debugging step
    await ctx.send(f"Blocked guilds after unblocking: {blocked_guilds}")

# Global check to prevent commands in blocked guilds, except unblock_guild
@bot.check
async def globally_blocked(ctx):
    # Allow unblock_guild to run even in blocked guilds
    if ctx.command.name == "unblock_guild":
        return True  # Bypass the block for this command

    if ctx.guild and ctx.guild.id in blocked_guilds:
        await ctx.send("This server is blocked from using the bot.")
        return False
    return True


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

tasks_started = False

@bot.command(name='setup')
@commands.has_permissions(administrator=True)
async def setup(ctx, channel_id: int = None, topic_id: str = None):
    """Sets the channel and topic for notifications."""
    settings = load_config()  # Load existing settings
    guild_id = str(ctx.guild.id)

    # Ensure there's an entry for this guild
    if guild_id not in settings:
        settings[guild_id] = {}  # Initialize an empty dict for this guild if it doesn't exist

    # Update only the provided values
    if channel_id is not None:
        settings[guild_id]["notification_channel_id"] = channel_id
    if topic_id is not None:
        settings[guild_id]["topic_id"] = topic_id

    save_config(settings)  # Save the updated settings

    # Build confirmation message
    msg_parts = []
    if channel_id is not None:
        msg_parts.append(f"Notification channel set to <#{channel_id}>.")
    if topic_id is not None:
        msg_parts.append(f"Topic ID set to `{topic_id}`.")
    if not msg_parts:
        await ctx.send("Please provide at least one value to update (channel ID or topic ID).")
        return

    await ctx.send(" ".join(msg_parts))

    global tasks_started
    if not tasks_started:
        bot.loop.create_task(update_player_list_and_forum_comments())
        bot.loop.create_task(monitor_replies())
        tasks_started = True

# Handle missing permissions error for setup
@setup.error
async def setup_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You must have administrator permissions to use this command.")
    else:
        await ctx.send(f"An unexpected error occurred: {str(error)}")


@bot.command()
@commands.has_permissions(administrator=True)
async def remove(ctx):
    server_id = str(ctx.guild.id)
    server_settings = load_config()

    if server_id in server_settings:
        del server_settings[server_id]  # Remove the server's settings
        save_config(server_settings)  # Save updated settings
        await ctx.send("Configuration removed for this server.")
    else:
        await ctx.send("No configuration found for this server.")

@remove.error
async def remove_error(ctx, error):
    print(f"Error Type: {type(error)}")  # Log the error type
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You must have administrator permissions to use this command.")
    else:
        await ctx.send(f"An unexpected error occurred: {str(error)}")



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



@bot.command()
async def info(ctx):
    embed = discord.Embed(title="Bot Functionality Guide", color=discord.Color.red())

    helpMessage = """
1. **!setup** - Admin command to set or update the bot configuration. Usage:
   - `!setup CHANNEL_ID` - Set the notification channel only (enables UCP monitoring).
   - `!setup CHANNEL_ID TOPIC_ID` - Set both the channel and topic (enables UCP and forum monitoring).
2. **!remove** - Admin command to delete the current bot configuration for this server, disabling all functionalities.
3. **!online** - Displays a list of all logged-in players.
4. **!admins** - Shows a list of currently online admins.
5. **!testers** - Lists all logged-in testers.
6. **!check FirstName_LastName** - Checks if the specified player is currently online.
7. **!latest** - Displays the last reply on our forum thread and its author.
8. **!thread** - Shows how many replies are left for the next page.
9. **!show_settings** - Shows the current configuration of the bot.
10. **!last_online FirstName_LastName** - Displays the last online status of the specified player.
"""

    embed.description = helpMessage
    await ctx.send(embed=embed)


@bot.command(name='show_settings')
async def show_settings(ctx):
    """Sets the channel and topic for notifications based on existing settings."""
    settings = load_config()  # Load existing settings
    guild_id = str(ctx.guild.id)

    if not is_configured(guild_id):
        await ctx.send("This bot is not configured for this server. Please run `!setup` to configure it.")
        return

    # Check if settings exist for the guild
    if guild_id in settings:
        notification_channel_id = settings[guild_id].get("notification_channel_id")
        topic_id = settings[guild_id].get("topic_id")

        if notification_channel_id and topic_id:
            await ctx.send(f"Notification channel is set to <#{notification_channel_id}> for topic ID `{topic_id}`.")
        else:
            await ctx.send("Notification channel ID or topic ID is not set.")
    else:
        await ctx.send("No settings found for this server. Please set them using the appropriate command.")    

@bot.command(name='latest')
async def latest(ctx):
    """Displays the last reply and its author, date."""
    settings = load_config()
    guild_id = str(ctx.guild.id)

    if not is_configured(guild_id):
        await ctx.send("This bot is not configured for this server. Please run `!setup` to configure it.")
        return
    
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

            await ctx.send(embed=embed)
        else:
            await ctx.send("No replies found.")
    else:
        await ctx.send("Please set up a topic ID first using `!setup channel_id topic_id`.")

@bot.command(name='thread')
async def thread(ctx):
    settings = load_config()
    guild_id = str(ctx.guild.id)

    if not is_configured(guild_id):
        await ctx.send("This bot is not configured for this server. Please run `!setup` to configure it.")
        return

    if guild_id in settings and settings[guild_id]["topic_id"]:
        topic_id = settings[guild_id]["topic_id"]
        replies = load_forum_data(topic_id) 

        if replies:
            current_replies = len(replies)
            replies_left = 15 - current_replies

            embed = discord.Embed(title="Replies Status", color=discord.Color.red())
            embed.add_field(name="Current Replies", value=current_replies, inline=False)
            embed.add_field(name="Replies Left for New Page", value=replies_left, inline=False)

            await ctx.send(embed=embed)
        else:
            await ctx.send("No replies found")
    else:
        await ctx.send("Please set up a topic ID first using `!setup channel_id topic_id`.")


@bot.command()
async def admins(ctx):
    guild_id = str(ctx.guild.id)

    if not is_configured(guild_id):
        await ctx.send("This bot is not configured for this server. Please run `!setup` to configure it.")
        return
    
    player_data = load_player_data()
    
    embed = discord.Embed(title="Online Admins", color=discord.Color.red())
    if not player_data or "players" not in player_data:
        await ctx.send("No player data available.")
        return

    admin_names = []
    for player in player_data["players"]:
        if player.get("isAdmin", False):
            character_name = player.get("characterName", "Unknown")
            account_name = player.get("accountName", "Unkown")
            admin_names.append(f"{character_name} **({account_name})**")

    if admin_names:
        embed.description = "\n".join(admin_names)
    else:
        embed.description = "No admins are currently logged in."

    await ctx.send(embed=embed)

@bot.command()
async def testers(ctx):
    guild_id = str(ctx.guild.id)

    if not is_configured(guild_id):
        await ctx.send("This bot is not configured for this server. Please run `!setup` to configure it.")
        return
    
    player_data = load_player_data()
    embed = discord.Embed(title="Online Testers", color=discord.Color.red())
    if not player_data or "players" not in player_data:
        await ctx.send("No player data available.")
        return
    
    tester_names = []
    for player in player_data["players"]:
        if player.get("isTester", "False"):
            character_name = player.get("characterName", "Unkown")
            account_name = player.get("accountName", "Unkown")
            tester_names.append(f"{character_name} **({account_name})**")

    if tester_names:
        embed.description = "\n".join(tester_names)
    else:
        embed.description = "No testers are currently logged in."

    await ctx.send(embed=embed)

    
@bot.command()
async def online(ctx):
    guild_id = str(ctx.guild.id)

    if not is_configured(guild_id):
        await ctx.send("This bot is not configured for this server. Please run `!setup` to configure it.")
        return
    
    player_data = load_player_data()  # Load player data from JSON
    if not player_data or "players" not in player_data:
        await ctx.send("No player data available.")
        return

    # Extract the names of the players
    player_names = [player["characterName"] for player in player_data["players"]]
    player_count = len(player_names)

    # Prepare the response
    response = "\n".join(player_names)

    embed = discord.Embed(title=f"Online Players ({player_count}):", color=discord.Color.red())

    if len(response) > 4096:
        embed.description = response[:4096]  
        await ctx.send(embed=embed)

        # Send additional chunks without the title
        for i in range(4096, len(response), 4096):
            chunk = response[i:i + 4096]
            embed_chunk = discord.Embed(color=discord.Color.red(), description=chunk)
            await ctx.send(embed=embed_chunk)
    else:
    # Send the response to the Discord channel
        embed.description = response
        await ctx.send(embed=embed)


@bot.command()
async def check(ctx, name: str = None):  # Set default to None to allow checking for missing argument
    guild_id = str(ctx.guild.id)

    if not is_configured(guild_id):
        await ctx.send("This bot is not configured for this server. Please run `!setup` to configure it.")
        return
    
    player_data = load_player_data()
    embed = discord.Embed(title="Player Status Check", color=discord.Color.red())


    # Check if name was provided
    if name is None:
        await ctx.send("Please provide a name in the format Firstname_Lastname.")
        return
    
    characters = [player["characterName"] for player in player_data.get("players", [])]

    if "_" not in name:  # Check if name contains '_'
        await ctx.send("Wrong format. Use Firstname_Lastname if you want the bot to work.")
        return
    
    if name in characters:
        response = f"{name} is currently logged in!"
    else:
        response = f"{name} is not logged in."

    embed.description = response  # Set the response in the embed description
    await ctx.send(embed=embed)  # Send the embed message

@bot.command(name="last_online")
async def last_online(ctx, full_name: str):
    last_seen_data = load_last_seen()  # Load only last seen data

    # Check if the player's last seen data exists
    last_seen_time = last_seen_data.get(full_name)

    if last_seen_time:
        # Convert the last seen time to a datetime object
        last_seen_dt = datetime.strptime(last_seen_time, "%Y-%m-%dT%H:%M:%S.%fZ")
        readable_time = last_seen_dt.strftime("%Y-%m-%d %I:%M %p")  # Format to 'YYYY-MM-DD HH:MM AM/PM'

        # Create an embed message for Discord
        embed = discord.Embed(title="Player Status", color=discord.Color.red())
        embed.add_field(name="Character Name", value=full_name, inline=False)
        embed.add_field(name="Last Seen", value=f"**{readable_time}**", inline=False)

        await ctx.send(embed=embed)
    else:
        await ctx.send(f"The player **{full_name}** does not appear to have a recorded last seen time.")

last_reply_ids = {}

async def monitor_replies():
    settings = load_config()
    if not settings:
        print("No configuration found. Monitor not starting.")
        return  # Don't start monitoring if no configuration is set up.

    while True:
        settings = load_config()
        for guild_id, config in settings.items():
            topic_id = config.get("topic_id")
            channel_id = config.get("notification_channel_id")
            
            if not topic_id or not channel_id:
                continue

            # Dynamically fetch replies for the current topic_id
            total_pages = fetch_total_pages(topic_id, FORUMS)
            if total_pages is None or total_pages == 0:
                print(f"No pages available to monitor for topic ID {topic_id}.")
                await asyncio.sleep(240)  # Sleep longer if no pages available
                continue

            last_page_replies = fetch_forum_replies(topic_id, FORUMS, total_pages)
            if last_page_replies:
                save_replies_to_file(last_page_replies, topic_id)  # Update this to save to specific file

                # Check for new replies since the last known ID
                latest_reply = last_page_replies[-1]
                latest_reply_id = latest_reply["id"]

                # If this is a new reply, send notification
                if last_reply_ids.get(guild_id) != latest_reply_id:
                    last_reply_ids[guild_id] = latest_reply_id
                    await send_notification(latest_reply, channel_id)

            await asyncio.sleep(240)  #

async def send_notification(new_reply, channel_id):
    """Send a notification to the specified channel when a new reply is detected."""
    channel = bot.get_channel(int(channel_id))
    if not channel:
        print(f"Notification channel {channel_id} not found.")
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
    print(f"Notification sent to channel {channel_id}.")

process = None
forum_process = None

async def update_player_list_and_forum_comments():
    global process
    global forum_process
    if process is None and forum_process is None:
       process = subprocess.Popen(['/opt/lsrp/venv/bin/python', 'setup_db.py'])
       forum_process = subprocess.Popen(['/opt/lsrp/venv/bin/python','forum_monitor.py'])
        # Run your setup_db.py script without blocking


    while True:
        await asyncio.sleep(15)  # Continue to wait 30 seconds
        # await check_for_serbians_online()  # Just check for online players, no subprocess needed


@bot.event
async def on_ready():
    global tasks_started
    print(f'Logged in as {bot.user}')

    # Check if config exists on startup
    config = load_config()
    if config and not tasks_started:
        bot.loop.create_task(update_player_list_and_forum_comments())
        bot.loop.create_task(monitor_replies())
        tasks_started = True

# Run the bot
bot.run(DISCORD_TOKEN)