"""
matcher.py
----------
Filters Reddit posts for YOUR profile: web dev, app dev, and scripts/automation.

Only sends posts where a CLIENT is hiring for dev work — not discussions,
news, advice threads, or freelancers looking for gigs.
"""

import re
from dataclasses import dataclass, field

# Subreddits that exist mainly for job posts — slightly more permissive.
HIRING_BOARD_SUBS = frozenset({
    "forhire", "jobbit", "slavelabour", "freelance_forhire",
    "donedirtcheap", "freelanceprogramming", "hireaprogrammer",
})

# ---------------------------------------------------------------------------
# YOUR profile — a post must match at least one of these to qualify.
# (Loose platform words like "api" or "saas" alone are NOT enough.)
# ---------------------------------------------------------------------------
PROFILE_KEYWORDS: dict[str, list[str]] = {
    "Web Dev": [
        "web developer", "web dev", "website", "web app", "webapp", "web site",
        "frontend", "front-end", "front end", "backend", "back-end", "back end",
        "full stack", "fullstack", "full-stack", "fullstack developer",
        "react", "next.js", "nextjs", "vue", "angular", "svelte",
        "node.js", "nodejs", "express", "laravel", "django", "flask", "rails",
        "html", "css", "tailwind", "javascript", "typescript",
        "php", "wordpress", "shopify", "webflow", "landing page",
        "e-commerce", "ecommerce", "cms",
    ],
    "App Dev": [
        "app developer", "app dev", "mobile app", "mobile developer",
        "ios developer", "android developer", "iphone app", "swift developer",
        "kotlin", "flutter", "react native", "react-native",
        "xamarin", "ionic", "play store app", "app store",
    ],
    "Software Dev": [
        "software developer", "software engineer", "programmer",
        "python developer", "python script", "automation", "automate",
        "script", "scripting", "discord bot", "telegram bot",
        "web scraping", "scraper", "scrape", "data pipeline",
        "bot developer", "custom script", "cron job", "workflow automation",
        "integration", "api integration",
    ],
}

# Hires that are NOT your stack — skip even if [Hiring].
NON_DEV_ROLES = [
    "graphic designer", "graphics designer", "ux designer", "ui designer",
    "ui/ux", "ux/ui", "video editor", "video editing", "virtual assistant",
    "va ", "seo specialist", "seo expert", "copywriter", "content writer",
    "social media manager", "marketing manager", "legal opinion", "lawyer",
    "accountant", "bookkeeper", "transcription", "data entry", "moderator",
    "community manager", "illustrator", "3d artist", "animator",
    "voice over", "voiceover", "photographer", "thumbnail",
]

_DEV_ROLE = r"(?:developer|programmer|coder|engineer|dev\b)"
_DELIVERABLE = (
    r"(?:website|web ?site|web ?app|webapp|mobile app|app|script|bot|"
    r"landing page|e-?commerce|shopify|wordpress|platform|dashboard|mvp)"
)

# ---------------------------------------------------------------------------
# Hard reject — discussion, news, advice, showcase (not job posts)
# ---------------------------------------------------------------------------
_NOISE = [
    r"\bi will not promote\b",
    r"\[i will not promote\]",
    r"looking for advice",
    r"bootstrapping",
    r"\bi built\b",
    r"\bi made\b",
    r"\bi created\b",
    r"\bi developed\b",
    r"is this normal",
    r"this week'?s top",
    r"news stories",
    r"^\s*how (?:do|can|should|to|would)\b",
    r"^\s*what (?:is|are|should|blog|app|business)\b",
    r"^\s*why (?:do|are|is|does)\b",
    r"^\s*any (?:tips|advice|suggestions|recommendations)\b",
    r"^\s*is it (?:worth|possible|normal)\b",
    r"^\s*should i\b",
    r"^\s*can i\b",
    r"^\s*does anyone (?:know|else|have)\b",
    r"^\s*has anyone\b",
    r"legal opinion",
    r"how are they not banned",
    r"401 error",
    r"avoid 401",
    r"without termux",
    r"showcase",
    r"side project",
    r"open source",
    r"what business problem",
    r"bring in outside help instead",
    r"people register and add students",
    r"not many pay",
    r"low pay \+ equity",
    r"how do i find (?:startups|jobs|work|clients)",
    r"looking for (?:a |an )?(?:job|work|gigs?|clients|freelance work)",
    r"seeking (?:work|clients|gigs|freelance)",
    r"\(freelancing\)",
    r"freelancing\)",
    r"looking for.{0,40}freelanc",
    r"^\s*an? .{0,60} app to (?:open|view|show)",  # showcase apps
]

# ---------------------------------------------------------------------------
# Hiring intent — client wants to pay a developer
# ---------------------------------------------------------------------------
_HIRING_STRONG = [
    r"\[hiring\]",
    r"\bhiring\b(?!\s+manager)",
    r"looking to hire",
    r"looking for (?:a |an |someone|freelance|remote)",
    r"need(?:s)? (?:a |an |someone to)",
    r"seeking (?:a |an |someone)",
    r"\biso\b",
    r"want to hire",
    r"will pay",
    r"willing to pay",
    r"budget.{0,25}\$\d",
    r"build me (?:a |an |my )",
    r"develop (?:my |a |an )",
    r"help me build",
    r"help (?:me )?(?:build|develop|create|code)",
    r"someone to build",
    r"\bneed(?:s)? (?:a |an )?(?:\w+ ){0,2}" + _DEV_ROLE,
    r"\bneed(?:s)? (?:a |an )?" + _DELIVERABLE,
    r"\blooking for (?:a |an )?(?:\w+ ){0,2}" + _DEV_ROLE,
    r"\blooking for (?:a |an )?" + _DELIVERABLE,
    r"\blooking for someone (?:to |who can )",
    r"\bi need (?:a |an |someone to )",
    r"\bwe need (?:a |an |someone to )",
    r"\bwant(?:s)? (?:a |an )?" + _DELIVERABLE,
    r"\bcan someone (?:build|code|develop|make)",
    r"\bwho can (?:build|code|develop|make)",
]

_OFFER_STRONG = [
    r"^\s*\[?\s*for\s*hire\s*\]?",
    r"\[for hire\]",
    r"\bfor hire\b",
    r"\bhire me\b",
    r"available for hire",
    r"offering my services",
    r"i am available",
    r"i'm available",
    r"open for (?:work|projects|freelance)",
    r"looking for (?:work|clients|projects|gigs)",
    r"my (?:rate|rates|portfolio)",
    r"years? of experience",
    r"i (?:can |will )build",
    r"i (?:am |'m )(?:a |an )?(?:experienced |senior |full)",
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
    return sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))


def _has_hiring_tag(title: str) -> bool:
    return bool(re.search(r"\[hiring\]|\bhiring\s*[\]\):\-–]", title, re.IGNORECASE))


def _title_offer_tag(title: str) -> bool:
    t = title.strip().lower()
    return bool(
        re.match(r"^[\[\(]?\s*(?:for\s*hire|forhire|available|offering)\s*[\]\)]?", t)
        or re.match(r"^for hire\b", t)
        or re.search(r"\[for hire\]", t, re.IGNORECASE)
    )


def _is_non_dev_role(haystack: str) -> bool:
    return any(role in haystack for role in NON_DEV_ROLES)


def _is_noise(title: str, haystack: str) -> str | None:
    title_n = _normalize(title)
    for pattern in _NOISE:
        if re.search(pattern, title_n, re.IGNORECASE):
            return "discussion / advice / showcase — not a job post"
        if re.search(pattern, haystack, re.IGNORECASE):
            return "discussion / advice / showcase — not a job post"
    return None


def _match_profile(haystack: str) -> tuple[list[str], list[str]]:
    """Return categories + keywords that match YOUR dev profile only."""
    matched_keywords: list[str] = []
    categories: list[str] = []
    for category, keywords in PROFILE_KEYWORDS.items():
        hit = False
        for kw in keywords:
            if kw in haystack:
                matched_keywords.append(kw)
                hit = True
        if hit:
            categories.append(category)

    # "need a developer" style without a profile keyword yet
    if not categories and re.search(
        r"(?:need|looking for|seeking|hire|hiring|iso).{0,50}"
        r"(?:developer|programmer|fullstack|full stack|web dev|app dev)",
        haystack,
    ):
        categories.append("Software Dev")
        matched_keywords.append("developer")

    seen: set[str] = set()
    unique: list[str] = []
    for kw in matched_keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return categories, unique


def _hiring_score(haystack: str, title: str) -> int:
    score = _count_patterns(haystack, _HIRING_STRONG) * 3
    score -= _count_patterns(haystack, _OFFER_STRONG) * 4
    if _has_hiring_tag(title):
        score += 8
    return score


def _find_budget(text: str) -> str:
    for pattern in _BUDGET_PATTERNS:
        match = pattern.search(text)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return "TBD"


def analyze(
    title: str,
    body: str = "",
    link_flair: str = "",
    subreddit: str = "",
) -> MatchResult:
    title = title or ""
    body = body or ""
    flair = link_flair or ""
    full_text = f"{flair} {title} {body}".strip()
    haystack = _normalize(full_text)
    sub = (subreddit or "").lower()

    categories, matched_keywords = _match_profile(haystack)
    budget = _find_budget(full_text)

    def reject(reason: str) -> MatchResult:
        return MatchResult(
            is_match=False,
            matched_keywords=matched_keywords,
            categories=categories,
            budget=budget,
            reject_reason=reason,
        )

    # 1) Freelancer offering services
    if _title_offer_tag(title) and not _has_hiring_tag(title):
        return reject("someone offering services ([For Hire])")

    # 2) Discussion / news / advice / showcase
    if noise := _is_noise(title, haystack):
        return reject(noise)

    # 3) Freelancer seeking work (not a client gig)
    if re.search(r"looking for.{0,30}(?:freelanc|work|gigs?|clients)", haystack):
        return reject("freelancer seeking work, not a client hiring")

    # 4) Must match your dev profile
    if not categories:
        return reject("not web / app / script dev work")

    # 5) Non-dev roles (designer, VA, legal, etc.)
    if _is_non_dev_role(haystack) and not re.search(
        r"(?:developer|programmer|fullstack|full stack|engineer|coder)", haystack
    ):
        return reject("not a dev role (design / VA / legal / etc.)")

    hire_score = _hiring_score(haystack, title)
    on_hiring_board = sub in HIRING_BOARD_SUBS

    # 6) Hiring boards: need clear [Hiring] tag OR client hiring language
    if on_hiring_board:
        if _has_hiring_tag(title) or hire_score >= 3:
            return MatchResult(
                is_match=True,
                matched_keywords=matched_keywords,
                categories=categories,
                budget=budget,
                hiring_score=hire_score,
            )
        return reject("hiring board post without clear client hiring intent")

    # 7) Tech/business subs (webdev, startups, SaaS…): much stricter
    #    Must have [Hiring] in title OR unmistakable client voice in title.
    title_n = _normalize(title)
    title_is_client = (
        _has_hiring_tag(title)
        or _count_patterns(title_n, _HIRING_STRONG) >= 1
    )
    if not title_is_client:
        return reject("no hiring intent in title (discussion subreddit)")

    if hire_score < 3:
        return reject("not a clear client job post")

    return MatchResult(
        is_match=True,
        matched_keywords=matched_keywords,
        categories=categories,
        budget=budget,
        hiring_score=hire_score,
    )
