"""
12Go Asia scraper for BusTime.lk — PLACEHOLDER

12Go Asia (12go.com) has strong Cloudflare anti-bot protection that blocks
both httpx and Playwright. This scraper is a placeholder that returns an
empty result with a clear status message.

To scrape 12Go in the future, options include:
- Apify 12Go scraper (https://apify.com/jungle_synthesizer/12go-asia-multimodal-scraper)
- Residential proxies + browser fingerprinting
- Official partnership/API (they don't offer a public API)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from scrapers.base import RouteEntry, ScrapeResult

logger = logging.getLogger(__name__)


class Go12Scraper:
    """Placeholder scraper for 12Go Asia — blocked by Cloudflare."""

    platform_id = "go12"
    platform_name = "12Go Asia"

    async def close(self) -> None:
        pass

    async def scrape(self) -> ScrapeResult:
        logger.warning(
            "[go12] 12Go Asia is blocked by Cloudflare anti-bot protection. "
            "Skipping. Consider using the Apify 12Go scraper as an alternative."
        )
        return ScrapeResult(
            platform_id=self.platform_id,
            scraped_at=datetime.now(timezone.utc).isoformat(),
            status="failed",
            routes_found=0,
            entries=[],
            errors=["Blocked by Cloudflare anti-bot protection"],
        )
