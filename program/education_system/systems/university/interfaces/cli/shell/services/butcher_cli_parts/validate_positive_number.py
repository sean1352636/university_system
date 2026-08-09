"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def validate_positive_number(value: str, field_name: str = "Value") -> Optional[float]:
    """Validate and convert a positive number"""
    try:
        num = float(value)
        if num <= 0:
            print(f"❌ {field_name} must be greater than 0")
            return None
        return num
    except ValueError:
        print(f"❌ Invalid {field_name}. Please enter a valid number.")
        return None
