import { useState } from 'react'
import { CheckCircle2, Loader2, MessageSquarePlus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { submitFeedback } from '@/services/api'

interface FeedbackFormProps {
  patientId: string
}

/** POST /feedback - attaches a clinician's actual diagnosis / notes
 * to a patient's latest record. Was live on the backend before this
 * UI existed for it. */
export function FeedbackForm({ patientId }: FeedbackFormProps) {
  const [actualDiagnosis, setActualDiagnosis] = useState('')
  const [feedbackText, setFeedbackText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)

  async function handleSubmit() {
    if (!actualDiagnosis.trim()) {
      setError('Enter the actual/confirmed diagnosis.')
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      await submitFeedback({
        patient_id: patientId,
        actual_diagnosis: actualDiagnosis.trim(),
        feedback_text: feedbackText.trim() || null,
      })
      setSubmitted(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not submit feedback.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-primary">
          <MessageSquarePlus className="size-4" />
          Add Feedback
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {submitted ? (
          <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            <CheckCircle2 className="size-4 shrink-0" />
            Feedback recorded for this patient's latest analysis.
          </div>
        ) : (
          <>
            <div className="space-y-1.5">
              <Label htmlFor="actual-diagnosis">Actual / confirmed diagnosis</Label>
              <Input
                id="actual-diagnosis"
                value={actualDiagnosis}
                onChange={(e) => setActualDiagnosis(e.target.value)}
                placeholder="e.g. Community-acquired pneumonia"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="feedback-notes">Notes (optional)</Label>
              <Textarea
                id="feedback-notes"
                value={feedbackText}
                onChange={(e) => setFeedbackText(e.target.value)}
                placeholder="Anything the model got right or wrong"
                rows={3}
              />
            </div>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <Button size="sm" className="gap-1.5" disabled={submitting} onClick={handleSubmit}>
              {submitting && <Loader2 className="size-3.5 animate-spin" />}
              Submit Feedback
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  )
}
