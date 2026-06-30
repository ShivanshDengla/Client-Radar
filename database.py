"""
database.py
-----------
A tiny SQLite layer whose only job is to remember which Reddit posts we have
already notified about, so we never send the same post to Discord twice.

We store the Reddit post ID (a short unique string like "1abcd23") plus a few
helpful columns for debugging / future features.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


class SeenPostsDB:
    def __init__(self, path: str):
        self.path = path
        self._create_table()

    @contextmanager
    def _connect(self):
        """Open a connection, commit on success, and always close it."""
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _create_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_posts (
                    post_id      TEXT PRIMARY KEY,
                    subreddit    TEXT,
                    title        TEXT,
                    notified_at  TEXT
                )
                """
            )

    def has_seen(self, post_id: str) -> bool:
        """Return True if we have already recorded this post ID."""
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT 1 FROM seen_posts WHERE post_id = ? LIMIT 1", (post_id,)
            )
            return cur.fetchone() is not None

    def mark_seen(self, post_id: str, subreddit: str, title: str) -> None:
        """Record a post ID so it is never notified again."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            # INSERT OR IGNORE means: if the post_id already exists, do nothing
            # (no crash). This makes the operation safe to call repeatedly.
            conn.execute(
                """
                INSERT OR IGNORE INTO seen_posts (post_id, subreddit, title, notified_at)
                VALUES (?, ?, ?, ?)
                """,
                (post_id, subreddit, title, now),
            )

    def count(self) -> int:
        """Return how many posts we have remembered (handy for logging)."""
        with self._connect() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM seen_posts")
            return cur.fetchone()[0]
