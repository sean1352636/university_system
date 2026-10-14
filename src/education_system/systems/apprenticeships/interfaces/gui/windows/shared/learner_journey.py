"""Learner journey (360): one learner's record across every system.

Hosts the platform's ``StudentJourneyFrame`` — school, college, university
and apprenticeship history on one screen. It reads across systems, so it
is for provider staff only: employers and end-point assessors are scoped
to their own apprentices and never reach it.
"""

from __future__ import annotations

from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services.access import (
    PermissionDenied,
    require,
)


def render(gui) -> None:
    frame = gui.clear()
    try:
        require(gui.actor, "admission.view")
    except PermissionDenied as exc:
        widgets.heading(frame, "Learner Journey")
        widgets.empty_state(frame, str(exc))
        return
    # Imported on open: the journey frame is a platform screen with its own
    # read models, which most sessions never open.
    from education_system.platform.cross_system.journey_gui import StudentJourneyFrame

    StudentJourneyFrame(frame, db_path=None, auth=gui.auth).pack(
        fill="both", expand=True)
