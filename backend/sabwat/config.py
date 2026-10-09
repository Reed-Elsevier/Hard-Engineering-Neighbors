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


def _data_dir() -> Path:
    """DATA_DIR if set; else ./Data (local dev) or ./data (where the deploy platform copies uploads)."""
    if os.getenv("DATA_DIR"):
        return _path("DATA_DIR", "Data")
    for name in ("Data", "data"):
        if (REPO_ROOT / name).is_dir():
            return REPO_ROOT / name
    return REPO_ROOT / "data"


def _path(var: str, default: str) -> Path:
    p = Path(os.getenv(var) or default)
    return p if p.is_absolute() else REPO_ROOT / p


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    artifacts_dir: Path
    decisions_db: Path
    llm_provider: str  # "gemini", "anthropic" or "bedrock"
    bedrock_model_id: str | None
    gemini_api_key: str | None
    gemini_model: str
    gemini_fallback_model: str | None
    anthropic_api_key: str | None
    anthropic_model: str
    anthropic_effort: str
    llm_timeout_s: float
    llm_max_retries: int
    web_dist: Path
    db_backend: str
    aws_region: str
    ddb_table_decisions: str
    ddb_table_briefs: str

    @property
    def risk_dir(self) -> Path:
        # Local: Data/D_risk/*.parquet. Deploy platform: uploads land flat in data/*.parquet.
        sub = self.data_dir / "D_risk"
        return sub if sub.is_dir() else self.data_dir

    @property
    def llm_enabled(self) -> bool:
        return bool({"gemini": self.gemini_api_key, "anthropic": self.anthropic_api_key,
                     "bedrock": self.bedrock_model_id}.get(self.llm_provider))

    @property
    def llm_model(self) -> str:
        return {"gemini": self.gemini_model, "bedrock": self.bedrock_model_id or ""}.get(
            self.llm_provider, self.anthropic_model)


def load_settings() -> Settings:
    return Settings(
        data_dir=_data_dir(),
        artifacts_dir=_path("ARTIFACTS_DIR", "artifacts"),
        decisions_db=_path("DECISIONS_DB", "artifacts/decisions.db"),
        # Default: Bedrock when the host provides a model (deploy platform), else Gemini.
        llm_provider=(os.getenv("LLM_PROVIDER") or ("bedrock" if os.getenv("BEDROCK_MODEL_ID") else "gemini")).strip().lower(),
        bedrock_model_id=os.getenv("BEDROCK_MODEL_ID") or None,
        gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        gemini_fallback_model=os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite") or None,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5"),
        anthropic_effort=os.getenv("ANTHROPIC_EFFORT", "low"),
        llm_timeout_s=float(os.getenv("LLM_TIMEOUT_S") or os.getenv("ANTHROPIC_TIMEOUT_S") or "12"),
        llm_max_retries=int(os.getenv("LLM_MAX_RETRIES") or os.getenv("ANTHROPIC_MAX_RETRIES") or "2"),
        web_dist=REPO_ROOT / "web" / "dist",
        db_backend=os.getenv("DB_BACKEND", "sqlite").lower(),
        aws_region=os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION") or "ap-southeast-1",
        ddb_table_decisions=os.getenv("DDB_TABLE_DECISIONS", "sabwat-decisions"),
        ddb_table_briefs=os.getenv("DDB_TABLE_BRIEFS", "sabwat-briefs"),
    )


settings = load_settings()
