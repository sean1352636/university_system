from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class EmergencyContact:
    student_id: int
    name: str
    relationship: str
    phone: str
    email: str | None = None
