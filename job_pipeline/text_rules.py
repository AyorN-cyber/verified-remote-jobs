from __future__ import annotations

import re


ROLE_KEYWORDS = (
    "customer support",
    "customer service",
    "customer success",
    "client success",
    "support specialist",
    "support agent",
    "crm",
    "hubspot",
    "virtual assistant",
    "operations assistant",
    "sales development",
    "sales support",
    "admin assistant",
)

GLOBAL_ELIGIBILITY_TERMS = (
    "anywhere in the world",
    "work from anywhere",
    "worldwide",
    "global remote",
    "globally remote",
    "remote worldwide",
    "fully remote globally",
    "africa",
    "emea",
    "nigeria",
)

RESTRICTED_LOCATION_PATTERNS = (
    r"\bus citizens? only\b",
    r"\bu\.s\. citizens? only\b",
    r"\bauthorized to work in the (united states|u\.s\.|us)\b",
    r"\bmust be authorized to work in the (united states|u\.s\.|us)\b",
    r"\bmust reside in\b",
    r"\bbased in the (united states|u\.s\.|us|canada|uk|united kingdom|european union|eu)\b",
    r"\bremote in (the )?(united states|u\.s\.|us|canada|uk|united kingdom)\b",
    r"\bremote.{0,50}\b(united states|u\.s\.|us only|canada only|uk only|united kingdom only)\b",
    r"\b-\s*(united states|canada|uk|united kingdom)\b",
    r"\bsecurity clearance\b",
    r"\bhybrid\b",
    r"\bon-?site\b",
)

SCAM_PATTERNS = (
    r"\bpay (a )?(fee|deposit|registration)\b",
    r"\bpay (to apply|before interview|before training|for equipment)\b",
    r"\bpay.{0,40}\b(application fee|registration fee|training fee|equipment fee)\b",
    r"\bbuy (equipment|starter kit|software)\b",
    r"\bcrypto\b",
    r"\btelegram only\b",
    r"\bwhatsapp only\b",
    r"\bbvn\b",
    r"\botp\b",
    r"\bprocessing checks?\b",
    r"\bdeposit checks?\b",
)

PAYWALL_PATTERNS = (
    r"\bunlock.{0,80}\bjobs?\b",
    r"\bpay (to apply|before applying)\b",
    r"\bsubscription\b",
    r"\bcredits?.{0,80}\bcontact\b",
)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def has_role_match(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in ROLE_KEYWORDS)


def find_global_eligibility(text: str) -> tuple[str, str]:
    lowered = text.lower()
    for pattern in RESTRICTED_LOCATION_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            return "rejected", match.group(0)
    for term in GLOBAL_ELIGIBILITY_TERMS:
        if term in lowered:
            return "eligible", term
    return "manual_review", "No explicit Nigeria/global eligibility language found."


def find_scam_risk(text: str) -> tuple[str, str]:
    lowered = text.lower()
    for pattern in SCAM_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            return "high", match.group(0)
    for pattern in PAYWALL_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            return "medium", match.group(0)
    return "low", "No payment, crypto, OTP, BVN, fake-check, or forced off-platform red flag found."
