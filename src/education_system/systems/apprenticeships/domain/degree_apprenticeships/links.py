"""Links between a degree apprentice and their university registration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DegreeApprenticeshipProgramme:
    apprenticeship_programme_id: int
    university_degree_program_id: int
    credits_required: float | None
    integration_type: str
    active: bool


@dataclass(frozen=True)
class DegreeApprenticeshipLink:
    link_id: int
    apprentice_id: int
    journey_id: str
    university_student_id: str
    university_degree_program_id: int
    status: str
    reconciliation_state: str
    linked_at: str | None
    last_academic_sync_at: str | None
