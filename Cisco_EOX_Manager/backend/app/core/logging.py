from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

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
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        logger.warning("File logging is unavailable", exc_info=True)

    return logger
