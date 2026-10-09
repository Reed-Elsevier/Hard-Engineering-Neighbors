import { useCallback, useEffect, useRef, useState } from "react"
import { BarChart3, BellOff, Bot, Database, FileText, IdCard, Moon, ScanSearch, Search, Sun, Waypoints, Workflow } from "lucide-react"

import { api, ApiError, type BriefResult, type Example, type Health, type Metrics, type ScoreInput, type ScoreResult } from "@/lib/api"
import { useTheme } from "@/components/theme-provider"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { BriefPanel } from "@/components/sabwat/BriefAndDecision"
import { InputPanel } from "@/components/sabwat/InputPanel"
import { ResultsPanel } from "@/components/sabwat/ResultsPanel"
import { RingGraph } from "@/components/sabwat/RingGraph"
import { NotesAlert, OwnershipPanel, RecordPanel, SignalsPanel, TriagePanel } from "@/components/sabwat/ScorePanels"
import { VerdictCard } from "@/components/sabwat/VerdictCard"

function StatusLine({ health }: { health: Health | null }) {
  if (!health) return <span className="inline-flex items-center gap-1.5"><Spinner className="size-3" />Connecting</span>
  const ready = health.engine_ready && !health.engine_error
  const dot = (ok: boolean) => <span className={`size-1.5 rounded-full ${ok ? "bg-risk-low" : "bg-risk-med"}`} aria-hidden />
  return (
    <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className="inline-flex items-center gap-1.5" title={health.engine_error ?? undefined}>
        {dot(ready)}<Workflow className="size-3.5" />{ready ? "Engine ready" : health.engine_error ? "Engine error" : health.building_model ? "Building model (first start, ~1 min)…" : "Loading model…"}
      </span>
      <span className="inline-flex items-center gap-1.5" title={health.llm_model ?? "No API key: template briefs"}>
        {dot(health.llm_enabled)}<Bot className="size-3.5" />{health.llm_enabled ? "AI writer on" : "AI writer off"}
      </span>
      <span className="inline-flex items-center gap-1.5">
        {dot(true)}<Database className="size-3.5" />{health.db_backend.startsWith("dynamodb") ? "DynamoDB" : "Local log"}
      </span>
    </span>
  )
}

export function App() {
  const { theme, setTheme } = useTheme()
  const [health, setHealth] = useState<Health | null>(null)
  const [examples, setExamples] = useState<Example[]>([])
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [result, setResult] = useState<ScoreResult | null>(null)
  const [scoring, setScoring] = useState(false)
  const [scoreErr, setScoreErr] = useState<{ msg: string; field?: string } | null>(null)
  const [brief, setBrief] = useState<BriefResult | null>(null)
  const [briefLoading, setBriefLoading] = useState(false)
  const [briefErr, setBriefErr] = useState<string | null>(null)
  const [view, setView] = useState("investigate")
  const [detailTab, setDetailTab] = useState("why")
  const runId = useRef(0)
  const resultRef = useRef<HTMLDivElement>(null)
  const scoreRef = useRef<((input: ScoreInput) => Promise<void>) | null>(null)
  const idRef = useRef<HTMLInputElement>(null)
  const initialTab = useRef(new URLSearchParams(window.location.search).get("tab"))

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)
      if (e.key === "/" && !typing) { e.preventDefault(); setView("investigate"); idRef.current?.focus() }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

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
    setScoring(true); setScoreErr(null); setBrief(null); setBriefErr(null); setView("investigate")
    try {
      const r = await api.score(input)
      if (id !== runId.current) return
      setResult(r)
      setDetailTab(initialTab.current ?? "why")
      initialTab.current = null
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50)
      setBriefLoading(true)
      api.brief(input)
        .then((b) => { if (id === runId.current) setBrief(b) })
        .catch((e: Error) => { if (id === runId.current) setBriefErr(e.message) })
        .finally(() => { if (id === runId.current) setBriefLoading(false) })
    } catch (e) {
      if (id === runId.current) { setScoreErr({ msg: (e as Error).message, field: (e as ApiError).field }); setResult(null) }
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
    <div className="mx-auto flex min-h-svh max-w-6xl flex-col gap-5 px-4 pt-5 pb-24 sm:px-6 md:pb-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex size-9 items-center justify-center bg-primary text-primary-foreground" aria-hidden><Waypoints className="size-5" /></span>
          <div>
            <h1 className="font-heading text-2xl leading-none font-semibold tracking-tight">Sabwat</h1>
            <p className="text-xs text-muted-foreground">Rule engines catch individuals. Sabwat catches the <em>sabwatan</em>.</p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <StatusLine health={health} />
          <Button variant="ghost" size="icon-sm" aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} onClick={() => setTheme(dark ? "light" : "dark")}>
            {dark ? <Sun /> : <Moon />}
          </Button>
        </div>
      </header>

      <Tabs value={view} onValueChange={(v) => setView(String(v))}>
        <TabsList>
          <TabsTrigger value="investigate"><Search />Investigate</TabsTrigger>
          <TabsTrigger value="results"><BarChart3 />Results</TabsTrigger>
        </TabsList>

        <TabsContent value="investigate" className="flex flex-col gap-5 pt-3">
          <Card size="sm"><CardContent><InputPanel ref={idRef} examples={examples} busy={scoring} onScore={score} serverError={scoreErr} /></CardContent></Card>

          {scoreErr && !scoreErr.field && <p className="text-sm text-destructive" role="alert">{scoreErr.msg}</p>}

          {!result && !scoring && (
            <Empty className="border border-dashed border-border py-12">
              <EmptyHeader>
                <EmptyMedia variant="icon"><ScanSearch /></EmptyMedia>
                <EmptyTitle>Score a transaction</EmptyTitle>
                <EmptyDescription>
                  Enter a transaction or alert ID, or pick a scenario above. Sabwat shows a risk score, why, and who it is connected to.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}

          {scoring && !result && (
            <Card size="sm"><CardContent className="flex items-center gap-6">
              <Skeleton className="size-24 rounded-full" />
              <div className="flex flex-1 flex-col gap-2"><Skeleton className="h-5 w-40" /><Skeleton className="h-4 w-64" /><Skeleton className="h-4 w-52" /></div>
            </CardContent></Card>
          )}

          {result && (
            <div ref={resultRef} className={`flex scroll-mt-2 flex-col gap-4 transition-opacity ${scoring ? "opacity-50" : ""}`}>
              <Card size="sm" className="z-20 md:sticky md:top-2">
                <CardContent><VerdictCard key={String(result.txn.txn_id) + result.score} r={result} brief={brief} briefLoading={briefLoading} /></CardContent>
              </Card>
              <NotesAlert r={result} />

              <Tabs value={detailTab} onValueChange={(v) => setDetailTab(String(v))}>
                <TabsList variant="line" className="w-full justify-start overflow-x-auto">
                  <TabsTrigger value="why"><ScanSearch />Why</TabsTrigger>
                  <TabsTrigger value="ring" disabled={!result.ring_graph}><Waypoints />Ring</TabsTrigger>
                  <TabsTrigger value="brief">{briefLoading ? <Spinner /> : <FileText />}Brief</TabsTrigger>
                  <TabsTrigger value="record"><IdCard />Record</TabsTrigger>
                </TabsList>
                <TabsContent value="why" className="pt-3">
                  <div className={`grid grid-cols-1 gap-4 ${result.triage.applied ? "lg:grid-cols-[3fr_2fr]" : ""}`}>
                    <Card size="sm"><CardContent><SignalsPanel r={result} /></CardContent></Card>
                    {result.triage.applied ? (
                      <Card size="sm"><CardContent><TriagePanel r={result} /></CardContent></Card>
                    ) : (
                      <p className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                        <BellOff className="size-3.5" aria-hidden />No rule alert on this transaction, so alert triage does not apply.
                      </p>
                    )}
                  </div>
                </TabsContent>
                <TabsContent value="ring" className="pt-3">
                  {result.ring_graph && (
                    <Card size="sm"><CardContent>
                      <RingGraph g={result.ring_graph} sender={sender} receiver={result.txn.counterparty_account_id as string | null} />
                    </CardContent></Card>
                  )}
                </TabsContent>
                <TabsContent value="brief" className="pt-3">
                  <Card size="sm"><CardContent><BriefPanel brief={brief} loading={briefLoading} error={briefErr} /></CardContent></Card>
                </TabsContent>
                <TabsContent value="record" className="pt-3">
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <Card size="sm"><CardContent><RecordPanel r={result} /></CardContent></Card>
                    {result.ownership && <Card size="sm"><CardContent><OwnershipPanel r={result} /></CardContent></Card>}
                  </div>
                </TabsContent>
              </Tabs>
            </div>
          )}
        </TabsContent>

        <TabsContent value="results" className="pt-3">
          {metrics ? <ResultsPanel m={metrics} /> : <p className="text-sm text-muted-foreground">Results load once the engine is ready.</p>}
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default App
