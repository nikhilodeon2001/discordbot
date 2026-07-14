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

_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Okra Trivia — Live Answer</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: #0f1115; color: #f2f4f8; min-height: 100vh; display: flex; flex-direction: column;
         align-items: center; padding: 24px 16px calc(24px + env(safe-area-inset-bottom)); }
  @media (prefers-color-scheme: light) { body { background: #f5f6fa; color: #16181d; } }
  .wrap { width: 100%; max-width: 520px; }
  h1 { font-size: 1.15rem; font-weight: 700; margin: 0 0 4px; letter-spacing: .01em; }
  .sub { opacity: .6; font-size: .82rem; margin-bottom: 20px; }
  .card { background: rgba(127,127,127,.10); border: 1px solid rgba(127,127,127,.18);
          border-radius: 16px; padding: 20px; }
  .cat { font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; opacity: .6; margin-bottom: 8px; }
  .q { font-size: 1.25rem; font-weight: 600; line-height: 1.35; margin-bottom: 18px; }
  .timer { font-variant-numeric: tabular-nums; font-weight: 700; font-size: 1rem; }
  .timer.low { color: #ff5c5c; }
  input[type=text] { width: 100%; padding: 14px 16px; font-size: 1.05rem; border-radius: 12px;
          border: 1px solid rgba(127,127,127,.3); background: rgba(127,127,127,.08); color: inherit; }
  input[type=text]:focus { outline: 2px solid #5865f2; }
  button.primary { width: 100%; margin-top: 12px; padding: 14px; font-size: 1.05rem; font-weight: 600;
          border: none; border-radius: 12px; background: #5865f2; color: #fff; cursor: pointer; }
  button.primary:disabled { opacity: .5; cursor: default; }
  .choices { display: grid; gap: 10px; }
  .choice { padding: 14px 16px; font-size: 1.02rem; text-align: left; border-radius: 12px;
          border: 1px solid rgba(127,127,127,.3); background: rgba(127,127,127,.08); color: inherit; cursor: pointer; }
  .choice:active { transform: scale(.99); }
  .status { margin-top: 14px; font-size: .95rem; min-height: 1.2em; }
  .ok { color: #46d17f; } .bad { color: #ff5c5c; }
  .login { display: inline-block; margin-top: 8px; padding: 14px 22px; background: #5865f2; color: #fff;
          text-decoration: none; border-radius: 12px; font-weight: 600; }
  .idle { text-align: center; opacity: .7; padding: 30px 0; }
  .me { font-size: .78rem; opacity: .55; margin-top: 22px; text-align: center; }
</style>
</head>
<body>
<div class="wrap">
  <h1>🥒 Okra Trivia</h1>
  <div class="sub">Answer live from your phone — private, timed, and scored with everyone else.</div>
  <div id="app" class="card"><div class="idle">Loading…</div></div>
  <div id="me" class="me"></div>
</div>
<script>
let es = null, countdownTimer = null, endsAt = 0, currentKey = null, answeredKey = null;

function fmtRemaining() {
  const rem = Math.max(0, Math.ceil(endsAt - Date.now() / 1000));
  const el = document.getElementById('timer');
  if (el) { el.textContent = rem + 's'; el.classList.toggle('low', rem <= 5); }
  if (rem <= 0 && countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
}

function render(state) {
  const app = document.getElementById('app');
  if (state.authenticated === false) {
    app.innerHTML = '<div class="idle">Log in with Discord to play.<br><a class="login" href="/login">Login with Discord</a></div>';
    return;
  }
  if (state.display_name) document.getElementById('me').textContent = 'Playing as ' + state.display_name;

  if (state.phase === 'revealed') {
    let mine = '';
    if (answeredKey === state.question_key) mine = '<div class="status">You answered this one.</div>';
    app.innerHTML = '<div class="cat">' + esc(state.category || '') + '</div>' +
      '<div class="q">' + esc(state.question || '') + '</div>' +
      '<div class="status ok">✅ Answer: ' + esc(state.correct_answer || '') + '</div>' + mine;
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    return;
  }

  if (state.phase !== 'open') {
    app.innerHTML = '<div class="idle">No live question right now.<br>Hang tight — the next one is coming up. ⏳</div>';
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    return;
  }

  // open
  const isNew = state.question_key !== currentKey;
  currentKey = state.question_key;
  endsAt = state.ends_at || 0;

  let inputHtml;
  const already = state.already_answered || answeredKey === state.question_key;
  if (already) {
    inputHtml = '<div class="status ok">🔒 Locked in! Waiting for the reveal…</div>';
  } else if (state.is_multiple_choice && (state.choices || []).length) {
    inputHtml = '<div class="choices">' + state.choices.map(function (c) {
      return '<button class="choice" onclick="submit(\\'' + esc(c.letter) + '\\')">' + esc(c.text) + '</button>';
    }).join('') + '</div>';
  } else {
    inputHtml = '<input id="ans" type="text" autocomplete="off" autocapitalize="off" ' +
      'placeholder="Type your answer…" onkeydown="if(event.key===\\'Enter\\')submitText()">' +
      '<button class="primary" onclick="submitText()">Submit</button>';
  }

  app.innerHTML = '<div class="cat">' + esc(state.category || '') +
      ' · <span id="timer" class="timer">--</span></div>' +
      '<div class="q">' + esc(state.question || '') + '</div>' + inputHtml +
      '<div id="status" class="status"></div>';

  if (isNew && !already) { const i = document.getElementById('ans'); if (i) i.focus(); }
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

async function submit(answer) {
  try {
    const r = await fetch('/api/answer', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({answer: answer}),
    });
    const data = await r.json();
    if (data.ok) {
      answeredKey = currentKey;
      setStatus('🔒 Locked in: ' + answer, 'ok');
      const inp = document.getElementById('ans'); if (inp) inp.disabled = true;
      document.querySelectorAll('.choice').forEach(function (b) { b.disabled = true; });
      const btn = document.querySelector('button.primary'); if (btn) btn.disabled = true;
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


async def handle_index(request):
    return web.Response(text=_INDEX_HTML, content_type="text/html")


async def handle_health(request):
    return web.Response(text="ok")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

async def start_companion_web(*, resolve_member, get_state, submit_answer):
    """Bind the aiohttp server to $PORT and start serving. Called from the bot's main()
    before the long-running gather so Heroku sees the port bound promptly (avoids R10)."""
    global _resolve_member, _get_state, _submit_answer
    global _session_secret, _oauth_client_id, _oauth_client_secret, _base_url

    _resolve_member = resolve_member
    _get_state = get_state
    _submit_answer = submit_answer

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
