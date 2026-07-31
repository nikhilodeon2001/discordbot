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
<link rel="icon" type="image/webp" href="/assets/logo-mark.webp">
<style>
  /* Header chrome below (:root, body, .wrap, .brand*, .game-tabs, .tab-btn) is a deliberate,
  byte-for-byte copy of companion_web.py's _INDEX_HTML header CSS -- not a shared stylesheet,
  per activity_web.py's precedent for why (a second page can't be allowed to risk the untested,
  prod-serving companion page) -- but copied exactly rather than re-derived, so switching between
  "/" and "/?view=tv" looks like the same page with only the content region below changing. */
  :root {
    color-scheme: dark;
    --blue:#146DE8; --blue-600:#0A4FB5; --red:#F71A14;
    --bg:#06080D; --bg2:#0E1219; --fg:#F8F8F8; --muted:rgba(248,248,248,.58);
    --card:rgba(248,248,248,.05); --line:rgba(248,248,248,.10);
    --header-logo:url(/assets/logo-header.webp);
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body { margin:0; min-height:100vh; color:var(--fg);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,sans-serif;
    background:radial-gradient(1100px 560px at 50% -12%, rgba(20,109,232,.14), transparent 60%),
               linear-gradient(180deg,var(--bg),var(--bg2)); background-attachment:fixed;
    display:flex; flex-direction:column; align-items:center;
    padding:26px 16px calc(26px + env(safe-area-inset-bottom)); }
  .wrap { width:100%; max-width:520px; }
  .brand { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
  .brandhead { display:flex; align-items:center; min-width:0; }
  .brandlogo { height:96px; width:96px; flex:none;
    background:var(--header-logo) left center/contain no-repeat; }
  .game-tabs { display:flex; gap:4px; flex:none; background:rgba(127,127,127,.10);
    border:1px solid var(--line); border-radius:12px; padding:3px; }
  .tab-btn { flex:none; border:none; background:transparent; color:var(--muted); cursor:pointer;
    font-size:.7rem; font-weight:700; letter-spacing:.01em; padding:7px 10px; border-radius:9px;
    white-space:nowrap; transition:background-color .15s, color .15s; }
  .tab-btn.active { background:var(--blue); color:#fff; }
  .companion-tab { margin-left:2px; padding-left:12px; border-left:1px solid var(--line); }
  .sub { color:var(--muted); font-size:.86rem; margin:13px 2px 20px; line-height:1.45; }

  /* Everything below here is TV-specific: a full-width region (not capped at .wrap's 520px,
  since this is the one part meant to look different -- optimized for a landscape screen rather
  than a phone) sitting directly beneath the shared header/wrap above. */
  .tvcontent { width:100%; max-width:1400px; }
  .lineup { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin:18px 0; }
  .lineup .chip {
    padding:6px 14px; border-radius:999px; font-size:.8rem; background:var(--card);
    border:1px solid var(--line); color:var(--muted);
  }
  .lineup .chip.cur { background:var(--blue); border-color:var(--blue); color:#fff; font-weight:600; }
  .lineup .chip.done { opacity:0.5; text-decoration:line-through; }
  .tvbody { display:grid; grid-template-columns: 1fr 320px; gap:20px; align-items:start; }
  .main {
    background:var(--card); border:1px solid var(--line); border-radius:20px; padding:40px;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    text-align:center; gap:24px; min-height:50vh;
  }
  .category { font-size:1.4rem; color:var(--muted); text-transform:uppercase; letter-spacing:2px; }
  .question { font-size:2.6rem; font-weight:700; line-height:1.25; max-width:100%; }
  .qimage { max-height:34vh; max-width:100%; border-radius:12px; margin-top:8px; }
  .choices { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:14px; width:100%; max-width:900px; }
  .choice {
    background:rgba(127,127,127,.08); border:1px solid var(--line); border-radius:10px;
    padding:16px 22px; font-size:1.3rem; text-align:left;
  }
  .answer-banner { font-size:1.8rem; font-weight:700; color:#38c26b; }
  .modes { display:flex; gap:10px; flex-wrap:wrap; justify-content:center; }
  .mode-pill { background:rgba(127,127,127,.08); border:1px solid var(--line); border-radius:999px; padding:6px 14px; font-size:.9rem; }
  .idle { font-size:1.7rem; color:var(--muted); }
  .side {
    background:var(--card); border:1px solid var(--line); border-radius:20px;
    padding:22px 20px; display:flex; flex-direction:column; gap:18px;
  }
  .streak-badge {
    background:linear-gradient(135deg, #ff8a3d, #ff4d6d); border-radius:12px;
    padding:14px 16px; font-size:1rem; font-weight:600; color:#fff;
  }
  .score-title { font-size:.8rem; color:var(--muted); text-transform:uppercase; letter-spacing:1.5px; }
  .score-row { display:flex; align-items:center; gap:10px; padding:8px 0; border-bottom:1px solid var(--line); font-size:1rem; }
  .score-rank { width:28px; text-align:center; }
  .score-name { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .score-val { color:var(--muted); font-variant-numeric:tabular-nums; }
  .arena-turn { font-size:1.2rem; color:var(--muted); }
</style>
</head>
<body>
<div class="wrap">
  <header class="brand">
    <div class="brandhead">
      <div class="brandlogo" role="img" aria-label="TriviaSphere logo"></div>
    </div>
    <div class="game-tabs" id="tabs">
      <button type="button" class="tab-btn active" data-game="main">Trivia &amp; Games</button>
      <button type="button" class="tab-btn" data-game="simply">Simply Trivia</button>
      <button type="button" class="tab-btn" data-game="arena">Mini-Game Arena</button>
      <button type="button" class="tab-btn companion-tab" data-action="back">📱 Companion View</button>
    </div>
  </header>
  <div class="sub">Read-only display for a TV or shared screen — everyone else answers from their own phone.</div>
</div>
<div class="tvcontent">
  <div class="lineup" id="lineup"></div>
  <div class="tvbody">
    <div class="main" id="main"><div class="idle">Waiting for the next question…</div></div>
    <div class="side" id="side"></div>
  </div>
</div>

<script>
(function () {
  var GAMES = ["main", "simply", "arena"];
  var initialGame = new URLSearchParams(location.search).get("game");
  var currentGame = GAMES.indexOf(initialGame) !== -1 ? initialGame : "main";
  var esc = function (s) { var d = document.createElement("div"); d.textContent = String(s == null ? "" : s); return d.innerHTML; };

  // #tabs lives in the header (.brand), never rebuilt by any render function below, but delegating
  // on document rather than binding directly to #tabs matches the same fix already applied to the
  // Activity panel's buttons -- cheap insurance against a future render touching that markup too.
  document.addEventListener("click", function (e) {
    var backBtn = e.target.closest('[data-action="back"]');
    if (backBtn) {
      location.href = "/?game=" + currentGame;
      return;
    }
    var btn = e.target.closest("button[data-game]");
    if (!btn) return;
    currentGame = btn.getAttribute("data-game");
    document.querySelectorAll("#tabs button[data-game]").forEach(function (b) { b.classList.toggle("active", b === btn); });
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
    el.innerHTML = chips + (modes ? '<div class="modes">' + modes + '</div>' : "");
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
      document.getElementById("lineup").innerHTML = "";
      renderArena(state);
      document.getElementById("side").innerHTML = "";
    } else {
      renderLineup(state);
      renderMainOrSimply(state);
      renderSide(state);
    }
  }

  document.querySelectorAll("#tabs button[data-game]").forEach(function (b) {
    b.classList.toggle("active", b.getAttribute("data-game") === currentGame);
  });
  poll();
  setInterval(poll, 2500);
})();
</script>
</body>
</html>
"""
