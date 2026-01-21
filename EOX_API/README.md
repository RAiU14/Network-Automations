# Cisco EOX Scraper API (EOX_API)

This project provides a Python service and API wrapper to scrape Cisco Support pages to retrieve:
- Cisco product/technology categories
- Device series links under a technology category
- EOX / EOL presence + milestone data (from Cisco announcement pages)
- Affected device list associated with an EOX announcement

> ✅ Note: The server returning `GET / -> 404` is expected unless a `/` route is defined. Your API is still running fine.

---

## Features

- **Service class** (`CiscoEoxScraperService`) for direct Python integration
- Optional API layer (FastAPI) if you want to expose routes later
- Uses `requests.Session()` for better performance
- Uses BeautifulSoup + lxml for parsing

> ⚠️ Scraping is dependent on Cisco HTML structure. If Cisco changes the page structure, parsing logic may need updates.

---

## Requirements

- Python 3.10+ recommended (3.12 works)
- Internet access (Cisco pages are fetched live)

Install dependencies:

```bash
pip install -r requirements.txt
```

## Project Structure 
Network-Automations/
  EOX_API/
    __init__.py
    main.py
    api/
      __init__.py
      routes_eox.py          (optional if you expose REST)
    core/
      __init__.py
      config.py
      log.py
    models/
      __init__.py
      eox.py                 (pydantic models, optional for library usage)
    services/
      __init__.py
      cisco_eox_scraper.py   (main scraper service)
  requirements.txt
  README.md


### Running the Application (Server Mode)

If your EOX_API/main.py defines a FastAPI app, you can run:
```bash
    python -m uvicorn EOX_API.main:app --reload
```

### You will see something like:
```bash
Uvicorn running on http://127.0.0.1:8000
```

### Why / shows 404

If you open http://127.0.0.1:8000/ in a browser, you'll get:

404 Not Found


That just means you have no route for /. The server is still running correctly.

## Using the Application in a Python Program (Recommended)

Most users will want to **import and call** the scraper directly from Python
(no server required).

The main entry point is the service class:

```python
from EOX_API.services.cisco_eox_scraper import CiscoEoxScraperService
```

## Example 1: Get Cisco Product Categories

```python
from EOX_API.services.cisco_eox_scraper import CiscoEoxScraperService

svc = CiscoEoxScraperService()
categories = svc.category()

print("Number of categories:", len(categories))
for name, link in list(categories.items())[:5]:
    print(f"{name}: {link}")
```


## Example 2: Find Device Series Link Using PID + Technology

```python 
from EOX_API.services.cisco_eox_scraper import CiscoEoxScraperService

svc = CiscoEoxScraperService()

pid = "C9300-24T"
technology = "Routing and Switching"

series_link = svc.find_device_series_link(pid, technology)

if not series_link:
    print("No matching series link found for PID.")
else:
    print("Matched series link:", series_link)
```


 ## Example 3: Check Product Page for EOX / EOL Information

This checks if a Cisco product page contains:
- EOX redirect URL
- Visible EOL/EOS date information

```python 
from EOX_API.services.cisco_eox_scraper import CiscoEoxScraperService

svc = CiscoEoxScraperService()

product_link = "/c/en/us/support/switches/catalyst-9300-series-switches/series.html"
result = svc.eox_check(product_link)

if not result:
    print("No EOX information found.")
else:
    has_eox, eol_data = result
    print("Has EOX redirect:", has_eox)
    print("EOL Data:", eol_data)
```

## Example 4: Retrieve EOX Announcement URLs from Redirect Page

```python
from EOX_API.services.cisco_eox_scraper import CiscoEoxScraperService

svc = CiscoEoxScraperService()

redirect_link = "/c/en/us/products/eos-eol-notice-listing.html"
announcement_urls = svc.eox_details(redirect_link)

print("Announcements found:", len(announcement_urls))
for title, link in list(announcement_urls.items())[:5]:
    print(f"{title} -> {link}")
```

## Example 5: Scrape Milestones and Affected Devices from Announcement Page

```python 
from EOX_API.services.cisco_eox_scraper import CiscoEoxScraperService

svc = CiscoEoxScraperService()

announcement_link = "/c/en/us/products/collateral/switches/catalyst-9300-series-switches/eos-eol-notice-c51-xxxxxx.html"
result = svc.eox_scrapping(announcement_link)

if not result:
    print("Failed to scrape EOX announcement page.")
else:
    milestones, affected_devices = result

    print("Milestones:")
    for key, value in milestones.items():
        print(f"  {key}: {value}")

    print("\nAffected Devices (first 10):")
    for device in affected_devices[:10]:
        print(" ", device)
```

## End-to-End Flow: PID → EOX Milestones

Typical automation flow:
- Find device series link from PID + technology
- Check product page for EOX/EOL details
- Retrieve EOX announcement URLs
- Scrape milestone dates and affected devices


# Complete End-to-End Example

```python
from EOX_API.services.cisco_eox_scrapper import CiscoEoxScraperService

svc = CiscoEoxScraperService()

pid = "WS-C2960-24-S"
technology = "Routing and Switching"

# Step 1: Find device series link
series_link = svc.find_device_series_link(pid, technology)
print("Series link:", series_link)

if not series_link:
    raise SystemExit("No series link found for PID")

# Step 2: Check EOX presence
result = svc.eox_check(series_link)
print("EOX check result:", result)

if not result:
    raise SystemExit("No EOX data on product page")

has_eox, eol_data = result
redirect_link = (eol_data or {}).get("url")
print("Redirect link:", redirect_link)

if not redirect_link:
    raise SystemExit("EOX redirect link not found")

# Step 3: Get announcement URLs
announcements = svc.eox_details(redirect_link) or {}
print("Number of announcements:", len(announcements))

if not announcements:
    raise SystemExit("No EOX announcements found")

# Step 4: Scrape first announcement
title, announcement_link = next(iter(announcements.items()))
print("Using announcement:", title)

scraped = svc.eox_scrapping(announcement_link)
if not scraped:
    raise SystemExit("Failed to scrape EOX announcement")

milestones, affected_devices = scraped

print("\nMilestones:")
for key, value in milestones.items():
    print(f"{key}: {value}")

print("\nAffected Devices Count:", len(affected_devices))
```

## Common Issues & Troubleshooting

---

### Import Could Not Be Resolved (VS Code)

If VS Code shows an error like:
Import "EOX_API.services.cisco_eox_scraper" could not be resolved

This is usually an **editor configuration issue**, not a Python error.

#### Fix checklist
- Open the **repository root folder** in VS Code (the folder that contains `EOX_API/`)
- Ensure these files exist:
EOX_API/init.py
EOX_API/services/init.py
- Select the correct Python interpreter:
- `Ctrl + Shift + P` → **Python: Select Interpreter**
- Run Python as a module:
```bash
python -m EOX_API.main
```

uvicorn EOX_API.main:app Does Not Work (Windows / VS Code)

On Windows, the uvicorn executable may not be on PATH or may use a different Python environment.
### Recommended way to run the server
```python
python -m uvicorn EOX_API.main:app --reload
```


This ensures:
- Correct Python interpreter
- Correct virtual environment
- Correct module resolution
- Server Running but / Returns 404

If you see:

```python
GET / 404 Not Found
```
This is expected behavior.

The application does not define a route for / by default.
The server is still running correctly.

To verify the server:
- Check terminal output for:

```bash
Application startup complete.
Uvicorn running on http://127.0.0.1:8000
```

```bash
ModuleNotFoundError: No module named 'EOX_API'
```
This means Python does not know where the EOX_API package is.

### Fix
- Run commands from the repository root, not inside EOX_API/
- Use module execution:
    ```python
        python -m EOX_API.main
    ```

Do not run individual files directly:

    ```python
        python EOX_API/services/cisco_eox_scraper.py  ❌
    ```

### Cisco Page Parsing Fails / Returns Empty Data

The scraper depends on Cisco’s public HTML structure.
If Cisco changes the page layout:
- Some fields may be missing
- Parsing logic may fail silently

### What to do

- Print or log the fetched HTML
- Inspect page structure using browser DevTools
- Update BeautifulSoup selectors accordingly

`langdetect` Errors or Unexpected Exceptions

`langdetect.detect()` may raise exceptions for short or malformed text.

This is already guarded in the code, but if errors persist:
- Wrap calls in try/except
- Skip language detection for very short strings

### Slow Performance or Timeouts
Scraping is network-bound and may be slow.
Recommendations: 
- Avoid running large PID batches sequentially
- Add caching (JSON / Redis) for repeated lookups
- Add rate limiting to avoid hitting Cisco too frequently

### Editor Warnings vs Runtime Errors
VS Code (Pylance) warnings do not always indicate runtime failures.

### Source of truth
Always test with:
```python
python -c "from EOX_API.services.cisco_eox_scraper import CiscoEoxScraperService; print('OK')"
```

If this prints OK, your code is valid even if VS Code shows warnings.

## Unexpected None or Empty Results
Some Cisco products:
- Do not have EOX announcements
- Have incomplete lifecycle data
- Are not listed under expected categories

Always check for None before accessing returned values.

## Support Notes

This project scrapes Cisco public pages.
Use responsibly and consider:
- Rate limiting
- Caching
- Internal-only usage for automation workflows

