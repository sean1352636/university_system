"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def create_themed_toplevel(self, title="", geometry=""):
    """Create a Toplevel window"""
    window = tk.Toplevel(self.root)
    _install_clean_close(window)
    if title:
        window.title(title)
    if geometry:
        window.geometry(geometry)
    window.transient(self.root)
    return window
