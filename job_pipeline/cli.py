from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
from datetime import timedelta
from email.utils import parsedate_to_datetime
import sys

from .config import get_settings
from .enrichment import enrich_company_links
from .exporters import export_all
from .models import CandidateProfile, SourceLead
from .sources import discover_all
from .text_rules import has_role_match
from .verifier import verify_lead


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover and verify recent global remote job prospects.")
    parser.add_argument("--limit", type=int, default=25, help="Maximum discovered leads to verify.")
    parser.add_argument("--approved-only", action="store_true", help="Export only approved prospects.")
    parser.add_argument("--include-watchlist", action="store_true", help="Also review company careers pages. These cannot become approved job prospects by themselves.")
    parser.add_argument("--no-ai", action="store_true", help="Disable Claude enrichment for this run.")
    parser.add_argument("--no-enrich", action="store_true", help="Skip company website/LinkedIn enrichment for faster broad scans.")
    args = parser.parse_args()

    settings = get_settings()
    if args.no_ai:
        settings = replace(settings, enable_ai=False)
    candidate = CandidateProfile(
        name=settings.candidate_name,
        location=settings.candidate_location,
        country=settings.candidate_country,
        target_work_regions=settings.target_work_regions,
        target_roles=settings.target_roles,
        strengths=settings.candidate_strengths,
    )
    safe_print("Discovering leads...")
    leads = discover_all(settings, include_watchlist=args.include_watchlist)
    leads = prioritize_leads([lead for lead in leads if lead.job_url])[: args.limit]
    safe_print(f"Discovered {len(leads)} leads to verify.")

    prospects = []
    for index, lead in enumerate(leads, start=1):
        safe_print(f"[{index}/{len(leads)}] Verifying: {lead.company or 'Unknown company'} - {lead.title}")
        prospect = verify_lead(settings, lead, candidate)
        if not args.no_enrich and prospect.status in {"approved", "manual_review"}:
            prospect = enrich_company_links(settings, prospect)
        prospects.append(prospect)

    if args.approved_only:
        prospects = [prospect for prospect in prospects if prospect.status == "approved"]

    export_all(prospects, settings.output_dir)
    approved = sum(1 for prospect in prospects if prospect.status == "approved")
    manual = sum(1 for prospect in prospects if prospect.status == "manual_review")
    rejected = sum(1 for prospect in prospects if prospect.status == "rejected")
    safe_print(f"Exported to: {settings.output_dir}")
    safe_print(f"Approved: {approved} | Manual review: {manual} | Rejected: {rejected}")


def safe_print(value: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    print(value.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def prioritize_leads(leads: list[SourceLead]) -> list[SourceLead]:
    return sorted(leads, key=lead_priority, reverse=True)


def lead_priority(lead: SourceLead) -> tuple[int, float]:
    text = " ".join([lead.title, lead.company, lead.location, lead.description]).lower()
    score = 0
    age_hours = estimate_age_hours(lead.posted_at)
    if lead.source == "Company watchlist":
        score -= 500
    if age_hours is not None and 0 <= age_hours <= 10 and lead.source != "Company watchlist":
        score += 1000
    elif age_hours is not None and age_hours <= 72:
        score += 300
    if has_role_match(text):
        score += 250
    if any(term in text for term in ("worldwide", "anywhere", "global", "africa", "emea")):
        score += 150
    if lead.apply_url:
        score += 75
    if lead.company_url:
        score += 50
    source_bonus = {
        "SerpAPI targeted search": 90,
        "We Work Remotely RSS": 80,
        "SerpAPI Google Jobs": 85,
        "Jobicy": 70,
        "Remotive": 60,
        "RemoteOK": 40,
        "Company watchlist": 20,
    }
    score += source_bonus.get(lead.source, 0)
    recency_sort = -(age_hours if age_hours is not None else 99999)
    return score, recency_sort


def estimate_age_hours(raw: str) -> float | None:
    if not raw:
        return None
    parsed = parse_datetime(raw)
    if not parsed:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600


def parse_datetime(raw: str) -> datetime | None:
    raw = raw.strip()
    relative = parse_relative_datetime(raw)
    if relative:
        return relative
    if raw.isdigit():
        try:
            value = int(raw)
            if value > 10_000_000_000:
                value = value // 1000
            return datetime.fromtimestamp(value, timezone.utc)
        except (ValueError, OSError):
            return None
    for parser in (
        lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")),
        parsedate_to_datetime,
    ):
        try:
            return parser(raw)
        except (ValueError, TypeError, IndexError, OverflowError):
            continue
    return None


def parse_relative_datetime(raw: str) -> datetime | None:
    lowered = raw.strip().lower()
    now = datetime.now(timezone.utc)
    if lowered in {"just posted", "posted just now", "just now", "today"}:
        return now
    parts = lowered.split()
    if len(parts) < 2:
        return None
    try:
        amount = int(parts[0])
    except ValueError:
        if parts[0] in {"a", "an", "one"}:
            amount = 1
        else:
            return None
    unit = parts[1].rstrip("s")
    if unit in {"minute", "min"}:
        return now - timedelta(minutes=amount)
    if unit in {"hour", "hr"}:
        return now - timedelta(hours=amount)
    if unit == "day":
        return now - timedelta(days=amount)
    if unit == "week":
        return now - timedelta(weeks=amount)
    return None
