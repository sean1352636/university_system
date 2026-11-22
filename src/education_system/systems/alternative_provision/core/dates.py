"""Date helpers (calendar-based)."""

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


def next_weekday(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def school_day(start: date, n: int) -> date:
    """The *n*-th school day counting *start* as day 1 (weekdays only; term
    dates and bank holidays aren't known here, so this is the earliest date)."""
    d = next_weekday(start)
    for _ in range(n - 1):
        d = next_weekday(d + timedelta(days=1))
    return d


def weekdays_between(start: date, end: date) -> int:
    """Weekdays from *start* to *end* inclusive."""
    if end < start:
        return 0
    days = (end - start).days + 1
    full, rest = divmod(days, 7)
    count = full * 5
    for i in range(rest):
        if (start + timedelta(days=full * 7 + i)).weekday() < 5:
            count += 1
    return count


def school_year_start(on: date) -> date:
    return date(on.year if on.month >= 9 else on.year - 1, 9, 1)
