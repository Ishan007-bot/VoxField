// Per-field confidence indicator for extraction results.
// Shows a colored bar (green > 0.7, amber > 0.4, red otherwise)
// and nudges re-recording when confidence is low.

const FIELD_LABELS = {
  asset_code: 'Equipment',
  inspection_result: 'Inspection',
  fault_code: 'Fault code',
  location: 'Location',
  severity: 'Severity',
  action_taken: 'Action taken',
  parts_required: 'Parts required',
}

function barColor(v) {
  if (v >= 0.7) return 'var(--green)'
  if (v >= 0.4) return 'var(--amber)'
  return 'var(--red)'
}

export default function ConfidenceBar({ confidence, onReRecord }) {
  if (!confidence || typeof confidence !== 'object') return null

  const entries = Object.entries(confidence).filter(([k]) => k in FIELD_LABELS)
  if (entries.length === 0) return null

  const avg = entries.reduce((s, [, v]) => s + v, 0) / entries.length
  const lowFields = entries.filter(([, v]) => v < 0.5)

  return (
    <div className="confidence-panel">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span className="mono" style={{ fontSize: '0.72rem', color: 'var(--ink-soft)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          Extraction Confidence
        </span>
        <span className="pill" style={{
          borderColor: barColor(avg),
          color: barColor(avg),
        }}>
          {Math.round(avg * 100)}% avg
        </span>
      </div>

      <div className="confidence-bars">
        {entries.map(([field, value]) => (
          <div key={field} className="conf-row">
            <span className="conf-label">{FIELD_LABELS[field]}</span>
            <div className="conf-track">
              <div
                className="conf-fill"
                style={{
                  width: `${Math.round(value * 100)}%`,
                  background: barColor(value),
                }}
              />
            </div>
            <span className="conf-pct" style={{ color: barColor(value) }}>
              {Math.round(value * 100)}%
            </span>
          </div>
        ))}
      </div>

      {lowFields.length > 0 && onReRecord && (
        <div style={{ marginTop: 10 }}>
          <div className="muted" style={{ fontSize: '0.78rem', marginBottom: 6 }}>
            ⚠ Low confidence on: {lowFields.map(([k]) => FIELD_LABELS[k]).join(', ')}
          </div>
          <button className="btn" onClick={onReRecord}
            style={{ padding: '8px 14px', fontSize: '0.8rem', borderColor: 'var(--amber)', color: 'var(--amber)' }}>
            🎙 Re-record for better accuracy
          </button>
        </div>
      )}
    </div>
  )
}
