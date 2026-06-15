"""VoxField backend — FastAPI app.

Phase 1: app setup, DB init + seed on startup, and asset/knowledge read endpoints.
Phase 2 will add: work order CRUD, voice extraction, and Q&A endpoints.
"""
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from db import db, init_db
from seed import seed


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
