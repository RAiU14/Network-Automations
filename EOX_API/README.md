# Cisco EOX API

`EOX_API` is the service package for Cisco End-of-Life (EOX) lookup workflows.

It supports two lookup styles:

1. Web scraping of publicly available Cisco pages. This does not require Cisco API credentials.
2. Optional Cisco API calls for hardware and software milestone data. This requires Cisco API credentials.

## Features

- FastAPI application entry point: `EOX_API.main:app`
- EOX routes under `/eox`
- Optional React frontend served from `front_end/dist` when built
- Reusable web scraper service
- Optional Cisco API client
- Environment-based credential loading
- Cisco token caching
- Retries and request timeouts
- Pydantic request and response models
- Backward compatibility for the old `cisco_eox_scrapper.py` import name

## Install

From the repository root:

```bash
pip install -r EOX_API/requirements.txt
```

## Run

```bash
python -m uvicorn EOX_API.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

API docs:

```text
http://127.0.0.1:8000/docs
```

If the React frontend has been built, FastAPI serves it from:

```text
http://127.0.0.1:8000
```

Build the frontend from the repository root with:

```bash
cd front_end
npm install
npm run build
```

## Configuration

The scraper works without API credentials.

For Cisco API-backed endpoints, set:

```bash
export CISCO_CLIENT_ID="your-client-id"
export CISCO_CLIENT_SECRET="your-client-secret"
```

Optional settings:

```bash
export CISCO_CREDENTIALS_FILE="/path/to/credentials.json"
export EOX_DATA_DIR="/path/to/json-cache"
export EOX_LOG_DIR="/path/to/logs"
export CISCO_TOKEN_CACHE_FILE="/path/to/.cisco_token_cache.json"
export EOX_HTTP_TIMEOUT_SECONDS="30"
export EOX_HTTP_RETRIES="3"
export EOX_HTTP_BACKOFF_SECONDS="0.5"
export EOX_USER_AGENT="Network-Automation-EOX/2.0"
```

Credential file format:

```json
{"client_id": "...", "client_secret": "..."}
```

Legacy credential file format is also supported:

```json
{"data": {"client_id": "...", "client_secret": "...", "grant_type": "client_credentials"}}
```

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/eox/categories` | Discover Cisco support categories |
| `POST` | `/eox/open-category` | Extract series and EOX links from a category page |
| `POST` | `/eox/find-series-link` | Match a PID to a Cisco product series page |
| `POST` | `/eox/check-product` | Check a product page for EOX details |
| `POST` | `/eox/details` | Extract EOX announcement URLs |
| `POST` | `/eox/scrape` | Scrape milestone and affected-device data |
| `POST` | `/eox/lookup-pids` | Lookup multiple PIDs from cache or online scraping |
| `POST` | `/eox/hardware-milestones` | Fetch hardware milestones through Cisco API |
| `POST` | `/eox/software-milestones` | Fetch software milestones through Cisco API |

## Example requests

### Find series link

```bash
curl -X POST http://127.0.0.1:8000/eox/find-series-link \
  -H "Content-Type: application/json" \
  -d '{"pid":"C9300-24T","technology":"Routing and Switching"}'
```

### Lookup PIDs using local cache

```bash
curl -X POST http://127.0.0.1:8000/eox/lookup-pids \
  -H "Content-Type: application/json" \
  -d '{"pids":["C9300-24T","ISR4331/K9"],"technology":"Routing and Switching","use_cache":true}'
```

### Hardware milestones through Cisco API

```bash
curl -X POST http://127.0.0.1:8000/eox/hardware-milestones \
  -H "Content-Type: application/json" \
  -d '{"pids":["C9300-24T"]}'
```

## Python usage

### Web scraper

```python
from EOX_API.services.cisco_eox_scraper import CiscoEoxScraperService

service = CiscoEoxScraperService()
link = service.find_device_series_link("C9300-24T", "Routing and Switching")
print(link)
```

### Cisco API client

```python
from EOX_API.services.cisco_api_client import CiscoApiClient

client = CiscoApiClient()
print(client.get_hardware_eox_by_product_id(["C9300-24T"]))
```

## Notes

- The web scraper depends on Cisco page structure and can break if the website changes.
- Cisco API calls require valid credentials and network access.
- Always validate important lifecycle data directly with Cisco before making business decisions.
- Do not commit credentials, token cache files, private device inventories, or generated logs.
