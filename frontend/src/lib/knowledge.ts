/**
 * Static reference data for form autocomplete/labels, mirroring
 * src/knowledge/{symptoms,labs,risk_factors}.json 1:1 (names, units, normal
 * ranges). This is display metadata only - no scoring/decision logic lives
 * here, that all stays server-side in the KB + agents.
 */

/** Keys from symptoms.json (excluding _meta). */
export const KNOWN_SYMPTOMS = [
  'fever',
  'cough',
  'shortness of breath',
  'chest pain',
  'sore throat',
  'runny nose',
  'nasal congestion',
  'sputum production',
  'wheezing',
  'fatigue',
  'headache',
  'dizziness',
  'palpitations',
  'nausea',
  'vomiting',
  'diarrhea',
  'abdominal pain',
  'heartburn',
  'night sweats',
  'chills',
  'muscle aches',
  'loss of appetite',
  'swelling in legs',
  'pale skin',
  'rapid heart rate',
  'sweating',
  'syncope',
  'hives',
  'throat swelling',
] as const

/** Keys from risk_factors.json's comorbidity_points. */
export const KNOWN_COMORBIDITIES = [
  'diabetes',
  'heart disease',
  'cancer',
  'kidney disease',
  'liver disease',
] as const

export interface LabMeta {
  key: string
  unit: string
  normalMin: number
  normalMax: number
}

/** Keys + units/ranges from labs.json (excluding _meta). */
export const KNOWN_LABS: LabMeta[] = [
  { key: 'WBC', unit: '10^9/L', normalMin: 4.5, normalMax: 11.0 },
  { key: 'CRP', unit: 'mg/L', normalMin: 0.0, normalMax: 5.0 },
  { key: 'glucose', unit: 'mg/dL', normalMin: 70.0, normalMax: 100.0 },
  { key: 'hemoglobin', unit: 'g/dL', normalMin: 12.0, normalMax: 17.5 },
  { key: 'troponin', unit: 'ng/mL', normalMin: 0.0, normalMax: 0.04 },
  { key: 'd_dimer', unit: 'ng/mL', normalMin: 0.0, normalMax: 500.0 },
  { key: 'creatinine', unit: 'mg/dL', normalMin: 0.6, normalMax: 1.3 },
  { key: 'BUN', unit: 'mg/dL', normalMin: 7.0, normalMax: 20.0 },
  { key: 'sodium', unit: 'mmol/L', normalMin: 135.0, normalMax: 145.0 },
  { key: 'potassium', unit: 'mmol/L', normalMin: 3.5, normalMax: 5.0 },
  { key: 'platelets', unit: '10^9/L', normalMin: 150.0, normalMax: 450.0 },
  { key: 'BNP', unit: 'pg/mL', normalMin: 0.0, normalMax: 100.0 },
  { key: 'procalcitonin', unit: 'ng/mL', normalMin: 0.0, normalMax: 0.1 },
  { key: 'AST', unit: 'U/L', normalMin: 10.0, normalMax: 40.0 },
  { key: 'ALT', unit: 'U/L', normalMin: 7.0, normalMax: 56.0 },
]

export function labMeta(key: string): LabMeta | undefined {
  return KNOWN_LABS.find((l) => l.key.toLowerCase() === key.toLowerCase())
}

/** Example patient used by the "Autofill Example" affordance in PatientForm. */
export const EXAMPLE_PATIENT = {
  age: 62,
  symptoms: ['fever', 'cough', 'shortness of breath'],
  labs: { WBC: 12.5, CRP: 8.5, sodium: 132, creatinine: 1.4 },
  comorbidities: ['diabetes', 'heart disease'],
}
