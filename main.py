"""
main.py
-------
The entry point. Ties every module together into a simple loop:

    while True:
        1. fetch newest posts from Reddit
        2. skip ones we've already seen (SQLite)
        3. check each new post with the matcher
        4. send matches to Discord
        5. remember every post we processed so we never repeat
        6. sleep, then do it again

Run it with:   python main.py
Run a single test pass with:   python main.py --once
Verbose (show why posts were skipped):   python main.py --once --verbose
Test Discord only:   python main.py --test-discord
Stop it any time with Ctrl+C.
"""

import sys
import time
from datetime import datetime, timezone

from config import load_config, ConfigError
from database import SeenPostsDB
from discord_notifier import DiscordNotifier
from matcher import analyze
from reddit_client import RedditClient


def _log(message: str) -> None:
    """Print a timestamped log line."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {message}")


def test_discord(discord: DiscordNotifier) -> None:
    """Send one fake post to Discord so you can verify the webhook works."""
    from reddit_client import RedditPost

    post = RedditPost(
        id="test_discord_only",
        subreddit="forhire",
        title="[Hiring] Looking for React Developer (TEST MESSAGE)",
        body="Budget $2,000 for a website build. This is a test from Client Radar.",
        flair="Hiring",
        url="https://www.reddit.com/r/forhire/",
        created_utc=datetime.now(timezone.utc).timestamp() - 120,
    )
    result = analyze(post.title, post.body, post.flair, post.subreddit)
    sent = discord.send(post, result)
    if sent:
        _log("Test message sent to Discord. Check your channel!")
    else:
        _log("Test message FAILED. Check your DISCORD_WEBHOOK_URL.")
        sys.exit(1)


def run_one_pass(
    reddit: RedditClient,
    db: SeenPostsDB,
    discord: DiscordNotifier,
    verbose: bool = False,
) -> None:
    """Do a single fetch-check-notify cycle."""
    posts = reddit.fetch_new_posts()
    already_seen = sum(1 for p in posts if db.has_seen(p.id))
    new_to_check = len(posts) - already_seen
    _log(
        f"Fetched {len(posts)} posts from Reddit "
        f"({already_seen} already in database, {new_to_check} new to check)."
    )

    new_count = 0
    match_count = 0
    skip_count = 0

    for post in posts:
        # Already handled this post in a previous run? Skip immediately.
        if db.has_seen(post.id):
            continue

        new_count += 1
        result = analyze(post.title, post.body, post.flair, post.subreddit)

        if result.is_match:
            match_count += 1
            sent = discord.send(post, result)
            status = "sent to Discord" if sent else "FAILED to send"
            _log(
                f"MATCH [{result.primary_type}] r/{post.subreddit}: "
                f"{post.title[:70]!r} -> {status}"
            )
        else:
            skip_count += 1
            if verbose:
                reason = result.reject_reason or "no hiring intent / not dev-related"
                _log(f"SKIP r/{post.subreddit}: {post.title[:70]!r} — {reason}")

        # Whether it matched or not, mark it seen so we never reprocess it.
        db.mark_seen(post.id, post.subreddit, post.title)

    _log(
        f"Pass complete. New posts: {new_count}, matches: {match_count}, "
        f"skipped: {skip_count}."
    )
    if new_count > 0 and match_count == 0 and not verbose:
        _log("Tip: run with --verbose to see why each post was skipped.")


def main() -> None:
    run_once = "--once" in sys.argv
    test_only = "--test-discord" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        sys.exit(1)

    discord = DiscordNotifier(config.discord_webhook_url)

    if test_only:
        _log("Sending a test message to Discord (no Reddit fetch).")
        test_discord(discord)
        return

    db = SeenPostsDB(config.database_path)
    reddit = RedditClient(config)

    _log("Reddit Client Radar starting up (anonymous RSS — no Reddit account).")
    _log(f"Monitoring subreddits: {', '.join(config.subreddits)}")

    if run_once:
        _log("Running a single pass (--once), then exiting.")
        run_one_pass(reddit, db, discord, verbose=verbose)
        return

    _log(f"Checking every {config.poll_interval_seconds} seconds. Press Ctrl+C to stop.")
    try:
        while True:
            try:
                run_one_pass(reddit, db, discord, verbose=verbose)
            except Exception as exc:  # noqa: BLE001 - keep the loop alive
                # Any unexpected error in a single pass is logged but does not
                # kill the program; we just wait and try again.
                _log(f"Unexpected error during pass: {exc}")
            time.sleep(config.poll_interval_seconds)
    except KeyboardInterrupt:
        _log("Stopped by user. Goodbye!")


if __name__ == "__main__":
    main()
