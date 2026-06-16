# VoxField — Voice-First AI Assistant for Field Workers

> **Speak. Inspect. Done.** — hands-free intelligence for industrial field technicians who can't look at a screen.

A field technician can complete a full inspection report, query equipment history, and
escalate a fault — **entirely by voice** — in under three minutes. Built for noisy
industrial environments where screens and keyboards are unusable.

---

## What it does

| Feature | How VoxField delivers it |
|---|---|
| **Domain-aware voice capture** | Push-to-talk speech, primed with the asset registry vocabulary — equipment codes (`PMP-4471`), procedure names, locations. **Hybrid:** Google Cloud Speech-to-Text when online (noise-robust, vocabulary-biased), browser Web Speech when offline. English / Hindi / Spanish. |
| **Structured data extraction** | A voice note becomes a structured work order: *inspection result, fault code, location, severity, action taken, parts required* — via Gemini (Vertex AI). |
| **Voice query answering** | Ask about specs, maintenance history, or procedures → answered from the knowledge base and **spoken back** in the same language, in well under 3 seconds. |
| **Work order integration** | Create / update / close work orders by voice, with **spoken confirmation** ("Work order 12 created for PMP-4471") in a natural Cloud TTS voice (browser TTS offline). |
| **Offline capability** | Voice notes & commands queue locally (IndexedDB) when offline and **auto-sync on reconnect**. Speech automatically falls back to the on-device browser engine. Text-confirm fallback guarantees content. |
| **Supervisor dashboard** | Live web view: field worker activity, work-order status, voice transcripts, and **exception alerts** for high/critical faults. |

The knowledge base ships seeded with **40 industrial assets** across 11 types
(pumps, motors, valves, compressors, generators, HVAC, heat exchangers, tanks,
pressure vessels, transformers, switchgear) — each with specs, procedures, and history.

---

## Architecture

```
┌─────────────────────────┐        REST / JSON        ┌───────────────────────────┐
│  Frontend (React PWA)    │ ────────────────────────► │  Backend (FastAPI)         │
│  • Worker voice terminal │                           │  • Work order CRUD         │
│  • Supervisor dashboard  │ ◄──────────────────────── │  • /extract  /query        │
│  • Hybrid speech:        │                           │  • /stt  /tts  (cloud)     │
│    cloud online /        │                           │  • /dashboard  /stats      │
│    browser offline       │                           │  • AI + speech (below)     │
│  • IndexedDB offline q    │                          │  • SQLite database         │
└─────────────────────────┘                           └───────────────────────────┘
                                                                    │
                                          ┌─────────────────────────┴─────────────────────────┐
                                          │  Google Cloud (one service-account credential):     │
                                          │   • LLM  → Vertex AI (Gemini 2.5 Flash)             │
                                          │   • STT  → Cloud Speech-to-Text   (online only)     │
                                          │   • TTS  → Cloud Text-to-Speech   (online only)     │
                                          │  Fallbacks: AI Studio key → rule-based; browser     │
                                          │  Web Speech for STT/TTS when offline.               │
                                          └─────────────────────────────────────────────────────┘
```

- **Frontend:** React + Vite, installable **PWA**. **Hybrid speech** — Google Cloud
  STT/TTS when online (records mic audio → backend → Cloud Speech), automatically falling
  back to the browser **Web Speech API** + **SpeechSynthesis** when offline. Industrial-HMI
  UI with dark + light themes.
- **Backend:** Python + FastAPI + SQLite. Plain SQL (no ORM) — trivial to read and to
  migrate to Postgres later if needed.
- **AI (LLM):** Google **Gemini** for extraction + Q&A, behind a clean interface with a
  layered fallback chain: **Vertex AI** (service-account, no rate limits) →
  **AI Studio key** (free tier) → **rule-based** (offline / no credentials). The active
  backend is reported at `GET /ai-status`.
- **Speech:** **Google Cloud Speech-to-Text** (vocabulary-biased with the asset codes for
  accuracy in noise) and **Text-to-Speech** (natural Neural2 voices). Gated by
  `USE_CLOUD_SPEECH`; status at `GET /speech-status`. The browser engine is the offline
  fallback, so **offline capability is preserved**.

---

## Quick start

### Prerequisites
- **Python 3.10+** and **Node.js 18+**
- A browser with Web Speech support: **Chrome or Edge** (desktop or Android)

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # then configure ONE of the AI options below
python -m uvicorn main:app --port 8000
```

The database auto-creates and seeds 40 assets on first run.
API docs: http://127.0.0.1:8000/docs

#### AI configuration (pick one; all are optional)

VoxField works out of the box with **no credentials** (rule-based fallback, browser
speech). For full quality, configure `backend/.env` with one of:

**Option A — Google Cloud service-account (best: no rate limits + Cloud STT/TTS)**
1. In Google Cloud Console (billing enabled): create a **service account**, download its
   **JSON key**, and save it as `backend/gcp-credentials.json` *(already gitignored)*.
2. Enable the **Vertex AI API**, **Cloud Speech-to-Text API**, and **Cloud
   Text-to-Speech API** on the project.
3. In `.env`:
   ```
   USE_VERTEX=true
   GOOGLE_APPLICATION_CREDENTIALS=gcp-credentials.json
   VERTEX_LOCATION=us-central1
   VERTEX_MODEL=gemini-2.5-flash
   USE_CLOUD_SPEECH=true          # enables Cloud STT/TTS when online
   ```
   The project ID is read automatically from the JSON.

**Option B — AI Studio API key (simplest, free tier)**
1. Get a free key at https://aistudio.google.com → "Get API key".
2. In `.env`: `GEMINI_API_KEY=...` and `GEMINI_MODEL=gemini-2.5-flash`.
   (Free tier is rate-limited to a few requests/min; the app falls back to rule-based when
   throttled.)

> **Security:** never commit `.env` or `gcp-credentials.json` — both are gitignored. A
> service-account key is a powerful secret; if it is ever exposed, rotate it in the GCP
> console (delete the key, create a new one).

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
7. Open DevTools → **Network → Offline**. The status pill flips to **Offline**, and the
   speech pill switches from **`🎙 cloud voice`** to **`🎙 browser`** automatically.
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
| Transcription accuracy in a noisy environment | Speak a report with background noise in Chrome. Online uses Cloud STT (vocabulary-biased toward equipment codes for accuracy); the transcript appears and is editable. |
| Structured extraction maps all required fields | Step 1 above — all six fields populate from one spoken sentence. |
| Voice query returns correct answer **< 3 s** | Step 3 — the answer card shows the measured `elapsed_ms` (typically single/double-digit ms locally). |
| Work order creation → correct backend record | After step 1, check `GET /work-orders` or the supervisor dashboard for the structured row. |
| Offline queue syncs & processes all notes | Steps 7–9 — queued items sync automatically on reconnect; confirmed in the dashboard. |

---

## Project layout

```
Voice AI/
├── backend/
│   ├── main.py            # FastAPI app + all routes (incl. /stt /tts /ai-status)
│   ├── db.py              # SQLite connection + schema
│   ├── seed.py            # 40 industrial assets + specs/procedures/history
│   ├── ai_engine.py       # LLM: Vertex AI → AI Studio → rule-based fallback
│   ├── speech_cloud.py    # Cloud Speech-to-Text + Text-to-Speech (online)
│   ├── knowledge.py       # asset retrieval for Q&A
│   ├── requirements.txt
│   ├── .env.example       # config template (copy to .env)
│   └── gcp-credentials.json   # your service-account JSON (gitignored — you add this)
├── frontend/
│   ├── src/
│   │   ├── pages/        Worker.jsx, Supervisor.jsx
│   │   ├── lib/          speech (browser + cloud), api, offlineQueue,
│   │   │                 useConnectivity, useTheme, useReveal
│   │   ├── components/   Reveal.jsx
│   │   └── styles.css    industrial-HMI design system (dark + light)
│   └── vite.config.js    PWA config + dev proxy
└── README.md
```

## Notes & limitations (honest)
- **Hybrid speech by design:** Cloud STT/TTS need internet, so when offline the app falls
  back to the browser engine. This keeps the **offline capability** intact while giving
  better accuracy and natural voices online.
- **Voice still needs Chrome or Edge** — the offline browser fallback uses the Web Speech
  API, which isn't reliable in Firefox/Safari. The app detects this and shows a notice.
- **Cloud STT/TTS require a billing-enabled GCP project.** Without cloud credentials the
  app uses browser speech only; without any LLM credentials it uses the rule-based
  extractor (English-tuned).
- **SQLite** is ideal for this scale and for demos (zero setup). For a multi-writer cloud
  deployment, swap the DB layer to Postgres — the SQL is standard.

## Deployment (optional)
- **Frontend:** `npm run build` → deploy `frontend/dist/` to any static host (Vercel/Netlify).
  Set `VITE_API_BASE` to the backend URL.
- **Backend:** deploy to a real-server host (Render / Railway / Fly.io) with a persistent
  disk for the SQLite file. Provide the AI credentials via the host's environment/secrets:
  either `GEMINI_API_KEY`, or the service-account JSON + `USE_VERTEX=true` /
  `USE_CLOUD_SPEECH=true` (mount the JSON as a secret file and point
  `GOOGLE_APPLICATION_CREDENTIALS` at it). **Never bake credentials into the image.**
