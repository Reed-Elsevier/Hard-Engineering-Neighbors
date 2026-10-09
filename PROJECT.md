# **PROJECT.md: Sabwat — Fraud Ring Intelligence (Track 4: Fraud & Identity Intelligence)**

> Persistent context for the coding assistant. Column and table names below are **assumptions**. Verify them against `_docs/03_data_dictionary.md` before writing code, and update this file if they differ.

> **Updates (2026-10-08, verified against the data; details in [docs/PLAN.md](docs/PLAN.md)):**
> * **UI is React + shadcn/ui (preset `b2trkIJUvo`) with a FastAPI backend, not Streamlit.** Wherever this file says Streamlit/`app.py`, read `web/` + `backend/sabwat/api.py`. Production serves both from one uvicorn process on port 8000.
> * Transaction PK is `txn_id`; amount feature is `amount_usd`. Phones/emails/IDs exist only as hashes in `identity_attributes`.
> * Transactions carry **no fraud label**. Label = alert `Closed - True Positive` or investigation outcome SAR-like / Account exited; the model trains on alerted transactions.
> * Shared-attribute rings are few and planted (4 shared device fingerprints, 1 shared phone hash, 2 shared addresses). Treat them as a high-precision signal and widen the graph with counterparty and ownership edges.
> * Repo layout: `backend/` (package `sabwat`, `scripts/`, `tests/`), `web/`, `deploy/`, `docs/`. `scripts/inspect.py` is named `inspect_data.py` so it does not shadow the stdlib module.

## **1\. Pitch**

* **Solution:** Sabwat scores any transaction in the context of the identity and ownership network around it. It explains the score, then drafts an evidence-cited brief so a human analyst can decide in under a minute.

* **Why AI is essential:** Fraud rings and hidden ownership are relational patterns that per-transaction rules cannot see. An ML model learns which network and behaviour signals predict fraud. An LLM condenses dozens of linked records into a readable, cited brief in seconds.

* **Name:** *Sabwat*, from Filipino *sabwatan* ("collusion"). Use it in UI titles, README and pitch.

* **Pitch line:** "Rule engines catch individuals. Sabwat catches the *sabwatan*."

## **2\. User and demo story**

* **User:** A Sentinel Risk L1 fraud/AML analyst who works a noisy rule-engine alert queue.

* **Trigger:** A new transaction arrives, or a rule alert fires on one.

* **Input:** A `transaction_id` from the data, or a new transaction entered by form, JSON or CSV. The judges' unseen input arrives this way.

* **Outcome:** The app returns:

  * a risk score from 0 to 100 with a band (Low/Med/High) and the top 5 SHAP reasons;  
  * a ring graph of identities sharing devices, addresses or phones with the account;  
  * the ownership path to a watchlisted entity, if one exists;  
  * a Claude brief citing record IDs.  
* The analyst clicks **Escalate / Review / Dismiss** with a note, and the decision is logged. Target: decision-ready in 60 seconds or less, compared with the baseline handling time.

## **3\. Scope**

| MUST-HAVE (demo-critical, \~3.5 h) | NICE-TO-HAVE | OUT OF SCOPE |
| ----- | ----- | ----- |
| Load Parquet; precompute graph features | Batch CSV scoring \+ ranked queue | Real-time streaming |
| Shared-attribute rings (connected components) | Rule-tuning report: noisiest `risk_alerts` rules | Auth/RBAC, multi-user |
| Ownership BFS to watchlist (max 4 hops) | Interactive pyvis graph | Case-management integration |
| LightGBM model \+ SHAP top-5 reasons | Analyst feedback → retrain | Model monitoring/drift |
| Metrics vs rule-alert baseline (FP rate) | Raw-table cleaning demo (`raw/`) | Individual analyst ranking (banned) |
| Claude brief, validated JSON \+ fallback | Supplier-risk cross-link (Area G) | Fine-tuning any LLM |
| Streamlit UI: input → score → evidence → decision |  |  |
| SQLite decision log; EC2 deploy |  |  |

## **4\. Architecture (fastest reliable build)**

Input (ID | form | JSON | CSV) → normalize.py → features.py (lookup precomputed graph feats)  
 → model.py (LightGBM score \+ SHAP) → evidence.py (ring \+ ownership path \+ top reasons, all with record IDs)  
 → brief.py (Claude → validated JSON | template fallback) → app.py (Streamlit) → decisions.db (SQLite)

* **Offline step** (`scripts/build.py`, run once, \~2 min): builds the graphs, writes `artifacts/graph_features.parquet`, trains and saves `artifacts/model.pkl`, and writes `artifacts/metrics.json`.  
* **Libraries:** pandas, pyarrow, networkx, lightgbm, shap, scikit-learn, anthropic, pydantic, streamlit, streamlit-agraph (or matplotlib fallback), python-dotenv.  
* **LLM:** Claude via the Anthropic API. Model ID is set in `.env`, temperature is 0\.

sabwat/  
  app.py            \# Streamlit UI  
  core/ normalize.py features.py graph.py model.py evidence.py brief.py db.py  
  scripts/build.py  \# offline precompute \+ train \+ eval  
  artifacts/        \# generated, gitignored  
  data/             \# Company Parquet, gitignored, never committed  
  tests/sample\_inputs/  \# good, messy, unknown-account examples  
  .env.example  requirements.txt  README.md  PROJECT.md

## **5\. AI pipeline**

* **ML:** Uses transaction features (amount, hour, velocity, new device, cross-border) plus graph features (ring size, ring fraud ratio, shared-device count, watchlist hop distance, degree). Training uses a **time-based split** (train ≤ 2025-12, test 2026\) to avoid leakage. Graph features come from training-period edges only.  
* **LLM input:** An `evidence_pack` JSON containing only computed facts. Each fact carries a `record_id` (txn, account, device, entity, watchlist ID). Raw PII fields (names, addresses, phones) are never sent; IDs and attribute types are enough.  
* **Prompt strategy:** The system prompt says: "You are an AML investigation assistant. Use ONLY the evidence provided. Cite record IDs in every finding. If evidence is insufficient, say so. You recommend; a human decides." Output is forced through a tool/JSON schema.  
* **Output schema:**

{"risk\_summary": "string (≤60 words)",  
 "key\_findings": \[{"finding": "string", "evidence\_ids": \["string"\], "severity": "high|medium|low"}\],  
 "recommended\_action": "escalate|review|dismiss",  
 "open\_questions": \["string"\], "confidence": "high|medium|low"}

* **Validation:** Pydantic parses the output. Any finding whose `evidence_ids` are not in the evidence pack is dropped and counted. If the model's score band is High and the action is `dismiss`, the output is marked `review` with a warning.  
* **Retries:** 20 s timeout. Up to 2 retries, each appending the validation error to the prompt.  
* **Fallback:** A deterministic template brief built from the evidence pack, labelled **"AI unavailable – template brief"**. The score, SHAP reasons and graph never depend on the LLM.

## **6\. Input handling (varied and unseen inputs)**

* **Modes:** `transaction_id` lookup; manual form; pasted JSON; CSV upload (one or many rows).  
* **Normalization:**  
  * Map column aliases case-insensitively, ignoring whitespace (`amt`, `amount_php` → `amount`).  
  * Parse dates with `pd.to_datetime(format="mixed", dayfirst=False)`.  
  * Strip currency symbols and commas from amounts.  
  * Trim and lowercase IDs.  
  * Drop exact-duplicate rows.  
* **Missing fields:** Impute with training medians and list them under "Data gaps" in the UI and brief.  
* **Unknown account/device (cold start):** Score on transaction features only, show the flag "No network history – lower confidence", and still produce a brief.  
* **Invalid input:** Return a readable error naming the field. The app never crashes; every step is wrapped in try/except.

## **7\. Simulated / mocked (disclose in demo and write-up)**

* All data and fraud labels are synthetic Company data. Results are preliminary, not validated findings.  
* Graph features are precomputed. A new transaction is looked up against the existing graph and is not inserted live.  
* The decision log is a local SQLite file, not a real case-management system.  
* Time-saved estimates assume the baseline handling time from `05_hackathon_package.md`.  
* Judges' "new transactions" are entered by hand. There is no live transaction feed.

## **8\. Success metrics (2026 hold-out set)**

| Metric | Target |
| ----- | ----- |
| False-positive rate vs rule-engine `risk_alerts` at equal recall | ≥30% lower |
| Precision@top-100 flagged | Beats rule baseline |
| Confirmed-fraud accounts inside detected rings | Report % |
| Brief grounding: findings with valid evidence IDs (validator \+ manual check of 10\) | 100% after validation |
| End-to-end latency, p95 (score \+ brief) | ≤15 s |
| Time-to-decision in timed demo vs baseline handling time | Report minutes saved per alert |

## **9\. Risks**

| Risk | Mitigation |
| ----- | ----- |
| Hallucinated findings | Evidence-only prompt, ID validation drops uncited claims, LLM never sets the score |
| Privacy | No PII to the LLM (IDs only), data gitignored, data stays in event environment, team-level only |
| API failure/latency | Timeout \+ 2 retries \+ template fallback; score works offline |
| Schema mismatch | Verify the data dictionary first (step 1); alias map in `normalize.py` |
| Label leakage / overfitting | Time-based split; graph from training period only |
| Over-trust in automation | Human decision required and logged; AI shows "recommends", never "decides" |
| EC2 deploy failure at demo | Deploy by hour 3; backup recording; local laptop run as fallback |

## **10\. Build order (each step runnable on its own)**

1. `scripts/inspect.py`: load the Parquet risk tables, print shapes and columns, compute the baseline alert FP rate.  
2. `core/graph.py`: build the shared-attribute graph and output ring IDs and sizes (prints top rings).  
3. `core/graph.py`: run the ownership BFS to the watchlist; print the paths for 3 sample entities.  
4. `scripts/build.py`: write graph features to `artifacts/graph_features.parquet`.  
5. `core/model.py`: train LightGBM on the time split; write `metrics.json` comparing against the rule baseline.  
6. `core/model.py`: `score(txn) → score, band, shap_top5`; CLI test on 3 IDs.  
7. `core/normalize.py`: normalize messy and unknown inputs; test against `tests/sample_inputs/`.  
8. `core/brief.py`: evidence pack → Claude → validated JSON, with retries and fallback; CLI test with the API key unset to confirm the fallback works.  
9. `app.py`: Streamlit flow, input → score → graph → brief → decision buttons → SQLite.  
10. Deploy to AWS EC2, run an end-to-end smoke test from a phone, record the backup demo, finalize README and write-up.

## **11\. Deployment (AWS)**

* **Host:** Company-approved EC2 instance (Ubuntu, t3.medium or larger). Set up with `git clone`, then `python -m venv`, `pip install -r requirements.txt`, and `python scripts/build.py`.  
* **Run:** `streamlit run app.py --server.port 8501 --server.address 0.0.0.0` as a `systemd` service (or `nohup`) so it survives SSH disconnects.  
* **Network:** Security group opens 8501 to event IPs only.  
* **Secrets:** `ANTHROPIC_API_KEY` goes in `.env` on the instance and is never committed.  
* **Data:** Copied to the instance from the event environment, not from GitHub.  
* **Timing:** Deploy a thin version by hour 3 and redeploy with `git pull` plus a service restart. Keep a local run as the demo fallback.

