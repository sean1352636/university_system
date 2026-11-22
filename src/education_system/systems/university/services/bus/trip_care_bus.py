"""Ports Trip Management uses to reach other university domains.

Trip Management lives in the Operations slice and may not import another
domain directly (the slice boundary ratchet), so the few things it needs
from Pastoral (sealing special-category fields, the health profile and
emergency contacts), Academics (the attendance register) and Finance (the
hardship fund) go through here:

* ``seal`` / ``seal_values`` / ``reveal`` / ``is_sealed`` — the health
  module's sealed-field helper, for ``trip_participants.medical_info``,
  ``dietary_requirements`` and ``accessibility_needs`` (registered there as
  always sealed);
* ``clinical_roles()`` — the health team's roles (``access.CLINICAL_ROLES``);
* ``health_details_for_trip(current_user, student_id)`` — the student's
  health profile (allergies, conditions, medications) and emergency
  contacts, read with the health portal's own access check and audit entry
  (fail closed) — so only the student themselves or the health team get
  anything back;
* ``record_trip_attendance(module_code, dates, student_ids, ...)`` — rows in
  ``attendance_records`` through the attendance service's writer, skipping
  any (student, module, date) already recorded;
* ``hardship_application(application_id)`` — a bursary application with
  its fund, for linking a trip hardship award to it.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

logger = logging.getLogger(__name__)

TABLE = "trip_participants"
SEALED_COLUMNS = ("medical_info", "dietary_requirements", "accessibility_needs")


# ── sealing ─────────────────────────────────────────────────────────────

def _sealed_fields():
    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    return sealed_fields


def seal(column: str, value: Any) -> Any:
    """``value`` as it is stored in ``trip_participants.<column>``."""
    return _sealed_fields().seal_value(TABLE, column, value)


def seal_values(values: dict) -> dict:
    """A copy of ``values`` with the special-category columns sealed."""
    return _sealed_fields().seal_values(TABLE, values)


def reveal(value: Any) -> Any:
    """Readable text of a stored value (plain text passes through)."""
    return _sealed_fields().reveal(value)


def is_sealed(value: Any) -> bool:
    from education_system.systems.university.domains.health.infrastructure.health import (
        field_crypto,
    )
    return field_crypto.is_sealed(value)


def clinical_roles() -> tuple[str, ...]:
    from education_system.systems.university.domains.health.application.health import access
    return tuple(access.CLINICAL_ROLES)


def admin_roles() -> tuple[str, ...]:
    from education_system.systems.university.domains.health.application.health import access
    return tuple(access.ADMIN_ROLES)


# ── health record import ────────────────────────────────────────────────

def health_details_for_trip(current_user: dict, student_id: str) -> dict:
    """The student's health profile and emergency contacts.

    ``current_user`` is the signed-in user (``username``, ``role``,
    ``student_id``). The health portal's rules decide: the student sees
    their own record, the health team anyone's, everybody else nothing
    (``PermissionError``). Each look is written to the immutable audit log
    first; if it can't be, nothing is returned.
    Returns ``{'profile': dict | None, 'allergies': [..], 'contacts': [..]}``.
    """
    from education_system.systems.university.domains.health.application.health import (
        access, profile,
    )
    from education_system.systems.university.domains.health.domain.health.services import (
        contacts,
    )
    from education_system.systems.university.domains.health.infrastructure.health.storage import (
        get_connection,
    )
    who = access.from_user(current_user)
    access.require_view(who, student_id)
    access.record_view(who, "trip_health_import", student_id=student_id,
                       reason="trip registration: participant consented to share")
    conn = get_connection()
    try:
        profile.ensure_schema(conn)
        record = profile.get(conn, student_id)
        if record:
            record = _sealed_fields().unseal_row(record)
        try:
            allergies = [dict(zip(("allergen", "severity", "reaction"), tuple(r))) for r in conn.execute(
                "SELECT allergen, severity, reaction_description FROM allergies "
                "WHERE student_id = ? ORDER BY id", (str(student_id),)).fetchall()]
        except Exception:
            allergies = []
    finally:
        conn.close()
    return {"profile": record, "allergies": allergies,
            "contacts": contacts.list_contacts(who, student_id)}


# ── attendance ──────────────────────────────────────────────────────────

def record_trip_attendance(module_code: str, dates: Iterable[str], student_ids: Iterable[str], *,
                           recorded_by: str = "System", note: str = "") -> int:
    """Mark each student present on each date for ``module_code``.

    Writes through the attendance service's ``record_attendance`` (lower-case
    status, session stamping, attendance-concern checks). A (student,
    module, date) that already has a row is left alone, so running it again
    writes nothing. Returns the number of rows written.
    """
    from education_system.systems.university.domains.teaching.domain.attendance.records import (
        record_attendance,
    )
    from education_system.systems.university.infrastructure.database.db import get_connection
    students = sorted({str(s) for s in student_ids if s})
    written = 0
    for date in dates:
        conn = get_connection()
        try:
            have = {r[0] for r in conn.execute(
                "SELECT student_id FROM attendance_records WHERE module_code = ? AND date = ?",
                (module_code, date)).fetchall()}
        finally:
            conn.close()
        rows = [(sid, "present", note) for sid in students if sid not in have]
        if not rows:
            continue
        if not record_attendance(module_code, date, rows, recorded_by=recorded_by):
            raise RuntimeError(f"attendance for {module_code} on {date} was not recorded")
        written += len(rows)
    return written


# ── hardship fund ───────────────────────────────────────────────────────

def hardship_application(application_id: int) -> dict:
    """``{'application_id', 'student_id', 'status', 'fund_id', 'fund_name',
    'fund_type'}`` for a bursary application. Raises ValueError when there
    is no such application."""
    from education_system.systems.university.domains.finance.domain.bursary.services.bursary_service import (
        BursaryService,
    )
    service = BursaryService()
    try:
        app = service.get_application(int(application_id))
        fund = service.get_fund(app["fund_id"])
    except Exception as exc:
        raise ValueError(f"bursary application {application_id}: {exc}") from None
    return {"application_id": app["application_id"], "student_id": app.get("student_id"),
            "status": app.get("status"), "fund_id": fund.get("fund_id"),
            "fund_name": fund.get("name"), "fund_type": fund.get("fund_type")}
