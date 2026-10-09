"""Analyst brief: evidence pack -> LLM (JSON-schema output) -> validated, or a deterministic template.

Provider is LLM_PROVIDER: "gemini" (Google AI Studio key), "anthropic" (Claude API key) or
"bedrock" (Claude on AWS Bedrock via the host's IAM role; default when BEDROCK_MODEL_ID is set).
The score, reasons and graph never depend on this module. The LLM recommends; a human decides.

Usage:  python -m sabwat.core.brief TXN00000001
"""

import json
import logging
import time
from typing import Literal

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


class LLMUnavailable(Exception):
    """Provider/API failure. `retryable` is False for errors that will not fix themselves."""

    def __init__(self, message: str, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


def _prompt(pack: dict, error: str | None) -> str:
    prompt = ("Write the analyst brief for this evidence pack.\n\n<evidence_pack>\n"
              + json.dumps({k: pack[k] for k in ("txn_id", "score", "band", "layers_fired", "facts")},
                           indent=1)
              + "\n</evidence_pack>")
    if error:
        prompt += (f"\n\nYour previous answer failed validation: {error}. Every evidence_ids entry "
                   f"must be one of: {', '.join(pack['allowed_ids'])}.")
    return prompt


def _call_gemini(pack: dict, error: str | None, fallback: bool = False) -> Brief:
    """Gemini (Google AI Studio key) with a JSON-schema-constrained response.

    `fallback` switches to GEMINI_FALLBACK_MODEL (free-tier models are often overloaded: 503).
    """
    import httpx
    from google import genai
    from google.genai import errors, types

    client = genai.Client(api_key=settings.gemini_api_key,
                          http_options=types.HttpOptions(timeout=int(settings.llm_timeout_s * 1000)))
    try:
        resp = client.models.generate_content(
            model=_gemini_model(fallback),
            contents=_prompt(pack, error),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                response_mime_type="application/json",
                response_json_schema=SCHEMA,
                temperature=0,
                max_output_tokens=4000,
            ),
        )
    except errors.ClientError as e:  # 4xx: bad key/model are fatal; 429 quota is retryable
        raise LLMUnavailable(f"Gemini {e.code}: {str(e)[:200]}", retryable=e.code == 429) from e
    except (errors.ServerError, httpx.HTTPError) as e:
        raise LLMUnavailable(f"Gemini {type(e).__name__}: {str(e)[:200]}", retryable=True) from e
    if resp.prompt_feedback and resp.prompt_feedback.block_reason:
        raise ValueError(f"prompt blocked ({resp.prompt_feedback.block_reason})")
    finish = resp.candidates[0].finish_reason if resp.candidates else None
    if finish is not None and finish.name not in ("STOP", "FINISH_REASON_UNSPECIFIED"):
        raise ValueError(f"response ended early ({finish.name})")
    if not resp.text:
        raise ValueError("empty response")
    return Brief.model_validate_json(resp.text)


def _gemini_model(fallback: bool) -> str:
    return (settings.gemini_fallback_model or settings.gemini_model) if fallback else settings.gemini_model


def _call_claude(pack: dict, error: str | None, fallback: bool = False) -> Brief:
    """Claude with structured outputs (Opus 5.5: no temperature, no forced tool use)."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key,
                                 timeout=settings.llm_timeout_s, max_retries=0)
    try:
        resp = client.beta.messages.create(
            model=settings.anthropic_model,
            max_tokens=4000,
            system=SYSTEM,
            messages=[{"role": "user", "content": _prompt(pack, error)}],
            output_config={"effort": settings.anthropic_effort,
                           "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.RateLimitError as e:
        raise LLMUnavailable(f"Claude rate limited: {str(e)[:200]}", retryable=True) from e
    except anthropic.APIStatusError as e:
        raise LLMUnavailable(f"Claude {e.status_code}: {str(e)[:200]}",
                             retryable=e.status_code >= 500) from e
    except anthropic.APIConnectionError as e:  # includes timeouts
        raise LLMUnavailable(f"Claude connection: {str(e)[:200]}", retryable=True) from e
    if resp.stop_reason == "refusal":
        raise ValueError(f"model declined ({getattr(resp.stop_details, 'category', None)})")
    if resp.stop_reason == "max_tokens":
        raise ValueError("response truncated at max_tokens")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return Brief.model_validate_json(text)


def _json_object(text: str) -> str:
    """The outermost {...} in a reply (models sometimes wrap JSON in prose or code fences)."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the response")
    return text[start:end + 1]


def _call_bedrock(pack: dict, error: str | None, fallback: bool = False) -> Brief:
    """Claude on AWS Bedrock via the host's IAM role (no API key). BEDROCK_MODEL_ID picks the model."""
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError

    client = boto3.client("bedrock-runtime", region_name=settings.aws_region,
                          config=Config(read_timeout=settings.llm_timeout_s, retries={"max_attempts": 1}))
    prompt = (_prompt(pack, error) + "\n\nReply with ONLY a JSON object matching this JSON Schema, "
              "no prose or code fences:\n" + json.dumps(SCHEMA))
    try:
        resp = client.converse(modelId=settings.bedrock_model_id, system=[{"text": SYSTEM}],
                               messages=[{"role": "user", "content": [{"text": prompt}]}],
                               inferenceConfig={"maxTokens": 4000})
    except ClientError as e:
        code = e.response["Error"]["Code"]
        retryable = code in ("ThrottlingException", "ServiceUnavailableException", "ModelNotReadyException",
                             "InternalServerException", "ModelTimeoutException")
        raise LLMUnavailable(f"Bedrock {code}: {str(e)[:200]}", retryable=retryable) from e
    except BotoCoreError as e:  # timeouts, connection errors, missing credentials
        raise LLMUnavailable(f"Bedrock {type(e).__name__}: {str(e)[:200]}", retryable=True) from e
    if resp.get("stopReason") == "max_tokens":
        raise ValueError("response truncated at max_tokens")
    text = "".join(b.get("text", "") for b in resp["output"]["message"]["content"])
    return Brief.model_validate_json(_json_object(text))


PROVIDERS = {"gemini": _call_gemini, "anthropic": _call_claude, "bedrock": _call_bedrock}
SOURCE_NAME = {"gemini": "gemini", "anthropic": "claude", "bedrock": "claude"}


def generate_brief(pack: dict) -> dict:
    """Returns {"brief", "source": "gemini"|"claude"|"template", "label", "validation", "latency_s"}."""
    t0 = time.monotonic()
    error = None
    call = PROVIDERS.get(settings.llm_provider)
    if call is None:
        error = f"unknown LLM_PROVIDER {settings.llm_provider!r}; use gemini or anthropic"
    elif settings.llm_enabled:
        fallback = False
        for attempt in range(settings.llm_max_retries + 1):
            if attempt and time.monotonic() - t0 > settings.llm_timeout_s:
                break  # keep total latency near one timeout, not three
            try:
                brief, report = validate(call(pack, error, fallback), pack)
                report["attempts"] = attempt + 1
                model = _gemini_model(fallback) if settings.llm_provider == "gemini" else settings.llm_model
                return {"brief": brief.model_dump(), "source": SOURCE_NAME[settings.llm_provider],
                        "label": f"AI draft ({model}) - analyst decides",
                        "validation": report, "latency_s": round(time.monotonic() - t0, 2)}
            except (ValidationError, ValueError) as e:
                error = str(e)[:500]
                log.warning("brief attempt %d failed validation: %s", attempt + 1, error)
            except LLMUnavailable as e:
                error = str(e)
                log.warning("brief attempt %d API error: %s", attempt + 1, error)
                if not e.retryable:
                    break
                fallback = True  # model unavailable: try the fallback model next
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
