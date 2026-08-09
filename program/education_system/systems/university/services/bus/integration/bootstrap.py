"""Integration subscriber bootstrap."""
import logging
from education_system.systems.university.services.events.in_process import subscribe
from .persistence.event_log import _ensure_log_table
from .registry import SUBSCRIBERS

logger = logging.getLogger(__name__)
_WIRED = False

def wire_subscribers() -> None:
    """Idempotently subscribe every consumer-side handler."""
    global _WIRED
    if _WIRED:
        return
    _ensure_log_table()
    for event_name, handler in SUBSCRIBERS:
        subscribe(event_name, handler)
    _WIRED = True
    logger.info("integration_bus subscribers wired")

def reset_for_tests() -> None:
    """Flip the wired flag back so wire_subscribers can re-run."""
    global _WIRED
    _WIRED = False
