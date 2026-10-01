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

    # --- "Spot the Kitty" bug: short partial guess vs. a much-longer question word ---
    ("short", "British Shorthair", "Spot the Kitty", "",
     "The British Straighthair, the British Shorthair, the British Nohair",
     False, "reported bug repro: partial giveaway-word fragment 'short' (substring of "
            "question's 'shorthair') stays WRONG under the scoring guard -- the red-card "
            "fix (see run_giveaway_guard_blocked_match) only changes the visible feedback, "
            "not the graded outcome"),
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


def run_per_call_override():
    """enable_giveaway_guard on legacy_fuzzy_match itself (not the global flag) --
    used by the 🟥 reaction to test "would this have matched without the guard?"
    on a single call, without touching GIVEAWAY_WORD_GUARD_ENABLED (unsafe to
    mutate mid-request in an async bot serving concurrent games)."""
    if discordbot is None:
        return 0

    kwargs = dict(
        category="\"Time\" For A Change",
        question_text="Scott Joplin is a famous performer & composer of this musical style",
    )
    original = discordbot.GIVEAWAY_WORD_GUARD_ENABLED
    cases = [
        (None, False, "enable_giveaway_guard=None falls back to the global default (True)"),
        (True, False, "enable_giveaway_guard=True explicitly matches the guarded default"),
        (False, True, "enable_giveaway_guard=False bypasses the guard for this call only"),
    ]
    failures = []
    for override, expected, note in cases:
        actual = discordbot.legacy_fuzzy_match("time", "ragtime", kwargs["category"], "",
                                                question_text=kwargs["question_text"],
                                                enable_giveaway_guard=override)
        global_unchanged = discordbot.GIVEAWAY_WORD_GUARD_ENABLED == original
        ok = actual == expected and global_unchanged
        if not ok:
            failures.append((override, expected, actual, global_unchanged, note))
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] enable_giveaway_guard={override!r} -> {actual} (expected {expected}), "
              f"global unchanged={global_unchanged}  -- {note}")
    return len(failures)


def run_short_shorthair_repro():
    """Proves the "short"/"shorthair" case is a real giveaway-guard collision --
    i.e. the guard is the *only* thing standing between "short" and a match --
    which is the precondition the red-card fix (_giveaway_guard_blocked_match)
    relies on to decide whether to flag it."""
    if discordbot is None:
        return 0
    category = "Spot the Kitty"
    question_text = "The British Straighthair, the British Shorthair, the British Nohair"
    guarded = discordbot.legacy_fuzzy_match(
        "short", "British Shorthair", category, "", question_text=question_text,
        enable_giveaway_guard=True)
    unguarded = discordbot.legacy_fuzzy_match(
        "short", "British Shorthair", category, "", question_text=question_text,
        enable_giveaway_guard=False)
    ok = guarded is False and unguarded is True
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] 'short' vs 'British Shorthair': guard on -> {guarded} (expected False), "
          f"guard off -> {unguarded} (expected True)")
    return 0 if ok else 1


def run_giveaway_guard_blocked_match():
    """Exercises discordbot._giveaway_guard_blocked_match directly -- the new
    helper that decides whether the 🟥 reaction fires for a partial giveaway-
    word collision like "short" vs. question word "shorthair"."""
    if discordbot is None:
        return 0
    original_question = discordbot.current_question
    discordbot.current_question = {
        "trivia_category": "Spot the Kitty",
        "trivia_question": "The British Straighthair, the British Shorthair, the British Nohair",
        "trivia_url": "",
        "trivia_answer_list": ["British Shorthair"],
    }
    try:
        cases = [
            ("short", True, "partial giveaway-word fragment must be flagged"),
            ("british shorthair", False, "already-correct guess must not be flagged"),
            ("xyz", False, "an answer that wouldn't match even unguarded must not be flagged"),
        ]
        failures = 0
        for guess, expected, note in cases:
            actual = discordbot._giveaway_guard_blocked_match(guess)
            ok = actual == expected
            failures += 0 if ok else 1
            status = "PASS" if ok else "FAIL"
            print(f"[{status}] _giveaway_guard_blocked_match({guess!r}) "
                  f"= {actual} (expected {expected})  -- {note}")
        return failures
    finally:
        discordbot.current_question = original_question


if __name__ == "__main__":
    sys.exit(1 if (run() + run_toggle() + run_per_call_override()
                    + run_short_shorthair_repro() + run_giveaway_guard_blocked_match()) else 0)
