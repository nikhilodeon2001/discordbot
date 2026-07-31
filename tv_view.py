"""
TV View: a read-only, landscape-oriented display meant to be cast to a TV while players answer
on their own phones via the companion app (companion_web.py). Shows the live question, category,
choices, active modes, round lineup, scoreboard, and streak for the main round and Simply Trivia,
or phase/whose-turn for the mini-game arena (which has no scoreboard concept at all). No flag
button, no answer-submission UI -- this is strictly spectator.

Served from the same "/" route as the phone companion, switched on by a "?view=tv" query param --
exactly the same trick companion_web.py's handle_index already uses to serve activity_web's
Activity page from "?frame_id=..." instead of a dedicated path, so there's only ever one URL
(play.triviasphere.com) to share, not a second one to remember. render_tv_page() is a plain
function (mirroring activity_web.render_activity_page), not a route handler itself -- handle_index
calls it directly. Only /api/tv_poll is a real dedicated route, since that's a fetch target, not
something anyone navigates to.

Modeled on activity_web.py's shape (module-level HTML blob + init()-injected callables), but
simpler: no Discord Activity SDK, no image-proxy, no sign/unsign/OAuth-secret plumbing of its
own. Login is a plain redirect to companion_web.py's existing /login flow (same domain, same
session cookie) -- this module only ever *checks* for a session via the injected
`session_from_request`, it doesn't manage sessions itself.

Poll-only (no SSE) for v1: a TV display tolerates a couple seconds of staleness fine, and this
avoids extending companion_web.py's per-game SSE subscriber/sequence bookkeeping (_GAMES/_seq/
_subscribers), which is scoped to ("main", "simply", "arena") and would need a parallel publish
call wired into the round loop for each of the three states used here.
"""

import os
import urllib.parse

from aiohttp import web

ENABLED = os.getenv("TV_VIEW_ENABLED", "false").lower() == "true"

_get_tv_state = None      # callable(game:str) -> dict (sanitized live state)
_session_from_request = None  # callable(request) -> dict|None, injected from companion_web.py


def init(*, get_tv_state, session_from_request):
    global _get_tv_state, _session_from_request
    _get_tv_state = get_tv_state
    _session_from_request = session_from_request


def _login_redirect(request):
    next_path = urllib.parse.quote(request.path_qs, safe="")
    return web.HTTPFound(f"/login?next={next_path}")


def render_tv_page(request):
    if not _session_from_request(request):
        return _login_redirect(request)
    return web.Response(text=_TV_HTML, content_type="text/html")


async def handle_tv_poll(request):
    if not _session_from_request(request):
        return web.json_response({"authenticated": False}, status=401)
    game = request.query.get("game", "main")
    if game not in ("main", "simply", "arena"):
        game = "main"
    state = _get_tv_state(game) if _get_tv_state else {"phase": "idle"}
    return web.json_response(state)


def tv_routes():
    return [web.get("/api/tv_poll", handle_tv_poll)]


_TV_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TriviaSphere TV</title>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden; }
  body {
    background: #0b0e14; color: #eef1f8;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    display: grid; grid-template-rows: auto 1fr; grid-template-columns: 1fr 320px;
    grid-template-areas: "lineup lineup" "main side";
  }
  .lineup {
    grid-area: lineup; display: flex; gap: 10px; align-items: center;
    padding: 14px 28px; background: #10141d; border-bottom: 1px solid #1e2430;
    overflow-x: auto; white-space: nowrap;
  }
  .lineup .chip {
    padding: 6px 14px; border-radius: 999px; font-size: 15px; background: #1a2030; color: #8994a8;
  }
  .lineup .chip.cur { background: #3d5afe; color: #fff; font-weight: 600; }
  .lineup .chip.done { opacity: 0.5; text-decoration: line-through; }
  .tabs { margin-left: auto; display: flex; gap: 6px; }
  .tabs button {
    background: #1a2030; color: #8994a8; border: none; border-radius: 8px;
    padding: 8px 16px; font-size: 15px; cursor: pointer;
  }
  .tabs button.active { background: #3d5afe; color: #fff; }
  .main {
    grid-area: main; display: flex; flex-direction: column; align-items: center;
    justify-content: center; padding: 40px 60px; text-align: center; gap: 24px; min-width: 0;
  }
  .category { font-size: 26px; color: #7c8aa5; text-transform: uppercase; letter-spacing: 2px; }
  .question { font-size: 48px; font-weight: 700; line-height: 1.25; max-width: 100%; }
  .qimage { max-height: 34vh; max-width: 100%; border-radius: 12px; margin-top: 8px; }
  .choices { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; width: 100%; max-width: 900px; }
  .choice {
    background: #171d2b; border-radius: 10px; padding: 16px 22px; font-size: 24px; text-align: left;
  }
  .choice.correct { background: #17351f; border: 2px solid #38c26b; }
  .answer-banner { font-size: 32px; font-weight: 700; color: #38c26b; }
  .modes { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }
  .mode-pill { background: #1a2030; border-radius: 999px; padding: 6px 14px; font-size: 16px; }
  .idle { font-size: 32px; color: #7c8aa5; }
  .side {
    grid-area: side; background: #10141d; border-left: 1px solid #1e2430;
    padding: 24px 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 18px;
  }
  .streak-badge {
    background: linear-gradient(135deg, #ff8a3d, #ff4d6d); border-radius: 12px;
    padding: 14px 16px; font-size: 18px; font-weight: 600;
  }
  .score-title { font-size: 15px; color: #7c8aa5; text-transform: uppercase; letter-spacing: 1.5px; }
  .score-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #1e2430; font-size: 18px; }
  .score-rank { width: 28px; text-align: center; }
  .score-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .score-val { color: #a7b2c8; font-variant-numeric: tabular-nums; }
  .arena-turn { font-size: 22px; color: #a7b2c8; }
</style>
</head>
<body>
  <div class="lineup" id="lineup">
    <div class="tabs" id="tabs">
      <button data-game="main" class="active">Trivia &amp; Games</button>
      <button data-game="simply">Simply Trivia</button>
      <button data-game="arena">Mini-Game Arena</button>
    </div>
  </div>
  <div class="main" id="main"><div class="idle">Waiting for the next question…</div></div>
  <div class="side" id="side"></div>

<script>
(function () {
  var GAMES = ["main", "simply", "arena"];
  var initialGame = new URLSearchParams(location.search).get("game");
  var currentGame = GAMES.indexOf(initialGame) !== -1 ? initialGame : "main";
  var esc = function (s) { var d = document.createElement("div"); d.textContent = String(s == null ? "" : s); return d.innerHTML; };

  // renderLineup() reassigns #lineup's innerHTML on every poll, which destroys and recreates the
  // tab buttons -- a listener attached to #tabs directly would only survive until the first poll.
  // Delegating on document (same fix as the Activity panel's button issue) survives every rebuild.
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("button[data-game]");
    if (!btn) return;
    currentGame = btn.getAttribute("data-game");
    document.querySelectorAll("#tabs button").forEach(function (b) { b.classList.toggle("active", b === btn); });
    history.replaceState(null, "", "/?view=tv&game=" + currentGame);
    poll();
  });

  function renderLineup(state) {
    var el = document.getElementById("lineup");
    var chips = "";
    var overview = state.round_overview || [];
    var cur = state.question_number || 0;
    overview.forEach(function (title, i) {
      var n = i + 1;
      var cls = n === cur ? "cur" : (n < cur ? "done" : "");
      chips += '<div class="chip ' + cls + '">' + esc(title) + '</div>';
    });
    var modes = (state.modes || []).map(function (m) {
      return '<div class="mode-pill">' + esc(m.emoji) + ' ' + esc(m.label) + '</div>';
    }).join("");
    el.innerHTML = chips + (modes ? '<div class="modes">' + modes + '</div>' : "") + el.querySelector(".tabs").outerHTML;
  }

  function renderMainOrSimply(state) {
    var main = document.getElementById("main");
    if (state.phase === "idle" || !state.phase) {
      main.innerHTML = '<div class="idle">Waiting for the next question…</div>';
      return;
    }
    var html = '<div class="category">' + esc(state.category || "") + '</div>';
    html += '<div class="question">' + esc(state.question || "") + '</div>';
    if (state.image_url) {
      html += '<img class="qimage" src="' + esc(state.image_url) + '" alt="">';
    }
    if (state.phase === "revealed") {
      html += '<div class="answer-banner">✅ ' + esc(state.correct_answer || "") + '</div>';
    } else if ((state.choices || []).length) {
      html += '<div class="choices">' + state.choices.map(function (c) {
        return '<div class="choice">' + esc(c.letter ? c.letter + ". " : "") + esc(c.text || c) + '</div>';
      }).join("") + '</div>';
    }
    main.innerHTML = html;
  }

  function renderArena(state) {
    var main = document.getElementById("main");
    if (state.phase === "idle" || !state.phase) {
      main.innerHTML = '<div class="idle">No mini-game running</div>';
      return;
    }
    var whoLine = "";
    var names = (state.prompt && state.prompt.allowed_names) || [];
    if (names.length) whoLine = '<div class="arena-turn">' + (state.phase === "spectating" ? "Watching " : "Waiting on ") + esc(names.join(", ")) + '</div>';
    main.innerHTML = '<div class="category">Mini-Game Arena</div><div class="question">' + esc(state.game_name || "") + '</div>' + whoLine;
  }

  function renderSide(state) {
    var side = document.getElementById("side");
    var html = "";
    if (state.streak && state.streak.streak > 1) {
      html += '<div class="streak-badge">🔥 ' + esc(state.streak.name) + ' — ' + esc(state.streak.streak) + ' in a row</div>';
    }
    var rows = state.scoreboard || [];
    if (rows.length) {
      html += '<div class="score-title">Standings</div>';
      rows.forEach(function (r) {
        html += '<div class="score-row"><div class="score-rank">' + esc(r.rank) + '</div>' +
          '<div class="score-name">' + esc(r.name) + (r.via_companion ? " 🌐" : "") + '</div>' +
          '<div class="score-val">' + esc(r.score) + '</div></div>';
      });
    }
    side.innerHTML = html;
  }

  async function poll() {
    var resp;
    try {
      resp = await fetch("/api/tv_poll?game=" + encodeURIComponent(currentGame));
    } catch (e) {
      return;
    }
    if (resp.status === 401) {
      location.href = "/login?next=" + encodeURIComponent(location.pathname + location.search);
      return;
    }
    if (!resp.ok) return;
    var state = await resp.json();
    if (currentGame === "arena") {
      document.getElementById("lineup").querySelectorAll(".chip, .modes").forEach(function (n) { n.remove(); });
      renderArena(state);
      document.getElementById("side").innerHTML = "";
    } else {
      renderLineup(state);
      renderMainOrSimply(state);
      renderSide(state);
    }
  }

  document.querySelectorAll("#tabs button").forEach(function (b) {
    b.classList.toggle("active", b.getAttribute("data-game") === currentGame);
  });
  poll();
  setInterval(poll, 2500);
})();
</script>
</body>
</html>
"""
