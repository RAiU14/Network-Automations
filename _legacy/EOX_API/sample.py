from services.cisco_eox_scrapper import CiscoEoxScraperService

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
