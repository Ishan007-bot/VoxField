# Deploying VoxField

Backend → **Render** · Frontend → **Vercel** · Secrets → set in each host (never committed).

> The repo is already prepared: `render.yaml`, `vercel.json`, and the code reads
> credentials from env vars in the cloud. You just click through the hosts and paste
> your secrets. Do these in order — the backend first, since the frontend needs its URL.

---

## Part 1 — Backend on Render

1. Push the latest code to GitHub (see "Commit & push" at the bottom).
2. Go to **https://render.com** → sign in with GitHub.
3. **New +** → **Blueprint** → select the **VoxField** repo → Render reads `render.yaml`
   and proposes the `voxfield-api` service. Click **Apply**.
4. The first build will start but **fail or run degraded until you add the secrets** —
   that's expected. Open the service → **Environment** → add:

   | Key | Value |
   |---|---|
   | `GCP_CREDENTIALS_JSON` | **paste the entire contents** of `backend/gcp-credentials.json` (the whole `{ ... }`). Mark as secret. |
   | `CORS_ORIGINS` | leave blank for now; set after Part 2 to your Vercel URL |

   (`USE_VERTEX`, `USE_CLOUD_SPEECH`, `VERTEX_LOCATION`, `VERTEX_MODEL`, `DB_PATH` are
   already set by `render.yaml`.)
5. **Save** → Render redeploys. When it's live, note the URL, e.g.
   `https://voxfield-api.onrender.com`.
6. Verify: open `https://voxfield-api.onrender.com/health` → `{"status":"ok","assets":40}`
   and `/ai-status` → `{"backend":"vertex",...}`.

> **Free tier sleeps** after ~15 min idle; the first request then takes ~30–60s to wake.
> Hit `/health` once to warm it up before a demo.

---

## Part 2 — Frontend on Vercel

1. Go to **https://vercel.com** → sign in with GitHub → **Add New… → Project** →
   import the **VoxField** repo.
2. **Root Directory:** set to **`frontend`** (important — the app isn't at the repo root).
3. Vercel auto-detects Vite. Under **Environment Variables**, add:

   | Key | Value |
   |---|---|
   | `VITE_API_BASE` | your Render URL, e.g. `https://voxfield-api.onrender.com` |

4. **Deploy.** When done you get a URL like `https://voxfield.vercel.app`.

---

## Part 3 — Connect them (CORS)

1. Back in **Render** → `voxfield-api` → **Environment** → set
   `CORS_ORIGINS` = your Vercel URL (e.g. `https://voxfield.vercel.app`).
   (Multiple origins allowed, comma-separated.)
2. Save → redeploy.
3. Open the Vercel URL in **Chrome**, allow the mic, and test:
   - Worker terminal: `/`
   - Supervisor dashboard: `/supervisor`

Done. 🎉

---

## Security & cost notes (read once)
- **Never commit** `gcp-credentials.json` or `.env` — both are gitignored. The credential
  lives only in Render's encrypted env. (If it's ever exposed, rotate it in GCP.)
- Vertex AI + Cloud STT/TTS bill to **your GCP account** per request. Cheap for a demo,
  but a public URL can be hit by anyone — consider taking the site down after grading,
  or set a GCP **budget alert**.
- Want zero cost / zero key risk in the cloud? Set `USE_VERTEX=false` and
  `USE_CLOUD_SPEECH=false` on Render — the app falls back to rule-based + browser speech.

## Commit & push (run locally before deploying)
```bash
git add -A
git commit -m "chore: add Render + Vercel deploy config"
git push origin main
```

## Troubleshooting
- **Frontend can't reach backend / CORS error** → `VITE_API_BASE` (Vercel) and
  `CORS_ORIGINS` (Render) must match the real URLs, no trailing slash.
- **`/ai-status` shows `rule-based`** → `GCP_CREDENTIALS_JSON` missing/invalid on Render,
  or the Vertex/Speech APIs aren't enabled on the GCP project.
- **`/supervisor` 404 on refresh** → ensure `frontend/vercel.json` (SPA rewrite) deployed.
- **Voice doesn't work** → must be Chrome/Edge **over HTTPS** (Vercel is HTTPS ✓); mic
  needs a secure origin.
