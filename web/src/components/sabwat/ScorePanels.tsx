import { Info, Network, ShieldQuestion } from "lucide-react"

import type { Reason, ScoreResult } from "@/lib/api"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { BandChip, RecordId, RecordIds, SectionTitle, pct, usd } from "./common"

/** 0-100 meter with the Low/Med/High band thresholds marked (40, 80). */
function ScoreMeter({ score }: { score: number }) {
  return (
    <div className="w-full" role="img" aria-label={`Risk score ${score} of 100`}>
      <div className="relative h-3 w-full bg-viz-neutral">
        <div className="absolute inset-y-0 left-0 bg-foreground" style={{ width: `${score}%` }} />
        {[40, 80].map((t) => (
          <div key={t} className="absolute inset-y-[-3px] w-0.5 bg-background" style={{ left: `${t}%` }} />
        ))}
      </div>
      <div className="mt-1 grid grid-cols-[40fr_40fr_20fr] text-[0.65rem] tracking-wider text-muted-foreground uppercase">
        <span>Low</span>
        <span>Med</span>
        <span>High</span>
      </div>
    </div>
  )
}

export function ScoreSummary({ r }: { r: ScoreResult }) {
  const t = r.txn
  return (
    <div className="grid gap-6 md:grid-cols-[minmax(0,14rem)_1fr]">
      <div className="flex flex-col gap-3">
        <div className="flex items-end gap-2">
          <span className="font-heading text-6xl leading-none font-semibold tabular-nums">{Math.round(r.score)}</span>
          <span className="pb-1 text-sm text-muted-foreground">/ 100</span>
        </div>
        <BandChip band={r.band} />
        <ScoreMeter score={r.score} />
      </div>
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="tracking-widest text-muted-foreground uppercase">Layer fired</span>
          {r.layers_fired.length ? (
            r.layers_fired.map((l) => (
              <span key={l} className="inline-flex items-center gap-1 border border-foreground px-2 py-0.5 font-semibold">
                {l === "Network" ? <Network className="size-3.5" /> : <ShieldQuestion className="size-3.5" />}
                {l}
              </span>
            ))
          ) : (
            <span className="text-muted-foreground">None. Neither layer found a reason for concern.</span>
          )}
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
          <Field label="Transaction">{t.txn_id ? <RecordId id={String(t.txn_id)} /> : "New"}</Field>
          <Field label="Amount (USD)">{usd(t.amount_usd as number)}</Field>
          <Field label="Channel">{(t.channel as string) ?? "—"}</Field>
          <Field label="Sender">{t.account_id ? <RecordId id={String(t.account_id)} /> : "—"}</Field>
          <Field label="Counterparty">
            {t.counterparty_account_id ? <RecordId id={String(t.counterparty_account_id)} /> : "—"}
          </Field>
          <Field label="Cross-border">{t.is_cross_border ? "Yes" : "No"}</Field>
        </dl>
        {(r.warnings.length > 0 || r.data_gaps.length > 0) && (
          <Alert>
            <Info />
            <AlertTitle>{r.network.cold_start ? "No network history - lower confidence" : "Notes"}</AlertTitle>
            <AlertDescription>
              <ul className="list-disc pl-4">
                {[...r.warnings.filter((w) => !w.startsWith("No network history")), ...r.data_gaps.map((g) => `Data gap: ${g}`)].map(
                  (w) => (
                    <li key={w}>{w}</li>
                  )
                )}
              </ul>
            </AlertDescription>
          </Alert>
        )}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[0.65rem] tracking-widest text-muted-foreground uppercase">{label}</dt>
      <dd className="truncate">{children}</dd>
    </div>
  )
}

/** Diverging SHAP bars: warm pole raises the alert's likelihood, cool pole lowers it. */
function ShapBars({ reasons }: { reasons: Reason[] }) {
  const max = Math.max(...reasons.map((x) => Math.abs(x.contribution)), 1e-6)
  return (
    <ul className="flex flex-col gap-2">
      {reasons.map((x) => {
        const w = (Math.abs(x.contribution) / max) * 50
        const up = x.contribution > 0
        return (
          <li
            key={x.feature}
            className="grid grid-cols-[minmax(0,11rem)_1fr_4.5rem] items-center gap-3 text-xs"
            title={`${x.label} ${x.direction} the likelihood (SHAP ${x.contribution.toFixed(3)})`}
          >
            <span className="truncate">
              <span className="font-medium">{x.label}</span>
              <span className="text-muted-foreground">
                {" "}= {x.value === null ? "missing" : typeof x.value === "number" ? +x.value.toFixed(2) : x.value}
              </span>
            </span>
            <span className="relative h-4">
              <span className="absolute inset-y-0 left-1/2 w-px bg-border" />
              <span
                className={up ? "absolute inset-y-0.5 left-1/2 rounded-r-[4px] bg-shap-up" : "absolute inset-y-0.5 right-1/2 rounded-l-[4px] bg-shap-down"}
                style={{ width: `${w}%` }}
              />
            </span>
            <span className="text-right text-muted-foreground tabular-nums">
              {up ? "raises" : "lowers"} {x.contribution > 0 ? "+" : ""}
              {x.contribution.toFixed(2)}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

const rankText = (p: number) => {
  const top = Math.max(1, Math.round((1 - p) * 100))
  return top <= 10 ? `in the top ${top}% of past alerts` : `higher than ${pct(p)} of past alerts`
}

export function TriagePanel({ r }: { r: ScoreResult }) {
  const t = r.triage
  if (!t.applied) {
    return (
      <div>
        <SectionTitle>Triage model · is this alert real?</SectionTitle>
        <p className="text-sm text-muted-foreground">{t.reason}</p>
      </div>
    )
  }
  return (
    <div>
      <SectionTitle hint={<BandChip band={t.band} short />}>Triage model · is this alert real?</SectionTitle>
      <p className="mb-3 text-sm">
        Alert {t.alert_id ? <RecordId id={t.alert_id} /> : "(supplied)"} from rule <RecordId id={t.rule_id} />{" "}
        <span className="text-muted-foreground">{t.rule_name}</span>. Chance it is real:{" "}
        <strong>{pct(t.p_real, 1)}</strong>, {rankText(t.percentile)}.
      </p>
      <ShapBars reasons={t.reasons} />
      <p className="mt-2 text-[0.7rem] text-muted-foreground">Top 5 factors (SHAP). Red raises the likelihood; blue lowers it.</p>
    </div>
  )
}

export function SignalsPanel({ r }: { r: ScoreResult }) {
  const s = r.network.signals
  return (
    <div>
      <SectionTitle hint={<BandChip band={r.network.band} short />}>Network · what the rules can't see</SectionTitle>
      {s.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No network signals: the sender is not in a ring, the counterparty is not a collection account, and the amount is not just under $10k.
        </p>
      ) : (
        <ol className="flex flex-col gap-3">
          {s.map((x, i) => (
            <li key={x.name} className="grid grid-cols-[1.5rem_1fr] gap-2">
              <span className="font-heading text-lg leading-none font-semibold">{i + 1}</span>
              <div>
                <p className="font-medium">{x.label}</p>
                <p className="text-sm text-muted-foreground">{x.detail}</p>
                {x.evidence_ids.length > 0 && (
                  <div className="mt-1">
                    <RecordIds ids={x.evidence_ids} max={6} />
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

export function OwnershipPanel({ r }: { r: ScoreResult }) {
  const o = r.ownership
  if (!o) return null
  return (
    <div>
      <SectionTitle hint="1-hop only">Ownership · links to watchlisted entities</SectionTitle>
      <p className="mb-2 text-sm">
        Account holder entity <RecordId id={o.entity_id} />
      </p>
      {o.own_entries.map((w) => (
        <p key={w.watchlist_entry_id} className="mb-2 text-sm">
          <strong>Itself listed:</strong> {w.list_type} ({w.reason}) <RecordId id={w.watchlist_entry_id} />
        </p>
      ))}
      {o.links.length === 0 && o.own_entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">No direct ownership link to a watchlisted entity.</p>
      ) : (
        <ul className="flex flex-col gap-2 text-sm">
          {o.links.slice(0, 6).map((l) => (
            <li key={l.ownership_link_id + l.watchlist_entry_id} className="flex flex-wrap items-center gap-1.5">
              {l.is_nominee && <span className="bg-foreground px-1.5 text-[0.65rem] font-semibold tracking-wider text-background uppercase">Nominee</span>}
              <span>{l.direction}</span>
              <RecordId id={l.other_entity_id} />
              <span className="text-muted-foreground">
                {l.link_type}, {l.ownership_pct.toFixed(1)}% · {l.list_type}
              </span>
              <RecordId id={l.watchlist_entry_id} />
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-[0.7rem] text-muted-foreground">
        Deeper ownership chains are not shown: almost every entity is within 4 hops of a watchlist, so they carry no signal.
      </p>
    </div>
  )
}
