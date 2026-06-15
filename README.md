# VoxField — Voice-First AI Assistant for Field Workers

> **Speak. Inspect. Done.** — hands-free intelligence for industrial field technicians who can't look at a screen.

A field technician can complete a full inspection report, query equipment history, and
escalate a fault — **entirely by voice** — in under three minutes. Built for noisy
industrial environments where screens and keyboards are unusable.

---

## What it does

| Feature | How VoxField delivers it |
|---|---|
| **Domain-aware voice capture** | Browser speech recognition (push-to-talk), primed with the asset registry vocabulary — equipment codes (`PMP-4471`), procedure names, locations. English / Hindi / Spanish. |
| **Structured data extraction** | A voice note becomes a structured work order: *inspection result, fault code, location, severity, action taken, parts required.* |
| **Voice query answering** | Ask about specs, maintenance history, or procedures → answered from the knowledge base and **spoken back** in the same language, in well under 3 seconds. |
| **Work order integration** | Create / update / close work orders by voice, with **spoken confirmation** ("Work order 12 created for PMP-4471"). |
| **Offline capability** | Voice notes & commands queue locally (IndexedDB) when offline and **auto-sync on reconnect**. Text-confirm fallback guarantees content. |
| **Supervisor dashboard** | Live web view: field worker activity, work-order status, voice transcripts, and **exception alerts** for high/critical faults. |

The knowledge base ships seeded with **40 industrial assets** across 11 types
(pumps, motors, valves, compressors, generators, HVAC, heat exchangers, tanks,
pressure vessels, transformers, switchgear) — each with specs, procedures, and history.

---

## Architecture

```
┌────────────────────────┐         REST / JSON        ┌──────────────────────────┐
│  Frontend (React PWA)   │ ─────────────────────────► │  Backend (FastAPI)        │
│  • Worker voice terminal│                            │  • Work order CRUD        │
│  • Supervisor dashboard │ ◄───────────────────────── │  • /extract  /query       │
│  • Web Speech STT + TTS │                            │  • /dashboard  /stats     │
│  • IndexedDB offline q  │                            │  • AI engine (see below)  │
└────────────────────────┘                            │  • SQLite database        │
                                                       └──────────────────────────┘
                                                                   │
                                              ┌────────────────────┴───────────────────┐
                                              │  AI engine: Gemini (primary)            │
                                              │  + rule-based fallback (offline/no key) │
                                              └─────────────────────────────────────────┘
```

- **Frontend:** React + Vite, installable **PWA**. Voice via the browser **Web Speech API**
  (speech-to-text) and **SpeechSynthesis** (text-to-speech) — free, no API key, works in
  Chrome/Edge. Industrial-HMI UI with dark + light themes.
- **Backend:** Python + FastAPI + SQLite. Plain SQL (no ORM) — trivial to read and to
  migrate to Postgres later if needed.
- **AI:** Google **Gemini** (`gemini-2.0-flash`, free tier) for extraction + Q&A, behind a
  clean interface with a **rule-based fallback** so the app works with no key and offline.

---

## Quick start

### Prerequisites
- **Python 3.10+** and **Node.js 18+**
- A browser with Web Speech support: **Chrome or Edge** (desktop or Android)

### 1. Backend

```bash
cd backend
pip install -r requirements.txt

# (optional but recommended) add a free Gemini key for best quality + full multi-language:
#   1. get a key at https://aistudio.google.com  ->  "Get API key"
#   2. copy the template and paste your key:
cp .env.example .env        # then edit .env and set GEMINI_API_KEY=...
# Without a key it still works using the rule-based fallback.

python -m uvicorn main:app --port 8000
```

The database auto-creates and seeds 40 assets on first run.
API docs: http://127.0.0.1:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in Chrome/Edge.
- Worker terminal: `/`
- Supervisor dashboard: `/supervisor`

(The dev server proxies `/api/*` to the backend on port 8000 automatically.)

---

## 3-minute demo script

> Run backend + frontend, open the worker terminal in Chrome, allow microphone access.

**0:00 — Inspect (create a work order by voice)**
1. Stay on the **Report** tab, tap the mic, and say:
   > *"Found cooling water pump PMP-4471 in pump house bay two leaking from the seal,
   > severity high, I replaced the mechanical seal, need a new gasket and seal kit."*
2. The extracted fields appear (equipment, location, severity, action, parts).
   Tap **Create work order** → it speaks *"Work order N created for PMP-4471, severity high."*

**0:45 — Query equipment history (voice answer in <3s)**
3. Switch to the **Ask** tab, tap the mic, and say:
   > *"When was the last maintenance on PMP-4471?"*
4. VoxField speaks the answer aloud and shows the response time (e.g. `12 ms`).
   (Try the quick-action chips too, e.g. "Specs of PMP-4471".)

**1:30 — Escalate a fault (critical)**
5. Back on **Report**, say:
   > *"Generator GEN-9001 will not start on test, fuel solenoid suspected, severity critical."*
6. Create the work order. This becomes an **exception alert**.

**2:00 — Offline → sync (the resilience story)**
7. Open DevTools → **Network → Offline**. The status pill flips to **Offline**.
8. Record another report (or type one in the offline box). It shows **`⧖ 1 queued`**.
9. Turn the network back **Online** → the queue **auto-syncs** and announces *"Synced 1 item."*

**2:30 — Supervisor view**
10. Open **`/supervisor`** in another tab. The LIVE dashboard shows the new work orders,
    the **CRITICAL** GEN-9001 alert at top, active technicians, and all voice transcripts —
    refreshing live.

---

## Success metrics — how to verify each

| Metric | How to demo / verify |
|---|---|
| Transcription accuracy in a noisy environment | Speak a report with background noise in Chrome; the transcript appears and is editable. |
| Structured extraction maps all required fields | Step 1 above — all six fields populate from one spoken sentence. |
| Voice query returns correct answer **< 3 s** | Step 3 — the answer card shows the measured `elapsed_ms` (typically single/double-digit ms locally). |
| Work order creation → correct backend record | After step 1, check `GET /work-orders` or the supervisor dashboard for the structured row. |
| Offline queue syncs & processes all notes | Steps 7–9 — queued items sync automatically on reconnect; confirmed in the dashboard. |

---

## Project layout

```
Voice AI/
├── backend/
│   ├── main.py          # FastAPI app + all routes
│   ├── db.py            # SQLite connection + schema
│   ├── seed.py          # 40 industrial assets + specs/procedures/history
│   ├── ai_engine.py     # Gemini + rule-based extraction & Q&A
│   ├── knowledge.py     # asset retrieval for Q&A
│   ├── requirements.txt
│   └── .env.example     # template for the Gemini key (copy to .env)
├── frontend/
│   ├── src/
│   │   ├── pages/        Worker.jsx, Supervisor.jsx
│   │   ├── lib/          speech, api, offlineQueue, useConnectivity, useTheme, useReveal
│   │   ├── components/   Reveal.jsx
│   │   └── styles.css    industrial-HMI design system (dark + light)
│   └── vite.config.js    PWA config + dev proxy
└── README.md
```

## Notes & limitations (honest)
- **Voice features need Chrome or Edge** — the Web Speech API isn't reliable in Firefox/Safari.
  The app detects this and shows a notice.
- **Full multi-language extraction/Q&A** is best with a Gemini key set; the offline
  rule-based fallback is tuned for English.
- **SQLite** is ideal for this scale and for demos (zero setup). For a multi-writer cloud
  deployment, swap the DB layer to Postgres — the SQL is standard.

## Deployment (optional)
- **Frontend:** `npm run build` → deploy `frontend/dist/` to any static host (Vercel/Netlify).
  Set `VITE_API_BASE` to the backend URL.
- **Backend:** deploy to a real-server host (Render / Railway / Fly.io) with a persistent
  disk for the SQLite file. Set `GEMINI_API_KEY` in the host's environment.
