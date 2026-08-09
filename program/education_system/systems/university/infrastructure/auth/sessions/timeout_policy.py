from datetime import datetime, timedelta

def has_timed_out(last_activity: datetime | None, timeout_minutes: int, *, now: datetime | None = None) -> bool:
    return last_activity is not None and (now or datetime.now()) - last_activity > timedelta(minutes=timeout_minutes)
