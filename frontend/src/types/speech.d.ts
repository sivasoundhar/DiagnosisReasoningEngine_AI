/**
 * The SpeechRecognition constructor/interface itself isn't in TypeScript's
 * lib.dom.d.ts (spec instability historically kept it out, even though the
 * supporting event types - SpeechRecognitionEvent, SpeechRecognitionErrorEvent,
 * SpeechRecognitionErrorCode - are already declared there). This fills just
 * that gap; everything else is reused from lib.dom.d.ts.
 */

interface SpeechRecognition extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number

  start(): void
  stop(): void
  abort(): void

  onstart: ((this: SpeechRecognition, ev: Event) => void) | null
  onend: ((this: SpeechRecognition, ev: Event) => void) | null
  onresult: ((this: SpeechRecognition, ev: SpeechRecognitionEvent) => void) | null
  onerror: ((this: SpeechRecognition, ev: SpeechRecognitionErrorEvent) => void) | null
  onnomatch: ((this: SpeechRecognition, ev: SpeechRecognitionEvent) => void) | null
}

declare var SpeechRecognition: {
  prototype: SpeechRecognition
  new (): SpeechRecognition
}

interface Window {
  SpeechRecognition?: typeof SpeechRecognition
  webkitSpeechRecognition?: typeof SpeechRecognition
}
