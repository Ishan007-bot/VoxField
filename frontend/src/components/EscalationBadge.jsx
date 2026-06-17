// Escalation alert badge and panel for both Worker and Supervisor views.

function timeAgo(iso) {
  try {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000
    if (diff < 60) return 'just now'
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return `${Math.floor(diff / 86400)}d ago`
  } catch { return '' }
}

export function EscalationAlert({ escalation, onAcknowledge }) {
  const e = escalation
  return (
    <div className="escalation-item">
      <div className="field">
        <span>
          <span className="chip critical" style={{ marginRight: 8 }}>
            {e.severity || 'critical'}
          </span>
          <b className="mono">{e.asset_code || '—'}</b>
        </span>
        <span className="muted mono" style={{ fontSize: '0.74rem' }}>
          {e.technician} · {timeAgo(e.created_at)}
        </span>
      </div>
      {e.reason && <p style={{ margin: '6px 0', fontSize: '0.88rem' }}>{e.reason}</p>}
      {e.location && <p className="muted" style={{ fontSize: '0.78rem' }}>📍 {e.location}</p>}
      {e.status === 'open' && onAcknowledge && (
        <button className="btn" onClick={() => onAcknowledge(e.id)}
          style={{ marginTop: 8, padding: '7px 14px', fontSize: '0.78rem', borderColor: 'var(--amber)', color: 'var(--amber)' }}>
          ✓ Acknowledge
        </button>
      )}
      {e.status === 'acknowledged' && (
        <span className="pill" style={{ marginTop: 8, borderColor: 'var(--amber)', color: 'var(--amber)' }}>
          Acknowledged
        </span>
      )}
      {e.status === 'resolved' && (
        <span className="pill" style={{ marginTop: 8, borderColor: 'var(--green)', color: 'var(--green)' }}>
          Resolved
        </span>
      )}
    </div>
  )
}

export function EscalationPanel({ escalations, onAcknowledge }) {
  if (!escalations || escalations.length === 0) return null

  const open = escalations.filter(e => e.status === 'open')

  return (
    <div className="escalation-panel" style={{
      borderColor: 'var(--red)',
      boxShadow: '0 0 24px rgba(255,90,110,0.25)',
    }}>
      <div className="section-title" style={{ color: 'var(--red)' }}>
        🚨 ESCALATIONS — {open.length} open
      </div>
      {escalations.map(e => (
        <EscalationAlert key={e.id} escalation={e} onAcknowledge={onAcknowledge} />
      ))}
    </div>
  )
}
