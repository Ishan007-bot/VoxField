import { useState, useEffect } from 'react'

const DEFAULT_TECHNICIANS = [
  'R. Mehta',
  'A. Khan',
  'S. Patel',
  'J. Lopez',
]

// Custom technician names are persisted so they survive navigation/reloads
// and stay available in the dropdown after switching away.
function loadExtras() {
  try {
    const saved = JSON.parse(localStorage.getItem('voxfield-technicians') || '[]')
    return Array.isArray(saved) ? saved : []
  } catch { return [] }
}

export default function TechnicianSelect({ value, onChange }) {
  const [editing, setEditing] = useState(false)   // showing the custom-name input?
  const [customName, setCustomName] = useState('')
  // Custom names added (persisted so they stay in the dropdown across remounts).
  const [extras, setExtras] = useState(loadExtras)

  useEffect(() => {
    localStorage.setItem('voxfield-technicians', JSON.stringify(extras))
  }, [extras])

  // The dropdown always includes the defaults, any session-added names, AND the
  // current value (so a persisted/custom name shows as the selected option).
  const options = Array.from(new Set([
    ...DEFAULT_TECHNICIANS,
    ...extras,
    ...(value ? [value] : []),
  ]))

  function handleSelect(e) {
    const v = e.target.value
    if (v === '__custom__') {
      setCustomName('')
      setEditing(true)
    } else {
      onChange(v)
    }
  }

  function commitCustom() {
    const name = customName.trim()
    if (!name) { setEditing(false); return }
    if (!options.includes(name)) setExtras(prev => [...prev, name])
    onChange(name)        // tell the parent
    setCustomName('')
    setEditing(false)     // close the input — this is what was failing before
  }

  return (
    <div className="tech-select">
      <select
        className="lang"
        value={editing ? '__custom__' : value}
        onChange={handleSelect}
        aria-label="Technician"
        style={{ minWidth: 130 }}>
        {options.map(t => <option key={t} value={t}>{t}</option>)}
        <option value="__custom__">+ Other…</option>
      </select>

      {editing && (
        <div className="row" style={{ gap: 6, marginTop: 6 }}>
          <input
            value={customName}
            onChange={e => setCustomName(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') commitCustom()
              if (e.key === 'Escape') { setCustomName(''); setEditing(false) }
            }}
            placeholder="Enter name"
            autoFocus
            style={{
              fontFamily: 'var(--mono)', fontSize: '0.82rem',
              padding: '8px 10px', borderRadius: 'var(--radius-sm)',
              color: 'var(--ink)', background: 'var(--bg-2)',
              border: '1px solid var(--edge)', flex: 1,
            }}
          />
          <button className="btn" onClick={commitCustom}
            style={{ padding: '8px 12px', fontSize: '0.78rem' }}>OK</button>
        </div>
      )}
    </div>
  )
}
