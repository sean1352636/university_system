"""Extracted function implementation."""

from .. import nailbar_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def launch_nailbar_gui(parent=None, auth=None):
    """Launch the Nail Bar GUI"""
    return NailBarGUI(parent, auth)
