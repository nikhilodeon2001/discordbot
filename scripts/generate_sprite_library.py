"""One-time/occasional seed script: generate decoy sprites for Where's Okra's
sprite-compositing pipeline (wheres_okra.compose_sprite_puzzle) and store them in S3 (the
image) plus Mongo (the metadata the compositor needs -- theme, tags, scale_class).

This replaced the earlier AI full-scene-generation pipelines (see
scripts/generate_hidden_okra_puzzles.py, kept for comparison but no longer the default) --
those asked one model call to solve placement, scale, and style-matching simultaneously for
one described character, and never reliably succeeded across five live test batches. This
script asks a much narrower question per call: draw ONE isolated object in a given style,
with a transparent background. There's no placement to get wrong and nothing to validate
afterward -- a sprite either looks right on review, or it's discarded; the compositor
places it deterministically, not this script.

One OpenAI call per sprite (no retry loop, no vision-based validation) -- a deliberate
choice over a sprite-sheet-and-slice approach that would need reliable alpha-based
segmentation this codebase has no precedent or dependency for. See the plan's "Deliberate
choice, not an oversight" note if you're revisiting this later at real scale.

Style consistency across a batch comes from using images.edit with the mascot
(okra_pod.png -- a PLAIN okra pod, not the anthropomorphised okra_chef.png character used
by the legacy AI pipeline) as a STYLE reference -- "draw this subject in the same
illustration style as the reference image" -- so decoys visually belong next to the
mascot they need to blend among. The mascot itself has no character traits (no face, no
gloves), so the prompt says explicitly that decoys shouldn't either -- matching a
reference's rendering style doesn't automatically avoid or add personification either
way; both need to be said out loud (see build_sprite_prompt's docstring).

Sprites are described via a JSON spec file, one entry per sprite:
    [
      {"subject": "a whole cucumber", "tags": ["green", "tall"], "scale_class": "small_prop"},
      {"subject": "a head of broccoli", "tags": ["green", "round"], "scale_class": "small_prop"}
    ]
`tags` drive the compositor's camouflage bias (see MASCOT_CAMOUFLAGE_TAGS in
wheres_okra.py -- "green", "tall" are the mascot's own, so decoys sharing those make
harder difficulties genuinely harder to spot, not just busier). `scale_class` is one
of "small_prop" | "person_sized" | "large_object" (wheres_okra.SCALE_CLASS_HEIGHT_FRACTION)
-- gives sprites bootstrapped in separate sessions a shared, principled size convention
instead of each being scaled arbitrarily.

Usage:
    # Staging first, and always look at what a dry run intends to do.
    openai_api_key=... \\
        mongo_db_string="$(heroku config:get mongo_db_string -a discordbot-staging)" \\
        AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=us-east-2 \\
        python3 scripts/generate_sprite_library.py --theme beach --spec beach_sprites.json --dry-run

    openai_api_key=... \\
        mongo_db_string="$(heroku config:get mongo_db_string -a discordbot-staging)" \\
        AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=us-east-2 \\
        python3 scripts/generate_sprite_library.py --theme beach --spec beach_sprites.json --save-local /tmp/beach_sprites

    # Then prod, once the staging sprites have been eyeballed.
    ... mongo_db_string="$(heroku config:get mongo_db_string -a discordtriviabot)" ...

--dry-run prints the prompts and the plan and writes nothing, and needs no credentials at
all: no OpenAI key, no AWS, no Mongo. Use it to review prompt wording and the spec file
before spending anything.

--save-local writes every generated PNG next to the run so they can be reviewed before
they enter the live game. Strongly recommended for the first batch of any new theme: no
automated check can tell you "these decoys don't actually feel like the same theme," or
whether a decoy quietly doesn't match the mascot's style -- only a look can.
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

import wheres_okra as wo  # noqa: E402

S3_BUCKET_NAME = "triviabotwebsite"
S3_PREFIX = "hidden_okra_sprites/"
S3_REGION = "us-east-2"
MONGO_COLLECTION = "hidden_okra_sprites"
VALID_SCALE_CLASSES = set(wo.SCALE_CLASS_HEIGHT_FRACTION)

MASCOT_FILENAME = "okra_pod.png"
SPRITE_IMAGE_MODEL = "gpt-image-1"
SPRITE_IMAGE_QUALITY = "high"


def mascot_path():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "private-assets", MASCOT_FILENAME)


def build_sprite_prompt(subject):
    """The one prompt this script sends per sprite. The mascot (okra_pod.png) is a plain
    vegetable, not a character -- no face, no gloves, no personality -- so decoys need to
    match it as plain rendered objects too, explicitly, not just in rendering style. An
    earlier direction for this game DID personify the mascot (see MASCOT_FILENAME's
    history / wheres_okra.py's legacy AI pipeline, which still uses okra_chef.png); this
    prompt is deliberately the opposite of that -- say "no character traits" out loud
    rather than assume matching the reference's style alone will avoid them, the same way
    the personified version needed to say "give it a face" out loud rather than assume
    style-matching alone would add one."""
    return (
        f"A single isolated illustration of {subject}, drawn in the exact same "
        f"illustration style as the reference image -- matching its line quality, line "
        f"weight, outline treatment, shading, texture, and colour saturation exactly, as "
        f"if the same illustrator drew both. A plain vegetable/plant, not a character: no "
        f"face, no eyes, no gloves, no limbs, no personality -- just the plant itself, the "
        f"same way the reference image is just a plain vegetable with no character traits. "
        f"The subject fills most of the frame, centred, fully visible, with nothing "
        f"cropped off. Background is fully transparent -- no scene, no shadow, no ground "
        f"plane, no other objects, no text."
    )


def load_spec(path):
    with open(os.path.expanduser(path), encoding="utf-8") as f:
        spec = json.load(f)
    if not isinstance(spec, list) or not spec:
        raise ValueError(f"{path} must contain a non-empty JSON array")
    for i, entry in enumerate(spec):
        if "subject" not in entry:
            raise ValueError(f"spec entry {i} is missing required key 'subject'")
        scale_class = entry.get("scale_class", wo.DEFAULT_SCALE_CLASS)
        if scale_class not in VALID_SCALE_CLASSES:
            raise ValueError(
                f"spec entry {i} ('{entry['subject']}'): scale_class {scale_class!r} "
                f"must be one of {sorted(VALID_SCALE_CLASSES)}")
        entry["scale_class"] = scale_class
        entry.setdefault("tags", [])
    return spec


async def run(args):
    spec = load_spec(args.spec)
    if args.limit:
        spec = spec[:args.limit]

    # --- Dry run: no credentials, no network, no writes. -------------------------------
    if args.dry_run:
        print(f"Dry run: would generate {len(spec)} sprite(s) for theme {args.theme!r}.\n")
        for i, entry in enumerate(spec):
            print(f"[{i + 1}/{len(spec)}] subject={entry['subject']!r}")
            print(f"           tags={entry['tags']} scale_class={entry['scale_class']}")
            if i == 0:
                print("\n--- prompt ---")
                print(build_sprite_prompt(entry["subject"]))
                print("--- end prompt ---\n")
        print(f"Would upload to s3://{S3_BUCKET_NAME}/{S3_PREFIX}{args.theme}/<uuid>.png")
        print(f"Would insert into Mongo collection {MONGO_COLLECTION!r}.")
        print("\nDry run -- no changes made.")
        return 0

    # --- Real run. ---------------------------------------------------------------------
    import boto3
    from openai import AsyncOpenAI
    from pymongo import MongoClient

    openai_key = os.environ["openai_api_key"]

    path = mascot_path()
    if not os.path.exists(path):
        print(f"❌ Mascot reference missing: {path}")
        print(f"   Download it from s3://{S3_BUCKET_NAME}/private_assets/{MASCOT_FILENAME} "
              f"or add it there first.")
        return 1
    with open(path, "rb") as handle:
        mascot_bytes = handle.read()

    openai_client = AsyncOpenAI(api_key=openai_key)
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
        subject = entry["subject"]
        print(f"\n[{i + 1}/{len(spec)}] {subject}")
        prompt = build_sprite_prompt(subject)
        try:
            response = await openai_client.images.edit(
                model=SPRITE_IMAGE_MODEL,
                image=(MASCOT_FILENAME, mascot_bytes, "image/png"),
                prompt=prompt,
                size="1024x1024",
                quality=SPRITE_IMAGE_QUALITY,
                background="transparent",
                # NOTE: images.edit has no output_format parameter (unlike
                # images.generate, which does) -- confirmed against the installed SDK's
                # AsyncImages.edit signature. gpt-image-1's edit endpoint returns PNG by
                # default when background="transparent" is set, which is what alpha
                # transparency requires anyway.
            )
            image_bytes = base64.b64decode(response.data[0].b64_json)
        except Exception as exc:  # noqa: BLE001 -- one bad sprite shouldn't end the run
            failed += 1
            print(f"    ❌ generation failed: {exc}")
            continue

        sprite_id = str(uuid.uuid4())
        s3_key = f"{S3_PREFIX}{args.theme}/{sprite_id}.png"
        s3.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=image_bytes,
                      ContentType="image/png")
        image_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{s3_key}"

        document = {
            "_id": sprite_id,
            "theme": args.theme,
            "s3_key": s3_key,
            "image_url": image_url,
            "tags": entry["tags"],
            "scale_class": entry["scale_class"],
            "source": "ai",
            "subject": subject,
            "prompt": prompt,
            "added_at": datetime.datetime.utcnow(),
        }
        collection.insert_one(document)
        accepted.append(document)

        if args.save_local:
            local = os.path.join(args.save_local, f"{sprite_id}.png")
            with open(local, "wb") as handle:
                handle.write(image_bytes)

        print(f"    ✅ stored {sprite_id}  tags={entry['tags']} scale_class={entry['scale_class']}")
        print(f"       {image_url}")

    print(f"\n{len(accepted)} accepted, {failed} failed")
    for document in accepted[:20]:
        print(f"  {document['_id']}  {document['theme']:<10} {document['subject']}")
    if len(accepted) > 20:
        print(f"  ... and {len(accepted) - 20} more")

    if args.save_local and accepted:
        print(f"\n⚠️  Look at the PNGs in {args.save_local} before letting anyone play them.")
        print("   Every sprite must look drawn by the same illustrator as the mascot and")
        print("   every other sprite in this theme -- check for style drift across the batch,")
        print("   not just against the reference.")

    total = collection.count_documents({"theme": args.theme})
    print(f"\nTheme {args.theme!r} now holds {total} sprite(s).")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", required=True)
    parser.add_argument("--spec", required=True, metavar="FILE",
                        help="JSON file: a list of {subject, tags, scale_class} entries")
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
