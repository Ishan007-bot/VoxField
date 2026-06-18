# VoxField — Voice-First AI Assistant for Field Workers

> **Speak. Inspect. Done.** — hands-free intelligence for industrial field technicians who can't look at a screen.

A field technician can complete a full inspection report, query equipment history, and
escalate a fault — **entirely by voice** — in under three minutes. Built for noisy
industrial environments where screens and keyboards are unusable.

---

## What it does

| Feature | How VoxField delivers it |
|---|---|
| **Domain-aware voice capture** | Push-to-talk + **continuous hands-free** speech capture with silence detection. Primed with asset vocabulary (equipment codes, procedures, locations). **Hybrid:** Google Cloud STT when online (noise-robust, vocabulary-biased), browser Web Speech when offline. English / Hindi / Spanish. **Noise simulation** demo to prove accuracy. |
| **Structured data extraction** | Voice note → structured work order: *inspection result, fault code, location, severity, action taken, parts required* — via Gemini (Vertex AI). **Per-field confidence scoring** with re-prompt on low confidence. |
| **Voice query answering** | Ask about specs, maintenance history, or procedures → answered from the knowledge base (asset-code + fuzzy retrieval) and **spoken back** in the same language. Response time displayed (well under 3 seconds). |
| **Work order integration** | Create / update / close work orders by voice, with **spoken confirmation**. Full CRUD with severity tracking. |
| **Fault escalation** | Say "escalate to supervisor" → auto-creates an escalation alert visible on the supervisor dashboard with real-time status (open → acknowledged → resolved). |
| **Offline capability** | Voice notes & commands queue locally (IndexedDB) when offline and **auto-sync on reconnect**. Speech falls back to on-device browser engine. Text-confirm fallback guarantees content. |
| **Supervisor dashboard** | Live web view: field worker activity, work-order status, voice transcripts, **exception alerts**, **escalation panel**, **analytics charts** (WO timeline, severity distribution). |

The knowledge base ships seeded with **40 industrial assets** across 11 types
(pumps, motors, valves, compressors, generators, HVAC, heat exchangers, tanks,
pressure vessels, transformers, switchgear) — each with specs, procedures, and history.

---

## Architecture

```
┌─────────────────────────┐        REST / JSON        ┌───────────────────────────┐
│  Frontend (React PWA)    │ ────────────────────────► │  Backend (FastAPI)         │
│  • Worker voice terminal │                           │  • Work order CRUD         │
│  • Supervisor dashboard  │ ◄──────────────────────── │  • Escalation management   │
│  • Hybrid speech:        │                           │  • /extract  /query        │
│    cloud online /        │                           │  • /stt  /tts  (cloud)     │
│    browser offline       │                           │  • /dashboard  /stats      │
│  • Continuous + PTT mode │                           │  • AI + speech             │
│  • IndexedDB offline q   │                           │  • SQLite database         │
└─────────────────────────┘                           └───────────────────────────┘
                                                                    │
                                          ┌─────────────────────────┴─────────────────────────┐
                                          │  AI / ML Stack:                                     │
                                          │   • LLM  → Vertex AI (Gemini 2.5 Flash)             │
                                          │   • STT  → Cloud Speech-to-Text   (online only)     │
                                          │   • TTS  → Cloud Text-to-Speech   (online only)     │
                                          │  Fallbacks: AI Studio key → rule-based; browser     │
                                          │  Web Speech for STT/TTS when offline.               │
                                          └─────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18 + Vite PWA, Recharts |
| **Backend** | Python + FastAPI + SQLite |
| **LLM** | Google Gemini (Vertex AI / AI Studio) with rule-based fallback |
| **Retrieval** | Asset-code match + rapidfuzz fuzzy search over the asset registry |
| **Speech** | Cloud STT/TTS + Web Speech API (hybrid) |
| **Offline** | IndexedDB + Service Worker (PWA) |
| **Testing** | pytest (extraction, API, offline sync) |

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

### 3. Run tests

```bash
cd backend
pytest test_extraction.py test_api.py test_offline_sync.py -v
```

Tests cover:
- **14 extraction accuracy tests** — 12 realistic voice transcripts + confidence + inspection result checks
- **20+ API endpoint tests** — assets, extraction, queries, work orders, escalations, dashboard
- **8 offline sync tests** — queue processing, order preservation, failure handling, retry

---

## 3-minute demo script

> Run backend + frontend, open the worker terminal in Chrome, allow microphone access.

**0:00 — Inspect (create a work order by voice)**
1. Stay on the **Report** tab, tap the mic, and say:
   > *"Found cooling water pump PMP-4471 in pump house bay two leaking from the seal,
   > severity high, I replaced the mechanical seal, need a new gasket and seal kit."*
2. The extracted fields appear with **confidence bars** showing per-field accuracy.
   Tap **Create work order** → it speaks *"Work order N created for PMP-4471, severity high."*

**0:30 — Test in noise (prove domain-aware capture)**
3. Click **Simulate Noise → Factory Floor** to play background machinery noise.
4. Speak another report — observe that Cloud STT (vocabulary-biased) still captures the equipment code accurately.

**0:45 — Query equipment history (voice answer in <3s)**
5. Switch to the **Ask** tab, tap the mic, and say:
   > *"When was the last maintenance on PMP-4471?"*
6. VoxField speaks the answer aloud and shows the response time (well under 3 seconds).

**1:15 — Escalate a fault**
7. Back on **Report**, say:
   > *"Escalate to supervisor, transformer TRF-100 Buchholz relay tripped, too dangerous to proceed."*
8. The escalation is auto-detected and sent to the supervisor dashboard.

**1:45 — Continuous listening mode**
9. Toggle from **Push-to-Talk** to **Continuous** mode.
10. Speak naturally — silence detection auto-segments your speech and processes each segment.

**2:00 — Offline → sync (the resilience story)**
11. Open DevTools → **Network → Offline**. The status pill flips to **Offline**, speech switches to browser engine.
12. Record a report (or type one). It shows **`⧖ 1 queued`**.
13. Turn the network back **Online** → auto-syncs and announces *"Synced 1 item."*

**2:30 — Supervisor view**
14. Open **`/supervisor`** — the LIVE dashboard shows:
    - **Escalation panel** with acknowledge button
    - **Exception alerts** for critical work orders
    - **Analytics charts** — WO timeline (bar chart) + severity distribution (pie chart)
    - **Per-technician activity** with note counts
    - **Voice transcripts** feed

---

## Success metrics — how to verify each

| Metric | How to demo / verify |
|---|---|
| **Transcription accuracy in noisy environment** | Enable noise simulation (Factory/Outdoor/Workshop), speak a report → Cloud STT captures accurately. Per-field confidence bars show extraction quality. Run `pytest test_extraction.py` for 12 transcript accuracy tests. |
| **Structured extraction maps all required fields** | Step 1 above — all 7 fields populate. Confidence bars show per-field scores. Extraction tests verify all fields across 12 voice samples. |
| **Voice query returns correct answer < 3 s** | Step 5 — answer card shows `elapsed_ms`. `test_api.py::TestQuery::test_query_response_time` asserts < 3s. |
| **Work order creation → correct backend record** | After step 1, `GET /work-orders` shows the structured row. `test_api.py::TestWorkOrders::test_work_order_correctly_structured` verifies all fields. |
| **Offline queue syncs & processes all notes** | Steps 11–13. `test_offline_sync.py` verifies: FIFO order, mixed success/failure, retry, and empty queue. |

---

## Core features mapping

| Assignment Feature | Implementation |
|---|---|
| Domain-Aware Voice Capture | Push-to-talk + continuous mode, Cloud STT with vocabulary boost, noise simulation demo |
| Structured Data Extraction | Gemini + rule-based fallback, 7 fields, confidence scoring, re-prompt on low confidence |
| Voice Query Answering | Asset-code + fuzzy keyword retrieval, spoken answers, < 3s response |
| Work Order Integration | Full CRUD by voice, verbal confirmation, multi-technician support |
| Offline Capability | IndexedDB queue, auto-sync, browser speech fallback, text-confirm fallback |
| Supervisor Dashboard | Live polling, exception alerts, escalation management, analytics charts, transcript feed |
| **Bonus: Escalation** | Voice-triggered escalation ("escalate to supervisor"), status tracking |
| **Bonus: Multi-language** | English, Hindi, Spanish (STT + TTS + extraction) |
| **Bonus: Multi-technician** | Technician selector, per-technician activity tracking |

---

## Project layout

```
VoxField/
├── backend/
│   ├── main.py              # FastAPI app + all routes
│   ├── db.py                # SQLite connection + schema (incl. escalations)
│   ├── seed.py              # 40 industrial assets + specs/procedures/history
│   ├── ai_engine.py         # LLM: Vertex AI → AI Studio → rule-based (w/ confidence)
│   ├── speech_cloud.py      # Cloud Speech-to-Text + Text-to-Speech
│   ├── knowledge.py         # Asset retrieval (code match → fuzzy)
│   ├── test_extraction.py   # 14 extraction accuracy tests
│   ├── test_api.py          # 20+ API endpoint tests
│   ├── test_offline_sync.py # 8 offline sync correctness tests
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/           Worker.jsx, Supervisor.jsx
│   │   ├── components/      Reveal, RetroMic, Charts, ConfidenceBar,
│   │   │                    NoiseDemo, TechnicianSelect, EscalationBadge
│   │   ├── lib/             speech (browser + cloud + continuous), api,
│   │   │                    offlineQueue, useConnectivity, useTheme, useReveal
│   │   └── styles.css       Industrial-HMI design system (dark + light)
│   └── vite.config.js       PWA config + dev proxy
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
