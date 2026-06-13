# Cisco EOX Manager Backend

FastAPI backend for Cisco EOX Manager.

## Main responsibilities

```text
REST API
GraphQL read layer
DB setup for SQLite/PostgreSQL
Auto_Pop background jobs
Smart PID lookup
Cisco scraper/API integration points
CSV/XLSX export
Frontend/system logging
```

## Important routes

```text
GET  /health
GET  /api/setup/status
POST /api/setup/database/use-sqlite
POST /api/setup/database/configure
POST /api/setup/database/initialize
POST /api/eox/lookup
GET  /api/eox/stats
GET  /api/eox/evidence/{pid}
POST /api/autopop/jobs
GET  /api/autopop/jobs
DELETE /api/autopop/jobs/clear
GET  /api/export/options/eox_report
GET  /api/export/eox_report?format=xlsx
POST /api/logs/frontend
GET  /graphql
```

## Storage design

The backend keeps `product_eox` small and stores raw Cisco table evidence once:

```text
product_eox              fast lookup snapshot
eox_announcements        one row per announcement URL
eox_announcement_tables  one copy of each Cisco table
eox_affected_products    PID-to-table-row mapping
pid_catalog              known PID/series catalog
auto_pop_jobs            job records
auto_pop_checkpoints     cooldown metadata
system_events            logs visible to GUI/API
```

## SQLite tuning

SQLite connections use WAL mode, busy timeout, and normal sync mode. This improves local/dev stability but does not make SQLite a production database.

## PostgreSQL JSONB

PostgreSQL gets selected JSONB/GIN indexes for payload searches. SQLite does not create those indexes because they caused large DB bloat.

## Run tests

```bash
cd Cisco_EOX_Manager
pip install -r requirements-dev.txt
pytest -q
```
