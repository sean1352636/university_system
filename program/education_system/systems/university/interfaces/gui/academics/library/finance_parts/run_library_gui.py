"""Extracted function implementation."""

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def run_library_gui():
    """Run the library GUI"""
    start_gui_library_system()
