from __future__ import annotations

from EOX_API.services.cisco_eox_scraper import CiscoEoxScraperService


def main() -> None:
    service = CiscoEoxScraperService()
    pid = "WS-C2960-24-S"
    technology = "Routing and Switching"

    series_link = service.find_device_series_link(pid, technology)
    print("Series link:", series_link)
    if not series_link:
        raise SystemExit("No series link found for PID")

    checked = service.eox_check(series_link)
    print("EOX check result:", checked)
    if not checked:
        raise SystemExit("No EOX data on product page")

    has_eox, eol_data = checked
    redirect_link = eol_data.get("url")
    if not has_eox or not redirect_link:
        print("No EOX redirect link. Product page dates:", eol_data)
        return

    announcements = service.eox_details(redirect_link) or {}
    print("Announcements found:", len(announcements))
    if not announcements:
        raise SystemExit("No EOX announcements found")

    title, announcement_link = next(iter(announcements.items()))
    print("Using announcement:", title)

    scraped = service.eox_scraping(announcement_link)
    if not scraped:
        raise SystemExit("Failed to scrape EOX announcement")

    milestones, affected_devices = scraped
    print("\nMilestones:")
    for key, value in milestones.items():
        print(f"{key}: {value}")
    print("\nAffected devices count:", len(affected_devices))


if __name__ == "__main__":
    main()
