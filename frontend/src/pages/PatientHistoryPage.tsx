import { useState } from 'react'
import { Clock, History as HistoryIcon, Loader2, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ResultsDisplay } from '@/components/ResultsDisplay'
import { FeedbackForm } from '@/components/FeedbackForm'
import { getPatientHistory } from '@/services/api'
import { getRecentPatients } from '@/lib/recentPatients'
import { riskColors } from '@/lib/risk'
import { formatDateTime } from '@/lib/dates'
import type { HistoryEntry } from '@/types'

export function PatientHistoryPage() {
  const [patientId, setPatientId] = useState('')
  const [entries, setEntries] = useState<HistoryEntry[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const recentPatients = getRecentPatients()

  async function handleSearch(id: string) {
    const trimmed = id.trim()
    if (!trimmed) return
    setPatientId(trimmed)
    setLoading(true)
    setError(null)
    setEntries(null)
    setExpandedId(null)
    try {
      const results = await getPatientHistory(trimmed)
      setEntries(results)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load history for this patient.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 md:px-6 md:py-8">
      <div className="mb-6">
        <h1 className="font-heading text-xl font-semibold">Patient History</h1>
        <p className="text-sm text-muted-foreground">Look up past analyses for a patient ID.</p>
      </div>

      <Card className="mb-4">
        <CardContent className="space-y-3 pt-1">
          <div className="flex gap-2">
            <Input
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch(patientId)}
              placeholder="Paste a patient ID (shown after running an analysis)"
              className="font-mono text-sm"
            />
            <Button onClick={() => handleSearch(patientId)} disabled={loading} className="gap-1.5">
              {loading ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
              Search
            </Button>
          </div>

          {recentPatients.length > 0 && (
            <div>
              <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Clock className="size-3.5" />
                Recently analyzed on this device
              </p>
              <div className="flex flex-wrap gap-1.5">
                {recentPatients.map((p) => (
                  <button
                    key={p.patientId}
                    type="button"
                    onClick={() => handleSearch(p.patientId)}
                    className="rounded-full border bg-muted px-2.5 py-1 text-xs hover:bg-accent hover:text-accent-foreground"
                  >
                    {p.patientName ? p.patientName : <span className="font-mono">{p.patientId.slice(0, 8)}…</span>}
                  </button>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertTitle>Lookup failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {entries && entries.length === 0 && (
        <div className="flex min-h-[200px] flex-col items-center justify-center rounded-xl border border-dashed p-10 text-center">
          <HistoryIcon className="mb-3 size-8 text-muted-foreground" />
          <p className="text-sm font-medium">No analyses found for this patient ID.</p>
        </div>
      )}

      {entries && entries.length > 0 && (
        <div className="space-y-3">
          {entries.map((entry, i) => {
            const top = entry.result.diagnoses[0]
            const colors = riskColors(entry.result.risk_assessment?.risk_level)
            const isExpanded = expandedId === entry.id
            return (
              <Card key={entry.id}>
                <button
                  type="button"
                  onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                  className="w-full text-left"
                >
                  <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
                    <div className="min-w-0">
                      <CardTitle className="text-sm font-medium">
                        {entry.patient_name || formatDateTime(entry.created_at)}
                        {i === 0 && (
                          <Badge variant="outline" className="ml-2 align-middle">
                            Latest
                          </Badge>
                        )}
                      </CardTitle>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {entry.patient_name && `${formatDateTime(entry.created_at)} · `}
                        {entry.age !== null && entry.age !== undefined && `Age ${entry.age} · `}
                        {entry.symptoms.join(', ') || 'No symptoms recorded'}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {top && (
                        <span className="text-xs text-muted-foreground">
                          {top.name} ({top.confidence.toFixed(0)}%)
                        </span>
                      )}
                      {entry.result.risk_assessment && (
                        <Badge variant="outline" className={colors.badge}>
                          {entry.result.risk_assessment.risk_level}
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                </button>
                {isExpanded && (
                  <CardContent className="border-t pt-4">
                    <ResultsDisplay
                      result={entry.result}
                      elapsedMs={null}
                      patientMeta={{
                        age: entry.age ?? undefined,
                        symptoms: entry.symptoms,
                        comorbidities: entry.comorbidities,
                      }}
                    />
                    {i === 0 && (
                      <div className="mt-4">
                        <FeedbackForm patientId={entry.patient_id} />
                      </div>
                    )}
                  </CardContent>
                )}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
