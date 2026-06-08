# Cisco_Automations

A collection of Python automation programs created to make common network engineering tasks faster, easier, and more repeatable.

This repository is a personal and learning-focused project. It includes tools for Cisco EOX lookups, network connectivity checks, log collection, simple local data handling, and PM report generation.

## Main focus: Cisco EOX automation

The Cisco EOX package helps gather End-of-Life (EOX) information for Cisco products by passing a product ID, model number, or device series as input.

The project now has three EOX-facing layers:

| Folder | Purpose | API required |
|---|---|---|
| `EOX/` | Backward-compatible Python wrapper used by older scripts and PM report flows | No |
| `EOX_API/` | Reusable service package with scraper services, optional Cisco API client, and FastAPI routes | Optional |
| `front_end/` | React/Vite browser UI for using the FastAPI EOX routes | Optional backend credentials only |

### Cisco EOX web scraping package

The scraper-based flow uses publicly available Cisco web pages to find product lifecycle information without requiring Cisco API credentials.

Use this when you want to:

- Search for Cisco product or model lifecycle information.
- Find the most likely Cisco product series page for a PID.
- Check whether a product page contains EOX information.
- Scrape EOX milestone details from Cisco announcement pages.
- Enrich PM report output with lifecycle details.

### Cisco EOX API service

`EOX_API/` adds a cleaner service-oriented structure around the EOX logic.

It includes:

- FastAPI endpoints for EOX lookup workflows.
- A reusable scraper service: `EOX_API.services.cisco_eox_scraper`.
- A Cisco API client: `EOX_API.services.cisco_api_client`.
- Environment-based credential loading.
- Token caching for Cisco API calls.
- Request retries, timeouts, and structured logging.
- Compatibility support for the old misspelled module name `cisco_eox_scrapper.py`.

The Cisco API client is optional. The web scraping functionality can still be used without Cisco API credentials.

## Disclaimer

This tool is not affiliated with, maintained by, or endorsed by Cisco.

All web-scraped data is sourced from publicly available Cisco web pages. The Cisco API functionality requires valid Cisco API access configured by the user.

Use this project at your own discretion and risk. The author does not take responsibility for how this tool is used, including commercial usage, production automation, product sales, procurement, audits, or business decisions.

Always validate lifecycle information directly from Cisco's official website before making business, support, renewal, migration, or purchasing decisions.

## Repository structure

```text
Cisco_Automations/
├── EOX/
│   ├── API.py
│   ├── Cisco_EOX.py
│   └── requirements.txt
├── EOX_API/
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── services/
│   ├── main.py
│   ├── sample.py
│   ├── requirements.txt
│   └── README.md
├── front_end/
│   ├── src/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── README.md
├── Database/
├── PM_Report/
├── Connection.py
├── Log_Capture.py
├── Alive_Checks.py
└── README.md
```

## Installation

Install EOX dependencies from the repository root:

```bash
pip install -r EOX_API/requirements.txt
```

For legacy scraper-only usage, you can also install:

```bash
pip install -r EOX/requirements.txt
```

## Cisco API credentials

The scraper does not require API credentials.

Cisco API-backed functions require credentials. Configure them with environment variables:

```bash
export CISCO_CLIENT_ID="your-client-id"
export CISCO_CLIENT_SECRET="your-client-secret"
```

Optional environment variables:

```bash
export CISCO_CREDENTIALS_FILE="/path/to/credentials.json"
export EOX_DATA_DIR="/path/to/json-cache"
export EOX_LOG_DIR="/path/to/logs"
export CISCO_TOKEN_CACHE_FILE="/path/to/.cisco_token_cache.json"
```

`CISCO_CREDENTIALS_FILE` supports either of these formats:

```json
{"client_id": "...", "client_secret": "..."}
```

```json
{"data": {"client_id": "...", "client_secret": "...", "grant_type": "client_credentials"}}
```

Do not commit real credentials, token cache files, or private data to Git.

## Running the EOX API and React UI

Start the FastAPI application from the repository root:

```bash
python -m uvicorn EOX_API.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Interactive API documentation is available through FastAPI when the app is running:

```text
http://127.0.0.1:8000/docs
```

### React development mode

Run the backend first, then start the React/Vite frontend in a second terminal:

```bash
cd front_end
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The Vite dev server proxies API calls to the FastAPI backend at `http://127.0.0.1:8000`.

### Single-server mode

Build the React app and serve it from FastAPI:

```bash
cd front_end
npm install
npm run build
cd ..
python -m uvicorn EOX_API.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

When `front_end/dist` exists, FastAPI serves the React app from `/` and keeps the API under `/eox`.

## EOX API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/eox/categories` | List Cisco support categories discovered by the scraper |
| `POST` | `/eox/open-category` | Open a Cisco category page and extract product series links |
| `POST` | `/eox/find-series-link` | Find the best matching Cisco product series page for a PID |
| `POST` | `/eox/check-product` | Check a Cisco product page for EOX information |
| `POST` | `/eox/details` | Extract EOX announcement links from a Cisco redirect/details page |
| `POST` | `/eox/scrape` | Scrape milestone data and affected products from an EOX announcement page |
| `POST` | `/eox/lookup-pids` | Lookup EOX data for one or more PIDs using cache or online scraping |
| `POST` | `/eox/hardware-milestones` | Fetch hardware EOX milestone data through Cisco API |
| `POST` | `/eox/software-milestones` | Fetch software milestone data through Cisco API |

## Python usage

### Scraper service

```python
from EOX_API.services.cisco_eox_scraper import CiscoEoxScraperService

service = CiscoEoxScraperService()

pid = "C9300-24T"
technology = "Routing and Switching"

series_link = service.find_device_series_link(pid, technology)
print(series_link)
```

### Legacy wrapper

Existing code can continue to use `EOX.Cisco_EOX`:

```python
from EOX.Cisco_EOX import request_EOX_data_from_local_db

pids = ["C9300-24T", "ISR4331/K9"]
results = request_EOX_data_from_local_db(pids, "Routing and Switching")
print(results)
```

### Cisco API client

```python
from EOX_API.services.cisco_api_client import CiscoApiClient

client = CiscoApiClient()
result = client.get_hardware_eox_by_product_id(["C9300-24T"])
print(result)
```

## Other modules

### Connection.py

Contains reusable connection snippets for connecting to network devices and running Netmiko commands.

### Log_Capture.py

Collects logs from Cisco switches or other network devices in bulk by passing IP addresses and required show commands. Log files are saved using the device hostname where possible.

### Alive_Checks.py

Provides simple device reachability checks using built-in Python functionality. It performs an operating system check before running ping commands and can be used to validate whether devices are reachable directly or through a jump host flow.

### Database directory

Contains database and local data experiments used to store and retrieve EOX-related data.

Current concepts include:

- SQLite-based lookup using `EOX.db`.
- CSV-based lookup logic.
- JSON-based lookup logic.
- Edit and retrieve functions for existing lifecycle data.

Some database features are still work in progress.

### auto_pop.py

A utility concept for automatically retrieving available EOX data from Cisco sources using the EOX package.

### PM_Report folder

Contains scripts to gather health parameters from network appliances based on technology and vendor.

Current status:

- Parses available log data.
- Extracts basic device health information.
- Marks unavailable data as `NA`.
- Supports ongoing integration with EOX lifecycle enrichment.

This area is still under active development.

## Current working status

Working:

- EOX scraper service structure.
- Legacy `EOX.Cisco_EOX` wrapper compatibility.
- FastAPI EOX route structure.
- React/Vite frontend for browser-based EOX lookup.
- Optional Cisco API client integration.
- Environment-based Cisco credential handling.
- JSON cache path configuration.

Known limitations:

- Web scraping may break if Cisco changes page layout or blocks automated requests.
- Scraped data should be treated as advisory until validated directly with Cisco.
- Cisco API-backed functions require valid credentials and network access.
- Local JSON cache quality depends on how recently it was populated.

Pending enhancements:

- Add automated parser and scraper tests with fixtures.
- Add a CLI command for bulk PID lookup.
- Add richer result tables and CSV/Excel export in the React UI.
- Add Docker support.
- Add CI linting and test workflow.
- Replace large JSON cache with SQLite or another structured store.
- Add authentication if the FastAPI app is deployed beyond local/internal usage.

## Git ignore note

The `.gitignore` file was created with help from gitignore.io and should be expanded to exclude generated logs, token caches, local credentials, temporary reports, and runtime artifacts.
