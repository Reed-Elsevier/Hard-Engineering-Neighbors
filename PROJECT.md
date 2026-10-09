# **PROJECT.md: Sabwat — Fraud Ring Intelligence (Track 4: Fraud & Identity Intelligence)**

> Persistent context for the coding assistant. Table and column names below were verified against `Data/_docs/03_data_dictionary.md` and the Parquet files on 2026-10-08. Numbers, evidence and the work-item list are in [docs/PLAN.md](docs/PLAN.md). If the data changes, re-verify and update both files.

## **1\. Pitch**

* **Solution:** Sabwat scores any transaction in the context of the identity network around it. It explains the score, then drafts an evidence-cited brief so a human analyst can decide in under a minute.

* **Two layers, one score:** an **alert-triage model** cuts the noise in the rule-engine queue ("is this alert real?"), and a **network layer** finds ring activity the rules never alerted on. The UI always says which layer fired.

* **Why AI is essential:** Fraud rings are relational patterns that per-transaction rules cannot see. An ML model learns which alert, behaviour and network signals separate real alerts from noise. An LLM condenses dozens of linked records into a readable, cited brief in seconds.

* **Name:** *Sabwat*, from Filipino *sabwatan* ("collusion"). Use it in UI titles, README and pitch.

* **Pitch line:** "Rule engines catch individuals. Sabwat catches the *sabwatan*." One layer cuts noise; the other finds what rules miss.

## **2\. User and demo story**

* **User:** A Sentinel Risk L1 fraud/AML analyst who works a noisy rule-engine alert queue.

* **Trigger:** A new transaction arrives, or a rule alert fires on one.

* **Input:** A `txn_id` from the data, or a new transaction entered by form, JSON or CSV. The judges' unseen input arrives this way.

* **Demo transaction:** a ring transaction the rule engine **never alerted on** (74.5% of the ring's 471 transactions qualify). Sabwat's network layer flags it High.

* **Outcome:** The app returns:

  * a risk score from 0 to 100 with a band (Low/Med/High) and the **layer that fired** (Triage model, Network, or both);  
  * for alerted transactions, the top 5 SHAP reasons from the triage model;  
  * the network signals that fired, each with record IDs (ring-member sender, fan-in mule counterparty, just-under-$10k amount);  
  * a ring graph of identities sharing device fingerprints, identity hashes or addresses with the account;  
  * an ownership panel listing **direct (1-hop) links** from the account's entity to watchlisted entities, highlighting Nominee links;  
  * a Claude brief citing record IDs.  
* The analyst clicks **Escalate / Review / Dismiss** with a note, and the decision is logged. Target: decision-ready in 60 seconds or less.

## **3\. Scope**

| MUST-HAVE (demo-critical, \~3.5 h) | NICE-TO-HAVE | OUT OF SCOPE |
| ----- | ----- | ----- |
| Load Parquet; precompute graph features | Batch CSV scoring \+ ranked queue | Real-time streaming |
| Shared-attribute ring (connected components on device / identity-hash / address edges only) | Interactive graph library | Auth/RBAC, multi-user |
| Network layer: ring-member sender, fan-in mule counterparty, just-under-$10k | Analyst feedback → retrain | Case-management integration |
| Triage model: LightGBM on alerted transactions \+ SHAP top-5 | Raw-table cleaning demo (`raw/`) | Model monitoring/drift |
| **Noisy-rule report:** R017 \+ R023 produce 30.8% of alerts at 94.5% FP | Supplier-risk cross-link (Area G) | Individual analyst ranking (banned) |
| Ownership panel: 1-hop / Nominee links to watchlist (no multi-hop BFS) |  | Fine-tuning any LLM |
| Metrics vs reviewing every alert (§8) |  | Ownership edges in ring detection |
| Claude brief, validated JSON \+ fallback |  |  |
| One-page React UI: input → result panels → decision buttons |  |  |
| DynamoDB decision log (SQLite fallback); EC2 deploy |  |  |

## **4\. Architecture (fastest reliable build)**

Input (ID | form | JSON | CSV) → `normalize.py` → `features.py` (lookup precomputed graph feats)  
 → `model.py` (layer A: triage score \+ SHAP, alerted only) \+ `network.py` (layer B: signals, any txn) → `score.py` (combine, band, layers fired)  
 → `evidence.py` (signals \+ ring \+ ownership \+ reasons, all with record IDs) → `brief.py` (Claude → validated JSON | template fallback)  
 → `api.py` (FastAPI) → `web/` (React \+ shadcn) → `db.py` (DynamoDB `sabwat-decisions`, SQLite fallback)

* **Offline step** (`backend/scripts/build.py`, run once, \~2 min): builds the graphs, writes `artifacts/graph_features.parquet`, trains and saves `artifacts/model.pkl`, and writes `artifacts/metrics.json`.  
* **Libraries:** pandas, pyarrow, networkx, lightgbm, shap, scikit-learn, anthropic, pydantic, fastapi, uvicorn, boto3, python-dotenv. Front end: Vite, React, shadcn/ui (preset `b2trkIJUvo`).  
* **LLM:** Claude via the Anthropic API. Model ID is set in `.env`, temperature is 0\.  
* **Serving:** one uvicorn process on **port 8000** serves the API at `/api` and the built UI (`web/dist`) at `/`.

```
backend/
  sabwat/ api.py config.py
          core/ normalize.py features.py graph.py network.py model.py score.py evidence.py brief.py db.py
  scripts/ check_env.py inspect_data.py provision_aws.py build.py
  tests/ sample_inputs/   # good, messy, unknown-account, PHP-amount examples
web/                      # React + shadcn UI (one page; Sabwat screens built onsite)
deploy/                   # ec2_setup.sh, sabwat.service
artifacts/                # generated, gitignored
Data/                     # Company Parquet, gitignored, never committed
.env.example  README.md  PROJECT.md  docs/PLAN.md
```

## **5\. AI pipeline**

* **Label (one definition, used everywhere):** a transaction is real fraud if its alert is `Closed - True Positive` or its investigation outcome is `Suspicious activity report filed (SAR-like)` or `Account exited`. Alerts or investigations still `Open` are excluded. Transactions have no label of their own.  
* **Layer A, triage model (alerted transactions only):** LightGBM with SHAP top-5. Features: `rule_id`, alert `score`, `amount_usd`, hour, `is_cross_border`, channel, account age, plus the layer B flags. Uses a **time-based split** (train on alerts created ≤ 2025-12-31, test on 2026). A non-alerted transaction never goes through layer A, because it sits outside the training population.  
* **Layer B, network signals (any transaction):** deterministic, each signal carries record IDs:  
  * `ring_member_sender`: the sender's holder is in a shared-attribute component (shared device fingerprint, identity hash, or address \+ postcode).  
  * `fanin_mule_counterparty`: the counterparty receives from ≥10 distinct accounts.  
  * `just_under_10k`: `9000 ≤ amount_usd < 10000`.  
  * `ring_flag`: binary. With one ring, a ring fraud ratio is constant, so it is not a feature.  
  * Scoring: ring-member sender or mule counterparty → High; just-under-$10k alone → Med; two or more signals → High.  
* **Not features:** watchlist hop distance (no signal in the data); any field from `investigations`, `analyst_actions`, `kyc_cases.outcome`, or `risk_alerts.disposition` / `is_false_positive` / `closed_at` / `analyst_employee_id`. These are labels only.  
* **Displayed score:** `max(A, B)` on 0–100, with the band and the list of layers that fired.  
* **LLM input:** An `evidence_pack` JSON containing only computed facts. Each fact carries a `record_id` (txn, account, device, entity, watchlist ID). Raw PII fields (names, addresses, phones) are never sent; IDs and attribute types are enough.  
* **Prompt strategy:** The system prompt says: "You are an AML investigation assistant. Use ONLY the evidence provided. Cite record IDs in every finding. If evidence is insufficient, say so. You recommend; a human decides." Output is forced through a tool/JSON schema.  
* **Output schema:**

{"risk\_summary": "string (≤60 words)",  
 "key\_findings": \[{"finding": "string", "evidence\_ids": \["string"\], "severity": "high|medium|low"}\],  
 "recommended\_action": "escalate|review|dismiss",  
 "open\_questions": \["string"\], "confidence": "high|medium|low"}

* **Validation:** Pydantic parses the output. Any finding whose `evidence_ids` are not in the evidence pack is dropped and counted. If the score band is High and the action is `dismiss`, the output is marked `review` with a warning.  
* **Retries:** 20 s timeout. Up to 2 retries, each appending the validation error to the prompt.  
* **Fallback:** A deterministic template brief built from the evidence pack, labelled **"AI unavailable – template brief"**. The score, SHAP reasons, signals and graph never depend on the LLM.

## **6\. Input handling (varied and unseen inputs)**

* **Modes:** `txn_id` lookup; manual form; pasted JSON; CSV upload (one or many rows).  
* **Normalization:**  
  * Map column aliases case-insensitively, ignoring whitespace (`transaction_id` → `txn_id`; `amt`, `amount_php` → `amount` \+ `currency`).  
  * Convert to **`amount_usd`** using the median `amount_usd / amount` per currency from `transactions` (EUR ≈1.079, GBP ≈1.271, JPY ≈0.00666, PHP ≈0.01788, USD 1).  
  * Parse dates with `pd.to_datetime(format="mixed", dayfirst=False)`.  
  * Strip currency symbols and commas from amounts.  
  * Trim and **UPPERCASE** IDs. All IDs in the data are uppercase (`ACC0000001`, `TXN00000012`).  
  * Drop exact-duplicate rows.  
* **Missing fields:** Impute with training medians and list them under "Data gaps" in the UI and brief.  
* **Unknown account/device (cold start):** Layer B shows the flag "No network history – lower confidence"; layer A is skipped unless alert context is supplied. A brief is still produced.  
* **Invalid input:** Return a readable error naming the field. The app never crashes; every step is wrapped in try/except.

## **7\. Simulated / mocked (disclose in demo and write-up)**

* All data and fraud labels are synthetic Company data. Results are preliminary, not validated findings.  
* Graph features are precomputed. A new transaction is looked up against the existing graph and is not inserted live.  
* The decision log is a DynamoDB table (`sabwat-decisions`), not a real case-management system.  
* Time-saved estimates use `investigations.time_to_decision_hours` (median **60.5 h**). That is investigation time, not L1 triage time, so the write-up also reports triage minutes derived from `analyst_actions`. `05_hackathon_package.md` has no handling-time baseline for risk.  
* Judges' "new transactions" are entered by hand. There is no live transaction feed.

## **8\. Success metrics (2026 hold-out set)**

| Metric | Target |
| ----- | ----- |
| False positives avoided at 90% recall of real cases, versus reviewing every alert (layer A) | Report count and % |
| Rule-engine baseline FP rate under the strict label (§5) | 93.6% (the package's 84.2% uses `is_false_positive`; footnote only) |
| Precision@top-100 flagged (layer A) | Beats rule-engine queue order |
| Ring transactions flagged by layer B that the rules never alerted | Report % of 471 |
| Noisy-rule report: share of alerts and FP rate of R017 \+ R023 | 30.8% of alerts, 94.5% FP |
| Brief grounding: findings with valid evidence IDs (validator \+ manual check of 10\) | 100% after validation |
| End-to-end latency, p95 (score \+ brief) | ≤15 s |
| Time-to-decision in timed demo vs baseline (§7) | Report time saved per alert |

## **9\. Risks**

| Risk | Mitigation |
| ----- | ----- |
| Hallucinated findings | Evidence-only prompt, ID validation drops uncited claims, LLM never sets the score |
| Privacy | No PII to the LLM (IDs only), data gitignored, data stays in event environment, team-level only |
| API failure/latency | Timeout \+ 2 retries \+ template fallback; score works offline |
| Schema mismatch | Data dictionary verified; alias map in `normalize.py`; IDs uppercased |
| Label leakage | Investigation, disposition and analyst-action fields are labels only, never features; time-based split; graph features from training-period edges only |
| Out-of-population scoring | Triage model scores alerted transactions only; non-alerted ones go through the network layer; UI shows which layer fired |
| Giant-component rings | Ownership edges never enter ring detection (one ownership component holds 97% of entities); ownership is a separate 1-hop panel |
| Over-trust in automation | Human decision required and logged; AI shows "recommends", never "decides" |
| Expired AWS credentials | EC2 uses an instance role (no session keys on the box); DB falls back to SQLite if DynamoDB is unreachable |
| EC2 deploy failure at demo | Deploy by hour 3; backup recording; local laptop run as fallback |

## **10\. Build order (each step runnable on its own)**

1. `scripts/inspect_data.py`: load the Parquet risk tables, print shapes and columns, compute the baseline FP rate. *(done)*  
2. `core/graph.py`: build the shared-attribute graph (device, identity-hash and address edges only); print the ring (15 individuals, 49 accounts), the fan-in table (23 mules), and the 1-hop/Nominee ownership lookup.  
3. `scripts/build.py`: write graph features to `artifacts/graph_features.parquet`, plus the FX and label tables.  
4. `core/model.py`: train layer A on the time split; write `metrics.json` (FP avoided at 90% recall, P@100, noisy rules).  
5. `core/network.py`: layer B signals with record IDs; the demo transaction (never alerted, ring) comes out High.  
6. `core/score.py`: combine A and B into score, band and layers fired; CLI test on 3 IDs (alerted-real, alerted-FP, unalerted-ring).  
7. `core/normalize.py`: normalize messy and unknown inputs; test against `tests/sample_inputs/`.  
8. `core/brief.py`: evidence pack → Claude → validated JSON, with retries and fallback; CLI test with the API key unset to confirm the fallback works.  
9. API endpoints and the one-page UI: input → score and layer fired → reasons/signals → ring graph → ownership panel → brief → decision buttons → DynamoDB.  
10. Deploy to AWS EC2, run an end-to-end smoke test from a phone, record the backup demo, finalize README and write-up.

## **11\. Deployment (AWS)**

* **Host:** Company-approved EC2 instance (Ubuntu, t3.medium or larger) in the shared account, region `ap-southeast-1`. Name and tag every resource `sabwat-*` / `Project=sabwat`; never modify other teams' resources.  
* **Setup:** `git clone`, copy `Data/` in, create `.env`, then `bash deploy/ec2_setup.sh`. It creates the venv, installs `backend/requirements.txt`, builds `web/`, runs `backend/scripts/build.py`, and installs the systemd unit.  
* **Run:** `uvicorn sabwat.api:app --app-dir backend --host 0.0.0.0 --port 8000` as the `sabwat` systemd service, so it survives SSH disconnects.  
* **Network:** Security group opens **8000** to event IPs only.  
* **Database:** DynamoDB tables `sabwat-decisions` and `sabwat-briefs`, created by `backend/scripts/provision_aws.py`.  
* **Credentials:** the instance uses the `sabwat-ec2-profile` instance profile (role `sabwat-ec2-role`, DynamoDB access to `sabwat-*` tables only). No AWS keys go in the instance's `.env`. Locally, SSO session keys in `.env` are fine; refresh them when they expire.  
* **Secrets:** `ANTHROPIC_API_KEY` goes in `.env` on the instance and is never committed.  
* **Data:** Copied to the instance from the event environment, not from GitHub, S3 or DynamoDB.  
* **Timing:** Deploy a thin version by hour 3 and redeploy with `git pull` plus a service restart. Keep a local run as the demo fallback.
