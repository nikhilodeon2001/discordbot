"""Golden corpus for answer_matching.match_answer.

Run directly (no pytest required):

    ./.venv/bin/python tests/test_answer_matching.py

Each case is (user, correct, category, url, config, expected, note). `config`
is a preset name: "STRICT" | "BALANCED" | "GENEROUS".
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from answer_matching import match_answer, STRICT, BALANCED, GENEROUS  # noqa: E402

CONFIGS = {"STRICT": STRICT, "BALANCED": BALANCED, "GENEROUS": GENEROUS}

# (user, correct, category, url, config, expected, note)
CASES = [
    # --- the reported bug ---
    ("Non-reactive", "It's unreactive", "", "", "BALANCED", True,
     "reported: paraphrase should be accepted"),
    ("Reac", "It's unreactive", "", "", "BALANCED", False,
     "reported: meaningless fragment must be rejected"),

    # --- antonym guards (same root, opposite negation) ---
    ("Reactive", "Unreactive", "", "", "BALANCED", False, "antonym"),
    ("Unreactive", "Reactive", "", "", "BALANCED", False, "antonym (reversed)"),
    ("Stop", "Nonstop", "", "", "BALANCED", False, "antonym"),
    ("Profit", "Nonprofit", "", "", "BALANCED", False, "antonym"),
    ("Newtonian", "Non-Newtonian", "", "", "BALANCED", False, "antonym: fluids"),
    ("Visible", "Invisible", "", "", "BALANCED", False, "antonym: in- prefix"),
    ("Possible", "Impossible", "", "", "BALANCED", False, "antonym: im- prefix"),

    # --- both negated: equivalent ---
    ("un-reactive", "non reactive", "", "", "BALANCED", True, "both negated, same root"),

    # --- typos / phonetic ---
    ("Napolean", "Napoleon", "", "", "BALANCED", True, "typo"),
    ("Einstien", "Einstein", "", "", "BALANCED", True, "transposition typo"),
    ("Shakespere", "Shakespeare", "", "", "BALANCED", True, "typo"),
    ("Pythagorus", "Pythagoras", "", "", "BALANCED", True, "typo"),

    # --- formatting / order / filler / accents ---
    ("the beatles", "Beatles", "", "", "BALANCED", True, "leading article"),
    ("beatles", "The Beatles", "", "", "BALANCED", True, "missing article"),
    ("cafe", "café", "", "", "BALANCED", True, "accent"),
    ("new york city", "City of New York", "", "", "BALANCED", True, "order + filler"),
    ("MONA LISA", "Mona Lisa", "", "", "BALANCED", True, "case"),

    # --- number words ---
    ("four", "4", "", "", "BALANCED", True, "number word vs digit"),
    ("4", "four", "", "", "BALANCED", True, "digit vs number word (free text)"),

    # --- partial / surname behaviour differs by dial ---
    ("Einstein", "Albert Einstein", "", "", "BALANCED", False, "surname-only: not in BALANCED"),
    ("Einstein", "Albert Einstein", "", "", "GENEROUS", True, "surname-only: allowed in GENEROUS"),
    ("Franklin Roosevelt", "Franklin Delano Roosevelt", "", "", "BALANCED", True,
     "2 of 3 name tokens -> majority coverage"),
    ("States", "United States", "", "", "BALANCED", False, "bare fragment"),
    ("Everest", "Mount Everest", "", "", "GENEROUS", True, "distinctive last word"),
    ("Roosevelt", "Franklin Roosevelt", "", "", "GENEROUS", True, "surname"),
    ("Ford", "Henry Ford", "", "", "GENEROUS", True, "short but distinctive surname"),
    ("Strom", "Strom Thurmond", "", "", "GENEROUS", True, "distinctive first name"),
    ("Thurmond", "Strom Thurmond", "", "", "GENEROUS", True, "surname"),
    ("Albert", "Albert Einstein", "", "", "GENEROUS", True, "first name"),
    ("West", "Kanye West", "", "", "GENEROUS", True, "surname that is also a common word"),
    ("Mount", "Mount Everest", "", "", "GENEROUS", False, "generic modifier is not enough"),
    ("The", "The Himalayas", "", "", "GENEROUS", False, "article-only never matches"),
    ("Himalayas", "The Himalayas", "", "", "GENEROUS", True, "key word (article is filler)"),

    # --- GENEROUS last-word rule rejects generic "type" nouns ---
    ("River", "Nile River", "", "", "GENEROUS", False, "generic head noun"),
    ("Ocean", "Pacific Ocean", "", "", "GENEROUS", False, "generic head noun"),
    ("City", "Mexico City", "", "", "GENEROUS", False, "generic head noun"),
    ("Island", "Long Island", "", "", "GENEROUS", False, "generic head noun"),
    ("States", "United States", "", "", "GENEROUS", False, "generic head noun (rely on alias/full)"),

    # --- GENEROUS must NOT loosen short-word typo tolerance ---
    ("cot", "cat", "", "", "GENEROUS", False, "one-letter-off short word stays wrong"),
    ("mark", "Mars", "", "", "GENEROUS", False, "short typo stays wrong"),

    # --- wrong answers stay wrong ---
    ("Paris", "London", "", "", "GENEROUS", False, "unrelated"),
    ("cat", "dog", "", "", "GENEROUS", False, "unrelated short"),
    ("Venus", "Mars", "", "", "BALANCED", False, "unrelated planets"),

    # --- aliases ---
    ("USA", "United States", "", "", "BALANCED", True, "alias group"),
    ("America", "United States of America", "", "", "BALANCED", True, "alias group"),
    ("England", "United Kingdom", "", "", "BALANCED", True, "alias group"),

    # --- STRICT / Poindexter ---
    ("the beatles", "Beatles", "", "", "STRICT", True, "strict allows filler/order"),
    ("Napolean", "Napoleon", "", "", "STRICT", False, "strict rejects typos"),
    ("Non-reactive", "It's unreactive", "", "", "STRICT", False, "strict rejects paraphrase"),
    ("Einstein", "Albert Einstein", "", "", "STRICT", False, "strict rejects partial"),

    # --- structured: multiple choice (compare first letter of the choice) ---
    ("B", "B. Mercury", "", "multiple choice", "BALANCED", True, "MC letter"),
    ("b", "B. Mercury", "", "multiple choice opentdb", "BALANCED", True, "MC letter lower"),
    ("A", "B. Mercury", "", "multiple choice", "BALANCED", False, "MC wrong letter"),

    # --- structured: numeric ---
    ("42", "42", "", "", "BALANCED", True, "number exact"),
    ("42 apples", "42", "", "", "BALANCED", True, "leading number"),
    ("43", "42", "", "", "BALANCED", False, "wrong number"),
    ("-3", "-3", "", "", "BALANCED", True, "negative number"),

    # --- structured: crossword ---
    ("REACT", "react", "Crossword", "", "BALANCED", True, "crossword case-insensitive"),
    ("re act", "react", "Crossword", "", "BALANCED", True, "crossword ignores spaces"),
    ("reacts", "react", "Crossword", "", "BALANCED", False, "crossword needs full word"),

    # --- structured: zeroes (set of integers) ---
    ("3 -2", "-2 3", "", "zeroes", "BALANCED", True, "zeroes order-independent"),
    ("3 2", "-2 3", "", "zeroes", "BALANCED", False, "zeroes wrong sign"),

    # --- structured: derivative (unordered terms) ---
    ("2x + 3", "3 + 2x", "", "derivative", "BALANCED", True, "derivative term order"),

    # --- structured: factors / trig ---
    ("(x+1)(x-2)", "(x + 1)(x - 2)", "", "factors", "BALANCED", True, "factors spacing"),
    ("sin(x)", "sin (x)", "", "trig", "BALANCED", True, "trig spacing"),

    # --- structured: scramble must be exact ---
    ("listen", "silent", "", "scramble", "BALANCED", False, "anagram is not the answer"),
    ("silent", "silent", "", "scramble", "BALANCED", True, "scramble solved"),
]


def run():
    failures = []
    for user, correct, category, url, cfg_name, expected, note in CASES:
        cfg = CONFIGS[cfg_name]
        actual = match_answer(user, correct, category=category, url=url, config=cfg)
        ok = actual == expected
        if not ok:
            failures.append((user, correct, cfg_name, expected, actual, note))
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {cfg_name:8} match({user!r}, {correct!r}) "
              f"= {actual} (expected {expected})  -- {note}")
    print(f"\n{len(CASES) - len(failures)}/{len(CASES)} passed, {len(failures)} failing")
    if failures:
        print("\nFAILURES:")
        for user, correct, cfg_name, expected, actual, note in failures:
            print(f"  {cfg_name:8} match({user!r}, {correct!r}) -> {actual}, "
                  f"expected {expected}  ({note})")
    return len(failures)


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
