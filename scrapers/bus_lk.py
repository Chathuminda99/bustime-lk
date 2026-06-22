"""
Bus.LK scraper for BusTime.lk

Bus.LK serves results via a simple AJAX endpoint (/search/data)
that returns HTML cards. No JavaScript rendering required — pure httpx.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode, urljoin

import httpx
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, RouteEntry, ScrapeResult

logger = logging.getLogger(__name__)

BUS_LK_BASE = "https://bus.lk"


def _parse_search_time(time_str: str) -> str:
    """Convert '07:50' → '07:50' (already 24h, just normalize)."""
    if not time_str:
        return ""
    time_str = time_str.strip()
    # Already 24h format
    try:
        return datetime.strptime(time_str, "%H:%M").strftime("%H:%M")
    except ValueError:
        return time_str


def _parse_fare(text: str) -> float | None:
    """Parse 'Rs.3,300.00' or '3,300.00' → 3300.0."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


class BusLKScraper(BaseScraper):
    """Scraper for Bus.LK using the /search/data AJAX endpoint."""

    platform_id = "bus_lk"
    platform_name = "Bus.LK"
    base_url = BUS_LK_BASE

    # ── Route discovery ─────────────────────────────────────────────────

    async def discover_routes(self) -> list[dict]:
        """
        Scrape the /bus-routes page for all linked city pairs.

        Returns list of dicts: {from_city, to_city, slug, url}
        """
        response = await self.fetch(f"{self.base_url}/bus-routes")
        soup = self.parse(response.text)

        routes: list[dict] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/bus-tickets/" not in href:
                continue

            # URL: /bus-tickets/{from}-to-{to}
            slug = href.rstrip("/").split("/")[-1]
            parts = slug.split("-to-")
            if len(parts) != 2:
                continue

            from_city = parts[0].replace("-", " ").title()
            to_city = parts[1].replace("-", " ").title()

            if slug in seen:
                continue
            seen.add(slug)

            routes.append(
                {
                    "from_city": from_city,
                    "to_city": to_city,
                    "slug": slug,
                    "url": urljoin(self.base_url, href),
                }
            )

        logger.info(f"[bus_lk] Discovered {len(routes)} routes")
        return routes

    # ── Search API ──────────────────────────────────────────────────────

    async def fetch_route_data(
        self, from_city: str, to_city: str, travel_date: str
    ) -> str:
        """
        Call the /search/data AJAX endpoint and return the HTML response.
        """
        params = {
            "from": from_city,
            "to": to_city,
            "from_date": travel_date,
            "type": "any",
            "departure": "asc",
        }
        url = f"{self.base_url}/search/data?{urlencode(params)}"

        client = await self._get_client()
        await self._rate_limit()

        headers = dict(client.headers)
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Referer"] = f"{self.base_url}/search?{urlencode(params)}"

        logger.info(f"[bus_lk] GET {url}")
        response = await client.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        if not data.get("success"):
            raise RuntimeError(f"API returned success=false")

        return data.get("html", "")

    # ── HTML card parsing ───────────────────────────────────────────────

    def parse_search_html(
        self, html: str, from_city: str, to_city: str
    ) -> list[RouteEntry]:
        """
        Parse the HTML returned by /search/data into RouteEntry objects.

        The HTML contains duplicate card structures for responsive display
        (desktop + mobile). We deduplicate by (bus_number, departure_time).
        """
        soup = self.parse(html)
        entries: list[RouteEntry] = []
        seen: set[tuple[str, str]] = set()

        # Each bus is in a .container.search_card
        for card in soup.find_all("div", class_="container"):
            card_classes = " ".join(card.get("class", []))
            if "search_card" not in card_classes:
                continue

            try:
                entry = self._parse_card(card, from_city, to_city)
                if not entry:
                    continue

                # Deduplicate by bus number + departure time
                key = (entry.route_number or "", entry.departure_time)
                if key in seen:
                    continue
                seen.add(key)

                # Skip entries with "Unknown" operator (they're duplicates
                # that lack the full data fields)
                if entry.operator == "Unknown" and entry.bus_type == "Unknown":
                    continue

                entries.append(entry)
            except Exception as exc:
                logger.debug(f"[bus_lk] Failed to parse card: {exc}")

        return entries

    def _parse_card(
        self, card, from_city: str, to_city: str
    ) -> RouteEntry | None:
        """Parse a single .container.search_card into a RouteEntry."""
        # Collapse text: join lines with space so regexes work across newlines
        raw_text = card.get_text()
        text = " ".join(raw_text.split())

        # ── Operator ──
        operator_match = re.search(r"Travel Name\s+(.+?)\s+Bus Number", text)
        operator = operator_match.group(1).strip() if operator_match else "Unknown"

        # ── Bus number ──
        bus_no_match = re.search(r"Bus Number\s+(\S+)", text)
        bus_number = bus_no_match.group(1).strip() if bus_no_match else None

        # ── Bus type ──
        type_match = re.search(r"Bus Type\s+([A-Za-z ]+?)\s+Rs\.", text)
        bus_type = type_match.group(1).strip() if type_match else "Unknown"

        # ── Departure time ──
        dep_match = re.search(
            r"Depature\s+\S+\s+Date\s+\w{3},\s+\d{2}\s+\w{3}\s+\d{4}\s+Time\s+(\d{2}:\d{2})",
            text,
        )
        dep_time = dep_match.group(1).strip() if dep_match else ""

        # ── Arrival time ──
        arr_match = re.search(
            r"Arrival\s+\S+\s+Date\s+\w{3},\s+\d{2}\s+\w{3}\s+\d{4}\s+Time\s+(\d{2}:\d{2})",
            text,
        )
        arr_time = arr_match.group(1).strip() if arr_match else ""

        if not dep_time:
            return None

        # ── Fare ──
        fare_match = re.search(r"Rs\.\s*(\d[\d,.]*)", text)
        fare = _parse_fare(fare_match.group(1)) if fare_match else None

        # ── Booking URL ──
        book_url = ""
        book_btn = card.find("a", href=True, string=re.compile(r"VIEW SEAT", re.I))
        if not book_btn:
            book_btn = card.find("a", href=True, string=re.compile(r"Book", re.I))
        if book_btn:
            book_url = urljoin(self.base_url, book_btn["href"])

        return RouteEntry(
            origin=from_city,
            destination=to_city,
            operator=operator,
            departure_time=dep_time,
            arrival_time=arr_time,
            bus_type=bus_type,
            fare=fare,
            booking_url=book_url,
            origin_stop=from_city,
            destination_stop=to_city,
            route_number=bus_number,
        )

    # ── Main entry point ────────────────────────────────────────────────

    async def scrape(self) -> ScrapeResult:
        """Discover routes, fetch data for each, parse results."""
        errors: list[str] = []
        all_entries: list[RouteEntry] = []
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        try:
            routes = await self.discover_routes()
        except Exception as exc:
            logger.error(f"[bus_lk] Route discovery failed: {exc}")
            return self.result(status="failed", errors=[str(exc)])

        for i, route in enumerate(routes):
            try:
                logger.info(
                    f"[bus_lk] [{i+1}/{len(routes)}] "
                    f"{route['from_city']} → {route['to_city']}"
                )
                html = await self.fetch_route_data(
                    route["from_city"], route["to_city"], tomorrow
                )
                entries = self.parse_search_html(
                    html, route["from_city"], route["to_city"]
                )
                all_entries.extend(entries)
                logger.info(f"[bus_lk]   → {len(entries)} buses found")
            except Exception as exc:
                msg = f"{route['from_city']}→{route['to_city']}: {exc}"
                logger.warning(f"[bus_lk] Failed: {msg}")
                errors.append(msg)

        status = "success"
        if errors and not all_entries:
            status = "failed"
        elif errors:
            status = "partial"

        return self.result(status=status, entries=all_entries, errors=errors)
