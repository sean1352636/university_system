"""University progression: apprentices applying on to a degree or top-up.

The board is the platform's own (``university_applications_gui``), the same
one the sixth form and FE College use; this screen hosts it for the
apprenticeships system. The university owns every decision — offers,
conditions, confirmation — and the board only displays its live status.

Provider staff see it; employers and end-point assessors never do. Staff
may watch the board, and only those who may decide admissions may submit.
"""

from __future__ import annotations

from education_system.platform.cross_system import university_applications_gui
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.security.access import (
    PermissionDenied,
    require,
)

SOURCE_SYSTEM = "apprenticeships"


def render(gui) -> None:
    frame = gui.clear()
    try:
        require(gui.actor, "admission.view")
    except PermissionDenied as exc:
        widgets.heading(frame, "University Progression")
        widgets.empty_state(frame, str(exc))
        return
    university_applications_gui.render(
        gui, SOURCE_SYSTEM, parent=frame,
        read_only=not gui.actor.can("admission.decide"))
