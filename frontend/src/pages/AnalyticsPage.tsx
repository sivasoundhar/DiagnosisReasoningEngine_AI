import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, BarChart3, CalendarRange, Loader2, MessageSquareCheck, Stethoscope, Users } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { getAnalytics } from '@/services/api'
import { riskColors, type RiskLevel } from '@/lib/risk'
import { formatDate } from '@/lib/dates'
import type { AnalyticsSummary } from '@/types'

const RISK_LEVELS: RiskLevel[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

function StatTile({ icon: Icon, label, value }: { icon: typeof Activity; label: string; value: string }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 pt-1">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
          <Icon className="size-4" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-lg font-semibold leading-tight">{value}</p>
          <p className="truncate text-xs text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  )
}

/** Bar spec: value lives as text at the bar's end (never colored text), bar
 * itself carries the color; status colors always pair with their LOW/MEDIUM/
 * HIGH/CRITICAL text label (never color alone) per dataviz's status-palette
 * rule, since MEDIUM/HIGH sit close enough in hue that color alone under-
 * distinguishes them even for full-color vision. */
function DistributionRow({ label, count, total, barClassName }: { label: string; count: number; total: number; barClassName: string }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0
  return (
    <div className="flex items-center gap-3">
      <span title={label} className="w-24 shrink-0 truncate text-sm font-medium sm:w-40">
        {label}
      </span>
      <div className="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
        <div className={`h-full rounded-full ${barClassName}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-16 shrink-0 text-right text-xs text-muted-foreground">
        {count} ({pct}%)
      </span>
    </div>
  )
}

export function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getAnalytics()
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load analytics.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 md:px-6 md:py-8">
      <div className="mb-6">
        <h1 className="font-heading text-xl font-semibold">Analytics</h1>
        <p className="text-sm text-muted-foreground">Aggregated across every analysis stored on this instance.</p>
      </div>

      {loading && (
        <div className="flex min-h-[200px] items-center justify-center text-muted-foreground">
          <Loader2 className="size-5 animate-spin" />
        </div>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Could not load analytics</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {data && data.total_analyses === 0 && (
        <div className="flex min-h-[200px] flex-col items-center justify-center rounded-xl border border-dashed p-10 text-center">
          <BarChart3 className="mb-3 size-8 text-muted-foreground" />
          <p className="text-sm font-medium">No analyses yet.</p>
          <p className="mt-1 text-xs text-muted-foreground">Run an analysis to start populating these stats.</p>
        </div>
      )}

      {data && data.total_analyses > 0 && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatTile icon={Activity} label="Total analyses" value={String(data.total_analyses)} />
            <StatTile icon={Users} label="Unique patients" value={String(data.unique_patients)} />
            <StatTile icon={MessageSquareCheck} label="Feedback coverage" value={`${data.feedback_coverage_pct}%`} />
            <StatTile
              icon={CalendarRange}
              label="Last analysis"
              value={data.last_analysis_at ? formatDate(data.last_analysis_at) : '—'}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-primary">
                <AlertTriangle className="size-4" />
                Risk Level Distribution
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {RISK_LEVELS.map((level) => (
                <DistributionRow
                  key={level}
                  label={level}
                  count={data.risk_level_distribution[level] ?? 0}
                  total={data.total_analyses}
                  barClassName={riskColors(level).bar}
                />
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-primary">
                <Stethoscope className="size-4" />
                Most Common Top Diagnoses
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {data.top_diagnoses.length === 0 ? (
                <p className="text-sm text-muted-foreground">No diagnoses recorded yet.</p>
              ) : (
                data.top_diagnoses.map((d) => (
                  <DistributionRow
                    key={d.name}
                    label={d.name}
                    count={d.count}
                    total={data.top_diagnoses[0].count}
                    barClassName="bg-primary"
                  />
                ))
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
