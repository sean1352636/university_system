from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    success: bool
    user: dict[str, Any] | None = None
    error: str | None = None
    requires_mfa: bool = False

@dataclass(frozen=True, slots=True)
class ChallengeResult:
    success: bool
    challenge_id: str | None = None
    error: str | None = None
