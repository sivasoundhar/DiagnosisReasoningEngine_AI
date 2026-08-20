import type { PatientInput } from '@/types'
import { EXAMPLE_PATIENT, KNOWN_SYMPTOMS } from '@/lib/knowledge'
import { getDefaultLabPanel } from '@/lib/labPanel'
import { stringSimilarity } from '@/lib/fuzzyMatch'

export interface LabRow {
  id: string
  name: string
  value: string
}

/** Plain preset shape shared by the "Autofill Example" patient and the Case
 * Library's sample patients - same fields as PatientInput but with numeric
 * labs, before being spread into editable form rows. */
export interface PatientPreset {
  age: number
  symptoms: string[]
  labs: Record<string, number>
  comorbidities: string[]
}

/** Editable form shape - looser than PatientInput (strings, row-based labs
 * so a half-filled row doesn't collapse into an invalid Record). Converted
 * to PatientInput just before the API call. */
export interface PatientFormData {
  patientName: string
  patientId: string
  age: string
  symptoms: string[]
  labs: LabRow[]
  comorbidities: string[]
}

let rowIdCounter = 0
function newRowId(): string {
  rowIdCounter += 1
  return `lab-${rowIdCounter}-${Date.now()}`
}

export function emptyFormData(): PatientFormData {
  const defaultLabs = getDefaultLabPanel().map((name) => ({ id: newRowId(), name, value: '' }))
  return { patientName: '', patientId: '', age: '', symptoms: [], labs: defaultLabs, comorbidities: [] }
}

export function formDataFromPreset(preset: PatientPreset): PatientFormData {
  return {
    patientName: '',
    patientId: '',
    age: String(preset.age),
    symptoms: [...preset.symptoms],
    labs: Object.entries(preset.labs).map(([name, value]) => ({
      id: newRowId(),
      name,
      value: String(value),
    })),
    comorbidities: [...preset.comorbidities],
  }
}

export function exampleFormData(): PatientFormData {
  return formDataFromPreset(EXAMPLE_PATIENT)
}

export function newLabRow(): LabRow {
  return { id: newRowId(), name: '', value: '' }
}

export interface FormValidationError {
  field: string
  message: string
}

/** Mirrors PatientInput's own constraints (models.py: symptoms min_length=1,
 * age 0-120) so the UI catches bad input before the API round-trip does. */
export function validateFormData(form: PatientFormData): FormValidationError | null {
  if (form.symptoms.length === 0) {
    return { field: 'symptoms', message: 'Add at least one symptom.' }
  }
  const age = Number(form.age)
  if (form.age.trim() === '' || Number.isNaN(age)) {
    return { field: 'age', message: 'Enter a valid age.' }
  }
  if (age < 0 || age > 120) {
    return { field: 'age', message: 'Age must be between 0 and 120.' }
  }
  return null
}

export function toPatientInput(form: PatientFormData): PatientInput {
  const labs: Record<string, number> = {}
  for (const row of form.labs) {
    const name = row.name.trim()
    const value = Number(row.value)
    if (!name || row.value.trim() === '' || Number.isNaN(value)) continue
    labs[name] = value
  }
  return {
    age: Number(form.age),
    symptoms: form.symptoms,
    labs,
    comorbidities: form.comorbidities,
    patient_id: form.patientId.trim() || undefined,
    patient_name: form.patientName.trim() || undefined,
  }
}

/** Splits a spoken phrase like "fever, cough and shortness of breath" into
 * individual symptom strings - voice input (Day 9) hands back one run-on
 * transcript, but the symptoms field is a list of tags. */
export function parseSpokenSymptoms(transcript: string): string[] {
  return transcript
    .split(/,|\band\b/gi)
    .map((s) => s.trim().replace(/[.!?]+$/, ''))
    .filter(Boolean)
}

const KNOWN_SYMPTOM_MATCH_THRESHOLD = 0.72

/** Fraction (0-1) of a spoken phrase's comma/and-separated segments that
 * closely match a real entry in KNOWN_SYMPTOMS - used to score
 * SpeechRecognition's alternatives against each other. */
function knownSymptomMatchScore(transcript: string): number {
  const segments = parseSpokenSymptoms(transcript)
  if (segments.length === 0) return 0
  const hits = segments.filter((segment) =>
    KNOWN_SYMPTOMS.some((known) => stringSimilarity(segment, known) >= KNOWN_SYMPTOM_MATCH_THRESHOLD),
  ).length
  return hits / segments.length
}

/**
 * SpeechRecognition's #1 guess (`alternatives[0]`) is sometimes just wrong
 * for a short phrase (e.g. "chest pain" transcribed as "just fine") even
 * though the correct wording is sitting in a lower-ranked alternative -
 * Google's ranking doesn't know this app only cares about medical symptom
 * vocabulary. Re-scores every alternative against KNOWN_SYMPTOMS and picks
 * whichever matches best, defaulting to the engine's own top guess on a tie
 * (including when nothing matches well - could be a real symptom that's
 * just not in the known list, not necessarily a misrecognition).
 */
export function pickBestSpokenAlternative(alternatives: string[]): string {
  if (alternatives.length === 0) return ''
  let best = alternatives[0]
  let bestScore = knownSymptomMatchScore(alternatives[0])
  for (let i = 1; i < alternatives.length; i++) {
    const score = knownSymptomMatchScore(alternatives[i])
    if (score > bestScore) {
      best = alternatives[i]
      bestScore = score
    }
  }
  return best
}
