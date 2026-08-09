from dataclasses import dataclass
from datetime import date
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class Member:
    name: str
    email: str | None = None
    phone: str | None = None

@dataclass(frozen=True, slots=True)
class Donation:
    amount: Decimal
    donation_type: str
    donated_on: date

@dataclass(frozen=True, slots=True)
class ChurchEvent:
    name: str
    event_date: date
