"""Golden corpus for discordbot.legacy_fuzzy_match's giveaway-word guard.

legacy_fuzzy_match is the LIVE answer matcher (USE_LEGACY_FUZZY_MATCH=True in
discordbot.py). discordbot.py imports discord/mongo/openai at module scope, so
this file imports it tolerantly (same pattern as tests/test_feud_matching.py's
_legacy_baseline) and prints a SKIPPED note rather than failing hard on a
machine without those dependencies / a populated .env.

Run directly (no pytest required):

    ./.venv/bin/python tests/test_legacy_fuzzy_match.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import discordbot  # noqa: E402
    _import_error = None
except Exception as e:  # pragma: no cover - environment dependent
    discordbot = None
    _import_error = e


# (user, correct, category, url, question_text, expected, note)
CASES = [
    # --- the reported bug, full repro ---
    ("time", "ragtime", "\"Time\" For A Change", "",
     "Scott Joplin is a famous performer & composer of this musical style",
     False, "category+question giveaway word 'time' must not win via substring leniency"),
    ("ragtime", "ragtime", "\"Time\" For A Change", "",
     "Scott Joplin is a famous performer & composer of this musical style",
     True, "guard must not block the actual exact answer"),
    ("joplin", "ragtime", "\"Time\" For A Change", "",
     "Scott Joplin is a famous performer & composer of this musical style",
     False, "question-text-only giveaway word (not in category) must also be blocked"),
    ("time", "ragtime", "\"Time\" For A Change", "", "",
     False, "category alone (no question_text passed) still blocks the giveaway word"),
    ("cucu", "a cucumber", "Vegetables", "", "A long green fruit often mistaken for a vegetable",
     True, "regression guard: substring leniency still works with no category/question overlap"),

    # --- first-5-characters heuristic, isolated from the substring heuristic ---
    # "atomix" and "atomicity" share only their first 5 characters ("atomi"); neither
    # is a substring of the other, so only the first-5-chars heuristic is in play.
    ("atomix", "atomicity", "Atomix Theory", "", "",
     False, "first-5-chars heuristic: category giveaway word must not win"),
    ("atomix", "atomicity", "", "", "",
     True, "regression guard: first-5-chars leniency still works absent giveaway overlap"),

    # --- first-word heuristic ---
    ("ocean", "Ocean Wave", "Ocean Exploration", "", "",
     False, "first-word heuristic: category giveaway word must not win"),
    ("ocean", "Ocean Wave", "", "", "",
     True, "regression guard: first-word leniency still works absent giveaway overlap"),

    # --- user-provided examples ---
    ("bottom", "your bottom dollar", "Bottom", "", "",
     False, "user-provided example: a whole word taken from the category must not win, even mid-phrase"),

    # --- morphological variant (plural category word vs. singular guess) ---
    ("martin", "Martin Bormann", "Martins", "",
     "A skeleton found in 1972 was declared to be this Nazi, rumored alive in South America",
     False, "reported gap: plural category word 'Martins' must still block singular guess 'martin'"),
    ("vincent", "Martin Bormann", "", "", "",
     False, "regression guard: 'vincent' is not a real match for 'Martin Bormann' regardless of giveaway logic"),
]


def run():
    if discordbot is None:
        print(f"SKIPPED: could not import discordbot ({_import_error!r}); "
              "legacy_fuzzy_match cannot be exercised in this environment.")
        return 0

    failures = []
    for user, correct, category, url, question_text, expected, note in CASES:
        actual = discordbot.legacy_fuzzy_match(user, correct, category, url, question_text=question_text)
        ok = actual == expected
        if not ok:
            failures.append((user, correct, expected, actual, note))
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] legacy_fuzzy_match({user!r}, {correct!r}, question_text={question_text!r}) "
              f"= {actual} (expected {expected})  -- {note}")
    print(f"\n{len(CASES) - len(failures)}/{len(CASES)} passed, {len(failures)} failing")
    if failures:
        print("\nFAILURES:")
        for user, correct, expected, actual, note in failures:
            print(f"  legacy_fuzzy_match({user!r}, {correct!r}) -> {actual}, expected {expected}  ({note})")
    return len(failures)


def run_toggle():
    if discordbot is None:
        return 0

    failures = []
    original = discordbot.GIVEAWAY_WORD_GUARD_ENABLED
    try:
        discordbot.GIVEAWAY_WORD_GUARD_ENABLED = True
        on = discordbot.legacy_fuzzy_match(
            "time", "ragtime", "\"Time\" For A Change", "",
            question_text="Scott Joplin is a famous performer & composer of this musical style")
        discordbot.GIVEAWAY_WORD_GUARD_ENABLED = False
        off = discordbot.legacy_fuzzy_match(
            "time", "ragtime", "\"Time\" For A Change", "",
            question_text="Scott Joplin is a famous performer & composer of this musical style")
    finally:
        discordbot.GIVEAWAY_WORD_GUARD_ENABLED = original

    ok = on is False and off is True
    if not ok:
        failures.append(("guard-on", on, False, "guard-off", off, True))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] GIVEAWAY_WORD_GUARD_ENABLED=True -> {on} (expected False), "
          f"=False -> {off} (expected True)  -- toggle must restore pre-guard leniency when disabled")
    return len(failures)


if __name__ == "__main__":
    sys.exit(1 if (run() + run_toggle()) else 0)
