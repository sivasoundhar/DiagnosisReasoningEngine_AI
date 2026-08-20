import { useState } from 'react'
import { Download, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { PatientForm } from '@/components/PatientForm'
import { PipelineStrip } from '@/components/PipelineStrip'
import { ResultsDisplay, ResultsEmptyState } from '@/components/ResultsDisplay'
import { analyzeDiagnosis } from '@/services/api'
import { emptyFormData, toPatientInput, validateFormData } from '@/lib/form'
import { useAnalysisForm } from '@/lib/analysisForm'
import { addRecentPatient } from '@/lib/recentPatients'
import type { DiagnosisOutput } from '@/types'

export function DiagnosisPage() {
  const { formData, setFormData } = useAnalysisForm()
  const [result, setResult] = useState<DiagnosisOutput | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorField, setErrorField] = useState<string | undefined>(undefined)
  const [elapsedMs, setElapsedMs] = useState<number | null>(null)

  async function handleSubmit() {
    const validationError = validateFormData(formData)
    if (validationError) {
      setError(validationError.message)
      setErrorField(validationError.field)
      return
    }
    setError(null)
    setErrorField(undefined)
    setLoading(true)
    const startedAt = performance.now()
    try {
      const output = await analyzeDiagnosis(toPatientInput(formData))
      setResult(output)
      setElapsedMs(performance.now() - startedAt)
      addRecentPatient(output.patient_id, output.patient_name)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong analyzing this patient.')
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  function handleReset() {
    setFormData(emptyFormData())
    setResult(null)
    setError(null)
    setErrorField(undefined)
    setElapsedMs(null)
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 md:px-6 md:py-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div>
          <h1 className="font-heading text-xl font-semibold">Patient Analysis Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Run the symptom → lab → risk → recommendation pipeline for a patient.
          </p>
        </div>
        {(result || error) && (
          <div className="flex gap-2">
            {result && (
              <Button variant="outline" size="sm" className="gap-1.5" onClick={() => window.print()}>
                <Download className="size-3.5" />
                Download Report
              </Button>
            )}
            <Button variant="outline" size="sm" className="gap-1.5" onClick={handleReset}>
              <RotateCcw className="size-3.5" />
              New Analysis
            </Button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[380px_1fr] print:block">
        <div className="lg:sticky lg:top-6 print:hidden">
          <PatientForm
            value={formData}
            onChange={setFormData}
            onSubmit={handleSubmit}
            loading={loading}
            errorField={errorField}
            errorMessage={error ?? undefined}
          />
        </div>

        <div className="min-w-0 space-y-4">
          {(loading || result) && (
            <div className="print:hidden">
              <PipelineStrip loading={loading} completed={Boolean(result) && !loading} />
            </div>
          )}

          {error && !errorField && (
            <Alert variant="destructive">
              <AlertTitle>Analysis failed</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {result ? (
            <ResultsDisplay
              result={result}
              elapsedMs={elapsedMs}
              patientMeta={{
                age: Number(formData.age) || undefined,
                symptoms: formData.symptoms,
                comorbidities: formData.comorbidities,
              }}
            />
          ) : (
            !loading && <ResultsEmptyState />
          )}
        </div>
      </div>

      <p className="mt-8 text-center text-xs text-muted-foreground print:hidden">
        This AI system is for educational and research purposes only. Always consult qualified healthcare professionals.
      </p>
    </div>
  )
}
