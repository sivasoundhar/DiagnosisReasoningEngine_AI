import { AlertTriangle, CheckCircle2, Sparkles } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import type { AIOpinion } from '@/types'

interface AIOpinionPanelProps {
  aiOpinion: AIOpinion | null
  /** The rule engine's #1 diagnosis (result.diagnoses[0]?.name), used only to render an
   * agree/differ badge - this panel never lets the AI opinion override or feed into the
   * rule-based result itself, it's a side-by-side comparison for the clinician. */
  ruleEngineTopDiagnosis?: string | null
}

/**
 * Shows the Day 12 AI Reasoning Agent's output - a genuinely independent LLM second
 * opinion, deliberately presented next to (never merged into) the deterministic
 * rule-engine result above it. When `aiOpinion` is null (no GROQ_API_KEY configured,
 * or the Groq call failed for this analysis) this renders an explanatory empty state
 * rather than hiding itself, so it's clear the feature exists but didn't run.
 */
export function AIOpinionPanel({ aiOpinion, ruleEngineTopDiagnosis }: AIOpinionPanelProps) {
  const agreement =
    aiOpinion && aiOpinion.diagnoses.length > 0 && ruleEngineTopDiagnosis
      ? aiOpinion.diagnoses[0].name.trim().toLowerCase() === ruleEngineTopDiagnosis.trim().toLowerCase()
      : null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-primary">
          <Sparkles className="size-4" />
          AI Second Opinion
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!aiOpinion ? (
          <p className="text-sm text-muted-foreground">
            AI second opinion unavailable for this analysis — either no{' '}
            <code className="rounded bg-muted px-1 py-0.5 text-xs">GROQ_API_KEY</code> is configured on the
            server, or the request to the model failed. The rule-based result above is unaffected.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              {agreement !== null && (
                <Badge
                  variant="outline"
                  className={
                    agreement
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                      : 'border-amber-200 bg-amber-50 text-amber-700'
                  }
                >
                  {agreement ? (
                    <CheckCircle2 className="mr-1 size-3" />
                  ) : (
                    <AlertTriangle className="mr-1 size-3" />
                  )}
                  {agreement ? 'Agrees with rule engine' : 'Differs from rule engine'}
                </Badge>
              )}
              {aiOpinion.model && (
                <Badge variant="outline" className="text-muted-foreground">
                  {aiOpinion.model}
                </Badge>
              )}
            </div>

            {aiOpinion.diagnoses.length > 0 && (
              <div className="space-y-2.5">
                {aiOpinion.diagnoses.map((d, i) => (
                  <div key={d.name} className="flex items-start gap-3">
                    <div className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-primary">
                      {i + 1}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <p className="truncate text-sm font-medium">{d.name}</p>
                        <span className="shrink-0 text-sm font-semibold text-primary">
                          {d.confidence.toFixed(0)}%
                        </span>
                      </div>
                      <Progress value={d.confidence} className="mt-1.5 h-1.5" />
                      <p className="mt-1.5 text-xs text-muted-foreground">{d.reasoning}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {aiOpinion.summary && (
              <p className="rounded-lg border bg-accent/40 p-2.5 text-xs leading-relaxed">{aiOpinion.summary}</p>
            )}

            {aiOpinion.red_flags.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground">Red flags noted by the AI</p>
                <ul className="mt-1.5 space-y-1">
                  {aiOpinion.red_flags.map((flag) => (
                    <li key={flag} className="flex items-start gap-1.5 text-xs">
                      <AlertTriangle className="mt-0.5 size-3 shrink-0 text-amber-600" />
                      {flag}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <p className="text-[11px] italic text-muted-foreground">
              Independent LLM opinion — generated from the same reported symptoms/labs/age/comorbidities as the
              rule-based analysis, not shown the rule engine's result. Supplementary, not authoritative.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}
