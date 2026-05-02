import os
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

DISCORD_TOKEN = os.getenv("discord_token")
MONGO_URI = os.getenv("mongo_db_string")
CHANNEL_ID = "1448895124183453696"
FLAG_TITLE = "🚩 Question Flagged"


def count_discord_flags():
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
    base_url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    count = 0
    last_id = None

    while True:
        params = {"limit": 100}
        if last_id:
            params["before"] = last_id

        resp = requests.get(base_url, headers=headers, params=params)
        resp.raise_for_status()
        messages = resp.json()

        if not messages:
            break

        for msg in messages:
            if msg.get("embeds") and msg["embeds"][0].get("title") == FLAG_TITLE:
                count += 1

        if len(messages) < 100:
            break

        last_id = messages[-1]["id"]

    return count


def count_mongo_audits():
    client = MongoClient(MONGO_URI)
    db = client["triviabot"]
    total = 0
    breakdown = {}

    for col_name in db.list_collection_names():
        n = db[col_name].count_documents({"audit": {"$exists": True, "$ne": []}})
        if n > 0:
            breakdown[col_name] = n
            total += n

    client.close()
    return total, breakdown


if __name__ == "__main__":
    print("Fetching Discord flag messages...")
    discord_count = count_discord_flags()

    print("Querying MongoDB for audit entries...")
    mongo_count, breakdown = count_mongo_audits()

    print(f"\nDiscord messages (flags): {discord_count}")
    print(f"MongoDB documents with audit: {mongo_count}")

    if breakdown:
        print("\nBreakdown by collection:")
        for col, n in sorted(breakdown.items(), key=lambda x: -x[1]):
            print(f"  {col}: {n}")

    print()
    if discord_count == mongo_count:
        print("✅ Counts match!")
    else:
        print(f"⚠️  Mismatch! Discord: {discord_count}, MongoDB: {mongo_count}")
