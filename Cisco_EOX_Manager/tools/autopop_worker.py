#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PRODUCT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.logging import get_logger  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.services.autopop_jobs import run_next_queued_job_once  # noqa: E402

logger = get_logger("eox_manager.autopop_worker")


def main() -> int:
    poll_seconds = float(os.getenv("EOX_AUTOPOP_WORKER_POLL_SECONDS", "5"))
    logger.info("Auto_Pop worker starting. Poll interval=%ss", poll_seconds)
    init_db()
    while True:
        try:
            ran = run_next_queued_job_once()
            if not ran:
                time.sleep(poll_seconds)
        except KeyboardInterrupt:
            logger.info("Auto_Pop worker stopped")
            return 0
        except Exception as exc:
            logger.exception("Auto_Pop worker loop failed: %s", exc)
            time.sleep(max(5.0, poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
