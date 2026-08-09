from dataclasses import dataclass
from datetime import date, timedelta

@dataclass(frozen=True, slots=True)
class RecurrenceRule:
    frequency: str
    occurrences: int

def generate_occurrences(start: date, rule: RecurrenceRule) -> tuple[date, ...]:
    days = {"daily": 1, "weekly": 7, "fortnightly": 14}.get(rule.frequency.lower())
    if days is None:
        raise ValueError("unsupported recurrence frequency")
    return tuple(start + timedelta(days=days * i) for i in range(rule.occurrences))
