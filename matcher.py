"""
matcher.py
----------
The "brain" of Client Radar. Given a Reddit post, it decides:

  1. Is someone HIRING (intent) and is it DEVELOPMENT related (topic)?
  2. What development category is it (web / app / general software / etc.)?
  3. What is the budget, if any?
  4. Which keywords actually matched (so we can show them in Discord)?

Everything that is missing or unclear is returned as "TBD" so the rest of the
app can display a clean message without crashing on edge cases.
"""

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 1. INTENT: words that suggest the poster wants to HIRE / PAY someone.
#    We need at least one of these for a post to qualify.
# ---------------------------------------------------------------------------
HIRING_INTENT = [
    "[hiring]",
    "hiring",
    "looking for",
    "looking to hire",
    "need a",
    "need an",
    "need someone",
    "seeking",
    "in search of",
    " iso ",
    "want to hire",
    "wanted",
    "will pay",
    "paid",
    "paying",
    "budget",
    "for hire?",  # some posts ask "anyone for hire"
    "build me",
    "develop my",
    "develop a",
    "looking for someone to build",
]

# Posts that are clearly people OFFERING their own services, not hiring.
# If we see these (and no strong hiring signal), we skip the post.
OFFERING_SIGNALS = [
    "[for hire]",
    "[task]",
    "[offer]",
    "offering my services",
    "i am available",
    "i'm available",
    "available for hire",
    "for hire -",
]

# ---------------------------------------------------------------------------
# 2. TOPIC: development categories and the keywords that map to each.
#    The order matters a little: we report all matched categories, but the
#    "primary" type is the first category that has a match.
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Web Dev": [
        "web developer", "web dev", "website", "web app", "webapp", "web site",
        "frontend", "front-end", "front end", "backend", "back-end", "back end",
        "full stack", "fullstack", "full-stack",
        "react", "next.js", "nextjs", "vue", "angular", "svelte",
        "node", "node.js", "nodejs", "express",
        "html", "css", "tailwind", "javascript", "typescript",
        "php", "laravel", "django", "flask", "rails",
        "wordpress", "shopify", "webflow", "wix", "squarespace",
        "landing page", "e-commerce", "ecommerce", "cms",
    ],
    "App Dev": [
        "app developer", "app dev", "mobile app", "mobile developer",
        "ios", "android", "iphone", "swift", "swiftui", "objective-c",
        "kotlin", "java app", "flutter", "react native", "react-native",
        "xamarin", "ionic", "play store", "app store",
    ],
    "Software Dev": [
        "software developer", "software engineer", "developer", "programmer",
        "coder", "coding", "programming", "python", "java ", "c++", "c#",
        "golang", "rust", "automation", "script", "scripting", "bot ",
        "discord bot", "telegram bot", "api", "integration", "scraper",
        "web scraping", "data pipeline", "etl", "saas", "mvp",
    ],
}

# ---------------------------------------------------------------------------
# 3. BUDGET: regular expressions to find money amounts in the text.
# ---------------------------------------------------------------------------
# Matches things like: $2,000  $2000  $50/hr  $1.5k  USD 500  500 usd  €300
_BUDGET_PATTERNS = [
    # $1,000 / $1000.00 / $50/hr / $1.5k  (with optional k / hr suffix)
    re.compile(
        r"(?:[$€£]|usd|eur|gbp)\s?\d[\d,]*\.?\d*\s?k?(?:\s?/?\s?(?:hr|hour|month|mo|project|fixed))?",
        re.IGNORECASE,
    ),
    # 1000 usd / 500 dollars (number first)
    re.compile(
        r"\d[\d,]*\.?\d*\s?(?:usd|eur|gbp|dollars?|euros?)\b",
        re.IGNORECASE,
    ),
]


@dataclass
class MatchResult:
    is_match: bool
    matched_keywords: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    budget: str = "TBD"

    @property
    def primary_type(self) -> str:
        """The headline client type, e.g. 'Web Dev'. 'TBD' if unknown."""
        return self.categories[0] if self.categories else "TBD"


def _normalize(text: str) -> str:
    """Lowercase and pad with spaces so word-boundary-ish checks work."""
    return f" {text.lower()} "


def _find_budget(text: str) -> str:
    """Return the first budget-looking string found, or 'TBD'."""
    for pattern in _BUDGET_PATTERNS:
        match = pattern.search(text)
        if match:
            # Clean up whitespace inside the matched snippet.
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return "TBD"


def analyze(title: str, body: str = "", link_flair: str = "") -> MatchResult:
    """
    Inspect a post's title + body and decide whether it is a relevant
    "client is hiring a developer" opportunity.
    """
    title = title or ""
    body = body or ""
    flair = link_flair or ""

    # Combine everything we know about the post into one searchable blob.
    haystack = _normalize(f"{flair} {title} {body}")

    # --- Step A: is this clearly someone offering services? If so, only keep
    #     it when there is ALSO an explicit hiring word (rare but possible). ---
    looks_like_offer = any(sig in haystack for sig in OFFERING_SIGNALS)

    # --- Step B: hiring intent ---
    has_intent = any(sig in haystack for sig in HIRING_INTENT)

    # --- Step C: development topic + which keywords matched ---
    matched_keywords: list[str] = []
    categories: list[str] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        category_hit = False
        for kw in keywords:
            if kw in haystack:
                # Show a tidy version of the keyword to the user.
                matched_keywords.append(kw.strip())
                category_hit = True
        if category_hit:
            categories.append(category)

    has_topic = len(categories) > 0

    # --- Decision ---
    # Must be development related AND show hiring intent.
    # If it looks like an offer with no intent, reject it.
    is_match = has_topic and has_intent and not (looks_like_offer and not _strong_intent(haystack))

    # De-duplicate matched keywords while preserving order.
    seen = set()
    unique_keywords = []
    for kw in matched_keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)

    return MatchResult(
        is_match=is_match,
        matched_keywords=unique_keywords,
        categories=categories,
        budget=_find_budget(f"{title} {body}"),
    )


def _strong_intent(haystack: str) -> bool:
    """A stricter hiring signal used to override 'looks like an offer'."""
    strong = ["[hiring]", "hiring", "will pay", "budget", "looking to hire"]
    return any(s in haystack for s in strong)
