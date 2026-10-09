"""Build step 1: load the D_risk tables, print shapes/columns, and compute the rule-engine baseline.

Usage:  python backend/scripts/inspect_data.py
"""

import pandas as pd

from sabwat.config import settings

TABLES = [
    "transactions", "accounts", "individuals", "devices", "addresses", "identity_attributes",
    "business_entities", "ownership_links", "watchlists", "alert_rules", "risk_alerts",
    "investigations", "analyst_actions", "kyc_cases",
]
POSITIVE = {"Closed - True Positive", "Escalated to investigation"}


def main() -> None:
    dfs = {t: pd.read_parquet(settings.risk_dir / f"{t}.parquet") for t in TABLES}
    for name, df in dfs.items():
        print(f"{name:22s} {df.shape[0]:>8,} rows  {', '.join(df.columns)}")

    alerts = dfs["risk_alerts"]
    closed = alerts["is_false_positive"].dropna().astype(bool)
    print(f"\nBaseline alert FP rate (closed alerts): {closed.mean():.1%}  (package says 84.2%)")
    print(f"Positive alerts (TP or escalated): {alerts['disposition'].isin(POSITIVE).sum():,}")

    txn = dfs["transactions"]
    print("Transactions by year:", txn["txn_ts"].dt.year.value_counts().sort_index().to_dict())

    rules = alerts.groupby("rule_id")["is_false_positive"].agg(["mean", "size"])
    rules = rules.join(dfs["alert_rules"].set_index("rule_id")[["rule_name", "rule_type"]])
    print("\nNoisiest rules:\n", rules.sort_values("mean", ascending=False).head(5).round(3))

    # Shared-attribute signal (the ring seed): same value across >1 individual.
    dev = dfs["devices"].groupby("device_fingerprint")["individual_id"].nunique()
    attr = dfs["identity_attributes"].groupby("attribute_value_hash")["individual_id"].nunique()
    addr = dfs["addresses"].groupby(["address_line", "postal_code"])["individual_id"].nunique()
    print(f"\nShared fingerprints: {(dev > 1).sum()}  shared attribute hashes: {(attr > 1).sum()}"
          f"  shared addresses: {(addr > 1).sum()}")


if __name__ == "__main__":
    main()
