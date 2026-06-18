from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CandidateProfile:
    name: str = "Olabisi Odogbo"
    location: str = "Lagos, Nigeria"
    target_roles: tuple[str, ...] = (
        "customer support",
        "customer success",
        "crm specialist",
        "hubspot",
        "virtual assistant",
        "operations assistant",
        "sales support",
    )
    strengths: tuple[str, ...] = (
        "HubSpot certification",
        "CRM hygiene",
        "WhatsApp, email, phone, and chat support",
        "client follow-up",
        "calendar and admin coordination",
        "remote work discipline",
    )


@dataclass
class SourceLead:
    source: str
    title: str
    company: str
    job_url: str
    apply_url: str = ""
    company_url: str = ""
    company_linkedin: str = ""
    location: str = ""
    salary: str = ""
    description: str = ""
    posted_at: str = ""
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerifiedProspect:
    source: str
    title: str
    company: str
    status: str
    confidence_score: int
    job_url: str
    apply_url: str
    company_url: str
    company_linkedin: str
    location: str
    salary: str
    posted_at: str
    freshness_status: str
    freshness_evidence: str
    official_source_status: str
    apply_link_status: str
    country_eligibility: str
    eligibility_evidence: str
    scam_risk: str
    rejection_reason: str
    verification_summary: str
    candidate_fit: str
    apply_strategy: str
    linkedin_outreach_message: str
    email_followup_message: str
    materials_to_prepare: str
    company_research_notes: str
    outreach_strategy: str
    evidence_links: str
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ai_notes: str = ""
