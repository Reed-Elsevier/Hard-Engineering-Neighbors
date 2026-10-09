# Sabwat — Fraud Ring Intelligence

> Rule engines catch individuals. Sabwat catches the *sabwatan*.

Sabwat scores a transaction in the context of the identity and ownership network around it. It explains the score with SHAP reasons, shows the ring and any ownership path to a watchlisted entity, and drafts an evidence-cited brief so an L1 analyst can decide in under a minute. Built for REPH AI Summit 2026, Track 4 (Fraud & Identity Intelligence).

* Product intent: [PROJECT.md](PROJECT.md)
* Data findings, modelling decisions, build order: [docs/PLAN.md](docs/PLAN.md)

## Layout

```
backend/          Python package `sabwat` (FastAPI + pipeline), scripts, tests
web/              React + Vite + shadcn/ui front end
deploy/           EC2 setup script and systemd unit
docs/             Plan and design notes
Data/             Company data — gitignored, never committed
artifacts/        Generated model/features/decision log — gitignored
```

## Setup (local)

Requires Python 3.11+ (developed on 3.14) and Node 20+.

```bash
# 1. Secrets
cp .env.example .env            # then fill GEMINI_API_KEY (https://aistudio.google.com/apikey), AWS_* as needed

# 2. Python
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate on Linux/macOS
pip install -r backend/requirements-dev.txt -e backend

# 3. Data: copy the event data package into ./Data (must contain Data/D_risk/*.parquet)
python backend/scripts/check_env.py      # preflight: deps, data, keys, AWS identity
python backend/scripts/inspect_data.py   # table shapes + rule-engine baseline
python backend/scripts/build.py          # ~45 s: ring/fan-in graph, FX, triage model, metrics -> artifacts/

# 4. Web
cd web && npm install && cd ..
```

## Run

```bash
# Dev: two terminals
uvicorn sabwat.api:app --app-dir backend --reload --port 8000
cd web && npm run dev                    # http://localhost:5173 (proxies /api → :8000)

# Prod-like: one process serves UI + API
cd web && npm run build && cd ..
uvicorn sabwat.api:app --app-dir backend --port 8000   # http://localhost:8000
```

## Demo

Open `http://localhost:8000/?id=TXN00000241` to score a transaction on load (alert IDs such as `ALR0000001` work too). The example cards at the top load the four pitch scenarios. The brief is written by Gemini (`LLM_PROVIDER=gemini`, default) or Claude (`LLM_PROVIDER=anthropic`). Without a key, or if the AI is unavailable, it uses the labelled template fallback; everything else works offline.

## Test

```bash
cd backend && pytest && ruff check .
cd web && npm run lint && npm run build
```

## Database (AWS DynamoDB)

Analyst decisions are logged to DynamoDB table `sabwat-decisions`. Briefs are cached in `sabwat-briefs`. If AWS can't be reached, for example because the SSO session expired, writes fall back to `artifacts/decisions.db` (SQLite). Set `DB_BACKEND=sqlite` to stay fully local.

One-time setup, using the AWS keys in `.env`. It is idempotent and only touches `sabwat-*` resources in the shared account:

```bash
python backend/scripts/provision_aws.py   # tables + IAM role/instance profile sabwat-ec2-profile
python backend/scripts/check_env.py       # should show both tables ACTIVE
```

## Deploy (AWS EC2)

Two commands from the laptop (Git Bash, fresh AWS keys in `.env`):

```bash
python deploy/launch_ec2.py          # sabwat-key, sabwat-web security group (your IP only), t3.small with sabwat-ec2-profile
bash deploy/push.sh <public-ip>      # ships HEAD + built UI + Data/D_risk parquet + .env without AWS keys, then sets up systemd
```

The server needs no AWS keys: the instance role (DynamoDB `sabwat-*` only) supplies rotating credentials. Redeploy by committing and re-running `push.sh`. Access control:

```bash
python deploy/launch_ec2.py --allow <venue-ip>   # add the venue Wi-Fi IP
python deploy/launch_ec2.py --open-all           # judging window only: port 8000 open to everyone
python deploy/launch_ec2.py --close-all          # close it again
```

## Responsible AI

* All data is synthetic. Results are preliminary.
* No PII is sent to the LLM; only record IDs and computed facts.
* The model recommends and a human decides. Every decision is logged.
* No individual analyst ranking.
