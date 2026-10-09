# Sabwat UI/UX Plan

**Goal:** an L1 analyst (or a judge) understands the verdict in **5 seconds**, the reasons in **20**, and can decide in **under 60**. The technical depth stays, but behind a click.

## Audit of the current UI (2026-10-09)

| # | Problem | UX principle broken |
|---|---|---|
| 1 | The verdict (score) is at the top, but the AI recommendation and the decision buttons are ~2 screens down. | Keep the primary action next to the information it depends on. |
| 2 | Every signal, finding and reason is a full sentence plus 3–8 record-ID chips. Dense walls of text. | Progressive disclosure: summary first, detail on demand. |
| 3 | Panels look alike (same card, same uppercase title), so nothing guides the eye. | Visual hierarchy: one focal point per section; icons for recognition. |
| 4 | Jargon: "fan-in mule", "SHAP", "percentile", "layer". | Speak the user's language (matches the pitch: "collection account", "AI writer"). |
| 5 | Model results sit under every investigation and add scroll. | Separate tasks into separate places. |
| 6 | Example cards are paragraphs; the first-run screen has no guidance. | Recognition over recall; a helpful empty state. |
| 7 | Long scroll on phones; decision buttons far from the thumb. | Mobile-first primary action. |
| 8 | A record opens in a small popover that is hard to read. | Use a side sheet for secondary detail. |

## Phases

### Phase 1: Structure and hierarchy ✅
- Top-level **tabs**: `Investigate` | `Results` (model metrics move out of the investigation flow).
- **Empty state** before the first score: icon, one sentence, and the four scenarios as compact items.
- **Verdict header**: score ring, band, "caught by" layer icons, the AI recommendation, and the **Escalate / Review / Dismiss** buttons in one card. It stays sticky while scrolling on desktop and docks to the bottom on mobile.
- **Result tabs** under the header: `Why` (signals and triage), `Ring` (graph), `Brief` (AI writer), `Record` (transaction details and ownership). Fewer things on screen at once.

### Phase 2: Less text, more icons (progressive disclosure) ✅
- **Signal tiles**: icon, short headline, one key number (e.g. *13 senders*, *15 people*, *$9,467*). The full sentence and record IDs go into a collapsible "Details".
- **Evidence IDs** collapse into an "N records" toggle everywhere; the first 2 stay visible.
- **Triage reasons**: a compact bar list with plain labels; SHAP explained in a tooltip.
- **Brief**: summary first; findings as an accordion (headline plus severity icon, expand for evidence); open questions collapsed.
- **Glossary tooltips** (hover card) on the few domain terms: collection account, ring, triage model.

### Phase 3: Input that guides ✅
- The ID box is the primary input (large, with a keyboard hint `Enter`).
- The four scenarios become small **icon items** (one line each), not paragraphs.
- The Form is grouped into "Who" / "What" / "Alert (optional)" with inline field errors.
- CSV becomes a **drop zone** (drag a file or click); results show in a ranked queue.

### Phase 4: Feedback and polish ✅
- Skeletons while scoring; a spinner chip for the AI writer with elapsed time.
- Records open in a **Sheet** (side panel) with readable fields.
- Keyboard: `/` focuses the ID box, `Enter` scores.
- A11y: every icon has a text label or `aria-label`; band is never color-only; focus states visible.
- Verify with headless screenshots: desktop light/dark and a 390 px phone.

## Rules applied throughout
1. **One sentence max** per visible line item; everything longer is behind "Details".
2. **Icon + word**, never icon alone, never color alone.
3. **Numbers over adjectives** ("13 senders", not "high fan-in").
4. **Plain words** from the pitch script: *false alarm*, *collection account*, *AI writer*, *the analyst decides*.
5. **The human decides**: the AI recommendation is labelled "suggests", and the buttons belong to the analyst.

## Status (2026-10-09)

All four phases are built and checked with screenshots: desktop light and dark, a 390 px phone (no horizontal overflow, measured in a real browser), the record sheet, form validation, and the Results tab. Deep links for demos: `/?id=TXN00000241&tab=ring` (tabs: `why`, `ring`, `brief`, `record`).
