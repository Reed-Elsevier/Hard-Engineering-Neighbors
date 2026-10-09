"""Offline build (run once, ~1 min): network artifacts, FX table, triage model and metrics.

Usage:  python backend/scripts/build.py

Writes to artifacts/:
  network.json            ring(s) with member accounts and shared-attribute links (record IDs)
  graph_features.parquet  per account: ring_id, counterparty fan-in
  fx.json                 per-currency amount -> amount_usd rate (median of amount_usd / amount)
  model.pkl               layer A triage model (trained on alerts created before 2026)
  metrics.json            2026 hold-out metrics, noisy-rule report, time baseline
"""

import json
import time
from dataclasses import asdict

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from sabwat.config import settings
from sabwat.core import model as m
from sabwat.core.data import TRAIN_CUTOFF, labelled_alerts, table
from sabwat.core.graph import MULE_FANIN, counterparty_fanin, find_rings
from sabwat.core.network import NetworkIndex, index_from_parts, network_signals

NOISY_RULES = ("R017", "R023")


def build_network(art) -> NetworkIndex:
    rings = find_rings()
    fanin = counterparty_fanin()
    (art / "network.json").write_text(json.dumps(
        {"mule_fanin": MULE_FANIN, "rings": [asdict(r) for r in rings]}, indent=1, default=str))
    ring_of = {a: r.ring_id for r in rings for a in r.accounts}
    acc = table("accounts")[["account_id"]].copy()
    acc["ring_id"] = acc["account_id"].map(ring_of)
    acc["fanin"] = acc["account_id"].map(fanin).fillna(0).astype(int)
    acc.to_parquet(art / "graph_features.parquet", index=False)
    print(f"network: {len(rings)} ring(s) {[len(r.individuals) for r in rings]} individuals, "
          f"{int((acc['fanin'] >= MULE_FANIN).sum())} mule accounts")
    return NetworkIndex.load(art)


def build_fx(art) -> dict:
    t = table("transactions")
    fx = (t["amount_usd"] / t["amount"]).groupby(t["currency"]).median().round(6).to_dict()
    (art / "fx.json").write_text(json.dumps(fx, indent=1))
    print("fx:", fx)
    return fx


def noisy_rule_report(alerts: pd.DataFrame) -> list[dict]:
    rules = table("alert_rules").set_index("rule_id")
    g = alerts.groupby("rule_id").agg(alerts=("alert_id", "size"), real=("is_real", "sum"),
                                      fp_flag=("is_false_positive", "mean"))
    g["share_of_alerts"] = g["alerts"] / g["alerts"].sum()
    g["fp_rate"] = 1 - g["real"] / g["alerts"]
    g = g.join(rules[["rule_name", "rule_type"]]).sort_values(["fp_rate", "alerts"], ascending=False)
    return [{"rule_id": k, "rule_name": r.rule_name, "rule_type": r.rule_type,
             "alerts": int(r.alerts), "share_of_alerts": round(r.share_of_alerts, 4),
             "fp_rate": round(r.fp_rate, 4), "fp_rate_is_false_positive": round(r.fp_flag, 4)}
            for k, r in g.iterrows()]


def as_of(cutoff: pd.Timestamp, ring_accts: set, alerted: set, real_txns: set) -> dict:
    """Network built ONLY from data before `cutoff`, applied to the ring's later transfers."""
    net = index_from_parts(find_rings(cutoff), counterparty_fanin(cutoff), MULE_FANIN)
    t = table("transactions")
    later = t[t["account_id"].isin(ring_accts) & (t["txn_ts"] >= cutoff)]
    bands = later.apply(lambda r: network_signals(r.to_dict(), net)["band"], axis=1)
    return {
        "cutoff": str(cutoff.date()),
        "ring_individuals_known": sum(len(r["individuals"]) for r in net.rings.values()),
        "mule_accounts_known": sum(f >= MULE_FANIN for f in net.fanin.values()),
        "later_ring_transfers": len(later),
        "flagged_high": int((bands == "High").sum()),
        "flagged_med_or_high": int(bands.isin(["High", "Med"]).sum()),
        "rules_alerted": int(later["txn_id"].isin(alerted).sum()),
        "rules_confirmed_real": int(later["txn_id"].isin(real_txns).sum()),
    }


def main() -> None:
    t0 = time.time()
    art = settings.artifacts_dir
    art.mkdir(parents=True, exist_ok=True)
    net = build_network(art)
    build_fx(art)

    alerts = labelled_alerts()
    df = m.training_frame(alerts)
    train_df = df[df["created_at"] < TRAIN_CUTOFF]
    test_df = df[df["created_at"] >= TRAIN_CUTOFF]
    version = f"triage-{pd.Timestamp.now(tz='UTC'):%Y%m%d%H%M}"
    model = m.train(train_df, version)
    model.save(art / "model.pkl")

    y = test_df["is_real"].astype(int).to_numpy()
    p = model.predict(m.build_features(test_df))
    rule_p = test_df["alert_score"].to_numpy()
    rules = noisy_rule_report(alerts)
    noisy = [r for r in rules if r["rule_id"] in NOISY_RULES]

    # Layer B on every transaction (deterministic, nothing fitted, so 2026 is a fair test).
    txns = table("transactions")
    alerted = set(table("risk_alerts")["txn_id"])
    ring_accts = set(net.ring_of)
    sig = txns.apply(lambda r: network_signals(r.to_dict(), net)["band"], axis=1)
    ring_txn = txns["account_id"].isin(ring_accts)
    high = sig == "High"
    ring_alerts = alerts[alerts["account_id"].isin(ring_accts)]

    # Demo transactions for the UI (picked deterministically from the data).
    mules = {a for a, f in net.fanin.items() if f >= MULE_FANIN}
    demo = txns[ring_txn & ~txns["txn_id"].isin(alerted) & txns["counterparty_account_id"].isin(mules)
                & txns["amount_usd"].between(9000, 9999.99)].sort_values("txn_ts")
    test_df = test_df.assign(p=p)
    real = test_df[test_df["is_real"] & ~test_df["account_id"].isin(ring_accts)]
    noisy_fp = test_df[~test_df["is_real"] & test_df["rule_id"].isin(NOISY_RULES)]
    examples = [
        {"txn_id": demo["txn_id"].iloc[-1], "title": "Missed by rules",
         "note": "Never alerted. Ring member sends just under $10k to a mule account."},
        {"txn_id": real.sort_values("p")["txn_id"].iloc[-1], "title": "Real alert, ranked first",
         "note": "Alert later confirmed real; the triage model puts it at the top of the queue."},
        {"txn_id": noisy_fp.sort_values("p")["txn_id"].iloc[0], "title": "Noisy rule, safe to deprioritise",
         "note": f"{noisy_fp['rule_id'].iloc[0]} alert closed as a false positive."},
    ]

    acts = table("analyst_actions")
    metrics = {
        "model_version": version,
        "label": "real = alert Closed - True Positive, or investigation outcome SAR-like / Account exited",
        "split": {"train_alerts": len(train_df), "train_real": int(train_df["is_real"].sum()),
                  "test_alerts": len(test_df), "test_real": int(y.sum()),
                  "cutoff": str(TRAIN_CUTOFF.date())},
        "baseline": {
            "fp_rate_strict": round(1 - alerts["is_real"].mean(), 4),
            "fp_rate_is_false_positive": round(
                float(table("risk_alerts")["is_false_positive"].dropna().astype(bool).mean()), 4),
        },
        "triage_test": {
            "auc_model": round(roc_auc_score(y, p), 4),
            "auc_rule_score": round(roc_auc_score(y, rule_p), 4),
            "at_90_recall_model": m.review_at_recall(p, y, 0.9),
            "at_90_recall_rule_score": m.review_at_recall(rule_p, y, 0.9),
            "precision_at_100_model": round(m.precision_at(p, y), 4),
            "precision_at_100_rule_score": round(m.precision_at(rule_p, y), 4),
            "base_rate": round(float(y.mean()), 4),
        },
        "network": {
            "ring_transactions": int(ring_txn.sum()),
            "ring_transactions_never_alerted": int((ring_txn & ~txns["txn_id"].isin(alerted)).sum()),
            "high_flags": int(high.sum()),
            "high_flags_in_ring": int((high & ring_txn).sum()),
            "high_flags_never_alerted": int((high & ~txns["txn_id"].isin(alerted)).sum()),
            "ring_alerts": len(ring_alerts),
            "ring_alerts_confirmed_real": int(ring_alerts["is_real"].sum()),
        },
        "noisy_rules": {
            "rules": noisy,
            "combined_share_of_alerts": round(sum(r["share_of_alerts"] for r in noisy), 4),
            "combined_fp_rate": round(
                1 - alerts[alerts["rule_id"].isin(NOISY_RULES)]["is_real"].mean(), 4),
        },
        "rules": rules,
        "examples": examples,
        "as_of": [as_of(pd.Timestamp(d), ring_accts, alerted,
                        set(alerts.loc[alerts["is_real"], "txn_id"]))
                  for d in ("2026-02-01", "2026-03-01", "2026-04-01")],
        "time_baseline": {
            "investigation_median_hours": round(
                float(table("investigations")["time_to_decision_hours"].median()), 1),
            "review_alert_details_median_min": round(float(
                acts.loc[acts["action_type"] == "Review alert details", "duration_min"].median()), 1),
            "investigation_steps_median": float(table("investigations")["steps_count"].median()),
        },
    }
    (art / "metrics.json").write_text(json.dumps(metrics, indent=1, default=float))
    print(json.dumps({k: metrics[k] for k in ("split", "baseline", "triage_test", "network",
                                               "time_baseline")}, indent=1, default=float))
    print("noisy:", metrics["noisy_rules"]["combined_share_of_alerts"],
          metrics["noisy_rules"]["combined_fp_rate"])
    for a in metrics["as_of"]:
        print("as-of:", a)
    print("examples:", [e["txn_id"] for e in examples])
    print(f"build done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
