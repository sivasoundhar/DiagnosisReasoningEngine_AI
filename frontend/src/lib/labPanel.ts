/**
 * Settings > Default Lab Panel: which labs auto-appear as empty rows when
 * starting a new analysis, instead of clicking "+ Add lab result" for the
 * same handful of labs every time. Pure display/convenience preference
 * (localStorage), same pattern as lib/theme.tsx.
 */
const STORAGE_KEY = 'diagnosis-engine-default-lab-panel'

export function getDefaultLabPanel(): string[] {
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

export function setDefaultLabPanel(labNames: string[]): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(labNames))
}
