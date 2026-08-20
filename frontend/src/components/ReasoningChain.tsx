import { Workflow } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { AICritique, AIOpinion, DiagnosisCandidate, LabInterpretation, Recommendation, RiskAssessment } from '@/types'

interface ReasoningChainProps {
  topDiagnosis?: DiagnosisCandidate
  labInterpretations: LabInterpretation[]
  risk: RiskAssessment | null
  recommendation: Recommendation | null
  aiOpinion?: AIOpinion | null
  aiCritique?: AICritique | null
}

/**
 * Human-readable trace of what each agent concluded, built only from strings
 * the API already returns (DiagnosisCandidate.reasoning,
 * LabInterpretation.interpretation, RiskAssessment.reasoning) - the
 * Recommender step is the one exception, since Recommendation has no
 * reasoning field of its own (tests/treatments/follow_up only), so its line
 * is synthesized from what it actually produced rather than invented. The AI
 * Reasoner and AI Critic steps are included only when `aiOpinion`/`aiCritique`
 * are present respectively - when either is null (no GROQ_API_KEY, or the
 * call failed), this chain simply omits that step rather than claiming it
 * happened, same as how Lab Interpreter is omitted when no labs were
 * submitted.
 */
export function ReasoningChain({
  topDiagnosis,
  labInterpretations,
  risk,
  recommendation,
  aiOpinion,
  aiCritique,
}: ReasoningChainProps) {
  const abnormalLabs = labInterpretations.filter((l) => l.status !== 'NORMAL')

  const steps: { label: string; text: string }[] = []

  if (topDiagnosis) {
    steps.push({ label: 'Symptom Analyzer', text: topDiagnosis.reasoning })
  }

  if (labInterpretations.length > 0) {
    steps.push({
      label: 'Lab Interpreter',
      text:
        abnormalLabs.length > 0
          ? abnormalLabs.map((l) => `${l.lab_name}: ${l.interpretation}`).join(' ')
          : 'All reported lab values fell within normal range.',
    })
  }

  if (risk) {
    steps.push({ label: 'Risk Assessor', text: risk.reasoning })
  }

  if (recommendation) {
    const parts: string[] = []
    if (recommendation.tests.length) parts.push(`${recommendation.tests.length} test(s)`)
    if (recommendation.treatments.length) parts.push(`${recommendation.treatments.length} treatment(s)`)
    steps.push({
      label: 'Recommender',
      text: `Recommended ${parts.join(' and ') || 'a supportive-care plan'} based on the top diagnosis and ${risk?.risk_level ?? 'assessed'} risk level. Follow-up: ${recommendation.follow_up}.`,
    })
  }

  if (aiOpinion && aiOpinion.summary) {
    steps.push({ label: 'AI Reasoner', text: aiOpinion.summary })
  }

  if (aiCritique && aiCritique.narrative) {
    const assessmentLabel = aiCritique.assessment.replace('_', ' ')
    steps.push({ label: 'AI Critic', text: `[${assessmentLabel}] ${aiCritique.narrative}` })
  }

  if (steps.length === 0) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-primary">
          <Workflow className="size-4" />
          Agent Reasoning Chain
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="space-y-3">
          {steps.map((step, i) => (
            <li key={step.label} className="flex gap-3">
              <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-primary">
                {i + 1}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium">{step.label}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">"{step.text}"</p>
              </div>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}
