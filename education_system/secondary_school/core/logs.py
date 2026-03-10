"""Logging configuration for the Secondary School Management System."""

import logging
from education_system.secondary_school.core.paths import LOGS_DIR, ensure_directories


def setup_logging(level: int = logging.INFO):
    """Configure application-wide logging."""
    ensure_directories()
    log_file = LOGS_DIR / "secondary_school.log"

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger("education_system.secondary_school")
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return root_logger
