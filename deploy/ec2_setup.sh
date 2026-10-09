#!/usr/bin/env bash
# One-time EC2 (Ubuntu) setup. Run on the instance from the repo root (~/sabwat).
# Prereqs: Data/ copied to ~/sabwat/Data from the event environment, and .env filled in.
# Redeploy later with:  git pull && bash deploy/ec2_setup.sh
set -euo pipefail

sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip nodejs npm

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt -e backend

(cd web && npm ci && npm run build)

if [ -f backend/scripts/build.py ]; then
  .venv/bin/python backend/scripts/build.py
fi

sudo cp deploy/sabwat.service /etc/systemd/system/sabwat.service
sudo systemctl daemon-reload
sudo systemctl enable --now sabwat
sudo systemctl restart sabwat
sleep 2 && curl -fsS localhost:8000/api/health && echo
