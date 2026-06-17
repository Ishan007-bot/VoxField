import { useState, useRef, useCallback } from 'react'

// Simulated industrial noise for demonstrating voice capture in noisy environments.
// Uses Web Audio API to generate factory-like ambient noise (white noise + low rumble).
const NOISE_TYPES = [
  { key: 'factory', label: 'Factory Floor', desc: 'Machinery hum + impact noise' },
  { key: 'outdoor', label: 'Outdoor Wind', desc: 'Wind + ambient site noise' },
  { key: 'workshop', label: 'Workshop', desc: 'Tools + compressor noise' },
]

function createNoise(ctx, type) {
  const bufferSize = ctx.sampleRate * 2 // 2 seconds of noise
  const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate)
  const data = buffer.getChannelData(0)

  for (let i = 0; i < bufferSize; i++) {
    let sample = (Math.random() * 2 - 1) // white noise base

    if (type === 'factory') {
      // Add low-frequency rumble
      sample = sample * 0.3 + Math.sin(i / ctx.sampleRate * 2 * Math.PI * 60) * 0.15
      // Add periodic impact
      if (i % Math.floor(ctx.sampleRate * 0.8) < 200) sample += 0.4
    } else if (type === 'outdoor') {
      // Slower modulation for wind
      sample = sample * 0.2 * (0.5 + 0.5 * Math.sin(i / ctx.sampleRate * 2 * Math.PI * 0.3))
    } else {
      // Workshop: intermittent bursts
      sample = sample * 0.25
      if (Math.random() < 0.005) sample += (Math.random() - 0.5) * 0.6
    }
    data[i] = sample
  }

  const source = ctx.createBufferSource()
  source.buffer = buffer
  source.loop = true

  const gain = ctx.createGain()
  gain.gain.value = 0.35 // moderate volume

  // Low-pass filter to make it sound more realistic
  const filter = ctx.createBiquadFilter()
  filter.type = 'lowpass'
  filter.frequency.value = type === 'outdoor' ? 800 : 2000

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
