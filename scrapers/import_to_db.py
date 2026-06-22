"""
BusTime.lk — Import scraped JSON data into SQLite.

Reads all platform JSON files from data/output/, resolves station
and operator names to canonical IDs using the mappings config,
then upserts into the SQLite database.

Usage:
    python -m scrapers.import_to_db
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from api.database import get_connection, init_db

logger = logging.getLogger("import_to_db")

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "output"
MAPPINGS_DIR = Path(__file__).resolve().parent.parent / "config"

# ── Normalization ───────────────────────────────────────────────────────────


class NameResolver:
    """Resolves platform-specific station/operator names to canonical IDs."""

    def __init__(self, mappings_file: Path) -> None:
        with open(mappings_file) as f:
            self.config = json.load(f)

        # Build lookup: (platform_id, alias) → canonical id
        self.station_map: dict[tuple[str, str], str] = {}
        self.station_names: dict[str, str] = {}  # id → canonical name

        for station in self.config.get("stations", []):
            sid = station["id"]
            self.station_names[sid] = station["canonical_name"]
            for platform_id, alias_value in station.get("aliases", {}).items():
                # Support both single string and list of strings
                aliases = alias_value if isinstance(alias_value, list) else [alias_value]
                for alias in aliases:
                    self.station_map[(platform_id, alias)] = sid

    def resolve_station(self, platform_id: str, name: str) -> tuple[Optional[str], Optional[str]]:
        """Return (canonical_id, canonical_name) or (None, None)."""
        clean_name = name.strip()
        key = (platform_id, clean_name)
        if key in self.station_map:
            sid = self.station_map[key]
            return sid, self.station_names.get(sid, clean_name)
        return None, None


# ── Import logic ────────────────────────────────────────────────────────────


class DataImporter:
    """Imports scraped JSON files into the SQLite database."""

    def __init__(self) -> None:
        self.conn = get_connection()
        self.resolver = NameResolver(MAPPINGS_DIR / "station_mappings.json")

        # Build operator lookup dynamically from the data
        self.operator_ids: dict[str, str] = {}
        self._next_operator_id = 1

    def _get_operator_id(self, platform_id: str, name: str) -> str:
        """Get or create a canonical operator ID."""
        safe_name = name.strip()
        # Use a slug as canonical ID
        slug = safe_name.lower().replace(" ", "-").replace("(", "").replace(")", "")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")[:50]

        key = f"{platform_id}:{safe_name}"
        if key not in self.operator_ids:
            # Check if slug exists
            cur = self.conn.execute(
                "SELECT id FROM operators WHERE id = ?", (slug,)
            )
            if not cur.fetchone():
                self.conn.execute(
                    "INSERT OR IGNORE INTO operators (id, canonical_name) VALUES (?, ?)",
                    (slug, safe_name),
                )
            self.conn.execute(
                "INSERT OR IGNORE INTO operator_aliases (operator_id, platform_id, alias_name) VALUES (?, ?, ?)",
                (slug, platform_id, safe_name),
            )
            self.operator_ids[key] = slug
            self.conn.commit()

        return self.operator_ids[key]

    def _ensure_station(self, canonical_id: str, canonical_name: str) -> None:
        """Ensure the station exists in the database."""
        self.conn.execute(
            "INSERT OR IGNORE INTO stations (id, canonical_name) VALUES (?, ?)",
            (canonical_id, canonical_name),
        )
        self.conn.commit()

    def _ensure_station_alias(
        self, canonical_id: str, platform_id: str, alias_name: str
    ) -> None:
        """Ensure the station alias is recorded."""
        self.conn.execute(
            "INSERT OR IGNORE INTO station_aliases (station_id, platform_id, alias_name) VALUES (?, ?, ?)",
            (canonical_id, platform_id, alias_name),
        )
        self.conn.commit()

    def import_platform(self, json_path: Path) -> dict:
        """Import a single platform's JSON file."""
        with open(json_path) as f:
            data = json.load(f)

        platform_id = data["platform_id"]
        status = data.get("status", "unknown")
        entries = data.get("entries", [])

        imported = 0
        skipped = 0
        unknown_stations = set()

        for entry in entries:
            origin_raw = entry.get("origin_stop") or entry.get("origin", "")
            dest_raw = entry.get("destination_stop") or entry.get("destination", "")
            operator_raw = entry.get("operator", "")

            # Resolve stations
            origin_id, origin_name = self.resolver.resolve_station(
                platform_id, origin_raw
            )
            dest_id, dest_name = self.resolver.resolve_station(
                platform_id, dest_raw
            )

            if not origin_id:
                unknown_stations.add((platform_id, origin_raw))
            if not dest_id:
                unknown_stations.add((platform_id, dest_raw))

            if not origin_id or not dest_id:
                skipped += 1
                continue

            # Ensure stations and aliases exist
            self._ensure_station(origin_id, origin_name or origin_raw)
            self._ensure_station(dest_id, dest_name or dest_raw)
            self._ensure_station_alias(origin_id, platform_id, origin_raw)
            self._ensure_station_alias(dest_id, platform_id, dest_raw)

            # Resolve operator
            operator_id = self._get_operator_id(platform_id, operator_raw)

            # Find or create route
            cur = self.conn.execute(
                """INSERT OR IGNORE INTO routes (origin_station_id, destination_station_id)
                   VALUES (?, ?) RETURNING id""",
                (origin_id, dest_id),
            )
            row = cur.fetchone()
            if row:
                route_id = row[0]
            else:
                cur = self.conn.execute(
                    "SELECT id FROM routes WHERE origin_station_id = ? AND destination_station_id = ?",
                    (origin_id, dest_id),
                )
                route_id = cur.fetchone()[0]

            # Insert schedule
            fare = entry.get("fare")
            if fare is not None:
                try:
                    fare = float(fare)
                except (ValueError, TypeError):
                    fare = None

            self.conn.execute(
                """INSERT OR IGNORE INTO schedules
                   (route_id, platform_id, operator_id, departure_time,
                    arrival_time, bus_type, fare, booking_url, route_number, scraped_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    route_id,
                    platform_id,
                    operator_id,
                    entry.get("departure_time", ""),
                    entry.get("arrival_time", ""),
                    entry.get("bus_type", ""),
                    fare,
                    entry.get("booking_url", ""),
                    entry.get("route_number", ""),
                    data.get("scraped_at", datetime.now(timezone.utc).isoformat()),
                ),
            )
            imported += 1

        self.conn.commit()

        return {
            "platform_id": platform_id,
            "status": status,
            "imported": imported,
            "skipped": skipped,
            "unknown_stations": len(unknown_stations),
            "unknown_list": sorted(unknown_stations) if unknown_stations else [],
        }

    def run(self) -> None:
        """Import all JSON files in the output directory."""
        json_files = sorted(
            [f for f in OUTPUT_DIR.glob("*.json") if not f.name.startswith("_")]
        )

        if not json_files:
            logger.warning("No JSON files found in data/output/")
            return

        total_imported = 0
        total_skipped = 0
        all_unknown: set = set()

        for json_path in json_files:
            logger.info(f"Importing {json_path.name} ...")
            result = self.import_platform(json_path)
            total_imported += result["imported"]
            total_skipped += result["skipped"]

            for u in result["unknown_list"]:
                all_unknown.add(u)

            logger.info(
                f"  → {result['imported']} imported, "
                f"{result['skipped']} skipped, "
                f"{result['unknown_stations']} unknown stations"
            )

        if all_unknown:
            logger.warning(
                f"{len(all_unknown)} unmapped station names found. "
                f"Add them to config/station_mappings.json"
            )
            for platform_id, name in sorted(all_unknown):
                logger.info(f"  [{platform_id}] {name}")

        logger.info(
            f"Done: {total_imported} entries imported, {total_skipped} skipped"
        )

    def close(self) -> None:
        self.conn.close()


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    init_db()
    importer = DataImporter()
    try:
        importer.run()
    finally:
        importer.close()


if __name__ == "__main__":
    main()
