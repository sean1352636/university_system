from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class HealthCommandResult:
    success: bool
    message: str = ""
    data: Any = None
