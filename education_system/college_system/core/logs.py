"""Logging configuration for the College Management System."""

import logging

from education_system.college_system.core.paths import LOGS_DIR
from education_system.shared.core.logging import setup_logging as _setup


_configured = False


def configure_logging(level: int = logging.INFO):
    """Set up file and console logging for the college system.

    Safe to call multiple times; only the first call has effect.
    """
    global _configured
    if _configured:
        return
    _configured = True

    _setup(
        logger_name="education_system.college_system",
        log_dir=LOGS_DIR,
        log_filename="app.log",
        level=level,
        console_level=logging.WARNING,
    )
