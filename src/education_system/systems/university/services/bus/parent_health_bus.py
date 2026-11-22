"""Port onto Pastoral's health records for the parent portal (Academics).

A parent sees an adult student's medical information only with the
student's current consent to share it with them, and every look is
recorded (pastoral/application/health: consent, access). The slice rules
keep Academics' parent portal from importing Pastoral directly, so the
rules it needs come through here.
"""

from __future__ import annotations

PARENT_VIEW_AREA = "parent_portal_medical"



def may_show_parent(current_user, student_id) -> bool:
    """True when the student has agreed to share their medical information
    with a parent — and the look has then been recorded. False when there is
    no consent (or none can be read). Raises ``PermissionError`` when the look
    cannot be recorded (the health portal refuses an unrecorded view)."""
    from education_system.systems.university.domains.health.application.health import (
        access, consent,
    )
    try:
        shared = consent.has_consent(student_id, "share_with_parent")
    except Exception:
        return False
    if shared:
        access.record_view(access.from_user(current_user), PARENT_VIEW_AREA,
                           student_id=student_id)
    return bool(shared)


def reveal(value):
    """A stored health value as readable text (sealed columns unsealed)."""
    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    return sealed_fields.reveal(value)


def ensure_records_schema(conn) -> None:
    """The health-record columns the portal reads (e.g. ``archived``)."""
    from education_system.systems.university.domains.health.application.health import (
        workflow,
    )
    workflow.ensure_schema(conn)


def ensure_profile_schema(conn) -> None:
    """The one-row-per-student health profile (``medical_info``)."""
    from education_system.systems.university.domains.health.application.health import (
        profile,
    )
    profile.ensure_schema(conn)


def upsert_profile(conn, student_id, values) -> None:
    """Update the student's health profile row, creating it if missing (in
    the caller's transaction)."""
    from education_system.systems.university.domains.health.application.health import (
        profile,
    )
    profile.upsert(conn, student_id, values)
