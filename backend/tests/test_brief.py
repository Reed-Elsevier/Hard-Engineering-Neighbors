"""Provider-agnostic retry/fallback logic in generate_brief, with fake providers (no network)."""

import dataclasses

import pytest

from sabwat.core import brief as b

PACK = {"txn_id": "TXN1", "score": 95, "band": "High", "layers_fired": ["Network"],
        "allowed_ids": ["TXN1", "ACC1"],
        "facts": [{"fact_id": "F1", "kind": "network_signal", "text": "Sender is a ring member",
                   "record_ids": ["ACC1"]}]}


def make(ids):
    return b.Brief(risk_summary="s", recommended_action="escalate", confidence="high",
                   key_findings=[b.Finding(finding="f", evidence_ids=ids, severity="high")])


@pytest.fixture
def gemini_on(monkeypatch):
    monkeypatch.setattr(b, "settings", dataclasses.replace(
        b.settings, llm_provider="gemini", gemini_api_key="test-key", llm_max_retries=2))


def fake(monkeypatch, responses):
    calls, flags = [], []

    def call(pack, error, fallback=False):
        calls.append(error)
        flags.append(fallback)
        r = responses[len(calls) - 1]
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setitem(b.PROVIDERS, "gemini", call)
    call.flags = flags
    return calls


def test_retries_with_validation_error_then_succeeds(gemini_on, monkeypatch):
    calls = fake(monkeypatch, [make(["ACC404"]), make(["ACC1"])])
    out = b.generate_brief(PACK)
    assert out["source"] == "gemini" and out["validation"]["attempts"] == 2
    assert calls[0] is None and "no finding cited valid evidence IDs" in calls[1]


def test_fatal_api_error_falls_back_immediately(gemini_on, monkeypatch):
    calls = fake(monkeypatch, [b.LLMUnavailable("Gemini 400: API key not valid", retryable=False)])
    out = b.generate_brief(PACK)
    assert out["source"] == "template" and len(calls) == 1
    assert "API key not valid" in out["validation"]["error"]


def test_quota_error_is_retried(gemini_on, monkeypatch):
    calls = fake(monkeypatch, [b.LLMUnavailable("Gemini 503", retryable=True), make(["TXN1"])])
    out = b.generate_brief(PACK)
    assert out["source"] == "gemini" and len(calls) == 2
    assert b.PROVIDERS["gemini"].flags == [False, True]  # second attempt used the fallback model
    assert b.settings.gemini_fallback_model in out["label"]


def test_no_key_uses_template_without_calling(monkeypatch):
    monkeypatch.setattr(b, "settings", dataclasses.replace(b.settings, llm_provider="gemini",
                                                           gemini_api_key=None))
    calls = fake(monkeypatch, [make(["ACC1"])])
    assert b.generate_brief(PACK)["source"] == "template" and calls == []
