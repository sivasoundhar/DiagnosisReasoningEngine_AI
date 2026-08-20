/**
 * Axios client for the Diagnosis Reasoning Engine backend.
 *
 * Retries transient failures (network errors, 5xx) with a short backoff;
 * never retries 4xx (bad input / not found) since retrying won't fix those.
 * All functions throw a plain Error with a readable message on failure, so
 * UI code can just try/catch and show `error.message`.
 */
import axios, { type AxiosInstance } from 'axios'
import type {
  AnalyticsSummary,
  ApiErrorResponse,
  DiagnosisOutput,
  FeedbackInput,
  FeedbackResponse,
  HistoryEntry,
  PatientInput,
} from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const MAX_RETRIES = 2
const RETRY_DELAY_MS = 500

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function isRetryable(error: unknown): boolean {
  if (!axios.isAxiosError(error)) return false
  // No response at all = network/timeout failure - worth a retry.
  // 5xx = the server itself failed (e.g. supervisor crash) - may be transient.
  // 4xx is never retried: bad input or "not found" won't change on a retry.
  if (!error.response) return true
  return error.response.status >= 500
}

function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as ApiErrorResponse | undefined
    if (data?.detail) return data.detail
    if (data?.error) return data.error
    if (error.response) return `Request failed with status ${error.response.status}.`
    return 'Network error - could not reach the server.'
  }
  return error instanceof Error ? error.message : 'An unknown error occurred.'
}

async function requestWithRetry<T>(fn: () => Promise<T>, retriesLeft = MAX_RETRIES): Promise<T> {
  try {
    return await fn()
  } catch (error) {
    if (retriesLeft > 0 && isRetryable(error)) {
      await sleep(RETRY_DELAY_MS)
      return requestWithRetry(fn, retriesLeft - 1)
    }
    throw new Error(extractErrorMessage(error))
  }
}

/** POST /analyze - runs the full 6-agent pipeline on a patient. */
export async function analyzeDiagnosis(patientData: PatientInput): Promise<DiagnosisOutput> {
  return requestWithRetry(async () => {
    const { data } = await apiClient.post<DiagnosisOutput>('/analyze', patientData)
    return data
  })
}

/** GET /history/{patient_id} - past analyses for a patient, most recent first. */
export async function getPatientHistory(patientId: string): Promise<HistoryEntry[]> {
  return requestWithRetry(async () => {
    const { data } = await apiClient.get<HistoryEntry[]>(`/history/${encodeURIComponent(patientId)}`)
    return data
  })
}

/** POST /feedback - attach a clinician's actual diagnosis / notes to a patient's latest analysis. */
export async function submitFeedback(feedback: FeedbackInput): Promise<FeedbackResponse> {
  return requestWithRetry(async () => {
    const { data } = await apiClient.post<FeedbackResponse>('/feedback', feedback)
    return data
  })
}

/** GET /analytics - aggregate stats across every stored analysis. */
export async function getAnalytics(): Promise<AnalyticsSummary> {
  return requestWithRetry(async () => {
    const { data } = await apiClient.get<AnalyticsSummary>('/analytics')
    return data
  })
}

export default apiClient
