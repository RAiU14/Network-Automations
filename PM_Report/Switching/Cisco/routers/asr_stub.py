# Switching/Cisco/routers/asr_stub.py
from __future__ import annotations

import os
from typing import Dict, Optional

from logging_setup import configure_logging

logger = configure_logging(__name__)


def parse_file_asr(path: str) -> Optional[Dict]:
    """
    ASR (IOS-XE Router) placeholder parser.
    - Purpose today: log everything, return None so the dispatcher produces a placeholder row.
    - Future: implement real ASR parsing here.
    """
    logger.info("ASR stub invoked for path=%s", path)
    try:
        if not path or not os.path.exists(path):
            logger.error("ASR stub: path missing or not found: %s", path)
            return None

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception as e:
            logger.exception("ASR stub: failed to read file %s: %s", path, e)
            return None

        # Minimal peek to aid debugging later
        head = "\n".join(text.splitlines()[:40])
        logger.debug("ASR stub: file head (first 40 lines):\n%s", head)

        # If you want to return placeholder directly from here instead of letting
        # the dispatcher do it, you could — but our convention: return None.
        logger.info("ASR stub: returning None (dispatcher will emit placeholder row).")
        return None

    except Exception as e:
        logger.exception("ASR stub: unexpected error path=%s: %s", path, e)
        return None
