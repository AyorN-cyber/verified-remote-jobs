from __future__ import annotations

from urllib.parse import urlencode, urlparse
import re

import requests

from .config import Settings
from .models import VerifiedProspect


_CACHE: dict[str, tuple[str, str]] = {}


BAD_COMPANY_TOKENS = {
    "",
    "unknown company",
    "remote",
    "contract",
    "india",
    "us",
    "temporary mon-fri",
}


def enrich_company_links(settings: Settings, prospect: VerifiedProspect) -> VerifiedProspect:
    company = (prospect.company or "").strip()
    if company.lower() in BAD_COMPANY_TOKENS or not settings.serpapi_api_key:
        return prospect
    if prospect.company_url and prospect.company_linkedin:
        return prospect
    website, linkedin = lookup_company_links(settings, company)
    if website and not prospect.company_url:
        prospect.company_url = website
    if linkedin and not prospect.company_linkedin:
        prospect.company_linkedin = linkedin
    return prospect


def lookup_company_links(settings: Settings, company: str) -> tuple[str, str]:
    key = company.lower()
    if key in _CACHE:
        return _CACHE[key]

    website = ""
    linkedin = ""
    query = f'{company} official website LinkedIn company'
    params = urlencode({"engine": "google", "q": query, "num": 8, "api_key": settings.serpapi_api_key})
    try:
        response = requests.get(
            f"https://serpapi.com/search.json?{params}",
            timeout=settings.request_timeout_seconds,
        )
        response.raise_for_status()
        results = response.json().get("organic_results") or []
    except requests.RequestException:
        results = []

    website_candidates: list[tuple[int, str]] = []
    company_tokens = company_search_tokens(company)
    for result in results:
        link = str(result.get("link") or "")
        host = (urlparse(link).hostname or "").lower()
        if not link:
            continue
        if "linkedin.com" in host and "/company/" in link and not linkedin:
            linkedin = link
            continue
        if is_likely_company_website(host):
            website_candidates.append((website_score(host, company_tokens), homepage_for(link)))
    if website_candidates:
        website_candidates.sort(key=lambda item: item[0], reverse=True)
        if website_candidates[0][0] > 0:
            website = website_candidates[0][1]

    _CACHE[key] = (website, linkedin)
    return website, linkedin


def homepage_for(link: str) -> str:
    parsed = urlparse(link)
    host = parsed.hostname or ""
    if not host:
        return link
    return f"{parsed.scheme or 'https'}://{host}/"


def is_likely_company_website(host: str) -> bool:
    if not host:
        return False
    blocked = (
        "linkedin.com",
        "facebook.com",
        "twitter.com",
        "x.com",
        "reddit.com",
        "youtube.com",
        "crunchbase.com",
        "glassdoor.com",
        "indeed.com",
        "wellfound.com",
        "remoterocketship.com",
        "builtin.com",
        "levels.fyi",
        "google.com",
        "wikipedia.org",
        "workable.com",
        "greenhouse.io",
        "lever.co",
        "ashbyhq.com",
        "smartrecruiters.com",
    )
    return not any(host == item or host.endswith(f".{item}") for item in blocked)


def company_search_tokens(company: str) -> list[str]:
    blocked = {"inc", "llc", "ltd", "limited", "company", "co", "the", "ai", "io", "hq"}
    tokens = re.findall(r"[a-z0-9]+", company.lower())
    return [token for token in tokens if len(token) > 2 and token not in blocked]


def website_score(host: str, tokens: list[str]) -> int:
    if not tokens:
        return 0
    host_text = host.removeprefix("www.")
    score = 1
    for token in tokens:
        if token in host_text:
            score += 10
    return score
