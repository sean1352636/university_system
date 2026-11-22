"""Port onto Pastoral's health records for subject access requests.

Governance's Information Rights answers a SAR with a health section built by
the health portal's own rules (``pastoral/application/health/subject_access``:
sealed fields readable, internal notes and third-party data withheld and
counted), written to the health export folder and optionally encrypted with
the health key. The slice rules keep Governance from importing Pastoral, so
those calls come through here.
"""

from __future__ import annotations

from pathlib import Path


def health_section(conn, student_id) -> dict:
    """``{"records": {table: [rows]}, "withheld": {what: count}, "consent": [...]}``"""
    from education_system.systems.university.domains.health.application.health import (
        subject_access,
    )
    return subject_access.health_section(conn, student_id)


def export_path(filename: str) -> Path:
    """A fresh path for ``filename`` in the health export folder."""
    from education_system.systems.university.domains.health.infrastructure.health import (
        export_writer,
    )
    return export_writer.export_path(filename)


def finalize_export(path, *, encrypt: bool = False) -> Path:
    """Make the export owner-only and, if asked, encrypt it in place."""
    from education_system.systems.university.domains.health.infrastructure.health import (
        export_writer,
    )
    return export_writer.finalize(path, encrypt=encrypt)
