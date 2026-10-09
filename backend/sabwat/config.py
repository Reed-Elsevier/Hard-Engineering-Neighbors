"""Central settings. Reads the repo-root .env once; every path is resolved against the repo root."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")


def _path(var: str, default: str) -> Path:
    p = Path(os.getenv(var) or default)
    return p if p.is_absolute() else REPO_ROOT / p


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    artifacts_dir: Path
    decisions_db: Path
    anthropic_api_key: str | None
    anthropic_model: str
    anthropic_timeout_s: float
    anthropic_max_retries: int
    web_dist: Path

    @property
    def risk_dir(self) -> Path:
        return self.data_dir / "D_risk"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


def load_settings() -> Settings:
    return Settings(
        data_dir=_path("DATA_DIR", "Data"),
        artifacts_dir=_path("ARTIFACTS_DIR", "artifacts"),
        decisions_db=_path("DECISIONS_DB", "artifacts/decisions.db"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        anthropic_timeout_s=float(os.getenv("ANTHROPIC_TIMEOUT_S", "20")),
        anthropic_max_retries=int(os.getenv("ANTHROPIC_MAX_RETRIES", "2")),
        web_dist=REPO_ROOT / "web" / "dist",
    )


settings = load_settings()
