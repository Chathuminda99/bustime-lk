"""Platforms list endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from api.database import get_async_db
from api.models import PlatformResponse

router = APIRouter(prefix="/api", tags=["platforms"])


@router.get("/platforms", response_model=list[PlatformResponse])
async def list_platforms() -> list[PlatformResponse]:
    """List all platforms with schedule counts."""
    db = await get_async_db()

    rows = await db.execute_fetchall(
        """SELECT p.id, p.name, p.url, COUNT(s.id) as bus_count
           FROM platforms p
           LEFT JOIN schedules s ON s.platform_id = p.id
           GROUP BY p.id
           ORDER BY bus_count DESC"""
    )

    return [
        PlatformResponse(id=row["id"], name=row["name"], url=row["url"])
        for row in rows
    ]
