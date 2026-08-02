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
from html import escape as html_escape

import aiohttp
import boto3
from aiohttp import web

import activity_web
import tv_view

# ---------------------------------------------------------------------------
# Module state (set by start_companion_web)
# ---------------------------------------------------------------------------

# Companion app (logged-in live play) is live at play.triviasphere.com.
COMPANION_APP_ENABLED = True

# Discord Embedded App SDK Activity panel -- staging POC, gated separately from the companion app
# above since it needs its own Discord dev-portal config (URL mappings) and isn't ready for prod.
_ACTIVITY_ENABLED = os.getenv("ACTIVITY_ENABLED", "false").lower() == "true"

_GAMES = ("main", "simply", "arena")
_subscribers = {g: set() for g in _GAMES}   # game -> set[asyncio.Queue], one queue per open SSE connection
_seq = {g: 0 for g in _GAMES}          # game -> monotonic publish counter, for the Activity poll fallback
_last_published = {}                   # game -> last broadcast state dict, ditto
_resolve_member = None        # callable(user_id:int) -> display_name:str | None
_get_state = None             # callable(user_id:int|None, game:str) -> dict (sanitized live state)
_submit_answer = None         # callable(user_id, display_name, text, game) -> {"ok":bool,"reason":str}
_submit_action = None         # async callable(user_id, display_name, text, game) -> {"ok":bool,"reason":str} -- post-round-menu/mini-game submissions, distinct from _submit_answer (live-question grading)
_reveal_extra = None          # callable(user_id, game) -> {"my_answers":[...], "result":"correct"/"incorrect"/None}
_submit_flag = None           # async callable(user_id, display_name, reasons, detail, game) -> {"ok":bool,"reason":str}
_submit_anon_flag = None      # async callable(trivia_db, trivia_id, cat_hint, question_hint, ans_hint, reasons, detail, ip_hash, user_id, display_name) -> {"ok":bool,"reason":str}
_get_flag_reveal_context = None  # async callable(trivia_db, trivia_id) -> {"revealed": bool, "answers": [...]}
_session_secret = b""
_oauth_client_id = ""
_oauth_client_secret = ""
_base_url = ""
_flag_relay_secret = ""       # shared secret for handle_flag_relay (server-to-server flag relay from other apps)

_SESSION_COOKIE = "okra_companion"
_STATE_COOKIE = "okra_oauth_state"
_SESSION_TTL = 12 * 3600      # 12h; re-auth is cheap
_STATE_TTL = 600              # 10m to complete the OAuth round-trip
_HEARTBEAT_SECONDS = 25       # under Heroku's 55s idle-connection timeout

# crude per-user submit rate limit: user_id -> last submit epoch
_last_submit = {}
_SUBMIT_MIN_INTERVAL = 0.4

# crude per-user flag rate limit: user_id -> last flag-attempt epoch. Looser than the answer
# debounce since flagging is a rarer, more deliberate action; the real anti-abuse (one flag per
# question, a daily cap) lives server-side in discordbot.py's companion_submit_flag.
_last_flag = {}
_FLAG_MIN_INTERVAL = 2.0
_FLAG_REASONS = {"category", "question", "answer", "too_niche", "other"}

# Anonymous (no-login) flag links embedded in Simply Trivia embeds -- see make_flag_token() and
# simply_trivia.py. 90 days is generous but bounds how long a leaked/scraped link stays valid.
_FLAG_TOKEN_TTL = 90 * 86400

# crude per-IP anonymous-flag debounce: ip_hash -> last flag epoch. The real anti-abuse (per-
# question cap, per-IP daily cap) lives server-side in discordbot.py's anonymous_submit_flag,
# same split of responsibilities as the logged-in flag flow above.
_anon_last_flag = {}
_ANON_FLAG_MIN_INTERVAL = 5.0

# crude per-user question-submission debounce: user_id -> last submit epoch. Same split as the
# flag flow above -- the real anti-abuse (24h cap, 30-day dedupe) lives server-side in
# discordbot.py's submit_question_for_review, shared with the Discord /submit modal.
_last_question_submit = {}
_QUESTION_SUBMIT_MIN_INTERVAL = 3.0

# Periodic cleanup for the four rate-limit dicts above. Each entry is functionally dead within
# single-digit seconds of being written (every *_MIN_INTERVAL above is well under that), but
# nothing else ever removes one -- left alone, each dict grows by one entry per distinct user/IP
# for the entire life of the process. _RATE_LIMIT_ENTRY_MAX_AGE is a generous margin above the
# largest window above, so pruning can never affect a still-meaningful check.
_RATE_LIMIT_ENTRY_MAX_AGE = 300   # 5 minutes
_RATE_LIMIT_PRUNE_INTERVAL = 900  # 15 minutes
_submit_question = None      # async callable(user_id, display_name, sub_type, category, question, correct_answer, alternates, source) -> (doc, error)
_submit_bulk_questions = None  # async callable(user_id, display_name, raw_text, source) -> (accepted_docs, skipped_messages)
_turnstile_site_key = ""     # Cloudflare Turnstile site key, rendered into the /submit page's widget
_turnstile_secret_key = ""   # Cloudflare Turnstile secret key, verified server-side on /api/submit_question
_discord_invite_url = ""     # shown in the "join the server" 403 when a non-member tries to log in


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
    """Read the session token from wherever it arrived: the cookie (companion web/phone), an
    Authorization header (Activity fetches), or a `?s=` query param (Activity EventSource, which
    cannot set custom headers) -- GET-only so a session token can never land in a POST query
    string. Deliberately `?s=`, not `?t=`: that param is already the anonymous flag token
    (handle_flag_page/handle_flag_anon), publicly embedded in Discord messages and signed with the
    same secret, so accepting it here would let a scraped flag link be treated as a session.
    Since three token kinds now share one secret, also assert the session's own shape (_unsign
    only checks HMAC + exp) so a flag/oauth-state token can't slip through and crash a handler
    that assumes `user_id`/`display_name` are present."""
    token = request.cookies.get(_SESSION_COOKIE, "")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token and request.method == "GET":
        token = request.query.get("s", "")
    payload = _unsign(token)
    if not payload or not isinstance(payload.get("user_id"), int) or not payload.get("display_name"):
        return None
    return payload


def _client_kind_from_request(request):
    """Which surface authenticated this request: the Activity (no session cookie -- auth arrives
    via the Authorization header, since the Activity iframe can't use the companion's session
    cookie -- see _session_from_request) vs. the phone/web companion (session cookie present).
    Used only to tag where a submitted answer came from, for the scoreboard's per-answer icon."""
    return "companion" if request.cookies.get(_SESSION_COOKIE, "") else "activity"


def get_base_url():
    """Public accessor for the companion app's base URL, so other modules (e.g. simply_trivia.py,
    building a flag link for an embed) don't need to reach into the private `_base_url` global."""
    return _base_url


def make_flag_token(trivia_db, trivia_id, category, question_text):
    """Sign a token identifying one specific (possibly historical) question, for the no-login
    'flag this question' link embedded in Simply Trivia messages. Unlike the logged-in companion
    flag flow (which always targets 'whatever is currently live'), a link clicked from an old
    Discord message needs to carry its own question identity, since by the time it's clicked the
    live question has long since moved on. `category`/`question_text` are carried along only for
    display on the flag page -- the moderation report itself re-reads the question fresh from
    Mongo.

    The answer is never embedded here -- one token per question covers both the still-open link
    and the post-reveal link, since whether the answer is safe to show is now checked live on
    every page load (handle_flag_page calls the injected get_flag_reveal_context callback) rather
    than decided once at link-creation time. That also means an old link keeps working correctly
    long after its question has since been revealed, instead of staying frozen at whatever was
    true when it was created."""
    payload = {
        "db": trivia_db,
        "id": str(trivia_id),
        "cat": (category or "")[:200],
        "q": (question_text or "")[:400],
        "exp": time.time() + _FLAG_TOKEN_TTL,
    }
    return _sign(payload)


def _client_ip_hash(request):
    """HMAC the requester's IP (never store it raw) for anonymous-flag rate limiting/dedup."""
    fwd = request.headers.get("X-Forwarded-For", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.remote or "")
    return hmac.new(_session_secret, ip.encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# SSE publish (called from the bot's game loop)
# ---------------------------------------------------------------------------

def publish_state(state: dict, game: str = "main"):
    """Fan a state dict out to SSE clients currently viewing `game`. Never raises. Also records
    a monotonic sequence number and the last-published state so the Activity poll fallback
    (/api/poll) can serve the reveal state even after build_companion_state would report idle."""
    _seq[game] = _seq.get(game, 0) + 1
    _last_published[game] = state
    try:
        for queue in list(_subscribers.get(game, ())):
            try:
                queue.put_nowait(state)
            except Exception:
                pass
    except Exception:
        pass


def _prune_stale_rate_limits():
    """Drop rate-limit entries old enough that they can no longer affect any future check --
    see _RATE_LIMIT_ENTRY_MAX_AGE above for why that's a safe cutoff."""
    cutoff = time.time() - _RATE_LIMIT_ENTRY_MAX_AGE
    for d in (_last_submit, _last_flag, _anon_last_flag, _last_question_submit):
        for key in [k for k, ts in d.items() if ts < cutoff]:
            del d[key]


async def _rate_limit_pruner():
    """Background task, started once in start_companion_web: periodically sweeps the rate-limit
    dicts so they don't grow by one entry per distinct user/IP for the entire process lifetime."""
    while True:
        await asyncio.sleep(_RATE_LIMIT_PRUNE_INTERVAL)
        try:
            _prune_stale_rate_limits()
        except Exception:
            pass


def _game_from_request(request):
    game = request.query.get("game", "main")
    return game if game in _GAMES else "main"


def _game_from_body(body):
    game = body.get("game", "main")
    return game if game in _GAMES else "main"


async def _write_event(resp, data: dict):
    await resp.write(f"data: {json.dumps(data)}\n\n".encode())


# ---------------------------------------------------------------------------
# OAuth2
# ---------------------------------------------------------------------------

def _request_origin(request):
    """(scheme, host) for the hostname the client actually used, so login works correctly no
    matter which registered custom domain (e.g. triviasphere.com or a staging domain) a request
    arrives on -- COMPANION_BASE_URL alone can't express "one app, multiple public domains."
    Heroku's router sets X-Forwarded-Proto/X-Forwarded-Host to the real public-facing values;
    request.scheme/request.host are the fallback for local dev, where those aren't set."""
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
    host = request.headers.get("X-Forwarded-Host", request.host)
    return scheme, host


def _redirect_uri(request):
    scheme, host = _request_origin(request)
    return f"{scheme}://{host}/auth/callback"


def _safe_next(request):
    """Validate a `next` redirect target (used by /login and /logout to return the visitor to
    where they started, e.g. a /flag page) is same-site -- starts with a single `/`, not `//`
    (which browsers treat as protocol-relative, i.e. an external host) -- so it can't be used as
    an open redirect."""
    next_path = request.query.get("next", "")
    if next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return "/"


@web.middleware
async def _https_enforcement_middleware(request, handler):
    """Redirect plain-HTTP requests to HTTPS before any route (esp. /login) can build an
    http:// OAuth redirect_uri, which Discord rejects since only the https:// variant is
    registered per domain. X-Forwarded-Proto is only set by Heroku's router, so its absence
    (local dev) leaves requests untouched."""
    if request.headers.get("X-Forwarded-Proto") == "http":
        _, host = _request_origin(request)
        resp = web.HTTPMovedPermanently(f"https://{host}{request.rel_url}")
        resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        raise resp
    return await handler(request)


async def handle_login(request):
    if not _oauth_client_id or not _oauth_client_secret:
        return web.Response(text="Companion login is not configured yet.", status=503)
    state = base64.urlsafe_b64encode(os.urandom(16)).decode().rstrip("=")
    next_path = _safe_next(request)
    params = {
        "client_id": _oauth_client_id,
        "redirect_uri": _redirect_uri(request),
        "response_type": "code",
        "scope": "identify",
        "state": state,
        # No prompt=none: first-time users must see the consent screen; Discord auto-skips
        # it on subsequent logins once the identify scope is already authorized.
    }
    url = "https://discord.com/api/oauth2/authorize?" + urllib.parse.urlencode(params)
    resp = web.HTTPFound(url)
    scheme, _ = _request_origin(request)
    resp.set_cookie(
        _STATE_COOKIE, _sign({"state": state, "next": next_path, "exp": time.time() + _STATE_TTL}),
        max_age=_STATE_TTL, httponly=True, secure=(scheme == "https"), samesite="Lax",
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
            "redirect_uri": _redirect_uri(request),
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
        # Wording depends on where the login was headed -- "to play" is wrong copy for someone
        # who came here via /submit. Read from the state cookie (not the query string) since
        # that's the one CSRF-protected value we can trust at this point.
        action = "submit a question" if cookie_state.get("next") == "/submit" else "play"
        join_html = (
            f' <a href="{html_escape(_discord_invite_url)}">Join the server</a>, then try again.'
            if _discord_invite_url else " Join the server, then try again."
        )
        return web.Response(
            text=f"You need to be a member of the TriviaSphere server to {action}.{join_html}",
            content_type="text/html",
            status=403,
        )

    session = {"user_id": user_id, "display_name": display_name, "exp": time.time() + _SESSION_TTL}
    resp = web.HTTPFound(cookie_state.get("next") or "/")
    scheme, _ = _request_origin(request)
    resp.set_cookie(
        _SESSION_COOKIE, _sign(session),
        max_age=_SESSION_TTL, httponly=True, secure=(scheme == "https"), samesite="Lax",
    )
    resp.del_cookie(_STATE_COOKIE)
    return resp


async def handle_logout(request):
    resp = web.HTTPFound(_safe_next(request))
    resp.del_cookie(_SESSION_COOKIE)
    return resp


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

async def handle_current(request):
    session = _session_from_request(request)
    if not session:
        return web.json_response({"authenticated": False}, status=401)
    game = _game_from_request(request)
    state = _get_state(session["user_id"], game) if _get_state else {"phase": "idle"}
    state = dict(state)
    if request.query.get("activity") == "1":
        state = activity_web.proxy_images(state)
    state["authenticated"] = True
    state["display_name"] = session["display_name"]
    return web.json_response(state)


async def handle_stream(request):
    session = _session_from_request(request)
    if not session:
        return web.json_response({"authenticated": False}, status=401)
    game = _game_from_request(request)
    as_activity = request.query.get("activity") == "1"

    resp = web.StreamResponse(
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
    await resp.prepare(request)
    if as_activity:
        # Some proxies/CDNs hold back the first chunk of a stream until a size threshold is hit;
        # a padding comment forces immediate flush through Discord's Activity proxy.
        await resp.write(b":" + b" " * 2048 + b"\n\n")

    async def _emit(data):
        await _write_event(resp, activity_web.proxy_images(data) if as_activity else data)

    queue = asyncio.Queue(maxsize=32)
    _subscribers[game].add(queue)
    try:
        # Send current state immediately so a fresh connection renders without waiting.
        if _get_state:
            await _emit(_get_state(session["user_id"], game))
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
                if isinstance(data, dict) and data.get("__refresh__"):
                    # A prompt (post-round menu / mini-game) appeared or cleared -- these carry
                    # no shared payload since e.g. you_can_act differs per viewer from the very
                    # first moment (unlike open/reveal below, where a fresh question means
                    # everyone starts equally unanswered). Re-derive this connection's own state
                    # fresh rather than relying on anything broadcast.
                    if _get_state:
                        try:
                            data = _get_state(session["user_id"], game)
                        except Exception:
                            continue
                    else:
                        continue
                # The reveal is broadcast; personalize it per connection with this user's own
                # submissions + result (copy so we never mutate the shared dict).
                elif _reveal_extra and isinstance(data, dict) and data.get("phase") == "revealed":
                    try:
                        data = {**data, **_reveal_extra(session["user_id"], game)}
                    except Exception:
                        pass
                await _emit(data)
            except asyncio.TimeoutError:
                await resp.write(b": heartbeat\n\n")
    except (asyncio.CancelledError, ConnectionResetError, ConnectionError):
        pass
    finally:
        _subscribers[game].discard(queue)
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
    game = _game_from_body(body)
    client = _client_kind_from_request(request)

    try:
        result = _submit_answer(user_id, session["display_name"], answer, game, client) if _submit_answer else {"ok": False, "reason": "unavailable"}
    except Exception:
        return web.json_response({"ok": False, "reason": "server_error"}, status=500)
    status = 200 if result.get("ok") else 409
    return web.json_response(result, status=status)


async def handle_action(request):
    """Post-round-menu / mini-game submissions (the "main" and "arena" toggles' single answer
    slot when no live question is open) -- distinct from handle_answer, which grades a live
    question. See companion_bridge.py for how this resolves into the bot's game logic."""
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
    text = (body.get("text") or "").strip()
    if not text:
        return web.json_response({"ok": False, "reason": "empty"}, status=400)
    game = _game_from_body(body)

    if not _submit_action:
        return web.json_response({"ok": False, "reason": "unavailable"}, status=503)
    try:
        result = await _submit_action(user_id, session["display_name"], text, game)
    except Exception:
        # Never let an unexpected exception surface as a raw non-JSON 500 -- the frontend's
        # r.json() would fail parsing it and misreport this as a generic "Network error".
        return web.json_response({"ok": False, "reason": "server_error"}, status=500)
    status = 200 if result.get("ok") else 409
    return web.json_response(result, status=status)


async def handle_flag(request):
    session = _session_from_request(request)
    if not session:
        return web.json_response({"ok": False, "reason": "unauthenticated"}, status=401)

    user_id = session["user_id"]
    now = time.time()
    last = _last_flag.get(user_id, 0)
    if now - last < _FLAG_MIN_INTERVAL:
        return web.json_response({"ok": False, "reason": "rate_limited"}, status=429)
    _last_flag[user_id] = now

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "reason": "bad_request"}, status=400)
    reasons = [r for r in (body.get("reasons") or []) if r in _FLAG_REASONS]
    if not reasons:
        return web.json_response({"ok": False, "reason": "empty"}, status=400)
    detail = str(body.get("detail") or "").strip()[:500]
    game = _game_from_body(body)

    result = (
        await _submit_flag(user_id, session["display_name"], reasons, detail, game)
        if _submit_flag else {"ok": False, "reason": "unavailable"}
    )
    status = 200 if result.get("ok") else 409
    return web.json_response(result, status=status)


# ---------------------------------------------------------------------------
# Anonymous (no-login) flag page -- linked directly from Simply Trivia embed headers
# ---------------------------------------------------------------------------

# Same Discord glyph as the main companion app's "Login with Discord" button (there it's built
# into a JS string, DISCORD_SVG below -- this page is server-rendered, so it's static HTML here).
_DISCORD_ICON_SVG = (
    '<svg viewBox="0 -28.5 256 256" fill="currentColor" aria-hidden="true">'
    '<path d="M216.856 16.597A208.502 208.502 0 0 0 164.042 0c-2.275 4.113-4.933 9.645-6.766 14.046-19.692-2.961-39.203-2.961-58.533 0-1.832-4.4-4.55-9.933-6.846-14.046a207.809 207.809 0 0 0-52.855 16.638C5.618 67.147-3.443 116.4 1.087 164.956c22.169 16.555 43.653 26.612 64.775 33.193A161.094 161.094 0 0 0 79.735 175.3a136.413 136.413 0 0 1-21.846-10.632 108.636 108.636 0 0 0 5.356-4.237c42.122 19.702 87.89 19.702 129.51 0a131.66 131.66 0 0 0 5.355 4.237 136.07 136.07 0 0 1-21.886 10.653c4.006 8.02 8.638 15.67 13.873 22.848 21.142-6.581 42.646-16.637 64.815-33.213 5.316-56.288-9.081-105.09-38.056-148.36ZM85.474 135.095c-12.645 0-23.015-11.805-23.015-26.18s10.149-26.2 23.015-26.2c12.867 0 23.236 11.804 23.015 26.2.02 14.375-10.148 26.18-23.015 26.18Zm85.051 0c-12.645 0-23.014-11.805-23.014-26.18s10.148-26.2 23.014-26.2c12.867 0 23.236 11.804 23.015 26.2 0 14.375-10.148 26.18-23.015 26.18Z"/>'
    '</svg>'
)

_FLAG_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Flag Question — TriviaSphere</title>
<meta name="theme-color" content="#06080D" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#F8F8F8" media="(prefers-color-scheme: light)">
<link rel="icon" type="image/webp" href="/assets/logo-mark.webp">
<style>
  :root {
    color-scheme: light dark;
    --blue:#146DE8; --blue-600:#0A4FB5; --red:#F71A14;
    --bg:#06080D; --bg2:#0E1219; --fg:#F8F8F8; --muted:rgba(248,248,248,.58);
    --card:rgba(248,248,248,.05); --line:rgba(248,248,248,.10);
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
  .wrap { width:100%; max-width:480px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:20px; padding:22px;
    box-shadow:0 12px 32px rgba(0,0,0,.20); }
  .cardhead { display:flex; align-items:center; gap:10px; margin:0 0 4px; }
  .cardhead .mark { width:26px; height:26px; flex:none;
    background:url(/assets/logo-mark.webp) center/contain no-repeat; }
  .card h3 { margin:0; font-size:1.15rem; font-weight:800; }
  .qctx { margin:10px 0 16px; padding:14px; border-radius:12px; border:1px solid var(--line);
    background:rgba(127,127,127,.06); }
  .qctx .cat { font-size:.7rem; font-weight:700; text-transform:uppercase; letter-spacing:.1em;
    color:var(--muted); margin-bottom:4px; }
  .qctx .q { font-size:1rem; font-weight:700; line-height:1.45; }
  .qctx .ansdivider { height:1px; background:var(--line); margin:14px 0 12px; }
  .qctx .anslabel { font-size:.68rem; font-weight:700; text-transform:uppercase; letter-spacing:.1em;
    color:var(--muted); margin-bottom:3px; }
  .qctx .ansval { font-size:1.02rem; font-weight:800; color:#3ddc84; line-height:1.4; }
  .authcard { display:flex; align-items:center; gap:11px; padding:12px 14px; border-radius:14px;
    border:1px solid var(--line); margin:0 0 16px; text-decoration:none; color:inherit; }
  .authcard--out { background:rgba(88,101,242,.10); border-color:rgba(88,101,242,.35); cursor:pointer; }
  .authcard--out:active { transform:scale(.99); }
  .authcard--in { background:rgba(61,220,132,.08); border-color:rgba(61,220,132,.30); }
  .authicon { flex:none; width:20px; height:20px; display:flex; align-items:center; justify-content:center; }
  .authcard--out .authicon { color:#5865f2; }
  .authcard--in .authicon { color:#3ddc84; font-weight:800; font-size:1rem; }
  .authtext { flex:1; min-width:0; display:flex; flex-direction:column; gap:1px; font-size:.9rem; font-weight:700; }
  .authtext span { font-size:.76rem; font-weight:500; color:var(--muted); }
  .authswitch { flex:none; font-size:.8rem; font-weight:700; color:var(--blue); text-decoration:none; }
  .modalsub { color:var(--muted); font-size:.85rem; margin:0 0 14px; line-height:1.4; }
  .reasons { display:flex; flex-direction:column; gap:8px; margin-bottom:14px; }
  .reasonrow { display:flex; align-items:center; gap:10px; padding:11px 13px; border-radius:12px;
    border:1px solid var(--line); background:rgba(127,127,127,.06); cursor:pointer; font-size:.95rem;
    transition:border-color .12s, background-color .12s; }
  .reasonrow:has(input:checked) { border-color:var(--blue); background:rgba(20,109,232,.10); }
  .reasonrow input { margin:0; }
  #flagDetail { width:100%; padding:13px 14px; font-size:.95rem; border-radius:12px;
    border:1px solid var(--line); background:rgba(127,127,127,.08); color:inherit; resize:vertical;
    min-height:70px; font-family:inherit; margin-bottom:14px; box-sizing:border-box; }
  button.primary { width:100%; padding:15px; font-size:1.02rem; font-weight:700;
    border:none; border-radius:14px; color:#fff; cursor:pointer;
    background:linear-gradient(180deg,var(--blue),var(--blue-600)); box-shadow:0 6px 16px rgba(20,109,232,.30); }
  button.primary:disabled { opacity:.5; box-shadow:none; cursor:default; }
  .status { margin-top:12px; font-size:.9rem; min-height:1.2em; }
  .bad { color:var(--red); }
  .done { text-align:center; font-size:1.02rem; font-weight:650; padding:20px 0; color:#3ddc84; }
  .foot { text-align:center; margin-top:16px; color:var(--muted); font-size:.72rem; font-weight:600; opacity:.85; }
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div class="cardhead"><span class="mark" role="img" aria-label="TriviaSphere"></span><h3>Flag this question</h3></div>
    <div class="qctx">
      <div class="cat">__CATEGORY__</div>
      <div class="q">__QUESTION__</div>
      __ANSWER_BLOCK__
    </div>
    __AUTH_BLOCK__
    <div class="modalsub">What's wrong with this question? Select all that apply.</div>
    <div class="reasons">
      <label class="reasonrow"><input type="checkbox" value="category">Category</label>
      <label class="reasonrow"><input type="checkbox" value="question">Question</label>
      <label class="reasonrow"><input type="checkbox" value="answer">Answer</label>
      <label class="reasonrow"><input type="checkbox" value="too_niche">Too Niche</label>
      <label class="reasonrow"><input type="checkbox" value="other">Other</label>
    </div>
    <textarea id="flagDetail" maxlength="500" placeholder="Provide more detail (optional — recommended if you selected 'Other')"></textarea>
    <button type="button" class="primary" id="flagSubmitBtn" onclick="submitFlag()">Submit</button>
    <div class="status" id="flagStatus"></div>
  </div>
  <div class="foot">TriviaSphere · No login required</div>
</div>
<script>
var TOKEN = __TOKEN_JSON__;
async function submitFlag() {
  var reasons = Array.prototype.slice.call(document.querySelectorAll('.reasons input:checked')).map(function (i) { return i.value; });
  var statusEl = document.getElementById('flagStatus');
  if (!reasons.length) { statusEl.textContent = 'Select at least one reason.'; statusEl.className = 'status bad'; return; }
  var detail = (document.getElementById('flagDetail') || {}).value || '';
  var btn = document.getElementById('flagSubmitBtn');
  btn.disabled = true;
  try {
    var r = await fetch('/api/flag_anon', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({t: TOKEN, reasons: reasons, detail: detail}),
    });
    var data = await r.json();
    if (data.ok) {
      document.querySelector('.card').innerHTML = '<div class="done">✅ Thanks — this question has been flagged for review.<br>You can close this tab now.</div>';
      setTimeout(function () { window.close(); }, 1200);  // best-effort -- most browsers won't allow closing a tab they didn't open via script, so this silently no-ops there; the message above is the real dismiss path
    } else if (data.reason === 'duplicate') {
      statusEl.textContent = "You've already flagged this question."; statusEl.className = 'status bad';
    } else if (data.reason === 'rate_limited') {
      statusEl.textContent = "You're flagging too fast — try again later."; statusEl.className = 'status bad';
    } else if (data.reason === 'question_cap') {
      statusEl.textContent = 'This question has already received enough reports — thanks!'; statusEl.className = 'status bad';
    } else if (data.reason === 'expired') {
      statusEl.textContent = 'This flag link has expired.'; statusEl.className = 'status bad';
    } else {
      statusEl.textContent = 'Could not submit (' + (data.reason || 'error') + ').'; statusEl.className = 'status bad';
    }
  } catch (e) {
    statusEl.textContent = 'Network error — try again.'; statusEl.className = 'status bad';
  } finally {
    btn.disabled = false;
  }
}
</script>
</body>
</html>
"""

_FLAG_EXPIRED_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Link Expired — TriviaSphere</title>
</head>
<body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;text-align:center;padding:60px 20px;color:#666">
  <h2>This flag link is invalid or has expired.</h2>
</body>
</html>
"""


async def handle_flag_page(request):
    payload = _unsign(request.query.get("t", ""))
    if not payload:
        return web.Response(text=_FLAG_EXPIRED_HTML, content_type="text/html", status=400)
    # Checked live, not read from the token (which never carries the answer -- see
    # make_flag_token) -- this is what lets the same link correctly start showing the answer once
    # the question is actually revealed, rather than being frozen at whatever was true when the
    # link was created.
    ctx = (
        await _get_flag_reveal_context(payload.get("db"), payload.get("id"))
        if _get_flag_reveal_context else {"revealed": False, "answers": []}
    )
    answers = ctx.get("answers") or []
    answer_text = ", ".join(str(a) for a in answers) if isinstance(answers, list) else str(answers)
    answer_block = (
        f'<div class="ansdivider"></div><div class="anslabel">Answer</div><div class="ansval">{html_escape(answer_text)}</div>'
        if ctx.get("revealed") and answer_text else ""
    )

    # Attribution is never silent: an existing companion session gets stated explicitly (with a
    # way to switch accounts), and logging in is framed as an explicit "associate this report
    # with your account" action rather than a generic sign-in wall -- either way it's opt-in,
    # submitting without it still works and stays anonymous. Both render as a tappable card (icon +
    # short bold title + muted subtitle) rather than a plain sentence, so it isn't easy to miss.
    next_path = "/flag?t=" + request.query.get("t", "")
    return_param = urllib.parse.quote(next_path, safe="")
    session = _session_from_request(request)
    if session:
        auth_block = (
            '<div class="authcard authcard--in"><span class="authicon">✓</span>'
            f'<div class="authtext"><b>Flagging as {html_escape(session["display_name"])}</b>'
            '<span>Associated with your Discord account</span></div>'
            f'<a class="authswitch" href="/logout?next={return_param}">Switch</a></div>'
        )
    else:
        auth_block = (
            f'<a class="authcard authcard--out" href="/login?next={return_param}">'
            f'<span class="authicon">{_DISCORD_ICON_SVG}</span>'
            '<div class="authtext"><b>Link Discord account</b>'
            '<span>Optional — attaches your name to this report</span></div></a>'
        )

    html = (_FLAG_PAGE_HTML
            .replace("__CATEGORY__", html_escape(payload.get("cat") or "Trivia"))
            .replace("__QUESTION__", html_escape(payload.get("q") or ""))
            .replace("__ANSWER_BLOCK__", answer_block)
            .replace("__AUTH_BLOCK__", auth_block)
            .replace("__TOKEN_JSON__", json.dumps(request.query.get("t", ""))))
    return web.Response(text=html, content_type="text/html")


async def handle_flag_anon(request):
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "reason": "bad_request"}, status=400)

    payload = _unsign(str(body.get("t") or ""))
    if not payload:
        return web.json_response({"ok": False, "reason": "expired"}, status=400)
    trivia_db = payload.get("db")
    trivia_id = payload.get("id")
    if not trivia_db or not trivia_id:
        return web.json_response({"ok": False, "reason": "bad_request"}, status=400)

    reasons = [r for r in (body.get("reasons") or []) if r in _FLAG_REASONS]
    if not reasons:
        return web.json_response({"ok": False, "reason": "empty"}, status=400)
    detail = str(body.get("detail") or "").strip()[:500]

    ip_hash = _client_ip_hash(request)
    now = time.time()
    if now - _anon_last_flag.get(ip_hash, 0) < _ANON_FLAG_MIN_INTERVAL:
        return web.json_response({"ok": False, "reason": "rate_limited"}, status=429)
    _anon_last_flag[ip_hash] = now

    # Live check, same as handle_flag_page -- the token itself never carries the answer. This
    # answer_hint only ever matters as a fallback inside anonymous_submit_flag, if its own fresh
    # Mongo re-fetch there somehow fails to find the document.
    ctx = (
        await _get_flag_reveal_context(trivia_db, trivia_id)
        if _get_flag_reveal_context else {"revealed": False, "answers": []}
    )
    answer_hint = ", ".join(str(a) for a in ctx.get("answers") or []) if ctx.get("revealed") else None

    # An existing companion session identifies the flagger for real -- see handle_flag_page's
    # explicit "this report will be associated with..." messaging, never applied silently.
    session = _session_from_request(request)
    user_id = session["user_id"] if session else None
    display_name = session["display_name"] if session else None

    result = (
        await _submit_anon_flag(trivia_db, trivia_id, payload.get("cat"), payload.get("q"), answer_hint, reasons, detail, ip_hash, user_id, display_name)
        if _submit_anon_flag else {"ok": False, "reason": "unavailable"}
    )
    status = 200 if result.get("ok") else 409
    return web.json_response(result, status=status)


async def handle_flag_relay(request):
    """Server-to-server counterpart of handle_flag_anon for other apps (e.g. trivia-saas) that
    share this Mongo cluster's question collections but run as a separate Discord bot
    application -- they can't post into OKRAN_GUILD_ID's flagged-questions channel themselves, so
    they relay the flag here and let this bot (already a member of that guild) post it, with the
    same FlaggedReviewView buttons as a native flag. Auth is a shared secret, not a login/token --
    this endpoint is never linked from a browser."""
    if not _flag_relay_secret or not hmac.compare_digest(
        request.headers.get("X-Flag-Relay-Secret", ""), _flag_relay_secret
    ):
        return web.json_response({"ok": False, "reason": "unauthorized"}, status=401)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "reason": "bad_request"}, status=400)

    trivia_db = body.get("source_collection")
    trivia_id = body.get("question_id")
    if not trivia_db or not trivia_id:
        return web.json_response({"ok": False, "reason": "bad_request"}, status=400)

    reasons = [r for r in (body.get("reasons") or []) if r in _FLAG_REASONS]
    if not reasons:
        return web.json_response({"ok": False, "reason": "empty"}, status=400)
    detail = str(body.get("detail") or "").strip()[:500]
    answers = body.get("answers") or []
    answer_hint = answers[0] if answers else None

    result = (
        await _submit_anon_flag(
            trivia_db, trivia_id, body.get("category"), body.get("question_text"), answer_hint,
            reasons, detail, str(body.get("ip_hash") or ""),
            body.get("discord_user_id"), body.get("display_name"),
            guild_id=body.get("guild_id"), app_source=str(body.get("app_source") or "external"),
        )
        if _submit_anon_flag else {"ok": False, "reason": "unavailable"}
    )
    status = 200 if result.get("ok") else 409
    return web.json_response(result, status=status)


# ---------------------------------------------------------------------------
# Question submission (triviasphere.com's web counterpart to Discord's /submit) -- login is
# mandatory (no anonymous path, unlike /flag) since this feeds moderator review and needs a
# reliable submitter identity for the same rate-limit/dedupe logic the Discord modal uses.
# ---------------------------------------------------------------------------

_SUBMIT_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Submit a Question — TriviaSphere</title>
<meta name="theme-color" content="#06080D" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#F8F8F8" media="(prefers-color-scheme: light)">
<link rel="icon" type="image/webp" href="/assets/logo-mark.webp">
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
<style>
  :root {
    color-scheme: light dark;
    --blue:#146DE8; --blue-600:#0A4FB5; --red:#F71A14;
    --bg:#06080D; --bg2:#0E1219; --fg:#F8F8F8; --muted:rgba(248,248,248,.58);
    --card:rgba(248,248,248,.05); --line:rgba(248,248,248,.10);
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
  .wrap { width:100%; max-width:480px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:20px; padding:22px;
    box-shadow:0 12px 32px rgba(0,0,0,.20); }
  .cardhead { display:flex; align-items:center; gap:10px; margin:0 0 4px; }
  .cardhead .mark { width:26px; height:26px; flex:none;
    background:url(/assets/logo-mark.webp) center/contain no-repeat; }
  .card h3 { margin:0; font-size:1.15rem; font-weight:800; }
  .authcard { display:flex; align-items:center; gap:11px; padding:12px 14px; border-radius:14px;
    border:1px solid rgba(61,220,132,.30); background:rgba(61,220,132,.08); margin:14px 0 16px; }
  .authicon { flex:none; width:20px; height:20px; display:flex; align-items:center; justify-content:center;
    color:#3ddc84; font-weight:800; font-size:1rem; }
  .authtext { flex:1; min-width:0; display:flex; flex-direction:column; gap:1px; font-size:.9rem; font-weight:700; }
  .authtext span { font-size:.76rem; font-weight:500; color:var(--muted); }
  .authswitch { flex:none; font-size:.8rem; font-weight:700; color:var(--blue); text-decoration:none; }
  .modalsub { color:var(--muted); font-size:.85rem; margin:0 0 14px; line-height:1.4; }
  .typerow { display:flex; gap:8px; margin-bottom:14px; }
  .typebtn { flex:1; padding:10px; text-align:center; border-radius:12px; border:1px solid var(--line);
    background:rgba(127,127,127,.06); cursor:pointer; font-size:.88rem; font-weight:700; }
  .typebtn.active { border-color:var(--blue); background:rgba(20,109,232,.10); }
  label.fieldlabel { display:block; font-size:.72rem; font-weight:700; text-transform:uppercase;
    letter-spacing:.08em; color:var(--muted); margin:0 0 6px; }
  .field { margin-bottom:14px; }
  input[type=text], textarea { width:100%; padding:12px 13px; font-size:.95rem; border-radius:12px;
    border:1px solid var(--line); background:rgba(127,127,127,.08); color:inherit; resize:vertical;
    font-family:inherit; box-sizing:border-box; }
  textarea { min-height:70px; }
  #fBulk { min-height:140px; }
  .guidetoggle { font-size:.8rem; font-weight:700; color:var(--blue); cursor:pointer; margin:0 0 12px; display:inline-block; }
  .guidebox { display:none; font-size:.82rem; line-height:1.55; color:var(--muted); background:rgba(127,127,127,.06);
    border:1px solid var(--line); border-radius:12px; padding:12px 14px; margin:0 0 14px; }
  .guidebox.open { display:block; }
  .guidebox code { background:rgba(127,127,127,.15); padding:1px 5px; border-radius:4px; font-size:.8rem; }
  .skiplist { text-align:left; margin:8px 0 0; padding-left:18px; font-size:.85rem; font-weight:500; }
  .skiplist li { margin-bottom:4px; }
  .cf-turnstile { margin-bottom:14px; }
  button.primary { width:100%; padding:15px; font-size:1.02rem; font-weight:700;
    border:none; border-radius:14px; color:#fff; cursor:pointer;
    background:linear-gradient(180deg,var(--blue),var(--blue-600)); box-shadow:0 6px 16px rgba(20,109,232,.30); }
  button.primary:disabled { opacity:.5; box-shadow:none; cursor:default; }
  .status { margin-top:12px; font-size:.9rem; min-height:1.2em; }
  .bad { color:var(--red); }
  .done { text-align:center; font-size:1.02rem; font-weight:650; padding:20px 0; color:#3ddc84; }
  .foot { text-align:center; margin-top:16px; color:var(--muted); font-size:.72rem; font-weight:600; opacity:.85; }
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div class="cardhead"><span class="mark" role="img" aria-label="TriviaSphere"></span><h3>Submit a question</h3></div>
    <div class="authcard"><span class="authicon">✓</span>
      <div class="authtext"><b>Submitting as __DISPLAY_NAME__</b><span>Reviewed by a moderator before it's used</span></div>
      <a class="authswitch" href="/logout?next=/submit">Switch</a></div>
    <div class="modalsub" id="modalSub">Multiple-choice needs 1–3 wrong choices; free-text can include up to 3 alternate spellings.</div>
    <div class="typerow">
      <div class="typebtn active" id="typeFree" onclick="setType('free_text')">Free-text</div>
      <div class="typebtn" id="typeMC" onclick="setType('multiple_choice')">Multiple Choice</div>
      <div class="typebtn" id="typeBulk" onclick="setType('bulk')">Bulk</div>
    </div>
    <div id="singleFields">
      <div class="field"><label class="fieldlabel">Category</label><input type="text" id="fCategory" maxlength="40" placeholder="e.g. Science, History, Movies"></div>
      <div class="field"><label class="fieldlabel">Question</label><textarea id="fQuestion" maxlength="300" placeholder="15–300 characters"></textarea></div>
      <div class="field"><label class="fieldlabel" id="lblAnswer">Primary Answer</label><input type="text" id="fAnswer" maxlength="100"></div>
      <div class="field"><label class="fieldlabel" id="lblAlts">Alternate Spellings (optional, up to 3)</label><textarea id="fAlts" maxlength="300" placeholder="One per line or comma-separated"></textarea></div>
    </div>
    <div id="bulkFields" style="display:none">
      <span class="guidetoggle" onclick="toggleGuide()">📋 Format Guide</span>
      <div class="guidebox" id="guideBox">
        One question per line, fields separated by <code>|</code>.<br><br>
        <b>Free-text:</b><br><code>Category | Question | free | Answer</code><br>
        <code>Category | Question | free | Answer | Alt1, Alt2</code><br><br>
        <b>Multiple choice:</b><br><code>Category | Question | mc | CorrectAnswer | Wrong1, Wrong2, Wrong3</code><br><br>
        Type field must be <code>free</code> or <code>mc</code>. MC needs 1–3 wrong choices; free-text alternates are optional. Questions must be 15–300 characters. Blank lines are ignored.<br><br>
        <b>Example:</b><br>
        <code>History | Who was the first US president? | free | George Washington | Washington</code><br>
        <code>Sports | How many players on a basketball team? | mc | 5 | 4, 6, 7</code>
      </div>
      <div class="field"><label class="fieldlabel">Questions (one per line)</label><textarea id="fBulk" maxlength="4000" placeholder="Category | Question | free/mc | Answer | Alternates"></textarea></div>
    </div>
    <div class="cf-turnstile" data-sitekey="__TURNSTILE_SITE_KEY__"></div>
    <button type="button" class="primary" id="submitBtn" onclick="submitQuestion()">Submit</button>
    <div class="status" id="submitStatus"></div>
  </div>
  <div class="foot">TriviaSphere</div>
</div>
<script>
var subType = 'free_text';
function setType(t) {
  subType = t;
  document.getElementById('typeFree').classList.toggle('active', t === 'free_text');
  document.getElementById('typeMC').classList.toggle('active', t === 'multiple_choice');
  document.getElementById('typeBulk').classList.toggle('active', t === 'bulk');
  document.getElementById('singleFields').style.display = t === 'bulk' ? 'none' : 'block';
  document.getElementById('bulkFields').style.display = t === 'bulk' ? 'block' : 'none';
  document.getElementById('modalSub').style.display = t === 'bulk' ? 'none' : 'block';
  document.getElementById('lblAnswer').textContent = t === 'multiple_choice' ? 'Correct Answer' : 'Primary Answer';
  document.getElementById('lblAlts').textContent = t === 'multiple_choice' ? 'Wrong Choices (1–3, comma or new lines)' : 'Alternate Spellings (optional, up to 3)';
}
function toggleGuide() {
  document.getElementById('guideBox').classList.toggle('open');
}
function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
async function submitQuestion() {
  var statusEl = document.getElementById('submitStatus');
  var turnstileInput = document.querySelector('.cf-turnstile input[name="cf-turnstile-response"]');
  var turnstileToken = turnstileInput ? turnstileInput.value : '';
  if (!turnstileToken) { statusEl.textContent = 'Please complete the verification challenge.'; statusEl.className = 'status bad'; return; }
  var btn = document.getElementById('submitBtn');
  btn.disabled = true;
  try {
    var isBulk = subType === 'bulk';
    var url = isBulk ? '/api/submit_questions_bulk' : '/api/submit_question';
    var payload = isBulk
      ? { lines: document.getElementById('fBulk').value, turnstile_token: turnstileToken }
      : {
          sub_type: subType,
          category: document.getElementById('fCategory').value,
          question: document.getElementById('fQuestion').value,
          correct_answer: document.getElementById('fAnswer').value,
          // Sent as the same raw comma/newline-delimited string the Discord modal collects --
          // server-side parsing (_parse_alternates) is shared, so don't pre-split here.
          alternates: document.getElementById('fAlts').value,
          turnstile_token: turnstileToken,
        };
    var r = await fetch(url, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    var data = await r.json();
    if (data.ok && isBulk) {
      var summary = '✅ ' + data.accepted + ' question(s) submitted for review.';
      if (data.skipped && data.skipped.length) {
        summary += '<ul class="skiplist">' + data.skipped.map(function (s) {
          return '<li>' + escapeHtml(s) + '</li>';
        }).join('') + '</ul>';
      }
      document.querySelector('.card').innerHTML = '<div class="done">' + summary + '</div>';
    } else if (data.ok) {
      document.querySelector('.card').innerHTML = '<div class="done">✅ Submitted — a moderator will review it shortly.</div>';
    } else if (data.reason === 'captcha_failed') {
      statusEl.textContent = 'Verification failed — try again.'; statusEl.className = 'status bad';
      if (window.turnstile) { window.turnstile.reset(); }
    } else if (data.reason === 'rate_limited') {
      statusEl.textContent = "You're submitting too fast — try again in a moment."; statusEl.className = 'status bad';
    } else if (data.reason === 'unauthenticated') {
      statusEl.textContent = 'Your session expired — refresh and log in again.'; statusEl.className = 'status bad';
    } else {
      statusEl.textContent = data.reason || 'Could not submit.'; statusEl.className = 'status bad';
    }
  } catch (e) {
    statusEl.textContent = 'Network error — try again.'; statusEl.className = 'status bad';
  } finally {
    btn.disabled = false;
  }
}
</script>
</body>
</html>
"""


async def _verify_turnstile(token, remote_ip):
    """POST to Cloudflare's siteverify endpoint; True only on an explicit 'success'. Any failure
    to verify (network error, malformed response, missing secret) is treated as a rejection --
    there's no safe default that lets a submission through when verification itself failed."""
    if not _turnstile_secret_key or not token:
        return False
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": _turnstile_secret_key, "response": token, "remoteip": remote_ip},
            ) as resp:
                data = await resp.json()
                return bool(data.get("success"))
    except Exception:
        return False


async def handle_submit_page(request):
    session = _session_from_request(request)
    if not session:
        return web.HTTPFound("/login?next=/submit")
    html = (_SUBMIT_PAGE_HTML
            .replace("__DISPLAY_NAME__", html_escape(session["display_name"]))
            .replace("__TURNSTILE_SITE_KEY__", html_escape(_turnstile_site_key)))
    return web.Response(text=html, content_type="text/html")


async def handle_submit_question(request):
    session = _session_from_request(request)
    if not session:
        return web.json_response({"ok": False, "reason": "unauthenticated"}, status=401)

    user_id = session["user_id"]
    now = time.time()
    last = _last_question_submit.get(user_id, 0)
    if now - last < _QUESTION_SUBMIT_MIN_INTERVAL:
        return web.json_response({"ok": False, "reason": "rate_limited"}, status=429)
    _last_question_submit[user_id] = now

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "reason": "bad_request"}, status=400)

    fwd = request.headers.get("X-Forwarded-For", "")
    remote_ip = fwd.split(",")[0].strip() if fwd else (request.remote or "")
    if not await _verify_turnstile(str(body.get("turnstile_token") or ""), remote_ip):
        return web.json_response({"ok": False, "reason": "captcha_failed"}, status=400)

    sub_type = body.get("sub_type") if body.get("sub_type") in ("free_text", "multiple_choice") else "free_text"
    if not _submit_question:
        return web.json_response({"ok": False, "reason": "unavailable"}, status=503)
    doc, err = await _submit_question(
        user_id, session["display_name"], sub_type,
        body.get("category"), body.get("question"), body.get("correct_answer"), body.get("alternates"),
        source="web",
    )
    if err:
        return web.json_response({"ok": False, "reason": err}, status=400)
    return web.json_response({"ok": True})


async def handle_submit_questions_bulk(request):
    session = _session_from_request(request)
    if not session:
        return web.json_response({"ok": False, "reason": "unauthenticated"}, status=401)

    user_id = session["user_id"]
    now = time.time()
    # Shares the single-submit cooldown clock -- a bulk paste and a single submit are the same
    # kind of action for rate-limiting purposes, and the real per-line anti-abuse (24h cap,
    # 30-day dedupe) lives in submit_bulk_questions_for_review regardless of which endpoint hit it.
    last = _last_question_submit.get(user_id, 0)
    if now - last < _QUESTION_SUBMIT_MIN_INTERVAL:
        return web.json_response({"ok": False, "reason": "rate_limited"}, status=429)
    _last_question_submit[user_id] = now

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "reason": "bad_request"}, status=400)

    fwd = request.headers.get("X-Forwarded-For", "")
    remote_ip = fwd.split(",")[0].strip() if fwd else (request.remote or "")
    if not await _verify_turnstile(str(body.get("turnstile_token") or ""), remote_ip):
        return web.json_response({"ok": False, "reason": "captcha_failed"}, status=400)

    if not _submit_bulk_questions:
        return web.json_response({"ok": False, "reason": "unavailable"}, status=503)
    accepted, skipped = await _submit_bulk_questions(
        user_id, session["display_name"], str(body.get("lines") or ""), source="web",
    )
    return web.json_response({"ok": True, "accepted": len(accepted), "skipped": skipped})


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

# Play-button app mark + okra chef mascot, inlined as WebP data URIs (small, decorative, and
# only used here) — referenced via CSS vars --play / --okra.
_PLAY_LOGO = "data:image/webp;base64,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"
_OKRA_LOGO = "data:image/webp;base64,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"

# TriviaSphere header/mark logos are hosted (not inlined) so the browser can cache them
# across page loads; see _ensure_companion_assets() and the /assets/* routes below.
_COMPANION_ASSET_FILES = ["companion_logo_header.webp", "companion_logo_mark.webp"]
_COMPANION_ASSETS_S3_PREFIX = "private_assets/"
_COMPANION_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "private-assets")


def _companion_asset_path(filename):
    return os.path.join(_COMPANION_ASSETS_DIR, filename)


def _ensure_companion_assets():
    """Download any companion logo files missing from local disk from S3 (same bucket/prefix
    convention as discordbot.py's ensure_game_assets() — not duplicated here to avoid importing
    discordbot from this module). Runs once at import, before any route can serve them."""
    os.makedirs(_COMPANION_ASSETS_DIR, exist_ok=True)
    missing = [f for f in _COMPANION_ASSET_FILES if not os.path.exists(_companion_asset_path(f))]
    if not missing:
        return
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_REGION", "us-east-2"),
    )
    for filename in missing:
        try:
            s3.download_file("triviabotwebsite", _COMPANION_ASSETS_S3_PREFIX + filename,
                              _companion_asset_path(filename))
            print(f"✅ Downloaded missing companion asset from S3: {filename}")
        except Exception as e:
            print(f"❌ Failed to download companion asset '{filename}' from S3: {e}")


_ensure_companion_assets()


_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>TriviaSphere</title>
<meta name="theme-color" content="#06080D" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#F8F8F8" media="(prefers-color-scheme: light)">
<link rel="icon" type="image/webp" href="/assets/logo-mark.webp">
<style>
  :root {
    color-scheme: light dark;
    --blue:#146DE8; --blue-600:#0A4FB5; --red:#F71A14;
    --bg:#06080D; --bg2:#0E1219; --fg:#F8F8F8; --muted:rgba(248,248,248,.58);
    --card:rgba(248,248,248,.05); --line:rgba(248,248,248,.10);
    --play:url(__PLAY_LOGO__); --okra:url(__OKRA_LOGO__);
    --header-logo:url(/assets/logo-header.webp); --footer-logo:url(/assets/logo-mark.webp);
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
  .wrap { width:100%; max-width:520px; position:relative; }
  .brand { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; padding-right:44px; }
  .icon-btn { position:absolute; top:0; right:0; width:34px; height:34px; flex:none;
    display:flex; align-items:center; justify-content:center; border:1px solid var(--line);
    border-radius:10px; background:rgba(127,127,127,.10); color:var(--muted); font-size:1rem;
    text-decoration:none; cursor:pointer; }
  .brandhead { display:flex; align-items:center; min-width:0; }
  .brandlogo { height:96px; width:96px; flex:none;
    background:var(--header-logo) left center/contain no-repeat; }
  .simple-toggle { display:flex; align-items:center; gap:8px; flex:none; cursor:pointer; }
  .simple-toggle span.lbl { font-size:.72rem; font-weight:700; letter-spacing:.02em; color:var(--muted); white-space:nowrap; }
  .game-toggle .lbl { transition:color .15s; }
  .game-toggle .lbl.active { color:var(--fg); }
  .switch { position:relative; display:inline-block; width:40px; height:23px; flex:none; }
  .switch input { position:absolute; inset:0; opacity:0; margin:0; cursor:pointer; }
  .switch .track { position:absolute; inset:0; border-radius:999px; background:rgba(255,180,58,.55);
    border:1px solid rgba(255,180,58,.7); transition:background-color .15s, border-color .15s; }
  .switch .thumb { position:absolute; top:2px; left:2px; width:17px; height:17px; border-radius:50%;
    background:#fff; box-shadow:0 1px 3px rgba(0,0,0,.35); transition:transform .15s; }
  .switch input:checked ~ .track { background:var(--blue); border-color:var(--blue); }
  .switch input:checked ~ .track .thumb { transform:translateX(17px); }
  .switch input:focus-visible ~ .track { box-shadow:0 0 0 3px rgba(20,109,232,.30); }
  .game-tabs { display:flex; gap:4px; max-width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch;
    scrollbar-width:none; background:rgba(127,127,127,.10); border:1px solid var(--line); border-radius:12px; padding:3px; }
  .game-tabs::-webkit-scrollbar { display:none; }
  .tab-btn { flex:none; border:none; background:transparent; color:var(--muted); cursor:pointer;
    font-size:.7rem; font-weight:700; letter-spacing:.01em; padding:7px 10px; border-radius:9px;
    white-space:nowrap; transition:background-color .15s, color .15s; }
  .tab-btn.active { background:var(--blue); color:#fff; }
  .sub { color:var(--muted); font-size:.86rem; margin:13px 2px 20px; line-height:1.45; }
  .card { position:relative; background:var(--card); border:1px solid var(--line); border-radius:20px; padding:22px;
    box-shadow:0 12px 32px rgba(0,0,0,.20); }
  .flagbar { display:block; width:100%; margin-top:14px; padding:15px; border-radius:14px;
    border:1px solid rgba(247,26,20,.4); background:rgba(247,26,20,.14); color:var(--red);
    font-size:.95rem; font-weight:700; text-align:center; cursor:pointer;
    transition:background-color .12s, border-color .12s, opacity .12s; }
  .flagbar:active { transform:scale(.99); }
  .flagbar.flagged, .flagbar:disabled { opacity:.6; cursor:default; }
  .modal-backdrop { position:fixed; inset:0; background:rgba(0,0,0,.55); display:flex; align-items:flex-end;
    justify-content:center; z-index:50; padding:0; }
  @media (min-width:560px) { .modal-backdrop { align-items:center; padding:16px; } }
  .modal { width:100%; max-width:480px; background:var(--bg2); border:1px solid var(--line);
    border-radius:20px 20px 0 0; padding:22px; padding-bottom:calc(22px + env(safe-area-inset-bottom));
    box-shadow:0 -8px 32px rgba(0,0,0,.35); max-height:85vh; overflow-y:auto; }
  @media (min-width:560px) { .modal { border-radius:20px; } }
  .modal h3 { margin:0 0 4px; font-size:1.1rem; font-weight:800; }
  .modal .modalsub { color:var(--muted); font-size:.82rem; margin:0 0 16px; line-height:1.4; }
  .modalqctx { margin:10px 0 16px; padding:13px 14px; border-radius:12px; border:1px solid var(--line);
    background:rgba(127,127,127,.06); }
  .modalqctx .modalcat { font-size:.68rem; font-weight:700; text-transform:uppercase; letter-spacing:.1em;
    color:var(--muted); margin-bottom:4px; }
  .modalqctx .modalq { font-size:.95rem; font-weight:700; line-height:1.4; }
  .modalqctx .modalansdivider { height:1px; background:var(--line); margin:14px 0 12px; }
  .modalqctx .modalanslabel { font-size:.68rem; font-weight:700; text-transform:uppercase; letter-spacing:.1em;
    color:var(--muted); margin-bottom:3px; }
  .modalqctx .modalansval { font-size:1rem; font-weight:800; color:#3ddc84; line-height:1.4; }
  .reasons { display:flex; flex-direction:column; gap:8px; margin-bottom:14px; }
  .reasonrow { display:flex; align-items:center; gap:10px; padding:11px 13px; border-radius:12px;
    border:1px solid var(--line); background:rgba(127,127,127,.06); cursor:pointer; font-size:.95rem;
    transition:border-color .12s, background-color .12s; }
  .reasonrow:has(input:checked) { border-color:var(--blue); background:rgba(20,109,232,.10); }
  .reasonrow input { margin:0; }
  #flagDetail { width:100%; padding:13px 14px; font-size:.95rem; border-radius:12px;
    border:1px solid var(--line); background:rgba(127,127,127,.08); color:inherit; resize:vertical;
    min-height:70px; font-family:inherit; margin-bottom:14px; box-sizing:border-box; }
  .modalbtns { display:flex; gap:10px; }
  .modalbtns button { flex:1; padding:13px; border-radius:12px; font-size:.95rem; font-weight:700;
    cursor:pointer; }
  .modalbtns .cancel { background:transparent; color:inherit; border:1px solid var(--line); }
  .modalbtns .submit { background:linear-gradient(180deg,var(--blue),var(--blue-600)); color:#fff; border:none; }
  .modalbtns .submit:disabled { opacity:.5; cursor:default; }
  .modalstatus { margin-top:10px; font-size:.86rem; min-height:1.2em; }
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
  .actionrow { display:flex; justify-content:flex-end; align-items:center; gap:10px; margin-top:14px; }
  .actionrow button.primary { width:auto; margin-top:0; padding:11px 20px; font-size:.95rem; }
  .actionrow .flagbar { display:inline-flex; align-items:center; width:auto; margin-top:0; padding:11px 16px; font-size:.85rem; white-space:nowrap; }
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
  .sbnote { font-size:.78rem; color:var(--muted); margin-top:8px; text-align:center; }
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
  __TV_TAB__
  <header class="brand">
    <div class="brandhead">
      <div class="brandlogo" role="img" aria-label="TriviaSphere logo"></div>
    </div>
    <div class="game-tabs" id="gameTabs">
      <button type="button" class="tab-btn" data-game="main" onclick="onGameSelect('main')">Trivia &amp; Games</button>
      <button type="button" class="tab-btn" data-game="simply" onclick="onGameSelect('simply')">Simply Trivia</button>
      <button type="button" class="tab-btn" data-game="arena" onclick="onGameSelect('arena')">Mini-Game Arena</button>
    </div>
  </header>
  <div id="subtext" class="sub">Answer live from your phone or computer — private, timed, and scored right alongside everyone in the channel.</div>
  <div id="app" class="card"><div class="idle">Loading…</div></div>
  <div id="me" class="me"></div>
  <footer class="foot"><span class="footlogo" role="img" aria-label="TriviaSphere"></span></footer>
</div>
<script>
let es = null, countdownTimer = null, endsAt = 0, currentKey = null, answeredKey = null, answeredValue = null, oneGuess = false;
let simpleMode = true, lastState = null, flaggedKey = null, flagSubmitting = false;
const GAMES = ['main', 'simply', 'arena'];
let currentGame = GAMES.includes(localStorage.getItem('okra_game')) ? localStorage.getItem('okra_game') : 'main';
var FLAG_REASONS = [
  ['category', 'Category'], ['question', 'Question'], ['answer', 'Answer'],
  ['too_niche', 'Too Niche'], ['other', 'Other'],
];
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
  var note = state.scoreboard_note
    ? '<div class="sbnote">' + esc(state.scoreboard_note) + '</div>'
    : '';
  return '<div class="sbtitle">Scoreboard</div><div class="sb">' + sb.map(function (r) {
    return '<div class="sbrow">' +
      '<span class="sbrank">' + esc(r.rank || '') + '</span>' +
      '<span class="sbname">' + esc(r.name || '') + '</span>' +
      (r.lightning ? '<span class="sblight">⚡' + r.lightning + '</span>' : '') +
      '<span class="sbscore">' + esc(r.score || '') + '</span>' +
      (r.delta ? '<span class="sbdelta">' + esc(r.delta) + '</span>' : '') +
      (r.via_activity ? '<span class="sbapp" title="Answered via the Activity">🧪</span>' :
        r.via_companion ? '<span class="sbapp" title="Answered via the app">🌐</span>' : '') +
    '</div>';
  }).join('') + note + '</div>';
}

function puzzleHtml(state) {
  return state.puzzle_text ? '<div class="puzzle">' + esc(state.puzzle_text) + '</div>' : '';
}

function flagHtml(state) {
  var isFlagged = flaggedKey === state.question_key;
  return '<button type="button" class="flagbar' + (isFlagged ? ' flagged' : '') + '" ' +
    (isFlagged ? 'disabled ' : '') + 'onclick="openFlagModal()" ' +
    'aria-label="' + (isFlagged ? 'Question flagged' : 'Flag this question') + '">' +
    (isFlagged ? '🚩 Flagged' : '🚩 Flag') + '</button>';
}

function promptHtml(state) {
  // Post-round-menu / WoF mini-game picker (main tab only -- Simply Trivia has no such menu,
  // and the arena tab renders prompts itself via renderArena/arenaPromptHtml instead).
  var p = state.prompt;
  if (!p) return '';
  var body = p.you_can_act
    ? '<input id="actionInput" type="text" autocomplete="off" autocapitalize="off" ' +
      'placeholder="Type your choice…" onkeydown="if(event.key===\\'Enter\\')submitActionInput()">' +
      '<button class="primary" onclick="submitActionInput()">Submit</button>' +
      '<div id="actionStatus" class="status"></div>'
    : '<div class="idle" style="padding:6px 0 0">Waiting for ' +
      esc((p.allowed_names || []).join(' / ') || 'the round winner') + ' to choose…</div>';
  return '<div class="modalqctx" style="margin-top:16px">' +
    '<div class="modalcat">Mini-Game Menu</div>' +
    '<div class="modalq" style="white-space:pre-wrap">' + esc(p.prompt_text || '') + '</div>' +
    '</div>' + body;
}

function submitActionInput() {
  var el = document.getElementById('actionInput');
  var text = el ? el.value.trim() : '';
  if (!text) return;
  submitAction(text, 'actionStatus');
  if (el) el.value = '';
}

function submitAction(text, statusElId) {
  fetch('/api/action', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text: text, game: currentGame})
  }).then(function (r) { return r.json().then(function (j) { return {ok: r.ok, body: j}; }); })
    .then(function (res) {
      var el = statusElId && document.getElementById(statusElId);
      if (!el) return;
      if (res.body.ok) { el.textContent = 'Sent ✓'; el.className = 'status ok'; }
      else { el.textContent = res.body.reason === 'no_active_prompt' ? 'That closed — refresh.' :
        res.body.reason === 'not_allowed' ? 'Only the round winner can choose.' : 'Could not send, try again.';
        el.className = 'status bad'; }
    })
    .catch(function () {
      var el = statusElId && document.getElementById(statusElId);
      if (el) { el.textContent = 'Network error'; el.className = 'status bad'; }
    });
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

function syncGameTabs(game) {
  var tabs = document.getElementById('gameTabs');
  if (!tabs) return;
  Array.prototype.forEach.call(tabs.querySelectorAll('.tab-btn'), function (btn) {
    btn.classList.toggle('active', btn.getAttribute('data-game') === game);
  });
}

function onGameSelect(game) {
  if (game === currentGame) return;
  currentGame = game;
  localStorage.setItem('okra_game', currentGame);
  syncGameTabs(currentGame);
  loadGame(currentGame);
}

function onTvView() {
  location.href = '/?view=tv&game=' + encodeURIComponent(currentGame);
}

function render(state) {
  const app = document.getElementById('app');
  const sub = document.getElementById('subtext');
  lastState = state;
  if (state.authenticated === false) {
    if (sub) sub.style.display = '';
    app.innerHTML = '<div class="hero"><div class="mascot"></div>' +
      '<h2>Ready to play?</h2>' +
      '<p>Log in with Discord to answer live questions privately from your phone or computer.</p>' +
      '<a class="login" href="/login">' + DISCORD_SVG + 'Login with Discord</a></div>';
    return;
  }
  if (sub) sub.style.display = 'none';
  if (state.display_name) document.getElementById('me').innerHTML = 'Playing as ' + esc(state.display_name) +
    ' · <a class="logout" href="/logout">Log out</a>';

  if (currentGame === 'arena') { renderArena(state); return; }

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
      ? resultBanner + answerLine + '<div class="actionrow">' + flagHtml(state) + '</div>'
      : '<div class="cat">' + esc(state.category || '') + '</div>' +
        (state.question ? '<div class="q">' + esc(state.question) + '</div>' : '') +
        imgHtml(state) +
        resultBanner + answerLine + '<div class="actionrow">' + flagHtml(state) + '</div>' + mine +
        scoreboardHtml(state) + legendHtml(state) + roundHtml(state);
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    return;
  }

  if (state.phase !== 'open') {
    app.innerHTML = '<div class="idle"><div class="mascot sm"></div>' +
      '<span class="big">No live question right now</span>' +
      'The chef is prepping the next one — hang tight. ⏳</div>' + promptHtml(state);
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    return;
  }

  // open
  const isNew = state.question_key !== currentKey;
  if (isNew) { answeredValue = null; flaggedKey = null; }
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
        'placeholder="Type a letter or the answer…" onpaste="return false" onkeydown="if(event.key===\\'Enter\\')submitText()">';
    } else {
      inputHtml = '<input id="ans" type="text" autocomplete="off" autocapitalize="off" ' +
        'placeholder="Type your answer…" onpaste="return false" onkeydown="if(event.key===\\'Enter\\')submitText()">';
    }
    // Multiple answers are allowed (like typing in Discord): note the last one, keep inputs open.
    if (prior) inputHtml = '<div class="status ok">✓ Submitted: ' + esc(prior) +
      ' — you can submit again</div>' + inputHtml;
  }

  const actionRow = '<div class="actionrow">' +
    (state.already_answered ? '' : '<button class="primary" onclick="submitText()">Submit</button>') +
    flagHtml(state) + '</div>';

  const timerHtml = state.ends_at ? '<span id="timer" class="timer">--</span>' : '';
  app.innerHTML = simpleMode
    ? inputHtml + actionRow + '<div id="status" class="status"></div>' + legendHtml(state)
    : '<div class="qhead"><span class="cat">' + esc(state.category || '') + '</span>' +
        timerHtml + '</div>' +
        (state.question ? '<div class="q">' + esc(state.question) + '</div>' : '') +
        imgHtml(state) + puzzleHtml(state) +
        (state.warning ? '<div class="warn">' + esc(state.warning) + '</div>' : '') + inputHtml +
        actionRow + '<div id="status" class="status"></div>' +
        scoreboardHtml(state) + legendHtml(state) + roundHtml(state);

  if (isNew && !state.already_answered) { const i = document.getElementById('ans'); if (i) i.focus(); }
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
  if (state.ends_at) {
    fmtRemaining();
    countdownTimer = setInterval(fmtRemaining, 250);
  }
}

function renderArena(state) {
  const app = document.getElementById('app');
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }

  if (state.phase === 'idle' || !state.phase) {
    app.innerHTML = '<div class="idle"><div class="mascot sm"></div>' +
      '<span class="big">No mini-game running</span>' +
      'Start one in the Mini-Game Arena channel with /arena. ⏳</div>';
    return;
  }

  const gameName = state.game_name ? esc(state.game_name.toUpperCase()) : 'Mini-Game';
  const p = state.prompt || {};

  if (state.phase === 'spectating' || !p.you_can_act) {
    app.innerHTML = '<div class="idle"><div class="mascot sm"></div>' +
      '<span class="big">🎮 ' + gameName + '</span>' +
      'Waiting for ' + esc((p.allowed_names || []).join(' / ') || 'the player') + ' to answer…</div>';
    return;
  }

  // phase === 'prompt' and this viewer is the one who can act
  app.innerHTML = '<div class="modalqctx">' +
    '<div class="modalcat">🎮 ' + gameName + '</div>' +
    '<div class="modalq" style="white-space:pre-wrap">' + esc(p.prompt_text || 'Your turn — type your answer.') + '</div>' +
    '</div>' +
    '<input id="arenaInput" type="text" autocomplete="off" autocapitalize="off" ' +
    'placeholder="Type your answer…" onkeydown="if(event.key===\\'Enter\\')submitArenaInput()">' +
    '<button class="primary" onclick="submitArenaInput()">Submit</button>' +
    '<div id="arenaStatus" class="status"></div>';
  const i = document.getElementById('arenaInput'); if (i) i.focus();
}

function submitArenaInput() {
  var el = document.getElementById('arenaInput');
  var text = el ? el.value.trim() : '';
  if (!text) return;
  submitAction(text, 'arenaStatus');
  if (el) el.value = '';
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
      body: JSON.stringify({answer: answer, game: currentGame}),
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
    } else if (data.reason === 'too_many_attempts') {
      setStatus("You've hit the max number of guesses for this question.", 'bad');
    } else {
      setStatus('Could not submit (' + (data.reason || 'error') + ').', 'bad');
    }
  } catch (e) { setStatus('Network error — try again.', 'bad'); }
}
function submitText() {
  const inp = document.getElementById('ans');
  if (inp && inp.value.trim()) submit(inp.value.trim());
}

function openFlagModal() {
  if (flagSubmitting || document.getElementById('flagBackdrop')) return;
  const state = lastState || {};
  // Never show the answer while the question is still open (or during a blind round, where it's
  // intentionally withheld even after reveal) -- otherwise flagging would let a player read the
  // answer before answering it.
  const revealed = state.phase === 'revealed' && !state.blind;
  const qctx = '<div class="modalqctx">' +
    '<div class="modalcat">' + esc(state.category || '') + '</div>' +
    (state.question ? '<div class="modalq">' + esc(state.question) + '</div>' : '') +
    (revealed && state.correct_answer ? '<div class="modalansdivider"></div><div class="modalanslabel">Answer</div><div class="modalansval">' + esc(state.correct_answer) + '</div>' : '') +
  '</div>';
  const backdrop = document.createElement('div');
  backdrop.id = 'flagBackdrop';
  backdrop.className = 'modal-backdrop';
  backdrop.onclick = function (e) { if (e.target === backdrop) closeFlagModal(); };
  backdrop.innerHTML = '<div class="modal">' +
    '<h3>Flag Question</h3>' +
    qctx +
    '<div class="modalsub">What\\'s wrong with this question? Select all that apply.</div>' +
    '<div class="reasons">' + FLAG_REASONS.map(function (r) {
      return '<label class="reasonrow"><input type="checkbox" value="' + r[0] + '">' + esc(r[1]) + '</label>';
    }).join('') + '</div>' +
    '<textarea id="flagDetail" maxlength="500" placeholder="Provide more detail (optional — recommended if you selected \\'Other\\')"></textarea>' +
    '<div class="modalbtns">' +
      '<button type="button" class="cancel" onclick="closeFlagModal()">Cancel</button>' +
      '<button type="button" class="submit" id="flagSubmitBtn" onclick="submitFlag()">Submit</button>' +
    '</div>' +
    '<div class="modalstatus" id="flagModalStatus"></div>' +
  '</div>';
  document.body.appendChild(backdrop);
}

function closeFlagModal() {
  const el = document.getElementById('flagBackdrop');
  if (el) el.remove();
}

async function submitFlag() {
  const backdrop = document.getElementById('flagBackdrop');
  if (!backdrop) return;
  const reasons = Array.prototype.slice.call(backdrop.querySelectorAll('.reasons input:checked'))
    .map(function (i) { return i.value; });
  const statusEl = document.getElementById('flagModalStatus');
  if (!reasons.length) {
    if (statusEl) { statusEl.textContent = 'Select at least one reason.'; statusEl.className = 'modalstatus bad'; }
    return;
  }
  const detail = (document.getElementById('flagDetail') || {}).value || '';
  flagSubmitting = true;
  const btn = document.getElementById('flagSubmitBtn'); if (btn) btn.disabled = true;
  try {
    const r = await fetch('/api/flag', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({reasons: reasons, detail: detail, game: currentGame}),
    });
    const data = await r.json();
    if (data.ok) {
      flaggedKey = currentKey;
      closeFlagModal();
      if (lastState) render(lastState);
    } else if (data.reason === 'already_flagged') {
      flaggedKey = currentKey;
      closeFlagModal();
      if (lastState) render(lastState);
    } else if (data.reason === 'rate_limited') {
      if (statusEl) { statusEl.textContent = "You've flagged too many questions today."; statusEl.className = 'modalstatus bad'; }
    } else if (data.reason === 'no_question') {
      if (statusEl) { statusEl.textContent = 'No live question to flag right now.'; statusEl.className = 'modalstatus bad'; }
    } else {
      if (statusEl) { statusEl.textContent = 'Could not submit (' + (data.reason || 'error') + ').'; statusEl.className = 'modalstatus bad'; }
    }
  } catch (e) {
    if (statusEl) { statusEl.textContent = 'Network error — try again.'; statusEl.className = 'modalstatus bad'; }
  } finally {
    flagSubmitting = false;
    if (btn) btn.disabled = false;
  }
}

function connect() {
  es = new EventSource('/api/stream?game=' + encodeURIComponent(currentGame));
  es.onmessage = function (ev) { try { render(JSON.parse(ev.data)); } catch (e) {} };
  es.onerror = function () { /* EventSource auto-reconnects */ };
}

function loadGame(game) {
  currentGame = game;
  if (es) { es.close(); es = null; }
  currentKey = null; answeredKey = null; answeredValue = null; endsAt = 0; flaggedKey = null;
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
  fetch('/api/current?game=' + encodeURIComponent(game)).then(function (r) { return r.json(); })
    .then(function (s) { render(s); if (s.authenticated !== false) connect(); })
    .catch(function () { render({phase: 'idle', authenticated: true}); connect(); });
}

syncGameTabs(currentGame);
loadGame(currentGame);
</script>
</body>
</html>
"""
_INDEX_HTML = _INDEX_HTML.replace("__PLAY_LOGO__", _PLAY_LOGO).replace("__OKRA_LOGO__", _OKRA_LOGO)

_COMING_SOON_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>TriviaSphere — Coming Soon</title>
<meta name="theme-color" content="#06080D" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#F8F8F8" media="(prefers-color-scheme: light)">
<link rel="icon" type="image/webp" href="/assets/logo-mark.webp">
<style>
  :root {
    color-scheme: light dark;
    --blue:#146DE8; --bg:#06080D; --bg2:#0E1219; --fg:#F8F8F8; --muted:rgba(248,248,248,.58);
    --card:rgba(248,248,248,.05); --line:rgba(248,248,248,.10);
  }
  @media (prefers-color-scheme: light) {
    :root { --bg:#F8F8F8; --bg2:#FCFCFC; --fg:#06080D; --muted:rgba(6,8,13,.55);
            --card:#ffffff; --line:rgba(6,8,13,.10); }
  }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; color:var(--fg);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,sans-serif;
    background:radial-gradient(1100px 560px at 50% -12%, rgba(20,109,232,.14), transparent 60%),
               linear-gradient(180deg,var(--bg),var(--bg2)); background-attachment:fixed;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    padding:26px 16px calc(26px + env(safe-area-inset-bottom)); }
  .wrap { width:100%; max-width:420px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:20px; padding:30px 22px;
    box-shadow:0 12px 32px rgba(0,0,0,.20); text-align:center; }
  .mark { width:44px; height:44px; margin:0 auto 16px;
    background:url(/assets/logo-mark.webp) center/contain no-repeat; }
  .card h1 { margin:0 0 8px; font-size:1.3rem; font-weight:800; }
  .card p { margin:0; color:var(--muted); font-size:.92rem; line-height:1.5; }
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div class="mark" role="img" aria-label="TriviaSphere"></div>
    <h1>Coming Soon</h1>
    <p>The TriviaSphere companion app isn't live yet — check back soon!</p>
  </div>
</div>
</body>
</html>
"""


async def handle_index(request):
    if not COMPANION_APP_ENABLED:
        return web.Response(text=_COMING_SOON_HTML, content_type="text/html")
    # Discord's Activity URL Mappings target a bare hostname with no path, so the iframe's
    # document always loads "/" -- `frame_id` is the query param Discord appends to that iframe's
    # src on every platform (and the SDK itself depends on it), so it's what tells us this hit is
    # the Activity rather than a normal companion-app page load.
    if activity_web.ENABLED and request.query.get("frame_id"):
        return activity_web.render_activity_page(request)
    # Read-only landscape display for a TV -- same "/" route, switched by a query param rather
    # than a separate path, so there's only ever one URL to share (see tv_view.py's docstring).
    if tv_view.ENABLED and request.query.get("view") == "tv":
        return tv_view.render_tv_page(request)
    tv_tab = '<button type="button" class="icon-btn" onclick="onTvView()" aria-label="TV View" title="TV View">📺</button>' if tv_view.ENABLED else ""
    return web.Response(text=_INDEX_HTML.replace("__TV_TAB__", tv_tab), content_type="text/html")


async def handle_health(request):
    return web.Response(text="ok")


def _companion_asset_response(filename):
    resp = web.FileResponse(_companion_asset_path(filename))
    resp.headers["Content-Type"] = "image/webp"
    resp.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return resp


async def handle_logo_header(request):
    return _companion_asset_response("companion_logo_header.webp")


async def handle_logo_mark(request):
    return _companion_asset_response("companion_logo_mark.webp")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

async def start_companion_web(*, resolve_member, get_state, submit_answer, submit_action=None, reveal_extra=None, submit_flag=None, submit_anon_flag=None, get_flag_reveal_context=None, submit_question=None, submit_bulk_questions=None):
    """Bind the aiohttp server to $PORT and start serving. Called from the bot's main()
    before the long-running gather so Heroku sees the port bound promptly (avoids R10)."""
    global _resolve_member, _get_state, _submit_answer, _submit_action, _reveal_extra, _submit_flag, _submit_anon_flag
    global _get_flag_reveal_context, _submit_question, _submit_bulk_questions
    global _session_secret, _oauth_client_id, _oauth_client_secret, _base_url, _flag_relay_secret
    global _turnstile_site_key, _turnstile_secret_key, _discord_invite_url

    _resolve_member = resolve_member
    _get_state = get_state
    _submit_answer = submit_answer
    _submit_action = submit_action
    _reveal_extra = reveal_extra
    _submit_flag = submit_flag
    _submit_anon_flag = submit_anon_flag
    _get_flag_reveal_context = get_flag_reveal_context
    _submit_question = submit_question
    _submit_bulk_questions = submit_bulk_questions

    secret = os.getenv("COMPANION_SESSION_SECRET")
    if not secret:
        secret = base64.urlsafe_b64encode(os.urandom(32)).decode()
        print("⚠️  COMPANION_SESSION_SECRET not set — using an ephemeral secret "
              "(sessions won't survive a restart).")
    _session_secret = secret.encode()
    _oauth_client_id = os.getenv("DISCORD_OAUTH_CLIENT_ID", "")
    _oauth_client_secret = os.getenv("DISCORD_OAUTH_CLIENT_SECRET", "")
    _base_url = os.getenv("COMPANION_BASE_URL", "")
    _flag_relay_secret = os.getenv("FLAG_RELAY_SECRET", "")
    if not _flag_relay_secret:
        print("⚠️  FLAG_RELAY_SECRET not set — /internal/flag_relay will reject all requests.")
    _turnstile_site_key = os.getenv("TURNSTILE_SITE_KEY", "")
    _turnstile_secret_key = os.getenv("TURNSTILE_SECRET_KEY", "")
    if not _turnstile_secret_key:
        print("⚠️  TURNSTILE_SECRET_KEY not set — /api/submit_question will reject all requests.")
    _discord_invite_url = os.getenv("DISCORD_INVITE_URL", "")

    if _ACTIVITY_ENABLED:
        activity_web.init(
            sign=_sign, unsign=_unsign,
            resolve_member=resolve_member, get_state=get_state, reveal_extra=reveal_extra,
            session_from_request=_session_from_request,
            session_ttl=_SESSION_TTL,
            oauth_client_id=_oauth_client_id, oauth_client_secret=_oauth_client_secret,
            discord_invite_url=_discord_invite_url,
            get_seq=lambda game: _seq.get(game, 0),
            get_last_published=lambda game: _last_published.get(game),
        )

    if tv_view.ENABLED:
        tv_view.init(session_from_request=_session_from_request)

    asyncio.create_task(_rate_limit_pruner())

    app = web.Application(middlewares=[_https_enforcement_middleware])
    routes = [
        web.get("/", handle_index),
        web.get("/healthz", handle_health),
        web.get("/assets/logo-header.webp", handle_logo_header),
        web.get("/assets/logo-mark.webp", handle_logo_mark),
        web.get("/login", handle_login),
        web.get("/logout", handle_logout),
        web.get("/auth/callback", handle_callback),
        web.get("/flag", handle_flag_page),
        web.post("/api/flag_anon", handle_flag_anon),
        web.post("/internal/flag_relay", handle_flag_relay),
        web.get("/submit", handle_submit_page),
        web.post("/api/submit_question", handle_submit_question),
        web.post("/api/submit_questions_bulk", handle_submit_questions_bulk),
    ]
    if COMPANION_APP_ENABLED:
        routes.extend([
            web.get("/api/current", handle_current),
            web.get("/api/stream", handle_stream),
            web.post("/api/answer", handle_answer),
            web.post("/api/action", handle_action),
            web.post("/api/flag", handle_flag),
        ])
        if _ACTIVITY_ENABLED:
            routes.extend(activity_web.activity_routes())
    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    if not _base_url:
        _base_url = f"http://localhost:{port}"
    print(f"🌐 Companion web app listening on :{port} (base_url={_base_url})")
    return runner
