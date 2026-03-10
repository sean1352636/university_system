"""Logging configuration for the Primary School Management System."""

import logging
from .paths import LOGS_DIR


def setup_logging(level=logging.INFO):
    """Configure application logging."""
    log_file = LOGS_DIR / "primary_school.log"
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logging.getLogger("primary_school").setLevel(level)
