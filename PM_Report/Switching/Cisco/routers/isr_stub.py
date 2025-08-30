# Switching/Cisco/routers/isr_stub.py
from __future__ import annotations

import os
from typing import Dict, Optional

from logging_setup import configure_logging

logger = configure_logging(__name__)


def parse_file_isr(path: str) -> Optional[Dict]:
    """
    ISR (IOS-XE Router) placeholder parser.
    - Purpose today: log everything, return None so the dispatcher produces a placeholder row.
    - Future: implement real ISR parsing here.
    """
    logger.info("ISR stub invoked for path=%s", path)
    try:
        if not path or not os.path.exists(path):
            logger.error("ISR stub: path missing or not found: %s", path)
            return None

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception as e:
            logger.exception("ISR stub: failed to read file %s: %s", path, e)
            return None

        # Minimal peek for diagnostics
        head = "\n".join(text.splitlines()[:40])
        logger.debug("ISR stub: file head (first 40 lines):\n%s", head)

        logger.info("ISR stub: returning None (dispatcher will emit placeholder row).")
        return None

    except Exception as e:
        logger.exception("ISR stub: unexpected error path=%s: %s", path, e)
        return None
