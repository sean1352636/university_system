from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    user_id: int
    username: str
    roles: tuple[str, ...] = ()
    attributes: dict[str, Any] | None = None

@dataclass(frozen=True, slots=True)
class Session:
    session_id: str
    principal: AuthenticatedPrincipal
    created_at: datetime
    last_activity: datetime
