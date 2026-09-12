"""
Audit: find questions in trivia_questions/jeopardy_questions/crossword_questions
where every acceptable answer is already "given away" by the category/question
text -- i.e. no real guessing is required to answer correctly.

Uses whole-word matching (plus simple plural/singular drift, e.g. "martins" vs
"martin"), deliberately NOT the looser substring-containment check the live
answer matcher uses (answer_matching._is_giveaway_word). That looser check is
the right tradeoff at answer-check time (a false positive there just makes the
game slightly stricter), but it's the wrong tradeoff here: it flags ordinary
English compounds/suffixes as giveaways just because they share characters
with an unrelated word (e.g. "fish" inside "sailfish", "ability" inside
"malleability", "wave" inside "wavelength") -- noise that would send a human
reviewer chasing questions that aren't actually broken. Whole-word matching
trades some recall (it won't catch e.g. "Tunis" being derivable from a
question naming "Tunisia" -- a real but rarer pattern with no clean way to
tell apart from the compound-word false positives) for much higher precision.

Read-only. Makes no database writes.

Usage:
  mongo_db_string="$(heroku config:get mongo_db_string -a discordtriviabot)" \\
      python3 audit_giveaway_questions.py [--out report.md]
"""
import argparse
import os
import sys
from datetime import datetime, timezone

from pymongo import MongoClient
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from answer_matching import _giveaway_words, _significant_tokens, normalize_text

MONGO_URI = os.environ.get("MONGO_URI") or os.getenv("mongo_db_string")
COLLECTIONS = ["trivia_questions", "jeopardy_questions", "crossword_questions"]


def _singularize(word):
    """Strip a simple trailing plural 's'/'es' -- just enough to bridge cases
    like 'martins' vs 'martin', not a full morphological analyzer."""
    if len(word) > 4 and word.endswith("es"):
        return word[:-2]
    if len(word) > 4 and word.endswith("s"):
        return word[:-1]
    return word


def is_whole_word_giveaway(word, giveaway_words):
    """Whole-word match (plus simple plural/singular drift) -- see module
    docstring for why this is stricter than answer_matching._is_giveaway_word."""
    if len(word) < 4:
        return False
    word_singular = _singularize(word)
    for gw in giveaway_words:
        if len(gw) < 4:
            continue
        if word == gw or word_singular == _singularize(gw):
            return True
    return False


def answer_is_given_away(answer, giveaway_words):
    sig = [w for w in _significant_tokens(normalize_text(answer)) if len(w) >= 4]
    if not sig:
        return False  # no checkable words -- don't flag on a vacuous match
    return all(is_whole_word_giveaway(w, giveaway_words) for w in sig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None, help="Markdown report path (default: auto-named with timestamp)")
    args = parser.parse_args()

    if not MONGO_URI:
        print("No Mongo URI provided (set mongo_db_string or MONGO_URI env var).")
        sys.exit(1)

    client = MongoClient(MONGO_URI)
    db = client["triviabot"]

    flagged = []  # (collection, _id, category, question, answers)
    for col_name in COLLECTIONS:
        col = db[col_name]
        total = col.count_documents({})
        col_flagged = 0
        cursor = col.find({}, {"category": 1, "question": 1, "answers": 1})
        for doc in tqdm(cursor, total=total, desc=col_name, unit="doc"):
            answers = doc.get("answers") or []
            category = doc.get("category") or ""
            question = doc.get("question") or ""
            if not answers or not (category or question):
                continue
            giveaway_words = _giveaway_words(category, question)
            if all(answer_is_given_away(a, giveaway_words) for a in answers):
                flagged.append((col_name, doc["_id"], category, question, answers))
                col_flagged += 1
        print(f"{col_name}: {total} documents checked, {col_flagged} flagged")

    client.close()

    print(f"\n{len(flagged)} questions flagged total")

    out_path = args.out or f"giveaway_questions_report_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.md"
    with open(out_path, "w") as f:
        f.write(f"# Giveaway-question audit ({datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC})\n\n")
        f.write(f"{len(flagged)} questions flagged across {', '.join(COLLECTIONS)}.\n\n")
        for col_name, _id, category, question, answers in flagged:
            f.write(f"## {col_name} / `{_id}`\n\n")
            f.write(f"- **Category:** {category}\n")
            f.write(f"- **Question:** {question}\n")
            f.write(f"- **Answers:** {', '.join(answers)}\n\n")
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()
