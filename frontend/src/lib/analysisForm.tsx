import { createContext, useContext, useState, type ReactNode } from 'react'
import { emptyFormData, type PatientFormData } from '@/lib/form'

interface AnalysisFormContextValue {
  formData: PatientFormData
  setFormData: (next: PatientFormData) => void
}

const AnalysisFormContext = createContext<AnalysisFormContextValue | null>(null)

/**
 * Lifts PatientFormData above DiagnosisPage so the Case Library page can
 * hand off a preset patient to the Analyze page (they're mounted/unmounted
 * as you navigate between nav items, so page-local useState alone can't
 * survive that).
 */
export function AnalysisFormProvider({ children }: { children: ReactNode }) {
  const [formData, setFormData] = useState<PatientFormData>(emptyFormData())
  return <AnalysisFormContext.Provider value={{ formData, setFormData }}>{children}</AnalysisFormContext.Provider>
}

export function useAnalysisForm(): AnalysisFormContextValue {
  const ctx = useContext(AnalysisFormContext)
  if (!ctx) throw new Error('useAnalysisForm must be used within an AnalysisFormProvider')
  return ctx
}
