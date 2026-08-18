"""Golden corpus for answer_matching.match_answer.

Run directly (no pytest required):

    ./.venv/bin/python tests/test_answer_matching.py

Each case is (user, correct, category, url, config, expected, note). `config`
is a preset name: "STRICT" | "BALANCED" | "GENEROUS".
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from answer_matching import (  # noqa: E402
    match_answer, STRICT, BALANCED, GENEROUS, extract_words, limit_words,
)

CONFIGS = {"STRICT": STRICT, "BALANCED": BALANCED, "GENEROUS": GENEROUS}

# (user, correct, category, url, config, expected, note)
CASES = [
    # --- the reported bug ---
    ("Non-reactive", "It's unreactive", "", "", "BALANCED", True,
     "reported: paraphrase should be accepted"),
    ("Reac", "It's unreactive", "", "", "BALANCED", False,
     "reported: meaningless fragment must be rejected"),
    ("Reac", "It's unreactive", "", "", "GENEROUS", True,
     "accepted trade-off: substring-anywhere leniency also re-admits this fragment under GENEROUS"),

    # --- substring leniency (GENEROUS only, substring-anywhere per word) ---
    ("Cucu", "a cucumber", "", "", "GENEROUS", True,
     "reported: prefix of a single-word answer should be accepted"),
    ("Cucu", "a cucumber", "", "", "BALANCED", False,
     "substring leniency is GENEROUS-only"),

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

    # --- structured: multiple choice (letter OR exact choice text) ---
    ("B", "B. Mercury", "", "multiple choice", "BALANCED", True, "MC letter"),
    ("b", "B. Mercury", "", "multiple choice opentdb", "BALANCED", True, "MC letter lower"),
    ("A", "B. Mercury", "", "multiple choice", "BALANCED", False, "MC wrong letter"),
    ("Mercury", "B. Mercury", "", "multiple choice", "BALANCED", True, "MC choice text"),
    ("mercury", "B. Mercury", "", "multiple choice", "BALANCED", True, "MC choice text lower"),
    ("Venus", "B. Mercury", "", "multiple choice", "BALANCED", False, "MC wrong choice text"),
    ("false", "A. False", "", "multiple choice", "BALANCED", True, "MC text for lettered True/False"),
    ("true", "A. False", "", "multiple choice", "BALANCED", False, "MC wrong text for lettered True/False"),
    ("False", "False", "", "multiple choice", "BALANCED", True, "MC text for bare True/False answer"),
    ("A", "A. The earth orbits the sun.", "", "multiple choice", "BALANCED", True,
     "MC letter still works when choice is a full sentence"),
    ("earth sun", "A. The earth orbits the sun.", "", "multiple choice", "BALANCED", False,
     "MC sentence choice: fragment must NOT match (exact-only guard)"),

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


# Word-limit enforcement for user-supplied AI prompts (museum paintings /
# Genie wishes). (input, max_words, max_chars, expected_text, expected_truncated, note)
WORD_LIMIT_CASES = [
    # --- the reported bypass ---
    ("blood-sugar-sex-magik-red-hot-chili-peppers-album-cover-1991-no-okras-please-no-okras",
     10, 90, "blood sugar sex magik red hot chili peppers album cover", True,
     "reported: hyphen chain counts as many words and is trimmed to 10"),

    # --- normal input passes through ---
    ("a cat surfing a giant wave at sunset", 10, 90,
     "a cat surfing a giant wave at sunset", False, "under-limit input unchanged"),
    ("space pirates", 3, 35, "space pirates", False, "genie: 2 words fine"),

    # --- alternative separators ---
    ("one_two_three_four", 3, 35, "one two three", True, "underscores split"),
    ("one.two.three.four", 3, 35, "one two three", True, "dots split"),
    ("one/two\\three|four", 3, 35, "one two three", True, "slashes/pipes split"),
    ("one😀two😀three😀four", 3, 35, "one two three", True, "emoji split"),
    ("one​two​three​four", 3, 35, "onetwothreefour", False,
     "zero-width chars vanish, can't act as hidden glue"),

    # --- fused words ---
    ("OneTwoThreeFour", 3, 35, "One Two Three", True, "camelCase splits"),
    ("no1okra2please", 1, 35, "no", True, "letter-digit boundaries split"),

    # --- long-blob backstop ---
    ("abcdefghijklmnopqrstuvwxyzabcdefghijklmnop", 1, 90,
     "abcdefghijklmnopqrst", True, "40-char blob chunked to 20-char words"),

    # --- char cap is the ultimate backstop ---
    ("extraordinarily magnificent hippopotamus", 3, 35,
     "extraordinarily magnificent", True, "35-char cap trims third word"),

    # --- words survive punctuation, apostrophes kept ---
    ("don't stop believin'", 3, 35, "don't stop believin", False,
     "apostrophes don't split words"),
    ("!!! ??? ...", 3, 35, "", False, "punctuation-only input yields empty"),
    ("", 3, 35, "", False, "empty input"),
]


def run_word_limits():
    failures = []
    for text, max_words, max_chars, expected_text, expected_trunc, note in WORD_LIMIT_CASES:
        actual_text, actual_trunc = limit_words(text, max_words, max_chars)
        ok = actual_text == expected_text and actual_trunc == expected_trunc
        if not ok:
            failures.append((text, expected_text, expected_trunc, actual_text, actual_trunc, note))
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] limit_words({text!r}, {max_words}, {max_chars}) "
              f"= ({actual_text!r}, {actual_trunc})  -- {note}")
    if failures:
        print("\nWORD-LIMIT FAILURES:")
        for text, exp_t, exp_f, act_t, act_f, note in failures:
            print(f"  limit_words({text!r}) -> ({act_t!r}, {act_f}), "
                  f"expected ({exp_t!r}, {exp_f})  ({note})")
    return len(failures)


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
    sys.exit(1 if (run() + run_word_limits()) else 0)
