"""One-time/occasional seed script: generate background variants for Where's Okra's
sprite-compositing pipeline (wheres_okra.compose_sprite_puzzle) and store them in S3 (the
image) plus Mongo (the theme tag the compositor looks them up by).

Only a handful of these are needed per theme -- they're reused across every puzzle played
in that theme forever (see wheres_okra.py's module docstring), the same one-time-asset
economics as the sprite library (scripts/generate_sprite_library.py). Unlike a sprite,
there's no reference-style-matching call needed here (a background isn't meant to visually
resemble the mascot the way a decoy needs to); a plain images.generate with consistent
style wording across every call is what keeps a theme's variants looking like the same
place, not four different art styles stitched together.

Backgrounds are described via a JSON spec file, one entry per variant:
    [
      {"description": "a sunny sandy beach with gentle waves lapping the shore"},
      {"description": "a boardwalk with striped beach umbrellas and a wooden pier"}
    ]

Usage:
    # Staging first, and always look at what a dry run intends to do.
    openai_api_key=... \\
        mongo_db_string="$(heroku config:get mongo_db_string -a discordbot-staging)" \\
        AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=us-east-2 \\
        python3 scripts/generate_theme_backgrounds.py --theme beach --spec beach_backgrounds.json --dry-run

    openai_api_key=... \\
        mongo_db_string="$(heroku config:get mongo_db_string -a discordbot-staging)" \\
        AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=us-east-2 \\
        python3 scripts/generate_theme_backgrounds.py --theme beach --spec beach_backgrounds.json --save-local /tmp/beach_bg

    # Then prod, once the staging backgrounds have been eyeballed.
    ... mongo_db_string="$(heroku config:get mongo_db_string -a discordtriviabot)" ...

--dry-run prints the prompts and the plan and writes nothing, and needs no credentials at
all. --save-local writes every generated PNG next to the run for review before it enters
the live game -- a background needs to actually look busy/detailed enough everywhere for a
sprite to plausibly hide anywhere on it, which is worth checking by eye, not assumed.
"""
import argparse
import asyncio
import base64
import datetime
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

S3_BUCKET_NAME = "triviabotwebsite"
S3_PREFIX = "hidden_okra_backgrounds/"
S3_REGION = "us-east-2"
MONGO_COLLECTION = "hidden_okra_backgrounds"

BACKGROUND_IMAGE_MODEL = "gpt-image-1"
BACKGROUND_IMAGE_QUALITY = "high"


def build_background_prompt(description):
    """No mascot, no specific characters -- just a densely-detailed backdrop consistent
    scenes/sprites can be scattered onto. Matches the flat-cartoon style wording used
    throughout wheres_okra.py's other prompts, so a background and the sprites pasted onto
    it read as one illustration style rather than two."""
    return (
        f"A wide illustrated backdrop of {description}, drawn in a consistent flat "
        f"cartoon style with clean uniform linework, even ambient lighting, and rich "
        f"small detail spread evenly across the entire frame -- no large empty or sparse "
        f"regions anywhere, since small objects will later be scattered across it and need "
        f"somewhere visually busy to blend into. No characters, no text, no logos."
    )


def load_spec(path):
    with open(os.path.expanduser(path), encoding="utf-8") as f:
        spec = json.load(f)
    if not isinstance(spec, list) or not spec:
        raise ValueError(f"{path} must contain a non-empty JSON array")
    for i, entry in enumerate(spec):
        if "description" not in entry:
            raise ValueError(f"spec entry {i} is missing required key 'description'")
    return spec


async def run(args):
    spec = load_spec(args.spec)
    if args.limit:
        spec = spec[:args.limit]

    # --- Dry run: no credentials, no network, no writes. -------------------------------
    if args.dry_run:
        print(f"Dry run: would generate {len(spec)} background(s) for theme {args.theme!r}.\n")
        for i, entry in enumerate(spec):
            print(f"[{i + 1}/{len(spec)}] description={entry['description']!r}")
            if i == 0:
                print("\n--- prompt ---")
                print(build_background_prompt(entry["description"]))
                print("--- end prompt ---\n")
        print(f"Would upload to s3://{S3_BUCKET_NAME}/{S3_PREFIX}{args.theme}/<uuid>.png")
        print(f"Would insert into Mongo collection {MONGO_COLLECTION!r}.")
        print("\nDry run -- no changes made.")
        return 0

    # --- Real run. ---------------------------------------------------------------------
    import boto3
    from openai import AsyncOpenAI
    from pymongo import MongoClient

    openai_client = AsyncOpenAI(api_key=os.environ["openai_api_key"])
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_REGION", S3_REGION),
    )
    mongo = MongoClient(os.environ["mongo_db_string"])
    collection = mongo["triviabot"][MONGO_COLLECTION]

    if args.save_local:
        os.makedirs(args.save_local, exist_ok=True)

    accepted, failed = [], 0

    for i, entry in enumerate(spec):
        description = entry["description"]
        print(f"\n[{i + 1}/{len(spec)}] {description}")
        prompt = build_background_prompt(description)
        try:
            response = await openai_client.images.generate(
                model=BACKGROUND_IMAGE_MODEL,
                prompt=prompt,
                size="1024x1024",
                quality=BACKGROUND_IMAGE_QUALITY,
            )
            image_bytes = base64.b64decode(response.data[0].b64_json)
        except Exception as exc:  # noqa: BLE001 -- one bad background shouldn't end the run
            failed += 1
            print(f"    ❌ generation failed: {exc}")
            continue

        background_id = str(uuid.uuid4())
        s3_key = f"{S3_PREFIX}{args.theme}/{background_id}.png"
        s3.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=image_bytes,
                      ContentType="image/png")
        image_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{s3_key}"

        document = {
            "_id": background_id,
            "theme": args.theme,
            "s3_key": s3_key,
            "image_url": image_url,
            "description": description,
            "prompt": prompt,
            "added_at": datetime.datetime.utcnow(),
        }
        collection.insert_one(document)
        accepted.append(document)

        if args.save_local:
            local = os.path.join(args.save_local, f"{background_id}.png")
            with open(local, "wb") as handle:
                handle.write(image_bytes)

        print(f"    ✅ stored {background_id}")
        print(f"       {image_url}")

    print(f"\n{len(accepted)} accepted, {failed} failed")
    for document in accepted[:20]:
        print(f"  {document['_id']}  {document['theme']:<10} {document['description']}")
    if len(accepted) > 20:
        print(f"  ... and {len(accepted) - 20} more")

    if args.save_local and accepted:
        print(f"\n⚠️  Look at the PNGs in {args.save_local} before letting anyone play them --")
        print("   confirm there's no large empty region a sprite would look out of place in.")

    total = collection.count_documents({"theme": args.theme})
    print(f"\nTheme {args.theme!r} now holds {total} background variant(s).")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", required=True)
    parser.add_argument("--spec", required=True, metavar="FILE",
                        help="JSON file: a list of {description} entries")
    parser.add_argument("--limit", type=int, default=None,
                        help="only process the first N entries of --spec")
    parser.add_argument("--save-local", default=None, metavar="DIR",
                        help="also write every generated PNG to DIR for visual review")
    parser.add_argument("--dry-run", action="store_true",
                        help="print prompts and the plan, write nothing, need no credentials")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
