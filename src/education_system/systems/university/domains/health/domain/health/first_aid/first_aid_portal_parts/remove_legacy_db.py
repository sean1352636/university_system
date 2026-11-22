"""Extracted function implementation."""

from .. import first_aid_portal_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _remove_legacy_db():
    """Sweep any stray local SQLite files that earlier iterations of
    this module may have written alongside it. Data lives in the
    central `student_records.db`."""
    here = os.path.dirname(os.path.abspath(__file__))
    for fname in os.listdir(here) if os.path.isdir(here) else []:
        if fname.endswith(('.db', '.db-wal', '.db-shm', '.db-journal')):
            path = os.path.join(here, fname)
            try:
                os.remove(path)
                logger.info("Removed legacy first-aid DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)
