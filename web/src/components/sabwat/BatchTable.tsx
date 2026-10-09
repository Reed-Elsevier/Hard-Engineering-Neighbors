import type { BatchRow } from "@/lib/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { BandChip, usd } from "./common"

/** Ranked queue from a CSV/JSON batch. Click a row to open it in the full view. */
export function BatchTable({ data, onOpen }: { data: { rows: BatchRow[]; scored: number; errors: number }; onOpen: (row: BatchRow) => void }) {
  return (
    <div>
      <p className="mb-2 text-xs text-muted-foreground">
        {data.scored} scored, {data.errors} with input errors, ranked by score. Click a row to open it.
      </p>
      <div className="max-h-96 overflow-auto border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <TableHead>Transaction</TableHead>
              <TableHead>Sender</TableHead>
              <TableHead className="text-right">USD</TableHead>
              <TableHead className="text-right">Score</TableHead>
              <TableHead>Band</TableHead>
              <TableHead>Why</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.rows.map((r) => (
              <TableRow key={r.row} className={r.error ? "" : "cursor-pointer"} onClick={() => !r.error && onOpen(r)}>
                <TableCell className="text-muted-foreground">{r.row}</TableCell>
                <TableCell className="font-mono text-xs">{r.txn_id ?? "—"}</TableCell>
                <TableCell className="font-mono text-xs">{r.account_id ?? "—"}</TableCell>
                <TableCell className="text-right tabular-nums">{r.error ? "" : usd(r.amount_usd)}</TableCell>
                <TableCell className="text-right font-semibold tabular-nums">{r.score ?? ""}</TableCell>
                <TableCell>{r.band && <BandChip band={r.band} short />}</TableCell>
                <TableCell className="max-w-72 text-xs whitespace-normal">
                  {r.error ? <span className="text-destructive">{r.error}</span>
                    : [...r.layers_fired.map((l) => `${l} layer`), ...r.signals].join(" · ") || "No signals"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
