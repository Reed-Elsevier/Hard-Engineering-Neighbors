import { useCallback, useEffect, useRef, useState } from "react"
import { Loader2, Moon, Sun } from "lucide-react"

import { api, type BriefResult, type Example, type Health, type Metrics, type ScoreInput, type ScoreResult } from "@/lib/api"
import { useTheme } from "@/components/theme-provider"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { BriefPanel, DecisionPanel } from "@/components/sabwat/BriefAndDecision"
import { InputPanel } from "@/components/sabwat/InputPanel"
import { ResultsPanel } from "@/components/sabwat/ResultsPanel"
import { RingGraph } from "@/components/sabwat/RingGraph"
import { OwnershipPanel, ScoreSummary, SignalsPanel, TriagePanel } from "@/components/sabwat/ScorePanels"

function StatusLine({ health }: { health: Health | null }) {
  if (!health) return <span>Connecting…</span>
  const items = [
    health.engine_error ? `Engine error: ${health.engine_error}` : health.engine_ready ? "Engine ready" : "Loading data and model…",
    health.llm_enabled ? `Briefs by ${health.llm_model}` : "Briefs: template (no API key)",
    `Decisions → ${health.db_backend.startsWith("dynamodb") ? "DynamoDB" : "SQLite"}`,
  ]
  return <span>{items.join(" · ")}</span>
}

export function App() {
  const { theme, setTheme } = useTheme()
  const [health, setHealth] = useState<Health | null>(null)
  const [examples, setExamples] = useState<Example[]>([])
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [result, setResult] = useState<ScoreResult | null>(null)
  const [scoring, setScoring] = useState(false)
  const [scoreErr, setScoreErr] = useState<string | null>(null)
  const [brief, setBrief] = useState<BriefResult | null>(null)
  const [briefLoading, setBriefLoading] = useState(false)
  const [briefErr, setBriefErr] = useState<string | null>(null)
  const runId = useRef(0)
  const resultRef = useRef<HTMLDivElement>(null)
  const scoreRef = useRef<((input: ScoreInput) => Promise<void>) | null>(null)

  // Poll health until the engine has loaded, then fetch examples and metrics once.
  useEffect(() => {
    let stop = false
    const tick = async () => {
      try {
        const h = await api.health()
        if (stop) return
        setHealth(h)
        if (h.engine_ready) {
          api.examples().then((r) => setExamples(r.examples)).catch(() => {})
          api.metrics().then(setMetrics).catch(() => {})
          // Deep link for demo bookmarks: /?id=TXN00000241 (or an alert ID) scores on load.
          const id = new URLSearchParams(window.location.search).get("id")
          if (id) void scoreRef.current?.({ txn_id: id })
          return
        }
        if (h.engine_error) return
      } catch {
        /* server not up yet */
      }
      if (!stop) setTimeout(tick, 1500)
    }
    tick()
    return () => { stop = true }
  }, [])

  const score = useCallback(async (input: ScoreInput) => {
    const id = ++runId.current
    setScoring(true); setScoreErr(null); setBrief(null); setBriefErr(null)
    try {
      const r = await api.score(input)
      if (id !== runId.current) return
      setResult(r)
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50)
      setBriefLoading(true)
      api.brief(input)
        .then((b) => { if (id === runId.current) setBrief(b) })
        .catch((e: Error) => { if (id === runId.current) setBriefErr(e.message) })
        .finally(() => { if (id === runId.current) setBriefLoading(false) })
    } catch (e) {
      if (id === runId.current) { setScoreErr((e as Error).message); setResult(null) }
    } finally {
      if (id === runId.current) setScoring(false)
    }
  }, [])

  useEffect(() => {
    scoreRef.current = score
  }, [score])

  const sender = result?.ring_graph?.nodes.find((n) => n.type === "individual" && n.accounts.includes(String(result.txn.account_id)))?.id
  const dark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)

  return (
    <div className="mx-auto flex min-h-svh max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-heading text-3xl font-semibold tracking-tight">Sabwat</h1>
          <p className="text-sm text-muted-foreground">
            Rule engines catch individuals. Sabwat catches the <em>sabwatan</em>.
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <StatusLine health={health} />
          <Button variant="ghost" size="icon-sm" aria-label="Toggle dark mode" onClick={() => setTheme(dark ? "light" : "dark")}>
            {dark ? <Sun /> : <Moon />}
          </Button>
        </div>
      </header>

      <Card size="sm">
        <CardContent>
          <InputPanel examples={examples} busy={scoring} onScore={score} />
        </CardContent>
      </Card>

      {scoring && !result && (
        <p className="inline-flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />Scoring…</p>
      )}
      {scoreErr && <p className="text-sm text-destructive" role="alert">{scoreErr}</p>}

      {result && (
        <div ref={resultRef} className={`flex scroll-mt-4 flex-col gap-6 transition-opacity ${scoring ? "opacity-50" : ""}`}>
          <Card size="sm"><CardContent><ScoreSummary r={result} /></CardContent></Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card size="sm"><CardContent><SignalsPanel r={result} /></CardContent></Card>
            <Card size="sm"><CardContent><TriagePanel r={result} /></CardContent></Card>
          </div>

          {result.ring_graph && (
            <Card size="sm">
              <CardContent>
                <RingGraph g={result.ring_graph} sender={sender} receiver={result.txn.counterparty_account_id as string | null} />
              </CardContent>
            </Card>
          )}

          <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
            <Card size="sm"><CardContent><BriefPanel brief={brief} loading={briefLoading} error={briefErr} /></CardContent></Card>
            <div className="flex flex-col gap-6">
              <Card size="sm"><CardContent><DecisionPanel key={String(result.txn.txn_id)} r={result} brief={brief} /></CardContent></Card>
              {result.ownership && <Card size="sm"><CardContent><OwnershipPanel r={result} /></CardContent></Card>}
            </div>
          </div>
          <p className="text-xs text-muted-foreground">Scored in {(result.latency_s * 1000).toFixed(0)} ms.</p>
        </div>
      )}

      {metrics && (
        <>
          <Separator />
          <section>
            <h2 className="mb-4 font-heading text-xl font-semibold">Results on the 2026 hold-out</h2>
            <ResultsPanel m={metrics} />
          </section>
        </>
      )}
    </div>
  )
}

export default App
