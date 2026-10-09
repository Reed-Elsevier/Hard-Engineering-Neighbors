import {
  ArrowDownToLine, ArrowLeftRight, Banknote, CalendarClock, CreditCard, Globe2, Info, ListFilter, ShieldCheck,
  Siren, Smartphone, TrendingDown, TrendingUp, Trophy, UserRound, Users, Waypoints,
} from "lucide-react"

import type { Reason, ScoreResult, Signal } from "@/lib/api"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { BandChip, Details, RecordId, RecordIds, SectionTitle, Term, pct, usd } from "./common"

/** Warnings and data gaps, shown right under the verdict so they are not missed. */
export function NotesAlert({ r }: { r: ScoreResult }) {
  const notes = [...r.warnings.filter((w) => !w.startsWith("No network history")), ...r.data_gaps.map((g) => `Missing: ${g}`)]
  if (!r.network.cold_start && notes.length === 0) return null
  return (
    <Alert>
      <Info />
      <AlertTitle>{r.network.cold_start ? "New account: no network history, so confidence is lower" : "Notes on this input"}</AlertTitle>
      {notes.length > 0 && (
        <AlertDescription>
          <ul className="list-disc pl-4">{notes.map((w) => <li key={w}>{w}</li>)}</ul>
        </AlertDescription>
      )}
    </Alert>
  )
}

export function RecordPanel({ r }: { r: ScoreResult }) {
  const t = r.txn
  return (
    <div>
      <SectionTitle>Transaction</SectionTitle>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
        <Field icon={CreditCard} label="Transaction">{t.txn_id ? <RecordId id={String(t.txn_id)} /> : "New"}</Field>
        <Field icon={Banknote} label="Amount">
          {usd(t.amount_usd as number)}
          {t.currency && t.currency !== "USD" && <span className="text-muted-foreground"> ({String(t.currency)})</span>}
        </Field>
        <Field icon={UserRound} label="Sender account">{t.account_id ? <RecordId id={String(t.account_id)} /> : "—"}</Field>
        <Field icon={ArrowLeftRight} label="Receiving account">{t.counterparty_account_id ? <RecordId id={String(t.counterparty_account_id)} /> : "—"}</Field>
        <Field icon={Smartphone} label="Channel">{(t.channel as string) ?? "—"}</Field>
        <Field icon={Globe2} label="Cross-border">{t.is_cross_border ? "Yes" : "No"}</Field>
        <Field icon={CalendarClock} label="Date">{t.txn_ts ? String(t.txn_ts).slice(0, 16).replace("T", " ") : "—"}</Field>
      </dl>
    </div>
  )
}

function Field({ icon: Icon, label, children }: { icon: typeof Info; label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 gap-2">
      <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
      <div className="min-w-0">
        <dt className="text-xs text-muted-foreground">{label}</dt>
        <dd className="truncate">{children}</dd>
      </div>
    </div>
  )
}

/** Diverging bars: warm pole raises the alert's likelihood, cool pole lowers it. */
function FactorBars({ reasons }: { reasons: Reason[] }) {
  const max = Math.max(...reasons.map((x) => Math.abs(x.contribution)), 1e-6)
  return (
    <ul className="flex flex-col gap-2">
      {reasons.map((x) => {
        const w = (Math.abs(x.contribution) / max) * 50
        const up = x.contribution > 0
        const val = x.value === null ? "missing" : typeof x.value === "number" ? +x.value.toFixed(2) : x.value
        return (
          <li key={x.feature} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_1.25rem] items-center gap-3 text-xs"
            title={`${x.label} = ${val}: ${x.direction} the estimate (${x.contribution > 0 ? "+" : ""}${x.contribution.toFixed(2)})`}>
            <span className="truncate"><span className="font-medium">{x.label}</span> <span className="text-muted-foreground">{val}</span></span>
            <span className="relative h-3.5">
              <span className="absolute inset-y-0 left-1/2 w-px bg-border" />
              <span className={up ? "absolute inset-y-0.5 left-1/2 rounded-r-[4px] bg-shap-up" : "absolute inset-y-0.5 right-1/2 rounded-l-[4px] bg-shap-down"}
                style={{ width: `${w}%` }} />
            </span>
            {up ? <TrendingUp className="size-4 text-shap-up" aria-label="raises" /> : <TrendingDown className="size-4 text-shap-down" aria-label="lowers" />}
          </li>
        )
      })}
    </ul>
  )
}

const rankText = (p: number) => {
  const top = Math.max(1, Math.round((1 - p) * 100))
  return top <= 10 ? `Top ${top}% of past alerts` : `Higher than ${pct(p)} of past alerts`
}

export function TriagePanel({ r }: { r: ScoreResult }) {
  const t = r.triage
  if (!t.applied) return null
  return (
    <div>
      <SectionTitle hint={<BandChip band={t.band} short />}>
        <ListFilter className="mr-1 inline size-3.5" /><Term k="triage">Alert triage</Term> · is this alert real?
      </SectionTitle>
      <div className="mb-4 flex items-end gap-4">
        <div>
          <p className="font-heading text-4xl leading-none font-semibold tabular-nums">{pct(t.p_real)}</p>
          <p className="mt-1 text-xs text-muted-foreground">chance it is real</p>
        </div>
        <div className="flex flex-col gap-1 pb-0.5 text-xs">
          <span className="inline-flex items-center gap-1.5"><Trophy className="size-3.5" aria-hidden />{rankText(t.percentile)}</span>
          <span className="inline-flex items-center gap-1.5 text-muted-foreground">
            <Siren className="size-3.5" aria-hidden />Rule <RecordId id={t.rule_id} /> {t.rule_name}
          </span>
        </div>
      </div>
      <p className="mb-2 text-xs text-muted-foreground">
        Top <Term k="factors">factors</Term> · <TrendingUp className="inline size-3.5 text-shap-up" /> raises
        {" "}<TrendingDown className="inline size-3.5 text-shap-down" /> lowers
      </p>
      <FactorBars reasons={t.reasons.slice(0, 3)} />
      {t.reasons.length > 3 && (
        <div className="mt-2"><Details label={`${t.reasons.length - 3} more factors`}><FactorBars reasons={t.reasons.slice(3)} /></Details></div>
      )}
    </div>
  )
}

/** Plain-language face of each network signal (wording matches the pitch). */
const SIGNAL_META: Record<Signal["name"], { title: React.ReactNode; Icon: typeof Users; format: (v: number) => string }> = {
  ring_member_sender: { title: <>Sender is in a <Term k="ring">ring</Term></>, Icon: Users, format: (v) => String(v) },
  fanin_mule_counterparty: { title: <>Money goes to a <Term k="collection">collection account</Term></>, Icon: ArrowDownToLine, format: (v) => String(v) },
  just_under_10k: { title: <>Amount sits just under $10k</>, Icon: Banknote, format: (v) => `$${Math.round(v).toLocaleString()}` },
}

export function SignalsPanel({ r }: { r: ScoreResult }) {
  const s = r.network.signals
  return (
    <div>
      <SectionTitle hint={<BandChip band={r.network.band} short />}>
        <Waypoints className="mr-1 inline size-3.5" /><Term k="network">Network</Term> · what rules can't see
      </SectionTitle>
      {s.length === 0 ? (
        <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
          <ShieldCheck className="size-4 text-risk-low" aria-hidden />No links to a ring or a collection account.
        </p>
      ) : (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {s.map((x) => {
            const m = SIGNAL_META[x.name]
            return (
              <li key={x.name} className="flex flex-col gap-2 border border-border p-3">
                <span className="flex size-8 items-center justify-center bg-risk-high/10 text-risk-high"><m.Icon className="size-4" aria-hidden /></span>
                {x.metric && (
                  <p>
                    <span className="font-heading text-2xl font-semibold tabular-nums">{m.format(x.metric.value)}</span>
                    <span className="ml-1.5 text-xs text-muted-foreground">{x.metric.unit}</span>
                  </p>
                )}
                <p className="text-sm font-medium">{m.title}</p>
                <Details>
                  <p className="mb-2 text-xs text-muted-foreground">{x.detail}</p>
                  {x.evidence_ids.length > 0 && <RecordIds ids={x.evidence_ids} />}
                </Details>
              </li>
            )
          })}
        </ul>
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
