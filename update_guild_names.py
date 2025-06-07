import discord
import json
import os
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CONFIG_FILE = 'bot_config.json'

class UpdateBot(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user}')
        
        # Load existing config
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        # Update each guild's config with its name
        updated = False
        for guild_id in config:
            try:
                guild = self.get_guild(int(guild_id))
                if guild:
                    if 'guild_name' not in config[guild_id]:
                        config[guild_id]['guild_name'] = guild.name
                        updated = True
                        print(f"Added name for guild: {guild.name}")
                else:
                    print(f"Could not find guild with ID {guild_id}")
            except Exception as e:
                print(f"Error processing guild {guild_id}: {e}")
        
        if updated:
            # Save updated config
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            print("Config file updated successfully!")
        else:
            print("No updates needed.")
        
        await self.close()

# Run the update
intents = discord.Intents.default()
intents.guilds = True  # Enable guilds intent
client = UpdateBot(intents=intents)
client.run(DISCORD_TOKEN) 