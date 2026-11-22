"""Training Provider Requests: apprentices sent on a short course.

The board is the platform's own (``training_provider_requests_gui``); this
screen hosts it - the apprenticeship side of the Apprenticeships ↔ Training
Provider link. A certificate the provider issues comes back as off-the-job
hours awaiting approval. Provider staff see it; employers and end-point
assessors never do. Only those who may decide admissions may send requests.
"""

from __future__ import annotations

from education_system.platform.cross_system import training_provider_requests_gui
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.security.access import (
    PermissionDenied,
    require,
)
from education_system.systems.apprenticeships.interfaces.gui import widgets

SOURCE_SYSTEM = "apprenticeships"


def apprentices(actor) -> list[tuple[str, str]]:
    """``[(apprentice_id, label), ...]`` for the apprentices *actor* may see."""
    return [(str(s.apprentice.apprentice_id),
             f"{s.apprentice.given_name} {s.apprentice.family_name} "
             f"({s.apprentice.status}{', ' + s.employer_name if s.employer_name else ''})")
            for s in apprentice_service.list_apprentices(actor)
            if s.apprentice.status not in ("Withdrawn", "Transferred")]


def render(gui) -> None:
    frame = gui.clear()
    try:
        require(gui.actor, "admission.view")
    except PermissionDenied as exc:
        widgets.heading(frame, training_provider_requests_gui.TITLE)
        widgets.empty_state(frame, str(exc))
        return
    training_provider_requests_gui.render(
        frame, SOURCE_SYSTEM, learners=lambda: apprentices(gui.actor),
        can_request=gui.actor.can("admission.decide"), referrer=gui.actor.name)
