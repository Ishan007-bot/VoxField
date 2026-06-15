"""VoxField backend — FastAPI app.

Phase 1: app setup, DB init + seed on startup, and asset/knowledge read endpoints.
Phase 2 will add: work order CRUD, voice extraction, and Q&A endpoints.
"""
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import ai_engine
import knowledge
from db import db, init_db
from seed import seed


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _vocab():
    """Domain vocabulary used to guide extraction. Mirrors the /vocabulary route."""
    with db() as conn:
        rows = conn.execute("SELECT code, name, location, procedures FROM assets").fetchall()
    codes, names, locations, procedures = [], [], set(), set()
    for r in rows:
        codes.append(r["code"])
        names.append(r["name"])
        locations.add(r["location"])
        for p in json.loads(r["procedures"]):
            procedures.add(p["name"])
    return {"codes": codes, "names": names,
            "locations": sorted(locations), "procedures": sorted(procedures)}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup: create tables and seed assets if the DB is empty.
    init_db()
    seed()
    yield


app = FastAPI(title="VoxField API", version="0.1.0", lifespan=lifespan)

# Allow the React dev server (and a deployed frontend) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the real frontend origin before production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _asset_to_dict(row):
    d = dict(row)
    d["specs"] = json.loads(d["specs"])
    d["procedures"] = json.loads(d["procedures"])
    return d


@app.get("/")
def root():
    return {"app": "VoxField", "tagline": "Speak. Inspect. Done.", "status": "ok"}


@app.get("/health")
def health():
    with db() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM assets").fetchone()["n"]
    return {"status": "ok", "assets": n}


@app.get("/assets")
def list_assets(type: str | None = None):
    """List all assets, optionally filtered by type (Pump, Motor, etc.)."""
    with db() as conn:
        if type:
            rows = conn.execute(
                "SELECT * FROM assets WHERE type = ? COLLATE NOCASE ORDER BY code",
                (type,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM assets ORDER BY code").fetchall()
    return [_asset_to_dict(r) for r in rows]


@app.get("/assets/{code}")
def get_asset(code: str):
    """Full detail for one asset, including its maintenance history."""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM assets WHERE code = ? COLLATE NOCASE", (code,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Asset {code} not found")
        history = conn.execute(
            "SELECT date, summary, technician FROM maintenance_history "
            "WHERE asset_code = ? COLLATE NOCASE ORDER BY date DESC",
            (code,),
        ).fetchall()
    asset = _asset_to_dict(row)
    asset["maintenance_history"] = [dict(h) for h in history]
    return asset


@app.get("/asset-types")
def asset_types():
    """Distinct asset types with counts — handy for the dashboard and vocab hints."""
    with db() as conn:
        rows = conn.execute(
            "SELECT type, COUNT(*) AS count FROM assets GROUP BY type ORDER BY type"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/vocabulary")
def vocabulary():
    """Domain vocabulary for the speech recognizer + AI prompts:
    every asset code, name, type, location, and procedure name."""
    with db() as conn:
        rows = conn.execute("SELECT code, name, type, location, procedures FROM assets").fetchall()
    codes, names, locations, procedures = [], [], set(), set()
    for r in rows:
        codes.append(r["code"])
        names.append(r["name"])
        locations.add(r["location"])
        for p in json.loads(r["procedures"]):
            procedures.add(p["name"])
    return {
        "codes": codes,
        "names": names,
        "locations": sorted(locations),
        "procedures": sorted(procedures),
    }


@app.get("/ai-status")
def ai_status():
    """Tells the frontend whether Gemini is active or we're on the fallback."""
    return {"gemini": ai_engine.gemini_available(),
            "engine": "gemini" if ai_engine.gemini_available() else "rule-based"}


@app.get("/stats")
def stats():
    """Headline numbers for the worker home screen and dashboard."""
    with db() as conn:
        assets = conn.execute("SELECT COUNT(*) n FROM assets").fetchone()["n"]
        wo_open = conn.execute(
            "SELECT COUNT(*) n FROM work_orders WHERE status != 'closed'").fetchone()["n"]
        wo_total = conn.execute("SELECT COUNT(*) n FROM work_orders").fetchone()["n"]
        critical = conn.execute(
            "SELECT COUNT(*) n FROM work_orders WHERE severity IN ('high','critical') "
            "AND status != 'closed'").fetchone()["n"]
        notes = conn.execute("SELECT COUNT(*) n FROM voice_notes").fetchone()["n"]
    return {"assets": assets, "open_work_orders": wo_open, "total_work_orders": wo_total,
            "critical_open": critical, "voice_notes": notes}


@app.get("/activity")
def activity(limit: int = 8):
    """Recent voice notes + work-order events for the live feed."""
    with db() as conn:
        notes = conn.execute(
            "SELECT transcript, intent, technician, created_at FROM voice_notes "
            "ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(n) for n in notes]


@app.get("/dashboard")
def dashboard():
    """Everything the supervisor view needs, in one call (good for polling):
    headline stats, work orders, recent transcripts, exception alerts,
    and per-technician activity summary."""
    with db() as conn:
        work_orders = [dict(r) for r in conn.execute(
            "SELECT * FROM work_orders ORDER BY created_at DESC").fetchall()]
        transcripts = [dict(r) for r in conn.execute(
            "SELECT id, transcript, intent, technician, work_order_id, created_at "
            "FROM voice_notes ORDER BY created_at DESC LIMIT 30").fetchall()]
        # Per-technician activity: note count + last seen
        techs = [dict(r) for r in conn.execute(
            "SELECT technician, COUNT(*) AS notes, MAX(created_at) AS last_seen "
            "FROM voice_notes WHERE technician IS NOT NULL "
            "GROUP BY technician ORDER BY last_seen DESC").fetchall()]
        assets = conn.execute("SELECT COUNT(*) n FROM assets").fetchone()["n"]

    # Exception alerts = open high/critical work orders (the things a supervisor must act on).
    alerts = [
        {
            "id": wo["id"], "asset_code": wo["asset_code"], "severity": wo["severity"],
            "inspection_result": wo["inspection_result"], "location": wo["location"],
            "technician": wo["technician"], "created_at": wo["created_at"],
        }
        for wo in work_orders
        if wo["status"] != "closed" and wo["severity"] in ("high", "critical")
    ]

    stats = {
        "assets": assets,
        "total_work_orders": len(work_orders),
        "open_work_orders": sum(1 for w in work_orders if w["status"] != "closed"),
        "closed_work_orders": sum(1 for w in work_orders if w["status"] == "closed"),
        "critical_open": len(alerts),
        "voice_notes": len(transcripts),
        "active_technicians": len(techs),
    }
    return {"stats": stats, "work_orders": work_orders, "transcripts": transcripts,
            "technicians": techs, "alerts": alerts}


# ===========================================================================
# Phase 2: extraction, Q&A, and work-order CRUD
# ===========================================================================
WO_FIELDS = ["asset_code", "inspection_result", "fault_code", "location",
             "severity", "action_taken", "parts_required", "status",
             "raw_transcript", "technician"]


class ExtractIn(BaseModel):
    transcript: str
    technician: str | None = None
    language: str | None = "en"


class QueryIn(BaseModel):
    question: str
    technician: str | None = None
    language: str | None = "en"


class WorkOrderIn(BaseModel):
    asset_code: str | None = None
    inspection_result: str | None = None
    fault_code: str | None = None
    location: str | None = None
    severity: str | None = None
    action_taken: str | None = None
    parts_required: str | None = None
    status: str | None = "open"
    raw_transcript: str | None = None
    technician: str | None = None


class WorkOrderUpdate(BaseModel):
    inspection_result: str | None = None
    fault_code: str | None = None
    location: str | None = None
    severity: str | None = None
    action_taken: str | None = None
    parts_required: str | None = None
    status: str | None = None


def _wo_to_dict(row):
    return dict(row)


def _log_voice_note(transcript, intent, technician, work_order_id=None):
    with db() as conn:
        conn.execute(
            "INSERT INTO voice_notes (transcript, intent, technician, work_order_id, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (transcript, intent, technician, work_order_id, _now()),
        )


@app.post("/extract")
def extract_fields(body: ExtractIn):
    """Voice transcript -> structured work-order fields (no DB write).
    The frontend shows these for confirmation, then POSTs /work-orders."""
    started = time.perf_counter()
    data, engine = ai_engine.extract(body.transcript, _vocab())
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    _log_voice_note(body.transcript, data.get("intent"), body.technician)
    return {"fields": data, "engine": engine, "elapsed_ms": elapsed_ms}


@app.post("/query")
def query(body: QueryIn):
    """Answer a domain question from the knowledge base. Times the round trip
    so the frontend can prove the <3s success metric."""
    started = time.perf_counter()
    context = knowledge.retrieve(body.question)
    answer_text, engine = ai_engine.answer(body.question, context)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    _log_voice_note(body.question, "query", body.technician)
    return {
        "answer": answer_text,
        "asset_code": context["asset"]["code"] if context else None,
        "engine": engine,
        "elapsed_ms": elapsed_ms,
    }


@app.get("/work-orders")
def list_work_orders(status: str | None = None):
    with db() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM work_orders WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM work_orders ORDER BY created_at DESC"
            ).fetchall()
    return [_wo_to_dict(r) for r in rows]


@app.get("/work-orders/{wo_id}")
def get_work_order(wo_id: int):
    with db() as conn:
        row = conn.execute("SELECT * FROM work_orders WHERE id = ?", (wo_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Work order {wo_id} not found")
    return _wo_to_dict(row)


@app.post("/work-orders")
def create_work_order(body: WorkOrderIn):
    now = _now()
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO work_orders "
            "(asset_code, inspection_result, fault_code, location, severity, "
            " action_taken, parts_required, status, raw_transcript, technician, "
            " created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (body.asset_code, body.inspection_result, body.fault_code, body.location,
             body.severity, body.action_taken, body.parts_required,
             body.status or "open", body.raw_transcript, body.technician, now, now),
        )
        wo_id = cur.lastrowid
        if body.raw_transcript:
            conn.execute(
                "INSERT INTO voice_notes (transcript, intent, technician, work_order_id, created_at) "
                "VALUES (?, 'create_wo', ?, ?, ?)",
                (body.raw_transcript, body.technician, wo_id, now),
            )
        row = conn.execute("SELECT * FROM work_orders WHERE id = ?", (wo_id,)).fetchone()
    return {"work_order": _wo_to_dict(row),
            "confirmation": f"Work order {wo_id} created"
                            + (f" for {body.asset_code}" if body.asset_code else "")
                            + (f", severity {body.severity}" if body.severity else "") + "."}


@app.patch("/work-orders/{wo_id}")
def update_work_order(wo_id: int, body: WorkOrderUpdate):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [_now(), wo_id]
    with db() as conn:
        cur = conn.execute(
            f"UPDATE work_orders SET {sets}, updated_at = ? WHERE id = ?", values
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Work order {wo_id} not found")
        row = conn.execute("SELECT * FROM work_orders WHERE id = ?", (wo_id,)).fetchone()
    return {"work_order": _wo_to_dict(row),
            "confirmation": f"Work order {wo_id} updated."}


@app.post("/work-orders/{wo_id}/close")
def close_work_order(wo_id: int):
    with db() as conn:
        cur = conn.execute(
            "UPDATE work_orders SET status = 'closed', updated_at = ? WHERE id = ?",
            (_now(), wo_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Work order {wo_id} not found")
        row = conn.execute("SELECT * FROM work_orders WHERE id = ?", (wo_id,)).fetchone()
    return {"work_order": _wo_to_dict(row),
            "confirmation": f"Work order {wo_id} closed."}
