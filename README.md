<div align="center">

# 🎙️ VoxField
### Voice-First AI Assistant for Field Workers

**_Speak. Inspect. Done._**

Hands-free intelligence for industrial field technicians who cannot look at a screen.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-vox--field.vercel.app-2563eb)](https://vox-field.vercel.app/)
[![Frontend](https://img.shields.io/badge/Frontend-React%20PWA-61dafb)]()
[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688)]()
[![AI](https://img.shields.io/badge/AI-Gemini%20%7C%20Vertex%20AI-orange)]()

</div>

---

## 📑 Table of Contents
1. [Problem Statement](#-problem-statement)
2. [Objectives](#-objectives)
3. [Solution Overview](#-solution-overview)
4. [Core Features](#-core-features)
5. [System Architecture](#-system-architecture)
6. [Technology Stack](#-technology-stack)
7. [Installation & Setup](#-installation--setup)
8. [How to Use / Demo Script](#-how-to-use--demo-script)
9. [Results & Success Metrics](#-results--success-metrics)
10. [Testing](#-testing)
11. [Project Structure](#-project-structure)
12. [Limitations](#-limitations)
13. [Future Scope](#-future-scope)
14. [Team](#-team)

---

## 🎯 Problem Statement

In industrial field environments — factories, plants, cell towers, substations — paper-based
data capture is still the norm because **screens and keyboards are unusable**: workers wear
gloves, their hands are occupied, the environment is noisy, and they often can't safely look
away from equipment.

> **The challenge:** A field technician should be able to complete a full inspection report,
> query equipment history, and escalate a fault — **entirely by voice** — in **under three minutes**.

This project builds a **voice-first field assistant** that delivers continuous speech capture,
domain-aware transcription, structured data extraction from voice, voice-query answering, and
backend system integration.

---

## 🎓 Objectives

- Capture a technician's spoken inspection notes **hands-free**, even in noisy conditions.
- **Understand domain vocabulary** — equipment codes (`PMP-4471`), technical terms, procedure names.
- **Extract structured work orders** from messy natural speech (severity, action taken, parts, etc.).
- **Answer equipment questions by voice** from a knowledge base, spoken back in natural speech, **in < 3 seconds**.
- **Create / update / close work orders** by voice with verbal confirmation.
- Work **offline** — queue notes when disconnected, sync automatically on reconnect.
- Provide a **supervisor dashboard** for real-time oversight.

---

## 💡 Solution Overview

**VoxField** is an installable **Progressive Web App (PWA)** paired with a **FastAPI** backend
and **Google Gemini** (via Vertex AI). A technician taps one button, speaks, and the system:

1. Transcribes the speech (cloud STT online, on-device browser STT offline),
2. Uses an LLM to extract a structured work order or answer a question,
3. Speaks the confirmation/answer back in the user's language,
4. Stores everything in a backend a supervisor can monitor live.

It is **deployed and live** at **https://vox-field.vercel.app/** (open in Chrome/Edge, allow the mic).

The knowledge base ships seeded with **40 industrial assets** across 11 types (pumps, motors,
valves, compressors, generators, HVAC, heat exchangers, tanks, pressure vessels, transformers,
switchgear) — each with specifications, maintenance procedures, and service history.

---

## ✨ Core Features

| # | Feature | What it does |
|---|---------|--------------|
| 1 | **Domain-Aware Voice Capture** | Push-to-talk **+ continuous** hands-free capture with silence detection. Recognition is primed with the asset vocabulary (codes, procedures, locations). **Hybrid engine:** Google Cloud Speech-to-Text when online (noise-robust, vocabulary-biased), browser Web Speech when offline. Includes a **noise simulator** (Factory / Workshop / Outdoor) to demonstrate accuracy in noise. |
| 2 | **Structured Data Extraction** | A voice note becomes a structured work order — *inspection result, fault code, location, severity, action taken, parts required* — via Gemini, with **per-field confidence scoring** and re-record prompts on low confidence. |
| 3 | **Voice Query Answering** | Ask about specs, maintenance history, or procedures → retrieved from the backend and **spoken back in the same language**, with response time displayed (**< 3 s**). |
| 4 | **Work Order Integration** | Create / update / close work orders by voice, with **spoken confirmation** ("Work order 12 created for PMP-4471"). |
| 5 | **Fault Escalation** | Say *"escalate to supervisor…"* → auto-creates a critical alert on the dashboard with status tracking (open → acknowledged → resolved). |
| 6 | **Offline Capability** | Notes & commands queue in **IndexedDB** when offline and **auto-sync on reconnect** (with retry). Speech falls back to the on-device browser engine; a text-confirm fallback guarantees content. |
| 7 | **Supervisor Dashboard** | Live web view: worker activity, work-order status, voice transcripts, **exception alerts**, **escalation panel**, and **analytics charts** (work-order timeline + severity distribution). |
| 8 | **Multi-language** | English, Hindi, and Spanish across STT, extraction, and TTS. |

---

## 🏗️ System Architecture

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
                                          │  AI / Cloud Stack:                                  │
                                          │   • LLM  → Vertex AI (Gemini 2.5 Flash)             │
                                          │   • STT  → Cloud Speech-to-Text   (online only)     │
                                          │   • TTS  → Cloud Text-to-Speech   (online only)     │
                                          │  Fallbacks: AI Studio key → rule-based; browser     │
                                          │  Web Speech for STT/TTS when offline.               │
                                          └─────────────────────────────────────────────────────┘
```

**Design principle — graceful degradation:** every cloud capability has a fallback so the app
never fully breaks. LLM: Vertex AI → AI Studio key → rule-based. Speech: Cloud STT/TTS (online)
→ browser Web Speech (offline). This is what keeps the **offline requirement** intact.

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, Vite, PWA (service worker), Recharts |
| **Backend** | Python, FastAPI, Uvicorn |
| **Database** | SQLite |
| **LLM** | Google Gemini 2.5 Flash via **Vertex AI** (with AI Studio + rule-based fallbacks) |
| **Speech-to-Text** | Google Cloud STT (online) + browser Web Speech API (offline) |
| **Text-to-Speech** | Google Cloud TTS (online) + browser SpeechSynthesis (offline) |
| **Retrieval** | Asset-code matching + `rapidfuzz` fuzzy search |
| **Offline storage** | IndexedDB + Service Worker |
| **Testing** | `pytest` (extraction, API, offline-sync) |
| **Deployment** | Vercel (frontend) + Render (backend) |

---

## ⚙️ Installation & Setup

### Prerequisites
- **Python 3.10+** and **Node.js 18+**
- A browser with Web Speech support: **Chrome or Edge** (desktop or Android)

### 1. Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # then configure the AI options (below)
python -m uvicorn main:app --port 8000
```
The database auto-creates and seeds 40 assets on first run. API docs: http://127.0.0.1:8000/docs

#### AI configuration (optional — app runs without it via rule-based fallback)

**Option A — Google Cloud service account (recommended: no rate limits + Cloud STT/TTS)**
1. In Google Cloud Console (billing enabled): create a **service account**, download its **JSON key**, save it as `backend/gcp-credentials.json` *(gitignored)*.
2. Enable the **Vertex AI**, **Cloud Speech-to-Text**, and **Cloud Text-to-Speech** APIs.
3. In `backend/.env`:
   ```env
   USE_VERTEX=true
   GOOGLE_APPLICATION_CREDENTIALS=gcp-credentials.json
   VERTEX_LOCATION=us-central1
   VERTEX_MODEL=gemini-2.5-flash
   USE_CLOUD_SPEECH=true
   ```

**Option B — AI Studio API key (simplest, free tier)**
1. Get a free key at https://aistudio.google.com → "Get API key".
2. In `backend/.env`: `GEMINI_API_KEY=...` and `GEMINI_MODEL=gemini-2.5-flash`.

> ⚠️ **Security:** never commit `.env` or `gcp-credentials.json` (both are gitignored). If a key is exposed, rotate it in the cloud console.

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
Open **http://localhost:5173** in Chrome/Edge — Worker terminal at `/`, Supervisor dashboard at `/supervisor`. (The dev server proxies `/api/*` to the backend automatically.)

---

## 🚀 How to Use / Demo Script

> Open the app in Chrome, allow microphone access. (Warm up the backend once before demoing — the first request after idle can be slow.)

| Time | Action |
|------|--------|
| **0:00 — Inspect** | On **Report**, tap the mic and say: *"Found cooling water pump PMP-4471 in pump house bay two leaking from the seal, severity high, I replaced the mechanical seal, need a new gasket and seal kit."* → Extracted fields appear with confidence bars → tap **Create work order** → it speaks the confirmation. |
| **0:30 — Test in noise** | Click **Simulate Noise → Factory Floor**, speak another report, and observe accurate capture of the equipment code. |
| **0:45 — Query (< 3 s)** | On **Ask**, say: *"What is the power rating of pump PMP-4471?"* → spoken answer + measured response time shown. |
| **1:15 — Escalate** | On **Report**, say: *"Escalate to supervisor, transformer TRF-100 Buchholz relay tripped, too dangerous to proceed."* → escalation appears on the dashboard. |
| **1:45 — Continuous mode** | Toggle **Push-to-Talk → Continuous**; speak naturally with silence-based segmentation. |
| **2:00 — Offline → sync** | DevTools → Network → **Offline** → record a note (shows `⧖ queued`) → back **Online** → auto-syncs. |
| **2:30 — Supervisor** | Open **`/supervisor`**: escalation panel, exception alerts, analytics charts, technician activity, transcript feed — refreshing live. |

**Multi-language tip:** set the language selector to हिन्दी and try *"GEN-9001 कहाँ स्थित है?"* — the answer is spoken back in Hindi.

---

## 📊 Results & Success Metrics

| Success Metric | Status | How it's met / verified |
|----------------|--------|--------------------------|
| Acceptable transcription accuracy in simulated noise | ✅ | Cloud STT with vocabulary biasing + noise simulator; per-field confidence bars |
| Structured extraction maps **all** required fields | ✅ | All 6 fields extracted by Gemini; verified by `test_extraction.py` |
| Voice query returns correct answer **< 3 s** | ✅ | Typically ~1–2 s; measured live and asserted in `test_api.py` |
| Work-order creation → correctly structured backend record | ✅ | Full CRUD; verified by `test_api.py` |
| Offline queue syncs & processes all queued notes | ✅ | IndexedDB queue + auto-sync; verified by `test_offline_sync.py` |

**Bonus features delivered:** voice-triggered escalation, multi-language (EN/HI/ES), multi-technician support, live analytics charts, PWA installability.

---

## 🧪 Testing

```bash
cd backend
pytest -v
```

| Test file | Coverage |
|-----------|----------|
| `test_extraction.py` | Extraction accuracy across realistic voice transcripts (fields + confidence + intent) |
| `test_api.py` | API endpoints — assets, extract, query (incl. < 3 s assertion), work orders, escalations, dashboard |
| `test_offline_sync.py` | Offline queue — FIFO order, mixed success/failure, retry, empty queue |

All tests pass (`51 passed`).

---

## 📁 Project Structure

```
VoxField/
├── backend/
│   ├── main.py              # FastAPI app + all routes
│   ├── db.py                # SQLite schema (assets, work_orders, voice_notes, escalations)
│   ├── seed.py              # 40 industrial assets + specs/procedures/history
│   ├── ai_engine.py         # LLM: Vertex AI → AI Studio → rule-based (with confidence)
│   ├── speech_cloud.py      # Cloud Speech-to-Text + Text-to-Speech
│   ├── knowledge.py         # Asset retrieval (code match → fuzzy search)
│   ├── test_*.py            # pytest suites
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/           Worker.jsx, Supervisor.jsx
│   │   ├── components/      RetroMic, Charts, ConfidenceBar, NoiseDemo,
│   │   │                    TechnicianSelect, EscalationBadge, Reveal
│   │   ├── lib/             speech, api, offlineQueue, useConnectivity, useTheme
│   │   └── styles.css       Soft-minimalist design system (light + dark)
│   └── vite.config.js
└── README.md
```

---

## ⚠️ Limitations

- **Browser support:** voice features rely on the Web Speech API (offline fallback), which is most reliable in **Chrome / Edge**. The app detects unsupported browsers and shows a notice.
- **Cloud features need internet + billing:** Cloud STT/TTS and Vertex AI require a billing-enabled Google Cloud project. Offline, the app uses browser speech and a rule-based extractor.
- **Multi-language quality:** English is the most accurate. Hindi/Spanish work well for common queries (e.g. location, specs) but the LLM is occasionally inconsistent on complex non-English phrasing.
- **Database:** SQLite is ideal for this scale and for demos; a multi-writer production deployment would migrate to PostgreSQL (the SQL is standard).

---

## 🔮 Future Scope

- Integrate with real enterprise systems (SAP PM, IBM Maximo) instead of the demo backend.
- Add **photo capture** alongside voice for visual fault evidence.
- On-device offline LLM (e.g. a small local model) for fully offline extraction.
- Role-based access control and authentication for multi-site deployments.
- Push notifications to supervisors for critical escalations.


---

<div align="center">

**Live:** https://vox-field.vercel.app/ · Built with React, FastAPI & Google Gemini

</div>
