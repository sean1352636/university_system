"""FE College referrals: apprentices taking an FE course (dual enrolment).

The board is the platform's own (``fe_applications_gui``); this screen hosts
it for the apprenticeships system — the apprenticeship side of the two-way
FE College ↔ Apprenticeship link. Provider staff see it; employers and
end-point assessors never do. Only those who may decide admissions may refer.
"""

from __future__ import annotations

from education_system.platform.cross_system import fe_applications_gui
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
        widgets.heading(frame, "FE College Referrals")
        widgets.empty_state(frame, str(exc))
        return
    fe_applications_gui.render(gui, SOURCE_SYSTEM, parent=frame,
                               read_only=not gui.actor.can("admission.decide"))
