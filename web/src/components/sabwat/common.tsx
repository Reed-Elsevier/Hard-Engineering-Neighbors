import { useState } from "react"
import { AlertTriangle, CircleCheck, OctagonAlert } from "lucide-react"

import { cn } from "@/lib/utils"
import { api, type Band } from "@/lib/api"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

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

/** A record ID the analyst can click to open the underlying record. */
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

  return (
    <Popover onOpenChange={load}>
      <PopoverTrigger className="cursor-pointer border border-border bg-muted px-1.5 py-0.5 font-mono text-[0.7rem] text-foreground hover:border-foreground/40 focus-visible:ring-2 focus-visible:ring-ring/40 focus-visible:outline-none">
        {id}
      </PopoverTrigger>
      <PopoverContent className="w-80 max-w-[90vw]">
        <div className="mb-2 font-mono text-xs font-semibold">{id}</div>
        {state.status === "loading" && <p className="text-xs text-muted-foreground">Loading record…</p>}
        {state.status === "error" && <p className="text-xs text-destructive">{state.msg}</p>}
        {state.status === "ok" && (
          <>
            <p className="mb-2 text-[0.65rem] tracking-widest text-muted-foreground uppercase">{state.type.replace(/_/g, " ")}</p>
            <dl className="grid max-h-72 grid-cols-[auto_1fr] gap-x-3 gap-y-1 overflow-auto text-xs">
              {Object.entries(state.fields).map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-muted-foreground">{k}</dt>
                  <dd className="break-all">{v === null ? "—" : String(v)}</dd>
                </div>
              ))}
            </dl>
          </>
        )}
      </PopoverContent>
    </Popover>
  )
}

export function RecordIds({ ids, max = 8 }: { ids: string[]; max?: number }) {
  const [all, setAll] = useState(false)
  const shown = all ? ids : ids.slice(0, max)
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {shown.map((id) => (
        <RecordId key={id} id={id} />
      ))}
      {ids.length > max && !all && (
        <button className="text-xs text-muted-foreground underline" onClick={() => setAll(true)}>
          +{ids.length - max} more
        </button>
      )}
    </span>
  )
}

export const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`
export const usd = (x: number | null | undefined) =>
  x == null ? "—" : x.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 })
