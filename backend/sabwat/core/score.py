"""Combine layer A (triage, alerted only) and layer B (network, any txn) into one score.

Usage:  python -m sabwat.core.score TXN00000001 [TXN...]
"""

import json
import sys
from functools import cache

import pandas as pd

from sabwat.config import settings
from sabwat.core.data import table
from sabwat.core.graph import watchlist_links
from sabwat.core.model import TriageModel, build_features
from sabwat.core.network import NetworkIndex, network_signals, ring_graph
from sabwat.core.normalize import InputError, Normalized, canonical_keys, normalize

LAYER_A, LAYER_B = "Triage model", "Network"


def band(score: float) -> str:
    return "High" if score >= 80 else "Med" if score >= 40 else "Low"


class Engine:
    """Everything needed at request time, loaded once from Data/ and artifacts/."""

    def __init__(self):
        art = settings.artifacts_dir
        self.model = TriageModel.load(art / "model.pkl")
        self.net = NetworkIndex.load(art)
        self.fx = json.loads((art / "fx.json").read_text())
        self.metrics = json.loads((art / "metrics.json").read_text())
        self.txns = table("transactions").set_index("txn_id")
        self.accounts = table("accounts").set_index("account_id")
        self.rules = table("alert_rules").set_index("rule_id")["rule_name"].to_dict()
        alerts = table("risk_alerts").sort_values("created_at")
        self.alerts = alerts.set_index("txn_id")
        self.alerted = set(self.alerts.index)
        self.alert_by_id = alerts.set_index("alert_id")
        self._t_perc = self.model.percentile(self.model.recall_threshold)

    # -- input --------------------------------------------------------------------------
    def resolve(self, record: dict) -> Normalized:
        """txn_id that exists in the data -> load it; otherwise normalize the supplied fields."""
        cmap = canonical_keys(record)[0]
        raw_id = cmap.get("alert_id") or cmap.get("txn_id")
        txn_id = str(raw_id).strip().upper() if raw_id and str(raw_id).strip() else None
        pinned = None
        if txn_id and txn_id in self.alert_by_id.index:  # an alert ID: score that alert's txn
            a = self.alert_by_id.loc[txn_id]
            pinned = {"alert_id": txn_id, "rule_id": a["rule_id"], "alert_score": float(a["score"])}
            txn_id = a["txn_id"]
        if txn_id and txn_id in self.txns.index:
            row = self.txns.loc[txn_id]
            txn = {"txn_id": txn_id, **{k: (None if pd.isna(v) else v)
                                        for k, v in row.to_dict().items()}}
            out = Normalized(txn=txn, alert=pinned)
            if pinned:
                out.warnings.append(f"Scored alert {pinned['alert_id']} on transaction {txn_id}")
            if len(record) > 1:
                out.warnings.append("Loaded transaction from data; other supplied fields ignored")
            return out
        if txn_id and set(cmap) <= {"txn_id", "alert_id"}:
            raise InputError("txn_id", f"{txn_id} is not a transaction or alert ID in the data. "
                                       "To score a new transaction, include an amount.")
        out = normalize(record, self.fx)
        if txn_id:
            out.warnings.append(f"{txn_id} not found in data; scored as a new transaction")
        return out

    def alert_contexts(self, n: Normalized) -> list[dict]:
        if n.alert and n.alert.get("alert_id"):
            return [n.alert]
        if n.alert and n.alert.get("rule_id") in self.rules and n.alert.get("alert_score") is not None:
            return [{"alert_id": None, **n.alert}]
        if n.alert:
            n.warnings.append("Alert context needs a known rule_id and alert_score (0-1); "
                              "triage model skipped")
        tid = n.txn.get("txn_id")
        if tid in self.alerted:
            g = self.alerts.loc[[tid]]
            return [{"alert_id": r.alert_id, "rule_id": r.rule_id, "alert_score": float(r.score)}
                    for r in g.itertuples()]
        return []

    # -- layer A ------------------------------------------------------------------------
    def _a_score(self, p: float) -> tuple[float, float]:
        """Map p to 0-100 so bands line up: below 90%-recall threshold -> Low, top decile -> High."""
        perc, t = self.model.percentile(p), self._t_perc
        if perc < t:
            s = 40 * perc / t
        elif perc < 0.9:
            s = 40 + 40 * (perc - t) / (0.9 - t)
        else:
            s = 80 + 20 * (perc - 0.9) / 0.1
        return round(min(s, 100), 1), perc

    def triage(self, txn: dict, alerts: list[dict]) -> dict:
        if not alerts:
            return {"applied": False,
                    "reason": "No alert context: the triage model only scores alerted transactions."}
        acct = self.accounts.loc[txn["account_id"]] if txn.get("account_id") in self.accounts.index else None
        best = None
        for a in alerts:
            row = {**txn, **a,
                   "account_type": None if acct is None else acct["account_type"],
                   "opened_at": None if acct is None else acct["opened_at"]}
            feats = build_features(pd.DataFrame([row]))
            p = float(self.model.predict(feats)[0])
            if best is None or p > best[0]:
                best = (p, a, feats)
        p, a, feats = best
        score, perc = self._a_score(p)
        return {
            "applied": True,
            "alert_id": a["alert_id"],
            "rule_id": a["rule_id"],
            "rule_name": self.rules.get(a["rule_id"]),
            "alert_score": a["alert_score"],
            "alerts_on_txn": len(alerts),
            "p_real": round(p, 4),
            "percentile": round(perc, 3),
            "score": score,
            "band": band(score),
            "reasons": self.model.shap_top(feats),
            "model_version": self.model.version,
        }

    # -- combined -----------------------------------------------------------------------
    def score(self, record: dict) -> dict:
        n = self.resolve(record)
        txn = n.txn
        trg = self.triage(txn, self.alert_contexts(n))
        net = network_signals(txn, self.net)
        if txn.get("account_id") is None or net["cold_start"]:
            n.warnings.append("No network history - lower confidence")

        scores = {LAYER_B: net["score"]}
        if trg["applied"]:
            scores[LAYER_A] = trg["score"]
        total = max(scores.values())
        fired = [k for k, v in scores.items() if v >= 40]
        driver = max(scores, key=scores.get)

        acct = txn.get("account_id")
        ent = self.net.entity_of.get(acct)
        return {
            "txn": {k: (str(v) if isinstance(v, pd.Timestamp) else v) for k, v in txn.items()},
            "score": round(total, 1),
            "band": band(total),
            "layers_fired": fired,
            "driver": driver,
            "triage": trg,
            "network": net,
            "ring_graph": (ring_graph(net["ring_id"], self.net,
                                      [acct, txn.get("counterparty_account_id")])
                           if net["ring_id"] else None),
            "ownership": watchlist_links(ent) if ent else None,
            "data_gaps": n.data_gaps,
            "warnings": n.warnings,
        }


    # -- record lookup (analyst clicks an evidence ID) ------------------------------------
    RECORD_TABLES = (("TXN", "transactions", "txn_id"), ("ACC", "accounts", "account_id"),
                     ("ALR", "risk_alerts", "alert_id"), ("IND", "individuals", "individual_id"),
                     ("DEV", "devices", "device_id"), ("ADR", "addresses", "address_id"),
                     ("IDA", "identity_attributes", "attribute_id"),
                     ("ENT", "business_entities", "entity_id"),
                     ("OWN", "ownership_links", "ownership_link_id"),
                     ("WL", "watchlists", "watchlist_entry_id"), ("R", "alert_rules", "rule_id"))

    def record(self, record_id: str) -> dict | None:
        rid = record_id.strip().upper()
        if rid in self.net.rings:
            r = self.net.rings[rid]
            return {"type": "ring", "id": rid,
                    "fields": {"individuals": len(r["individuals"]), "accounts": len(r["accounts"]),
                               "shared_attribute_links": len(r["links"])}}
        for prefix, name, col in self.RECORD_TABLES:
            if rid.startswith(prefix):
                t = table(name)
                rows = t[t[col] == rid]
                if rows.empty:
                    return None
                fields = {k: (None if pd.isna(v) else str(v) if isinstance(v, pd.Timestamp) else v)
                          for k, v in rows.iloc[0].to_dict().items()}
                if name == "risk_alerts":
                    fields["rule_name"] = self.rules.get(fields["rule_id"])
                if name == "accounts":
                    fields["ring_id"] = self.net.ring_of.get(rid)
                    fields["distinct_senders"] = self.net.fanin.get(rid, 0)
                return {"type": name, "id": rid, "fields": fields}
        return None


@cache
def get_engine() -> Engine:
    return Engine()


if __name__ == "__main__":
    eng = get_engine()
    for tid in sys.argv[1:]:
        r = eng.score({"txn_id": tid})
        print(f"{tid}: score {r['score']} {r['band']} fired={r['layers_fired']} driver={r['driver']}")
        if r["triage"]["applied"]:
            print("   A:", r["triage"]["p_real"], r["triage"]["rule_id"],
                  [(x["feature"], x["direction"]) for x in r["triage"]["reasons"]])
        print("   B:", [s["name"] for s in r["network"]["signals"]],
              "| ownership links:", len(r["ownership"]["links"]) if r["ownership"] else None)
