"""
Rathna Travels scraper for BusTime.lk

Rathna Travels is a single-operator Next.js SPA serving northern routes.
Uses UUID-based route URLs. Requires Playwright for JS rendering.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PwTimeout

from scrapers.base import RouteEntry, ScrapeResult

logger = logging.getLogger(__name__)

RATHNA_BASE = "https://rathnatravels.lk"


def _parse_time_12h(time_str: str) -> str:
    """Convert '7:15 PM' or '7:15PM' → '19:15' (24h)."""
    if not time_str:
        return ""
    t = time_str.strip()
    # Insert space if missing: "9:00AM" → "9:00 AM"
    t = re.sub(r'(\d)([AP]M)', r'\1 \2', t, flags=re.I)
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
        try:
            return datetime.strptime(t, fmt).strftime("%H:%M")
        except ValueError:
            continue
    return time_str.strip()


class RathnaTravelsScraper:
    """Scraper for Rathna Travels using Playwright."""

    platform_id = "rathna"
    platform_name = "Rathna Travels"
    base_url = RATHNA_BASE

    def __init__(self) -> None:
        self._playwright = None
        self._browser: Browser | None = None

    async def _ensure_browser(self) -> Browser:
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
        return self._browser

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def discover_routes(self) -> list[dict]:
        """Extract UUID-based route links from the homepage."""
        browser = await self._ensure_browser()
        page = await browser.new_page()

        try:
            await page.goto(self.base_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)

            html = await page.content()
        finally:
            await page.close()

        routes: list[dict] = []
        seen: set[str] = set()

        # Match route cards on homepage: "Jaffna → Colombo" style text
        city_pairs = re.findall(
            r'(\w[\w\s]+?)\s*→\s*(\w[\w\s]+)',
            html,
        )

        # Match /availableBuses/{uuid}/{uuid}/date
        uuid_matches = list(re.finditer(
            r'/availableBuses/([a-f0-9-]+)/([a-f0-9-]+)/(\d{4}-\d{2}-\d{2})',
            html,
        ))

        for i, match in enumerate(uuid_matches):
            origin_uuid = match.group(1)
            dest_uuid = match.group(2)

            key = f"{origin_uuid}-{dest_uuid}"
            if key in seen:
                continue
            seen.add(key)

            # Try to get city names from nearby text
            origin_city = ""
            dest_city = ""
            if i < len(city_pairs):
                origin_city = city_pairs[i][0].strip()
                dest_city = city_pairs[i][1].strip()

            routes.append({
                "origin_uuid": origin_uuid,
                "dest_uuid": dest_uuid,
                "origin_city": origin_city,
                "dest_city": dest_city,
            })

        logger.info(f"[rathna] Discovered {len(routes)} routes")
        return routes

    async def scrape_route(self, route: dict) -> list[RouteEntry]:
        """Load a route page and extract bus listings."""
        browser = await self._ensure_browser()
        page = await browser.new_page()
        entries: list[RouteEntry] = []

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        url = f"{self.base_url}/availableBuses/{route['origin_uuid']}/{route['dest_uuid']}/{tomorrow}"

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            try:
                await page.wait_for_selector('text=LKR', timeout=10000)
            except PwTimeout:
                logger.debug(f"[rathna] No results at {url}")
                return []

            await page.wait_for_timeout(2000)
            text = await page.inner_text('body')
            entries = self._parse_route_text(
                text, route.get("origin_city", ""), route.get("dest_city", "")
            )
        finally:
            await page.close()

        return entries

    def _parse_route_text(self, text: str, origin_city: str = "", dest_city: str = "") -> list[RouteEntry]:
        """Extract bus data from rendered page text."""
        entries: list[RouteEntry] = []
        seen_times: set[tuple[str, str]] = set()

        # Collapse whitespace
        text = " ".join(text.split())

        # Parse route name for origin/destination from [CITY - CITY] pattern
        route_match = re.search(r'([A-Z][A-Z\s]+?)\s*[-–]\s*([A-Z][A-Z\s]+?)\s*\[', text)
        if route_match and not origin_city:
            origin_city = route_match.group(1).strip().title()
            dest_city = route_match.group(2).strip().title()

        # Find fares: "3100 LKR"
        fares = re.findall(r'(\d[\d,]*)\s*LKR', text)

        # Find bus codes: "JF_9:00AM"
        codes = re.findall(r'([A-Z]{2,3}_\d{1,2}:\d{2}[AP]M)', text)

        # Find all times
        all_times = re.findall(r'(\d{1,2}:\d{2}\s*[AP]M)', text)

        # Map codes to their positions and nearest times
        fare_idx = 0
        for code_idx, code in enumerate(codes):
            # Find times near this code in the text
            code_pos = text.find(code)
            # Find times after this code position
            nearby_times = re.findall(r'(\d{1,2}:\d{2}\s*[AP]M)', text[code_pos:code_pos+300])

            if len(nearby_times) < 2:
                continue

            dep_time = _parse_time_12h(nearby_times[0])
            # Last time before the next code or "LKR" is the arrival
            arr_time = ""
            for t in reversed(nearby_times):
                t_pos = text[code_pos:code_pos+300].rfind(t)
                lkr_pos = text[code_pos:code_pos+300].find('LKR')
                if lkr_pos < 0 or t_pos < lkr_pos:
                    arr_time = _parse_time_12h(t)
                    break
            if not arr_time:
                arr_time = _parse_time_12h(nearby_times[1])

            if not dep_time:
                continue

            key = (dep_time, arr_time)
            if key in seen_times:
                continue
            seen_times.add(key)

            fare = None
            if fare_idx < len(fares):
                try:
                    fare = float(fares[fare_idx].replace(',', ''))
                except ValueError:
                    pass
                fare_idx += 1

            entries.append(RouteEntry(
                origin=origin_city,
                destination=dest_city,
                operator="Rathna Travels",
                departure_time=dep_time,
                arrival_time=arr_time,
                bus_type="Luxury",
                fare=fare,
                booking_url=self.base_url,
                origin_stop=origin_city,
                destination_stop=dest_city,
            ))

        return entries

    async def scrape(self) -> ScrapeResult:
        """Discover routes and scrape all bus listings."""
        errors: list[str] = []
        all_entries: list[RouteEntry] = []

        try:
            routes = await self.discover_routes()
        except Exception as exc:
            logger.error(f"[rathna] Route discovery failed: {exc}")
            return ScrapeResult(
                platform_id=self.platform_id,
                scraped_at=datetime.now(timezone.utc).isoformat(),
                status="failed",
                routes_found=0,
                entries=[],
                errors=[str(exc)],
            )

        for i, route in enumerate(routes):
            try:
                logger.info(f"[rathna] [{i+1}/{len(routes)}] scraping...")
                entries = await self.scrape_route(route)
                all_entries.extend(entries)
                logger.info(f"[rathna]   → {len(entries)} buses found")
            except Exception as exc:
                errors.append(str(exc))
                logger.warning(f"[rathna] Failed: {exc}")

        status = "success"
        if errors and not all_entries:
            status = "failed"
        elif errors:
            status = "partial"

        return ScrapeResult(
            platform_id=self.platform_id,
            scraped_at=datetime.now(timezone.utc).isoformat(),
            status=status,
            routes_found=len(all_entries),
            entries=all_entries,
            errors=errors,
        )
