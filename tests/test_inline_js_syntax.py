"""Syntax-check the inline <script> blocks embedded in this repo's HTML templates.

    ./.venv/bin/python tests/test_inline_js_syntax.py     # or: pytest tests/test_inline_js_syntax.py

These templates are Python triple-quoted strings holding a whole page of JavaScript, so a
quote-escaping slip is invisible to Python and to every import-time check -- it fails only in
the browser, where a syntax error anywhere in a <script> block stops the WHOLE block from
executing. That is not a partial degradation: no function in it is ever defined, so the page
freezes on whatever the server rendered, silently.

That is exactly how a rebrand ("Join TriviaSphere" -> "Join Okra's World", commit ce4710d) left
an unescaped apostrophe in a single-quoted JS string in _ACTIVITY_HTML and bricked the /play
Activity panel on an endless "Loading..." for months.

The templates are read with `ast`, never imported -- these modules pull in aiohttp and friends
and expect a configured environment. `ast.literal_eval` matters for a second reason: it resolves
Python's escapes, so what gets checked is the JS the browser actually receives (source `\\'`
-> delivered `\'`). Checking the raw source text would have missed the bug.
"""

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Modules holding page templates with inline JS.
MODULES = ["companion_web.py", "activity_web.py", "tv_view.py"]

# Inline blocks only -- a tag with src= has no body of ours to check.
_SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S)


def iter_blocks():
    """Yield (label, js) for every inline <script> body in every *_HTML string constant."""
    for module in MODULES:
        path = os.path.join(REPO, module)
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not (isinstance(target, ast.Name) and target.id.endswith("HTML")):
                    continue
                try:
                    value = ast.literal_eval(node.value)
                except Exception:
                    continue  # built by concatenation/format, not a plain literal
                if not isinstance(value, str):
                    continue
                for i, match in enumerate(_SCRIPT_RE.finditer(value)):
                    yield f"{module}:{target.id}[{i}]", match.group(1)


def check(js):
    """Return None if the JS parses, else node's error text."""
    fd, tmp = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(js)
        proc = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
        if proc.returncode == 0:
            return None
        # node prints the offending line and a caret; keep that, drop its stack trace. It reports
        # the resolved path (/var -> /private/var on macOS), so scrub both spellings.
        text = proc.stderr.split("\n    at ")[0]
        for path in (os.path.realpath(tmp), tmp):
            text = text.replace(path, "<inline script>")
        return text.strip()
    finally:
        os.unlink(tmp)


# --- pytest tier -----------------------------------------------------------

try:
    import pytest
except ImportError:  # standalone run without pytest installed
    pytest = None

if pytest is not None:
    BLOCKS = list(iter_blocks())

    @pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
    @pytest.mark.parametrize("label,js", BLOCKS, ids=[b[0] for b in BLOCKS])
    def test_inline_js_parses(label, js):
        error = check(js)
        assert error is None, f"{label} is not valid JavaScript:\n{error}"

    def test_templates_were_found():
        """Guard the discovery itself: a renamed constant must not silently check nothing."""
        assert len(BLOCKS) >= 5, f"expected to find the known templates, found {len(BLOCKS)}"


# --- standalone tier -------------------------------------------------------

def main():
    if shutil.which("node") is None:
        print("node not on PATH -- skipping")
        return 0
    failures = 0
    blocks = list(iter_blocks())
    for label, js in blocks:
        error = check(js)
        if error is None:
            print(f"  OK      {label}")
        else:
            failures += 1
            print(f"  BROKEN  {label}\n{error}\n")
    print(f"\n{len(blocks)} blocks checked, {failures} failing")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
