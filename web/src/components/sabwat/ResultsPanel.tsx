import type { Metrics } from "@/lib/api"
import { SectionTitle, pct } from "./common"

const NOISY = new Set(["R017", "R023"])

function Tile({ value, label, sub }: { value: string; label: string; sub: string }) {
  return (
    <div className="border border-border p-4">
      <p className="font-heading text-3xl font-semibold tabular-nums">{value}</p>
      <p className="mt-1 text-sm font-medium">{label}</p>
      <p className="mt-1 text-xs text-muted-foreground">{sub}</p>
    </div>
  )
}

/** Hold-out results for the Value slide; every number comes from artifacts/metrics.json. */
export function ResultsPanel({ m }: { m: Metrics }) {
  const t = m.triage_test
  const asOf = m.as_of.find((a) => a.cutoff === "2026-03-01") ?? m.as_of[0]
  const cutoff = new Date(asOf.cutoff).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
  const rules = [...m.rules].sort((a, b) => b.alerts - a.alerts).slice(0, 10)
  const maxShare = Math.max(...rules.map((r) => r.share_of_alerts))

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Tile value={pct(m.baseline.fp_rate_strict, 1)} label="of rule alerts are false alarms"
          sub={`Strict label (confirmed real or SAR / exit). Published figure ${pct(m.baseline.fp_rate_is_false_positive, 1)} uses a looser definition.`} />
        <Tile value={t.at_90_recall_model.fp_avoided.toLocaleString()} label="false alarms skipped, 90% of real cases kept"
          sub={`2026 hold-out: ${pct(t.at_90_recall_model.fp_avoided_pct)} of false alarms, vs ${t.at_90_recall_rule_score.fp_avoided.toLocaleString()} ranking by the rule score.`} />
        <Tile value={`${asOf.flagged_high} of ${asOf.later_ring_transfers}`} label={`later ring transfers flagged, using data before ${cutoff}`}
          sub={`Rules alerted on ${asOf.rules_alerted}; analysts confirmed ${asOf.rules_confirmed_real}.`} />
        <Tile value={pct(m.noisy_rules.combined_share_of_alerts)} label="of all alerts come from two rules"
          sub={`R017 and R023: ${pct(m.noisy_rules.combined_fp_rate, 1)} false alarms. Tuning them is a quick win.`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div>
          <SectionTitle hint="share of all alerts · label shows false-alarm rate">Busiest rules</SectionTitle>
          <ul className="flex flex-col gap-1.5">
            {rules.map((r) => (
              <li key={r.rule_id} className="grid grid-cols-[minmax(0,13rem)_1fr_7.5rem] items-center gap-3 text-xs"
                title={`${r.rule_id} ${r.rule_name}: ${r.alerts.toLocaleString()} alerts, ${pct(r.share_of_alerts, 1)} of all, ${pct(r.fp_rate, 1)} false alarms`}>
                <span className={`truncate ${NOISY.has(r.rule_id) ? "font-semibold" : ""}`}>
                  <span className="font-mono">{r.rule_id}</span> {r.rule_name}
                </span>
                <span className="h-3.5">
                  <span className={`block h-full rounded-r-[4px] ${NOISY.has(r.rule_id) ? "bg-primary" : "bg-muted-foreground/50"}`}
                    style={{ width: `${(r.share_of_alerts / maxShare) * 100}%` }} />
                </span>
                <span className="text-right tabular-nums text-muted-foreground">
                  {pct(r.share_of_alerts, 1)} · <span className={NOISY.has(r.rule_id) ? "font-semibold text-foreground" : ""}>{pct(r.fp_rate, 0)} false</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className="flex flex-col gap-3 text-sm">
          <SectionTitle>Model quality (2026 hold-out)</SectionTitle>
          <dl className="grid grid-cols-[1fr_auto_auto] gap-x-4 gap-y-1.5 tabular-nums">
            <dt className="text-xs text-muted-foreground" />
            <dd className="text-xs text-muted-foreground">Sabwat</dd>
            <dd className="text-xs text-muted-foreground">Rule score</dd>
            <dt>Ranking quality (AUC)</dt><dd className="font-semibold">{t.auc_model.toFixed(2)}</dd><dd>{t.auc_rule_score.toFixed(2)}</dd>
            <dt>Precision, top 100</dt><dd className="font-semibold">{pct(t.precision_at_100_model)}</dd><dd>{pct(t.precision_at_100_rule_score)}</dd>
            <dt>False alarms skipped @90% recall</dt><dd className="font-semibold">{pct(t.at_90_recall_model.fp_avoided_pct)}</dd><dd>{pct(t.at_90_recall_rule_score.fp_avoided_pct)}</dd>
          </dl>
          <p className="text-xs text-muted-foreground">
            Baseline time: investigations take a median {m.time_baseline.investigation_median_hours} h to decide; reviewing alert
            details alone takes a median {m.time_baseline.review_alert_details_median_min} min.
          </p>
          <p className="text-xs text-muted-foreground">
            Synthetic data with one planted ring; results are preliminary. Nothing is closed automatically.
          </p>
        </div>
      </div>
    </div>
  )
}
