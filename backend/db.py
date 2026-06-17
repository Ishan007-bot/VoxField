"""SQLite connection + schema setup. Single-file DB, no ORM to keep it readable."""
import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "field_assistant.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,          -- e.g. PMP-4471
    name TEXT NOT NULL,                 -- human name
    type TEXT NOT NULL,                 -- Pump | Motor | Valve | Compressor | Generator | HVAC
    location TEXT NOT NULL,
    specs TEXT NOT NULL,                -- JSON string of spec key/values
    procedures TEXT NOT NULL            -- JSON string: [{name, steps:[...]}]
);

CREATE TABLE IF NOT EXISTS maintenance_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_code TEXT NOT NULL,
    date TEXT NOT NULL,
    summary TEXT NOT NULL,
    technician TEXT,
    FOREIGN KEY (asset_code) REFERENCES assets(code)
);

CREATE TABLE IF NOT EXISTS work_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_code TEXT,
    inspection_result TEXT,
    fault_code TEXT,
    location TEXT,
    severity TEXT,                      -- low | medium | high | critical
    action_taken TEXT,
    parts_required TEXT,                -- comma-separated
    status TEXT NOT NULL DEFAULT 'open', -- open | in_progress | closed
    raw_transcript TEXT,               -- original voice note text
    technician TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS voice_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript TEXT NOT NULL,
    intent TEXT,                       -- create_wo | query | update_wo | close_wo | escalate | note
    technician TEXT,
    work_order_id INTEGER,
    confidence REAL,                   -- STT transcription confidence 0.0-1.0
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS escalations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id INTEGER,
    asset_code TEXT,
    severity TEXT NOT NULL DEFAULT 'critical',
    reason TEXT,                       -- why the technician escalated
    location TEXT,
    technician TEXT,
    status TEXT NOT NULL DEFAULT 'open',  -- open | acknowledged | resolved
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY (work_order_id) REFERENCES work_orders(id)
);
"""


def init_db():
    with db() as conn:
        conn.executescript(SCHEMA)
