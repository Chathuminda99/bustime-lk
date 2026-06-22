"""Station autocomplete endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Query

from api.database import get_async_db
from api.models import StationResponse

router = APIRouter(prefix="/api", tags=["stations"])


@router.get("/stations", response_model=list[StationResponse])
async def list_stations(
    q: str = Query("", description="Search query for autocomplete"),
    limit: int = Query(20, ge=1, le=100),
) -> list[StationResponse]:
    """
    List or search stations.

    When `q` is empty, returns all stations.
    When `q` is provided, returns stations matching the query (case-insensitive
    partial match on canonical name).
    """
    db = await get_async_db()

    if q:
        rows = await db.execute_fetchall(
            """SELECT id, canonical_name FROM stations
               WHERE canonical_name LIKE ?
               ORDER BY canonical_name
               LIMIT ?""",
            (f"%{q}%", limit),
        )
    else:
        rows = await db.execute_fetchall(
            "SELECT id, canonical_name FROM stations ORDER BY canonical_name LIMIT ?",
            (limit,),
        )

    return [
        StationResponse(id=row["id"], name=row["canonical_name"])
        for row in rows
    ]
