from dataclasses import dataclass
from typing import Any

@dataclass(slots=True)
class HealthPortalContext:
    auth: Any
