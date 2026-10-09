"""Cached Parquet loaders for the D_risk tables."""

from functools import cache

import pandas as pd

from sabwat.config import settings

# Investigation outcomes that count as real fraud (strict label, PROJECT.md section 5).
REAL_OUTCOMES = {"Suspicious activity report filed (SAR-like)", "Account exited"}
TRAIN_CUTOFF = pd.Timestamp("2026-01-01")  # train < cutoff <= test


@cache
def table(name: str) -> pd.DataFrame:
    return pd.read_parquet(settings.risk_dir / f"{name}.parquet")


def labelled_alerts() -> pd.DataFrame:
    """risk_alerts joined to investigation outcome, with the strict label `is_real`.

    Open alerts and open investigations are dropped. disposition / outcome / is_false_positive are
    label sources only and must never be used as features.
    """
    alerts = table("risk_alerts")
    inv = table("investigations")[["alert_id", "outcome"]]
    a = alerts.merge(inv, on="alert_id", how="left")
    a = a[(a["disposition"] != "Open") & (a["outcome"] != "Open")].copy()
    a["is_real"] = (a["disposition"] == "Closed - True Positive") | a["outcome"].isin(REAL_OUTCOMES)
    return a
