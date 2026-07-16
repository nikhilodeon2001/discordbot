"""Companion web app for live Discord trivia.

A small aiohttp server that runs *in the bot process* so it can read live question
state and inject answers directly into the same `collected_responses` list the Discord
surfaces use. Players open this on their phones to answer privately (no copying from a
public channel), authenticated via Discord OAuth2 so answers are reliably attributed.

Design notes:
- Timing is server-authoritative: a web answer is stamped with `time.time()` on HTTP
  receipt, the same wall clock the bot already uses for `question_asked_start`. Grading
  subtracts `question_ask_time`, so web answers are timed identically to Discord ones.
- This module imports NOTHING from discordbot (avoids a circular import). The bot passes
  in callbacks (`resolve_member`, `get_state`, `submit_answer`) and calls `publish_state`.
- Live updates use Server-Sent Events (push), not polling: steady-state load is N idle
  connections that only emit on the two per-question transitions (open / reveal).
"""

import asyncio
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse

import aiohttp
from aiohttp import web

# ---------------------------------------------------------------------------
# Module state (set by start_companion_web)
# ---------------------------------------------------------------------------

_subscribers = set()          # set[asyncio.Queue] — one per open SSE connection
_resolve_member = None        # callable(user_id:int) -> display_name:str | None
_get_state = None             # callable(user_id:int|None) -> dict (sanitized live state)
_submit_answer = None         # callable(user_id, display_name, text) -> {"ok":bool,"reason":str}
_reveal_extra = None          # callable(user_id) -> {"my_answers":[...], "result":"correct"/"incorrect"/None}
_session_secret = b""
_oauth_client_id = ""
_oauth_client_secret = ""
_base_url = ""

_SESSION_COOKIE = "okra_companion"
_STATE_COOKIE = "okra_oauth_state"
_SESSION_TTL = 12 * 3600      # 12h; re-auth is cheap
_STATE_TTL = 600              # 10m to complete the OAuth round-trip
_HEARTBEAT_SECONDS = 25       # under Heroku's 55s idle-connection timeout

# crude per-user submit rate limit: user_id -> last submit epoch
_last_submit = {}
_SUBMIT_MIN_INTERVAL = 0.4


# ---------------------------------------------------------------------------
# Signed-cookie helpers (stdlib HMAC; no extra dependency)
# ---------------------------------------------------------------------------

def _sign(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(_session_secret, raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def _unsign(token: str):
    if not token or "." not in token:
        return None
    raw, _, sig = token.partition(".")
    expected = hmac.new(_session_secret, raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        padded = raw + "=" * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        return None
    if float(payload.get("exp", 0)) < time.time():
        return None
    return payload


def _session_from_request(request):
    return _unsign(request.cookies.get(_SESSION_COOKIE, ""))


# ---------------------------------------------------------------------------
# SSE publish (called from the bot's game loop)
# ---------------------------------------------------------------------------

def publish_state(state: dict):
    """Fan a state dict out to all connected SSE clients. Never raises."""
    try:
        for queue in list(_subscribers):
            try:
                queue.put_nowait(state)
            except Exception:
                pass
    except Exception:
        pass


async def _write_event(resp, data: dict):
    await resp.write(f"data: {json.dumps(data)}\n\n".encode())


# ---------------------------------------------------------------------------
# OAuth2
# ---------------------------------------------------------------------------

def _redirect_uri():
    return f"{_base_url.rstrip('/')}/auth/callback"


async def handle_login(request):
    if not _oauth_client_id or not _oauth_client_secret:
        return web.Response(text="Companion login is not configured yet.", status=503)
    state = base64.urlsafe_b64encode(os.urandom(16)).decode().rstrip("=")
    params = {
        "client_id": _oauth_client_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": "identify",
        "state": state,
        # No prompt=none: first-time users must see the consent screen; Discord auto-skips
        # it on subsequent logins once the identify scope is already authorized.
    }
    url = "https://discord.com/api/oauth2/authorize?" + urllib.parse.urlencode(params)
    resp = web.HTTPFound(url)
    resp.set_cookie(
        _STATE_COOKIE, _sign({"state": state, "exp": time.time() + _STATE_TTL}),
        max_age=_STATE_TTL, httponly=True, secure=_base_url.startswith("https"), samesite="Lax",
    )
    return resp


async def handle_callback(request):
    code = request.query.get("code")
    state = request.query.get("state")
    cookie_state = _unsign(request.cookies.get(_STATE_COOKIE, ""))
    if not code or not state or not cookie_state or cookie_state.get("state") != state:
        return web.Response(text="Login failed (bad state). Please try again.", status=400)

    async with aiohttp.ClientSession() as http:
        token_data = {
            "client_id": _oauth_client_id,
            "client_secret": _oauth_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _redirect_uri(),
        }
        async with http.post(
            "https://discord.com/api/oauth2/token",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as tok_resp:
            if tok_resp.status != 200:
                return web.Response(text="Login failed (token exchange).", status=400)
            token = await tok_resp.json()
        access_token = token.get("access_token")
        async with http.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        ) as me_resp:
            if me_resp.status != 200:
                return web.Response(text="Login failed (identify).", status=400)
            me = await me_resp.json()

    user_id = int(me["id"])
    # Authoritative anti-impersonation + attribution: must be a guild member, and we use
    # the server nickname so it matches the display_name used everywhere in scoring.
    display_name = _resolve_member(user_id) if _resolve_member else None
    if not display_name:
        return web.Response(
            text="You need to be a member of the trivia server to play. Join, then try again.",
            status=403,
        )

    session = {"user_id": user_id, "display_name": display_name, "exp": time.time() + _SESSION_TTL}
    resp = web.HTTPFound("/")
    resp.set_cookie(
        _SESSION_COOKIE, _sign(session),
        max_age=_SESSION_TTL, httponly=True, secure=_base_url.startswith("https"), samesite="Lax",
    )
    resp.del_cookie(_STATE_COOKIE)
    return resp


async def handle_logout(request):
    resp = web.HTTPFound("/")
    resp.del_cookie(_SESSION_COOKIE)
    return resp


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

async def handle_current(request):
    session = _session_from_request(request)
    if not session:
        return web.json_response({"authenticated": False}, status=401)
    state = _get_state(session["user_id"]) if _get_state else {"phase": "idle"}
    state = dict(state)
    state["authenticated"] = True
    state["display_name"] = session["display_name"]
    return web.json_response(state)


async def handle_stream(request):
    session = _session_from_request(request)
    if not session:
        return web.json_response({"authenticated": False}, status=401)

    resp = web.StreamResponse(
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
    await resp.prepare(request)

    queue = asyncio.Queue(maxsize=32)
    _subscribers.add(queue)
    try:
        # Send current state immediately so a fresh connection renders without waiting.
        if _get_state:
            await _write_event(resp, _get_state(session["user_id"]))
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
                # The reveal is broadcast; personalize it per connection with this user's own
                # submissions + result (copy so we never mutate the shared dict).
                if _reveal_extra and isinstance(data, dict) and data.get("phase") == "revealed":
                    try:
                        data = {**data, **_reveal_extra(session["user_id"])}
                    except Exception:
                        pass
                await _write_event(resp, data)
            except asyncio.TimeoutError:
                await resp.write(b": heartbeat\n\n")
    except (asyncio.CancelledError, ConnectionResetError, ConnectionError):
        pass
    finally:
        _subscribers.discard(queue)
    return resp


async def handle_answer(request):
    session = _session_from_request(request)
    if not session:
        return web.json_response({"ok": False, "reason": "unauthenticated"}, status=401)

    user_id = session["user_id"]
    now = time.time()
    last = _last_submit.get(user_id, 0)
    if now - last < _SUBMIT_MIN_INTERVAL:
        return web.json_response({"ok": False, "reason": "rate_limited"}, status=429)
    _last_submit[user_id] = now

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "reason": "bad_request"}, status=400)
    answer = (body.get("answer") or "").strip()
    if not answer:
        return web.json_response({"ok": False, "reason": "empty"}, status=400)

    result = _submit_answer(user_id, session["display_name"], answer) if _submit_answer else {"ok": False, "reason": "unavailable"}
    status = 200 if result.get("ok") else 409
    return web.json_response(result, status=status)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

# Brand logos, inlined as WebP data URIs so the page is fully self-contained (no external hosts).
# Play-button app mark + okra chef mascot; referenced via CSS vars --play / --okra.
_PLAY_LOGO = "data:image/webp;base64,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"
_OKRA_LOGO = "data:image/webp;base64,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"
# TriviaSphere wordmark logos: header (with tagline), footer (name only), favicon (mark only).
_HEADER_LOGO="data:image/webp;base64,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"
_FOOTER_LOGO="data:image/webp;base64,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"
_FAVICON="data:image/webp;base64,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"

_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>TriviaSphere</title>
<meta name="theme-color" content="#06080D" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#F8F8F8" media="(prefers-color-scheme: light)">
<link rel="icon" type="image/webp" href="__FAVICON__">
<style>
  :root {
    color-scheme: light dark;
    --blue:#146DE8; --blue-600:#0A4FB5; --red:#F71A14;
    --bg:#06080D; --bg2:#0E1219; --fg:#F8F8F8; --muted:rgba(248,248,248,.58);
    --card:rgba(248,248,248,.05); --line:rgba(248,248,248,.10);
    --play:url(__PLAY_LOGO__); --okra:url(__OKRA_LOGO__);
    --header-logo:url(__HEADER_LOGO__); --footer-logo:url(__FOOTER_LOGO__);
  }
  @media (prefers-color-scheme: light) {
    :root { --bg:#F8F8F8; --bg2:#FCFCFC; --fg:#06080D; --muted:rgba(6,8,13,.55);
            --card:#ffffff; --line:rgba(6,8,13,.10); }
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
  .simple-toggle { display:flex; align-items:center; gap:8px; flex:none; cursor:pointer; }
  .simple-toggle span.lbl { font-size:.72rem; font-weight:700; letter-spacing:.02em; color:var(--muted); white-space:nowrap; }
  .switch { position:relative; display:inline-block; width:40px; height:23px; flex:none; }
  .switch input { position:absolute; inset:0; opacity:0; margin:0; cursor:pointer; }
  .switch .track { position:absolute; inset:0; border-radius:999px; background:rgba(127,127,127,.20);
    border:1px solid var(--line); transition:background-color .15s, border-color .15s; }
  .switch .thumb { position:absolute; top:2px; left:2px; width:17px; height:17px; border-radius:50%;
    background:#fff; box-shadow:0 1px 3px rgba(0,0,0,.35); transition:transform .15s; }
  .switch input:checked ~ .track { background:var(--blue); border-color:var(--blue); }
  .switch input:checked ~ .track .thumb { transform:translateX(17px); }
  .switch input:focus-visible ~ .track { box-shadow:0 0 0 3px rgba(20,109,232,.30); }
  .sub { color:var(--muted); font-size:.86rem; margin:13px 2px 20px; line-height:1.45; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:20px; padding:22px;
    box-shadow:0 12px 32px rgba(0,0,0,.20); }
  .qhead { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:14px; }
  .cat { font-size:.7rem; font-weight:700; text-transform:uppercase; letter-spacing:.1em; color:var(--muted); }
  .timer { flex:none; font-variant-numeric:tabular-nums; font-weight:800; font-size:.74rem;
    padding:4px 10px; border-radius:999px; background:rgba(20,109,232,.16); color:var(--blue); }
  .timer.low { background:rgba(247,26,20,.16); color:var(--red); }
  .q { font-size:1.3rem; font-weight:650; line-height:1.34; margin-bottom:20px; letter-spacing:-.01em; }
  .qimage { display:block; width:100%; max-height:44vh; object-fit:contain; border-radius:12px;
    margin:0 0 16px; background:rgba(127,127,127,.06); }
  .puzzle { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:1.35rem;
    letter-spacing:.18em; text-align:center; margin:2px 0 18px; color:var(--fg); overflow-x:auto; }
  input[type=text] { width:100%; padding:15px 16px; font-size:1.05rem; border-radius:14px;
    border:1px solid var(--line); background:rgba(127,127,127,.08); color:inherit; }
  input[type=text]:focus { outline:none; border-color:var(--blue); box-shadow:0 0 0 3px rgba(20,109,232,.25); }
  button.primary { width:100%; margin-top:12px; padding:15px; font-size:1.05rem; font-weight:700;
    border:none; border-radius:14px; color:#fff; cursor:pointer;
    background:linear-gradient(180deg,var(--blue),var(--blue-600)); box-shadow:0 6px 16px rgba(20,109,232,.30); }
  button.primary:active { transform:translateY(1px); }
  button.primary:disabled { opacity:.5; box-shadow:none; cursor:default; }
  .choices { display:grid; gap:10px; }
  .ortype { text-align:center; color:var(--muted); font-size:.78rem; margin:14px 0 10px; }
  .choice { padding:15px 16px; font-size:1.02rem; text-align:left; border-radius:14px;
    border:1px solid var(--line); background:rgba(127,127,127,.06); color:inherit; cursor:pointer;
    display:flex; align-items:center; gap:10px;
    transition:border-color .12s, background-color .12s, box-shadow .12s, transform .06s; }
  .choice:active { transform:scale(.99); }
  .choice.selected { border-color:var(--blue); background:rgba(20,109,232,.18);
    box-shadow:0 0 0 2px rgba(20,109,232,.45) inset; font-weight:700; }
  .choice.simple { justify-content:center; text-align:center; }
  .choice .tick { margin-left:auto; flex:none; font-weight:800; color:var(--blue); }
  .choice.dim { opacity:.45; }
  .choice.selected:disabled, .choice.selected.dim { opacity:1; }
  .status { margin-top:14px; font-size:.95rem; min-height:1.2em; }
  .ok { color:#3ddc84; } .bad { color:var(--red); }
  .warn { display:inline-block; font-size:.82rem; font-weight:600; padding:6px 11px; border-radius:10px;
    margin:0 0 14px; background:rgba(255,170,40,.14); border:1px solid rgba(255,170,40,.42); color:#ffb43a; }
  .result { font-size:1.1rem; font-weight:800; letter-spacing:-.01em; margin:2px 0 10px; }
  .result.correct { color:#3ddc84; } .result.incorrect { color:var(--red); } .result.none { color:var(--muted); }
  .sbtitle { font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em;
    color:var(--muted); margin:20px 0 8px; }
  .sb { display:flex; flex-direction:column; gap:3px; max-height:46vh; overflow-y:auto; }
  .sbrow { display:flex; align-items:center; gap:8px; padding:8px 11px; border-radius:11px;
    background:rgba(127,127,127,.07); font-size:.94rem; }
  .sbrank { min-width:1.5em; text-align:center; flex:none; }
  .sbname { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .sblight { flex:none; font-size:.82rem; color:var(--muted); margin-right:6px; }
  .sbscore { flex:none; font-variant-numeric:tabular-nums; font-weight:700; }
  .sbdelta { flex:none; color:#3ddc84; font-weight:600; font-size:.85em; margin-left:4px; }
  .sbapp { flex:none; font-size:.9rem; margin-left:2px; }
  .legend { display:flex; flex-wrap:wrap; gap:6px; margin-top:16px; }
  .lchip { font-size:.72rem; font-weight:600; padding:4px 9px; border-radius:999px;
    background:rgba(127,127,127,.10); border:1px solid var(--line); color:var(--muted); }
  .rndtitle { font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em;
    color:var(--muted); margin:20px 0 8px; }
  .rnd { display:flex; flex-wrap:wrap; gap:6px; }
  .rchip { font-size:.72rem; font-weight:600; padding:4px 9px; border-radius:8px;
    background:rgba(127,127,127,.08); border:1px solid var(--line); color:var(--muted); }
  .rchip.cur { background:rgba(20,109,232,.16); border-color:var(--blue); color:var(--blue); }
  .rchip.done { opacity:.45; }
  .hero { text-align:center; padding:6px 0 2px; }
  .mascot { width:130px; aspect-ratio:338/595; margin:0 auto 8px;
    background:var(--okra) center/contain no-repeat; filter:drop-shadow(0 8px 18px rgba(0,0,0,.28)); }
  .mascot.sm { width:92px; }
  .hero h2 { font-size:1.18rem; font-weight:750; margin:4px 0 4px; letter-spacing:-.01em; }
  .hero p { color:var(--muted); font-size:.9rem; margin:0 0 18px; line-height:1.4; }
  .login { display:inline-flex; align-items:center; gap:9px; padding:14px 24px; background:#5865f2;
    color:#fff; text-decoration:none; border-radius:14px; font-weight:700; box-shadow:0 6px 16px rgba(88,101,242,.35); }
  .login svg { width:20px; height:20px; }
  .idle { text-align:center; color:var(--muted); padding:10px 0 6px; line-height:1.5; }
  .idle .big { display:block; font-weight:650; color:var(--fg); margin:2px 0 2px; }
  .me { font-size:.78rem; color:var(--muted); margin-top:20px; text-align:center; }
  .logout { color:var(--blue); text-decoration:none; font-weight:600; }
  .foot { display:flex; align-items:center; justify-content:center; gap:8px; margin-top:16px;
    color:var(--muted); font-size:.72rem; font-weight:600; opacity:.85; }
  .footlogo { height:32px; width:32px; display:inline-block;
    background:var(--footer-logo) center/contain no-repeat; }
</style>
</head>
<body>
<div class="wrap">
  <header class="brand">
    <div class="brandhead">
      <div class="brandlogo" role="img" aria-label="TriviaSphere logo"></div>
    </div>
    <label class="simple-toggle">
      <span class="lbl">Detail mode</span>
      <span class="switch">
        <input type="checkbox" id="simpleToggle" onchange="onSimpleToggle(this.checked)">
        <span class="track"><span class="thumb"></span></span>
      </span>
    </label>
  </header>
  <div class="sub">Answer live from your phone or computer — private, timed, and scored right alongside everyone in the channel.</div>
  <div id="app" class="card"><div class="idle">Loading…</div></div>
  <div id="me" class="me"></div>
  <footer class="foot"><span class="footlogo" role="img" aria-label="TriviaSphere"></span></footer>
</div>
<script>
let es = null, countdownTimer = null, endsAt = 0, currentKey = null, answeredKey = null, answeredValue = null, oneGuess = false;
let simpleMode = true, lastState = null;
var DISCORD_SVG = '<svg viewBox="0 -28.5 256 256" fill="currentColor" aria-hidden="true"><path d="M216.856 16.597A208.502 208.502 0 0 0 164.042 0c-2.275 4.113-4.933 9.645-6.766 14.046-19.692-2.961-39.203-2.961-58.533 0-1.832-4.4-4.55-9.933-6.846-14.046a207.809 207.809 0 0 0-52.855 16.638C5.618 67.147-3.443 116.4 1.087 164.956c22.169 16.555 43.653 26.612 64.775 33.193A161.094 161.094 0 0 0 79.735 175.3a136.413 136.413 0 0 1-21.846-10.632 108.636 108.636 0 0 0 5.356-4.237c42.122 19.702 87.89 19.702 129.51 0a131.66 131.66 0 0 0 5.355 4.237 136.07 136.07 0 0 1-21.886 10.653c4.006 8.02 8.638 15.67 13.873 22.848 21.142-6.581 42.646-16.637 64.815-33.213 5.316-56.288-9.081-105.09-38.056-148.36ZM85.474 135.095c-12.645 0-23.015-11.805-23.015-26.18s10.149-26.2 23.015-26.2c12.867 0 23.236 11.804 23.015 26.2.02 14.375-10.148 26.18-23.015 26.18Zm85.051 0c-12.645 0-23.014-11.805-23.014-26.18s10.148-26.2 23.014-26.2c12.867 0 23.236 11.804 23.015 26.2 0 14.375-10.148 26.18-23.015 26.18Z"/></svg>';

function roundHtml(state) {
  var rq = state.round_overview;
  if (!rq || !rq.length) return '';
  var cur = state.question_number || 0;
  return '<div class="rndtitle">This round</div><div class="rnd">' + rq.map(function (cat, i) {
    var n = i + 1;
    var cls = n === cur ? 'rchip cur' : (n < cur ? 'rchip done' : 'rchip');
    return '<span class="' + cls + '">' + n + '. ' + esc(cat || '') + '</span>';
  }).join('') + '</div>';
}

function legendHtml(state) {
  var m = state.modes;
  if (!m || !m.length) return '';
  return '<div class="legend">' + m.map(function (x) {
    return '<span class="lchip">' + esc(x.emoji || '') + ' ' + esc(x.label || '') + '</span>';
  }).join('') + '</div>';
}

function scoreboardHtml(state) {
  var sb = state.scoreboard;
  if (!sb || !sb.length) return '';
  return '<div class="sbtitle">Scoreboard</div><div class="sb">' + sb.map(function (r) {
    return '<div class="sbrow">' +
      '<span class="sbrank">' + esc(r.rank || '') + '</span>' +
      '<span class="sbname">' + esc(r.name || '') + '</span>' +
      (r.lightning ? '<span class="sblight">⚡' + r.lightning + '</span>' : '') +
      '<span class="sbscore">' + esc(r.score || '') + '</span>' +
      (r.delta ? '<span class="sbdelta">' + esc(r.delta) + '</span>' : '') +
      (r.via_companion ? '<span class="sbapp" title="Answered via the app">🌐</span>' : '') +
    '</div>';
  }).join('') + '</div>';
}

function puzzleHtml(state) {
  return state.puzzle_text ? '<div class="puzzle">' + esc(state.puzzle_text) + '</div>' : '';
}

function imgHtml(state) {
  return state.image_url
    ? '<img class="qimage" src="' + esc(state.image_url) + '" alt="Question image" ' +
      'referrerpolicy="no-referrer" onerror="this.style.display=\\'none\\'">'
    : '';
}

function fmtRemaining() {
  const rem = Math.max(0, Math.ceil(endsAt - Date.now() / 1000));
  const el = document.getElementById('timer');
  if (el) { el.textContent = rem + 's'; el.classList.toggle('low', rem <= 5); }
  if (rem <= 0 && countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
}

function onSimpleToggle(checked) {
  simpleMode = !checked;
  if (lastState) render(lastState);
}

function render(state) {
  const app = document.getElementById('app');
  lastState = state;
  if (state.authenticated === false) {
    app.innerHTML = '<div class="hero"><div class="mascot"></div>' +
      '<h2>Ready to play?</h2>' +
      '<p>Log in with Discord to answer live questions privately from your phone or computer.</p>' +
      '<a class="login" href="/login">' + DISCORD_SVG + 'Login with Discord</a></div>';
    return;
  }
  if (state.display_name) document.getElementById('me').innerHTML = 'Playing as ' + esc(state.display_name) +
    ' · <a class="logout" href="/logout">Log out</a>';

  if (state.phase === 'revealed') {
    // All of this user's submissions (merged in per-connection by the SSE layer), falling back
    // to the one we tracked locally this session.
    var answers = (state.my_answers && state.my_answers.length) ? state.my_answers
      : ((answeredKey === state.question_key && answeredValue) ? [answeredValue] : []);
    var mine = answers.length
      ? '<div class="status">Your answer' + (answers.length > 1 ? 's' : '') + ': ' +
          answers.map(esc).join(', ') + '</div>'
      : '';
    var resultBanner = '';
    if (!state.blind && state.result === 'correct') {
      resultBanner = '<div class="result correct">✅ You got it right!</div>';
    } else if (!state.blind && state.result === 'incorrect') {
      resultBanner = '<div class="result incorrect">❌ Not quite</div>';
    } else if (!state.blind && !answers.length) {
      resultBanner = '<div class="result none">You didn\\'t answer this one.</div>';
    }
    const answerLine = state.blind
      ? '<div class="status">🙈 Answers are hidden this round.</div>'
      : '<div class="status ok">✅ Answer: ' + esc(state.correct_answer || '') + '</div>';
    app.innerHTML = simpleMode
      ? resultBanner + answerLine
      : '<div class="cat">' + esc(state.category || '') + '</div>' +
        (state.question ? '<div class="q">' + esc(state.question) + '</div>' : '') +
        imgHtml(state) +
        resultBanner + answerLine + mine +
        scoreboardHtml(state) + legendHtml(state) + roundHtml(state);
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    return;
  }

  if (state.phase !== 'open') {
    app.innerHTML = '<div class="idle"><div class="mascot sm"></div>' +
      '<span class="big">No live question right now</span>' +
      'The chef is prepping the next one — hang tight. ⏳</div>';
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    return;
  }

  // open
  const isNew = state.question_key !== currentKey;
  if (isNew) answeredValue = null;
  currentKey = state.question_key;
  endsAt = state.ends_at || 0;
  oneGuess = !!state.warning;  // one-guess questions lock after a submit (see submit())

  let inputHtml;
  const prior = (answeredKey === state.question_key && answeredValue) || state.my_answer || '';
  if (state.already_answered) {
    // Locked only when they used the multiple-choice button (one answer on Discord).
    inputHtml = '<div class="status ok">🔒 Locked in' + (prior ? ': ' + esc(prior) : '!') + '</div>' +
      (simpleMode ? '' : '<div class="idle" style="padding:6px 0">Waiting for the reveal…</div>');
  } else {
    if (state.is_multiple_choice && (state.choices || []).length) {
      // Multiple choice: click a choice, or type the letter/answer — both submit the same way.
      // Simple mode shows bare letters (no answer text) for fast, spoiler-free tapping.
      inputHtml = '<div class="choices">' + state.choices.map(function (c) {
        var sel = (answeredKey === state.question_key && answeredValue === c.letter);
        var label = simpleMode ? esc(c.letter) : esc(c.text);
        return '<button class="choice' + (simpleMode ? ' simple' : '') + (sel ? ' selected' : '') + '" data-letter="' + esc(c.letter) + '" ' +
          'onclick="choose(this,\\'' + esc(c.letter) + '\\')">' +
          label + (sel ? '<span class="tick">✓</span>' : '') + '</button>';
      }).join('') + '</div>' +
        '<div class="ortype">or type your answer</div>' +
        '<input id="ans" type="text" autocomplete="off" autocapitalize="off" ' +
        'placeholder="Type a letter or the answer…" onkeydown="if(event.key===\\'Enter\\')submitText()">' +
        '<button class="primary" onclick="submitText()">Submit</button>';
    } else {
      inputHtml = '<input id="ans" type="text" autocomplete="off" autocapitalize="off" ' +
        'placeholder="Type your answer…" onkeydown="if(event.key===\\'Enter\\')submitText()">' +
        '<button class="primary" onclick="submitText()">Submit</button>';
    }
    // Multiple answers are allowed (like typing in Discord): note the last one, keep inputs open.
    if (prior) inputHtml = '<div class="status ok">✓ Submitted: ' + esc(prior) +
      ' — you can submit again</div>' + inputHtml;
  }

  app.innerHTML = simpleMode
    ? inputHtml + '<div id="status" class="status"></div>'
    : '<div class="qhead"><span class="cat">' + esc(state.category || '') + '</span>' +
        '<span id="timer" class="timer">--</span></div>' +
        (state.question ? '<div class="q">' + esc(state.question) + '</div>' : '') +
        imgHtml(state) + puzzleHtml(state) +
        (state.warning ? '<div class="warn">' + esc(state.warning) + '</div>' : '') + inputHtml +
        '<div id="status" class="status"></div>' + legendHtml(state) + roundHtml(state);

  if (isNew && !state.already_answered) { const i = document.getElementById('ans'); if (i) i.focus(); }
  if (countdownTimer) clearInterval(countdownTimer);
  fmtRemaining();
  countdownTimer = setInterval(fmtRemaining, 250);
}

function esc(s) { return String(s).replace(/[&<>"']/g, function (c) {
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }

function setStatus(msg, cls) {
  const el = document.getElementById('status');
  if (el) { el.textContent = msg; el.className = 'status ' + (cls || ''); }
}

function markChoice(letter) {
  // Give the tapped multiple-choice option an obvious selected state (no-op for typed answers).
  document.querySelectorAll('.choice').forEach(function (b) {
    var on = b.getAttribute('data-letter') === letter;
    b.classList.toggle('selected', on);
    var tick = b.querySelector('.tick');
    if (on && !tick) { var t = document.createElement('span'); t.className = 'tick'; t.textContent = '✓'; b.appendChild(t); }
    else if (!on && tick) { tick.remove(); }
  });
}
function choose(el, letter) { markChoice(letter); submit(letter); }

async function submit(answer) {
  try {
    const r = await fetch('/api/answer', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({answer: answer}),
    });
    const data = await r.json();
    if (data.ok) {
      answeredKey = currentKey;
      answeredValue = answer;
      markChoice(answer);  // highlight the chosen option (no-op for typed free-text)
      if (oneGuess) {
        // One-guess question: lock the inputs after the single allowed submit.
        setStatus('🔒 Locked in: ' + answer, 'ok');
        const inp = document.getElementById('ans'); if (inp) inp.disabled = true;
        document.querySelectorAll('.choice').forEach(function (b) {
          b.disabled = true;
          if (b.getAttribute('data-letter') !== answer) b.classList.add('dim');
        });
        const btn = document.querySelector('button.primary'); if (btn) btn.disabled = true;
      } else {
        // Free-text: multiple submissions allowed (like Discord typing).
        setStatus('✓ Submitted: ' + answer + ' — you can submit again', 'ok');
        const inp = document.getElementById('ans'); if (inp) { inp.value = ''; inp.focus(); }
      }
    } else if (data.reason === 'already') {
      answeredKey = currentKey; setStatus('You already answered this question.', 'ok');
    } else if (data.reason === 'closed') {
      setStatus("⏰ That question just closed.", 'bad');
    } else {
      setStatus('Could not submit (' + (data.reason || 'error') + ').', 'bad');
    }
  } catch (e) { setStatus('Network error — try again.', 'bad'); }
}
function submitText() {
  const inp = document.getElementById('ans');
  if (inp && inp.value.trim()) submit(inp.value.trim());
}

function connect() {
  es = new EventSource('/api/stream');
  es.onmessage = function (ev) { try { render(JSON.parse(ev.data)); } catch (e) {} };
  es.onerror = function () { /* EventSource auto-reconnects */ };
}

fetch('/api/current').then(function (r) { return r.json(); })
  .then(function (s) { render(s); if (s.authenticated !== false) connect(); })
  .catch(function () { render({phase: 'idle', authenticated: true}); connect(); });
</script>
</body>
</html>
"""
_INDEX_HTML = (_INDEX_HTML
    .replace("__PLAY_LOGO__", _PLAY_LOGO)
    .replace("__OKRA_LOGO__", _OKRA_LOGO)
    .replace("__HEADER_LOGO__", _HEADER_LOGO)
    .replace("__FOOTER_LOGO__", _FOOTER_LOGO)
    .replace("__FAVICON__", _FAVICON))


async def handle_index(request):
    return web.Response(text=_INDEX_HTML, content_type="text/html")


async def handle_health(request):
    return web.Response(text="ok")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

async def start_companion_web(*, resolve_member, get_state, submit_answer, reveal_extra=None):
    """Bind the aiohttp server to $PORT and start serving. Called from the bot's main()
    before the long-running gather so Heroku sees the port bound promptly (avoids R10)."""
    global _resolve_member, _get_state, _submit_answer, _reveal_extra
    global _session_secret, _oauth_client_id, _oauth_client_secret, _base_url

    _resolve_member = resolve_member
    _get_state = get_state
    _submit_answer = submit_answer
    _reveal_extra = reveal_extra

    secret = os.getenv("COMPANION_SESSION_SECRET")
    if not secret:
        secret = base64.urlsafe_b64encode(os.urandom(32)).decode()
        print("⚠️  COMPANION_SESSION_SECRET not set — using an ephemeral secret "
              "(sessions won't survive a restart).")
    _session_secret = secret.encode()
    _oauth_client_id = os.getenv("DISCORD_OAUTH_CLIENT_ID", "")
    _oauth_client_secret = os.getenv("DISCORD_OAUTH_CLIENT_SECRET", "")
    _base_url = os.getenv("COMPANION_BASE_URL", "")

    app = web.Application()
    app.add_routes([
        web.get("/", handle_index),
        web.get("/healthz", handle_health),
        web.get("/login", handle_login),
        web.get("/logout", handle_logout),
        web.get("/auth/callback", handle_callback),
        web.get("/api/current", handle_current),
        web.get("/api/stream", handle_stream),
        web.post("/api/answer", handle_answer),
    ])

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    if not _base_url:
        _base_url = f"http://localhost:{port}"
    print(f"🌐 Companion web app listening on :{port} (base_url={_base_url})")
    return runner
