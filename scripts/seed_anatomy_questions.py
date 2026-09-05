"""One-time seed script: load the Usable=True rows of trivia_game_data.csv into the
anatomy_questions Mongo collection for Okra's Anatomy.

Safe to re-run: upserts by `filename`, so it's fine to run again if the CSV is later
corrected or extended.

Must be run once against EACH environment's own Mongo, using that environment's own
mongo_db_string (same convention as scripts/normalize_canis_species.py):

    mongo_db_string="$(heroku config:get mongo_db_string -a discordbot-staging)" \
        python3 scripts/seed_anatomy_questions.py --csv ~/Desktop/bone_trivia_images/trivia_game_data.csv --dry-run
    mongo_db_string="$(heroku config:get mongo_db_string -a discordbot-staging)" \
        python3 scripts/seed_anatomy_questions.py --csv ~/Desktop/bone_trivia_images/trivia_game_data.csv

    mongo_db_string="$(heroku config:get mongo_db_string -a discordtriviabot)" \
        python3 scripts/seed_anatomy_questions.py --csv ~/Desktop/bone_trivia_images/trivia_game_data.csv --dry-run
    mongo_db_string="$(heroku config:get mongo_db_string -a discordtriviabot)" \
        python3 scripts/seed_anatomy_questions.py --csv ~/Desktop/bone_trivia_images/trivia_game_data.csv

Document shape (see row_to_doc below) uses lowercase snake_case fields, matching the
animal_questions convention rather than the CSV's TitleCase headers.
"""
import argparse
import asyncio
import csv
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

S3_BUCKET_NAME = "triviabotwebsite"
S3_PREFIX = "anatomy_images/"


def row_to_doc(row):
    aws_region = os.environ.get("AWS_REGION", "us-east-2")
    s3_key = S3_PREFIX + row["Filename"]
    return {
        "filename": row["Filename"],
        "s3_key": s3_key,
        "image_url": f"https://{S3_BUCKET_NAME}.s3.{aws_region}.amazonaws.com/{s3_key}",
        "anatomy_type": row["Anatomy_Type"],
        "body_part_name": row["Body_Part_Name"],
        "side": row.get("Side", ""),
        "source": row["Source"],
        "region": row["Region"],
        "difficulty": row["Difficulty"],
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(os.path.expanduser(args.csv), newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["Usable"] == "True"]

    print(f"Loaded {len(rows)} usable rows from {args.csv}")

    if args.dry_run:
        for r in rows[:5]:
            print("  ", row_to_doc(r))
        print(f"Dry run -- would upsert {len(rows)} docs. No changes made.")
        return

    client = AsyncIOMotorClient(os.environ["mongo_db_string"])
    collection = client["triviabot"]["anatomy_questions"]

    upserted = 0
    for row in rows:
        doc = row_to_doc(row)
        await collection.update_one({"filename": doc["filename"]}, {"$set": doc}, upsert=True)
        upserted += 1

    total = await collection.count_documents({})
    print(f"Upserted {upserted} docs. anatomy_questions now has {total} documents.")

    by_region = {}
    async for d in collection.aggregate([{"$group": {"_id": "$region", "count": {"$sum": 1}}}]):
        by_region[d["_id"]] = d["count"]
    print("By region:", by_region)

    by_difficulty = {}
    async for d in collection.aggregate([{"$group": {"_id": "$difficulty", "count": {"$sum": 1}}}]):
        by_difficulty[d["_id"]] = d["count"]
    print("By difficulty:", by_difficulty)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
