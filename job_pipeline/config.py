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
    enable_ai: bool = True
    freshness_hours: int = 10
    max_results_per_source: int = 50
    request_timeout_seconds: int = 25
    output_dir: Path = ROOT / "Find Jobs - CV" / "Olabisi Odogbo" / "verified_pipeline_output"


def get_settings() -> Settings:
    load_env()
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        serpapi_api_key=os.getenv("SERPAPI_API_KEY", "").strip(),
        brave_search_api_key=os.getenv("BRAVE_SEARCH_API_KEY", "").strip(),
        ai_provider=os.getenv("AI_PROVIDER", "claude").strip() or "claude",
        enable_ai=os.getenv("ENABLE_AI", "true").strip().lower() not in {"0", "false", "no"},
        freshness_hours=int(os.getenv("FRESHNESS_HOURS", "10")),
        max_results_per_source=int(os.getenv("MAX_RESULTS_PER_SOURCE", "50")),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "25")),
    )
