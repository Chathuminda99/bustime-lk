"""
BusTime.lk — SQLite database layer (sync + async).

Sync path: used by import_to_db.py (scrapers)
Async path: used by FastAPI (aiosqlite)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "bustime.db"

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS platforms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    enabled INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS stations (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS station_aliases (
    station_id TEXT NOT NULL REFERENCES stations(id),
    platform_id TEXT NOT NULL REFERENCES platforms(id),
    alias_name TEXT NOT NULL,
    PRIMARY KEY (station_id, platform_id, alias_name)
);

CREATE TABLE IF NOT EXISTS operators (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS operator_aliases (
    operator_id TEXT NOT NULL REFERENCES operators(id),
    platform_id TEXT NOT NULL REFERENCES platforms(id),
    alias_name TEXT NOT NULL,
    PRIMARY KEY (operator_id, platform_id, alias_name)
);

CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin_station_id TEXT NOT NULL REFERENCES stations(id),
    destination_station_id TEXT NOT NULL REFERENCES stations(id),
    UNIQUE(origin_station_id, destination_station_id)
);

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER NOT NULL REFERENCES routes(id),
    platform_id TEXT NOT NULL REFERENCES platforms(id),
    operator_id TEXT NOT NULL REFERENCES operators(id),
    departure_time TEXT NOT NULL,
    arrival_time TEXT,
    bus_type TEXT,
    fare REAL,
    booking_url TEXT,
    route_number TEXT,
    scraped_at TEXT NOT NULL,
    UNIQUE(route_id, platform_id, operator_id, departure_time)
);

CREATE TABLE IF NOT EXISTS scrape_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id TEXT NOT NULL REFERENCES platforms(id),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    routes_found INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_schedules_route ON schedules(route_id);
CREATE INDEX IF NOT EXISTS idx_schedules_platform ON schedules(platform_id);
CREATE INDEX IF NOT EXISTS idx_routes_stations ON routes(origin_station_id, destination_station_id);
CREATE INDEX IF NOT EXISTS idx_station_aliases_platform ON station_aliases(platform_id, alias_name);
CREATE INDEX IF NOT EXISTS idx_operator_aliases_platform ON operator_aliases(platform_id, alias_name);
"""

# ── Sync (for import script) ────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db(conn: sqlite3.Connection | None = None) -> None:
    conn = conn or get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        platforms = [
            ("busseat", "BusSeat.lk", "https://busseat.lk"),
            ("magiya", "Magiya.lk", "https://magiya.lk"),
            ("bus_lk", "Bus.LK", "https://bus.lk"),
            ("sltb_eseat", "SLTB eSeat", "https://sltb.eseat.lk"),
            ("rathna", "Rathna Travels", "https://rathnatravels.lk"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO platforms (id, name, url) VALUES (?, ?, ?)",
            platforms,
        )
        conn.commit()
    finally:
        if conn:
            conn.close()

# ── Async (for FastAPI) ─────────────────────────────────────────────────────

_async_db: aiosqlite.Connection | None = None

async def get_async_db() -> aiosqlite.Connection:
    global _async_db
    if _async_db is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _async_db = await aiosqlite.connect(str(DB_PATH))
        _async_db.row_factory = aiosqlite.Row
        await _async_db.execute("PRAGMA journal_mode=WAL")
        await _async_db.execute("PRAGMA foreign_keys=ON")
    return _async_db

async def close_async_db() -> None:
    global _async_db
    if _async_db:
        await _async_db.close()
        _async_db = None
