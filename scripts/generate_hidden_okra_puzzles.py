"""One-time seed script: generate validated hidden-object puzzles for Where's Okra and
store them in S3 (the image) plus Mongo (the secret answer box).

Two pipelines, both in wheres_okra.py (--pipeline, default "hybrid"):

  hybrid (default): a mascot-free background is generated first, then the mascot is drawn
  into a masked region at a position WE choose (see build_validated_puzzle_hybrid). Built
  after the single-call pipeline's real generated samples showed a reliable failure mode:
  one call asked to solve placement, rendering and style-matching together for a heavily
  described character kept making that character the centred, full-height visual hero
  instead of a hidden background figure. Splitting the work into a plain background call
  plus a narrower "draw this character HERE" edit fixed that. Per-attempt cost and success
  rate have not been measured over a real batch yet -- this is what the first live runs
  are for; don't trust a guessed number for it.

  single (build_validated_puzzle): the original one-call full-scene redraw with the mascot
  as an identity reference, retried with a text-only fallback on repeated oversizing.
  Kept available for comparison via --pipeline single. Measured at ~$0.21/attempt,
  roughly $0.40/accepted puzzle, but with a much higher observed rejection rate in
  practice than that alone suggests -- see the samples that motivated the hybrid pipeline.

Either way, every attempt is located by a vision pass over the finished pixels (never the
generator's own claims about placement) and cross-checked against a crop of that location
before being trusted -- see wheres_okra.py's module docstring for why.

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


def build_hybrid_image_fns(openai_client):
    """Bind the hybrid pipeline's two OpenAI calls (see
    wo.build_validated_puzzle_hybrid): a plain background generation with no reference
    image and no mask, and a masked local edit that draws the mascot into that background
    only within the region the mask marks transparent/editable."""
    async def background_fn(prompt):
        response = await openai_client.images.generate(
            model=wo.BACKGROUND_IMAGE_MODEL,
            prompt=prompt,
            size="1024x1024",
            quality=wo.BACKGROUND_IMAGE_QUALITY,
        )
        return base64.b64decode(response.data[0].b64_json)

    async def insert_fn(background_bytes, mask_bytes, prompt):
        response = await openai_client.images.edit(
            model=wo.INSERTION_IMAGE_MODEL,
            image=("background.png", background_bytes, "image/png"),
            mask=("mask.png", mask_bytes, "image/png"),
            prompt=prompt,
            size="1024x1024",
            quality=wo.INSERTION_IMAGE_QUALITY,
        )
        return base64.b64decode(response.data[0].b64_json)

    return background_fn, insert_fn


def build_document(puzzle_id, s3_key, image_url, theme, difficulty, region, result, meta):
    """The stored puzzle. `target` is the secret and never leaves the server -- see the
    integrity note in wheres_okra.py and the game loop in discordbot.py.

    Shared between both pipelines; the hybrid-only meta keys (background_model/quality/
    prompt) are added only when present rather than assumed, since build_validated_puzzle
    (the single-call pipeline) never sets them.
    """
    box = wo.normalize_target(result.target)
    document = {
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
        "pipeline": meta.get("pipeline", "single"),
        "image_model": meta["image_model"],
        "image_quality": meta["image_quality"],
        "vision_model": meta["vision_model"],
        "verify_model": meta["verify_model"],
        "verify_confidence": meta["verify_confidence"],
        "prompt": meta["prompt"],
    }
    if "background_model" in meta:
        document["background_model"] = meta["background_model"]
        document["background_quality"] = meta["background_quality"]
        document["background_prompt"] = meta["background_prompt"]
    return document


async def run(args):
    rng = wo.make_rng(args.seed)

    # --- Dry run: no credentials, no network, no writes. -------------------------------
    if args.dry_run:
        print(f"Dry run [{args.pipeline}]: would generate {args.count} "
              f"'{args.difficulty}' puzzle(s).\n")
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
                if args.pipeline == "hybrid":
                    print("\n--- background prompt (no mascot mentioned) ---")
                    print(wo.build_background_prompt(theme, args.difficulty))
                    print("--- end background prompt ---\n")
                    print("--- insertion prompt (masked local edit) ---")
                    print(wo.build_insertion_prompt(args.difficulty))
                    print("--- end insertion prompt ---\n")
                    region_index = wo.REGIONS.index(region)
                    box = wo.pick_target_box(args.difficulty, region_index, wo.make_rng())
                    print(f"example chosen target box: {tuple(round(v, 4) for v in box)}\n")
                else:
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
    background_fn, insert_fn = build_hybrid_image_fns(openai_client)

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
            if args.pipeline == "hybrid":
                image_bytes, result, meta = await wo.build_validated_puzzle_hybrid(
                    background_fn=background_fn, insert_fn=insert_fn,
                    vision_client=vision_client, mascot_bytes=mascot_bytes, theme=theme,
                    difficulty=args.difficulty, region=region,
                    max_attempts=args.max_attempts, on_attempt=on_attempt,
                    save_attempts_dir=args.save_rejected)
            else:
                image_bytes, result, meta = await wo.build_validated_puzzle(
                    edit_fn=edit_fn, generate_fn=generate_fn, vision_client=vision_client,
                    mascot_bytes=mascot_bytes, theme=theme, difficulty=args.difficulty,
                    region=region, max_attempts=args.max_attempts, on_attempt=on_attempt,
                    save_attempts_dir=args.save_rejected)
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
        if args.pipeline == "single":
            # Image generation dominates; the locate + crop-check pair adds roughly $0.04.
            print(f"Rough spend: ${total_attempts * 0.21:.2f} (measured -- see wheres_okra.py)")
        else:
            print(f"{total_attempts} insertion attempts across {len(accepted) + failed} "
                  f"background(s) -- exact hybrid pricing is not yet measured over a real "
                  f"batch, check actual OpenAI/Anthropic usage after this run rather than "
                  f"trust a guessed number here.")

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
    parser.add_argument("--pipeline", default="hybrid", choices=["hybrid", "single"],
                        help="'hybrid' (default): mascot-free background + a targeted "
                             "masked edit at a position we choose. 'single': the original "
                             "one-call full-scene redraw (build_validated_puzzle) -- kept "
                             "available for comparison, not the current default.")
    parser.add_argument("--difficulty", default="hard", choices=wo.DIFFICULTY_ORDER)
    parser.add_argument("--theme", default=None,
                        help="force a single theme (default: sampled from wheres_okra.THEMES)")
    parser.add_argument("--max-attempts", type=int, default=4,
                        help="generation attempts before giving up on one puzzle")
    parser.add_argument("--seed", type=int, default=None,
                        help="seed theme/region selection, for reproducible batches")
    parser.add_argument("--save-local", default=None, metavar="DIR",
                        help="also write accepted PNGs to DIR for visual inspection")
    parser.add_argument("--save-rejected", default=None, metavar="DIR",
                        help="write EVERY generated attempt to DIR, accepted or rejected -- "
                             "for diagnosing why attempts keep failing, not routine use")
    parser.add_argument("--dry-run", action="store_true",
                        help="print prompts and the plan, write nothing, need no credentials")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
