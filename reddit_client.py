"""
reddit_client.py
----------------
Fetches public Reddit posts via anonymous RSS feeds.

No Reddit account, no API keys, no login, no cookies. We only request public
Atom feeds (e.g. reddit.com/r/forhire/new/.rss) with a descriptive User-Agent.
Your Reddit account is never involved.
"""

import html
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

import requests

from config import Config

ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
# Reddit asks automated clients to identify themselves. This is NOT a login.
DEFAULT_USER_AGENT = "ClientRadar/1.0 (anonymous RSS monitor; no Reddit account)"
# Fetch subreddits in small batches so long lists don't break one giant RSS URL.
RSS_BATCH_SIZE = 5
REQUEST_DELAY_SECONDS = 2.5
RETRY_WAIT_SECONDS = 12
MAX_RETRIES = 2


@dataclass
class RedditPost:
    id: str
    subreddit: str
    title: str
    body: str
    flair: str
    url: str
    created_utc: float

    @property
    def permalink(self) -> str:
        return self.url

    def age_human(self) -> str:
        """Return a friendly age string like '2 minutes' or '3 hours'."""
        created = datetime.fromtimestamp(self.created_utc, tz=timezone.utc)
        delta = datetime.now(timezone.utc) - created
        seconds = int(delta.total_seconds())

        if seconds < 0:
            return "just now"
        if seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''}"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        days = hours // 24
        return f"{days} day{'s' if days != 1 else ''}"


def _strip_html(raw: str) -> str:
    """Turn Reddit's HTML content into plain text for keyword matching."""
    text = re.sub(r"<!--.*?-->", " ", raw, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _post_id_from_link(link: str) -> str:
    match = re.search(r"/comments/([a-z0-9]+)/", link, re.IGNORECASE)
    return match.group(1) if match else link


def _subreddit_from_link(link: str) -> str:
    match = re.search(r"/r/([^/]+)/", link, re.IGNORECASE)
    return match.group(1) if match else "unknown"


def _parse_timestamp(raw: str) -> float:
    if not raw:
        return time.time()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(raw).timestamp()
    except (TypeError, ValueError, IndexError):
        return time.time()


def _entry_to_post(entry: ET.Element) -> RedditPost | None:
    link_el = entry.find("a:link", ATOM_NS)
    if link_el is None:
        return None

    link = link_el.get("href", "").strip()
    if not link:
        return None

    title_el = entry.find("a:title", ATOM_NS)
    title = (title_el.text or "").strip() if title_el is not None else ""

    updated_el = entry.find("a:updated", ATOM_NS)
    published_el = entry.find("a:published", ATOM_NS)
    timestamp_raw = ""
    if updated_el is not None and updated_el.text:
        timestamp_raw = updated_el.text
    elif published_el is not None and published_el.text:
        timestamp_raw = published_el.text

    content_el = entry.find("a:content", ATOM_NS)
    body = _strip_html(content_el.text or "") if content_el is not None else ""

    return RedditPost(
        id=_post_id_from_link(link),
        subreddit=_subreddit_from_link(link),
        title=title,
        body=body,
        flair="",  # RSS does not include post flair
        url=link,
        created_utc=_parse_timestamp(timestamp_raw),
    )


class RedditClient:
    def __init__(self, config: Config):
        self.subreddits = config.subreddits
        self.fetch_limit = config.post_fetch_limit
        self.user_agent = config.user_agent
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def _rss_url(self, subreddit_names: list[str]) -> str:
        joined = "+".join(subreddit_names)
        query = urlencode({"limit": self.fetch_limit})
        return f"https://www.reddit.com/r/{joined}/new/.rss?{query}"

    def _fetch_feed(self, url: str) -> list[RedditPost]:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.session.get(url, timeout=20)
                if response.status_code == 429:
                    wait = RETRY_WAIT_SECONDS * (attempt + 1)
                    print(f"[reddit] Rate limited (429). Waiting {wait}s before retry...")
                    time.sleep(wait)
                    continue
                response.raise_for_status()

                root = ET.fromstring(response.content)
                posts: list[RedditPost] = []
                for entry in root.findall("a:entry", ATOM_NS):
                    post = _entry_to_post(entry)
                    if post is not None:
                        posts.append(post)
                return posts
            except requests.RequestException as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_WAIT_SECONDS)
        raise last_error or requests.RequestException("RSS fetch failed")

    def _fetch_batch(self, subreddit_names: list[str]) -> list[RedditPost]:
        """Fetch one batch; on non-rate-limit errors, try each sub slowly."""
        url = self._rss_url(subreddit_names)
        try:
            return self._fetch_feed(url)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                print(f"[reddit] Still rate limited for batch {subreddit_names}. Skipping for now.")
                return []
            print(f"[reddit] Batch RSS failed ({exc}). Trying subs one-by-one (slow).")
        except requests.RequestException as exc:
            print(f"[reddit] Batch RSS failed ({exc}). Trying subs one-by-one (slow).")

        posts: list[RedditPost] = []
        for sub_name in subreddit_names:
            time.sleep(REQUEST_DELAY_SECONDS)
            try:
                posts.extend(self._fetch_feed(self._rss_url([sub_name])))
            except requests.RequestException as sub_exc:
                print(f"[reddit] Could not read r/{sub_name}: {sub_exc}")
        return posts

    def fetch_new_posts(self) -> list[RedditPost]:
        """
        Pull newest posts from configured subreddits via public RSS.

        Fetches in small batches (polite to Reddit, works with long sub lists).
        """
        posts: list[RedditPost] = []
        seen_ids: set[str] = set()

        def add_posts(batch: list[RedditPost]) -> None:
            for post in batch:
                if post.id in seen_ids:
                    continue
                seen_ids.add(post.id)
                posts.append(post)

        for i in range(0, len(self.subreddits), RSS_BATCH_SIZE):
            chunk = self.subreddits[i : i + RSS_BATCH_SIZE]
            add_posts(self._fetch_batch(chunk))
            if i + RSS_BATCH_SIZE < len(self.subreddits):
                time.sleep(REQUEST_DELAY_SECONDS)

        posts.sort(key=lambda p: p.created_utc)
        return posts
