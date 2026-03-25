"""Logging configuration for the Primary School Management System."""

import logging

from education_system.primary_school.core.paths import LOGS_DIR
from education_system.shared.core.logging import setup_logging as _setup


def setup_logging(level=logging.INFO):
    """Configure application logging."""
    _setup(
        logger_name="education_system.primary_school",
        log_dir=LOGS_DIR,
        log_filename="primary_school.log",
        level=level,
    )
