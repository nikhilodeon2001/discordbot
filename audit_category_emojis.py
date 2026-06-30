"""
Audit: find categories actually present in the live question collections that
have no emoji mapping in the category_emojis collection (the source of truth
get_category_title() reads from), accounting for the same colon-prefix
fallback get_category_title() uses (e.g. "Verbal: Foo" falls back to "Verbal").

Usage:
  MONGO_URI=<connection string> python3 audit_category_emojis.py
"""

import os
import sys

from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI") or os.getenv("mongo_db_string")

# Collections the live game actually pulls questions from (see select_trivia_questions()
# and get_random_trivia_question() in discordbot.py). math_questions/stats_questions are
# generated at runtime, not stored, so they're excluded.
QUESTION_COLLECTIONS = [
    "trivia_questions",
    "crossword_questions",
    "jeopardy_questions",
    "sat_questions",
    "wof_questions",
    "mysterybox_questions",
]


def main():
    if not MONGO_URI:
        print("No Mongo URI provided (set MONGO_URI env var).")
        sys.exit(1)

    client = MongoClient(MONGO_URI)
    db = client["triviabot"]

    emoji_docs = list(db.category_emojis.find({}, {"_id": 1}))
    known_categories = {d["_id"] for d in emoji_docs}
    print(f"category_emojis collection has {len(known_categories)} entries\n")

    fully_missing = {}  # category -> [collections it appears in]
    prefix_fallback_only = {}  # category -> (prefix, [collections])

    for col_name in QUESTION_COLLECTIONS:
        try:
            categories = db[col_name].distinct("category")
        except Exception as e:
            print(f"⚠️  Failed to read {col_name}: {e}")
            continue
        print(f"{col_name}: {len(categories)} distinct categories")
        for cat in categories:
            if not cat or not isinstance(cat, str):
                continue
            if cat in known_categories:
                continue
            prefix = cat.split(":")[0].strip()
            if prefix in known_categories:
                prefix_fallback_only.setdefault(cat, (prefix, []))[1].append(col_name)
            else:
                fully_missing.setdefault(cat, []).append(col_name)

    print(f"\n{'='*60}")
    print(f"FULLY MISSING (shows ❓❔ in-game) — {len(fully_missing)} categories:")
    print(f"{'='*60}")
    for cat, cols in sorted(fully_missing.items()):
        print(f"  {cat!r}  (in: {', '.join(cols)})")

    print(f"\n{'='*60}")
    print(f"PREFIX-FALLBACK ONLY (has a generic emoji via prefix, no exact match) — {len(prefix_fallback_only)} categories:")
    print(f"{'='*60}")
    for cat, (prefix, cols) in sorted(prefix_fallback_only.items()):
        print(f"  {cat!r} -> falls back to {prefix!r}  (in: {', '.join(cols)})")

    client.close()


if __name__ == "__main__":
    main()
