"""FastAPI app: JSON API under /api, and the built React UI (web/dist) at /."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from sabwat import __version__
from sabwat.config import settings

app = FastAPI(title="Sabwat", version=__version__)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "data_available": settings.risk_dir.is_dir(),
        "model_available": (settings.artifacts_dir / "model.pkl").is_file(),
        "llm_enabled": settings.llm_enabled,
    }


# Mounted last so /api routes take precedence. Absent in dev (Vite serves the UI on :5173).
if settings.web_dist.is_dir():
    app.mount("/", StaticFiles(directory=settings.web_dist, html=True), name="web")
