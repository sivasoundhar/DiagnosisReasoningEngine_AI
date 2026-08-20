/**
 * Single date-formatting helper used everywhere a timestamp is shown
 * (Analytics, Patient History, the print report) so the whole app reads one
 * consistent, unambiguous style instead of each screen calling raw
 * `toLocaleString()`/`toLocaleDateString()` (locale-numeric, e.g. "8/12/2026" -
 * ambiguous between US month/day and day/month elsewhere).
 */
const DATE_FORMAT: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', year: 'numeric' }
const TIME_FORMAT: Intl.DateTimeFormatOptions = { hour: 'numeric', minute: '2-digit' }

/** "Aug 12, 2026" */
export function formatDate(value: string | Date): string {
  const date = typeof value === 'string' ? new Date(value) : value
  return date.toLocaleDateString(undefined, DATE_FORMAT)
}

/** "Aug 12, 2026 · 6:53 AM" */
export function formatDateTime(value: string | Date): string {
  const date = typeof value === 'string' ? new Date(value) : value
  return `${date.toLocaleDateString(undefined, DATE_FORMAT)} · ${date.toLocaleTimeString(undefined, TIME_FORMAT)}`
}
