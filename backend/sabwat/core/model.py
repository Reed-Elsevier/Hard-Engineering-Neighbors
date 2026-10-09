"""Layer A: alert-triage model. "Is this alert real?" Alerted transactions only.

Features are alert + transaction + account attributes known at alert time. Ring/mule features are
deliberately absent: the ring appears only from Nov 2025, so with a time split they are all zero in
training (layer B covers them instead). Label-source fields are never features.
"""

import pickle
from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from sabwat.core.data import table

CATEGORICAL = ["rule_id", "channel", "merchant_category", "account_type"]
NUMERIC = ["alert_score", "amount_usd", "hour", "is_cross_border", "account_age_days",
           "just_under_10k", "has_counterparty", "has_device"]
FEATURES = CATEGORICAL + NUMERIC

LABELS = {
    "rule_id": "Alert rule",
    "alert_score": "Rule-engine alert score",
    "amount_usd": "Amount (USD)",
    "hour": "Hour of day",
    "is_cross_border": "Cross-border",
    "account_age_days": "Account age (days)",
    "just_under_10k": "Just under $10k",
    "has_counterparty": "Has counterparty account",
    "has_device": "Device recorded",
    "channel": "Channel",
    "merchant_category": "Merchant category",
    "account_type": "Account type",
}

PARAMS = {"n_estimators": 300, "learning_rate": 0.03, "num_leaves": 15, "min_child_samples": 40,
          "subsample": 0.8, "subsample_freq": 1, "colsample_bytree": 0.8, "reg_lambda": 1.0,
          "random_state": 7, "verbose": -1}
RECALL_TARGET = 0.90


def is_just_under_10k(amount_usd) -> bool:
    return 9000 <= float(amount_usd) < 10000


def build_features(rows: pd.DataFrame) -> pd.DataFrame:
    """rows needs: rule_id, alert_score, txn columns, account_type, opened_at."""
    ts = pd.to_datetime(rows["txn_ts"])
    out = pd.DataFrame(index=rows.index)
    out["rule_id"] = rows["rule_id"]
    out["channel"] = rows["channel"]
    out["merchant_category"] = rows["merchant_category"]
    out["account_type"] = rows["account_type"]
    out["alert_score"] = rows["alert_score"].astype(float)
    out["amount_usd"] = rows["amount_usd"].astype(float)
    out["hour"] = ts.dt.hour
    out["is_cross_border"] = rows["is_cross_border"].astype(float)
    out["account_age_days"] = (ts - pd.to_datetime(rows["opened_at"])).dt.days.astype(float)
    out["just_under_10k"] = rows["amount_usd"].astype(float).between(9000, 9999.999).astype(float)
    out["has_counterparty"] = rows["counterparty_account_id"].notna().astype(float)
    out["has_device"] = rows["device_id"].notna().astype(float)
    return out


def training_frame(alerts: pd.DataFrame) -> pd.DataFrame:
    """Labelled alerts joined with their transaction and account."""
    t = table("transactions")
    acc = table("accounts")[["account_id", "account_type", "opened_at"]]
    df = (alerts.rename(columns={"score": "alert_score"})
          .merge(t.drop(columns=["status"]), on=["txn_id", "account_id"], how="inner")
          .merge(acc, on="account_id", how="left"))
    return df


@dataclass
class TriageModel:
    model: lgb.LGBMClassifier
    categories: dict[str, list]
    oof_quantiles: np.ndarray  # 1001 quantiles of out-of-fold p on training alerts
    recall_threshold: float  # p at which OOF recall of real alerts is RECALL_TARGET
    version: str

    def _prep(self, feats: pd.DataFrame) -> pd.DataFrame:
        x = feats[FEATURES].copy()
        for c in CATEGORICAL:
            x[c] = pd.Categorical(x[c], categories=self.categories[c])
        return x

    def predict(self, feats: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(self._prep(feats))[:, 1]

    def percentile(self, p: float) -> float:
        """Share of training alerts (out-of-fold) scored below p, in [0, 1]."""
        return float(np.searchsorted(self.oof_quantiles, p, side="right") - 1) / 1000

    def shap_top(self, feats: pd.DataFrame, k: int = 5) -> list[dict]:
        """Top-k SHAP contributions for one row (log-odds units)."""
        x = self._prep(feats.iloc[[0]])
        contrib = self.model.predict(x, pred_contrib=True)[0][:-1]  # last column is bias
        order = np.argsort(-np.abs(contrib))[:k]
        out = []
        for i in order:
            name = FEATURES[i]
            val = feats.iloc[0][name]
            out.append({
                "feature": name,
                "label": LABELS[name],
                "value": None if pd.isna(val) else (val if isinstance(val, str) else float(val)),
                "contribution": round(float(contrib[i]), 4),
                "direction": "raises" if contrib[i] > 0 else "lowers",
            })
        return out

    def save(self, path) -> None:
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path) -> "TriageModel":
        with open(path, "rb") as f:
            return pickle.load(f)


def _categories(x: pd.DataFrame) -> dict[str, list]:
    return {c: sorted(x[c].dropna().unique().tolist()) for c in CATEGORICAL}


def _cast(x: pd.DataFrame, cats: dict) -> pd.DataFrame:
    x = x[FEATURES].copy()
    for c in CATEGORICAL:
        x[c] = pd.Categorical(x[c], categories=cats[c])
    return x


def train(train_df: pd.DataFrame, version: str) -> TriageModel:
    feats = build_features(train_df)
    y = train_df["is_real"].astype(int).to_numpy()
    cats = _categories(feats)
    x = _cast(feats, cats)

    # Out-of-fold predictions calibrate the displayed percentile and the 90%-recall threshold
    # without using any test data.
    oof = np.zeros(len(x))
    for tr, va in StratifiedKFold(5, shuffle=True, random_state=7).split(x, y):
        m = lgb.LGBMClassifier(**PARAMS).fit(x.iloc[tr], y[tr])
        oof[va] = m.predict_proba(x.iloc[va])[:, 1]

    model = lgb.LGBMClassifier(**PARAMS).fit(x, y)
    return TriageModel(
        model=model,
        categories=cats,
        oof_quantiles=np.quantile(oof, np.linspace(0, 1, 1001)),
        recall_threshold=threshold_at_recall(oof, y, RECALL_TARGET),
        version=version,
    )


def threshold_at_recall(p: np.ndarray, y: np.ndarray, target: float) -> float:
    """Highest threshold t such that flagging p >= t keeps at least `target` of positives."""
    pos = np.sort(p[y == 1])[::-1]
    k = int(np.ceil(target * len(pos)))
    return float(pos[k - 1])


def review_at_recall(p: np.ndarray, y: np.ndarray, target: float) -> dict:
    """Review alerts in descending p until `target` recall; count what was skipped."""
    order = np.argsort(-p, kind="stable")
    ys = y[order]
    need = int(np.ceil(target * ys.sum()))
    k = int(np.searchsorted(np.cumsum(ys), need) + 1)
    total_fp = int((y == 0).sum())
    fp_reviewed = int(k - ys[:k].sum())
    return {
        "alerts_reviewed": k,
        "alerts_total": len(y),
        "fp_avoided": total_fp - fp_reviewed,
        "fp_avoided_pct": round((total_fp - fp_reviewed) / total_fp, 4),
        "workload_cut_pct": round(1 - k / len(y), 4),
    }


def precision_at(p: np.ndarray, y: np.ndarray, k: int = 100) -> float:
    return float(y[np.argsort(-p, kind="stable")[:k]].mean())
