from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True, slots=True)
class Vaccination:
    student_id: int
    vaccine_name: str
    vaccination_date: date
    next_due_date: date | None = None
