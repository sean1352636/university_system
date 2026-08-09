from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    success: bool
    user: dict | None = None
    error: str | None = None
