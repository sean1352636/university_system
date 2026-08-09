"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def launch_butcher_cli(auth=None):
    """Launch butcher shop CLI (called from main menu)"""
    butcher_menu()
