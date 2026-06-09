# Cisco EOX Manager

Cisco EOX Manager is a standalone EOX product. It gives you a React GUI, FastAPI backend, PostgreSQL PID database, PostgreSQL EOX cache, Cisco API setup from the browser, scraper fallback, bundled preset import, Auto_Pop preset generation, and a GraphQL-ready data layer.

## What changed in this version

- EOX is now treated as its own product under `Cisco_EOX_Manager/`.
- PostgreSQL now has two local data layers:
  - `pid_catalog` - the PID / product-series database generated from Auto_Pop or online discovery.
  - `product_eox` - the EOX milestone cache used for lookups and GraphQL.
- The lookup flow is now database-first:
  1. Search PostgreSQL EOX cache.
  2. Search local PID catalog for known PID/series context.
  3. If missing, optionally query Cisco API.
  4. If still missing, use scraper fallback.
  5. Save learned results back to PostgreSQL.
- The GUI now has first-run setup cards for:
  - PostgreSQL database setup and initialization.
  - Bundled PID/EOX preset import.
  - Cisco API key/token setup.
- A fixed Auto_Pop exporter is included at `tools/auto_pop_pid_database.py`.

## Quick start for non-technical users

From this folder:

```bash
cp .env.example .env
docker compose up --build
```

Open the GUI:

```text
http://127.0.0.1:5173
```

Then use the setup wizard in the browser:

1. Click **Initialize current DB** or **Save and initialize**.
2. Click **Import bundled preset**.
3. Optional: add Cisco API credentials under **Cisco API keys**.
4. Use **EOX lookup** or **Browse PID catalog and EOX cache**.

Backend API docs:

```text
http://127.0.0.1:8000/docs
```

GraphQL:

```text
http://127.0.0.1:8000/graphql
```

## Bundled preset

The product ships with this preset path:

```text
Cisco_EOX_Manager/data/presets/eox_pid_seed.json
```

For now, it contains a small starter preset from the existing repository sample. Replace this file with the full Auto_Pop output when you generate it.

## Generate or replace the PID preset with Auto_Pop

The maintained Auto_Pop exporter is:

```text
Cisco_EOX_Manager/tools/auto_pop_pid_database.py
```

The old repo-level command still works through the compatibility wrapper:

```bash
python Database/auto_pop.py --limit-categories 2
```

### Online Cisco crawl

Run this from `Cisco_EOX_Manager/`:

```bash
python tools/auto_pop_pid_database.py --output data/presets/eox_pid_seed.json
```

For a small test run:

```bash
python tools/auto_pop_pid_database.py --limit-categories 2 --output data/presets/eox_pid_seed.json
```

To add model names from each product series page:

```bash
python tools/auto_pop_pid_database.py --limit-categories 2 --crawl-models --limit-series 20 --output data/presets/eox_pid_seed.json
```

To also crawl EOX announcement pages and affected PID milestone data:

```bash
python tools/auto_pop_pid_database.py --crawl-eox --output data/presets/eox_pid_seed.json
```

That full crawl can take a long time and depends on Cisco page structure and network availability.

### When Cisco returns 403 or blocks the crawl

Cisco may block non-browser requests. The exporter no longer has to fail in that case. Use one of these safer flows:

TXT file, one PID per line:

```bash
python tools/auto_pop_pid_database.py --no-cisco-crawl --input-file pids.txt --output data/presets/eox_pid_seed.json
```

CSV file with columns like `pid,product_name,technology,product_url,is_eox`:

```bash
python tools/auto_pop_pid_database.py --no-cisco-crawl --input-file pids.csv --output data/presets/eox_pid_seed.json
```

Manual Cisco category URL if the all-products page is blocked but category pages open:

```bash
python tools/auto_pop_pid_database.py --category-url Switches=https://www.cisco.com/c/en/us/support/switches/category.html --output data/presets/eox_pid_seed.json
```

If no online/input data is discovered, Auto_Pop falls back to the bundled preset unless you pass `--no-fallback-preset`.

After generating or replacing the preset file, open the GUI and click **Import bundled preset**.

## First-run setup details

### Database setup

Docker Compose starts PostgreSQL automatically with these defaults:

```text
host: postgres inside Docker / localhost from host
port: 5432
user: eox_user
password: eox_password
database: eox_cache
```

The GUI can test and save database settings. It writes runtime database settings to:

```text
Cisco_EOX_Manager/data/runtime_config.json
Cisco_EOX_Manager/data/.env.local
```

The running backend uses `runtime_config.json`. The `.env.local` file is a local reference/export file; Docker Compose still needs a restart if you choose to wire it directly into Compose later.

### Cisco API setup

Cisco API credentials are entered through the GUI. They are saved encrypted in PostgreSQL, not hardcoded in source code.

For stable credential encryption across rebuilds, set `EOX_SECRET_KEY` in `.env`.

Generate a key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then add it to `.env`:

```text
EOX_SECRET_KEY=<generated-value>
```

## Main REST endpoints

```text
GET  /api/setup/status
POST /api/setup/database/configure
POST /api/setup/database/initialize
POST /api/setup/cisco
GET  /api/eox/preset
POST /api/eox/import-preset
GET  /api/eox/pid-catalog
GET  /api/eox/cache
GET  /api/eox/stats
POST /api/eox/lookup
POST /api/eox/auto-populate
POST /api/eox/discover-catalog
```

## GraphQL examples

```graphql
query {
  product(pid: "AIR-CT5520-K9") {
    pid
    status
    source
    endOfSaleDate
    lastDateOfSupport
    payload
  }
}
```

```graphql
query {
  pidCatalog(search: "Catalyst", limit: 10) {
    pid
    technology
    categoryName
    productUrl
    isEox
  }
}
```

## Notes

- This is not affiliated with or endorsed by Cisco.
- Scraping can break if Cisco changes its page structure.
- Validate critical EOX dates directly with Cisco before business decisions.
- Use Cisco API credentials only in trusted environments.
