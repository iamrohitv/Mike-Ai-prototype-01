import logging
import os

from security.paths import get_config_path


def get_logger():
    log_dir = os.path.join(get_config_path(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger("mike")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(
            os.path.join(log_dir, "mike.log"), encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
    return logger