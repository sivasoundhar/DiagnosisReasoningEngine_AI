import { useEffect, useState } from 'react'
import { Volume2, VolumeX } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface TextToSpeechButtonProps {
  /** Plain-text summary to read aloud - callers build a short spoken
   * version of the results, not the full report (nobody wants the entire
   * reasoning chain read out loud). */
  text: string
}

const supported = typeof window !== 'undefined' && 'speechSynthesis' in window

/**
 * "Read aloud" (Day 9, optional per spec): browser-native text-to-speech via
 * SpeechSynthesisUtterance - a clinician can listen to the summary while
 * still looking at the patient instead of the screen. Broadly supported
 * (unlike SpeechRecognition), but still feature-detected defensively.
 */
export function TextToSpeechButton({ text }: TextToSpeechButtonProps) {
  const [speaking, setSpeaking] = useState(false)

  // Stop speaking if the component unmounts (navigating away) or the
  // underlying text changes out from under an in-progress utterance.
  useEffect(() => {
    return () => {
      if (supported) window.speechSynthesis.cancel()
    }
  }, [text])

  if (!supported) return null

  function handleClick() {
    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      return
    }
    window.speechSynthesis.cancel() // clear any stale utterance first
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'en-US'
    utterance.onstart = () => setSpeaking(true)
    utterance.onend = () => setSpeaking(false)
    utterance.onerror = () => setSpeaking(false)
    window.speechSynthesis.speak(utterance)
  }

  return (
    <Button type="button" variant="outline" size="sm" className="gap-1.5" onClick={handleClick}>
      {speaking ? <VolumeX className="size-3.5" /> : <Volume2 className="size-3.5" />}
      {speaking ? 'Stop' : 'Read Aloud'}
    </Button>
  )
}
