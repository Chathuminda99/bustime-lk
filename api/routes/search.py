"""Search endpoint — find buses by origin/destination."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query

from api.database import get_async_db
from api.models import RouteResponse, ScheduleEntry, SearchResponse

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    from_station: str = Query(..., description="Origin station name or ID"),
    to_station: str = Query(..., description="Destination station name or ID"),
) -> SearchResponse:
    """
    Search for bus schedules between two stations.

    Accepts station names (partial match) or canonical IDs.
    Returns all matching routes with schedules grouped by platform.
    """
    db = await get_async_db()

    # Resolve station IDs — try exact ID first, then name match
    origin_rows = await db.execute_fetchall(
        """SELECT id, canonical_name FROM stations
           WHERE id = ? OR canonical_name LIKE ?
           LIMIT 1""",
        (from_station, f"%{from_station}%"),
    )
    dest_rows = await db.execute_fetchall(
        """SELECT id, canonical_name FROM stations
           WHERE id = ? OR canonical_name LIKE ?
           LIMIT 1""",
        (to_station, f"%{to_station}%"),
    )

    if not origin_rows:
        raise HTTPException(status_code=404, detail=f"Station not found: {from_station}")
    if not dest_rows:
        raise HTTPException(status_code=404, detail=f"Station not found: {to_station}")

    origin_id = origin_rows[0]["id"]
    origin_name = origin_rows[0]["canonical_name"]
    dest_id = dest_rows[0]["id"]
    dest_name = dest_rows[0]["canonical_name"]

    # Find matching routes
    route_rows = await db.execute_fetchall(
        """SELECT id, origin_station_id, destination_station_id
           FROM routes
           WHERE origin_station_id = ? AND destination_station_id = ?""",
        (origin_id, dest_id),
    )

    if not route_rows:
        return SearchResponse(
            from_station=origin_name,
            to_station=dest_name,
            routes=[],
            total_buses=0,
            platforms=[],
        )

    routes_result: list[RouteResponse] = []
    all_platforms: set[str] = set()
    total_buses = 0

    for route_row in route_rows:
        # Get all schedules for this route, grouped by platform
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
            (route_row["id"],),
        )

        schedules: list[ScheduleEntry] = []
        for sr in schedule_rows:
            schedules.append(
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
            )
            all_platforms.add(sr["platform_name"])

        platform_count = len(set(s.platform_id for s in schedules))
        total_buses += len(schedules)

        routes_result.append(
            RouteResponse(
                id=route_row["id"],
                origin=origin_name,
                destination=dest_name,
                schedules=schedules,
                platform_count=platform_count,
                bus_count=len(schedules),
            )
        )

    return SearchResponse(
        from_station=origin_name,
        to_station=dest_name,
        routes=routes_result,
        total_buses=total_buses,
        platforms=sorted(all_platforms),
    )
