"""
Audit: find questions in trivia_questions/jeopardy_questions/crossword_questions
where every acceptable answer is already "given away" by the category/question
text -- i.e. no real guessing is required to answer correctly.

Uses answer_matching.is_fully_given_away: whole-word matching (plus simple
plural/singular drift, e.g. "martins" vs "martin"), deliberately NOT the
looser substring-containment check the live answer matcher uses
(answer_matching._is_giveaway_word). That looser check is the right tradeoff
at answer-check time (a false positive there just makes the game slightly
stricter), but it's the wrong tradeoff here: it flags ordinary English
compounds/suffixes as giveaways just because they share characters with an
unrelated word (e.g. "fish" inside "sailfish", "ability" inside
"malleability", "wave" inside "wavelength") -- noise that would send a human
reviewer chasing questions that aren't actually broken. Whole-word matching
trades some recall (it won't catch e.g. "Tunis" being derivable from a
question naming "Tunisia" -- a real but rarer pattern with no clean way to
tell apart from the compound-word false positives) for much higher precision.

Every significant word of an answer is checked, including short ones (no
4-char floor): skipping short words meant a multi-word answer like "San
Salvador" or "Top Gun: Maverick" could get flagged just because its single
longest word ("Salvador", "Maverick") was given away, without ever verifying
the short, actually-distinguishing words ("San", "Top", "Gun") appeared
anywhere at all.

is_fully_given_away is shared with discordbot.py, which uses the same check to
react to a live guess that parrots the category/question in real time.

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
from answer_matching import _giveaway_words, is_fully_given_away

MONGO_URI = os.environ.get("MONGO_URI") or os.getenv("mongo_db_string")
COLLECTIONS = ["trivia_questions", "jeopardy_questions", "crossword_questions"]


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
            if all(is_fully_given_away(a, giveaway_words) for a in answers):
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
