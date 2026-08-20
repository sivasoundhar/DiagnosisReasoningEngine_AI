/**
 * Shared TypeScript interfaces mirroring src/models.py (Pydantic) 1:1, so the
 * frontend and backend never drift on what a field is called or shaped like.
 */

export interface PatientInput {
  symptoms: string[] // e.g. ['fever', 'cough']
  labs?: Record<string, number> // e.g. { WBC: 11.2 }
  age: number
  comorbidities?: string[] // e.g. ['diabetes']
  patient_id?: string | null // optional - server generates one if omitted
  patient_name?: string | null // optional display name, for history/reports
}

export interface DiagnosisCandidate {
  name: string
  confidence: number // 0-100
  reasoning: string
}

export interface LabInterpretation {
  lab_name: string
  value: number
  status: 'LOW' | 'NORMAL' | 'ELEVATED' | 'CRITICAL'
  interpretation: string
  confidence: number // 0-100
}

export interface RiskAssessment {
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  score: number
  reasoning: string
  likely_complications: string[]
}

export interface Recommendation {
  tests: string[]
  treatments: string[]
  follow_up: string
}

export interface AIOpinionDiagnosis {
  name: string
  confidence: number // 0-100
  reasoning: string
}

/** Output of the Day 12 AI Reasoning Agent - an independent LLM second opinion,
 * deliberately separate from `diagnoses` (the rule engine's output). `null` on
 * DiagnosisOutput when no GROQ_API_KEY is configured or the LLM call failed. */
export interface AIOpinion {
  diagnoses: AIOpinionDiagnosis[]
  summary: string
  red_flags: string[]
  model: string
}

/** Output of the Day 13 AI Critic Agent - an LLM cross-check of the RULE-BASED result (unlike
 * `AIOpinion`, this agent is shown `diagnoses`/`risk_assessment`/`recommendation` and asked to
 * critique that specific result). `null` on DiagnosisOutput when no GROQ_API_KEY is configured
 * or the LLM call failed. */
export interface AICritique {
  assessment: 'agrees' | 'partially_agrees' | 'disagrees'
  concerns: string[]
  missed_considerations: string[]
  narrative: string
  model: string
}

export interface DiagnosisOutput {
  patient_id: string
  patient_name?: string | null
  diagnoses: DiagnosisCandidate[]
  lab_interpretations: LabInterpretation[]
  risk_assessment: RiskAssessment | null
  recommendation: Recommendation | null
  ai_opinion: AIOpinion | null
  ai_critique: AICritique | null
  analyzed_at: string // ISO datetime
}

export interface HistoryEntry {
  id: number
  patient_id: string
  patient_name?: string | null
  created_at: string // ISO datetime
  symptoms: string[]
  age?: number | null
  comorbidities: string[]
  result: DiagnosisOutput
}

export interface FeedbackInput {
  patient_id: string
  actual_diagnosis: string
  feedback_text?: string | null
}

export interface FeedbackResponse {
  status: string
  message: string
}

export interface ApiErrorResponse {
  error: string
  detail?: string | null
}

export interface DiagnosisFrequency {
  name: string
  count: number
}

export interface AnalyticsSummary {
  total_analyses: number
  unique_patients: number
  risk_level_distribution: Partial<Record<'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL', number>>
  top_diagnoses: DiagnosisFrequency[]
  records_with_feedback: number
  feedback_coverage_pct: number
  first_analysis_at: string | null // ISO datetime
  last_analysis_at: string | null // ISO datetime
}
