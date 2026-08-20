import { AlertTriangle, ListChecks, ShieldCheck, ShieldQuestion, ShieldX } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { AICritique } from '@/types'

interface AICritiquePanelProps {
  aiCritique: AICritique | null
}

const ASSESSMENT_META = {
  agrees: { label: 'Agrees', icon: ShieldCheck, className: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
  partially_agrees: {
    label: 'Partially Agrees',
    icon: ShieldQuestion,
    className: 'border-amber-200 bg-amber-50 text-amber-700',
  },
  disagrees: { label: 'Disagrees', icon: ShieldX, className: 'border-red-200 bg-red-50 text-red-700' },
} as const

/**
 * Shows the AI Critic Agent's output - the actual cross-verification step. Unlike
 * AIOpinionPanel (an independent take, never shown the rule engine's answer), this agent WAS
 * shown `diagnoses`/`risk_assessment`/`recommendation` and asked to critique that specific
 * result: does it hold up, what's missing, any concerns. Rendered as its own card, separate
 * from AIOpinionPanel, so "independent opinion" and "critique of our own result" don't get
 * conflated - they're different questions with different answers.
 */
export function AICritiquePanel({ aiCritique }: AICritiquePanelProps) {
  const meta = aiCritique ? ASSESSMENT_META[aiCritique.assessment] ?? ASSESSMENT_META.partially_agrees : null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-primary">
          <ListChecks className="size-4" />
          AI Cross-Check
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!aiCritique ? (
          <p className="text-sm text-muted-foreground">
            AI cross-check unavailable for this analysis — either no{' '}
            <code className="rounded bg-muted px-1 py-0.5 text-xs">GROQ_API_KEY</code> is configured on the
            server, or the request to the model failed. The rule-based result above is unaffected.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              {meta && (
                <Badge variant="outline" className={meta.className}>
                  <meta.icon className="mr-1 size-3" />
                  {meta.label}
                </Badge>
              )}
              {aiCritique.model && (
                <Badge variant="outline" className="text-muted-foreground">
                  {aiCritique.model}
                </Badge>
              )}
            </div>

            {aiCritique.narrative && (
              <p className="rounded-lg border bg-accent/40 p-2.5 text-xs leading-relaxed">{aiCritique.narrative}</p>
            )}

            {aiCritique.concerns.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground">Concerns raised</p>
                <ul className="mt-1.5 space-y-1">
                  {aiCritique.concerns.map((c) => (
                    <li key={c} className="flex items-start gap-1.5 text-xs">
                      <AlertTriangle className="mt-0.5 size-3 shrink-0 text-amber-600" />
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {aiCritique.missed_considerations.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground">Possibly missed</p>
                <ul className="mt-1.5 space-y-1">
                  {aiCritique.missed_considerations.map((m) => (
                    <li key={m} className="flex items-start gap-1.5 text-xs">
                      <span className="mt-1 size-1 shrink-0 rounded-full bg-muted-foreground" />
                      {m}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <p className="text-[11px] italic text-muted-foreground">
              This agent WAS shown the rule-based diagnosis/risk/recommendation above and asked to review it —
              opposite of the AI Second Opinion panel, which never sees it. Supplementary, not authoritative.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}
