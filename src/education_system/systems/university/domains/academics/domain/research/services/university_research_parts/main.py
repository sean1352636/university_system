"""Extracted function implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def main():
    _remove_legacy_db()
    app = UniversityApp()
    app.run()
