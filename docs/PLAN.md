# Sabwat: Work Plan

This file holds verified data facts, design decisions and build order. [PROJECT.md](../PROJECT.md) holds product intent, and its body now reflects these decisions.
Every number here was reproduced against `Data/D_risk` on 2026-10-08 (scripts in §7).

---

## 1. Design: two scoring layers, one displayed score

| Layer | Applies to | Question it answers | Output |
|---|---|---|---|
| **A. Alert triage** (LightGBM + SHAP) | Alerted transactions only | "Is this alert real?" Cuts the 94% FP noise. | `p_real`, top-5 SHAP reasons |
| **B. Network** (deterministic rules over precomputed graph) | **Any** transaction | "Is this part of a ring the rules missed?" | Fired signals, each with record IDs |

* **Displayed score** = `max(A, B)` mapped to 0–100 and a Low/Med/High band. The UI always shows **which layer fired** ("Triage model", "Network", or both).
* A non-alerted transaction is never sent through layer A, because it sits outside A's training population. It gets layer B plus a "No alert context" note.
* **Demo transaction:** a ring transaction that was **never alerted** (74.5% of ring transactions qualify). Rules missed it; layer B flags it High.
* Pitch: *one layer cuts noise, the other finds what rules miss.*

### Layer B signals (verified)

| Signal | Definition | Evidence |
|---|---|---|
| `ring_member_sender` | Sender's holder is in a shared-attribute component (shared device fingerprint, identity hash, or address+postcode) | 1 ring: 15 individuals, 49 accounts, 471 txns |
| `fanin_mule_counterparty` | Counterparty receives from ≥10 distinct accounts | 23 such accounts (overall p99 fan-in is 3); **all 23 held by ring members**; 95% of transactions into them come from ring accounts |
| `just_under_10k` | `9000 ≤ amount_usd < 10000` | 85% of ring transactions vs 0.5% of all; only 40% of such transactions are ring, so this is weak alone and strong combined |
| `ring_flag` | Binary flag. There is only one ring, so a "ring fraud ratio" would be constant | — |

Scoring rule for B: `ring_member_sender` or `fanin_mule_counterparty` → High. `just_under_10k` alone → Med. Two or more signals → High.

### Ownership: a separate evidence panel, never part of ring detection

* Ownership edges are **not** added to the ring graph. Undirected, one component holds 9,693 of 10,000 entities. It contains a 3,500-entity circular-ownership cluster (strongly connected). 97% of entities are within 4 undirected hops of a watchlisted entity (87% via directed ancestry).
* Hop distance shows **no signal**: the strict-positive rate is 6.4–6.9% at hops 0–2, versus 4.2% when no watchlisted entity is reachable. It is **not a feature.**
* The panel shows **1-hop links only** between the account's entity and a watchlisted entity, with `link_type` and `ownership_pct`, and highlights **Nominee** links. There are 6,078 1-hop links to watchlisted entities, so plain 1-hop is common; Nominee is the selective cut (286 links). The search stops at depth 1 and the code is loop-safe.

## 2. Labels, features, leakage

* **One label definition used everywhere (strict):** real = alert `Closed - True Positive`, or an investigation outcome of `SAR-like` or `Account exited`. Rows that are `Open` are excluded.
  * Under this label the **rule-engine baseline FP rate is 93.6%**. The package's 84.2% uses `is_false_positive`, where Monitoring and Escalated-then-no-action count as "not FP". The deck quotes 93.6% and footnotes 84.2% as the published figure under a looser definition.
* **Label-only fields (never features):** `risk_alerts.disposition`, `is_false_positive`, `closed_at`, `analyst_employee_id`; everything in `investigations`, `analyst_actions`, `kyc_cases.outcome`.
* **Layer A features:** `rule_id`, alert `score`, `amount_usd`, hour, `is_cross_border`, channel, merchant category, account type, account age, `just_under_10k`, has-counterparty, has-device. **Ring/mule flags were dropped from layer A:** rebuilt from pre-2026 edges only, the ring has 1 account and there are 0 mules (the ring forms Nov 2025 to Apr 2026), so they would be all zero in training. Layer B carries them.
* **Split:** train on alerts created ≤ 2025-12-31, test on 2026.
* **Measured (2026 hold-out, `scripts/build.py`):** AUC **0.65** vs 0.52 for the rule-engine score. At 90% recall: **2,844 FPs avoided (26%)** vs 1,280 (12%) ranking by rule score. Precision@100: 0.10 vs 0.13 (the model loses this one; report as-is).
* **Layer B:** 488 High flags, 471 of them ring txns, 364 never alerted. **As-of 2026-03-01** (network rebuilt from earlier data only): 315 of the ring's 420 later transfers flagged High; rules alerted on 113, 26 confirmed real.
* Noisy rules under the strict label: R017 + R023 = 30.8% of alerts at **97.7%** FP.

## 3. Input normalization

* **IDs: trim and UPPERCASE.** All IDs are uppercase (`ACC0000001`, `TXN00000012`), so lowercasing would break every lookup.
* Aliases: `transaction_id` → `txn_id`, `amt` and `amount_*` → `amount` + `currency`.
* **Currency → `amount_usd`** using the median `amount_usd / amount` per currency from transactions. Rates are stable: EUR ≈1.079, GBP ≈1.271, JPY ≈0.00666, PHP ≈0.01788, USD 1.
* Unknown account or device: layer B returns "No network history, lower confidence", and layer A is skipped unless alert context is supplied.

## 4. Metrics (2026 hold-out)

| Metric | Definition |
|---|---|
| **FP avoided at 90% recall** | Rank 2026 alerts by layer A. At the cutoff that keeps 90% of real cases, count the FPs not reviewed, versus reviewing every alert. (Equal-recall FP rate against the rule engine can't be measured; there are no labels outside alerts.) |
| Precision@100 | Layer A top-100 versus the rule-engine queue order |
| Missed-by-rules recall | Share of ring transactions that layer B flags and were never alerted (target ≈ 74.5% of 471) |
| **Noisy-rule report** | R017 + R023 produce **30.8% of alerts at 94.5% FP**. Must-have results slide. |
| Brief grounding | 100% of findings carry valid evidence IDs after validation |
| Latency p95 | ≤ 15 s for score + brief |
| Time-to-decision | Baseline: `investigations.time_to_decision_hours` median **60.5 h**. `05_hackathon_package.md` *is* in the upload but has no risk handling-time figure. Caveat: 60.5 h is investigation time, not L1 triage. Also derive triage minutes from `analyst_actions` ("Review alert details" durations) and compare like with like. |

## 5. Database: AWS DynamoDB with the same AWS credentials

**Choice: DynamoDB (on-demand), not RDS.** The decision log is append-only key-value data. DynamoDB needs no VPC, security group or DB password. It authenticates with the same IAM credentials via `boto3`, which is already installed. It is ready in seconds and costs nothing at demo volume. RDS Postgres would take ~10 minutes to provision, plus subnet, security-group and password management, for no gain here.

Verified 2026-10-08: the team's SSO credentials can create DynamoDB tables in the event's AWS account (region `ap-southeast-1`); no tables existed before. **The account is shared** (other teams' instances and buckets), so:

* Every resource is named `sabwat-*` and tagged `Project=sabwat`. We never modify anything else.
* Tables (created by `backend/scripts/provision_aws.py`, idempotent):
  * `sabwat-decisions`: PK `txn_id`, SK `decided_at` (ISO). Attributes: `decision` (escalate/review/dismiss), `note`, `score`, `band`, `layers_fired`, `brief_source` (claude/template), `model_version`.
  * `sabwat-briefs`: PK `txn_id`, the cached brief JSON with TTL on `expires_at` (24 h). This keeps demo latency low.
* `sabwat/core/db.py` exposes `get_store()` returning one interface with two backends: DynamoDB (when `DB_BACKEND=dynamodb`) and SQLite. AWS errors (expired token, throttling, no network) log a warning and write to SQLite, so the app never crashes. Reads merge both.
* **Credentials:**
  * Local: SSO session keys in `.env`. These expire (typically within hours); refresh them from the SSO portal and re-run `check_env.py`.
  * **EC2: do not paste admin session keys on the instance.** They expire mid-demo and are over-privileged. Launch it with instance profile `sabwat-ec2-profile` (role `sabwat-ec2-role`), whose inline policy allows only `PutItem/GetItem/Query/UpdateItem/DescribeTable` on `table/sabwat-*`. Leave `AWS_*` blank in the instance's `.env`; config drops blank values so boto3 uses the role.
* `.env` vars: `DB_BACKEND=dynamodb|sqlite`, `DDB_TABLE_DECISIONS=sabwat-decisions`, `DDB_TABLE_BRIEFS=sabwat-briefs`.
* Data (`Data/`) is **not** uploaded to S3 or DynamoDB. It is copied to the instance from the event environment.

## 6. Work items (in order; each is runnable alone)

Prep (allowed before the event: environment only, no Sabwat screens):

| # | Task | Status |
|---|---|---|
| W0 | Rewrite the **body** of PROJECT.md with these decisions and delete the override header | ✅ No Streamlit / 8501 / `inspect.py` / lowercase-ID instructions left; hop distance appears only as a non-feature |
| W1 | `provision_aws.py`: create `sabwat-decisions` + `sabwat-briefs`, tags, IAM role + instance profile | ✅ Both tables ACTIVE (verified via `check_env.py`) |
| W2 | `core/db.py` with DynamoDB + SQLite backends and fallback | ✅ pytest green (SQLite, fake DynamoDB table, fallback on ExpiredToken) |

Build (onsite):

| # | Task | Done when |
|---|---|---|
| B1 ✅ | `core/graph.py`: shared-attribute components (ring), fan-in table, 1-hop/Nominee ownership lookup | Prints ring of 15 / 49 accounts / 23 mules |
| B2 ✅ | `scripts/build.py`: `artifacts/graph_features.parquet` (training-period edges), FX table, label table | < 2 min |
| B3 ✅ | `core/model.py`: layer A train + `metrics.json` (FP avoided @90% recall, P@100, noisy rules) | Metrics file written |
| B4 ✅ | `core/network.py`: layer B signals with record IDs | Demo txn (never alerted, ring) → High via B |
| B5 ✅ | `core/score.py`: combine A/B, band, `layers_fired` | CLI on 3 IDs: alerted-real, alerted-FP, unalerted-ring |
| B6 ✅ | `core/normalize.py` + `tests/sample_inputs/` (good, messy, unknown, PHP amount) | pytest green |
| B7 ✅ (Gemini verified live: 3–6 s, 0 dropped findings; DynamoDB brief cache verified) | `core/evidence.py` + `core/brief.py`: Claude (validated JSON, 20 s timeout, 2 retries) with template fallback; cache in `sabwat-briefs` | Works with the key unset |
| B8 ✅ | API (+ `/api/record/{id}`, `/api/examples`, alert-ID lookup): `/api/score`, `/api/score/batch`, `/api/decision`, `/api/metrics`, `/api/rules/noisy` | pytest green |
| B9 ✅ | **One-page UI** (+ `?id=` deep link, results panel, light/dark): input (ID / form / JSON / CSV) → score + "layer fired" → SHAP / signals → ring graph → ownership panel → brief → Escalate/Review/Dismiss | Decision in < 60 s on the demo transaction |
| B10 | Deploy to EC2 with `sabwat-ec2-profile`; security group opens 8000 to event IPs; phone smoke test; backup recording | Public URL works; decision appears in `sabwat-decisions` |

## 7. How these numbers were checked

`backend/scripts/inspect_data.py` reproduces the baseline and rule noise. The ring, fan-in, ownership, label and FX checks were one-off scripts and will become `scripts/build.py` (B2) and its printed summary. Re-verify after any data refresh.
