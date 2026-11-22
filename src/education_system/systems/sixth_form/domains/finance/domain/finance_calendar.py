"""Date arithmetic shared by the sixth-form finance modules.

Small, dependency-free helpers for the questions every finance screen
asks: which academic year is a date in, when does that year start and
end, how old is a learner on 31 August (the date 16-19 funding and fee
eligibility are measured on), and what is "one calendar month later"
(the UK GDPR response deadline, and a monthly bursary instalment).

Academic years are written ``"2026/27"`` throughout the sixth form; a
bare ``"2026"`` or ``"2026-27"`` is accepted and normalised.
"""

from __future__ import annotations

import calendar
import datetime as _dt
import re

_YEAR_RE = re.compile(r"^\s*(\d{4})\s*(?:[/\-]\s*(\d{2}|\d{4}))?\s*$")

#: Month and day the academic year starts on (1 September).
YEAR_START: tuple[int, int] = (9, 1)
#: Month and day the teaching year ends on (31 July). Bursary schedules
#: stop here; the funding year itself runs to 31 August.
TEACHING_END: tuple[int, int] = (7, 31)


def _as_date(value: str | _dt.date | None) -> _dt.date:
    if value is None:
        return _dt.date.today()
    if isinstance(value, _dt.date):
        return value
    return _dt.date.fromisoformat(str(value).strip())


def academic_year_for(on: str | _dt.date | None = None) -> str:
    """The academic year a date falls in, as ``"2026/27"``."""
    d = _as_date(on)
    start = d.year if (d.month, d.day) >= YEAR_START else d.year - 1
    return f"{start}/{str(start + 1)[-2:]}"


def normalise_year(value: str | None) -> str:
    """``"2026"``, ``"2026-27"``, ``"2026/2027"`` -> ``"2026/27"``.

    An empty value means the current academic year.
    """
    if value is None or not str(value).strip():
        return academic_year_for()
    m = _YEAR_RE.match(str(value))
    if not m:
        raise ValueError(
            f"Academic year must look like 2026/27 (got {value!r})")
    start = int(m.group(1))
    if m.group(2):
        end = int(m.group(2)[-2:])
        if end != (start + 1) % 100:
            raise ValueError(
                f"Academic year {value!r} must span consecutive years")
    return f"{start}/{str(start + 1)[-2:]}"


def year_bounds(year: str | None) -> tuple[str, str]:
    """First and last day of an academic year (1 Sep .. 31 Aug)."""
    norm = normalise_year(year)
    start = int(norm[:4])
    return (_dt.date(start, *YEAR_START).isoformat(),
            _dt.date(start + 1, 8, 31).isoformat())


def teaching_end(year: str | None) -> str:
    """31 July of an academic year — the default end of a bursary."""
    start = int(normalise_year(year)[:4])
    return _dt.date(start + 1, *TEACHING_END).isoformat()


def age_on_31_august(date_of_birth: str | _dt.date, year: str | None) -> int:
    """A learner's age on 31 August at the start of an academic year.

    This is the date ESFA 16-19 funding and fee eligibility use: a
    learner who is 18 on 31 August 2026 is a 16-18 learner for the whole
    of 2026/27, even after their 19th birthday in October.
    """
    dob = _as_date(date_of_birth)
    start = int(normalise_year(year)[:4])
    ref = _dt.date(start, 8, 31)
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))


def add_months(value: str | _dt.date, months: int) -> str:
    """Add calendar months, clamping to the month end (31 Jan + 1 -> 28/29 Feb)."""
    d = _as_date(value)
    index = d.month - 1 + months
    year = d.year + index // 12
    month = index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return _dt.date(year, month, day).isoformat()


def month_bounds(month: str) -> tuple[str, str]:
    """``"2026-10"`` -> (``"2026-10-01"``, ``"2026-10-31"``)."""
    m = re.match(r"^\s*(\d{4})-(\d{2})\s*$", str(month or ""))
    if not m:
        raise ValueError(f"Month must be YYYY-MM (got {month!r})")
    year, mon = int(m.group(1)), int(m.group(2))
    if not 1 <= mon <= 12:
        raise ValueError(f"Month must be YYYY-MM (got {month!r})")
    last = calendar.monthrange(year, mon)[1]
    return (_dt.date(year, mon, 1).isoformat(),
            _dt.date(year, mon, last).isoformat())


def weekdays_between(date_from: str, date_to: str) -> list[str]:
    """Every Monday-Friday between two dates, inclusive."""
    d = _as_date(date_from)
    end = _as_date(date_to)
    out: list[str] = []
    while d <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += _dt.timedelta(days=1)
    return out
