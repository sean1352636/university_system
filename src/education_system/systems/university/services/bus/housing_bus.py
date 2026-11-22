"""Port onto university housing for other slices.

Learners' Create Student asks "does the student want university
accommodation?" and files the application here; the slice rules keep it
from importing Operations' housing package directly. The application lands
in the Housing GUI's Applications list as Pending, where housing staff
approve (assigning a room), reject or wait-list it as usual.

Usage::

    from education_system.systems.university.services.bus import housing_bus
    halls = housing_bus.halls()                  # [(building_id, name), ...]
    housing_bus.apply(student_id, room_type="Single", move_in_date="2026-09-20",
                      duration_months=9, building_id="B001", actor="admin")
"""

from __future__ import annotations


def _applications():
    from education_system.systems.university.domains.operations.domain.campus.housing.services.housing_accommodation import (
        applications,
    )
    return applications


def room_types() -> tuple[str, ...]:
    return tuple(_applications().ROOM_TYPES)


def halls() -> list[tuple[str, str]]:
    """``[(building_id, building_name), ...]``; empty if housing isn't set up."""
    try:
        return _applications().list_halls()
    except Exception:
        return []


def apply(student_id, *, room_type, move_in_date, duration_months, building_id=None,
          special_requirements=None, actor="housing") -> dict:
    """File a Pending application (see ``applications.submit_new_application``)."""
    return _applications().submit_new_application(
        student_id, room_type=room_type, move_in_date=move_in_date,
        duration_months=duration_months, preferred_building_id=building_id,
        special_requirements=special_requirements, actor=actor)
