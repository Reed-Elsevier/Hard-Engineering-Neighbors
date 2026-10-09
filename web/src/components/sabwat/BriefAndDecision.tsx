import { useState } from "react"
import { Bot, FileText, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { api, type BriefResult, type ScoreResult } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { RecordIds, SectionTitle } from "./common"

const SEV_CLS = { high: "bg-risk-high text-white", medium: "bg-risk-med text-black", low: "bg-muted text-foreground" }

export function BriefPanel({ brief, loading, error }: { brief: BriefResult | null; loading: boolean; error: string | null }) {
  if (loading)
    return (
      <div>
        <SectionTitle>Case brief</SectionTitle>
        <p className="mb-3 inline-flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> The AI writer is drafting the brief from the evidence…
        </p>
        <div className="flex flex-col gap-2">
          <Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-5/6" /><Skeleton className="h-4 w-2/3" />
        </div>
      </div>
    )
  if (error) return (<div><SectionTitle>Case brief</SectionTitle><p className="text-sm text-destructive">{error}</p></div>)
  if (!brief) return null
  const b = brief.brief
  const ai = brief.source !== "template"
  return (
    <div>
      <SectionTitle hint={`${brief.cached ? "cached · " : ""}${brief.latency_s.toFixed(1)} s`}>Case brief</SectionTitle>
      <p className={`mb-3 inline-flex items-center gap-1.5 text-xs font-semibold tracking-wider uppercase ${ai ? "" : "text-destructive"}`}>
        {ai ? <Bot className="size-4" /> : <FileText className="size-4" />}
        {brief.label}
      </p>
      <p className="mb-4 text-base leading-relaxed">{b.risk_summary}</p>

      <ul className="mb-4 flex flex-col gap-3">
        {b.key_findings.map((f, i) => (
          <li key={i} className="grid grid-cols-[4.5rem_1fr] gap-3">
            <span className={`h-fit px-1.5 py-0.5 text-center text-[0.65rem] font-semibold tracking-wider uppercase ${SEV_CLS[f.severity]}`}>{f.severity}</span>
            <div>
              <p className="text-sm">{f.finding}</p>
              <div className="mt-1"><RecordIds ids={f.evidence_ids} max={5} /></div>
            </div>
          </li>
        ))}
      </ul>

      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-[0.65rem] tracking-widest text-muted-foreground uppercase">Recommends (analyst decides)</dt>
          <dd className="font-semibold capitalize">{b.recommended_action}</dd>
        </div>
        <div>
          <dt className="text-[0.65rem] tracking-widest text-muted-foreground uppercase">Confidence</dt>
          <dd className="capitalize">{b.confidence}</dd>
        </div>
      </dl>
      {b.open_questions.length > 0 && (
        <div className="mt-3 text-sm">
          <p className="text-[0.65rem] tracking-widest text-muted-foreground uppercase">Open questions</p>
          <ul className="list-disc pl-4">{b.open_questions.map((q) => <li key={q}>{q}</li>)}</ul>
        </div>
      )}
      {(brief.validation.findings_dropped ?? 0) > 0 && (
        <p className="mt-3 text-xs text-muted-foreground">
          {brief.validation.findings_dropped} finding(s) removed because they cited records not in the evidence.
        </p>
      )}
      {brief.validation.warnings?.map((w) => <p key={w} className="mt-1 text-xs text-muted-foreground">{w}</p>)}
    </div>
  )
}

type Decision = "escalate" | "review" | "dismiss"

export function DecisionPanel({ r, brief }: { r: ScoreResult; brief: BriefResult | null }) {
  const [note, setNote] = useState("")
  const [saving, setSaving] = useState<Decision | null>(null)
  const [saved, setSaved] = useState<{ decision: Decision; where: string } | null>(null)
  const txnId = r.txn.txn_id ? String(r.txn.txn_id) : null

  const decide = async (decision: Decision) => {
    if (!txnId) return
    setSaving(decision)
    try {
      const res = await api.decide({ txn_id: txnId, decision, note, score: r.score, band: r.band,
        layers_fired: r.layers_fired, brief_source: brief?.source ?? null })
      setSaved({ decision, where: res.stored_in })
      toast.success(`Decision saved: ${decision}`, { description: `Logged to ${res.stored_in === "dynamodb" ? "DynamoDB" : "local SQLite"}` })
    } catch (e) {
      toast.error("Could not save the decision", { description: (e as Error).message })
    } finally {
      setSaving(null)
    }
  }

  return (
    <div>
      <SectionTitle>Analyst decision</SectionTitle>
      {!txnId && <p className="mb-2 text-sm text-muted-foreground">Add a transaction ID to the input to log a decision.</p>}
      <Textarea placeholder="Note (optional), e.g. Ring activity, escalate." value={note} onChange={(e) => setNote(e.target.value)} className="mb-3" maxLength={2000} />
      <div className="flex flex-wrap gap-2">
        {(["escalate", "review", "dismiss"] as Decision[]).map((d) => (
          <Button key={d} variant={d === "escalate" ? "default" : "outline"} disabled={!txnId || saving !== null} onClick={() => decide(d)}>
            {saving === d && <Loader2 className="animate-spin" />}
            {d}
          </Button>
        ))}
      </div>
      {saved && (
        <p className="mt-3 text-sm" role="status">
          Saved: <strong className="capitalize">{saved.decision}</strong>
          {note && <> · “{note}”</>} <span className="text-muted-foreground">({saved.where === "dynamodb" ? "DynamoDB" : "local SQLite"})</span>
        </p>
      )}
    </div>
  )
}
