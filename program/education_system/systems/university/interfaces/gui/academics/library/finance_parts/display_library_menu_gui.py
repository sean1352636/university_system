"""Extracted function implementation."""

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_library_menu_gui():
    """Display library menu in GUI mode (backwards compatible)"""
    start_gui_library_system()
