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

// ── Cloud speech (used when online) ─────────────────────────────────────────
const API_BASE = import.meta.env.VITE_API_BASE || '/api'

// Record from the mic and return the audio Blob when stop() is called.
// Returns { stop } — call stop() to end recording; resolves via onStop(blob).
export async function recordAudio({ onStop, onError }) {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const chunks = []
    const rec = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
    rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data) }
    rec.onstop = () => {
      stream.getTracks().forEach(t => t.stop())
      onStop && onStop(new Blob(chunks, { type: 'audio/webm' }))
    }
    rec.start()
    return { stop: () => { try { rec.stop() } catch (_) {} } }
  } catch (e) {
    onError && onError(e)
    return { stop: () => {} }
  }
}

// Send recorded audio to the backend Cloud STT endpoint.
export async function cloudTranscribe(blob, lang = 'en-US') {
  const fd = new FormData()
  fd.append('audio', blob, 'note.webm')
  fd.append('language', lang.split('-')[0])
  const res = await fetch(API_BASE + '/stt', { method: 'POST', body: fd })
  if (!res.ok) throw new Error('STT ' + res.status)
  return res.json()  // { transcript, confidence }
}

// One reused <audio> element so playback isn't blocked by autoplay policy
// (it's "unlocked" once on the first user gesture — see unlockAudio()).
let _ttsAudio = null
function _audioEl() {
  if (!_ttsAudio) { _ttsAudio = new Audio(); _ttsAudio.preload = 'auto' }
  return _ttsAudio
}

// Call once from a click handler to satisfy the browser's autoplay policy.
export function unlockAudio() {
  try {
    const a = _audioEl()
    // a tiny silent play/pause primes the element for later programmatic play()
    a.muted = true
    a.play().then(() => { a.pause(); a.muted = false }).catch(() => { a.muted = false })
  } catch (_) {}
}

// Speak text via Cloud TTS (natural voice). Returns true if Cloud audio played,
// false if it fell back to browser synthesis. onFallback(reason) reports why.
export async function cloudSpeak(text, lang = 'en-US', onFallback) {
  let url
  try {
    const res = await fetch(API_BASE + '/tts', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, language: lang.split('-')[0] }),
    })
    if (!res.ok) throw new Error('TTS HTTP ' + res.status)
    const buf = await res.arrayBuffer()
    if (!buf || buf.byteLength < 200) throw new Error('empty audio')
    url = URL.createObjectURL(new Blob([buf], { type: 'audio/mpeg' }))
    const a = _audioEl()
    a.src = url
    a.onended = () => { URL.revokeObjectURL(url); url = null }
    await a.play()             // may reject if autoplay is blocked
    return true
  } catch (e) {
    if (url) URL.revokeObjectURL(url)
    onFallback && onFallback(e.message || String(e))
    speak(text, lang)          // fallback to browser synthesis
    return false
  }
}

// Is cloud speech enabled on the backend?
export async function cloudSpeechAvailable() {
  try {
    const res = await fetch(API_BASE + '/speech-status')
    if (!res.ok) return false
    return (await res.json()).cloud_speech === true
  } catch { return false }
}
