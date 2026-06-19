from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.local"


def load_env(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    serpapi_api_key: str
    brave_search_api_key: str
    ai_provider: str = "claude"
    ai_model: str = "claude-haiku-4-5-20251001"
    enable_ai: bool = True
    freshness_hours: int = 10
    max_results_per_source: int = 50
    request_timeout_seconds: int = 25
    output_dir: Path = ROOT / "verified_pipeline_output"
    candidate_name: str = "Sample Candidate"
    candidate_location: str = "Remote"
    candidate_country: str = ""
    target_work_regions: tuple[str, ...] = ("Worldwide",)
    target_roles: tuple[str, ...] = (
        "customer support",
        "customer success",
        "crm specialist",
        "virtual assistant",
        "operations assistant",
        "sales support",
    )
    candidate_strengths: tuple[str, ...] = (
        "customer support",
        "CRM hygiene",
        "email, phone, and chat support",
        "client follow-up",
        "calendar and admin coordination",
        "remote work discipline",
    )


def get_settings() -> Settings:
    load_env()
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        serpapi_api_key=os.getenv("SERPAPI_API_KEY", "").strip(),
        brave_search_api_key=os.getenv("BRAVE_SEARCH_API_KEY", "").strip(),
        ai_provider=os.getenv("AI_PROVIDER", "claude").strip() or "claude",
        ai_model=os.getenv("AI_MODEL", "claude-haiku-4-5-20251001").strip() or "claude-haiku-4-5-20251001",
        enable_ai=os.getenv("ENABLE_AI", "true").strip().lower() not in {"0", "false", "no"},
        freshness_hours=int(os.getenv("FRESHNESS_HOURS", "10")),
        max_results_per_source=int(os.getenv("MAX_RESULTS_PER_SOURCE", "50")),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "25")),
        output_dir=Path(os.getenv("OUTPUT_DIR", str(ROOT / "verified_pipeline_output"))),
        candidate_name=os.getenv("CANDIDATE_NAME", "Sample Candidate").strip() or "Sample Candidate",
        candidate_location=os.getenv("CANDIDATE_LOCATION", "Remote").strip() or "Remote",
        candidate_country=os.getenv("CANDIDATE_COUNTRY", "").strip(),
        target_work_regions=split_env_tuple(os.getenv("TARGET_WORK_REGIONS", "Worldwide")),
        target_roles=split_env_tuple(
            os.getenv(
                "TARGET_ROLES",
                "customer support,customer success,crm specialist,virtual assistant,operations assistant,sales support",
            )
        ),
        candidate_strengths=split_env_tuple(
            os.getenv(
                "CANDIDATE_STRENGTHS",
                "customer support,CRM hygiene,email phone and chat support,client follow-up,calendar and admin coordination,remote work discipline",
            )
        ),
    )


def split_env_tuple(value: str) -> tuple[str, ...]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    return tuple(items)
