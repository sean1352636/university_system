"""Port onto Pastoral's Disability & Accessibility services for other slices.

Learners' Create Student asks "does the student have a disability?", opens
the portal for the student being entered, and records what was entered
once the student exists; the slice rules keep it from importing Pastoral
directly, so it comes through here (as ``visa_bus`` does for visas).

Usage::

    from education_system.systems.university.services.bus import disability_bus
    disability_bus.open_new_student_disabilities(dialog, auth, intake={...},
                                                 on_save=..., on_close=...)
    disability_bus.record_at_enrolment(auth, student_id, items)
"""

from __future__ import annotations


def categories() -> dict[str, str]:
    from education_system.systems.university.domains.student_support.domain.disability import portal
    return dict(portal.DISABILITY_CATEGORIES)


def open_new_student_disabilities(parent, auth, *, intake: dict, on_save, on_close=None):
    """Open the portal in new-student mode and return its window.

    ``on_save(items)`` gets ``[{'category', 'details', 'adjustment_type'}]``
    when the user saves; the window then closes. ``on_close()`` runs whenever
    the window goes, saved or not, after ``on_save``."""
    from education_system.systems.university.domains.student_support.interfaces.gui.disability.portal import (
        DisabilityPortal,
    )
    portal_window = DisabilityPortal(parent, auth, intake=intake, on_save=on_save).window
    if on_close is not None:
        portal_window.bind("<Destroy>",
                           lambda e: on_close() if e.widget is portal_window else None, add="+")
    return portal_window


def record_at_enrolment(auth, student_id, items) -> dict:
    """Record the disabilities for the student just created; returns
    ``{'disabilities': [ids], 'requests': [adjustment request ids]}``."""
    from education_system.systems.university.domains.student_support.domain.disability import portal
    return portal.record_at_enrolment(auth, student_id, items)
