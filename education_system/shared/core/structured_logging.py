"""Centralized structured logging for the education system.

Provides:
- ``JSONFormatter`` — ELK-compatible JSON log formatter
- ``setup_structured_logging()`` — configure root logger with JSON or text
  format, driven by the ``LOG_FORMAT`` and ``LOG_LEVEL`` environment variables

ELK field mapping
-----------------
``@timestamp``  ISO-8601 UTC timestamp
``level``       Log level name (INFO, WARNING, …)
``logger``      Logger name (dotted module path)
``message``     Human-readable message
``request_id``  Correlation / request ID from context (if set)
``system``      System tag injected at setup time (optional)
``user_id``     Present when callers pass ``extra={"user_id": ...}``
``module``      Python module name from the log record
``exc_info``    Formatted exception traceback (only when an exception is active)
"""

from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Any

from education_system.shared.core.correlation import CorrelationFilter, get_correlation_id

__all__ = [
    "JSONFormatter",
    "setup_structured_logging",
]

# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON suitable for ELK / OpenSearch.

    Parameters
    ----------
    system:
        Optional system tag included in every record (e.g. ``"college"``).
    extra_fields:
        Additional static key/value pairs merged into every record.
    """

    def __init__(
        self,
        system: str = "",
        extra_fields: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self._system = system
        self._extra_fields = extra_fields or {}

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        # Base payload — order matters for readability in Kibana
        payload: dict[str, Any] = {
            "@timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "correlation_id", None)
                          or get_correlation_id()
                          or None,
            "module": record.module,
        }

        # Optional static fields
        if self._system:
            payload["system"] = self._system

        # Per-record extras forwarded via logging's extra= parameter
        for field in ("user_id", "system", "request_id"):
            val = getattr(record, field, None)
            if val is not None:
                payload[field] = val

        # Merge static extra fields (lowest precedence)
        for k, v in self._extra_fields.items():
            payload.setdefault(k, v)

        # Exception info
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        elif record.exc_text:
            payload["exc_info"] = record.exc_text

        # Stack info (e.g. from logger.warning(..., stack_info=True))
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        # Drop None values so ELK mappings stay clean
        payload = {k: v for k, v in payload.items() if v is not None}

        return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# Setup helper
# ---------------------------------------------------------------------------

def setup_structured_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    system: str = "",
) -> None:
    """Configure the root logger for structured output.

    Call once at application startup. Subsequent calls are idempotent
    (honours the ``_configured`` sentinel).

    Environment variables (override keyword arguments):
        ``LOG_LEVEL``   — e.g. ``"DEBUG"``, ``"WARNING"``
        ``LOG_FORMAT``  — ``"json"`` (default) or ``"text"``
        ``LOG_SYSTEM``  — system tag embedded in every JSON record

    Parameters
    ----------
    log_level:
        Default log level if ``LOG_LEVEL`` env var is absent.
    log_format:
        ``"json"`` for ELK-compatible output, ``"text"`` for human-readable.
    system:
        System tag (e.g. ``"university"``).  Overridden by ``LOG_SYSTEM``.
    """
    if getattr(setup_structured_logging, "_configured", False):
        return
    setup_structured_logging._configured = True  # type: ignore[attr-defined]

    effective_level = os.getenv("LOG_LEVEL", log_level).upper()
    effective_format = os.getenv("LOG_FORMAT", log_format).lower()
    effective_system = os.getenv("LOG_SYSTEM", system)

    numeric_level = getattr(logging, effective_level, logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Remove any handlers added before this call (e.g. by basicConfig)
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setLevel(numeric_level)

    if effective_format == "json":
        formatter: logging.Formatter = JSONFormatter(system=effective_system)
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s "
            "[%(correlation_id)s] — %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    handler.setFormatter(formatter)
    handler.addFilter(CorrelationFilter())
    root.addHandler(handler)

    logging.getLogger(__name__).debug(
        "Structured logging configured (format=%s, level=%s, system=%s)",
        effective_format,
        effective_level,
        effective_system or "(none)",
    )
