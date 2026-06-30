"""
matcher.py
----------
The "brain" of Client Radar. Given a Reddit post, it decides:

  1. Is someone HIRING (a client with a gig) — not offering their own services?
  2. Is it DEVELOPMENT related?
  3. What is the budget, if any?
  4. Which keywords matched?

Uses a simple scoring system (like lightweight AI filtering) instead of one
keyword accidentally flipping a post to "match".
"""

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Development topic keywords (unchanged categories)
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
        "kotlin", "flutter", "react native", "react-native",
        "xamarin", "ionic", "play store", "app store",
    ],
    "Software Dev": [
        "software developer", "software engineer", "programmer",
        "coder", "coding", "programming", "python", "java ", "c++", "c#",
        "golang", "rust", "automation", "script", "scripting", "bot ",
        "discord bot", "telegram bot", "api", "integration", "scraper",
        "web scraping", "data pipeline", "etl", "saas", "mvp",
    ],
}

# Standalone "developer" only counts when paired with hiring context (see below).
_DEV_ROLE = r"(?:developer|programmer|coder|engineer|dev\b)"

# ---------------------------------------------------------------------------
# Hiring signals — client wants to pay YOU (weighted)
# ---------------------------------------------------------------------------
_HIRING_STRONG = [
    r"\[hiring\]",
    r"\bhiring\b(?!\s+manager)",  # not "hiring manager experience"
    r"looking to hire",
    r"looking for (?:a |an |someone|freelance|remote)",
    r"need (?:a |an |someone to)",
    r"seeking (?:a |an |someone)",
    r"\biso\b",
    r"in search of",
    r"want to hire",
    r"will pay",
    r"willing to pay",
    r"paying \$\d",
    r"budget.{0,20}\$\d",  # "budget $2000" / "budget: $500"
    r"\$\d.{0,30}(?:budget|fixed|project)",
    r"build me (?:a |an )",
    r"develop (?:my |a |an )",
    r"help me build",
    r"someone to build",
    r"client (?:needs|looking|seeking)",
    r"job opening",
    r"freelance (?:project|gig|work) (?:available|needed|posted)",
]

_HIRING_MEDIUM = [
    r"looking for.{0,40}" + _DEV_ROLE,
    r"need.{0,30}" + _DEV_ROLE,
    r"seeking.{0,30}" + _DEV_ROLE,
    r"hire (?:a |an )",
    r"contract (?:work|position|role)",
    r"project (?:needs|requires|looking)",
]

# ---------------------------------------------------------------------------
# Offering signals — freelancer advertising themselves (weighted negative)
# ---------------------------------------------------------------------------
_OFFER_STRONG = [
    r"^\s*\[?\s*for\s*hire\s*\]?",  # title starts with [For Hire]
    r"\[for hire\]",
    r"\[forhire\]",
    r"\[available\]",
    r"\[offer\]",
    r"\[task\]",  # slavelabour: person offering to do tasks
    r"\bhire me\b",
    r"\bfor hire\b",
    r"available for hire",
    r"offering my services",
    r"offering services",
    r"i am available",
    r"i'm available",
    r"im available",
    r"open for (?:work|projects|freelance)",
    r"looking for (?:work|clients|projects|gigs)",
    r"seeking (?:work|clients|projects|gigs)",
    r"my (?:rate|rates|portfolio|services|skills)",
    r"years? of experience",
    r"dm me(?: for)?",
    r"pm me(?: for)?",
    r"message me(?: for)?",
    r"contact me(?: for)?",
    r"i (?:can |will )build",
    r"i (?:am |'m )(?:a |an )?(?:experienced |senior |full)",
    r"experienced (?:developer|engineer|programmer|designer)",
]

_OFFER_MEDIUM = [
    r"portfolio",
    r"resume",
    r"cv available",
    r"rate(?:s)? (?:is|are|start)",
    r"\$\d+\s*/?\s*hr",  # "$50/hr" in offering context (their rate)
    r"hourly rate",
    r"clients welcome",
    r"take on (?:new )?projects",
    r"freelancer (?:here|available)",
]

# Phrases that look like hiring but are actually freelancers talking
_FALSE_HIRING = [
    r"hiring manager",
    r"experience (?:with |in )?hiring",
    r"paying clients",
    r"paid (?:internship|course|version)",
]

_BUDGET_PATTERNS = [
    re.compile(
        r"(?:[$€£]|usd|eur|gbp)\s?\d[\d,]*\.?\d*\s?k?(?:\s?/?\s?(?:hr|hour|month|mo|project|fixed))?",
        re.IGNORECASE,
    ),
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
    hiring_score: int = 0
    offering_score: int = 0
    reject_reason: str = ""

    @property
    def primary_type(self) -> str:
        return self.categories[0] if self.categories else "TBD"


def _normalize(text: str) -> str:
    return f" {text.lower()} "


def _count_patterns(text: str, patterns: list[str]) -> int:
    hits = 0
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            hits += 1
    return hits


def _title_offer_tag(title: str) -> bool:
    """True when the title is clearly a [For Hire] style post."""
    t = title.strip().lower()
    return bool(
        re.match(r"^[\[\(]?\s*(?:for\s*hire|forhire|available|offering)\s*[\]\)]?", t)
        or re.match(r"^for hire\b", t)
    )


def _title_hire_tag(title: str) -> bool:
    """True when the title starts with [Hiring] or similar tag — not 'hiring manager'."""
    t = title.strip().lower()
    return bool(
        re.match(r"^[\[\(]\s*hiring\s*[\]\)]", t)  # [Hiring] or (Hiring)
        or re.match(r"^hiring\s*[\]\):\-–]", t)  # Hiring: or Hiring -
    )


def _find_budget(text: str) -> str:
    for pattern in _BUDGET_PATTERNS:
        match = pattern.search(text)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return "TBD"


def _match_topics(haystack: str) -> tuple[list[str], list[str]]:
    matched_keywords: list[str] = []
    categories: list[str] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        category_hit = False
        for kw in keywords:
            if kw in haystack:
                matched_keywords.append(kw.strip())
                category_hit = True
        if category_hit:
            categories.append(category)

    # "developer" alone is too broad — only count with hiring-ish context nearby
    if "developer" in haystack or " dev " in haystack:
        if re.search(
            r"(?:need|seeking|looking for|hire|hiring|iso).{0,50}(?:developer|dev\b)"
            r"|(?:developer|dev\b).{0,50}(?:needed|wanted|required)",
            haystack,
        ):
            if "developer" not in matched_keywords:
                matched_keywords.append("developer")
            if "Software Dev" not in categories:
                categories.append("Software Dev")

    seen: set[str] = set()
    unique_keywords = []
    for kw in matched_keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)

    return categories, unique_keywords


def analyze(title: str, body: str = "", link_flair: str = "") -> MatchResult:
    """
    Decide if a post is a client hiring a developer (not someone offering services).
    """
    title = title or ""
    body = body or ""
    flair = link_flair or ""

    title_norm = title.strip().lower()
    full_text = f"{flair} {title} {body}"
    haystack = _normalize(full_text)

    categories, matched_keywords = _match_topics(haystack)
    has_topic = len(categories) > 0

    # --- Fast path: title tags (most Reddit job posts use these) ---
    if _title_offer_tag(title) and not _title_hire_tag(title):
        return MatchResult(
            is_match=False,
            matched_keywords=matched_keywords,
            categories=categories,
            budget=_find_budget(full_text),
            reject_reason="title is [For Hire] — someone offering services",
        )

    if _title_hire_tag(title) and has_topic:
        return MatchResult(
            is_match=True,
            matched_keywords=matched_keywords,
            categories=categories,
            budget=_find_budget(full_text),
            hiring_score=10,
            offering_score=0,
        )

    # --- Scoring pass for untagged or ambiguous posts ---
    hiring_score = _count_patterns(haystack, _HIRING_STRONG) * 3
    hiring_score += _count_patterns(haystack, _HIRING_MEDIUM) * 2

    offering_score = _count_patterns(haystack, _OFFER_STRONG) * 3
    offering_score += _count_patterns(haystack, _OFFER_MEDIUM) * 2

    # Cancel false hiring signals
    if _count_patterns(haystack, _FALSE_HIRING):
        hiring_score = max(0, hiring_score - 3)

    # First-person "I build websites" is almost always a freelancer pitch
    if re.search(r"\bi(?:'m| am) (?:a |an )?(?:\w+ ){0,3}(?:developer|engineer|designer|freelancer)", haystack):
        offering_score += 4

    # Need clear hiring lead AND not dominated by offering signals
    is_match = (
        has_topic
        and hiring_score >= 3
        and hiring_score > offering_score
        and offering_score < 6
    )

    reject_reason = ""
    if not is_match and has_topic:
        if offering_score >= hiring_score:
            reject_reason = "reads like someone offering services, not hiring"
        elif hiring_score < 3:
            reject_reason = "no clear hiring intent"
        elif offering_score >= 6:
            reject_reason = "too many freelancer/offering signals"

    return MatchResult(
        is_match=is_match,
        matched_keywords=matched_keywords,
        categories=categories,
        budget=_find_budget(full_text),
        hiring_score=hiring_score,
        offering_score=offering_score,
        reject_reason=reject_reason,
    )
