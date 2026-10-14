"""Cross-system screens for provider staff.

University progression (an apprentice applying on to a degree or top-up)
and the learner journey across every system. Both read beyond this
system's own records, so both need ``admission.view`` — held by admin and
staff, never by employers or end-point assessors. Submitting an
application additionally needs ``admission.decide``.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from education_system.platform.cross_system import journey_cli, university_applications_cli
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.services.access import Actor, require

SOURCE_SYSTEM = "apprenticeships"


def university_progression(actor: Actor) -> None:
    require(actor, "admission.view")
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Application dashboard",
         partial(university_applications_cli.dashboard, SOURCE_SYSTEM)),
    ]
    if actor.can("admission.decide"):
        entries.append((
            "Progress an apprentice to university",
            partial(university_applications_cli.create, SOURCE_SYSTEM,
                    actor=actor.username or None)))
    prompts.run_menu("University Progression", entries)


def learner_journey(actor: Actor) -> None:
    require(actor, "admission.view")
    journey_cli.prompt_and_show(SOURCE_SYSTEM)
