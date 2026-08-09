from datetime import datetime, timedelta

def lockout_expires(*, locked_at: datetime, minutes: int) -> datetime:
    return locked_at + timedelta(minutes=minutes)

def is_locked(*, locked_at: datetime, minutes: int, now: datetime | None = None) -> bool:
    return (now or datetime.now()) < lockout_expires(locked_at=locked_at, minutes=minutes)
