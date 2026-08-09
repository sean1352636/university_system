"""Extracted function implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def fmt_date(s):
    if not s:
        return "—"
    try:
        return datetime.fromisoformat(s).strftime("%d %b %Y")
    except Exception:
        return s
