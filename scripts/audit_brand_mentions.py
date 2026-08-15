"""One-off, read-only audit: find every live Discord channel topic, pinned message, and
message in known reference channels (rules / how-to-play / game-options / anything whose
name suggests wiki/guide/faq content) that still mentions "TriviaSphere" or "triviasphere",
so they can be reviewed and updated to "Okra's World" by hand.

This content isn't stored anywhere in the repo (no /rules command, no channel-topic-setting
code, no sync mechanism) -- it was authored directly in Discord, so this is the only way to
find it. Makes no edits.

Run once per environment, with the matching bot token:

    ENVIRONMENT=stage discord_token=<stage bot token> python scripts/audit_brand_mentions.py
    ENVIRONMENT=prod discord_token=<prod bot token> python scripts/audit_brand_mentions.py

Writes a report to audit_brand_mentions_<environment>.md in the current directory and also
prints a summary to stdout.
"""
import os
import re

import discord

ENVIRONMENT = os.environ.get("ENVIRONMENT", "prod")

GUILD_IDS = {"prod": 1367682586079395902, "stage": 1375328358573015050}
RULES_CHANNEL_IDS = {"prod": 1372347624648347649, "stage": 1420238660342648873}
HOW_TO_PLAY_CHANNEL_IDS = {"prod": 1411551000065609939, "stage": 1423894911908057118}

GUILD_ID = GUILD_IDS[ENVIRONMENT]
KNOWN_REFERENCE_CHANNEL_IDS = {RULES_CHANNEL_IDS[ENVIRONMENT], HOW_TO_PLAY_CHANNEL_IDS[ENVIRONMENT]}
REFERENCE_NAME_PATTERN = re.compile(r"rule|how.?to|howto|guide|wiki|faq|info|welcome|start|option", re.IGNORECASE)
BRAND_PATTERN = re.compile(r"triviasphere", re.IGNORECASE)
HISTORY_LIMIT = 500  # per reference channel

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def _jump_url(channel_id, message_id=None, guild_id=GUILD_ID):
    if message_id:
        return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
    return f"https://discord.com/channels/{guild_id}/{channel_id}"


def _snippet(text, width=140):
    text = text.replace("\n", " ⏎ ")
    return text if len(text) <= width else text[:width] + "…"


@client.event
async def on_ready():
    hits = []  # list of dict: kind, channel_name, channel_id, message_id, author, snippet, url
    try:
        guild = client.get_guild(GUILD_ID)
        if guild is None:
            print(f"❌ Guild {GUILD_ID} not found (bot not in that server?)")
            return

        print(f"🔍 Auditing '{guild.name}' ({ENVIRONMENT}) — {len(guild.text_channels)} text channels…")

        for channel in guild.text_channels:
            # 1. Channel topic/description
            if channel.topic and BRAND_PATTERN.search(channel.topic):
                hits.append({
                    "kind": "channel topic",
                    "channel": f"#{channel.name}",
                    "url": _jump_url(channel.id),
                    "author": None,
                    "snippet": _snippet(channel.topic),
                })

            # 2. Pinned messages, in every channel (cheap: one API call each)
            try:
                pins = await channel.pins()
            except (discord.Forbidden, discord.HTTPException) as e:
                print(f"  ⚠️  couldn't read pins in #{channel.name}: {e}")
                pins = []
            for msg in pins:
                if BRAND_PATTERN.search(msg.content or ""):
                    hits.append({
                        "kind": "pinned message",
                        "channel": f"#{channel.name}",
                        "url": _jump_url(channel.id, msg.id),
                        "author": str(msg.author),
                        "snippet": _snippet(msg.content),
                    })

            # 3. Recent history in known/likely reference channels (anyone's messages, not
            # just the bot's -- admins may have posted rules/wiki content by hand)
            is_reference_channel = (
                channel.id in KNOWN_REFERENCE_CHANNEL_IDS
                or REFERENCE_NAME_PATTERN.search(channel.name)
            )
            if is_reference_channel:
                print(f"  📖 scanning history of #{channel.name} (reference channel)…")
                try:
                    async for msg in channel.history(limit=HISTORY_LIMIT):
                        if BRAND_PATTERN.search(msg.content or ""):
                            hits.append({
                                "kind": "message in reference channel",
                                "channel": f"#{channel.name}",
                                "url": _jump_url(channel.id, msg.id),
                                "author": str(msg.author),
                                "snippet": _snippet(msg.content),
                            })
                except (discord.Forbidden, discord.HTTPException) as e:
                    print(f"  ⚠️  couldn't read history in #{channel.name}: {e}")

        # Webhooks: flag anything still named after the old brand (renamed in code, but
        # existing live webhooks need a manual/one-time rename -- chat_mirror.py now does
        # this automatically on next use, this just confirms current live state)
        for channel in guild.text_channels:
            try:
                webhooks = await channel.webhooks()
            except (discord.Forbidden, discord.HTTPException):
                continue
            for wh in webhooks:
                if wh.name and BRAND_PATTERN.search(wh.name):
                    hits.append({
                        "kind": "webhook name",
                        "channel": f"#{channel.name}",
                        "url": _jump_url(channel.id),
                        "author": None,
                        "snippet": wh.name,
                    })

        report_path = f"audit_brand_mentions_{ENVIRONMENT}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# TriviaSphere mention audit — {guild.name} ({ENVIRONMENT})\n\n")
            f.write(f"{len(hits)} hit(s) found.\n\n")
            for hit in hits:
                f.write(f"## {hit['kind']} — {hit['channel']}\n")
                if hit["author"]:
                    f.write(f"- Author: {hit['author']}\n")
                f.write(f"- Link: {hit['url']}\n")
                f.write(f"- Text: {hit['snippet']}\n\n")

        print(f"\n✅ Done. {len(hits)} hit(s) written to {report_path}")
        for hit in hits:
            print(f"  [{hit['kind']}] {hit['channel']}: {_snippet(hit['snippet'], 80)}")
    finally:
        await client.close()


client.run(os.environ["discord_token"])
