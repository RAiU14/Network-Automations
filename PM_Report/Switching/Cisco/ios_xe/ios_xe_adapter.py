# Switching/Cisco/ios_xe/ios_xe_adapter.py
# Thin adapter around your existing Cisco_IOS_XE.process_file(), with deep logging.
from __future__ import annotations

import os
import sys
import logging
from typing import Any, Dict, Optional

# central logger
try:
    from logging_setup import configure_logging
    logger = configure_logging(__file__)
except Exception:
    # very early fallback if logging_setup import fails
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("ios_xe_adapter")
    logger.warning("ios_xe_adapter: using fallback logger; logging_setup not found.")

# -------------------------------------------------------------------
# Make sure we can import your top-level Cisco_IOS_XE module
# (it lives at project root alongside IOS_XE_Stack_Switch.py).
# This file is at:  PM_Report/Switching/Cisco/ios_xe/ios_xe_adapter.py
# Root is three levels up.
# -------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
    logger.debug(f"ios_xe_adapter: inserted PROJECT_ROOT into sys.path: {PROJECT_ROOT}")

XE = None
try:
    import Cisco_IOS_XE as XE
    logger.info("ios_xe_adapter: imported Cisco_IOS_XE successfully.")
except Exception as e:
    logger.exception(f"ios_xe_adapter: FAILED to import Cisco_IOS_XE: {e}")
    XE = None  # keep going; dispatcher will show placeholder if None

# -------------------------
# Helpers / validations
# -------------------------
REQUIRED_KEYS = {
    "File name", "Host name", "Model number", "Serial number",
    "Interface ip address", "Uptime", "Current s/w version",
    "Last Reboot Reason", "Any Debug?", "CPU Utilization",
    "Total memory", "Used memory", "Free memory", "Memory Utilization (%)",
    "Total flash memory", "Used flash memory", "Free flash memory", "Used Flash (%)",
    "Fan status", "Temperature status", "PowerSupply status", "Available Free Ports",
    "Any Half Duplex", "Interface/Module Remark", "Config Status", "Config Save Date",
    "Critical logs", "Current SW EOS", "Suggested s/w ver", "s/w release date",
    "Latest S/W version", "Production s/w is deffered or not?",
    "End-of-Sale Date: HW", "Last Date of Support: HW",
    "End of Routine Failure Analysis Date:  HW",
    "End of Vulnerability/Security Support: HW",
    "End of SW Maintenance Releases Date: HW", "Remark"
}

def _is_wide_row_dict(d: Dict[str, Any]) -> bool:
    """Validate the 'one wide row' dict shape your Excel writer expects."""
    if not isinstance(d, dict):
        logger.debug(f"_is_wide_row_dict: not a dict (type={type(d)})")
        return False
    missing = [k for k in REQUIRED_KEYS if k not in d]
    if missing:
        logger.debug(f"_is_wide_row_dict: missing keys: {missing}")
        # it's OK to be missing; we still accept but log it
    # At least ensure we have File name and some core fields
    core = {"File name", "Host name", "Current s/w version"}
    if not core.issubset(d.keys()):
        logger.debug(f"_is_wide_row_dict: core keys missing -> have={list(d.keys())[:8]}")
        return False
    return True

# -------------------------
# Public API (used by dispatcher)
# -------------------------
def parse_file_xe(path: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single IOS-XE device log and return a *single wide row dict*
    (values are lists for columns), exactly as Cisco_IOS_XE.process_file returns.

    Returns:
        dict on success (wide row shape), or None on error (dispatcher will placeholder).
    """
    fname = os.path.basename(path)
    logger.info(f"parse_file_xe: start file={fname} path={path}")

    # sanity
    if XE is None:
        logger.error("parse_file_xe: Cisco_IOS_XE is not imported; returning None.")
        return None
    if not os.path.isfile(path):
        logger.error("parse_file_xe: path not a file or missing: %s", path)
        return None

    try:
        # We let your original module read the file and do everything.
        logger.debug("parse_file_xe: calling XE.process_file(%s)", path)
        row = XE.process_file(path)
        logger.debug("parse_file_xe: XE.process_file returned type=%s", type(row))

        if not row:
            logger.warning("parse_file_xe: XE.process_file returned empty/falsey for %s", fname)
            return None

        if not isinstance(row, dict):
            logger.error("parse_file_xe: unexpected return (not dict). type=%s", type(row))
            return None

        # Validate shape (non-fatal; we still return but log details)
        if _is_wide_row_dict(row):
            logger.info("parse_file_xe: validated wide row shape for %s", fname)
        else:
            logger.warning("parse_file_xe: row shape is non-standard for %s (Excel may still accept).", fname)

        # Light peek into a couple of key values so we can see them in logs
        try:
            host = row.get("Host name", [""])[0] if isinstance(row.get("Host name"), list) else row.get("Host name")
            ver  = row.get("Current s/w version", [""])[0] if isinstance(row.get("Current s/w version"), list) else row.get("Current s/w version")
            ip   = row.get("Interface ip address", [""])[0] if isinstance(row.get("Interface ip address"), list) else row.get("Interface ip address")
            logger.debug("parse_file_xe: head values host=%r version=%r ip=%r", host, ver, ip)
        except Exception:
            logger.debug("parse_file_xe: could not preview head values safely.")

        return row

    except Exception as e:
        # We never raise — dispatcher will convert None → placeholder row with reason.
        logger.exception(f"parse_file_xe: exception while parsing {fname}: {e}")
        return None

__all__ = ["parse_file_xe"]