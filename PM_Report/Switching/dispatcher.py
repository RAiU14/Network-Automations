# Switching/dispatcher.py
from __future__ import annotations

import glob
import logging
import os
from typing import Dict, List, Optional

# --- platform detector ---
from platform_detect import detect_family_from_file


# ----- Adapters/Stubs (import if available; otherwise fall back to placeholder) -----
def _placeholder_row(filename: str, remark: str = "Non-IOS_XE") -> Dict:
    U = "Unsupported IOS"
    return {
        "File name": [os.path.basename(filename)],
        "Host name": [U],
        "Model number": [U],
        "Serial number": [U],
        "Interface ip address": [U],
        "Uptime": [U],
        "Current s/w version": [U],
        "Last Reboot Reason": [U],
        "Any Debug?": [U],
        "CPU Utilization": [U],
        "Total memory": [U],
        "Used memory": [U],
        "Free memory": [U],
        "Memory Utilization (%)": [U],
        "Total flash memory": [U],
        "Used flash memory": [U],
        "Free flash memory": [U],
        "Used Flash (%)": [U],
        "Fan status": [U],
        "Temperature status": [U],
        "PowerSupply status": [U],
        "Available Free Ports": [U],
        "Any Half Duplex": [U],
        "Interface/Module Remark": [U],
        "Config Status": [U],
        "Config Save Date": [U],
        "Critical logs": [U],
        "Current SW EOS": [U],
        "Suggested s/w ver": [U],
        "s/w release date": [U],
        "Latest S/W version": [U],
        "Production s/w is deffered or not?": [U],
        "End-of-Sale Date: HW": [U],
        "Last Date of Support: HW": [U],
        "End of Routine Failure Analysis Date:  HW": [U],
        "End of Vulnerability/Security Support: HW": [U],
        "End of SW Maintenance Releases Date: HW": [U],
        "Remark": [remark],
    }


# Default fallbacks
def _xe_fallback(path: str) -> Dict:
    logging.warning("XE adapter not found; returning placeholder for %s", path)
    return _placeholder_row(path, "Non-IOS_XE")

def _ios_fallback(path: str) -> Dict:
    logging.warning("IOS classic stub not found; returning placeholder for %s", path)
    return _placeholder_row(path, "IOS_CLASSIC (stub)")

def _asr_fallback(path: str) -> Dict:
    logging.warning("ASR stub not found; returning placeholder for %s", path)
    return _placeholder_row(path, "ASR (stub)")

def _isr_fallback(path: str) -> Dict:
    logging.warning("ISR stub not found; returning placeholder for %s", path)
    return _placeholder_row(path, "ISR (stub)")


# Try to import real adapters/stubs
try:
    from Switching.Cisco.ios_xe.ios_xe_adapter import parse_file_xe  # type: ignore
except Exception:
    parse_file_xe = _xe_fallback  # noqa: F401

try:
    from Switching.Cisco.ios.ios_classic_stub import parse_file_ios_classic  # type: ignore
except Exception:
    parse_file_ios_classic = _ios_fallback  # noqa: F401

try:
    from Switching.Cisco.routers.asr_stub import parse_file_asr  # type: ignore
except Exception:
    parse_file_asr = _asr_fallback  # noqa: F401

try:
    from Switching.Cisco.routers.isr_stub import parse_file_isr  # type: ignore
except Exception:
    parse_file_isr = _isr_fallback  # noqa: F401


# -------- file collection helper (used by File_to_call) ----------
def collect_paths(
    input_path: str,
    includes: Optional[List[str]] = None,
    excludes: Optional[List[str]] = None,
) -> List[str]:
    """
    Accepts a directory OR a single file and returns a sorted list of files to process.
    Filters out temp/hidden files; keeps .txt/.log/.cfg.
    """
    def _match_any(name: str, patterns: Optional[List[str]]) -> bool:
        if not patterns:
            return True
        return any(glob.fnmatch.fnmatch(name, pat) for pat in patterns)

    if os.path.isfile(input_path):
        base = os.path.basename(input_path)
        if base.startswith(("~$", ".")):
            return []
        if not base.lower().endswith((".txt", ".log", ".cfg")):
            return []
        if not _match_any(base, includes):
            return []
        if excludes and any(glob.fnmatch.fnmatch(base, pat) for pat in excludes):
            return []
        return [input_path]

    if not os.path.isdir(input_path):
        raise FileNotFoundError(f"Input path is neither file nor directory: {input_path}")

    files: List[str] = []
    for n in os.listdir(input_path):
        if n.startswith(("~$", ".")):
            continue
        if not n.lower().endswith((".txt", ".log", ".cfg")):
            continue
        if includes and not _match_any(n, includes):
            continue
        if excludes and any(glob.fnmatch.fnmatch(n, pat) for pat in excludes):
            continue
        files.append(os.path.join(input_path, n))
    return sorted(files)


# -------- main dispatcher ----------
def parse_file_via_dispatcher(path: str) -> Dict:
    """
    Detect family from file, route to the right adapter, and always return a row dict.
    """
    try:
        info = detect_family_from_file(path)
        family = (info.get("family") or "UNKNOWN").upper()
        logging.debug("Detection for %s → %s (version=%s) why=%s",
                      os.path.basename(path), family, info.get("version_raw"),
                      (info.get("evidence") or {}).get("why"))

        if family in ("IOS_XE_SWITCH",):
            return parse_file_xe(path)

        if family in ("IOS_CLASSIC",):
            return parse_file_ios_classic(path)

        if family in ("IOS_XE_ROUTER_ASR", "ASR"):
            return parse_file_asr(path)

        if family in ("IOS_XE_ROUTER_ISR", "ISR"):
            return parse_file_isr(path)

        # Unknown → placeholder
        return _placeholder_row(path, remark="UNKNOWN family")

    except Exception as e:
        logging.exception("Dispatcher error for %s: %s", path, e)
        return _placeholder_row(path, remark="Dispatcher exception")
