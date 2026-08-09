"""Extracted function implementation."""

from .. import first_aid_portal_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _is_valid_id(value: str) -> bool:
    return bool(_ID_RE.match((value or "").strip()))
