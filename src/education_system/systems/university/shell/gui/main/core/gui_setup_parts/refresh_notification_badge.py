"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _refresh_notification_badge(self):
    """Update the bell button label with the current unread count.
    Safe to call from the periodic session timer — swallows the Tk
    destroy-race TclError like the other timer-driven updates."""
    btn = getattr(self, 'notif_bell_btn', None)
    if btn is None:
        return
    try:
        if not btn.winfo_exists():
            return
    except tk.TclError:
        return
    count = self._get_unread_notification_count()
    label = "🔔" if count <= 0 else (f"🔔 {count}" if count < 100 else "🔔 99+")
    try:
        btn.config(text=label)
    except tk.TclError:
        pass
