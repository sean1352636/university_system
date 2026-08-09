from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True, slots=True)
class DemographicFilters:
    course: str | None = None
    gender: str | None = None
    nationality: str | None = None
    age_min: int | None = None
    age_max: int | None = None

@dataclass(slots=True)
class ProcessedDemographics:
    total: int = 0
    categories: dict[str, dict[str, int]] = field(default_factory=dict)
    raw_rows: list[dict[str, Any]] = field(default_factory=list)
