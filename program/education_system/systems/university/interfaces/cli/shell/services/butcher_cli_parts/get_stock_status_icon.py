"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def get_stock_status_icon(stock: float) -> str:
    """Get status icon based on stock level"""
    if stock > 10:
        return "🟢"  # Good stock
    elif stock > 5:
        return "🟡"  # Low stock
    elif stock > 0:
        return "🟠"  # Very low stock
    else:
        return "🔴"  # Out of stock
