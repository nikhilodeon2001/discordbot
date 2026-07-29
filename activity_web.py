"""Discord Embedded App SDK Activity panel -- STAGING PROOF OF CONCEPT.

Docks the live trivia question, image, answer reveal, scoreboard, mode legend, and a silent
answer input beside the real Discord text chat, inside a voice channel. Reuses the same state
pipeline as companion_web.py (build_companion_state / build_companion_reveal_state /
publish_state) -- the only thing that changes is the auth transport, since the Activity iframe
runs at <client_id>.discordsays.com, a third-party context where the phone companion's
SameSite=Lax session cookie will not arrive.

Dependency direction matches companion_web.py's house style: this module imports nothing from
companion_web (avoids a circular import); companion_web imports this module and hands it
everything it needs -- the sign/unsign helpers, the bot callbacks, and a couple of small state
accessors -- via init(), called once from start_companion_web.

The render logic in _ACTIVITY_HTML below is a deliberate COPY of the relevant pieces of
companion_web._INDEX_HTML's client JS (the "detail" / non-simpleMode branch only), not a shared
import. _INDEX_HTML has no test coverage and serves play.triviasphere.com directly; editing it to
extract shared partials risks a quote-escaping slip breaking prod for the sake of a POC. If this
graduates past POC, promote the copied builders to a shared constant instead.
"""
import asyncio
import ipaddress
import os
import socket
import time
import urllib.parse

import aiohttp
from aiohttp import web

# ---------------------------------------------------------------------------
# Injected state (set by init(), called from companion_web.start_companion_web)
# ---------------------------------------------------------------------------

ENABLED = False

_sign = None                    # callable(payload:dict) -> str
_unsign = None                  # callable(token:str) -> dict | None
_resolve_member = None          # callable(user_id:int) -> display_name:str | None
_get_state = None               # callable(user_id:int|None, game:str) -> dict
_reveal_extra = None            # callable(user_id, game) -> {"my_answers":[...], "result":...}
_session_from_request = None    # callable(request) -> session dict | None (companion_web's, reused)
_session_ttl = 12 * 3600
_oauth_client_id = ""
_oauth_client_secret = ""
_discord_invite_url = ""
_get_seq = None                 # callable(game) -> int
_get_last_published = None      # callable(game) -> dict | None

_IMAGE_TOKEN_TTL = 6 * 3600
_IMAGE_MAX_BYTES = 8 * 1024 * 1024
_IMAGE_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp", "image/avif"}
_image_semaphore = None  # created lazily, bound to the running loop

# Per-IP debounce on the token-exchange endpoint (it calls out to discord.com twice per hit).
_last_activity_auth = {}
_ACTIVITY_AUTH_MIN_INTERVAL = 1.0
_RATE_LIMIT_PRUNE_INTERVAL = 900
_RATE_LIMIT_ENTRY_MAX_AGE = 300


def init(*, sign, unsign, resolve_member, get_state, reveal_extra, session_from_request,
         session_ttl, oauth_client_id, oauth_client_secret, discord_invite_url,
         get_seq, get_last_published):
    global ENABLED, _sign, _unsign, _resolve_member, _get_state, _reveal_extra
    global _session_from_request, _session_ttl
    global _oauth_client_id, _oauth_client_secret, _discord_invite_url
    global _get_seq, _get_last_published
    ENABLED = True
    _sign = sign
    _unsign = unsign
    _resolve_member = resolve_member
    _get_state = get_state
    _reveal_extra = reveal_extra
    _session_from_request = session_from_request
    _session_ttl = session_ttl
    _oauth_client_id = oauth_client_id
    _oauth_client_secret = oauth_client_secret
    _discord_invite_url = discord_invite_url
    _get_seq = get_seq
    _get_last_published = get_last_published
    asyncio.create_task(_prune_activity_auth_loop())


async def _prune_activity_auth_loop():
    while True:
        await asyncio.sleep(_RATE_LIMIT_PRUNE_INTERVAL)
        cutoff = time.time() - _RATE_LIMIT_ENTRY_MAX_AGE
        for key in [k for k, ts in _last_activity_auth.items() if ts < cutoff]:
            del _last_activity_auth[key]


# ---------------------------------------------------------------------------
# Signed image proxy
# ---------------------------------------------------------------------------
# Arbitrary question images (trivia_url for normal image questions is any external host) can't
# be declared as Discord Activity URL Mappings one host at a time -- the set is unbounded, since
# the question DB now accepts user submissions. Routing every image through our own already-
# mapped domain sidesteps that entirely; the signed token is what keeps this from becoming an
# open proxy (only URLs the bot itself put in a state payload are ever fetchable, and only for 6h).

def _image_proxy_url(url):
    return "/img?i=" + _sign({"k": "img", "u": url, "exp": time.time() + _IMAGE_TOKEN_TTL})


def proxy_images(state):
    """Rewrite image_url to route through /img. Never mutates the input, which may be the shared
    broadcast dict handed to every SSE subscriber."""
    if not isinstance(state, dict):
        return state
    url = state.get("image_url")
    if not url:
        return state
    return {**state, "image_url": _image_proxy_url(url)}


def _is_safe_host(host):
    """Resolve `host` and reject it if any address is private/loopback/link-local/reserved --
    blocks SSRF targets like 169.254.169.254 (cloud metadata), 127.0.0.1, and RFC1918 ranges.
    Known residual: TOCTOU between this check and the actual connect (DNS rebinding) -- accepted
    for a staging POC."""
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


async def handle_image_proxy(request):
    global _image_semaphore
    if _image_semaphore is None:
        _image_semaphore = asyncio.Semaphore(8)

    payload = _unsign(request.query.get("i", "")) if _unsign else None
    if not payload or payload.get("k") != "img" or not isinstance(payload.get("u"), str):
        return web.Response(status=403, text="bad token")
    url = payload["u"]

    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https":
        return web.Response(status=403, text="scheme not allowed")
    if parsed.port not in (None, 443):
        return web.Response(status=403, text="port not allowed")
    if not _is_safe_host(parsed.hostname or ""):
        return web.Response(status=403, text="host not allowed")

    async with _image_semaphore:
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as http:
                async with http.get(url, allow_redirects=False) as upstream:
                    if upstream.status != 200:
                        return web.Response(status=502, text="upstream error")
                    ctype = (upstream.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                    if ctype not in _IMAGE_ALLOWED_TYPES:
                        return web.Response(status=415, text="unsupported content-type")
                    length = upstream.headers.get("Content-Length")
                    if length and int(length) > _IMAGE_MAX_BYTES:
                        return web.Response(status=413, text="too large")

                    resp = web.StreamResponse(headers={
                        "Content-Type": ctype,
                        "Cache-Control": "public, max-age=86400, immutable",
                    })
                    await resp.prepare(request)
                    sent = 0
                    async for chunk in upstream.content.iter_chunked(65536):
                        sent += len(chunk)
                        if sent > _IMAGE_MAX_BYTES:
                            break
                        await resp.write(chunk)
                    return resp
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return web.Response(status=502, text="fetch failed")


# ---------------------------------------------------------------------------
# Activity auth handshake
# ---------------------------------------------------------------------------

async def handle_activity_token(request):
    ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (request.remote or "")
    now = time.time()
    if now - _last_activity_auth.get(ip, 0) < _ACTIVITY_AUTH_MIN_INTERVAL:
        return web.json_response({"ok": False, "reason": "rate_limited"}, status=429)
    _last_activity_auth[ip] = now

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "reason": "bad_request"}, status=400)
    code = str(body.get("code") or "")
    if not code:
        return web.json_response({"ok": False, "reason": "empty"}, status=400)

    async with aiohttp.ClientSession() as http:
        token_data = {
            "client_id": _oauth_client_id,
            "client_secret": _oauth_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            # Deliberately no redirect_uri: the Activity `authorize` command's code isn't bound
            # to one, unlike the phone companion's OAuth flow (companion_web.handle_callback).
            # Sending one here returns invalid_grant.
        }
        async with http.post(
            "https://discord.com/api/oauth2/token", data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as tok_resp:
            if tok_resp.status != 200:
                return web.json_response({"ok": False, "reason": "token_exchange_failed"}, status=400)
            token = await tok_resp.json()
        access_token = token.get("access_token")
        async with http.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        ) as me_resp:
            if me_resp.status != 200:
                return web.json_response({"ok": False, "reason": "identify_failed"}, status=400)
            me = await me_resp.json()

    user_id = int(me["id"])
    # Same anti-impersonation gate as the phone companion: must be a guild member, using the
    # server nickname so scoring attribution matches everywhere else.
    display_name = _resolve_member(user_id) if _resolve_member else None
    if not display_name:
        return web.json_response(
            {"ok": False, "reason": "not_a_member", "invite": _discord_invite_url}, status=403)

    session = _sign({"user_id": user_id, "display_name": display_name, "exp": time.time() + _session_ttl})
    return web.json_response({
        "ok": True, "access_token": access_token, "session": session, "display_name": display_name,
    })


# ---------------------------------------------------------------------------
# Poll fallback (for when SSE doesn't survive Discord's Activity proxy)
# ---------------------------------------------------------------------------

async def handle_poll(request):
    session = _session_from_request(request) if _session_from_request else None
    if not session:
        return web.json_response({"ok": False, "reason": "unauthenticated"}, status=401)
    game = request.query.get("game", "main")
    try:
        since = int(request.query.get("since", "0"))
    except ValueError:
        since = 0

    seq = _get_seq(game) if _get_seq else 0
    live = _get_state(session["user_id"], game) if _get_state else {"phase": "idle"}
    last = _get_last_published(game) if _get_last_published else None

    # Mirrors handle_stream's personalization: an open question always needs live per-user fields
    # (already_answered/my_answer); a reveal only exists in the last-published cache, since
    # build_companion_state reports bare "idle" the instant the question closes.
    if live.get("phase") == "open":
        state = live
    elif last and last.get("phase") == "revealed":
        extra = _reveal_extra(session["user_id"], game) if _reveal_extra else {}
        state = {**last, **extra}
    else:
        state = live

    if seq <= since and live.get("phase") != "open":
        return web.Response(status=204)

    return web.json_response({"seq": seq, "state": proxy_images(state)})


# ---------------------------------------------------------------------------
# Page + vendored SDK bundle
# ---------------------------------------------------------------------------

_SDK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "vendor", "embedded_app_sdk", "discord-embedded-app-sdk.iife.js")


async def handle_sdk_js(request):
    if not os.path.exists(_SDK_PATH):
        return web.Response(
            status=404, text="SDK bundle not vendored -- see vendor/embedded_app_sdk/README.md")
    resp = web.FileResponse(_SDK_PATH)
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return resp


def render_activity_page(request):
    # Discord's URL Mappings target a bare hostname with no path, so the iframe's document is
    # always "/" -- companion_web.handle_index branches here based on the `frame_id` query param
    # Discord appends to the iframe src on every platform. Direct browser hits to /activity (or
    # /?frame_id=... during local testing without the prefix) have no frame_id, so `prefix` is ""
    # and requests go straight to our own origin instead of through /.proxy.
    prefix = "/.proxy" if request.query.get("frame_id") else ""
    dev = "true" if request.query.get("dev") == "1" else "false"
    html = (_ACTIVITY_HTML
            .replace("__P__", prefix)
            .replace("__CLIENT_ID__", _oauth_client_id)
            .replace("__DEV__", dev))
    return web.Response(text=html, content_type="text/html")


async def handle_activity_page(request):
    return render_activity_page(request)


def activity_routes():
    return [
        web.get("/activity", handle_activity_page),
        web.post("/api/activity/token", handle_activity_token),
        web.get("/api/poll", handle_poll),
        web.get("/img", handle_image_proxy),
        web.get("/activity/sdk.js", handle_sdk_js),
    ]


_ACTIVITY_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>TriviaSphere Activity</title>
<meta name="theme-color" content="#06080D" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#F8F8F8" media="(prefers-color-scheme: light)">
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
  html, body { height: 100%; }
  body { margin:0; color:var(--fg);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,sans-serif;
    background:linear-gradient(180deg,var(--bg),var(--bg2));
    padding:14px calc(14px + env(safe-area-inset-right)) calc(14px + env(safe-area-inset-bottom)) 14px; }
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
  .q { font-size:1.2rem; font-weight:650; line-height:1.34; margin-bottom:18px; letter-spacing:-.01em; }
  .qimage { display:block; width:100%; max-height:38vh; object-fit:contain; border-radius:12px;
    margin:0 0 16px; background:rgba(127,127,127,.06); }
  .puzzle { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:1.3rem;
    letter-spacing:.16em; text-align:center; margin:2px 0 18px; color:var(--fg); overflow-x:auto; }
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
  .choice { padding:15px 16px; font-size:1.0rem; text-align:left; border-radius:14px;
    border:1px solid var(--line); background:rgba(127,127,127,.06); color:inherit; cursor:pointer;
    display:flex; align-items:center; gap:10px;
    transition:border-color .12s, background-color .12s, box-shadow .12s, transform .06s; }
  .choice:active { transform:scale(.99); }
  .choice.selected { border-color:var(--blue); background:rgba(20,109,232,.18);
    box-shadow:0 0 0 2px rgba(20,109,232,.45) inset; font-weight:700; }
  .choice .tick { margin-left:auto; flex:none; font-weight:800; color:var(--blue); }
  .choice.dim { opacity:.45; }
  .choice.selected:disabled, .choice.selected.dim { opacity:1; }
  .status { margin-top:14px; font-size:.92rem; min-height:1.2em; }
  .ok { color:#3ddc84; } .bad { color:var(--red); }
  .warn { display:inline-block; font-size:.8rem; font-weight:600; padding:6px 11px; border-radius:10px;
    margin:0 0 14px; background:rgba(255,170,40,.14); border:1px solid rgba(255,170,40,.42); color:#ffb43a; }
  .result { font-size:1.05rem; font-weight:800; letter-spacing:-.01em; margin:2px 0 10px; }
  .result.correct { color:#3ddc84; } .result.incorrect { color:var(--red); } .result.none { color:var(--muted); }
  .sbtitle { font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em;
    color:var(--muted); margin:18px 0 8px; }
  .sb { display:flex; flex-direction:column; gap:3px; max-height:40vh; overflow-y:auto; }
  .sbrow { display:flex; align-items:center; gap:8px; padding:8px 11px; border-radius:11px;
    background:rgba(127,127,127,.07); font-size:.92rem; }
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
    color:var(--muted); margin:18px 0 8px; }
  .rnd { display:flex; flex-wrap:wrap; gap:6px; }
  .rchip { font-size:.72rem; font-weight:600; padding:4px 9px; border-radius:8px;
    background:rgba(127,127,127,.08); border:1px solid var(--line); color:var(--muted); }
  .rchip.cur { background:rgba(20,109,232,.16); border-color:var(--blue); color:var(--blue); }
  .rchip.done { opacity:.45; }
  .idle { text-align:center; color:var(--muted); padding:10px 0 6px; line-height:1.5; }
  .idle .big { display:block; font-weight:650; color:var(--fg); margin:2px 0 6px; }
  .login { display:inline-flex; align-items:center; gap:9px; padding:12px 20px; background:#5865f2;
    color:#fff; text-decoration:none; border-radius:14px; font-weight:700; margin-top:10px;
    box-shadow:0 6px 16px rgba(88,101,242,.35); }
</style>
</head>
<body>
<div id="app"><div class="idle">Loading…</div></div>
<script>
const P = "__P__";
const CLIENT_ID = "__CLIENT_ID__";
const DEV = __DEV__;
let TOKEN = null;
const currentGame = 'main';
let es = null, pollTimer = null, lastSeq = 0;
let countdownTimer = null, endsAt = 0, currentKey = null, answeredKey = null, answeredValue = null, oneGuess = false;
let lastState = null, flaggedKey = null, flagSubmitting = false;
var FLAG_REASONS = [
  ['category', 'Category'], ['question', 'Question'], ['answer', 'Answer'],
  ['too_niche', 'Too Niche'], ['other', 'Other'],
];

function esc(s) { return String(s).replace(/[&<>"']/g, function (c) {
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }

function authHeaders() {
  return TOKEN ? {'Authorization': 'Bearer ' + TOKEN} : {};
}

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
      (r.via_companion ? '<span class="sbapp" title="Answered via the app">🌐</span>' : '') +
    '</div>';
  }).join('') + note + '</div>';
}

function puzzleHtml(state) {
  return state.puzzle_text ? '<div class="puzzle">' + esc(state.puzzle_text) + '</div>' : '';
}

function flagHtml(state) {
  var isFlagged = flaggedKey === state.question_key;
  return '<button type="button" class="flagbar' + (isFlagged ? ' flagged' : '') + '" ' +
    (isFlagged ? 'disabled ' : '') + 'data-action="open-flag" ' +
    'aria-label="' + (isFlagged ? 'Question flagged' : 'Flag this question') + '">' +
    (isFlagged ? '🚩 Flagged' : '🚩 Flag this question') + '</button>';
}

function imgHtml(state) {
  return state.image_url
    ? '<img class="qimage" src="' + esc(P + state.image_url) + '" alt="Question image">'
    : '';
}

function fmtRemaining() {
  const rem = Math.max(0, Math.ceil(endsAt - Date.now() / 1000));
  const el = document.getElementById('timer');
  if (el) { el.textContent = rem + 's'; el.classList.toggle('low', rem <= 5); }
  if (rem <= 0 && countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
}

function setStatus(msg, cls) {
  const el = document.getElementById('status');
  if (el) { el.textContent = msg; el.className = 'status ' + (cls || ''); }
}

function markChoice(letter) {
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
    const r = await fetch(P + '/api/answer', {
      method: 'POST',
      headers: Object.assign({'Content-Type': 'application/json'}, authHeaders()),
      body: JSON.stringify({answer: answer, game: currentGame}),
    });
    const data = await r.json();
    if (data.ok) {
      answeredKey = currentKey;
      answeredValue = answer;
      markChoice(answer);
      if (oneGuess) {
        setStatus('🔒 Locked in: ' + answer, 'ok');
        const inp = document.getElementById('ans'); if (inp) inp.disabled = true;
        document.querySelectorAll('.choice').forEach(function (b) {
          b.disabled = true;
          if (b.getAttribute('data-letter') !== answer) b.classList.add('dim');
        });
        const btn = document.querySelector('button.primary'); if (btn) btn.disabled = true;
      } else {
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
      '<button type="button" class="cancel" data-action="close-flag">Cancel</button>' +
      '<button type="button" class="submit" id="flagSubmitBtn" data-action="submit-flag">Submit</button>' +
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
    const r = await fetch(P + '/api/flag', {
      method: 'POST',
      headers: Object.assign({'Content-Type': 'application/json'}, authHeaders()),
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

function renderLoggedOut() {
  document.getElementById('app').innerHTML =
    '<div class="idle"><span class="big">Not signed in</span>Close and reopen the activity to sign in again.</div>';
}

function render(state) {
  const app = document.getElementById('app');
  lastState = state;
  if (state.authenticated === false) { renderLoggedOut(); return; }

  if (state.phase === 'revealed') {
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
    app.innerHTML = '<div class="cat">' + esc(state.category || '') + '</div>' +
      (state.question ? '<div class="q">' + esc(state.question) + '</div>' : '') +
      imgHtml(state) +
      resultBanner + answerLine + flagHtml(state) + mine +
      scoreboardHtml(state) + legendHtml(state) + roundHtml(state);
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    return;
  }

  if (state.phase !== 'open') {
    app.innerHTML = '<div class="idle"><span class="big">No live question right now</span>' +
      'Hang tight — the next one is coming. ⏳</div>';
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    return;
  }

  const isNew = state.question_key !== currentKey;
  if (isNew) { answeredValue = null; flaggedKey = null; }
  currentKey = state.question_key;
  endsAt = state.ends_at || 0;
  oneGuess = !!state.warning;

  let inputHtml;
  const prior = (answeredKey === state.question_key && answeredValue) || state.my_answer || '';
  if (state.already_answered) {
    inputHtml = '<div class="status ok">🔒 Locked in' + (prior ? ': ' + esc(prior) : '!') + '</div>' +
      '<div class="idle" style="padding:6px 0">Waiting for the reveal…</div>';
  } else {
    if (state.is_multiple_choice && (state.choices || []).length) {
      inputHtml = '<div class="choices">' + state.choices.map(function (c) {
        var sel = (answeredKey === state.question_key && answeredValue === c.letter);
        return '<button class="choice' + (sel ? ' selected' : '') + '" data-letter="' + esc(c.letter) + '" ' +
          'data-action="choose">' +
          esc(c.text) + (sel ? '<span class="tick">✓</span>' : '') + '</button>';
      }).join('') + '</div>' +
        '<div class="ortype">or type your answer</div>' +
        '<input id="ans" type="text" autocomplete="off" autocapitalize="off" ' +
        'placeholder="Type a letter or the answer…">' +
        '<button class="primary" data-action="submit-text">Submit</button>';
    } else {
      inputHtml = '<input id="ans" type="text" autocomplete="off" autocapitalize="off" ' +
        'placeholder="Type your answer…">' +
        '<button class="primary" data-action="submit-text">Submit</button>';
    }
    if (prior) inputHtml = '<div class="status ok">✓ Submitted: ' + esc(prior) +
      ' — you can submit again</div>' + inputHtml;
  }

  const timerHtml = state.ends_at ? '<span id="timer" class="timer">--</span>' : '';
  app.innerHTML = '<div class="qhead"><span class="cat">' + esc(state.category || '') + '</span>' +
      timerHtml + '</div>' +
      (state.question ? '<div class="q">' + esc(state.question) + '</div>' : '') +
      imgHtml(state) + puzzleHtml(state) +
      (state.warning ? '<div class="warn">' + esc(state.warning) + '</div>' : '') + inputHtml +
      '<div id="status" class="status"></div>' + flagHtml(state) + legendHtml(state) + roundHtml(state);

  if (isNew && !state.already_answered) { const i = document.getElementById('ans'); if (i) i.focus(); }
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
  if (state.ends_at) {
    fmtRemaining();
    countdownTimer = setInterval(fmtRemaining, 250);
  }
}

function tokenQS() { return TOKEN ? '&s=' + encodeURIComponent(TOKEN) : ''; }

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(pollOnce, 2000);
}

async function pollOnce() {
  try {
    const url = P + '/api/poll?game=' + currentGame + '&since=' + lastSeq + tokenQS();
    const r = await fetch(url, {headers: authHeaders()});
    if (r.status === 204) return;
    if (!r.ok) return;
    const j = await r.json();
    lastSeq = j.seq;
    const s = j.state;
    // Avoid tearing down app.innerHTML (and any in-progress typing) on a poll tick that carries
    // nothing new to show.
    if (lastState && s.phase === lastState.phase && s.question_key === lastState.question_key) return;
    render(s);
  } catch (e) {}
}

function connectStream() {
  let sseOk = false, errCount = 0;
  const url = P + '/api/stream?game=' + currentGame + '&activity=1' + tokenQS();
  es = new EventSource(url);
  es.onmessage = function (ev) {
    sseOk = true;
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    try { render(JSON.parse(ev.data)); } catch (e) {}
  };
  es.onerror = function () {
    errCount++;
    if (errCount >= 3) { es.close(); es = null; startPolling(); }
  };
  setTimeout(function () { if (!sseOk) { if (es) { es.close(); es = null; } startPolling(); } }, 8000);
}

async function loadCurrent() {
  const url = P + '/api/current?game=' + currentGame + '&activity=1' + tokenQS();
  try {
    const r = await fetch(url, {headers: authHeaders()});
    const s = await r.json();
    if (s.authenticated === false) { renderLoggedOut(); return; }
    render(s);
    connectStream();
  } catch (e) {
    render({phase: 'idle'});
    connectStream();
  }
}

function loadSdkScript() {
  return new Promise(function (resolve, reject) {
    var s = document.createElement('script');
    s.src = P + '/activity/sdk.js';
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

async function boot() {
  if (DEV) {
    // Dev escape hatch: skip the SDK entirely and ride the existing okra_companion cookie, so
    // the whole panel is testable in a normal browser (open /activity?dev=1 after /login).
    loadCurrent();
    return;
  }
  try {
    await loadSdkScript();
    const sdk = new DiscordSDKBundle.DiscordSDK(CLIENT_ID);
    await sdk.ready();
    const { code } = await sdk.commands.authorize({
      client_id: CLIENT_ID, response_type: 'code', state: '', prompt: 'none', scope: ['identify'],
    });
    const tokenResp = await fetch(P + '/api/activity/token', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({code: code}),
    });
    const tokenJson = await tokenResp.json();
    if (!tokenJson.ok) {
      document.getElementById('app').innerHTML = tokenJson.reason === 'not_a_member'
        ? '<div class="idle"><span class="big">Join the server to play</span>' +
          '<a class="login" href="' + esc(tokenJson.invite || '#') + '" target="_blank">Join TriviaSphere</a></div>'
        : '<div class="idle bad">Could not sign in (' + esc(tokenJson.reason || 'error') + ').</div>';
      return;
    }
    await sdk.commands.authenticate({ access_token: tokenJson.access_token });
    TOKEN = tokenJson.session;
    loadCurrent();
  } catch (e) {
    document.getElementById('app').innerHTML = '<div class="idle bad">Activity failed to start. Reopen it to retry.</div>';
  }
}

// Discord's Activity CSP blocks inline onclick/onkeydown/onpaste/onerror HTML attributes (even
// though the page's own <script> block is allowed to run), so every interactive element above is
// marked with data-action/data-letter instead of an inline handler, and wired here once via
// delegation -- these listeners live on `document`, outside any render function, so they survive
// every innerHTML rebuild rather than needing to be re-attached after each render.
document.addEventListener('click', function (e) {
  const el = e.target.closest('[data-action]');
  if (!el) return;
  const action = el.getAttribute('data-action');
  if (action === 'choose') choose(el, el.getAttribute('data-letter'));
  else if (action === 'submit-text') submitText();
  else if (action === 'open-flag') openFlagModal();
  else if (action === 'close-flag') closeFlagModal();
  else if (action === 'submit-flag') submitFlag();
});

document.addEventListener('keydown', function (e) {
  if (e.target && e.target.id === 'ans' && e.key === 'Enter') submitText();
});

document.addEventListener('paste', function (e) {
  if (e.target && e.target.id === 'ans') e.preventDefault();
});

// 'error' events (a broken question image) don't bubble, so this needs the capture phase.
document.addEventListener('error', function (e) {
  if (e.target && e.target.classList && e.target.classList.contains('qimage')) {
    e.target.style.display = 'none';
  }
}, true);

boot();
</script>
</body>
</html>
"""
