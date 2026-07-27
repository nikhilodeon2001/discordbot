"""
One-time data-prep script: enrich the Scripps "Words of the Champions" word list
with Merriam-Webster definitions/etymology/pronunciation audio, ready for
seed_spelling_bee.py to load into the spellingbee_questions Mongo collection.

Resumable: results are checkpointed in private-assets/spelling_bee/enriched.json,
keyed by word, so re-running only processes words not yet attempted. The MW
Collegiate Dictionary API's free tier caps at 1000 queries/day, so this is
expected to be run once a day for several days until every word is processed.

Usage:
    python3 mw_enrich_spelling_bee.py [--limit 900] [--tier one_bee]
"""
import argparse
import json
import os
import re
import string
import sys
import time

import boto3
import requests
from dotenv import load_dotenv

load_dotenv()

WEBSTER_API_KEY = os.getenv("webster_api_key")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
S3_BUCKET_NAME = "triviabotwebsite"
S3_AUDIO_PREFIX = "spellingbee_audio/"

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "private-assets", "spelling_bee")
WORDS_PATH = os.path.join(DATA_DIR, "scripps_words.json")
CHECKPOINT_PATH = os.path.join(DATA_DIR, "enriched.json")

MW_TAG_RE = re.compile(r"\{/?[a-z_]+\}")
MW_XREF_RE = re.compile(r"\{[a-z_]+\|([^|}]*)(?:\|[^}]*)?\}")


def clean_mw_text(text):
    """Strip Merriam-Webster's markup tokens, keeping the readable text they wrap."""
    if not text:
        return ""
    text = MW_XREF_RE.sub(r"\1", text)
    text = MW_TAG_RE.sub("", text)
    return text.strip()


def extract_example_sentence(def_block):
    """Walk the nested def -> sseq structure looking for the first verbal illustration."""
    for entry in def_block or []:
        for seq_group in entry.get("sseq", []):
            for sense in seq_group:
                if not isinstance(sense, list) or len(sense) < 2:
                    continue
                sense_data = sense[1]
                if not isinstance(sense_data, dict):
                    continue
                for dt in sense_data.get("dt", []):
                    if dt[0] == "vis":
                        for vis in dt[1]:
                            t = vis.get("t")
                            if t:
                                return clean_mw_text(t)
    return ""


def resolve_audio_url(audio_filename):
    if audio_filename.startswith("bix"):
        subdir = "bix"
    elif audio_filename.startswith("gg"):
        subdir = "gg"
    elif audio_filename[0].isdigit() or audio_filename[0] in string.punctuation:
        subdir = "number"
    else:
        subdir = audio_filename[0].lower()
    return f"https://media.merriam-webster.com/audio/prons/en/us/mp3/{subdir}/{audio_filename}.mp3"


def normalize_headword(hw):
    return re.sub(r"[*]", "", hw or "").lower()


def fetch_mw_entry(word):
    url = f"https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}?key={WEBSTER_API_KEY}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if not data or not isinstance(data[0], dict):
        return None  # MW returned bare suggestion strings -> word not in dictionary

    for entry in data:
        hwi = entry.get("hwi", {})
        if normalize_headword(hwi.get("hw")) == word.lower():
            return entry
    return data[0]  # fall back to first entry if no exact headword match


def enrich_word(word, s3_client):
    entry = fetch_mw_entry(word)
    if entry is None:
        return {"found": False}

    part_of_speech = entry.get("fl", "")

    shortdef = entry.get("shortdef", [])
    definition = clean_mw_text(shortdef[0]) if shortdef else ""

    et_raw = entry.get("et", [])
    etymology = " ".join(clean_mw_text(t[1]) for t in et_raw if t[0] == "text").strip()

    example_sentence = extract_example_sentence(entry.get("def", []))

    pronunciation_url = None
    prs = entry.get("hwi", {}).get("prs", [])
    if prs:
        audio = prs[0].get("sound", {}).get("audio")
        if audio:
            mw_url = resolve_audio_url(audio)
            try:
                audio_resp = requests.get(mw_url, timeout=15)
                if audio_resp.status_code == 200:
                    key = f"{S3_AUDIO_PREFIX}{word.lower()}.mp3"
                    s3_client.put_object(
                        Bucket=S3_BUCKET_NAME,
                        Key=key,
                        Body=audio_resp.content,
                        ContentType="audio/mpeg",
                    )
                    pronunciation_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{key}"
            except requests.RequestException as e:
                print(f"  audio download/upload failed for {word}: {e}")

    return {
        "found": True,
        "definition": definition,
        "part_of_speech": part_of_speech,
        "example_sentence": example_sentence,
        "etymology": etymology,
        "pronunciation_url": pronunciation_url,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=900, help="Max new MW API calls this run")
    parser.add_argument("--tier", default=None, help="Only process this tier (one_bee/two_bee/three_bee/championship)")
    args = parser.parse_args()

    if not WEBSTER_API_KEY:
        print("Missing webster_api_key in .env")
        sys.exit(1)

    with open(WORDS_PATH, encoding="utf-8") as f:
        words_by_tier = json.load(f)

    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, encoding="utf-8") as f:
            checkpoint = json.load(f)
    else:
        checkpoint = {}

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )

    tiers = [args.tier] if args.tier else list(words_by_tier.keys())
    calls_made = 0

    for tier in tiers:
        for word in words_by_tier.get(tier, []):
            if calls_made >= args.limit:
                break
            if word in checkpoint:
                continue

            try:
                result = enrich_word(word, s3_client)
                result["tier"] = tier
                checkpoint[word] = result
                calls_made += 1
                status = "OK" if result["found"] else "NOT FOUND"
                print(f"[{calls_made}/{args.limit}] {tier}: {word} -> {status}")
            except requests.RequestException as e:
                print(f"  API error for {word}: {e} (will retry next run)")

            time.sleep(0.4)

            if calls_made % 50 == 0:
                with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
                    json.dump(checkpoint, f, indent=2)
        if calls_made >= args.limit:
            break

    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=2)

    total_words = sum(len(v) for v in words_by_tier.values())
    print(f"\nDone this run: {calls_made} words processed.")
    print(f"Checkpoint total: {len(checkpoint)}/{total_words} words across all tiers.")


if __name__ == "__main__":
    main()
