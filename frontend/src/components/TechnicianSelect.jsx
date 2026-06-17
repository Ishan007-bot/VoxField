import { useState } from 'react'

const DEFAULT_TECHNICIANS = [
  'R. Mehta',
  'A. Khan',
  'S. Patel',
  'J. Lopez',
]

export default function TechnicianSelect({ value, onChange }) {
  const [adding, setAdding] = useState(false)
  const [customName, setCustomName] = useState('')
  // Track any custom names added this session so they stay in the dropdown
  const [extras, setExtras] = useState([])

  const allTechs = [...DEFAULT_TECHNICIANS, ...extras]

  function handleSelect(e) {
    const v = e.target.value
    if (v === '__custom__') {
      setAdding(true)
    } else {
      setAdding(false)
      onChange(v)
    }
  }

  function handleCustomSubmit() {
    const name = customName.trim()
    if (!name) return
    // Add to extras if not already in the list
    if (!allTechs.includes(name)) {
      setExtras(prev => [...prev, name])
    }
    onChange(name)
    setAdding(false)
    setCustomName('')
  }

  // Is the current value in our list? If not (e.g. page reload), show it anyway
  const isKnown = allTechs.includes(value)

  return (
    <div className="tech-select">
      <select
        className="lang"
        value={adding ? '__custom__' : (isKnown ? value : '__custom__')}
        onChange={handleSelect}
        aria-label="Technician"
        style={{ minWidth: 130 }}>
        {allTechs.map(t => (
          <option key={t} value={t}>{t}</option>
        ))}
        <option value="__custom__">+ Other…</option>
      </select>
      {(adding || !isKnown) && (
        <div className="row" style={{ gap: 6, marginTop: 6 }}>
          <input
            value={customName || (!isKnown && !adding ? value : '')}
            onChange={e => setCustomName(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleCustomSubmit() }}
            placeholder="Enter name"
            autoFocus
            style={{
              fontFamily: 'var(--mono)', fontSize: '0.82rem',
              padding: '8px 10px', borderRadius: 'var(--radius-sm)',
              color: 'var(--ink)', background: 'var(--bg-2)',
              border: '1px solid var(--edge)', flex: 1,
            }}
          />
          <button className="btn" onClick={handleCustomSubmit}
            style={{ padding: '8px 12px', fontSize: '0.78rem' }}>OK</button>
        </div>
      )}
    </div>
  )
}
