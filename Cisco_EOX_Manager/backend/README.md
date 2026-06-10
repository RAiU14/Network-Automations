# Cisco EOX Manager Backend

The backend is a FastAPI application for Cisco EOX data collection, persistence, retrieval, export, and operational control.

## Responsibilities

```text
Database setup
Cisco API credential storage
Cache-first EOX lookup
Scraper fallback
Auto_Pop background jobs
GraphQL DB retrieval
CSV/Excel export with selected columns
Optional-token auth
Frontend/backend event logging
Alembic migration support
```

## Start locally

```bash
cd Cisco_EOX_Manager
python -m venv .venv
. .venv/Scripts/activate
pip install -r backend/requirements.txt
python -m uvicorn app.main:app --reload --app-dir backend
```

SQLite example:

```bash
set EOX_DATABASE_URL=sqlite:///./data/eox_dev.db
python -m uvicorn app.main:app --reload --app-dir backend
```

PostgreSQL example:

```bash
set EOX_DATABASE_URL=postgresql+psycopg://eox_user:eox_password@localhost:5432/eox_cache
python -m uvicorn app.main:app --reload --app-dir backend
```

## Main modules

| Module | Purpose |
|---|---|
| `app/main.py` | FastAPI app assembly. |
| `app/db/models.py` | SQLAlchemy RDBMS models. |
| `app/graphql/schema.py` | GraphQL read layer. |
| `app/api/routes_setup.py` | DB and Cisco API setup. |
| `app/api/routes_auth.py` | Optional token bootstrap/verify/status. |
| `app/api/routes_autopop.py` | Background Auto_Pop jobs. |
| `app/api/routes_export.py` | CSV/Excel export endpoints. |
| `app/api/routes_logs.py` | Frontend and system event logs. |
| `app/api/routes_eox.py` | Lookup/cache/catalog actions. |
| `app/services/seed_persistence.py` | Smart DB save/upsert layer. |
| `app/services/autopop_jobs.py` | Background subprocess runner. |
| `app/services/export_service.py` | DB-to-CSV/Excel export. |
| `app/services/cisco_scraper.py` | Cisco page scraping helpers. |
| `app/services/cisco_api_client.py` | Cisco API client placeholder for later live testing. |

## Authentication

Authentication is disabled by default. The backend is meant to run as a local/internal free utility without account setup.

```env
EOX_AUTH_ENABLED=false
```

The optional token middleware still exists for future restricted deployments, but the standard GUI flow does not use it.

## GraphQL

GraphQL is mounted at:

```text
/graphql
```

It is intended for reads and flexible data retrieval. Mutating operations remain REST endpoints.

Important queries:

```graphql
query { databaseOverview { totalProducts totalAnnouncements totalAutopopJobs } }
query { products(search: "9300", limit: 20) { pid status lastDateOfSupport } }
query { productJson(pid: "C9300-24T") }
query { autoPopJobs(limit: 20) { id status logFile } }
```

## Background Auto_Pop

Start from REST:

```text
POST /api/autopop/jobs
```

Example body:

```json
{
  "limit_categories": 1,
  "limit_series_eox": 10,
  "limit_announcements": 2,
  "parse_workers": 2,
  "delay": 1,
  "category_break": 10
}
```

The backend runs:

```text
tools/auto_pop_pid_database.py
```

as a subprocess and stores status in `auto_pop_jobs`.

## Exports

```text
GET /api/export/options/eox_report
GET /api/export/eox_report?format=xlsx&fields=pid&fields=last_date_of_support
GET /api/export/eox_report?format=csv&include_all=true
```

Supported datasets:

```text
eox_report
products
pid_catalog
affected_products
announcements
checkpoints
system_events
```

## Migrations

```bash
alembic -c backend/alembic.ini upgrade head
```

Development can still use automatic table creation. Deployment should use Alembic once the schema stabilizes.

## Testing

```bash
cd Cisco_EOX_Manager
pip install -r requirements-dev.txt
pytest -q
```


## JSONB / GIN index strategy

On PostgreSQL, the backend maps JSON payload columns to JSONB and provides migration `0002_postgresql_jsonb_indexes.py`. The migration converts existing JSON columns to JSONB and adds GIN indexes for common nested evidence fields. SQLite remains supported for development, but PostgreSQL is recommended once raw Cisco table volume grows.

## Authentication stance

Authentication is disabled by default. The product is intended to run as a free local/internal utility. If a team later exposes it on a shared network, `EOX_AUTH_ENABLED=true` can re-enable the optional token middleware.

## Report export behavior

`eox_report` is intended for non-programmer report downloads. It joins product snapshots with affected-product Cisco table rows, exposes standard lifecycle columns, and also exposes dynamic Cisco table columns discovered from populated DB records. The frontend uses `/api/export/options/{dataset}` to render checkboxes.

JSON file export is not part of the GUI workflow. GraphQL can still return JSON-shaped data for developers and integrations.
