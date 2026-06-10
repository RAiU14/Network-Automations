# Cisco_Automations

This repository contains several network automation experiments and tools. The older folders are intentionally kept for reference and backward compatibility.

The current active product work is:

```text
Cisco_EOX_Manager/
```

Cisco EOX Manager is a standalone Cisco End-of-Life / End-of-Sale data product with its own backend, frontend, database models, Auto_Pop crawler, GraphQL read layer, and tests.

## Active product: Cisco_EOX_Manager

Use this when you want to:

- Build a local Cisco PID/EOX database.
- Scrape Cisco EOX announcement tables.
- Store every affected PID row and lifecycle field in PostgreSQL or SQLite.
- Query the database through GraphQL, including JSON-shaped retrieval directly from DB.
- Use a beginner-friendly GUI for setup, lookup, raw Cisco table viewing, Auto_Pop jobs, and exports.
- Prepare for later Cisco API live testing.
- Run without account/admin authentication by default for local free-tool usage.
- Use PostgreSQL JSONB/GIN indexing for scalable raw table evidence search.

Main folder:

```text
Network-Automations/
└── Cisco_EOX_Manager/
```

Detailed documentation:

```text
Cisco_EOX_Manager/README.md
Cisco_EOX_Manager/backend/README.md
Cisco_EOX_Manager/front_end/README.md
Cisco_EOX_Manager/tests/README.md
Database/README_AUTO_POP.md
```

## Cisco EOX Manager quick start

```bash
cd Cisco_EOX_Manager
cp .env.example .env
docker compose up --build
```

Open:

```text
React GUI:      http://127.0.0.1:5173
Backend docs:   http://127.0.0.1:8000/docs
GraphQL:        http://127.0.0.1:8000/graphql
```

Run Auto_Pop with a small safe test from CLI, or start it from the GUI Auto_Pop jobs panel:

```bash
python tools/auto_pop_pid_database.py --limit-categories 1 --limit-series-eox 10 --limit-announcements 2
```

Use SQLite for quick local testing:

```bash
python tools/auto_pop_pid_database.py --sqlite --limit-categories 1
```

## Current Cisco EOX Manager direction

```text
Cisco website / Cisco API later
        ↓
Auto_Pop / lookup engine
        ↓
PostgreSQL or SQLite
        ↓
GraphQL / GUI / CSV / Excel exports
```

The database is the source of truth. JSON seed/import/export files are no longer part of the Cisco EOX Manager workflow. JSON-shaped retrieval comes from GraphQL queries against the database.

## Repository folders

```text
Network-Automations/
├── Cisco_EOX_Manager/   # Active standalone Cisco EOX product
├── EOX/                 # Legacy scraper compatibility code
├── EOX_API/             # Legacy/service-style EOX API code
├── Database/            # Legacy DB experiments plus Auto_Pop wrapper
├── PM_Report/           # Older PM report work, currently not part of EOX Manager
├── EN-NMS/              # Older NMS work
├── WebPage/             # Older web workflow
├── front_end/           # Older EOX_API React UI experiment
└── other legacy scripts
```

## Auto_Pop wrapper

The old command still works:

```bash
python Database/auto_pop.py --limit-categories 1
```

It forwards to:

```text
Cisco_EOX_Manager/tools/auto_pop_pid_database.py
```

## Tests

```bash
cd Cisco_EOX_Manager
pip install -r requirements-dev.txt
pytest -q
```

## Disclaimer

This project is not affiliated with or endorsed by Cisco. Scraped data comes from publicly available Cisco pages. Always validate lifecycle dates directly with Cisco before using the data for renewals, migrations, procurement, audits, or customer-facing decisions.

## GUI behavior

The GUI no longer asks users to choose API or scraper. Users add or remove PID chips and click search. The backend checks the DB first, uses Cisco API only if credentials are already configured, then falls back to scraping and saves new data.
