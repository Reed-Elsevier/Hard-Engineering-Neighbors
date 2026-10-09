"""Analyst brief: evidence pack -> Claude (structured JSON) -> validated, or a deterministic template.

The score, reasons and graph never depend on this module. Claude recommends; a human decides.

Usage:  python -m sabwat.core.brief TXN00000001
"""

import json
import logging
import time
from typing import Literal

import anthropic
from pydantic import BaseModel, Field, ValidationError

from sabwat.config import settings

log = logging.getLogger(__name__)

SYSTEM = (
    "You are an AML investigation assistant for an L1 fraud analyst. Use ONLY the evidence "
    "provided. Cite record IDs from the evidence in every finding. If evidence is insufficient, "
    "say so. You recommend; a human decides. Keep risk_summary to 60 words or fewer. Do not "
    "invent record IDs, names, amounts or dates."
)


class Finding(BaseModel):
    finding: str
    evidence_ids: list[str]
    severity: Literal["high", "medium", "low"]


class Brief(BaseModel):
    risk_summary: str
    key_findings: list[Finding]
    recommended_action: Literal["escalate", "review", "dismiss"]
    open_questions: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]


# Hand-written so it stays inside the structured-output schema subset.
SCHEMA = {
    "type": "object",
    "properties": {
        "risk_summary": {"type": "string"},
        "key_findings": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "finding": {"type": "string"},
                "evidence_ids": {"type": "array", "items": {"type": "string"}},
                "severity": {"type": "string", "enum": ["high", "medium", "low"]},
            },
            "required": ["finding", "evidence_ids", "severity"],
            "additionalProperties": False,
        }},
        "recommended_action": {"type": "string", "enum": ["escalate", "review", "dismiss"]},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["risk_summary", "key_findings", "recommended_action", "open_questions",
                 "confidence"],
    "additionalProperties": False,
}


def validate(brief: Brief, pack: dict) -> tuple[Brief, dict]:
    """Drop findings citing IDs outside the pack; never let High + dismiss through."""
    allowed = set(pack["allowed_ids"])
    kept = [f for f in brief.key_findings if f.evidence_ids and set(f.evidence_ids) <= allowed]
    report = {"findings_total": len(brief.key_findings),
              "findings_dropped": len(brief.key_findings) - len(kept), "warnings": []}
    brief = brief.model_copy(update={"key_findings": kept})
    if pack["band"] == "High" and brief.recommended_action == "dismiss":
        brief = brief.model_copy(update={"recommended_action": "review"})
        report["warnings"].append("Model suggested dismiss on a High score; changed to review.")
    if not kept:
        raise ValueError("no finding cited valid evidence IDs")
    if len(brief.risk_summary.split()) > 60:
        report["warnings"].append("risk_summary exceeded 60 words")
    return brief, report


def template_brief(pack: dict) -> Brief:
    """Deterministic brief from the evidence pack (used when Claude is unavailable)."""
    sev = {"network_signal": "high", "watchlist": "high", "ring": "high", "ownership": "medium",
           "alert": "medium", "triage_reason": "low"}
    reasons = [f for f in pack["facts"] if f["kind"] == "triage_reason"][:2]  # strongest two only
    findings = [Finding(finding=f["text"], evidence_ids=f["record_ids"],
                        severity=sev.get(f["kind"], "low"))
                for f in pack["facts"]
                if f["kind"] in sev and f["record_ids"]
                and (f["kind"] != "triage_reason" or f in reasons)
                and not f["text"].startswith("No network signals")][:6]
    if not findings:
        findings = [Finding(finding=pack["facts"][0]["text"],
                            evidence_ids=pack["facts"][0]["record_ids"], severity="low")]
    action = {"High": "escalate", "Med": "review", "Low": "dismiss"}[pack["band"]]
    return Brief(
        risk_summary=(f"{pack['txn_id']} scores {pack['score']} ({pack['band']}). Layers fired: "
                      f"{', '.join(pack['layers_fired']) or 'none'}. See findings for the cited "
                      f"records."),
        key_findings=findings,
        recommended_action=action,
        open_questions=[f["text"] for f in pack["facts"] if f["kind"] == "data_gap"],
        confidence="medium" if pack["layers_fired"] else "low",
    )


def _call_claude(client: anthropic.Anthropic, pack: dict, error: str | None) -> Brief:
    prompt = ("Write the analyst brief for this evidence pack.\n\n<evidence_pack>\n"
              + json.dumps({k: pack[k] for k in ("txn_id", "score", "band", "layers_fired", "facts")},
                           indent=1)
              + "\n</evidence_pack>")
    if error:
        prompt += (f"\n\nYour previous answer failed validation: {error}. Every evidence_ids entry "
                   f"must be one of: {', '.join(pack['allowed_ids'])}.")
    resp = client.beta.messages.create(
        model=settings.anthropic_model,
        max_tokens=4000,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": settings.anthropic_effort,
                       "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if resp.stop_reason == "refusal":
        raise ValueError(f"model declined ({getattr(resp.stop_details, 'category', None)})")
    if resp.stop_reason == "max_tokens":
        raise ValueError("response truncated at max_tokens")
    text = next(b.text for b in resp.content if b.type == "text")
    return Brief.model_validate_json(text)


def generate_brief(pack: dict) -> dict:
    """Returns {"brief", "source": "claude"|"template", "label", "validation", "latency_s"}."""
    t0 = time.monotonic()
    error = None
    if settings.llm_enabled:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key,
                                     timeout=settings.anthropic_timeout_s, max_retries=0)
        for attempt in range(settings.anthropic_max_retries + 1):
            if attempt and time.monotonic() - t0 > settings.anthropic_timeout_s:
                break  # keep total latency near one timeout, not three
            try:
                brief, report = validate(_call_claude(client, pack, error), pack)
                report["attempts"] = attempt + 1
                return {"brief": brief.model_dump(), "source": "claude",
                        "label": f"AI draft ({settings.anthropic_model}) - analyst decides",
                        "validation": report, "latency_s": round(time.monotonic() - t0, 2)}
            except (ValidationError, ValueError, StopIteration) as e:
                error = str(e)[:500]
                log.warning("brief attempt %d failed validation: %s", attempt + 1, error)
            except (anthropic.APIConnectionError, anthropic.APITimeoutError,
                    anthropic.RateLimitError, anthropic.APIStatusError) as e:
                error = f"{type(e).__name__}: {str(e)[:200]}"
                log.warning("brief attempt %d API error: %s", attempt + 1, error)
                if isinstance(e, anthropic.APIStatusError) and e.status_code < 500 \
                        and not isinstance(e, anthropic.RateLimitError):
                    break  # 4xx other than 429 will not fix itself
    return {"brief": template_brief(pack).model_dump(), "source": "template",
            "label": "AI unavailable - template brief",
            "validation": {"error": error} if error else {},
            "latency_s": round(time.monotonic() - t0, 2)}


if __name__ == "__main__":
    import sys

    from sabwat.core.evidence import build_evidence
    from sabwat.core.score import get_engine

    res = get_engine().score({"txn_id": sys.argv[1]})
    print(json.dumps(generate_brief(build_evidence(res)), indent=1))
