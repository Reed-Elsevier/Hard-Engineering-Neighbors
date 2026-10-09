#!/usr/bin/env bash
# Ship the committed code + built UI + risk data + a server .env to the EC2 instance, then set it up.
# Usage (from repo root, Git Bash):  bash deploy/push.sh <public-ip>
# Redeploy after new commits: run it again (the venv on the server is reused).
set -euo pipefail

IP="${1:?usage: bash deploy/push.sh <public-ip>}"
KEY="$HOME/.ssh/sabwat-key.pem"
SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 "ubuntu@$IP")
ROOT="$(git rev-parse --show-toplevel)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cd "$ROOT"
if ! git diff --quiet HEAD -- backend web deploy; then
  echo "WARNING: uncommitted changes in backend/web/deploy are NOT deployed (push.sh ships HEAD)."
fi

echo "==> building UI"
(cd web && npm run build >/dev/null)

echo "==> staging $(git rev-parse --short HEAD)"
mkdir -p "$STAGE/sabwat/Data/D_risk" "$STAGE/sabwat/web"
git archive HEAD | tar -x -C "$STAGE/sabwat"
cp -r web/dist "$STAGE/sabwat/web/dist"
cp Data/D_risk/*.parquet "$STAGE/sabwat/Data/D_risk/"
# Server .env: same settings, but NO AWS keys (the instance role supplies credentials).
grep -vE '^(AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN)=' .env > "$STAGE/sabwat/.env"
sed -i 's/^DB_BACKEND=.*/DB_BACKEND=dynamodb/' "$STAGE/sabwat/.env"
tar -czf "$STAGE/sabwat.tgz" -C "$STAGE" sabwat
echo "    bundle $(du -h "$STAGE/sabwat.tgz" | cut -f1)"

echo "==> waiting for the instance to finish booting"
for i in $(seq 1 30); do "${SSH[@]}" true 2>/dev/null && break; sleep 10; done
"${SSH[@]}" 'cloud-init status --wait >/dev/null 2>&1 || true'

echo "==> uploading"
scp -i "$KEY" -o StrictHostKeyChecking=accept-new "$STAGE/sabwat.tgz" "ubuntu@$IP:/tmp/sabwat.tgz"

echo "==> installing on the server (first run ~3-5 min)"
"${SSH[@]}" 'set -e
  mkdir -p ~/sabwat
  tar -xzf /tmp/sabwat.tgz -C ~ && rm /tmp/sabwat.tgz
  chmod 600 ~/sabwat/.env
  cd ~/sabwat && bash deploy/ec2_setup.sh'

echo
echo "Sabwat is live at  http://$IP:8000"
