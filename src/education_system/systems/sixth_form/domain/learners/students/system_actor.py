"""Run a student-record write as the system when nobody is signed in.

Student, enrolment, learning-aim and tutor-group writes check the
signed-in principal (see ``admissions/_guard.py``). Work that reaches
them with nobody signed in into the sixth form — the cross-system
adapter driven by another phase's handover or a drainer, a background
job — names itself here instead, so the write is attributed to
``system:<name>`` and an anonymous call is still refused everywhere
else.

When a person *is* signed in their own principal is used unchanged:
a signed-in user is never widened to the system's capabilities.
"""

from __future__ import annotations

import contextlib
from typing import Any, Iterable, Iterator


def default_capabilities() -> tuple[str, ...]:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return (access.STUDENTS_MANAGE, access.ADMISSIONS)


@contextlib.contextmanager
def unless_signed_in(name: str, capabilities: Iterable[str] | None = None
                     ) -> Iterator[Any]:
    """Bind ``system:<name>`` with *capabilities* (default
    ``students.manage`` + ``admissions``) only if nobody is signed in."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    if _guard.actor() is not None:
        yield _guard.principal()
        return
    with _guard.system_actor(name, tuple(capabilities or default_capabilities())
                             ) as p:
        yield p
