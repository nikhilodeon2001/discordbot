"""One-off script: attach the DM Reply button to a single already-sent relay message.

Must be run AFTER the updated bot (with the DMReplyButton dynamic item registered
in on_ready via bot.add_dynamic_items) has been deployed and restarted on prod —
otherwise clicking the button on the retrofitted message won't be handled.

Usage:
    discord_token=<prod bot token> python scripts/retrofit_dm_reply_button.py

Safe to delete after running once.
"""
import os
import re
import discord

CHANNEL_ID = 1516676355482452018
MESSAGE_ID = 1529920979210342450

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    try:
        channel = await client.fetch_channel(CHANNEL_ID)
        message = await channel.fetch_message(MESSAGE_ID)

        user_id = None
        for embed in message.embeds:
            if embed.footer and embed.footer.text:
                match = re.search(r"User ID:\s*(\d+)", embed.footer.text)
                if match:
                    user_id = int(match.group(1))
                    break

        if user_id is None:
            print("❌ Could not find 'User ID: ...' in the message's embed footer.")
            return

        view = discord.ui.View(timeout=None)
        view.add_item(
            discord.ui.Button(
                label="Reply",
                style=discord.ButtonStyle.primary,
                emoji="✉️",
                custom_id=f"dm_reply:user:{user_id}",
            )
        )
        await message.edit(view=view)
        print(f"✅ Added Reply button for user {user_id} to message {MESSAGE_ID}.")
    finally:
        await client.close()


client.run(os.environ["discord_token"])
