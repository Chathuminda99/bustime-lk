"""
BusSeat.lk scraper for BusTime.lk

Discovers routes from the homepage, then fetches each route page
to extract timetable data: operator, departure/arrival times, bus type,
fare, and booking links.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import urljoin

from scrapers.base import BaseScraper, RouteEntry, ScrapeResult

logger = logging.getLogger(__name__)

# ── Bus type mapping from CSS class ─────────────────────────────────────────
BUS_TYPE_MAP = {
    "btn-superlux": "Super Luxury",
    "btn-luxury": "Luxury",
    "btn-semiluxury": "Semi Luxury",
    "btn-normal": "Normal",
    "btn-semi-luxury": "Semi Luxury",
    "btn-super-luxury": "Super Luxury",
}


def _parse_bus_type(p_tag) -> str:
    """Extract bus type from the <p> tag's CSS class list or text content."""
    class_list = p_tag.get("class", [])

    # Match against known CSS class patterns
    for css_class, label in BUS_TYPE_MAP.items():
        if css_class in class_list:
            return label

    # Fallback: parse from visible text
    text = p_tag.get_text(strip=True).lower()
    if "super luxury" in text or "xl" in text:
        return "Super Luxury"
    if "semi luxury" in text:
        return "Semi Luxury"
    if "luxury" in text:
        return "Luxury"
    if "normal" in text:
        return "Normal"
    return text.strip()


def _parse_time_12h(time_str: str) -> str:
    """Convert '7:15 PM' or '07:15 PM' → '19:15' (24h)."""
    if not time_str:
        return ""
    time_str = time_str.strip()
    try:
        return datetime.strptime(time_str, "%I:%M %p").strftime("%H:%M")
    except ValueError:
        try:
            return datetime.strptime(time_str, "%I:%M%p").strftime("%H:%M")
        except ValueError:
            return time_str


def _parse_fare(fare_text: str) -> float | None:
    """Parse 'LKR 3000.00' → 3000.0 or '2,800.00' → 2800.0."""
    if not fare_text:
        return None
    cleaned = re.sub(r"[^\d.]", "", fare_text.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


class BusSeatScraper(BaseScraper):
    """Scraper for BusSeat.lk — private bus aggregator platform."""

    platform_id = "busseat"
    platform_name = "BusSeat.lk"
    base_url = "https://busseat.lk"

    # ── Route discovery ─────────────────────────────────────────────────

    async def discover_routes(self) -> list[dict]:
        """
        Scrape the homepage for all linked route pages.

        Returns list of dicts: {origin, destination, url}
        """
        response = await self.fetch(self.base_url)
        soup = self.parse(response.text)

        routes: list[dict] = []
        seen: set[str] = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if not href.startswith("/buses/"):
                continue

            # Normalize URL
            url = urljoin(self.base_url, href.rstrip("/"))
            if url in seen:
                continue
            seen.add(url)

            parts = href.rstrip("/").split("/")
            # /buses/{origin}/{destination}
            if len(parts) >= 4:
                origin = parts[2].replace("%20", " ")
                destination = parts[3].replace("%20", " ")
                routes.append(
                    {"origin": origin, "destination": destination, "url": url}
                )

        logger.info(f"[busseat] Discovered {len(routes)} routes from homepage")
        return routes

    # ── Route page parsing ──────────────────────────────────────────────

    def parse_route_page(self, html: str, route_url: str) -> list[RouteEntry]:
        """
        Parse a route page (e.g., /buses/Jaffna/Colombo) and extract
        all bus listings.
        """
        soup = self.parse(html)
        entries: list[RouteEntry] = []

        containers = soup.find_all("div", class_="booking-item-container")
        if not containers:
            logger.info(f"[busseat] No bus listings found at {route_url}")
            return entries

        # Extract route origin/destination from URL
        route_parts = route_url.rstrip("/").split("/")
        route_origin = route_parts[-2].replace("%20", " ") if len(route_parts) >= 2 else ""
        route_destination = route_parts[-1].replace("%20", " ") if len(route_parts) >= 1 else ""

        for container in containers:
            try:
                entry = self._parse_container(container, route_url, route_origin, route_destination)
                if entry:
                    entries.append(entry)
            except Exception as exc:
                logger.warning(f"[busseat] Failed to parse a bus listing: {exc}")

        return entries

    def _parse_container(
        self,
        container,
        route_url: str,
        route_origin: str,
        route_destination: str,
    ) -> RouteEntry | None:
        """Parse a single div.booking-item-container into a RouteEntry."""

        # ── Operator name ──
        operator_tag = container.find("h5", class_="booking-item-flight-class")
        operator = operator_tag.get_text(strip=True) if operator_tag else "Unknown"

        # ── Bus type ──
        # The bus type <p> has a class like "btn btn-superlux btn-block btn-xs"
        bus_type_tag = container.find(
            "p", class_=lambda c: any(cls.startswith("btn-") for cls in c) if isinstance(c, (list, tuple)) else str(c).startswith("btn-")
        )
        bus_type = _parse_bus_type(bus_type_tag) if bus_type_tag else "Unknown"

        # ── Route number ──
        route_num = ""
        for p in container.find_all("p", class_="booking-item-flight-class"):
            text = p.get_text(strip=True)
            if text.lower().startswith("route number"):
                route_num = text.replace("Route number:", "").strip()
                break

        # ── Wizard steps (origin → waypoint → destination) ──
        # Match "bs-wizard-step" as a whole class, not "bs-wizard-stepnum"
        wizard_steps = container.find_all(
            "div",
            class_=lambda c: (
                "bs-wizard-step" in c and "bs-wizard-stepnum" not in c
            ) if isinstance(c, (list, tuple)) else (
                c == "bs-wizard-step"
            ),
        )
        origin_stop = ""
        departure_time = ""
        destination_stop = ""
        arrival_time = ""

        if len(wizard_steps) >= 1:
            first_step = wizard_steps[0]
            origin_stop = self._get_step_city(first_step)
            departure_time = self._get_step_time(first_step)

        if len(wizard_steps) >= 2:
            last_step = wizard_steps[-1]
            destination_stop = self._get_step_city(last_step)
            arrival_time = self._get_step_time(last_step)

        # Use route URL parts as fallback for origin/destination
        if not origin_stop:
            origin_stop = route_origin
        if not destination_stop:
            destination_stop = route_destination

        # ── Fare ──
        fare_tag = container.find("p", class_="booking-item-price")
        fare = None
        if fare_tag:
            fare = _parse_fare(fare_tag.get_text(strip=True))

        # ── Booking URL ──
        booking_url = ""
        book_btn = container.find("a", class_="btn-primary")
        if book_btn and book_btn.get("href"):
            booking_url = urljoin(self.base_url, book_btn["href"])

        # ── Convert times to 24h ──
        dep_24 = _parse_time_12h(departure_time)
        arr_24 = _parse_time_12h(arrival_time)

        if not dep_24:
            logger.debug(f"[busseat] Could not parse departure time for '{operator}'")
            return None

        return RouteEntry(
            origin=origin_stop,
            destination=destination_stop,
            operator=operator,
            departure_time=dep_24,
            arrival_time=arr_24,
            bus_type=bus_type,
            fare=fare,
            booking_url=booking_url,
            origin_stop=origin_stop,
            destination_stop=destination_stop,
            route_number=route_num or None,
        )

    @staticmethod
    def _get_step_city(step) -> str:
        """Extract city name from a bs-wizard-step div."""
        stepnum = step.find("div", class_="bs-wizard-stepnum")
        if stepnum:
            return stepnum.get_text(strip=True)
        return ""

    @staticmethod
    def _get_step_time(step) -> str:
        """Extract time from a bs-wizard-step div."""
        timetag = step.find("div", class_="bs-wizard-time")
        if timetag:
            return timetag.get_text(strip=True)
        return ""

    # ── Main scrape entry point ────────────────────────────────────────

    async def scrape(self) -> ScrapeResult:
        """
        Main entry point: discover routes, fetch each, parse listings.
        """
        errors: list[str] = []
        all_entries: list[RouteEntry] = []

        try:
            routes = await self.discover_routes()
        except Exception as exc:
            logger.error(f"[busseat] Route discovery failed: {exc}")
            return self.result(status="failed", errors=[str(exc)])

        for i, route in enumerate(routes):
            try:
                logger.info(
                    f"[busseat] [{i+1}/{len(routes)}] {route['origin']} → {route['destination']}"
                )
                response = await self.fetch(route["url"])
                entries = self.parse_route_page(response.text, route["url"])
                all_entries.extend(entries)
                logger.info(
                    f"[busseat]   → {len(entries)} buses found"
                )
            except Exception as exc:
                msg = f"{route['origin']}→{route['destination']}: {exc}"
                logger.warning(f"[busseat] Failed: {msg}")
                errors.append(msg)

        status = "success"
        if errors and not all_entries:
            status = "failed"
        elif errors:
            status = "partial"

        return self.result(status=status, entries=all_entries, errors=errors)
