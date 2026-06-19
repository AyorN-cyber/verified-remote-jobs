from __future__ import annotations

from datetime import datetime, timezone
import csv
import json
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import requests

from .config import ROOT, Settings
from .models import SourceLead


SOURCE_TIMEOUT = 30


def _get_json(url: str, timeout: int = SOURCE_TIMEOUT) -> object:
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "VerifiedJobsPipeline/0.1"},
    )
    response.raise_for_status()
    return response.json()


def _safe_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


ROLE_HINTS = (
    "customer",
    "support",
    "success",
    "client",
    "specialist",
    "representative",
    "manager",
    "consultant",
    "assistant",
    "coordinator",
    "operations",
    "sales",
    "hubspot",
    "crm",
    "onboarding",
)


def split_search_title(title: str) -> tuple[str, str]:
    clean = title.replace("Job Application for ", "").strip()
    for marker in (" @ ", " at "):
        if marker in clean:
            left, right = clean.rsplit(marker, 1)
            return right.strip(), left.strip()
    if " - " in clean:
        left, right = clean.rsplit(" - ", 1)
        left_has_role = any(hint in left.lower() for hint in ROLE_HINTS)
        right_has_role = any(hint in right.lower() for hint in ROLE_HINTS)
        if left_has_role and not right_has_role:
            return right.strip(), left.strip()
        if right_has_role and not left_has_role:
            return left.strip(), right.strip()
    return "", clean


def company_from_url(url: str) -> str:
    lowered = url.lower()
    markers = (
        ("jobs.ashbyhq.com/", 0),
        ("jobs.lever.co/", 0),
        ("apply.workable.com/", 0),
        ("boards.greenhouse.io/", 0),
        ("job-boards.greenhouse.io/", 0),
        ("jobs.smartrecruiters.com/", 0),
        ("jobs.teamtailor.com/", 0),
        ("recruitee.com/o/", 0),
    )
    for marker, index in markers:
        if marker in lowered:
            tail = url.split(marker, 1)[1].strip("/")
            parts = [part for part in tail.split("/") if part]
            if len(parts) > index:
                return prettify_company_slug(parts[index])
    return ""


def prettify_company_slug(value: str) -> str:
    value = re.sub(r"\d+$", "", value)
    clean = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    clean = clean.replace("-", " ").replace("_", " ").strip()
    return " ".join(part.capitalize() for part in clean.split())


def discover_remoteok(settings: Settings) -> list[SourceLead]:
    data = _get_json("https://remoteok.com/api", settings.request_timeout_seconds)
    leads: list[SourceLead] = []
    if not isinstance(data, list):
        return leads
    for item in data:
        if not isinstance(item, dict) or "position" not in item:
            continue
        leads.append(
            SourceLead(
                source="RemoteOK",
                title=_safe_str(item.get("position")),
                company=_safe_str(item.get("company")),
                job_url=_safe_str(item.get("url")),
                apply_url=_safe_str(item.get("apply_url") or item.get("url")),
                company_url=_safe_str(item.get("company_url")),
                location=_safe_str(item.get("location")),
                salary=_safe_str(item.get("salary_min")) + "-" + _safe_str(item.get("salary_max")),
                description=_safe_str(item.get("description")),
                posted_at=_safe_str(item.get("date") or item.get("epoch")),
                raw=item,
            )
        )
        if len(leads) >= settings.max_results_per_source:
            break
    return leads


def discover_remotive(settings: Settings) -> list[SourceLead]:
    urls = [
        "https://remotive.com/api/remote-jobs?category=customer-support",
        "https://remotive.com/api/remote-jobs?category=sales",
        "https://remotive.com/api/remote-jobs?category=business",
    ]
    leads: list[SourceLead] = []
    for url in urls:
        data = _get_json(url, settings.request_timeout_seconds)
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        for item in jobs:
            if not isinstance(item, dict):
                continue
            leads.append(
                SourceLead(
                    source="Remotive",
                    title=_safe_str(item.get("title")),
                    company=_safe_str(item.get("company_name")),
                    job_url=_safe_str(item.get("url")),
                    apply_url=_safe_str(item.get("url")),
                    company_url=_safe_str(item.get("company_logo_url")),
                    location=_safe_str(item.get("candidate_required_location")),
                    salary=_safe_str(item.get("salary")),
                    description=_safe_str(item.get("description")),
                    posted_at=_safe_str(item.get("publication_date")),
                    raw=item,
                )
            )
            if len(leads) >= settings.max_results_per_source:
                return leads
    return leads


def discover_jobicy(settings: Settings) -> list[SourceLead]:
    url = "https://jobicy.com/api/v2/remote-jobs?count=50&tag=customer-support"
    data = _get_json(url, settings.request_timeout_seconds)
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    leads: list[SourceLead] = []
    for item in jobs:
        if not isinstance(item, dict):
            continue
        leads.append(
            SourceLead(
                source="Jobicy",
                title=_safe_str(item.get("jobTitle")),
                company=_safe_str(item.get("companyName")),
                job_url=_safe_str(item.get("url")),
                apply_url=_safe_str(item.get("url")),
                company_url=_safe_str(item.get("companyWebsite")),
                location=_safe_str(item.get("jobGeo")),
                salary=_safe_str(item.get("annualSalaryMin")) + "-" + _safe_str(item.get("annualSalaryMax")),
                description=_safe_str(item.get("jobDescription")),
                posted_at=_safe_str(item.get("pubDate")),
                raw=item,
            )
        )
    return leads[: settings.max_results_per_source]


def discover_weworkremotely(settings: Settings) -> list[SourceLead]:
    urls = [
        "https://weworkremotely.com/categories/remote-customer-support-jobs.rss",
        "https://weworkremotely.com/categories/remote-sales-and-marketing-jobs.rss",
        "https://weworkremotely.com/categories/remote-business-and-management-jobs.rss",
    ]
    leads: list[SourceLead] = []
    for url in urls:
        response = requests.get(url, timeout=settings.request_timeout_seconds)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        for item in root.findall("./channel/item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            description = (item.findtext("description") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            company = title.split(":", 1)[0].strip() if ":" in title else ""
            role = title.split(":", 1)[1].strip() if ":" in title else title
            leads.append(
                SourceLead(
                    source="We Work Remotely RSS",
                    title=role,
                    company=company,
                    job_url=link,
                    apply_url=link,
                    description=description,
                    posted_at=pub_date,
                    raw={"rss_url": url},
                )
            )
            if len(leads) >= settings.max_results_per_source:
                return leads
    return leads


def discover_serpapi(settings: Settings) -> list[SourceLead]:
    if not settings.serpapi_api_key:
        return []
    queries = [
        'site:greenhouse.io "customer support" "remote" "worldwide"',
        'site:lever.co "customer success" "remote" "worldwide"',
        'site:jobs.ashbyhq.com "customer support" "remote" "global"',
        'site:workable.com "HubSpot" "remote" "customer"',
        'site:smartrecruiters.com "customer support" "remote" "worldwide"',
        'site:jobs.ashbyhq.com "customer success" "remote" "worldwide"',
        'site:jobs.ashbyhq.com "customer support" "remote"',
        'site:jobs.ashbyhq.com "customer experience" "remote"',
        'site:jobs.ashbyhq.com "client success" "remote"',
        'site:jobs.ashbyhq.com "onboarding specialist" "remote"',
        'site:jobs.ashbyhq.com "technical support" "remote"',
        'site:boards.greenhouse.io "customer success" "remote"',
        'site:boards.greenhouse.io "customer support" "remote"',
        'site:boards.greenhouse.io "customer experience" "remote"',
        'site:boards.greenhouse.io "client success" "remote"',
        'site:boards.greenhouse.io "onboarding specialist" "remote"',
        'site:boards.greenhouse.io "technical support" "remote"',
        'site:jobs.lever.co "customer operations" "remote"',
        'site:jobs.lever.co "customer support" "remote"',
        'site:jobs.lever.co "customer success" "remote"',
        'site:jobs.lever.co "client success" "remote"',
        'site:jobs.lever.co "onboarding specialist" "remote"',
        'site:jobs.lever.co "technical support" "remote"',
        'site:apply.workable.com "customer support" "remote"',
        'site:apply.workable.com "customer success" "remote"',
        'site:apply.workable.com "customer experience" "remote"',
        'site:apply.workable.com "client success" "remote"',
        'site:apply.workable.com "onboarding specialist" "remote"',
        'site:apply.workable.com "technical support" "remote"',
        'site:jobs.smartrecruiters.com "customer support" "remote"',
        'site:jobs.smartrecruiters.com "customer success" "remote"',
        'site:jobs.smartrecruiters.com "customer experience" "remote"',
        'site:jobs.smartrecruiters.com "technical support" "remote"',
        'site:jobs.teamtailor.com "customer support" "remote"',
        'site:jobs.teamtailor.com "customer success" "remote"',
        'site:*.recruitee.com "customer support" "remote"',
        'site:*.breezy.hr "customer support" "remote"',
        'site:*.bamboohr.com/jobs "customer support" "remote"',
        'site:*.personio.com "customer support" "remote"',
        'site:jobs.ashbyhq.com "virtual assistant" "remote"',
        'site:jobs.lever.co "virtual assistant" "remote"',
        'site:boards.greenhouse.io "hubspot" "remote"',
        'site:reddit.com/r/forhire "remote" "customer support" "hiring"',
        'site:reddit.com/r/remotework "remote" "customer support" "hiring"',
        'site:linkedin.com/jobs "customer support" "remote" "worldwide"',
        'site:linkedin.com/jobs "customer success" "remote" "worldwide"',
    ]
    leads: list[SourceLead] = []
    for query in queries:
        params = urlencode(
            {
                "engine": "google",
                "q": query,
                "api_key": settings.serpapi_api_key,
                "num": 10,
                "tbs": "qdr:d",
            }
        )
        data = _get_json(f"https://serpapi.com/search.json?{params}", settings.request_timeout_seconds)
        results = data.get("organic_results", []) if isinstance(data, dict) else []
        for result in results:
            if not isinstance(result, dict):
                continue
            link = _safe_str(result.get("link"))
            company, title = split_search_title(_safe_str(result.get("title")))
            company = company or company_from_url(link)
            leads.append(
                SourceLead(
                    source="SerpAPI targeted search",
                    title=title,
                    company=company,
                    job_url=link,
                    apply_url=link,
                    description=_safe_str(result.get("snippet")),
                    posted_at=_safe_str(result.get("date")),
                    raw={"query": query, "result": result},
                )
            )
    return leads[: settings.max_results_per_source]


def discover_serpapi_google_jobs(settings: Settings) -> list[SourceLead]:
    if not settings.serpapi_api_key:
        return []
    region_queries = []
    for region in settings.target_work_regions:
        clean_region = region.strip()
        if clean_region and clean_region.lower() not in {"worldwide", "global", "remote"}:
            region_queries.extend(
                [
                    f"remote customer support {clean_region}",
                    f"remote customer success {clean_region}",
                ]
            )
    queries = [
        "remote customer support worldwide",
        "remote customer success worldwide",
        "remote virtual assistant worldwide",
        "remote CRM specialist worldwide",
        "remote HubSpot specialist worldwide",
        "remote customer operations worldwide",
        "remote customer experience worldwide",
        "remote client success worldwide",
        "remote onboarding specialist worldwide",
        "remote technical support worldwide",
        "remote chat support worldwide",
        "remote sales support worldwide",
        "remote customer support Africa",
        "remote customer success EMEA",
    ] + region_queries
    leads: list[SourceLead] = []
    for query in queries:
        params = urlencode(
            {
                "engine": "google_jobs",
                "q": query,
                "location": settings.candidate_country or settings.candidate_location or "Remote",
                "hl": "en",
                "api_key": settings.serpapi_api_key,
            }
        )
        data = _get_json(f"https://serpapi.com/search.json?{params}", settings.request_timeout_seconds)
        jobs = data.get("jobs_results", []) if isinstance(data, dict) else []
        for item in jobs:
            if not isinstance(item, dict):
                continue
            detected = item.get("detected_extensions") or {}
            apply_options = item.get("apply_options") or []
            apply_url = ""
            if apply_options and isinstance(apply_options[0], dict):
                apply_url = _safe_str(apply_options[0].get("link"))
            highlights = item.get("job_highlights") or []
            highlight_text = " ".join(_safe_str(section) for section in highlights)
            leads.append(
                SourceLead(
                    source="SerpAPI Google Jobs",
                    title=_safe_str(item.get("title")),
                    company=_safe_str(item.get("company_name")),
                    job_url=_safe_str(item.get("share_link") or apply_url),
                    apply_url=apply_url,
                    location=_safe_str(item.get("location")),
                    salary=_safe_str(detected.get("salary")),
                    description=" ".join(
                        filter(
                            None,
                            [
                                _safe_str(item.get("description")),
                                highlight_text,
                                " ".join(_safe_str(ext) for ext in item.get("extensions", [])),
                            ],
                        )
                    ),
                    posted_at=_safe_str(detected.get("posted_at")),
                    raw={"query": query, "job": item},
                )
            )
            if len(leads) >= settings.max_results_per_source:
                return leads
    return leads[: settings.max_results_per_source]


def discover_company_watchlist(settings: Settings) -> list[SourceLead]:
    path = ROOT / "job_pipeline" / "company_watchlist.csv"
    if not path.exists():
        return []
    leads: list[SourceLead] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            leads.append(
                SourceLead(
                    source="Company watchlist",
                    title="Company careers page review",
                    company=row.get("company", ""),
                    job_url=row.get("careers_url", ""),
                    apply_url=row.get("careers_url", ""),
                    company_url=row.get("website", ""),
                    company_linkedin=row.get("linkedin", ""),
                    location=row.get("remote_policy", ""),
                    description=row.get("notes", ""),
                    posted_at=datetime.now(timezone.utc).isoformat(),
                    raw=row,
                )
            )
    return leads


def discover_all(settings: Settings, include_watchlist: bool = False) -> list[SourceLead]:
    collectors = (
        discover_remoteok,
        discover_remotive,
        discover_jobicy,
        discover_weworkremotely,
        discover_serpapi_google_jobs,
        discover_serpapi,
    )
    if include_watchlist:
        collectors = collectors + (discover_company_watchlist,)
    leads: list[SourceLead] = []
    for collector in collectors:
        try:
            leads.extend(collector(settings))
        except Exception as exc:
            leads.append(
                SourceLead(
                    source=f"{collector.__name__} error",
                    title="Source failed",
                    company="",
                    job_url="",
                    description=str(exc),
                )
            )
    return dedupe_leads(leads)


def dedupe_leads(leads: Iterable[SourceLead]) -> list[SourceLead]:
    seen: set[str] = set()
    unique: list[SourceLead] = []
    for lead in leads:
        key = (lead.job_url or lead.apply_url or f"{lead.company}:{lead.title}").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(lead)
    return unique
