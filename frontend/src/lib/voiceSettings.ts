/**
 * Settings > Voice Input Language: which accent/locale the SpeechRecognition
 * engine targets. Google's ASR model is locale-specific - "mishears words"
 * is very often just `en-US` being the wrong model for how someone actually
 * speaks English, not a bug in this app. localStorage-backed, same pattern
 * as lib/theme.tsx and lib/labPanel.ts.
 */
const STORAGE_KEY = 'diagnosis-engine-voice-language'
const DEFAULT_LANGUAGE = 'en-US'

export interface VoiceLanguageOption {
  code: string
  label: string
}

export const VOICE_LANGUAGE_OPTIONS: VoiceLanguageOption[] = [
  { code: 'en-US', label: 'English (US)' },
  { code: 'en-GB', label: 'English (UK)' },
  { code: 'en-IN', label: 'English (India)' },
  { code: 'en-AU', label: 'English (Australia)' },
  { code: 'en-CA', label: 'English (Canada)' },
  { code: 'en-IE', label: 'English (Ireland)' },
  { code: 'en-NZ', label: 'English (New Zealand)' },
  { code: 'en-ZA', label: 'English (South Africa)' },
  { code: 'en-PH', label: 'English (Philippines)' },
  { code: 'en-NG', label: 'English (Nigeria)' },
]

export function getVoiceLanguage(): string {
  if (typeof window === 'undefined') return DEFAULT_LANGUAGE
  return window.localStorage.getItem(STORAGE_KEY) || DEFAULT_LANGUAGE
}

export function setVoiceLanguage(code: string): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(STORAGE_KEY, code)
}
