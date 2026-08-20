import { useCallback, useEffect, useRef, useState } from 'react'
import { getVoiceLanguage } from '@/lib/voiceSettings'

export type SpeechErrorKind = 'not-supported' | 'not-allowed' | 'no-speech' | 'audio-capture' | 'network' | 'other'

interface UseSpeechRecognitionResult {
  supported: boolean
  recording: boolean
  /** Live, not-yet-final transcript - shown as a preview while the user is still talking. */
  interimTranscript: string
  error: SpeechErrorKind | null
  start: () => void
  stop: () => void
}

/** How long a pause is tolerated (measured from the last bit of speech we
 * actually heard) before treating the user as truly done, vs. just pausing
 * between symptoms. */
const SILENCE_TIMEOUT_MS = 3000

/** Chrome briefly needs to fully release one SpeechRecognition session
 * before a new one can start cleanly - starting immediately inside onend
 * can throw InvalidStateError on some versions. */
const RESTART_DELAY_MS = 250

/**
 * Thin wrapper around the browser's SpeechRecognition API.
 *
 * Deliberately uses `continuous: false` for every underlying session, NOT
 * `continuous: true` - Chrome's continuous mode has long-standing bugs
 * where `onresult` can silently stop firing altogether after the first
 * utterance (widely reported, not something app code can work around from
 * the inside). Instead, each short `continuous: false` session (the
 * reliable, well-supported mode) is auto-restarted behind the scenes in
 * `onend` if the user already said something and it's been less than
 * `SILENCE_TIMEOUT_MS` since - so pauses between "fever... cough..." don't
 * cut things off, without touching the flaky continuous mode at all. If
 * nothing has been heard yet, it does NOT auto-restart (avoids silently
 * looping forever against a muted/broken mic).
 *
 * `lang` is read from Settings (`lib/voiceSettings`) instead of hardcoded
 * 'en-US', since recognition accuracy depends heavily on matching the
 * model to the speaker's actual accent. Chrome desktop/Android only in
 * practice; `supported` lets callers fall back to plain text entry
 * everywhere else (the symptoms field already is one, so "fallback" is
 * just "the mic button doesn't do anything special").
 */
export function useSpeechRecognition(
  onFinalTranscript: (alternatives: string[]) => void,
): UseSpeechRecognitionResult {
  const supported =
    typeof window !== 'undefined' && Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)

  const [recording, setRecording] = useState(false)
  const [interimTranscript, setInterimTranscript] = useState('')
  const [error, setError] = useState<SpeechErrorKind | null>(null)

  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const manualStopRef = useRef(false)
  const everHeardRef = useRef(false)
  const lastResultAtRef = useRef(0)
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Always call the latest onFinalTranscript without re-creating the
  // recognition wiring every time the parent re-renders.
  const onFinalTranscriptRef = useRef(onFinalTranscript)
  onFinalTranscriptRef.current = onFinalTranscript

  // Self-referencing so onend can trigger the next session without
  // start()'s own identity changing (start stays a stable useCallback).
  const beginSessionRef = useRef<() => void>(() => {})

  function clearRestartTimer() {
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current)
      restartTimerRef.current = null
    }
  }

  function beginSession() {
    const RecognitionCtor = (window.SpeechRecognition ?? window.webkitSpeechRecognition) as typeof SpeechRecognition
    const recognition = new RecognitionCtor()
    recognition.lang = getVoiceLanguage()
    recognition.continuous = false
    recognition.interimResults = true
    // Ask for multiple ranked guesses, not just one - the engine's own #1
    // pick is sometimes wrong for a short phrase, and the correct wording
    // is often still in there at a lower rank. Callers re-score these.
    recognition.maxAlternatives = 5

    recognition.onstart = () => {
      setRecording(true)
    }

    recognition.onresult = (event) => {
      lastResultAtRef.current = Date.now()
      everHeardRef.current = true
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) {
          const alternatives: string[] = []
          for (let a = 0; a < result.length; a++) {
            const alt = result[a].transcript.trim()
            if (alt) alternatives.push(alt)
          }
          if (alternatives.length > 0) onFinalTranscriptRef.current(alternatives)
        } else {
          interim += result[0].transcript
        }
      }
      setInterimTranscript(interim)
    }

    recognition.onerror = (event) => {
      // Expected, not a real failure: 'aborted' happens whenever we stop
      // the session ourselves; 'no-speech' during the natural gap between
      // symptoms (once we've already heard something) is exactly what the
      // restart-on-end logic below is designed to absorb quietly.
      if (event.error === 'aborted') return
      if (event.error === 'no-speech' && everHeardRef.current) return

      switch (event.error) {
        case 'not-allowed':
        case 'service-not-allowed':
          setError('not-allowed')
          break
        case 'no-speech':
          setError('no-speech')
          break
        case 'audio-capture':
          setError('audio-capture')
          break
        case 'network':
          setError('network')
          break
        default:
          setError('other')
      }
    }

    recognition.onend = () => {
      recognitionRef.current = null
      const idleFor = Date.now() - lastResultAtRef.current
      const shouldKeepListening = !manualStopRef.current && everHeardRef.current && idleFor < SILENCE_TIMEOUT_MS

      if (shouldKeepListening) {
        clearRestartTimer()
        restartTimerRef.current = setTimeout(() => {
          try {
            beginSessionRef.current()
          } catch {
            setRecording(false)
            setInterimTranscript('')
          }
        }, RESTART_DELAY_MS)
      } else {
        setRecording(false)
        setInterimTranscript('')
        everHeardRef.current = false
      }
    }

    recognitionRef.current = recognition
    recognition.start()
  }

  beginSessionRef.current = beginSession

  const start = useCallback(() => {
    if (!supported) {
      setError('not-supported')
      return
    }
    setError(null)
    setInterimTranscript('')
    manualStopRef.current = false
    everHeardRef.current = false
    lastResultAtRef.current = Date.now()
    beginSession()
  }, [supported])

  const stop = useCallback(() => {
    manualStopRef.current = true
    clearRestartTimer()
    recognitionRef.current?.stop()
  }, [])

  // Abort (not just stop) on unmount so a lingering mic session doesn't
  // keep the browser's recording indicator active after navigating away.
  useEffect(() => {
    return () => {
      manualStopRef.current = true
      clearRestartTimer()
      recognitionRef.current?.abort()
    }
  }, [])

  return { supported, recording, interimTranscript, error, start, stop }
}
