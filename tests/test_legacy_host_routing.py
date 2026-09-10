"""How the legacy companion domain (play.triviasphere.com) is routed.

    ./.venv/bin/python tests/test_legacy_host_routing.py     # or: pytest tests/test_legacy_host_routing.py

The Discord Activity's URL Mapping pointed at the legacy host, so every request the Activity
made arrived on it and was answered with a 301. A 301 does NOT preserve the request method:
the POST to /api/activity/token came back as a bodyless GET, hit a POST-only route, and got a
405 whose plaintext body then blew up `await tokenResp.json()` in boot(). The panel reported
"Activity failed to start." Seven POST routes were affected, so even a working token exchange
would have left answering silently broken.

Two properties keep that from recurring, and this file pins both:

  1. API paths are never redirected -- they are served on whichever host they arrive on.
  2. Anything still redirected uses 308, which preserves method and body.

The middleware is exercised directly rather than through the real app, so no Mongo, no Discord
credentials, and no fixed port are involved.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiohttp import web  # noqa: E402
from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

import branding  # noqa: E402
import companion_web  # noqa: E402

LEGACY = branding.COMPANION_LEGACY_HOST
NEW = branding.COMPANION_NEW_HOST


def _build_app():
    """A stand-in route table with the same shapes as the real one: a POST API endpoint, a GET
    API endpoint, and a human-facing page."""
    async def echo(request):
        return web.json_response({"method": request.method})

    async def page(request):
        return web.Response(text="page")

    app = web.Application(middlewares=[companion_web._legacy_domain_redirect_middleware])
    app.add_routes([
        web.post("/api/activity/token", echo),
        web.get("/api/poll", echo),
        web.get("/activity/sdk.js", echo),
        web.get("/", page),
        web.get("/submit", page),
    ])
    return app


async def _request(method, path, host):
    """Issue one request with X-Forwarded-Host set -- the header _request_origin actually reads
    (Heroku's router sets it). Redirects are NOT followed, so we can inspect the hop itself."""
    async with TestClient(TestServer(_build_app())) as client:
        resp = await client.request(
            method, path, headers={"X-Forwarded-Host": host}, allow_redirects=False,
        )
        body = await resp.text()
        return resp.status, resp.headers.get("Location"), body


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def test_api_post_on_legacy_host_is_not_redirected():
    """The actual bug: this used to answer 301, and the retry arrived as a GET -> 405."""
    status, location, body = asyncio.run(_request("POST", "/api/activity/token", LEGACY))
    assert status == 200, f"expected the handler to run, got {status} (Location={location})"
    assert location is None, f"API POST must not be redirected, got a hop to {location}"
    assert '"method": "POST"' in body.replace("'", '"'), f"method was not preserved: {body}"


@case
def test_api_get_on_legacy_host_is_not_redirected():
    status, location, _ = asyncio.run(_request("GET", "/api/poll", LEGACY))
    assert status == 200 and location is None, f"got {status} -> {location}"


@case
def test_sdk_asset_on_legacy_host_is_not_redirected():
    status, location, _ = asyncio.run(_request("GET", "/activity/sdk.js", LEGACY))
    assert status == 200 and location is None, f"got {status} -> {location}"


@case
def test_pages_on_legacy_host_still_redirect_to_the_new_host():
    """The redirect still exists -- old links and bookmarks are the reason it was added."""
    for path in ("/", "/submit"):
        status, location, _ = asyncio.run(_request("GET", path, LEGACY))
        assert status == 308, f"{path}: expected 308, got {status}"
        assert location == f"https://{NEW}{path}", f"{path}: bad Location {location}"


@case
def test_page_redirect_is_method_preserving():
    """308, never 301/302 -- those rewrite POST to GET and drop the body."""
    status, _, _ = asyncio.run(_request("GET", "/", LEGACY))
    assert status not in (301, 302), f"{status} would downgrade the method on a non-GET"


@case
def test_new_host_is_untouched():
    status, location, _ = asyncio.run(_request("POST", "/api/activity/token", NEW))
    assert status == 200 and location is None, f"got {status} -> {location}"


def main():
    failures = 0
    for fn in CASES:
        try:
            fn()
            print(f"[PASS] {fn.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"[FAIL] {fn.__name__}: {e}")
    print(f"\n{len(CASES)} cases, {failures} failing")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
