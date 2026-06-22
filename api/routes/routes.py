"""Routes list and detail endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.database import get_async_db
from api.models import RouteListItem, RouteResponse, ScheduleEntry

router = APIRouter(prefix="/api", tags=["routes"])


@router.get("/routes", response_model=list[RouteListItem])
async def list_routes(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[RouteListItem]:
    """List all known routes with bus counts."""
    db = await get_async_db()

    rows = await db.execute_fetchall(
        """SELECT r.id, os.canonical_name as origin, ds.canonical_name as dest,
                  COUNT(s.id) as bus_count
           FROM routes r
           JOIN stations os ON r.origin_station_id = os.id
           JOIN stations ds ON r.destination_station_id = ds.id
           LEFT JOIN schedules s ON s.route_id = r.id
           GROUP BY r.id
           ORDER BY bus_count DESC
           LIMIT ? OFFSET ?""",
        (limit, offset),
    )

    return [
        RouteListItem(
            id=row["id"],
            origin=row["origin"],
            destination=row["dest"],
            bus_count=row["bus_count"],
        )
        for row in rows
    ]


@router.get("/routes/{route_id}", response_model=RouteResponse)
async def get_route(route_id: int) -> RouteResponse:
    """Get a single route with all its schedules."""
    db = await get_async_db()

    route_row = await db.execute_fetchall(
        """SELECT r.id, os.canonical_name as origin, ds.canonical_name as dest
           FROM routes r
           JOIN stations os ON r.origin_station_id = os.id
           JOIN stations ds ON r.destination_station_id = ds.id
           WHERE r.id = ?""",
        (route_id,),
    )

    if not route_row:
        raise HTTPException(status_code=404, detail="Route not found")

    r = route_row[0]

    schedule_rows = await db.execute_fetchall(
        """SELECT s.departure_time, s.arrival_time, s.bus_type,
                  s.fare, s.booking_url, s.route_number,
                  p.name as platform_name, p.id as platform_id,
                  o.canonical_name as operator_name
           FROM schedules s
           JOIN platforms p ON s.platform_id = p.id
           JOIN operators o ON s.operator_id = o.id
           WHERE s.route_id = ?
           ORDER BY s.departure_time""",
        (route_id,),
    )

    schedules = [
        ScheduleEntry(
            platform=sr["platform_name"],
            platform_id=sr["platform_id"],
            operator=sr["operator_name"],
            departure_time=sr["departure_time"],
            arrival_time=sr["arrival_time"] or "",
            bus_type=sr["bus_type"] or "Normal",
            fare=sr["fare"],
            booking_url=sr["booking_url"] or "",
            route_number=sr["route_number"],
        )
        for sr in schedule_rows
    ]

    platform_ids = set(s.platform_id for s in schedules)

    return RouteResponse(
        id=r["id"],
        origin=r["origin"],
        destination=r["dest"],
        schedules=schedules,
        platform_count=len(platform_ids),
        bus_count=len(schedules),
    )
