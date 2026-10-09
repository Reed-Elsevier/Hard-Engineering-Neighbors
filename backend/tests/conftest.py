"""Test isolation: never write to AWS or call Claude from tests.

Set before any sabwat import; load_dotenv() does not override variables that already exist.
"""

import os
import tempfile
from pathlib import Path

import pytest

os.environ["DB_BACKEND"] = "sqlite"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["DECISIONS_DB"] = str(Path(tempfile.mkdtemp()) / "test_decisions.db")

SAMPLES = Path(__file__).parent / "sample_inputs"


def artifacts_ready() -> bool:
    from sabwat.config import settings

    return settings.risk_dir.is_dir() and (settings.artifacts_dir / "model.pkl").is_file()


needs_artifacts = pytest.mark.skipif(
    not artifacts_ready(), reason="needs Data/ and artifacts/ (run backend/scripts/build.py)")
