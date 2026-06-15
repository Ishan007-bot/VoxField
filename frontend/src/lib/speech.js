// Web Speech API wrappers: speech-to-text (recognition) + text-to-speech.
// Free, on-device, no API key. Best support in Chrome/Edge.

export function speechSupported() {
  return 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window
}

// Language codes used by both STT and TTS.
export const LANGUAGES = [
  { code: 'en-US', label: 'English' },
  { code: 'hi-IN', label: 'हिन्दी (Hindi)' },
  { code: 'es-ES', label: 'Español (Spanish)' },
]

let recognition = null

// Start listening. Calls onResult(text, isFinal) as speech is transcribed,
// onEnd() when it stops, onError(err) on failure. Returns a stop() function.
export function listen({ lang = 'en-US', continuous = false, onResult, onEnd, onError }) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SR) {
    onError && onError(new Error('Speech recognition not supported in this browser.'))
    return () => {}
  }
  recognition = new SR()
  recognition.lang = lang
  recognition.continuous = continuous
  recognition.interimResults = true
  recognition.maxAlternatives = 1

  let finalText = ''
  recognition.onresult = (e) => {
    let interim = ''
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const tr = e.results[i][0].transcript
      if (e.results[i].isFinal) finalText += tr + ' '
      else interim += tr
    }
    onResult && onResult((finalText + interim).trim(), false)
  }
  recognition.onerror = (e) => onError && onError(e)
  recognition.onend = () => {
    onResult && onResult(finalText.trim(), true)
    onEnd && onEnd(finalText.trim())
  }
  recognition.start()
  return () => { try { recognition && recognition.stop() } catch (_) {} }
}

// Speak text aloud, picking a voice that matches the language if available.
export function speak(text, lang = 'en-US') {
  if (!('speechSynthesis' in window) || !text) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = lang
  const voices = window.speechSynthesis.getVoices()
  const match = voices.find(v => v.lang === lang) || voices.find(v => v.lang.startsWith(lang.split('-')[0]))
  if (match) u.voice = match
  u.rate = 1.0
  u.pitch = 1.0
  window.speechSynthesis.speak(u)
}

export function stopSpeaking() {
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
}
