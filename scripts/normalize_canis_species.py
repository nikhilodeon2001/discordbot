"""One-off data cleanup: normalize `species` for genus=="Canis" docs that are dog-breed/mix
entries to the canonical string "Canis Lupus". Leaves the 11 recognized wild-canid docs
untouched. Companion to OkrAnimal's common-name-mode Canis exclusion in discordbot.py
(filters on species == "Canis Lupus") -- keep the wild-canid name list in sync if it changes.

Usage:
    mongo_db_string=<uri> python scripts/normalize_canis_species.py --dry-run
    mongo_db_string=<uri> python scripts/normalize_canis_species.py
"""
import argparse
import os

from pymongo import MongoClient

WILD_CANID_NAMES = {
    "Eurasian Wolf", "Arctic Wolf", "Red Wolf", "Desert Wolf", "Arabian Wolf",
    "Mackenzie Valley Wolf", "Apennine Wolf", "Coyote", "Dingo", "Jackal", "Golden Jackal",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    client = MongoClient(os.environ["mongo_db_string"])
    collection = client["triviabot"]["animal_questions"]
    query = {"genus": "Canis", "name": {"$nin": sorted(WILD_CANID_NAMES)}}

    matched = list(collection.find(query, {"_id": 1, "name": 1, "species": 1}))
    print(f"Found {len(matched)} docs to normalize.")
    for doc in matched[:20]:
        print(f"  {doc['_id']}: {doc['name']!r} species={doc.get('species')!r} -> 'Canis Lupus'")
    if len(matched) > 20:
        print(f"  ... and {len(matched) - 20} more")

    if args.dry_run:
        print("Dry run -- no changes made.")
        return

    result = collection.update_many(query, {"$set": {"species": "Canis Lupus"}})
    print(f"Updated {result.modified_count} docs.")


if __name__ == "__main__":
    main()
