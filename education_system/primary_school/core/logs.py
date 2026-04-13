"""Logging configuration for the Primary School Management System."""

import logging
import os

from education_system.primary_school.core.paths import LOGS_DIR
from education_system.shared.core.logging import setup_logging as _setup

_LOGGER_NAME = "education_system.primary_school"


def _resolve_level(level: int | str) -> int:
    """Normalise a logging level, accepting both int and string forms.

    Raises ``ValueError`` for unrecognised level names.
    """
    if isinstance(level, int):
        return level
    numeric = logging.getLevelNamesMapping().get(level.upper())
    if numeric is None:
        raise ValueError(
            f"Invalid logging level: {level!r}. "
            f"Expected one of: {', '.join(logging.getLevelNamesMapping())}"
        )
    return numeric


def setup_logging(
    level: int | str | None = None,
    log_filename: str = "primary_school.log",
) -> logging.Logger:
    """Configure application logging and return the configured logger.

    Parameters
    ----------
    level:
        Logging level as an ``int`` (e.g. ``logging.DEBUG``) or a ``str``
        (e.g. ``"INFO"``).  Falls back to the ``PRIMARY_SCHOOL_LOG_LEVEL``
        environment variable, then to ``logging.INFO``.
    log_filename:
        Name of the log file written inside the logs directory.
    """
    if level is None:
        env_level = os.environ.get("PRIMARY_SCHOOL_LOG_LEVEL")
        level = _resolve_level(env_level) if env_level else logging.INFO
    else:
        level = _resolve_level(level)

    return _setup(
        logger_name=_LOGGER_NAME,
        log_dir=LOGS_DIR,
        log_filename=log_filename,
        level=level,
    )


logger = logging.getLogger(_LOGGER_NAME)

__all__ = ["setup_logging", "logger"]
