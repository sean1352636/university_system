"""Domain package: admissions stages."""

from __future__ import annotations

from education_system.systems.apprenticeships.domain.admissions.stages import (  # noqa: F401
    AdmissionStage,
    require_move,
    validate_stage,
)

__all__ = ["AdmissionStage", "require_move", "validate_stage"]
