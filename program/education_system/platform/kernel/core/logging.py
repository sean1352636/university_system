"""Shared logging configuration for all education subsystems.

Provides a single ``setup_logging()`` function that configures file + console
handlers with a consistent format.  Each subsystem calls this once at startup.
"""

from __future__ import annotations

import logging
from pathlib import Path

_configured_loggers: set[str] = set()


def setup_logging(
    logger_name: str,
    log_dir: Path,
    log_filename: str = "app.log",
    level: int = logging.INFO,
    console_level: int = logging.WARNING,
) -> logging.Logger:
    """Configure file and console logging for a subsystem.

    Safe to call multiple times for the same *logger_name*; subsequent calls
    are no-ops.

    Parameters
    ----------
    logger_name:
        The logger namespace, e.g. ``"education_system.systems.university"``.
    log_dir:
        Directory where the log file will be written.
    log_filename:
        Name of the log file (default ``"app.log"``).
    level:
        Logging level for the file handler (default ``INFO``).
    console_level:
        Logging level for the console handler (default ``WARNING``).

    Returns
    -------
    logging.Logger
        The configured logger instance.
    """
    if logger_name in _configured_loggers:
        return logging.getLogger(logger_name)
    _configured_loggers.add(logger_name)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / log_filename

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
