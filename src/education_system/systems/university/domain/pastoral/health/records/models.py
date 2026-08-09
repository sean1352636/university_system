from dataclasses import dataclass, field
from typing import Any

@dataclass(slots=True)
class HealthRecord:
    student_id: int
    blood_type: str | None = None
    allergies: str | None = None
    medications: str | None = None
    conditions: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
