"""
Fixes entries in category_emojis.py that have <2 or >2 visual emoji clusters.
- >2: trims to first 2 clusters
- <2: re-queries Claude for those categories
Run once, re-run safe.
"""

import sys, time
sys.path.insert(0, '.')
from category_emojis import CATEGORY_EMOJIS
import anthropic

# ── Emoji cluster counter ────────────────────────────────────────────────────

ZWJ = '‍'
VARIATION_16 = '️'
CANCEL_TAG = '\U000e007f'

def is_regional_indicator(c):
    return 0x1F1E0 <= ord(c) <= 0x1F1FF

def is_tag_char(c):
    return 0xE0000 <= ord(c) <= 0xE007F

def is_skin_tone(c):
    return 0x1F3FB <= ord(c) <= 0x1F3FF

def is_emoji_base(c):
    cp = ord(c)
    return (
        0x1F300 <= cp <= 0x1FAFF or
        0x2600 <= cp <= 0x27BF or
        cp in (0x231A, 0x231B, 0x23E9, 0x23EA, 0x23EB, 0x23EC, 0x23ED, 0x23EE,
               0x23EF, 0x23F0, 0x23F1, 0x23F2, 0x23F3, 0x23F8, 0x23F9, 0x23FA,
               0x25AA, 0x25AB, 0x25B6, 0x25C0, 0x25FB, 0x25FC, 0x25FD, 0x25FE,
               0x2614, 0x2615, 0x2648, 0x2649, 0x264A, 0x264B, 0x264C, 0x264D,
               0x264E, 0x264F, 0x2650, 0x2651, 0x2652, 0x2653, 0x267F, 0x2693,
               0x26A1, 0x26AA, 0x26AB, 0x26BD, 0x26BE, 0x26C4, 0x26C5, 0x26CE,
               0x26D4, 0x26EA, 0x26F2, 0x26F3, 0x26F5, 0x26FA, 0x26FD, 0x2702,
               0x2705, 0x2708, 0x2709, 0x270A, 0x270B, 0x270C, 0x270D, 0x270F,
               0x2712, 0x2714, 0x2716, 0x271D, 0x2721, 0x2728, 0x2733, 0x2734,
               0x2744, 0x2747, 0x274C, 0x274E, 0x2753, 0x2754, 0x2755, 0x2757,
               0x2763, 0x2764, 0x27A1, 0x27B0, 0x27BF, 0x2934, 0x2935,
               0x2B05, 0x2B06, 0x2B07, 0x2B1B, 0x2B1C, 0x2B50, 0x2B55,
               0x3030, 0x303D, 0x3297, 0x3299, 0x1F004, 0x1F0CF,
               0x2139,   # ℹ
               0x231A, 0x231B,
               0x2122, 0x2139, 0x2194, 0x2195, 0x2196, 0x2197, 0x2198, 0x2199,
               0x21A9, 0x21AA, 0x231A, 0x231B, 0x2328, 0x23CF,
               ) or
        0x2194 <= cp <= 0x2199 or
        0x21A9 <= cp <= 0x21AA or
        0x0023 <= cp <= 0x0039  # digits/# for keycaps
    )

def split_clusters(s):
    """Split emoji string into visual grapheme clusters."""
    s = s.strip()
    clusters = []
    i = 0
    while i < len(s):
        c = s[i]
        cp = ord(c)

        # Skip plain spaces
        if c == ' ':
            i += 1
            continue

        # Subdivision flag: U+1F3F4 followed by tag chars ending in CANCEL_TAG
        if cp == 0x1F3F4 and i + 1 < len(s) and is_tag_char(s[i + 1]):
            j = i + 1
            while j < len(s) and is_tag_char(s[j]):
                j += 1
            clusters.append(s[i:j])
            i = j
            continue

        # Regional indicator pair (flag)
        if is_regional_indicator(c) and i + 1 < len(s) and is_regional_indicator(s[i + 1]):
            clusters.append(s[i:i + 2])
            i += 2
            continue

        # Keycap: digit/# + optional variation selector + combining enclosing keycap U+20E3
        if c in '0123456789#*':
            j = i + 1
            if j < len(s) and s[j] == VARIATION_16:
                j += 1
            if j < len(s) and ord(s[j]) == 0x20E3:
                clusters.append(s[i:j + 1])
                i = j + 1
                continue
            # Plain digit not forming keycap — skip it
            i += 1
            continue

        # Emoji base char
        if is_emoji_base(c) or (0x2000 <= cp <= 0x2BFF and cp not in (0x200D,)):
            j = i + 1
            # Consume variation selector, skin tones, ZWJ sequences
            while j < len(s):
                nc = s[j]
                ncp = ord(nc)
                if nc == VARIATION_16 or is_skin_tone(nc):
                    j += 1
                elif ncp == 0x20E3:  # combining enclosing keycap
                    j += 1
                elif nc == ZWJ:
                    j += 1
                    if j < len(s):
                        j += 1  # consume the char after ZWJ
                else:
                    break
            clusters.append(s[i:j])
            i = j
            continue

        # Everything else (ASCII letters, symbols, CJK, replacement chars) — skip
        i += 1

    return clusters


# ── Identify bad entries ─────────────────────────────────────────────────────

too_few, too_many = {}, {}
for cat, val in CATEGORY_EMOJIS.items():
    clusters = split_clusters(val)
    n = len(clusters)
    if n < 2:
        too_few[cat] = (val, clusters)
    elif n > 2:
        too_many[cat] = (val, clusters)

print(f"Too few (<2): {len(too_few)}")
print(f"Too many (>2): {len(too_many)}")

# ── Fix >2: keep first 2 clusters ───────────────────────────────────────────

fixes = {}
for cat, (val, clusters) in too_many.items():
    fixes[cat] = ''.join(clusters[:2])

# ── Fix <2: re-query Claude ──────────────────────────────────────────────────

if too_few:
    print(f"\nRe-querying Claude for {len(too_few)} under-emoji entries...")
    client = anthropic.Anthropic()
    cats = list(too_few.keys())

    def build_prompt(batch):
        lines = "\n".join(f"{i+1}. {cat}" for i, cat in enumerate(batch))
        return (
            "You are an emoji curator for a trivia game. For each numbered category below, "
            "respond with exactly one line per category in the format:\n"
            "N. 🎯🔥\n\n"
            "Rules:\n"
            "- Exactly 2 emojis per line, nothing else\n"
            "- Keep the same number as the input\n"
            "- No extra text, explanations, or blank lines\n"
            "- You MUST respond for every single category — never skip a line.\n\n"
            f"Categories:\n{lines}"
        )

    def parse_response(text, batch):
        result = {}
        for line in text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            dot = line.find(". ")
            if dot == -1:
                continue
            try:
                idx = int(line[:dot]) - 1
            except ValueError:
                continue
            if 0 <= idx < len(batch):
                emojis = line[dot + 2:].strip()
                if emojis:
                    result[batch[idx]] = emojis
        return result

    BATCH = 100
    for i in range(0, len(cats), BATCH):
        batch = cats[i:i + BATCH]
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": build_prompt(batch)}],
        )
        parsed = parse_response(resp.content[0].text, batch)
        fixes.update(parsed)
        print(f"  Re-queried {min(i+BATCH, len(cats))}/{len(cats)} — got {len(parsed)}/{len(batch)}")
        time.sleep(0.3)

# ── Write fixes to category_emojis.py ───────────────────────────────────────

if not fixes:
    print("Nothing to fix.")
    sys.exit(0)

from pathlib import Path
EMOJIS_FILE = Path(__file__).parent / "category_emojis.py"
content = EMOJIS_FILE.read_text(encoding="utf-8")

for cat, new_val in fixes.items():
    escaped_cat = cat.replace("\\", "\\\\").replace('"', '\\"')
    escaped_new = new_val.replace("\\", "\\\\").replace('"', '\\"')
    # Replace the value for this exact key
    old_val = CATEGORY_EMOJIS[cat].replace("\\", "\\\\").replace('"', '\\"')
    old_line = f'    "{escaped_cat}": "{old_val}",'
    new_line = f'    "{escaped_cat}": "{escaped_new}",'
    if old_line in content:
        content = content.replace(old_line, new_line, 1)
    else:
        print(f"  WARN: couldn't find line for {cat!r}, skipping")

EMOJIS_FILE.write_text(content, encoding="utf-8")
print(f"\nWrote {len(fixes)} fixes to category_emojis.py")

# ── Verify syntax ────────────────────────────────────────────────────────────
import py_compile
try:
    py_compile.compile(str(EMOJIS_FILE), doraise=True)
    print("Syntax check: OK")
except py_compile.PyCompileError as e:
    print(f"Syntax check FAILED: {e}")
