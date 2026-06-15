import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api.js'
import { useTheme } from '../lib/useTheme.js'
import { RevealCard } from '../components/Reveal.jsx'

const ICONS = { create_wo: '🛠', close_wo: '✅', update_wo: '✏️', query: '❓', note: '🗒' }
const LABELS = { create_wo: 'Work order', close_wo: 'Closed WO', update_wo: 'Updated WO', query: 'Question', note: 'Note' }

function timeAgo(iso) {
  try {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000
    if (diff < 60) return 'just now'
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return `${Math.floor(diff / 86400)}d ago`
  } catch { return '' }
}

export default function Supervisor() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(false)
  const [filter, setFilter] = useState('all')   // work-order status filter
  const [live, setLive] = useState(true)
  const { theme, toggle } = useTheme()
  const timer = useRef(null)

  function load() {
    api.dashboard().then(d => { setData(d); setErr(false) }).catch(() => setErr(true))
  }

  useEffect(() => {
    load()
    if (live) timer.current = setInterval(load, 4000)  // live polling
    return () => clearInterval(timer.current)
  }, [live])

  const s = data?.stats
  const orders = (data?.work_orders || []).filter(o => filter === 'all' ? true
    : filter === 'open' ? o.status !== 'closed' : o.status === filter)

  return (
    <div className="shell" style={{ maxWidth: 1080 }}>
      <div className="topbar glass-accent">
        <div className="brand">
          <div className="logo">▣</div>
          <div>
            <h1>VOXFIELD · OPS</h1>
            <div className="tag">Supervisor Control Center</div>
          </div>
        </div>
        <div className="row" style={{ gap: 10, flexWrap: 'nowrap', alignItems: 'center' }}>
          <button className="pill" onClick={() => setLive(l => !l)}
            style={{ borderColor: live ? 'var(--green)' : 'var(--edge)', color: live ? 'var(--green)' : 'var(--ink-soft)' }}>
            <span className={`dot ${live ? 'online' : 'offline'}`} /> {live ? 'LIVE' : 'PAUSED'}
          </button>
          <button className="icon-btn" onClick={toggle} title="Toggle theme">{theme === 'dark' ? '☀️' : '🌙'}</button>
        </div>
      </div>

      {err && <RevealCard className="center"><strong style={{ color: 'var(--red)' }}>Backend unreachable.</strong>
        <p className="muted">Start the API server, then this will reconnect automatically.</p></RevealCard>}

      {/* Stats */}
      {s && (
        <div className="stats stagger" style={{ gridTemplateColumns: 'repeat(6, 1fr)' }}>
          <div className="card stat reveal"><div className="num">{s.assets}</div><div className="lbl">Assets</div></div>
          <div className="card stat reveal"><div className="num">{s.open_work_orders}</div><div className="lbl">Open</div></div>
          <div className="card stat reveal"><div className="num">{s.closed_work_orders}</div><div className="lbl">Closed</div></div>
          <div className={`card stat reveal ${s.critical_open ? 'alert' : ''}`}><div className="num">{s.critical_open}</div><div className="lbl">Alerts</div></div>
          <div className="card stat reveal"><div className="num">{s.active_technicians}</div><div className="lbl">Techs</div></div>
          <div className="card stat reveal"><div className="num">{s.voice_notes}</div><div className="lbl">Notes</div></div>
        </div>
      )}

      {/* Exception alerts — most important, surfaced at top */}
      {data?.alerts?.length > 0 && (
        <RevealCard style={{ borderColor: 'var(--red)', boxShadow: '0 0 24px rgba(255,90,110,0.25)' }}>
          <div className="section-title" style={{ color: 'var(--red)' }}>⚠ EXCEPTION ALERTS — {data.alerts.length}</div>
          {data.alerts.map(a => (
            <div className="field" key={a.id}>
              <span>
                <span className={`chip ${a.severity}`} style={{ marginRight: 8 }}>{a.severity}</span>
                <b className="mono">{a.asset_code || '—'}</b> · {a.inspection_result || 'No detail'}
              </span>
              <span className="muted mono" style={{ fontSize: '0.74rem' }}>{a.technician} · {timeAgo(a.created_at)}</span>
            </div>
          ))}
        </RevealCard>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 14, marginTop: 14 }}
        className="dash-grid">

        {/* Work orders */}
        <RevealCard>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div className="section-title">🛠 Work Orders</div>
            <div className="tabs" style={{ margin: 0 }}>
              {['all', 'open', 'closed'].map(f => (
                <button key={f} className={`tab ${filter === f ? 'active' : ''}`}
                  style={{ padding: '7px 12px', fontSize: '0.72rem' }} onClick={() => setFilter(f)}>{f}</button>
              ))}
            </div>
          </div>
          {orders.length === 0 && <p className="muted center" style={{ padding: 20 }}>No work orders.</p>}
          {orders.map(o => (
            <div className="field" key={o.id}>
              <span style={{ minWidth: 0 }}>
                <b className="mono">WO-{String(o.id).padStart(3, '0')}</b> · <span className="mono">{o.asset_code || 'unassigned'}</span>
                <div className="muted" style={{ fontSize: '0.82rem', marginTop: 2 }}>{o.inspection_result || '—'}</div>
              </span>
              <span style={{ whiteSpace: 'nowrap' }}>
                {o.severity && <span className={`chip ${o.severity}`} style={{ marginRight: 6 }}>{o.severity}</span>}
                <span className={`chip ${o.status}`}>{o.status.replace('_', ' ')}</span>
              </span>
            </div>
          ))}
        </RevealCard>

        {/* Right column: technicians + transcripts */}
        <div>
          <RevealCard>
            <div className="section-title">👷 Field Activity</div>
            {(!data?.technicians || data.technicians.length === 0) &&
              <p className="muted center" style={{ padding: 14 }}>No active technicians yet.</p>}
            {data?.technicians?.map(t => (
              <div className="field" key={t.technician}>
                <span><span className="dot online" style={{ marginRight: 8 }} /><b>{t.technician}</b></span>
                <span className="muted mono" style={{ fontSize: '0.74rem' }}>{t.notes} notes · {timeAgo(t.last_seen)}</span>
              </div>
            ))}
          </RevealCard>

          <RevealCard style={{ marginTop: 14 }}>
            <div className="section-title">🗒 Voice Transcripts</div>
            <div style={{ maxHeight: 360, overflowY: 'auto' }}>
              {(!data?.transcripts || data.transcripts.length === 0) &&
                <p className="muted center" style={{ padding: 14 }}>No transcripts yet.</p>}
              {data?.transcripts?.map(t => (
                <div className="feed-item" key={t.id}>
                  <div className="feed-icon">{ICONS[t.intent] || '🗒'}</div>
                  <div className="feed-text">
                    <div className="t">{t.transcript}</div>
                    <div className="m">{LABELS[t.intent] || 'Note'} · {t.technician || 'field'} · {timeAgo(t.created_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          </RevealCard>
        </div>
      </div>

      <RevealCard className="center" style={{ marginTop: 18 }}>
        <Link className="navlink" to="/">← Worker Terminal</Link>
      </RevealCard>
    </div>
  )
}
