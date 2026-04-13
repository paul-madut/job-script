"""
Logging setup for Job Cannon.
Logs to both console and a rotating file in output/logs/.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / "output" / "logs"


def get_logger(name: str) -> logging.Logger:
    """Get a logger that writes to console + file."""
    logger = logging.getLogger(f"jobcannon.{name}")

    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)

    # Console handler - INFO level
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))

    # File handler - DEBUG level, rotates at 5MB, keeps 3 backups
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_DIR / "jobcannon.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    logger.addHandler(console)
    logger.addHandler(file_handler)

    return logger
