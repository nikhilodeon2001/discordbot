"""
Greg's Nightmare -- procedural math trivia question engine.

Pure-logic module (mirrors answer_matching.py): generates questions, renders
them to PNG images, and grades free-text answers, with no Discord dependency.
The only external dependency is discordbot.get_font (for the shared, S3-backed
font cache), imported lazily inside the render helpers to avoid a circular
import at module load time -- same convention mini_games.py uses for pulling
game functions out of discordbot.

Every category exposes a "normal" and a "hard" difficulty. All correct
answers and multiple-choice options are plain ASCII strings a player can type
on a phone keyboard (decimals, "a/b" fractions, "(x, y)" pairs, "^" for
exponents) -- nothing requires a symbol keyboard (no √, ∫, θ, π glyphs).
"""

import io
import math
import random
import re


CATEGORIES = [
    {"name": "algebra", "url": "algebra", "emoji": "➗", "display": "Algebra"},
    {"name": "geometry", "url": "geometry", "emoji": "📐", "display": "Geometry"},
    {"name": "trigonometry", "url": "trig", "emoji": "🔺", "display": "Trigonometry"},
    {"name": "calculus", "url": "calculus", "emoji": "📈", "display": "Calculus"},
    {"name": "statistics", "url": "stats", "emoji": "📊", "display": "Statistics"},
    {"name": "number theory", "url": "numbertheory", "emoji": "🔢", "display": "Number Theory"},
    {"name": "probability", "url": "probability", "emoji": "🎲", "display": "Probability"},
    {"name": "sequences", "url": "sequences", "emoji": "🔁", "display": "Sequences"},
    {"name": "coordinate geometry", "url": "coordgeo", "emoji": "📍", "display": "Coordinate Geometry"},
    {"name": "exponents", "url": "explog", "emoji": "⚡", "display": "Exponents & Logs"},
]

CATEGORY_URLS = {c["url"] for c in CATEGORIES}

# One of these is picked at random per question (not per category) -- high-saturation,
# high-brightness colors chosen to read clearly against the black canvas background.
_NEON_COLORS = [
    (57, 255, 20),    # neon green
    (255, 16, 240),   # neon magenta
    (0, 255, 255),    # neon cyan
    (255, 255, 0),    # neon yellow
    (255, 95, 31),    # neon orange
    (0, 191, 255),    # neon sky blue
    (191, 0, 255),    # neon purple
    (255, 7, 58),     # neon red
    (0, 255, 128),    # neon spring green
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _get_font(size):
    from discordbot import get_font
    return get_font("DejaVuSans.ttf", size)


def _wrap_lines(measure_draw, text, font, max_width):
    """Greedy word-wrap: pack words onto a line until the next one would overflow
    max_width, then start a new line. A single word longer than max_width on its
    own is left as-is rather than split mid-word."""
    words = text.split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        bbox = measure_draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _fit_wrapped(measure_draw, text, max_width, start_size, min_size, max_lines):
    """Shrink the font until the wrapped text fits within max_lines (or bottoms out
    at min_size, in which case the last -- most-wrapped -- attempt is used as-is)."""
    size = start_size
    font = _get_font(size)
    lines = _wrap_lines(measure_draw, text, font, max_width)
    while len(lines) > max_lines and size > min_size:
        size -= 2
        font = _get_font(size)
        lines = _wrap_lines(measure_draw, text, font, max_width)
    return font, lines


def _line_height(font):
    bbox = font.getbbox("Ag")
    return (bbox[3] - bbox[1]) + 12


def _draw_centered_lines(draw, lines, font, y, width, color):
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (width - (bbox[2] - bbox[0])) // 2 - bbox[0]
        draw.text((x, y), line, fill=color, font=font)
        y += _line_height(font)
    return y


def _render_composed_image(question_text, math_line=None, shape_fn=None,
                            header_color=(57, 255, 20), content_color=(57, 255, 20)):
    """Renders the *entire* question -- instruction text plus the math content (an
    expression/dataset, or a drawn diagram) -- into one self-contained image, with
    real word-wrapping so long sentences (e.g. probability's full word problems)
    never run off the edge of the canvas. Nothing about the question is meant to
    be shown anywhere else (no separate embed caption) -- the image is the point."""
    from PIL import Image, ImageDraw

    width = 600
    margin = 40
    max_width = width - 2 * margin
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    # When there's secondary math content (an expression or a diagram), the
    # instruction text plays a smaller, supporting role; when it's the only
    # content (e.g. a probability word problem), it needs to be the headline.
    header_start_size = 26 if (math_line or shape_fn) else 36
    header_font, header_lines = _fit_wrapped(probe, question_text, max_width, header_start_size, 16, 5)
    header_block_height = len(header_lines) * _line_height(header_font)

    shape_height = 350
    body_font, body_lines, body_block_height = None, [], 0
    if shape_fn is not None:
        content_height = shape_height
    elif math_line:
        body_font, body_lines = _fit_wrapped(probe, math_line, max_width, 46, 22, 3)
        body_block_height = len(body_lines) * _line_height(body_font)
        content_height = body_block_height
    else:
        content_height = 0

    spacing = 25 if content_height else 0
    height = max(150, margin + header_block_height + spacing + content_height + margin)

    img = Image.new("RGB", (width, height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = _draw_centered_lines(draw, header_lines, header_font, margin, width, header_color)
    y += spacing

    if shape_fn is not None:
        shape_fn(draw, _get_font(28), width, shape_height, y, content_color)
    elif math_line:
        _draw_centered_lines(draw, body_lines, body_font, y, width, content_color)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _to_superscript(n):
    superscript_map = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵",
                        "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻"}
    return "".join(superscript_map[d] for d in str(n))


def _reduce_fraction(num, den):
    if den < 0:
        num, den = -num, -den
    g = math.gcd(abs(num), abs(den)) or 1
    return num // g, den // g


def _fmt_fraction(num, den):
    num, den = _reduce_fraction(num, den)
    return str(num) if den == 1 else f"{num}/{den}"


def _parse_number(s):
    if s is None:
        return None
    match = re.search(r"-?\d+\.?\d*", s.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def _parse_fraction(s):
    """Returns a float from either an 'a/b' fraction or a plain decimal."""
    if s is None:
        return None
    frac_match = re.search(r"(-?\d+)\s*/\s*(-?\d+)", s)
    if frac_match:
        num, den = int(frac_match.group(1)), int(frac_match.group(2))
        if den == 0:
            return None
        return num / den
    return _parse_number(s)


def _close(a, b, tol=0.06):
    return a is not None and b is not None and abs(a - b) <= tol


_FRACTION_RE = re.compile(r"\s*(-?\d+)\s*/\s*(-?\d+)\s*")
_PAIR_RE = re.compile(r"\s*\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)\s*")


def _bump_value(correct, filler):
    """Produce a same-shape-but-numerically-different string, so a padded filler
    choice can never accidentally parse back to the same value as `correct` --
    a plain string suffix (e.g. "1/6~1") would still regex-match as "1/6"."""
    frac_match = _FRACTION_RE.fullmatch(correct)
    if frac_match:
        num, den = int(frac_match.group(1)), int(frac_match.group(2))
        return _fmt_fraction(num + filler, den)
    pair_match = _PAIR_RE.fullmatch(correct)
    if pair_match:
        x, y = pair_match.group(1), pair_match.group(2)
        bumped_x = (float(x) if "." in x else int(x)) + filler
        return f"({bumped_x}, {y})"
    if re.fullmatch(r"-?\d+\.?\d*", correct):
        bumped = (float(correct) if "." in correct else int(correct)) + filler
        return f"{bumped:.1f}" if "." in correct else str(bumped)
    return f"{correct} ({filler})"


def _values_equal(a, b):
    """Numeric-aware equality so e.g. '8' and '8.0', or two equivalent unreduced
    fractions, are recognized as duplicates when assembling MC choices -- plain
    string equality would let both appear as separate buttons for the same value."""
    if a == b:
        return True
    fa, fb = _FRACTION_RE.fullmatch(a), _FRACTION_RE.fullmatch(b)
    if fa and fb:
        na, da = int(fa.group(1)), int(fa.group(2))
        nb, db = int(fb.group(1)), int(fb.group(2))
        return da != 0 and db != 0 and na * db == nb * da
    pa, pb = _PAIR_RE.fullmatch(a), _PAIR_RE.fullmatch(b)
    if pa and pb:
        return float(pa.group(1)) == float(pb.group(1)) and float(pa.group(2)) == float(pb.group(2))
    if fa or fb or pa or pb:
        return False
    # Only compare numerically when BOTH strings are nothing but a number --
    # matching a number *within* a longer expression (e.g. calculus's "45x² +
    # 14x") would treat unrelated compound answers as duplicates whenever they
    # happen to share a leading digit, which also makes the padding loop below
    # loop forever (every filler-bumped candidate still contains that digit).
    if re.fullmatch(r"-?\d+\.?\d*", a) and re.fullmatch(r"-?\d+\.?\d*", b):
        return abs(float(a) - float(b)) < 1e-9
    return False


def _make_mc_choices(correct, wrongs):
    """Dedupe wrong answers against the correct one and each other, shuffle."""
    choices = [correct]
    for w in wrongs:
        if not any(_values_equal(w, c) for c in choices):
            choices.append(w)
    # Pad if collisions collapsed us below 4 unique choices.
    filler = 1
    while len(choices) < 4:
        candidate = _bump_value(correct, filler)
        if not any(_values_equal(candidate, c) for c in choices):
            choices.append(candidate)
        filler += 1
    choices = choices[:4]
    random.shuffle(choices)
    return choices


# ---------------------------------------------------------------------------
# Algebra
# ---------------------------------------------------------------------------

def _fmt_coef(a, var="x"):
    if a == 1:
        return var
    if a == -1:
        return f"-{var}"
    return f"{a}{var}"


def _gen_linear(hard):
    if hard:
        x = random.choice([i for i in range(-15, 16) if i != 0])
        a = random.choice([i for i in range(-9, 10) if i != 0])
        c = random.choice([i for i in range(-9, 10) if i != 0 and i != a])
        b = random.choice([i for i in range(-15, 16) if i != 0])
        d = b + (a - c) * x
        left = f"{_fmt_coef(a)} {'+' if b >= 0 else '-'} {abs(b)}"
        right = f"{_fmt_coef(c)} {'+' if d >= 0 else '-'} {abs(d)}"
        display = f"{left} = {right}"
    else:
        a = random.choice([i for i in range(-10, 11) if i != 0])
        x = random.choice([i for i in range(-20, 21) if i != 0])
        b = random.choice([i for i in range(-20, 21) if i != 0])
        c = a * x + b
        display = f"{_fmt_coef(a)} {'+' if b >= 0 else '-'} {abs(b)} = {c}"

    answer = str(x)
    wrongs = [str(x + 1), str(x - 1), str(-x)]
    return {"question_text": "Solve for x:", "display": display, "answer": answer, "wrongs": wrongs}


def _factor_term(z):
    return f"(x - {z})" if z >= 0 else f"(x + {abs(z)})"


def _build_quadratic():
    """A quadratic with two known integer roots z1, z2 -- ported from the in-game
    trivia engine's zeroes/zeroes-sum/zeroes-product/factors question family
    (discordbot.py's generate_and_render_polynomial), which Greg's Nightmare folds
    into Algebra as additional subtypes rather than a separate category."""
    z1 = random.choice([i for i in range(-9, 10) if i != 0])
    z2 = random.choice([i for i in range(-9, 10) if i != 0 and i != z1])
    b = -(z1 + z2)
    c = z1 * z2
    b_coef = "" if abs(b) == 1 else str(abs(b))
    b_term = "" if b == 0 else f" {'+' if b >= 0 else '-'} {b_coef}x"
    c_term = f" {'+' if c >= 0 else '-'} {abs(c)}"
    display = f"x²{b_term}{c_term}"
    return z1, z2, display


def _gen_zeroes_sum_product():
    z1, z2, display = _build_quadratic()
    ask_sum = random.choice([True, False])
    answer_val = z1 + z2 if ask_sum else z1 * z2
    wrong_val = z1 * z2 if ask_sum else z1 + z2
    wrongs = [str(wrong_val), str(answer_val + 1), str(-answer_val)]
    return {
        "question_text": f"For the quadratic below, find the {'sum' if ask_sum else 'product'} of its zeroes:",
        "display": display,
        "answer": str(answer_val),
        "wrongs": wrongs,
    }


def _gen_zeroes():
    z1, z2, display = _build_quadratic()
    lo, hi = sorted((z1, z2))
    answer = f"{lo}, {hi}"
    # The checker compares pairs as unordered sets, so a candidate distractor whose
    # *set* of values happens to equal {lo, hi} (e.g. negating both roots of a
    # symmetric pair like -2/2) would silently grade as correct -- filter those out.
    candidates = [f"{lo + 1}, {hi}", f"{lo}, {hi + 1}", f"{-lo}, {-hi}", f"{lo - 1}, {hi}", f"{lo}, {hi - 1}"]
    wrongs = []
    seen = {frozenset((lo, hi))}
    for candidate in candidates:
        pair = frozenset(int(x) for x in re.findall(r"-?\d+", candidate))
        if pair in seen:
            continue
        seen.add(pair)
        wrongs.append(candidate)
        if len(wrongs) == 3:
            break
    return {
        "question_text": "Find the two zeroes of the quadratic below (either order):",
        "display": display,
        "answer": answer,
        "wrongs": wrongs,
    }


def _gen_factors():
    z1, z2, display = _build_quadratic()
    answer = f"{_factor_term(z1)}{_factor_term(z2)}"
    # Both factor orders grade as correct, so a distractor built from a root pair
    # that's a permutation of {z1, z2} (e.g. negating a symmetric -k/k pair leaves
    # the same set) would silently match too -- filter those out, same as _gen_zeroes.
    candidate_pairs = [(z1 + 1, z2), (z1, z2 + 1), (-z1, -z2), (z1 - 1, z2), (z1, z2 - 1)]
    wrongs = []
    seen = {frozenset((z1, z2))}
    for a, b in candidate_pairs:
        pair = frozenset((a, b))
        if pair in seen:
            continue
        seen.add(pair)
        wrongs.append(f"{_factor_term(a)}{_factor_term(b)}")
        if len(wrongs) == 3:
            break
    return {"question_text": "Factor the quadratic below:", "display": display, "answer": answer, "wrongs": wrongs}


def _gen_algebra(difficulty):
    if difficulty == "hard":
        subtype = random.choice(["linear", "zeroes", "factors"])
        if subtype == "linear":
            return _gen_linear(hard=True)
        return _gen_zeroes() if subtype == "zeroes" else _gen_factors()

    subtype = random.choice(["linear", "zeroes_sum_product"])
    return _gen_linear(hard=False) if subtype == "linear" else _gen_zeroes_sum_product()


def _check_algebra(guess, answer):
    if "," in answer:
        # "zeroes" -- an unordered pair, e.g. "-3, 5"; order doesn't matter.
        guess_nums = sorted(int(x) for x in re.findall(r"-?\d+", guess))
        answer_nums = sorted(int(x) for x in re.findall(r"-?\d+", answer))
        return len(guess_nums) >= 2 and guess_nums[:2] == answer_nums[:2]
    if "(" in answer:
        # "factors" -- e.g. "(x - 3)(x + 5)"; either factor order is accepted.
        norm = lambda s: s.lower().replace(" ", "").replace("*", "")
        parts = re.findall(r"\([^)]*\)", answer)
        swapped = "".join(reversed(parts))
        g = norm(guess)
        return g == norm(answer) or g == norm(swapped)
    n = _parse_number(guess)
    return n is not None and n == float(answer)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def _draw_rectangle(draw, font, w, h, base, height, y_offset=0, color=(57, 255, 20)):
    x0, y0, x1, y1 = 100, 80 + y_offset, 400, 260 + y_offset
    draw.rectangle([x0, y0, x1, y1], outline=color, width=4)
    draw.text(((x0 + x1) // 2 - 10, y1 + 10), str(base), fill=color, font=font)
    draw.text((x1 + 15, (y0 + y1) // 2 - 15), str(height), fill=color, font=font)


def _draw_circle(draw, font, w, h, radius_label, y_offset=0, color=(57, 255, 20)):
    cx, cy, r = 250, 170 + y_offset, 100
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=4)
    draw.line([cx, cy, cx + r, cy], fill=color, width=3)
    draw.text((cx + r // 2 - 10, cy - 35), str(radius_label), fill=color, font=font)


def _draw_right_triangle(draw, font, w, h, leg_a, leg_b, hyp, unknown, y_offset=0, color=(57, 255, 20)):
    x0, y0 = 100, 280 + y_offset
    x1, y1 = 400, 280 + y_offset
    x2, y2 = 100, 80 + y_offset
    draw.polygon([(x0, y0), (x1, y1), (x2, y2)], outline=color, width=4)
    draw.rectangle([x0, y0 - 18, x0 + 18, y0], outline=color, width=2)
    bottom_label = "?" if unknown == "base" else str(leg_a)
    side_label = "?" if unknown == "height" else str(leg_b)
    draw.text(((x0 + x1) // 2 - 10, y0 + 10), bottom_label, fill=color, font=font)
    draw.text((x0 - 45, (y0 + y2) // 2 - 15), side_label, fill=color, font=font)
    if hyp is not None:
        hyp_label = "?" if unknown == "hyp" else str(hyp)
        draw.text(((x1 + x2) // 2 + 10, (y1 + y2) // 2 - 25), hyp_label, fill=color, font=font)


def _gen_geometry(difficulty):
    if difficulty == "hard":
        leg_a = random.randint(4, 20)
        leg_b = random.randint(4, 20)
        while round(math.sqrt(leg_a ** 2 + leg_b ** 2), 1).is_integer():
            leg_b = random.randint(4, 20)
        unknown = "hyp"
        hyp = round(math.sqrt(leg_a ** 2 + leg_b ** 2), 1)
        answer = f"{hyp:.1f}"
        wrongs = [str(leg_a + leg_b), f"{round(math.sqrt(leg_a * leg_b), 1):.1f}", f"{hyp + 1:.1f}"]
        shape_fn = lambda d, f, w, h, yo, c: _draw_right_triangle(d, f, w, h, leg_a, leg_b, hyp, unknown, yo, c)
        return {
            "question_text": "Find the length of the hypotenuse (round to 1 decimal):",
            "shape_fn": shape_fn,
            "answer": answer,
            "wrongs": wrongs,
        }

    shape = random.choice(["rectangle", "circle", "triangle"])
    if shape == "rectangle":
        base = random.randint(3, 15)
        height = random.randint(3, 15)
        ask_area = random.choice([True, False])
        answer_val = base * height if ask_area else 2 * (base + height)
        question_text = f"Find the {'area' if ask_area else 'perimeter'} of the rectangle:"
        wrongs = [str(2 * (base + height) if ask_area else base * height),
                  str(base + height), str(answer_val + base)]
        shape_fn = lambda d, f, w, h, yo, c: _draw_rectangle(d, f, w, h, base, height, yo, c)
    elif shape == "circle":
        r = random.randint(3, 12)
        ask_area = random.choice([True, False])
        answer_val = round(3.14 * r * r, 1) if ask_area else round(2 * 3.14 * r, 1)
        question_text = f"Find the {'area' if ask_area else 'circumference'} of the circle (use π ≈ 3.14, round to 1 decimal):"
        wrongs = [f"{round(2 * 3.14 * r, 1) if ask_area else round(3.14 * r * r, 1):.1f}",
                  f"{round(3.14 * (2 * r) if ask_area else 3.14 * (2 * r) * (2 * r), 1):.1f}",
                  f"{answer_val + 1:.1f}"]
        shape_fn = lambda d, f, w, h, yo, c: _draw_circle(d, f, w, h, r, yo, c)
    else:
        base = random.randint(4, 16)
        height = random.randint(4, 16)
        answer_val = round(0.5 * base * height, 1)
        question_text = "Find the area of the triangle:"
        wrongs = [str(base * height), f"{round(0.5 * (base + height), 1):.1f}", f"{answer_val + 1:.1f}"]
        shape_fn = lambda d, f, w, h, yo, c: _draw_right_triangle(d, f, w, h, base, height, None, None, yo, c)

    answer = f"{answer_val:.1f}" if isinstance(answer_val, float) and not float(answer_val).is_integer() else str(int(answer_val))
    return {"question_text": question_text, "shape_fn": shape_fn, "answer": answer, "wrongs": wrongs}


def _check_geometry(guess, answer):
    n = _parse_number(guess)
    return _close(n, float(answer), tol=0.05)


# ---------------------------------------------------------------------------
# Trigonometry
# ---------------------------------------------------------------------------

_TRIG_ANGLES = [0, 30, 45, 60, 90]

# Ported from the in-game engine's generate_trig_question: a generic right triangle
# labeled x (adjacent), y (opposite), z (hypotenuse) with angle θ, where the answer
# is the ratio itself (e.g. "y/z") rather than a computed value.
_RATIO_MAP = {"sin": "y/z", "cos": "x/z", "tan": "y/x", "cot": "x/y", "sec": "z/x", "csc": "z/y"}


def _draw_ratio_triangle(draw, font, w, h, y_offset=0, color=(57, 255, 20)):
    x0, y0 = 100, 280 + y_offset
    x1, y1 = 400, 280 + y_offset
    x2, y2 = 100, 80 + y_offset
    draw.polygon([(x0, y0), (x1, y1), (x2, y2)], outline=color, width=4)
    draw.rectangle([x0, y0 - 18, x0 + 18, y0], outline=color, width=2)
    draw.text((x1 - 55, y1 - 45), "θ", fill=color, font=font)
    draw.text(((x0 + x1) // 2 - 5, y0 + 10), "x", fill=color, font=font)
    draw.text((x0 - 35, (y0 + y2) // 2 - 15), "y", fill=color, font=font)
    draw.text(((x1 + x2) // 2 + 10, (y1 + y2) // 2 - 25), "z", fill=color, font=font)


def _gen_trig_ratio():
    func = random.choice(list(_RATIO_MAP.keys()))
    answer = _RATIO_MAP[func]
    wrongs = random.sample([v for k, v in _RATIO_MAP.items() if k != func], 3)
    return {
        "question_text": f"What is {func}(θ) in the triangle below?",
        "shape_fn": _draw_ratio_triangle,
        "answer": answer,
        "wrongs": wrongs,
    }


def _gen_trig(difficulty):
    if difficulty == "hard":
        angle = random.choice([30, 45, 60])
        given_side = random.choice(["opposite", "adjacent", "hyp"])
        unknown = random.choice([s for s in ["opposite", "adjacent", "hyp"] if s != given_side])
        base_len = random.randint(5, 20)
        rad = math.radians(angle)
        if given_side == "hyp":
            hyp = base_len
            opposite = hyp * math.sin(rad)
            adjacent = hyp * math.cos(rad)
        elif given_side == "adjacent":
            adjacent = base_len
            hyp = adjacent / math.cos(rad)
            opposite = hyp * math.sin(rad)
        else:
            opposite = base_len
            hyp = opposite / math.sin(rad)
            adjacent = hyp * math.cos(rad)
        values = {"opposite": opposite, "adjacent": adjacent, "hyp": hyp}
        answer_val = round(values[unknown], 1)
        given_val = round(values[given_side], 1)
        leg_a = round(values["adjacent"], 1) if unknown != "adjacent" else "?"
        leg_b = round(values["opposite"], 1) if unknown != "opposite" else "?"
        hyp_disp = round(values["hyp"], 1) if unknown != "hyp" else "?"

        def draw(d, f, w, h, yo=0, color=(57, 255, 20)):
            x0, y0 = 100, 280 + yo
            x1, y1 = 400, 280 + yo
            x2, y2 = 100, 80 + yo
            d.polygon([(x0, y0), (x1, y1), (x2, y2)], outline=color, width=4)
            d.rectangle([x0, y0 - 18, x0 + 18, y0], outline=color, width=2)
            # adjacent (leg_a) runs x0->x1 and opposite (leg_b) runs x0->x2, so the
            # angle they're measured from sits at the OTHER acute vertex, (x1, y1) --
            # not next to the right-angle marker at (x0, y0).
            d.text((x1 - 70, y1 - 45), f"{angle}°", fill=color, font=f)
            d.text(((x0 + x1) // 2 - 10, y0 + 10), str(leg_a), fill=color, font=f)
            d.text((x0 - 55, (y0 + y2) // 2 - 15), str(leg_b), fill=color, font=f)
            d.text(((x1 + x2) // 2 + 10, (y1 + y2) // 2 - 25), str(hyp_disp), fill=color, font=f)

        wrongs = [f"{round(values[given_side] * math.tan(rad), 1):.1f}",
                  f"{answer_val + 1:.1f}", f"{round(given_val * math.sin(rad), 1):.1f}"]
        return {
            "question_text": f"Given the {angle}° angle, find the unknown side (round to 1 decimal):",
            "shape_fn": draw,
            "answer": f"{answer_val:.1f}",
            "wrongs": wrongs,
        }

    if random.choice([True, False]):
        return _gen_trig_ratio()

    func = random.choice(["sin", "cos", "tan"])
    angle = random.choice([a for a in _TRIG_ANGLES if not (func == "tan" and a == 90)])
    rad = math.radians(angle)
    value = {"sin": math.sin, "cos": math.cos, "tan": math.tan}[func](rad)
    answer_val = round(value, 2)
    other_funcs = {"sin": math.cos, "cos": math.sin, "tan": lambda r: 1 / math.tan(r) if math.tan(r) else 0}
    wrongs = [f"{round(other_funcs[func](rad), 2):.2f}", f"{round(answer_val + 0.5, 2):.2f}", f"{round(1 - answer_val, 2):.2f}"]
    return {
        "question_text": f"Evaluate {func}({angle}°). Round to 2 decimals:",
        "display": f"{func}({angle}°) = ?",
        "answer": f"{answer_val:.2f}",
        "wrongs": wrongs,
    }


def _check_trig(guess, answer):
    if re.fullmatch(r"[a-zA-Z]+/[a-zA-Z]+", answer.replace(" ", "")):
        norm = lambda s: s.strip().lower().replace(" ", "").replace("(", "").replace(")", "")
        return norm(guess) == norm(answer)
    n = _parse_number(guess)
    return _close(n, float(answer), tol=0.05 if abs(float(answer)) < 5 else 0.15)


# ---------------------------------------------------------------------------
# Calculus
# ---------------------------------------------------------------------------

def _poly_term(coef, power):
    sign = "-" if coef < 0 else "+"
    abs_coef = abs(coef)
    coef_str = "" if abs_coef == 1 and power != 0 else str(abs_coef)
    if power == 0:
        text = str(abs_coef)
    elif power == 1:
        text = f"{coef_str}x"
    else:
        text = f"{coef_str}x{_to_superscript(power)}"
    return sign, text


def _join_signed(terms):
    if not terms:
        return "0"
    sign, text = terms[0]
    result = f"-{text}" if sign == "-" else text
    for sign, text in terms[1:]:
        result += f" {sign} {text}"
    return result


def _gen_calculus(difficulty):
    if difficulty == "hard":
        return _gen_calculus_hard_numeric()

    powers = sorted(random.sample([1, 2, 3], 2), reverse=True)
    coefs = [random.randint(1, 20) * random.choice([-1, 1]) for _ in powers]
    terms = [_poly_term(coef, power) for coef, power in zip(coefs, powers)]
    deriv_terms = [_poly_term(coef * power, power - 1) for coef, power in zip(coefs, powers)]
    # Forgot-the-power-rule-multiply mistake: drops the exponent by one without
    # scaling the coefficient. Numerically distinct from the real derivative
    # (unlike a mere term reorder, which the order-independent checker would
    # accept as equivalent, making it a useless MC distractor).
    forgot_multiply_terms = [_poly_term(coef, power - 1) for coef, power in zip(coefs, powers)]
    const = random.randint(1, 20) * random.choice([-1, 1])
    terms.append(_poly_term(const, 0))

    polynomial = _join_signed(terms)
    derivative = _join_signed(deriv_terms)

    wrong1 = _join_signed(forgot_multiply_terms)
    wrong2 = _join_signed([("-" if s == "+" else "+", t) for s, t in deriv_terms])
    wrong3 = polynomial

    return {
        "question_text": "Find the derivative:",
        "display": polynomial,
        "answer": derivative,
        "wrongs": [wrong1, wrong2, wrong3],
    }


def _gen_calculus_hard_numeric():
    powers = sorted(random.sample([1, 2, 3, 4], 2), reverse=True)
    coefs = {p: random.randint(1, 12) * random.choice([-1, 1]) for p in powers}
    const = random.randint(1, 15) * random.choice([-1, 1])
    k = random.choice([i for i in range(-3, 4) if i != 0])

    terms = [_poly_term(coefs[p], p) for p in powers] + [_poly_term(const, 0)]
    polynomial = _join_signed(terms)

    def f(x):
        return sum(coefs[p] * (x ** p) for p in powers) + const

    def fprime(x):
        return sum(coefs[p] * p * (x ** (p - 1)) for p in powers)

    answer_val = fprime(k)
    without_const = sum(coefs[p] * (k ** p) for p in powers)
    wrongs = [str(f(k)), str(fprime(k + 1)), str(without_const)]
    return {
        "question_text": f"For f(x) shown below, find f'({k}):",
        "display": polynomial,
        "answer": str(answer_val),
        "wrongs": wrongs,
    }


_SUPERSCRIPT_REVERSE = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5",
                         "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁻": "-"}


def _normalize_superscripts(text):
    return "".join(_SUPERSCRIPT_REVERSE.get(ch, ch) for ch in text)


def _term_set(expr):
    # "^" and unicode superscripts (x², from the rendered image) both normalize to
    # plain digits, so "6x^2" and "6x2" grade the same as the image's "6x²".
    expr = expr.lower().replace(" ", "").replace("^", "").replace("*", "")
    expr = _normalize_superscripts(expr)
    terms = re.findall(r"[+-]?[^+-]+", expr)
    cleaned = (t[1:] if t.startswith("+") else t for t in terms if t)
    return {t for t in cleaned if t.lstrip("-") != "0"}


def _check_calculus(guess, answer):
    if re.fullmatch(r"-?\d+", answer.replace(" ", "")):
        n = _parse_number(guess)
        return n is not None and n == float(answer)
    return _term_set(guess) == _term_set(answer)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def _gen_stats(difficulty):
    if difficulty == "hard":
        n = random.randint(4, 5)
        nums = [random.randint(1, 15) for _ in range(n)]
        mean = sum(nums) / n
        variance = sum((x - mean) ** 2 for x in nums) / n
        std = round(math.sqrt(variance), 1)
        wrongs = [f"{round(math.sqrt(sum((x - mean) ** 2 for x in nums) / (n - 1)), 1):.1f}",
                  f"{round(variance, 1):.1f}", f"{std + 0.5:.1f}"]
        return {
            "question_text": "Find the population standard deviation (round to 1 decimal):",
            "display": ", ".join(str(x) for x in nums),
            "answer": f"{std:.1f}",
            "wrongs": wrongs,
        }

    kind = random.choice(["mean", "median", "mode", "range"])
    if kind == "mode":
        n = random.randint(4, 6)
        nums = [random.randint(1, 15) for _ in range(n - 1)]
        mode_val = random.choice(nums)
        nums.append(mode_val)
        random.shuffle(nums)
        answer_val = mode_val
        others = [x for x in nums if x != mode_val]
        wrongs = [str(random.choice(others) if others else mode_val + 1), str(min(nums)), str(max(nums))]
    elif kind == "range":
        n = random.randint(4, 6)
        nums = [random.randint(1, 20) for _ in range(n)]
        answer_val = max(nums) - min(nums)
        wrongs = [str(max(nums)), str(min(nums)), str(answer_val + 2)]
    elif kind == "mean":
        while True:
            n = random.randint(3, 5)
            nums = [random.randint(1, 10) for _ in range(n)]
            if sum(nums) % n == 0:
                break
        answer_val = sum(nums) // n
        wrongs = [str(sum(nums)), str(sorted(nums)[len(nums) // 2]), str(answer_val + 1)]
    else:
        n = random.randint(3, 5)
        nums = [random.randint(1, 20) for _ in range(n)]
        sorted_nums = sorted(nums)
        mid = n // 2
        answer_val = sorted_nums[mid] if n % 2 else (sorted_nums[mid - 1] + sorted_nums[mid]) / 2
        wrongs = [str(round(sum(nums) / n, 1)), str(max(nums)), str(min(nums))]

    answer = str(answer_val) if float(answer_val).is_integer() else f"{answer_val:.1f}"
    return {
        "question_text": f"Find the {kind} of the dataset:",
        "display": ", ".join(str(x) for x in nums),
        "answer": answer,
        "wrongs": wrongs,
    }


def _check_stats(guess, answer):
    n = _parse_number(guess)
    return _close(n, float(answer), tol=0.05)


# ---------------------------------------------------------------------------
# Number Theory / Arithmetic
# ---------------------------------------------------------------------------

def _gen_base_conversion(hard):
    """Ported from the in-game engine's generate_base_question (base-2/3/4 to
    decimal); hard mode widens the base range and digit count."""
    if hard:
        input_base = random.choice([5, 6, 7, 8])
        num_digits = random.choice([3, 4])
    else:
        input_base = random.choice([2, 3, 4])
        num_digits = 3
    first = random.randint(1, input_base - 1)
    digits = str(first) + "".join(str(random.randint(0, input_base - 1)) for _ in range(num_digits - 1))
    answer_val = int(digits, input_base)
    question_text = f"Convert the base-{input_base} number below to decimal:"
    wrongs = [str(int(digits)), str(answer_val + input_base), str(max(0, answer_val - 1))]
    return {"question_text": question_text, "display": digits, "answer": str(answer_val), "wrongs": wrongs}


def _gen_numbertheory(difficulty):
    if difficulty == "hard":
        kind = random.choice(["gcd", "primefactors", "base"])
        if kind == "base":
            return _gen_base_conversion(hard=True)
        if kind == "gcd":
            a = random.randint(20, 120)
            b = random.randint(20, 120)
            answer_val = math.gcd(a, b)
            wrongs = [str(a * b // answer_val), str(answer_val + 1), str(min(a, b))]
            question_text = f"Find the GCD of {a} and {b}:"
        else:
            n = random.choice([12, 18, 20, 24, 30, 36, 40, 42, 45, 60, 66, 70, 72, 84, 90, 100])
            factors = set()
            m = n
            d = 2
            while d * d <= m:
                if m % d == 0:
                    factors.add(d)
                    while m % d == 0:
                        m //= d
                d += 1
            if m > 1:
                factors.add(m)
            answer_val = len(factors)
            wrongs = [str(answer_val + 1), str(max(1, answer_val - 1)), str(len(factors) * 2)]
            question_text = f"How many distinct prime factors does {n} have?"
        return {"question_text": question_text, "display": None, "answer": str(answer_val), "wrongs": wrongs}

    kind = random.choice(["percent", "gcdlcm", "base"])
    if kind == "base":
        return _gen_base_conversion(hard=False)
    if kind == "percent":
        p = random.choice([5, 10, 15, 20, 25, 40, 50, 60, 75, 80])
        n = random.choice([20, 40, 60, 80, 100, 120, 140, 160, 180, 200])
        answer_val = p * n // 100
        question_text = f"What is {p}% of {n}?"
        wrongs = [str(p), str(n - answer_val), str(answer_val * 2)]
    else:
        a = random.randint(6, 30)
        b = random.randint(6, 30)
        ask_gcd = random.choice([True, False])
        g = math.gcd(a, b)
        answer_val = g if ask_gcd else (a * b // g)
        question_text = f"Find the {'GCD' if ask_gcd else 'LCM'} of {a} and {b}:"
        wrongs = [str(a * b // g if ask_gcd else g), str(a), str(b)]

    return {"question_text": question_text, "display": None, "answer": str(answer_val), "wrongs": wrongs}


def _check_numbertheory(guess, answer):
    n = _parse_number(guess)
    return n is not None and n == float(answer)


# ---------------------------------------------------------------------------
# Probability
# ---------------------------------------------------------------------------

def _gen_probability(difficulty):
    if difficulty == "hard":
        kind = random.choice(["independent", "dependent"])
        if kind == "independent":
            target1 = random.randint(1, 6)
            target2 = random.randint(1, 6)
            question_text = f"Two dice are rolled. What is the probability die 1 shows a {target1} and die 2 shows a {target2}?"
            answer = _fmt_fraction(1, 36)
            wrongs = [_fmt_fraction(1, 6), _fmt_fraction(2, 36), _fmt_fraction(1, 12)]
        else:
            question_text = "Two cards are drawn from a standard 52-card deck without replacement. What is the probability both are Aces?"
            answer = _fmt_fraction(4 * 3, 52 * 51)
            wrongs = [_fmt_fraction(4, 52), _fmt_fraction(1, 13), _fmt_fraction(4 * 4, 52 * 52)]
        return {"question_text": question_text, "display": None, "answer": answer, "wrongs": wrongs}

    kind = random.choice(["die_single", "die_range", "coin", "card_rank", "card_suit"])
    if kind == "die_single":
        target = random.randint(1, 6)
        question_text = f"A fair 6-sided die is rolled. What is the probability of rolling a {target}?"
        answer = _fmt_fraction(1, 6)
        wrongs = [_fmt_fraction(1, 3), _fmt_fraction(1, 2), _fmt_fraction(2, 6)]
    elif kind == "die_range":
        question_text = "A fair 6-sided die is rolled. What is the probability of rolling an even number?"
        answer = _fmt_fraction(3, 6)
        wrongs = [_fmt_fraction(1, 6), _fmt_fraction(2, 6), _fmt_fraction(4, 6)]
    elif kind == "coin":
        question_text = "A fair coin is flipped twice. What is the probability of getting heads both times?"
        answer = _fmt_fraction(1, 4)
        wrongs = [_fmt_fraction(1, 2), _fmt_fraction(1, 3), _fmt_fraction(2, 4)]
    elif kind == "card_rank":
        question_text = "A card is drawn from a standard 52-card deck. What is the probability it's an Ace?"
        answer = _fmt_fraction(4, 52)
        wrongs = [_fmt_fraction(1, 4), _fmt_fraction(1, 52), _fmt_fraction(4, 13)]
    else:
        question_text = "A card is drawn from a standard 52-card deck. What is the probability it's a Heart?"
        answer = _fmt_fraction(13, 52)
        wrongs = [_fmt_fraction(1, 13), _fmt_fraction(1, 2), _fmt_fraction(4, 52)]

    return {"question_text": question_text, "display": None, "answer": answer, "wrongs": wrongs}


def _check_probability(guess, answer):
    # Reduced fractions can be very small (e.g. 1/221), where a fixed absolute
    # float tolerance would consider almost any two small probabilities "close
    # enough". Cross-multiply exactly when the guess itself looks like a
    # fraction; only fall back to a tight decimal tolerance otherwise.
    ans_match = re.fullmatch(r"\s*(-?\d+)\s*/\s*(-?\d+)\s*", answer)
    ans_num, ans_den = int(ans_match.group(1)), int(ans_match.group(2))
    guess_match = re.search(r"(-?\d+)\s*/\s*(-?\d+)", guess)
    if guess_match:
        g_num, g_den = int(guess_match.group(1)), int(guess_match.group(2))
        return g_den != 0 and g_num * ans_den == ans_num * g_den
    n = _parse_number(guess)
    return _close(n, ans_num / ans_den, tol=0.002)


# ---------------------------------------------------------------------------
# Sequences & Patterns
# ---------------------------------------------------------------------------

def _gen_sequences(difficulty):
    if difficulty == "hard":
        kind = random.choice(["geometric", "nth_arithmetic"])
        if kind == "geometric":
            a1 = random.randint(1, 6)
            r = random.choice([2, 3, -2])
            terms = [a1 * (r ** i) for i in range(4)]
            answer_val = a1 * (r ** 4)
            question_text = "What is the next term in the geometric sequence?"
            display = ", ".join(str(t) for t in terms)
            wrongs = [str(terms[-1] + r), str(terms[-1] * r + 1), str(a1 * (r ** 3))]
        else:
            a1 = random.randint(1, 10)
            d = random.choice([i for i in range(-9, 10) if i != 0])
            n = random.randint(6, 15)
            answer_val = a1 + (n - 1) * d
            question_text = f"An arithmetic sequence starts at {a1} with common difference {d}. What is the {n}th term?"
            display = None
            wrongs = [str(a1 + n * d), str(a1 + (n - 2) * d), str(a1 * n + d)]
        return {"question_text": question_text, "display": display, "answer": str(answer_val), "wrongs": wrongs}

    a1 = random.randint(1, 20)
    d = random.choice([i for i in range(-9, 10) if i != 0])
    terms = [a1 + i * d for i in range(4)]
    answer_val = a1 + 4 * d
    wrongs = [str(a1 + 3 * d), str(a1 + 5 * d), str(terms[-1] - d)]
    return {
        "question_text": "What is the next term in the sequence?",
        "display": ", ".join(str(t) for t in terms),
        "answer": str(answer_val),
        "wrongs": wrongs,
    }


def _check_sequences(guess, answer):
    n = _parse_number(guess)
    return n is not None and n == float(answer)


# ---------------------------------------------------------------------------
# Coordinate Geometry
# ---------------------------------------------------------------------------

_PYTHAGOREAN_TRIPLES = [(3, 4, 5), (6, 8, 10), (5, 12, 13), (8, 15, 17), (9, 12, 15)]


def _gen_coordgeo(difficulty):
    if difficulty == "hard":
        kind = random.choice(["slope", "distance_decimal"])
        if kind == "slope":
            x1, y1 = random.randint(-10, 10), random.randint(-10, 10)
            dx = random.choice([i for i in range(-8, 9) if i != 0])
            dy = random.randint(-8, 8)
            x2, y2 = x1 + dx, y1 + dy
            answer = _fmt_fraction(dy, dx)
            wrongs = [_fmt_fraction(dx, dy) if dy != 0 else "0", _fmt_fraction(-dy, dx), _fmt_fraction(dy, -dx)]
            question_text = f"Find the slope between ({x1}, {y1}) and ({x2}, {y2}):"
        else:
            x1, y1 = random.randint(-10, 10), random.randint(-10, 10)
            dx, dy = random.randint(2, 12), random.randint(2, 12)
            while round(math.sqrt(dx ** 2 + dy ** 2), 1).is_integer():
                dy = random.randint(2, 12)
            x2, y2 = x1 + dx, y1 + dy
            dist = round(math.sqrt(dx ** 2 + dy ** 2), 1)
            answer = f"{dist:.1f}"
            wrongs = [str(dx + dy), f"{dist + 1:.1f}", str(dx * dy)]
            question_text = f"Find the distance between ({x1}, {y1}) and ({x2}, {y2}) (round to 1 decimal):"
        return {"question_text": question_text, "display": None, "answer": answer, "wrongs": wrongs}

    kind = random.choice(["midpoint", "distance_triple"])
    if kind == "midpoint":
        mx, my = random.randint(-10, 10), random.randint(-10, 10)
        ox, oy = random.randint(-6, 6), random.randint(-6, 6)
        x1, y1 = mx - ox, my - oy
        x2, y2 = mx + ox, my + oy
        answer = f"({mx}, {my})"
        wrongs = [f"({x1 + x2}, {y1 + y2})", f"({my}, {mx})", f"({mx + 1}, {my})"]
        question_text = f"Find the midpoint of ({x1}, {y1}) and ({x2}, {y2}):"
    else:
        a, b, c = random.choice(_PYTHAGOREAN_TRIPLES)
        if random.choice([True, False]):
            a, b = b, a
        x1, y1 = random.randint(-8, 8), random.randint(-8, 8)
        x2, y2 = x1 + a, y1 + b
        answer = str(c)
        wrongs = [str(a + b), str(round(math.sqrt(a * b), 1)), str(c + 1)]
        question_text = f"Find the distance between ({x1}, {y1}) and ({x2}, {y2}):"

    return {"question_text": question_text, "display": None, "answer": answer, "wrongs": wrongs}


def _check_coordgeo(guess, answer):
    if answer.startswith("("):
        nums = [int(float(x)) for x in re.findall(r"-?\d+\.?\d*", answer)]
        guess_nums = [int(float(x)) for x in re.findall(r"-?\d+\.?\d*", guess)]
        return len(guess_nums) >= 2 and guess_nums[:2] == nums[:2]
    g = _parse_fraction(guess)
    a = _parse_fraction(answer)
    return _close(g, a, tol=0.06)


# ---------------------------------------------------------------------------
# Exponents & Logarithms
# ---------------------------------------------------------------------------

def _gen_explog(difficulty):
    if difficulty == "hard":
        base = random.choice([2, 3, 5])
        exponent = random.randint(2, 6)
        n = base ** exponent
        phrasing = random.choice(["log", "solve"])
        if phrasing == "log":
            question_text = f"Evaluate: log base {base} of {n} = ?"
        else:
            question_text = f"Solve for x: {base}^x = {n}"
        wrongs = [str(exponent + 1), str(exponent - 1) if exponent > 1 else str(exponent + 2), str(base)]
        return {"question_text": question_text, "display": None, "answer": str(exponent), "wrongs": wrongs}

    kind = random.choice(["power", "combine"])
    if kind == "power":
        base = random.randint(2, 9)
        exponent = random.randint(2, 4)
        answer_val = base ** exponent
        question_text = f"Evaluate: {base}^{exponent}"
        wrongs = [str(base * exponent), str(answer_val // base if base else 0), str(answer_val + base)]
    else:
        base = random.randint(2, 5)
        m = random.randint(1, 4)
        n = random.randint(1, 4)
        answer_val = base ** (m + n)
        question_text = f"Simplify and evaluate: {base}^{m} × {base}^{n}"
        wrongs = [str(base ** (m * n)), str((base * 2) ** (m + n)), str(base ** m + base ** n)]

    return {"question_text": question_text, "display": None, "answer": str(answer_val), "wrongs": wrongs}


def _check_explog(guess, answer):
    n = _parse_number(guess)
    return n is not None and n == float(answer)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_GENERATORS = {
    "algebra": _gen_algebra,
    "geometry": _gen_geometry,
    "trig": _gen_trig,
    "calculus": _gen_calculus,
    "stats": _gen_stats,
    "numbertheory": _gen_numbertheory,
    "probability": _gen_probability,
    "sequences": _gen_sequences,
    "coordgeo": _gen_coordgeo,
    "explog": _gen_explog,
}

_CHECKERS = {
    "algebra": _check_algebra,
    "geometry": _check_geometry,
    "trig": _check_trig,
    "calculus": _check_calculus,
    "stats": _check_stats,
    "numbertheory": _check_numbertheory,
    "probability": _check_probability,
    "sequences": _check_sequences,
    "coordgeo": _check_coordgeo,
    "explog": _check_explog,
}

def generate_question(category_url, difficulty):
    """Returns a dict: question_text, image_buffer, plain_text, answer, mc_choices.
    image_buffer is the ONLY presentation of the question -- it always contains the
    full instruction text (word-wrapped) plus whatever math content applies (an
    expression/dataset, or a drawn diagram), so callers shouldn't also show
    question_text as a separate caption."""
    if category_url not in _GENERATORS:
        raise ValueError(f"Unknown category: {category_url}")
    spec = _GENERATORS[category_url](difficulty)

    shape_fn = spec.get("shape_fn")
    math_line = spec.get("display")
    header_color = random.choice(_NEON_COLORS)
    if math_line or shape_fn:
        # Two distinct neon colors -- one for the instruction, one for the actual
        # math content -- so the two visually separate instead of blending together.
        content_color = random.choice([c for c in _NEON_COLORS if c != header_color])
    else:
        content_color = header_color
    image_buffer = _render_composed_image(
        spec["question_text"], math_line=math_line, shape_fn=shape_fn,
        header_color=header_color, content_color=content_color,
    )
    plain_text = f"{spec['question_text']}\n{math_line}" if math_line else spec["question_text"]

    mc_choices = _make_mc_choices(spec["answer"], spec["wrongs"])
    return {
        "question_text": spec["question_text"],
        "image_buffer": image_buffer,
        "plain_text": plain_text,
        "answer": spec["answer"],
        "mc_choices": mc_choices,
    }


def check_answer(category_url, guess, correct_answer):
    if category_url not in _CHECKERS:
        return guess.strip().lower() == correct_answer.strip().lower()
    try:
        return _CHECKERS[category_url](guess, correct_answer)
    except Exception:
        return guess.strip().lower() == correct_answer.strip().lower()
