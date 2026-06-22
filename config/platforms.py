"""
BusTime.lk — BusSeat.lk Scraper Configuration

Platform-specific metadata.
"""

PLATFORMS = [
    {
        "id": "busseat",
        "name": "BusSeat.lk",
        "base_url": "https://busseat.lk",
        "enabled": True,
        "route_url_pattern": "/buses/{origin}/{destination}",
        "notes": "Private aggregator, ~12 operators, 25+ routes",
    },
]
