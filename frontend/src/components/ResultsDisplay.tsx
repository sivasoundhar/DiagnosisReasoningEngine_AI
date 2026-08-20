import { CheckCircle2, Stethoscope } from 'lucide-react'
import { DiagnosesTable } from '@/components/DiagnosesTable'
import { RiskCard } from '@/components/RiskCard'
import { RecommendationsPanel } from '@/components/RecommendationsPanel'
import { AbnormalFindings } from '@/components/AbnormalFindings'
import { AIOpinionPanel } from '@/components/AIOpinionPanel'
import { AICritiquePanel } from '@/components/AICritiquePanel'
import { ReasoningChain } from '@/components/ReasoningChain'
import { PrintReport, type PrintPatientMeta } from '@/components/PrintReport'
import { TextToSpeechButton } from '@/components/TextToSpeechButton'
import { buildResultSummary } from '@/lib/summary'
import { cn } from '@/lib/utils'
import type { DiagnosisOutput } from '@/types'

interface ResultsDisplayProps {
  result: DiagnosisOutput
  elapsedMs: number | null
  /** Age/symptoms/comorbidities for the printed report's patient-info
   * section - not part of DiagnosisOutput itself (the backend doesn't echo
   * them back), so callers pass whatever they have on hand (the live form
   * data on Analyze, HistoryEntry.symptoms on Patient History). */
  patientMeta?: PrintPatientMeta
}

export function ResultsDisplay({ result, elapsedMs, patientMeta }: ResultsDisplayProps) {
  return (
    <div className="space-y-4">
      {/* Screen-only status banner */}
      <div className="flex items-center justify-between gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800 print:hidden">
        <span className="flex items-center gap-2">
          <CheckCircle2 className="size-4 shrink-0" />
          Analysis completed{elapsedMs !== null ? ` in ${(elapsedMs / 1000).toFixed(2)} seconds` : ''}
        </span>
        <TextToSpeechButton text={buildResultSummary(result)} />
      </div>

      {/* Purpose-built print/PDF layout - replaces the dashboard cards below
          entirely when printing (see PrintReport's own doc comment). */}
      <PrintReport result={result} patientMeta={patientMeta} />

      <div className="grid grid-cols-1 gap-4 print:hidden lg:grid-cols-2">
        <DiagnosesTable diagnoses={result.diagnoses} />
        <RiskCard risk={result.risk_assessment} />
      </div>

      <div
        className={cn(
          'grid grid-cols-1 gap-4 print:hidden',
          result.lab_interpretations.length > 0 && 'lg:grid-cols-2',
        )}
      >
        <RecommendationsPanel recommendation={result.recommendation} />
        {/* AbnormalFindings renders nothing when no labs were submitted - the grid
            above drops to a single column in that case so it doesn't reserve a
            dead second column next to Recommendations. */}
        <AbnormalFindings labInterpretations={result.lab_interpretations} />
      </div>

      {/* Day 12 + 13: two different LLM checks, deliberately paired but visually distinct -
          AIOpinionPanel never saw the rule-based result (independent), AICritiquePanel WAS
          shown it (cross-check). Their own row, not merged into the rule-based grid above, so
          both always read as supplementary to it. */}
      <div className="grid grid-cols-1 gap-4 print:hidden lg:grid-cols-2">
        <AIOpinionPanel aiOpinion={result.ai_opinion} ruleEngineTopDiagnosis={result.diagnoses[0]?.name ?? null} />
        <AICritiquePanel aiCritique={result.ai_critique} />
      </div>

      <div className="print:hidden">
        <ReasoningChain
          topDiagnosis={result.diagnoses[0]}
          labInterpretations={result.lab_interpretations}
          risk={result.risk_assessment}
          recommendation={result.recommendation}
          aiOpinion={result.ai_opinion}
          aiCritique={result.ai_critique}
        />
      </div>
    </div>
  )
}

export function ResultsEmptyState() {
  return (
    <div className="flex min-h-[300px] flex-col items-center justify-center rounded-xl border border-dashed p-10 text-center">
      <div className="mb-3 flex size-12 items-center justify-center rounded-full bg-accent">
        <Stethoscope className="size-6 text-primary" />
      </div>
      <p className="text-sm font-medium">No analysis yet</p>
      <p className="mt-1 max-w-xs text-xs text-muted-foreground">
        Fill in the patient's symptoms and click "Analyze Patient" to run the 6-agent diagnosis pipeline.
      </p>
    </div>
  )
}
