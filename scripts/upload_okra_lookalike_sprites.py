"""One-time seed script: upload the "spot the non-duplicated one" okra_chef profession
variants (30 generated this session, e.g. okra_astronaut.png, okra_pirate.png, ...) into
the existing hidden_okra_sprites collection under theme "okra_lookalike".

NOT a generation script like generate_sprite_library.py -- these images already exist
(made via ChatGPT, reviewed by hand). This just uploads local files to S3 and inserts
their Mongo metadata, same collection/S3-prefix convention as every other sprite in this
project, so wheres_okra.compose_lookalike_puzzle's pool loader
(discordbot.py's _wheres_okra_load_lookalike_pool) can find them.

Each file's profession label (used as the sprite's `tags` entry) is derived from its own
filename: "okra_astronaut.png" -> "astronaut". Files not matching the "okra_<slug>.png"
pattern are skipped with a warning rather than guessed at.

Usage:
    # Staging first, and always look at what a dry run intends to do.
    mongo_db_string="$(heroku config:get mongo_db_string -a discordbot-staging)" \\
        AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=us-east-2 \\
        python3 scripts/upload_okra_lookalike_sprites.py --dir ~/Desktop/okra_professions --dry-run

    mongo_db_string="$(heroku config:get mongo_db_string -a discordbot-staging)" \\
        AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=us-east-2 \\
        python3 scripts/upload_okra_lookalike_sprites.py --dir ~/Desktop/okra_professions

    # Then prod, once staging is confirmed working end-to-end.
    ... mongo_db_string="$(heroku config:get mongo_db_string -a discordtriviabot)" ...

--dry-run prints the plan and writes nothing -- no AWS/Mongo credentials needed at all.
"""
import argparse
import datetime
import os
import re
import sys
import uuid

S3_BUCKET_NAME = "triviabotwebsite"
S3_PREFIX = "hidden_okra_sprites/"
S3_REGION = "us-east-2"
MONGO_COLLECTION = "hidden_okra_sprites"
THEME = "okra_lookalike"

_FILENAME_RE = re.compile(r"^okra_([a-z0-9_]+)\.png$", re.IGNORECASE)


def find_sprites(directory):
    """Every "okra_<slug>.png" file in `directory`, as (path, slug) pairs, sorted by slug
    for stable/predictable ordering across runs. Anything else in the directory (stray
    files, review artifacts like a "_checker" composite) is skipped, not guessed at."""
    found = []
    skipped = []
    for name in sorted(os.listdir(directory)):
        match = _FILENAME_RE.match(name)
        if match is None:
            if name.lower().endswith(".png"):
                skipped.append(name)
            continue
        found.append((os.path.join(directory, name), match.group(1)))
    return found, skipped


async def run(args):
    directory = os.path.expanduser(args.dir)
    if not os.path.isdir(directory):
        print(f"❌ Not a directory: {directory}")
        return 1

    sprites, skipped = find_sprites(directory)
    if args.limit:
        sprites = sprites[:args.limit]

    if not sprites:
        print(f"No 'okra_<slug>.png' files found in {directory}.")
        return 1

    # --- Dry run: no credentials, no network, no writes. -------------------------------
    if args.dry_run:
        print(f"Dry run: would upload {len(sprites)} sprite(s) to theme {THEME!r}.\n")
        for path, slug in sprites:
            print(f"  {os.path.basename(path)}  ->  tag={slug!r}")
        if skipped:
            print(f"\nSkipped (not 'okra_<slug>.png'): {', '.join(skipped)}")
        print(f"\nWould upload to s3://{S3_BUCKET_NAME}/{S3_PREFIX}{THEME}/<uuid>.png")
        print(f"Would insert into Mongo collection {MONGO_COLLECTION!r}.")
        print("\nDry run -- no changes made.")
        return 0

    # --- Real run. ---------------------------------------------------------------------
    import boto3
    from pymongo import MongoClient

    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_REGION", S3_REGION),
    )
    mongo = MongoClient(os.environ["mongo_db_string"])
    collection = mongo["triviabot"][MONGO_COLLECTION]

    accepted, failed = [], 0

    for i, (path, slug) in enumerate(sprites):
        print(f"\n[{i + 1}/{len(sprites)}] {slug}")
        try:
            with open(path, "rb") as handle:
                image_bytes = handle.read()
        except Exception as exc:  # noqa: BLE001 -- one bad file shouldn't end the run
            failed += 1
            print(f"    ❌ read failed: {exc}")
            continue

        sprite_id = str(uuid.uuid4())
        s3_key = f"{S3_PREFIX}{THEME}/{sprite_id}.png"
        try:
            s3.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=image_bytes,
                          ContentType="image/png")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"    ❌ upload failed: {exc}")
            continue
        image_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{s3_key}"

        document = {
            "_id": sprite_id,
            "theme": THEME,
            "s3_key": s3_key,
            "image_url": image_url,
            "tags": [slug],
            "scale_class": None,
            "source": "chatgpt_manual",
            "subject": slug,
            "added_at": datetime.datetime.utcnow(),
        }
        collection.insert_one(document)
        accepted.append(document)
        print(f"    ✅ stored {sprite_id}")
        print(f"       {image_url}")

    print(f"\n{len(accepted)} accepted, {failed} failed")
    for document in accepted[:35]:
        print(f"  {document['_id']}  {document['subject']}")

    total = collection.count_documents({"theme": THEME})
    print(f"\nTheme {THEME!r} now holds {total} sprite(s).")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, metavar="DIR",
                        help="local directory of 'okra_<slug>.png' files to upload")
    parser.add_argument("--limit", type=int, default=None,
                        help="only process the first N sprites found")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan, write nothing, need no credentials")
    args = parser.parse_args()
    import asyncio
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
