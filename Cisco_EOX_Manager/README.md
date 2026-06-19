# Cisco EOX Manager

Cisco EOX Manager is the active Cisco lifecycle product inside the larger `Network-Automations` repository. It is focused only on Cisco End-of-Life / End-of-Sale data for now.

The tool is designed for two audiences:

1. Common users who want a simple GUI, CSV, and Excel reports.
2. Developers who want REST/GraphQL access and a database-backed EOX engine.

The database is the source of truth. Auto_Pop saves directly into the configured database. JSON files are not used for seeding or exporting in the GUI.

## Project positioning, data source, and legal note

Cisco EOX Manager is an independent home-lab and internal-operations tool. It is not affiliated with, endorsed by, sponsored by, or supported by Cisco.

This repository is intended to provide a self-hosted API and optional dashboard for lifecycle planning. It does **not** bundle a Cisco EOX dataset. Users generate their own local cache for their own environment and are responsible for following Cisco terms, API terms, website terms, robots.txt, rate limits, and applicable laws.

Preferred data source order:

```text
1. Local database cache
2. Cisco official Support EoX API, when credentials are configured
3. Optional rate-limited public-page fallback for local/internal use
```

Do not present this project as an official Cisco product, an official Cisco dataset, a Cisco data mirror, or a replacement for Cisco support resources. Cisco product names are used only descriptively. Do not use Cisco logos or branding unless you have permission.

Good public wording:

```text
Independent home-lab/internal inventory tool for Cisco EoX lifecycle lookups.
Users generate their own local cache. Not affiliated with Cisco. Use official APIs where available.
```

Avoid wording like:

```text
Official Cisco database
Free Cisco data mirror
Unlimited Cisco scraper
Cisco replacement API
```

Additional notes are in:

```text
docs/LEGAL_AND_DATA_SOURCE_NOTICE.md
docs/LINKEDIN_POST_TEMPLATE.md
```


## Current workflow

```text
Fresh git pull
   ↓
Docker compose up
   ↓
Open GUI
   ↓
Optionally enable API token protection
   ↓
Choose SQLite or PostgreSQL
   ↓
Initialize DB
   ↓
Run safe Auto_Pop or search individual PIDs
   ↓
DB stores the result
   ↓
GUI shows lookup, raw Cisco tables, and CSV/XLSX export
```

## Folder structure

```text
Cisco_EOX_Manager/
├── backend/                 # FastAPI, SQLAlchemy, GraphQL, REST routes
├── front_end/               # React/Vite GUI
├── tools/                   # Auto_Pop and local maintenance tools
├── data/                    # Runtime DB/config; do not commit DB files
├── logs/                    # Backend and Auto_Pop job logs
├── tests/                   # Pytest modules
├── docker-compose.yml
├── requirements-dev.txt
└── README.md
```

## Quick Docker run

```bash
cd Cisco_EOX_Manager
cp .env.example .env
docker compose up -d --build --force-recreate
```

Open:

```text
GUI:          http://127.0.0.1:5173
API docs:     http://127.0.0.1:8000/docs
GraphQL:      http://127.0.0.1:8000/graphql
Health:       http://127.0.0.1:8000/health
```

For a remote server or Tailscale host, open the same ports using the server IP:

```text
http://SERVER-IP:5173
http://SERVER-IP:8000/docs
```

Use **HTTP**, not HTTPS, unless you add your own reverse proxy/TLS certificate. A browser error like `SSL_ERROR_RX_RECORD_TOO_LONG` usually means you opened `https://SERVER-IP:5173` even though the built-in frontend is plain HTTP.

### Ports used by Docker

| Service | Container port | Host port default | Notes |
|---|---:|---:|---|
| Frontend | 5173 | 5173 | Set `EOX_FRONTEND_HOST_PORT=5174` in `.env` if 5173 is busy. |
| API | 8000 | 8000 | REST, docs, GraphQL. |
| PostgreSQL | 5432 | 5433 | Host 5432 is often already used by system PostgreSQL, so Docker defaults to 5433. |

The API container connects to PostgreSQL internally using:

```text
postgres:5432
```

The server shell or external database tools connect to Docker PostgreSQL using:

```text
127.0.0.1:5433
```

### Remote GUI / CORS

The compose file allows common local and LAN/Tailscale frontend origins on ports `5173` and `5174`. The frontend should keep this empty so the browser auto-detects the backend host:

```yaml
VITE_API_BASE_URL: ""
```

If you want to restrict origins more tightly, set this in `.env`:

```text
EOX_CORS_ORIGINS=http://SERVER-IP:5173,http://SERVER-IP:5174,http://localhost:5173,http://localhost:5174
EOX_CORS_ORIGIN_REGEX=
```


## API security and rate limits

Cisco EOX Manager is still easy to run on a private home/LAN network, but it now includes optional API-token protection and built-in rate limiting.

### Default security posture

By default:

```text
API token auth: disabled
Rate limiting:  enabled
```

This means a beginner can open the GUI immediately on a private network, while the API still has protection against accidental browser loops or repeated script calls.

### When to enable an API token

Enable an API token if any of these are true:

```text
Other people can reach your server IP
You are sharing the API with scripts or integrations
You expose the service outside your home/Tailscale network
You want to prevent accidental Auto_Pop starts by unauthenticated users
```

Do **not** expose this app directly to the public internet without a reverse proxy, TLS, and token protection.

### Enable API token protection from the GUI

Open the GUI and go to:

```text
Security → Create or rotate admin token
```

Then:

```text
1. Type a long admin token, at least 12 characters.
2. Click Save token + enable protection.
3. The GUI stores the token in this browser only.
4. Future API calls from this browser include the token automatically.
```

The token is saved on the backend as a SHA-256 hash in:

```text
Cisco_EOX_Manager/data/.eox_auth.env
```

The plain token is not written to the backend runtime file. Keep your chosen token somewhere safe, such as a password manager.

### Use the token from curl or scripts

When protection is enabled, protected REST and GraphQL routes require either a bearer token:

```bash
curl -H "Authorization: Bearer YOUR_LONG_TOKEN" \
  http://SERVER-IP:8000/api/eox/stats
```

or the EOX token header:

```bash
curl -H "X-EOX-Admin-Token: YOUR_LONG_TOKEN" \
  http://SERVER-IP:8000/api/eox/stats
```

A PID lookup example:

```bash
curl -s -X POST http://SERVER-IP:8000/api/eox/lookup \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_LONG_TOKEN" \
  -d '{"pids":["AIR-CT5520-K9"],"refresh":false,"auto_learn":false}' | python3 -m json.tool
```

### Authentication endpoints

The auth endpoints are intentionally simple:

| Endpoint | Purpose |
|---|---|
| `GET /api/auth/status` | Show whether auth is enabled and whether a token exists. |
| `GET /api/auth/security-status` | Show auth plus rate-limit settings. |
| `POST /api/auth/bootstrap` | Create/rotate the token and optionally enable protection. |
| `POST /api/auth/verify` | Verify the current browser/script token. |
| `POST /api/auth/enabled` | Enable or disable runtime token protection. |

If `EOX_AUTH_ENABLED=true` is set in Docker/environment, protection is forced on and the GUI cannot fully disable it until the environment value is changed.

### Rate limits

Rate limiting is enabled by default and is in-memory inside the API container. It is meant for a single-container home/server deployment.

Default limits:

```text
Read requests:        240 per minute
Write requests:       60 per minute
Auto_Pop job starts:  12 per hour
```

Configure in `.env`:

```text
EOX_RATE_LIMIT_ENABLED=true
EOX_RATE_LIMIT_READ_PER_MINUTE=240
EOX_RATE_LIMIT_WRITE_PER_MINUTE=60
EOX_RATE_LIMIT_AUTOPOP_JOBS_PER_HOUR=12
```

If the limit is exceeded, the API returns:

```text
HTTP 429 Too Many Requests
Retry-After: <seconds>
```

For multiple API replicas, place a reverse proxy or Redis-backed limiter in front of the app. The built-in limiter is intentionally dependency-free and local to one API container.

### Protected paths

When token auth is enabled, these route groups require the token:

```text
/api/eox
/api/setup
/api/logs
/api/export
/api/autopop
/graphql
```

These remain open for startup and troubleshooting:

```text
/health
/api/health
/api/auth/status
/api/auth/security-status
/api/auth/bootstrap
/api/auth/verify
/docs
/openapi.json
```


## Deployment modes

Cisco EOX Manager can be used in three ways. The frontend is optional. The backend is the reusable product.

### 1. Full GUI mode

Run everything:

```bash
docker compose up -d postgres api frontend
```

Use this when you want the browser dashboard, setup wizard, Auto_Pop controls, exports, and help pages.

### 2. API-only mode

Run only the API and database:

```bash
docker compose up -d postgres api
```

Use this when another application, script, or automation platform will call Cisco EOX Manager over HTTP. The React frontend is not required.

API docs remain available at:

```text
http://SERVER-IP:8000/docs
```

Example Python integration:

```python
import requests

response = requests.post(
    "http://EOX-SERVER:8000/api/eox/lookup",
    json={"pids": ["AIR-CT5520-K9"], "refresh": False, "auto_learn": False},
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    timeout=30,
)
print(response.json())
```

Recommended architecture for other applications:

```text
Your application
   ↓ REST/GraphQL
Cisco EOX Manager API
   ↓
SQLite or PostgreSQL
```

Avoid having other applications depend directly on the internal tables unless you control both systems. The API is the stable integration boundary.

### 3. Lightweight local mode

Run only the API with SQLite:

```bash
docker compose up -d api
```

Use this for small labs, quick checks, or demos. PostgreSQL is recommended for full Auto_Pop datasets.

More details are in:

```text
docs/API_ONLY_DEPLOYMENT.md
```

## Database options

### SQLite

SQLite is for first-time use, demos, and small development runs.

Use the GUI button:

```text
Pick a database → Start with local SQLite
```

The DB file is stored at:

```text
Cisco_EOX_Manager/data/eox_dev.db
```

SQLite is now tuned with:

```text
WAL journal mode
busy_timeout
synchronous=NORMAL
small cache size
foreign keys enabled
```

This makes it more stable on older servers, but PostgreSQL is still preferred for large Auto_Pop runs.

### PostgreSQL

PostgreSQL is recommended for full-scale runs, GraphQL retrieval, and shared usage. Docker Compose includes PostgreSQL by default, so beginners do **not** need to install PostgreSQL on the server OS.

Default Docker PostgreSQL credentials:

```text
Host in GUI/API: postgres
Port in GUI/API: 5432
Database:        eox_cache
Username:        eox_user
Password:        eox_password
```

From the server shell only:

```text
Host:     127.0.0.1
Port:     5433
Database: eox_cache
Username: eox_user
Password: eox_password
```

Beginner GUI flow:

```text
Pick and initialize a database
   ↓
Use Docker PostgreSQL defaults
   ↓
Save + Create Tables
   ↓
Seed / Start Auto_Pop
```

The `Save + Create Tables` button will test PostgreSQL, create the database if the current user has permission, initialize all Cisco EOX tables, and save it as the active app database.

For custom PostgreSQL servers, choose PostgreSQL, type your host/database/user/password, then click `Save + Create Tables`. If the database does not exist, the user must have permission to create databases through the maintenance database named `postgres`.

PostgreSQL gives better:

```text
concurrency
large table storage
JSONB querying
GraphQL filtering
scaling
```

## Reset local SQLite cleanly

After code/storage changes, it is better to delete a faulty dev DB than spend time cleaning it.

Stop API/frontend first:

```bash
docker compose stop api frontend
```

Delete the local SQLite DB:

```bash
python tools/reset_sqlite_dev_db.py --yes
```

Or manually:

```bash
rm -f data/eox_dev.db data/eox_dev.db-journal data/eox_dev.db-wal data/eox_dev.db-shm
```

Start again:

```bash
docker compose up -d --build --force-recreate api frontend
```

Then initialize SQLite again from GUI or CLI:

```bash
curl -s -X POST http://127.0.0.1:8000/api/setup/database/use-sqlite | python3 -m json.tool
curl -s -X POST http://127.0.0.1:8000/api/setup/database/initialize | python3 -m json.tool
```

## Smart storage design

The optimized storage design is:

```text
product_eox
  Small fast lookup row only.
  Stores PID, status, dates, source, announcement URL, and small metadata.

eox_announcements
  One row per Cisco EOX announcement URL.

eox_announcement_tables
  Stores each scraped Cisco table once per announcement.
  Full table rows live here, not in every product row.

eox_affected_products
  Maps PID → exact Cisco affected-product table row.
  Stores row columns and milestone references.

pid_catalog
  Known PID/product/series catalog.

auto_pop_checkpoints
  Remembers category cooldown and last successful run.

auto_pop_jobs
  Tracks GUI/REST Auto_Pop jobs.

system_events
  Stores backend/frontend operational logs.
```

This avoids the old problem where raw Cisco tables were duplicated inside every `product_eox.payload` row.

## Why JSONB indexes exist only for PostgreSQL

PostgreSQL has `JSONB` and `GIN` indexes for efficient nested JSON search. SQLite does not. Creating JSON-style indexes on SQLite payload columns caused huge local DB bloat.

Current behavior:

```text
SQLite      → normal relational indexes only
PostgreSQL  → selected JSONB/GIN indexes for scalable evidence queries
```

## Auto_Pop

Auto_Pop is the database builder. It crawls Cisco category/series/announcement pages, parses all announcement tables, maps affected PIDs, and saves to DB.

Small safe CLI run:

```bash
python tools/auto_pop_pid_database.py --limit-categories 1 --limit-series-eox 10 --limit-announcements 2
```

Force refresh when cooldown is active:

```bash
python tools/auto_pop_pid_database.py --limit-categories 1 --limit-series-eox 10 --limit-announcements 2 --force-refresh
```

Use SQLite explicitly:

```bash
python tools/auto_pop_pid_database.py --sqlite --limit-categories 1 --limit-series-eox 10 --limit-announcements 2
```

### Auto_Pop advanced options

| Option | Purpose |
|---|---|
| Categories | Number of Cisco categories to crawl. |
| Series per category | Number of product/series pages checked for EOX. |
| Announcements | Number of EOX announcement pages opened per EOX listing. |
| Parser workers | Local worker threads for parsing already-fetched HTML. Cisco requests remain controlled. |
| Delay seconds | Sleep between Cisco requests. |
| Category break | Sleep after one category completes. |
| Force refresh | Ignore cooldown and crawl again. Use carefully. |
| Treat cooldown-only runs as successful | Prevents a skipped cooldown run from appearing as a failure. |

## Multi-threading model

The tool intentionally does not hammer Cisco with many parallel requests.

```text
Cisco HTTP requests       mostly sequential and delayed
HTML/table parsing        limited worker threads
DB writes                 single controlled writer
```

This is safer for Cisco pages and safer for SQLite.


### Is it multi-threading or multi-processing?

The current Auto_Pop design uses controlled concurrency, but it is not an unlimited multi-process crawler.

```text
FastAPI API server       one Uvicorn process by default
FastAPI sync routes      executed through a threadpool
Auto_Pop parsing         limited worker threads/process-style worker pool depending on runtime path
Cisco HTTP requests      intentionally delayed and mostly controlled
Database writes          controlled writer pattern
```

This is intentional. Cisco request rate, database writes, and old home-server RAM are usually the bottlenecks. Setting very high worker counts can make the system slower or less stable.

For future larger deployments, the preferred architecture is:

```text
API container       handles REST/GraphQL requests
Worker container    runs Auto_Pop jobs
PostgreSQL          stores data and job state
Redis/queue         optional distributed rate limit and job queue
Reverse proxy       TLS and public access control
```

## PID lookup flow

When a user searches `AIR-CT5520-K9`:

```text
Normalize PID
   ↓
Check product_eox
   ↓
If found, return cache
   ↓
If not found, use Cisco API only if credentials exist
   ↓
If API is unavailable, scrape Cisco
   ↓
Save learned data into DB
   ↓
Return user-friendly result
```

The GUI does not ask users to choose API/scraper. The backend decides.

## Raw Cisco table viewer

The viewer uses REST now:

```text
GET /api/eox/evidence/{pid}
```

It returns:

```text
product summary
affected product rows
announcement metadata
bounded Cisco tables
```

The response is intentionally bounded so an old 2-core server does not try to push huge raw payloads to the browser.

## Reports

The GUI exports user-facing files only:

```text
CSV
XLSX
```

No JSON file export is presented to common users. Developers can use API/GraphQL for JSON-shaped data.

Main report dataset:

```text
eox_report
```

It combines:

```text
product_eox
+ eox_affected_products
+ dynamic Cisco table columns
```

## Useful API checks

```bash
curl http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/setup/status | python3 -m json.tool
curl -s http://127.0.0.1:8000/api/eox/stats | python3 -m json.tool
```

Lookup a PID:

```bash
curl -s -X POST http://127.0.0.1:8000/api/eox/lookup \
  -H "Content-Type: application/json" \
  -d '{"pids":["AIR-CT5520-K9"],"refresh":false,"auto_learn":true}' | python3 -m json.tool
```

View evidence:

```bash
curl -s http://127.0.0.1:8000/api/eox/evidence/AIR-CT5520-K9 | python3 -m json.tool
```

Start Auto_Pop job:

```bash
curl -s -X POST http://127.0.0.1:8000/api/autopop/jobs \
  -H "Content-Type: application/json" \
  -d '{"limit_categories":1,"limit_series_eox":10,"limit_announcements":2,"parse_workers":2,"delay":1,"category_break":10,"allow_empty":true}' | python3 -m json.tool
```

Clear old jobs:

```bash
curl -X DELETE "http://127.0.0.1:8000/api/autopop/jobs/clear?delete_logs=true" | python3 -m json.tool
```

## Logs

Docker logs:

```bash
docker compose logs api --tail=200
docker compose logs frontend --tail=100
docker compose logs -f api
```

Auto_Pop job logs:

```bash
docker exec cisco-eox-api sh -lc 'ls -lah /product/logs/jobs'
docker exec cisco-eox-api sh -lc 'cat /product/logs/jobs/auto_pop_job_1.log'
```

System events:

```bash
curl -s "http://127.0.0.1:8000/api/logs/events?limit=30" | python3 -m json.tool
```

## Tests

```bash
cd Cisco_EOX_Manager
pip install -r requirements-dev.txt
pytest -q
```

The storage-efficiency tests verify that product snapshots do not duplicate raw Cisco tables.


## Recommended future hardening

The current product is usable for home-lab and internal testing, but these improvements would make it stronger for broader release:

```text
API-only Docker profile so users can run api + postgres without frontend
System capability detection for CPU/RAM/disk and recommended worker values
Database health page with DB size, table sizes, index sizes, and last update time
Live Auto_Pop monitor with current category, latest log lines, runtime, and cancel/pause/resume
Separate Auto_Pop worker container so long crawls cannot block the API process
Persistent job queue and restart-safe job recovery
Read-only and admin API tokens instead of one token type
GraphQL query depth/complexity limits to prevent expensive queries
Redis-backed rate limiting for multi-container API deployments
Backup/restore buttons for SQLite and PostgreSQL
Official Cisco API setup wizard and credential validation
Crawler policy controls: delay, cooldown, user-agent, retry/backoff, and source attribution
OpenAPI examples for common integrations
```

Security hardening for non-home-lab use:

```text
Use HTTPS through a reverse proxy
Enable API token protection
Restrict CORS to known frontend origins
Do not expose PostgreSQL directly to the internet
Prefer official APIs and local caching over repeated public-page fetches
```

## Known boundaries

```text
Cisco API live testing is still pending.
SQLite is for local/dev use, not huge production crawls.
PostgreSQL should be used for full-scale Auto_Pop.
Cisco pages can change or block scraping; use delays/cooldowns.
Always verify lifecycle data with Cisco before business decisions.
```

## Disclaimer

This project is an independent tool and is not affiliated with, endorsed by, sponsored by, or supported by Cisco. Cisco product names are used only descriptively. This repository does not include a Cisco EOX dataset, and users are expected to generate their own local cache for internal inventory and lifecycle planning.

Use Cisco official APIs where available. Users are responsible for complying with Cisco terms, API terms, website terms, robots.txt, rate limits, and applicable laws. Validate important lifecycle decisions directly with Cisco or your authorized support channel. This project is provided as-is for home-lab, educational, and internal operations use.

## v18 production-hardening additions

This version adds a stronger separation between the GUI, backend API, Auto_Pop worker, and database.

### Deployment modes

#### Full GUI mode

Use this when you want the dashboard plus API:

```bash
docker compose up -d --build
```

This starts:

```text
postgres
api
frontend
```

#### API-only mode

Use this when another application will call Cisco EOX Manager through REST/GraphQL and you do not want to spend resources on the React dashboard:

```bash
docker compose -f docker-compose.yml -f docker-compose.api-only.yml up -d --build
```

This runs PostgreSQL and the FastAPI backend. The frontend service is placed behind a `gui` profile and will not start.

API docs are still available:

```text
http://SERVER-IP:8000/docs
```

#### Dedicated Auto_Pop worker mode

For longer or shared deployments, do not make the API process run heavy Auto_Pop jobs. Use a separate worker process:

```bash
EOX_AUTOPOP_EXECUTION_MODE=external docker compose --profile worker up -d --build
```

In this mode:

```text
API container: creates queued Auto_Pop jobs and serves users
Worker container: picks up queued jobs and runs the crawler/parser
PostgreSQL: stores the queue and records
```

This is better for multi-user deployments because long background jobs do not compete as directly with API requests.

### Multi-process API mode

The API can run multiple Uvicorn worker processes:

```text
EOX_API_WORKERS=2
```

Then recreate containers:

```bash
docker compose up -d --build --force-recreate
```

On old 2-core servers, start with `EOX_API_WORKERS=1` or `2`. More workers are not always faster because each worker has its own memory use and its own in-memory rate limiter.

### System capability detection

The API now exposes:

```text
GET /api/system/capabilities
```

It detects:

```text
CPU logical cores
available memory
disk space
active database type
recommended Auto_Pop worker profiles
recommended delay and category break
```

The GUI uses this to fill safer Auto_Pop defaults for the current machine.

### Database health and metadata

The API now exposes:

```text
GET /api/system/database-health
```

It returns:

```text
database type
database URL hint
database size
last updated time
table counts
table sizes
index sizes
disk free space
storage warnings
```

For SQLite it also reports `.db`, `-wal`, `-shm`, and `-journal` file sizes when present.

### Backups and maintenance

The GUI and API support:

```text
POST /api/system/backups
GET  /api/system/backups
GET  /api/system/backups/{file_name}/download
POST /api/system/backups/restore
POST /api/system/maintenance/analyze
POST /api/system/maintenance/vacuum
```

SQLite backups are copied safely using SQLite's backup API. PostgreSQL backups use `pg_dump` from inside the API container, so the backend Docker image now includes `postgresql-client`.

Restores are destructive and require explicit confirmation in the API request.

### Live Auto_Pop job monitor

The API now supports:

```text
GET  /api/autopop/jobs/{job_id}/log
POST /api/autopop/jobs/{job_id}/pause
POST /api/autopop/jobs/{job_id}/resume
POST /api/autopop/jobs/{job_id}/cancel
```

The log endpoint returns the latest log lines and best-effort progress information such as current category and series. Pause/resume uses POSIX process signals when available, so it is meant for Linux/Docker deployments.

### Read-only token vs admin token

API protection now supports two token roles:

```text
Admin token:
  setup, security, backups, maintenance, Auto_Pop control, writes, reads

Read-only token:
  lookup, stats, evidence, exports, GraphQL read queries, browses
```

Create tokens in the Security section of the GUI or with API endpoints:

```text
POST /api/auth/bootstrap      # admin token
POST /api/auth/read-token     # read-only token
POST /api/auth/verify         # returns accepted role
```

Use either token with:

```bash
curl -H "Authorization: Bearer TOKEN" http://SERVER-IP:8000/api/eox/stats
```

### GraphQL limits

GraphQL now has guardrails:

```text
EOX_GRAPHQL_LIMITS_ENABLED=true
EOX_GRAPHQL_MAX_QUERY_CHARS=20000
EOX_GRAPHQL_MAX_DEPTH=10
```

These limits help prevent accidentally huge nested queries from hurting a small server.

### Cisco API and crawler policy

Recommended public posture:

```text
Use Cisco's official Support EoX API where credentials are available.
Use public-page fallback only as an optional, rate-limited local-cache mechanism.
Do not bundle or redistribute a vendor dataset.
Let users generate their own local cache.
```

Crawler settings should be conservative by default:

```text
Delay seconds: 3-5
Category break: 30-60
Cooldown enabled
Force refresh off unless intentionally re-crawling
```

### What this still does not replace

For a true public multi-tenant service, add these outside Docker Compose:

```text
TLS reverse proxy
centralized rate limiting such as nginx/Traefik/Redis
proper user management
monitoring and alerting
regular database backups
a legal review of data-source behavior
```

The current design is strong for home labs, internal tooling, and single-organization deployments.
