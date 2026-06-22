"""
Magiya.lk scraper for BusTime.lk

Magiya is a Laravel Livewire SPA — bus data is embedded as JSON
inside Livewire component snapshots. This scraper uses Playwright
to load pages, then extracts structured data directly from the
wire:snapshot attributes without HTML parsing.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PwTimeout

from scrapers.base import RouteEntry, ScrapeResult

logger = logging.getLogger(__name__)

MAGIYA_BASE = "https://magiya.lk"

# ── Known productive routes (city pairs with numeric IDs) ──────────────────
# Discovered by systematically testing 35 major cities against Magiya's
# search API. These pairs return actual bus results.
KNOWN_ROUTES: list[dict] = [
    {"from": "Colombo", "to": "Kandy", "pickup_id": "1863", "destination_id": "800"},
    {"from": "Colombo", "to": "Jaffna", "pickup_id": "1863", "destination_id": "650"},
    {"from": "Colombo", "to": "Matara", "pickup_id": "1863", "destination_id": "1395"},
    {"from": "Colombo", "to": "Badulla", "pickup_id": "1863", "destination_id": "180"},
    {"from": "Colombo", "to": "Anuradhapura", "pickup_id": "1863", "destination_id": "44"},
    {"from": "Colombo", "to": "Trincomalee", "pickup_id": "1863", "destination_id": "1827"},
    {"from": "Colombo", "to": "Batticaloa", "pickup_id": "1863", "destination_id": "290"},
    {"from": "Colombo", "to": "Kurunegala", "pickup_id": "1863", "destination_id": "1129"},
    {"from": "Colombo", "to": "Nuwara Eliya", "pickup_id": "1863", "destination_id": "1535"},
    {"from": "Colombo", "to": "Hambantota", "pickup_id": "1863", "destination_id": "603"},
    {"from": "Colombo", "to": "Ratnapura", "pickup_id": "1863", "destination_id": "1768"},
    {"from": "Colombo", "to": "Vavuniya", "pickup_id": "1863", "destination_id": "1829"},
    {"from": "Colombo", "to": "Mannar", "pickup_id": "1863", "destination_id": "1281"},
    {"from": "Colombo", "to": "Kalmunai", "pickup_id": "1863", "destination_id": "11"},
    {"from": "Colombo", "to": "Ampara", "pickup_id": "1863", "destination_id": "3"},
    {"from": "Colombo", "to": "Kegalle", "pickup_id": "1863", "destination_id": "960"},
    {"from": "Colombo", "to": "Negombo", "pickup_id": "1863", "destination_id": "545"},
    {"from": "Colombo", "to": "Bandarawela", "pickup_id": "1863", "destination_id": "184"},
    {"from": "Colombo", "to": "Kataragama", "pickup_id": "1863", "destination_id": "1445"},
    {"from": "Colombo", "to": "Panadura", "pickup_id": "1863", "destination_id": "721"},
    {"from": "Colombo", "to": "Moratuwa", "pickup_id": "1863", "destination_id": "355"},
    {"from": "Colombo", "to": "Matale", "pickup_id": "1863", "destination_id": "1330"},
    {"from": "Colombo", "to": "Polonnaruwa", "pickup_id": "1863", "destination_id": "1575"},
    {"from": "Colombo", "to": "Puttalam", "pickup_id": "1863", "destination_id": "1648"},
    {"from": "Colombo", "to": "Chilaw", "pickup_id": "1863", "destination_id": "1592"},
    {"from": "Colombo", "to": "Welimada", "pickup_id": "1863", "destination_id": "279"},
    {"from": "Colombo", "to": "Avissawella", "pickup_id": "1863", "destination_id": "330"},
    {"from": "Colombo", "to": "Makumbura", "pickup_id": "1863", "destination_id": "1733"},
    {"from": "Kandy", "to": "Nuwara Eliya", "pickup_id": "800", "destination_id": "1535"},
    {"from": "Anuradhapura", "to": "Jaffna", "pickup_id": "44", "destination_id": "650"},
    # Reverse routes (City → Colombo and key cross-country returns)
    {"from": "Kandy", "to": "Colombo", "pickup_id": "800", "destination_id": "1863"},
    {"from": "Jaffna", "to": "Colombo", "pickup_id": "650", "destination_id": "1863"},
    {"from": "Matara", "to": "Colombo", "pickup_id": "1395", "destination_id": "1863"},
    {"from": "Badulla", "to": "Colombo", "pickup_id": "180", "destination_id": "1863"},
    {"from": "Anuradhapura", "to": "Colombo", "pickup_id": "44", "destination_id": "1863"},
    {"from": "Trincomalee", "to": "Colombo", "pickup_id": "1827", "destination_id": "1863"},
    {"from": "Batticaloa", "to": "Colombo", "pickup_id": "290", "destination_id": "1863"},
    {"from": "Kurunegala", "to": "Colombo", "pickup_id": "1129", "destination_id": "1863"},
    {"from": "Nuwara Eliya", "to": "Colombo", "pickup_id": "1535", "destination_id": "1863"},
    {"from": "Vavuniya", "to": "Colombo", "pickup_id": "1829", "destination_id": "1863"},
    {"from": "Ratnapura", "to": "Colombo", "pickup_id": "1768", "destination_id": "1863"},
    {"from": "Ampara", "to": "Colombo", "pickup_id": "3", "destination_id": "1863"},
    {"from": "Negombo", "to": "Colombo", "pickup_id": "545", "destination_id": "1863"},
    {"from": "Puttalam", "to": "Colombo", "pickup_id": "1648", "destination_id": "1863"},
    {"from": "Kegalle", "to": "Colombo", "pickup_id": "960", "destination_id": "1863"},
    {"from": "Moratuwa", "to": "Colombo", "pickup_id": "355", "destination_id": "1863"},
    {"from": "Panadura", "to": "Colombo", "pickup_id": "721", "destination_id": "1863"},
    {"from": "Nuwara Eliya", "to": "Kandy", "pickup_id": "1535", "destination_id": "800"},
    {"from": "Jaffna", "to": "Anuradhapura", "pickup_id": "650", "destination_id": "44"},
]

# ── Helpers ─────────────────────────────────────────────────────────────────


def _parse_time_12h(time_str: str) -> str:
    """Convert '03:00 AM' → '03:00' (24h)."""
    if not time_str:
        return ""
    time_str = time_str.strip()
    try:
        return datetime.strptime(time_str, "%I:%M %p").strftime("%H:%M")
    except ValueError:
        return time_str


def _parse_price(price: str | int | float) -> float | None:
    """Parse price from the Livewire snapshot."""
    if price is None:
        return None
    try:
        return float(price)
    except (ValueError, TypeError):
        return None


# ── Scraper ─────────────────────────────────────────────────────────────────


class MagiyaScraper:
    """Scraper for Magiya.lk using Playwright + Livewire snapshot extraction."""

    platform_id = "magiya"
    platform_name = "Magiya.lk"
    base_url = MAGIYA_BASE

    def __init__(self) -> None:
        self._playwright = None
        self._browser: Browser | None = None

    async def _ensure_browser(self) -> Browser:
        """Lazily launch a Playwright Chromium browser."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
        return self._browser

    async def close(self) -> None:
        """Clean up browser resources."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    # ── Route discovery ─────────────────────────────────────────────────

    async def discover_routes(self) -> list[dict]:
        """
        Return the list of known productive route pairs.

        Uses a pre-discovered list of 30 city pairs that return bus results
        on Magiya. Route discovery is done offline via a separate script.
        """
        routes: list[dict] = []
        for r in KNOWN_ROUTES:
            routes.append(
                {
                    "pickup_id": r["pickup_id"],
                    "destination_id": r["destination_id"],
                    "from_city_name": r["from"],
                    "to_city_name": r["to"],
                    "url": f"{self.base_url}/journeys/search",
                }
            )

        logger.info(f"[magiya] Using {len(routes)} known productive routes")
        return routes

    # ── Route page scraping ─────────────────────────────────────────────

    async def scrape_route(self, route: dict) -> list[RouteEntry]:
        """
        Load a route search page with Playwright, wait for results,
        extract Livewire snapshot JSON from journey-card components.
        Handles pagination (all pages).
        """
        browser = await self._ensure_browser()
        page = await browser.new_page()
        all_entries: list[RouteEntry] = []

        try:
            # We need a date — use tomorrow to ensure availability
            from datetime import date, timedelta
            tomorrow = (date.today() + timedelta(days=1)).isoformat()

            params = {
                "pickup_id": route["pickup_id"],
                "destination_id": route["destination_id"],
                "date_of_journey": tomorrow,
                "from_city_name": route["from_city_name"],
                "to_city_name": route["to_city_name"],
                "pickup_id_proximity": "5",
                "destination_id_proximity": "5",
            }
            url = f"{self.base_url}/journeys/search?{urlencode(params)}"

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for bus cards to render
            try:
                await page.wait_for_selector('text=LKR', timeout=15000)
            except PwTimeout:
                logger.info(
                    f"[magiya] No results for {route['from_city_name']} → {route['to_city_name']}"
                )
                return []

            await page.wait_for_timeout(1000)

            # Scroll to load all pages (infinite scroll)
            await self._load_all_pages(page)

            entries = await self._extract_cards_from_page(page, route["url"])
            all_entries.extend(entries)

        finally:
            await page.close()

        return all_entries

    async def _extract_cards_from_page(
        self, page: Page, booking_base_url: str
    ) -> list[RouteEntry]:
        """Extract journey-card Livewire snapshots from the current page."""
        html = await page.content()

        entries: list[RouteEntry] = []

        # Find all journey-card wire:snapshot attributes
        pattern = re.compile(
            r'wire:snapshot="({[^"]*journey\.journey-card[^"]*})"'
        )
        for match in pattern.finditer(html):
            try:
                snap_json = match.group(1)
                # Unescape HTML entities
                snap_json = snap_json.replace("&quot;", '"')
                snap = json.loads(snap_json)
                entry = self._parse_card_snapshot(snap, booking_base_url)
                if entry:
                    entries.append(entry)
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.debug(f"[magiya] Failed to parse card snapshot: {exc}")
                continue

        return entries

    def _parse_card_snapshot(
        self, snap: dict, booking_base_url: str
    ) -> RouteEntry | None:
        """Parse a journey-card Livewire snapshot into a RouteEntry."""
        data = snap.get("data", {})
        schedule_wrapper = data.get("schedule", [])
        if not schedule_wrapper or not schedule_wrapper[0]:
            return None

        schedule = schedule_wrapper[0]

        # ── Basic fields ──
        schedule_id = schedule.get("id")
        operator = schedule.get("operator_name", "Unknown")
        route_name = schedule.get("name", "")

        # ── Bus type ──
        vehicle_data = schedule.get("vehicle", [[], {}])
        vehicle = vehicle_data[0] if vehicle_data and vehicle_data[0] else {}
        bus_type = vehicle.get("type", "") or "Unknown"

        # ── Times ──
        start_time = schedule.get("start_time", "")
        arrival_times = schedule.get("arrival_times", [[], {}])
        arrival_list = arrival_times[0] if isinstance(arrival_times, list) and arrival_times else []
        end_time = arrival_list[-1] if arrival_list else ""

        dep_24 = _parse_time_12h(start_time)
        arr_24 = _parse_time_12h(end_time)

        if not dep_24:
            return None

        # ── Stops ──
        start_from = schedule.get("start_from", [[], {}])
        origin_stop = start_from[0].get("name", "") if start_from and start_from[0] else ""

        end_to = schedule.get("end_to", [[], {}])
        dest_stop = end_to[0].get("name", "") if end_to and end_to[0] else ""

        # ── Nearest counters (what the search matched) ──
        nearest_pickup = data.get("nearestPickupCounter", "") or origin_stop
        nearest_drop = data.get("nearestDestinationCounter", "") or dest_stop

        # ── Price ──
        fare = _parse_price(data.get("tripPrice") or schedule.get("total_price"))

        # ── Date ──
        journey_date = schedule.get("date", "")

        # ── Booking URL ──
        booking_url = (
            f"{self.base_url}/journeys/search"
            f"?pickup_id={data.get('fromID', '')}"
            f"&destination_id={data.get('toID', '')}"
            f"&date_of_journey={journey_date}"
        )

        # ── Build route name from origin/destination if not provided ──
        origin = nearest_pickup
        destination = nearest_drop

        return RouteEntry(
            origin=origin,
            destination=destination,
            operator=operator,
            departure_time=dep_24,
            arrival_time=arr_24,
            bus_type=bus_type,
            fare=fare,
            booking_url=booking_url,
            origin_stop=nearest_pickup,
            destination_stop=nearest_drop,
            route_number=str(schedule_id) if schedule_id else None,
        )

    async def _load_all_pages(self, page: Page) -> None:
        """Scroll down to trigger Livewire infinite-scroll pagination.

        Limited to 3 scrolls (max ~18 buses per route) to keep nightly
        scrape time reasonable. Over multiple nights we accumulate
        full schedule coverage naturally.
        """
        previous_count = 0

        for attempt in range(3):
            current_count = await page.evaluate(
                '''() => {
                    const cards = document.querySelectorAll('[wire\\\\:snapshot]');
                    return Array.from(cards).filter(el => {
                        const snap = el.getAttribute('wire:snapshot') || '';
                        return snap.includes('journey.journey-card');
                    }).length;
                }'''
            )

            if current_count == previous_count and attempt > 0:
                break

            previous_count = current_count
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)

    # ── Main entry point ────────────────────────────────────────────────

    async def scrape(self) -> ScrapeResult:
        """Discover routes and scrape all bus listings."""
        errors: list[str] = []
        all_entries: list[RouteEntry] = []

        try:
            routes = await self.discover_routes()
        except Exception as exc:
            logger.error(f"[magiya] Route discovery failed: {exc}")
            return ScrapeResult(
                platform_id=self.platform_id,
                scraped_at=datetime.now().isoformat(),
                status="failed",
                routes_found=0,
                entries=[],
                errors=[str(exc)],
            )

        for i, route in enumerate(routes):
            try:
                logger.info(
                    f"[magiya] [{i+1}/{len(routes)}] "
                    f"{route['from_city_name']} → {route['to_city_name']}"
                )
                entries = await self.scrape_route(route)
                all_entries.extend(entries)
                logger.info(f"[magiya]   → {len(entries)} buses found")
            except Exception as exc:
                msg = (
                    f"{route['from_city_name']}→{route['to_city_name']}: {exc}"
                )
                logger.warning(f"[magiya] Failed: {msg}")
                errors.append(msg)

        status = "success"
        if errors and not all_entries:
            status = "failed"
        elif errors:
            status = "partial"

        return ScrapeResult(
            platform_id=self.platform_id,
            scraped_at=datetime.now().isoformat(),
            status=status,
            routes_found=len(all_entries),
            entries=all_entries,
            errors=errors,
        )
