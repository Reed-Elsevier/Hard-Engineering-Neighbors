"""Evidence pack: computed facts only, each tied to record IDs. No names, addresses or phones.

The brief (LLM or template) may only cite IDs that appear here.
"""


def build_evidence(result: dict) -> dict:
    txn = result["txn"]
    tid = txn.get("txn_id") or "NEW-TXN"
    facts: list[dict] = []

    def add(kind: str, text: str, ids: list) -> None:
        ids = [i for i in dict.fromkeys(ids) if i]
        facts.append({"fact_id": f"F{len(facts) + 1}", "kind": kind, "text": text, "record_ids": ids})

    add("transaction",
        f"Transaction {tid}: USD {txn.get('amount_usd', 0):,.2f} via {txn.get('channel') or 'unknown channel'}"
        f", {'cross-border' if txn.get('is_cross_border') else 'domestic'}"
        f", sender account {txn.get('account_id') or 'unknown'}"
        f", counterparty {txn.get('counterparty_account_id') or 'none'}.",
        [tid, txn.get("account_id"), txn.get("counterparty_account_id"), txn.get("device_id")])
    add("score",
        f"Combined score {result['score']} ({result['band']}); layers fired: "
        f"{', '.join(result['layers_fired']) or 'none'}; highest layer: {result['driver']}.",
        [tid])

    trg = result["triage"]
    if trg["applied"]:
        add("alert",
            f"Rule alert {trg['alert_id'] or '(supplied)'} from {trg['rule_id']} "
            f"'{trg['rule_name']}' with rule score {trg['alert_score']:.2f}. Triage model puts the "
            f"chance this alert is real at {trg['p_real']:.1%} (higher than {trg['percentile']:.0%} "
            f"of past alerts).",
            [trg["alert_id"], trg["rule_id"], tid])
        for r in trg["reasons"]:
            add("triage_reason",
                f"Triage factor: {r['label']} = {r['value']} {r['direction']} the alert's likelihood "
                f"(SHAP {r['contribution']:+.3f}).",
                [trg["alert_id"] or tid, trg["rule_id"] if r["feature"] == "rule_id" else None])
    else:
        add("note", trg["reason"], [tid])

    for s in result["network"]["signals"]:
        add("network_signal", f"{s['label']}: {s['detail']}", s["evidence_ids"])
    if not result["network"]["signals"]:
        add("network_signal", "No network signals fired (no ring membership, no mule counterparty, "
            "amount not just under $10k).", [txn.get("account_id")])

    g = result.get("ring_graph")
    if g:
        inds = [n for n in g["nodes"] if n["type"] == "individual"]
        kinds = sorted({n["kind"] for n in g["nodes"] if n["type"] == "attribute"})
        mules = [a for n in inds for a in n["mule_accounts"]]
        add("ring",
            f"{g['ring_id']} links {len(inds)} individuals through shared {', '.join(kinds)} values; "
            f"{len(mules)} of its accounts receive from 10+ senders.",
            [g["ring_id"]] + [n["id"] for n in inds])

    own = result.get("ownership")
    if own:
        for w in own["own_entries"]:
            add("watchlist", f"Account entity {own['entity_id']} is itself listed: {w['list_type']} "
                f"({w['reason']}).", [own["entity_id"], w["watchlist_entry_id"]])
        for link in own["links"][:5]:
            add("ownership",
                f"Entity {own['entity_id']} {link['direction']} {link['other_entity_id']} "
                f"({link['link_type']}, {link['ownership_pct']:.1f}%), which is on a "
                f"{link['list_type']} list.",
                [own["entity_id"], link["ownership_link_id"], link["other_entity_id"],
                 link["watchlist_entry_id"]])

    for gap in result["data_gaps"]:
        add("data_gap", f"Data gap: {gap}.", [tid])
    for w in result["warnings"]:
        add("warning", w, [tid])

    return {
        "txn_id": tid,
        "score": result["score"],
        "band": result["band"],
        "layers_fired": result["layers_fired"],
        "facts": facts,
        "allowed_ids": sorted({i for f in facts for i in f["record_ids"]}),
    }
