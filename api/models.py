"""Pydantic models for BusTime.lk API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── Request models ──────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    from_station: str
    to_station: str


# ── Response models ─────────────────────────────────────────────────────────

class StationResponse(BaseModel):
    id: str
    name: str

class PlatformResponse(BaseModel):
    id: str
    name: str
    url: str

class ScheduleEntry(BaseModel):
    platform: str
    platform_id: str
    operator: str
    departure_time: str
    arrival_time: str
    bus_type: str
    fare: Optional[float] = None
    booking_url: str
    route_number: Optional[str] = None

class RouteResponse(BaseModel):
    id: int
    origin: str
    destination: str
    schedules: list[ScheduleEntry]
    platform_count: int
    bus_count: int

class RouteListItem(BaseModel):
    id: int
    origin: str
    destination: str
    bus_count: int

class SearchResponse(BaseModel):
    from_station: str
    to_station: str
    routes: list[RouteResponse]
    total_buses: int
    platforms: list[str]

class HealthResponse(BaseModel):
    status: str
    platforms: int
    routes: int
    schedules: int
    last_scrape: Optional[str] = None
