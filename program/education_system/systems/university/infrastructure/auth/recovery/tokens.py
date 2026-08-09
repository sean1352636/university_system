from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True, slots=True)
class RecoveryToken:
    token_hash: str
    expires_at: datetime
    used_at: datetime | None = None

    def is_valid(self, *, now: datetime | None = None) -> bool:
        return self.used_at is None and (now or datetime.now()) < self.expires_at
