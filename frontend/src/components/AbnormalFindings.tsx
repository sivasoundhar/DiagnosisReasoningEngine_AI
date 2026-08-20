import { FlaskConical } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { labStatusColors } from '@/lib/risk'
import { labMeta } from '@/lib/knowledge'
import type { LabInterpretation } from '@/types'

interface AbnormalFindingsProps {
  labInterpretations: LabInterpretation[]
}

export function AbnormalFindings({ labInterpretations }: AbnormalFindingsProps) {
  const abnormal = labInterpretations.filter((l) => l.status !== 'NORMAL')

  if (labInterpretations.length === 0) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-primary">
          <FlaskConical className="size-4" />
          Lab Findings
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {abnormal.length === 0 ? (
          <p className="text-sm text-muted-foreground">All reported labs are within normal range.</p>
        ) : (
          abnormal.map((lab) => {
            const colors = labStatusColors(lab.status)
            const unit = labMeta(lab.lab_name)?.unit
            return (
              <div key={lab.lab_name} className={`rounded-lg border p-2.5 ${colors.panel}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">
                    {lab.lab_name} — {lab.value}
                    {unit ? ` ${unit}` : ''}
                  </span>
                  <Badge variant="outline" className={colors.badge}>
                    {lab.status}
                  </Badge>
                </div>
                <p className="mt-1 text-xs leading-relaxed">{lab.interpretation}</p>
              </div>
            )
          })
        )}
      </CardContent>
    </Card>
  )
}
