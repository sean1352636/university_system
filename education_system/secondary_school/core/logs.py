"""Logging configuration for the Secondary School Management System."""

import logging

from education_system.secondary_school.core.paths import LOGS_DIR
from education_system.shared.core.logging import setup_logging as _setup


def setup_logging(level: int = logging.INFO):
    """Configure application-wide logging."""
    return _setup(
        logger_name="education_system.secondary_school",
        log_dir=LOGS_DIR,
        log_filename="secondary_school.log",
        level=level,
    )
