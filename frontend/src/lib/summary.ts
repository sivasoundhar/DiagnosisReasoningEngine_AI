import type { DiagnosisOutput } from '@/types'

/**
 * Short plain-language summary of a diagnosis result - top diagnosis +
 * confidence, risk level + score, follow-up action. Shared by
 * TextToSpeechButton (spoken aloud) and PrintReport (a "Summary" box at the
 * end of the printed report) so both say the same thing rather than
 * maintaining two versions of "the short version." Deliberately not the
 * full reasoning chain - nobody wants the entire report read aloud or
 * repeated verbatim in a TL;DR.
 */
export function buildResultSummary(result: DiagnosisOutput): string {
  const parts: string[] = []
  const top = result.diagnoses[0]
  if (top) {
    parts.push(`Top diagnosis: ${top.name}, ${top.confidence.toFixed(0)}% confidence.`)
  } else {
    parts.push('No candidate diagnoses were matched.')
  }
  if (result.risk_assessment) {
    parts.push(`Risk level: ${result.risk_assessment.risk_level}, score ${result.risk_assessment.score}.`)
  }
  if (result.recommendation?.follow_up) {
    parts.push(`Follow-up: ${result.recommendation.follow_up}`)
  }
  return parts.join(' ')
}
