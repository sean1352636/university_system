"""People lookups shared by the pastoral record modules.

The looked-after register, young carers, tutorial programme, contact log
and exit interviews all link records to students and to members of
staff. Forms hand staff over as ``"<staff id> — <name>"`` labels (or a
bare id); these helpers turn either into a checked id, and give the
interfaces the label lists to choose from.
"""

from __future__ import annotations

from typing import Any, Callable

LABEL_SEP = " — "


def _students():
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _s,
    )
    return _s


def _staff():
    from education_system.systems.sixth_form.domain.staff import staff as _st
    return _st


def student_exists(student_id: str) -> bool:
    return _students().get_student(student_id) is not None


def student_names() -> dict[str, str]:
    """``{student_id: full name}`` for every student."""
    return {s.student_id: s.full_name for s in _students().list_students()}


def staff_choices(*, active_only: bool = True) -> tuple[str, ...]:
    """``"<id> — <name>"`` labels for staff, for choice fields."""
    rows = _staff().list_staff(active_only=active_only)
    return tuple(f"{s.staff_id}{LABEL_SEP}{s.full_name}"
                 for s in sorted(rows, key=lambda s: (s.last_name,
                                                      s.first_name)))


def staff_label(staff_id: str | None) -> str | None:
    if not staff_id:
        return None
    s = _staff().get_staff(staff_id)
    return f"{staff_id}{LABEL_SEP}{s.full_name}" if s else staff_id


def staff_name(staff_id: str | None) -> str | None:
    if not staff_id:
        return None
    s = _staff().get_staff(staff_id)
    return s.full_name if s else None


def id_of(label: Any) -> str | None:
    """The id out of a ``"<id> — <name>"`` label, or the bare value."""
    if label is None:
        return None
    s = str(label).split(LABEL_SEP, 1)[0].strip()
    return s or None


def check_staff(value: Any, label: str,
                error: Callable[[str], Exception]) -> str | None:
    """A staff label or id → a staff id that exists (``None`` if blank)."""
    sid = id_of(value)
    if not sid:
        return None
    if _staff().get_staff(sid) is None:
        raise error(f"{label}: no member of staff with id {sid}")
    return sid


def current_staff_id() -> str | None:
    """The signed-in member of staff's id, when they have one."""
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access.current().staff_id


__all__ = ["LABEL_SEP", "student_exists", "student_names", "staff_choices",
           "staff_label", "staff_name", "id_of", "check_staff",
           "current_staff_id"]
