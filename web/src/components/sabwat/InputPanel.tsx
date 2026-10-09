import { forwardRef, useRef, useState } from "react"
import {
  BadgeCheck, Braces, ClipboardList, EyeOff, FileSpreadsheet, Hash, Search, Siren, Upload, UserPlus, VolumeX,
} from "lucide-react"

import { api, ApiError, type BatchRow, type Example, type ScoreInput } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Kbd } from "@/components/ui/kbd"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { BatchTable } from "./BatchTable"
import { Details } from "./common"

const CHANNELS = ["ATM", "Branch", "Card", "Mobile wallet", "Online transfer", "Wire"]
const CURRENCIES = ["USD", "PHP", "EUR", "GBP", "JPY"]
const MERCHANTS = ["", "Crypto exchange", "Dining", "Electronics", "Fuel", "Gaming", "Groceries", "Online marketplace", "Travel"]
const SELECT_CLS =
  "h-10 w-full border border-input bg-transparent px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 dark:bg-input/30"

/** Short, scannable face for each demo scenario (full note on hover). */
const SCENARIO: Record<string, { Icon: typeof EyeOff; short: string }> = {
  "Missed by rules": { Icon: EyeOff, short: "Ring transfer, never alerted" },
  "Real alert, ranked first": { Icon: BadgeCheck, short: "Confirmed real, ranked top" },
  "Noisy rule, safe to deprioritise": { Icon: VolumeX, short: "False alarm, ranked low" },
  "New sender, collection account": { Icon: UserPlus, short: "Unknown sender, known receiver" },
}

const JSON_SAMPLE = `{
  "Account ID": "acc0046651",
  "Amount (PHP)": "₱540,000.00",
  "Channel": "mobile wallet",
  "Date": "30/09/2026",
  "Cross border": "yes"
}`
const CSV_SAMPLE = `txn_id,account_id,counterparty_account_id,amount,currency,channel,date
TXN00000241,,,,,,
NEW-0002,acc0021473,ACC0033211,"9,700.00",usd,online transfer,2026-09-01
NEW-0003,ACC9999999,,"€8,000",,card,"Sep 30, 2026"`

type FormState = {
  txn_id: string; account_id: string; counterparty_account_id: string; amount: string; currency: string
  channel: string; merchant_category: string; txn_ts: string; is_cross_border: boolean; rule_id: string; alert_score: string
}
const EMPTY: FormState = { txn_id: "", account_id: "", counterparty_account_id: "", amount: "", currency: "USD",
  channel: "Online transfer", merchant_category: "", txn_ts: "", is_cross_border: false, rule_id: "", alert_score: "" }

type Props = {
  examples: Example[]
  busy: boolean
  onScore: (input: ScoreInput) => void
  serverError?: { msg: string; field?: string } | null
}

export const InputPanel = forwardRef<HTMLInputElement, Props>(function InputPanel({ examples, busy, onScore, serverError }, idRef) {
  const [tab, setTab] = useState("id")
  const [id, setId] = useState("")
  const [form, setForm] = useState<FormState>(EMPTY)
  const [json, setJson] = useState(JSON_SAMPLE)
  const [csv, setCsv] = useState(CSV_SAMPLE)
  const [err, setErr] = useState<{ msg: string; field?: string } | null>(null)
  const [batch, setBatch] = useState<{ rows: BatchRow[]; scored: number; errors: number } | null>(null)
  const [batchBusy, setBatchBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setForm((f) => ({ ...f, [k]: v }))
  const fieldErr = (f: string) =>
    err?.field === f ? err.msg : tab === "form" && serverError?.field === f ? serverError.msg.replace(/^\w+: /, "") : undefined

  const pickExample = (ex: Example) => {
    setErr(null)
    if (ex.txn_id) {
      setTab("id"); setId(ex.txn_id); onScore({ txn_id: ex.txn_id })
    } else if (ex.transaction) {
      const t = ex.transaction as Record<string, string | number | boolean>
      setForm({ ...EMPTY, account_id: String(t.account_id ?? ""), counterparty_account_id: String(t.counterparty_account_id ?? ""),
        amount: String(t.amount ?? ""), currency: String(t.currency ?? "USD"), channel: String(t.channel ?? "Online transfer"),
        is_cross_border: Boolean(t.is_cross_border) })
      setTab("form")
    }
  }

  const submitForm = () => {
    setErr(null)
    if (!form.amount.trim() && !form.txn_id.trim()) return setErr({ msg: "Enter an amount", field: "amount" })
    const t: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(form)) if (v !== "" && v !== null) t[k] = v
    onScore({ transaction: t })
  }

  const submitJson = () => {
    setErr(null)
    let parsed: unknown
    try { parsed = JSON.parse(json) } catch (e) { return setErr({ msg: `That isn't valid JSON: ${(e as Error).message}` }) }
    if (Array.isArray(parsed)) return void runBatch(() => api.batch({ rows: parsed as Record<string, unknown>[] }))
    if (parsed && typeof parsed === "object") return onScore({ transaction: parsed as Record<string, unknown> })
    setErr({ msg: "Expected an object (one transaction) or an array (many)" })
  }

  const runBatch = async (fn: () => Promise<{ rows: BatchRow[]; scored: number; errors: number }>) => {
    setErr(null); setBatchBusy(true)
    try { setBatch(await fn()) } catch (e) { setErr({ msg: (e as Error).message, field: (e as ApiError).field }) } finally { setBatchBusy(false) }
  }
  const upload = (f: File | undefined) => {
    if (f) void runBatch(() => api.batchUpload(f))
  }

  return (
    <div className="flex flex-col gap-4">
      {examples.length > 0 && (
        <div>
          <p className="mb-2 text-xs text-muted-foreground">Try a scenario</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {examples.map((ex) => {
              const s = SCENARIO[ex.title] ?? { Icon: Siren, short: ex.note }
              return (
                <button key={ex.title} onClick={() => pickExample(ex)} disabled={busy} title={ex.note}
                  className="group flex items-center gap-3 border border-border p-2.5 text-left transition-colors hover:border-foreground/40 hover:bg-muted disabled:opacity-50">
                  <span className="flex size-8 shrink-0 items-center justify-center bg-muted group-hover:bg-background"><s.Icon className="size-4" aria-hidden /></span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{ex.title}</span>
                    <span className="block truncate text-xs text-muted-foreground">{s.short}</span>
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      )}

      <Tabs value={tab} onValueChange={(v) => { setTab(String(v)); setErr(null) }}>
        <TabsList className="max-w-full overflow-x-auto">
          <TabsTrigger value="id"><Hash />ID</TabsTrigger>
          <TabsTrigger value="form"><ClipboardList />Form</TabsTrigger>
          <TabsTrigger value="json"><Braces />JSON</TabsTrigger>
          <TabsTrigger value="csv"><FileSpreadsheet />CSV</TabsTrigger>
        </TabsList>

        <TabsContent value="id" className="pt-3">
          <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); setErr(null); if (id.trim()) onScore({ txn_id: id.trim() }) }}>
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input ref={idRef} aria-label="Transaction or alert ID" placeholder="Transaction or alert ID, e.g. TXN00000241"
                value={id} onChange={(e) => setId(e.target.value)} className="h-12 pr-24 pl-9 font-mono text-base" />
              <span className="pointer-events-none absolute top-1/2 right-3 hidden -translate-y-1/2 items-center gap-1 text-xs text-muted-foreground sm:flex">
                press <Kbd>/</Kbd> or <Kbd>Enter</Kbd>
              </span>
            </div>
            <Button type="submit" size="lg" className="h-12" disabled={busy || !id.trim()}>{busy ? <Spinner /> : <Search />}Score</Button>
          </form>
        </TabsContent>

        <TabsContent value="form" className="pt-3">
          <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); submitForm() }} noValidate>
            <fieldset className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <legend className="mb-2 text-xs font-semibold tracking-wider text-muted-foreground uppercase">Who</legend>
              <F label="Sender account" hint="Leave blank if unknown"><Input value={form.account_id} onChange={(e) => set("account_id", e.target.value)} placeholder="ACC…" className="font-mono" /></F>
              <F label="Receiving account" hint="Optional"><Input value={form.counterparty_account_id} onChange={(e) => set("counterparty_account_id", e.target.value)} placeholder="ACC…" className="font-mono" /></F>
            </fieldset>
            <fieldset className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <legend className="mb-2 text-xs font-semibold tracking-wider text-muted-foreground uppercase">What</legend>
              <F label="Amount" error={fieldErr("amount")}>
                <div className="flex">
                  <Input value={form.amount} onChange={(e) => set("amount", e.target.value)} placeholder="9,500.00" inputMode="decimal" aria-invalid={!!fieldErr("amount")} />
                  <select aria-label="Currency" className={`${SELECT_CLS} w-24 border-l-0`} value={form.currency} onChange={(e) => set("currency", e.target.value)}>
                    {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
                  </select>
                </div>
              </F>
              <F label="Channel"><select className={SELECT_CLS} value={form.channel} onChange={(e) => set("channel", e.target.value)}>{CHANNELS.map((c) => <option key={c}>{c}</option>)}</select></F>
              <F label="Date and time" hint="Defaults to now" error={fieldErr("txn_ts")}><Input type="datetime-local" value={form.txn_ts} onChange={(e) => set("txn_ts", e.target.value)} /></F>
              <div className="flex items-center gap-2 sm:pt-6">
                <Checkbox id="xb" checked={form.is_cross_border} onCheckedChange={(v) => set("is_cross_border", Boolean(v))} />
                <Label htmlFor="xb">Cross-border</Label>
              </div>
            </fieldset>
            <Details label="Alert and other details (optional)">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <F label="Alert rule" error={fieldErr("rule_id")}><Input value={form.rule_id} onChange={(e) => set("rule_id", e.target.value)} placeholder="R017" className="font-mono" /></F>
                <F label="Alert score (0 to 1)" error={fieldErr("alert_score")}><Input value={form.alert_score} onChange={(e) => set("alert_score", e.target.value)} placeholder="0.72" inputMode="decimal" /></F>
                <F label="Merchant category"><select className={SELECT_CLS} value={form.merchant_category} onChange={(e) => set("merchant_category", e.target.value)}>{MERCHANTS.map((c) => <option key={c} value={c}>{c || "None"}</option>)}</select></F>
                <F label="Transaction ID" hint="To log a decision"><Input value={form.txn_id} onChange={(e) => set("txn_id", e.target.value)} placeholder="NEW-0001" className="font-mono" /></F>
              </div>
            </Details>
            <div><Button type="submit" disabled={busy}>{busy ? <Spinner /> : <Search />}Score transaction</Button></div>
          </form>
        </TabsContent>

        <TabsContent value="json" className="pt-3">
          <p className="mb-2 text-xs text-muted-foreground">Paste any field names. Sabwat maps aliases, currencies and date formats. An array scores many.</p>
          <Textarea aria-label="Transaction JSON" value={json} onChange={(e) => setJson(e.target.value)} rows={7} className="font-mono text-xs" />
          <Button className="mt-2" onClick={submitJson} disabled={busy || batchBusy}>{busy || batchBusy ? <Spinner /> : <Braces />}Score JSON</Button>
        </TabsContent>

        <TabsContent value="csv" className="pt-3">
          <button type="button" onClick={() => fileRef.current?.click()} disabled={batchBusy}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); upload(e.dataTransfer.files?.[0]) }}
            className={`flex w-full flex-col items-center gap-2 border-2 border-dashed px-4 py-8 text-center transition-colors ${dragging ? "border-foreground bg-muted" : "border-border hover:bg-muted"}`}>
            {batchBusy ? <Spinner className="size-6" /> : <Upload className="size-6 text-muted-foreground" aria-hidden />}
            <span className="text-sm font-medium">Drop a CSV file here, or click to choose</span>
            <span className="text-xs text-muted-foreground">Many rows are scored and ranked. Messy columns are fine.</span>
          </button>
          <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden"
            onChange={(e) => { upload(e.target.files?.[0]); e.target.value = "" }} />
          <div className="mt-3">
            <Details label="Or paste CSV rows">
              <Textarea aria-label="CSV rows" value={csv} onChange={(e) => setCsv(e.target.value)} rows={5} className="font-mono text-xs" />
              <Button className="mt-2" size="sm" onClick={() => runBatch(() => api.batch({ csv }))} disabled={batchBusy}><FileSpreadsheet />Score pasted rows</Button>
            </Details>
          </div>
        </TabsContent>
      </Tabs>

      {err && !err.field && <p className="text-sm text-destructive" role="alert">{err.msg}</p>}
      {err?.field && tab !== "form" && <p className="text-sm text-destructive" role="alert">{err.msg}</p>}
      {serverError?.field && !(tab === "form" && ["amount", "txn_ts", "rule_id", "alert_score"].includes(serverError.field)) && (
        <p className="text-sm text-destructive" role="alert">{serverError.msg}</p>
      )}
      {batch && (tab === "csv" || tab === "json") && (
        <BatchTable data={batch} onOpen={(row) => onScore({ transaction: row.input })} />
      )}
    </div>
  )
})

function F({ label, hint, error, children }: { label: string; hint?: string; error?: string; children: React.ReactNode }) {
  return (
    <div className={`flex flex-col gap-1.5 ${error ? "[&_input]:border-destructive" : ""}`}>
      <Label className="text-xs">{label}{hint && <span className="font-normal text-muted-foreground"> · {hint}</span>}</Label>
      {children}
      {error && <p className="text-xs text-destructive" role="alert">{error}</p>}
    </div>
  )
}
