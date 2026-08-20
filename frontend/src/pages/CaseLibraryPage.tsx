import { ArrowRight, FlaskConical, Library } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { CASE_LIBRARY } from '@/lib/samplePatients'
import { formDataFromPreset } from '@/lib/form'
import { useAnalysisForm } from '@/lib/analysisForm'
import { riskColors } from '@/lib/risk'

interface CaseLibraryPageProps {
  onTryCase: () => void
}

export function CaseLibraryPage({ onTryCase }: CaseLibraryPageProps) {
  const { setFormData } = useAnalysisForm()

  function tryCase(presetId: string) {
    const entry = CASE_LIBRARY.find((c) => c.id === presetId)
    if (!entry) return
    setFormData(formDataFromPreset(entry.preset))
    onTryCase()
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 md:px-6 md:py-8">
      <div className="mb-6">
        <h1 className="font-heading text-xl font-semibold">Case Library</h1>
        <p className="text-sm text-muted-foreground">
          Pre-built sample patients, hand-picked to cover a range of risk levels. Pick one to load it
          straight into the Analyze form.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {CASE_LIBRARY.map((entry) => {
          const colors = riskColors(entry.expectedRiskHint)
          return (
            <Card key={entry.id}>
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base">{entry.title}</CardTitle>
                  <Badge variant="outline" className={colors.badge}>
                    {entry.expectedRiskHint}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">{entry.summary}</p>
                <div className="flex flex-wrap gap-1.5">
                  {entry.preset.symptoms.map((s) => (
                    <Badge key={s} variant="secondary" className="font-normal">
                      {s}
                    </Badge>
                  ))}
                </div>
                {Object.keys(entry.preset.labs).length > 0 && (
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <FlaskConical className="size-3.5" />
                    Includes: {Object.keys(entry.preset.labs).join(', ')}
                  </p>
                )}
                <Button size="sm" variant="outline" className="w-full gap-1.5" onClick={() => tryCase(entry.id)}>
                  Try this case
                  <ArrowRight className="size-3.5" />
                </Button>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <p className="mt-6 flex items-center gap-1.5 text-xs text-muted-foreground">
        <Library className="size-3.5" />
        These scenarios are hand-authored to match conditions already in the knowledge base — they're
        demo cases, not validated ground truth (that's a separate offline validation pass).
      </p>
    </div>
  )
}
