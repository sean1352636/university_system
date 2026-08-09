"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def launch_barber_cli(auth=None):
    """Launch barber shop CLI (called from main menu)"""
    barber_menu()
