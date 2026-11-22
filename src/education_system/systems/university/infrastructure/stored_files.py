"""Finding a stored file whose recorded path is out of date.

Rows written before the repository moved (2026-08-09) still hold absolute
paths under the old tree, e.g. ``~/education_system/post_18/
university_system/data/submissions/…``. The files themselves now live under
``var/`` (``UNIVERSITY_SUBMISSIONS_DIR`` …). :func:`resolve` returns the path
as stored when it exists, otherwise the same file under its current home,
otherwise the stored path unchanged (so the caller reports it missing).
"""

from __future__ import annotations

from pathlib import Path

# (marker in an old path, current directory that holds what follows it)
def _homes():
    from education_system import paths
    return (
        ("/data/submissions/", paths.UNIVERSITY_SUBMISSIONS_DIR),
        ("/submissions/", paths.UNIVERSITY_SUBMISSIONS_DIR),
        ("/backups/database/", paths.UNIVERSITY_BACKUP_DATABASE_DIR),
        ("/data/uploads/", paths.UNIVERSITY_UPLOAD_DIR),
        ("/data/student_documents/", paths.UNIVERSITY_STUDENT_DOCUMENTS_DIR),
    )


def resolve(stored) -> Path:
    """The stored file's current location (see the module docstring)."""
    path = Path(str(stored or ""))
    if not str(stored or "") or path.exists():
        return path
    text = path.as_posix()
    for marker, home in _homes():
        if marker in text:
            candidate = Path(home) / text.split(marker, 1)[1]
            if candidate.exists():
                return candidate
    return path
