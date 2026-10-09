import { AlertTriangle, Bot, CircleHelp, FileText, Gauge, Info, OctagonAlert, ShieldCheck, Sparkles } from "lucide-react"

import type { BriefResult } from "@/lib/api"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Details, RecordIds, SectionTitle } from "./common"

const SEVERITY = {
  high: { Icon: OctagonAlert, cls: "text-risk-high", label: "High" },
  medium: { Icon: AlertTriangle, cls: "text-risk-med", label: "Medium" },
  low: { Icon: Info, cls: "text-muted-foreground", label: "Low" },
}

/** First sentence (or ~90 chars) as the accordion headline; the full text sits inside. */
function headline(text: string) {
  const first = text.split(/(?<=\.)\s/)[0]
  return first.length > 110 ? first.slice(0, 100).trimEnd() + "…" : first
}

export function BriefPanel({ brief, loading, error }: { brief: BriefResult | null; loading: boolean; error: string | null }) {
  if (loading)
    return (
      <div>
        <SectionTitle>Case brief</SectionTitle>
        <p className="mb-3 inline-flex items-center gap-2 text-sm text-muted-foreground"><Spinner />The AI writer is reading the evidence…</p>
        <div className="flex flex-col gap-2"><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-5/6" /><Skeleton className="h-4 w-2/3" /></div>
      </div>
    )
  if (error) return <Alert variant="destructive"><AlertTriangle /><AlertTitle>Brief unavailable</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>
  if (!brief) return null
  const b = brief.brief
  const ai = brief.source !== "template"

  return (
    <div className="flex flex-col gap-4">
      <SectionTitle hint={`${brief.cached ? "cached · " : ""}${brief.latency_s.toFixed(1)} s`}>Case brief</SectionTitle>

      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center bg-muted">{ai ? <Bot className="size-5" /> : <FileText className="size-5" />}</span>
        <div className="min-w-0">
          <p className={`mb-1 text-xs ${ai ? "text-muted-foreground" : "font-semibold text-destructive"}`}>{brief.label}</p>
          <p className="text-base leading-relaxed">{b.risk_summary}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <span className="inline-flex items-center gap-1.5 border border-border px-2 py-1">
          <Sparkles className="size-3.5" />Suggests <strong className="capitalize">{b.recommended_action}</strong>
        </span>
        <span className="inline-flex items-center gap-1.5 border border-border px-2 py-1">
          <Gauge className="size-3.5" />Confidence <strong className="capitalize">{b.confidence}</strong>
        </span>
        {(brief.validation.findings_dropped ?? 0) === 0 ? (
          <span className="inline-flex items-center gap-1.5 border border-border px-2 py-1" title="Every finding cites records that exist in the evidence">
            <ShieldCheck className="size-3.5 text-risk-low" />All findings cite real records
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 border border-border px-2 py-1">
            <ShieldCheck className="size-3.5" />{brief.validation.findings_dropped} unsupported finding(s) removed
          </span>
        )}
      </div>

      <div>
        <p className="mb-1 text-xs text-muted-foreground">Findings · open one to see its records</p>
        <Accordion className="border-y border-border">
          {b.key_findings.map((f, i) => {
            const sev = SEVERITY[f.severity]
            return (
              <AccordionItem key={i} value={String(i)}>
                <AccordionTrigger className="gap-3 text-left text-sm">
                  <span className="flex min-w-0 items-start gap-2">
                    <sev.Icon className={`mt-0.5 size-4 shrink-0 ${sev.cls}`} aria-label={`${sev.label} severity`} />
                    <span>{headline(f.finding)}</span>
                  </span>
                </AccordionTrigger>
                <AccordionContent className="pl-6">
                  <p className="mb-2 text-sm text-muted-foreground">{f.finding}</p>
                  <RecordIds ids={f.evidence_ids} max={4} />
                </AccordionContent>
              </AccordionItem>
            )
          })}
        </Accordion>
      </div>

      {b.open_questions.length > 0 && (
        <Details label={`${b.open_questions.length} open question(s) for the analyst`}>
          <ul className="flex flex-col gap-1.5 text-sm">
            {b.open_questions.map((q) => (
              <li key={q} className="flex gap-2"><CircleHelp className="mt-0.5 size-4 shrink-0 text-muted-foreground" />{q}</li>
            ))}
          </ul>
        </Details>
      )}
      {brief.validation.warnings?.map((w) => <p key={w} className="text-xs text-muted-foreground">{w}</p>)}
    </div>
  )
}
