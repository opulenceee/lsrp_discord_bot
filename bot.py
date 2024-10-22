import discord
import json
from discord.ext import commands
import os
import asyncio
import subprocess
from dotenv import load_dotenv


load_dotenv()  # Load environment variables from .env file
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
JSON_FILE_PATH = 'player_list.json'
NOTIFICATION_CHANNEL_ID = 1297658903965991045



intents = discord.Intents.default()
intents.messages = True  
intents.message_content = True


def load_player_data():
    if os.path.exists(JSON_FILE_PATH):
        with open(JSON_FILE_PATH, "r") as file:
            return json.load(file)
    return {}

bot = commands.Bot(command_prefix='!', intents=intents)

  #List of online Serbians
serbians = [
        "Vahan Kalajian",
        "Slobodan Milovanovic",
        "David Komljenovic",
        "Vuksan Adzic",
        "Vasko Bojevic",
        "Dragan Agovic",
        "Rade Bojovic",
        "Relja Bjelic",
        "Zoran Brdjanin",
        "Spasoje Obradovic",
        "Lazar Vladimirovic",
        "Ivo Vutovic",
        "Peter Lazic",
        "Vasilije Stefanovic",
        "Emilijan Borisov",
        "Goran Strahota",
        "Nemanja Stojkovic",
        "Dragomir Sarovic",
        "Antonije Simic"
    ]

last_online_status = {}

async def check_for_serbians_online():
    global last_online_status
    
    # Initialize last_online_status if it's empty (first run)
    if not last_online_status:
        last_online_status.update({serbian.replace(" ", "_"): False for serbian in serbians})

    player_data = load_player_data()
    online_players = [player["characterName"] for player in player_data.get("players", [])]
    channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)

    if channel is None:
        print(f"Failed to retrieve channel with ID {NOTIFICATION_CHANNEL_ID}")
        return  # Ensure the bot is fetching the right channel

    for serbian in serbians:
        serbian_formatted = serbian.replace(" ", "_")

        if serbian_formatted in online_players and not last_online_status[serbian_formatted]:
            await channel.send(f"@everyone {serbian} has just logged in!")
            last_online_status[serbian_formatted] = True  # Player logged in

        elif serbian_formatted not in online_players and last_online_status[serbian_formatted]:
            last_online_status[serbian_formatted] = False  # Player logged out
            
        
@bot.command()
async def commands(ctx):
    embed = discord.Embed(title="Bot Functionality Guide", color=discord.Color.red())

    helpMessage = """
1. **!online** - Displays a list of all logged-in players.
2. **!admins** - Shows a list of currently online admins.
3. **!testers** - Lists all logged-in testers.
4. **!check FirstName_LastName** - Checks if the specified player is currently online.
5. **!war** - Displays the current status of members of the STCO (alive/dead). This will be removed once the war is over.
6. **!serbia** - Displays all logged in serbians who are still alive."
"""

    embed.description = helpMessage.strip()  # Use strip() to remove any extra leading/trailing whitespace

    await ctx.send(embed=embed)

@bot.command()
async def serbia(ctx):
  
    player_data = load_player_data()
    online_players = [player["characterName"] for player in player_data.get("players", [])]
    embed = discord.Embed(title="Online Serbians", color=discord.Color.red())
    online_status = []

    for serbian in serbians:
        serbian_formatted = serbian.replace(" ", "_")
        if serbian_formatted in online_players:
            online_status.append(f"**{serbian} is online**.")
        
    response = "\n".join(online_status) if online_status else "No Serbians are online."
    embed.description = response

    await ctx.send(embed=embed)


@bot.command()
async def war(ctx):
    #List of Serbians:
    people = [
    "Slobodan Milovanovic (David_Komljenovic)",
        "Vuksan Adzic",
        "Vasko Bojevic",
        "Dragan Agovic",
        "Radovan Predimirovic - DEAD",
        "Rade Bojovic",
        "Relja Bjelic",
        "Zoran Brdjanin",
        "Spasoje Obradovic",
        "Lazar Vladimirovic",
        "Ivo Vutovic",
        "Peter Lazic",
        "Vasilije Stefanovic",
        "Emilijan Borisov",
        "Goran Strahota",
        "Nemanja Stojkovic",
        "Dragomir Sarovic",
        "Antonije Simic",
        "Marko Pajic - DEAD",
        "Milorad Pajic - DEAD",
        "Bosko Brankovic - DEAD",
        "Vlado Predimirovic - DEAD",
        "Danijel Krstovic - DEAD"
    ]

    alive = []
    dead = []

    for person in people:
        if "DEAD" in person:
            dead.append(person.replace(" ", ""))
        else:
            alive.append(person)

    embed = discord.Embed(title="Serbian Transnational Criminal Organistation", color=discord.Color.red())

    embed.add_field(name="Alive", value="\n".join(alive) if alive else "No one is alive.", inline=False)
    embed.add_field(name="Dead", value="\n".join(dead) if dead else "No one is dead.", inline=False)

    await ctx.send(embed=embed)


@bot.command()
async def admins(ctx):
    player_data = load_player_data()
    embed = discord.Embed(title="Online Admins", color=discord.Color.red())
    if not player_data or "players" not in player_data:
        await ctx.send("No player data available.")
        return

    admin_names = [player["characterName"] for player in player_data["players"] if player.get("isAdmin", False)]

    if admin_names:
        response = f"\n".join(admin_names)
        embed.description = response
    else:
        response = "No admins are currently logged in."
        embed.description = response

    await ctx.send(embed=embed)

@bot.command()
async def testers(ctx):
    player_data = load_player_data()
    embed = discord.Embed(title="Online Testers", color=discord.Color.red())
    if not player_data or "players" not in player_data:
        await ctx.send("No player data available.")
        return
    
    tester_names = [player["characterName"] for player in player_data["players"] if player.get("isTester", False)]

    if tester_names:
        response = f"\n".join(tester_names)
        embed.description = response

    else:
        response = f"No testers are currently logged in."
        embed.description = response

    await ctx.send(embed=embed)

    
@bot.command()
async def online(ctx):
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


async def update_player_list():
    while True:
        await asyncio.sleep(30)  # Wait for 30 seconds
        loop = asyncio.get_running_loop()
        # Run your setup_db.py script without blocking
        await loop.run_in_executor(None, subprocess.run, ['/opt/lsrp/venv/bin/python', 'setup_db.py'])
        await check_for_serbians_online()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    bot.loop.create_task(update_player_list())

# Run the bot
bot.run(DISCORD_TOKEN)