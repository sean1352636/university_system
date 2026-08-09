"""Extracted function implementation."""

from .. import butcher_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def launch_butcher_gui(parent=None, auth=None):
    """Launch the Butcher Shop GUI"""
    return ButcherGUI(parent, auth)
