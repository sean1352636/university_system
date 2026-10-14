"""Extracted function implementation."""
import logging

logger = logging.getLogger(__name__)

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _cancel_timers(self):
    """Cancel all scheduled timers to prevent errors on window destroy"""
    try:
        if self._session_timer_id is not None:
            self.root.after_cancel(self._session_timer_id)
            self._session_timer_id = None
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
    try:
        clock_id = getattr(self, '_clock_timer_id', None)
        if clock_id is not None:
            self.root.after_cancel(clock_id)
            self._clock_timer_id = None
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
