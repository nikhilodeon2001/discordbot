"""
One-time seed script: load private-assets/spelling_bee/enriched.json (produced by
mw_enrich_spelling_bee.py) into the spellingbee_questions Mongo collection.

Safe to re-run: upserts by word, so it can be run again each time a new
mw_enrich_spelling_bee.py batch adds more words to the checkpoint file.

Usage:
    python3 seed_spelling_bee.py
"""
import json
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "private-assets", "spelling_bee")
CHECKPOINT_PATH = os.path.join(DATA_DIR, "enriched.json")


async def main():
    uri = os.getenv("mongo_db_string")
    client = AsyncIOMotorClient(uri)
    db = client["triviabot"]
    collection = db["spellingbee_questions"]

    with open(CHECKPOINT_PATH, encoding="utf-8") as f:
        enriched = json.load(f)

    inserted = 0
    skipped_not_found = 0

    for word, data in enriched.items():
        if not data.get("found"):
            skipped_not_found += 1
            continue

        doc = {
            "word": word,
            "definition": data.get("definition", ""),
            "part_of_speech": data.get("part_of_speech", ""),
            "example_sentence": data.get("example_sentence", ""),
            "etymology": data.get("etymology", ""),
            "tier": data.get("tier", ""),
            "pronunciation_url": data.get("pronunciation_url"),
            "enabled": True,
        }

        await collection.update_one({"word": word}, {"$set": doc}, upsert=True)
        inserted += 1

    total = await collection.count_documents({})
    print(f"Upserted {inserted} words ({skipped_not_found} not found in MW skipped).")
    print(f"spellingbee_questions collection now has {total} documents.")

    by_tier = {}
    async for doc in collection.aggregate([{"$group": {"_id": "$tier", "count": {"$sum": 1}}}]):
        by_tier[doc["_id"]] = doc["count"]
    print("By tier:", by_tier)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
