import { useState } from "react"
import { CircleCheck, Eye, Flag, MessageSquarePlus, Sparkles, Waypoints, ListFilter } from "lucide-react"
import { toast } from "sonner"

import { api, type Band, type BriefResult, type ScoreResult } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { BandChip, usd } from "./common"

type Decision = "escalate" | "review" | "dismiss"
const DECISIONS: { value: Decision; label: string; Icon: typeof Flag }[] = [
  { value: "escalate", label: "Escalate", Icon: Flag },
  { value: "review", label: "Review", Icon: Eye },
  { value: "dismiss", label: "Dismiss", Icon: CircleCheck },
]
const RING_COLOR: Record<Band, string> = { High: "var(--risk-high)", Med: "var(--risk-med)", Low: "var(--risk-low)" }

/** Circular 0-100 gauge; the number is the focal point of the whole page. */
function ScoreRing({ score, band }: { score: number; band: Band }) {
  const r = 34
  const c = 2 * Math.PI * r
  return (
    <div className="relative size-24 shrink-0" role="img" aria-label={`Risk score ${Math.round(score)} of 100, ${band}`}>
      <svg viewBox="0 0 80 80" className="size-full -rotate-90">
        <circle cx="40" cy="40" r={r} fill="none" stroke="var(--viz-neutral)" strokeWidth="7" />
        <circle cx="40" cy="40" r={r} fill="none" stroke={RING_COLOR[band]} strokeWidth="7"
          strokeDasharray={`${(score / 100) * c} ${c}`} strokeLinecap="butt" />
      </svg>
      <span className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-heading text-3xl leading-none font-semibold tabular-nums">{Math.round(score)}</span>
        <span className="text-[0.6rem] text-muted-foreground">/ 100</span>
      </span>
    </div>
  )
}

export const LAYER_META: Record<string, { label: string; Icon: typeof Waypoints; hint: string }> = {
  Network: { label: "Network", Icon: Waypoints, hint: "Found through links to other people and accounts" },
  "Triage model": { label: "Alert triage", Icon: ListFilter, hint: "The alert looks like past real cases" },
}

function useDecision(r: ScoreResult, brief: BriefResult | null) {
  const [saving, setSaving] = useState<Decision | null>(null)
  const [saved, setSaved] = useState<Decision | null>(null)
  const txnId = r.txn.txn_id ? String(r.txn.txn_id) : null
  const decide = async (decision: Decision, note: string) => {
    if (!txnId) return
    setSaving(decision)
    try {
      const res = await api.decide({ txn_id: txnId, decision, note, score: r.score, band: r.band,
        layers_fired: r.layers_fired, brief_source: brief?.source ?? null })
      setSaved(decision)
      toast.success(`Saved: ${decision}`, { description: res.stored_in === "dynamodb" ? "Logged to the decision log (DynamoDB)" : "Logged locally (SQLite)" })
    } catch (e) {
      toast.error("Could not save the decision", { description: (e as Error).message })
    } finally {
      setSaving(null)
    }
  }
  return { txnId, saving, saved, decide }
}

function DecisionButtons({ d, note, compact }: { d: ReturnType<typeof useDecision>; note: string; compact?: boolean }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {DECISIONS.map(({ value, label, Icon }) => (
        <Button key={value} size={compact ? "sm" : "default"} variant={d.saved === value || (!d.saved && value === "escalate") ? "default" : "outline"}
          disabled={!d.txnId || d.saving !== null} onClick={() => d.decide(value, note)} aria-pressed={d.saved === value}>
          {d.saving === value ? <Spinner /> : <Icon />}
          {label}
        </Button>
      ))}
    </div>
  )
}

function AiSuggestion({ brief, loading }: { brief: BriefResult | null; loading: boolean }) {
  if (loading)
    return <p className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"><Spinner className="size-3.5" />AI writer is drafting…</p>
  if (!brief) return null
  const action = brief.brief.recommended_action
  return (
    <p className="inline-flex items-center gap-1.5 text-xs">
      <Sparkles className="size-3.5" aria-hidden />
      <span className="text-muted-foreground">{brief.source === "template" ? "Rule-based suggestion:" : "AI suggests:"}</span>
      <strong className="capitalize">{action}</strong>
      <span className="text-muted-foreground">· you decide</span>
    </p>
  )
}

export function VerdictCard({ r, brief, briefLoading }: { r: ScoreResult; brief: BriefResult | null; briefLoading: boolean }) {
  const d = useDecision(r, brief)
  const [note, setNote] = useState("")
  const headline = r.band === "High" ? "Needs attention" : r.band === "Med" ? "Worth a look" : "Looks routine"

  return (
    <>
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:gap-6">
        <div className="flex items-center gap-4">
          <ScoreRing score={r.score} band={r.band} />
          <div className="flex flex-col gap-1.5">
            <BandChip band={r.band} />
            <p className="font-heading text-xl font-semibold">{headline}</p>
            <p className="text-xs text-muted-foreground">
              <span className="font-mono">{r.txn.txn_id ?? "New transaction"}</span> · {usd(r.txn.amount_usd as number)}
            </p>
          </div>
        </div>

        <div className="flex flex-1 flex-col gap-2 md:border-l md:border-border md:pl-6">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-muted-foreground">Caught by</span>
            {r.layers_fired.length === 0 && <span className="text-muted-foreground">nothing: no reason for concern</span>}
            {r.layers_fired.map((l) => {
              const m = LAYER_META[l]
              return (
                <span key={l} title={m?.hint} className="inline-flex items-center gap-1 border border-foreground px-2 py-0.5 font-semibold">
                  {m && <m.Icon className="size-3.5" aria-hidden />}{m?.label ?? l}
                </span>
              )
            })}
          </div>
          <AiSuggestion brief={brief} loading={briefLoading} />
        </div>

        <div className="hidden w-full flex-col gap-2 md:flex md:w-auto md:min-w-80">
          <DecisionButtons d={d} note={note} />
          <Collapsible>
            <CollapsibleTrigger className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
              <MessageSquarePlus className="size-3.5" />{note ? "Edit note" : "Add a note"}
            </CollapsibleTrigger>
            <CollapsibleContent>
              <Textarea className="mt-2" rows={2} maxLength={2000} placeholder="e.g. Ring activity, escalate." value={note} onChange={(e) => setNote(e.target.value)} />
            </CollapsibleContent>
          </Collapsible>
          {!d.txnId && <p className="text-xs text-muted-foreground">Add a transaction ID to log a decision.</p>}
        </div>
      </div>

      {/* Mobile: the primary action docks to the bottom, within thumb reach. */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-background/95 p-3 backdrop-blur md:hidden">
        <DecisionButtons d={d} note={note} compact />
      </div>
    </>
  )
}
