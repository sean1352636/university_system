from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

AUDIT_EVENT_VERSION = 1

@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_type: str
    occurred_at: datetime
    principal_id: int | None
    payload: dict[str, Any]
    version: Literal[1] = 1
