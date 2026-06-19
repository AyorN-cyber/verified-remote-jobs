from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from job_pipeline.config import get_settings
from job_pipeline.enrichment import enrich_company_links
from job_pipeline.exporters import export_all
from job_pipeline.models import VerifiedProspect
from job_pipeline.sources import company_from_url


BAD_COMPANY_RE = re.compile(r"^[0-9a-f]{6,}[-0-9a-f ]*$", re.IGNORECASE)
LOW_FIT_TITLE_RE = re.compile(
    r"\b(associate director|general manager|senior visual design|visual design)\b",
    re.IGNORECASE,
)
COMPANY_ALIASES = {
    "creditgenie": "Credit Genie",
    "forcetherapeutics": "Force Therapeutics",
    "futurefitai": "FutureFit AI",
    "gohighlevel": "HighLevel",
    "obsidiansecurity": "Obsidian Security",
    "opentable": "OpenTable",
    "simberobotics": "Simbe Robotics",
    "telnyx54": "Telnyx",
}
KNOWN_COMPANY_URLS = {
    "HighLevel": "https://www.gohighlevel.com/",
    "Jobgether": "https://jobgether.com/",
    "Telnyx": "https://telnyx.com/",
}
KNOWN_LINKEDIN_URLS = {
    "HighLevel": "https://www.linkedin.com/company/highlevel",
    "Telnyx": "https://www.linkedin.com/company/telnyx",
}
BAD_LINKEDIN_MATCHES = {
    ("Nash", "harvey-nash"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a curated prospect pack from verified sweep output.")
    parser.add_argument("--input", required=True, help="Input verified_job_prospects.csv from a broad sweep.")
    parser.add_argument("--output-dir", required=True, help="Directory for curated CSV/XLSX/DOCX outputs.")
    parser.add_argument("--count", type=int, default=25, help="Number of prospects to export.")
    parser.add_argument("--no-enrich", action="store_true", help="Skip SerpAPI company website/LinkedIn enrichment.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    rows = load_rows(Path(args.input))
    prospects = [to_prospect(row) for row in rows if row.get("status") in {"approved", "manual_review"}]
    prospects = dedupe(prospects)
    prospects.sort(key=rank_prospect)

    selected = []
    deferred = []
    for prospect in prospects:
        if LOW_FIT_TITLE_RE.search(prospect.title):
            deferred.append(prospect)
            continue
        selected.append(prospect)
        if len(selected) >= args.count:
            break

    if len(selected) < args.count:
        selected.extend(deferred[: args.count - len(selected)])

    selected = selected[: args.count]
    for idx, prospect in enumerate(selected, start=1):
        normalize_company(prospect)
        prospect.confidence_score = score(prospect)
        prospect.candidate_fit = candidate_fit(prospect)
        prospect.apply_strategy = apply_strategy(prospect, settings.candidate_country)
        prospect.outreach_strategy = outreach_strategy(prospect)
        prospect.linkedin_outreach_message = linkedin_message(prospect)
        prospect.email_followup_message = email_message(prospect, settings.candidate_name)
        prospect.materials_to_prepare = materials(prospect)
        prospect.company_research_notes = research_notes(prospect)
        prospect.ai_notes = "Curated deterministic strategy pack; no personal data or API keys included."
        if not args.no_enrich:
            prospect = enrich_company_links(settings, prospect)
            selected[idx - 1] = prospect
        if prospect.company in KNOWN_COMPANY_URLS:
            prospect.company_url = KNOWN_COMPANY_URLS[prospect.company]
        if prospect.company in KNOWN_LINKEDIN_URLS:
            prospect.company_linkedin = KNOWN_LINKEDIN_URLS[prospect.company]
        if is_bad_linkedin_match(prospect.company, prospect.company_linkedin):
            prospect.company_linkedin = ""

    export_all(selected, Path(args.output_dir))
    approved = sum(1 for item in selected if item.status == "approved")
    manual = sum(1 for item in selected if item.status == "manual_review")
    print(f"Exported {len(selected)} prospects to {args.output_dir} ({approved} approved, {manual} manual_review).")


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def to_prospect(row: dict[str, str]) -> VerifiedProspect:
    names = {field.name for field in fields(VerifiedProspect)}
    payload = {name: row.get(name, "") for name in names if name != "verified_at"}
    payload["confidence_score"] = int(payload.get("confidence_score") or 0)
    verified_at = row.get("verified_at") or ""
    try:
        payload["verified_at"] = datetime.fromisoformat(verified_at)
    except ValueError:
        payload["verified_at"] = datetime.now(timezone.utc)
    return VerifiedProspect(**payload)


def normalize_company(prospect: VerifiedProspect) -> None:
    company = (prospect.company or "").strip()
    from_url = company_from_url(prospect.apply_url or prospect.job_url)
    weak_company = (
        not company
        or company.lower() in {"jobs", "contract"}
        or BAD_COMPANY_RE.match(company)
        or "..." in company
        or company.lower().startswith(("english", "temporary", "remote", "india"))
    )
    if weak_company:
        prospect.company = from_url or company
    elif from_url and (company.lower().startswith("jobs") or len(company) > 60):
        prospect.company = from_url
    prospect.company = COMPANY_ALIASES.get(prospect.company.lower(), prospect.company)


def dedupe(prospects: list[VerifiedProspect]) -> list[VerifiedProspect]:
    seen = set()
    output = []
    for prospect in prospects:
        key = normalized_job_key(prospect)
        if key in seen:
            continue
        seen.add(key)
        output.append(prospect)
    return output


def normalized_job_key(prospect: VerifiedProspect) -> tuple[str, str]:
    apply_url = (prospect.apply_url or prospect.job_url).replace("/apply", "").replace("/application", "").rstrip("/")
    return (apply_url.lower(), prospect.title.lower())


def rank_prospect(prospect: VerifiedProspect) -> tuple[int, int, int]:
    status_rank = 0 if prospect.status == "approved" else 1
    fit_rank = 0 if is_strong_fit(prospect.title) else 1
    age = freshness_hours(prospect.freshness_evidence)
    return (status_rank, fit_rank, age)


def freshness_hours(text: str) -> int:
    match = re.search(r"(\d+(?:\.\d+)?)\s+hours? old", text or "")
    if not match:
        return 999
    return int(float(match.group(1)))


def is_strong_fit(title: str) -> bool:
    return bool(
        re.search(
            r"\b(customer|client|support|success|onboarding|community|operations|implementation|crm|enablement)\b",
            title,
            re.IGNORECASE,
        )
    )


def score(prospect: VerifiedProspect) -> int:
    value = 78
    if prospect.status == "approved":
        value += 12
    if is_strong_fit(prospect.title):
        value += 6
    if prospect.apply_link_status.startswith("verified"):
        value += 4
    if "worldwide" in (prospect.eligibility_evidence or "").lower():
        value += 4
    return min(value, 98)


def candidate_fit(prospect: VerifiedProspect) -> str:
    return (
        "Good fit for a remote customer operations/support profile: the role overlaps with customer communication, "
        "CRM discipline, client follow-up, issue tracking, scheduling, and structured remote coordination. Tailor the CV "
        "summary toward measurable customer response quality, admin ownership, and calm written communication."
    )


def apply_strategy(prospect: VerifiedProspect, candidate_country: str) -> str:
    region_label = candidate_country or "the candidate's country/region"
    base = (
        "Apply through the official company/ATS link only. Use a tailored CV headline that mirrors the title, add a short "
        "cover note, and reference remote collaboration, CRM hygiene, and customer follow-up experience."
    )
    if prospect.status == "approved":
        return (
            f"{base} This role is apply-ready because eligibility evidence includes {prospect.eligibility_evidence}. "
            "After applying, send a LinkedIn note to a recruiter, talent partner, customer success lead, or support operations lead within 24 hours."
        )
    return (
        f"{base} Before applying, verify country/time-zone acceptance because the posting did not explicitly state global/{region_label} eligibility. "
        "Ask the recruiter whether they consider globally remote applicants, then apply if they confirm or the application form permits the candidate location."
    )


def outreach_strategy(prospect: VerifiedProspect) -> str:
    return (
        "1. Apply on the official link. 2. Find the company LinkedIn page and search employees for Recruiter, Talent Acquisition, "
        "People Partner, Customer Success Manager, Head of Support, or Operations Manager. 3. Send a concise note with the job title, "
        "why the candidate fits, and the application email/name used. 4. Follow up after 3 business days with one extra proof point."
    )


def linkedin_message(prospect: VerifiedProspect) -> str:
    return (
        f"Hello, I just applied for the {prospect.title} role at {prospect.company}. My background is in customer support, "
        "CRM/admin coordination, client follow-up, and remote communication. I would appreciate any guidance on the process "
        "or the right hiring contact for this opening."
    )


def email_message(prospect: VerifiedProspect, candidate_name: str) -> str:
    signoff = candidate_name or "Candidate Name"
    return (
        f"Subject: Follow-up on {prospect.title} application\n\n"
        f"Hello {prospect.company} team,\n\n"
        f"I recently applied for the {prospect.title} role through your official careers link. I am especially interested because "
        "the role aligns with my customer support, CRM, admin coordination, and client follow-up experience. Please let me know "
        "if there is any additional information I can provide.\n\n"
        f"Best regards,\n{signoff}"
    )


def materials(prospect: VerifiedProspect) -> str:
    return (
        "Tailored one-page CV; short cover note; LinkedIn profile URL; CRM/customer support proof points; examples of client follow-up, "
        "ticket handling, spreadsheet/CRM accuracy, and remote availability. Prepare a 60-second answer on why this company and role."
    )


def research_notes(prospect: VerifiedProspect) -> str:
    return (
        f"Research {prospect.company}'s product, customer segment, support channels, recent announcements, and leadership team. "
        "Use the company website and LinkedIn page for outreach; do not rely on third-party job boards as proof of validity."
    )


def is_bad_linkedin_match(company: str, linkedin_url: str) -> bool:
    normalized_url = linkedin_url.lower()
    return any(company == bad_company and bad_token in normalized_url for bad_company, bad_token in BAD_LINKEDIN_MATCHES)


if __name__ == "__main__":
    main()
