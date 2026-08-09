from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class OperationResult:
    success: bool
    message: str = ""
    value: Any = None

@dataclass(frozen=True, slots=True)
class RegisterForEventCommand:
    event_id: int
    student_id: int
