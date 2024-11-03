import logging
from datetime import datetime
from pathlib import Path

def setup_logger() -> logging.Logger:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_filename = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    logger = logging.getLogger("SolarEVChargerLogger")
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(file_handler)
    return logger