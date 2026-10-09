// Typed client for the Sabwat FastAPI backend (/api).

export type Band = "Low" | "Med" | "High"

export type Reason = {
  feature: string
  label: string
  value: string | number | null
  contribution: number
  direction: "raises" | "lowers"
}

export type Triage =
  | { applied: false; reason: string }
  | {
      applied: true
      alert_id: string | null
      rule_id: string
      rule_name: string | null
      alert_score: number
      alerts_on_txn: number
      p_real: number
      percentile: number
      score: number
      band: Band
      reasons: Reason[]
      model_version: string
    }

export type Signal = {
  name: "ring_member_sender" | "fanin_mule_counterparty" | "just_under_10k"
  label: string
  detail: string
  evidence_ids: string[]
}

export type GraphNode =
  | { id: string; type: "individual"; focus: boolean; accounts: string[]; mule_accounts: string[] }
  | { id: string; type: "attribute"; kind: string }

export type RingGraph = {
  ring_id: string
  nodes: GraphNode[]
  edges: { source: string; target: string; record_id: string }[]
}

export type OwnershipLink = {
  ownership_link_id: string
  direction: "owns" | "owned by"
  other_entity_id: string
  link_type: string
  ownership_pct: number
  watchlist_entry_id: string
  list_type: string
  is_nominee: boolean
}

export type ScoreResult = {
  txn: Record<string, string | number | boolean | null>
  score: number
  band: Band
  layers_fired: string[]
  driver: string
  triage: Triage
  network: { score: number; band: Band; signals: Signal[]; ring_id: string | null; cold_start: boolean }
  ring_graph: RingGraph | null
  ownership: {
    entity_id: string
    own_entries: { watchlist_entry_id: string; list_type: string; reason: string }[]
    links: OwnershipLink[]
  } | null
  data_gaps: string[]
  warnings: string[]
  evidence: { allowed_ids: string[] }
  latency_s: number
}

export type Brief = {
  risk_summary: string
  key_findings: { finding: string; evidence_ids: string[]; severity: "high" | "medium" | "low" }[]
  recommended_action: "escalate" | "review" | "dismiss"
  open_questions: string[]
  confidence: "high" | "medium" | "low"
}

export type BriefResult = {
  brief: Brief
  source: "gemini" | "claude" | "template"
  label: string
  validation: { findings_dropped?: number; warnings?: string[]; error?: string; attempts?: number }
  latency_s: number
  cached: boolean
}

export type BatchRow = {
  row: number
  input: Record<string, unknown>
  txn_id: string | null
  account_id?: string | null
  amount_usd?: number | null
  score: number | null
  band: Band | null
  layers_fired: string[]
  signals: string[]
  triage_p_real?: number | null
  warnings?: string[]
  error: string | null
}

export type Example = {
  title: string
  note: string
  txn_id?: string
  transaction?: Record<string, unknown>
}

export type RuleStat = {
  rule_id: string
  rule_name: string
  rule_type: string
  alerts: number
  share_of_alerts: number
  fp_rate: number
}

export type Metrics = {
  model_version: string
  baseline: { fp_rate_strict: number; fp_rate_is_false_positive: number }
  split: { test_alerts: number; test_real: number }
  triage_test: {
    auc_model: number
    auc_rule_score: number
    at_90_recall_model: { fp_avoided: number; fp_avoided_pct: number; workload_cut_pct: number }
    at_90_recall_rule_score: { fp_avoided: number; fp_avoided_pct: number }
    precision_at_100_model: number
    precision_at_100_rule_score: number
  }
  network: { ring_transactions: number; ring_transactions_never_alerted: number; ring_alerts: number; ring_alerts_confirmed_real: number }
  noisy_rules: { combined_share_of_alerts: number; combined_fp_rate: number }
  rules: RuleStat[]
  as_of: {
    cutoff: string
    later_ring_transfers: number
    flagged_high: number
    flagged_med_or_high: number
    rules_alerted: number
    rules_confirmed_real: number
  }[]
  time_baseline: { investigation_median_hours: number; review_alert_details_median_min: number }
}

export type Health = {
  status: string
  version: string
  engine_ready: boolean
  engine_error: string | null
  llm_enabled: boolean
  llm_provider: string
  llm_model: string | null
  db_backend: string
}

export class ApiError extends Error {
  field?: string
  constructor(message: string, field?: string) {
    super(message)
    this.field = field
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, init)
  } catch {
    throw new ApiError("Cannot reach the Sabwat server.")
  }
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = body.error ?? (typeof body.detail === "string" ? body.detail : null)
    throw new ApiError(msg ?? `Request failed (HTTP ${res.status})`, body.field)
  }
  return body as T
}

const post = <T,>(path: string, body: unknown) =>
  call<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })

export type ScoreInput = { txn_id: string } | { transaction: Record<string, unknown> }

export const api = {
  health: () => call<Health>("/health"),
  examples: () => call<{ examples: Example[] }>("/examples"),
  metrics: () => call<Metrics>("/metrics"),
  score: (input: ScoreInput) => post<ScoreResult>("/score", input),
  brief: (input: ScoreInput) => post<BriefResult>("/brief", input),
  batch: (body: { rows: Record<string, unknown>[] } | { csv: string }) =>
    post<{ rows: BatchRow[]; scored: number; errors: number }>("/score/batch", body),
  batchUpload: (file: File) => {
    const fd = new FormData()
    fd.append("file", file)
    return call<{ rows: BatchRow[]; scored: number; errors: number }>("/score/batch/upload", { method: "POST", body: fd })
  },
  decide: (body: {
    txn_id: string
    decision: "escalate" | "review" | "dismiss"
    note: string
    score: number
    band: Band
    layers_fired: string[]
    brief_source: "gemini" | "claude" | "template" | null
  }) => post<{ stored_in: string }>("/decision", body),
  record: (id: string) => call<{ type: string; id: string; fields: Record<string, unknown> }>(`/record/${encodeURIComponent(id)}`),
}
