"""
discord_notifier.py
-------------------
Sends matched posts to a Discord channel using an incoming Webhook.

A webhook is just a special URL Discord gives you; POSTing JSON to it makes a
message appear in the channel. No bot, no login, no gateway connection needed.
We use a rich "embed" so the message looks clean and structured.
"""

import requests

from matcher import MatchResult
from reddit_client import RedditPost

# Discord colors are integers. This is a pleasant blue. (0x5865F2 = Discord blurple)
EMBED_COLOR = 0x5865F2


class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _build_payload(self, post: RedditPost, match: MatchResult) -> dict:
        """Build the JSON Discord expects, using the requested field layout."""
        keywords = ", ".join(match.matched_keywords) if match.matched_keywords else "TBD"

        embed = {
            "title": post.title[:250] if post.title else "TBD",
            "url": post.permalink,
            "color": EMBED_COLOR,
            "fields": [
                {"name": "Subreddit", "value": f"r/{post.subreddit}", "inline": True},
                {"name": "Age", "value": post.age_human(), "inline": True},
                {"name": "Budget", "value": match.budget or "TBD", "inline": True},
                {"name": "Client Type", "value": match.primary_type, "inline": True},
                {"name": "Keywords matched", "value": keywords, "inline": False},
                {"name": "Link", "value": post.permalink, "inline": False},
            ],
            "footer": {"text": "Reddit Client Radar"},
        }

        return {
            "content": "**New Client Post!**",
            "embeds": [embed],
        }

    def send(self, post: RedditPost, match: MatchResult) -> bool:
        """
        Send one post to Discord. Returns True on success, False on failure.
        We never raise, so a Discord hiccup cannot crash the monitor loop.
        """
        payload = self._build_payload(post, match)
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=15)
            # Discord returns 204 No Content on a successful webhook post.
            if response.status_code in (200, 204):
                return True
            print(
                f"[discord] Webhook returned {response.status_code}: "
                f"{response.text[:200]}"
            )
            return False
        except requests.RequestException as exc:
            print(f"[discord] Failed to send message: {exc}")
            return False
