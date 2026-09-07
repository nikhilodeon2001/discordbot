"""One-time backfill: set `image_urls` and `flag_url` fields on every border_questions doc,
combining
(a) the existing "Identify the country filled in below" images already in trivia_questions
    (joined to border_questions by country name via a small alias map -- the two collections
    don't always use the same country name string),
(b) the Wikimedia "on the globe" locator images uploaded to
    s3://triviabotwebsite/geo_maps_wikimedia/<alpha2>.png (see
    scripts/upload_geo_wikimedia_images_to_s3.py), and
(c) the national flag (flag_detail == "National Flag") from flags_questions, joined by
    country name via the same kind of alias map (a different, overlapping set of spelling
    mismatches than (a) -- flags_questions uses accented/ampersand/"The X" forms).

Countries end up with 0-2 image_urls plus an optional flag_url. Run once per environment:

    mongo_db_string="$(heroku config:get mongo_db_string -a discordbot-staging)" \
        python3 scripts/backfill_border_image_urls.py --commons-lookup /path/to/commons_lookup.json --dry-run

    mongo_db_string="$(heroku config:get mongo_db_string -a discordtriviabot)" \
        python3 scripts/backfill_border_image_urls.py --commons-lookup /path/to/commons_lookup.json
"""
import argparse
import json
import os

import pymongo

WIKIMEDIA_S3_PREFIX = "https://triviabotwebsite.s3.us-east-2.amazonaws.com/geo_maps_wikimedia/"

# trivia_questions.answers[0] -> border_questions.country, where the two collections
# spell the same country differently.
NAME_ALIAS = {
    "Côte d'Ivoire": "Ivory Coast",
    "Democratic People's Republic of Korea": "North Korea",
    "Democratic Republic of the Congo": "DR Congo",
    "Macedonia": "North Macedonia",
    "Netherlands": "The Netherlands",
    "Republic of Korea": "South Korea",
    "Republic of the Congo": "Congo Republic",
    "The United States of America": "United States",
    "Turkey": "Türkiye",
}

# flags_questions.answer -> border_questions.country
FLAG_NAME_ALIAS = {
    **NAME_ALIAS,
    "Antigua & Barbuda": "Antigua and Barbuda",
    "Bhután": "Bhutan",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Cape Verde": "Cabo Verde",
    "Congo-Brazzaville": "Congo Republic",
    "Congo-Kinshasa": "DR Congo",
    "Côte d’Ivoire": "Ivory Coast",
    "Irân": "Iran",
    "México": "Mexico",
    "Panamá": "Panama",
    "Perú": "Peru",
    "România": "Romania",
    "Russian Federation": "Russia",
    "São Tomé & Príncipe": "São Tomé and Príncipe",
    "St. Helena & Dependencies": "Saint Helena",
    "St. Kitts & Nevis": "St Kitts and Nevis",
    "St. Vincent & the Grenadines": "St Vincent and Grenadines",
    "Swaziland": "Eswatini",
    "The Bahamas": "Bahamas",
    "The Czech Republic": "Czechia",
    "The Sudan": "Sudan",
    "Trinidad & Tobago": "Trinidad and Tobago",
    "Turks & Caicos Islands": "Turks and Caicos Islands",
    "Viêt Nam": "Vietnam",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commons-lookup", required=True, help="path to commons_lookup.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(os.path.expanduser(args.commons_lookup)) as f:
        wiki_lookup = json.load(f)

    client = pymongo.MongoClient(os.environ["mongo_db_string"])
    db = client["triviabot"]

    geo_docs = list(db["trivia_questions"].find(
        {"category": "Geography", "question": "Identify the country filled in below:"}
    ))
    existing_by_border_name = {}
    for d in geo_docs:
        primary = d["answers"][0]
        border_name = NAME_ALIAS.get(primary, primary)
        existing_by_border_name[border_name] = d["url"]

    # Exact match on "National Flag" misses countries whose only entry is a named
    # variant (e.g. Canada -> 'National Flag "The Maple Leaf"', United States ->
    # 'National Flag "Stars and Stripes"') -- match the whole family instead.
    flag_docs = list(db["flags_questions"].find({"flag_detail": {"$regex": '^National Flag'}}))
    # Process the plain "National Flag" docs first so they win when a country has
    # both a plain entry and a named variant (e.g. Spain) -- first-write-wins below.
    flag_docs.sort(key=lambda d: d["flag_detail"] != "National Flag")
    flag_by_border_name = {}
    for d in flag_docs:
        border_name = FLAG_NAME_ALIAS.get(d["answer"], d["answer"])
        flag_by_border_name.setdefault(border_name, d["flag_url"])

    border_docs = list(db["border_questions"].find({}))
    stats = {"both": 0, "existing_only": 0, "wiki_only": 0, "neither": 0}
    flag_matched = 0
    ops = []
    for doc in border_docs:
        name = doc["country"]
        alpha2 = doc["alpha2"]
        urls = []

        existing_url = existing_by_border_name.get(name)
        if existing_url:
            urls.append(existing_url)

        wiki_entry = wiki_lookup.get(name)
        has_wiki = bool(wiki_entry and wiki_entry.get("found"))
        if has_wiki:
            urls.append(WIKIMEDIA_S3_PREFIX + f"{alpha2}.png")

        if existing_url and has_wiki:
            stats["both"] += 1
        elif existing_url:
            stats["existing_only"] += 1
        elif has_wiki:
            stats["wiki_only"] += 1
        else:
            stats["neither"] += 1

        update = {"image_urls": urls}
        flag_url = flag_by_border_name.get(name)
        if flag_url:
            update["flag_url"] = flag_url
            flag_matched += 1

        ops.append(pymongo.UpdateOne({"_id": doc["_id"]}, {"$set": update}))

    print(f"Environment: {client.address}")
    print(f"border_questions docs: {len(border_docs)}")
    print(f"Image coverage: {stats}")
    print(f"Flag matches: {flag_matched} / {len(flag_docs)} national flags")

    if args.dry_run:
        print("[dry-run] would apply", len(ops), "updates -- not writing.")
        return

    result = db["border_questions"].bulk_write(ops)
    print(f"Modified: {result.modified_count}")


if __name__ == "__main__":
    main()
