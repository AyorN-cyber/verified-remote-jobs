from __future__ import annotations

import json
import requests

from .config import Settings
from .models import CandidateProfile, SourceLead


def analyze_with_claude(
    settings: Settings,
    lead: SourceLead,
    page_text: str,
    candidate: CandidateProfile,
) -> dict[str, str]:
    if not settings.enable_ai or not settings.anthropic_api_key:
        return {}

    prompt = {
        "task": "Extract job verification evidence. Return strict JSON only.",
        "candidate": {
            "name": candidate.name,
            "location": candidate.location,
            "target_roles": candidate.target_roles,
            "strengths": candidate.strengths,
        },
        "job": {
            "source": lead.source,
            "title": lead.title,
            "company": lead.company,
            "url": lead.job_url,
            "location": lead.location,
            "salary": lead.salary,
            "posted_at": lead.posted_at,
            "text": page_text[:12000],
        },
        "required_json_keys": [
            "role_match",
            "country_eligibility",
            "country_evidence",
            "restriction_evidence",
            "scam_red_flags",
            "verification_summary",
            "candidate_fit_summary",
            "apply_strategy",
            "linkedin_outreach_message",
            "email_followup_message",
            "materials_to_prepare",
            "company_research_notes",
            "outreach_strategy",
        ],
        "style_rules": [
            "Be concise and specific.",
            "Do not invent a recruiter name, email, salary, or eligibility evidence.",
            "If a fact is missing, say it needs verification.",
            "Write outreach messages in a polished human tone with no hype.",
            "Keep LinkedIn message under 600 characters.",
            "Keep email follow-up under 140 words.",
        ],
    }

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        timeout=settings.request_timeout_seconds,
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-3-5-haiku-latest",
            "max_tokens": 900,
            "temperature": 0,
            "messages": [{"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
        },
    )
    response.raise_for_status()
    data = response.json()
    text = data.get("content", [{}])[0].get("text", "{}")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"raw_ai_response": text[:1000]}
    return {str(k): str(v) for k, v in parsed.items()}
