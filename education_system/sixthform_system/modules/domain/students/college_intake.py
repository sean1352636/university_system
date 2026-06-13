"""Sixth-form-side consumer for secondary progression events.

Subscribes to ``student.progression.completed`` on the durable
cross-system bus and admits the pupil into the sixth form (the
``college`` slot): it creates a ``students`` row linked to the canonical
``journey_id``.

Sixth-form enrolment requires three distinct, valid A-Level subjects. The
in-process ``sixthform_transfer`` flow captures real choices from staff
and forwards them on the bus payload; when the event arrives without them
(a pure event-driven progression) we seed three placeholder subjects so
the record is valid, leaving staff to amend the choices — mirroring the
default course the university intake assigns.

Idempotent: re-delivery is dropped by the bus, and a journey whose
``college`` slot is already filled is skipped.

Drained by :func:`drain_intake`, called on sixth-form startup.
"""

from __future__ import annotations

import logging

from education_system.shared.cross_system import progression

logger = logging.getLogger(__name__)

CONSUMER_SYSTEM = "college"


def _placeholder_subjects() -> list[str]:
    """Three distinct valid A-Level subjects to seed a bus-admitted
    student whose event carried no subject choices."""
    from education_system.sixthform_system.modules.domain.students.students import (
        students,
    )
    seed = list(dict.fromkeys(students.A_LEVEL_SUBJECTS))[:3]
    while len(seed) < 3:
        seed.append(f"TBC {len(seed) + 1}")
    return seed


def _admit(journey_id: str, payload: dict) -> str | None:
    """Create a sixth-form student from a progression payload."""
    from education_system.sixthform_system.modules.domain.students.students import (
        students,
    )
    from education_system.shared.cross_system import person

    p = person.get(journey_id)
    chosen = [
        (payload.get("subject_1") or "").strip(),
        (payload.get("subject_2") or "").strip(),
        (payload.get("subject_3") or "").strip(),
    ]
    if len([s for s in chosen if s]) != 3 or len(set(chosen)) != 3:
        chosen = _placeholder_subjects()

    student = students.create_student({
        "first_name": payload.get("first_name")
        or (p.legal_first_name if p else ""),
        "last_name": payload.get("last_name")
        or (p.legal_last_name if p else ""),
        "middle_name": payload.get("middle_name") or "",
        "title": payload.get("title") or "",
        "gender": payload.get("gender") or "",
        "date_of_birth": payload.get("date_of_birth")
        or (p.date_of_birth if p else ""),
        "phone": payload.get("phone") or "",
        "emergency_contact_name": payload.get("parent_name") or "",
        "emergency_contact_phone": payload.get("parent_phone") or "",
        "emergency_contact_relation": "Parent/Carer"
        if (payload.get("parent_name") or payload.get("parent_phone")) else "",
        "subject_1": chosen[0],
        "subject_2": chosen[1],
        "subject_3": chosen[2],
        "status": "Active",
    })
    return student.student_id


_intake = progression.ProgressionIntake(
    CONSUMER_SYSTEM, _admit,
    handler_name="college.students.college_intake",
    from_system="school")


def register_intake_consumer() -> None:
    """Idempotently subscribe the intake handler to the bus."""
    _intake.register()


def drain_intake(*, db_path: str | None = None) -> int:
    """Process any pending secondary progression events. Returns the
    number of (event, handler) dispatches. Safe to call repeatedly."""
    return _intake.drain(db_path=db_path)
