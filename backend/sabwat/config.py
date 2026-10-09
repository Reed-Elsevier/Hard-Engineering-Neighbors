"""Central settings. Reads the repo-root .env once; every path is resolved against the repo root."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

# Blank AWS_* entries (as on EC2, where the instance role supplies credentials) must not shadow
# boto3's credential chain, so drop them.
for _k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
    if os.environ.get(_k) == "":
        del os.environ[_k]


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
    anthropic_effort: str
    anthropic_timeout_s: float
    anthropic_max_retries: int
    web_dist: Path
    db_backend: str
    aws_region: str
    ddb_table_decisions: str
    ddb_table_briefs: str

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
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5"),
        anthropic_effort=os.getenv("ANTHROPIC_EFFORT", "low"),
        anthropic_timeout_s=float(os.getenv("ANTHROPIC_TIMEOUT_S", "20")),
        anthropic_max_retries=int(os.getenv("ANTHROPIC_MAX_RETRIES", "2")),
        web_dist=REPO_ROOT / "web" / "dist",
        db_backend=os.getenv("DB_BACKEND", "sqlite").lower(),
        aws_region=os.getenv("AWS_DEFAULT_REGION", "ap-southeast-1"),
        ddb_table_decisions=os.getenv("DDB_TABLE_DECISIONS", "sabwat-decisions"),
        ddb_table_briefs=os.getenv("DDB_TABLE_BRIEFS", "sabwat-briefs"),
    )


settings = load_settings()
