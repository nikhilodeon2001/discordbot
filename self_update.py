# self_update.py
import os
import sys
import asyncio
import aiohttp
import logging
from motor.motor_asyncio import AsyncIOMotorClient

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ─────────────────────────────────────────────
# Persistent commit tracking using MongoDB
# ─────────────────────────────────────────────

async def get_mongodb_connection():
    """Get MongoDB connection."""
    mongo_uri = os.getenv("mongo_db_string")
    if not mongo_uri:
        raise ValueError("mongo_db_string environment variable not set")
    client = AsyncIOMotorClient(mongo_uri)
    return client["triviabot"]


async def get_last_commit_from_db():
    """Get last stored commit SHA from MongoDB parameters_discord collection."""
    logger.info("Fetching last commit SHA from MongoDB")
    try:
        db = await get_mongodb_connection()
        doc = await db.parameters_discord.find_one({"_id": "last_commit_sha"})
        sha = doc.get("value", "") if doc else ""
        logger.info(f"Retrieved last commit SHA: {sha[:7] if sha else 'none'}")
        return sha
    except Exception as e:
        logger.error(f"Error fetching last commit SHA from MongoDB: {e}")
        return ""


async def set_last_commit_in_db(sha):
    """Store latest commit SHA in MongoDB parameters_discord collection."""
    logger.info(f"Storing commit SHA in MongoDB: {sha[:7]}")
    try:
        db = await get_mongodb_connection()
        await db.parameters_discord.update_one(
            {"_id": "last_commit_sha"},
            {"$set": {"value": sha}},
            upsert=True
        )
        logger.info(f"Successfully stored commit SHA: {sha[:7]}")
    except Exception as e:
        logger.error(f"Error storing commit SHA in MongoDB: {e}")
        raise


# ─────────────────────────────────────────────
# Core update functions
# ─────────────────────────────────────────────

async def check_for_new_commit():
    """Check GitHub for new commits on main branch."""
    logger.info("Checking GitHub for new commits")
    repo = os.getenv("GITHUB_REPO")
    gh_token = os.getenv("GITHUB_TOKEN")
    headers = {"Authorization": f"token {gh_token}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.github.com/repos/{repo}/commits/main", headers=headers) as res:
            res.raise_for_status()
            data = await res.json()
            latest = data["sha"]
            logger.info(f"Latest commit on GitHub: {latest[:7]}")

    last_sha = await get_last_commit_from_db()
    if latest != last_sha:
        await set_last_commit_in_db(latest)
        print(f"New commit detected: {latest[:7]} (previous: {last_sha[:7] if last_sha else 'none'})")
        logger.info(f"New commit detected: {latest[:7]} (previous: {last_sha[:7] if last_sha else 'none'})")
        return True
    print("No new commit found.")
    logger.info("No new commit found - already up to date")
    return False


async def deploy_new_build_and_wait():
    """Trigger a new Heroku build from GitHub and wait until it finishes.
    NOTE: Heroku will automatically deploy the new release and restart dynos when build succeeds.
    """
    app = os.getenv("HEROKU_APP_NAME")
    heroku_token = os.getenv("HEROKU_API_KEY")
    gh_token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPO")

    headers = {
        "Authorization": f"Bearer {heroku_token}",
        "Accept": "application/vnd.heroku+json; version=3",
        "Content-Type": "application/json",
    }

    # Embed GitHub token in the URL for private repo access
    tarball_url = f"https://{gh_token}:x-oauth-basic@api.github.com/repos/{repo}/tarball/main"

    data = {
        "source_blob": {
            "url": tarball_url,
            "version": "main",
        }
    }

    async with aiohttp.ClientSession() as session:
        # Start the build - this will auto-deploy and restart when it succeeds
        logger.info("Triggering Heroku build via API")
        async with session.post(f"https://api.heroku.com/apps/{app}/builds", json=data, headers=headers) as res:
            res.raise_for_status()
            build_info = await res.json()
            build_id = build_info["id"]
            release_id = build_info.get("release", {}).get("id") if build_info.get("release") else "pending"
            print(f"Triggered Heroku build: {build_id}, release: {release_id}")
            logger.info(f"Build triggered: build_id={build_id}, initial_release_id={release_id}")

        # Poll build status until it finishes
        poll_count = 0
        while True:
            await asyncio.sleep(5)
            poll_count += 1
            logger.debug(f"Polling build status (attempt {poll_count})")
            async with session.get(f"https://api.heroku.com/apps/{app}/builds/{build_id}", headers=headers) as check:
                check.raise_for_status()
                status_data = await check.json()
                status = status_data["status"]
                if status in ("succeeded", "failed"):
                    release_info = status_data.get("release", {})
                    release_id = release_info.get("id") if release_info else "unknown"
                    print(f"Build {status} with release: {release_id}")
                    logger.info(f"Build {status}: build_id={build_id}, release_id={release_id}")
                    print(f"Heroku will now automatically deploy this release and restart dynos.")
                    logger.info("Heroku will now automatically deploy this release and restart dynos")
                    if status == "failed":
                        logger.error("Build failed")
                        raise RuntimeError("Heroku build failed. Check the Heroku dashboard for details.")
                    break
                print("Waiting for Heroku build to complete...")


async def wait_for_sigterm():
    """Wait indefinitely for Heroku to send SIGTERM when deploying the new release."""
    print("Build complete. Waiting for Heroku to deploy new release and send SIGTERM...")
    logger.info("Entering wait loop for SIGTERM signal from Heroku")
    sys.stdout.flush()
    # Block forever - Heroku will kill this process when it deploys the new release
    # Use time.sleep to fully block and prevent any further rounds from starting
    import time
    iteration = 0
    while True:
        iteration += 1
        logger.info(f"Waiting for SIGTERM (iteration {iteration})")
        time.sleep(3600)  # Sleep 1 hour at a time, forever
        logger.info(f"Completed sleep iteration {iteration}, continuing to wait")


# ─────────────────────────────────────────────
# Main entrypoint for convenience
# ─────────────────────────────────────────────

async def self_update():
    """Full self-update process: check → build → wait for deployment.
    Returns True if an update was performed, False otherwise.
    This function does NOT return if an update is found - it blocks until SIGTERM.
    """
    logger.info("=== self_update() started ===")
    print("Checking for new commits...")
    if await check_for_new_commit():
        print("New commit found! Deploying new build...")
        logger.info("New commit detected - starting build and deployment process")
        await deploy_new_build_and_wait()
        logger.info("Build polling complete - now waiting for SIGTERM from Heroku")
        await wait_for_sigterm()
        # Never reaches here - SIGTERM will kill the process
        logger.critical("This line should never be reached - SIGTERM should have killed the process")
        return True
    else:
        print("No update required.")
        logger.info("=== self_update() completed - no update needed ===")
        return False
