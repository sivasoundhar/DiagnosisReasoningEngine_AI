import type { ReactNode } from 'react'
import { formatDateTime } from '@/lib/dates'
import { buildResultSummary } from '@/lib/summary'
import type { DiagnosisOutput } from '@/types'

export interface PrintPatientMeta {
  age?: number
  symptoms?: string[]
  comorbidities?: string[]
}

interface PrintReportProps {
  result: DiagnosisOutput
  patientMeta?: PrintPatientMeta
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="pt-4 first:pt-0" style={{ breakInside: 'avoid' }}>
      <h2 className="mb-1.5 border-b border-black pb-1 text-[11px] font-bold tracking-widest uppercase">{title}</h2>
      {children}
    </section>
  )
}

function FieldRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2 text-[12px]">
      <span className="w-32 shrink-0 font-semibold">{label}</span>
      <span>{value}</span>
    </div>
  )
}

/**
 * Purpose-built print/PDF layout - NOT the on-screen dashboard cards reused
 * with chrome hidden. Screen UI (colored badges, progress bars, rounded
 * cards, icons) doesn't read as a document; this is plain black-on-white,
 * ruled sections, and a fixed reading order, closer to a real lab/clinical
 * report printout. Rendered via `hidden print:block` - only exists in the
 * print/PDF output, never on screen.
 *
 * Section order: Presenting Information -> Differential Diagnosis (rule-based)
 * -> Risk Assessment -> Abnormal Labs -> Recommendations -> AI Second Opinion
 * -> AI Cross-Check -> Clinical Reasoning Chain -> Clinical
 * Summary. Both AI sections only render when their data is present (`ai_opinion`
 * / `ai_critique`) - omitted entirely otherwise, not shown as an empty
 * placeholder. They're deliberately placed *after* the rule-based sections and
 * labeled "Independent, Supplementary" / with an explicit "opposite of AI
 * Second Opinion" note so the reading order and labels themselves communicate
 * what each one is - a second opinion vs a critique of the result above it -
 * not the report's authoritative finding either way.
 */
export function PrintReport({ result, patientMeta }: PrintReportProps) {
  const risk = result.risk_assessment
  const rec = result.recommendation
  const abnormalLabs = result.lab_interpretations.filter((l) => l.status !== 'NORMAL')

  return (
    <div className="hidden text-black print:block" style={{ fontSize: '12px', lineHeight: 1.5 }}>
      <header className="mb-4 border-b-2 border-black pb-3">
        <div className="flex items-baseline justify-between">
          <h1 className="text-[18px] font-bold">Diagnosis Reasoning Engine</h1>
          <span className="text-[11px]">Clinical Analysis Report</span>
        </div>
        <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-0.5">
          {result.patient_name && <FieldRow label="Patient Name" value={result.patient_name} />}
          <FieldRow label="Patient ID" value={result.patient_id} />
          {patientMeta?.age !== undefined && <FieldRow label="Age" value={`${patientMeta.age} years`} />}
          <FieldRow label="Analyzed" value={formatDateTime(result.analyzed_at)} />
          <FieldRow label="Printed" value={formatDateTime(new Date())} />
        </div>
      </header>

      <div className="space-y-4">
        {(patientMeta?.symptoms?.length || patientMeta?.comorbidities?.length) ? (
          <Section title="Presenting Information">
            {patientMeta?.symptoms && patientMeta.symptoms.length > 0 && (
              <FieldRow label="Symptoms" value={patientMeta.symptoms.join(', ')} />
            )}
            {patientMeta?.comorbidities && patientMeta.comorbidities.length > 0 && (
              <FieldRow label="Comorbidities" value={patientMeta.comorbidities.join(', ')} />
            )}
          </Section>
        ) : null}

        <Section title="Differential Diagnosis">
          {result.diagnoses.length === 0 ? (
            <p>No candidate diagnoses were matched from the reported symptoms.</p>
          ) : (
            <ol className="space-y-1.5">
              {result.diagnoses.map((d, i) => (
                <li key={d.name}>
                  <p className="font-semibold">
                    {i + 1}. {d.name} — {d.confidence.toFixed(1)}% confidence
                  </p>
                  <p className="pl-4 text-[11px] text-neutral-700">{d.reasoning}</p>
                </li>
              ))}
            </ol>
          )}
        </Section>

        {risk && (
          <Section title="Risk Assessment">
            <p className="font-bold">
              {risk.risk_level} RISK — Score {risk.score}
            </p>
            <p className="mt-0.5 text-[11px]">{risk.reasoning}</p>
            {risk.likely_complications.length > 0 && (
              <>
                <p className="mt-1.5 text-[11px] font-semibold">Likely complications:</p>
                <ul className="list-disc pl-5 text-[11px]">
                  {risk.likely_complications.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </>
            )}
          </Section>
        )}

        {abnormalLabs.length > 0 && (
          <Section title="Abnormal Laboratory Findings">
            <ul className="space-y-1">
              {abnormalLabs.map((lab) => (
                <li key={lab.lab_name} className="text-[11px]">
                  <span className="font-semibold">
                    {lab.lab_name}: {lab.value} — {lab.status}.
                  </span>{' '}
                  {lab.interpretation}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {rec && (
          <Section title="Recommendations">
            {rec.tests.length > 0 && (
              <>
                <p className="text-[11px] font-semibold">Tests:</p>
                <p className="mb-1.5 text-[11px]">{rec.tests.join(' · ')}</p>
              </>
            )}
            {rec.treatments.length > 0 && (
              <>
                <p className="text-[11px] font-semibold">Treatments:</p>
                <p className="mb-1.5 text-[11px]">{rec.treatments.join(' · ')}</p>
              </>
            )}
            <p className="text-[11px]">
              <span className="font-semibold">Follow-up:</span> {rec.follow_up}
            </p>
          </Section>
        )}

        {/* Omitted entirely (not an "unavailable" placeholder) when ai_opinion is null - a printed
            report has no use for explaining why a section is missing the way the on-screen empty
            state does; it just doesn't print a section with nothing to say. */}
        {result.ai_opinion && (
          <Section title="AI Second Opinion (Independent, Supplementary)">
            <p className="mb-1.5 text-[10px] italic text-neutral-700">
              Generated independently by an LLM ({result.ai_opinion.model || 'Groq'}) from the same reported
              symptoms/labs/age/comorbidities as the differential above — the model was not shown that result. Not
              authoritative; provided for comparison alongside the rule-based analysis.
            </p>
            {result.ai_opinion.diagnoses.length > 0 && (
              <ol className="space-y-1.5">
                {result.ai_opinion.diagnoses.map((d, i) => (
                  <li key={d.name}>
                    <p className="font-semibold">
                      {i + 1}. {d.name} — {d.confidence.toFixed(0)}% confidence
                    </p>
                    <p className="pl-4 text-[11px] text-neutral-700">{d.reasoning}</p>
                  </li>
                ))}
              </ol>
            )}
            {result.ai_opinion.summary && (
              <p className="mt-1.5 text-[11px] leading-relaxed">{result.ai_opinion.summary}</p>
            )}
            {result.ai_opinion.red_flags.length > 0 && (
              <>
                <p className="mt-1.5 text-[11px] font-semibold">Red flags noted by the AI:</p>
                <ul className="list-disc pl-5 text-[11px]">
                  {result.ai_opinion.red_flags.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </>
            )}
          </Section>
        )}

        {result.ai_critique && (
          <Section title="AI Cross-Check (Reviewed the Result Above)">
            <p className="mb-1.5 text-[10px] italic text-neutral-700">
              Unlike the AI Second Opinion above, this review WAS shown the rule-based differential, risk
              assessment, and recommendations, and asked to critique that specific result — the actual
              cross-verification step, not another independent take.
            </p>
            <p className="font-semibold uppercase">
              Assessment: {result.ai_critique.assessment.replace('_', ' ')}
            </p>
            {result.ai_critique.narrative && (
              <p className="mt-0.5 text-[11px]">{result.ai_critique.narrative}</p>
            )}
            {result.ai_critique.concerns.length > 0 && (
              <>
                <p className="mt-1.5 text-[11px] font-semibold">Concerns raised:</p>
                <ul className="list-disc pl-5 text-[11px]">
                  {result.ai_critique.concerns.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </>
            )}
            {result.ai_critique.missed_considerations.length > 0 && (
              <>
                <p className="mt-1.5 text-[11px] font-semibold">Possibly missed:</p>
                <ul className="list-disc pl-5 text-[11px]">
                  {result.ai_critique.missed_considerations.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              </>
            )}
          </Section>
        )}

        <Section title="Clinical Reasoning Chain">
          <ol className="list-decimal space-y-1 pl-5 text-[11px]">
            {result.diagnoses[0] && (
              <li>
                <span className="font-semibold">Symptom Analyzer</span> — {result.diagnoses[0].reasoning}
              </li>
            )}
            {result.lab_interpretations.length > 0 && (
              <li>
                <span className="font-semibold">Lab Interpreter</span> —{' '}
                {abnormalLabs.length > 0
                  ? abnormalLabs.map((l) => `${l.lab_name}: ${l.interpretation}`).join(' ')
                  : 'All reported lab values fell within normal range.'}
              </li>
            )}
            {risk && (
              <li>
                <span className="font-semibold">Risk Assessor</span> — {risk.reasoning}
              </li>
            )}
            {rec && (
              <li>
                <span className="font-semibold">Recommender</span> — Recommended {rec.tests.length} test(s) and{' '}
                {rec.treatments.length} treatment(s) based on the top diagnosis and {risk?.risk_level ?? 'assessed'}{' '}
                risk level. Follow-up: {rec.follow_up}.
              </li>
            )}
            {result.ai_opinion?.summary && (
              <li>
                <span className="font-semibold">AI Reasoner (independent)</span> — {result.ai_opinion.summary}
              </li>
            )}
            {result.ai_critique?.narrative && (
              <li>
                <span className="font-semibold">AI Critic ({result.ai_critique.assessment.replace('_', ' ')})</span> —{' '}
                {result.ai_critique.narrative}
              </li>
            )}
          </ol>
        </Section>

        <section className="border-2 border-black p-3" style={{ breakInside: 'avoid' }}>
          <h2 className="mb-1 text-[11px] font-bold tracking-widest uppercase">Clinical Summary</h2>
          <p className="text-[12px] leading-relaxed">{buildResultSummary(result)}</p>
        </section>
      </div>

      <footer className="mt-5 border-t border-black pt-2 text-[10px] text-neutral-700">
        <p>
          This report was generated by an AI clinical decision-support system for educational and research purposes
          only. It is not a medical device and must not be used for real clinical decisions. Always consult a
          qualified healthcare professional.
        </p>
        <p className="mt-1">Diagnosis Reasoning Engine · Generated {formatDateTime(new Date())}</p>
      </footer>
    </div>
  )
}
