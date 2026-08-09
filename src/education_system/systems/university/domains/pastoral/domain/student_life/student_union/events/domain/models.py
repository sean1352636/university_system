from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class Event:
    event_id: int | None
    name: str
    event_date: date
    start_time: time
    end_time: time
    capacity: int | None = None

@dataclass(frozen=True, slots=True)
class Registration:
    event_id: int
    student_id: int
    status: str = "registered"

@dataclass(frozen=True, slots=True)
class Ticket:
    event_id: int
    ticket_type: str
    price: Decimal

@dataclass(frozen=True, slots=True)
class Attendance:
    event_id: int
    student_id: int
    checked_in: bool = False
