import { Mic, MicOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useSpeechRecognition, type SpeechErrorKind } from '@/hooks/useSpeechRecognition'

interface MicButtonProps {
  /** Called with all of SpeechRecognition's ranked guesses each time it
   * finalizes one phrase (best-first) - parent re-scores them against known
   * vocabulary and decides how to fold the winner into the symptoms field. */
  onTranscript: (alternatives: string[]) => void
  className?: string
}

const ERROR_MESSAGES: Record<SpeechErrorKind, string> = {
  'not-supported': "Voice input isn't supported in this browser. Try Chrome on desktop or Android, or type symptoms directly.",
  'not-allowed': 'Microphone access was denied. Allow it in your browser\'s site settings and try again.',
  'no-speech': "Didn't catch that — please speak clearly and try again.",
  'audio-capture': 'No microphone was found. Check that one is connected and try again.',
  network: 'Network issue reaching the speech service. Try again.',
  other: 'Voice input hit an unexpected error. Try again, or type symptoms directly.',
}

/**
 * Voice input: click to start, browser transcribes speech to text,
 * each finalized phrase's ranked alternatives are handed to the parent to
 * re-score and merge into the symptoms field. Stops itself after a few
 * seconds of true silence (the hook's own timer, not the browser's more
 * trigger-happy default) so pauses between symptoms don't cut it off early.
 * Unsupported browsers just show a disabled button with an explanation; the
 * symptoms field is a plain text input regardless, so "fallback" requires
 * no extra code - typing still works exactly as before.
 */
export function MicButton({ onTranscript, className }: MicButtonProps) {
  const { supported, recording, interimTranscript, error, start, stop } = useSpeechRecognition(onTranscript)

  return (
    <div className={cn('relative', className)}>
      <Button
        type="button"
        variant={recording ? 'destructive' : 'secondary'}
        disabled={!supported}
        onClick={recording ? stop : start}
        title={supported ? undefined : ERROR_MESSAGES['not-supported']}
        className="gap-2"
      >
        {!supported ? (
          <MicOff className="size-4" />
        ) : (
          <span className="relative flex size-4 items-center justify-center">
            <Mic className="size-4" />
            {recording && (
              <span className="absolute -right-0.5 -top-0.5 size-2 animate-pulse rounded-full bg-red-500" />
            )}
          </span>
        )}
        {recording ? 'Listening… (click to stop)' : 'Voice Input'}
      </Button>

      {recording && interimTranscript && (
        <p className="absolute top-full left-0 z-10 mt-1 max-w-xs rounded-md border bg-popover px-2 py-1 text-xs text-popover-foreground shadow-sm">
          "{interimTranscript}"
        </p>
      )}

      {error && (
        <p className="mt-1 max-w-xs text-xs text-destructive">{ERROR_MESSAGES[error]}</p>
      )}
    </div>
  )
}
