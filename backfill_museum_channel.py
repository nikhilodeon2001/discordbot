"""
One-time backfill: post every existing Okra Museum image (from S3) into the
#okra-museum Discord channel in chronological order, and record each image's
metadata in the `museum_images` MongoDB collection.

Idempotent: re-running skips any image whose museum_images doc already has
`channel_posted_at` (so images posted by the live bot path are never duplicated).

Run against PROD only (stage is not backfilled):

    ENVIRONMENT=prod discord_token=... mongo_db_string=... \
        AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=... \
        python backfill_museum_channel.py

Historical images have no known user_id, so their "By ..." line uses the stored
muse name. Images already recorded with a real user_id (from the live path) keep
a clickable <@user_id> mention.
"""

import argparse
import asyncio
import datetime
import os
import re
from urllib.parse import quote

import aioboto3
import discord
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()  # picks up .env like discordbot.py; real env vars still take precedence

ENVIRONMENT = os.environ.get("ENVIRONMENT", "prod")
CHANNEL_IDS = {"prod": 1524472945240572075, "stage": 1524473435328090304}
OKRA_MUSEUM_CHANNEL_ID = CHANNEL_IDS[ENVIRONMENT]

DISCORD_TOKEN = os.getenv("discord_token")
MONGO_DB_STRING = os.getenv("mongo_db_string")

BUCKET_NAME = "triviabotwebsite"
PREFIX = "generated-images/"
POST_DELAY_SECONDS = 1.5
MUSEUM_ACTIVE_THREAD_SAFETY_CAP = 990  # headroom below Discord's guild-wide 1000 active-thread limit


def parse_museum_image_key(object_key):
    """Parse title, muse, and date from generated museum image filenames.

    Kept in sync with discordbot.py::parse_museum_image_key.
    """
    filename = os.path.splitext(os.path.basename(object_key))[0]
    match = re.match(r'^(.+?)\s*&\s*(.+?)\s+\((.+?)\)$', filename)
    if match:
        title, muse, full_date = match.groups()
        clean_title = re.sub(r"[\"']", "", title)
    else:
        # Older title-less format: "{muse} ({date})"
        match = re.match(r'^(.+?)\s+\((.+?)\)$', filename)
        if not match:
            return None
        muse, full_date = match.groups()
        clean_title = None
    date_only = " ".join(full_date.split()[:-1]) or full_date
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            date_only = datetime.datetime.strptime(date_only, fmt).strftime("%b %-d, %Y")
            break
        except ValueError:
            continue
    return {
        "s3_key": object_key,
        "image_url": f"https://triviabotwebsite.s3.amazonaws.com/{quote(object_key, safe='/')}",
        "title": clean_title,
        "muse": muse,
        "creation_date": date_only,
    }


async def list_museum_images_chronologically():
    """Return parsed museum posts sorted by S3 LastModified ascending (oldest first)."""
    session = aioboto3.Session()
    items = []
    async with session.client("s3") as s3:
        token = None
        while True:
            kwargs = {"Bucket": BUCKET_NAME, "Prefix": PREFIX}
            if token:
                kwargs["ContinuationToken"] = token
            resp = await s3.list_objects_v2(**kwargs)
            items.extend(resp.get("Contents", []))
            if resp.get("IsTruncated"):
                token = resp.get("NextContinuationToken")
            else:
                break

    items = [it for it in items if it["Key"].lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
    items.sort(key=lambda it: it["LastModified"])  # oldest first → chronological

    posts = []
    for it in items:
        parsed = parse_museum_image_key(it["Key"])
        if parsed:
            posts.append(parsed)
        else:
            print(f"⚠️ Skipping malformed museum filename: {it['Key']}")
    return posts


def build_museum_embed(post, user_id=None):
    """Single embed: bold title / By <muse or mention> / date, with the image below."""
    muse_ref = f"<@{user_id}>" if user_id else post["muse"]
    header = f"**{post['title']}**\n" if post.get("title") else ""
    description = f"{header}By {muse_ref}\n{post['creation_date']}"
    embed = discord.Embed(description=description)
    embed.set_image(url=post["image_url"])
    return embed


def museum_thread_name(post):
    """Forum thread name showing title + painter so the gallery card (one line) shows both.

    Thread names are static plain text (no live mention), capped at Discord's 100 chars;
    the title is truncated if needed so the "by {muse}" always survives.
    """
    title = post.get("title")
    muse = post["muse"] or "Okra"
    if not title:
        return muse[:100]
    suffix = f" — by {muse}"
    max_title = 100 - len(suffix)
    if max_title < 1:
        return title[:100]
    shown = title if len(title) <= max_title else title[:max_title - 1] + "…"
    return f"{shown}{suffix}"


async def make_room_for_new_thread(museum_channel):
    """Archive the single oldest active thread in the forum if the guild is near Discord's
    1000 active-thread cap, so a rolling window of the newest paintings stays open."""
    try:
        guild = museum_channel.guild
        active = await guild.active_threads()
        if len(active) < MUSEUM_ACTIVE_THREAD_SAFETY_CAP:
            return
        forum_threads = sorted(
            (t for t in active if t.parent_id == museum_channel.id),
            key=lambda t: t.id,
        )
        if forum_threads:
            await forum_threads[0].edit(archived=True)
    except Exception as e:
        print(f"⚠️ Could not make room in okra-museum forum: {e}")


async def run_backfill(limit=None):
    if not DISCORD_TOKEN or not MONGO_DB_STRING:
        raise SystemExit("Missing required env vars: discord_token and mongo_db_string")

    mongo = AsyncIOMotorClient(MONGO_DB_STRING)
    museum_images = mongo["triviabot"]["museum_images"]

    posts = await list_museum_images_chronologically()
    if limit is not None:
        posts = posts[:limit]
        print(f"Limiting to first {limit} image(s) for this run.")
    print(f"Found {len(posts)} museum image(s) to process for {ENVIRONMENT}.")

    intents = discord.Intents.none()
    intents.guilds = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        posted = 0
        skipped = 0
        try:
            channel = (
                client.get_channel(OKRA_MUSEUM_CHANNEL_ID)
                or await client.fetch_channel(OKRA_MUSEUM_CHANNEL_ID)
            )
            for post in posts:
                s3_key = post["s3_key"]
                existing = await museum_images.find_one({"_id": s3_key})

                # Record/refresh metadata. Never clobber a real user_id/created_at
                # written by the live path — only set them on first insert.
                await museum_images.update_one(
                    {"_id": s3_key},
                    {
                        "$set": {
                            "muse": post["muse"],
                            "title": post["title"],
                            "image_url": post["image_url"],
                            "s3_key": s3_key,
                            "creation_date": post["creation_date"],
                        },
                        "$setOnInsert": {
                            "user_id": None,
                            "created_at": datetime.datetime.utcnow(),
                        },
                    },
                    upsert=True,
                )

                # Idempotency: skip anything already posted to the channel.
                if existing and existing.get("channel_posted_at"):
                    skipped += 1
                    continue

                user_id = existing.get("user_id") if existing else None
                embed = build_museum_embed(post, user_id)
                if isinstance(channel, discord.ForumChannel):
                    await make_room_for_new_thread(channel)
                    await channel.create_thread(name=museum_thread_name(post), embed=embed)
                else:
                    await channel.send(embed=embed)
                await museum_images.update_one(
                    {"_id": s3_key},
                    {"$set": {"channel_posted_at": datetime.datetime.utcnow()}},
                )
                posted += 1
                await asyncio.sleep(POST_DELAY_SECONDS)
        except Exception as e:
            print(f"❌ Backfill error: {e}")
        finally:
            print(f"✅ Backfill complete for {ENVIRONMENT}: posted {posted}, skipped {skipped}.")
            await client.close()

    await client.start(DISCORD_TOKEN)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill Okra Museum images into the Discord channel.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only process the first N images (chronological), for a test batch.")
    cli_args = parser.parse_args()
    asyncio.run(run_backfill(limit=cli_args.limit))
