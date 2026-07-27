"""
One-time follow-up to mw_enrich_spelling_bee.py: retry words Merriam-Webster's free
Collegiate API couldn't find (it only covers ~225k entries; Scripps actually draws
from the larger paid Unabridged dictionary, so some harder words fall outside it).

Uses the free, keyless dictionaryapi.dev (Wiktionary-backed) as a fallback source.
It has no etymology and rarely has audio, but does recover definitions/part of
speech for a large share of these words -- and the game already handles missing
etymology/example_sentence/pronunciation_url gracefully.

Usage:
    python3 retry_not_found_spelling_bee.py
"""
import json
import os
import time

import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "private-assets", "spelling_bee")
CHECKPOINT_PATH = os.path.join(DATA_DIR, "enriched.json")


def fetch_fallback(word):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if not isinstance(data, list) or not data:
        return None

    entry = data[0]
    meanings = entry.get("meanings", [])
    if not meanings:
        return None

    part_of_speech = meanings[0].get("partOfSpeech", "")
    definitions = meanings[0].get("definitions", [])
    definition = definitions[0].get("definition", "") if definitions else ""
    example_sentence = definitions[0].get("example", "") if definitions else ""

    pronunciation_url = None
    for phon in entry.get("phonetics", []):
        if phon.get("audio"):
            pronunciation_url = phon["audio"]
            break

    if not definition:
        return None

    return {
        "found": True,
        "definition": definition,
        "part_of_speech": part_of_speech,
        "example_sentence": example_sentence,
        "etymology": "",
        "pronunciation_url": pronunciation_url,
        "source": "dictionaryapi.dev",
    }


def main():
    with open(CHECKPOINT_PATH, encoding="utf-8") as f:
        checkpoint = json.load(f)

    not_found_words = [w for w, v in checkpoint.items() if not v.get("found")]
    print(f"Retrying {len(not_found_words)} words not found in MW...")

    recovered = 0
    for i, word in enumerate(not_found_words, start=1):
        tier = checkpoint[word].get("tier", "")
        try:
            result = fetch_fallback(word)
        except requests.RequestException as e:
            print(f"[{i}/{len(not_found_words)}] {word} -> error: {e}")
            continue

        if result:
            result["tier"] = tier
            checkpoint[word] = result
            recovered += 1
            print(f"[{i}/{len(not_found_words)}] {word} -> RECOVERED")
        else:
            print(f"[{i}/{len(not_found_words)}] {word} -> still not found")

        time.sleep(0.2)

        if i % 50 == 0:
            with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
                json.dump(checkpoint, f, indent=2)

    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=2)

    still_missing = len(not_found_words) - recovered
    print(f"\nRecovered {recovered}/{len(not_found_words)} words via dictionaryapi.dev.")
    print(f"Still missing: {still_missing}")


if __name__ == "__main__":
    main()
