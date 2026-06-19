from __future__ import annotations

from datetime import datetime, timezone
from datetime import timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from .ai import analyze_with_claude
from .apply_links import BOARD_HOSTS, TRUSTED_ATS_HOSTS, is_board_host, is_low_trust_host, resolve_apply_url
from .config import Settings
from .http import fetch_page
from .models import CandidateProfile, SourceLead, VerifiedProspect
from .text_rules import find_global_eligibility, find_scam_risk, has_role_match, normalize_text


def verify_lead(settings: Settings, lead: SourceLead, candidate: CandidateProfile) -> VerifiedProspect:
    lead_text = normalize_text(" ".join([lead.title, lead.location, lead.salary, lead.description]))
    freshness_status, freshness_evidence = check_freshness(lead, settings.freshness_hours)
    if freshness_status != "approved_recent":
        return build_fast_rejection(lead, freshness_status, freshness_evidence, lead_text)

    job_page = fetch_page(lead.job_url, settings.request_timeout_seconds)
    apply_resolution = resolve_apply_url(lead.apply_url, job_page, settings.request_timeout_seconds)
    apply_url = apply_resolution.resolved_url or apply_resolution.original_url
    apply_page = apply_resolution.page
    full_text = normalize_text(" ".join([lead_text, job_page.text, apply_page.text]))

    eligibility_status, eligibility_evidence = find_global_eligibility(full_text)
    scam_risk, scam_evidence = find_scam_risk(lead_text)
    role_match = has_role_match(full_text)
    official_status = check_official_source(lead, job_page.final_url, apply_page.final_url)
    apply_status = check_apply_link(
        apply_resolution.original_url,
        apply_page.final_url,
        apply_page.ok,
        apply_page.status_code,
        apply_resolution.evidence,
    )

    ai_data = {}
    try:
        ai_data = analyze_with_claude(settings, lead, full_text, candidate)
    except Exception as exc:
        ai_data = {"ai_error": str(exc)}

    status = "manual_review"
    rejection_reasons: list[str] = []
    confidence = 50

    if lead.source == "Company watchlist":
        rejection_reasons.append("watchlist company page is not a specific verified job posting")
    if not job_page.ok:
        rejection_reasons.append(f"job page did not open: HTTP {job_page.status_code} {job_page.error}")
    if not role_match and lead.source != "Company watchlist":
        rejection_reasons.append("role does not match candidate target areas")
    if freshness_status != "approved_recent":
        rejection_reasons.append(f"freshness not approved: {freshness_status}")
    if eligibility_status == "rejected":
        rejection_reasons.append(f"location restriction found: {eligibility_evidence}")
    if scam_risk == "high":
        rejection_reasons.append(f"high scam risk: {scam_evidence}")
    if apply_status.startswith("rejected"):
        rejection_reasons.append(apply_status)

    if rejection_reasons:
        status = "rejected"
        confidence = 20
    elif eligibility_status == "eligible" and official_status.startswith("verified") and apply_status.startswith("verified"):
        status = "approved"
        confidence = 90
    elif eligibility_status == "eligible":
        status = "manual_review"
        confidence = 70

    candidate_fit = ai_data.get("candidate_fit_summary") or ai_data.get("role_match") or (
        "Potential fit if the role is customer support, CRM, customer success, virtual assistant, or operations support."
    )
    verification_summary = ai_data.get(
        "verification_summary",
        f"{status.title()} after checking freshness, eligibility, apply link, source, and scam-risk signals.",
    )
    apply_strategy = ai_data.get(
        "apply_strategy",
        "Apply through the official application route only after confirming the role is still open and accepts the candidate's location or target work region.",
    )
    linkedin_message = ai_data.get(
        "linkedin_outreach_message",
        "Hello, I applied for the role and wanted to briefly share my fit. I have customer support, CRM, HubSpot, and remote client follow-up experience, and I would value the chance to support your team.",
    )
    email_message = ai_data.get(
        "email_followup_message",
        f"Hello Hiring Team,\n\nI applied for this role and wanted to add a short note on fit. I have experience with customer support, CRM hygiene, client follow-up, and remote coordination. I would appreciate the opportunity to discuss how I can support your team.\n\nBest regards,\n{candidate.name}",
    )
    materials = ai_data.get(
        "materials_to_prepare",
        "Tailored CV, HubSpot certificate links, concise cover note, LinkedIn profile, and two examples of customer follow-up or CRM work.",
    )
    company_notes = ai_data.get(
        "company_research_notes",
        "Review the company website, product, customer type, support channels, and careers page before applying.",
    )
    outreach = ai_data.get(
        "outreach_strategy",
        "Apply through the official route first. Then follow up through verified LinkedIn recruiter, hiring manager, or company-domain recruiting email after 3 business days.",
    )

    evidence_links = "; ".join(filter(None, [lead.job_url, apply_url, lead.company_url, lead.company_linkedin]))
    return VerifiedProspect(
        source=lead.source,
        title=lead.title,
        company=lead.company,
        status=status,
        confidence_score=confidence,
        job_url=lead.job_url,
        apply_url=apply_url,
        company_url=lead.company_url,
        company_linkedin=lead.company_linkedin,
        location=lead.location,
        salary=lead.salary,
        posted_at=lead.posted_at,
        freshness_status=freshness_status,
        freshness_evidence=freshness_evidence,
        official_source_status=official_status,
        apply_link_status=apply_status,
        country_eligibility=eligibility_status,
        eligibility_evidence=ai_data.get("country_evidence") or eligibility_evidence,
        scam_risk=f"{scam_risk}: {scam_evidence}",
        rejection_reason="; ".join(rejection_reasons),
        verification_summary=verification_summary,
        candidate_fit=candidate_fit,
        apply_strategy=apply_strategy,
        linkedin_outreach_message=linkedin_message,
        email_followup_message=email_message,
        materials_to_prepare=materials,
        company_research_notes=company_notes,
        outreach_strategy=outreach,
        evidence_links=evidence_links,
        ai_notes="; ".join(f"{k}={v}" for k, v in ai_data.items() if k != "candidate_fit_summary"),
    )


def build_fast_rejection(
    lead: SourceLead,
    freshness_status: str,
    freshness_evidence: str,
    lead_text: str,
) -> VerifiedProspect:
    eligibility_status, eligibility_evidence = find_global_eligibility(lead_text)
    scam_risk, scam_evidence = find_scam_risk(lead_text)
    reason = f"freshness not approved: {freshness_status}"
    if lead.source == "Company watchlist":
        reason = "watchlist company page is not a specific verified job posting"
    return VerifiedProspect(
        source=lead.source,
        title=lead.title,
        company=lead.company,
        status="rejected",
        confidence_score=20,
        job_url=lead.job_url,
        apply_url=lead.apply_url,
        company_url=lead.company_url,
        company_linkedin=lead.company_linkedin,
        location=lead.location,
        salary=lead.salary,
        posted_at=lead.posted_at,
        freshness_status=freshness_status,
        freshness_evidence=freshness_evidence,
        official_source_status="not_checked_stale_or_watchlist",
        apply_link_status="not_checked_stale_or_watchlist",
        country_eligibility=eligibility_status,
        eligibility_evidence=eligibility_evidence,
        scam_risk=f"{scam_risk}: {scam_evidence}",
        rejection_reason=reason,
        verification_summary=f"Rejected before live apply-link verification because freshness status is {freshness_status}.",
        candidate_fit="Not assessed because the lead failed freshness verification.",
        apply_strategy="Do not apply unless the role is re-posted and verified through an official company or ATS route.",
        linkedin_outreach_message="",
        email_followup_message="",
        materials_to_prepare="",
        company_research_notes="",
        outreach_strategy="No outreach recommended for stale or non-job leads.",
        evidence_links="; ".join(filter(None, [lead.job_url, lead.apply_url, lead.company_url, lead.company_linkedin])),
        ai_notes="",
    )


def check_freshness(lead: SourceLead, max_hours: int) -> tuple[str, str]:
    if lead.source == "Company watchlist":
        return "watchlist_not_job", "Company watchlist timestamps are local review timestamps, not job posting times."
    raw = (lead.posted_at or "").strip()
    if not raw:
        return "unknown", "No reliable posting timestamp."
    parsed = parse_datetime(raw)
    if not parsed:
        if "hour" in raw.lower():
            return "fresh_unverified", raw
        return "unknown", f"Could not parse timestamp: {raw}"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600
    if 0 <= age_hours <= max_hours:
        return "approved_recent", f"{age_hours:.1f} hours old from source timestamp {raw}"
    return "stale", f"{age_hours:.1f} hours old from source timestamp {raw}"


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


def check_official_source(lead: SourceLead, final_job_url: str, final_apply_url: str = "") -> str:
    host = urlparse(final_job_url or lead.job_url).hostname or ""
    apply_host = urlparse(final_apply_url).hostname or ""
    if any(apply_host.endswith(ats) for ats in TRUSTED_ATS_HOSTS):
        return f"verified_via_apply_trusted_ats:{apply_host}"
    if any(host.endswith(ats) for ats in TRUSTED_ATS_HOSTS):
        return f"verified_trusted_ats:{host}"
    if lead.company_url:
        company_host = urlparse(lead.company_url).hostname or ""
        if company_host and apply_host.endswith(".".join(company_host.split(".")[-2:])):
            return f"verified_via_apply_company_domain:{apply_host}"
        if company_host and host.endswith(".".join(company_host.split(".")[-2:])):
            return f"verified_company_domain:{host}"
    if lead.source == "Company watchlist":
        return "manual_review_company_careers_page"
    return f"manual_review_unmatched_source:{host}"


def check_apply_link(original_url: str, final_url: str, ok: bool, status_code: int, evidence: str = "") -> str:
    if not original_url:
        return "rejected_missing_apply_url"
    if not ok:
        return f"rejected_apply_link_failed_http_{status_code}"
    host = urlparse(final_url or original_url).hostname or ""
    if is_board_host(host):
        return f"rejected_apply_link_still_on_job_board:{host}"
    if any(host.endswith(ats) for ats in TRUSTED_ATS_HOSTS):
        return f"verified_trusted_ats:{host}; {evidence}"
    if is_low_trust_host(host):
        return f"rejected_low_trust_apply_domain:{host}"
    return f"verified_opened_manual_domain_check_needed:{host}; {evidence}"
