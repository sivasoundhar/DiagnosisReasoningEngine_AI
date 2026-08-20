/**
 * Backend has no "list all patients" endpoint (GET /history/{patient_id}
 * needs an id up front) - this keeps a small local list of patient_ids the
 * user has actually analyzed on this device, purely as a convenience for
 * the Patient History page's search box. Not clinical data, just IDs.
 */
const STORAGE_KEY = 'diagnosis-engine-recent-patients'
const MAX_RECENT = 10

interface RecentPatient {
  patientId: string
  patientName?: string | null
  analyzedAt: string
}

export function getRecentPatients(): RecentPatient[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function addRecentPatient(patientId: string, patientName?: string | null): void {
  if (typeof window === 'undefined' || !patientId) return
  const existing = getRecentPatients().filter((p) => p.patientId !== patientId)
  const next = [{ patientId, patientName, analyzedAt: new Date().toISOString() }, ...existing].slice(0, MAX_RECENT)
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
}
