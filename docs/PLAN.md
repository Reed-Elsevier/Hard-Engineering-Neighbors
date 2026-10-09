# Sabwat — Work Plan

Companion to [PROJECT.md](../PROJECT.md). PROJECT.md holds the product intent; this file holds what we learned from the data and the order we build in.

## 1. What the data actually says (verified 2026-10-08)

Source: `Data/D_risk/*.parquet`, checked against `Data/_docs/03_data_dictionary.md`. Re-run with `python backend/scripts/inspect_data.py`.

| Fact | Value | Consequence |
|---|---|---|
| transactions | 200,000 rows, 2024-01 → 2026-09 (47k / 75k / 78k by year) | Time split: train 2024–2025, test 2026 works |
| PK of transactions | `txn_id` (not `transaction_id`) | Alias `transaction_id` → `txn_id` in normalize |
| Amount | `amount` (local ccy) and `amount_usd` | Model uses `amount_usd` |
| Fraud label | **No label on transactions.** Must derive from `risk_alerts` + `investigations` | See §2 |
| risk_alerts | 30,000 alerts on 27,831 txns; closed-alert FP rate **84.2%** (matches package baseline) | Baseline reproduced |
| Positive alerts | 1,407 Closed-TP + 2,132 Escalated (of which 358 SAR-like, 163 exited) | Small positive class — use class weights |
| Phones / emails / IDs | Hashed in `identity_attributes.attribute_value_hash` (no raw phone column) | Ring edges use hashes; nothing PII to send |
| Shared device fingerprints | **4** (sizes 7, 7, 4, 3 individuals) | Rings are few and planted — high-precision signal, low coverage |
| Shared identity hashes | **1** (a Phone hash across 6 individuals) | Same |
| Shared addresses (line+postcode) | **2** | Same |
| Device reuse across accounts | Common (device → 2–6 accounts) but always the same holder | Not a ring signal by itself |
| Accounts | 80% individual, 20% entity holders | Entity accounts → ownership BFS to watchlist |
| ownership_links | 23,871 edges, contains loops (A↔B) by design | BFS must track visited set |
| watchlists | 2,414 individual + 1,592 entity entries | Hop distance feature |
| Transaction-feature signal | Positive rate ~1.4–1.8% across every channel / merchant / cross-border value | Plain txn features are weak; network + alert features must carry the model |
| Noisiest rules | R023 Name similarity >0.6 (94.9% FP), R017 Round-amount cross-border (94.2% FP) | Rule-tuning report (nice-to-have) has a clear story |
| Model-based rules | ~66% FP vs ~85%+ rule-based | Worth showing in metrics |

**Risk to the pitch:** "shared-attribute rings" exist but are tiny (~27 individuals). The demo should (a) widen the ring graph with account→counterparty and account→holder→entity→owner edges so rings are visible beyond the planted seeds, and (b) be honest that the planted rings are high-precision, low-recall.

## 2. Modelling decisions

* **Unit scored:** a transaction. **Training set:** alerted transactions (the analyst queue), because only they have outcomes. Unalerted transactions are not presumed clean.
* **Label (`is_fraud`):** alert `Closed - True Positive`, or an investigation outcome of `SAR-like` / `Account exited`. Escalated → `No further action` / `Enhanced monitoring` = negative. `Open` = excluded.
* **Split:** train on alerts created ≤ 2025-12-31, test on 2026. Graph features built from training-period edges only.
* **Baseline to beat:** rule-engine queue (every alert = flagged). Report FP rate at equal recall and precision@100.

## 3. Architecture (changed from PROJECT.md)

The UI uses **React + shadcn/ui (preset `b2trkIJUvo`)**, not Streamlit. The backend is a **FastAPI** JSON API.

```
web/ (Vite + React + shadcn)  ──/api──▶  backend/sabwat/api.py (FastAPI)
                                           ├─ core/normalize.py   input → canonical txn
                                           ├─ core/graph.py       rings + ownership BFS
                                           ├─ core/features.py    lookup precomputed graph feats
                                           ├─ core/model.py       LightGBM + SHAP top-5
                                           ├─ core/evidence.py    evidence pack (IDs only)
                                           ├─ core/brief.py       Claude → validated JSON | template
                                           └─ core/db.py          SQLite decision log
backend/scripts/build.py   offline: graph feats + train + metrics → artifacts/
```

In production one process serves both: FastAPI serves `web/dist` at `/` and the API at `/api` on port 8000 (systemd unit in `deploy/`).

## 4. Build order (each step runnable alone)

| # | Step | Done when |
|---|---|---|
| 0 | Environment, repo, secrets, CI-free smoke test | ✅ `check_env.py` green, `/api/health` serves UI |
| 1 | `scripts/inspect_data.py` — shapes + baseline FP | ✅ prints 84.2% |
| 2 | `core/graph.py` — shared-attribute graph, connected components, ring IDs | prints top rings with member IDs |
| 3 | `core/graph.py` — ownership BFS to watchlist (≤4 hops, loop-safe) | prints paths for 3 entities |
| 4 | `scripts/build.py` — `artifacts/graph_features.parquet` | file written, < 2 min |
| 5 | `core/model.py` — label, time split, LightGBM, `metrics.json` vs baseline | metrics file exists |
| 6 | `core/model.py` — `score(txn) → score, band, shap_top5` | CLI on 3 txn IDs |
| 7 | `core/normalize.py` + `tests/sample_inputs/` (good, messy, unknown) | pytest green |
| 8 | `core/brief.py` — evidence pack → Claude → validated JSON, retries, fallback | works with key unset |
| 9 | API endpoints: `/api/score`, `/api/score/batch`, `/api/decision`, `/api/metrics` | pytest green |
| 10 | UI: input (ID / form / JSON / CSV) → score + SHAP → ring graph → brief → decision buttons | demo flow in < 60 s |
| 11 | EC2 deploy via `deploy/ec2_setup.sh`; phone smoke test; backup recording | public URL works |

## 5. Open items needing the team

* **AWS credentials:** keys go in `.env` (gitignored). Session tokens expire, so refresh before deploying. `check_env.py` verifies them via STS.
* **ANTHROPIC_API_KEY:** needed for step 8. Without it the template-brief fallback runs.
* **EC2 instance / security group:** not created yet. Open port 8000 to event IPs only.
