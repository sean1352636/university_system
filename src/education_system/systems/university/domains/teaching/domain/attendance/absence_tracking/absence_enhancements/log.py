"""Shared logger for the absence enhancement services.

Routes through the central rotating file handler (logs/app.log) so output
joins ``university_system/logs/app.log``.
"""

from __future__ import annotations

import logging

try:
    from education_system.systems.university.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="absence_enhancements")
except Exception:  # pragma: no cover
    logger = logging.getLogger("absence_enhancements")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

__all__ = ["logger"]
