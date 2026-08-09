"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _save_pinned(pins):
    try:
        _PIN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PIN_FILE.write_text(json.dumps(list(pins)))
    except Exception as e:
        logger.warning(f"Could not save pinned: {e}")
