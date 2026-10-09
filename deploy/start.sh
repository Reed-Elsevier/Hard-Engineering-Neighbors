#!/usr/bin/env bash
# Container entrypoint: serve UI + API. If artifacts/model.pkl is missing, the app builds it
# in the background on startup (see sabwat.api._ensure_artifacts), so /api/health answers
# immediately while the engine comes up.
set -euo pipefail
cd "$(dirname "$0")/.."

exec uvicorn sabwat.api:app --app-dir backend --host 0.0.0.0 --port "${PORT:-8000}"
