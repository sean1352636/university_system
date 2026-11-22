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

from education_system.systems.sixth_form.domain.progression.university_visits import university_visits as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data

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


def _university():
    """The university's platform adapter.

    The sixth form never imports the university: the CRM rows are the
    university's to write, so it is asked through the adapter registry.
    """
    try:
        from education_system.platform.cross_system.adapters import route_support
        return route_support.adapter_for("university")
    except Exception as exc:
        raise CrmLinkError(
            f"university_system not available: {exc}") from None


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

    skipped: list[tuple[str, str]] = []
    sent: list[dict] = []
    by_key: dict[str, object] = {}
    for a in attendees:
        s = students_by_id.get(a.student_id)
        if s is None:
            skipped.append((a.student_id, "student not found"))
            continue
        key = str(a.attendee_id)
        by_key[key] = a
        sent.append({
            "key": key,
            "prospect_id": a.prospect_id,  # type: ignore[attr-defined]
            "first_name": s.first_name or "",
            "last_name": s.last_name or "",
            "email": (s.email or "").strip(),
            "date_of_birth": getattr(s, "dob", None) or "",
            "high_school": school_name,
            "source": f"School Visit — {visit.university_name}",
            "attended": bool(a.attended),
        })

    tour = {
        "tour_id": visit.campus_tour_id,  # type: ignore[attr-defined]
        "tour_date": visit.visit_date, "tour_time": tour_time,
        "tour_guide": tour_guide, "max_attendees": capacity,
        "meeting_point": meeting_point, "duration_minutes": duration,
        "status": _tour_status(visit.status),
    }
    # Unavailable university -> CrmLinkError; a database error from the
    # university side propagates as before.
    result = _university().record_school_visit(tour, sent)

    tour_id = int(result["tour_id"])
    prospects_created = 0
    prospects_reused = 0
    for key, link in (result.get("prospects") or {}).items():
        a = by_key.get(key)
        if a is None:
            continue
        prospect_id = int(link["prospect_id"])
        if link.get("created"):
            prospects_created += 1
        else:
            prospects_reused += 1
        if prospect_id != a.prospect_id:  # type: ignore[attr-defined]
            data.set_attendee_link(a.attendee_id, prospect_id)  # type: ignore[attr-defined]
    registrations_created = int(result.get("registrations_created") or 0)

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

def _tour_status(visit_status: str) -> str:
    return {
        "Planning":  "scheduled",
        "Confirmed": "scheduled",
        "Completed": "completed",
        "Cancelled": "cancelled",
    }.get(visit_status, "scheduled")


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
