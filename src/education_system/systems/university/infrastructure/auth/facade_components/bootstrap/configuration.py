from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class AuthConfiguration:
    session_timeout_minutes: int = 30
    max_attempts: int = 5
