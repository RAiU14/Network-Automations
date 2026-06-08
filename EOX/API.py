from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping

from EOX_API.services.cisco_api_client import CiscoApiClient, CiscoApiError

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

_client = CiscoApiClient()


def get_cisco_access_token() -> str | None:
    try:
        return _client.get_access_token()
    except CiscoApiError as exc:
        logger.error("Error fetching Cisco access token: %s", exc)
        return None


def get_software_suggestions(token: str | None, pid_list: Iterable[str]) -> dict[str, Any] | None:
    try:
        suggestions = _client.get_software_suggestions(list(pid_list), token=token)
        # Preserve legacy behavior: single suggestion returns a dict, multiple returns a list.
        output: dict[str, Any] = {}
        for pid, rows in suggestions.items():
            if len(rows) == 1:
                output[pid] = rows[0]
            else:
                output[pid] = rows
        return output
    except Exception as exc:
        logger.error("Error fetching suggested software: %s", exc)
        return None


def get_software_eos(token: str | None, devices: Mapping[str, Iterable[str] | str]) -> dict[str, Any] | None:
    try:
        return _client.get_software_eos_by_release(devices, token=token)
    except Exception as exc:
        logger.error("Error fetching software EoS data: %s", exc)
        return None


def get_compatible_software(token: str | None, pids: Iterable[str]) -> dict[str, Any]:
    try:
        return _client.get_compatible_software(list(pids), token=token)
    except Exception as exc:
        logger.error("Error fetching compatible software data: %s", exc)
        return {}


def software_deferred_check(
    token: str | None,
    device_details: Mapping[str, Iterable[str] | str],
) -> dict[str, Any] | None:
    try:
        return _client.software_deferred_check(device_details, token=token)
    except Exception as exc:
        logger.error("Error checking software deferred status: %s", exc)
        return None


def eox_milestone(device_details: Mapping[str, Any] | Iterable[str]) -> dict[str, Any] | None:
    try:
        return _client.get_hardware_eox_by_product_id(device_details)
    except Exception as exc:
        logger.error("Error fetching hardware EOX milestone data: %s", exc)
        return None


def software_milestones(device_details: Mapping[str, Iterable[str] | str]) -> dict[str, Any] | None:
    try:
        return _client.software_milestones(device_details)
    except Exception as exc:
        logger.error("Error fetching software milestone data: %s", exc)
        return None


if __name__ == "__main__":
    sample_devices = {
        "C9200L-48P-4G-E": ["17.12.5", "16.12.8", "16.11.1", "17.9.6"],
    }
    print(software_milestones(sample_devices))
