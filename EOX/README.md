# Cisco EOX Legacy Wrapper

`EOX/` contains backward-compatible Python modules used by older scripts in this repository.

The implementation now delegates to `EOX_API` services, but old imports and function names are kept where practical.

## Main modules

| File | Purpose |
|---|---|
| `Cisco_EOX.py` | Legacy web scraping wrapper functions |
| `API.py` | Legacy wrapper around Cisco API client functions |
| `requirements.txt` | Minimal dependency list for EOX usage |

## Common legacy functions

- `category()`
- `open_cat(link)`
- `eox_check(link)`
- `eox_details(link)`
- `eox_scrapping(link)`
- `eox_scraping(link)`
- `find_device_series_link(pid, tech)`
- `request_EOX_data_from_local_db(unique_pid_list, tech)`
- `request_EOX_data_from_online(unique_pid_list, tech)`
- `sub_controller(raw_data, unique_pid, tech)`

## Example

```python
from EOX.Cisco_EOX import request_EOX_data_from_local_db

pids = ["C9300-24T", "ISR4331/K9"]
results = request_EOX_data_from_local_db(pids, "Routing and Switching")
print(results)
```

## Recommendation

For new code, use `EOX_API.services.cisco_eox_scraper.CiscoEoxScraperService` directly.

Use this package only when maintaining older scripts that already depend on `EOX.Cisco_EOX` or `EOX.API`.
