""""
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
        "Antonije Simic - DEAD",
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
            dead.append(person)
        else:
            alive.append(person)

    embed = discord.Embed(title="Serbian Transnational Criminal Organistation", color=discord.Color.red())

    embed.add_field(name="Alive", value="\n".join(alive) if alive else "No one is alive.", inline=False)
    embed.add_field(name="Dead", value="\n".join(dead) if dead else "No one is dead.", inline=False)

    await ctx.send(embed=embed)



  #List of online Serbians
serbians = [
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
    ]

last_online_status = {}

async def check_for_serbians_online():
    print("check_for_serbians_online has been called")  # Debugging line
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
        print(f"Checking player: {serbian_formatted}")  # Debugging line 

        if serbian_formatted in online_players and not last_online_status[serbian_formatted]:
            await channel.send(f"@everyone {serbian} has just logged in!")
            last_online_status[serbian_formatted] = True  # Player logged in

        elif serbian_formatted not in online_players and last_online_status[serbian_formatted]:
            last_online_status[serbian_formatted] = False  # Player logged out
"""