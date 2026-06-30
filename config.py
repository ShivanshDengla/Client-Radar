"""
config.py
---------
Loads all settings from the .env file into one simple object so the rest of
the app never has to touch os.environ directly.

No Reddit account or API keys are required — we use anonymous public RSS feeds.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


class ConfigError(Exception):
    """Raised when a required setting is missing or invalid."""


def _require(name: str) -> str:
    """Return an environment variable or raise a helpful error."""
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(
            f"Missing required setting '{name}'. "
            f"Did you copy .env.example to .env and fill it in?"
        )
    return value


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"Setting '{name}' must be a whole number, got '{raw}'.")


def _get_subreddits() -> list[str]:
    raw = os.getenv("SUBREDDITS", "").strip()
    if not raw:
        raise ConfigError("Missing required setting 'SUBREDDITS'.")
    subs = []
    for part in raw.split(","):
        name = part.strip().lstrip("r/").strip()
        if name:
            subs.append(name)
    if not subs:
        raise ConfigError("'SUBREDDITS' did not contain any valid subreddit names.")
    return subs


@dataclass
class Config:
    discord_webhook_url: str
    subreddits: list[str] = field(default_factory=list)
    post_fetch_limit: int = 25
    poll_interval_seconds: int = 300
    database_path: str = "seen_posts.db"
    user_agent: str = "ClientRadar/1.0 (anonymous RSS monitor; no Reddit account)"


def load_config() -> Config:
    """Build and return a validated Config object."""
    return Config(
        discord_webhook_url=_require("DISCORD_WEBHOOK_URL"),
        subreddits=_get_subreddits(),
        post_fetch_limit=_get_int("POST_FETCH_LIMIT", 25),
        poll_interval_seconds=_get_int("POLL_INTERVAL_SECONDS", 300),
        database_path=os.getenv("DATABASE_PATH", "seen_posts.db").strip()
        or "seen_posts.db",
        user_agent=os.getenv("USER_AGENT", "").strip()
        or "ClientRadar/1.0 (anonymous RSS monitor; no Reddit account)",
    )
