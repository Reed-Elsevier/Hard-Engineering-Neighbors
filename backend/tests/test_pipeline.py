"""End-to-end against the real data and built artifacts (skipped when they are absent)."""

import json

import pytest
from conftest import SAMPLES, needs_artifacts
from fastapi.testclient import TestClient

from sabwat.core.brief import Brief, Finding, template_brief, validate
from sabwat.core.evidence import build_evidence

pytestmark = needs_artifacts


@pytest.fixture(scope="module")
def client():
    from sabwat.api import app

    return TestClient(app)


@pytest.fixture(scope="module")
def examples(client):
    ex = client.get("/api/examples").json()["examples"]
    return {e["title"]: e.get("txn_id") or e["transaction"] for e in ex}


def score(client, **body):
    r = client.post("/api/score", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_unalerted_ring_txn_is_high_via_network(client, examples):
    r = score(client, txn_id=examples["Missed by rules"])
    assert r["band"] == "High"
    assert r["layers_fired"] == ["Network"]
    assert not r["triage"]["applied"]
    names = {s["name"] for s in r["network"]["signals"]}
    assert names == {"ring_member_sender", "fanin_mule_counterparty", "just_under_10k"}
    assert r["ring_graph"]["ring_id"] == "RING-01"


def test_real_alert_is_high_via_triage(client, examples):
    r = score(client, txn_id=examples["Real alert, ranked first"])
    assert r["triage"]["applied"] and r["band"] == "High"
    assert "Triage model" in r["layers_fired"]
    assert len(r["triage"]["reasons"]) == 5


def test_noisy_fp_alert_is_low(client, examples):
    r = score(client, txn_id=examples["Noisy rule, safe to deprioritise"].lower())  # case-insensitive
    assert r["band"] == "Low"
    assert r["triage"]["rule_id"] in {"R017", "R023"}


def test_unknown_account_is_cold_start(client):
    r = score(client, transaction=json.loads((SAMPLES / "unknown_account.json").read_text()))
    assert r["network"]["cold_start"]
    assert any("No network history" in w for w in r["warnings"])


def test_invalid_input_is_422_naming_field(client):
    r = client.post("/api/score", json={"transaction": {"account_id": "ACC0021473", "amount": "abc"}})
    assert r.status_code == 422
    assert r.json()["field"] == "amount"
    assert client.post("/api/score", json={}).status_code == 422


def test_batch_csv_ranks_and_reports_errors(client):
    csv = (SAMPLES / "messy.csv").read_text(encoding="utf-8")
    body = client.post("/api/score/batch", json={"csv": csv}).json()
    assert body["scored"] == 4 and body["errors"] == 1  # NEW-0004 has no amount
    assert body["rows"][0]["band"] == "High"
    assert body["rows"][-1]["error"].startswith("amount")


def test_brief_falls_back_to_template_without_key(client, examples):
    b = client.post("/api/brief", json={"txn_id": examples["Missed by rules"]}).json()
    assert b["source"] == "template"
    assert b["label"] == "AI unavailable - template brief"
    assert b["brief"]["recommended_action"] == "escalate"


def test_template_brief_only_cites_pack_ids(client, examples):
    from sabwat.core.score import get_engine

    for tid in [v for v in examples.values() if isinstance(v, str)]:
        pack = build_evidence(get_engine().score({"txn_id": tid}))
        brief = template_brief(pack)
        validated, report = validate(brief, pack)
        assert report["findings_dropped"] == 0
        assert all(set(f.evidence_ids) <= set(pack["allowed_ids"]) for f in validated.key_findings)


def test_validator_drops_uncited_and_blocks_high_dismiss():
    pack = {"band": "High", "allowed_ids": ["TXN1", "ACC1"]}
    brief = Brief(risk_summary="x", recommended_action="dismiss", confidence="low",
                  key_findings=[Finding(finding="ok", evidence_ids=["TXN1"], severity="high"),
                                Finding(finding="made up", evidence_ids=["ACC404"], severity="high")])
    out, report = validate(brief, pack)
    assert report["findings_dropped"] == 1
    assert out.recommended_action == "review"


def test_decision_roundtrip(client):
    r = client.post("/api/decision", json={"txn_id": "txn00000241", "decision": "escalate",
                                           "note": "ring", "score": 98, "band": "High",
                                           "layers_fired": ["Network"], "brief_source": "template"})
    assert r.status_code == 200 and r.json()["stored_in"] == "sqlite"
    hist = client.get("/api/decisions/TXN00000241").json()["decisions"]
    assert hist[-1]["decision"] == "escalate"
    assert client.post("/api/decision", json={"txn_id": "X", "decision": "approve"}).status_code == 422


def test_metrics_exposes_noisy_rules(client):
    m = client.get("/api/metrics").json()
    assert m["noisy_rules"]["combined_share_of_alerts"] > 0.3
    assert m["triage_test"]["at_90_recall_model"]["fp_avoided"] > 0


def test_new_sender_paying_collection_account_is_flagged(client, examples):
    """Pitch demo part 2: a made-up sender, any amount, to a known collection account."""
    mule = score(client, txn_id=examples["Missed by rules"])["txn"]["counterparty_account_id"]
    r = score(client, transaction={"account": "ACC7777777", "to account": mule, "amount": "5,000",
                                   "currency": "php", "channel": "Mobile wallet"})
    assert r["band"] == "High"
    assert [s["name"] for s in r["network"]["signals"]] == ["fanin_mule_counterparty"]
    assert r["network"]["cold_start"]


def test_alert_id_scores_that_alert(client):
    from sabwat.core.data import table

    a = table("risk_alerts").iloc[0]
    r = score(client, txn_id=a["alert_id"].lower())
    assert r["txn"]["txn_id"] == a["txn_id"]
    assert r["triage"]["alert_id"] == a["alert_id"]


def test_unknown_id_says_not_found(client):
    r = client.post("/api/score", json={"txn_id": "TXN99999999"})
    assert r.status_code == 422 and "not a transaction or alert ID" in r.json()["error"]


def test_record_lookup_for_evidence_ids(client, examples):
    r = score(client, txn_id=examples["Missed by rules"])
    for rid in r["evidence"]["allowed_ids"]:
        if rid != "NEW-TXN":
            assert client.get(f"/api/record/{rid}").status_code == 200, rid
    assert client.get("/api/record/NOPE123").status_code == 404


def test_as_of_metric_present(client):
    as_of = {a["cutoff"]: a for a in client.get("/api/metrics").json()["as_of"]}
    m = as_of["2026-03-01"]
    assert m["flagged_high"] > m["rules_alerted"]
