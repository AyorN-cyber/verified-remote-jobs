from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .http import FetchResult, fetch_page


BOARD_HOSTS = (
    "remoteok.com",
    "weworkremotely.com",
    "remotive.com",
    "jobicy.com",
    "remote.co",
    "himalayas.app",
    "workingnomads.com",
    "nodesk.co",
    "dynamitejobs.com",
    "jobspresso.co",
)

TRUSTED_ATS_HOSTS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workable.com",
    "smartrecruiters.com",
    "teamtailor.com",
    "recruitee.com",
    "bamboohr.com",
    "workdayjobs.com",
    "myworkdayjobs.com",
    "personio.com",
    "breezy.hr",
)

APPLY_TERMS = (
    "apply",
    "apply now",
    "apply for this job",
    "apply for this position",
    "submit application",
    "application",
)

BAD_LINK_TERMS = (
    "share",
    "twitter",
    "facebook",
    "linkedin",
    "login",
    "sign in",
    "pricing",
    "post a job",
    "terms",
    "privacy",
    "report",
    "save",
    "product hunt",
    "producthunt",
    "api",
    "launch",
)


@dataclass(frozen=True)
class ApplyResolution:
    original_url: str
    resolved_url: str
    page: FetchResult
    evidence: str


def resolve_apply_url(lead_apply_url: str, job_page: FetchResult, timeout: int) -> ApplyResolution:
    candidates = extract_apply_candidates(job_page.final_url or job_page.url, job_page.html)
    ordered = order_candidates(lead_apply_url, candidates, job_page.final_url or job_page.url)

    fallback_url = lead_apply_url or job_page.final_url or job_page.url
    best = ApplyResolution(fallback_url, job_page.final_url, job_page, "fallback lead apply URL")

    for candidate in ordered[:3]:
        page = fetch_page(candidate, timeout)
        if not page.ok:
            continue
        final_host = host_of(page.final_url)
        candidate_host = host_of(candidate)
        if is_trusted_ats_host(final_host):
            return ApplyResolution(candidate, page.final_url, page, f"apply link resolved to trusted ATS: {final_host}")
        if not is_board_host(final_host) and not is_board_host(candidate_host):
            return ApplyResolution(candidate, page.final_url, page, f"apply link resolved outside job board: {final_host}")
        if not is_board_host(final_host) and is_board_host(candidate_host):
            return ApplyResolution(candidate, page.final_url, page, f"board apply redirect resolved outside job board: {final_host}")
        if best.page is job_page or is_board_host(host_of(best.resolved_url)):
            best = ApplyResolution(candidate, page.final_url, page, "best opened apply candidate, still board-hosted")
    if fallback_url and best.page is job_page and normalize_url(fallback_url) != normalize_url(job_page.url):
        page = fetch_page(fallback_url, timeout)
        best = ApplyResolution(fallback_url, page.final_url, page, "fallback lead apply URL")
    return best


def extract_apply_candidates(base_url: str, html: str) -> list[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    scored: list[tuple[int, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        text = " ".join(
            [
                anchor.get_text(" ", strip=True),
                str(anchor.get("aria-label") or ""),
                str(anchor.get("title") or ""),
                " ".join(anchor.get("class") or []),
                str(anchor.get("id") or ""),
            ]
        ).lower()
        if any(term in text for term in BAD_LINK_TERMS):
            continue
        url = urljoin(base_url, href)
        score = score_apply_link(url, text, base_url)
        if score > 0:
            scored.append((score, url))
    scored.sort(reverse=True)
    unique: list[str] = []
    seen: set[str] = set()
    for _, url in scored:
        key = url.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(url)
    return unique


def order_candidates(lead_apply_url: str, candidates: list[str], job_url: str) -> list[str]:
    ordered: list[str] = []
    for url in [lead_apply_url, *candidates]:
        if not url:
            continue
        if normalize_url(url) == normalize_url(job_url) and candidates:
            continue
        if url not in ordered:
            ordered.append(url)
    return ordered


def score_apply_link(url: str, text: str, base_url: str) -> int:
    host = host_of(url)
    base_host = host_of(base_url)
    score = 0
    has_apply_text = any(term in text for term in APPLY_TERMS)
    has_apply_path = "/apply" in url.lower() or "application" in url.lower()
    trusted_ats = is_trusted_ats_host(host)
    mailto = "mailto:" in url
    if not (has_apply_text or has_apply_path or trusted_ats or mailto):
        return 0
    if has_apply_text:
        score += 80
    if mailto:
        score += 30
    if trusted_ats:
        score += 90
    if host and host != base_host and not is_board_host(host):
        score += 60
    if has_apply_path:
        score += 30
    if is_board_host(host) and host == base_host:
        score -= 20
    return score


def is_board_host(host: str) -> bool:
    return any(host == board or host.endswith(f".{board}") for board in BOARD_HOSTS)


def is_trusted_ats_host(host: str) -> bool:
    return any(host == ats or host.endswith(f".{ats}") for ats in TRUSTED_ATS_HOSTS)


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl().rstrip("/")
