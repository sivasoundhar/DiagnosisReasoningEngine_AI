import { CalendarClock, ClipboardList, Pill, TestTube } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import type { Recommendation } from '@/types'

interface RecommendationsPanelProps {
  recommendation: Recommendation | null
}

export function RecommendationsPanel({ recommendation }: RecommendationsPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-primary">
          <ClipboardList className="size-4" />
          Recommended Next Steps
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!recommendation ? (
          <p className="text-sm text-muted-foreground">Recommendations unavailable for this analysis.</p>
        ) : (
          <>
            <div>
              <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <TestTube className="size-3.5" />
                Recommended Tests
              </p>
              {recommendation.tests.length === 0 ? (
                <p className="text-xs text-muted-foreground">None recommended.</p>
              ) : (
                <ul className="space-y-1">
                  {recommendation.tests.map((t) => (
                    <li key={t} className="flex items-start gap-1.5 text-sm">
                      <span className="mt-1.5 size-1 shrink-0 rounded-full bg-primary" />
                      {t}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <Separator />

            <div>
              <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Pill className="size-3.5" />
                Recommended Treatments
              </p>
              {recommendation.treatments.length === 0 ? (
                <p className="text-xs text-muted-foreground">None recommended.</p>
              ) : (
                <ul className="space-y-1">
                  {recommendation.treatments.map((t) => (
                    <li key={t} className="flex items-start gap-1.5 text-sm">
                      <span className="mt-1.5 size-1 shrink-0 rounded-full bg-primary" />
                      {t}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <Separator />

            <div className="flex items-start gap-1.5 rounded-lg bg-accent px-3 py-2 text-xs text-accent-foreground">
              <CalendarClock className="mt-0.5 size-3.5 shrink-0" />
              <span>
                <span className="font-medium">Follow-up: </span>
                {recommendation.follow_up}
              </span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
