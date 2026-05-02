"""
Review flagged trivia questions using Claude AI.

Mode 1 — analyze:
  python review_flagged.py --mode 1 [--output flagged_review.json]

Mode 2 — apply:
  python review_flagged.py --mode 2 --input flagged_review.json
"""

import argparse
import json
import os
import sys
import time

import anthropic
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("mongo_db_string")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-opus-4-7"
COLLECTIONS = [
    "trivia_questions",
    "mysterybox_questions",
    "crossword_questions",
    "jeopardy_questions",
]

SYSTEM_PROMPT = """You are a trivia question quality reviewer. You will be given a trivia question with user-submitted flag reports, and you must decide whether the question needs to be updated.

ANSWER ARRAY RULES:
- For multiple choice questions (url = "multiple choice", "multiple choice opentrivia", or "multiple choice oracle"):
  - answers[0] = the correct answer letter (A, B, C, D, True, or False)
  - answers[1:] = the labeled choices shown to players (e.g. "A) Paris", "B) London")
  - To fix a wrong answer, update answers[0] to the correct letter
- For free-text questions:
  - answers[0] = the primary correct answer
  - answers[1:] = accepted alternate answers

YOUR TASK:
1. Analyze the question, category, answers, and all user flag comments
2. Decide: does the question need to be updated, or is it fine as-is?
3. Return ONLY a JSON object with this exact structure:

{
  "ai_action": "no_change" | "update",
  "ai_reasoning": "Brief explanation of your decision",
  "proposed_changes": {
    "category": "new category if needed",
    "question": "new question text if needed",
    "answers": ["new", "answers", "array", "if", "needed"]
  }
}

IMPORTANT:
- Only include keys in proposed_changes for fields that actually need to change
- If ai_action is "no_change", proposed_changes must be {}
- If a user flag is incorrect or the question is already right, set ai_action to "no_change"
- Be conservative — only update if the flag is clearly correct
- Return valid JSON only, no markdown, no explanation outside the JSON"""


def is_multiple_choice(url):
    return url in {"multiple choice", "multiple choice opentrivia", "multiple choice oracle"}


def format_question_for_claude(doc):
    url = doc.get("url", "")
    answers = doc.get("answers", [])
    question_type = "multiple choice" if is_multiple_choice(url) else "free-text"

    lines = [
        f"CATEGORY: {doc.get('category', 'N/A')}",
        f"QUESTION: {doc.get('question', 'N/A')}",
        f"QUESTION TYPE: {question_type}",
    ]

    if is_multiple_choice(url):
        lines.append(f"CORRECT ANSWER LETTER: {answers[0] if answers else 'N/A'}")
        if len(answers) > 1:
            lines.append("ANSWER CHOICES:")
            for choice in answers[1:]:
                lines.append(f"  {choice}")
    else:
        lines.append(f"CORRECT ANSWER: {answers[0] if answers else 'N/A'}")
        if len(answers) > 1:
            lines.append(f"ALTERNATE ANSWERS: {', '.join(answers[1:])}")

    lines.append("\nUSER FLAG REPORTS:")
    for entry in doc.get("audit", []):
        name = entry.get("display_name", "Unknown")
        comment = entry.get("message_content", "")
        lines.append(f"  [{name}]: {comment}")

    return "\n".join(lines)


def analyze_document(client, doc, index, total):
    user_content = format_question_for_claude(doc)
    print(f"  [{index}/{total}] Analyzing: {doc.get('question', '')[:60]}...")

    for attempt in range(2):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_content}],
            )
            raw = response.content[0].text.strip()
            result = json.loads(raw)
            return result
        except json.JSONDecodeError:
            if attempt == 0:
                time.sleep(1)
                continue
            print(f"    ⚠️  JSON parse failed, skipping")
            return {"ai_action": "no_change", "ai_reasoning": "Parse error", "proposed_changes": {}}
        except Exception as e:
            print(f"    ⚠️  API error: {e}")
            return {"ai_action": "no_change", "ai_reasoning": f"API error: {e}", "proposed_changes": {}}


def mode1_analyze(output_path):
    mongo = MongoClient(MONGO_URI)
    db = mongo["triviabot"]
    ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    all_docs = []
    for col_name in COLLECTIONS:
        docs = list(db[col_name].find({"audit": {"$exists": True, "$ne": []}}))
        for doc in docs:
            doc["_collection"] = col_name
        all_docs.extend(docs)
        print(f"  {col_name}: {len(docs)} flagged documents")

    mongo.close()

    total = len(all_docs)
    print(f"\nTotal: {total} documents to analyze\n")

    results = []
    for i, doc in enumerate(all_docs, 1):
        if doc.get("url") == "scramble":
            print(f"  [{i}/{total}] Skipping scramble question (runtime-generated)")
            analysis = {
                "ai_action": "no_change",
                "ai_reasoning": "Scramble questions are generated at runtime — skipping.",
                "proposed_changes": {},
            }
        else:
            analysis = analyze_document(ai, doc, i, total)

        entry = {
            "collection": doc["_collection"],
            "id": str(doc["_id"]),
            "category": doc.get("category", ""),
            "question": doc.get("question", ""),
            "url": doc.get("url", ""),
            "answers": doc.get("answers", []),
            "audit": doc.get("audit", []),
            "ai_action": analysis.get("ai_action", "no_change"),
            "ai_reasoning": analysis.get("ai_reasoning", ""),
            "proposed_changes": analysis.get("proposed_changes", {}),
        }
        results.append(entry)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    updates = sum(1 for r in results if r["ai_action"] == "update")
    print(f"\n✅ Analysis complete.")
    print(f"   {updates}/{total} questions flagged for update")
    print(f"   Output written to: {output_path}")


def mode2_apply(input_path):
    with open(input_path) as f:
        entries = json.load(f)

    print(f"Processing {len(entries)} documents (clearing audit on all, applying changes where needed)...\n")

    mongo = MongoClient(MONGO_URI)
    db = mongo["triviabot"]

    changed = 0
    audit_cleared = 0
    for entry in entries:
        col_name = entry["collection"]
        doc_id = ObjectId(entry["id"])
        changes = entry.get("proposed_changes") if entry.get("ai_action") == "update" else {}

        update_op = {"$unset": {"audit": ""}}
        if changes:
            update_op["$set"] = changes

        result = db[col_name].update_one({"_id": doc_id}, update_op)
        if result.modified_count:
            audit_cleared += 1
            if changes:
                changed += 1
                print(f"  ✅ Updated + audit cleared: {col_name} / {entry['id']}")
                print(f"     Changes: {list(changes.keys())}")
            else:
                print(f"  🧹 Audit cleared: {col_name} / {entry['id']}")
        else:
            print(f"  ⚠️  No match for {col_name} / {entry['id']}")

    mongo.close()
    print(f"\nDone. Questions updated: {changed}, Audit fields cleared: {audit_cleared}")


def main():
    parser = argparse.ArgumentParser(description="Review and update flagged trivia questions")
    parser.add_argument("--mode", type=int, required=True, choices=[1, 2])
    parser.add_argument("--output", default="flagged_review.json")
    parser.add_argument("--input", default="flagged_review.json")
    args = parser.parse_args()

    if args.mode == 1:
        print("=== Mode 1: Analyzing flagged questions ===\n")
        print("Fetching flagged documents from MongoDB...")
        mode1_analyze(args.output)
    elif args.mode == 2:
        print("=== Mode 2: Applying updates ===\n")
        mode2_apply(args.input)


if __name__ == "__main__":
    main()
