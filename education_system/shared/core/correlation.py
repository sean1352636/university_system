"""Correlation/request ID context management for structured logging.

Provides a context variable that carries a request/correlation ID across
the lifetime of a single request. A logging Filter injects the ID into
every log record so it appears in all structured log output.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

# ---------------------------------------------------------------------------
# Context variable
# ---------------------------------------------------------------------------

_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Return the current correlation ID, or an empty string if none is set."""
    return _correlation_id_var.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current execution context."""
    _correlation_id_var.set(correlation_id)


def new_correlation_id() -> str:
    """Generate a new short correlation ID, set it, and return it."""
    cid = uuid.uuid4().hex[:16]
    set_correlation_id(cid)
    return cid


# ---------------------------------------------------------------------------
# Logging filter
# ---------------------------------------------------------------------------

class CorrelationFilter(logging.Filter):
    """Inject ``correlation_id`` into every log record.

    Attach to any handler or logger::

        logger.addFilter(CorrelationFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.correlation_id = get_correlation_id() or "-"
        return True
