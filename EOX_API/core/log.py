from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from EOX_API.core.config import get_settings


def get_logger(name: str = "eox") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    settings = get_settings()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = RotatingFileHandler(
        settings.log_dir / "eox.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
