import discord
from discord.ext import commands
import asyncio
import logging

class OkraHunt:
    def __init__(self, bot, the_lodge_channel_id, level_0_channel_id, level_0_role_id, hunt_progress_channel_id, level_1_channel_id, host_role_id, okrag_id, level_1_role_id, level_2_channel_id, level_2_role_id, level_3_channel_id, level_3_role_id, level_4_role_id, level_4_channel_id, rules_channel_id, rules_message_id, hunt_leaderboard_channel_id, hunt_leaderboard_message_id):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.the_lodge_channel_id = the_lodge_channel_id
        self.level_0_channel_id = level_0_channel_id
        self.level_0_role_id = level_0_role_id
        self.hunt_progress_channel_id = hunt_progress_channel_id
        self.level_1_channel_id = level_1_channel_id
        self.host_role_id = host_role_id
        self.okrag_id = okrag_id
        self.level_1_role_id = level_1_role_id
        self.level_2_channel_id = level_2_channel_id
        self.level_2_role_id = level_2_role_id
        self.level_3_channel_id = level_3_channel_id
        self.level_3_role_id = level_3_role_id
        self.level_4_role_id = level_4_role_id
        self.level_4_channel_id = level_4_channel_id
        self.rules_channel_id = rules_channel_id
        self.rules_message_id = rules_message_id
        self.hunt_leaderboard_channel_id = hunt_leaderboard_channel_id
        self.hunt_leaderboard_message_id = hunt_leaderboard_message_id

    async def check_user_id_answer(self, message):
        """
        Check if user entered their own Discord user ID in THE_LODGE_CHANNEL
        If correct, grant them LEVEL_0_ROLE_ID
        """
        if message.channel.id != self.the_lodge_channel_id:
            return False

        # Check if user has HOST_ROLE_ID - if so, preserve their message
        has_host_role = False
        if hasattr(message.author, 'roles'):
            host_role = message.guild.get_role(self.host_role_id)
            if host_role and host_role in message.author.roles:
                has_host_role = True

        # If user has host role, don't delete their message
        if has_host_role:
            print(f"✅ Preserving message from host user: {message.author.display_name}")
            return False  # Don't handle this message, let it stay

        # Delete the message immediately to prevent others from seeing the answer
        try:
            await message.delete()
        except discord.Forbidden:
            self.logger.warning(f"Cannot delete message in channel {message.channel.id} - missing permissions")
        except Exception as e:
            self.logger.error(f"Error deleting message: {e}")

        # Check if message content is the user's ID
        user_id_str = str(message.author.id)

        if message.content.strip() == user_id_str:
            try:
                # Get the guild and role
                guild = message.guild
                role = guild.get_role(self.level_0_role_id)

                if not role:
                    self.logger.error(f"Role {self.level_0_role_id} not found in guild {guild.id}")
                    return True  # Still return True since we handled the message

                # Check if user already has the role
                if role in message.author.roles:
                    await self.announce_progress(message.author, "already_completed", "THE_LODGE")
                    return True

                # Add the role to the user
                await message.author.add_roles(role)

                # Announce success in progress channel
                await self.announce_progress(message.author, "completed", "THE_LODGE")

                # Update leaderboard
                await self.update_leaderboard()

                self.logger.info(f"User {message.author.id} ({message.author.name}) solved THE_LODGE challenge")
                return True

            except discord.Forbidden:
                self.logger.error(f"Bot lacks permission to add role {self.level_0_role_id} to user {message.author.id}")
                await self.announce_progress(message.author, "error", "THE_LODGE")
                return True  # Still return True since we handled the message
            except Exception as e:
                self.logger.error(f"Error adding role to user {message.author.id}: {e}")
                await self.announce_progress(message.author, "error", "THE_LODGE")
                return True  # Still return True since we handled the message

        return True  # Always return True for messages in THE_LODGE to delete them

    async def check_user_id_answer_without_deletion(self, message):
        """
        Check if user entered correct answer in THE_LODGE without deleting the message
        """
        # Check if message content is the user's ID
        user_id_str = str(message.author.id)

        if message.content.strip() == user_id_str:
            try:
                # Get the guild and role
                guild = message.guild
                role = guild.get_role(self.level_0_role_id)

                if not role:
                    self.logger.error(f"Role {self.level_0_role_id} not found in guild {guild.id}")
                    return

                # Check if user already has the role
                if role in message.author.roles:
                    await self.announce_progress(message.author, "already_completed", "THE_LODGE")
                    return

                # Add the role to the user
                await message.author.add_roles(role)

                # Announce success in progress channel
                await self.announce_progress(message.author, "completed", "THE_LODGE")

                # Update leaderboard
                await self.update_leaderboard()

                self.logger.info(f"User {message.author.id} ({message.author.name}) solved THE_LODGE challenge")

            except discord.Forbidden:
                self.logger.error(f"Bot lacks permission to add role {self.level_0_role_id} to user {message.author.id}")
                await self.announce_progress(message.author, "error", "THE_LODGE")
            except Exception as e:
                self.logger.error(f"Error adding role to user {message.author.id}: {e}")
                await self.announce_progress(message.author, "error", "THE_LODGE")

    async def process_lodge_answer(self, message):
        """
        Process THE_LODGE answer after message has been deleted
        """
        # Check if message content is the user's ID
        user_id_str = str(message.author.id)

        if message.content.strip() == user_id_str:
            try:
                # Get the guild and role
                guild = message.guild
                role = guild.get_role(self.level_0_role_id)

                if not role:
                    self.logger.error(f"Role {self.level_0_role_id} not found in guild {guild.id}")
                    return

                # Check if user already has the role
                if role in message.author.roles:
                    await self.announce_progress(message.author, "already_completed", "THE_LODGE")
                    return

                # Add the role to the user
                await message.author.add_roles(role)

                # Announce success in progress channel
                await self.announce_progress(message.author, "completed", "THE_LODGE")

                # Update leaderboard
                await self.update_leaderboard()

                self.logger.info(f"User {message.author.id} ({message.author.name}) solved THE_LODGE challenge")

            except discord.Forbidden:
                self.logger.error(f"Bot lacks permission to add role {self.level_0_role_id} to user {message.author.id}")
                await self.announce_progress(message.author, "error", "THE_LODGE")
            except Exception as e:
                self.logger.error(f"Error adding role to user {message.author.id}: {e}")
                await self.announce_progress(message.author, "error", "THE_LODGE")

    async def check_okra_rules_answer(self, message):
        """
        Check if user with LEVEL_0_ROLE_ID said 'Okra Rules' in LEVEL_0_CHANNEL
        If correct, remove LEVEL_0_ROLE_ID and add LEVEL_1_ROLE_ID
        """
        if message.channel.id != self.level_0_channel_id:
            return False

        # Check if user has LEVEL_0_ROLE_ID
        level_0_role = message.guild.get_role(self.level_0_role_id)
        if not level_0_role or level_0_role not in message.author.roles:
            return False

        # Normalize the message content - remove spaces, special characters, and make lowercase
        import re
        normalized_content = re.sub(r'[^a-zA-Z]', '', message.content.lower())
        target_answer = re.sub(r'[^a-zA-Z]', '', 'okra rules'.lower())

        if normalized_content == target_answer:
            try:
                # Get both roles
                level_1_role = message.guild.get_role(self.level_1_role_id)

                if not level_1_role:
                    self.logger.error(f"LEVEL_1_ROLE_ID {self.level_1_role_id} not found in guild {message.guild.id}")
                    return False

                # Check if user already has LEVEL_1_ROLE_ID
                if level_1_role in message.author.roles:
                    await self.announce_progress(message.author, "already_completed", "LEVEL_0")
                    return True

                # Remove LEVEL_0_ROLE_ID and add LEVEL_1_ROLE_ID
                await message.author.remove_roles(level_0_role)
                await message.author.add_roles(level_1_role)

                # Announce success in progress channel
                await self.announce_progress(message.author, "completed", "LEVEL_0")

                # Update leaderboard
                await self.update_leaderboard()

                self.logger.info(f"User {message.author.id} ({message.author.name}) solved LEVEL_0 challenge")
                return True

            except discord.Forbidden:
                self.logger.error(f"Bot lacks permission to modify roles for user {message.author.id}")
                await self.announce_progress(message.author, "error", "LEVEL_0")
                return False
            except Exception as e:
                self.logger.error(f"Error processing LEVEL_0 challenge for user {message.author.id}: {e}")
                await self.announce_progress(message.author, "error", "LEVEL_0")
                return False

        return False

    async def check_level_1_puzzle(self, message):
        """
        Check if user with LEVEL_1_ROLE_ID answered '94061' in LEVEL_1_CHANNEL
        If correct, add LEVEL_2_ROLE_ID
        """
        if message.channel.id != self.level_1_channel_id:
            return False

        # Check if user has LEVEL_1_ROLE_ID
        level_1_role = message.guild.get_role(self.level_1_role_id)
        if not level_1_role or level_1_role not in message.author.roles:
            return False

        if message.content.strip() == '94061':
            try:
                # Get LEVEL_2_ROLE_ID
                level_2_role = message.guild.get_role(self.level_2_role_id)

                if not level_2_role:
                    self.logger.error(f"LEVEL_2_ROLE_ID {self.level_2_role_id} not found in guild {message.guild.id}")
                    return False

                # Check if user already has LEVEL_2_ROLE_ID
                if level_2_role in message.author.roles:
                    await self.announce_progress(message.author, "already_completed", "LEVEL_1")
                    return True

                # Remove LEVEL_1_ROLE_ID and add LEVEL_2_ROLE_ID
                await message.author.remove_roles(level_1_role)
                await message.author.add_roles(level_2_role)

                # Announce success in progress channel
                await self.announce_progress(message.author, "completed", "LEVEL_1")

                # Update leaderboard
                await self.update_leaderboard()

                self.logger.info(f"User {message.author.id} ({message.author.name}) solved LEVEL_1 challenge")
                return True

            except discord.Forbidden:
                self.logger.error(f"Bot lacks permission to add role {self.level_2_role_id} to user {message.author.id}")
                await self.announce_progress(message.author, "error", "LEVEL_1")
                return False
            except Exception as e:
                self.logger.error(f"Error processing LEVEL_1 challenge for user {message.author.id}: {e}")
                await self.announce_progress(message.author, "error", "LEVEL_1")
                return False

        return False

    async def check_level_2_puzzle(self, message):
        """
        Check if user with LEVEL_2_ROLE_ID answered '29212' in LEVEL_2_CHANNEL
        If correct, add LEVEL_3_ROLE_ID
        """
        if message.channel.id != self.level_2_channel_id:
            return False

        # Check if user has LEVEL_2_ROLE_ID
        level_2_role = message.guild.get_role(self.level_2_role_id)
        if not level_2_role or level_2_role not in message.author.roles:
            return False

        if message.content.strip() == '29212':
            try:
                # Get LEVEL_3_ROLE_ID
                level_3_role = message.guild.get_role(self.level_3_role_id)

                if not level_3_role:
                    self.logger.error(f"LEVEL_3_ROLE_ID {self.level_3_role_id} not found in guild {message.guild.id}")
                    return False

                # Check if user already has LEVEL_3_ROLE_ID
                if level_3_role in message.author.roles:
                    await self.announce_progress(message.author, "already_completed", "LEVEL_2")
                    return True

                # Remove LEVEL_2_ROLE_ID and add LEVEL_3_ROLE_ID
                await message.author.remove_roles(level_2_role)
                await message.author.add_roles(level_3_role)

                # Announce success in progress channel
                await self.announce_progress(message.author, "completed", "LEVEL_2")

                # Update leaderboard
                await self.update_leaderboard()

                self.logger.info(f"User {message.author.id} ({message.author.name}) solved LEVEL_2 challenge")
                return True

            except discord.Forbidden:
                self.logger.error(f"Bot lacks permission to add role {self.level_3_role_id} to user {message.author.id}")
                await self.announce_progress(message.author, "error", "LEVEL_2")
                return False
            except Exception as e:
                self.logger.error(f"Error processing LEVEL_2 challenge for user {message.author.id}: {e}")
                await self.announce_progress(message.author, "error", "LEVEL_2")
                return False

        return False

    async def check_level_3_reaction(self, reaction, user):
        """
        Check if user with LEVEL_3_ROLE_ID reacted with :palm_tree: to message in RULES_CHANNEL
        If correct, remove LEVEL_3_ROLE_ID and add LEVEL_4_ROLE_ID
        """
        # Check if reaction is in RULES_CHANNEL
        if reaction.message.channel.id != self.rules_channel_id:
            return False

        # Check if reaction is on the specific message
        if reaction.message.id != self.rules_message_id:
            return False

        # Check if the emoji is palm_tree
        if str(reaction.emoji) != "🌴":
            return False

        # Check if user has LEVEL_3_ROLE_ID
        level_3_role = user.guild.get_role(self.level_3_role_id)
        if not level_3_role or level_3_role not in user.roles:
            return False

        try:
            # Get LEVEL_4_ROLE_ID
            level_4_role = user.guild.get_role(self.level_4_role_id)

            if not level_4_role:
                self.logger.error(f"LEVEL_4_ROLE_ID {self.level_4_role_id} not found in guild {user.guild.id}")
                return False

            # Check if user already has LEVEL_4_ROLE_ID
            if level_4_role in user.roles:
                await self.announce_progress(user, "already_completed", "LEVEL_3")
                return True

            # Remove LEVEL_3_ROLE_ID and add LEVEL_4_ROLE_ID
            await user.remove_roles(level_3_role)
            await user.add_roles(level_4_role)

            # Announce success in progress channel
            await self.announce_progress(user, "completed", "LEVEL_3")

            # Update leaderboard
            await self.update_leaderboard()

            self.logger.info(f"User {user.id} ({user.name}) solved LEVEL_3 challenge")
            return True

        except discord.Forbidden:
            self.logger.error(f"Bot lacks permission to modify roles for user {user.id}")
            await self.announce_progress(user, "error", "LEVEL_3")
            return False
        except Exception as e:
            self.logger.error(f"Error processing LEVEL_3 challenge for user {user.id}: {e}")
            await self.announce_progress(user, "error", "LEVEL_3")
            return False

    async def announce_progress(self, user, status, challenge_name):
        """
        Announce user progress in the hunt progress channel
        """
        try:
            progress_channel = self.bot.get_channel(self.hunt_progress_channel_id)
            if not progress_channel:
                self.logger.error(f"Hunt progress channel {self.hunt_progress_channel_id} not found")
                return

            if status == "completed":
                # Map internal challenge names to display names
                display_names = {
                    "THE_LODGE": "The Lodge",
                    "LEVEL_0": "The Forest",
                    "LEVEL_1": "The River",
                    "LEVEL_2": "The Mountain",
                    "LEVEL_3": "The Meadow",
                    "LEVEL_4": "The Beach"
                }

                display_name = display_names.get(challenge_name, challenge_name)

                embed = discord.Embed(
                    title="🎉 Completed!",
                    description=f"**{user.display_name}** has successfully completed **{display_name}**!",
                    color=discord.Color.green()
                )

                if challenge_name == "THE_LODGE":
                    embed.add_field(
                        name="Next Step",
                        value=f"Check out <#{self.level_0_channel_id}> for your next adventure!",
                        inline=False
                    )
                elif challenge_name == "LEVEL_0":
                    embed.add_field(
                        name="Next Step",
                        value=f"Check out <#{self.level_1_channel_id}> for your next adventure!",
                        inline=False
                    )
                elif challenge_name == "LEVEL_1":
                    embed.add_field(
                        name="Next Step",
                        value=f"Check out <#{self.level_2_channel_id}> for your next adventure!",
                        inline=False
                    )
                elif challenge_name == "LEVEL_2":
                    embed.add_field(
                        name="Next Step",
                        value=f"Check out <#{self.level_3_channel_id}> for your next adventure!",
                        inline=False
                    )
                elif challenge_name == "LEVEL_3":
                    embed.add_field(
                        name="Next Step",
                        value=f"Check out <#{self.level_4_channel_id}> for your next adventure!",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Congratulations!",
                        value="You've completed this level!",
                        inline=False
                    )

                embed.set_footer(text="🏃 Keep hunting!")

            elif status == "already_completed":
                embed = discord.Embed(
                    title="🎯 Already Completed",
                    description=f"**{user.display_name}** already has access to the next level!",
                    color=discord.Color.blue()
                )

            elif status == "error":
                embed = discord.Embed(
                    title="❌ Error",
                    description=f"**{user.display_name}** encountered an error while solving **{challenge_name}**. Please contact an admin.",
                    color=discord.Color.red()
                )

            await progress_channel.send(embed=embed)

        except Exception as e:
            self.logger.error(f"Error announcing progress: {e}")

    async def cleanup_escape_room_channels(self):
        """
        Clean up messages in escape room channels that are not from users with HOST_ROLE_ID
        """
        channels_to_clean = [
            (self.the_lodge_channel_id, "THE_LODGE"),
            (self.level_0_channel_id, "LEVEL_0"),
            (self.level_1_channel_id, "LEVEL_1"),
            (self.level_2_channel_id, "LEVEL_2"),
            (self.level_3_channel_id, "LEVEL_3")
        ]

        print(f"🧹 Starting escape room cleanup - okrag_id: {self.okrag_id}, host_role_id: {self.host_role_id}")
        self.logger.info(f"🧹 Starting escape room cleanup - okrag_id: {self.okrag_id}, host_role_id: {self.host_role_id}")
        total_cleaned = 0

        for channel_id, channel_name in channels_to_clean:
            try:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    print(f"❌ Channel {channel_name} ({channel_id}) not found")
                    self.logger.warning(f"Channel {channel_name} ({channel_id}) not found")
                    continue

                print(f"🧹 Cleaning up {channel_name} channel (ID: {channel_id})...")
                self.logger.info(f"🧹 Cleaning up {channel_name} channel (ID: {channel_id})...")

                # Get all messages in the channel
                messages_to_delete = []
                total_messages_checked = 0
                async for message in channel.history(limit=None):
                    total_messages_checked += 1

                    # Skip messages from the bot itself
                    if message.author.id == self.bot.user.id:
                        continue

                    # Debug logging for okrag specifically
                    if message.author.id == self.okrag_id:
                        print(f"🔍 Found message from okrag_id ({self.okrag_id}) in {channel_name}: '{message.content[:50]}...'")
                        self.logger.info(f"Found message from okrag_id ({self.okrag_id}) in {channel_name}: '{message.content[:50]}...'")

                    # Check if the author has the HOST_ROLE_ID
                    has_host_role = False
                    if hasattr(message.author, 'roles'):
                        host_role = message.guild.get_role(self.host_role_id)
                        if message.author.id == self.okrag_id:
                            print(f"🔍 okrag role debug - host_role found: {host_role is not None}, host_role_id: {self.host_role_id}")
                            print(f"🔍 okrag user roles: {[role.id for role in message.author.roles]}")
                            print(f"🔍 okrag has host role: {host_role in message.author.roles if host_role else False}")

                        if host_role and host_role in message.author.roles:
                            has_host_role = True
                            # Debug logging for host role
                            if message.author.id == self.okrag_id:
                                print(f"✅ okrag_id ({self.okrag_id}) HAS host role - preserving message")
                                self.logger.info(f"okrag_id ({self.okrag_id}) HAS host role - preserving message")

                    # If user doesn't have host role, mark for deletion
                    if not has_host_role:
                        if message.author.id == self.okrag_id:
                            print(f"❌ okrag_id ({self.okrag_id}) does NOT have host role - marking for deletion")
                            self.logger.info(f"okrag_id ({self.okrag_id}) does NOT have host role - marking for deletion")
                        messages_to_delete.append(message)

                print(f"📊 Checked {total_messages_checked} messages in {channel_name}, marked {len(messages_to_delete)} for deletion")
                self.logger.info(f"Checked {total_messages_checked} messages in {channel_name}, marked {len(messages_to_delete)} for deletion")

                # Delete messages in batches
                if messages_to_delete:
                    # Discord allows bulk delete for messages newer than 14 days
                    import datetime
                    two_weeks_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14)

                    # Separate recent and old messages
                    recent_messages = [msg for msg in messages_to_delete if msg.created_at > two_weeks_ago]
                    old_messages = [msg for msg in messages_to_delete if msg.created_at <= two_weeks_ago]

                    # Bulk delete recent messages
                    if recent_messages:
                        try:
                            # Discord bulk delete has a limit of 100 messages at a time
                            for i in range(0, len(recent_messages), 100):
                                batch = recent_messages[i:i+100]
                                if len(batch) > 1:
                                    await channel.delete_messages(batch)
                                else:
                                    await batch[0].delete()
                                await asyncio.sleep(1)  # Rate limit protection

                            self.logger.info(f"Bulk deleted {len(recent_messages)} recent messages from {channel_name}")
                            total_cleaned += len(recent_messages)
                        except discord.Forbidden:
                            self.logger.error(f"Missing permissions to bulk delete messages in {channel_name}")
                        except Exception as e:
                            self.logger.error(f"Error bulk deleting messages in {channel_name}: {e}")

                    # Delete old messages individually
                    if old_messages:
                        for message in old_messages:
                            try:
                                await message.delete()
                                await asyncio.sleep(0.5)  # Rate limit protection
                            except discord.Forbidden:
                                self.logger.warning(f"Missing permissions to delete message {message.id} in {channel_name}")
                            except discord.NotFound:
                                pass  # Message already deleted
                            except Exception as e:
                                self.logger.error(f"Error deleting message {message.id} in {channel_name}: {e}")

                        self.logger.info(f"Individually deleted {len(old_messages)} old messages from {channel_name}")
                        total_cleaned += len(old_messages)

                else:
                    self.logger.info(f"No messages to clean up in {channel_name}")

            except discord.Forbidden:
                self.logger.error(f"Missing permissions to access {channel_name} channel")
            except Exception as e:
                self.logger.error(f"Error cleaning up {channel_name} channel: {e}")

        if total_cleaned > 0:
            print(f"✅ Escape room cleanup complete! Removed {total_cleaned} messages total")
            self.logger.info(f"✅ Escape room cleanup complete! Removed {total_cleaned} messages total")
        else:
            print("✅ Escape room cleanup complete! No messages needed removal")
            self.logger.info("✅ Escape room cleanup complete! No messages needed removal")

    async def cleanup_rules_message_reactions(self):
        """
        Clean up all reactions on the rules message
        """
        try:
            rules_channel = self.bot.get_channel(self.rules_channel_id)
            if not rules_channel:
                print(f"❌ Rules channel {self.rules_channel_id} not found")
                self.logger.warning(f"Rules channel {self.rules_channel_id} not found")
                return

            print(f"🧹 Cleaning up reactions on rules message...")
            self.logger.info(f"🧹 Cleaning up reactions on rules message...")

            # Get the specific message
            try:
                rules_message = await rules_channel.fetch_message(self.rules_message_id)
            except discord.NotFound:
                print(f"❌ Rules message {self.rules_message_id} not found")
                self.logger.warning(f"Rules message {self.rules_message_id} not found")
                return
            except discord.Forbidden:
                print(f"❌ No permission to access rules message {self.rules_message_id}")
                self.logger.error(f"No permission to access rules message {self.rules_message_id}")
                return

            # Clear all reactions from the message
            try:
                await rules_message.clear_reactions()
                print(f"✅ Cleared all reactions from rules message")
                self.logger.info(f"Cleared all reactions from rules message {self.rules_message_id}")
            except discord.Forbidden:
                print(f"❌ No permission to clear reactions from rules message")
                self.logger.error(f"No permission to clear reactions from rules message {self.rules_message_id}")
            except Exception as e:
                print(f"❌ Error clearing reactions: {e}")
                self.logger.error(f"Error clearing reactions from rules message {self.rules_message_id}: {e}")

        except Exception as e:
            print(f"❌ Error during rules message reaction cleanup: {e}")
            self.logger.error(f"Error during rules message reaction cleanup: {e}")

    async def handle_message(self, message):
        """
        Main handler for okra hunt messages
        Returns True if message was handled by okra hunt system
        """
        if message.author.bot:
            return False

        # Check if message is in any escape room channel
        escape_room_channels = [self.the_lodge_channel_id, self.level_0_channel_id, self.level_1_channel_id, self.level_2_channel_id, self.level_3_channel_id]

        if message.channel.id in escape_room_channels:
            # Check if user has HOST_ROLE_ID
            has_host_role = False
            if hasattr(message.author, 'roles'):
                host_role = message.guild.get_role(self.host_role_id)
                if host_role and host_role in message.author.roles:
                    has_host_role = True

            # If user has host role, preserve their message
            if has_host_role:
                print(f"✅ Preserving message from host user: {message.author.display_name} in {message.channel.name}")
                # For THE_LODGE, still check if it's a correct answer
                if message.channel.id == self.the_lodge_channel_id:
                    await self.check_user_id_answer_without_deletion(message)
                # For LEVEL_0, still check if it's a correct answer
                elif message.channel.id == self.level_0_channel_id:
                    await self.check_okra_rules_answer(message)
                # For LEVEL_1, still check if it's a correct answer
                elif message.channel.id == self.level_1_channel_id:
                    await self.check_level_1_puzzle(message)
                # For LEVEL_2, still check if it's a correct answer
                elif message.channel.id == self.level_2_channel_id:
                    await self.check_level_2_puzzle(message)
                return False  # Don't delete, let message stay

            # Delete message from non-host users
            try:
                await message.delete()
                print(f"🗑️ Deleted message from {message.author.display_name} in {message.channel.name}")
            except discord.Forbidden:
                self.logger.warning(f"Cannot delete message in channel {message.channel.id} - missing permissions")
            except Exception as e:
                self.logger.error(f"Error deleting message: {e}")

            # For THE_LODGE, still process the answer logic after deletion
            if message.channel.id == self.the_lodge_channel_id:
                await self.process_lodge_answer(message)
            # For LEVEL_0, still process the answer logic after deletion
            elif message.channel.id == self.level_0_channel_id:
                await self.check_okra_rules_answer(message)
            # For LEVEL_1, still process the answer logic after deletion
            elif message.channel.id == self.level_1_channel_id:
                await self.check_level_1_puzzle(message)
            # For LEVEL_2, still process the answer logic after deletion
            elif message.channel.id == self.level_2_channel_id:
                await self.check_level_2_puzzle(message)

            return True  # Message was handled

        return False

    async def handle_reaction(self, reaction, user):
        """
        Main handler for okra hunt reactions
        Returns True if reaction was handled by okra hunt system
        """
        if user.bot:
            return False

        # Check LEVEL_3 palm tree reaction challenge
        if await self.check_level_3_reaction(reaction, user):
            return True

        return False

    async def get_user_progress(self, user):
        """
        Get user's current progress in the escape room
        Returns a dictionary with progress information
        """
        progress = {
            "level": "lodge",
            "completed_challenges": [],
            "current_channels": [self.the_lodge_channel_id]
        }

        # Check if user has LEVEL_0_ROLE
        level_0_role = user.guild.get_role(self.level_0_role_id)
        if level_0_role and level_0_role in user.roles:
            progress["level"] = "level_0"
            progress["completed_challenges"].append("lodge_user_id")
            progress["current_channels"].append(self.level_0_channel_id)

        return progress

    async def reset_user_progress(self, user):
        """
        Reset a user's progress in the escape room
        Removes all escape room related roles
        """
        try:
            roles_to_remove = []

            # Check for LEVEL_0_ROLE
            level_0_role = user.guild.get_role(self.level_0_role_id)
            if level_0_role and level_0_role in user.roles:
                roles_to_remove.append(level_0_role)

            if roles_to_remove:
                await user.remove_roles(*roles_to_remove)
                self.logger.info(f"Reset progress for user {user.id} ({user.name})")
                return True

            return False

        except discord.Forbidden:
            self.logger.error(f"Bot lacks permission to remove roles from user {user.id}")
            return False
        except Exception as e:
            self.logger.error(f"Error resetting progress for user {user.id}: {e}")
            return False

    async def get_all_level_roles(self):
        """
        Get all level roles that exist in the guild, following the LEVEL_N_ROLE_ID pattern
        Returns list of (level_number, role) tuples sorted by level
        """
        guild = self.bot.get_guild(self.bot.guilds[0].id) if self.bot.guilds else None
        if not guild:
            return []

        level_roles = []

        # Check known level roles first
        known_roles = [
            (0, self.level_0_role_id),
            (1, self.level_1_role_id),
            (2, self.level_2_role_id),
            (3, self.level_3_role_id),
            (4, self.level_4_role_id)
        ]

        for level, role_id in known_roles:
            role = guild.get_role(role_id)
            if role and len(role.members) > 0:
                level_roles.append((level, role))

        # Check for higher levels with pattern LEVEL_N_ROLE_ID
        # We'll check up to level 20 to be safe
        for level in range(5, 21):
            try:
                # This assumes there might be variables like LEVEL_5_ROLE_ID, etc.
                # For now, we'll just use the known roles
                pass
            except:
                break

        return sorted(level_roles, key=lambda x: x[0])

    async def generate_leaderboard_embed(self):
        """
        Generate a Discord embed showing the current leaderboard
        """
        level_roles = await self.get_all_level_roles()

        if not level_roles:
            embed = discord.Embed(
                title="🏆 Hunt Leaderboard",
                description="No players currently in the hunt!",
                color=discord.Color.blue()
            )
            return embed

        embed = discord.Embed(
            title="🏆 Hunt Leaderboard",
            description="Current progress of all hunt participants\n\u200b",  # Add invisible space for padding
            color=discord.Color.gold()
        )

        # Get role names and locations dynamically
        def get_role_display_info(role, level):
            if not role or not role.name:
                return "Unknown Role", "🔸"

            # Map level numbers to locations and emojis
            location_map = {
                0: ("The Forest", "🌲"),
                1: ("The River", "🌊"),
                2: ("The Mountain", "⛰️"),
                3: ("The Meadow", "🌾"),
                4: ("The Beach", "🌴")
            }

            location, emoji = location_map.get(level, ("Unknown Location", "🔸"))
            # Clean up the role name - remove extra emojis and parentheses for cleaner display
            clean_role_name = role.name
            return f"**{clean_role_name}**", emoji, location

        total_players = 0

        for level, role in level_roles:
            members = role.members
            if not members:
                continue

            total_players += len(members)
            role_display_text, emoji, location = get_role_display_info(role, level)

            # Sort members by display name for consistent ordering
            member_names = sorted([member.display_name for member in members])
            members_text = ", ".join(member_names)

            # Truncate if too long for embed field
            if len(members_text) > 1024:
                visible_names = []
                current_length = 0
                for name in member_names:
                    if current_length + len(name) + 2 > 1000:  # Leave space for "..."
                        break
                    visible_names.append(name)
                    current_length += len(name) + 2

                members_text = ", ".join(visible_names) + f"... (+{len(members) - len(visible_names)} more)"

            embed.add_field(
                name=f"{role_display_text} ({len(members)})\n📍 {location} {emoji}",
                value=f"{members_text}\n\u200b",  # Add spacing after each section
                inline=False
            )

        # Remove footer and timestamp for cleaner look

        return embed

    async def update_leaderboard(self):
        """
        Update the leaderboard message in the hunt leaderboard channel
        """
        try:
            leaderboard_channel = self.bot.get_channel(self.hunt_leaderboard_channel_id)
            if not leaderboard_channel:
                self.logger.error(f"Hunt leaderboard channel {self.hunt_leaderboard_channel_id} not found")
                return

            embed = await self.generate_leaderboard_embed()

            # Try to update the existing message using the constant ID
            try:
                existing_message = await leaderboard_channel.fetch_message(self.hunt_leaderboard_message_id)
                await existing_message.edit(embed=embed)
                self.logger.info(f"Updated existing leaderboard message {self.hunt_leaderboard_message_id}")
                return
            except discord.NotFound:
                self.logger.warning(f"Leaderboard message {self.hunt_leaderboard_message_id} not found, creating new one")
            except Exception as e:
                self.logger.error(f"Error updating leaderboard message {self.hunt_leaderboard_message_id}: {e}")

            # Create new leaderboard message
            message = await leaderboard_channel.send(embed=embed)
            self.logger.info(f"Created new leaderboard message with ID {message.id}")
            self.logger.warning(f"Please update HUNT_LEADERBOARD_MESSAGE_ID to {message.id} in discordbot.py")

        except Exception as e:
            self.logger.error(f"Error updating leaderboard: {e}")
