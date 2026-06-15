import { useEffect, useRef, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api.js'
import { listen, speak, speechSupported, LANGUAGES } from '../lib/speech.js'
import { useRevealGroup } from '../lib/useReveal.js'
import { useTheme } from '../lib/useTheme.js'
import { useConnectivity } from '../lib/useConnectivity.js'
import * as queue from '../lib/offlineQueue.js'
import { RevealCard } from '../components/Reveal.jsx'

const TECH = 'R. Mehta' // demo technician identity

const MODES = [
  { key: 'report', label: '📋 Report' },
  { key: 'ask', label: '❓ Ask' },
  { key: 'orders', label: '🛠 Work Orders' },
]

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

const FIELD_LABELS = {
  asset_code: 'Equipment',
  inspection_result: 'Inspection',
  fault_code: 'Fault code',
  location: 'Location',
  severity: 'Severity',
  action_taken: 'Action taken',
  parts_required: 'Parts required',
}

export default function Worker() {
  const [mode, setMode] = useState('report')
  const [lang, setLang] = useState('en-US')
  const [listening, setListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [extracted, setExtracted] = useState(null)
  const [answer, setAnswer] = useState(null)
  const [orders, setOrders] = useState([])
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState('')
  const [supported] = useState(speechSupported())
  const [aiEngine, setAiEngine] = useState(null)
  const [stats, setStats] = useState(null)
  const [feed, setFeed] = useState([])
  const [pending, setPending] = useState(0)
  const [syncing, setSyncing] = useState(false)
  const [textNote, setTextNote] = useState('')   // offline text-confirm fallback
  const stopRef = useRef(null)
  const gridRef = useRevealGroup()
  const { theme, toggle } = useTheme()

  const refreshPending = useCallback(async () => {
    setPending(await queue.pendingCount())
  }, [])

  // Process one queued item against the backend. Throws on failure (stays queued).
  const processItem = useCallback(async (item) => {
    const p = item.payload
    if (item.type === 'create_wo') {
      // Re-extract at sync time so Gemini (if available) does the smart parsing.
      const ex = await api.extract(item.transcript, TECH, p.language)
      const f = ex.fields
      return api.createWorkOrder({
        asset_code: f.asset_code, inspection_result: f.inspection_result,
        fault_code: f.fault_code, location: f.location, severity: f.severity,
        action_taken: f.action_taken, parts_required: f.parts_required,
        raw_transcript: item.transcript, technician: TECH,
      })
    }
    if (item.type === 'query') return api.query(p.question, TECH, p.language)
    if (item.type === 'update_wo') return api.updateWorkOrder(p.id, p.patch)
    if (item.type === 'close_wo') return api.closeWorkOrder(p.id)
    throw new Error('Unknown queued action: ' + item.type)
  }, [])

  const syncQueue = useCallback(async () => {
    setSyncing(true)
    try {
      const { synced, failed } = await queue.drain(processItem)
      await queue.clearDone()
      await refreshPending()
      if (synced > 0) {
        showToast(`Synced ${synced} queued ${synced === 1 ? 'item' : 'items'}.`)
        refreshHome(); if (mode === 'orders') refreshOrders()
      }
      if (failed > 0) showToast(`${failed} item(s) failed to sync — will retry.`)
    } finally { setSyncing(false) }
  }, [processItem, refreshPending, mode])

  const { online } = useConnectivity(syncQueue)

  useEffect(() => {
    api.aiStatus().then(s => setAiEngine(s.engine)).catch(() => setAiEngine('offline'))
    if ('speechSynthesis' in window) window.speechSynthesis.getVoices()
    refreshHome()
    refreshPending()
  }, [refreshPending])

  useEffect(() => { if (mode === 'orders') refreshOrders() }, [mode])

  function refreshHome() {
    api.stats().then(setStats).catch(() => {})
    api.activity(6).then(setFeed).catch(() => {})
  }

  function showToast(msg) { setToast(msg); setTimeout(() => setToast(''), 3200) }

  function refreshOrders() {
    api.listWorkOrders().then(setOrders).catch(() => showToast('Could not load work orders'))
  }

  function toggleListen() {
    if (listening) { stopRef.current && stopRef.current(); return }
    setTranscript(''); setExtracted(null); setAnswer(null)
    setListening(true)
    stopRef.current = listen({
      lang,
      continuous: false,
      onResult: (text) => setTranscript(text),
      onEnd: (finalText) => { setListening(false); if (finalText) handleFinal(finalText) },
      onError: (e) => { setListening(false); showToast('Mic error: ' + (e.error || e.message || 'unknown')) },
    })
  }

  async function handleFinal(text) {
    if (mode === 'ask') return doQuery(text)
    return doExtract(text)
  }

  // Quick-action chip: jump to Ask mode and answer a sample question by voice-equivalent.
  function runQuickQuery(q) {
    setMode('ask'); setExtracted(null); setTranscript(q); doQuery(q)
  }

  async function doExtract(text) {
    // Offline: queue the raw note now; it will be extracted + filed on reconnect.
    if (!online) {
      await queue.enqueue('create_wo', { language: lang.split('-')[0] }, text)
      await refreshPending()
      const msg = 'Offline — report queued. It will sync when you reconnect.'
      speak(msg, lang); showToast(msg)
      setTranscript(''); setExtracted(null)
      return
    }
    setBusy(true)
    try {
      const res = await api.extract(text, TECH, lang.split('-')[0])
      setExtracted(res.fields)
    } catch (e) {
      // Network failed mid-request — fall back to queueing.
      await queue.enqueue('create_wo', { language: lang.split('-')[0] }, text)
      await refreshPending()
      showToast('Connection lost — report queued for sync.')
      setTranscript('')
    } finally { setBusy(false) }
  }

  async function doQuery(text) {
    // Queries need the backend (knowledge base + AI). Offline: queue it.
    if (!online) {
      await queue.enqueue('query', { question: text, language: lang.split('-')[0] }, text)
      await refreshPending()
      const msg = 'Offline — your question is queued and will be answered on reconnect.'
      speak(msg, lang); showToast(msg)
      return
    }
    setBusy(true)
    try {
      const res = await api.query(text, TECH, lang.split('-')[0])
      setAnswer(res)
      speak(res.answer, lang) // speak the answer back in the same language
    } catch (e) {
      await queue.enqueue('query', { question: text, language: lang.split('-')[0] }, text)
      await refreshPending()
      showToast('Connection lost — question queued.')
    } finally { setBusy(false) }
  }

  async function confirmWorkOrder() {
    if (!extracted) return
    setBusy(true)
    try {
      const res = await api.createWorkOrder({
        asset_code: extracted.asset_code,
        inspection_result: extracted.inspection_result,
        fault_code: extracted.fault_code,
        location: extracted.location,
        severity: extracted.severity,
        action_taken: extracted.action_taken,
        parts_required: extracted.parts_required,
        raw_transcript: transcript,
        technician: TECH,
      })
      speak(res.confirmation, lang)        // verbal confirmation
      showToast(res.confirmation)
      setExtracted(null); setTranscript(''); refreshHome()
    } catch (e) {
      // Queue the confirmed fields so nothing is lost if the network drops.
      await queue.enqueue('create_wo', { language: lang.split('-')[0] }, transcript || extracted.inspection_result || '')
      await refreshPending()
      showToast('Connection lost — work order queued for sync.')
      setExtracted(null); setTranscript('')
    } finally { setBusy(false) }
  }

  async function closeOrder(id) {
    if (!online) {
      await queue.enqueue('close_wo', { id })
      await refreshPending()
      const msg = `Offline — close request for WO ${id} queued.`
      speak(msg, lang); showToast(msg)
      return
    }
    try {
      const res = await api.closeWorkOrder(id)
      speak(res.confirmation, lang)
      showToast(res.confirmation)
      refreshOrders(); refreshHome()
    } catch (e) {
      await queue.enqueue('close_wo', { id }); await refreshPending()
      showToast('Connection lost — close request queued.')
    }
  }

  // Offline text-confirm fallback: file a typed note when voice/STT isn't available offline.
  async function submitTextNote() {
    const text = textNote.trim()
    if (!text) return
    await queue.enqueue(mode === 'ask' ? 'query' : 'create_wo',
      mode === 'ask' ? { question: text, language: lang.split('-')[0] } : { language: lang.split('-')[0] },
      text)
    await refreshPending()
    setTextNote('')
    const msg = 'Note queued. It will sync when you reconnect.'
    showToast(msg); speak(msg, lang)
  }

  const micLabel = listening ? '● Recording — tap to stop'
    : mode === 'ask' ? 'Tap to query equipment'
    : mode === 'report' ? 'Tap to log inspection'
    : 'Tap to record'

  return (
    <div className="shell">
      <div className="topbar glass-accent">
        <div className="brand">
          <div className="logo">◉</div>
          <div>
            <h1>VOXFIELD</h1>
            <div className="tag">Field Voice Terminal</div>
          </div>
        </div>
        <div className="row" style={{ gap: 10, flexWrap: 'nowrap' }}>
          <select className="lang" value={lang} onChange={e => setLang(e.target.value)} aria-label="Language">
            {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
          <button className="icon-btn" onClick={toggle} aria-label="Toggle dark mode"
            title={theme === 'dark' ? 'Switch to light' : 'Switch to dark'}>
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </div>
      </div>

      {!supported && (
        <RevealCard className="center">
          <strong style={{ color: 'var(--rose)' }}>Voice not supported in this browser.</strong>
          <p className="muted">Please open VoxField in <b>Chrome</b> or <b>Edge</b> for speech features.</p>
        </RevealCard>
      )}

      {/* Stats strip */}
      {stats && (
        <div className="stats stagger">
          <div className="card stat reveal"><div className="num">{stats.assets}</div><div className="lbl">Assets</div></div>
          <div className="card stat reveal"><div className="num">{stats.open_work_orders}</div><div className="lbl">Open WOs</div></div>
          <div className={`card stat reveal ${stats.critical_open ? 'alert' : ''}`}><div className="num">{stats.critical_open}</div><div className="lbl">Critical</div></div>
          <div className="card stat reveal"><div className="num">{stats.voice_notes}</div><div className="lbl">Voice notes</div></div>
        </div>
      )}

      {/* Mode tabs */}
      <div className="tabs">
        {MODES.map(m => (
          <button key={m.key}
            className={`tab ${mode === m.key ? 'active' : ''}`}
            onClick={() => { setMode(m.key); setExtracted(null); setAnswer(null); setTranscript('') }}>
            {m.label}
          </button>
        ))}
      </div>

      {/* Big mic */}
      {mode !== 'orders' && (
        <div className="mic-wrap">
          <button
            className={`mic-btn ${listening ? 'listening' : ''}`}
            onClick={toggleListen}
            disabled={!supported || busy}
            aria-label="Push to talk">
            {listening ? '⏸' : '🎤'}
          </button>
          <div className="mic-label">{busy ? 'Processing…' : micLabel}</div>
          <div className="statusbar">
            <span className="pill"><span className={`dot ${online ? 'online' : 'offline'}`} />
              {online ? 'Online' : 'Offline'}</span>
            {aiEngine && <span className="pill">🧠 {aiEngine}</span>}
            {pending > 0 && (
              <button className="pill" style={{ borderColor: 'var(--amber)', color: 'var(--amber)', cursor: online ? 'pointer' : 'default' }}
                onClick={() => online && syncQueue()} title={online ? 'Tap to sync now' : 'Will sync when online'}>
                {syncing ? '⟳ syncing…' : `⧖ ${pending} queued`}
              </button>
            )}
          </div>

          {/* Quick-action chips — guide the worker / demo voice features */}
          {!transcript && !answer && (
            <div className="qchips" style={{ marginTop: 18 }}>
              <button className="qchip" onClick={() => runQuickQuery('What are the specs of pump PMP-4471?')}>🔧 Specs of PMP-4471</button>
              <button className="qchip" onClick={() => runQuickQuery('When was the last maintenance on GEN-9001?')}>🕑 GEN-9001 history</button>
              <button className="qchip" onClick={() => runQuickQuery('How do I clean the condenser tubes on the chiller?')}>📋 Chiller procedure</button>
            </div>
          )}

          {/* Offline text-confirm fallback — guarantees a queued note has content */}
          {!online && (
            <div className="row" style={{ marginTop: 16, width: '100%', maxWidth: 520, justifyContent: 'center' }}>
              <input
                value={textNote}
                onChange={e => setTextNote(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') submitTextNote() }}
                placeholder={mode === 'ask' ? 'Type a question to queue…' : 'Type a note to queue…'}
                style={{
                  flex: 1, minWidth: 200, fontFamily: 'var(--mono)', fontSize: '0.9rem',
                  padding: '12px 14px', borderRadius: 'var(--radius-sm)', color: 'var(--ink)',
                  background: 'var(--bg-2)', border: '1px solid var(--edge)'
                }} />
              <button className="btn" onClick={submitTextNote}>Queue</button>
            </div>
          )}
        </div>
      )}

      {/* Live transcript */}
      {transcript && mode !== 'orders' && (
        <RevealCard className="bignote">
          <div className="field"><span className="k">You said</span></div>
          <p style={{ marginTop: 8 }}>{transcript}</p>
        </RevealCard>
      )}

      {/* Extracted fields -> confirm work order (Report mode) */}
      {extracted && mode === 'report' && (
        <RevealCard>
          <h3 style={{ marginBottom: 8 }}>Work order preview</h3>
          {Object.keys(FIELD_LABELS).map(k => (
            <div className="field" key={k}>
              <span className="k">{FIELD_LABELS[k]}</span>
              <span className="v">
                {k === 'severity' && extracted[k]
                  ? <span className={`chip ${extracted[k]}`}>{extracted[k]}</span>
                  : (extracted[k] || <span className="muted">—</span>)}
              </span>
            </div>
          ))}
          <div className="row" style={{ marginTop: 16 }}>
            <button className="btn primary" onClick={confirmWorkOrder} disabled={busy}>✓ Create work order</button>
            <button className="btn" onClick={() => { setExtracted(null); setTranscript('') }}>Discard</button>
          </div>
        </RevealCard>
      )}

      {/* Spoken answer (Ask mode) */}
      {answer && mode === 'ask' && (
        <RevealCard>
          <div className="field">
            <span className="k">Answer</span>
            <span className="pill">⚡ {answer.elapsed_ms} ms</span>
          </div>
          <p className="bignote" style={{ marginTop: 10 }}>{answer.answer}</p>
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn teal" onClick={() => speak(answer.answer, lang)}>🔊 Repeat</button>
            {answer.asset_code && <span className="pill" style={{ alignSelf: 'center' }}>📦 {answer.asset_code}</span>}
          </div>
        </RevealCard>
      )}

      {/* Work orders list */}
      {mode === 'orders' && (
        <div ref={gridRef}>
          <RevealCard>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <h3>My work orders</h3>
              <button className="btn" onClick={refreshOrders}>↻ Refresh</button>
            </div>
          </RevealCard>
          {orders.length === 0 && (
            <RevealCard className="center muted">No work orders yet. Create one from the Report tab.</RevealCard>
          )}
          {orders.map(o => (
            <RevealCard key={o.id}>
              <div className="field">
                <span className="k">WO #{o.id} · {o.asset_code || 'unassigned'}</span>
                <span>
                  {o.severity && <span className={`chip ${o.severity}`} style={{ marginRight: 6 }}>{o.severity}</span>}
                  <span className={`chip ${o.status}`}>{o.status.replace('_', ' ')}</span>
                </span>
              </div>
              <p style={{ margin: '8px 0' }}>{o.inspection_result || '—'}</p>
              {o.parts_required && <p className="muted">Parts: {o.parts_required}</p>}
              {o.status !== 'closed' && (
                <button className="btn rose" style={{ marginTop: 10 }} onClick={() => closeOrder(o.id)}>
                  ✓ Close work order
                </button>
              )}
            </RevealCard>
          ))}
        </div>
      )}

      {/* Recent activity feed — only on the home (no active transcript/answer) */}
      {mode !== 'orders' && !transcript && !answer && !extracted && feed.length > 0 && (
        <RevealCard style={{ marginTop: 18 }}>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="section-title">⚡ Recent activity</div>
            <button className="btn" style={{ padding: '8px 14px', fontSize: '0.85rem' }} onClick={refreshHome}>↻</button>
          </div>
          <div style={{ marginTop: 6 }}>
            {feed.map((f, i) => (
              <div className="feed-item" key={i}>
                <div className="feed-icon">{ICONS[f.intent] || '🗒'}</div>
                <div className="feed-text">
                  <div className="t">{f.transcript}</div>
                  <div className="m">{LABELS[f.intent] || 'Note'} · {f.technician || 'field'} · {timeAgo(f.created_at)}</div>
                </div>
              </div>
            ))}
          </div>
        </RevealCard>
      )}

      <RevealCard className="center" style={{ marginTop: 20 }}>
        <Link className="navlink" to="/supervisor">Supervisor dashboard →</Link>
      </RevealCard>

      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
