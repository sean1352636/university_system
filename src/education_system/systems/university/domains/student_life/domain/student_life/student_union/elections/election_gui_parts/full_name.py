"""Extracted function implementation."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _full_name(first, last, fallback=""):
    """Compose 'first last' from possibly-None columns; fall back to id."""
    s = " ".join(p for p in (first or "", last or "") if p).strip()
    return s or fallback
