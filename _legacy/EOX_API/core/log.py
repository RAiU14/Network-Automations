import logging

def get_logger(name: str = "app") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
        logger.addHandler(h)
    return logger
