import { useEffect, useRef, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api.js'
import { listen, listenContinuous, speak, speechSupported, LANGUAGES, unlockAudio,
         recordAudio, cloudTranscribe, cloudSpeak, cloudSpeechAvailable } from '../lib/speech.js'
import { useRevealGroup } from '../lib/useReveal.js'
import { useTheme } from '../lib/useTheme.js'
import { useConnectivity } from '../lib/useConnectivity.js'
import * as queue from '../lib/offlineQueue.js'
import { RevealCard } from '../components/Reveal.jsx'
import RetroMic from '../components/RetroMic.jsx'
import ConfidenceBar from '../components/ConfidenceBar.jsx'
import TechnicianSelect from '../components/TechnicianSelect.jsx'
import NoiseDemo from '../components/NoiseDemo.jsx'

const MODES = [
  { key: 'report', label: 'Report', ico: '📋' },
  { key: 'ask', label: 'Ask', ico: '❓' },
  { key: 'orders', label: 'Work Orders', ico: '🛠' },
]

const ICONS = { create_wo: '🛠', close_wo: '✅', update_wo: '✏️', query: '❓', note: '🗒', escalate: '🚨' }
const LABELS = { create_wo: 'Work order', close_wo: 'Closed WO', update_wo: 'Updated WO', query: 'Question', note: 'Note', escalate: 'Escalation' }

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
  const [continuous, setContinuous] = useState(false)  // continuous listening mode
  const [transcript, setTranscript] = useState('')
  const [extracted, setExtracted] = useState(null)
  const [confidence, setConfidence] = useState(null)
  const [answer, setAnswer] = useState(null)
  const [orders, setOrders] = useState([])
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState('')
  const [supported] = useState(speechSupported())
  const [aiEngine, setAiEngine] = useState(null)
  const [cloudSpeech, setCloudSpeech] = useState(false)
  const [stats, setStats] = useState(null)
  const [feed, setFeed] = useState([])
  const [pending, setPending] = useState(0)
  const [failed, setFailed] = useState(0)   // queue items that exhausted auto-retry
  const [syncing, setSyncing] = useState(false)
  const [textNote, setTextNote] = useState('')
  // Persist the selected technician so it survives navigating away and back.
  const [technician, setTechnician] = useState(() => localStorage.getItem('voxfield-technician') || 'R. Mehta')
  const stopRef = useRef(null)
  const gridRef = useRevealGroup()
  const { theme, toggle } = useTheme()

  const refreshPending = useCallback(async () => {
    setPending(await queue.pendingCount())
    setFailed(await queue.errorCount())
  }, [])

  const processItem = useCallback(async (item) => {
    const p = item.payload
    if (item.type === 'create_wo') {
      const ex = await api.extract(item.transcript, technician, p.language)
      const f = ex.fields
      return api.createWorkOrder({
        asset_code: f.asset_code, inspection_result: f.inspection_result,
        fault_code: f.fault_code, location: f.location, severity: f.severity,
        action_taken: f.action_taken, parts_required: f.parts_required,
        raw_transcript: item.transcript, technician,
      })
    }
    if (item.type === 'query') return api.query(p.question, technician, p.language)
    if (item.type === 'update_wo') return api.updateWorkOrder(p.id, p.patch)
    if (item.type === 'close_wo') return api.closeWorkOrder(p.id)
    if (item.type === 'escalate') return api.createEscalation({
      asset_code: p.asset_code, reason: p.reason, location: p.location,
      severity: p.severity || 'critical', technician,
    })
    throw new Error('Unknown queued action: ' + item.type)
  }, [technician])

  const syncQueue = useCallback(async () => {
    setSyncing(true)
    try {
      const { synced, retrying, failed } = await queue.drain(processItem)
      await queue.clearDone()
      await refreshPending()
      if (synced > 0) {
        showToast(`Synced ${synced} queued ${synced === 1 ? 'item' : 'items'}.`)
        refreshHome(); if (mode === 'orders') refreshOrders()
      }
      // Honest status: transient failures retry automatically; only items that
      // exhausted their attempts ask the worker to retry by hand.
      if (failed > 0) showToast(`${failed} item(s) couldn't sync after several tries — tap the queue to retry.`)
      else if (retrying > 0) showToast(`${retrying} item(s) didn't sync — retrying automatically.`)
    } finally { setSyncing(false) }
  }, [processItem, refreshPending, mode])

  // Manual retry of items that exhausted auto-retry: re-arm them, then sync.
  const retrySync = useCallback(async () => {
    await queue.retryErrored()
    await refreshPending()
    await syncQueue()
  }, [refreshPending, syncQueue])

  const { online } = useConnectivity(syncQueue)

  useEffect(() => {
    api.aiStatus().then(s => setAiEngine(s.engine)).catch(() => setAiEngine('offline'))
    cloudSpeechAvailable().then(setCloudSpeech).catch(() => setCloudSpeech(false))
    if ('speechSynthesis' in window) window.speechSynthesis.getVoices()
    refreshHome()
    refreshPending()
  }, [refreshPending])

  // Remember the technician across navigation/reloads.
  useEffect(() => { localStorage.setItem('voxfield-technician', technician) }, [technician])

  function say(text) {
    if (online && cloudSpeech) {
      cloudSpeak(text, lang, (reason) => {
        showToast('Using browser voice (cloud TTS: ' + reason + ')')
      })
    } else speak(text, lang)
  }

  const useCloud = online && cloudSpeech

  useEffect(() => { if (mode === 'orders') refreshOrders() }, [mode])

  function refreshHome() {
    api.stats().then(setStats).catch(() => {})
    api.activity(6).then(setFeed).catch(() => {})
  }

  async function deleteNote(id) {
    setFeed(f => f.filter(n => n.id !== id))
    try { await api.deleteNote(id) } catch { /* ignore */ }
    refreshHome()
  }

  async function clearActivity() {
    if (!window.confirm('Clear all recent activity? This cannot be undone.')) return
    setFeed([])
    try { await api.clearNotes(); showToast('Activity cleared.') } catch { showToast('Could not clear activity') }
    refreshHome()
  }

  function showToast(msg) { setToast(msg); setTimeout(() => setToast(''), 3200) }

  function refreshOrders() {
    api.listWorkOrders().then(setOrders).catch(() => showToast('Could not load work orders'))
  }

  async function toggleListen() {
    unlockAudio()
    if (listening) { stopRef.current && stopRef.current(); setListening(false); return }
    setTranscript(''); setExtracted(null); setAnswer(null); setConfidence(null)
    setListening(true)

    // Continuous mode (browser speech only — silence-detected segmentation)
    if (continuous && !useCloud) {
      const ctrl = listenContinuous({
        lang,
        silenceMs: 2500,
        onResult: (text) => setTranscript(text),
        onSegment: (text) => {
          setListening(false)
          if (text) handleFinal(text)
        },
        onError: (e) => { setListening(false); showToast('Mic error: ' + (e.error || e.message || 'unknown')) },
      })
      stopRef.current = ctrl.stop
      return
    }

    if (useCloud) {
      const rec = await recordAudio({
        onStop: async (blob) => {
          setListening(false); setBusy(true)
          try {
            const { transcript: text, confidence: sttConf } = await cloudTranscribe(blob, lang)
            setTranscript(text)
            if (text) await handleFinal(text)
          } catch (e) {
            showToast('Cloud STT failed, retry or go offline for browser mode.')
          } finally { setBusy(false) }
        },
        onError: (e) => { setListening(false); showToast('Mic error: ' + (e.message || 'unknown')) },
      })
      stopRef.current = rec.stop
      return
    }

    // Push-to-talk browser mode
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

  function runQuickQuery(q) {
    unlockAudio()
    setMode('ask'); setExtracted(null); setTranscript(q); doQuery(q)
  }

  async function doExtract(text) {
    if (!online) {
      await queue.enqueue('create_wo', { language: lang.split('-')[0] }, text)
      await refreshPending()
      const msg = 'Offline — report queued. It will sync when you reconnect.'
      speak(msg, lang); showToast(msg)
      setTranscript(''); setExtracted(null); setConfidence(null)
      return
    }
    setBusy(true)
    try {
      const res = await api.extract(text, technician, lang.split('-')[0])
      setExtracted(res.fields)
      setConfidence(res.confidence || null)

      // Auto-escalate if intent is escalate
      if (res.fields.intent === 'escalate') {
        await handleEscalation(res.fields, text)
      }
    } catch (e) {
      await queue.enqueue('create_wo', { language: lang.split('-')[0] }, text)
      await refreshPending()
      showToast('Connection lost — report queued for sync.')
      setTranscript('')
    } finally { setBusy(false) }
  }

  async function handleEscalation(fields, rawTranscript) {
    try {
      const res = await api.createEscalation({
        asset_code: fields.asset_code,
        reason: fields.inspection_result || rawTranscript,
        location: fields.location,
        severity: fields.severity || 'critical',
        technician,
      })
      const msg = res.confirmation
      say(msg)
      showToast(msg)
      refreshHome()
    } catch {
      await queue.enqueue('escalate', {
        asset_code: fields.asset_code, reason: fields.inspection_result,
        location: fields.location, severity: fields.severity,
      }, rawTranscript)
      await refreshPending()
      showToast('Offline — escalation queued.')
    }
  }

  async function doQuery(text) {
    if (!online) {
      await queue.enqueue('query', { question: text, language: lang.split('-')[0] }, text)
      await refreshPending()
      const msg = 'Offline — your question is queued and will be answered on reconnect.'
      speak(msg, lang); showToast(msg)
      return
    }
    setBusy(true)
    try {
      const res = await api.query(text, technician, lang.split('-')[0])
      setAnswer(res)
      say(res.answer)
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
        technician,
      })
      say(res.confirmation)
      showToast(res.confirmation)
      setExtracted(null); setTranscript(''); setConfidence(null); refreshHome()
    } catch (e) {
      await queue.enqueue('create_wo', { language: lang.split('-')[0] }, transcript || extracted.inspection_result || '')
      await refreshPending()
      showToast('Connection lost — work order queued for sync.')
      setExtracted(null); setTranscript(''); setConfidence(null)
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
      say(res.confirmation)
      showToast(res.confirmation)
      refreshOrders(); refreshHome()
    } catch (e) {
      await queue.enqueue('close_wo', { id }); await refreshPending()
      showToast('Connection lost — close request queued.')
    }
  }

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

  // Re-record handler for low confidence
  function handleReRecord() {
    setExtracted(null); setConfidence(null); setTranscript('')
    showToast('Speak again clearly for better accuracy.')
  }

  const micLabel = listening
    ? (continuous ? '● Continuous — tap to stop' : '● Recording — tap to stop')
    : mode === 'ask' ? 'Tap to query equipment'
    : mode === 'report' ? 'Tap to log inspection'
    : 'Tap to record'

  const setModeReset = (k) => { setMode(k); setExtracted(null); setAnswer(null); setTranscript(''); setConfidence(null) }

  return (
    <div className="app">
      {/* ---------- Sidebar (desktop) ---------- */}
      <aside className="sidebar">
        <div className="brand"><span className="bar" /><h1>VOXFIELD</h1></div>
        <div className="brand-sub">Field Voice Terminal</div>
        <nav className="nav">
          {MODES.map(m => (
            <button key={m.key} className={`nav-item ${mode === m.key ? 'active' : ''}`} onClick={() => setModeReset(m.key)}>
              <span className="ico">{m.ico}</span>{m.label}
            </button>
          ))}
          <Link className="nav-item" to="/supervisor"><span className="ico">📊</span>Supervisor</Link>
        </nav>
        <button className="cta" onClick={() => setModeReset('report')}><span className="ico">＋</span>New Capture</button>
      </aside>

      {/* ---------- Main ---------- */}
      <div className="main">
        <header className="appbar">
          <div className="left">
            <span className="pill"><span className={`dot ${online ? 'online' : 'offline'}`} />{online ? 'System Online' : 'Offline'}</span>
            {aiEngine && <span className="pill">🧠 {aiEngine}</span>}
            <span className="pill" title="Speech engine in use">🎙 {useCloud ? 'cloud voice' : 'browser'}</span>
            {(pending > 0 || failed > 0) && (
              <button className="pill"
                style={{ borderColor: failed ? 'var(--red)' : 'var(--amber)', color: failed ? 'var(--red)' : 'var(--amber)', cursor: online ? 'pointer' : 'default' }}
                onClick={() => online && (failed ? retrySync() : syncQueue())}
                title={online ? (failed ? 'Tap to retry failed items' : 'Tap to sync now') : 'Will sync when online'}>
                {syncing ? '⟳ syncing…' : failed ? `⚠ ${failed} failed — retry` : `⧖ ${pending} queued`}
              </button>
            )}
          </div>
          <div className="right">
            <TechnicianSelect value={technician} onChange={setTechnician} />
            <select className="lang" value={lang} onChange={e => setLang(e.target.value)} aria-label="Language">
              {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
            </select>
            <button className="icon-btn" onClick={toggle} aria-label="Toggle dark mode"
              title={theme === 'dark' ? 'Switch to light' : 'Switch to dark'}>
              {theme === 'dark' ? '☀️' : '🌙'}
            </button>
          </div>
        </header>

        <div className="content">
          {/* ===== Central stage ===== */}
          <section className="stage">
            <div className="blob a" /><div className="blob b" />

            {!supported && (
              <div className="card center" style={{ maxWidth: 460, marginBottom: 20 }}>
                <strong style={{ color: 'var(--red)' }}>Voice not supported in this browser.</strong>
                <p className="muted">Please open VoxField in <b>Chrome</b> or <b>Edge</b> for speech features.</p>
              </div>
            )}

            {/* Voice hearth (Report/Ask modes) */}
            {mode !== 'orders' && (
              <div className="mic-wrap">
                <div className="hearth">
                  <span className="ring r1" /><span className="ring r2" /><span className="ring r3" />
                  <button className={`mic-btn ${listening ? 'listening' : ''}`} onClick={toggleListen}
                    disabled={!supported || busy} aria-label={continuous ? 'Continuous listening' : 'Push to talk'}>
                    {listening ? <span style={{ fontSize: '2.6rem', lineHeight: 1 }}>⏹</span> : <RetroMic size={72} />}
                  </button>
                </div>
                <h2 className="hero">{busy ? 'Processing' : listening ? 'Listening now' : 'Ready to listen'}<span style={{ color: 'var(--primary)', fontWeight: 700 }}>.</span></h2>
                <div className="hero-sub">{micLabel}</div>
                <div className="viz"><span/><span/><span/><span/><span/><span/></div>

                {/* Continuous / PTT toggle */}
                <div className="qchips" style={{ marginTop: 20 }}>
                  <button className="qchip" onClick={() => setContinuous(false)}
                    style={!continuous ? { borderColor: 'var(--primary)', color: 'var(--primary)' } : {}}>Push-to-Talk</button>
                  <button className="qchip" onClick={() => setContinuous(true)}
                    style={continuous ? { borderColor: 'var(--primary)', color: 'var(--primary)' } : {}}>Continuous</button>
                </div>

                {/* Quick-action chips */}
                {!transcript && !answer && (
                  <div className="qchips" style={{ marginTop: 14 }}>
                    <button className="qchip" onClick={() => runQuickQuery('What are the specs of pump PMP-4471?')}>🔧 Specs of PMP-4471</button>
                    <button className="qchip" onClick={() => runQuickQuery('When was the last maintenance on GEN-9001?')}>🕑 GEN-9001 history</button>
                    <button className="qchip" onClick={() => runQuickQuery('How do I clean the condenser tubes on the chiller?')}>📋 Chiller procedure</button>
                  </div>
                )}

                {/* Noise simulation demo */}
                {!transcript && !answer && (
                  <div style={{ marginTop: 16, width: '100%', maxWidth: 520 }}><NoiseDemo /></div>
                )}

                {/* Offline text fallback */}
                {!online && (
                  <div className="row" style={{ marginTop: 16, width: '100%', maxWidth: 520, justifyContent: 'center' }}>
                    <input value={textNote} onChange={e => setTextNote(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') submitTextNote() }}
                      placeholder={mode === 'ask' ? 'Type a question to queue…' : 'Type a note to queue…'}
                      style={{ flex: 1, minWidth: 200, fontFamily: 'var(--mono)', fontSize: '0.9rem', padding: '12px 14px',
                               borderRadius: 'var(--radius-sm)', color: 'var(--ink)', background: 'var(--bg-2)', border: '1px solid var(--edge)' }} />
                    <button className="btn" onClick={submitTextNote}>Queue</button>
                  </div>
                )}

                {/* Live transcript */}
                {transcript && (
                  <div className="card reveal visible bignote" style={{ marginTop: 18, width: '100%', maxWidth: 560, textAlign: 'left' }}>
                    <div className="field"><span className="k">You said</span></div>
                    <p style={{ marginTop: 8 }}>{transcript}</p>
                  </div>
                )}

                {/* Extracted -> confirm (Report) */}
                {extracted && mode === 'report' && (
                  <div className="card reveal visible" style={{ marginTop: 16, width: '100%', maxWidth: 560, textAlign: 'left' }}>
                    <h3 style={{ marginBottom: 8 }}>{extracted.intent === 'escalate' ? '🚨 Escalation detected' : 'Work order preview'}</h3>
                    {Object.keys(FIELD_LABELS).map(k => (
                      <div className="field" key={k}>
                        <span className="k">{FIELD_LABELS[k]}</span>
                        <span className="v">
                          {k === 'severity' && extracted[k] ? <span className={`chip ${extracted[k]}`}>{extracted[k]}</span> : (extracted[k] || <span className="muted">—</span>)}
                        </span>
                      </div>
                    ))}
                    <ConfidenceBar confidence={confidence} onReRecord={handleReRecord} />
                    <div className="row" style={{ marginTop: 16 }}>
                      <button className="btn primary" onClick={confirmWorkOrder} disabled={busy}>✓ {extracted.intent === 'escalate' ? 'Also create work order' : 'Create work order'}</button>
                      <button className="btn" onClick={() => { setExtracted(null); setTranscript(''); setConfidence(null) }}>{extracted.intent === 'escalate' ? 'Done' : 'Discard'}</button>
                    </div>
                  </div>
                )}

                {/* Spoken answer (Ask) */}
                {answer && mode === 'ask' && (
                  <div className="card reveal visible" style={{ marginTop: 16, width: '100%', maxWidth: 560, textAlign: 'left' }}>
                    <div className="field">
                      <span className="k">Answer</span>
                      <span className="row" style={{ gap: 6 }}>
                        <span className="pill">⚡ {answer.elapsed_ms} ms</span>
                        {answer.retrieval && <span className="pill" title="Knowledge retrieval method">🔍 {answer.retrieval}</span>}
                      </span>
                    </div>
                    <p className="bignote" style={{ marginTop: 10 }}>{answer.answer}</p>
                    <div className="row" style={{ marginTop: 14 }}>
                      <button className="btn teal" onClick={() => say(answer.answer)}>🔊 Repeat</button>
                      {answer.asset_code && <span className="pill" style={{ alignSelf: 'center' }}>📦 {answer.asset_code}</span>}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Work orders list (fills the stage in orders mode) */}
            {mode === 'orders' && (
              <div ref={gridRef} style={{ width: '100%', maxWidth: 620, alignSelf: 'stretch' }}>
                <div className="row" style={{ justifyContent: 'space-between', marginBottom: 14 }}>
                  <h2 className="hero" style={{ fontSize: '1.6rem' }}>Work Orders</h2>
                  <button className="btn" onClick={refreshOrders}>↻ Refresh</button>
                </div>
                {orders.length === 0 && <div className="card center muted reveal visible">No work orders yet. Create one from Report.</div>}
                {orders.map(o => (
                  <div className="card reveal visible" key={o.id} style={{ marginBottom: 12 }}>
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
                      <button className="btn rose" style={{ marginTop: 10 }} onClick={() => closeOrder(o.id)}>✓ Close work order</button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* ===== Right context column ===== */}
          <aside className="context">
            {stats && (
              <div>
                <div className="section-title">📈 Overview</div>
                <div className="stats">
                  <div className="card stat"><div className="num">{stats.assets}</div><div className="lbl">Assets</div></div>
                  <div className="card stat"><div className="num">{stats.open_work_orders}</div><div className="lbl">Open WOs</div></div>
                  <div className={`card stat ${stats.critical_open ? 'alert' : ''}`}><div className="num">{stats.critical_open}</div><div className="lbl">Critical</div></div>
                  <div className="card stat"><div className="num">{stats.voice_notes}</div><div className="lbl">Voice notes</div></div>
                </div>
              </div>
            )}

            {feed.length > 0 && (
              <div className="card">
                <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                  <div className="section-title" style={{ marginBottom: 0 }}>⚡ Recent activity</div>
                  <div className="row" style={{ gap: 8 }}>
                    <button className="btn" style={{ padding: '7px 12px', fontSize: '0.8rem' }} onClick={refreshHome} title="Refresh">↻</button>
                    <button className="btn" style={{ padding: '7px 12px', fontSize: '0.8rem', color: 'var(--red)' }} onClick={clearActivity} title="Clear all">Clear</button>
                  </div>
                </div>
                <div style={{ marginTop: 8 }}>
                  {feed.map((f) => (
                    <div className="feed-item" key={f.id}>
                      <div className="feed-icon">{ICONS[f.intent] || '🗒'}</div>
                      <div className="feed-text">
                        <div className="t">{f.transcript}</div>
                        <div className="m">{LABELS[f.intent] || 'Note'} · {f.technician || 'field'} · {timeAgo(f.created_at)}</div>
                      </div>
                      <button className="feed-del" onClick={() => deleteNote(f.id)} title="Delete" aria-label="Delete note">✕</button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </aside>
        </div>

        <footer className="statusfoot">
          <span>{online ? '☁ Cloud Synced' : '⚠ Offline — queue active'}{(pending > 0) ? ` · ${pending} queued` : ''}</span>
          <span>VOXFIELD · {useCloud ? 'Cloud Speech' : 'Browser Speech'}</span>
        </footer>
      </div>

      {/* ---------- Bottom bar (mobile) ---------- */}
      <nav className="bottombar">
        {MODES.map(m => (
          <button key={m.key} className={mode === m.key ? 'active' : ''} onClick={() => setModeReset(m.key)}>
            <span className="ico">{m.ico}</span>{m.label}
          </button>
        ))}
        <Link to="/supervisor" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 3, textDecoration: 'none', color: 'var(--ink-soft)', fontFamily: 'var(--display)', fontSize: '0.66rem', fontWeight: 700 }}>
          <span className="ico" style={{ fontSize: '1.25rem' }}>📊</span>Super
        </Link>
      </nav>

      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
