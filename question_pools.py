"""Registry of minigame-exclusive question pools folded into the main trivia rotation.

Each pool's documents are sampled directly from their own MongoDB collection -- never
copied into trivia_questions -- so a moderator's correction (via ApplyFlaggedModal or the
manual-edit modal in discordbot.py) always lands on the one real document, regardless of
whether it was flagged from a /arena minigame, Continuous Trivia, or Simply Trivia. This
mirrors the existing pattern already used for crossword_questions/jeopardy_questions/
wof_questions/mysterybox_questions.

Every pool, and every variant within a pool that has more than one question framing,
carries an `enabled` flag and a `weight`. `pick_variant()` does a weighted random choice
among the *enabled* variants -- equal weights (the default) reproduce plain uniform-random.
Turning a variant off, or biasing it, is a one-line edit here; no logic changes needed.
A pool's own `enabled`/`weight` (read by select_trivia_questions()/get_trivia_question() in
discordbot.py/simply_trivia.py, not by anything in this file) works the same way one level up.

`adapter(doc)` returns a dict with the category/question/url/answers keys that need
overriding on the sampled doc -- applied once, right after sampling, mutating the doc in
place before it's turned into the final (category, question, url, answers, db, _id, paragraph)
tuple. The document itself is never rewritten in Mongo.
"""

import random
import re

# How many documents from any one collection (trivia_questions included) enter the combined
# pool before the final round-sized $sample draws from it -- see select_trivia_questions()
# in discordbot.py. A pool's "weight" scales this cap up or down for that pool specifically.
PER_POOL_SAMPLE_CAP = 2000


def pick_variant(variants):
    enabled = {name: cfg for name, cfg in variants.items() if cfg.get("enabled", True)}
    if not enabled:
        raise ValueError(f"No enabled variants among: {list(variants.keys())}")
    names = list(enabled.keys())
    weights = [enabled[name].get("weight", 1) for name in names]
    return random.choices(names, weights=weights, k=1)[0]


def render_sports_logos(doc):
    """sports_logos_questions: {league, image_url, team_location_college, team_nickname,
    team_alternative_name}. Mirrors ask_sports_logos_challenge's own modes 1-3 exactly
    (mode 4, "guess the league", isn't a fit here -- that's a different kind of question)."""
    variant = pick_variant(QUESTION_POOLS["sports_logos"]["variants"])
    location = doc.get("team_location_college", "")
    nickname = doc["team_nickname"]
    alt_name = doc.get("team_alternative_name", "")
    full_name = f"{location} {nickname}".strip() if location else nickname
    league = doc.get("league", "")

    if variant == "location":
        question = "🎓 Name the **COLLEGE or UNIVERSITY**!" if league == "NCAA" else "📍 Name the **TEAM'S LOCATION**!"
        answers = [a for a in [location, alt_name] if a]
    elif variant == "mascot":
        question = "🦅 Name the **TEAM NICKNAME**!"
        answers = [nickname]
    else:  # either
        question = "🏆 Name the **TEAM** (Location OR Nickname)!"
        answers = [a for a in [location, nickname, alt_name, full_name] if a]

    return {
        "category": f"Sports Logos: {league}" if league else "Sports Logos",
        "question": question,
        "url": doc["image_url"],
        "answers": answers,
    }


def render_president(doc):
    """president_questions: {name, url, year_start_1, year_end_1, year_start_2, year_end_2}.
    year_start_2/year_end_2 are falsy for single-term presidents (see ask_president_challenge's
    own `y2_start and ...` check). Both variants work on every doc regardless of its native
    `type` field ("years"/"odd_duck") -- that field only matters to the standalone minigame's
    own two modes, which aren't reproduced here as-is (odd_duck needs two extra fetched
    portraits and is a different kind of puzzle, not "who is this")."""
    variant = pick_variant(QUESTION_POOLS["president"]["variants"])
    name = doc["name"]
    url = doc.get("url", "")

    if variant == "year_served":
        years = [str(y) for y in range(int(doc["year_start_1"]), int(doc["year_end_1"]) + 1)]
        if doc.get("year_start_2"):
            years += [str(y) for y in range(int(doc["year_start_2"]), int(doc["year_end_2"]) + 1)]
        return {
            "category": "Presidents",
            "question": f"📅 Name a **YEAR** during President {name}'s time in office.",
            "url": url,
            "answers": years,
        }

    return {
        "category": "Presidents",
        "question": "🦅🇺🇸 Who is this President?",
        "url": url,
        "answers": [name],
    }


def render_element(doc):
    """element_questions (question_type=="single", hypothetical=="No"): {name, symbol}.
    Deliberately plain text -- the minigame's "single" image is a periodic-table highlight
    rendered on the fly via highlight_element() (Pillow, no stored URL), which would need new
    render-time image-generation machinery for a cosmetic upgrade only; the ticker-symbol-style
    plain-text question is still fully valid trivia on its own."""
    variant = pick_variant(QUESTION_POOLS["element"]["variants"])
    name = doc["name"]
    symbol = doc["symbol"]

    if variant == "name_from_symbol":
        question, answers = f"Which element has the symbol **{symbol}**?", [name]
    else:  # symbol_from_name
        question, answers = f"What is the chemical symbol for **{name}**?", [symbol]

    return {"category": "Elements", "question": question, "url": "", "answers": answers}


def render_geokraphy(doc):
    """border_questions: {country, capital, currency, primary_language, neighbours, flag_url,
    image_urls}. Two independent axes (image, question) rather than the paired branches in
    discordbot.py's own _geokraphy_round_content() -- that function always pairs one specific
    image with one specific question per branch, which doesn't allow e.g. a flag shown while
    asking for the capital. "text_clue" (no image, neighbor list as the clue) always implies
    question="country" -- that's its only mechanic, matching Borderline's old "Okrap" mode."""
    pool_cfg = QUESTION_POOLS["geokraphy"]
    country = doc["country"]
    image_variant = pick_variant(pool_cfg["image_variants"])

    if image_variant == "text_clue":
        return {
            "category": "Geography",
            "question": f"🚧 Name the country!\n\n**Neighbors**: {doc['neighbours']}",
            "url": "",
            "answers": [country],
        }

    if image_variant == "flag":
        image_url = doc.get("flag_url", "")
    else:  # map/landmark
        landmark_images = list(doc.get("image_urls") or [])
        image_url = random.choice(landmark_images) if landmark_images else doc.get("flag_url", "")

    question_variant = pick_variant(pool_cfg["question_variants"])
    if question_variant == "country":
        prompt, answers = "🗺️ Which country is this?", [country]
    elif question_variant == "capital":
        prompt, answers = "🏛️ What's the capital of this country?", [doc["capital"]]
    elif question_variant == "currency":
        raw = doc["currency"]
        name_part = raw.split("(")[0].strip()
        code_match = re.search(r"\(([^)]+)\)", raw)
        answers = [name_part] + ([code_match.group(1)] if code_match else [])
        prompt = "💰 What currency does this country use?"
    elif question_variant == "language":
        prompt, answers = "🗣️ What's the most commonly spoken language in this country?", [doc["primary_language"]]
    else:  # neighbor
        prompt = "🧭 Name ONE country that borders this country!"
        answers = [n.strip() for n in doc["neighbours"].split(",") if n.strip()]

    return {"category": "Geography", "question": prompt, "url": image_url, "answers": answers}


QUESTION_POOLS = {
    "sports_logos": {
        "collection": "sports_logos_questions", "id_limit_key": "sports_logos",
        "adapter": render_sports_logos, "enabled": True, "weight": 1,
        "variants": {
            "location": {"enabled": True, "weight": 1},  # "Which city/location is this team from?"
            "mascot":   {"enabled": True, "weight": 1},  # "What's this team's mascot/nickname?"
            "either":   {"enabled": True, "weight": 1},  # "Which team is this?" -- location or mascot both accepted
        },
    },
    "president": {
        "collection": "president_questions", "id_limit_key": "president",
        "adapter": render_president, "enabled": True, "weight": 1,
        "variants": {
            "year_served": {"enabled": True, "weight": 1},  # "Name a year President X served"
            "who_is_this": {"enabled": True, "weight": 1},  # "Who is this President?"
        },
    },
    "element": {
        "collection": "element_questions", "id_limit_key": "element",
        "adapter": render_element, "enabled": True, "weight": 1,
        "variants": {
            "name_from_symbol": {"enabled": True, "weight": 1},  # symbol shown -> name element
            "symbol_from_name": {"enabled": True, "weight": 1},  # name shown -> give the symbol
        },
    },
    "geokraphy": {
        "collection": "border_questions", "id_limit_key": "geokraphy",
        "adapter": render_geokraphy, "enabled": True, "weight": 1,
        # Two independent axes: which image is shown, and what's actually being asked.
        # "text_clue" always forces question="country" (see render_geokraphy) -- it doesn't
        # cross with the question axis below.
        "image_variants": {
            "flag":      {"enabled": True, "weight": 1},  # doc["flag_url"]
            "map":       {"enabled": True, "weight": 1},  # doc["image_urls"] -- landmark/photo
            "text_clue": {"enabled": True, "weight": 1},  # no image; doc["neighbours"] shown as the clue text
        },
        "question_variants": {
            "country":  {"enabled": True, "weight": 1},
            "capital":  {"enabled": True, "weight": 1},
            "currency": {"enabled": True, "weight": 1},
            "language": {"enabled": True, "weight": 1},
            "neighbor": {"enabled": True, "weight": 1},  # name any one bordering country
        },
    },
}
