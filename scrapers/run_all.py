"""
BusTime.lk — Scraper Orchestrator

Runs all enabled platform scrapers and writes results to data/output/*.json.
Intended to be triggered by GitHub Actions nightly workflow.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from scrapers.busseat import BusSeatScraper
from scrapers.magiya import MagiyaScraper
from scrapers.bus_lk import BusLKScraper
from scrapers.sltb_eseat import SLTBeSeatScraper
from scrapers.rathna import RathnaTravelsScraper
from scrapers.go12 import Go12Scraper

# ── Config ──────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("run_all")

# ── Scraper registry ────────────────────────────────────────────────────────
SCRAPERS = [
    BusSeatScraper,
    MagiyaScraper,
    BusLKScraper,
    SLTBeSeatScraper,
    RathnaTravelsScraper,
    Go12Scraper,
]


class ScrapeRun:
    """Runs all registered scrapers and writes JSON output."""

    def __init__(self) -> None:
        self.results: dict[str, dict] = {}

    async def run(self) -> None:
        """Run all scrapers sequentially."""
        logger.info(f"Starting scrape run — {len(SCRAPERS)} scraper(s) registered")

        for scraper_cls in SCRAPERS:
            scraper = scraper_cls()
            try:
                logger.info(f"─── {scraper.platform_name} ───")
                result = await scraper.scrape()
                self._save_result(result)
                logger.info(
                    f"[{scraper.platform_id}] {result.status.upper()} — "
                    f"{result.routes_found} routes, {len(result.errors)} errors"
                )
            except Exception as exc:
                logger.error(f"[{scraper.platform_id}] Scraper crashed: {exc}", exc_info=True)
                self._save_error(scraper.platform_id, str(exc))
            finally:
                await scraper.close()

        self._write_summary()

    def _save_result(self, result) -> None:
        """Write a single scraper's result to JSON."""
        data = {
            "platform_id": result.platform_id,
            "scraped_at": result.scraped_at,
            "status": result.status,
            "routes_found": result.routes_found,
            "errors": result.errors,
            "entries": [
                {
                    "origin": e.origin,
                    "destination": e.destination,
                    "operator": e.operator,
                    "departure_time": e.departure_time,
                    "arrival_time": e.arrival_time,
                    "bus_type": e.bus_type,
                    "fare": e.fare,
                    "booking_url": e.booking_url,
                    "origin_stop": e.origin_stop,
                    "destination_stop": e.destination_stop,
                    "route_number": e.route_number,
                }
                for e in result.entries
            ],
        }

        output_path = OUTPUT_DIR / f"{result.platform_id}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"  Wrote {output_path}")

        self.results[result.platform_id] = {
            "status": result.status,
            "routes_found": result.routes_found,
            "errors": len(result.errors),
        }

    def _save_error(self, platform_id: str, error_msg: str) -> None:
        """Write an error result when a scraper crashes entirely."""
        data = {
            "platform_id": platform_id,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "routes_found": 0,
            "errors": [error_msg],
            "entries": [],
        }
        output_path = OUTPUT_DIR / f"{platform_id}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.results[platform_id] = {"status": "failed", "routes_found": 0, "errors": 1}

    def _write_summary(self) -> None:
        """Write a summary of all scraper runs."""
        summary = {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "scrapers": self.results,
            "total_routes": sum(r["routes_found"] for r in self.results.values()),
        }
        summary_path = OUTPUT_DIR / "_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        logger.info(f"Summary: {summary_path}")


# ── CLI entry point ─────────────────────────────────────────────────────────


async def main() -> None:
    runner = ScrapeRun()
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
