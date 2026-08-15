"""
Chat Mirror: bidirectionally mirrors messages between the real trivia round channel and the
trivia-beta voice channel's own native chat, so beta-testing the new Discord Activity/TV-view
experience in trivia-beta feels like a live extension of the real channel instead of an empty
room -- without touching the real channel's existing behavior at all.

Modeled on companion_bridge.py's webhook-relay pattern (per-channel webhook, created lazily and
looked up by a fixed name, sends under the original author's real name/avatar). Sends are routed
through a small per-destination asyncio.Queue + single worker task rather than fired directly
from on_message, so a burst of chat doesn't try to fire many concurrent webhook.send() calls at
once -- Discord webhooks are rate-limited (~5 req/sec); the queue guarantees in-order delivery
and lets a message wait its turn instead of racing others, without blocking on_message's dispatch
of anything else (the round loop, mini-games, and companion streaming all run as independent
asyncio tasks regardless of how long a mirror send takes). Each destination gets its own
queue/worker (lazily started on first use, same laziness as the webhook cache below), so the two
directions can never block each other.

Only ever driven from on_message on the real, connected bot instance -- never called across the
module-duplication boundary described in companion_bridge.py's docstring, so (unlike
companion_bridge.py) no init()/injected bot reference is needed here.
"""

import asyncio

import discord

_webhook_cache = {}  # channel_id -> discord.Webhook
_MIRROR_WEBHOOK_NAME = "Okra's World Chat Mirror"
_LEGACY_MIRROR_WEBHOOK_NAME = "TriviaSphere Chat Mirror"

_queues = {}  # dest_channel_id -> asyncio.Queue
_worker_tasks = {}  # dest_channel_id -> asyncio.Task


async def _get_or_create_mirror_webhook(channel):
    cached = _webhook_cache.get(channel.id)
    if cached is not None:
        return cached
    try:
        webhooks = await channel.webhooks()
        webhook = discord.utils.get(webhooks, name=_MIRROR_WEBHOOK_NAME)
        if webhook is None:
            # Rename the pre-rebrand webhook in place rather than creating a duplicate.
            legacy_webhook = discord.utils.get(webhooks, name=_LEGACY_MIRROR_WEBHOOK_NAME)
            if legacy_webhook is not None:
                webhook = await legacy_webhook.edit(name=_MIRROR_WEBHOOK_NAME)
            else:
                webhook = await channel.create_webhook(name=_MIRROR_WEBHOOK_NAME)
    except (discord.HTTPException, discord.Forbidden) as e:
        print(f"⚠️ chat_mirror: failed to get/create webhook for #{channel.id}: {e}")
        return None
    _webhook_cache[channel.id] = webhook
    return webhook


def is_mirror_webhook(message):
    """True if `message` was posted by our own mirror webhook -- used by on_message to skip
    re-mirroring the echo back the way it came."""
    webhook_id = getattr(message, "webhook_id", None)
    if webhook_id is None:
        return False
    return any(webhook.id == webhook_id for webhook in _webhook_cache.values())


async def _mirror_message(message, dest_channel):
    webhook = await _get_or_create_mirror_webhook(dest_channel)
    if webhook is None:
        return
    content = message.content or ""
    if message.attachments:
        urls = "\n".join(a.url for a in message.attachments)
        content = f"{content}\n{urls}" if content else urls
    if not content:
        return
    try:
        await webhook.send(
            content=content[:2000],
            username=message.author.display_name[:80],
            avatar_url=message.author.display_avatar.url,
            wait=True,
        )
    except (discord.HTTPException, discord.Forbidden) as e:
        print(f"⚠️ chat_mirror: failed to send mirrored message to #{dest_channel.id}: {e}")


async def _worker(queue):
    while True:
        message, dest_channel = await queue.get()
        try:
            await _mirror_message(message, dest_channel)
        finally:
            queue.task_done()


def enqueue(message, dest_channel):
    """Queue `message` to be mirrored into `dest_channel`. Lazily starts that destination's
    worker on first use, mirroring the lazy webhook creation above."""
    queue = _queues.get(dest_channel.id)
    if queue is None:
        queue = asyncio.Queue()
        _queues[dest_channel.id] = queue
        _worker_tasks[dest_channel.id] = asyncio.create_task(_worker(queue))
    queue.put_nowait((message, dest_channel))
