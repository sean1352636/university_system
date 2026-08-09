"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def format_currency(amount: float) -> str:
    """Format amount as currency"""
    return f"GBP {amount:.2f}"
