"""FastAPI app: JSON API under /api, and the built React UI (web/dist) at /.

Every endpoint returns a readable error instead of crashing: input problems are 422 with the
offending field named; anything unexpected is a 500 with a short message.
"""

import hashlib
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sabwat import __version__
from sabwat.config import settings
from sabwat.core.brief import generate_brief
from sabwat.core.db import BriefCache, Decision, get_store
from sabwat.core.evidence import build_evidence
from sabwat.core.normalize import InputError, read_csv
from sabwat.core.score import get_engine

log = logging.getLogger("sabwat")
MAX_BATCH_ROWS = 2000

_state: dict[str, Any] = {"engine_error": None}
_store = get_store()
_brief_cache = BriefCache()


def _warm_engine() -> None:
    try:
        get_engine()
    except Exception as e:  # surfaced through /api/health; never crashes the app
        log.exception("engine failed to load")
        _state["engine_error"] = f"{type(e).__name__}: {e}"


@asynccontextmanager
async def _lifespan(_: FastAPI):
    # Load data + model in the background (~10 s) so /api/health answers immediately.
    threading.Thread(target=_warm_engine, daemon=True).start()
    yield


app = FastAPI(title="Sabwat", version=__version__, lifespan=_lifespan)


@app.exception_handler(InputError)
def _input_error(_: Request, e: InputError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": str(e), "field": e.field})


@app.exception_handler(Exception)
def _unexpected(_: Request, e: Exception) -> JSONResponse:
    log.exception("unhandled error")
    return JSONResponse(status_code=500, content={"error": f"Internal error: {type(e).__name__}"})


def _engine():
    if _state["engine_error"]:
        raise HTTPException(503, f"Scoring engine unavailable: {_state['engine_error']}. "
                                 "Run backend/scripts/build.py.")
    return get_engine()


class ScoreRequest(BaseModel):
    txn_id: str | None = None
    transaction: dict[str, Any] | None = None

    def record(self) -> dict:
        if self.transaction:
            return self.transaction
        if self.txn_id and self.txn_id.strip():
            return {"txn_id": self.txn_id}
        raise InputError("txn_id", "provide a txn_id or a transaction object")


class BatchRequest(BaseModel):
    rows: list[dict[str, Any]] | None = None
    csv: str | None = None


class DecisionRequest(BaseModel):
    txn_id: str
    decision: Literal["escalate", "review", "dismiss"]
    note: str = Field("", max_length=2000)
    score: float | None = None
    band: Literal["Low", "Med", "High"] | None = None
    layers_fired: list[str] = Field(default_factory=list)
    brief_source: Literal["claude", "template"] | None = None


@app.get("/api/health")
def health() -> dict:
    loaded = get_engine.cache_info().currsize > 0
    return {
        "status": "ok",
        "version": __version__,
        "data_available": settings.risk_dir.is_dir(),
        "model_available": (settings.artifacts_dir / "model.pkl").is_file(),
        "engine_ready": loaded,
        "engine_error": _state["engine_error"],
        "llm_enabled": settings.llm_enabled,
        "llm_model": settings.anthropic_model if settings.llm_enabled else None,
        "db_backend": _store.name,
    }


@app.post("/api/score")
def score(req: ScoreRequest) -> dict:
    t0 = time.monotonic()
    result = _engine().score(req.record())
    result["evidence"] = build_evidence(result)
    result["latency_s"] = round(time.monotonic() - t0, 3)
    return result


@app.post("/api/brief")
def brief(req: ScoreRequest) -> dict:
    result = _engine().score(req.record())
    pack = build_evidence(result)
    key = hashlib.sha256(json.dumps(pack, sort_keys=True, default=str).encode()).hexdigest()[:16]
    tid = result["txn"].get("txn_id")
    if tid and (hit := _brief_cache.get(tid, key)):
        return {**hit, "cached": True}
    out = generate_brief(pack)
    if tid and out["source"] == "claude":
        _brief_cache.put(tid, key, out)
    return {**out, "cached": False}


def _batch_rows(records: list[dict]) -> list[dict]:
    if len(records) > MAX_BATCH_ROWS:
        raise InputError("rows", f"at most {MAX_BATCH_ROWS} rows per batch, got {len(records)}")
    eng = _engine()
    out = []
    for i, rec in enumerate(records, start=1):
        try:
            r = eng.score(rec)
            out.append({"row": i, "txn_id": r["txn"].get("txn_id"),
                        "account_id": r["txn"].get("account_id"),
                        "amount_usd": r["txn"].get("amount_usd"),
                        "score": r["score"], "band": r["band"], "layers_fired": r["layers_fired"],
                        "signals": [s["label"] for s in r["network"]["signals"]],
                        "triage_p_real": r["triage"].get("p_real"),
                        "warnings": r["warnings"] + r["data_gaps"], "error": None})
        except InputError as e:
            out.append({"row": i, "txn_id": rec.get("txn_id"), "score": None, "band": None,
                        "layers_fired": [], "signals": [], "error": str(e)})
    out.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    return out


@app.post("/api/score/batch")
def score_batch(req: BatchRequest) -> dict:
    records = req.rows if req.rows is not None else read_csv(req.csv or "")
    rows = _batch_rows(records)
    return {"rows": rows, "scored": sum(r["error"] is None for r in rows),
            "errors": sum(r["error"] is not None for r in rows)}


@app.post("/api/score/batch/upload")
async def score_batch_upload(file: Annotated[UploadFile, File()]) -> dict:
    text = (await file.read()).decode("utf-8-sig", errors="replace")
    rows = _batch_rows(read_csv(text))
    return {"rows": rows, "scored": sum(r["error"] is None for r in rows),
            "errors": sum(r["error"] is not None for r in rows)}


@app.post("/api/decision")
def decide(req: DecisionRequest) -> dict:
    version = get_engine().model.version if get_engine.cache_info().currsize else None
    d = Decision(**{**req.model_dump(), "txn_id": req.txn_id.strip().upper(),
                    "model_version": version})
    return {"stored_in": _store.put(d), "decision": d.model_dump()}


@app.get("/api/decisions/{txn_id}")
def decisions(txn_id: str) -> dict:
    return {"txn_id": txn_id.upper(),
            "decisions": [d.model_dump() for d in _store.history(txn_id.strip().upper())]}


@app.get("/api/record/{record_id}")
def record(record_id: str) -> dict:
    rec = _engine().record(record_id)
    if rec is None:
        raise HTTPException(404, f"No record {record_id.upper()}")
    return rec


@app.get("/api/metrics")
def metrics() -> dict:
    return _engine().metrics


@app.get("/api/examples")
def examples() -> dict:
    return {"examples": _engine().metrics.get("examples", [])}


# Mounted last so /api routes take precedence. Absent in dev (Vite serves the UI on :5173).
if settings.web_dist.is_dir():
    app.mount("/", StaticFiles(directory=settings.web_dist, html=True), name="web")
