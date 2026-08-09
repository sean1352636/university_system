from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True, slots=True)
class Appointment:
    student_id: int
    appointment_type: str
    scheduled_at: datetime
    reason: str = ""
    status: str = "scheduled"
