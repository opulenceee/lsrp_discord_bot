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
from discord.ui import Button, View
from discord import app_commands



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


@bot.tree.command(name="creator", description="Learn more about who created this bot.")
async def creator(interaction: discord.Interaction):
    # Create a button that links to your website
    button = Button(label="Visit Official Website", url="https://opulenceee.wtf")
    
    # Create a view to hold the button
    view = View()
    view.add_item(button)

    # Send a message with the button and creator info
    await interaction.response.send_message(
        content="This bot was created by **opulenceee.**. You can find more information about me at my official website.",
        view=view
    )

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

# Global check to prevent commands in blocked guilds, except unblock_guild
async def check_guild(interaction: discord.Interaction) -> bool:
    if interaction.guild and interaction.guild.id in blocked_guilds:
        await interaction.response.send_message(
            f"Commands are disabled for **{interaction.guild.name}**. "
            "Please contact the bot owner if you think this is an error."
        ) 
        return False  # Block this guild
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

tasks_started = False

@bot.tree.command(name="setup", description="Configure bot settings for this server")
@app_commands.check(check_guild)
async def setup(interaction: discord.Interaction, channel_id: str, topic_id: str = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You must have administrator permissions to use this command.", ephemeral=True)
        return

    settings = load_config()
    guild_id = str(interaction.guild_id)

    if guild_id not in settings:
        settings[guild_id] = {}

    try:
        channel_id = int(channel_id)
        settings[guild_id]["notification_channel_id"] = channel_id
        if topic_id:
            settings[guild_id]["topic_id"] = topic_id

        save_config(settings)

        msg_parts = []
        msg_parts.append(f"Notification channel set to <#{channel_id}>.")
        if topic_id:
            msg_parts.append(f"Topic ID set to `{topic_id}`.")

        await interaction.response.send_message(" ".join(msg_parts))

        global tasks_started
        if not tasks_started:
            bot.loop.create_task(update_player_list_and_forum_comments())
            bot.loop.create_task(monitor_replies())
            tasks_started = True

    except ValueError:
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

    if not is_configured(guild_id):
        await interaction.response.send_message("This bot is not configured for this server. Please run `/setup` to configure it.")
        return

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

    if not is_configured(guild_id):
        await interaction.response.send_message("This bot is not configured for this server. Please run `/setup` to configure it.")
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

    if not is_configured(guild_id):
        await interaction.response.send_message("This bot is not configured for this server. Please run `/setup` to configure it.")
        return

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
    guild_id = str(interaction.guild_id)

    if not is_configured(guild_id):
        await interaction.response.send_message("This bot is not configured for this server. Please use /setup to configure it.")
        return

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
    guild_id = str(interaction.guild_id)

    if not is_configured(guild_id):
        await interaction.response.send_message("This bot is not configured for this server. Please use /setup to configure it.")
        return

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
    guild_id = str(interaction.guild_id)

    if not is_configured(guild_id):
        await interaction.response.send_message("This bot is not configured for this server. Please use /setup to configure it.")
        return

    player_data = load_player_data()
    if not player_data or "players" not in player_data:
        await interaction.response.send_message("No player data available.")
        return

    player_names = [player["characterName"] for player in player_data["players"]]
    player_count = len(player_names)
    response = "\n".join(player_names)

    embed = discord.Embed(title=f"Online Players ({player_count}):", color=discord.Color.red())
    
    # Handle long responses
    if len(response) > 4096:
        chunks = [response[i:i + 4096] for i in range(0, len(response), 4096)]
        embed.description = chunks[0]
        await interaction.response.send_message(embed=embed)
        
        for chunk in chunks[1:]:
            embed_chunk = discord.Embed(color=discord.Color.red(), description=chunk)
            await interaction.followup.send(embed=embed_chunk)
    else:
        embed.description = response
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="check", description="Check if a player is logged in.")
@app_commands.check(check_guild)
@app_commands.describe(name="The player's full name in the format Firstname_Lastname")
async def check(interaction: discord.Interaction, name: str = None):
    guild_id = str(interaction.guild.id)

    if not is_configured(guild_id):
        await interaction.response.send_message("This bot is not configured for this server. Please run `/setup` to configure it.")
        return
    
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

        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"The player **{full_name}** does not appear to have a recorded last seen time.")

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

they_gotta_go_names = []
THEY_GOTTA_GO_CHANNEL = ''
THEY_GOTTA_GO_GUILD_ID = ''
last_online_status = {}

async def they_gotta_go():
    print("they_gotta_go has been started")
    global last_online_status

    while True:
        if not last_online_status:
            last_online_status.update({about_to_die.replace(" ", "_"): False for about_to_die in they_gotta_go_names})

        player_data = load_player_data()
        online_players = [player["characterName"] for player in player_data.get("players", [])]

        if THEY_GOTTA_GO_CHANNEL:
            try:
                channel = bot.get_channel(int(THEY_GOTTA_GO_CHANNEL))
            except ValueError:
                # Handle the case where the channel ID is invalid
                print(f"Invalid channel ID: {THEY_GOTTA_GO_CHANNEL}")
                await asyncio.sleep(30)  # Wait before retrying
                continue
        else:
            print("THEY_GOTTA_GO_CHANNEL is empty!")
            await asyncio.sleep(30)  # Wait before retrying
            continue

        if channel is None:
            print(f"Failed to retrieve channel with ID {THEY_GOTTA_GO_CHANNEL}")
            await asyncio.sleep(30)  # Wait before retrying
            continue

        if channel.guild.id != int(THEY_GOTTA_GO_GUILD_ID):
            print(f"Channel does not belong to the specified guild ID {THEY_GOTTA_GO_GUILD_ID}")
            await asyncio.sleep(30)  # Wait before retrying
            continue

        for about_to_die in they_gotta_go_names:
            about_to_die_formatted = about_to_die.replace(" ", "_")
            print(f"Checking player: {about_to_die_formatted}")  # debugging

            if about_to_die_formatted in online_players and not last_online_status[about_to_die_formatted]:
                await channel.send(f"@everyone {about_to_die} has just logged in!")
                last_online_status[about_to_die_formatted] = True  # player logged in

            elif about_to_die_formatted not in online_players and last_online_status[about_to_die_formatted]:
                last_online_status[about_to_die_formatted] = False  # player logged out

        await asyncio.sleep(30)  # Run every 30 seconds

async def send_support_message():
    """Send support message every 4 hours to all configured channels."""
    while True:
        settings = load_config()
        if settings:
            embed = discord.Embed(
                title="❤️ Support LSRP Bot Development!",
                description=(
                    "**Hey everyone!** Thanks for using the LSRP Bot!\n\n"
                    "🤖 **What this bot offers:**\n"
                    "• Real-time player tracking\n"
                    "• Forum thread monitoring\n"
                    "• Admin & tester status checks\n"
                    "• Last seen player tracking\n"
                    "And much more!\n\n"
                    "🌟 **If you're finding this bot useful**, consider supporting its development! "
                    "Every coffee helps keep the servers running and features coming!"
                ),
                color=discord.Color.red()
            )
            
            # Add footer with bot stats
            embed.set_footer(text=f"Currently serving {len(settings)} communities!")
            
            # Add timestamp to show when the message was sent
            embed.timestamp = datetime.now()

            # Create a view with multiple buttons
            view = View()
            
            # Support button
            support_button = Button(
                label="☕ Buy Me a Coffee", 
                url="https://buymeacoffee.com/opulenceee",
                style=discord.ButtonStyle.link
            )
            view.add_item(support_button)
            
            # Add website button if you have one
            website_button = Button(
                label="🌐 Visit Website", 
                url="https://opulenceee.wtf",
                style=discord.ButtonStyle.link
            )
            view.add_item(website_button)

            # Send to all configured channels
            for guild_id, config in settings.items():
                channel_id = config.get("notification_channel_id")
                if channel_id:
                    try:
                        channel = bot.get_channel(int(channel_id))
                        if channel:
                            await channel.send(embed=embed, view=view)
                    except Exception as e:
                        print(f"Failed to send support message to channel {channel_id}: {e}")

        # Wait for 4 hours
        await asyncio.sleep(28800)  # 4 hours in seconds


@bot.event
async def on_ready():
    global tasks_started
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')

    # Check if config exists on startup
    config = load_config()
    if config and not tasks_started:
        bot.loop.create_task(update_player_list_and_forum_comments())
        bot.loop.create_task(monitor_replies())
        bot.loop.create_task(send_support_message())
        # bot.loop.create_task(they_gotta_go())  # Add this line
        tasks_started = True

# Run the bot
bot.run(DISCORD_TOKEN)