"""
Base scraper class for BusTime.lk platform scrapers.

Provides:
- Async HTTP client with retry, rate limiting, and user-agent rotation
- HTML parsing via BeautifulSoup
- Structured output via ScrapeResult / RouteEntry dataclasses
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)

# ── User-agent rotation pool ────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

# ── Rate limiting ───────────────────────────────────────────────────────────
MIN_REQUEST_INTERVAL = 1.0  # seconds between requests to the same domain


@dataclass
class RouteEntry:
    """A single bus route/timetable entry scraped from a platform."""

    origin: str
    destination: str
    operator: str
    departure_time: str  # "HH:MM" 24h
    arrival_time: str  # "HH:MM" 24h
    bus_type: str  # "Super Luxury", "Luxury", "Semi Luxury", "Normal"
    fare: Optional[float] = None
    booking_url: str = ""
    origin_stop: Optional[str] = None  # specific boarding point
    destination_stop: Optional[str] = None  # specific drop-off point
    route_number: Optional[str] = None
    days_of_week: Optional[list[int]] = None  # [1..7], None = assume daily


@dataclass
class ScrapeResult:
    """Result from a single scraper run."""

    platform_id: str
    scraped_at: str  # ISO 8601
    status: str  # "success" | "partial" | "failed"
    routes_found: int = 0
    entries: list[RouteEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class BaseScraper:
    """
    Base class for all platform scrapers.

    Usage:
        class BusSeatScraper(BaseScraper):
            platform_id = "busseat"
            platform_name = "BusSeat.lk"
            base_url = "https://busseat.lk"

            async def scrape(self) -> ScrapeResult:
                ...
    """

    platform_id: str
    platform_name: str
    base_url: str

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._own_client = False
        self._last_request_time = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        """Return or create an httpx client with sensible defaults."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self._default_headers(),
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
            )
            self._own_client = True
        return self._client

    def _default_headers(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,si;q=0.8,ta;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _rate_limit(self) -> None:
        """Enforce minimum interval between requests."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            await asyncio.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.monotonic()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)
        ),
    )
    async def fetch(self, url: str) -> httpx.Response:
        """
        Fetch a URL with retry and rate limiting.

        Raises httpx.HTTPStatusError on 4xx/5xx after retries exhausted.
        """
        client = await self._get_client()
        await self._rate_limit()

        # Refresh user-agent per request
        client.headers["User-Agent"] = random.choice(USER_AGENTS)

        logger.info(f"[{self.platform_id}] GET {url}")
        response = await client.get(url)
        response.raise_for_status()
        logger.info(
            f"[{self.platform_id}] {url} → {response.status_code} ({len(response.text)} bytes)"
        )
        return response

    async def fetch_post(self, url: str, data: dict) -> httpx.Response:
        """POST to a URL with form data, retry, and rate limiting."""
        client = await self._get_client()
        await self._rate_limit()

        client.headers["User-Agent"] = random.choice(USER_AGENTS)

        logger.info(f"[{self.platform_id}] POST {url} {data}")
        response = await client.post(url, data=data)
        response.raise_for_status()
        logger.info(
            f"[{self.platform_id}] {url} → {response.status_code} ({len(response.text)} bytes)"
        )
        return response

    def parse(self, html: str) -> BeautifulSoup:
        """Parse HTML into a BeautifulSoup object using lxml."""
        return BeautifulSoup(html, "lxml")

    def now_iso(self) -> str:
        """Return current UTC time as ISO 8601 string."""
        return datetime.now(timezone.utc).isoformat()

    def result(
        self, status: str = "success", entries: list[RouteEntry] | None = None, errors: list[str] | None = None
    ) -> ScrapeResult:
        """Build a ScrapeResult with defaults filled."""
        entries = entries or []
        errors = errors or []
        return ScrapeResult(
            platform_id=self.platform_id,
            scraped_at=self.now_iso(),
            status=status,
            routes_found=len(entries),
            entries=entries,
            errors=errors,
        )

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._own_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def scrape(self) -> ScrapeResult:
        """Override in subclasses. Returns a ScrapeResult."""
        raise NotImplementedError("Subclasses must implement scrape()")
