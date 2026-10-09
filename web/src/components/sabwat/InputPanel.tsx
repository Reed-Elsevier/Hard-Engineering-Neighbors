import { useRef, useState } from "react"
import { Loader2, Upload } from "lucide-react"

import { api, ApiError, type BatchRow, type Example, type ScoreInput } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { BatchTable } from "./BatchTable"

const CHANNELS = ["ATM", "Branch", "Card", "Mobile wallet", "Online transfer", "Wire"]
const CURRENCIES = ["USD", "PHP", "EUR", "GBP", "JPY"]
const MERCHANTS = ["", "Crypto exchange", "Dining", "Electronics", "Fuel", "Gaming", "Groceries", "Online marketplace", "Travel"]
const SELECT_CLS =
  "h-10 w-full border border-input bg-transparent px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 dark:bg-input/30"

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

export function InputPanel({ examples, busy, onScore }: { examples: Example[]; busy: boolean; onScore: (input: ScoreInput) => void }) {
  const [tab, setTab] = useState("id")
  const [id, setId] = useState("")
  const [form, setForm] = useState<FormState>(EMPTY)
  const [json, setJson] = useState(JSON_SAMPLE)
  const [csv, setCsv] = useState(CSV_SAMPLE)
  const [err, setErr] = useState<{ msg: string; field?: string } | null>(null)
  const [batch, setBatch] = useState<{ rows: BatchRow[]; scored: number; errors: number } | null>(null)
  const [batchBusy, setBatchBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setForm((f) => ({ ...f, [k]: v }))

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
    const t: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(form)) if (v !== "" && v !== null) t[k] = v
    if (!form.amount && !form.txn_id) return setErr({ msg: "amount: required for a new transaction", field: "amount" })
    onScore({ transaction: t })
  }

  const submitJson = () => {
    setErr(null)
    let parsed: unknown
    try { parsed = JSON.parse(json) } catch (e) { return setErr({ msg: `JSON: ${(e as Error).message}` }) }
    if (Array.isArray(parsed)) return runBatch(() => api.batch({ rows: parsed as Record<string, unknown>[] }))
    if (parsed && typeof parsed === "object") return onScore({ transaction: parsed as Record<string, unknown> })
    setErr({ msg: "JSON: expected an object (one transaction) or an array (many)" })
  }

  const runBatch = async (fn: () => Promise<{ rows: BatchRow[]; scored: number; errors: number }>) => {
    setErr(null); setBatchBusy(true)
    try { setBatch(await fn()) } catch (e) { setErr({ msg: (e as Error).message, field: (e as ApiError).field }) } finally { setBatchBusy(false) }
  }

  return (
    <div className="flex flex-col gap-4">
      {examples.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {examples.map((ex) => (
            <button key={ex.title} onClick={() => pickExample(ex)} disabled={busy}
              className="border border-border p-3 text-left transition-colors hover:border-foreground/50 hover:bg-muted disabled:opacity-50">
              <span className="block text-xs font-semibold tracking-wider uppercase">{ex.title}</span>
              <span className="mt-1 block text-xs text-muted-foreground">{ex.note}</span>
              {ex.txn_id && <span className="mt-1 block font-mono text-[0.7rem]">{ex.txn_id}</span>}
            </button>
          ))}
        </div>
      )}

      <Tabs value={tab} onValueChange={(v) => { setTab(String(v)); setErr(null) }}>
        <TabsList>
          <TabsTrigger value="id">Transaction / alert ID</TabsTrigger>
          <TabsTrigger value="form">Form</TabsTrigger>
          <TabsTrigger value="json">JSON</TabsTrigger>
          <TabsTrigger value="csv">CSV / batch</TabsTrigger>
        </TabsList>

        <TabsContent value="id" className="pt-3">
          <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); setErr(null); if (id.trim()) onScore({ txn_id: id.trim() }) }}>
            <Input aria-label="Transaction or alert ID" placeholder="e.g. TXN00000241 or ALR0000001" value={id} onChange={(e) => setId(e.target.value)} className="font-mono" />
            <Button type="submit" disabled={busy || !id.trim()}>{busy && <Loader2 className="animate-spin" />}Score</Button>
          </form>
        </TabsContent>

        <TabsContent value="form" className="pt-3">
          <form className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" onSubmit={(e) => { e.preventDefault(); submitForm() }}>
            <F label="Sender account" invalid={err?.field === "account_id"}><Input value={form.account_id} onChange={(e) => set("account_id", e.target.value)} placeholder="ACC…" className="font-mono" /></F>
            <F label="Counterparty account"><Input value={form.counterparty_account_id} onChange={(e) => set("counterparty_account_id", e.target.value)} placeholder="ACC… (optional)" className="font-mono" /></F>
            <F label="Amount" invalid={err?.field === "amount"}><Input value={form.amount} onChange={(e) => set("amount", e.target.value)} placeholder="9,500.00" inputMode="decimal" /></F>
            <F label="Currency"><select className={SELECT_CLS} value={form.currency} onChange={(e) => set("currency", e.target.value)}>{CURRENCIES.map((c) => <option key={c}>{c}</option>)}</select></F>
            <F label="Channel"><select className={SELECT_CLS} value={form.channel} onChange={(e) => set("channel", e.target.value)}>{CHANNELS.map((c) => <option key={c}>{c}</option>)}</select></F>
            <F label="Merchant category"><select className={SELECT_CLS} value={form.merchant_category} onChange={(e) => set("merchant_category", e.target.value)}>{MERCHANTS.map((c) => <option key={c} value={c}>{c || "—"}</option>)}</select></F>
            <F label="Date and time" invalid={err?.field === "txn_ts"}><Input type="datetime-local" value={form.txn_ts} onChange={(e) => set("txn_ts", e.target.value)} /></F>
            <div className="flex items-end gap-2 pb-2">
              <Checkbox id="xb" checked={form.is_cross_border} onCheckedChange={(v) => set("is_cross_border", Boolean(v))} />
              <Label htmlFor="xb">Cross-border</Label>
            </div>
            <F label="Alert rule (optional)" invalid={err?.field === "rule_id"}><Input value={form.rule_id} onChange={(e) => set("rule_id", e.target.value)} placeholder="R017" className="font-mono" /></F>
            <F label="Alert score 0-1 (optional)" invalid={err?.field === "alert_score"}><Input value={form.alert_score} onChange={(e) => set("alert_score", e.target.value)} placeholder="0.72" inputMode="decimal" /></F>
            <F label="Transaction ID (optional)"><Input value={form.txn_id} onChange={(e) => set("txn_id", e.target.value)} placeholder="NEW-0001" className="font-mono" /></F>
            <div className="flex items-end"><Button type="submit" disabled={busy} className="w-full">{busy && <Loader2 className="animate-spin" />}Score</Button></div>
          </form>
        </TabsContent>

        <TabsContent value="json" className="pt-3">
          <Textarea aria-label="Transaction JSON" value={json} onChange={(e) => setJson(e.target.value)} rows={8} className="font-mono text-xs" />
          <p className="mt-1 text-xs text-muted-foreground">Any field names; Sabwat maps aliases, currencies and date formats. An array scores many.</p>
          <Button className="mt-2" onClick={submitJson} disabled={busy || batchBusy}>{(busy || batchBusy) && <Loader2 className="animate-spin" />}Score JSON</Button>
        </TabsContent>

        <TabsContent value="csv" className="pt-3">
          <Textarea aria-label="CSV rows" value={csv} onChange={(e) => setCsv(e.target.value)} rows={6} className="font-mono text-xs" />
          <div className="mt-2 flex flex-wrap gap-2">
            <Button onClick={() => runBatch(() => api.batch({ csv }))} disabled={batchBusy}>{batchBusy && <Loader2 className="animate-spin" />}Score CSV</Button>
            <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={batchBusy}><Upload />Upload CSV file</Button>
            <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) {
                  void runBatch(() => api.batchUpload(f))
                }
                e.target.value = "" // allow re-uploading the same file
              }} />
          </div>
        </TabsContent>
      </Tabs>

      {err && <p className="text-sm text-destructive" role="alert">{err.msg}</p>}
      {batch && tab !== "id" && tab !== "form" && (
        <BatchTable data={batch} onOpen={(row) => onScore({ transaction: row.input })} />
      )}
    </div>
  )
}

function F({ label, invalid, children }: { label: string; invalid?: boolean; children: React.ReactNode }) {
  return (
    <div className={`flex flex-col gap-1.5 ${invalid ? "[&_input]:border-destructive" : ""}`}>
      <Label className="text-xs text-muted-foreground">{label}</Label>
      {children}
    </div>
  )
}
