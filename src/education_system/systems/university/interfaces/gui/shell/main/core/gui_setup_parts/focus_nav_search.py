"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _focus_nav_search(self):
    """Focus the navigation search entry. Called by the Ctrl+K
    binding on the root window. Best-effort — if the entry isn't
    alive (e.g. nav panel is mid-rebuild) the call is silent."""
    try:
        entry = getattr(self, 'nav_search_entry', None)
        if entry is None:
            return "break"
        if not entry.winfo_exists():
            return "break"
        entry.focus_set()
        # Select all so a follow-up keystroke replaces the
        # placeholder / previous query.
        try:
            entry.select_range(0, "end")
        except Exception:
            pass
    except tk.TclError:
        pass
    return "break"
