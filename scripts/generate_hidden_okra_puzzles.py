"""One-time seed script: generate validated hidden-object puzzles for Where's Okra and
store them in S3 (the image) plus Mongo (the secret answer box).

Each puzzle is generated with the okra chef mascot as an identity reference, then located
by a vision pass over the finished pixels, then cross-checked against a crop of that
location. Only puzzles that survive all three steps are stored -- see wheres_okra.py for
why the generator's own claims about placement are never trusted.

Generation is slow (~30-90s per accepted puzzle) and costs real money (~$0.21 per attempt,
roughly $0.40 per accepted puzzle), which is exactly why the game draws from a pre-built
pool rather than generating inside a round.

Run once per environment -- staging and prod use different Mongo databases, so a pool
built against one is invisible to the other.

Usage:
    # Staging first, and always look at what a dry run intends to do.
    openai_api_key=... ANTHROPIC_API_KEY=... \\
        mongo_db_string="$(heroku config:get mongo_db_string -a discordbot-staging)" \\
        AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=us-east-2 \\
        python3 scripts/generate_hidden_okra_puzzles.py --count 4 --difficulty hard --dry-run

    openai_api_key=... ANTHROPIC_API_KEY=... \\
        mongo_db_string="$(heroku config:get mongo_db_string -a discordbot-staging)" \\
        AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=us-east-2 \\
        python3 scripts/generate_hidden_okra_puzzles.py --count 4 --difficulty hard

    # Then prod, once the staging puzzles have been eyeballed.
    ... mongo_db_string="$(heroku config:get mongo_db_string -a discordtriviabot)" ...

--dry-run prints the prompts and the plan and writes nothing, and needs no credentials at
all: no OpenAI key, no Anthropic key, no AWS, no Mongo. Use it to review prompt wording.

--save-local writes accepted PNGs next to the run so they can be inspected before anyone
plays them. Strongly recommended on the first batch of any new theme or difficulty: the
one failure mode no automated check can catch is a mascot that looks pasted on top of the
scene rather than drawn into it.
"""
import argparse
import asyncio
import base64
import datetime
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wheres_okra as wo  # noqa: E402

S3_BUCKET_NAME = "triviabotwebsite"
S3_PREFIX = "hidden_okra/"
S3_REGION = "us-east-2"
MONGO_COLLECTION = "hidden_okra_puzzles"

# The mascot identity reference. Lives in private-assets/, which is gitignored and
# hydrated from S3 at bot startup -- see GAME_ASSET_FILES in discordbot.py.
MASCOT_FILENAME = "okra_chef.png"


def mascot_path():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "private-assets", MASCOT_FILENAME)


def build_image_fns(openai_client):
    """Bind the OpenAI image endpoints into the two callables wheres_okra expects.

    Deliberately not imported from discordbot.py: importing that module pulls in the whole
    bot (discord.py, Mongo, S3 clients, a 1.5MB module executed at import time). The call
    is four lines, so a local copy is cheaper than the coupling.
    """
    async def edit_fn(reference_bytes, prompt):
        response = await openai_client.images.edit(
            model=wo.IMAGE_MODEL,
            image=(MASCOT_FILENAME, reference_bytes, "image/png"),
            prompt=prompt,
            size="1024x1024",
            quality=wo.IMAGE_QUALITY,
        )
        return base64.b64decode(response.data[0].b64_json)

    async def generate_fn(prompt):
        response = await openai_client.images.generate(
            model=wo.IMAGE_MODEL,
            prompt=prompt,
            size="1024x1024",
            quality=wo.IMAGE_QUALITY,
        )
        return base64.b64decode(response.data[0].b64_json)

    return edit_fn, generate_fn


def build_document(puzzle_id, s3_key, image_url, theme, difficulty, region, result, meta):
    """The stored puzzle. `target` is the secret and never leaves the server -- see the
    integrity note in wheres_okra.py and the game loop in discordbot.py."""
    box = wo.normalize_target(result.target)
    return {
        "_id": puzzle_id,
        "image_url": image_url,
        "s3_key": s3_key,
        "difficulty": difficulty,
        "theme": theme,
        "region": region,
        "target": {"xMin": box[0], "yMin": box[1], "xMax": box[2], "yMax": box[3]},
        "confidence": result.confidence,
        "visibility": result.visibility,
        "too_obvious": result.too_obvious,
        "malformed": result.malformed,
        "area": wo.bbox_area(box),
        "generated_at": datetime.datetime.utcnow(),
        "attempts": meta["attempts"],
        "used_reference": meta["used_reference"],
        "image_model": meta["image_model"],
        "image_quality": meta["image_quality"],
        "vision_model": meta["vision_model"],
        "verify_model": meta["verify_model"],
        "verify_confidence": meta["verify_confidence"],
        "prompt": meta["prompt"],
    }


async def run(args):
    rng = wo.make_rng(args.seed)

    # --- Dry run: no credentials, no network, no writes. -------------------------------
    if args.dry_run:
        print(f"Dry run: would generate {args.count} '{args.difficulty}' puzzle(s).\n")
        last_theme = last_region = None
        for i in range(args.count):
            theme = args.theme or wo.pick_theme(rng, exclude=last_theme)
            region = wo.pick_region(rng, exclude=last_region)
            last_theme, last_region = theme, region
            spec = wo.DIFFICULTIES[args.difficulty]
            print(f"[{i + 1}/{args.count}] theme={theme!r}")
            print(f"           region={region!r} grid={spec['grid'][0]}x{spec['grid'][1]} "
                  f"area band={spec['area']} min_visibility={spec['min_visibility']}")
            if i == 0:
                print("\n--- prompt ---")
                print(wo.build_puzzle_prompt(theme, args.difficulty, region))
                print("--- end prompt ---\n")
        print(f"Would upload to s3://{S3_BUCKET_NAME}/{S3_PREFIX}{args.difficulty}/<uuid>.png")
        print(f"Would insert into Mongo collection {MONGO_COLLECTION!r}.")
        print("\nDry run -- no changes made.")
        return 0

    # --- Real run. ---------------------------------------------------------------------
    import anthropic
    import boto3
    from openai import AsyncOpenAI
    from pymongo import MongoClient

    openai_key = os.environ["openai_api_key"]
    anthropic_key = os.environ["ANTHROPIC_API_KEY"]

    path = mascot_path()
    if not os.path.exists(path):
        print(f"❌ Mascot reference missing: {path}")
        print(f"   Download it from s3://{S3_BUCKET_NAME}/private_assets/{MASCOT_FILENAME} "
              f"or add it there first.")
        return 1
    with open(path, "rb") as handle:
        mascot_bytes = handle.read()

    openai_client = AsyncOpenAI(api_key=openai_key)
    vision_client = anthropic.AsyncAnthropic(api_key=anthropic_key)
    edit_fn, generate_fn = build_image_fns(openai_client)

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

    accepted, failed, total_attempts = [], 0, 0
    last_theme = last_region = None

    for i in range(args.count):
        theme = args.theme or wo.pick_theme(rng, exclude=last_theme)
        region = wo.pick_region(rng, exclude=last_region)
        last_theme, last_region = theme, region
        print(f"\n[{i + 1}/{args.count}] {args.difficulty} -- {theme} -- {region}")

        def on_attempt(index, ok, reasons):
            print(f"    attempt {index}: {'accepted' if ok else 'rejected'}"
                  f"{'' if ok else ' -- ' + ', '.join(reasons)}")

        try:
            image_bytes, result, meta = await wo.build_validated_puzzle(
                edit_fn=edit_fn, generate_fn=generate_fn, vision_client=vision_client,
                mascot_bytes=mascot_bytes, theme=theme, difficulty=args.difficulty,
                region=region, max_attempts=args.max_attempts, on_attempt=on_attempt)
        except wo.PuzzleGenerationError as exc:
            failed += 1
            total_attempts += args.max_attempts
            print(f"    ❌ {exc}")
            continue

        total_attempts += meta["attempts"]
        puzzle_id = str(uuid.uuid4())
        s3_key = f"{S3_PREFIX}{args.difficulty}/{puzzle_id}.png"

        s3.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=image_bytes,
                      ContentType="image/png")
        image_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{s3_key}"

        document = build_document(puzzle_id, s3_key, image_url, theme, args.difficulty,
                                  region, result, meta)
        collection.insert_one(document)
        accepted.append(document)

        if args.save_local:
            local = os.path.join(args.save_local, f"{args.difficulty}_{puzzle_id}.png")
            with open(local, "wb") as handle:
                handle.write(image_bytes)

        grid = wo.DIFFICULTIES[args.difficulty]["grid"]
        print(f"    ✅ stored {puzzle_id}")
        print(f"       area={document['area']:.5f} visibility={result.visibility:.2f} "
              f"confidence={result.confidence:.2f} "
              f"cell={wo.target_grid_label(result.target, *grid)}")
        print(f"       {image_url}")

    print(f"\n{len(accepted)} accepted, {failed} failed, {total_attempts} total attempts")
    if total_attempts:
        # Image generation dominates; the locate + crop-check pair adds roughly $0.04.
        print(f"Rough spend: ${total_attempts * 0.21:.2f}")

    for document in accepted[:20]:
        print(f"  {document['_id']}  {document['difficulty']:<7} {document['theme']}")
    if len(accepted) > 20:
        print(f"  ... and {len(accepted) - 20} more")

    if args.save_local and accepted:
        print(f"\n⚠️  Look at the PNGs in {args.save_local} before letting anyone play them.")
        print("   The mascot must read as drawn by the same illustrator as every other")
        print("   character -- no halo, no crisper linework, no clean space around it.")

    counts = {d: collection.count_documents({"difficulty": d}) for d in wo.DIFFICULTY_ORDER}
    print(f"\nPool now holds: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1,
                        help="how many puzzles to accept (default 1)")
    parser.add_argument("--difficulty", default="hard", choices=wo.DIFFICULTY_ORDER)
    parser.add_argument("--theme", default=None,
                        help="force a single theme (default: sampled from wheres_okra.THEMES)")
    parser.add_argument("--max-attempts", type=int, default=4,
                        help="generation attempts before giving up on one puzzle")
    parser.add_argument("--seed", type=int, default=None,
                        help="seed theme/region selection, for reproducible batches")
    parser.add_argument("--save-local", default=None, metavar="DIR",
                        help="also write accepted PNGs to DIR for visual inspection")
    parser.add_argument("--dry-run", action="store_true",
                        help="print prompts and the plan, write nothing, need no credentials")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
