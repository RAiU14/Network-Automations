from __future__ import annotations

import logging
import time
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings


@lru_cache(maxsize=16)
def get_logger(name: str = "eox_manager") -> logging.Logger:
    settings = get_settings()
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    try:
        log_file = Path(settings.log_dir) / "eox_manager.log"
        file_handler = RotatingFileHandler(log_file, maxBytes=10_000_000, backupCount=5, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        logger.warning("File logging is unavailable", exc_info=True)

    return logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        logger = get_logger("eox_manager.access")
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.exception("%s %s failed after %sms", request.method, request.url.path, duration_ms)
            raise
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info("%s %s -> %s in %sms", request.method, request.url.path, response.status_code, duration_ms)
        return response
