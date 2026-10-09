"""Graphs: shared-attribute rings, counterparty fan-in, and 1-hop ownership links to watchlists.

Ownership edges never enter ring detection: one ownership component holds ~97% of entities, so
mixing them in would merge every ring into a giant component (docs/PLAN.md section 1).

Usage:  python -m sabwat.core.graph      # prints rings, mules and sample ownership links
"""

from dataclasses import dataclass, field

import networkx as nx
import pandas as pd

from sabwat.core.data import table

MULE_FANIN = 10  # counterparty receiving from >= this many distinct accounts (overall p99 is 3)


@dataclass
class Ring:
    ring_id: str
    individuals: list[str]
    accounts: list[str]
    # Shared attribute links: {"kind", "value_key", "individual_id", "record_id"}
    links: list[dict] = field(default_factory=list)


def _shared_links(cutoff: pd.Timestamp | None) -> pd.DataFrame:
    """One row per (individual, record) whose attribute value is shared with another individual."""
    dev = table("devices")
    ia = table("identity_attributes")
    adr = table("addresses")
    if cutoff is not None:
        dev = dev[dev["first_seen_at"] < cutoff]
        ia = ia[ia["verified_at"].isna() | (ia["verified_at"] < cutoff)]
        adr = adr[adr["valid_from"] < cutoff]
    frames = [
        pd.DataFrame({"kind": "Device fingerprint", "value_key": dev["device_fingerprint"],
                      "individual_id": dev["individual_id"], "record_id": dev["device_id"]}),
        pd.DataFrame({"kind": ia["attribute_type"], "value_key": ia["attribute_value_hash"],
                      "individual_id": ia["individual_id"], "record_id": ia["attribute_id"]}),
        pd.DataFrame({"kind": "Address", "value_key": adr["address_line"] + "|" + adr["postal_code"],
                      "individual_id": adr["individual_id"], "record_id": adr["address_id"]}),
    ]
    links = pd.concat(frames, ignore_index=True)
    n = links.groupby("value_key")["individual_id"].transform("nunique")
    return links[n > 1].reset_index(drop=True)


def find_rings(cutoff: pd.Timestamp | None = None) -> list[Ring]:
    """Connected components of individuals linked by shared device/identity/address values."""
    links = _shared_links(cutoff)
    g = nx.Graph()
    for _, grp in links.groupby("value_key"):
        inds = grp["individual_id"].unique()
        g.add_edges_from((inds[0], other) for other in inds[1:])
    acc = table("accounts")
    if cutoff is not None:
        acc = acc[acc["opened_at"] < cutoff]
    rings = []
    comps = sorted(nx.connected_components(g), key=lambda c: (-len(c), min(c)))
    for i, comp in enumerate(comps, start=1):
        members = sorted(comp)
        rings.append(Ring(
            ring_id=f"RING-{i:02d}",
            individuals=members,
            accounts=sorted(acc.loc[acc["individual_id"].isin(comp), "account_id"]),
            links=links[links["individual_id"].isin(comp)].to_dict("records"),
        ))
    return rings


def counterparty_fanin(cutoff: pd.Timestamp | None = None) -> pd.Series:
    """Distinct sending accounts per counterparty account."""
    t = table("transactions")
    if cutoff is not None:
        t = t[t["txn_ts"] < cutoff]
    t = t.dropna(subset=["counterparty_account_id"])
    return t.groupby("counterparty_account_id")["account_id"].nunique().rename("fanin")


def watchlist_links(entity_id: str) -> dict:
    """The entity's own watchlist entries plus 1-hop ownership links to watchlisted entities.

    Depth is capped at 1 on purpose: multi-hop paths reach almost every entity (ownership loops).
    """
    wl = table("watchlists")
    ol = table("ownership_links")
    listed = wl.dropna(subset=["entity_id"]).set_index("entity_id")
    own = [_wl_entry(r) for _, r in wl[wl["entity_id"] == entity_id].iterrows()]
    hops = []
    near = ol[(ol["parent_entity_id"] == entity_id) | (ol["child_entity_id"] == entity_id)]
    for _, link in near.iterrows():
        other = link["child_entity_id"] if link["parent_entity_id"] == entity_id else link["parent_entity_id"]
        if other not in listed.index:
            continue
        entries = listed.loc[[other]]
        for _, w in entries.iterrows():
            hops.append({
                "ownership_link_id": link["ownership_link_id"],
                "direction": "owned by" if link["child_entity_id"] == entity_id else "owns",
                "other_entity_id": other,
                "link_type": link["link_type"],
                "ownership_pct": float(link["ownership_pct"]),
                "watchlist_entry_id": w["watchlist_entry_id"],
                "list_type": w["list_type"],
                "is_nominee": link["link_type"] == "Nominee",
            })
    hops.sort(key=lambda h: (not h["is_nominee"], -h["ownership_pct"]))
    return {"entity_id": entity_id, "own_entries": own, "links": hops}


def _wl_entry(r: pd.Series) -> dict:
    return {"watchlist_entry_id": r["watchlist_entry_id"], "list_type": r["list_type"],
            "reason": r["reason"]}


if __name__ == "__main__":
    for cut in (None, pd.Timestamp("2026-01-01")):
        rings = find_rings(cut)
        print(f"cutoff={cut}: {len(rings)} ring(s)")
        for r in rings:
            kinds = pd.Series([x["kind"] for x in r.links]).value_counts().to_dict()
            print(f"  {r.ring_id}: {len(r.individuals)} individuals, {len(r.accounts)} accounts, "
                  f"links {kinds}")
        fan = counterparty_fanin(cut)
        mules = fan[fan >= MULE_FANIN]
        ring_accts = {a for r in rings for a in r.accounts}
        print(f"  mules (fan-in >= {MULE_FANIN}): {len(mules)}, held by ring: "
              f"{len(set(mules.index) & ring_accts)}")
    ents = table("accounts")["entity_id"].dropna().unique()[:200]
    shown = 0
    for e in ents:
        res = watchlist_links(e)
        if res["links"] and shown < 3:
            print(e, res["links"][:2])
            shown += 1
