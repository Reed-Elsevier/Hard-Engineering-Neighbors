#!/usr/bin/env bash
# Container entrypoint: build artifacts if the image was built without data, then serve UI + API.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f artifacts/model.pkl ]; then
  if ls data/*.parquet Data/D_risk/*.parquet >/dev/null 2>&1; then
    echo "Building artifacts (ring graph, FX, triage model)..."
    python backend/scripts/build.py
  else
    echo "WARNING: no data found in ./data (upload the Data/D_risk parquet files). The UI starts, scoring will not."
  fi
fi

exec uvicorn sabwat.api:app --app-dir backend --host 0.0.0.0 --port "${PORT:-8000}"
