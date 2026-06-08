from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

from EOX_API.services.cisco_eox_scraper import CiscoEoxScraperService

logging.getLogger(__name__).addHandler(logging.NullHandler())

default_database_path = str(Path(__file__).resolve().parents[1] / "Database" / "JSON_Files" / "eox_pid.json")
cisco_url = "https://www.cisco.com"

_service = CiscoEoxScraperService(db_path=Path(default_database_path))


def _service_with_db(db_path: str | Path | None = None) -> CiscoEoxScraperService:
    if db_path:
        return CiscoEoxScraperService(db_path=Path(db_path))
    return _service


def link_check(link: str) -> str | bool:
    return _service.link_check(link) or False


def category() -> dict[str, str]:
    return _service.category()


def open_cat(link: str) -> list[dict[str, dict[str, str]]] | None:
    opened = _service.open_cat(link)
    if opened is None:
        return None
    series, eox = opened
    output = [{"series": series}]
    if eox:
        output.append({"eox": eox})
    return output


def eox_check(link: str) -> list[Any] | None:
    checked = _service.eox_check(link)
    return [checked[0], checked[1]] if checked else None


def eox_details(link: str) -> dict[str, str] | bool | None:
    details = _service.eox_details(link)
    if details == {}:
        return False
    return details


def eox_scrapping(link: str) -> list[Any] | None:
    scraped = _service.eox_scraping(link)
    return [scraped[0], scraped[1]] if scraped else None


def eox_scraping(link: str) -> list[Any] | None:
    return eox_scrapping(link)


def get_possible_series(pid: str) -> list[str]:
    return _service.get_possible_series(pid)


def find_device_series_link(pid: str, tech: str) -> str | bool | None:
    return _service.find_device_series_link(pid, tech) or False


def pid_eox_check(pid: str, link: str) -> list[Any] | None:
    checked = _service.pid_eox_check(pid, link)
    return [checked[0], checked[1]] if checked else None


def eox_online_scrapping(pid: str, tech: str) -> dict[str, list[Any]]:
    return _service.eox_online_scraping(pid, tech)


def eox_online_scraping(pid: str, tech: str) -> dict[str, list[Any]]:
    return eox_online_scrapping(pid, tech)


def request_EOX_data_from_local_db(
    unique_pid_list: Iterable[str],
    tech: str,
    db_path: str | Path = default_database_path,
) -> dict[str, Any]:
    return _service_with_db(db_path).request_eox_data_from_local_db(unique_pid_list, tech)


def request_EOX_data_from_online(
    unique_pid_list: Iterable[str] | None = None,
    tech: str | None = None,
    existing_data: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    # Older WebPage code sometimes called this with excel_file_path=...; do not crash.
    if unique_pid_list is None:
        logging.getLogger(__name__).warning(
            "request_EOX_data_from_online called without PID list. kwargs=%s", kwargs
        )
        return existing_data or {}
    if tech is None:
        tech = kwargs.get("technology") or "Routing and Switching"
    return _service.request_eox_data_from_online(unique_pid_list, tech, existing_data=existing_data)


def update_lifecycle_data(data_list: list[dict[str, Any]], lifecycle_info: dict[str, Any]) -> list[dict[str, Any]]:
    return _service.update_lifecycle_data(data_list, lifecycle_info)


def sub_controller(raw_data: list[dict[str, Any]], unique_pid: Iterable[str], tech: str) -> list[dict[str, Any]]:
    return _service.sub_controller(raw_data, unique_pid, tech)


def eox_tes() -> bool:
    """Simple availability hook used by the WebPage controller."""
    return True
