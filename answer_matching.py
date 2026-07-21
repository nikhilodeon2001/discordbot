"""Programmatic trivia answer matching.

This module owns every "is this guess correct?" decision the bot makes. It is
deliberately free of discord/mongo/openai imports so it can be unit-tested in
isolation (see tests/test_answer_matching.py).

Two kinds of question are handled:

  * Structured types (multiple choice, crossword, numeric, zeroes, derivative,
    factors, trig, scramble) get deterministic, type-specific checks. These are
    not "fuzzy" at all and their behaviour is preserved from the old
    implementation.

  * Free-text questions go through a principled, ordered pipeline with a tunable
    leniency dial (STRICT / BALANCED / GENEROUS). The pipeline is generous about
    things that should count (case, punctuation, accents, word order, filler
    words, typos, common equivalences) and conservative about things that should
    not (bare fragments, antonyms, coincidental character overlap).

The public entry point is match_answer(). discordbot.fuzzy_match is a thin
backward-compatible wrapper around it.
"""

import re
import string
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from metaphone import doublemetaphone
from rapidfuzz import fuzz
from rapidfuzz.distance import DamerauLevenshtein


# ---------------------------------------------------------------------------
# Normalization primitives
# ---------------------------------------------------------------------------

# Unicode superscript digits -> ASCII digits (e.g. x²  ->  x2).
_SUPERSCRIPT_MAP = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
}

# Non-ASCII "smart" punctuation from copy-pasted content -> ASCII equivalents.
# string.punctuation is ASCII-only, so these would otherwise survive the strip.
SMART_PUNCTUATION_MAP = {
    "‘": "'", "’": "'",   # curly single quotes
    "“": '"', "”": '"',   # curly double quotes
    "–": "-", "—": "-",   # en / em dash
    "−": "-",             # unicode minus sign
    "°": "",              # degree sign
}

_SMART_PUNCT_TABLE = str.maketrans(SMART_PUNCTUATION_MAP)
_PUNCT_TABLE = str.maketrans("", "", string.punctuation)

# Words that carry no distinguishing meaning in a trivia answer. Kept
# deliberately small so we never strip a whole short answer to nothing.
FILLER_WORDS = {
    "a", "an", "the", "of", "and", "to", "in", "on", "at", "with", "for", "by",
    "it", "its",
}

# Generic "type" nouns that commonly trail a proper name ("Nile River", "Red
# Sea", "Mexico City"). The surname/last-word rule refuses to accept one of
# these on its own, so "River" never counts for "Nile River" while a distinctive
# proper noun like "Einstein" still counts for "Albert Einstein". Edit freely.
GENERIC_HEAD_WORDS = {
    # water / landforms
    "sea", "seas", "ocean", "oceans", "river", "rivers", "lake", "lakes",
    "mountain", "mountains", "mount", "hill", "hills", "gulf", "bay", "desert",
    "island", "islands", "isle", "isles", "sound", "strait", "straits",
    "peninsula", "valley", "valleys", "falls", "waterfall", "canyon", "forest",
    "jungle", "plateau", "glacier", "volcano", "channel", "coast", "cape",
    "reef", "delta", "basin", "plain", "plains", "lagoon", "fjord",
    # places / polities
    "city", "cities", "town", "village", "county", "state", "states", "country",
    "nation", "province", "region", "territory", "district", "kingdom",
    "republic", "empire", "federation", "colony", "borough",
    # events / eras
    "war", "wars", "battle", "siege", "revolution", "rebellion", "treaty",
    "era", "age", "period", "dynasty", "movement", "crisis",
    # structures / orgs
    "street", "avenue", "road", "bridge", "tower", "building", "palace",
    "castle", "cathedral", "church", "chapel", "temple", "mosque", "museum",
    "gallery", "university", "college", "school", "hospital", "stadium",
    "arena", "park", "garden", "gardens", "station", "airport", "harbor",
    "harbour", "port", "canal", "dam", "wall", "gate", "company",
    "corporation", "party", "club", "league", "association", "society",
}

# Prefixes that negate/oppose the root word. Used both to fold equivalent
# negations ("non-reactive" == "unreactive") and, more importantly, to BLOCK
# antonyms whose only difference is the presence of such a prefix
# ("reactive" != "unreactive", "visible" != "invisible").
NEGATION_PREFIXES = ("non", "anti", "dis", "un", "im", "in", "ir", "il")
_MIN_NEGATION_ROOT = 4

# Spelled-out numbers <-> digits, so "four" matches "4".
_NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
    "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
    "eighty": "80", "ninety": "90", "hundred": "100", "thousand": "1000",
}


def _normalize_superscripts(text):
    return "".join(_SUPERSCRIPT_MAP.get(ch, ch) for ch in text)


def remove_diacritics(input_str):
    """café -> cafe, naïve -> naive."""
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join(ch for ch in nfkd_form if not unicodedata.combining(ch))


def normalize_text(value):
    """Canonical form of a free-text answer.

    strip -> lower -> superscripts to ASCII -> drop diacritics -> smart
    punctuation to ASCII -> hyphen/underscore/slash to SPACE (so "non-reactive"
    becomes two words, not the fused "nonreactive") -> strip remaining ASCII
    punctuation -> collapse whitespace.
    """
    text = str(value).strip().lower()
    text = _normalize_superscripts(text)
    text = remove_diacritics(text)
    text = text.translate(_SMART_PUNCT_TABLE)
    # Word-joining punctuation becomes a space rather than vanishing.
    text = text.replace("-", " ").replace("_", " ").replace("/", " ")
    # Everything else (apostrophes, commas, periods, ...) is deleted.
    text = text.translate(_PUNCT_TABLE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokens(normalized):
    return normalized.split()


def _significant_tokens(normalized):
    """Tokens with filler words removed, with number-words folded to digits.
    Falls back to all tokens if removing filler would empty the answer."""
    toks = [_NUMBER_WORDS.get(t, t) for t in normalized.split()]
    kept = [t for t in toks if t not in FILLER_WORDS]
    return kept if kept else toks


# ---------------------------------------------------------------------------
# Negation handling
# ---------------------------------------------------------------------------

def _strip_negation(word):
    """(root, was_negated) for a single word, else (word, False)."""
    for prefix in NEGATION_PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= _MIN_NEGATION_ROOT:
            return word[len(prefix):], True
    return word, False


def _merge_standalone_negations(tokens):
    """Join a lone negation word onto the next token: ["non","reactive"] ->
    ["nonreactive"]."""
    merged = []
    i = 0
    while i < len(tokens):
        if tokens[i] in NEGATION_PREFIXES and i + 1 < len(tokens):
            merged.append(tokens[i] + tokens[i + 1])
            i += 2
        else:
            merged.append(tokens[i])
            i += 1
    return merged


def _content_pairs(significant_tokens):
    """[(root, negated), ...] for the significant tokens of an answer."""
    return [_strip_negation(t) for t in _merge_standalone_negations(significant_tokens)]


def _negation_aware_setmatch(user_sig, correct_sig, config):
    """Compare two answers by their negation-folded content roots.

    Returns:
        True  -> definitely a match (same roots, same negation status)
        False -> definitely NOT a match (same roots but opposite negation ->
                 antonym, e.g. "reactive" vs "unreactive")
        None  -> inconclusive; fall through to the fuzzy layers
    """
    pairs_u = _content_pairs(user_sig)
    pairs_c = _content_pairs(correct_sig)

    roots_u = sorted(r for r, _ in pairs_u)
    roots_c = sorted(r for r, _ in pairs_c)
    if not roots_u or not roots_c or roots_u != roots_c:
        return None

    neg_u = {r for r, n in pairs_u if n}
    neg_c = {r for r, n in pairs_c if n}
    if neg_u == neg_c:
        if not neg_u:
            # No negation anywhere: plain (order/filler-insensitive) equality.
            return True
        # Both sides negate exactly the same roots: equivalent phrasing.
        return True if config.enable_negation_fold else None
    # Same roots, but a root is negated on one side only -> antonyms. Block it
    # so no downstream fuzzy layer can bridge the gap.
    return False


# ---------------------------------------------------------------------------
# Structured-answer checkers (behaviour preserved from the old implementation)
# ---------------------------------------------------------------------------

def is_number(s):
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def extract_leading_number(text):
    match = re.match(r"^-?\d+(?:\.\d+)?", str(text).strip())
    return match.group(0) if match else None


def derivative_checker(response, answer):
    response = response.lower().replace(" ", "").replace("^", "").replace("*", "")
    answer = answer.lower().replace(" ", "").replace("^", "").replace("*", "")
    response = _normalize_superscripts(response)
    answer = _normalize_superscripts(answer)

    def term_set(expr):
        terms = re.findall(r"[+-]?[^+-]+", expr)
        cleaned = (t[1:] if t.startswith("+") else t for t in terms if t)
        # Drop zero terms so an optional explicit "+0" doesn't cause a mismatch.
        return {t for t in cleaned if t.lstrip("-") != "0"}

    return term_set(response) == term_set(answer)


def factors_checker(response, answer):
    for ch in (" ", "*", "(", ")"):
        response = response.replace(ch, "")
        answer = answer.replace(ch, "")
    return response.lower() == answer.lower()


def trig_checker(response, answer):
    for ch in (" ", "(", ")"):
        response = response.replace(ch, "")
        answer = answer.replace(ch, "")
    return response.lower() == answer.lower()


def _zeroes_checker(user_answer, correct_answer):
    user_numbers = [int(n) for n in re.findall(r"-?\d+", user_answer)]
    correct_numbers = [int(n) for n in re.findall(r"-?\d+", correct_answer)]
    return set(user_numbers) == set(correct_numbers)


def _choice_text(normalized_choice):
    """Strip a leading single-letter label from a normalized MC choice:
    "a false" -> "false", "b mercury" -> "mercury", "false" -> "false"."""
    parts = normalized_choice.split(None, 1)
    if len(parts) == 2 and len(parts[0]) == 1:
        return parts[1]
    return normalized_choice


# ---------------------------------------------------------------------------
# Leniency dial
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MatchConfig:
    name: str
    # Whole-answer rapidfuzz similarity (0..1) required to call it a typo match.
    edit_ratio_threshold: float
    # Max edit distance allowed per whole (no-space) answer, keyed by answer
    # length buckets: (len<=4, len<=8, len>8).
    typo_caps: tuple
    enable_phonetic: bool
    enable_negation_fold: bool
    # Fraction of the correct answer's significant tokens a guess must cover to
    # count as a partial match. 1.0 effectively disables partial matching.
    subset_coverage: float
    # Accept a guess that matches the last significant token of a multi-word
    # answer (surname of a person, etc.).
    allow_surname_match: bool
    # Accept a guess that matches ANY single significant token of the answer.
    allow_any_key_word: bool
    min_key_word_len: int = 4
    # Whether the leniency (fuzzy/partial) layers run at all.
    enable_fuzzy: bool = True


STRICT = MatchConfig(
    name="STRICT",
    edit_ratio_threshold=1.0,
    typo_caps=(0, 0, 0),
    enable_phonetic=False,
    enable_negation_fold=False,
    subset_coverage=1.0,
    allow_surname_match=False,
    allow_any_key_word=False,
    enable_fuzzy=False,
)

BALANCED = MatchConfig(
    name="BALANCED",
    edit_ratio_threshold=0.85,
    typo_caps=(0, 1, 2),
    enable_phonetic=True,
    enable_negation_fold=True,
    subset_coverage=0.6,
    allow_surname_match=False,
    allow_any_key_word=False,
)

GENEROUS = MatchConfig(
    name="GENEROUS",
    # Typo strictness stays at BALANCED levels on purpose: "generous" here means
    # accept partial answers (a surname / distinctive last word, or most of a
    # multi-word answer), NOT accept looser misspellings. Loosening typo caps
    # for short answers makes distinct answers collide ("cot" == "cat").
    edit_ratio_threshold=0.85,
    typo_caps=(0, 1, 2),
    enable_phonetic=True,
    enable_negation_fold=True,
    # Same coverage as BALANCED: a single non-final word (e.g. "Mount" of
    # "Mount Everest") stays below the bar. The distinctive LAST word is
    # accepted by the position-aware surname rule below instead.
    subset_coverage=0.6,
    allow_surname_match=True,
    # Accept any distinctive single name token, first or last ("Strom" or
    # "Thurmond" for "Strom Thurmond", "Albert" or "Einstein" for "Albert
    # Einstein"). Generic type nouns (GENERIC_HEAD_WORDS: River, Mount, City...)
    # are still excluded, so "Mount" never counts for "Mount Everest".
    allow_any_key_word=True,
)

# The adjustable default for normal (non-Poindexter) play. Point this at a
# different preset, or tweak a preset's numbers, to move the dial.
ACTIVE_CONFIG = GENEROUS


# ---------------------------------------------------------------------------
# Alias groups (common answers with several valid surface forms)
# ---------------------------------------------------------------------------

ALIAS_GROUPS = [
    ["united states", "united states of america", "us", "usa", "america"],
    ["united kingdom", "great britain", "uk", "britain", "england"],
    ["netherlands", "holland", "the netherlands"],
    ["united arab emirates", "uae", "emirates"],
    ["south korea", "republic of korea", "rok"],
    ["north korea", "democratic people's republic of korea", "dprk"],
    ["new york city", "nyc"],
    ["los angeles", "la"],
    ["san francisco", "sf"],
]


def _alias_match(user_answer, correct_answer, category, url, config):
    """True if the guess matches the correct answer via a known alias group."""
    normalized_correct = normalize_text(correct_answer)
    for variants in ALIAS_GROUPS:
        normalized_variants = [normalize_text(v) for v in variants]
        if normalized_correct not in normalized_variants:
            continue
        normalized_user = normalize_text(user_answer)
        for variant, normalized_variant in zip(variants, normalized_variants):
            if len(normalized_variant) <= 3:
                # Short aliases ("us", "uk", "la") must match exactly so they
                # don't swallow unrelated short guesses.
                if normalized_user == normalized_variant:
                    return True
            elif match_answer(user_answer, variant, category=category, url=url,
                              config=config, skip_alias=True):
                return True
        # Correct answer belongs to this group but nothing matched; stop here.
        return False
    return False


# ---------------------------------------------------------------------------
# Fuzzy primitives
# ---------------------------------------------------------------------------

def _ratio(a, b):
    return fuzz.ratio(a, b) / 100.0


def _token_sort_ratio(a, b):
    return fuzz.token_sort_ratio(a, b) / 100.0


def _typo_cap(length, config):
    if length <= 4:
        return config.typo_caps[0]
    if length <= 8:
        return config.typo_caps[1]
    return config.typo_caps[2]


def _phonetic_equal(a, b):
    ca = [c for c in doublemetaphone(a) if c]
    cb = [c for c in doublemetaphone(b) if c]
    return any(x == y for x in ca for y in cb)


def _word_match(user_word, correct_word, config):
    """Does one guess word match one answer word (exact / typo / phonetic)?"""
    if user_word == correct_word:
        return True
    cap = _typo_cap(len(correct_word), config)
    if cap and DamerauLevenshtein.distance(user_word, correct_word) <= cap:
        return True
    if _ratio(user_word, correct_word) >= config.edit_ratio_threshold:
        # Guard: a short length gap plus prefix negation shouldn't slip through.
        if abs(len(user_word) - len(correct_word)) <= 2:
            return True
    if config.enable_phonetic and min(len(user_word), len(correct_word)) >= 4:
        if _phonetic_equal(user_word, correct_word) and \
                abs(len(user_word) - len(correct_word)) <= 2:
            return True
    return False


def _subset_coverage_match(user_sig, correct_sig, config):
    """Fraction of correct significant tokens matched by a distinct guess token."""
    if not correct_sig:
        return False
    remaining = list(user_sig)
    matched = 0
    for cw in correct_sig:
        for i, uw in enumerate(remaining):
            if _word_match(uw, cw, config):
                matched += 1
                del remaining[i]
                break
    coverage = matched / len(correct_sig)
    return coverage >= config.subset_coverage


# ---------------------------------------------------------------------------
# Free-text pipeline
# ---------------------------------------------------------------------------

def _free_text_match(user_answer, correct_answer, url, config):
    norm_user = normalize_text(user_answer)
    norm_correct = normalize_text(correct_answer)

    if not norm_user or not norm_correct:
        return False

    # Layer 1: exact normalized equality (with and without spaces).
    if norm_user == norm_correct:
        return True
    if norm_user.replace(" ", "") == norm_correct.replace(" ", ""):
        return True

    # Scramble answers must be typed exactly (letters are shuffled, so anything
    # looser would reward guessing the anagram's characters).
    if url == "scramble":
        return False

    user_sig = _significant_tokens(norm_user)
    correct_sig = _significant_tokens(norm_correct)

    # Layer 2: negation-aware content match. Can return a definitive True
    # (equivalent) or False (antonym); None means keep going.
    verdict = _negation_aware_setmatch(user_sig, correct_sig, config)
    if verdict is not None:
        return verdict

    if not config.enable_fuzzy:
        return False

    # Layer 3: whole-answer typo / phonetic tolerance.
    if _token_sort_ratio(norm_user, norm_correct) >= config.edit_ratio_threshold:
        return True
    nsu, nsc = norm_user.replace(" ", ""), norm_correct.replace(" ", "")
    cap = _typo_cap(len(nsc), config)
    if cap and DamerauLevenshtein.distance(nsu, nsc) <= cap:
        return True
    if config.enable_phonetic and " " not in norm_user and " " not in norm_correct:
        if min(len(nsu), len(nsc)) >= 4 and _phonetic_equal(nsu, nsc) \
                and abs(len(nsu) - len(nsc)) <= 2:
            return True

    # Layer 4: guarded partial match.
    if config.subset_coverage < 1.0 and _subset_coverage_match(user_sig, correct_sig, config):
        return True
    if config.allow_surname_match and len(correct_sig) >= 2:
        last = correct_sig[-1]
        if len(last) >= config.min_key_word_len and last not in GENERIC_HEAD_WORDS \
                and len(user_sig) == 1 and _word_match(user_sig[0], last, config):
            return True
    if config.allow_any_key_word and len(user_sig) == 1:
        uw = user_sig[0]
        if any(len(cw) >= config.min_key_word_len and cw not in GENERIC_HEAD_WORDS
               and _word_match(uw, cw, config)
               for cw in correct_sig):
            return True

    return False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def match_answer(user_answer, correct_answer, category="", url="",
                 config=None, skip_alias=False):
    """Return True if `user_answer` should be accepted for `correct_answer`.

    category / url select the structured checker (if any); otherwise the
    free-text pipeline runs. `config` is a MatchConfig (defaults to
    ACTIVE_CONFIG); pass STRICT for Poindexter/exact mode.
    """
    if config is None:
        config = ACTIVE_CONFIG

    if not isinstance(user_answer, str) or not isinstance(correct_answer, str):
        return False
    if not user_answer.strip() or not correct_answer.strip():
        return False

    if user_answer == correct_answer:
        return True

    if not skip_alias and _alias_match(user_answer, correct_answer, category, url, config):
        return True

    # --- structured question types (deterministic) ---
    if category == "Crossword":
        return user_answer.replace(" ", "").lower() == correct_answer.replace(" ", "").lower()
    if url == "zeroes":
        return _zeroes_checker(user_answer, correct_answer)
    if url == "derivative":
        return derivative_checker(user_answer, correct_answer)
    if url == "factors":
        return factors_checker(user_answer, correct_answer)
    if url == "trig":
        return trig_checker(user_answer, correct_answer)
    if is_number(correct_answer):
        target = correct_answer.strip()
        leading = extract_leading_number(user_answer)
        if leading is not None and leading == target:
            return True
        # Spelled-out numbers: "four" -> "4".
        folded = " ".join(_NUMBER_WORDS.get(t, t) for t in normalize_text(user_answer).split())
        leading = extract_leading_number(folded)
        return leading is not None and leading == target
    if "multiple choice" in (url or ""):
        nu, nc = normalize_text(user_answer), normalize_text(correct_answer)
        if not nu or not nc:
            return False
        if nu[0] == nc[0]:
            return True
        # Accept the choice's TEXT too ("false" for "A. False", "mercury" for
        # "B. Mercury"), not just the letter. Exact match only -- no fuzzy or
        # partial credit, since sentence-length choices overlap heavily and a
        # partial guess could match the wrong option.
        text = _choice_text(nc)
        return nu == text or nu.replace(" ", "") == text.replace(" ", "")

    # --- free text ---
    return _free_text_match(user_answer, correct_answer, url, config)
