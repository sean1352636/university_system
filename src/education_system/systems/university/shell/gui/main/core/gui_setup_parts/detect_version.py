"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _detect_version():
    try:
        from education_system.systems.university.services.bus import (
            __version__,
        )
        return str(__version__)
    except Exception:
        return ""
