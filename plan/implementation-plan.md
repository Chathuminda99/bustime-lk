# BusBooking Cross-Platform Aggregator — Implementation Plan

## Context

Sri Lanka has multiple siloed bus booking platforms (BusSeat.lk, Magiya.lk, Bus.LK, SLTB eSeat, etc.) — passengers currently search each site separately to find routes, timetables, and fares. This project builds a **cross-platform timetable search engine** (not a booking system) that aggregates static timetable/route/fare data from all platforms via nightly scraping and presents a unified search interface. Users find their bus, compare options across platforms, then click through to book on the source platform.

## Tech Stack (Final)

| Layer | Technology |
|-------|-----------|
| Scrapers | Python (httpx + BeautifulSoup4 + lxml) |
| Scheduler | GitHub Actions scheduled workflow (nightly) |
| Database | SQLite (single file, zero-config) |
| Backend API | FastAPI (Python) |
| Frontend | React (Next.js, App Router) |
| Deployment | VPS via GitHub Actions deploy pipeline |

## Project Structure

```
busbooking-crossplatform/
├── .github/
│   └── workflows/
│       ├── nightly-scrape.yml      # Scheduled scraper run
│       └── deploy.yml              # Deploy to VPS on push to main
├── scrapers/
│   ├── __init__.py
│   ├── base.py                     # BaseScraper class (HTTP, retries, logging)
│   ├── busseat.py                  # BusSeat.lk scraper
│   ├── bus_lk.py                   # Bus.LK scraper
│   ├── magiya.py                   # Magiya.lk scraper
│   ├── sltb_eseat.py              # SLTB eSeat scraper
│   ├── busticket_gov.py           # BusTicket.gov.lk scraper (when live)
│   ├── rathna.py                  # Rathna Travels scraper
│   ├── go12.py                    # 12Go Asia scraper
│   ├── import_to_db.py            # Reads JSON → populates SQLite
│   └── run_all.py                 # Orchestrator: runs all scrapers, writes JSON
├── config/
│   ├── station_mappings.json      # Platform station names → canonical
│   ├── operator_mappings.json     # Platform operator names → canonical
│   └── platforms.json             # Platform metadata (URLs, enabled/disabled)
├── data/
│   └── output/                    # Scraped JSON files (committed to repo)
│       ├── busseat.json
│       ├── bus_lk.json
│       ├── magiya.json
│       └── ...
├── api/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── database.py                # SQLite connection + schema init
│   ├── models.py                  # Pydantic models
│   ├── routes/
│   │   ├── search.py              # GET /api/search
│   │   ├── routes.py              # GET /api/routes
│   │   ├── stations.py            # GET /api/stations (autocomplete)
│   │   └── platforms.py           # GET /api/platforms
│   └── import_data.py             # Endpoint/script to load JSON → SQLite
├── web/                           # Next.js app
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx           # Home: search form
│   │   │   ├── search/
│   │   │   │   └── page.tsx       # Search results (SSR from API)
│   │   │   └── route/
│   │   │       └── [id]/
│   │   │           └── page.tsx   # Route detail with all platforms
│   │   ├── components/
│   │   │   ├── SearchForm.tsx
│   │   │   ├── SearchResults.tsx
│   │   │   ├── RouteCard.tsx      # One route, shows all platform options
│   │   │   ├── StationAutocomplete.tsx
│   │   │   └── PlatformBadge.tsx
│   │   └── lib/
│   │       └── api.ts             # API client functions
│   └── public/
└── README.md
```

## Phase 1: Data Foundation (Days 1–3)

### 1.1 Station Name Normalization (`config/station_mappings.json`)

Manually build a canonical registry of ~60-80 stations across Sri Lanka. Each entry maps platform-specific names to a canonical name:

```json
{
  "stations": [
    {
      "id": "colombo-fort",
      "canonical_name": "Colombo Fort",
      "canonical_name_si": "කොළඹ කොටුව",
      "canonical_name_ta": "கொழும்பு கோட்டை",
      "aliases": {
        "busseat": "Colombo",
        "bus_lk": "Colombo Fort",
        "magiya": "Pettah (Bastian MW)",
        "sltb_eseat": "Colombo",
        "rathna": "Colombo",
        "go12": "Colombo Central Bus Station"
      },
      "lat": 6.9344,
      "lng": 79.8431
    }
  ]
}
```

### 1.2 Operator Name Normalization (`config/operator_mappings.json`)

Same pattern for bus operators — same operator may appear under different names on different platforms.

### 1.3 SQLite Schema (`api/database.py`)

```sql
CREATE TABLE platforms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    enabled INTEGER DEFAULT 1
);

CREATE TABLE stations (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    canonical_name_si TEXT,
    canonical_name_ta TEXT,
    lat REAL,
    lng REAL
);

CREATE TABLE station_aliases (
    station_id TEXT REFERENCES stations(id),
    platform_id TEXT REFERENCES platforms(id),
    alias_name TEXT NOT NULL,
    PRIMARY KEY (station_id, platform_id)
);

CREATE TABLE operators (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL
);

CREATE TABLE operator_aliases (
    operator_id TEXT REFERENCES operators(id),
    platform_id TEXT REFERENCES platforms(id),
    alias_name TEXT NOT NULL,
    PRIMARY KEY (operator_id, platform_id)
);

CREATE TABLE routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin_station_id TEXT REFERENCES stations(id),
    destination_station_id TEXT REFERENCES stations(id),
    UNIQUE(origin_station_id, destination_station_id)
);

CREATE TABLE schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER REFERENCES routes(id),
    platform_id TEXT REFERENCES platforms(id),
    operator_id TEXT REFERENCES operators(id),
    departure_time TEXT NOT NULL,        -- HH:MM format
    arrival_time TEXT,                   -- HH:MM format
    days_of_week TEXT,                   -- "1,2,3,4,5,6,7" (Mon-Sun)
    bus_type TEXT,                       -- "Normal","Semi Luxury","Luxury","Super Luxury"
    fare REAL,
    booking_url TEXT,                    -- Deep link to book on source platform
    scraped_at TEXT NOT NULL,            -- ISO timestamp
    UNIQUE(route_id, platform_id, operator_id, departure_time, days_of_week)
);

CREATE TABLE scrape_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id TEXT REFERENCES platforms(id),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT,                         -- "success", "failed", "partial"
    routes_found INTEGER DEFAULT 0,
    error_message TEXT
);
```

## Phase 2: Python Scrapers (Days 3–7)

### 2.1 Base Scraper (`scrapers/base.py`)

```python
class BaseScraper:
    platform_id: str
    platform_name: str
    base_url: str
    
    async def fetch(url) -> httpx.Response
    def parse_soup(html) -> BeautifulSoup
    def normalize_station(platform_name) -> str | None
    def normalize_operator(platform_name) -> str | None
    async def scrape() -> ScrapeResult
    def log_success/failure()
```

- Uses `httpx` with async and `BeautifulSoup4`
- Built-in retry (3 attempts, exponential backoff)
- User-agent rotation
- Rate limiting (1 req/sec per domain)
- Outputs structured `ScrapeResult` with list of `RouteInfo` dicts

### 2.2 Per-Platform Scrapers

**BusSeat.lk** (`scrapers/busseat.py`):
- Strategy: Enumerate the `/buses/{origin}/{destination}` URL pattern for known station pairs
- Extract: departure times, operator names, bus types, fares, booking URL
- Public route listing pages are accessible without auth

**Bus.LK** (`scrapers/bus_lk.py`):
- Strategy: Use the "View all routes" directory page, then iterate route pages
- Extract: operator, bus type, departure times, fare range

**Magiya.lk** (`scrapers/magiya.py`):
- Strategy: POST to `/journeys/search` with known origin-destination pairs
- Extract: operator, departure time, bus type, fare, booking URL

**SLTB eSeat** (`scrapers/sltb_eseat.py`):
- Strategy: Use public FAQ/timetable pages; form POST for route search
- Extract: departure times, route info (SLTB-only, single operator)

**Rathna Travels** (`scrapers/rathna.py`):
- Strategy: Simple single-site scrape — very few routes
- Extract: departure times, fares

**12Go Asia** (`scrapers/go12.py`):
- Strategy: Sri Lanka-specific pages; or use Apify scraper API for reliable data
- Extract: operator, departure, bus type, fare

### 2.3 Scraped JSON Output Format

Each scraper writes to `data/output/{platform_id}.json`:

```json
{
  "platform_id": "busseat",
  "scraped_at": "2026-06-23T02:00:00+05:30",
  "status": "success",
  "routes_found": 87,
  "entries": [
    {
      "origin": "Jaffna",
      "destination": "Colombo",
      "operator": "Superline Travels",
      "departure_time": "06:00",
      "arrival_time": "11:30",
      "days_of_week": [1,2,3,4,5,6,7],
      "bus_type": "Super Luxury",
      "fare": 3500.00,
      "booking_url": "https://busseat.lk/buses/Jaffna/Colombo/..."
    }
  ]
}
```

## Phase 3: Data Import Pipeline (Day 7–8)

### 3.1 Import Script (`scrapers/import_to_db.py`)

- Reads all JSON files from `data/output/`
- For each entry, resolves platform station names → canonical station IDs using `config/station_mappings.json`
- Resolves operator names → canonical operator IDs
- Upserts into SQLite (INSERT OR IGNORE for new, UPDATE for changed)
- Writes entry to `scrape_logs`
- Runs as part of the GHA workflow (scrape → import → commit updated DB)

### 3.2 Data Flow

```
GHA (nightly 2:00 AM IST)
  → python scrapers/run_all.py       # Run all scrapers → data/output/*.json
  → python scrapers/import_to_db.py   # Load JSON → SQLite
  → git add data/output/ data/buses.db
  → git commit -m "Nightly scrape: $(date)"
  → git push
```

VPS:
- Git pulls on a cron (every 30 min) or webhook-triggered
- FastAPI reads SQLite directly from the pulled file
- Alternatively: GHA deploys the updated DB + code to VPS via SSH

## Phase 4: FastAPI Backend (Day 8–10)

### 4.1 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/search` | GET | Search routes: `?from=colombo-fort&to=kandy&date=2026-06-25` |
| `/api/routes` | GET | List all routes (paginated) |
| `/api/routes/{id}` | GET | Route detail: all platforms offering this route |
| `/api/stations` | GET | Station autocomplete: `?q=colo` |
| `/api/platforms` | GET | List active platforms |
| `/api/health` | GET | Health check, last scrape time |

### 4.2 Search Endpoint Logic

1. Resolve `from`/`to` station IDs
2. Find matching routes in `routes` table
3. Join with `schedules` for those routes
4. Group results by route, then by platform
5. Return unified response showing all platform options for the route

### 4.3 Key Design Decisions

- SQLite read via aiosqlite (async)
- CORS enabled for Next.js frontend
- No auth needed (read-only public data)
- Pagination on list endpoints

## Phase 5: Next.js Frontend (Day 10–17)

### 5.1 Pages

**Home Page** (`/`):
- Hero section with search form: From, To, Date
- Autocomplete station inputs (debounced fetch to `/api/stations?q=...`)
- Quick links to popular routes
- Mobile-first design

**Search Results** (`/search?from=X&to=Y&date=Z`):
- Server-side rendered (fetch from FastAPI at request time)
- Results grouped by route, showing each platform's offering side-by-side
- Each card shows: operator, departure time, arrival time, bus type, fare, platform badge
- "Book Now" button deep-links to the source platform
- Filter by: departure time range, bus type, platform
- Sort by: departure time, fare, bus type

**Route Detail** (`/route/[id]`):
- Full timetable for a specific origin-destination pair
- All platforms stacked, all operators listed
- Days-of-week indicator

### 5.2 Components

- `SearchForm` — controlled form with autocomplete, date picker
- `StationAutocomplete` — debounced async select
- `RouteCard` — single route result with platform comparison
- `PlatformBadge` — colored badge per platform (BusSeat=blue, Magiya=orange, etc.)
- `TimetableGrid` — visual timetable for route detail page
- `FilterBar` — departure time slider, bus type checkboxes, platform toggles

### 5.3 Styling

- Tailwind CSS
- Mobile-first responsive
- Light/dark mode support
- Clean, simple design — Sri Lankan commuters will use this on mobile primarily

## Phase 6: CI/CD (Day 17–19)

### 6.1 Nightly Scrape Workflow (`.github/workflows/nightly-scrape.yml`)

```yaml
name: Nightly Scrape
on:
  schedule:
    - cron: '30 20 * * *'   # 2:00 AM IST (UTC+5:30 = 20:30 UTC)
  workflow_dispatch:         # Manual trigger
jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - run: pip install -r scrapers/requirements.txt
      - run: python scrapers/run_all.py
      - run: python scrapers/import_to_db.py
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: 'chore: nightly scrape data update'
          file_pattern: 'data/'
```

### 6.2 Deploy Workflow (`.github/workflows/deploy.yml`)

```yaml
name: Deploy to VPS
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/busbooking
            git pull origin main
            pip install -r api/requirements.txt
            systemctl restart busbooking-api
            cd web && npm install && npm run build
            pm2 restart busbooking-web
```

### 6.3 VPS Setup

- FastAPI served via uvicorn behind nginx reverse proxy
- Next.js served via `next start` (or static export to nginx)
- SQLite file at `/opt/busbooking/data/buses.db`
- `systemd` unit for FastAPI, `pm2` for Next.js

## Phase 7: Monitoring & Polish (Day 19–21)

- Scrape failure alerts: if `scrape_logs` shows failure, GHA sends email or Slack notification
- Admin dashboard (simple page at `/admin`): shows scrape status per platform, last successful run, route counts
- Sitemap generation for SEO
- Basic analytics (plausible.io or similar privacy-friendly)
- PWA setup for mobile install

## Verification Plan

### Scrapers
- Run `python scrapers/run_all.py` manually, verify JSON output in `data/output/`
- Check `scrape_logs` table for success/failure counts
- Spot-check 3-4 routes per platform against live website

### API
- `curl http://localhost:8000/api/search?from=colombo-fort&to=kandy&date=2026-06-25`
- Verify response includes entries from multiple platforms
- Test all endpoints with `pytest` + `httpx.AsyncClient`

### Frontend
- `npm run dev` in `web/`, verify:
  - Home page loads with search form
  - Autocomplete works for station search
  - Search returns results from API
  - "Book Now" links open correct external URLs
  - Mobile responsive (test at 375px width)

### CI/CD
- Push to main, verify deploy completes and site is live on VPS
- Manually trigger nightly scrape workflow, verify data updates appear on site

## Key Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| Platform changes HTML structure | Base scraper has defensive parsing; alerts on failure; easy to update one scraper |
| Platform blocks IP | GHA rotates runner IPs; low volume (nightly) is unlikely to trigger blocks |
| Station name mapping gaps | Unmapped names logged; manual review of `unmapped_stations` report after each scrape |
| SQLite write contention | Single writer (import script); reads are concurrent-safe via aiosqlite WAL mode |
| VPS cost | $5-10/mo VPS sufficient for this workload; SQLite = no DB server cost |
