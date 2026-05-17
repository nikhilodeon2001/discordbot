"""One-time helper to mint a long-lived Facebook Page token.

Usage:
  FACEBOOK_APP_ID=... \
  FACEBOOK_APP_SECRET=... \
  FACEBOOK_SHORT_LIVED_USER_TOKEN=... \
  python3 get_facebook_page_token.py

The short-lived user token must already include the Page permissions your app needs,
including pages_show_list, business_management, pages_read_engagement, and
pages_manage_posts.
"""

import json
import os
import sys
from urllib.parse import urlencode
from urllib.request import urlopen

GRAPH_VERSION = os.getenv("FACEBOOK_GRAPH_API_VERSION", "v23.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
TARGET_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "1100185043186368")


def graph_get(path: str, **params):
    with urlopen(f"{GRAPH_BASE}{path}?{urlencode(params)}") as response:
        return json.loads(response.read().decode())


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def main() -> None:
    app_id = required_env("FACEBOOK_APP_ID")
    app_secret = required_env("FACEBOOK_APP_SECRET")
    short_user_token = required_env("FACEBOOK_SHORT_LIVED_USER_TOKEN")

    long_user = graph_get(
        "/oauth/access_token",
        grant_type="fb_exchange_token",
        client_id=app_id,
        client_secret=app_secret,
        fb_exchange_token=short_user_token,
    )
    long_user_token = long_user["access_token"]

    accounts = graph_get("/me/accounts", access_token=long_user_token)
    page = next((item for item in accounts.get("data", []) if item.get("id") == TARGET_PAGE_ID), None)
    if not page:
        available = [f"{item.get('name')} ({item.get('id')})" for item in accounts.get("data", [])]
        raise SystemExit(
            f"Page {TARGET_PAGE_ID} not found in /me/accounts. Available pages: {available or 'none'}"
        )

    print("Long-lived Page token ready.")
    print(f"Page: {page.get('name')} ({page.get('id')})")
    print("Set this as FACEBOOK_PAGE_ACCESS_TOKEN:")
    print(page["access_token"])


if __name__ == "__main__":
    main()
