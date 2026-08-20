import { ListChecks } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import type { DiagnosisCandidate } from '@/types'

interface DiagnosesTableProps {
  diagnoses: DiagnosisCandidate[]
}

export function DiagnosesTable({ diagnoses }: DiagnosesTableProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-primary">
          <ListChecks className="size-4" />
          Top Differential Diagnoses
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {diagnoses.length === 0 && (
          <p className="text-sm text-muted-foreground">No candidate diagnoses were matched from the reported symptoms.</p>
        )}
        {diagnoses.map((d, i) => (
          <div key={d.name} className="flex items-start gap-3">
            <div className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-primary">
              {i + 1}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <p className="truncate text-sm font-medium">{d.name}</p>
                <span className="shrink-0 text-sm font-semibold text-primary">{d.confidence.toFixed(1)}%</span>
              </div>
              <Progress value={d.confidence} className="mt-1.5 h-1.5" />
              <p className="mt-1.5 text-xs text-muted-foreground">{d.reasoning}</p>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
