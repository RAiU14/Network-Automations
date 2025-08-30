# Switching/Cisco/ios/ios_classic_stub.py
# Classic IOS stub: detect/acknowledge, log everything, and return None so dispatcher placeholders neatly.
from __future__ import annotations

import os
import re
import sys
import logging
from typing import Optional, Dict, Any

# central logger
try:
    from logging_setup import configure_logging
    logger = configure_logging(__file__)
except Exception:
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("ios_classic_stub")
    logger.warning("ios_classic_stub: using fallback logger; logging_setup not found.")

# Make sure project root is importable (mirrors ios_xe_adapter approach)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
    logger.debug(f"ios_classic_stub: inserted PROJECT_ROOT into sys.path: {PROJECT_ROOT}")

# --- simple signatures for classic IOS ---
SIG_IOS_CLASSIC = re.compile(r"(?mi)^\s*cisco\s+ios\s+software\b")
SIG_IOS_XE      = re.compile(r"(?mi)\bios[- ]?xe\b")

def _peek_hostname(text: str) -> Optional[str]:
    try:
        m = re.search(r"(?mi)^\s*hostname\s+(\S+)", text)
        return m.group(1) if m else None
    except Exception:
        return None

def _peek_version(text: str) -> Optional[str]:
    try:
        m = re.search(r"(?mi)^\s*cisco\s+ios\s+software.*?\bversion\s+([^\s,]+)", text)
        return m.group(1) if m else None
    except Exception:
        return None

def parse_file_ios(path: str) -> Optional[Dict[str, Any]]:
    """
    Classic IOS stub parser.
    Behavior:
      - If file looks like *classic IOS* (and not IOS-XE), we log evidence and return None
        so the dispatcher will emit a standard placeholder row ("Unsupported IOS").
      - If the file actually looks like IOS-XE, we also return None so the dispatcher
        can route it through the XE adapter on a subsequent attempt.
      - On read errors, return None and the dispatcher will placeholder.

    Returns:
        None — always, because this is a stub (we don't parse classic IOS yet).
    """
    fname = os.path.basename(path)
    logger.info(f"ios_classic_stub.parse_file_ios: start file={fname} path={path}")

    if not os.path.isfile(path):
        logger.error("ios_classic_stub: path is not a file or missing: %s", path)
        return None

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        logger.debug("ios_classic_stub: loaded file bytes=%d", len(text))

        # quick signals
        has_iosxe = bool(SIG_IOS_XE.search(text))
        has_ios   = bool(SIG_IOS_CLASSIC.search(text))
        logger.debug("ios_classic_stub: has_ios=%s has_iosxe=%s", has_ios, has_iosxe)

        host = _peek_hostname(text) or "-"
        ver  = _peek_version(text) or "-"
        logger.info("ios_classic_stub: peek hostname=%r version=%r", host, ver)

        if has_iosxe:
            logger.info("ios_classic_stub: looks like IOS-XE; this stub is not responsible. Returning None.")
            return None

        if has_ios:
            logger.info("ios_classic_stub: confirmed classic IOS; stub returns None so dispatcher placeholders.")
            return None

        # Unknown/undetected — still return None; dispatcher will handle with a generic placeholder.
        logger.warning("ios_classic_stub: no clear IOS/IOS-XE signatures; returning None.")
        return None

    except Exception as e:
        logger.exception(f"ios_classic_stub: exception while reading/parsing {fname}: {e}")
        return None


__all__ = ["parse_file_ios"]