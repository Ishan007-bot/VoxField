import { useState, useRef, useCallback } from 'react'

// Simulated industrial noise for demonstrating voice capture in noisy environments.
// Uses Web Audio API to generate factory-like ambient noise (white noise + low rumble).
const NOISE_TYPES = [
  { key: 'factory', label: 'Factory Floor', desc: 'Machinery hum + impact noise' },
  { key: 'outdoor', label: 'Outdoor Wind', desc: 'Wind + ambient site noise' },
  { key: 'workshop', label: 'Workshop', desc: 'Tools + compressor noise' },
]

function createNoise(ctx, type) {
  const sr = ctx.sampleRate
  const bufferSize = sr * 3 // 3 seconds, looped
  const buffer = ctx.createBuffer(1, bufferSize, sr)
  const data = buffer.getChannelData(0)

  for (let i = 0; i < bufferSize; i++) {
    const t = i / sr
    const white = Math.random() * 2 - 1
    let sample = 0

    if (type === 'factory') {
      // Heavy low rumble (40 Hz) dominates; quiet hiss; regular metallic CLANG every ~1.2s.
      sample = Math.sin(t * 2 * Math.PI * 40) * 0.35       // deep rumble
             + Math.sin(t * 2 * Math.PI * 120) * 0.12      // motor harmonic
             + white * 0.08                                 // faint hiss
      const clangPhase = i % Math.floor(sr * 1.2)
      if (clangPhase < sr * 0.05) {                         // sharp metallic hit, decaying
        const env = 1 - clangPhase / (sr * 0.05)
        sample += Math.sin(t * 2 * Math.PI * 900) * 0.5 * env
      }
    } else if (type === 'outdoor') {
      // Wind: slow swelling broadband whoosh, no tonal/rhythmic content.
      const gust = 0.4 + 0.6 * Math.abs(Math.sin(t * 2 * Math.PI * 0.25))
      sample = white * 0.45 * gust
    } else {
      // Workshop: busy mid-frequency tool WHINE + frequent erratic bursts (drill/grinder).
      sample = Math.sin(t * 2 * Math.PI * 520) * 0.18      // power-tool whine
             + Math.sin(t * 2 * Math.PI * 780) * 0.10      // overtone
             + white * 0.15
      if (Math.random() < 0.03) sample += (Math.random() - 0.5) * 0.7  // frequent sharp bursts
    }
    data[i] = Math.max(-1, Math.min(1, sample))
  }

  const source = ctx.createBufferSource()
  source.buffer = buffer
  source.loop = true

  const gain = ctx.createGain()
  gain.gain.value = 0.35

  // Per-type tone shaping so each preset is clearly distinguishable.
  const filter = ctx.createBiquadFilter()
  if (type === 'factory') { filter.type = 'lowpass'; filter.frequency.value = 700 }   // muffled, bass-heavy
  else if (type === 'outdoor') { filter.type = 'lowpass'; filter.frequency.value = 1200 } // airy whoosh
  else { filter.type = 'bandpass'; filter.frequency.value = 1500; filter.Q.value = 0.7 } // bright, mid-forward

  source.connect(filter)
  filter.connect(gain)
  gain.connect(ctx.destination)
  source.start()

  return { source, gain, filter }
}

export default function NoiseDemo() {
  const [active, setActive] = useState(false)
  const [noiseType, setNoiseType] = useState('factory')
  const ctxRef = useRef(null)
  const noiseRef = useRef(null)

  const toggle = useCallback(() => {
    if (active) {
      // Stop
      if (noiseRef.current) {
        try { noiseRef.current.source.stop() } catch {}
        noiseRef.current = null
      }
      if (ctxRef.current) {
        ctxRef.current.close()
        ctxRef.current = null
      }
      setActive(false)
    } else {
      // Start
      const ctx = new (window.AudioContext || window.webkitAudioContext)()
      ctxRef.current = ctx
      noiseRef.current = createNoise(ctx, noiseType)
      setActive(true)
    }
  }, [active, noiseType])

  const changeType = (type) => {
    setNoiseType(type)
    if (active && ctxRef.current) {
      // Restart with new type
      if (noiseRef.current) try { noiseRef.current.source.stop() } catch {}
      noiseRef.current = createNoise(ctxRef.current, type)
    }
  }

  return (
    <div className="noise-demo">
      <div className="row" style={{ alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <button
          className={`btn ${active ? 'rose' : ''}`}
          onClick={toggle}
          style={{ padding: '8px 14px', fontSize: '0.8rem' }}>
          {active ? '🔊 Stop Noise' : '🔇 Simulate Noise'}
        </button>
        {NOISE_TYPES.map(n => (
          <button
            key={n.key}
            className={`qchip ${noiseType === n.key ? 'active-chip' : ''}`}
            onClick={() => changeType(n.key)}
            title={n.desc}
            style={noiseType === n.key ? { borderColor: 'var(--amber)', color: 'var(--amber)' } : {}}>
            {n.label}
          </button>
        ))}
      </div>
      {active && (
        <div className="muted mono" style={{ fontSize: '0.72rem', marginTop: 6 }}>
          ▶ Playing {NOISE_TYPES.find(n => n.key === noiseType)?.desc} — speak into mic to test voice capture accuracy
        </div>
      )}
    </div>
  )
}
