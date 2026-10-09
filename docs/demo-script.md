Here's the rewrite. It gives the demo **half the time (5 minutes)**, uses short, plain sentences, and is written at a calm 120 words per minute, slower than normal speech, so nobody has to rush. *\[Pause\]* marks are deliberate; use them. It also folds in the corrected numbers from PLAN.md (93.6% false alarms under the strict label).

---

# **Sabwat: Pitch Script v3 (demo-focused)**

| Section | Time | Speaker |
| ----- | ----- | ----- |
| Hook | 0:00–0:40 | Kirk |
| Problem | 0:40–1:30 | Kirk |
| Solution | 1:30–2:30 | \[Member 2\] |
| **Demo** | **2:30–7:30** | \[Member 3\] drives, \[Member 2\] talks |
| Value | 7:30–8:30 | \[Member 3\] |
| Team \+ Close | 8:30–9:30 | Kirk |
| Buffer | 0:30 | — |

## **HOOK (0:00–0:40) · Kirk**

*\[Slide: 15 dots.\]*

**Fifteen people. One phone.**

*\[Pause.\]*

These fifteen customers look unrelated. Different names. Different accounts.

*\[Click: lines connect them.\]*

But they share one phone number, four devices and two home addresses. Together, they move money through 49 accounts.

*\[Pause.\]*

And the rule engine? It missed three out of every four of their transfers.

*\[Click: title slide.\]*

We're Team \[Name\]. This is **Sabwat**, from the Filipino word *sabwatan*: collusion.

## **PROBLEM (0:40–1:30) · Kirk**

*\[Slide: three numbers.\]*

Today, fraud analysts at the Center work through a long queue of alerts. Three things make that hard.

**First, noise.** More than nine out of ten alerts turn out to be false alarms.

**Second, blind spots.** Rules check one transaction at a time. So when people work together, rules don't see it.

**Third, time.** A typical investigation takes about 60 hours to reach a decision.

*\[Pause.\]*

So analysts spend their days on false alarms, while organized fraud slips through.

## **SOLUTION (1:30–2:30) · \[Member 2\]**

*\[Slide: two layers.\]*

Sabwat helps in two ways.

**Layer one cuts the noise.** It looks at every alert and asks: is this likely real? It learned that from thousands of past alerts and their outcomes.

**Layer two finds what rules miss.** It looks at any transaction and asks: who is this connected to? Shared phones. Shared devices. Accounts that collect money from many people.

Then Claude, our AI writer, turns the evidence into a short case brief. Every sentence points to a real record, so the analyst can check it.

*\[Pause.\]*

And the most important part: **the analyst makes the final decision.** Not the AI.

Let us show you.

## **DEMO (2:30–7:30)**

*\[Switch to the live app. Speak slowly. Let the screen do the work.\]*

**\[Member 2\]:** This is Sabwat, running live on AWS with the Company data. We'll show you four things.

### **Part 1: A transfer the rules missed (2:30–4:30)**

**\[Member 2\]:** Here's a real transfer from the data. *\[Member 3 enters \[TXN ID\].\]* The rule engine never raised an alert on it. It looked normal.

Let's score it.

*\[Click Score. Wait for the result.\]*

Sabwat says: **High risk.** *\[Point.\]* And you can see which layer caught it: the network layer.

Why? Three reasons, right here.

*\[Point to each one.\]*

One: the sender is part of a group of fifteen people who share a phone and devices.

Two: the receiving account collects money from \[N\] different senders.

Three: the amount is just under ten thousand dollars, a common way to avoid checks.

*\[Pause.\]*

Here's the picture. *\[Point to the graph.\]* These are the fifteen people, and these are the accounts the money flows into. One transfer alone looks fine. Together, it's clearly organized.

*\[Point to the brief.\]*

And here's the case brief Claude wrote in a few seconds. Notice the codes in brackets. *\[Point to one.\]* Each one is a real record the analyst can open and check. If Claude ever writes something without a valid source, Sabwat removes it.

*\[Member 3 clicks Escalate and types "Ring activity, escalate."\]*

The analyst decides: **escalate.** Saved.

### **Part 2: Proof it's live, not staged (4:30–5:15)**

**\[Member 2\]:** You might wonder: did we just prepare that one example?

So let's make up a brand-new transfer, right now. *\[Member 3 opens the form.\]* A new sender, any amount, sent to one of those collection accounts.

*\[Fill in and click Score.\]*

Sabwat flags it. It has never seen this sender, but it knows where the money is going. That's the logic working live.

### **Part 3: Cutting the noise (5:15–6:15)**

**\[Member 2\]:** Now the other side: an alert sitting in today's queue. *\[Open \[ALERT ID\].\]*

*\[Click Score.\]*

The triage layer ranks it **low priority.** *\[Point to the reasons.\]* The main reason: it came from a rule whose alerts are almost always false.

*\[Pause.\]*

Sabwat doesn't close it. The analyst can still open it. But now she knows to look at the real cases first.

### **Part 4: Your turn (6:15–7:30)**

**\[Member 2\]:** Now we'd like you to try it. **Give us any transaction or alert ID, or make up a new one.**

*\[Member 3 enters it. While it loads:\]*

You can type an ID, fill in the form, or upload a file. Sabwat cleans up messy formats and converts currencies on its own.

*\[Explain the result in one or two sentences: the score, which layer fired, and the top reason.\]*

*\[If the account is new:\]* This account has no history yet, so Sabwat says clearly that it's less confident. It doesn't pretend to know more than it does.

> **If something goes wrong (stay calm, say one line, move on):**

> * Brief is slow: *"The score works without the AI writer, so here's our backup brief."*  
> * App fails: *"Let's switch to our local copy."* Use the recording only as a last resort.

## **VALUE (7:30–8:30) · \[Member 3\]**

*\[Slide: results.\]*

So what does this mean for the Center?

**One: hidden fraud gets caught.** Using only the data available by \[date\], Sabwat would have flagged \[N\] of this group's later transfers. The rules caught \[M\].

**Two: a quick win today.** Just two rules create a third of all alerts, and nearly all of those are false. Fixing them alone frees up a lot of analyst time.

**Three: faster decisions.** Instead of piecing a case together by hand, the analyst gets a ready case file in about \[time\].

*\[Pause.\]*

To be honest about what we built: this uses made-up data with one planted fraud group, so these results are early. Nothing is closed automatically. And Claude only sees record codes, never personal details.

## **TEAM \+ CLOSE (8:30–9:30) · Kirk**

*\[Slide: team.\]*

We're three builders. *\[Name each one and one thing they built, one sentence each.\]*

*\[Slide: the ring of fifteen, now flagged.\]*

*\[Pause.\]*

Remember our fifteen people? Rules saw small pieces and let them go. Sabwat saw the whole group.

Our ask is one simple next step: **let us test Sabwat on real Sentinel alert history, with your analysts checking the results.**

*\[Pause.\]*

Fraudsters work together. Now, so does our detection.

**Rule engines catch individuals. Sabwat catches the *sabwatan*.**

Thank you.

---

## **What changed from v2**

* **The demo grew from 4 to 5 minutes** and now has four parts. The new Part 2 (a made-up sender paying a known collection account) answers the "is it hardcoded?" concern live.  
* **Solution and AI integration are merged** into one minute of plain language. The technical detail moved to the appendix for Q\&A.  
* **Simpler words throughout:** "false alarms" instead of "false positives," "collection accounts" instead of "fan-in mules," "AI writer" instead of "LLM."  
* **Corrected numbers:** "more than 9 in 10" (93.6%, strict label) and "nearly all false" for the noisy rules (97.7%).  
* **The value section uses the "as-of" metric** instead of the circular one, and the transparency line now mentions the single planted ring.

## **Pacing tips**

* **Read it aloud with a timer once before editing anything.** If you finish early, add pauses, not words.  
* **During the demo, stop talking while the screen loads.** Silence while something computes feels confident, not awkward.  
* **Point before you speak.** Move the cursor to the thing, *then* explain it. Judges follow the cursor.  
* **Prepare Part 2's inputs in advance** (the collection account ID and an amount), so typing takes seconds.  
* **For Part 4, keep the answer to two sentences:** score, layer, top reason. Expand only if a judge asks.

