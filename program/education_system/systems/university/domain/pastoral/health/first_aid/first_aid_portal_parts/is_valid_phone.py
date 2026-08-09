"""Extracted function implementation."""

from .. import first_aid_portal_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _is_valid_phone(value: str) -> bool:
    v = (value or "").strip()
    return bool(_PHONE_RE.match(v)) and sum(c.isdigit() for c in v) >= 7
