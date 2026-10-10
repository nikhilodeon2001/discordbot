"""One-time backfill: replay every doc in `user_selection_history` (the old per-event log,
retired in favor of per-user counters in `user_option_defaults`) into the new
`round_end_options.combo_counts` / `minigame.combo_counts` + `last_selected` shape, so existing
collected signal isn't thrown away by the storage switch.

Reads each history doc's already-computed `value`/`display`/`keywords` (no need to
re-derive keyword display names or canonical mini-game keys here -- those were already
resolved at log time) and replays them in `timestamp` ascending order, so the final
`last_selected` naturally ends up being each user's actual most recent historical pick.

Caveat (accepted, not fixed here): the old logging recorded one entry per message/action
rather than one per round, so a historical round where someone typed keywords across two
separate messages replays as two separate combo-count increments instead of one merged combo.
Not worth reconstructing after the fact.

Guarded against accidental double-runs (the $inc's aren't idempotent) via a marker doc in
`migrations`; pass --force to re-run anyway. Run once per environment -- staging and prod are
separate Mongo databases, so each needs its own invocation:

    mongo_db_string="$(heroku config:get mongo_db_string -a discordbot-staging)" \
        python3 scripts/migrate_user_selection_history_to_counters.py --dry-run
    mongo_db_string="$(heroku config:get mongo_db_string -a discordbot-staging)" \
        python3 scripts/migrate_user_selection_history_to_counters.py

    mongo_db_string="$(heroku config:get mongo_db_string -a discordtriviabot)" \
        python3 scripts/migrate_user_selection_history_to_counters.py --dry-run
    mongo_db_string="$(heroku config:get mongo_db_string -a discordtriviabot)" \
        python3 scripts/migrate_user_selection_history_to_counters.py

No ordering dependency with deploying the new counter-based bot code -- this only replays rows
already sitting in `user_selection_history`, and the new code never writes there, so running
this before or after the deploy is equally safe.
"""
import argparse
import datetime
import os

import pymongo

MARKER_ID = "user_selection_history_to_counters"


def combo_key(value):
    """Mirrors discordbot.py's _combo_key -- "_none_" (not "") for the empty-combo case, since
    Mongo dynamic update paths can't end in an empty segment."""
    return value or "_none_"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print what would be migrated without writing.")
    parser.add_argument("--force", action="store_true", help="Re-run even if the marker doc says this already completed.")
    args = parser.parse_args()

    client = pymongo.MongoClient(os.environ["mongo_db_string"])
    db = client["triviabot"]

    if not args.dry_run and not args.force:
        already_done = db.migrations.find_one({"_id": MARKER_ID})
        if already_done:
            print(f"❌ Already migrated at {already_done.get('completed_at')} -- pass --force to re-run.")
            return

    docs = list(db.user_selection_history.find({}).sort("timestamp", 1))
    print(f"Found {len(docs)} user_selection_history docs to replay.")

    round_options_ops = 0
    minigame_ops = 0
    skipped = 0

    for doc in docs:
        user_id = doc.get("user_id")
        category = doc.get("category")
        value = doc.get("value")
        display = doc.get("display")
        entry_point = doc.get("entry_point")
        selected_at = datetime.datetime.utcfromtimestamp(doc["timestamp"]) if "timestamp" in doc else datetime.datetime.utcnow()

        if user_id is None or category is None or value is None:
            skipped += 1
            continue

        if category == "round_end_options":
            key = combo_key(value)
            keywords = doc.get("keywords") or []
            update = {
                "$inc": {f"round_end_options.combo_counts.{key}.count": 1},
                "$set": {
                    f"round_end_options.combo_counts.{key}.display": display,
                    f"round_end_options.combo_counts.{key}.keywords": keywords,
                    "round_end_options.last_selected": {
                        "value": key, "display": display, "keywords": keywords,
                        "selected_at": selected_at,
                    },
                },
            }
            round_options_ops += 1
        elif category == "minigame":
            update = {
                "$inc": {
                    f"minigame.combo_counts.{value}.count": 1,
                    f"minigame.combo_counts.{value}.by_entry_point.{entry_point}": 1,
                },
                "$set": {
                    f"minigame.combo_counts.{value}.display": display,
                    "minigame.last_selected": {
                        "value": value, "display": display, "entry_point": entry_point,
                        "selected_at": selected_at,
                    },
                },
            }
            minigame_ops += 1
        else:
            skipped += 1
            continue

        if args.dry_run:
            print(f"[dry-run] user={user_id} category={category} value={value!r} entry_point={entry_point}")
        else:
            db.user_option_defaults.update_one({"_id": user_id}, update, upsert=True)

    print(f"round_end_options picks replayed: {round_options_ops}")
    print(f"minigame picks replayed: {minigame_ops}")
    print(f"skipped (missing fields / unknown category): {skipped}")

    if args.dry_run:
        print("Dry run only -- nothing written.")
        return

    db.migrations.update_one(
        {"_id": MARKER_ID},
        {"$set": {"completed_at": datetime.datetime.utcnow(), "docs_replayed": len(docs)}},
        upsert=True,
    )
    print("✅ Migration complete, marker doc written.")


if __name__ == "__main__":
    main()
