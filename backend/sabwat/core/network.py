"""Layer B: deterministic network signals for ANY transaction, alerted or not.

Each signal carries the record IDs that justify it. Built from artifacts/network.json and
graph_features.parquet (scripts/build.py).
"""

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from sabwat.core.data import table

JUST_UNDER_LOW, JUST_UNDER_HIGH = 9000.0, 10000.0


@dataclass
class NetworkIndex:
    rings: dict[str, dict]  # ring_id -> {"individuals", "accounts", "links"}
    ring_of: dict[str, str]  # account_id -> ring_id
    holder_of: dict[str, str]  # account_id -> individual_id (individual holders only)
    entity_of: dict[str, str]  # account_id -> entity_id (entity holders only)
    fanin: dict[str, int]  # account_id -> distinct senders (only > 0 kept)
    mule_fanin: int
    known_accounts: set[str]

    @classmethod
    def load(cls, art: Path) -> "NetworkIndex":
        net = json.loads((art / "network.json").read_text())
        gf = pd.read_parquet(art / "graph_features.parquet")
        acc = table("accounts")
        return cls(
            rings={r["ring_id"]: r for r in net["rings"]},
            ring_of=gf.dropna(subset=["ring_id"]).set_index("account_id")["ring_id"].to_dict(),
            holder_of=acc.dropna(subset=["individual_id"]).set_index("account_id")["individual_id"].to_dict(),
            entity_of=acc.dropna(subset=["entity_id"]).set_index("account_id")["entity_id"].to_dict(),
            fanin=gf[gf["fanin"] > 0].set_index("account_id")["fanin"].to_dict(),
            mule_fanin=net["mule_fanin"],
            known_accounts=set(acc["account_id"]),
        )


def index_from_parts(rings: list, fanin: pd.Series, mule_fanin: int) -> NetworkIndex:
    """NetworkIndex from find_rings()/counterparty_fanin() output, e.g. as of a past date."""
    acc = table("accounts")
    return NetworkIndex(
        rings={r.ring_id: {"individuals": r.individuals, "accounts": r.accounts, "links": r.links}
               for r in rings},
        ring_of={a: r.ring_id for r in rings for a in r.accounts},
        holder_of=acc.dropna(subset=["individual_id"]).set_index("account_id")["individual_id"].to_dict(),
        entity_of=acc.dropna(subset=["entity_id"]).set_index("account_id")["entity_id"].to_dict(),
        fanin=fanin[fanin > 0].to_dict(),
        mule_fanin=mule_fanin,
        known_accounts=set(acc["account_id"]),
    )


def network_signals(txn: dict, net: NetworkIndex) -> dict:
    """Evaluate layer B for one canonical transaction dict."""
    acct = txn.get("account_id")
    cp = txn.get("counterparty_account_id")
    cp = cp if isinstance(cp, str) and cp else None
    amt = txn.get("amount_usd")
    signals = []

    ring_id = net.ring_of.get(acct)
    if ring_id:
        ind = net.holder_of.get(acct)
        links = [x for x in net.rings[ring_id]["links"] if x["individual_id"] == ind]
        signals.append({
            "name": "ring_member_sender",
            "label": "Sender is a ring member",
            "detail": f"{acct} is held by {ind}, one of {len(net.rings[ring_id]['individuals'])} "
                      f"individuals in {ring_id} who share devices, phones or addresses.",
            "evidence_ids": [acct, ind, ring_id] + [x["record_id"] for x in links],
        })

    if cp and net.fanin.get(cp, 0) >= net.mule_fanin:
        n = net.fanin[cp]
        cp_ring = net.ring_of.get(cp)
        signals.append({
            "name": "fanin_mule_counterparty",
            "label": "Counterparty looks like a mule (fan-in)",
            "detail": f"{cp} receives from {n} distinct accounts (typical is 1-3)"
                      + (f"; it is held by a member of {cp_ring}." if cp_ring else "."),
            "evidence_ids": [cp] + ([cp_ring, net.holder_of.get(cp)] if cp_ring else []),
        })

    if amt is not None and JUST_UNDER_LOW <= float(amt) < JUST_UNDER_HIGH:
        signals.append({
            "name": "just_under_10k",
            "label": "Amount just under $10k",
            "detail": f"USD {float(amt):,.2f} sits just below the 10,000 reporting threshold.",
            "evidence_ids": [txn["txn_id"]] if txn.get("txn_id") else [],
        })

    names = {s["name"] for s in signals}
    strong = names & {"ring_member_sender", "fanin_mule_counterparty"}
    if len(signals) >= 3:
        score = 98
    elif len(signals) == 2:
        score = 95
    elif strong:
        score = 90
    elif signals:
        score = 55
    else:
        score = 5
    cold_start = acct not in net.known_accounts
    return {
        "score": score,
        "band": "High" if score >= 80 else "Med" if score >= 40 else "Low",
        "signals": signals,
        "ring_id": ring_id or (net.ring_of.get(cp) if cp else None),
        "cold_start": cold_start,
    }


def ring_graph(ring_id: str, net: NetworkIndex, focus_accounts: list[str]) -> dict:
    """Nodes/edges for the UI: individuals linked through shared attribute values (no PII)."""
    ring = net.rings[ring_id]
    focus_inds = {net.holder_of.get(a) for a in focus_accounts if a}
    accounts_by_ind: dict[str, list[str]] = {}
    for a in ring["accounts"]:
        accounts_by_ind.setdefault(net.holder_of.get(a), []).append(a)
    nodes = [{"id": i, "type": "individual", "focus": i in focus_inds,
              "accounts": accounts_by_ind.get(i, []),
              "mule_accounts": [a for a in accounts_by_ind.get(i, [])
                                if net.fanin.get(a, 0) >= net.mule_fanin]}
             for i in ring["individuals"]]
    attrs: dict[str, dict] = {}
    edges = []
    for x in ring["links"]:
        key = f"{x['kind']}:{x['value_key']}"
        if key not in attrs:
            attrs[key] = {"id": f"A{len(attrs) + 1:02d}", "type": "attribute", "kind": x["kind"]}
        edges.append({"source": x["individual_id"], "target": attrs[key]["id"],
                      "record_id": x["record_id"]})
    return {"ring_id": ring_id, "nodes": nodes + list(attrs.values()), "edges": edges}
