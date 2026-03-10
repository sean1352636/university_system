"""Logging configuration for the College Management System."""

import logging
from pathlib import Path

from education_system.college_system.core.paths import LOGS_DIR


_configured = False


def configure_logging(level: int = logging.INFO):
    """Set up file and console logging for the college system.

    Safe to call multiple times; only the first call has effect.
    """
    global _configured
    if _configured:
        return
    _configured = True

    log_file = LOGS_DIR / "app.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    root = logging.getLogger("education_system.college_system")
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
