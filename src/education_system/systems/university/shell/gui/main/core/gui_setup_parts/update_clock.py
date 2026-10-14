"""Extracted function implementation."""
import logging

logger = logging.getLogger(__name__)

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _update_clock(self):
    """Tick the header clock once a second.

    Reschedules itself via ``after`` and stores the id on
    ``_clock_timer_id`` so ``_cancel_timers`` can stop it cleanly on
    window destroy (mirrors the session-timer pattern; swallows the
    destroy-race TclError like the other timer-driven updates)."""
    var = getattr(self, 'clock_var', None)
    if var is None:
        return
    try:
        if not self.root.winfo_exists():
            return
    except tk.TclError:
        return
    from datetime import datetime
    try:
        var.set(datetime.now().strftime('%a %d %b %Y  ·  %H:%M:%S'))
    except tk.TclError:
        return
    try:
        self._clock_timer_id = self.root.after(1000, self._update_clock)
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
