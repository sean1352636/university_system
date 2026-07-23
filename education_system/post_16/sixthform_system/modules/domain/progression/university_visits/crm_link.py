"""Bridge from sixth-form University Visits to the university system's
Admissions CRM (``campus_tours`` + ``admission_prospects`` +
``tour_registrations``).

Push direction only: a visit + its attendees on the sixth-form side
becomes a campus tour with one prospect per student on the university
side. The resulting ``tour_id`` / ``prospect_id`` are written back into
the sixth-form rows so subsequent pushes update the existing records
instead of duplicating.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.post_16.sixthform_system.modules.domain.progression.university_visits import university_visits as data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data

logger = logging.getLogger(__name__)


@dataclass
class PushResult:
    visit_id: int
    campus_tour_id: int
    prospects_created: int
    prospects_reused: int
    registrations_created: int
    skipped: list[tuple[str, str]]   # (student_id, reason)


class CrmLinkError(RuntimeError):
    """Raised when the university system DB can't be reached or written."""


def _uni_transaction():
    """Open a transaction against the university system's DB.

    Import is deferred so the sixth-form module never hard-depends on
    the university_system package at import time.
    """
    try:
        from education_system.post_18.university_system.infrastructure.database.db import (
            transaction,
        )
    except Exception as exc:
        raise CrmLinkError(
            f"university_system not available: {exc}") from None
    return transaction()


def _ensure_admissions_schema() -> None:
    """Make sure the admissions tables exist in the university DB."""
    try:
        from education_system.post_18.university_system.infrastructure.database.schemas.admissions_schemas import (
            AdmissionsSchemas,
        )
    except Exception:
        # Older university-system layouts don't ship the schemas class —
        # the tables may already exist from runtime setup elsewhere.
        return
    try:
        from education_system.post_18.university_system.infrastructure.database.db import (
            get_connection,
        )
        conn = get_connection()
        try:
            AdmissionsSchemas.create_schemas(conn)
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception as exc:
        logger.debug("AdmissionsSchemas bootstrap failed: %s", exc)


def push_visit_to_university_crm(visit_id: int,
                                 *, school_name: str = "Sixth Form"
                                 ) -> PushResult:
    """Push a sixth-form visit + attendees into the university CRM.

    Idempotent: re-pushing updates the existing tour and tour-registration
    rows instead of creating duplicates.
    """
    visit = data.get_visit(visit_id)
    if visit is None:
        raise CrmLinkError(f"No visit #{visit_id}")
    attendees = data.list_attendees(visit_id)

    # Fetch student records once.
    students_by_id: dict[str, object] = {}
    for a in attendees:
        s = student_data.get_student(a.student_id)
        if s is not None:
            students_by_id[a.student_id] = s

    tour_guide = (visit.organiser_staff_id or school_name).strip()
    meeting_point = visit.university_name + (
        f" — {visit.location}" if visit.location else "")
    tour_time = visit.departure_time or "10:00"
    duration = _duration_minutes(visit.departure_time, visit.return_time)
    capacity = visit.capacity or max(len(attendees), 20)

    _ensure_admissions_schema()

    prospects_created = 0
    prospects_reused = 0
    registrations_created = 0
    skipped: list[tuple[str, str]] = []

    with _uni_transaction() as conn:
        # ── Tour upsert ─────────────────────────────────────────────
        existing_tour_id = visit.campus_tour_id  # type: ignore[attr-defined]
        tour_id: int
        if existing_tour_id:
            cur = conn.execute(
                "SELECT 1 FROM campus_tours WHERE tour_id = ?",
                (existing_tour_id,),
            )
            if cur.fetchone():
                conn.execute(
                    """UPDATE campus_tours SET
                           tour_date = ?, tour_time = ?, tour_guide = ?,
                           max_attendees = ?, meeting_point = ?,
                           duration_minutes = ?, status = ?
                       WHERE tour_id = ?""",
                    (visit.visit_date, tour_time, tour_guide,
                     capacity, meeting_point, duration,
                     _tour_status(visit.status), existing_tour_id),
                )
                tour_id = existing_tour_id
            else:
                tour_id = _insert_tour(
                    conn, visit.visit_date, tour_time, tour_guide,
                    capacity, meeting_point, duration, visit.status)
        else:
            tour_id = _insert_tour(
                conn, visit.visit_date, tour_time, tour_guide,
                capacity, meeting_point, duration, visit.status)

        # ── Per-attendee prospect + registration ───────────────────
        for a in attendees:
            s = students_by_id.get(a.student_id)
            if s is None:
                skipped.append((a.student_id, "student not found"))
                continue
            existing_prospect_id = a.prospect_id  # type: ignore[attr-defined]
            if existing_prospect_id and _prospect_exists(
                    conn, existing_prospect_id):
                prospect_id = existing_prospect_id
                prospects_reused += 1
            else:
                # Dedupe by email if a prospect with that email already exists.
                email = (s.email or "").strip()
                prospect_id = (_find_prospect_by_email(conn, email)
                                if email else None)
                if prospect_id is not None:
                    prospects_reused += 1
                else:
                    prospect_id = _insert_prospect(
                        conn, s, school_name=school_name,
                        source=f"School Visit — {visit.university_name}")
                    prospects_created += 1
                data.set_attendee_link(a.attendee_id, prospect_id)

            if _ensure_registration(conn, tour_id, prospect_id,
                                    attended=a.attended):
                registrations_created += 1

    data.set_visit_link(visit_id, tour_id)
    logger.info(
        "Pushed visit #%d to uni CRM: tour_id=%d, "
        "prospects_created=%d, prospects_reused=%d, registrations=%d",
        visit_id, tour_id, prospects_created, prospects_reused,
        registrations_created,
    )
    return PushResult(
        visit_id=visit_id, campus_tour_id=tour_id,
        prospects_created=prospects_created,
        prospects_reused=prospects_reused,
        registrations_created=registrations_created,
        skipped=skipped,
    )


# ── helpers ───────────────────────────────────────────────────────

def _insert_tour(conn, date: str, time: str, guide: str,
                 capacity: int, meeting_point: str,
                 duration_minutes: int, visit_status: str) -> int:
    cur = conn.execute(
        """INSERT INTO campus_tours
               (tour_date, tour_time, tour_guide, max_attendees,
                meeting_point, duration_minutes, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (date, time, guide, capacity, meeting_point,
         duration_minutes, _tour_status(visit_status)),
    )
    return int(cur.lastrowid)


def _tour_status(visit_status: str) -> str:
    return {
        "Planning":  "scheduled",
        "Confirmed": "scheduled",
        "Completed": "completed",
        "Cancelled": "cancelled",
    }.get(visit_status, "scheduled")


def _prospect_exists(conn, prospect_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM admission_prospects WHERE prospect_id = ?",
        (prospect_id,),
    ).fetchone() is not None


def _find_prospect_by_email(conn, email: str) -> int | None:
    if not email:
        return None
    r = conn.execute(
        "SELECT prospect_id FROM admission_prospects WHERE email = ? "
        "ORDER BY prospect_id LIMIT 1",
        (email,),
    ).fetchone()
    if r is None:
        return None
    # sqlite3.Row supports both index + name access.
    try:
        return int(r["prospect_id"])
    except Exception:
        return int(r[0])


def _insert_prospect(conn, student, *, school_name: str,
                     source: str) -> int:
    cur = conn.execute(
        """INSERT INTO admission_prospects
               (first_name, last_name, email, date_of_birth,
                high_school, source, status)
           VALUES (?, ?, ?, ?, ?, ?, 'prospect')""",
        (student.first_name or "",
         student.last_name or "",
         (student.email or "").strip(),
         getattr(student, "dob", None) or "",
         school_name, source),
    )
    return int(cur.lastrowid)


def _ensure_registration(conn, tour_id: int, prospect_id: int,
                         *, attended: bool) -> bool:
    """Insert a tour_registrations row if one doesn't already exist for
    this (tour, prospect). Returns True if a row was inserted."""
    r = conn.execute(
        "SELECT registration_id FROM tour_registrations "
        "WHERE tour_id = ? AND prospect_id = ?",
        (tour_id, prospect_id),
    ).fetchone()
    if r is not None:
        # Keep the attended flag in sync.
        conn.execute(
            "UPDATE tour_registrations SET attended = ? "
            "WHERE tour_id = ? AND prospect_id = ?",
            (1 if attended else 0, tour_id, prospect_id),
        )
        return False
    conn.execute(
        """INSERT INTO tour_registrations
               (tour_id, prospect_id, num_guests, attended)
           VALUES (?, ?, 0, ?)""",
        (tour_id, prospect_id, 1 if attended else 0),
    )
    # Bump the attendee counter on the tour.
    conn.execute(
        "UPDATE campus_tours SET current_attendees = current_attendees + 1 "
        "WHERE tour_id = ?",
        (tour_id,),
    )
    return True


def _duration_minutes(dep: str | None, ret: str | None) -> int:
    if not dep or not ret:
        return 90
    try:
        dh, dm = (int(p) for p in dep.split(":", 1))
        rh, rm = (int(p) for p in ret.split(":", 1))
    except (TypeError, ValueError):
        return 90
    mins = (rh * 60 + rm) - (dh * 60 + dm)
    return mins if mins > 0 else 90
