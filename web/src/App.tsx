import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

type Health = {
  status: string
  version: string
  data_available: boolean
  model_available: boolean
  llm_enabled: boolean
}

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return <Badge variant={ok ? "default" : "outline"}>{label}</Badge>
}

export function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setHealth)
      .catch((e: Error) => setError(e.message))
  }, [])

  return (
    <div className="mx-auto flex min-h-svh max-w-5xl flex-col gap-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Sabwat</h1>
        <p className="text-sm text-muted-foreground">
          Rule engines catch individuals. Sabwat catches the <em>sabwatan</em>.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>System status</CardTitle>
          <CardDescription>
            Backend readiness. Scoring, ring graph and briefs are added in later build steps.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {error && <span className="text-sm text-destructive">API unreachable: {error}</span>}
          {!health && !error && <span className="text-sm text-muted-foreground">Checking…</span>}
          {health && (
            <>
              <StatusBadge ok label={`API v${health.version}`} />
              <StatusBadge ok={health.data_available} label="Data" />
              <StatusBadge ok={health.model_available} label="Model" />
              <StatusBadge
                ok={health.llm_enabled}
                label={health.llm_enabled ? "Claude brief" : "Template brief (no API key)"}
              />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default App
