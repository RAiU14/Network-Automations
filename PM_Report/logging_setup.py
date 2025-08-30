# logging_setup.py
import os
import logging
import datetime

def configure_logging(module_file: str) -> logging.Logger:
    """
    Configure logging for a module.
    Logs go to <module_folder>/logs/<YYYY-MM-DD>.log.
    Each module gets a named logger (module filename) with one handler,
    so importing across modules won’t duplicate handlers.
    """
    log_dir = os.path.join(os.path.dirname(os.path.abspath(module_file)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(
        log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"
    )

    logger_name = os.path.basename(module_file)  # e.g., "Cisco_IOS_XE.py"
    logger = logging.getLogger(logger_name)

    # Only add a handler once per logger
    if not logger.handlers:
        handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

    # Keep propagation off so we don't duplicate to root handlers
    logger.propagate = False
    return logger
