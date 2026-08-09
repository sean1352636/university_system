"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _load_pinned():
    try:
        if _PIN_FILE.exists():
            data = json.loads(_PIN_FILE.read_text())
            if isinstance(data, list):
                return data
    except Exception as e:
        logger.debug(f"Could not load pinned: {e}")
    return []
