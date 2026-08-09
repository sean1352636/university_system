from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class AuthConfiguration:
    session_timeout_minutes: int = 30
    max_login_attempts: int = 5
    lockout_minutes: int = 15
