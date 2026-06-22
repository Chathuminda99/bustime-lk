"""
BusTime.lk — FastAPI Application

Cross-platform bus timetable search API for Sri Lanka.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiosqlite
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import close_async_db, get_async_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: init DB + ensure schema. Shutdown: close DB."""
    # Ensure schema exists (sync init)
    init_db()
    # Warm up the async connection
    await get_async_db()
    yield
    await close_async_db()


app = FastAPI(
    title="BusTime.lk API",
    description="Cross-platform bus timetable search for Sri Lanka",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=dict)
async def health() -> dict:
    """Health check with basic stats."""
    db = await get_async_db()
    platforms = await db.execute_fetchall("SELECT COUNT(*) as c FROM platforms")
    routes = await db.execute_fetchall("SELECT COUNT(*) as c FROM routes")
    schedules = await db.execute_fetchall("SELECT COUNT(*) as c FROM schedules")
    return {
        "status": "ok",
        "platforms": platforms[0]["c"],
        "routes": routes[0]["c"],
        "schedules": schedules[0]["c"],
    }


# ── Import route modules AFTER app creation ─────────────────────────────────

from api.routes import platforms, routes, search, stations  # noqa: E402

app.include_router(search.router)
app.include_router(routes.router)
app.include_router(stations.router)
app.include_router(platforms.router)
