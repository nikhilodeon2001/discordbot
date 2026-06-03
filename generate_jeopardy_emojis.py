"""
One-time script to generate emoji pairs for all jeopardy categories not yet in
category_emojis.py. Calls the Claude API in batches of 100 categories per request
and incrementally saves results to category_emojis.py after every batch.

Usage:
    ANTHROPIC_API_KEY=$(heroku config:get ANTHROPIC_API_KEY --app discordtriviabot) \
        python3 generate_jeopardy_emojis.py

Re-running is safe — already-mapped categories are skipped automatically.
"""

import csv
import sys
import time
from pathlib import Path

import anthropic

JEOPARDY_CSV = Path(__file__).parent.parent.parent / "Desktop/questions/categories/jeopardy_categories.csv"
EMOJIS_FILE = Path(__file__).parent / "category_emojis.py"
BATCH_SIZE = 100
MODEL = "claude-haiku-4-5-20251001"


def load_existing_categories() -> set[str]:
    namespace: dict = {}
    exec(EMOJIS_FILE.read_text(encoding="utf-8"), namespace)
    return set(namespace["CATEGORY_EMOJIS"].keys())


def load_jeopardy_categories() -> list[str]:
    categories: list[str] = []
    seen: set[str] = set()
    with open(JEOPARDY_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat = row.get("_id", "").strip()
            if cat and cat not in seen:
                seen.add(cat)
                categories.append(cat)
    return categories


def build_prompt(batch: list[str]) -> str:
    """Numbered list prompt — Claude responds with index + emojis only, no echoing."""
    lines = "\n".join(f"{i+1}. {cat}" for i, cat in enumerate(batch))
    return (
        "You are an emoji curator for a trivia game. For each numbered Jeopardy! category below, "
        "respond with exactly one line per category in the format:\n"
        "N. 🎯🔥\n\n"
        "Rules:\n"
        "- Exactly 2 emojis per line, nothing else\n"
        "- Keep the same number as the input\n"
        "- No extra text, explanations, or blank lines\n"
        "- You MUST respond for every single category — even punctuation marks, symbols, or "
        "categories that seem weird. Pick the 2 most fitting emojis you can. Never skip a line.\n\n"
        f"Categories:\n{lines}"
    )


def parse_response(text: str, batch: list[str]) -> dict[str, str]:
    """Parse indexed response lines back to {category: emojis} using position."""
    result: dict[str, str] = {}
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Expect "N. 🎯🔥"
        dot = line.find(". ")
        if dot == -1:
            continue
        try:
            idx = int(line[:dot]) - 1
        except ValueError:
            continue
        if idx < 0 or idx >= len(batch):
            continue
        emojis = line[dot + 2:].strip()
        if emojis:
            result[batch[idx]] = emojis
    return result


def append_to_emojis_file(new_entries: dict[str, str]) -> None:
    """Append new category→emoji entries to category_emojis.py before the closing }."""
    content = EMOJIS_FILE.read_text(encoding="utf-8")
    insert_pos = content.rfind("\n}")
    if insert_pos == -1:
        print("ERROR: could not find closing } in category_emojis.py", file=sys.stderr)
        sys.exit(1)
    lines = []
    for cat, emojis in sorted(new_entries.items()):
        escaped_cat = cat.replace("\\", "\\\\").replace('"', '\\"')
        escaped_emojis = emojis.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'    "{escaped_cat}": "{escaped_emojis}",')
    new_block = "\n" + "\n".join(lines)
    new_content = content[:insert_pos] + new_block + content[insert_pos:]
    EMOJIS_FILE.write_text(new_content, encoding="utf-8")


def main() -> None:
    client = anthropic.Anthropic()

    print("Loading existing categories...", flush=True)
    existing = load_existing_categories()
    print(f"  {len(existing)} categories already mapped", flush=True)

    print("Loading jeopardy categories...", flush=True)
    all_jeopardy = load_jeopardy_categories()
    missing = [c for c in all_jeopardy if c not in existing]
    print(f"  {len(all_jeopardy)} total jeopardy categories", flush=True)
    print(f"  {len(missing)} need emoji assignments\n", flush=True)

    if not missing:
        print("Nothing to do — all jeopardy categories are already mapped.")
        return

    total_batches = (len(missing) + BATCH_SIZE - 1) // BATCH_SIZE
    total_written = 0
    total_failed = 0

    for i in range(0, len(missing), BATCH_SIZE):
        batch = missing[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} categories)... ", end="", flush=True)

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": build_prompt(batch)}],
            )
            parsed = parse_response(response.content[0].text, batch)
            unparsed_count = len(batch) - len(parsed)

            if parsed:
                append_to_emojis_file(parsed)
                total_written += len(parsed)

            total_failed += unparsed_count
            print(f"✓ {len(parsed)}/{len(batch)}" + (f"  ({unparsed_count} unparsed)" if unparsed_count else ""), flush=True)

        except Exception as e:
            print(f"✗ FAILED: {e}", flush=True)
            total_failed += len(batch)

        time.sleep(0.3)

    print(f"\nDone. {total_written} new entries written, {total_failed} unparsed.")
    if total_failed:
        print("Re-run the script to retry any unparsed categories.")


if __name__ == "__main__":
    main()
