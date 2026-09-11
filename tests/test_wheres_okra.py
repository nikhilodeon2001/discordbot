"""Golden corpus for wheres_okra.

Two tiers.

    ./.venv/bin/python tests/test_wheres_okra.py

runs the offline tier only: coordinate geometry, guess parsing, locator-reply parsing,
difficulty validation, prompt construction, and the generate/validate retry loop driven by
fake clients. No network, no API key, no cost.

    ./.venv/bin/python tests/test_wheres_okra.py --live [--difficulty hard] [--count 1]

additionally generates real puzzles end to end against the real image and vision APIs and
prints accept/reject reasons, attempt counts and measured cost. It costs real money
(roughly $0.20-0.65 per accepted puzzle) and needs openai_api_key + ANTHROPIC_API_KEY.

The geometry cases are the ones that matter most. The bounding box produced by the vision
pass is the permanent answer key for a puzzle: if hit_test or rect_intersects is wrong,
every player who ever sees that puzzle is told they missed when they pointed straight at
the mascot, and there is nothing in the game loop that would surface the bug.
"""

import argparse
import asyncio
import io
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wheres_okra as wo  # noqa: E402


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

_FAILURES = []


def check(condition, note):
    if not condition:
        _FAILURES.append(note)
        print(f"  FAIL  {note}")
    return condition


def section(title):
    print(f"\n{title}")


# ---------------------------------------------------------------------------
# Column labels
# ---------------------------------------------------------------------------

def run_columns():
    section("column labels")
    for index, expected in [(0, "A"), (1, "B"), (25, "Z"), (26, "AA"), (27, "AB")]:
        check(wo.column_label(index) == expected,
              f"column_label({index}) == {expected!r}")
    for index in range(0, 60):
        check(wo.column_index(wo.column_label(index)) == index,
              f"column label round-trips at {index}")
    check(wo.column_index("") is None, "empty column label rejected")
    check(wo.column_index("3") is None, "numeric column label rejected")
    check(wo.column_index("a") == 0, "lowercase column label accepted")


# ---------------------------------------------------------------------------
# Grid guesses
# ---------------------------------------------------------------------------

# (text, cols, rows, expected, note)
GRID_CASES = [
    ("A1", 10, 10, (0, 0), "top-left cell"),
    ("J10", 10, 10, (9, 9), "bottom-right cell"),
    ("F7", 10, 10, (5, 6), "mid-grid"),
    ("f7", 10, 10, (5, 6), "lowercase"),
    ("  F7  ", 10, 10, (5, 6), "surrounding whitespace"),
    ("F-7", 10, 10, (5, 6), "hyphen separator"),
    ("F 7", 10, 10, (5, 6), "space separator"),
    ("F,7", 10, 10, (5, 6), "comma separator"),
    ("K1", 10, 10, None, "column past the right edge"),
    ("A11", 10, 10, None, "row past the bottom edge"),
    ("A0", 10, 10, None, "rows are 1-based, so 0 is out of range"),
    ("7F", 10, 10, None, "reversed order is not a grid reference"),
    ("F", 10, 10, None, "letter with no number"),
    ("7", 10, 10, None, "number with no letter"),
    ("", 10, 10, None, "empty string"),
    ("nice one F7", 10, 10, None, "grid reference embedded in chat is not a guess"),
    ("okra", 10, 10, None, "ordinary chat"),
    (None, 10, 10, None, "non-string input"),
    ("L12", 12, 12, (11, 11), "brutal grid corner"),
]


def run_grid():
    section("grid guesses")
    for text, cols, rows, expected, note in GRID_CASES:
        check(wo.parse_grid_guess(text, cols, rows) == expected, f"parse_grid_guess: {note}")

    # Cells must tile the unit square exactly, with no gap or overlap at the seams.
    rect = wo.grid_cell_rect(0, 0, 10, 10)
    check(rect == (0.0, 0.0, 0.1, 0.1), "grid_cell_rect covers the first tenth")
    left = wo.grid_cell_rect(4, 0, 10, 10)
    right = wo.grid_cell_rect(5, 0, 10, 10)
    check(left[2] == right[0], "adjacent cells share an edge exactly")
    last = wo.grid_cell_rect(9, 9, 10, 10)
    check(last[2] == 1.0 and last[3] == 1.0, "final cell reaches the bottom-right corner")

    check(wo.grid_label_to_rect("A1", 10, 10) == (0.0, 0.0, 0.1, 0.1),
          "grid_label_to_rect matches grid_cell_rect")
    check(wo.grid_label_to_rect("ZZ9", 10, 10) is None,
          "grid_label_to_rect rejects an out-of-range label")


# ---------------------------------------------------------------------------
# Click payloads
# ---------------------------------------------------------------------------

CLICK_CASES = [
    ("click:0.5,0.5", (0.5, 0.5), "plain"),
    ("click:0.6312,0.7104", (0.6312, 0.7104), "four decimal places"),
    ("CLICK:0.5,0.5", (0.5, 0.5), "uppercase prefix"),
    ("click: 0.5 , 0.5 ", (0.5, 0.5), "internal whitespace"),
    ("click:0,0", (0.0, 0.0), "top-left corner"),
    ("click:1,1", (1.0, 1.0), "bottom-right corner"),
    ("click:1.5,0.5", None, "x past the right edge"),
    ("click:0.5,-0.1", None, "negative y"),
    ("click:0.5", None, "missing y"),
    ("click:a,b", None, "non-numeric"),
    ("0.5,0.5", None, "no prefix"),
    ("click:0.5,0.5 extra", None, "trailing junk"),
    ("", None, "empty"),
    (None, None, "non-string"),
]


def run_clicks():
    section("click payloads")
    for text, expected, note in CLICK_CASES:
        check(wo.parse_click(text) == expected, f"parse_click: {note}")


# ---------------------------------------------------------------------------
# Target geometry
# ---------------------------------------------------------------------------

def run_geometry():
    section("target geometry")
    target = {"xMin": 0.60, "yMin": 0.60, "xMax": 0.70, "yMax": 0.75}

    check(wo.normalize_target(target) == (0.60, 0.60, 0.70, 0.75),
          "normalize_target unpacks a dict")
    check(wo.normalize_target([0.1, 0.2, 0.3, 0.4]) == (0.1, 0.2, 0.3, 0.4),
          "normalize_target accepts a sequence")
    check(wo.normalize_target({"xMin": 0.7, "yMin": 0.75, "xMax": 0.6, "yMax": 0.6})
          == (0.6, 0.6, 0.7, 0.75),
          "normalize_target repairs inverted edges rather than discarding the box")
    check(wo.normalize_target(None) is None, "normalize_target: None")
    check(wo.normalize_target({"xMin": 0.1}) is None, "normalize_target: missing keys")
    check(wo.normalize_target([0.1, 0.2]) is None, "normalize_target: wrong length")
    check(wo.normalize_target("nope") is None, "normalize_target: junk")

    check(abs(wo.bbox_area(target) - 0.015) < 1e-9, "bbox_area multiplies the sides")
    check(wo.bbox_area(None) == 0.0, "bbox_area of an unusable box is zero")

    # Hit testing, with tolerance disabled so the edges are exact.
    check(wo.hit_test(0.65, 0.65, target, 0.0), "point inside")
    check(wo.hit_test(0.60, 0.60, target, 0.0), "top-left corner counts as inside")
    check(wo.hit_test(0.70, 0.75, target, 0.0), "bottom-right corner counts as inside")
    check(not wo.hit_test(0.59, 0.65, target, 0.0), "point just left of the box")
    check(not wo.hit_test(0.65, 0.76, target, 0.0), "point just below the box")
    check(not wo.hit_test(0.65, 0.65, None, 0.0), "no target means no hit")

    # Tolerance is what makes a phone tap forgiving.
    check(not wo.hit_test(0.58, 0.65, target, 0.0), "0.58 misses with no tolerance")
    check(wo.hit_test(0.58, 0.65, target, wo.TAP_TOLERANCE),
          "0.58 hits with tap tolerance")
    check(not wo.hit_test(0.50, 0.65, target, wo.TAP_TOLERANCE),
          "tap tolerance is padding, not a free pass across the image")

    # Grid cells overlap the target if any part of them does, so a mascot straddling a
    # cell boundary is findable from either side.
    check(wo.rect_intersects((0.6, 0.6, 0.7, 0.7), target), "fully overlapping cell")
    check(wo.rect_intersects((0.55, 0.55, 0.62, 0.62), target), "partially overlapping cell")
    check(wo.rect_intersects((0.0, 0.0, 1.0, 1.0), target), "cell containing the target")
    check(not wo.rect_intersects((0.0, 0.0, 0.1, 0.1), target), "distant cell")
    check(not wo.rect_intersects((0.71, 0.6, 0.8, 0.7), target), "cell just right of the box")
    check(not wo.rect_intersects(None, target), "no rect means no intersection")

    straddler = {"xMin": 0.495, "yMin": 0.495, "xMax": 0.505, "yMax": 0.505}
    left_cell = wo.grid_cell_rect(4, 4, 10, 10)
    right_cell = wo.grid_cell_rect(5, 5, 10, 10)
    check(wo.rect_intersects(left_cell, straddler) and wo.rect_intersects(right_cell, straddler),
          "a mascot on a cell boundary is findable from both cells")

    check(wo.target_grid_label(target, 10, 10) == "G7",
          "target_grid_label names the cell holding the box centre")
    check(wo.target_grid_label({"xMin": 0.0, "yMin": 0.0, "xMax": 0.01, "yMax": 0.01},
                               10, 10) == "A1",
          "target_grid_label at the top-left")
    check(wo.target_grid_label({"xMin": 0.99, "yMin": 0.99, "xMax": 1.0, "yMax": 1.0},
                               10, 10) == "J10",
          "target_grid_label at the bottom-right stays in range")
    check(wo.target_grid_label(None, 10, 10) is None, "target_grid_label: no target")


# ---------------------------------------------------------------------------
# Submission grading
# ---------------------------------------------------------------------------

def run_grading():
    section("submission grading")
    target = {"xMin": 0.60, "yMin": 0.60, "xMax": 0.70, "yMax": 0.75}
    cols = rows = 10

    kind, correct = wo.grade_submission("G7", target, cols, rows, allow_click=False)
    check(kind == "grid" and correct, "correct grid cell from chat")

    kind, correct = wo.grade_submission("A1", target, cols, rows, allow_click=False)
    check(kind == "grid" and not correct, "wrong grid cell from chat")

    kind, correct = wo.grade_submission("hello everyone", target, cols, rows,
                                        allow_click=False)
    check(kind is None and not correct, "ordinary chat is not a guess at all")

    # The important one: coordinates typed into Discord must never be graded, or a player
    # could sweep the image far more finely than the grid allows.
    kind, correct = wo.grade_submission("click:0.65,0.65", target, cols, rows,
                                        allow_click=False)
    check(kind is None and not correct,
          "a click payload typed into chat is rejected, not graded")

    kind, correct = wo.grade_submission("click:0.65,0.65", target, cols, rows,
                                        allow_click=True)
    check(kind == "click" and correct, "correct tap from the Activity")

    kind, correct = wo.grade_submission("click:0.10,0.10", target, cols, rows,
                                        allow_click=True)
    check(kind == "click" and not correct, "wrong tap from the Activity")

    kind, correct = wo.grade_submission("click:9,9", target, cols, rows, allow_click=True)
    check(kind is None and not correct, "out-of-range tap is not a guess")


# ---------------------------------------------------------------------------
# Locator reply parsing
# ---------------------------------------------------------------------------

_GOOD = ('{"targetCount": 1, "boundingBox": {"xMin": 0.645, "yMin": 0.63, "xMax": 0.69, '
         '"yMax": 0.74}, "confidence": 0.97, "visibility": 0.61, "tooObvious": false, '
         '"malformed": false}')


def run_parsing():
    section("locator reply parsing")

    result = wo.parse_validation(_GOOD)
    check(result.target_count == 1, "parse: target count")
    check(result.target == (0.645, 0.63, 0.69, 0.74), "parse: bounding box")
    check(abs(result.confidence - 0.97) < 1e-9, "parse: confidence")
    check(abs(result.visibility - 0.61) < 1e-9, "parse: visibility")
    check(result.too_obvious is False and result.malformed is False, "parse: flags")

    fenced = "```json\n" + _GOOD + "\n```"
    check(wo.parse_validation(fenced).target_count == 1,
          "parse: a code fence around the object is tolerated")

    chatty = "Here is what I found:\n" + _GOOD + "\nHope that helps!"
    check(wo.parse_validation(chatty).target_count == 1,
          "parse: surrounding prose is tolerated")

    # Everything unusable collapses to a zero result, which validate() then rejects.
    for raw, note in [
        ("", "empty body"),
        (None, "None body"),
        ("I could not find it.", "prose with no JSON"),
        ('{"targetCount": 1,', "truncated body"),
        ("{not json}", "malformed JSON"),
    ]:
        result = wo.parse_validation(raw)
        check(result.target_count == 0 and result.target is None and result.confidence == 0.0,
              f"parse: {note} becomes a zero result")

    result = wo.parse_validation('{"targetCount": 2, "boundingBox": null, '
                                 '"confidence": 0.9, "visibility": 0.5}')
    check(result.target_count == 2 and result.target is None,
          "parse: duplicate mascots reported, no box")

    result = wo.parse_validation('{"targetCount": "1", "confidence": "0.9", '
                                 '"tooObvious": "true"}')
    check(result.target_count == 1 and abs(result.confidence - 0.9) < 1e-9
          and result.too_obvious is True,
          "parse: stringly-typed values are coerced")

    result = wo.parse_validation('{"targetCount": 1, "confidence": "high"}')
    check(result.confidence == 0.0, "parse: an unparseable float falls back to zero")

    check(wo.parse_validation(_GOOD).to_dict()["boundingBox"]["xMin"] == 0.645,
          "to_dict round-trips the box into the stored document shape")


# ---------------------------------------------------------------------------
# Difficulty validation
# ---------------------------------------------------------------------------

def _result(**kwargs):
    # area 0.06 * 0.08 = 0.0048: comfortably inside hard's (0.002, 0.008), clear of
    # brutal's 0.004 ceiling and easy's 0.010 floor. Deliberately not sitting on a band
    # edge, where the comparison would turn on floating-point representation.
    base = {"target_count": 1, "target": (0.60, 0.60, 0.66, 0.68),
            "confidence": 0.95, "visibility": 0.50, "too_obvious": False,
            "malformed": False}
    base.update(kwargs)
    return wo.ValidationResult(**base)


def run_validation():
    section("difficulty validation")

    ok, reasons = wo.validate(_result(), "hard")
    check(ok and not reasons, f"a good hard puzzle validates (got {reasons})")

    ok, reasons = wo.validate(_result(target_count=0), "hard")
    check(not ok and any("target_count" in r for r in reasons), "missing mascot rejected")

    ok, reasons = wo.validate(_result(target_count=2), "hard")
    check(not ok and any("target_count" in r for r in reasons), "duplicate mascots rejected")

    ok, reasons = wo.validate(_result(malformed=True), "hard")
    check(not ok and "malformed" in reasons, "malformed mascot rejected")

    ok, reasons = wo.validate(_result(too_obvious=True), "hard")
    check(not ok and "too_obvious" in reasons, "obvious mascot rejected")

    ok, reasons = wo.validate(_result(confidence=0.5), "hard")
    check(not ok and any("low_confidence" in r for r in reasons),
          "an unsure locator is rejected -- its box would become a wrong answer key")

    ok, reasons = wo.validate(_result(visibility=0.10), "hard")
    check(not ok and any("low_visibility" in r for r in reasons),
          "a mascot hidden past the fairness floor is rejected")

    ok, reasons = wo.validate(_result(target=None), "hard")
    check(not ok and "no_bounding_box" in reasons, "no box rejected")

    ok, reasons = wo.validate(_result(target=(0.9, 0.9, 1.4, 1.4)), "hard")
    check(not ok and "bounding_box_out_of_range" in reasons, "out-of-range box rejected")

    # The area band is what actually enforces difficulty: the same image is too big for
    # brutal, right for hard, and too small for easy.
    mid = _result()
    ok, reasons = wo.validate(mid, "brutal")
    check(not ok and any("area_too_large" in r for r in reasons),
          "a hard-sized mascot is too large for brutal")
    ok, reasons = wo.validate(mid, "easy")
    check(not ok and any("area_too_small" in r for r in reasons),
          "a hard-sized mascot is too small for easy")

    big = _result(target=(0.3, 0.3, 0.45, 0.45), visibility=0.9)  # area 0.0225
    ok, reasons = wo.validate(big, "easy")
    check(ok, f"an easy-sized mascot validates for easy (got {reasons})")

    # Bands overlap on purpose (slack keeps the cost of regeneration down), but they must
    # march monotonically downwards -- if a harder tier ever allowed a larger mascot than
    # an easier one, difficulty selection would silently stop meaning anything.
    for name in wo.DIFFICULTY_ORDER:
        lo, hi = wo.DIFFICULTIES[name]["area"]
        check(lo < hi, f"{name}: area band is non-empty")
    for a, b in zip(wo.DIFFICULTY_ORDER, wo.DIFFICULTY_ORDER[1:]):
        check(wo.DIFFICULTIES[b]["area"][0] < wo.DIFFICULTIES[a]["area"][0],
              f"{b} allows a smaller mascot than {a}")
        check(wo.DIFFICULTIES[b]["area"][1] < wo.DIFFICULTIES[a]["area"][1],
              f"{b} caps the mascot smaller than {a}")
        check(wo.DIFFICULTIES[b]["min_visibility"] <= wo.DIFFICULTIES[a]["min_visibility"],
              f"{b} tolerates less visibility than {a}")
        check(wo.DIFFICULTIES[b]["grid"][0] >= wo.DIFFICULTIES[a]["grid"][0],
              f"{b} uses at least as fine a grid as {a}")


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def run_prompts():
    section("prompt construction")
    prompt = wo.build_puzzle_prompt(wo.THEMES[0], "hard", wo.REGIONS[0])

    check("Redraw the supplied mascot as a native character" in prompt,
          "prompt carries the redraw instruction")
    check("Do not paste, composite, overlay, or copy" in prompt,
          "prompt forbids compositing the original artwork")
    check("line quality" in prompt and "perspective" in prompt and "saturation" in prompt,
          "prompt names the style properties that must match")
    check("Exactly ONE such okra character" in prompt, "prompt demands a single mascot")
    check("chef" in prompt and "gloves" in prompt and "mustache" in prompt,
          "prompt preserves the identifying features")
    check("halo" in prompt and "empty space" in prompt,
          "prompt forbids the pasted-in tells")
    check("arrows" in prompt and "labels" in prompt,
          "prompt forbids drawing answer information into the image")
    check(wo.REGIONS[0] in prompt, "prompt places the mascot in the chosen region")
    check("30-50%" in prompt, "hard occlusion band reaches the prompt")

    # A coordinate in the prompt would be a hint baked into the image.
    check("xMin" not in prompt and "0." not in prompt.replace("30-50", ""),
          "prompt never contains normalised coordinates")

    for name in wo.DIFFICULTY_ORDER:
        p = wo.build_puzzle_prompt(wo.THEMES[0], name, wo.REGIONS[0])
        spec = wo.DIFFICULTIES[name]
        check(spec["scale"] in p, f"{name}: scale reaches the prompt")
        check(spec["density"] in p, f"{name}: density reaches the prompt")
        check(spec["camouflage"] in p, f"{name}: camouflage reaches the prompt")

    easy = wo.build_puzzle_prompt(wo.THEMES[0], "easy", wo.REGIONS[0])
    brutal = wo.build_puzzle_prompt(wo.THEMES[0], "brutal", wo.REGIONS[0])
    check(easy != brutal, "difficulty changes the prompt rather than the finished image")


def run_placement():
    section("placement randomisation")
    rng = random.Random(1234)

    picks = [wo.pick_region(rng) for _ in range(2000)]
    check(set(picks) == set(wo.REGIONS), "every region is reachable")

    centre = picks.count(wo.REGIONS[4]) / len(picks)
    check(centre < 1.0 / len(wo.REGIONS),
          f"the centre is under-weighted (got {centre:.3f})")

    excluded = wo.REGIONS[0]
    picks = [wo.pick_region(rng, exclude=excluded) for _ in range(500)]
    check(excluded not in picks, "the previous region is never picked twice in a row")

    themes = [wo.pick_theme(rng, exclude=wo.THEMES[0]) for _ in range(200)]
    check(wo.THEMES[0] not in themes, "the previous theme is excluded")
    check(len(set(themes)) > 5, "themes vary")


# ---------------------------------------------------------------------------
# Pipeline, with fake clients
# ---------------------------------------------------------------------------

def _png(width=512, height=512, colour=(40, 120, 60)):
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="PNG")
    return buffer.getvalue()


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _ThinkingBlock:
    def __init__(self):
        self.type = "thinking"
        self.thinking = "considering the image"


class _Response:
    def __init__(self, text, with_thinking=True):
        # A thinking block first, mirroring what LOCATE_MODEL actually returns -- this is
        # the shape that makes the repo's usual response.content[0].text pattern wrong.
        self.content = ([_ThinkingBlock()] if with_thinking else []) + [_Block(text)]


class _FakeMessages:
    def __init__(self, locate_replies, verify_reply):
        self._locate = list(locate_replies)
        self._verify = verify_reply
        self.locate_calls = 0
        self.verify_calls = 0

    async def create(self, **kwargs):
        system = kwargs["system"][0]["text"]
        if system.startswith("You verify"):
            self.verify_calls += 1
            return _Response(self._verify)
        self.locate_calls += 1
        index = min(self.locate_calls - 1, len(self._locate) - 1)
        return _Response(self._locate[index])


class _FakeVisionClient:
    def __init__(self, locate_replies, verify_reply='{"present": true, "confidence": 0.95}'):
        self.messages = _FakeMessages(locate_replies, verify_reply)


def _box_reply(x_min, y_min, x_max, y_max, confidence=0.95, visibility=0.5,
               count=1, too_obvious=False, malformed=False):
    return json.dumps({
        "targetCount": count,
        "boundingBox": {"xMin": x_min, "yMin": y_min, "xMax": x_max, "yMax": y_max},
        "confidence": confidence, "visibility": visibility,
        "tooObvious": too_obvious, "malformed": malformed,
    })


def _fns(record=None):
    async def edit_fn(mascot_bytes, prompt):
        if record is not None:
            record.append(("edit", prompt))
        return _png()

    async def generate_fn(prompt):
        if record is not None:
            record.append(("generate", prompt))
        return _png()

    return edit_fn, generate_fn


def run_pipeline():
    section("generate/validate pipeline")

    good = _box_reply(0.60, 0.60, 0.65, 0.68)          # area 0.0040 -> valid for hard
    oversize = _box_reply(0.10, 0.10, 0.60, 0.60)      # area 0.25   -> far too large

    async def first_try():
        edit_fn, generate_fn = _fns()
        client = _FakeVisionClient([good])
        image, result, meta = await wo.build_validated_puzzle(
            edit_fn=edit_fn, generate_fn=generate_fn, vision_client=client,
            mascot_bytes=_png(64, 64), theme=wo.THEMES[0], difficulty="hard",
            region=wo.REGIONS[0])
        check(image, "a validated puzzle returns image bytes")
        check(result.target == (0.60, 0.60, 0.65, 0.68), "the located box is returned")
        check(meta["attempts"] == 1, "a good first attempt does not retry")
        check(meta["used_reference"] is True, "the reference path is used by default")
        check(client.messages.verify_calls == 1, "the crop cross-check runs on success")

    asyncio.run(first_try())

    async def retries_then_succeeds():
        edit_fn, generate_fn = _fns()
        client = _FakeVisionClient([_box_reply(0, 0, 0, 0, count=0), good])
        _, _, meta = await wo.build_validated_puzzle(
            edit_fn=edit_fn, generate_fn=generate_fn, vision_client=client,
            mascot_bytes=_png(64, 64), theme=wo.THEMES[0], difficulty="hard",
            region=wo.REGIONS[0])
        check(meta["attempts"] == 2, "a rejected attempt is retried")

    asyncio.run(retries_then_succeeds())

    async def falls_back_to_text_prompt():
        record = []
        edit_fn, generate_fn = _fns(record)
        # Two oversized boxes in a row means the edit endpoint is turning the reference
        # into the subject of the picture; the loop should stop supplying it.
        client = _FakeVisionClient([oversize, oversize, good])
        _, _, meta = await wo.build_validated_puzzle(
            edit_fn=edit_fn, generate_fn=generate_fn, vision_client=client,
            mascot_bytes=_png(64, 64), theme=wo.THEMES[0], difficulty="hard",
            region=wo.REGIONS[0])
        kinds = [kind for kind, _ in record]
        check(kinds == ["edit", "edit", "generate"],
              f"repeated oversize switches to the text-to-image path (got {kinds})")
        check(meta["used_reference"] is False, "meta records which path produced the image")
        text_prompt = record[-1][1]
        check("green okra pod" in text_prompt,
              "the fallback prompt describes the mascot in words")
        check("Do not paste" not in text_prompt,
              "the fallback prompt drops the supplied-image instruction")

    asyncio.run(falls_back_to_text_prompt())

    async def crop_check_rejects():
        edit_fn, generate_fn = _fns()
        # The locator is confident and in-band, but the crop shows nothing -- exactly the
        # hallucinated-box case that would otherwise become an unwinnable answer key.
        client = _FakeVisionClient([good], verify_reply='{"present": false, "confidence": 0.1}')
        try:
            await wo.build_validated_puzzle(
                edit_fn=edit_fn, generate_fn=generate_fn, vision_client=client,
                mascot_bytes=_png(64, 64), theme=wo.THEMES[0], difficulty="hard",
                region=wo.REGIONS[0], max_attempts=2)
        except wo.PuzzleGenerationError as exc:
            check("crop_check_failed" in str(exc),
                  "a failed crop check rejects an otherwise-valid box")
            return
        check(False, "a failed crop check must not yield a puzzle")

    asyncio.run(crop_check_rejects())

    async def gives_up():
        edit_fn, generate_fn = _fns()
        client = _FakeVisionClient([_box_reply(0, 0, 0, 0, count=0)])
        try:
            await wo.build_validated_puzzle(
                edit_fn=edit_fn, generate_fn=generate_fn, vision_client=client,
                mascot_bytes=_png(64, 64), theme=wo.THEMES[0], difficulty="hard",
                region=wo.REGIONS[0], max_attempts=3)
        except wo.PuzzleGenerationError as exc:
            check("3 attempts" in str(exc), "gives up after max_attempts with a reason")
            return
        check(False, "an always-failing generator must raise")

    asyncio.run(gives_up())

    async def survives_a_broken_generator():
        async def boom(*args):
            raise RuntimeError("image provider exploded")

        async def generate_fn(prompt):
            return _png()

        client = _FakeVisionClient([good])
        try:
            await wo.build_validated_puzzle(
                edit_fn=boom, generate_fn=generate_fn, vision_client=client,
                mascot_bytes=_png(64, 64), theme=wo.THEMES[0], difficulty="hard",
                region=wo.REGIONS[0], max_attempts=2)
        except wo.PuzzleGenerationError as exc:
            check("image provider exploded" in str(exc),
                  "a provider exception is captured as a rejection reason, not raised raw")
            return
        check(False, "expected PuzzleGenerationError")

    asyncio.run(survives_a_broken_generator())

    async def vision_failure_is_not_fatal():
        edit_fn, generate_fn = _fns()

        class _Boom:
            class messages:
                @staticmethod
                async def create(**kwargs):
                    raise RuntimeError("vision API down")

        result = await wo.locate_mascot(_Boom(), _png(), _png(64, 64))
        check(result.target_count == 0 and "vision API down" in (result.raw or ""),
              "a vision failure becomes a zero result carrying the error text")

    asyncio.run(vision_failure_is_not_fatal())


# ---------------------------------------------------------------------------
# Hybrid pipeline: background generated separately, mascot inserted at a chosen spot
# ---------------------------------------------------------------------------

def run_target_box():
    section("pick_target_box (hybrid)")
    rng = random.Random(42)

    for name in wo.DIFFICULTY_ORDER:
        lo, hi = wo.DIFFICULTIES[name]["area"]
        for region_index in range(9):
            box = wo.pick_target_box(name, region_index, rng)
            check(len(box) == 4, f"{name} region {region_index}: box has 4 coordinates")
            x_min, y_min, x_max, y_max = box
            check(0.0 <= x_min < x_max <= 1.0 and 0.0 <= y_min < y_max <= 1.0,
                  f"{name} region {region_index}: box is within the unit square")
            area = (x_max - x_min) * (y_max - y_min)
            check(lo - 1e-9 <= area <= hi + 1e-9,
                  f"{name} region {region_index}: area {area:.5f} within band ({lo}, {hi})")

    # The box's centre should land inside the requested region's 3x3 cell.
    x_min, y_min, x_max, y_max = wo.pick_target_box("hard", 0, rng)  # upper-left
    cx, cy = (x_min + x_max) / 2, (y_min + y_max) / 2
    check(cx <= 1 / 3 + 1e-6 and cy <= 1 / 3 + 1e-6,
          f"region 0 (upper-left) keeps the box centre in its cell (got {cx:.3f},{cy:.3f})")

    x_min, y_min, x_max, y_max = wo.pick_target_box("hard", 8, rng)  # lower-right
    cx, cy = (x_min + x_max) / 2, (y_min + y_max) / 2
    check(cx >= 2 / 3 - 1e-6 and cy >= 2 / 3 - 1e-6,
          f"region 8 (lower-right) keeps the box centre in its cell (got {cx:.3f},{cy:.3f})")

    x_min, y_min, x_max, y_max = wo.pick_target_box("hard", 4, rng)  # centre
    cx, cy = (x_min + x_max) / 2, (y_min + y_max) / 2
    check(1 / 3 - 1e-6 <= cx <= 2 / 3 + 1e-6 and 1 / 3 - 1e-6 <= cy <= 2 / 3 + 1e-6,
          f"region 4 (centre) keeps the box centre in its cell (got {cx:.3f},{cy:.3f})")

    # An explicit aspect ratio should be respected exactly (small enough to fit its cell).
    x_min, y_min, x_max, y_max = wo.pick_target_box("easy", 4, rng, aspect_ratio=2.0)
    w, h = x_max - x_min, y_max - y_min
    check(abs(h / w - 2.0) < 1e-6, f"explicit aspect_ratio is respected (got {h / w:.3f})")

    boxes = {wo.pick_target_box("hard", 4, rng) for _ in range(20)}
    check(len(boxes) > 5, "repeated calls at the same region produce varied boxes")


def run_mask_building():
    section("build_mask_bytes (hybrid)")
    from PIL import Image

    size = (1024, 1024)
    target = (0.5, 0.5, 0.6, 0.7)
    mask_bytes = wo.build_mask_bytes(size, target, margin=0.5)
    check(bool(mask_bytes), "build_mask_bytes returns bytes")

    with Image.open(io.BytesIO(mask_bytes)) as mask:
        check(mask.size == size, f"mask matches the requested image size (got {mask.size})")
        check(mask.mode == "RGBA", f"mask is RGBA (got {mask.mode})")

        a = mask.getpixel((5, 5))[3]
        check(a == 255, "top-left corner is opaque (protected from editing)")
        a = mask.getpixel((size[0] - 5, size[1] - 5))[3]
        check(a == 255, "bottom-right corner is opaque (protected from editing)")

        cx = int(((target[0] + target[2]) / 2) * size[0])
        cy = int(((target[1] + target[3]) / 2) * size[1])
        a = mask.getpixel((cx, cy))[3]
        check(a == 0, f"target centre is transparent/editable (got alpha={a})")

    tiny_near_corner = (0.01, 0.01, 0.02, 0.02)
    check(bool(wo.build_mask_bytes(size, tiny_near_corner, margin=0.5)),
          "a tiny near-corner target does not crash mask building")


def run_crop_mapping():
    section("crop <-> full-image coordinate mapping (hybrid)")

    target = (0.6, 0.6, 0.66, 0.68)
    padded = wo._padded_bounds(target, 0.5)
    check(padded is not None, "_padded_bounds returns a box")
    px_min, py_min, px_max, py_max = padded
    check(px_min < target[0] and py_min < target[1],
          "padding expands the box outward on the low edge")
    check(px_max > target[2] and py_max > target[3],
          "padding expands the box outward on the high edge")
    check(0.0 <= px_min and px_max <= 1.0, "padded bounds stay clamped to the unit square")

    # A crop-local box spanning the whole crop (0,0)-(1,1) must map back to exactly the
    # padded bounds it was cropped from.
    full = wo._map_crop_target_to_full((0.0, 0.0, 1.0, 1.0), padded)
    check(all(abs(a - b) < 1e-9 for a, b in zip(full, padded)),
          "mapping the crop's own full extent back reproduces the padded bounds")

    # A box covering the crop's centre half maps back to the centre half of the padded
    # region in the full image.
    pw, ph = px_max - px_min, py_max - py_min
    expected = (px_min + 0.25 * pw, py_min + 0.25 * ph,
                px_min + 0.75 * pw, py_min + 0.75 * ph)
    full2 = wo._map_crop_target_to_full((0.25, 0.25, 0.75, 0.75), padded)
    check(all(abs(a - b) < 1e-9 for a, b in zip(full2, expected)),
          "a partial crop-local box maps back proportionally")

    check(wo._map_crop_target_to_full(None, padded) is None,
          "no crop target maps to no full-image target")


def run_hybrid_prompts():
    section("hybrid prompt construction")

    bg = wo.build_background_prompt(wo.THEMES[0], "hard")
    check("okra" not in bg.lower(), "background prompt never mentions okra")
    check("mascot" not in bg.lower(), "background prompt never mentions the mascot")
    check("chef" not in bg.lower(), "background prompt never mentions a chef character")
    check("reference" not in bg.lower(), "background prompt never mentions a reference image")
    check(wo.THEMES[0] in bg, "background prompt carries the theme")
    check(wo.DIFFICULTIES["hard"]["density"] in bg,
          "background prompt carries the difficulty's density wording")

    ins = wo.build_insertion_prompt("hard")
    check("chef" in ins.lower() and "gloves" in ins.lower() and "mustache" in ins.lower(),
          "insertion prompt carries the mascot's identifying features")
    check("masked region" in ins, "insertion prompt references the masked region")
    check("exactly one such character" in ins.lower(),
          "insertion prompt still demands a single character")
    check("haloed" in ins.lower(), "insertion prompt forbids the pasted-in tells")
    spec = wo.DIFFICULTIES["hard"]
    occ_text = f"{int(spec['occlusion'][0] * 100)}-{int(spec['occlusion'][1] * 100)}%"
    check(occ_text in ins, "insertion prompt carries the difficulty's occlusion band")

    for name in wo.DIFFICULTY_ORDER:
        b = wo.build_background_prompt(wo.THEMES[1], name)
        i = wo.build_insertion_prompt(name)
        check("okra" not in b.lower(), f"{name}: background prompt stays mascot-free")
        check(wo.DIFFICULTIES[name]["camouflage"] in i,
              f"{name}: insertion prompt carries camouflage wording")


class _HybridFakeMessages:
    """Dispatches on a distinguishing phrase rather than a shared prefix: both
    _LOCATE_IN_CROP_SYSTEM and the full-image _LOCATE_SYSTEM open with "You are a precise
    visual localisation tool", so a naive startswith() check (fine for the non-hybrid fakes
    above, which never see both in the same test) would misroute here."""

    def __init__(self, locate_replies, verify_reply='{"present": true, "confidence": 0.95}'):
        self._locate = list(locate_replies)
        self._verify = verify_reply
        self.locate_calls = 0
        self.verify_calls = 0

    async def create(self, **kwargs):
        system = kwargs["system"][0]["text"]
        if system.startswith("You verify a single crop"):
            self.verify_calls += 1
            return _Response(self._verify)
        assert "checking one small crop" in system, f"unrouted system prompt: {system[:80]!r}"
        self.locate_calls += 1
        index = min(self.locate_calls - 1, len(self._locate) - 1)
        return _Response(self._locate[index])


class _HybridFakeVisionClient:
    def __init__(self, locate_replies, verify_reply='{"present": true, "confidence": 0.95}'):
        self.messages = _HybridFakeMessages(locate_replies, verify_reply)


def run_hybrid_pipeline():
    section("hybrid generate/validate pipeline")

    # pick_target_box's own box is guaranteed within its difficulty's area band; the mask
    # (and crop) around it pads by _INSERTION_MASK_MARGIN=0.5 on every side, so the
    # original box occupies exactly the middle half of the padded/cropped region along
    # each axis: padded width = w*(1+2*0.5) = 2w, and the offset from each padded edge to
    # the original edge is (2w-w)/2 = w/2 = 0.25 of the padded width. A crop-local reply of
    # exactly (0.25, 0.25, 0.75, 0.75) therefore reconstructs pick_target_box's own box
    # EXACTLY once mapped back -- and so is valid for ANY difficulty/region draw, without
    # needing to know what pick_target_box's internal (unseeded) rng actually picked.
    # region=wo.REGIONS[4] (centre) is passed throughout so that reconstruction is never
    # perturbed by _padded_bounds clamping a near-edge box against the unit square.
    # visibility=0.9 clears every difficulty's min_visibility floor (highest is easy's
    # 0.75), since this fixture is reused across sub-tests running different difficulties.
    good_crop_reply = _box_reply(0.25, 0.25, 0.75, 0.75, confidence=0.95, visibility=0.9)
    # A crop-local reply spanning the whole crop maps back to ~4x the original target's
    # area (2x width * 2x height). "easy" and "medium" have a hi/lo band ratio of 3, so 4x
    # ANY valid underlying draw exceeds their ceiling regardless of where in the band that
    # draw landed -- unlike "hard"/"brutal", whose ratio of exactly 4 makes the worst case
    # (draw at the band's own minimum) land exactly AT the ceiling, not over it.
    oversized_crop_reply = _box_reply(0.0, 0.0, 1.0, 1.0, confidence=0.95, visibility=0.9)
    centre_region = wo.REGIONS[4]

    async def background_fn(prompt):
        return _png()

    def make_insert_fn(record=None):
        async def insert_fn(background_bytes, mask_bytes, prompt):
            if record is not None:
                record.append((background_bytes, mask_bytes, prompt))
            return _png()
        return insert_fn

    async def first_try():
        client = _HybridFakeVisionClient([good_crop_reply])
        image, result, meta = await wo.build_validated_puzzle_hybrid(
            background_fn=background_fn, insert_fn=make_insert_fn(),
            vision_client=client, mascot_bytes=_png(64, 64),
            theme=wo.THEMES[0], difficulty="hard", region=centre_region)
        check(bool(image), "a validated hybrid puzzle returns image bytes")
        check(result.target is not None, "the mapped-back box is returned")
        check(meta["attempts"] == 1, "a good first attempt does not retry")
        check(meta["pipeline"] == "hybrid", "meta records which pipeline produced the image")
        check(meta["used_reference"] is False,
              "hybrid insertion never claims to use a reference image")
        check(client.messages.locate_calls == 1, "exactly one locate_in_crop call on success")
        check(client.messages.verify_calls == 1, "the crop cross-check runs on success")

    asyncio.run(first_try())

    async def background_generated_once():
        calls = {"background": 0}

        async def counting_background_fn(prompt):
            calls["background"] += 1
            return _png()

        record = []
        # First reply oversized (rejected), second good -- this must retry the INSERTION,
        # not regenerate the background, which is the whole cost point of the hybrid split.
        # "easy" (not "hard"): see oversized_crop_reply's comment above for why the band's
        # hi/lo ratio matters here.
        client = _HybridFakeVisionClient([oversized_crop_reply, good_crop_reply])
        _, _, meta = await wo.build_validated_puzzle_hybrid(
            background_fn=counting_background_fn, insert_fn=make_insert_fn(record),
            vision_client=client, mascot_bytes=_png(64, 64),
            theme=wo.THEMES[0], difficulty="easy", region=centre_region)
        check(meta["attempts"] == 2, "a rejected attempt is retried")
        check(calls["background"] == 1,
              "the background is generated once and reused across insertion retries")
        check(len(record) == 2, "the insertion call itself does retry")
        first_bg, second_bg = record[0][0], record[1][0]
        check(first_bg == second_bg,
              "every insertion retry is handed the SAME background bytes, not a fresh one")

    asyncio.run(background_generated_once())

    async def crop_check_rejects():
        client = _HybridFakeVisionClient(
            [good_crop_reply], verify_reply='{"present": false, "confidence": 0.1}')
        try:
            await wo.build_validated_puzzle_hybrid(
                background_fn=background_fn, insert_fn=make_insert_fn(),
                vision_client=client, mascot_bytes=_png(64, 64),
                theme=wo.THEMES[0], difficulty="hard", region=centre_region, max_attempts=1)
        except wo.PuzzleGenerationError as exc:
            check("crop_check_failed" in str(exc),
                  "a failed crop cross-check rejects an otherwise-valid hybrid box")
            return
        check(False, "a failed crop check must not yield a hybrid puzzle")

    asyncio.run(crop_check_rejects())

    async def survives_a_broken_insertion():
        async def boom(background_bytes, mask_bytes, prompt):
            raise RuntimeError("edit endpoint exploded")

        client = _HybridFakeVisionClient([good_crop_reply])
        try:
            await wo.build_validated_puzzle_hybrid(
                background_fn=background_fn, insert_fn=boom,
                vision_client=client, mascot_bytes=_png(64, 64),
                theme=wo.THEMES[0], difficulty="hard", max_attempts=2)
        except wo.PuzzleGenerationError as exc:
            check("edit endpoint exploded" in str(exc),
                  "an insertion exception is captured as a rejection reason, not raised raw")
            return
        check(False, "expected PuzzleGenerationError")

    asyncio.run(survives_a_broken_insertion())

    async def broken_background_is_fatal_immediately():
        async def boom(prompt):
            raise RuntimeError("background provider down")

        client = _HybridFakeVisionClient([good_crop_reply])
        try:
            await wo.build_validated_puzzle_hybrid(
                background_fn=boom, insert_fn=make_insert_fn(),
                vision_client=client, mascot_bytes=_png(64, 64),
                theme=wo.THEMES[0], difficulty="hard")
        except wo.PuzzleGenerationError as exc:
            check("background provider down" in str(exc),
                  "a background failure raises immediately (nothing to retry without one)")
            check(client.messages.locate_calls == 0,
                  "no vision call happens if the background never got generated")
            return
        check(False, "expected PuzzleGenerationError")

    asyncio.run(broken_background_is_fatal_immediately())


def run_text_extraction():
    section("response text extraction")
    check(wo._first_text(_Response("hello")) == "hello",
          "text is read past a leading thinking block")
    check(wo._first_text(_Response("hello", with_thinking=False)) == "hello",
          "text is read when there is no thinking block")
    check(wo._first_text(type("r", (), {"content": []})()) == "",
          "an empty response yields empty text")
    check(wo._first_text(type("r", (), {"content": None})()) == "",
          "a content-less response yields empty text")


def run_cropping():
    section("cropping")
    image = _png(1024, 1024)
    crop = wo.crop_to_bytes(image, (0.60, 0.60, 0.65, 0.68))
    check(crop, "a crop is produced")

    from PIL import Image
    with Image.open(io.BytesIO(crop)) as img:
        # 0.05 * 1024 = ~51px before the margin, well under min_side, so it must be
        # upscaled or the verifier is handed an unreadable smudge.
        check(min(img.size) >= 192, f"a small crop is upscaled for legibility (got {img.size})")

    check(wo.crop_to_bytes(image, None) is None, "no target means no crop")
    check(wo.crop_to_bytes(image, (0.5, 0.5, 0.5, 0.5)) is None, "a zero-area box yields no crop")


# ---------------------------------------------------------------------------
# Live tier
# ---------------------------------------------------------------------------

async def run_live(difficulty, count):
    import anthropic
    from openai import AsyncOpenAI

    openai_key = os.getenv("openai_api_key")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not openai_key or not anthropic_key:
        print("live tier needs openai_api_key and ANTHROPIC_API_KEY")
        return 1

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mascot_path = os.path.join(root, "private-assets", "okra_chef.png")
    if not os.path.exists(mascot_path):
        print(f"live tier needs the mascot reference at {mascot_path}")
        return 1
    with open(mascot_path, "rb") as handle:
        mascot_bytes = handle.read()

    openai_client = AsyncOpenAI(api_key=openai_key)
    vision_client = anthropic.AsyncAnthropic(api_key=anthropic_key)

    async def edit_fn(reference, prompt):
        response = await openai_client.images.edit(
            model=wo.IMAGE_MODEL, image=("okra_chef.png", reference, "image/png"),
            prompt=prompt, size="1024x1024", quality=wo.IMAGE_QUALITY)
        import base64
        return base64.b64decode(response.data[0].b64_json)

    async def generate_fn(prompt):
        response = await openai_client.images.generate(
            model=wo.IMAGE_MODEL, prompt=prompt, size="1024x1024",
            quality=wo.IMAGE_QUALITY)
        import base64
        return base64.b64decode(response.data[0].b64_json)

    rng = wo.make_rng()
    out_dir = os.path.join(root, "tmp_live_puzzles")
    os.makedirs(out_dir, exist_ok=True)
    total_attempts = 0

    for i in range(count):
        theme = wo.pick_theme(rng)
        region = wo.pick_region(rng)
        print(f"\n[{i + 1}/{count}] {difficulty} -- {theme} -- {region}")
        started = time.time()

        def on_attempt(index, ok, reasons):
            print(f"    attempt {index}: {'OK' if ok else 'reject'} {reasons or ''}")

        try:
            image, result, meta = await wo.build_validated_puzzle(
                edit_fn=edit_fn, generate_fn=generate_fn, vision_client=vision_client,
                mascot_bytes=mascot_bytes, theme=theme, difficulty=difficulty,
                region=region, on_attempt=on_attempt)
        except wo.PuzzleGenerationError as exc:
            print(f"    FAILED: {exc}")
            continue

        total_attempts += meta["attempts"]
        path = os.path.join(out_dir, f"{difficulty}_{i + 1}.png")
        with open(path, "wb") as handle:
            handle.write(image)
        print(f"    accepted in {meta['attempts']} attempt(s), "
              f"{time.time() - started:.0f}s -> {path}")
        print(f"    box={result.to_dict()['boundingBox']} "
              f"area={wo.bbox_area(result.target):.5f} "
              f"visibility={result.visibility:.2f} "
              f"cell={wo.target_grid_label(result.target, *wo.DIFFICULTIES[difficulty]['grid'])}")

    if total_attempts:
        # Image generation dominates; the two vision calls add roughly $0.04 per attempt.
        print(f"\n{total_attempts} attempts, rough cost ${total_attempts * 0.21:.2f}")
    print(f"\nInspect the PNGs in {out_dir} -- the mascot must look drawn by the same "
          f"illustrator as everything else, not pasted on top.")
    return 0


# ---------------------------------------------------------------------------

def run_offline():
    run_columns()
    run_grid()
    run_clicks()
    run_geometry()
    run_grading()
    run_parsing()
    run_validation()
    run_prompts()
    run_placement()
    run_target_box()
    run_mask_building()
    run_crop_mapping()
    run_hybrid_prompts()
    run_text_extraction()
    run_cropping()
    run_pipeline()
    run_hybrid_pipeline()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true",
                        help="also generate real puzzles against the live APIs (costs money)")
    parser.add_argument("--difficulty", default="hard", choices=wo.DIFFICULTY_ORDER)
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()

    run_offline()
    print(f"\noffline tier: {len(_FAILURES)} failing")
    for note in _FAILURES:
        print(f"  - {note}")

    if args.live:
        asyncio.run(run_live(args.difficulty, args.count))

    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
