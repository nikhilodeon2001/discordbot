"""
Companion Bridge: lets the companion web app (companion_web.py) act on the post-round
options menu, the mini-game/category picker, and mini-game answer prompts -- all of
which normally only accept a real Discord message via bot.wait_for("message", check=...).

Discord webhook messages can't satisfy those check(m): m.author.id == winner_id closures
(a webhook message's author.id is the webhook's own id, not the real user's, and there's
no reliable hook to rewrite that before wait_for's internal listener evaluates its check --
that check runs synchronously inside Client.dispatch, before our own on_message coroutine
is even scheduled). So logic and appearance are split, both driven by the same event:

  - Logic: a small in-memory registry of "active prompts". wait_for_message_or_companion()
    races the real bot.wait_for(...) against a prompt's Future using
    asyncio.wait(..., return_when=FIRST_COMPLETED) -- whichever resolves first wins, so
    Discord typing keeps working exactly as today, unaffected.
  - Appearance: submit_companion_input() also echoes the submission into the channel via
    a per-channel cached webhook (real display name + avatar). This is purely
    cosmetic/best-effort -- if it fails (e.g. missing Manage Webhooks), the logic path
    still works, only the visual echo silently no-ops.

Prompts are scoped to "main" (the fixed main trivia channel) or "arena"
(MINI_GAME_ARENA_CHANNEL_ID), matching companion_web.py's per-toggle answer slots -- a
submission on one toggle can only ever resolve a prompt registered in that same scope.

Imports discordbot lazily inside functions to avoid circular imports (same pattern as
mini_games.py). CRITICAL caveat learned the hard way: discordbot.py is actually executed
*twice* under two different sys.modules names -- once as `__main__` (the real, connected
bot; this is the only copy `main()` ever runs in), and once as `discordbot` (an inert,
never-logged-in duplicate, created as a side effect of discordbot.py's own circular import
with simply_trivia.py -- see `_IS_REIMPORT` in discordbot.py for a pre-existing workaround
for a different instance of the same issue). `import discordbot` from any *other* file
always binds to that inert `discordbot`-named copy, never to `__main__`. Plain constants
(`MINI_GAME_ARENA_CHANNEL_ID`, `OKRAN_GUILD_ID`) are identical either way and safe to read
via `import discordbot`, but a live *object reference* (the actual connected bot) is not --
hence `init()`/`_get_bot` below, injected explicitly from `main()` (which only exists in the
real `__main__` copy) instead of re-derived via `import discordbot`.
"""

import asyncio
import datetime
import itertools

import discord

_prompts = {}  # prompt_id -> Prompt
_prompts_by_user = {}  # user_id -> set[prompt_id]
_prompt_id_counter = itertools.count(1)
_webhook_cache = {}  # channel_id -> discord.Webhook
_get_bot = None  # injected by init() -- see module docstring for why this can't just be `import discordbot; discordbot.get_bot()`

_RELAY_WEBHOOK_NAME = "Okra Companion Relay"
_COMPANION_INDICATOR = " 🌐"  # matches the existing companion-app scoreboard icon (see build_companion_scoreboard/render_emoji_icon)


def init(get_bot_func):
    """Called once from discordbot.py's main() (the real `__main__` copy) to hand this
    module a reliable reference to the live, connected bot's get_bot() function."""
    global _get_bot
    _get_bot = get_bot_func


class CompanionAuthor:
    """Duck-typed stand-in for a discord.Member -- enough surface for check() closures
    (`.id`) and mention/attribution code (`.display_name`, `.mention`). A distinct object
    from bot.user, so `m.author != get_bot().user` checks hold without any extra work."""

    def __init__(self, user_id, display_name):
        self.id = user_id
        self.display_name = display_name
        self.bot = False

    @property
    def mention(self):
        return f"<@{self.id}>"


class CompanionMessage:
    """Duck-typed stand-in for a discord.Message, returned by
    wait_for_message_or_companion() when a companion (web) submission wins the race
    against the real Discord wait_for(). `.add_reaction`/`.remove_reaction`/`.delete`
    proxy to the cosmetic webhook echo when one was successfully posted (`echo`);
    otherwise they no-op, since there's no real message for a companion answer to act on."""

    def __init__(self, content, author, channel, echo=None):
        self.content = content
        self.author = author
        self.channel = channel
        self.created_at = datetime.datetime.now(datetime.timezone.utc)
        self.id = echo.id if echo is not None else None
        self._echo = echo

    async def add_reaction(self, emoji):
        if self._echo is not None:
            try:
                await self._echo.add_reaction(emoji)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                pass

    async def remove_reaction(self, emoji, member):
        if self._echo is not None:
            try:
                await self._echo.remove_reaction(emoji, member)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                pass

    async def delete(self):
        if self._echo is not None:
            try:
                await self._echo.delete()
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                pass


class Prompt:
    def __init__(self, prompt_id, channel, scope, allowed_user_ids, kind, prompt_text, reveal_answer=True):
        self.id = prompt_id
        self.channel = channel
        self.scope = scope
        # None means "open floor" -- many mini-games' answer-guessing loops have no author-id
        # restriction at all (check() only filters on channel + not-the-bot), so literally any
        # guild member typing in the channel can guess. allowed_user_ids stays a concrete set
        # for winner-only sub-steps (tier/category picks, post-round menus, etc.).
        self.open_floor = allowed_user_ids is None
        self.allowed_user_ids = set() if self.open_floor else set(allowed_user_ids)
        self.kind = kind
        self.prompt_text = prompt_text
        # Whether the webhook echo shows the literal submitted text. True for post-round-menu/
        # WoF-selection prompts (a public one-shot pick, no different from typing it in Discord)
        # and for "first correct answer wins the round" mini-games (Discord-typed guesses are
        # already visible to everyone there in real time, so there's nothing to protect). False
        # for mini-games where multiple players can independently get credit within the same
        # window -- echoing the raw guess would let a companion-app user's answer be read and
        # copied by someone who hasn't answered yet, the same leak the live-trivia companion
        # flow is designed to avoid.
        self.reveal_answer = reveal_answer
        self.future = asyncio.get_running_loop().create_future()


_MASKED_ANSWER_ECHO = "🔒 *submitted an answer*"


def _scope_for_channel(channel):
    import discordbot
    if channel is not None and getattr(channel, "id", None) == discordbot.MINI_GAME_ARENA_CHANNEL_ID:
        return "arena"
    return "main"


def register_prompt(channel, allowed_user_ids, kind, prompt_text=None, reveal_answer=True):
    """`allowed_user_ids=None` registers an "open floor" prompt -- any authenticated companion
    user may submit (matching a Discord check() with no author-id restriction). Otherwise pass
    the concrete set of ids check() already restricts to."""
    prompt_id = next(_prompt_id_counter)
    prompt = Prompt(prompt_id, channel, _scope_for_channel(channel), allowed_user_ids, kind, prompt_text, reveal_answer)
    _prompts[prompt_id] = prompt
    for uid in prompt.allowed_user_ids:
        _prompts_by_user.setdefault(uid, set()).add(prompt_id)
    return prompt


def clear_prompt(prompt_id):
    prompt = _prompts.pop(prompt_id, None)
    if prompt is None:
        return
    for uid in prompt.allowed_user_ids:
        ids = _prompts_by_user.get(uid)
        if ids is not None:
            ids.discard(prompt_id)
            if not ids:
                _prompts_by_user.pop(uid, None)


def get_active_prompt(scope):
    """Return the active Prompt for a scope ("main"/"arena"), or None. At most one prompt
    per scope realistically exists at a time (_active_game_channel/arena_game_lock and the
    round loop's sequential post-round menu both guarantee it), but this doesn't assume it."""
    for prompt in _prompts.values():
        if prompt.scope == scope:
            return prompt
    return None


def describe_prompt(prompt, user_id=None):
    if prompt is None:
        return None
    return {
        "kind": prompt.kind,
        "prompt_text": prompt.prompt_text,
        "you_can_act": user_id is not None and (prompt.open_floor or user_id in prompt.allowed_user_ids),
        "open_floor": prompt.open_floor,
        "allowed_user_ids": sorted(prompt.allowed_user_ids),
    }


async def _get_avatar_url(user_id):
    import discordbot
    guild = _get_bot().get_guild(discordbot.OKRAN_GUILD_ID)
    if guild is None:
        return None
    member = guild.get_member(int(user_id))
    if member is None:
        return None
    return member.display_avatar.url


async def _get_or_create_relay_webhook(channel):
    cached = _webhook_cache.get(channel.id)
    if cached is not None:
        return cached
    try:
        webhooks = await channel.webhooks()
        webhook = discord.utils.get(webhooks, name=_RELAY_WEBHOOK_NAME)
        if webhook is None:
            webhook = await channel.create_webhook(name=_RELAY_WEBHOOK_NAME)
    except (discord.HTTPException, discord.Forbidden):
        return None
    _webhook_cache[channel.id] = webhook
    return webhook


def is_companion_relay_webhook(message):
    """True if `message` was posted by our own relay webhook -- used by on_message to skip
    re-parsing the cosmetic echo as an independent, second command/answer."""
    webhook_id = getattr(message, "webhook_id", None)
    if webhook_id is None:
        return False
    return any(webhook.id == webhook_id for webhook in _webhook_cache.values())


async def _send_relay_echo(channel, display_name, user_id, text):
    if channel is None:
        return None
    webhook = await _get_or_create_relay_webhook(channel)
    if webhook is None:
        return None
    try:
        # Same 🌐 the scoreboard already uses to mark a companion (web) answer -- on the
        # username (never parsed by game logic) rather than the content, so it can't
        # interfere with exact-text keyword/number matching in the menus/mini-games.
        base_name = (display_name or "Companion").strip() or "Companion"
        username = f"{base_name[:80 - len(_COMPANION_INDICATOR)]}{_COMPANION_INDICATOR}"
        avatar_url = await _get_avatar_url(user_id)
        sent = await webhook.send(
            content=text[:2000] or "​",
            username=username,
            avatar_url=avatar_url,
            wait=True,
        )
    except (discord.HTTPException, discord.Forbidden):
        return None
    try:
        await sent.add_reaction("🌐")
    except (discord.HTTPException, discord.Forbidden, discord.NotFound):
        pass
    return sent


async def submit_companion_input(user_id, display_name, text, scope):
    """Resolve the active prompt for `scope` on behalf of a companion (web) user. Never
    reaches across scopes -- an "arena" toggle submission can only ever resolve an
    arena-scoped prompt, and vice versa, so there's no ambiguity when a main-channel
    question and an arena mini-game are open at the same time."""
    prompt = get_active_prompt(scope)
    if prompt is None or prompt.future.done():
        return {"ok": False, "reason": "no_active_prompt"}
    if not prompt.open_floor and user_id not in prompt.allowed_user_ids:
        return {"ok": False, "reason": "not_allowed"}
    echo_text = text if prompt.reveal_answer else _MASKED_ANSWER_ECHO
    echo = await _send_relay_echo(prompt.channel, display_name, user_id, echo_text)
    message = CompanionMessage(text, CompanionAuthor(user_id, display_name), prompt.channel, echo=echo)
    prompt.future.set_result(message)
    return {"ok": True}


def _notify_prompt_change(scope):
    """Wake up any companion (web) session already connected via SSE so it re-fetches state --
    otherwise a prompt appearing/disappearing is invisible to a phone that isn't actively
    polling (companion_web.py's publish_state is otherwise only called from the main-trivia/
    Simply-Trivia question-open/reveal transitions, never for prompts). `scope` ("main"/"arena")
    already matches companion_web's `game` values 1:1. The pushed payload is a content-free
    sentinel, not the actual state, because `you_can_act` differs per viewer (only the allowed
    user(s) see True) -- handle_stream re-derives the real, personalized state per connection
    when it sees this sentinel rather than broadcasting one shared dict."""
    import companion_web
    try:
        companion_web.publish_state({"__refresh__": True}, game=scope)
    except Exception:
        pass


async def wait_for_message_or_companion(check, timeout, channel, allowed_user_ids, kind, prompt_text=None, reveal_answer=True):
    """Drop-in replacement for `get_bot().wait_for("message", timeout=timeout, check=check)`
    that also accepts a matching companion (web) submission. Returns a real discord.Message
    when Discord wins the race, or a CompanionMessage when the companion app does. Raises
    asyncio.TimeoutError exactly like the plain wait_for did, on the same timeout budget.
    `reveal_answer=False` masks the webhook echo's content (see Prompt.reveal_answer) -- pass
    it for mini-games where multiple players can independently get credit in the same window."""
    prompt = register_prompt(channel, allowed_user_ids, kind, prompt_text, reveal_answer=reveal_answer)
    _notify_prompt_change(prompt.scope)
    msg_task = asyncio.ensure_future(_get_bot().wait_for("message", check=check))
    comp_task = asyncio.ensure_future(prompt.future)
    try:
        done, pending = await asyncio.wait({msg_task, comp_task}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        if not done:
            raise asyncio.TimeoutError()
        return done.pop().result()
    finally:
        clear_prompt(prompt.id)
        _notify_prompt_change(prompt.scope)
