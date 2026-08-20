/**
 * Case Library presets. Hand-authored against src/knowledge/conditions.json's
 * own typical_symptoms/severity fields and labs.json's normal ranges -
 * deliberately NOT auto-mapped from the DDXPlus dataset's evidence codes,
 * since that mapping (DDXPlus code -> our 29-symptom vocabulary) is a
 * nontrivial translation layer that risks silently misrepresenting a real
 * case. These are demo scenarios for the UI, not validation data (that's
 * Day 10's job, against the DDXPlus CSVs directly).
 */
import type { PatientPreset } from '@/lib/form'

export interface CaseLibraryEntry {
  id: string
  title: string
  summary: string
  expectedRiskHint: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  preset: PatientPreset
}

export const CASE_LIBRARY: CaseLibraryEntry[] = [
  {
    id: 'urti',
    title: 'Mild Upper Respiratory Infection',
    summary: 'Young adult, classic common-cold triad, no comorbidities.',
    expectedRiskHint: 'LOW',
    preset: {
      age: 24,
      symptoms: ['sore throat', 'runny nose', 'nasal congestion', 'cough'],
      labs: {},
      comorbidities: [],
    },
  },
  {
    id: 'gerd',
    title: 'Heartburn with Chest Discomfort',
    summary: 'Reflux symptoms that overlap with cardiac chest pain — a good differential-diagnosis test case.',
    expectedRiskHint: 'MEDIUM',
    preset: {
      age: 41,
      symptoms: ['heartburn', 'abdominal pain', 'nausea', 'chest pain'],
      labs: {},
      comorbidities: [],
    },
  },
  {
    id: 'pe',
    title: 'Suspected Pulmonary Embolism',
    summary: 'Sudden shortness of breath, chest pain, and leg swelling with an elevated D-dimer.',
    expectedRiskHint: 'HIGH',
    preset: {
      age: 58,
      symptoms: ['shortness of breath', 'chest pain', 'swelling in legs'],
      labs: { d_dimer: 1200 },
      comorbidities: [],
    },
  },
  {
    id: 'sepsis',
    title: 'Elderly Patient with Sepsis',
    summary: 'Fever, tachycardia, and rising infection markers on top of existing comorbidities.',
    expectedRiskHint: 'CRITICAL',
    preset: {
      age: 78,
      symptoms: ['fever', 'rapid heart rate', 'shortness of breath', 'chills'],
      labs: { WBC: 15.8, procalcitonin: 2.5 },
      comorbidities: ['diabetes', 'kidney disease'],
    },
  },
  {
    id: 'nstemi',
    title: 'Possible Cardiac Event (NSTEMI/STEMI)',
    summary: 'Chest pain with sweating, nausea, and an elevated troponin in a patient with known heart disease.',
    expectedRiskHint: 'CRITICAL',
    preset: {
      age: 67,
      symptoms: ['chest pain', 'shortness of breath', 'sweating', 'nausea'],
      labs: { troponin: 0.8 },
      comorbidities: ['heart disease'],
    },
  },
]
