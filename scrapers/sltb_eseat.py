"""
SLTB eSeat (1315.lk) scraper for BusTime.lk

SLTB is the state-run Sri Lanka Transport Board. Its eSeat platform uses
server-rendered HTML with a simple GET form at /bus/schedule/search.
Results come back as an HTML table — no JS needed.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

from scrapers.base import BaseScraper, RouteEntry, ScrapeResult

logger = logging.getLogger(__name__)

SLTB_BASE = "https://sltb.eseat.lk"

# Major city IDs discovered from the /bus/schedules page select options.
# These are the main city-level stops (not granular stops).
CITY_IDS: dict[str, int] = {
    "Colombo": 39,
    "Kandy": 15,
    "Jaffna": 11,
    "Galle": 212,
    "Matara": 240,
    "Badulla": 30,
    "Anuradhapura": 17,
    "Trincomalee": 29,
    "Batticaloa": 37,
    "Ratnapura": 1564,
    "Kurunegala": 126,
    "Vavuniya": 739,
    "Mannar": 21,
    "Kalmunai": 4,
    "Ampara": 5,
    "Negombo": 697,
    "Puttalam": 721,
    "Polonnaruwa": 479,
    "Matale": 1354,
    "Kegalle": 323,
    "Bandarawela": 1074,
}

# City pairs that are most likely to have SLTB buses
ROUTE_PAIRS: list[tuple[str, str]] = [
    # Colombo hub-and-spoke
    ("Colombo", "Kandy"),
    ("Colombo", "Galle"),
    ("Colombo", "Matara"),
    ("Colombo", "Jaffna"),
    ("Colombo", "Badulla"),
    ("Colombo", "Anuradhapura"),
    ("Colombo", "Trincomalee"),
    ("Colombo", "Batticaloa"),
    ("Colombo", "Ratnapura"),
    ("Colombo", "Kurunegala"),
    ("Colombo", "Vavuniya"),
    ("Colombo", "Mannar"),
    ("Colombo", "Kalmunai"),
    ("Colombo", "Ampara"),
    ("Colombo", "Negombo"),
    ("Colombo", "Puttalam"),
    ("Colombo", "Polonnaruwa"),
    ("Colombo", "Matale"),
    ("Colombo", "Kegalle"),
    ("Colombo", "Bandarawela"),
    # Key cross-country
    ("Kandy", "Jaffna"),
    ("Kandy", "Badulla"),
    ("Kandy", "Anuradhapura"),
    ("Kandy", "Matara"),
    ("Galle", "Matara"),
    ("Galle", "Kandy"),
    ("Anuradhapura", "Jaffna"),
    ("Anuradhapura", "Trincomalee"),
    ("Jaffna", "Trincomalee"),
    ("Jaffna", "Batticaloa"),
]


class SLTBeSeatScraper(BaseScraper):
    """Scraper for SLTB eSeat — state-run bus platform."""

    platform_id = "sltb_eseat"
    platform_name = "SLTB eSeat"
    base_url = SLTB_BASE

    async def discover_routes(self) -> list[dict]:
        """Return pre-discovered route pairs with numeric IDs."""
        routes = []
        for from_city, to_city in ROUTE_PAIRS:
            from_id = CITY_IDS.get(from_city)
            to_id = CITY_IDS.get(to_city)
            if from_id and to_id:
                routes.append({
                    "from_city": from_city,
                    "to_city": to_city,
                    "from_id": str(from_id),
                    "to_id": str(to_id),
                })
        logger.info(f"[sltb] Using {len(routes)} known route pairs")
        return routes

    async def fetch_schedule(self, from_id: str, to_id: str) -> str:
        """Call /bus/schedule/search and return HTML."""
        params = {
            "from": from_id,
            "to": to_id,
            "start": "00:00",
            "end": "23:55",
            "bus_type": "any",
        }
        url = f"{self.base_url}/bus/schedule/search?{urlencode(params)}"
        response = await self.fetch(url)
        return response.text

    def parse_schedule_table(self, html: str, from_city: str, to_city: str) -> list[RouteEntry]:
        """Parse the schedule results table into RouteEntry objects."""
        soup = self.parse(html)
        entries: list[RouteEntry] = []

        table = soup.find('table')
        if not table:
            return entries

        for row in table.find_all('tr')[1:]:  # Skip header
            cells = row.find_all(['td', 'th'])
            if len(cells) < 5:
                continue

            dep_raw = cells[0].get_text(strip=True)
            arr_raw = cells[1].get_text(strip=True)
            route_no = cells[2].get_text(strip=True)
            via = cells[3].get_text(strip=True).replace('via', '')
            bus_type = cells[4].get_text(strip=True)

            # Parse times: "00:10  |" → "00:10"
            dep_time = re.sub(r'\s*\|.*', '', dep_raw).strip()
            arr_time = re.sub(r'\s*\|.*', '', arr_raw).strip()

            if not dep_time or dep_time == 'Departure':
                continue

            # Convert "Normal" to canonical case
            bus_type = bus_type.strip().title()
            if bus_type == 'Normal':
                bus_type = 'Normal'

            entries.append(RouteEntry(
                origin=from_city,
                destination=to_city,
                operator="SLTB",
                departure_time=dep_time,
                arrival_time=arr_time,
                bus_type=bus_type or "Normal",
                fare=None,  # SLTB timetable doesn't show fares
                booking_url=f"{self.base_url}?from={CITY_IDS.get(from_city)}&to={CITY_IDS.get(to_city)}",
                origin_stop=from_city,
                destination_stop=to_city,
                route_number=route_no,
            ))

        return entries

    async def scrape(self) -> ScrapeResult:
        """Discover and scrape all route pairs."""
        errors: list[str] = []
        all_entries: list[RouteEntry] = []

        try:
            routes = await self.discover_routes()
        except Exception as exc:
            logger.error(f"[sltb] Route discovery failed: {exc}")
            return self.result(status="failed", errors=[str(exc)])

        for i, route in enumerate(routes):
            try:
                logger.info(
                    f"[sltb] [{i+1}/{len(routes)}] "
                    f"{route['from_city']} → {route['to_city']}"
                )
                html = await self.fetch_schedule(route["from_id"], route["to_id"])
                entries = self.parse_schedule_table(
                    html, route["from_city"], route["to_city"]
                )
                all_entries.extend(entries)
                logger.info(f"[sltb]   → {len(entries)} buses found")
            except Exception as exc:
                msg = f"{route['from_city']}→{route['to_city']}: {exc}"
                logger.warning(f"[sltb] Failed: {msg}")
                errors.append(msg)

        status = "success"
        if errors and not all_entries:
            status = "failed"
        elif errors:
            status = "partial"

        return self.result(status=status, entries=all_entries, errors=errors)
