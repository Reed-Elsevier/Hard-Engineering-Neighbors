#!/usr/bin/env bash
# Server-side setup, run on the instance from ~/sabwat (deploy/push.sh does this for you).
# Expects: Data/D_risk/*.parquet, web/dist (built on the laptop) and .env without AWS keys.
set -euo pipefail

sudo apt-get install -y -qq python3-venv python3-pip >/dev/null

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r backend/requirements.txt -e backend

# UI is prebuilt on the laptop (no Node needed on the server).
[ -f web/dist/index.html ] || { echo "web/dist missing: run deploy/push.sh from the laptop"; exit 1; }

# Network graph, FX table, triage model and metrics (~1 min).
.venv/bin/python backend/scripts/build.py | tail -3

.venv/bin/python backend/scripts/check_env.py || true

sudo cp deploy/sabwat.service /etc/systemd/system/sabwat.service
sudo systemctl daemon-reload
sudo systemctl enable sabwat >/dev/null
sudo systemctl restart sabwat

# Wait for the engine to load, then show health.
for i in $(seq 1 60); do
  curl -fsS localhost:8000/api/health 2>/dev/null | grep -q '"engine_ready":true' && break
  sleep 2
done
curl -fsS localhost:8000/api/health && echo
