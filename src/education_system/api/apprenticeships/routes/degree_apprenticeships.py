"""Framework-neutral degree-apprenticeship API handlers.

The web host supplies the authenticated :class:`Actor`; these functions keep
HTTP adapters thin and ensure API, CLI and GUI all use the same service gates.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from education_system.systems.apprenticeships.application.programmes import (
    degree_apprenticeship_service as service,
)
from education_system.systems.apprenticeships.application.security.access import Actor


def map_programme(actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    result = service.map_programme(
        actor,
        int(payload["apprenticeship_programme_id"]),
        int(payload["university_degree_program_id"]),
        credits_required=(float(payload["credits_required"])
                          if payload.get("credits_required") is not None else None),
        integration_type=str(payload.get("integration_type") or "Integrated"),
        active=bool(payload.get("active", True)),
    )
    return asdict(result)


def link_learner(actor: Actor, apprentice_id: int,
                 payload: dict[str, Any]) -> dict[str, Any]:
    result = service.link_learner(
        actor, int(apprentice_id),
        journey_id=str(payload["journey_id"]),
        university_student_id=str(payload["university_student_id"]),
        institution_id=payload.get("institution_id"),
        start_date=payload.get("start_date"),
    )
    return asdict(result)


def academic_progress(actor: Actor, apprentice_id: int) -> dict[str, Any]:
    return service.academic_progress(actor, int(apprentice_id))


def reconciliation(actor: Actor, *, stale_after_days: int = 7) -> list[dict[str, Any]]:
    return service.reconciliation_dashboard(
        actor, stale_after_days=int(stale_after_days),
    )
