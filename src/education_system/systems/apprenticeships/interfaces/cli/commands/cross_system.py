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

from education_system.platform.cross_system import (
    fe_applications_cli,
    journey_cli,
    training_provider_requests_cli,
    university_applications_cli,
)
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.application.security.access import Actor, require

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


def fe_referrals(actor: Actor) -> None:
    """Refer an apprentice onto an FE College course (dual enrolment)."""
    require(actor, "admission.view")
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Referral dashboard", partial(fe_applications_cli.dashboard, SOURCE_SYSTEM)),
    ]
    if actor.can("admission.decide"):
        entries.append(("Refer an apprentice to FE College",
                        partial(fe_applications_cli.new_referral, SOURCE_SYSTEM)))
    prompts.run_menu("FE College Referrals", entries)


def training_requests(actor: Actor) -> None:
    """Send an apprentice on a training provider's short course."""
    require(actor, "admission.view")
    from education_system.systems.apprenticeships.application.apprentices import (
        apprentice_service,
    )

    def apprentices() -> list[tuple[str, str]]:
        return [(str(s.apprentice.apprentice_id),
                 f"{s.apprentice.given_name} {s.apprentice.family_name} "
                 f"({s.apprentice.status})")
                for s in apprentice_service.list_apprentices(actor)
                if s.apprentice.status not in ("Withdrawn", "Transferred")]

    training_provider_requests_cli.menu(
        SOURCE_SYSTEM, apprentices,
        can_request=actor.can("admission.decide"), referrer=actor.name)


def learner_journey(actor: Actor) -> None:
    require(actor, "admission.view")
    journey_cli.prompt_and_show(SOURCE_SYSTEM)
