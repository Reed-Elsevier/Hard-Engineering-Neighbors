# Sabwat Demo Guide

For the presenters: what to click, what appears, what to say, and how to answer questions. Every number below was checked against the running app on 2026-10-09.

---

## 1. Before you go on stage (10 minutes)

| ✓ | Check |
|---|---|
| ☐ | Open the deployed link. The header shows **● Engine ready** and **● AI writer on**. |
| ☐ | Score each of the four scenario cards once so nothing is loading for the first time on stage. |
| ☐ | Open a tab with the **Results** view ready (for the Value section). |
| ☐ | Zoom the browser to 110–125% so the back row can read it. Pick light or dark mode and keep it. |
| ☐ | Have the local fallback running on a laptop (`http://localhost:5173`) and the backup recording ready. |
| ☐ | Keep this page or the quick-reference card (section 7) open on a second screen. |

**Shortcut links** (replace `<link>` with the deployed URL):

| Opens | URL |
|---|---|
| Part 1, straight to the result | `<link>/?id=TXN00000241` |
| Part 1, ring graph tab | `<link>/?id=TXN00000241&tab=ring` |
| Part 1, case brief tab | `<link>/?id=TXN00000241&tab=brief` |
| Part 3, noisy alert | `<link>/?id=TXN00081086` |

---

## 2. What is on the screen

| Area | What it shows | Why it matters |
|---|---|---|
| **Header** | Engine, AI writer and decision-log status dots | Shows the system is live |
| **Try a scenario** | Four one-click demo cases | No typing on stage |
| **ID / Form / JSON / CSV** | Four ways to enter a transaction | Judges can give us anything |
| **Verdict card** | Score ring (0–100), risk band, **Caught by**, **AI suggests**, and Escalate / Review / Dismiss | The decision in one glance; the human decides |
| **Why** tab | Network signal tiles and alert-triage reasons | The evidence, as numbers |
| **Ring** tab | Graph of the people and accounts linked to the sender | "Who is this connected to?" |
| **Brief** tab | The AI writer's case summary with record citations | Saves the analyst writing time |
| **Record** tab | Transaction fields and ownership links | Raw detail for checking |
| **Results** (top tab) | Model results on the 2026 hold-out data | The Value slide, live |

Anything underlined with dots (*ring*, *collection account*, *alert triage*) explains itself on hover. Any grey code such as `ACC0023898` opens the real record in a side panel.

---

## 3. The demo, step by step (5 minutes)

### Part 1: A transfer the rules missed (2:30–4:30)

**Click:** the **Missed by rules** card (or open `<link>/?id=TXN00000241`).

**What appears:**
- Score **98 / 100**, **HIGH RISK**, "Needs attention".
- **Caught by: Network**. **AI suggests: Escalate · you decide**.
- *Why* tab, three tiles:

| Tile | Number | Plain meaning |
|---|---|---|
| Sender is in a ring | **15** people in the ring | The sender shares phones, devices or addresses with 14 other people |
| Money goes to a collection account | **13** accounts pay into it | The receiving account `ACC0079937` collects from 13 different senders (normal is 1–3) |
| Amount just under $10k | **$9,467** | Kept just below the $10,000 reporting threshold |

**Say:** "The rule engine never raised an alert on this transfer. Sabwat flags it **High**, and you can see which layer caught it: the network layer. One transfer alone looks fine. Together, it's clearly organised."

**Then:**
1. Click the **Ring** tab. Point to the red **Sender** circle, then the **Receiver** square. "These are the 15 people. The small squares are the accounts the money flows into."
2. Click the **Brief** tab. "The AI writer drafted this in a few seconds." Open one finding and click one of its record codes: the record opens on the right. "Every finding cites a real record. If the AI cites something that isn't in the evidence, Sabwat removes it." Point to the **All findings cite real records** chip.
3. Click **Add a note**, type `Ring activity, escalate.`, click **Escalate**. A confirmation appears: "Saved."

### Part 2: Proof it's live, not staged (4:30–5:15)

**Click:** the **New sender, collection account** card. It fills the **Form** tab:

| Field | Value |
|---|---|
| Sender account | `ACC0999999` (never seen before) |
| Receiving account | `ACC0079937` (the collection account from Part 1) |
| Amount | `250000` **PHP** (about USD 4,464) |

Change the amount to any number you like, then click **Score transaction**.

**What appears:** score **90**, **HIGH RISK**, caught by **Network**, one tile: **13** accounts pay into it. A blue note reads **"New account: no network history, so confidence is lower."**

**Say:** "Sabwat has never seen this sender, but it knows where the money is going. That's the logic working live, and it's honest that it knows less about a new account."

### Part 3: Cutting the noise (5:15–6:15)

**Click:** the **Noisy rule, safe to deprioritise** card (`TXN00081086`).

**What appears:**
- Score **5 / 100**, **LOW RISK**, "Looks routine". Nothing in **Caught by**.
- *Why* tab, alert-triage panel: **1% chance it is real**. Rule **R017** *Round-amount cross-border transfer*. The top factor is the alert rule itself.

**Say:** "This alert came from R017, a rule whose alerts are almost always false (98% of them). Sabwat ranks it low priority. It doesn't close it: the analyst can still open it. But now she knows to look at the real cases first."

*Optional contrast:* the **Real alert, ranked first** card (`TXN00162305`) scores **99**, caught by **Alert triage**: **25% chance it is real**, in the **top 1% of past alerts** (the typical alert is about 6.5%). That alert was later confirmed real.

### Part 4: Your turn (6:15–7:30)

Ask a judge for an ID, or let them make one up.

| They give you | Where to type it | Notes |
|---|---|---|
| A transaction ID (`TXN…`) | **ID** tab, press Enter | Case doesn't matter |
| An alert ID (`ALR…`, e.g. `ALR0000001`) | **ID** tab | Scores that alert's transaction with the triage model |
| A made-up transaction | **Form** tab | Any currency (USD, PHP, EUR, GBP, JPY); date defaults to now |
| Messy data | **JSON** tab | Odd field names, `₱540,000.00`, `30/09/2026` all work |
| Many rows | **CSV** tab | Drag a file in; you get a ranked queue, and clicking a row opens it |

**Answer in two sentences:** the score and band, which layer fired, and the top reason. Expand only if asked.

If the account is new: "This account has no history yet, so Sabwat says clearly that it's less confident. It doesn't pretend to know more than it does."

---

## 4. The Results tab (Value section)

| Tile | Number | What to say |
|---|---|---|
| False alarms today | **93.6%** of rule alerts are false | "More than nine out of ten alerts are false alarms." (The package quotes 84.2% under a looser definition.) |
| False alarms skipped | **2,844** (26%) while keeping 90% of real cases | "Ranking by our model, analysts skip a quarter of the false alarms and still catch 9 in 10 real cases. Ranking by the rule engine's own score skips 1,280." |
| Ring caught early | **315 of 420** later ring transfers flagged | "Using only data available before 1 March 2026, Sabwat flags 315 of the group's 420 later transfers. The rules alerted on 113." |
| Two noisy rules | **31%** of all alerts | "R017 and R023 create a third of all alerts, and 97.7% of those are false. Tuning them is a quick win." |

The **Busiest rules** bars and the **Model quality** table back these up. Be ready to say that the model is slightly *worse* on the very top 100 alerts (10% vs 13% real). We report it honestly; the gain is across the whole queue.

Time baseline: an investigation takes a median **60.5 hours** to reach a decision; reviewing alert details alone takes a median **12 minutes**.

---

## 5. How it works (for questions)

### Two layers, one score
| Layer | Looks at | Answers | Works on |
|---|---|---|---|
| **Alert triage** (machine-learning model) | The alert's rule, rule score, amount, time, account age, channel… | "Is this alert real?" | Alerted transactions only |
| **Network** (rules over a graph) | Who the sender and receiver are connected to | "Is this part of a group the rules can't see?" | Any transaction |

The displayed score is the **higher** of the two (0–100). **High** is 80 or more, **Med** 40 to 79, **Low** under 40. The verdict card always says which layer fired.

### The network signals
- **Ring:** people linked because they share a device fingerprint, a phone or ID hash, or a home address. The data contains one ring: 15 people, 49 accounts.
- **Collection account:** an account receiving from 10 or more different senders. Normal accounts receive from 1 to 3. All 23 such accounts belong to ring members.
- **Just under $10k:** an amount between $9,000 and $9,999. This is common in the ring (85% of its transfers) but rare overall (0.5%).
- Scoring: a ring sender or collection account means High (90). Two signals score 95, three score 98. Just under $10k alone is Med (55).

### The alert-triage model
- LightGBM trained on 18,368 alerts from 2024–2025, and tested on 11,599 alerts from 2026 it never saw.
- "Real" means the alert was confirmed true, or the investigation ended in a suspicious-activity report or account exit.
- The **factors** bars (SHAP values) show how much each detail pushed this alert's estimate up (red) or down (blue).
- The ring isn't a model feature: it only formed from November 2025, so the training data has no examples of it. The network layer covers it instead.

### The case brief
- Claude (on AWS Bedrock) or Gemini writes it from an **evidence pack**: computed facts and record IDs only. **No names, addresses or phone numbers are sent.**
- Every finding must cite record IDs from the pack. Findings that cite anything else are removed. If the score is High, a "dismiss" suggestion is changed to "review".
- If the AI is slow or unavailable, a rule-based template brief appears, clearly labelled **AI unavailable – template brief**. The score, reasons and graph never depend on the AI.

### Decisions
Escalate / Review / Dismiss are logged with the score, the layer that fired and the note. Sabwat never closes or escalates anything by itself.

---

## 6. Likely questions

| Question | Short answer |
|---|---|
| "Is this real data?" | No. It's synthetic data from the event package, with one planted fraud group. The results are early. |
| "Did you hard-code the demo?" | No. Part 2 makes up a new sender live, and any ID from the data works. |
| "Why not just add more rules?" | Rules look at one transaction at a time. The ring is only visible across people and accounts. |
| "What if the AI makes things up?" | Findings that cite records outside the evidence are removed, and the AI never sets the score. |
| "Does the AI see personal data?" | No. Only record IDs and computed facts. |
| "Why is the network score so confident with no model?" | The signals are deterministic and each one shows its evidence. The as-of test shows they work on data the rules missed. |
| "Why is 25% chance 'High'?" | The typical alert is real about 6.5% of the time, so 25% puts it in the top 1% of the queue. |
| "What about new accounts?" | Scored on what we know (the receiver, the amount), with a lower-confidence warning. |
| "Does a new transaction change the network?" | Not live. The graph is precomputed, and new transactions are scored against it. A redeploy with new data rebuilds it. |
| "How fast is it?" | Scoring takes under a second; the brief a few seconds. |
| "What would you do next?" | Test on real Sentinel alert history, with analysts checking the results. |

---

## 7. If something goes wrong

| Problem | Say | Do |
|---|---|---|
| The brief is slow | "The score works without the AI writer; here's our backup brief." | Keep going. The template brief appears automatically if the AI fails. |
| Header shows **Loading model…** | "It's warming up." | Wait about 15 seconds, then refresh. |
| An ID isn't found | "That one isn't in the dataset. Let's make it up instead." | Use the **Form** tab. |
| The link is down | "Let's switch to our local copy." | Open `http://localhost:5173` on the fallback laptop. |
| Everything fails | — | Play the backup recording. |

### Quick-reference card

| Use | ID |
|---|---|
| Missed by rules (Part 1) | `TXN00000241` → 98 High, Network |
| Collection account | `ACC0079937` (13 senders) |
| Ring sender | `ACC0023898` (person `IND0016675`) |
| Real alert | `TXN00162305` / `ALR0029928` → 99 High, Alert triage, 25% |
| Noisy false alarm (Part 3) | `TXN00081086` / `ALR0006171` → 5 Low, rule R017 |
| Any alert ID | `ALR0000001` |
| Spare unalerted ring transfers | `TXN00000271`, `TXN00000122` |
