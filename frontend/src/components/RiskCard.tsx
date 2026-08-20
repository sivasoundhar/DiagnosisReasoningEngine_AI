import { AlertTriangle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { riskColors } from '@/lib/risk'
import type { RiskAssessment } from '@/types'

interface RiskCardProps {
  risk: RiskAssessment | null
}

export function RiskCard({ risk }: RiskCardProps) {
  const colors = riskColors(risk?.risk_level)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-primary">
          <AlertTriangle className="size-4" />
          Risk Assessment
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!risk ? (
          <p className="text-sm text-muted-foreground">Risk assessment unavailable for this analysis.</p>
        ) : (
          <>
            <div className={`rounded-lg border p-3 ${colors.panel}`}>
              <div className="flex items-center gap-2">
                <AlertTriangle className={`size-4 ${colors.icon}`} />
                <span className="text-sm font-semibold">{risk.risk_level} RISK</span>
                <Badge variant="outline" className={`ml-auto ${colors.badge}`}>
                  Score {risk.score}
                </Badge>
              </div>
              <p className="mt-2 text-xs leading-relaxed">{risk.reasoning}</p>
            </div>

            {risk.likely_complications.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground">Likely complications</p>
                <ul className="mt-1.5 space-y-1">
                  {risk.likely_complications.map((c) => (
                    <li key={c} className="flex items-start gap-1.5 text-xs">
                      <span className={`mt-1 size-1 shrink-0 rounded-full ${colors.bar}`} />
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
