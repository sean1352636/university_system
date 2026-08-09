from datetime import datetime

def appointment_is_in_future(scheduled_at: datetime, *, now: datetime | None = None) -> bool:
    return scheduled_at > (now or datetime.now())
