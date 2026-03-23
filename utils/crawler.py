import asyncio
import os
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse, urlunparse

import aiohttp
from agents import function_tool
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel

try:
    from serpapi import GoogleSearch  # type: ignore
except Exception:  # pragma: no cover
    try:
        from serpapi.google_search import GoogleSearch  # type: ignore
    except Exception:  # pragma: no cover
        GoogleSearch = None

from utils.logger import logger

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

GENERIC_FUNDING_TERMS = {
    "funding",
    "scholarship",
    "scholarships",
    "studentship",
    "studentships",
    "stipend",
    "bursary",
    "bursaries",
    "grant",
    "grants",
    "financial aid",
    "tuition",
    "fee",
    "fees",
    "finance",
    "money support",
    "aid",
    "full-funding",
    "tuition-waiver",
}
GENERIC_QUERY_TERMS = GENERIC_FUNDING_TERMS | {
    "phd",
    "doctoral",
    "doctorate",
    "masters",
    "master",
    "msc",
    "undergraduate",
    "bachelor",
    "international",
    "uk",
}
FUNDING_PREFERENCE_TERMS = {
    "full funding",
    "full-funding",
    "tuition waiver",
    "tuition-waiver",
    "stipend",
    "international",
}
INSTITUTION_HINT_TERMS = {
    "university",
    "college",
    "institute",
    "school",
    "faculty",
    "department",
}

# Base funding keywords
BASE_FUNDING_KEYWORDS = [
    r"ph\.?d",
    r"doctoral",
    r"doctorate",
    r"masters?",
    r"m\.sc",
    r"funding",
    r"scholarship",
    r"studentship",
    r"stipend",
    r"bursary",
    r"grant",
    r"financial aid",
    r"tuition",
    r"fee",
    r"finance",
    r"money support",
    r"aid",
]

FUNDING_URL_PATTERNS = [
    "/funding/",
    "/scholarship/",
    "/financial-aid/",
    "/bursary/",
    "/studentship/",
    "/fees-funding/",
    "/finance/",
    "/grants/",
    "/funding-opportunities/",
    "/scholarships/",
    "/financialsupport/",
    "/pg-research/",
    "/phdfunding/",
]

DOCTORAL_PATH_HINTS = {
    "phd",
    "doctoral",
    "doctorate",
    "pgr",
    "pg research",
    "pg-research",
    "postgraduate research",
    "postgraduate-research",
    "research degree",
    "research degrees",
    "research-degrees",
    "researchdegrees",
}

FUNDING_PATH_HINTS = {
    "funding",
    "fees funding",
    "fees-funding",
    "studentship",
    "studentships",
    "scholarship",
    "scholarships",
    "phd funding",
    "phdfunding",
    "doctoral funding",
    "doctoral-funding",
}

ACADEMIC_HUB_PATH_HINTS = {
    "study",
    "research",
    "graduate school",
    "graduate-school",
    "graduateschool",
    "doctoral college",
    "doctoral-college",
    "postgraduate research",
    "postgraduate-research",
    "pg research",
    "pg-research",
    "research degrees",
    "research-degrees",
    "researchdegrees",
}

MAX_SEED_URLS = 60
MAX_AUXILIARY_SEED_DOMAINS = 3
MAX_TOTAL_INITIAL_QUEUE = 50
MAIN_DOMAIN_SEED_LIMIT = 24
AUXILIARY_DOMAIN_SEED_LIMIT = 8
SEARCH_FALLBACK_URL_LIMIT = 8


class UniversityInput(BaseModel):
    """Strict input schema for formatted crawler batch calls."""

    school: Optional[str] = None
    name: Optional[str] = None
    domain: Optional[str] = None
    domain_url: Optional[str] = None
    url: Optional[str] = None
    domains: Optional[List[str]] = None


class QueryConstraints(BaseModel):
    degree_terms: List[str]
    subject_terms: List[str]
    generic_terms: List[str]
    funding_preference_terms: List[str]


class CrawlQueueItem(BaseModel):
    url: str
    priority: int
    source: str


class PageScoreBreakdown(BaseModel):
    score: int
    is_relevant: bool
    url_suggests_funding: bool
    url_has_custom: bool
    text_matches_funding: bool
    subject_match_count: int
    has_doctoral_terms: bool
    has_taught_only_terms: bool


# ----------------------------
# Keyword Extraction
# ----------------------------
async def extract_keywords_from_query(query: str) -> List[str]:
    """
    Extract relevant academic keywords from user query using AI

    Args:
        query: User's search query

    Returns:
        List of lowercase keywords to prioritize in crawling
    """
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Extract academic field keywords, degree levels, and funding-related terms from the query. Return as a JSON array of lowercase keywords suitable for URL/text matching.",
                },
                {
                    "role": "user",
                    "content": f"""Query: {query}

Extract ALL relevant keywords including:
- Field of study (ANY academic discipline: STEM, humanities, social sciences, arts, etc.)
  Examples: 'machine-learning', 'renaissance-history', 'organic-chemistry', 'public-policy'
- Degree level (e.g., 'phd', 'doctoral', 'masters', 'undergraduate')
- Geographic/status terms (e.g., 'international', 'european', 'domestic')
- Funding-specific terms (e.g., 'full-funding', 'tuition-waiver', 'stipend')

Be comprehensive - include all academic terms, even interdisciplinary ones.

Return format: {{"keywords": ["keyword1", "keyword2", ...]}}""",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        import json

        result = json.loads(response.choices[0].message.content)
        keywords = result.get("keywords", [])
    except Exception as e:
        print(f"⚠️  Keyword extraction failed: {e}, using fallback")
        keywords = []

    # Fallback extraction using regex
    query_lower = query.lower()

    # Extract degree levels
    if any(word in query_lower for word in ["phd", "doctoral", "doctorate"]):
        keywords.extend(["phd", "doctoral", "doctorate"])
    if any(word in query_lower for word in ["master", "master's", "msc", "m.sc"]):
        keywords.extend(["masters", "master", "msc"])
    if any(word in query_lower for word in ["undergraduate", "bachelor", "bachelors"]):
        keywords.extend(["undergraduate", "bachelor"])

    # Extract location/status keywords
    if "international" in query_lower:
        keywords.append("international")
    if any(word in query_lower for word in ["europe", "european", "eu"]):
        keywords.extend(["europe", "european"])

    # Deduplicate and clean
    keywords = list(set(k.lower().strip() for k in keywords if k))

    return keywords


def create_dynamic_keyword_pattern(custom_keywords: List[str]) -> re.Pattern:
    """Create a regex pattern combining base and custom keywords"""
    keyword_variants: List[str] = []
    for kw in custom_keywords:
        keyword_variants.extend(re.escape(variant) for variant in keyword_variants_for_matching(kw))
    all_keywords = BASE_FUNDING_KEYWORDS + keyword_variants
    pattern = r"(" + r"|".join(all_keywords) + r")"
    return re.compile(pattern, re.I)


def keyword_variants_for_matching(keyword: str) -> List[str]:
    cleaned = (keyword or "").strip().lower()
    if not cleaned:
        return []

    variants = {
        cleaned,
        cleaned.replace("-", " "),
        cleaned.replace("_", " "),
        cleaned.replace("-", ""),
        cleaned.replace("_", ""),
    }
    return [variant for variant in variants if variant]


def slugify_path_term(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", normalized_match_text(value))
    return cleaned.strip("-")


def path_variants_for_term(value: str) -> List[str]:
    normalized = normalized_match_text(value)
    slug = slugify_path_term(value)
    squashed = slug.replace("-", "")
    variants = {normalized, slug, squashed}
    return [variant for variant in variants if variant]


def normalized_match_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").lower().replace("-", " ").replace("_", " ")).strip()


def sanitize_text_for_llm(value: str) -> str:
    """Remove control characters that can break downstream model calls."""
    cleaned = value or ""
    cleaned = cleaned.replace("\x00", " ")
    cleaned = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def sanitize_page_payload(page: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize crawler page payloads before caching or returning them."""
    sanitized = dict(page)
    for key in ("title", "preview", "text", "full_text", "page_type", "url"):
        if key in sanitized and sanitized[key] is not None:
            sanitized[key] = sanitize_text_for_llm(str(sanitized[key]))
    return sanitized


def normalize_query_cache_key(query: Optional[str]) -> str:
    return normalized_match_text(query or "")


def is_institution_keyword(keyword: str) -> bool:
    normalized = normalized_match_text(keyword)
    if not normalized:
        return True
    return any(term in normalized.split() for term in INSTITUTION_HINT_TERMS)


def build_query_constraints(query: Optional[str], custom_keywords: List[str]) -> QueryConstraints:
    query_text = normalized_match_text(query or "")
    generic_terms = sorted(
        {term for term in custom_keywords if normalized_match_text(term) in GENERIC_QUERY_TERMS}
    )
    funding_preference_terms = sorted(
        {
            normalized_match_text(term)
            for term in custom_keywords
            if normalized_match_text(term) in FUNDING_PREFERENCE_TERMS
        }
    )

    degree_terms: List[str] = []
    if any(term in query_text for term in ["phd", "doctoral", "doctorate", "doctor of philosophy"]):
        degree_terms.extend(["phd", "doctoral", "doctorate"])
    if any(term in query_text for term in ["master", "masters", "m.sc", "msc"]):
        degree_terms.extend(["masters", "master"])
    if any(term in query_text for term in ["undergraduate", "bachelor"]):
        degree_terms.extend(["undergraduate", "bachelor"])

    subject_terms = []
    for keyword in custom_keywords:
        normalized = normalized_match_text(keyword)
        if (
            not normalized
            or normalized in GENERIC_QUERY_TERMS
            or normalized in FUNDING_PREFERENCE_TERMS
            or is_institution_keyword(normalized)
        ):
            continue
        subject_terms.append(normalized)

    # Fall back to query tokens if keyword extraction missed obvious subject phrases.
    if not subject_terms and query_text:
        for chunk in re.split(r"\bor\b|\band\b|,", query_text):
            chunk = chunk.strip()
            if not chunk or is_institution_keyword(chunk):
                continue
            if any(
                degree in chunk
                for degree in ["phd", "doctoral", "doctorate", "master", "undergraduate"]
            ):
                continue
            if any(
                term in chunk
                for term in ["artificial intelligence", "machine learning", "computer science"]
            ):
                if chunk not in {"uk", "usa", "us"}:
                    subject_terms.append(chunk)

    deduped_subject_terms = sorted(set(subject_terms), key=len, reverse=True)
    deduped_degree_terms = sorted(set(degree_terms))

    return QueryConstraints(
        degree_terms=deduped_degree_terms,
        subject_terms=deduped_subject_terms,
        generic_terms=generic_terms,
        funding_preference_terms=funding_preference_terms,
    )


def should_keep_page_for_query(
    url: str,
    text: str,
    constraints: QueryConstraints,
) -> bool:
    if not constraints.degree_terms and not constraints.subject_terms:
        return True

    match_text = normalized_match_text(f"{url} {text}")
    has_subject_match = any(term in match_text for term in constraints.subject_terms)
    has_doctoral_match = any(
        term in match_text
        for term in ["phd", "doctoral", "doctorate", "doctoral college", "research degree"]
    )
    has_research_funding_hub_match = any(
        term in match_text
        for term in [
            "research funding",
            "postgraduate research",
            "doctoral funding",
            "studentship",
            "studentships",
            "doctoral college",
        ]
    )
    has_taught_only_match = any(
        term in match_text
        for term in ["postgraduate taught", "masters", "master's", "undergraduate"]
    )

    if (
        "phd" in constraints.degree_terms
        or "doctoral" in constraints.degree_terms
        or "doctorate" in constraints.degree_terms
    ):
        if has_subject_match and has_doctoral_match:
            return True
        if has_subject_match and not has_taught_only_match:
            return True
        if has_doctoral_match and has_research_funding_hub_match:
            return True
        if has_research_funding_hub_match and not has_taught_only_match:
            return True
        if has_doctoral_match and not constraints.subject_terms:
            return True
        return False

    if constraints.subject_terms and not has_subject_match:
        return False

    return True


def explain_page_filter_decision(
    url: str,
    text: str,
    constraints: QueryConstraints,
) -> tuple[bool, str]:
    if not constraints.degree_terms and not constraints.subject_terms:
        return True, "no specific degree/subject constraints"

    match_text = normalized_match_text(f"{url} {text}")
    has_subject_match = any(term in match_text for term in constraints.subject_terms)
    has_doctoral_match = any(
        term in match_text
        for term in ["phd", "doctoral", "doctorate", "doctoral college", "research degree"]
    )
    has_research_funding_hub_match = any(
        term in match_text
        for term in [
            "research funding",
            "postgraduate research",
            "doctoral funding",
            "studentship",
            "studentships",
            "doctoral college",
        ]
    )
    has_taught_only_match = any(
        term in match_text
        for term in ["postgraduate taught", "masters", "master's", "undergraduate"]
    )

    if any(term in constraints.degree_terms for term in ["phd", "doctoral", "doctorate"]):
        if has_subject_match and has_doctoral_match:
            return True, "subject + doctoral match"
        if has_subject_match and not has_taught_only_match:
            return True, "subject match on a non-taught page"
        if has_doctoral_match and has_research_funding_hub_match:
            return True, "doctoral research funding hub"
        if has_research_funding_hub_match and not has_taught_only_match:
            return True, "research funding hub"
        if has_taught_only_match:
            return False, "taught-only or undergraduate page"
        if constraints.subject_terms and not has_subject_match:
            return False, "missing requested subject terms"
        if not has_doctoral_match and not has_research_funding_hub_match:
            return False, "missing doctoral or research funding signals"
        return False, "did not satisfy PhD query filter"

    if constraints.subject_terms and not has_subject_match:
        return False, "missing requested subject terms"

    return True, "passed general query filter"


def generate_seed_urls(domain_url: str, constraints: QueryConstraints) -> List[tuple[str, int]]:
    """Generate high-priority university URLs that are likely to contain doctoral funding."""
    parsed = urlparse(normalize_url(domain_url))
    base = f"{parsed.scheme}://{parsed.netloc}"

    seed_scores: Dict[str, int] = {}

    def add_seed(path: str, priority: int) -> None:
        normalized_path = "/" + path.strip().strip("/")
        if normalized_path == "/":
            return
        existing = seed_scores.get(normalized_path, -(10**9))
        if priority > existing:
            seed_scores[normalized_path] = priority

    core_paths = {
        "/study/funding": 250,
        "/study/funding/postgraduate": 245,
        "/study/funding/postgraduate-research": 245,
        "/study/postgraduate-research": 240,
        "/study/pg-research": 240,
        "/research": 180,
        "/research/degrees": 225,
        "/doctoral-college": 225,
        "/graduateschool": 210,
        "/study": 140,
    }
    for path, priority in core_paths.items():
        add_seed(path, priority)

    has_doctoral_query = any(
        term in constraints.degree_terms for term in ["phd", "doctoral", "doctorate"]
    )
    if has_doctoral_query:
        doctoral_priority_paths = {
            "/study/funding/postgraduate-research/funding": 260,
            "/study/pg-research/funding": 260,
            "/study/pg-research/funding/phdfunding": 280,
            "/study/pg-research/funding/phd-funding": 275,
            "/study/funding/award": 205,
            "/research/degrees/funding": 260,
            "/research/degrees/doctoral": 255,
            "/doctoral-college/funding": 255,
        }
        for path, priority in doctoral_priority_paths.items():
            add_seed(path, priority)

        doctoral_hubs = sorted(
            {slugify_path_term(term) for term in DOCTORAL_PATH_HINTS if slugify_path_term(term)}
        )
        funding_hubs = sorted(
            {slugify_path_term(term) for term in FUNDING_PATH_HINTS if slugify_path_term(term)}
        )
        academic_hubs = sorted(
            {slugify_path_term(term) for term in ACADEMIC_HUB_PATH_HINTS if slugify_path_term(term)}
        )

        for hub in academic_hubs:
            add_seed(f"/{hub}", 180)

        for doctoral in doctoral_hubs:
            add_seed(f"/{doctoral}", 210)
            add_seed(f"/study/{doctoral}", 225)
            add_seed(f"/research/{doctoral}", 225)
            for funding in funding_hubs:
                add_seed(f"/study/{doctoral}/{funding}", 240)
                add_seed(f"/research/{doctoral}/{funding}", 235)
                add_seed(f"/{doctoral}/{funding}", 220)

        for hub in academic_hubs:
            for funding in funding_hubs:
                add_seed(f"/{hub}/{funding}", 210)

    subject_path_hints = {
        "machine learning": [
            "/computer-science",
            "/data-science",
            "/ai",
            "/artificial-intelligence",
        ],
        "artificial intelligence": [
            "/computer-science",
            "/data-science",
            "/ai",
            "/artificial-intelligence",
        ],
        "computer science": [
            "/computer-science",
            "/computerscience",
            "/engineering/computer-science",
        ],
    }
    for subject in constraints.subject_terms:
        for suffix in subject_path_hints.get(subject, []):
            add_seed(suffix, 235)
            add_seed(f"/study{suffix}", 240)
            add_seed(f"/research{suffix}", 240)
            if has_doctoral_query:
                add_seed(f"/study/pg-research{suffix}", 250)
                add_seed(f"/research/degrees{suffix}", 250)

        for variant in path_variants_for_term(subject):
            if not variant:
                continue
            add_seed(f"/{variant}", 190)
            add_seed(f"/study/{variant}", 210)
            add_seed(f"/research/{variant}", 210)
            if has_doctoral_query:
                add_seed(f"/study/pg-research/{variant}", 235)
                add_seed(f"/study/postgraduate-research/{variant}", 235)
                add_seed(f"/research/degrees/{variant}", 230)
                add_seed(f"/doctoral-college/{variant}", 225)

    ranked_seed_paths = sorted(seed_scores.items(), key=lambda item: (-item[1], item[0]))
    seeded: List[tuple[str, int]] = []
    for path, priority in ranked_seed_paths[:MAX_SEED_URLS]:
        seeded.append((normalize_url(urljoin(base, path)), priority))

    return seeded


def build_initial_queue(
    domain_url: str, constraints: QueryConstraints, max_seed_urls: int = MAX_SEED_URLS
) -> List[CrawlQueueItem]:
    queue = [CrawlQueueItem(url=normalize_url(domain_url), priority=0, source="root")]
    queue.extend(
        CrawlQueueItem(url=seeded_url, priority=priority, source="seed")
        for seeded_url, priority in generate_seed_urls(domain_url, constraints)[:max_seed_urls]
    )
    return queue


def pop_next_batch(
    queue: List[CrawlQueueItem],
    visited: Set[str],
    queued_urls: Set[str],
    batch_size: int = 5,
    required_seed_visits_remaining: int = 0,
) -> List[CrawlQueueItem]:
    queue.sort(key=lambda item: item.priority, reverse=True)

    batch: List[CrawlQueueItem] = []
    while queue and len(batch) < batch_size and required_seed_visits_remaining > 0:
        seed_index = next((i for i, item in enumerate(queue) if item.source == "seed"), None)
        if seed_index is None:
            break
        item = queue.pop(seed_index)
        queued_urls.discard(item.url)
        if item.url in visited:
            continue
        visited.add(item.url)
        batch.append(item)
        required_seed_visits_remaining -= 1

    while queue and len(batch) < batch_size:
        item = queue.pop(0)
        queued_urls.discard(item.url)
        if item.url in visited:
            continue
        visited.add(item.url)
        batch.append(item)

    return batch


def score_link_priority(
    link: str, custom_keywords: List[str], constraints: Optional[QueryConstraints] = None
) -> int:
    priority = 0

    if any(pattern in link.lower() for pattern in FUNDING_URL_PATTERNS):
        priority += 100

    priority += calculate_funding_depth(link) * 20

    normalized_link = normalized_match_text(link)
    for kw in custom_keywords:
        if any(variant in normalized_link for variant in keyword_variants_for_matching(kw)):
            priority += 10

    if constraints:
        if any(term in constraints.degree_terms for term in ["phd", "doctoral", "doctorate"]):
            if any(term in normalized_link for term in DOCTORAL_PATH_HINTS):
                priority += 80
            if any(term in normalized_link for term in FUNDING_PATH_HINTS):
                priority += 60
            if any(term in normalized_link for term in ACADEMIC_HUB_PATH_HINTS):
                priority += 30
        if any(term in normalized_link for term in constraints.subject_terms):
            priority += 40

    return priority


def build_page_payload(
    url: str,
    title: str,
    text: str,
    relevance_score: int,
    score_breakdown: PageScoreBreakdown,
    crawl_source: str,
    page_type: str = "funding_page",
) -> Dict[str, Any]:
    full_text = text[:2000]
    preview_text = text[:700]
    payload = {
        "url": url,
        "title": title or "No title",
        "preview": preview_text,
        "text": preview_text,
        "full_text": full_text,
        "page_type": page_type,
        "relevance_score": relevance_score,
        "score_breakdown": score_breakdown.model_dump(),
        "crawl_source": crawl_source,
    }
    return sanitize_page_payload(payload)


def select_final_candidates(
    results: List[Dict[str, Any]],
    query_constraints: QueryConstraints,
    min_relevance_score: int,
    max_results: int,
) -> tuple[List[Dict[str, Any]], List[tuple[str, str]]]:
    prefiltered_results = [r for r in results if r.get("relevance_score", 0) >= min_relevance_score]

    filtered_results: List[Dict[str, Any]] = []
    dropped_results: List[tuple[str, str]] = []
    for result in prefiltered_results:
        keep, reason = explain_page_filter_decision(
            str(result.get("url", "")),
            str(result.get("full_text", "") or result.get("text", "")),
            query_constraints,
        )
        if keep:
            filtered_results.append(result)
        else:
            dropped_results.append((str(result.get("url", "")), reason))

    deduped_results: Dict[str, Dict[str, Any]] = {}
    for result in filtered_results:
        normalized_result_url = normalize_url(str(result.get("url", "")))
        existing = deduped_results.get(normalized_result_url)
        if existing is None or result.get("relevance_score", 0) > existing.get(
            "relevance_score", 0
        ):
            deduped_results[normalized_result_url] = result

    final_results = list(deduped_results.values())
    final_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return final_results[:max_results], dropped_results


# ----------------------------
# Async Utilities
# ----------------------------
async def fetch(session: aiohttp.ClientSession, url: str, timeout: int = 15):
    """Fetch a single URL"""
    try:
        async with session.get(url, headers=HEADERS, timeout=timeout) as r:
            content_type = r.headers.get("content-type", "").lower()
            if r.status == 200 and (
                "text/html" in content_type or "application/xhtml+xml" in content_type
            ):
                return await r.text()
            logger.debug(
                "Skipping %s due to status/content-type mismatch: status=%s content_type=%s",
                url,
                r.status,
                content_type,
            )
    except Exception as exc:
        logger.debug("Fetch failed for %s: %s", url, exc)
        return None
    return None


def normalize_url(url: str) -> str:
    """
    Normalize URL to prevent duplicate fetching.
    - Removes fragments (#section)
    - Removes trailing slashes (except for root)
    - Converts to lowercase
    - Removes default ports
    """
    parsed = urlparse(url)
    # Remove fragment
    scheme = parsed.scheme.lower() or "https"
    if scheme == "http":
        scheme = "https"
    normalized = urlunparse(
        (
            scheme,
            parsed.netloc.lower().replace(":80", "").replace(":443", ""),
            parsed.path.rstrip("/") or "/",  # Keep / for root, remove trailing / otherwise
            parsed.params,
            parsed.query,
            "",  # Remove fragment
        )
    )
    return normalized


def get_base_domain(url: str) -> str:
    """
    Extract base domain (netloc) from URL for caching purposes.
    This ensures all URLs from the same domain share the same cache.
    """
    parsed = urlparse(url)
    base = parsed.netloc.lower().replace(":80", "").replace(":443", "")
    # Remove 'www.' prefix for consistency (www.example.com = example.com)
    if base.startswith("www."):
        base = base[4:]
    return base


def get_domain_scope(url: str) -> str:
    """
    Return a university-wide crawl/cache scope.

    For subdomains like ``financialaid.oregonstate.edu`` this returns
    ``oregonstate.edu`` so the crawler can move between departmental and
    scholarship hosts that belong to the same university.
    """
    base = get_base_domain(url)
    if not base:
        return ""

    parts = base.split(".")
    if len(parts) <= 2:
        return base

    # Handle common academic/public suffixes such as *.ac.uk.
    if parts[-2:] == ["ac", "uk"] and len(parts) >= 3:
        return ".".join(parts[-3:])

    # Default to the registrable domain for common university hosts.
    return ".".join(parts[-2:])


def generate_auxiliary_seed_domains(domain_url: str) -> List[str]:
    """Generate a small set of likely university subdomains worth probing."""
    normalized = normalize_url(domain_url)
    parsed = urlparse(normalized)
    scope = get_domain_scope(normalized)
    if not scope:
        return []

    current_host = parsed.netloc.lower().replace(":80", "").replace(":443", "")
    candidate_prefixes = [
        "ask",
        "scholarships",
        "funding",
        "finance",
        "financialaid",
        "research",
        "graduate",
        "graduateschool",
    ]

    auxiliary_domains: List[str] = []
    seen: Set[str] = set()
    for prefix in candidate_prefixes:
        host = f"{prefix}.{scope}"
        if host == current_host:
            continue
        url = f"{parsed.scheme}://{host}"
        if url not in seen:
            auxiliary_domains.append(url)
            seen.add(url)
    return auxiliary_domains


def search_fallback_urls(
    domain_url: str, user_query: Optional[str], constraints: QueryConstraints
) -> List[Dict[str, str]]:
    """Use site-restricted search to find likely funding pages when structural crawl is weak."""
    if GoogleSearch is None or not SERPAPI_KEY:
        return []

    scope = get_domain_scope(domain_url)
    if not scope:
        return []

    subject_terms = constraints.subject_terms[:2]
    degree_terms = constraints.degree_terms[:2] or ["phd", "doctoral"]
    query_variants = [
        f"site:{scope} {' '.join(degree_terms)} funding",
        f"site:{scope} {' '.join(degree_terms)} scholarship",
    ]
    if subject_terms:
        query_variants.append(f"site:{scope} {' '.join(subject_terms)} {' '.join(degree_terms)}")
        query_variants.append(
            f"site:{scope} {' '.join(subject_terms)} funding scholarship research"
        )
    if user_query:
        query_variants.append(f"site:{scope} {user_query}")

    url_entries: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for query in query_variants[:4]:
        try:
            search = GoogleSearch({"q": query, "api_key": SERPAPI_KEY, "num": 5})
            results = search.get_dict()
        except Exception as exc:
            logger.debug("Fallback search failed for %s: %s", query, exc)
            continue

        for result in results.get("organic_results", []) or []:
            link = normalize_url(str(result.get("link", "") or ""))
            if not link or get_domain_scope(link) != scope or link in seen:
                continue
            seen.add(link)
            url_entries.append(
                {
                    "url": link,
                    "title": sanitize_text_for_llm(str(result.get("title", "") or "")),
                    "snippet": sanitize_text_for_llm(str(result.get("snippet", "") or "")),
                }
            )
            if len(url_entries) >= SEARCH_FALLBACK_URL_LIMIT:
                return url_entries

    return url_entries


def extract_links(html: str, base_url: str) -> List[str]:
    """Extract all internal links from HTML"""
    soup = BeautifulSoup(html, "lxml")
    base = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(base_url))
    base_scope = get_domain_scope(base_url)
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        absolute = urljoin(base, href)
        if get_domain_scope(absolute) == base_scope:
            # Normalize the URL before adding
            normalized = normalize_url(absolute)
            links.append(normalized)

    # Remove duplicates
    return list(set(links))


def is_funding_relevant(
    url: str,
    text: str,
    keyword_pattern: re.Pattern,
    custom_keywords: List[str],
    constraints: QueryConstraints,
) -> PageScoreBreakdown:
    """
    Determine if page is funding-related and calculate relevance score

    Returns:
        (is_relevant, relevance_score)
    """
    # URL check
    url_suggests_funding = any(pattern in url.lower() for pattern in FUNDING_URL_PATTERNS)
    normalized_url = normalized_match_text(url)
    normalized_text = normalized_match_text(text)
    url_has_custom = any(
        variant in normalized_url
        for kw in custom_keywords
        for variant in keyword_variants_for_matching(kw)
    )

    # Text check
    text_matches_funding = bool(keyword_pattern.search(text))

    # Calculate relevance score
    score = 0
    if url_suggests_funding:
        score += 10
    if url_has_custom:
        score += 5
    if text_matches_funding:
        score += 3

    # Count custom keyword occurrences
    subject_match_count = 0
    for kw in custom_keywords:
        variants = keyword_variants_for_matching(kw)
        variant_hits = (
            max(normalized_text.count(variant) for variant in variants) if variants else 0
        )
        if normalized_match_text(kw) in constraints.subject_terms:
            if variant_hits:
                subject_match_count += 1
            score += variant_hits * 12
        else:
            score += variant_hits * 2

    if subject_match_count:
        score += subject_match_count * 25

    if any(term in constraints.degree_terms for term in ["phd", "doctoral", "doctorate"]):
        if any(
            term in normalized_text
            for term in ["phd", "doctoral", "doctorate", "doctoral college", "research degree"]
        ):
            score += 30
        if any(
            term in normalized_text
            for term in ["postgraduate taught", "undergraduate", "master's", "masters"]
        ):
            score -= 35

    if constraints.subject_terms and not any(
        term in normalized_text for term in constraints.subject_terms
    ):
        score -= 20

    if any(term in normalized_url for term in ["undergraduate", "postgraduatetaught"]):
        score -= 20

    has_doctoral_terms = any(
        term in normalized_text
        for term in ["phd", "doctoral", "doctorate", "doctoral college", "research degree"]
    )
    has_taught_only_terms = any(
        term in normalized_text
        for term in ["postgraduate taught", "undergraduate", "master's", "masters"]
    )
    is_relevant = score >= 3  # Threshold for relevance

    return PageScoreBreakdown(
        score=score,
        is_relevant=is_relevant,
        url_suggests_funding=url_suggests_funding,
        url_has_custom=url_has_custom,
        text_matches_funding=text_matches_funding,
        subject_match_count=subject_match_count,
        has_doctoral_terms=has_doctoral_terms,
        has_taught_only_terms=has_taught_only_terms,
    )


# Global cache to prevent re-crawling the same domain in the same session
_crawled_domains_cache: Dict[str, Dict[str, List[Dict[str, object]]]] = {}


def get_cached_crawl_payload(
    domain_url: str, user_query: Optional[str] = None
) -> Dict[str, List[Dict[str, object]]]:
    """Return sanitized cached crawl results for a domain/query pair if available."""
    domain_scope = get_domain_scope(domain_url)
    cache_key = f"{domain_scope}:{normalize_query_cache_key(user_query)}"
    cached = _crawled_domains_cache.get(cache_key, {})
    return {
        "funding_pages": [sanitize_page_payload(page) for page in cached.get("funding_pages", [])],
        "candidate_pages": [
            sanitize_page_payload(page) for page in cached.get("candidate_pages", [])
        ],
    }


async def _crawl_university_funding_impl(
    domain_url: str,
    user_query: Optional[str] = None,
    precomputed_keywords: Optional[List[str]] = None,
    extra_seed_domains: Optional[List[str]] = None,
    max_pages: int = 100,
    max_results: int = 40,  # Return up to 40 results
    min_relevance_score: int = 5,  # Minimum score threshold
) -> Dict[str, List[Dict[str, object]]]:
    """
    Crawl a university domain to find funding pages.

    This function caches results per domain to prevent duplicate crawling.
    If the same domain is requested again, returns cached results.
    """
    # Use university-wide domain scope for cache key so related subdomains share results.
    domain_scope = get_domain_scope(domain_url)
    cache_key = f"{domain_scope}:{normalize_query_cache_key(user_query)}"

    # Check cache first
    if cache_key in _crawled_domains_cache:
        logger.warning(
            f"⚠️  DUPLICATE CRAWL ATTEMPT: {domain_url} "
            f"(scope {domain_scope} already crawled - using cache)"
        )
        logger.info(
            f"♻️  Using cached results for {domain_url} (scope {domain_scope} already crawled)"
        )
        cached = _crawled_domains_cache[cache_key]
        return {
            "funding_pages": [
                sanitize_page_payload(page) for page in cached.get("funding_pages", [])
            ],
            "candidate_pages": [
                sanitize_page_payload(page) for page in cached.get("candidate_pages", [])
            ],
        }

    custom_keywords = precomputed_keywords or []
    if not custom_keywords and user_query:
        custom_keywords = await extract_keywords_from_query(user_query)
    if custom_keywords:
        logger.info(f"🎯 Extracted keywords for {domain_url}: {', '.join(custom_keywords)}")

    keyword_pattern = create_dynamic_keyword_pattern(custom_keywords)
    query_constraints = build_query_constraints(user_query, custom_keywords)
    logger.info(
        "🧭 Query constraints for %s | degree_terms=%s | subject_terms=%s | funding_preferences=%s | generic_terms=%s",
        domain_url,
        query_constraints.degree_terms,
        query_constraints.subject_terms,
        query_constraints.funding_preference_terms,
        query_constraints.generic_terms,
    )

    # Normalize the starting URL
    domain_url = normalize_url(domain_url)

    visited: Set[str] = set()
    to_visit = build_initial_queue(
        domain_url, query_constraints, max_seed_urls=min(MAIN_DOMAIN_SEED_LIMIT, max_pages)
    )
    extra_domains_to_seed = list(extra_seed_domains or [])
    extra_domains_to_seed.extend(generate_auxiliary_seed_domains(domain_url))
    deduped_extra_domains: List[str] = []
    seen_extra_domains: Set[str] = set()
    for extra_domain in extra_domains_to_seed:
        normalized_extra = normalize_url(extra_domain)
        if (
            not normalized_extra
            or normalized_extra == domain_url
            or normalized_extra in seen_extra_domains
        ):
            continue
        seen_extra_domains.add(normalized_extra)
        deduped_extra_domains.append(normalized_extra)
        if len(deduped_extra_domains) >= MAX_AUXILIARY_SEED_DOMAINS:
            break

    for extra_domain in deduped_extra_domains:
        normalized_extra_domain = normalize_url(extra_domain)
        if not normalized_extra_domain or normalized_extra_domain == domain_url:
            continue
        extra_queue = build_initial_queue(
            normalized_extra_domain,
            query_constraints,
            max_seed_urls=min(AUXILIARY_DOMAIN_SEED_LIMIT, max_pages),
        )
        for item in extra_queue:
            to_visit.append(
                CrawlQueueItem(
                    url=item.url,
                    priority=max(item.priority, 220),
                    source="seed",
                )
            )
    to_visit.sort(key=lambda item: item.priority, reverse=True)
    to_visit = to_visit[:MAX_TOTAL_INITIAL_QUEUE]
    to_visit_set: Set[str] = {item.url for item in to_visit}
    total_seed_count = sum(1 for item in to_visit if item.source == "seed")
    required_seed_visits = min((total_seed_count + 1) // 2, max_pages)
    logger.info(
        "🪜 Seeded %d initial crawl target(s) for %s (target seed visits: %d)",
        len(to_visit),
        domain_url,
        required_seed_visits,
    )
    results: List[Dict[str, Any]] = []
    fetched_page_results: List[Dict[str, Any]] = []
    fetched_seed_pages = 0
    fetched_discovered_pages = 0
    fetched_root_pages = 0

    async with aiohttp.ClientSession() as session:
        while to_visit and len(visited) < max_pages:
            current_batch = pop_next_batch(
                to_visit,
                visited,
                to_visit_set,
                batch_size=5,
                required_seed_visits_remaining=max(0, required_seed_visits),
            )
            if not current_batch:
                break
            required_seed_visits = max(
                0, required_seed_visits - sum(1 for item in current_batch if item.source == "seed")
            )

            tasks = [fetch(session, item.url) for item in current_batch]
            pages = await asyncio.gather(*tasks)

            for i, html in enumerate(pages):
                queue_item = current_batch[i]
                url = queue_item.url
                if not html:
                    continue

                if queue_item.source == "seed":
                    fetched_seed_pages += 1
                elif queue_item.source == "root":
                    fetched_root_pages += 1
                else:
                    fetched_discovered_pages += 1

                soup = BeautifulSoup(html, "lxml")

                # Remove scripts, styles, and navigation elements (same as analyzer does)
                # This ensures clean text for both relevance checking and analysis
                for element in soup(["script", "style", "nav", "footer", "header"]):
                    element.decompose()

                text = sanitize_text_for_llm(soup.get_text(separator="\n", strip=True))

                score_breakdown = is_funding_relevant(
                    url, text, keyword_pattern, custom_keywords, query_constraints
                )
                fetched_page_results.append(
                    build_page_payload(
                        url=url,
                        title=soup.title.string if soup.title else "No title",
                        text=text,
                        relevance_score=score_breakdown.score,
                        score_breakdown=score_breakdown,
                        crawl_source=queue_item.source,
                        page_type="funding_page" if score_breakdown.is_relevant else "crawled_page",
                    )
                )

                if score_breakdown.is_relevant:
                    results.append(
                        build_page_payload(
                            url=url,
                            title=soup.title.string if soup.title else "No title",
                            text=text,
                            relevance_score=score_breakdown.score,
                            score_breakdown=score_breakdown,
                            crawl_source=queue_item.source,
                        )
                    )

                # Extract links with priority scores
                all_links = extract_links(html, url)
                logger.debug("🔗 Extracted %d link(s) from %s", len(all_links), url)
                source_page_priority_boost = 0
                if score_breakdown.is_relevant:
                    source_page_priority_boost += 60
                elif score_breakdown.text_matches_funding or score_breakdown.has_doctoral_terms:
                    source_page_priority_boost += 25

                for link in all_links:
                    normalized_link = normalize_url(link)
                    if normalized_link not in visited and normalized_link not in to_visit_set:
                        priority = score_link_priority(
                            normalized_link, custom_keywords, query_constraints
                        )
                        priority += source_page_priority_boost
                        to_visit.append(
                            CrawlQueueItem(
                                url=normalized_link,
                                priority=priority,
                                source=url,
                            )
                        )
                        to_visit_set.add(normalized_link)

        if not fetched_page_results:
            fallback_entries = search_fallback_urls(domain_url, user_query, query_constraints)
            if fallback_entries:
                logger.info(
                    "🔎 Search fallback found %d URL(s) for %s: %s",
                    len(fallback_entries),
                    domain_url,
                    [entry.get("url", "") for entry in fallback_entries[:5]],
                )
                fallback_tasks = [
                    fetch(session, entry.get("url", "")) for entry in fallback_entries
                ]
                fallback_pages = await asyncio.gather(*fallback_tasks)
                for entry, html in zip(fallback_entries, fallback_pages):
                    url = entry.get("url", "")
                    title = entry.get("title", "") or "No title"
                    snippet = entry.get("snippet", "")

                    if html:
                        soup = BeautifulSoup(html, "lxml")
                        for element in soup(["script", "style", "nav", "footer", "header"]):
                            element.decompose()
                        text = sanitize_text_for_llm(soup.get_text(separator="\n", strip=True))
                    else:
                        text = sanitize_text_for_llm(f"{title}\n{snippet}")
                        if not text:
                            continue

                    score_breakdown = is_funding_relevant(
                        url, text, keyword_pattern, custom_keywords, query_constraints
                    )
                    fetched_page_results.append(
                        build_page_payload(
                            url=url,
                            title=title,
                            text=text,
                            relevance_score=score_breakdown.score,
                            score_breakdown=score_breakdown,
                            crawl_source="search_fallback",
                            page_type="funding_page"
                            if score_breakdown.is_relevant
                            else "search_result",
                        )
                    )
                    if score_breakdown.is_relevant:
                        results.append(
                            build_page_payload(
                                url=url,
                                title=title,
                                text=text,
                                relevance_score=score_breakdown.score,
                                score_breakdown=score_breakdown,
                                crawl_source="search_fallback",
                            )
                        )

    prefiltered_results = [r for r in results if r.get("relevance_score", 0) >= min_relevance_score]
    logger.info(
        "🔎 %s produced %d candidate page(s) before query-specific filtering",
        domain_url,
        len(prefiltered_results),
    )
    final_results, dropped_results = select_final_candidates(
        results=results,
        query_constraints=query_constraints,
        min_relevance_score=min_relevance_score,
        max_results=max_results,
    )
    if dropped_results:
        logger.info(
            "🪂 %s dropped %d page(s) after query-specific filtering: %s",
            domain_url,
            len(dropped_results),
            [f"{url} ({reason})" for url, reason in dropped_results[:10]],
        )

    # Log relevance distribution for monitoring
    tier_100_plus = len([r for r in final_results if r.get("relevance_score", 0) >= 100])
    tier_50_99 = len([r for r in final_results if 50 <= r.get("relevance_score", 0) < 100])
    tier_5_49 = len([r for r in final_results if 5 <= r.get("relevance_score", 0) < 50])

    logger.info(
        f"✅ {domain_url}: {len(final_results)} pages | "
        f"🔥 Exceptional (100+): {tier_100_plus} | "
        f"⭐ High (50-99): {tier_50_99} | "
        f"✓ Moderate (5-49): {tier_5_49}"
    )
    logger.info(
        "📊 Crawl metrics for %s | visited=%d | fetched_html=%d | fetched_seed=%d | fetched_root=%d | fetched_discovered=%d | remaining_queue=%d",
        domain_url,
        len(visited),
        len(fetched_page_results),
        fetched_seed_pages,
        fetched_root_pages,
        fetched_discovered_pages,
        len(to_visit),
    )

    candidate_page_map: Dict[str, Dict[str, Any]] = {}
    for page in fetched_page_results:
        normalized_candidate_url = normalize_url(str(page.get("url", "")))
        existing = candidate_page_map.get(normalized_candidate_url)
        if existing is None or int(page.get("relevance_score", 0) or 0) >= int(
            existing.get("relevance_score", 0) or 0
        ):
            candidate_page_map[normalized_candidate_url] = sanitize_page_payload(page)

    sanitized_candidate_pages = list(candidate_page_map.values())
    sanitized_candidate_pages.sort(
        key=lambda page: (
            1 if str(page.get("crawl_source", "")) == "seed" else 0,
            int(page.get("relevance_score", 0) or 0),
        ),
        reverse=True,
    )
    sanitized_candidate_pages = sanitized_candidate_pages[:max_results]
    sanitized_final_results = [sanitize_page_payload(page) for page in final_results]

    # Cache results to prevent re-crawling the same domain
    _crawled_domains_cache[cache_key] = {
        "funding_pages": sanitized_final_results,
        "candidate_pages": sanitized_candidate_pages,
    }

    return {
        "funding_pages": sanitized_final_results,
        "candidate_pages": sanitized_candidate_pages,
    }

    # print(results)
    # results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    # print(f"✅ Crawled {len(visited)} pages, found {len(results)} funding pages for {domain_url}")

    # return results


def calculate_funding_depth(url: str) -> int:
    """Count funding-related terms in URL"""
    url_lower = url.lower()
    funding_terms = [
        "funding",
        "scholarship",
        "phd",
        "doctoral",
        "studentship",
        "financial",
        "bursary",
    ]
    return sum(url_lower.count(term) for term in funding_terms)


def _normalize_domain_url(domain: str) -> str:
    """Ensure domain has an HTTP scheme so it can be crawled."""
    cleaned = (domain or "").strip()
    if not cleaned:
        return ""
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    return f"https://{cleaned}"


def _coerce_university_input(entry: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Best-effort coercion from search-agent style objects to school/domain pairs."""
    school = (entry.get("school") or entry.get("name") or "").strip()

    raw_domains = entry.get("domains")
    auxiliary_domains: List[str] = []
    if isinstance(raw_domains, list):
        auxiliary_domains = [
            normalized
            for normalized in (
                _normalize_domain_url(str(raw_domain or "")) for raw_domain in raw_domains
            )
            if normalized
        ]

    domain = entry.get("domain") or entry.get("domain_url") or entry.get("url")
    if not domain:
        if auxiliary_domains:
            domain = auxiliary_domains[0]

    domain = _normalize_domain_url(str(domain or ""))
    if not domain:
        return None

    auxiliary_domains = [candidate for candidate in auxiliary_domains if candidate != domain]

    return {
        "school": school or "Unknown School",
        "domain": domain,
        "auxiliary_domains": auxiliary_domains,
    }


@function_tool
async def crawl_universities_formatted(
    universities: Optional[List[UniversityInput]] = None,
    schools: Optional[List[UniversityInput]] = None,
    domains: Optional[List[str]] = None,
    user_query: Optional[str] = None,
    max_pages: int = 40,
    max_results_per_university: int = 40,
    min_relevance_score: int = 5,
) -> Dict[str, Any]:
    """
    Crawl multiple universities and return a fully formatted CrawlerResult object.

    Expected university item shape:
    - {"school": "...", "domain": "https://example.edu"}
    OR search-agent style:
    - {"school": "...", "domains": ["https://example.edu", ...]}
    """
    try:
        normalized_universities: List[Dict[str, str]] = []
        seen_domains: Set[str] = set()
        input_universities = universities or schools or []
        # Hard cap to keep tool output within model context limits.
        effective_max_pages = max(10, min(max_pages, 40))
        effective_max_results_per_university = max(
            1, min(max_results_per_university, effective_max_pages)
        )

        for raw in input_universities:
            raw_dict = raw.model_dump() if isinstance(raw, UniversityInput) else raw
            if not isinstance(raw_dict, dict):
                continue
            normalized = _coerce_university_input(raw_dict)
            if not normalized:
                continue

            dedupe_key = get_domain_scope(normalized["domain"])
            if dedupe_key in seen_domains:
                continue
            seen_domains.add(dedupe_key)
            normalized_universities.append(normalized)

        # Backward-compatible input style: domains=["https://mit.edu", ...]
        for domain in domains or []:
            normalized_domain = _normalize_domain_url(str(domain or ""))
            if not normalized_domain:
                continue
            dedupe_key = get_domain_scope(normalized_domain)
            if dedupe_key in seen_domains:
                continue
            seen_domains.add(dedupe_key)
            normalized_universities.append(
                {
                    "school": dedupe_key,
                    "domain": normalized_domain,
                }
            )

        # Hard cap to bound runtime and context size for broad queries.
        normalized_universities = normalized_universities[:5]

        extracted_keywords = await extract_keywords_from_query(user_query) if user_query else []
        crawler_universities: List[Dict[str, Any]] = []
        all_scores: List[int] = []

        async def crawl_one_university(uni: Dict[str, str]) -> Dict[str, Any]:
            try:
                crawl_result = await asyncio.wait_for(
                    _crawl_university_funding_impl(
                        domain_url=uni["domain"],
                        user_query=user_query,
                        precomputed_keywords=extracted_keywords,
                        extra_seed_domains=uni.get("auxiliary_domains", []),
                        max_pages=effective_max_pages,
                        max_results=effective_max_results_per_university,
                        min_relevance_score=min_relevance_score,
                    ),
                    timeout=35,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"⏱️  Crawl timed out for {uni['domain']} - returning partial empty result"
                )
                crawl_result = {"funding_pages": [], "candidate_pages": []}
            except Exception as exc:
                logger.exception(
                    "❌ Crawl failed for %s (%s): %s",
                    uni["school"],
                    uni["domain"],
                    exc,
                )
                crawl_result = {"funding_pages": [], "candidate_pages": []}

            filtered_funding_pages = []
            for page in crawl_result.get("funding_pages", []):
                score = int(page.get("relevance_score", 0) or 0)
                all_scores.append(score)
                filtered_funding_pages.append(
                    {
                        "url": page.get("url", ""),
                        "title": page.get("title", "No title"),
                        "preview": page.get("preview", page.get("text", "")),
                        "relevance_score": score,
                        "text": page.get("text", page.get("preview", "")),
                        "full_text": page.get("full_text", ""),
                        "page_type": page.get("page_type", "funding_page"),
                        "crawl_source": page.get("crawl_source", ""),
                    }
                )

            candidate_pages = []
            for page in crawl_result.get("candidate_pages", []):
                candidate_pages.append(
                    {
                        "url": page.get("url", ""),
                        "title": page.get("title", "No title"),
                        "preview": page.get("preview", page.get("text", "")),
                        "relevance_score": int(page.get("relevance_score", 0) or 0),
                        "text": page.get("text", page.get("preview", "")),
                        "full_text": page.get("full_text", ""),
                        "page_type": page.get("page_type", "funding_page"),
                        "crawl_source": page.get("crawl_source", ""),
                    }
                )

            funding_pages = candidate_pages or filtered_funding_pages

            return {
                "school": uni["school"],
                "domain": uni["domain"],
                "funding_pages": funding_pages,
                "candidate_pages": candidate_pages,
                "filtered_funding_pages": filtered_funding_pages,
                "summary": (
                    f"Found {len(filtered_funding_pages)} high-confidence funding page(s) "
                    f"and {len(candidate_pages)} crawler candidate page(s)."
                ),
            }

        crawl_tasks = [crawl_one_university(uni) for uni in normalized_universities]
        if crawl_tasks:
            crawler_universities = await asyncio.gather(*crawl_tasks)

        relevance_tiers = {
            "exceptional": sum(1 for s in all_scores if s >= 100),
            "high": sum(1 for s in all_scores if 50 <= s < 100),
            "moderate": sum(1 for s in all_scores if 5 <= s < 50),
        }

        return {
            "universities": crawler_universities,
            "search_strategy": "query-guided crawl with keyword extraction"
            if user_query
            else "domain crawl without query keywords",
            "total_funding_pages": sum(len(u["funding_pages"]) for u in crawler_universities),
            "keyword_analysis": {
                "user_query": user_query or "",
                "keywords": extracted_keywords,
                "keyword_count": len(extracted_keywords),
            },
            "relevance_tiers": relevance_tiers,
        }
    except Exception as exc:
        logger.exception("❌ crawl_universities_formatted failed: %s", exc)
        return {
            "universities": [],
            "search_strategy": "query-guided crawl with keyword extraction"
            if user_query
            else "domain crawl without query keywords",
            "total_funding_pages": 0,
            "keyword_analysis": {
                "user_query": user_query or "",
                "keywords": [],
                "keyword_count": 0,
            },
            "relevance_tiers": {"exceptional": 0, "high": 0, "moderate": 0},
        }


@function_tool
async def crawl_university_funding(
    domain_url: str,
    user_query: Optional[str] = None,
    max_pages: int = 100,
    max_results: int = 40,
    min_relevance_score: int = 5,
) -> List[Dict[str, object]]:
    """Tool wrapper for single-university crawl."""
    crawl_result = await _crawl_university_funding_impl(
        domain_url=domain_url,
        user_query=user_query,
        precomputed_keywords=None,
        max_pages=max_pages,
        max_results=max_results,
        min_relevance_score=min_relevance_score,
    )
    return crawl_result.get("funding_pages", [])
