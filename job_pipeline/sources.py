from __future__ import annotations

from datetime import datetime, timezone
import csv
import json
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
    ]
    leads: list[SourceLead] = []
    for query in queries:
        params = urlencode({"engine": "google", "q": query, "api_key": settings.serpapi_api_key, "num": 10})
        data = _get_json(f"https://serpapi.com/search.json?{params}", settings.request_timeout_seconds)
        results = data.get("organic_results", []) if isinstance(data, dict) else []
        for result in results:
            if not isinstance(result, dict):
                continue
            leads.append(
                SourceLead(
                    source="SerpAPI targeted search",
                    title=_safe_str(result.get("title")),
                    company="",
                    job_url=_safe_str(result.get("link")),
                    apply_url=_safe_str(result.get("link")),
                    description=_safe_str(result.get("snippet")),
                    posted_at=_safe_str(result.get("date")),
                    raw={"query": query, "result": result},
                )
            )
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
