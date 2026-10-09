import { useMemo, useState } from "react"

import type { GraphNode, RingGraph as RingGraphData } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { RecordId, SectionTitle } from "./common"

type Kind = "device" | "identity" | "address"
const KIND: Record<Kind, { label: string; color: string; dash?: string }> = {
  device: { label: "Shared device", color: "var(--link-device)" },
  identity: { label: "Shared phone / ID", color: "var(--link-phone)", dash: "7 4" },
  address: { label: "Shared address", color: "var(--link-address)", dash: "2 3" },
}
const kindOf = (k: string): Kind => (k === "Device fingerprint" ? "device" : k === "Address" ? "address" : "identity")

const W = 640
const H = 500
const CX = W / 2
const CY = H / 2
const R = 160

type Ind = Extract<GraphNode, { type: "individual" }>
type Attr = Extract<GraphNode, { type: "attribute" }>

export function RingGraph({ g, sender, receiver }: { g: RingGraphData; sender?: string | null; receiver?: string | null }) {
  const [hover, setHover] = useState<string | null>(null)
  const [asList, setAsList] = useState(false)

  const layout = useMemo(() => {
    const inds = g.nodes.filter((n): n is Ind => n.type === "individual")
    const attrs = g.nodes.filter((n): n is Attr => n.type === "attribute")
    const attrsOf = new Map<string, string[]>()
    for (const e of g.edges) attrsOf.set(e.source, [...(attrsOf.get(e.source) ?? []), e.target])
    // Order individuals by the attributes they share so linked people sit next to each other.
    const order = [...inds].sort((a, b) =>
      (attrsOf.get(a.id) ?? []).sort().join().localeCompare((attrsOf.get(b.id) ?? []).sort().join())
    )
    const pos = new Map<string, { x: number; y: number; a: number }>()
    order.forEach((n, i) => {
      const a = (i / order.length) * 2 * Math.PI - Math.PI / 2
      pos.set(n.id, { x: CX + R * Math.cos(a), y: CY + R * Math.sin(a), a })
    })
    for (const at of attrs) {
      const linked = g.edges.filter((e) => e.target === at.id).map((e) => pos.get(e.source)!)
      const mx = linked.reduce((s, p) => s + p.x, 0) / linked.length
      const my = linked.reduce((s, p) => s + p.y, 0) / linked.length
      pos.set(at.id, { x: CX + (mx - CX) * 0.45, y: CY + (my - CY) * 0.45, a: 0 })
    }
    return { inds: order, attrs, pos }
  }, [g])

  const { inds, attrs, pos } = layout
  const kindById = new Map(attrs.map((a) => [a.id, kindOf(a.kind)]))
  const caption = (() => {
    if (!hover) return "Hover a person or account for details. Click an ID below to open its record."
    const n = inds.find((x) => x.id === hover)
    if (n)
      return `${n.id}: ${n.accounts.length} account(s), ${n.mule_accounts.length} collection account(s)${n.focus ? " · involved in this transaction" : ""}`
    const a = attrs.find((x) => x.id === hover)
    if (a) return `${KIND[kindOf(a.kind)].label} (${a.kind}) used by ${g.edges.filter((e) => e.target === a.id).length} people`
    return `${hover}: collection account (receives from 10+ senders)`
  })()
  const people = inds.length
  const mules = inds.reduce((s, n) => s + n.mule_accounts.length, 0)

  return (
    <div>
      <SectionTitle hint={<Button variant="ghost" size="xs" onClick={() => setAsList(!asList)}>{asList ? "Show graph" : "Show as list"}</Button>}>
        Ring {g.ring_id} · {people} people, {mules} collection accounts
      </SectionTitle>

      {asList ? (
        <div className="max-h-96 overflow-auto text-xs">
          <table className="w-full">
            <thead className="text-left text-muted-foreground">
              <tr><th className="py-1 font-medium">Person</th><th className="font-medium">Link</th><th className="font-medium">Record</th><th className="font-medium">Collection accounts</th></tr>
            </thead>
            <tbody>
              {g.edges.map((e) => {
                const n = inds.find((x) => x.id === e.source)!
                return (
                  <tr key={e.record_id} className="border-t border-border">
                    <td className="py-1"><RecordId id={e.source} /></td>
                    <td>{KIND[kindById.get(e.target)!].label}</td>
                    <td><RecordId id={e.record_id} /></td>
                    <td>{n.mule_accounts.join(", ") || "—"}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full [&_text]:[paint-order:stroke] [&_text]:[stroke:var(--card)] [&_text]:[stroke-width:4px]" role="img" aria-label={`Ring ${g.ring_id}: ${people} people linked by shared devices, phones and addresses`}>
          {g.edges.map((e) => {
            const a = pos.get(e.source)!
            const b = pos.get(e.target)!
            const k = KIND[kindById.get(e.target)!]
            const dim = hover && hover !== e.source && hover !== e.target
            return (
              <line key={e.record_id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={k.color} strokeWidth={2}
                strokeDasharray={k.dash} opacity={dim ? 0.15 : 0.9}>
                <title>{`${e.source} · ${k.label} · ${e.record_id}`}</title>
              </line>
            )
          })}

          {attrs.map((at) => {
            const p = pos.get(at.id)!
            const k = KIND[kindOf(at.kind)]
            return (
              <g key={at.id} onMouseEnter={() => setHover(at.id)} onMouseLeave={() => setHover(null)} className="cursor-default">
                <circle cx={p.x} cy={p.y} r={14} fill="transparent" />
                <rect x={p.x - 7} y={p.y - 7} width={14} height={14} transform={`rotate(45 ${p.x} ${p.y})`}
                  fill={k.color} stroke="var(--background)" strokeWidth={2} />
              </g>
            )
          })}

          {inds.map((n) => {
            const p = pos.get(n.id)!
            const isSender = n.id === sender
            const dim = hover && hover !== n.id && !g.edges.some((e) => e.source === n.id && e.target === hover)
            return (
              <g key={n.id} onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)} opacity={dim ? 0.35 : 1}>
                {n.mule_accounts.map((m, j) => {
                  const spread = (j - (n.mule_accounts.length - 1) / 2) * 0.09
                  const mx = CX + (R + 30) * Math.cos(p.a + spread)
                  const my = CY + (R + 30) * Math.sin(p.a + spread)
                  const isRecv = m === receiver
                  return (
                    <g key={m} onMouseEnter={(ev) => { ev.stopPropagation(); setHover(m) }}>
                      <line x1={p.x} y1={p.y} x2={mx} y2={my} stroke="var(--muted-foreground)" strokeWidth={1} />
                      <rect x={mx - 5} y={my - 5} width={10} height={10} fill="var(--foreground)"
                        stroke={isRecv ? "var(--primary)" : "var(--background)"} strokeWidth={isRecv ? 3 : 2} />
                      {isRecv && (
                        <text x={CX + (R + 52) * Math.cos(p.a + spread)} y={CY + (R + 52) * Math.sin(p.a + spread) + 4} textAnchor="middle" className="fill-primary text-[11px] font-semibold">Receiver</text>
                      )}
                    </g>
                  )
                })}
                <circle cx={p.x} cy={p.y} r={18} fill="transparent" />
                <circle cx={p.x} cy={p.y} r={isSender ? 11 : 8} fill="var(--card)" stroke={isSender ? "var(--primary)" : "var(--foreground)"} strokeWidth={isSender ? 4 : 2} />
                <text x={CX + (R - 26) * Math.cos(p.a)} y={CY + (R - 26) * Math.sin(p.a) + 3} textAnchor="middle"
                  className={isSender ? "fill-primary text-[11px] font-semibold" : "fill-muted-foreground text-[10px]"}>
                  {isSender ? "Sender" : `…${n.id.slice(-4)}`}
                </text>
              </g>
            )
          })}
        </svg>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        {(Object.keys(KIND) as Kind[]).map((k) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <svg width="22" height="8" aria-hidden><line x1="0" y1="4" x2="22" y2="4" stroke={KIND[k].color} strokeWidth="2" strokeDasharray={KIND[k].dash} /></svg>
            {KIND[k].label}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 border-2 border-foreground bg-card" style={{ borderRadius: 9999 }} />Person</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 bg-foreground" />Collection account</span>
      </div>
      <p className="mt-1 min-h-5 text-xs text-muted-foreground" aria-live="polite">{caption}</p>
    </div>
  )
}
