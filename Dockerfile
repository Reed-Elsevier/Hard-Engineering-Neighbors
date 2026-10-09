# Sabwat: one container serving the React UI and the FastAPI API on port 8000.
# Data files (*.parquet from Data/D_risk) are NOT in the repo: the deploy platform copies uploads into ./data.

# --- 1. Build the UI ---
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# --- 2. Python app ---
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# LightGBM needs the OpenMP runtime.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY . .
RUN pip install -e backend
COPY --from=web /web/dist web/dist
# Build the ring graph, FX table and triage model now if the data is already here (else at start-up).
RUN if ls data/*.parquet Data/D_risk/*.parquet >/dev/null 2>&1; then python backend/scripts/build.py; fi

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s CMD curl -fsS localhost:8000/api/health || exit 1
CMD ["bash", "deploy/start.sh"]
