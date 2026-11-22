"""Port onto Academics' windows for other slices.

A screen in another domain that offers a "open Grade Tracking" shortcut
(Pastoral's Internship Management) comes through here; the slice rules keep
it from importing Academics' GUI directly (as ``visa_bus`` does for the
visa window).
"""

from __future__ import annotations


def open_grade_tracking(parent, auth=None) -> None:
    """Open Grade Tracking in a window over ``parent``. Raises ImportError
    when Academics' GUI isn't available."""
    from education_system.systems.university.domains.teaching.interfaces.gui._cross_launchers import (
        open_grade_gui,
    )
    open_grade_gui(parent, auth=auth)
