"""Where's Okra -- hidden-object ("Where's Waldo") puzzle generation and grading.

A puzzle is a dense, crowded illustration with the okra chef mascot redrawn into it as a
native character. Players hunt for it; the first to point at it wins the round.

Two things make this harder than "generate an image and remember where you put it":

1. The mascot has to look like the same illustrator drew it. That is a *prompting*
   problem, not a compositing one -- pasting the reference PNG into the scene is the one
   failure mode that ruins the game instantly, so the reference image is used only as an
   identity reference and every prompt says so explicitly.

2. Image models do not reliably know where they put things. Whatever the generator claims
   about placement is worthless, so the finished pixels get sent to a vision model and
   *its* answer becomes the ground truth. That answer is then cross-checked against a crop
   of itself, because a confidently hallucinated bounding box would make the puzzle
   permanently unwinnable -- this box IS the answer key, so it is worth a second call.

Difficulty is expressed in the generation prompt (how small, how occluded, how camouflaged)
and then *enforced* by the validator via the bounding-box area band -- never by resizing a
finished image, which would give the mascot a different line weight than its neighbours and
reintroduce exactly the pasted-in look this module exists to avoid.

Like answer_matching.py and feud_llm_matching.py, this module is deliberately free of
discord / mongo / boto3 imports and takes its clients and generation functions by
injection, so it can be unit-tested offline (see tests/test_wheres_okra.py).

SDK note: the repo pins anthropic==0.49.0, which predates `output_config` (effort /
structured outputs). Calls here therefore use only model/max_tokens/system/messages, and
the JSON reply is parsed tolerantly rather than schema-enforced. Model IDs are passed
through as plain strings, so LOCATE_MODEL can name a model newer than the SDK.
"""

import asyncio
import base64
import io
import json
import random
import re

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

# Spatial grounding in a cluttered scene is the entire job of stage 2, so this is the one
# place worth an Opus-tier model. It runs offline while building the pool, never in a
# round, so latency is irrelevant. Thinking is on by default on Opus 5 and the pinned SDK
# does not expose an effort knob -- _first_text() below skips thinking blocks rather than
# assuming content[0] is text (which the rest of the repo does, and which would break here).
LOCATE_MODEL = "claude-opus-5"

# The crop cross-check is a much easier question ("is this thing in this small picture?"),
# so it does not need the same model. Kept separate so it can be downgraded independently.
VERIFY_MODEL = "claude-opus-5"

LOCATE_MAX_TOKENS = 2000
VERIFY_MAX_TOKENS = 1000

# Stage 1. gpt-image-1 rather than -mini: dense crowd scenes with many small consistent
# characters are exactly where the small model degrades, and pool generation is amortized
# across every replay of the puzzle.
IMAGE_MODEL = "gpt-image-1"
IMAGE_QUALITY = "high"


# ---------------------------------------------------------------------------
# Difficulty
# ---------------------------------------------------------------------------

# `area` is the fraction of the whole image the mascot's bounding box may cover, and it is
# what actually holds difficulty honest: the prompt asks for a given scale, the validator
# rejects the result if the generator ignored it. Both endpoints decrease strictly as
# difficulty rises, but adjacent bands deliberately OVERLAP: a puzzle is only ever checked
# against the band it was requested at, and slack here is what keeps the generator from
# being rejected over a few thousandths -- every rejection is another paid generation.
#
# `min_visibility` is the fairness floor. Brutal is allowed to be brutal, but a human must
# still be able to recognise the mascot once their eye lands on it -- enough of the white
# hat, the eyes, the mustache and the raised glove has to survive the occlusion.
DIFFICULTIES = {
    "easy": {
        "scale": "roughly the size of a mid-ground person",
        "occlusion": (0.00, 0.10),
        "density": "moderately busy",
        "camouflage": "low -- the surrounding palette may differ from the mascot's greens and whites",
        "grid": (6, 6),
        "area": (0.010, 0.030),
        "min_visibility": 0.75,
        "guess_time": 30,
    },
    "medium": {
        "scale": "roughly the size of a background person",
        "occlusion": (0.20, 0.30),
        "density": "dense",
        "camouflage": "moderate -- some nearby objects share the mascot's green or white tones",
        "grid": (8, 8),
        "area": (0.005, 0.015),
        "min_visibility": 0.55,
        "guess_time": 40,
    },
    "hard": {
        "scale": "roughly the size of a small background person",
        "occlusion": (0.30, 0.50),
        "density": "very dense",
        "camouflage": "strong -- the immediate surroundings repeat the mascot's green body and white hat tones",
        "grid": (10, 10),
        "area": (0.002, 0.008),
        "min_visibility": 0.40,
        "guess_time": 50,
    },
    "brutal": {
        "scale": "roughly the size of a distant background figure",
        "occlusion": (0.40, 0.60),
        "density": "extremely dense, with almost no empty space anywhere in the frame",
        "camouflage": "very strong -- the mascot sits inside a cluster of similarly coloured and similarly shaped objects",
        "grid": (12, 12),
        "area": (0.001, 0.004),
        "min_visibility": 0.28,
        "guess_time": 60,
    },
}

DIFFICULTY_ORDER = ["easy", "medium", "hard", "brutal"]

# Minimum confidence the locator must report before its box is trusted as ground truth.
MIN_CONFIDENCE = 0.80


# ---------------------------------------------------------------------------
# Scenes and placement
# ---------------------------------------------------------------------------

THEMES = [
    "a night market with food stalls and paper lanterns",
    "a crowded water park with slides and wave pools",
    "a grand railway station concourse at rush hour",
    "an autumn harvest fair with hay bales and livestock pens",
    "a ski resort base village with lifts and lodges",
    "a public aquarium with tanks and school groups",
    "a city marathon passing through a downtown crossroads",
    "an airport terminal with check-in queues and gate lounges",
    "a medieval castle siege with tents and siege engines",
    "a beach boardwalk with arcades and fairground rides",
    "a botanical glasshouse with tour groups and plant stalls",
    "a busy hospital atrium with clinics and a cafe",
    "a rooftop new year street party across several buildings",
    "a construction site for a stadium, mid-build",
    "a university open day quad with club stalls",
    "a fishing harbour with trawlers and a morning fish market",
    "a natural history museum hall with skeletons and school tours",
    "a desert music festival with stages and camping",
    "an alpine mountain rescue training exercise",
    "a floating market of boats on a wide canal",
]

# 3x3 placement regions. The centre is deliberately down-weighted and the previously used
# region is excluded, so a pool of puzzles does not quietly cluster the mascot in the
# middle of the frame the way an unguided generator does.
REGIONS = [
    "the upper-left region", "the upper-centre region", "the upper-right region",
    "the mid-left region", "the exact centre of the frame", "the mid-right region",
    "the lower-left region", "the lower-centre region", "the lower-right region",
]
_CENTRE_REGION_INDEX = 4
_CENTRE_WEIGHT = 0.35


def pick_region(rng, exclude=None):
    """Choose a placement region, biased away from the centre and away from `exclude`.

    `exclude` is the region string used by the previous puzzle in this batch; passing it
    keeps consecutive puzzles from reusing the same corner.
    """
    weights = []
    for i, region in enumerate(REGIONS):
        if region == exclude:
            weights.append(0.0)
        elif i == _CENTRE_REGION_INDEX:
            weights.append(_CENTRE_WEIGHT)
        else:
            weights.append(1.0)
    if not any(weights):  # every region excluded (only possible with a 1-region list)
        weights = [1.0] * len(REGIONS)
    return rng.choices(REGIONS, weights=weights, k=1)[0]


def pick_theme(rng, exclude=None):
    choices = [t for t in THEMES if t != exclude] or list(THEMES)
    return rng.choice(choices)


# ---------------------------------------------------------------------------
# Stage 1 -- the generation prompt
# ---------------------------------------------------------------------------

# The clause that does the real work. Everything here is aimed at one failure mode: a
# mascot that reads as pasted on top of the scene rather than drawn as part of it.
_INTEGRATION_CLAUSE = (
    "Redraw the supplied mascot as a native character within this illustration. Do not "
    "paste, composite, overlay, or copy the original artwork; the supplied image is an "
    "identity reference for ONE character only, and you must draw a completely new full "
    "scene around a newly drawn version of that character. Match the surrounding "
    "characters' illustration style, line quality and line weight, outline treatment, "
    "shading, texture, lighting direction, perspective, colour saturation and level of "
    "detail exactly. Partially obscure the character and integrate it naturally into a "
    "visually busy cluster."
)

_IDENTITY_CLAUSE = (
    "The mascot must remain recognisable: a green okra pod for a body, a tall white chef's "
    "hat, large expressive eyes, a smiling mouth beneath a dark mustache, white gloves, and "
    "one hand raised in a gesture. Exactly ONE such okra character appears in the entire "
    "image. No other okra, and no other chef-hatted vegetable, anywhere in the scene."
)

_NEGATIVE_CLAUSE = (
    "Do not draw any text, letters, numbers, arrows, circles, outlines, labels, callouts, "
    "highlights, spotlights or markers indicating where the character is. The character "
    "must not have a glow, halo, drop shadow, rectangular backing, or any clean empty space "
    "around it, and must not be drawn with sharper linework, higher contrast or more detail "
    "than the characters beside it."
)


def build_puzzle_prompt(theme, difficulty, region):
    """Compose the stage-1 image prompt.

    Difficulty is expressed here, in the prompt, and nowhere else -- a finished image is
    never resized to hit a difficulty band (see the module docstring).
    """
    spec = DIFFICULTIES[difficulty]
    occ_lo, occ_hi = spec["occlusion"]
    return (
        f"A single-scene hidden-object puzzle illustration of {theme}, drawn in a "
        f"consistent flat cartoon style with clean uniform linework, in the manner of a "
        f"'find the character' children's puzzle book. The scene is {spec['density']}: it "
        f"is packed with many small characters going about separate little activities, "
        f"plus animals, vehicles, market stalls, signage, banners, crates, tools, food, "
        f"luggage and scattered props. Every character is drawn at the same level of "
        f"detail and with the same line weight as every other character. Wide establishing "
        f"view, even ambient lighting, no single focal point.\n\n"
        f"{_INTEGRATION_CLAUSE}\n\n"
        f"{_IDENTITY_CLAUSE}\n\n"
        f"Place the okra character in {region}, drawn at {spec['scale']} relative to the "
        f"rest of the scene. Approximately {int(occ_lo * 100)}-{int(occ_hi * 100)}% of the "
        f"character is hidden behind objects or other characters in front of it. Visual "
        f"camouflage: {spec['camouflage']}. Enough of the hat, face and raised glove must "
        f"stay visible for an attentive person to recognise the character once they look "
        f"directly at it.\n\n"
        f"{_NEGATIVE_CLAUSE}"
    )


def describe_mascot_for_text_prompt():
    """Textual mascot description, for the no-reference-image fallback path.

    Used when the edit endpoint keeps transforming the reference instead of treating it as
    an identity reference (see build_validated_puzzle).
    """
    return (
        "a cartoon okra mascot: a tall slender green okra pod standing upright as a body, "
        "with a tall white chef's hat, large white eyes with dark pupils, a wide smile "
        "under a dark curled mustache, white cartoon gloves, and one gloved hand raised"
    )


# ---------------------------------------------------------------------------
# Stage 2 -- the locator prompt
# ---------------------------------------------------------------------------

_LOCATE_SYSTEM = """You are a precise visual localisation tool for a hidden-object puzzle game.

You receive two images. The FIRST is a reference picture of a mascot character. The SECOND \
is a busy puzzle illustration that should contain exactly one redrawn version of that \
mascot, hidden among many other characters and objects.

Find the mascot in the SECOND image. Identify it by its combination of features -- a green \
okra pod body, a tall white chef's hat, large eyes, a smile with a mustache, white gloves, \
a raised hand -- not by colour alone; the scene deliberately contains other green objects \
and other white hats as decoys.

Report its bounding box in NORMALISED coordinates from 0 to 1, where (0,0) is the TOP-LEFT \
corner of the second image and (1,1) is the bottom-right. xMin/yMin are the top-left of the \
box and xMax/yMax the bottom-right. Make the box tight around the visible extent of the \
character.

Also report:
- targetCount: how many distinct okra-mascot characters you can find in the second image. \
This must be 1 for a valid puzzle. Report 0 if you cannot find it at all, or 2+ if the \
generator mistakenly drew several.
- confidence: 0 to 1, how certain you are that the box contains the mascot.
- visibility: 0 to 1, how much of the character is unobscured and readable. 1.0 means fully \
visible, 0.3 means only a small fraction peeks out from behind other objects.
- tooObvious: true if the character stands out immediately -- it is much larger than nearby \
characters, sits in open empty space, has a halo or a backing shape, or is drawn with \
crisper linework or higher contrast than its neighbours. These are the signs it was pasted \
in rather than drawn in.
- malformed: true if the character is drawn incorrectly enough to be unrecognisable or is \
missing its defining features (no chef hat, not green, no face).

Answer only with a single JSON object, no prose and no code fence:
{"targetCount": <int>, "boundingBox": {"xMin": <float>, "yMin": <float>, "xMax": <float>, \
"yMax": <float>}, "confidence": <float>, "visibility": <float>, "tooObvious": <bool>, \
"malformed": <bool>}

If targetCount is 0, still emit the object with a zeroed boundingBox."""


_VERIFY_SYSTEM = """You verify a single crop from a hidden-object puzzle.

The FIRST image is a reference picture of a mascot character. The SECOND image is a small \
crop taken from a larger puzzle illustration.

Answer whether the mascot from the first image is present in the crop. It may be partially \
hidden behind other objects, and it will be redrawn in a different illustration style -- \
judge by its identifying features (green okra pod body, tall white chef's hat, large eyes, \
mustache and smile, white gloves, raised hand), not by style similarity.

Be strict. A merely green object, or a merely white hat, is not the mascot.

Answer only with a single JSON object, no prose and no code fence:
{"present": <bool>, "confidence": <float>}"""


# ---------------------------------------------------------------------------
# Geometry (pure)
# ---------------------------------------------------------------------------

# Padding added around the target box when testing a guess. Chat grid guesses are already
# coarse so they need almost none; a finger on a phone screen needs considerably more.
HIT_TOLERANCE = 0.015
TAP_TOLERANCE = 0.035

_GRID_RE = re.compile(r"^\s*([A-Za-z]{1,2})\s*[-_, ]?\s*(\d{1,2})\s*$")
_CLICK_RE = re.compile(r"^\s*click\s*:\s*(-?\d*\.?\d+)\s*,\s*(-?\d*\.?\d+)\s*$", re.IGNORECASE)


def column_label(index):
    """0 -> 'A', 25 -> 'Z', 26 -> 'AA'. Grids never get near AA, but the round-trip with
    parse_grid_guess should not quietly break if one ever does."""
    label = ""
    index += 1
    while index > 0:
        index, rem = divmod(index - 1, 26)
        label = chr(ord("A") + rem) + label
    return label


def column_index(label):
    """Inverse of column_label. Returns None for anything unparseable."""
    label = label.strip().upper()
    if not label or not label.isalpha():
        return None
    index = 0
    for ch in label:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return index - 1


def parse_grid_guess(text, cols, rows):
    """Parse a player's grid guess ("F7", "f-7", "f 7") into a 0-based (col, row).

    Returns None if it does not look like a grid reference at all, or if it names a cell
    outside the grid. Both cases are treated the same by the caller: not a guess, ignore it
    and keep waiting. That matters because the guess channel is open-floor chat, where most
    messages are ordinary conversation rather than attempts at an answer.
    """
    if not isinstance(text, str):
        return None
    match = _GRID_RE.match(text)
    if not match:
        return None
    col = column_index(match.group(1))
    if col is None or not 0 <= col < cols:
        return None
    row = int(match.group(2)) - 1
    if not 0 <= row < rows:
        return None
    return col, row


def grid_cell_rect(col, row, cols, rows):
    """The normalised rectangle covered by one grid cell, as (xMin, yMin, xMax, yMax)."""
    return (col / cols, row / rows, (col + 1) / cols, (row + 1) / rows)


def grid_label_to_rect(label, cols, rows):
    """Convenience wrapper: "F7" -> its normalised rectangle, or None."""
    parsed = parse_grid_guess(label, cols, rows)
    if parsed is None:
        return None
    return grid_cell_rect(parsed[0], parsed[1], cols, rows)


def parse_click(text):
    """Parse an Activity tap payload ("click:0.6312,0.7104") into (x, y).

    Returns None for anything malformed or out of the unit square. The bot only ever
    accepts this form from a companion/Activity submission, never from a typed Discord
    message -- otherwise players could brute-force the target by pasting coordinates into
    chat.
    """
    if not isinstance(text, str):
        return None
    match = _CLICK_RE.match(text)
    if not match:
        return None
    try:
        x = float(match.group(1))
        y = float(match.group(2))
    except ValueError:
        return None
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        return None
    return x, y


def normalize_target(target):
    """Coerce a stored target dict into an ordered (xMin, yMin, xMax, yMax) tuple.

    Swaps inverted edges rather than rejecting them: a locator that returns xMax < xMin has
    still told us where the mascot is, and the box is the answer key -- salvaging it beats
    discarding an otherwise good puzzle.
    """
    if target is None:
        return None
    if isinstance(target, dict):
        try:
            values = (float(target["xMin"]), float(target["yMin"]),
                      float(target["xMax"]), float(target["yMax"]))
        except (KeyError, TypeError, ValueError):
            return None
    else:
        try:
            values = tuple(float(v) for v in target)
        except (TypeError, ValueError):
            return None
        if len(values) != 4:
            return None
    x_min, y_min, x_max, y_max = values
    if x_min > x_max:
        x_min, x_max = x_max, x_min
    if y_min > y_max:
        y_min, y_max = y_max, y_min
    return x_min, y_min, x_max, y_max


def bbox_area(target):
    """Fraction of the image covered by the target box. 0.0 for an unusable box."""
    box = normalize_target(target)
    if box is None:
        return 0.0
    x_min, y_min, x_max, y_max = box
    return max(0.0, x_max - x_min) * max(0.0, y_max - y_min)


def hit_test(x, y, target, tolerance=HIT_TOLERANCE):
    """Is the normalised point (x, y) inside the target box, allowing `tolerance` padding?"""
    box = normalize_target(target)
    if box is None:
        return False
    x_min, y_min, x_max, y_max = box
    return (x_min - tolerance <= x <= x_max + tolerance
            and y_min - tolerance <= y <= y_max + tolerance)


def rect_intersects(rect, target, tolerance=0.0):
    """Does a rectangle overlap the target box? Used for grid-cell guesses.

    A cell counts as correct if any part of it overlaps the mascot, so a mascot straddling
    a cell boundary can be found from either side -- the alternative (requiring the box
    centre) makes straddling puzzles feel arbitrary and unfair.
    """
    box = normalize_target(target)
    other = normalize_target(rect)
    if box is None or other is None:
        return False
    x_min, y_min, x_max, y_max = box
    rx_min, ry_min, rx_max, ry_max = other
    return not (rx_max < x_min - tolerance or rx_min > x_max + tolerance
                or ry_max < y_min - tolerance or ry_min > y_max + tolerance)


def target_grid_label(target, cols, rows):
    """The grid label of the cell containing the target's centre. For the reveal message."""
    box = normalize_target(target)
    if box is None:
        return None
    x_min, y_min, x_max, y_max = box
    cx = min(max((x_min + x_max) / 2.0, 0.0), 0.999999)
    cy = min(max((y_min + y_max) / 2.0, 0.0), 0.999999)
    return f"{column_label(int(cx * cols))}{int(cy * rows) + 1}"


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

class ValidationResult:
    """Ground truth for one puzzle, as reported by the vision pass.

    Deliberately a plain class rather than a dataclass so it round-trips cleanly through
    the Mongo document shape without importing anything.
    """

    __slots__ = ("target_count", "target", "confidence", "visibility",
                 "too_obvious", "malformed", "raw")

    def __init__(self, target_count=0, target=None, confidence=0.0, visibility=0.0,
                 too_obvious=False, malformed=False, raw=None):
        self.target_count = target_count
        self.target = target
        self.confidence = confidence
        self.visibility = visibility
        self.too_obvious = too_obvious
        self.malformed = malformed
        self.raw = raw

    def to_dict(self):
        box = normalize_target(self.target)
        return {
            "targetCount": self.target_count,
            "boundingBox": None if box is None else {
                "xMin": box[0], "yMin": box[1], "xMax": box[2], "yMax": box[3],
            },
            "confidence": self.confidence,
            "visibility": self.visibility,
            "tooObvious": self.too_obvious,
            "malformed": self.malformed,
        }

    def __repr__(self):
        return f"<ValidationResult {self.to_dict()}>"


class PuzzleGenerationError(Exception):
    """No acceptable puzzle could be produced. Raised only after every attempt failed."""


def _coerce_float(value, default=0.0):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if result != result:  # NaN
        return default
    return result


def _coerce_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "yes", "1"):
            return True
        if lowered in ("false", "no", "0"):
            return False
    return default


def _extract_json_object(raw):
    """Pull the first balanced {...} out of a model reply.

    The pinned SDK has no structured-output support, so the reply is plain text and may
    arrive wrapped in a code fence or trailed by a sentence of commentary despite the
    instruction not to. Scanning for a balanced object handles both without a regex that
    would trip over the nested boundingBox.
    """
    if not raw or not isinstance(raw, str):
        return None
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def parse_validation(raw):
    """Turn a locator reply into a ValidationResult. Never raises.

    An unparseable reply becomes a zero-confidence, zero-target result, which `validate`
    then rejects -- "the model said something we could not read" and "the model said the
    mascot is missing" both mean regenerate, so they do not need to be distinguished.
    """
    payload = _extract_json_object(raw)
    if not isinstance(payload, dict):
        return ValidationResult(raw=raw)

    count = payload.get("targetCount")
    if isinstance(count, bool) or not isinstance(count, int):
        count = int(_coerce_float(count, 0))

    box = payload.get("boundingBox")
    target = normalize_target(box) if isinstance(box, (dict, list, tuple)) else None

    return ValidationResult(
        target_count=count,
        target=target,
        confidence=_coerce_float(payload.get("confidence")),
        visibility=_coerce_float(payload.get("visibility")),
        too_obvious=_coerce_bool(payload.get("tooObvious")),
        malformed=_coerce_bool(payload.get("malformed")),
        raw=raw,
    )


def validate(result, difficulty):
    """Decide whether a located puzzle is usable. Returns (ok, reasons).

    `reasons` is a list of short strings naming every failure, not just the first, so the
    pool builder's log says *why* a batch is being rejected -- if every rejection is
    "area_too_large", the reference image is being transformed rather than used as an
    identity reference, which is a prompt problem rather than bad luck.
    """
    spec = DIFFICULTIES[difficulty]
    reasons = []

    if result.target_count != 1:
        reasons.append(f"target_count={result.target_count}")
    if result.malformed:
        reasons.append("malformed")
    if result.too_obvious:
        reasons.append("too_obvious")

    box = normalize_target(result.target)
    if box is None:
        reasons.append("no_bounding_box")
    else:
        x_min, y_min, x_max, y_max = box
        if not (0.0 <= x_min < x_max <= 1.0 and 0.0 <= y_min < y_max <= 1.0):
            reasons.append("bounding_box_out_of_range")
        else:
            area = bbox_area(box)
            lo, hi = spec["area"]
            if area < lo:
                reasons.append(f"area_too_small={area:.5f}<{lo}")
            elif area > hi:
                reasons.append(f"area_too_large={area:.5f}>{hi}")

    if result.confidence < MIN_CONFIDENCE:
        reasons.append(f"low_confidence={result.confidence:.2f}")
    if result.visibility < spec["min_visibility"]:
        reasons.append(f"low_visibility={result.visibility:.2f}<{spec['min_visibility']}")

    return (not reasons), reasons


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def _b64(data):
    return base64.b64encode(data).decode()


def _image_block(data, media_type="image/png"):
    return {"type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": _b64(data)}}


def _first_text(response):
    """Concatenate the text blocks of an Anthropic response.

    The rest of the repo reads `response.content[0].text`, which is only safe on a model
    with thinking off. LOCATE_MODEL has thinking on by default, so content[0] is a
    thinking block and that indexing would raise -- iterate and keep the text instead.
    """
    parts = []
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", "") or "")
    return "".join(parts).strip()


def crop_to_bytes(image_bytes, target, margin=0.25, min_side=192):
    """Crop `image_bytes` to the target box plus a relative margin, as PNG bytes.

    The margin gives the verifier enough surrounding context to judge whether the thing in
    the box is really the mascot rather than a lone green smudge; `min_side` keeps a very
    small brutal-difficulty crop from arriving as an unreadable handful of pixels.

    PIL is imported lazily so the pure-geometry half of this module stays importable
    without it (the offline tests exercise the geometry without ever touching an image).
    """
    from PIL import Image

    box = normalize_target(target)
    if box is None:
        return None
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        width, height = img.size
        x_min, y_min, x_max, y_max = box
        pad_x = (x_max - x_min) * margin
        pad_y = (y_max - y_min) * margin
        left = int(max(0.0, x_min - pad_x) * width)
        top = int(max(0.0, y_min - pad_y) * height)
        right = int(min(1.0, x_max + pad_x) * width)
        bottom = int(min(1.0, y_max + pad_y) * height)
        if right <= left or bottom <= top:
            return None
        crop = img.crop((left, top, right, bottom))
        if crop.width < min_side or crop.height < min_side:
            scale = max(min_side / crop.width, min_side / crop.height)
            crop = crop.resize((int(crop.width * scale), int(crop.height * scale)),
                               Image.LANCZOS)
        buffer = io.BytesIO()
        crop.save(buffer, format="PNG")
        return buffer.getvalue()


# ---------------------------------------------------------------------------
# Stage 2 -- the calls
# ---------------------------------------------------------------------------

async def locate_mascot(client, puzzle_bytes, mascot_bytes, *,
                        model=LOCATE_MODEL, max_tokens=LOCATE_MAX_TOKENS, timeout=180):
    """Locate the mascot in a finished puzzle. Returns a ValidationResult.

    The reference image goes first and the puzzle second, matching the order the system
    prompt describes. Failures come back as a zero result rather than an exception so the
    retry loop treats "the API broke" the same as "the mascot isn't there" -- both mean
    throw this image away.
    """
    if client is None:
        raise PuzzleGenerationError("No vision client configured (ANTHROPIC_API_KEY unset).")
    try:
        response = await asyncio.wait_for(
            client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": _LOCATE_SYSTEM}],
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": "Reference mascot:"},
                    _image_block(mascot_bytes),
                    {"type": "text", "text": "Puzzle image to search:"},
                    _image_block(puzzle_bytes),
                ]}],
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return ValidationResult(raw="<timeout>")
    except Exception as exc:  # noqa: BLE001 -- surfaced through `raw` for the ops log
        return ValidationResult(raw=f"<error: {exc}>")

    return parse_validation(_first_text(response))


async def verify_crop(client, crop_bytes, mascot_bytes, *,
                      model=VERIFY_MODEL, max_tokens=VERIFY_MAX_TOKENS, timeout=120):
    """Second opinion on a crop of the located box. Returns (present, confidence).

    This exists because the located box becomes the permanent answer key. A hallucinated
    box would not fail any of `validate`'s checks -- the model would happily report high
    confidence about a spot with nothing in it -- and the puzzle would then be unwinnable
    for every player who ever sees it. Asking a much easier question about a much smaller
    image catches that cheaply.
    """
    if client is None:
        raise PuzzleGenerationError("No vision client configured (ANTHROPIC_API_KEY unset).")
    if not crop_bytes:
        return False, 0.0
    try:
        response = await asyncio.wait_for(
            client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": _VERIFY_SYSTEM}],
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": "Reference mascot:"},
                    _image_block(mascot_bytes),
                    {"type": "text", "text": "Crop to check:"},
                    _image_block(crop_bytes),
                ]}],
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return False, 0.0
    except Exception:  # noqa: BLE001 -- a failed cross-check must reject, never crash
        return False, 0.0

    payload = _extract_json_object(_first_text(response))
    if not isinstance(payload, dict):
        return False, 0.0
    return _coerce_bool(payload.get("present")), _coerce_float(payload.get("confidence"))


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------

# If this many consecutive attempts are rejected specifically for an oversized box, the
# edit endpoint is transforming the reference image into the subject of the picture rather
# than treating it as an identity reference. Switching to the text-to-image path (which
# describes the mascot in words instead of supplying it) reliably recovers from that.
_OVERSIZE_STRIKES_BEFORE_FALLBACK = 2

MIN_VERIFY_CONFIDENCE = 0.60


async def build_validated_puzzle(*, edit_fn, generate_fn, vision_client, mascot_bytes,
                                 theme, difficulty, region, max_attempts=4,
                                 use_reference=True, on_attempt=None):
    """Generate and validate one puzzle. Returns (image_bytes, ValidationResult, meta).

    `edit_fn(mascot_bytes, prompt) -> bytes` and `generate_fn(prompt) -> bytes` are async
    callables already bound to a provider/model/quality by the caller, which is what keeps
    this module free of the bot's image plumbing.

    `on_attempt(index, ok, reasons)`, if given, is called after each attempt so an ops
    script can stream progress.

    Raises PuzzleGenerationError if no attempt produced an acceptable puzzle.
    """
    if difficulty not in DIFFICULTIES:
        raise PuzzleGenerationError(f"Unknown difficulty {difficulty!r}")

    prompt = build_puzzle_prompt(theme, difficulty, region)
    fallback_prompt = prompt.replace(
        _INTEGRATION_CLAUSE,
        "Draw into the scene, as one of its native characters, "
        + describe_mascot_for_text_prompt()
        + ". Draw it in exactly the same illustration style, line weight, shading and level "
        "of detail as every other character in the scene, and partially obscure it inside a "
        "visually busy cluster.",
    )

    attempts = []
    oversize_streak = 0
    using_reference = use_reference

    for index in range(1, max_attempts + 1):
        active_prompt = prompt if using_reference else fallback_prompt
        try:
            if using_reference:
                image_bytes = await edit_fn(mascot_bytes, active_prompt)
            else:
                image_bytes = await generate_fn(active_prompt)
        except Exception as exc:  # noqa: BLE001 -- one bad generation shouldn't end the run
            attempts.append({"attempt": index, "ok": False,
                             "reasons": [f"generation_failed: {exc}"],
                             "used_reference": using_reference})
            if on_attempt:
                on_attempt(index, False, [f"generation_failed: {exc}"])
            continue

        result = await locate_mascot(vision_client, image_bytes, mascot_bytes)
        ok, reasons = validate(result, difficulty)

        # Only worth cross-checking a box that already passed everything else.
        if ok:
            crop = crop_to_bytes(image_bytes, result.target)
            present, verify_confidence = await verify_crop(
                vision_client, crop, mascot_bytes)
            if not present or verify_confidence < MIN_VERIFY_CONFIDENCE:
                ok = False
                reasons.append(f"crop_check_failed(present={present}, "
                               f"confidence={verify_confidence:.2f})")

        attempts.append({"attempt": index, "ok": ok, "reasons": list(reasons),
                         "used_reference": using_reference})
        if on_attempt:
            on_attempt(index, ok, reasons)

        if ok:
            meta = {
                "prompt": active_prompt,
                "attempts": index,
                "attempt_log": attempts,
                "used_reference": using_reference,
                "image_model": IMAGE_MODEL,
                "image_quality": IMAGE_QUALITY,
                "vision_model": LOCATE_MODEL,
                "verify_model": VERIFY_MODEL,
                "verify_confidence": verify_confidence,
            }
            return image_bytes, result, meta

        if any(r.startswith("area_too_large") for r in reasons):
            oversize_streak += 1
            if using_reference and oversize_streak >= _OVERSIZE_STRIKES_BEFORE_FALLBACK:
                using_reference = False
        else:
            oversize_streak = 0

    summary = "; ".join(
        f"#{a['attempt']}: {', '.join(a['reasons']) or 'ok'}" for a in attempts)
    raise PuzzleGenerationError(
        f"No valid puzzle after {max_attempts} attempts ({difficulty}, {theme}) -- {summary}")


# ---------------------------------------------------------------------------
# Round-time grading (pure)
# ---------------------------------------------------------------------------

def grade_submission(text, target, cols, rows, *, allow_click):
    """Grade one player submission against the secret target.

    Returns (kind, correct) where kind is "grid", "click" or None. A None kind means the
    message was not an attempt at an answer at all -- ordinary chat in an open-floor
    channel -- and the caller should keep waiting rather than counting a wrong guess.

    `allow_click` must be True only for companion/Activity submissions. A click payload
    typed into Discord chat is rejected outright: coordinates are far finer-grained than
    the grid, so accepting them from chat would let a player brute-force the target.
    """
    click = parse_click(text)
    if click is not None:
        if not allow_click:
            return None, False
        return "click", hit_test(click[0], click[1], target, TAP_TOLERANCE)

    cell = parse_grid_guess(text, cols, rows)
    if cell is not None:
        rect = grid_cell_rect(cell[0], cell[1], cols, rows)
        return "grid", rect_intersects(rect, target)

    return None, False


def make_rng(seed=None):
    """A local Random, so puzzle selection in tests is reproducible without touching the
    global random module the rest of the bot shares."""
    return random.Random(seed)
