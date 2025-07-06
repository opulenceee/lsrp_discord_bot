import discord
import asyncio
import os
import json
import csv
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import List, Optional, Dict, Any

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

class ServerManager:
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True
        intents.members = True
        
        self.bot = discord.Client(intents=intents)
        self.guilds = []
        self.ready = False
        
        # Set up event handlers
        @self.bot.event
        async def on_ready():
            print("✅ Bot is ready!")
            self.guilds = self.bot.guilds
            print(f"📊 Found {len(self.guilds)} servers")
            self.ready = True
    
    def create_server_logs_dir(self, guild: discord.Guild) -> str:
        """Create and return the logs directory path for a specific server"""
        safe_guild_name = self.sanitize_filename(guild.name)
        logs_dir = f"logs/{safe_guild_name}_{guild.id}"
        os.makedirs(logs_dir, exist_ok=True)
        return logs_dir
    
    def sanitize_filename(self, name: str) -> str:
        """Sanitize a string to be safe for use as a filename"""
        return name.replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_").replace("?", "_").replace("\"", "_").replace("<", "_").replace(">", "_").replace("|", "_").replace("#", "")
        
    async def initialize(self):
        """Initialize the bot and fetch guilds"""
        try:
            print("🔐 Logging in...")
            
            # Start the bot in the background
            bot_task = asyncio.create_task(self.bot.start(DISCORD_TOKEN))
            
            # Wait for the bot to be ready
            timeout = 30  # 30 second timeout
            start_time = asyncio.get_event_loop().time()
            
            while not self.ready:
                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise TimeoutError("Bot connection timed out after 30 seconds")
                await asyncio.sleep(0.1)
            
            print("🌐 Connected to Discord successfully!")
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            if not self.bot.is_closed():
                await self.bot.close()
            raise
        
    def display_servers(self):
        """Display all servers the bot is in"""
        print("\n" + "="*50)
        print("🌐 DISCORD SERVERS")
        print("="*50)
        
        if not self.guilds:
            print("❌ Bot is not in any servers!")
            return False
            
        for i, guild in enumerate(self.guilds, 1):
            member_count = guild.member_count or "Unknown"
            print(f"{i:2d}. {guild.name} (ID: {guild.id}) - {member_count} members")
        
        print("="*50)
        return True
    
    def display_actions_menu(self, guild_name: str):
        """Display available actions for a selected server"""
        print(f"\n" + "="*50)
        print(f"⚙️  ACTIONS FOR: {guild_name}")
        print("="*50)
        print("1. 🗑️  Remove all channels")
        print("2. 🧹 Remove all messages (from all channels)")
        print("3. 🎭 Remove all roles")
        print("4. 📤 Send a message to a specific channel")
        print("5. 💥 NUCLEAR OPTION: Delete everything")
        print("")
        print("📊 SERVER ANALYTICS & INFO:")
        print("6. 📈 Server statistics")
        print("7. 👥 Member analysis")
        print("8. 📋 Channel overview")
        print("9. 🎭 Role overview")
        print("")
        print("🎯 SMART BULK OPERATIONS:")
        print("10. 🔍 Delete channels by pattern")
        print("11. 🏷️  Mass role assignment")
        print("12. 📁 Create channel categories")
        print("13. 🧹 Clean nicknames")
        print("")
        print("📢 ADVANCED MESSAGING:")
        print("14. 📨 Mass DM users")
        print("15. 📢 Multi-channel announcement")
        print("16. 🎨 Create embed message")
        print("17. 📋 Message all role members")
        print("")
        print("👥 USER MANAGEMENT:")
        print("18. 🔨 Mass ban/kick users")
        print("19. 📊 Export member list")
        print("20. 👑 Manage role hierarchy")
        print("21. 🔍 Find users by criteria")
        print("")
        print("🕵️ MONITORING & SURVEILLANCE:")
        print("22. 👁️  Message sniffer (live monitor)")
        print("23. 📜 Channel history export")
        print("24. 🔍 Search messages by keyword")
        print("")
        print("🚪 BOT MANAGEMENT:")
        print("25. 🚪 Leave this server (uninvite bot)")
        print("")
        print("26. ⬅️  Go back to server selection")
        print("0. ❌ Exit")
        print("="*50)
    
    async def remove_all_channels(self, guild: discord.Guild):
        """Remove all channels from a guild"""
        print(f"\n🗑️  Starting channel deletion for '{guild.name}'...")
        
        channels = guild.channels
        total_channels = len(channels)
        deleted_count = 0
        
        print(f"📊 Found {total_channels} channels to delete")
        
        for i, channel in enumerate(channels, 1):
            try:
                await channel.delete(reason="Bulk deletion via server manager")
                deleted_count += 1
                print(f"✅ Deleted [{i}/{total_channels}]: #{channel.name}")
                await asyncio.sleep(0.5)  # Rate limiting
            except discord.Forbidden:
                print(f"❌ No permission to delete: #{channel.name}")
            except discord.NotFound:
                print(f"⚠️  Channel already deleted: #{channel.name}")
            except Exception as e:
                print(f"❌ Error deleting #{channel.name}: {e}")
        
        print(f"\n✅ Channel deletion complete! Deleted {deleted_count}/{total_channels} channels")
    
    async def remove_all_messages(self, guild: discord.Guild):
        """Remove all messages from all channels in a guild"""
        print(f"\n🧹 Starting message deletion for '{guild.name}'...")
        
        text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]
        total_channels = len(text_channels)
        
        if total_channels == 0:
            print("❌ No text channels found!")
            return
        
        print(f"📊 Found {total_channels} text channels")
        
        for i, channel in enumerate(text_channels, 1):
            print(f"🧹 Cleaning channel [{i}/{total_channels}]: #{channel.name}")
            try:
                deleted_count = 0
                async for message in channel.history(limit=None):
                    try:
                        await message.delete()
                        deleted_count += 1
                        if deleted_count % 10 == 0:
                            print(f"   Deleted {deleted_count} messages...")
                        await asyncio.sleep(0.1)  # Rate limiting
                    except:
                        pass
                print(f"✅ Cleaned #{channel.name}: {deleted_count} messages deleted")
            except discord.Forbidden:
                print(f"❌ No permission to access: #{channel.name}")
            except Exception as e:
                print(f"❌ Error cleaning #{channel.name}: {e}")
        
        print(f"\n✅ Message deletion complete!")
    
    async def remove_all_roles(self, guild: discord.Guild):
        """Remove all roles from a guild (except @everyone and bot roles)"""
        print(f"\n🎭 Starting role deletion for '{guild.name}'...")
        
        # Get all roles except @everyone and managed roles (bot roles)
        roles_to_delete = [role for role in guild.roles 
                          if role.name != "@everyone" and not role.managed and role < guild.me.top_role]
        
        total_roles = len(roles_to_delete)
        deleted_count = 0
        
        print(f"📊 Found {total_roles} deletable roles")
        
        for i, role in enumerate(roles_to_delete, 1):
            try:
                await role.delete(reason="Bulk deletion via server manager")
                deleted_count += 1
                print(f"✅ Deleted [{i}/{total_roles}]: @{role.name}")
                await asyncio.sleep(0.5)  # Rate limiting
            except discord.Forbidden:
                print(f"❌ No permission to delete: @{role.name}")
            except discord.HTTPException as e:
                print(f"❌ Error deleting @{role.name}: {e}")
        
        print(f"\n✅ Role deletion complete! Deleted {deleted_count}/{total_roles} roles")
    
    async def send_message_to_channel(self, guild: discord.Guild):
        """Send a message to a specific channel"""
        print(f"\n📤 Sending message in '{guild.name}'...")
        
        # Show available text channels
        text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]
        
        if not text_channels:
            print("❌ No text channels found!")
            return
        
        print("\n📋 Available channels:")
        for i, channel in enumerate(text_channels, 1):
            print(f"{i:2d}. #{channel.name}")
        
        try:
            channel_choice = int(input(f"\nSelect channel (1-{len(text_channels)}): ")) - 1
            if 0 <= channel_choice < len(text_channels):
                selected_channel = text_channels[channel_choice]
                
                message_content = input("Enter message to send: ")
                if message_content.strip():
                    await selected_channel.send(message_content)
                    print(f"✅ Message sent to #{selected_channel.name}")
                else:
                    print("❌ Empty message not sent")
            else:
                print("❌ Invalid channel selection")
        except ValueError:
            print("❌ Invalid input")
        except discord.Forbidden:
            print("❌ No permission to send messages")
        except Exception as e:
            print(f"❌ Error sending message: {e}")
    
    async def nuclear_option(self, guild: discord.Guild):
        """Delete everything: channels, roles, and messages"""
        print(f"\n💥 NUCLEAR OPTION for '{guild.name}'")
        print("⚠️  This will delete EVERYTHING:")
        print("   - All channels")
        print("   - All roles (except @everyone and bot roles)")
        print("   - All messages")
        
        confirm = input("\n⚠️  Type 'CONFIRM DELETE EVERYTHING' to proceed: ")
        if confirm != "CONFIRM DELETE EVERYTHING":
            print("❌ Nuclear option cancelled")
            return
        
        print("\n💥 Starting nuclear deletion...")
        
        # Delete messages first (before channels are deleted)
        await self.remove_all_messages(guild)
        
        # Delete roles
        await self.remove_all_roles(guild)
        
        # Delete channels
        await self.remove_all_channels(guild)
        
        print(f"\n💥 NUCLEAR DELETION COMPLETE for '{guild.name}'!")
    
    # ============ SERVER ANALYTICS & INFO ============
    
    async def show_server_statistics(self, guild: discord.Guild):
        """Show comprehensive server statistics"""
        print(f"\n📊 SERVER STATISTICS FOR: {guild.name}")
        print("="*60)
        
        # Basic info
        print(f"🆔 Server ID: {guild.id}")
        print(f"👑 Owner: {guild.owner.name if guild.owner else 'Unknown'}")
        print(f"📅 Created: {guild.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"🌍 Region: {getattr(guild, 'region', 'Unknown')}")
        print(f"🔒 Verification Level: {guild.verification_level}")
        print(f"📋 Description: {guild.description or 'None'}")
        
        # Counts
        total_members = guild.member_count or len(guild.members)
        online_members = sum(1 for m in guild.members if m.status != discord.Status.offline)
        bot_members = sum(1 for m in guild.members if m.bot)
        human_members = total_members - bot_members
        
        print(f"\n👥 MEMBERS:")
        print(f"   Total: {total_members}")
        print(f"   Humans: {human_members}")
        print(f"   Bots: {bot_members}")
        print(f"   Online: {online_members}")
        
        # Channels
        text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
        voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
        categories = len([c for c in guild.channels if isinstance(c, discord.CategoryChannel)])
        
        print(f"\n📺 CHANNELS:")
        print(f"   Text: {text_channels}")
        print(f"   Voice: {voice_channels}")
        print(f"   Categories: {categories}")
        print(f"   Total: {len(guild.channels)}")
        
        # Roles
        print(f"\n🎭 ROLES:")
        print(f"   Total: {len(guild.roles)}")
        print(f"   Highest: {guild.roles[-1].name}")
        
        # Emojis
        print(f"\n😀 EMOJIS:")
        print(f"   Total: {len(guild.emojis)}")
        print(f"   Animated: {len([e for e in guild.emojis if e.animated])}")
        
        # Features
        if guild.features:
            print(f"\n✨ FEATURES:")
            for feature in guild.features:
                print(f"   • {feature.replace('_', ' ').title()}")
    
    async def show_member_analysis(self, guild: discord.Guild):
        """Show detailed member analysis"""
        print(f"\n👥 MEMBER ANALYSIS FOR: {guild.name}")
        print("="*60)
        
        members = guild.members
        if not members:
            print("❌ Cannot access member list (missing permissions)")
            return
        
        # Status breakdown
        status_counts = {"online": 0, "idle": 0, "dnd": 0, "offline": 0}
        for member in members:
            status_counts[str(member.status)] += 1
        
        print("📊 STATUS BREAKDOWN:")
        print(f"   🟢 Online: {status_counts['online']}")
        print(f"   🟡 Idle: {status_counts['idle']}")
        print(f"   🔴 Do Not Disturb: {status_counts['dnd']}")
        print(f"   ⚫ Offline: {status_counts['offline']}")
        
        # Join dates
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        recent_joins = [m for m in members if m.joined_at and m.joined_at.replace(tzinfo=None) > week_ago]
        month_joins = [m for m in members if m.joined_at and m.joined_at.replace(tzinfo=None) > month_ago]
        
        print(f"\n📅 JOIN ACTIVITY:")
        print(f"   Last 7 days: {len(recent_joins)}")
        print(f"   Last 30 days: {len(month_joins)}")
        
        # Top roles by member count
        role_counts = {}
        for member in members:
            for role in member.roles:
                if role.name != "@everyone":
                    role_counts[role.name] = role_counts.get(role.name, 0) + 1
        
        if role_counts:
            print(f"\n🏆 TOP ROLES:")
            sorted_roles = sorted(role_counts.items(), key=lambda x: x[1], reverse=True)
            for role_name, count in sorted_roles[:5]:
                print(f"   {role_name}: {count} members")
        
        # Permissions analysis
        admin_members = [m for m in members if m.guild_permissions.administrator]
        mod_members = [m for m in members if m.guild_permissions.manage_messages or m.guild_permissions.kick_members]
        
        print(f"\n🛡️  PERMISSIONS:")
        print(f"   Administrators: {len(admin_members)}")
        print(f"   Moderators: {len(mod_members)}")
    
    async def show_channel_overview(self, guild: discord.Guild):
        """Show detailed channel information"""
        print(f"\n📋 CHANNEL OVERVIEW FOR: {guild.name}")
        print("="*60)
        
        categories = [c for c in guild.channels if isinstance(c, discord.CategoryChannel)]
        text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        voice_channels = [c for c in guild.channels if isinstance(c, discord.VoiceChannel)]
        
        print(f"📁 CATEGORIES ({len(categories)}):")
        for cat in categories:
            cat_text = len([c for c in cat.channels if isinstance(c, discord.TextChannel)])
            cat_voice = len([c for c in cat.channels if isinstance(c, discord.VoiceChannel)])
            print(f"   📁 {cat.name}: {cat_text} text, {cat_voice} voice")
        
        print(f"\n💬 TEXT CHANNELS ({len(text_channels)}):")
        for i, channel in enumerate(text_channels[:10]):  # Show first 10
            category = channel.category.name if channel.category else "No Category"
            print(f"   #{channel.name} (in {category})")
        if len(text_channels) > 10:
            print(f"   ... and {len(text_channels) - 10} more")
        
        print(f"\n🔊 VOICE CHANNELS ({len(voice_channels)}):")
        for i, channel in enumerate(voice_channels[:10]):  # Show first 10
            category = channel.category.name if channel.category else "No Category"
            user_count = len(channel.members)
            print(f"   🔊 {channel.name} ({user_count} users) (in {category})")
        if len(voice_channels) > 10:
            print(f"   ... and {len(voice_channels) - 10} more")
    
    async def show_role_overview(self, guild: discord.Guild):
        """Show detailed role information"""
        print(f"\n🎭 ROLE OVERVIEW FOR: {guild.name}")
        print("="*60)
        
        roles = sorted(guild.roles, key=lambda r: r.position, reverse=True)
        
        print(f"📊 TOTAL ROLES: {len(roles)}")
        print("\n🏆 ROLE HIERARCHY (Top 15):")
        
        for i, role in enumerate(roles[:15]):
            if role.name == "@everyone":
                continue
            
            member_count = len(role.members)
            permissions = []
            
            if role.permissions.administrator:
                permissions.append("Admin")
            if role.permissions.manage_guild:
                permissions.append("Manage Server")
            if role.permissions.manage_channels:
                permissions.append("Manage Channels")
            if role.permissions.kick_members:
                permissions.append("Kick")
            if role.permissions.ban_members:
                permissions.append("Ban")
            
            perm_str = ", ".join(permissions) if permissions else "Basic"
            color = f"#{role.color.value:06x}" if role.color.value else "Default"
            
            print(f"   {i+1:2d}. @{role.name}")
            print(f"       Members: {member_count} | Color: {color} | Perms: {perm_str}")
    
    # ============ SMART BULK OPERATIONS ============
    
    async def delete_channels_by_pattern(self, guild: discord.Guild):
        """Delete channels matching a pattern"""
        print(f"\n🔍 DELETE CHANNELS BY PATTERN")
        print("Examples: 'temp*', '*-old', 'test-*', etc.")
        
        pattern = input("Enter pattern (use * as wildcard): ").strip()
        if not pattern:
            print("❌ No pattern provided")
            return
        
        # Convert pattern to regex
        regex_pattern = pattern.replace("*", ".*")
        
        matching_channels = []
        for channel in guild.channels:
            if re.match(regex_pattern, channel.name, re.IGNORECASE):
                matching_channels.append(channel)
        
        if not matching_channels:
            print(f"❌ No channels match pattern '{pattern}'")
            return
        
        print(f"\n📋 Found {len(matching_channels)} matching channels:")
        for channel in matching_channels:
            print(f"   #{channel.name}")
        
        confirm = input(f"\n⚠️  Delete {len(matching_channels)} channels? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Cancelled")
            return
        
        deleted_count = 0
        for channel in matching_channels:
            try:
                await channel.delete(reason=f"Pattern deletion: {pattern}")
                deleted_count += 1
                print(f"✅ Deleted #{channel.name}")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"❌ Failed to delete #{channel.name}: {e}")
        
        print(f"\n✅ Deleted {deleted_count}/{len(matching_channels)} channels")
    
    async def mass_role_assignment(self, guild: discord.Guild):
        """Mass assign/remove roles to/from users"""
        print(f"\n🏷️  MASS ROLE ASSIGNMENT")
        
        # Show available roles
        roles = [r for r in guild.roles if r.name != "@everyone" and not r.managed]
        if not roles:
            print("❌ No assignable roles found")
            return
        
        print("\n📋 Available roles:")
        for i, role in enumerate(roles, 1):
            print(f"{i:2d}. @{role.name} ({len(role.members)} members)")
        
        try:
            role_choice = int(input(f"\nSelect role (1-{len(roles)}): ")) - 1
            if not (0 <= role_choice < len(roles)):
                print("❌ Invalid role selection")
                return
            
            selected_role = roles[role_choice]
            
            action = input("Action (add/remove): ").strip().lower()
            if action not in ["add", "remove"]:
                print("❌ Invalid action")
                return
            
            target = input("Target (all/bots/humans/online): ").strip().lower()
            
            # Get target members
            target_members = []
            if target == "all":
                target_members = guild.members
            elif target == "bots":
                target_members = [m for m in guild.members if m.bot]
            elif target == "humans":
                target_members = [m for m in guild.members if not m.bot]
            elif target == "online":
                target_members = [m for m in guild.members if m.status != discord.Status.offline]
            else:
                print("❌ Invalid target")
                return
            
            # Filter based on action
            if action == "add":
                target_members = [m for m in target_members if selected_role not in m.roles]
            else:
                target_members = [m for m in target_members if selected_role in m.roles]
            
            if not target_members:
                print(f"❌ No members to {action} role to/from")
                return
            
            print(f"\n📊 Will {action} @{selected_role.name} to/from {len(target_members)} members")
            confirm = input("Continue? (y/N): ")
            if confirm.lower() != 'y':
                print("❌ Cancelled")
                return
            
            success_count = 0
            for member in target_members:
                try:
                    if action == "add":
                        await member.add_roles(selected_role, reason="Mass role assignment")
                    else:
                        await member.remove_roles(selected_role, reason="Mass role removal")
                    success_count += 1
                    if success_count % 10 == 0:
                        print(f"   Processed {success_count}/{len(target_members)} members...")
                    await asyncio.sleep(0.1)
                except Exception as e:
                    print(f"❌ Failed for {member.name}: {e}")
            
            print(f"✅ Successfully {action}ed role for {success_count}/{len(target_members)} members")
            
        except ValueError:
            print("❌ Invalid input")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    async def create_channel_categories(self, guild: discord.Guild):
        """Create multiple channel categories with templates"""
        print(f"\n📁 CREATE CHANNEL CATEGORIES")
        
        categories_input = input("Enter category names (comma-separated): ").strip()
        if not categories_input:
            print("❌ No categories provided")
            return
        
        category_names = [name.strip() for name in categories_input.split(",")]
        
        create_channels = input("Create default channels in each category? (y/N): ").strip().lower() == 'y'
        
        print(f"\n📊 Will create {len(category_names)} categories")
        for name in category_names:
            print(f"   📁 {name}")
        
        confirm = input("Continue? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Cancelled")
            return
        
        created_count = 0
        for category_name in category_names:
            try:
                # Create category
                category = await guild.create_category(category_name, reason="Bulk category creation")
                created_count += 1
                print(f"✅ Created category: {category_name}")
                
                if create_channels:
                    # Create default channels
                    await guild.create_text_channel("general", category=category, reason="Default channel")
                    await guild.create_voice_channel("General", category=category, reason="Default channel")
                    print(f"   ├─ #general")
                    print(f"   └─ 🔊 General")
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Failed to create {category_name}: {e}")
        
        print(f"\n✅ Created {created_count}/{len(category_names)} categories")
    
    async def clean_nicknames(self, guild: discord.Guild):
        """Clean or reset member nicknames"""
        print(f"\n🧹 CLEAN NICKNAMES")
        print("1. Reset all nicknames to default")
        print("2. Remove special characters")
        print("3. Standardize format (Firstname Lastname)")
        
        action = input("Select action (1-3): ").strip()
        
        members_with_nicks = [m for m in guild.members if m.nick and not m.bot]
        if not members_with_nicks:
            print("❌ No members with nicknames found")
            return
        
        print(f"\n📊 Found {len(members_with_nicks)} members with nicknames")
        confirm = input("Continue? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Cancelled")
            return
        
        success_count = 0
        for member in members_with_nicks:
            try:
                if action == "1":
                    await member.edit(nick=None, reason="Nickname reset")
                elif action == "2":
                    clean_nick = re.sub(r'[^\w\s-]', '', member.nick)
                    await member.edit(nick=clean_nick, reason="Nickname cleaning")
                elif action == "3":
                    # Basic standardization
                    parts = member.nick.split()
                    if len(parts) >= 2:
                        standard_nick = f"{parts[0].capitalize()} {parts[1].capitalize()}"
                        await member.edit(nick=standard_nick, reason="Nickname standardization")
                
                success_count += 1
                await asyncio.sleep(0.2)
                
            except Exception as e:
                print(f"❌ Failed for {member.name}: {e}")
        
        print(f"✅ Processed {success_count}/{len(members_with_nicks)} nicknames")
    
    # ============ ADVANCED MESSAGING ============
    
    async def mass_dm_users(self, guild: discord.Guild):
        """Send DMs to multiple users"""
        print(f"\n📨 MASS DM USERS")
        print("⚠️  Warning: This can trigger rate limits and may be considered spam")
        
        target = input("Target (all/role/online/humans): ").strip().lower()
        
        target_members = []
        if target == "all":
            target_members = [m for m in guild.members if not m.bot]
        elif target == "role":
            # Show roles
            roles = [r for r in guild.roles if r.name != "@everyone"]
            print("\nAvailable roles:")
            for i, role in enumerate(roles, 1):
                print(f"{i:2d}. @{role.name} ({len(role.members)} members)")
            
            try:
                role_choice = int(input(f"Select role (1-{len(roles)}): ")) - 1
                if 0 <= role_choice < len(roles):
                    target_members = [m for m in roles[role_choice].members if not m.bot]
                else:
                    print("❌ Invalid role selection")
                    return
            except ValueError:
                print("❌ Invalid input")
                return
        elif target == "online":
            target_members = [m for m in guild.members if not m.bot and m.status != discord.Status.offline]
        elif target == "humans":
            target_members = [m for m in guild.members if not m.bot]
        else:
            print("❌ Invalid target")
            return
        
        if not target_members:
            print("❌ No target members found")
            return
        
        message_content = input("Enter message to send: ").strip()
        if not message_content:
            print("❌ No message provided")
            return
        
        print(f"\n📊 Will send DM to {len(target_members)} members")
        print(f"💬 Message: {message_content}")
        
        confirm = input("⚠️  This action cannot be undone. Continue? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Cancelled")
            return
        
        success_count = 0
        failed_count = 0
        
        for member in target_members:
            try:
                await member.send(message_content)
                success_count += 1
                if success_count % 5 == 0:
                    print(f"   Sent to {success_count}/{len(target_members)} members...")
                await asyncio.sleep(1)  # Longer delay for DMs
            except discord.Forbidden:
                failed_count += 1
            except Exception as e:
                failed_count += 1
                print(f"❌ Failed to DM {member.name}: {e}")
        
        print(f"✅ DM sent to {success_count} members")
        if failed_count > 0:
            print(f"⚠️  Failed to send to {failed_count} members (privacy settings/blocked)")
    
    async def multi_channel_announcement(self, guild: discord.Guild):
        """Send announcement to multiple channels"""
        print(f"\n📢 MULTI-CHANNEL ANNOUNCEMENT")
        
        text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        if not text_channels:
            print("❌ No text channels found")
            return
        
        print("\nSelect channels (comma-separated numbers):")
        for i, channel in enumerate(text_channels, 1):
            print(f"{i:2d}. #{channel.name}")
        
        try:
            choices = input(f"Select channels (1-{len(text_channels)}) or 'all': ").strip()
            
            if choices.lower() == "all":
                selected_channels = text_channels
            else:
                indices = [int(x.strip()) - 1 for x in choices.split(",")]
                selected_channels = [text_channels[i] for i in indices if 0 <= i < len(text_channels)]
            
            if not selected_channels:
                print("❌ No channels selected")
                return
            
            message_content = input("Enter announcement message: ").strip()
            if not message_content:
                print("❌ No message provided")
                return
            
            print(f"\n📊 Will send to {len(selected_channels)} channels:")
            for channel in selected_channels:
                print(f"   #{channel.name}")
            
            confirm = input("Continue? (y/N): ")
            if confirm.lower() != 'y':
                print("❌ Cancelled")
                return
            
            success_count = 0
            for channel in selected_channels:
                try:
                    await channel.send(message_content)
                    success_count += 1
                    print(f"✅ Sent to #{channel.name}")
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"❌ Failed to send to #{channel.name}: {e}")
            
            print(f"✅ Announcement sent to {success_count}/{len(selected_channels)} channels")
            
        except ValueError:
            print("❌ Invalid input")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    async def create_embed_message(self, guild: discord.Guild):
        """Create and send a rich embed message"""
        print(f"\n🎨 CREATE EMBED MESSAGE")
        
        # Get channel
        text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        if not text_channels:
            print("❌ No text channels found")
            return
        
        print("\nSelect channel:")
        for i, channel in enumerate(text_channels, 1):
            print(f"{i:2d}. #{channel.name}")
        
        try:
            channel_choice = int(input(f"Select channel (1-{len(text_channels)}): ")) - 1
            if not (0 <= channel_choice < len(text_channels)):
                print("❌ Invalid channel selection")
                return
            
            selected_channel = text_channels[channel_choice]
            
            # Create embed
            title = input("Embed title: ").strip()
            description = input("Embed description: ").strip()
            color_input = input("Embed color (hex, e.g., ff0000) [default: blue]: ").strip()
            
            embed = discord.Embed(
                title=title or "Announcement",
                description=description or "No description provided",
                color=discord.Color.blue()
            )
            
            if color_input:
                try:
                    embed.color = discord.Color(int(color_input, 16))
                except ValueError:
                    print("⚠️  Invalid color, using blue")
            
            # Optional fields
            add_fields = input("Add fields? (y/N): ").strip().lower() == 'y'
            if add_fields:
                while True:
                    field_name = input("Field name (or press Enter to finish): ").strip()
                    if not field_name:
                        break
                    field_value = input("Field value: ").strip()
                    inline = input("Inline? (y/N): ").strip().lower() == 'y'
                    embed.add_field(name=field_name, value=field_value or "No value", inline=inline)
            
            # Optional footer and timestamp
            footer = input("Footer text (optional): ").strip()
            if footer:
                embed.set_footer(text=footer)
            
            timestamp = input("Add timestamp? (y/N): ").strip().lower() == 'y'
            if timestamp:
                embed.timestamp = datetime.now()
            
            # Send embed
            await selected_channel.send(embed=embed)
            print(f"✅ Embed sent to #{selected_channel.name}")
            
        except ValueError:
            print("❌ Invalid input")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # ============ USER MANAGEMENT ============
    
    async def export_member_list(self, guild: discord.Guild):
        """Export member list to CSV"""
        print(f"\n📊 EXPORT MEMBER LIST")
        
        # Create server-specific directory
        logs_dir = self.create_server_logs_dir(guild)
        safe_guild_name = self.sanitize_filename(guild.name)
        
        filename = f"{logs_dir}/{safe_guild_name}_members_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Name', 'Display Name', 'ID', 'Bot', 'Status', 'Joined', 'Roles', 'Top Role'])
                
                for member in guild.members:
                    roles = [role.name for role in member.roles if role.name != "@everyone"]
                    top_role = member.top_role.name if member.top_role.name != "@everyone" else "None"
                    joined = member.joined_at.strftime('%Y-%m-%d') if member.joined_at else "Unknown"
                    
                    writer.writerow([
                        member.name,
                        member.display_name,
                        member.id,
                        member.bot,
                        str(member.status),
                        joined,
                        ", ".join(roles),
                        top_role
                    ])
            
            print(f"✅ Member list exported to: {filename}")
            print(f"📊 Exported {len(guild.members)} members")
            
        except Exception as e:
            print(f"❌ Export failed: {e}")
    
    # ============ MONITORING & SURVEILLANCE ============
    
    async def message_sniffer(self, guild: discord.Guild):
        """Live message monitoring for specific channels"""
        print(f"\n👁️  MESSAGE SNIFFER")
        print("⚠️  This will monitor messages in real-time. Press Ctrl+C to stop.")
        
        # Show available text channels
        text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        if not text_channels:
            print("❌ No text channels found")
            return
        
        print("\nAvailable channels:")
        for i, channel in enumerate(text_channels, 1):
            print(f"{i:2d}. #{channel.name}")
        
        try:
            choices = input(f"Select channels to monitor (comma-separated, 1-{len(text_channels)}) or 'all': ").strip()
            
            if choices.lower() == "all":
                selected_channels = text_channels
            else:
                indices = [int(x.strip()) - 1 for x in choices.split(",")]
                selected_channels = [text_channels[i] for i in indices if 0 <= i < len(text_channels)]
            
            if not selected_channels:
                print("❌ No channels selected")
                return
            
            # Options
            show_edits = input("Show message edits? (y/N): ").strip().lower() == 'y'
            show_deletes = input("Show message deletions? (y/N): ").strip().lower() == 'y'
            save_to_file = input("Save messages to file? (y/N): ").strip().lower() == 'y'
            
            log_filename = None
            if save_to_file:
                # Create server-specific directory
                logs_dir = self.create_server_logs_dir(guild)
                safe_guild_name = self.sanitize_filename(guild.name)
                
                log_filename = f"{logs_dir}/sniffer_log_{safe_guild_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            print(f"\n🕵️  Starting message sniffer for {len(selected_channels)} channels...")
            for channel in selected_channels:
                print(f"   👁️  Monitoring: #{channel.name}")
            
            if log_filename:
                print(f"💾 Logging to: {log_filename}")
            
            print("\n" + "="*80)
            print("LIVE MESSAGE FEED (Press Ctrl+C to stop)")
            print("="*80)
            
            # Set up message monitoring using polling instead of events
            monitored_channel_ids = [ch.id for ch in selected_channels]
            last_message_ids = {ch.id: None for ch in selected_channels}
            
            # Get the latest message ID for each channel to start monitoring from
            for channel in selected_channels:
                try:
                    async for message in channel.history(limit=1):
                        last_message_ids[channel.id] = message.id
                        break
                except:
                    pass
            
            print("🔄 Starting monitoring loop...")
            
            # Monitoring loop
            try:
                while True:
                    for channel in selected_channels:
                        try:
                            # Get new messages since last check
                            new_messages = []
                            after_message = None
                            
                            if last_message_ids[channel.id]:
                                # Get message object to use as 'after' parameter
                                try:
                                    after_message = await channel.fetch_message(last_message_ids[channel.id])
                                except:
                                    after_message = None
                            
                            # Fetch new messages
                            async for message in channel.history(limit=50, after=after_message):
                                if not message.author.bot:
                                    new_messages.append(message)
                            
                            # Process new messages (reverse to show chronologically)
                            for message in reversed(new_messages):
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                channel_name = message.channel.name
                                author = message.author.display_name
                                content = message.content or "[No text content]"
                                
                                # Handle attachments
                                attachments = ""
                                if message.attachments:
                                    att_list = [f"{att.filename}" for att in message.attachments]
                                    attachments = f" [Attachments: {', '.join(att_list)}]"
                                
                                # Handle embeds
                                embeds = ""
                                if message.embeds:
                                    embeds = f" [Embeds: {len(message.embeds)}]"
                                
                                log_entry = f"[{timestamp}] #{channel_name} | {author}: {content}{attachments}{embeds}"
                                print(log_entry)
                                
                                # Save to file if enabled
                                if log_filename:
                                    try:
                                        with open(log_filename, 'a', encoding='utf-8') as f:
                                            f.write(log_entry + "\n")
                                    except Exception as e:
                                        print(f"❌ Failed to log: {e}")
                                
                                # Update last message ID
                                last_message_ids[channel.id] = message.id
                        
                        except discord.Forbidden:
                            print(f"❌ Lost access to #{channel.name}")
                        except Exception as e:
                            print(f"❌ Error monitoring #{channel.name}: {e}")
                    
                    # Wait before next check
                    await asyncio.sleep(2)  # Check every 2 seconds
                    
            except KeyboardInterrupt:
                print("\n" + "="*80)
                print("🛑 Message sniffer stopped")
                if log_filename:
                    print(f"💾 Messages saved to: {log_filename}")
                print("Note: Edit and delete tracking not available in polling mode")
                
        except ValueError:
            print("❌ Invalid input")
        except KeyboardInterrupt:
            print("\n🛑 Monitoring cancelled")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    async def export_channel_history(self, guild: discord.Guild):
        """Export message history from a channel"""
        print(f"\n📜 CHANNEL HISTORY EXPORT")
        
        # Show available text channels
        text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        if not text_channels:
            print("❌ No text channels found")
            return
        
        print("\nAvailable channels:")
        for i, channel in enumerate(text_channels, 1):
            print(f"{i:2d}. #{channel.name}")
        
        try:
            channel_choice = int(input(f"Select channel (1-{len(text_channels)}): ")) - 1
            if not (0 <= channel_choice < len(text_channels)):
                print("❌ Invalid channel selection")
                return
            
            selected_channel = text_channels[channel_choice]
            
            # Get options
            print("\nExport options:")
            print("1. Last 100 messages")
            print("2. Last 500 messages")
            print("3. Last 1000 messages")
            print("4. All messages (may take a long time)")
            print("5. Messages from specific date range")
            
            option = input("Select option (1-5): ").strip()
            
            limit = None
            after_date = None
            before_date = None
            
            if option == "1":
                limit = 100
            elif option == "2":
                limit = 500
            elif option == "3":
                limit = 1000
            elif option == "4":
                limit = None
            elif option == "5":
                after_input = input("Start date (YYYY-MM-DD) or press Enter for no limit: ").strip()
                before_input = input("End date (YYYY-MM-DD) or press Enter for no limit: ").strip()
                
                if after_input:
                    after_date = datetime.strptime(after_input, '%Y-%m-%d')
                if before_input:
                    before_date = datetime.strptime(before_input, '%Y-%m-%d')
            else:
                print("❌ Invalid option")
                return
            
            # Create server-specific directory and filename
            logs_dir = self.create_server_logs_dir(guild)
            safe_guild_name = self.sanitize_filename(guild.name)
            safe_channel_name = self.sanitize_filename(selected_channel.name)
            
            filename = f"{logs_dir}/history_{safe_guild_name}_{safe_channel_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            print(f"\n📊 Exporting messages from #{selected_channel.name}...")
            
            message_count = 0
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"CHANNEL HISTORY EXPORT\n")
                f.write(f"Server: {guild.name}\n")
                f.write(f"Channel: #{selected_channel.name}\n")
                f.write(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*80 + "\n\n")
                
                async for message in selected_channel.history(limit=limit, after=after_date, before=before_date):
                    timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    author = message.author.display_name
                    content = message.content or "[No text content]"
                    
                    # Handle attachments
                    if message.attachments:
                        att_list = [f"{att.filename} ({att.url})" for att in message.attachments]
                        content += f"\n[Attachments: {', '.join(att_list)}]"
                    
                    # Handle embeds
                    if message.embeds:
                        content += f"\n[Embeds: {len(message.embeds)}]"
                    
                    f.write(f"[{timestamp}] {author}:\n{content}\n\n")
                    message_count += 1
                    
                    if message_count % 100 == 0:
                        print(f"   Exported {message_count} messages...")
            
            print(f"✅ Exported {message_count} messages to: {filename}")
            
        except ValueError:
            print("❌ Invalid input")
        except Exception as e:
            print(f"❌ Export failed: {e}")
    
    async def search_messages_by_keyword(self, guild: discord.Guild):
        """Search for messages containing specific keywords"""
        print(f"\n🔍 SEARCH MESSAGES BY KEYWORD")
        
        # Show available text channels
        text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        if not text_channels:
            print("❌ No text channels found")
            return
        
        print("\nAvailable channels:")
        for i, channel in enumerate(text_channels, 1):
            print(f"{i:2d}. #{channel.name}")
        
        try:
            choices = input(f"Select channels to search (comma-separated, 1-{len(text_channels)}) or 'all': ").strip()
            
            if choices.lower() == "all":
                selected_channels = text_channels
            else:
                indices = [int(x.strip()) - 1 for x in choices.split(",")]
                selected_channels = [text_channels[i] for i in indices if 0 <= i < len(text_channels)]
            
            if not selected_channels:
                print("❌ No channels selected")
                return
            
            keyword = input("Enter keyword/phrase to search for: ").strip()
            if not keyword:
                print("❌ No keyword provided")
                return
            
            case_sensitive = input("Case sensitive search? (y/N): ").strip().lower() == 'y'
            limit = int(input("Search limit per channel (default 1000): ").strip() or "1000")
            
            print(f"\n🔍 Searching for '{keyword}' in {len(selected_channels)} channels...")
            
            # Create server-specific directory
            logs_dir = self.create_server_logs_dir(guild)
            safe_guild_name = self.sanitize_filename(guild.name)
            safe_keyword = self.sanitize_filename(keyword)
            
            total_found = 0
            results_filename = f"{logs_dir}/search_results_{safe_keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            with open(results_filename, 'w', encoding='utf-8') as f:
                f.write(f"KEYWORD SEARCH RESULTS\n")
                f.write(f"Server: {guild.name}\n")
                f.write(f"Keyword: '{keyword}'\n")
                f.write(f"Case Sensitive: {case_sensitive}\n")
                f.write(f"Search Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*80 + "\n\n")
                
                for channel in selected_channels:
                    print(f"   Searching #{channel.name}...")
                    channel_found = 0
                    
                    try:
                        async for message in channel.history(limit=limit):
                            content = message.content
                            if not content:
                                continue
                            
                            # Check if keyword is in message
                            if case_sensitive:
                                found = keyword in content
                            else:
                                found = keyword.lower() in content.lower()
                            
                            if found:
                                timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
                                author = message.author.display_name
                                
                                result = f"[{timestamp}] #{channel.name} | {author}:\n{content}\n"
                                print(f"✅ Found in #{channel.name}: {author}")
                                
                                f.write(result + "\n" + "-"*40 + "\n\n")
                                channel_found += 1
                                total_found += 1
                    
                    except discord.Forbidden:
                        print(f"❌ No access to #{channel.name}")
                    except Exception as e:
                        print(f"❌ Error searching #{channel.name}: {e}")
                    
                    if channel_found > 0:
                        print(f"   Found {channel_found} matches in #{channel.name}")
            
            print(f"\n✅ Search complete! Found {total_found} total matches")
            print(f"📄 Results saved to: {results_filename}")
            
        except ValueError:
            print("❌ Invalid input")
        except Exception as e:
            print(f"❌ Search failed: {e}")
    
    async def leave_server(self, guild: discord.Guild):
        """Leave/uninvite the bot from the current server"""
        print(f"\n🚪 LEAVE SERVER")
        print(f"Server: {guild.name}")
        print(f"ID: {guild.id}")
        print(f"Members: {guild.member_count or len(guild.members)}")
        
        print("\n⚠️  WARNING: This will permanently remove the bot from this server!")
        print("The bot will lose access to all channels, messages, and data.")
        print("You will need a new invite link to add the bot back.")
        
        confirm1 = input(f"\nAre you sure you want to leave '{guild.name}'? (y/N): ")
        if confirm1.lower() != 'y':
            print("❌ Cancelled")
            return False
        
        confirm2 = input(f"Type the server name '{guild.name}' to confirm: ")
        if confirm2 != guild.name:
            print("❌ Server name doesn't match. Cancelled for safety.")
            return False
        
        try:
            print(f"\n🚪 Leaving server '{guild.name}'...")
            await guild.leave()
            print(f"✅ Successfully left '{guild.name}'")
            
            # Update the guilds list
            self.guilds = [g for g in self.guilds if g.id != guild.id]
            
            return True
            
        except discord.HTTPException as e:
            print(f"❌ Failed to leave server: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False
    
    async def handle_server_actions(self, guild: discord.Guild):
        """Handle actions for a selected server"""
        while True:
            self.display_actions_menu(guild.name)
            
            try:
                choice = input("\nSelect action: ").strip()
                
                if choice == "1":
                    confirm = input(f"⚠️  Delete ALL channels in '{guild.name}'? (y/N): ")
                    if confirm.lower() == 'y':
                        await self.remove_all_channels(guild)
                    else:
                        print("❌ Cancelled")
                
                elif choice == "2":
                    confirm = input(f"⚠️  Delete ALL messages in '{guild.name}'? (y/N): ")
                    if confirm.lower() == 'y':
                        await self.remove_all_messages(guild)
                    else:
                        print("❌ Cancelled")
                
                elif choice == "3":
                    confirm = input(f"⚠️  Delete ALL roles in '{guild.name}'? (y/N): ")
                    if confirm.lower() == 'y':
                        await self.remove_all_roles(guild)
                    else:
                        print("❌ Cancelled")
                
                elif choice == "4":
                    await self.send_message_to_channel(guild)
                
                elif choice == "5":
                    await self.nuclear_option(guild)
                
                # Server Analytics & Info
                elif choice == "6":
                    await self.show_server_statistics(guild)
                elif choice == "7":
                    await self.show_member_analysis(guild)
                elif choice == "8":
                    await self.show_channel_overview(guild)
                elif choice == "9":
                    await self.show_role_overview(guild)
                
                # Smart Bulk Operations
                elif choice == "10":
                    await self.delete_channels_by_pattern(guild)
                elif choice == "11":
                    await self.mass_role_assignment(guild)
                elif choice == "12":
                    await self.create_channel_categories(guild)
                elif choice == "13":
                    await self.clean_nicknames(guild)
                
                # Advanced Messaging
                elif choice == "14":
                    await self.mass_dm_users(guild)
                elif choice == "15":
                    await self.multi_channel_announcement(guild)
                elif choice == "16":
                    await self.create_embed_message(guild)
                elif choice == "17":
                    # Message all role members (similar to mass DM but for specific role)
                    print("Feature coming soon!")
                
                # User Management
                elif choice == "18":
                    print("Mass ban/kick feature coming soon!")
                elif choice == "19":
                    await self.export_member_list(guild)
                elif choice == "20":
                    print("Role hierarchy manager coming soon!")
                elif choice == "21":
                    print("Find users feature coming soon!")
                
                # Monitoring & Surveillance
                elif choice == "22":
                    await self.message_sniffer(guild)
                elif choice == "23":
                    await self.export_channel_history(guild)
                elif choice == "24":
                    await self.search_messages_by_keyword(guild)
                
                # Bot Management
                elif choice == "25":
                    left_server = await self.leave_server(guild)
                    if left_server:
                        print("\n🚪 Returning to server selection...")
                        break
                
                elif choice == "26":
                    break
                
                elif choice == "0":
                    return False
                
                else:
                    print("❌ Invalid choice")
                
                input("\nPress Enter to continue...")
                
            except KeyboardInterrupt:
                print("\n❌ Interrupted")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                input("Press Enter to continue...")
        
        return True
    
    async def run(self):
        """Main menu loop"""
        try:
            print("🤖 Discord Server Manager")
            print("Connecting to Discord...")
            
            await self.initialize()
            
            while True:
                if not self.display_servers():
                    break
                
                try:
                    choice = input(f"\nSelect server (1-{len(self.guilds)}) or 0 to exit: ").strip()
                    
                    if choice == "0":
                        break
                    
                    server_index = int(choice) - 1
                    if 0 <= server_index < len(self.guilds):
                        selected_guild = self.guilds[server_index]
                        
                        # Check bot permissions
                        if not selected_guild.me.guild_permissions.administrator:
                            print(f"⚠️  Warning: Bot doesn't have admin permissions in '{selected_guild.name}'")
                            print("Some actions may fail!")
                            
                            continue_anyway = input("Continue anyway? (y/N): ")
                            if continue_anyway.lower() != 'y':
                                continue
                        
                        should_continue = await self.handle_server_actions(selected_guild)
                        if not should_continue:
                            break
                    else:
                        print("❌ Invalid server selection")
                
                except ValueError:
                    print("❌ Invalid input")
                except KeyboardInterrupt:
                    print("\n❌ Interrupted")
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")
                    input("Press Enter to continue...")
        
        finally:
            await self.bot.close()
            print("\n👋 Disconnected from Discord")

async def main():
    if not DISCORD_TOKEN:
        print("❌ Error: DISCORD_TOKEN not found in .env file!")
        return
    
    manager = ServerManager()
    await manager.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}") 