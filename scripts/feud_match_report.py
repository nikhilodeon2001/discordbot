"""Read-only report over the feud_match_log collection.

Feud grades answers through a model (see feud_llm_matching.py) because its board holds
survey responses and players phrase the same thing differently. Every LLM-graded guess is
logged alongside what the pre-LLM matcher would have said, so this script can show whether
the change is actually earning its place in live play.

The rows that matter are the DISAGREEMENTS:

  * llm-only  -- the model matched, the old matcher didn't. These are the synonym saves
                 the feature exists for ("pop" -> "Soda").
  * legacy-only -- the old matcher matched, the model didn't. Usually legacy's loose
                 heuristics (first-5-characters, substring, character-set Jaccard) being
                 caught, but read them: a real regression would show up here too.
  * conflict  -- both matched, different slots.

Makes no writes.

    python scripts/feud_match_report.py
    python scripts/feud_match_report.py --days 3 --examples 15
"""
import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime  # noqa: E402

from dotenv import load_dotenv  # noqa: E402
from pymongo import MongoClient  # noqa: E402

# Per-1M-token rates, matching the candidates evaluated in tests/test_feud_matching.py.
RATES = {
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
}


def percentile(values, pct):
    if not values:
        return 0
    values = sorted(values)
    return values[min(int(len(values) * pct), len(values) - 1)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=float, default=None,
                        help="only consider rows from the last N days")
    parser.add_argument("--examples", type=int, default=10,
                        help="disagreement examples to print per category")
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             ".env"))
    db = MongoClient(os.getenv("mongo_db_string"))["triviabot"]

    query = {}
    if args.days:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=args.days)
        query["ts"] = {"$gte": cutoff}

    rows = list(db.feud_match_log.find(query))
    if not rows:
        print("No rows in feud_match_log"
              + (f" for the last {args.days} days." if args.days else "."))
        return 0

    total = len(rows)
    agreed = sum(1 for r in rows if r.get("agreed"))
    llm_only, legacy_only, conflict, both_none = [], [], [], 0

    for r in rows:
        llm, legacy = r.get("llm_answer"), r.get("legacy_answer")
        if llm == legacy:
            if llm is None:
                both_none += 1
            continue
        if llm and not legacy:
            llm_only.append(r)
        elif legacy and not llm:
            legacy_only.append(r)
        else:
            conflict.append(r)

    span = ""
    timestamps = [r["ts"] for r in rows if r.get("ts")]
    if timestamps:
        span = f"  ({min(timestamps):%Y-%m-%d} to {max(timestamps):%Y-%m-%d})"

    print(f"feud_match_log: {total} graded guesses{span}")
    print(f"  agreement with pre-LLM matcher : {agreed}/{total} "
          f"({agreed / total * 100:.1f}%)")
    print(f"  both said no match             : {both_none}")
    print(f"  LLM matched, legacy did not    : {len(llm_only)}   <- the point of this")
    print(f"  legacy matched, LLM did not    : {len(legacy_only)}")
    print(f"  both matched, different slots  : {len(conflict)}")

    def show(title, subset, note):
        if not subset:
            return
        print(f"\n--- {title} ({len(subset)}) ---")
        print(f"    {note}")
        for r in subset[:args.examples]:
            print(f"  {r.get('guess')!r:32} llm={r.get('llm_answer')!r:24}"
                  f" legacy={r.get('legacy_answer')!r:24}")
            print(f"      Q: {str(r.get('question'))[:88]}")

    show("LLM matched, legacy did not", llm_only,
         "These should read as correct synonyms. Anything wrong here is a false positive "
         "that cost a board slot.")
    show("legacy matched, LLM did not", legacy_only,
         "Usually legacy's loose heuristics being caught. Anything genuinely correct here "
         "is a regression.")
    show("both matched, different slots", conflict,
         "Check which slot is actually right.")

    # --- latency and spend ---
    latencies = [r["latency_ms"] for r in rows if r.get("latency_ms")]
    if latencies:
        print(f"\nlatency: p50 {percentile(latencies, 0.5)}ms  "
              f"p95 {percentile(latencies, 0.95)}ms  max {max(latencies)}ms")

    by_model = Counter(r.get("model") for r in rows)
    spend = 0.0
    for model, count in by_model.items():
        model_rows = [r for r in rows if r.get("model") == model]
        pin = sum(r.get("prompt_tokens") or 0 for r in model_rows)
        pout = sum(r.get("completion_tokens") or 0 for r in model_rows)
        if model in RATES:
            cin, cout = RATES[model]
            cost = (pin * cin + pout * cout) / 1_000_000
            spend += cost
            print(f"  {model}: {count} calls, {pin} in / {pout} out tokens, ${cost:.4f}")
        else:
            print(f"  {model}: {count} calls, {pin} in / {pout} out tokens "
                  f"(no rate on file)")
    if spend:
        print(f"\ntotal spend on file: ${spend:.4f}"
              f"   (~${spend / total * 1000:.4f} per 1,000 guesses)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
