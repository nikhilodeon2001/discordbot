"""
One-time migration: replace readme/wiki messages that were posted by the
human account "TheOkraG" (username okrastrut, user id 591861826690613248)
with identical messages posted by the real OkraStrut bot, in the same
channels, in the same order.

Two-phase, manual-gate workflow:

    post   - fetch each target channel's TheOkraG-authored messages, repost
             them verbatim as the bot, and record an old_id -> new_id mapping
             in okrastrut_readme_migration.json. Does NOT delete anything.

    delete - read okrastrut_readme_migration.json and delete the original
             TheOkraG messages. Only run this after manually verifying the
             new bot messages look right in Discord.

Run against PROD only:

    discord_token=... python replace_okrastrut_readme_messages.py post
    discord_token=... python replace_okrastrut_readme_messages.py delete
"""

import argparse
import json
import os
import sys
import time

import requests

API_BASE = "https://discord.com/api/v10"
SOURCE_AUTHOR_ID = "591861826690613248"  # TheOkraG / okrastrut

TARGET_CHANNELS = {
    "1372347624648347649": "rules",
    "1411551000065609939": "how-to-play",
    "1447284872841269399": "simply-wiki",
    "1416665273301205064": "tournament-wiki",
    "1447285179176714443": "okra-hunt-wiki",
}

MAPPING_FILE = "okrastrut_readme_migration.json"


def _headers(token):
    return {"Authorization": f"Bot {token}", "Content-Type": "application/json"}


def _get(session, url, **kwargs):
    resp = session.get(url, **kwargs)
    if resp.status_code == 429:
        retry_after = resp.json().get("retry_after", 1)
        time.sleep(retry_after)
        return _get(session, url, **kwargs)
    resp.raise_for_status()
    return resp


def _post(session, url, **kwargs):
    resp = session.post(url, **kwargs)
    if resp.status_code == 429:
        retry_after = resp.json().get("retry_after", 1)
        time.sleep(retry_after)
        return _post(session, url, **kwargs)
    resp.raise_for_status()
    return resp


def _delete(session, url, **kwargs):
    resp = session.delete(url, **kwargs)
    if resp.status_code == 429:
        retry_after = resp.json().get("retry_after", 1)
        time.sleep(retry_after)
        return _delete(session, url, **kwargs)
    resp.raise_for_status()
    return resp


def fetch_source_messages(session, channel_id):
    resp = _get(session, f"{API_BASE}/channels/{channel_id}/messages", params={"limit": 100})
    messages = [m for m in resp.json() if m["author"]["id"] == SOURCE_AUTHOR_ID]
    messages.sort(key=lambda m: int(m["id"]))  # oldest first
    return messages


def do_post(token):
    session = requests.Session()
    session.headers.update(_headers(token))

    mapping = []
    for channel_id, channel_name in TARGET_CHANNELS.items():
        source_messages = fetch_source_messages(session, channel_id)
        print(f"# {channel_name} ({channel_id}): {len(source_messages)} message(s) to repost")

        for msg in source_messages:
            resp = _post(
                session,
                f"{API_BASE}/channels/{channel_id}/messages",
                json={"content": msg["content"]},
            )
            new_message = resp.json()
            print(f"  {msg['id']} -> {new_message['id']}")
            mapping.append(
                {
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "old_message_id": msg["id"],
                    "new_message_id": new_message["id"],
                }
            )

    with open(MAPPING_FILE, "w") as f:
        json.dump(mapping, f, indent=2)
    print(f"\nWrote {len(mapping)} entries to {MAPPING_FILE}")

    rules_entries = [m for m in mapping if m["channel_name"] == "rules"]
    if rules_entries:
        print(f"\nNew Rules message id (update RULES_MESSAGE_ID): {rules_entries[0]['new_message_id']}")


def do_delete(token):
    if not os.path.exists(MAPPING_FILE):
        sys.exit(f"{MAPPING_FILE} not found - run 'post' first")

    with open(MAPPING_FILE) as f:
        mapping = json.load(f)

    session = requests.Session()
    session.headers.update(_headers(token))

    for entry in mapping:
        _delete(session, f"{API_BASE}/channels/{entry['channel_id']}/messages/{entry['old_message_id']}")
        print(f"  deleted {entry['old_message_id']} in {entry['channel_name']}")

    print(f"\nDeleted {len(mapping)} original message(s)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["post", "delete"])
    args = parser.parse_args()

    token = os.getenv("discord_token")
    if not token:
        sys.exit("discord_token env var is required")

    if args.action == "post":
        do_post(token)
    else:
        do_delete(token)


if __name__ == "__main__":
    main()
