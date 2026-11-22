"""Date helpers for SEND deadlines (all calendar-based, as the statutory ones are)."""

from __future__ import annotations

from datetime import date, timedelta


def today() -> date:
    return date.today()


def add_weeks(d: date, weeks: int) -> date:
    return d + timedelta(weeks=weeks)


def add_months(d: date, months: int) -> date:
    """Same day *months* later, clamped to the month's last day."""
    month = d.month - 1 + months
    year, month = d.year + month // 12, month % 12 + 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise AssertionError("unreachable")


def age_on(dob: date, on: date) -> int:
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def uk(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""
