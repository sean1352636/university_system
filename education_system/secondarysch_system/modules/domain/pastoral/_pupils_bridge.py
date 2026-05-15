"""Adapter exposing pupils with `.student_id` for modules ported from
the sixth-form system (which uses ``student_id``).

Only the subset of the sixth-form ``students`` API actually called by
ported modules is exposed: ``init_db``, ``list_students``,
``get_student``.
"""

from __future__ import annotations

from dataclasses import dataclass

from education_system.secondarysch_system.modules.domain.pupils.pupils import (
    pupils as _pupils_mod,
)


@dataclass
class StudentLike:
    student_id: str
    first_name: str
    last_name: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


def _wrap(p) -> StudentLike:
    return StudentLike(
        student_id=p.pupil_id,
        first_name=p.first_name,
        last_name=p.last_name,
    )


def init_db() -> None:
    _pupils_mod.init_db()


def list_students() -> list[StudentLike]:
    return [_wrap(p) for p in _pupils_mod.list_pupils()]


def get_student(sid: str) -> StudentLike | None:
    p = _pupils_mod.get_pupil(sid)
    return _wrap(p) if p else None
