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
calls it directly.

No dedicated state endpoint of its own: the client JS below hits companion_web.py's existing
/api/current and /api/stream directly (same session cookie, same "main"/"simply"/"arena" `game`
values), exactly the same connect()/loadGame() pattern _INDEX_HTML's own JS uses. This isn't just
simpler, it's the only way to actually see the "revealed" phase -- that phase is a one-shot
broadcast (build_companion_reveal_state(), published via companion_web.publish_state() at the
exact moment of reveal), never a queryable persistent field, so a poll loop calling a stateless
"give me current state" builder can structurally never observe it. Riding the same SSE stream the
phone uses is what makes the reveal (and everything else that's push-only) visible here too.

Modeled on activity_web.py's shape (module-level HTML blob + init()-injected callables), but
simpler: no Discord Activity SDK, no image-proxy, no sign/unsign/OAuth-secret plumbing of its
own. Login is a plain redirect to companion_web.py's existing /login flow (same domain, same
session cookie) -- this module only ever *checks* for a session via the injected
`session_from_request`, it doesn't manage sessions itself.
"""

import os
import urllib.parse

from aiohttp import web

ENABLED = os.getenv("TV_VIEW_ENABLED", "false").lower() == "true"

_session_from_request = None  # callable(request) -> dict|None, injected from companion_web.py


def init(*, session_from_request):
    global _session_from_request
    _session_from_request = session_from_request


def _login_redirect(request):
    next_path = urllib.parse.quote(request.path_qs, safe="")
    return web.HTTPFound(f"/login?next={next_path}")


def render_tv_page(request):
    if not _session_from_request(request):
        return _login_redirect(request)
    return web.Response(text=_TV_HTML, content_type="text/html")


_TV_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TriviaSphere TV</title>
<style>
  :root {
    color-scheme: dark;
    --blue:#146DE8; --blue-600:#0A4FB5;
    --bg:#06080D; --bg2:#0E1219; --fg:#F8F8F8; --muted:rgba(248,248,248,.58);
    --card:rgba(248,248,248,.05); --line:rgba(248,248,248,.10);
    --header-logo:url(/assets/logo-header.webp);
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; width: 100vw; min-height: 100vh; overflow-x: hidden; }
  body {
    color: var(--fg); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: radial-gradient(1100px 560px at 50% -12%, rgba(20,109,232,.14), transparent 60%),
                linear-gradient(180deg, var(--bg), var(--bg2)); background-attachment: fixed;
    display: grid; grid-template-rows: auto auto 1fr; grid-template-columns: 1fr 340px;
    grid-template-areas: "brand brand" "lineup lineup" "main side";
  }
  .brand {
    grid-area: brand; display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
    padding: 14px 28px 0;
  }
  .brandlogo { height: 56px; width: 56px; flex: none;
    background: var(--header-logo) left center/contain no-repeat; }
  .game-tabs { display: flex; gap: 4px; flex-wrap: wrap; background: rgba(127,127,127,.10);
    border: 1px solid var(--line); border-radius: 12px; padding: 3px; }
  .tab-btn { flex: none; border: none; background: transparent; color: var(--muted); cursor: pointer;
    font-size: 15px; font-weight: 700; letter-spacing: .01em; padding: 9px 16px; border-radius: 9px;
    white-space: nowrap; transition: background-color .15s, color .15s; }
  .tab-btn.active { background: var(--blue); color: #fff; }
  .companion-tab { margin-left: 6px; padding-left: 18px; border-left: 1px solid var(--line); }
  .lineup {
    grid-area: lineup; display: flex; gap: 10px; align-items: center;
    padding: 14px 28px; overflow-x: auto; white-space: nowrap;
  }
  .lineup .chip {
    padding: 6px 14px; border-radius: 999px; font-size: 15px; background: var(--card);
    border: 1px solid var(--line); color: var(--muted);
  }
  .lineup .chip.cur { background: var(--blue); border-color: var(--blue); color: #fff; font-weight: 600; }
  .lineup .chip.done { opacity: 0.5; text-decoration: line-through; }
  .main {
    grid-area: main; display: flex; flex-direction: column; align-items: center;
    justify-content: center; padding: 40px 60px; text-align: center; gap: 24px; min-width: 0;
  }
  .qheader { display: flex; align-items: center; gap: 16px; }
  .category { font-size: 26px; color: var(--muted); text-transform: uppercase; letter-spacing: 2px; }
  .timer { font-size: 26px; font-weight: 800; font-variant-numeric: tabular-nums; color: var(--muted); }
  .timer.low { color: #ff4d6d; }
  .question { font-size: 48px; font-weight: 700; line-height: 1.25; max-width: 100%; }
  .qimage { max-height: 34vh; max-width: 100%; border-radius: 12px; margin-top: 8px; }
  .choices { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; width: 100%; max-width: 900px; }
  .choice {
    background: var(--card); border: 1px solid var(--line); border-radius: 10px;
    padding: 16px 22px; font-size: 24px; text-align: left;
  }
  .answer-banner { font-size: 32px; font-weight: 700; color: #38c26b; }
  .modes { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }
  .mode-pill { background: var(--card); border: 1px solid var(--line); border-radius: 999px; padding: 6px 14px; font-size: 16px; }
  .idle { font-size: 32px; color: var(--muted); }
  .side {
    grid-area: side; border-left: 1px solid var(--line);
    padding: 24px 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 18px;
  }
  .streak-badge {
    background: linear-gradient(135deg, #ff8a3d, #ff4d6d); border-radius: 12px;
    padding: 14px 16px; font-size: 18px; font-weight: 600; color: #fff;
  }
  .score-title { font-size: 15px; color: var(--muted); text-transform: uppercase; letter-spacing: 1.5px; }
  .score-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--line); font-size: 18px; }
  .score-rank { width: 28px; text-align: center; }
  .score-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .score-lightning { font-size: 14px; color: #ffcc4d; font-variant-numeric: tabular-nums; }
  .score-val { color: var(--fg); font-weight: 700; font-variant-numeric: tabular-nums; }
  .score-delta { font-size: 14px; font-weight: 700; color: #38c26b; font-variant-numeric: tabular-nums; }
  .arena-turn { font-size: 22px; color: var(--muted); }
</style>
</head>
<body>
  <div class="brand">
    <div class="brandlogo" role="img" aria-label="TriviaSphere logo"></div>
    <div class="game-tabs" id="tabs">
      <button type="button" class="tab-btn active" data-game="main">Trivia &amp; Games</button>
      <button type="button" class="tab-btn" data-game="simply">Simply Trivia</button>
      <button type="button" class="tab-btn" data-game="arena">Mini-Game Arena</button>
      <button type="button" class="tab-btn companion-tab" data-action="back">📱 Companion View</button>
    </div>
  </div>
  <div class="lineup" id="lineup"></div>
  <div class="main" id="main"><div class="idle">Waiting for the next question…</div></div>
  <div class="side" id="side"></div>

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
    document.querySelectorAll("#tabs button[data-game]").forEach(function (b) { b.classList.toggle("active", b === btn); });
    history.replaceState(null, "", "/?view=tv&game=" + btn.getAttribute("data-game"));
    loadGame(btn.getAttribute("data-game"));
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

  var timerInterval = null;

  function stopTimer() {
    if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
  }

  function tickTimer(endsAt) {
    var el = document.getElementById("timer");
    if (!el) { stopTimer(); return; }
    var rem = Math.max(0, Math.ceil(endsAt - Date.now() / 1000));
    el.textContent = rem + "s";
    el.classList.toggle("low", rem <= 5);
    if (rem <= 0) stopTimer();
  }

  function renderMainOrSimply(state) {
    var main = document.getElementById("main");
    stopTimer();
    if (state.phase === "idle" || !state.phase) {
      main.innerHTML = '<div class="idle">Waiting for the next question…</div>';
      return;
    }
    var html = '<div class="qheader"><div class="category">' + esc(state.category || "") + '</div>';
    if (state.phase === "open" && state.ends_at) {
      html += '<span id="timer" class="timer"></span>';
    }
    html += '</div>';
    html += '<div class="question">' + esc(state.question || "") + '</div>';
    if (state.image_url) {
      html += '<img class="qimage" src="' + esc(state.image_url) + '" alt="">';
    }
    if (state.phase === "revealed") {
      html += '<div class="answer-banner">✅ ' + esc(state.correct_answer || "") + '</div>';
    } else if ((state.choices || []).length) {
      html += '<div class="choices">' + state.choices.map(function (c) {
        return '<div class="choice">' + esc(c.text || c) + '</div>';
      }).join("") + '</div>';
    }
    main.innerHTML = html;
    if (state.phase === "open" && state.ends_at) {
      tickTimer(state.ends_at);
      timerInterval = setInterval(function () { tickTimer(state.ends_at); }, 250);
    }
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
          (r.lightning ? '<div class="score-lightning">⚡' + esc(r.lightning) + '</div>' : '') +
          '<div class="score-val">' + esc(r.score) + '</div>' +
          (r.delta ? '<div class="score-delta">' + esc(r.delta) + '</div>' : '') +
          '</div>';
      });
    }
    side.innerHTML = html;
  }

  function render(state) {
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

  // Same connect()/loadGame() shape as _INDEX_HTML's own JS: an initial fetch for instant paint,
  // then a live EventSource for everything after, including the one-shot "revealed" broadcast a
  // poll loop could never see (only pushed once at the moment of reveal, not a queryable field).
  var es = null;

  function connect() {
    es = new EventSource("/api/stream?game=" + encodeURIComponent(currentGame));
    es.onmessage = function (ev) { try { render(JSON.parse(ev.data)); } catch (e) {} };
    es.onerror = function () { /* EventSource auto-reconnects */ };
  }

  function loadGame(game) {
    currentGame = game;
    if (es) { es.close(); es = null; }
    fetch("/api/current?game=" + encodeURIComponent(game)).then(function (r) { return r.json(); })
      .then(function (s) { render(s); connect(); })
      .catch(function () { connect(); });
  }

  document.querySelectorAll("#tabs button[data-game]").forEach(function (b) {
    b.classList.toggle("active", b.getAttribute("data-game") === currentGame);
  });
  loadGame(currentGame);
})();
</script>
</body>
</html>
"""
