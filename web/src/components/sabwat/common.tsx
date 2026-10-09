import { useState } from "react"
import {
  AlertTriangle, BookOpen, Building2, ChevronRight, CircleCheck, CreditCard, FileStack, FileText, Fingerprint, Home,
  Link2, ListChecks, OctagonAlert, ShieldAlert, Siren, Smartphone, UserRound, Wallet, Waypoints,
} from "lucide-react"

import { cn } from "@/lib/utils"
import { api, type Band } from "@/lib/api"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Spinner } from "@/components/ui/spinner"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card"

const BAND_STYLE: Record<Band, { cls: string; Icon: typeof AlertTriangle; label: string }> = {
  High: { cls: "bg-risk-high text-white", Icon: OctagonAlert, label: "High risk" },
  Med: { cls: "bg-risk-med text-black", Icon: AlertTriangle, label: "Medium risk" },
  Low: { cls: "bg-risk-low text-white", Icon: CircleCheck, label: "Low risk" },
}

/** Risk band chip: status color + icon + word, never color alone. */
export function BandChip({ band, className, short }: { band: Band; className?: string; short?: boolean }) {
  const { cls, Icon, label } = BAND_STYLE[band]
  return (
    <span className={cn("inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-semibold tracking-wider uppercase", cls, className)}>
      <Icon className="size-3.5" aria-hidden />
      {short ? band : label}
    </span>
  )
}

export function SectionTitle({ children, hint }: { children: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <h3 className="font-heading text-xs font-semibold tracking-widest text-muted-foreground uppercase">{children}</h3>
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </div>
  )
}

const RECORD_TYPE: Record<string, { label: string; Icon: typeof AlertTriangle }> = {
  transactions: { label: "Transaction", Icon: CreditCard },
  accounts: { label: "Account", Icon: Wallet },
  risk_alerts: { label: "Rule alert", Icon: Siren },
  individuals: { label: "Person", Icon: UserRound },
  devices: { label: "Device", Icon: Smartphone },
  addresses: { label: "Address", Icon: Home },
  identity_attributes: { label: "Identity attribute (hashed)", Icon: Fingerprint },
  business_entities: { label: "Company", Icon: Building2 },
  ownership_links: { label: "Ownership link", Icon: Link2 },
  watchlists: { label: "Watchlist entry", Icon: ShieldAlert },
  alert_rules: { label: "Alert rule", Icon: ListChecks },
  ring: { label: "Ring", Icon: Waypoints },
}

const humanKey = (k: string) => {
  const t = k.replace(/_/g, " ").replace(/\bid\b/g, "ID").replace(/\busd\b/g, "USD")
  return t.charAt(0).toUpperCase() + t.slice(1)
}
const humanVal = (v: unknown) =>
  v === null || v === undefined || v === "" ? "—" : typeof v === "boolean" ? (v ? "Yes" : "No")
    : typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(v).replace(/T(\d\d:\d\d).*$/, " $1")

/** A record ID the analyst can click; the record opens in a side sheet. */
export function RecordId({ id }: { id: string }) {
  const [state, setState] = useState<
    { status: "idle" } | { status: "loading" } | { status: "ok"; fields: Record<string, unknown>; type: string } | { status: "error"; msg: string }
  >({ status: "idle" })

  const load = (open: boolean) => {
    if (!open || state.status === "ok" || state.status === "loading") return
    setState({ status: "loading" })
    api
      .record(id)
      .then((r) => setState({ status: "ok", fields: r.fields, type: r.type }))
      .catch((e: Error) => setState({ status: "error", msg: e.message }))
  }
  const meta = state.status === "ok" ? RECORD_TYPE[state.type] : undefined
  const Icon = meta?.Icon ?? FileText

  return (
    <Sheet onOpenChange={load}>
      <SheetTrigger aria-label={`Open record ${id}`}
        className="cursor-pointer border border-border bg-muted px-1.5 py-0.5 font-mono text-[0.7rem] text-foreground hover:border-foreground/40 focus-visible:ring-2 focus-visible:ring-ring/40 focus-visible:outline-none">
        {id}
      </SheetTrigger>
      <SheetContent className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <span className="flex size-8 items-center justify-center bg-muted"><Icon className="size-4" /></span>
            <span className="font-mono">{id}</span>
          </SheetTitle>
          <SheetDescription>{meta?.label ?? "Record"} · from the source data</SheetDescription>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto px-4 pb-6">
          {state.status === "loading" && <p className="inline-flex items-center gap-2 text-sm text-muted-foreground"><Spinner />Loading record…</p>}
          {state.status === "error" && <p className="text-sm text-destructive">{state.msg}</p>}
          {state.status === "ok" && (
            <dl className="divide-y divide-border text-sm">
              {Object.entries(state.fields).map(([k, v]) => (
                <div key={k} className="grid grid-cols-[minmax(0,10rem)_1fr] gap-3 py-2">
                  <dt className="text-muted-foreground">{humanKey(k)}</dt>
                  <dd className="break-words">{humanVal(v)}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

export function RecordIds({ ids, max = 2 }: { ids: string[]; max?: number }) {
  const [all, setAll] = useState(false)
  const shown = all ? ids : ids.slice(0, max)
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {shown.map((id) => (
        <RecordId key={id} id={id} />
      ))}
      {ids.length > max && !all && (
        <button className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground" onClick={() => setAll(true)}>
          <FileStack className="size-3.5" aria-hidden />+{ids.length - max} records
        </button>
      )}
    </span>
  )
}

/** "Details" disclosure: the long sentence and record IDs stay one click away. */
export function Details({ children, label = "Details" }: { children: React.ReactNode; label?: string }) {
  return (
    <Collapsible>
      <CollapsibleTrigger className="group inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
        <ChevronRight className="size-3.5 transition-transform group-data-[panel-open]:rotate-90" aria-hidden />
        {label}
      </CollapsibleTrigger>
      <CollapsibleContent className="pt-2 pl-4.5">{children}</CollapsibleContent>
    </Collapsible>
  )
}

const GLOSSARY: Record<string, { title: string; text: string }> = {
  ring: { title: "Ring", text: "People linked because they share a device, phone or home address. Sabwat found one ring of 15 people." },
  collection: { title: "Collection account", text: "An account that receives money from many different senders (10 or more). Typical accounts receive from 1 to 3." },
  triage: { title: "Alert triage", text: "A model trained on past alerts and their outcomes. It estimates whether a rule alert is real or a false alarm." },
  network: { title: "Network layer", text: "Checks who the sender and receiver are connected to. Works on any transaction, even ones the rules never flagged." },
  factors: { title: "Factors", text: "How much each detail pushed this alert's estimate up or down (SHAP values). Longer bar = bigger effect." },
}

/** A domain term with a plain-language definition on hover or focus. */
export function Term({ k, children }: { k: keyof typeof GLOSSARY; children: React.ReactNode }) {
  const g = GLOSSARY[k]
  return (
    <HoverCard>
      <HoverCardTrigger render={<span tabIndex={0} />} className="cursor-help underline decoration-dotted underline-offset-3">
        {children}
      </HoverCardTrigger>
      <HoverCardContent className="w-72 text-sm">
        <p className="mb-1 inline-flex items-center gap-1.5 font-semibold"><BookOpen className="size-3.5" />{g.title}</p>
        <p className="text-muted-foreground">{g.text}</p>
      </HoverCardContent>
    </HoverCard>
  )
}

export const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`
export const usd = (x: number | null | undefined) =>
  x == null ? "—" : x.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 })
