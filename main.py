"""
main.py
-------
Manual trigger only. Each time you run this, it:

    1. Fetches the newest posts from Reddit (anonymous RSS)
    2. Skips posts already seen in SQLite (from your last run)
    3. Sends new matches to Discord
    4. Remembers every post checked so you never get duplicates

Usage:
    python main.py              # scan once (normal use)
    python main.py --verbose    # scan + show why posts were skipped
    python main.py --test-discord   # test webhook only
"""

import sys
from datetime import datetime, timezone

from config import load_config, ConfigError
from database import SeenPostsDB
from discord_notifier import DiscordNotifier
from matcher import analyze
from reddit_client import RedditClient


def _log(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {message}")


def test_discord(discord: DiscordNotifier) -> None:
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


def run_scan(
    reddit: RedditClient,
    db: SeenPostsDB,
    discord: DiscordNotifier,
    *,
    verbose: bool = False,
    send_status: bool = True,
    subreddits: list[str] | None = None,
) -> int:
    """Fetch new posts since last run, notify Discord, return match count."""
    posts = reddit.fetch_new_posts()
    # Newest first — fresh morning posts get checked and sent first.
    posts.sort(key=lambda p: p.created_utc, reverse=True)

    already_seen = sum(1 for p in posts if db.has_seen(p.id))
    new_to_check = len(posts) - already_seen
    _log(
        f"Fetched {len(posts)} posts from Reddit "
        f"({already_seen} already seen, {new_to_check} new since last run)."
    )

    new_count = 0
    match_count = 0
    skip_count = 0

    for post in posts:
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
                reason = result.reject_reason or "not a hiring post for your profile"
                _log(f"SKIP r/{post.subreddit}: {post.title[:70]!r} — {reason}")

        db.mark_seen(post.id, post.subreddit, post.title)

    _log(
        f"Done. New posts checked: {new_count}, matches sent: {match_count}, "
        f"skipped: {skip_count}."
    )
    if new_count > 0 and match_count == 0 and not verbose:
        _log("No matches this run. Use --verbose to see why posts were skipped.")

    if send_status:
        sent = discord.send_scan_status(
            fetched=len(posts),
            already_seen=already_seen,
            new_checked=new_count,
            matches=match_count,
            skipped=skip_count,
            subreddits=subreddits or reddit.subreddits,
        )
        if sent:
            _log("Summary sent to Discord.")
        else:
            _log("Summary failed to send to Discord.")

    return match_count


def main() -> None:
    test_only = "--test-discord" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        sys.exit(1)

    discord = DiscordNotifier(config.discord_webhook_url)

    if test_only:
        _log("Testing Discord webhook (no Reddit fetch).")
        test_discord(discord)
        return

    db = SeenPostsDB(config.database_path)
    reddit = RedditClient(config)

    _log("Client Radar — manual scan starting.")
    _log(f"Subreddits: {', '.join(config.subreddits)}")
    _log(f"Posts in memory: {db.count()} (from previous runs)")

    run_scan(
        reddit,
        db,
        discord,
        verbose=verbose,
        send_status=config.send_status_to_discord,
        subreddits=config.subreddits,
    )


if __name__ == "__main__":
    main()
