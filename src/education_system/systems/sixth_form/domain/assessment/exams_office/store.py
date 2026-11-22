"""Shared plumbing for the exams-office modules.

Every exams-office table lives in the sixth-form database beside
``exam_entries`` (all the ``SIXTH_FORM_*_DB`` constants point at one
file), so connections come from :mod:`exam_entries` and this package
never opens SQLite itself. Tables are created on first use, never at
import.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from typing import Any, Iterable

from education_system.systems.sixth_form.domain.assessment.exam_entries import (
    exam_entries as _entries,
)

logger = logging.getLogger(__name__)

IntegrityError = _entries.IntegrityError

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]([01]\d|2[0-3]):[0-5]\d$")

_READY: set[str] = set()


class ValidationError(ValueError):
    """Raised for invalid exams-office input."""


def connect():
    """A connection to the sixth-form database (Row factory, FKs on)."""
    return _entries._connect()


def ensure(key: str, schema: str, *, columns: dict[str, dict[str, str]] | None = None,
           after: Iterable[Any] = ()) -> None:
    """Create *schema* once per process, then add any missing *columns*.

    ``columns`` maps table -> {column: "TYPE ..."}; each is added with
    ``ALTER TABLE ... ADD COLUMN`` only when ``PRAGMA table_info`` lacks
    it. ``after`` holds init functions of tables this schema references.
    """
    if key in _READY:
        return
    _entries.init_db()
    for init in after:
        init()
    with connect() as conn:
        conn.executescript(schema)
        for table, cols in (columns or {}).items():
            add_missing_columns(conn, table, cols)
        conn.commit()
    _READY.add(key)
    logger.debug("Exams-office schema %s ready", key)


def table_columns(conn, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def add_missing_columns(conn, table: str, cols: dict[str, str]) -> list[str]:
    """Add each column in *cols* that *table* lacks; returns those added."""
    have = table_columns(conn, table)
    added: list[str] = []
    for name, decl in cols.items():
        if name not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
            added.append(name)
    if added:
        logger.info("Added column(s) %s to %s", ", ".join(added), table)
    return added


# ── Small validators ────────────────────────────────────────────────

def text(value: Any, label: str, *, limit: int = 200,
         required: bool = False) -> str | None:
    s = value.strip() if isinstance(value, str) else ("" if value is None else str(value).strip())
    if not s:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if len(s) > limit:
        raise ValidationError(f"{label} must be {limit} characters or fewer")
    return s


def date(value: Any, label: str, *, required: bool = False) -> str | None:
    s = text(value, label, limit=10, required=required)
    if s is None:
        return None
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def time(value: Any, label: str, *, required: bool = False) -> str | None:
    s = text(value, label, limit=5, required=required)
    if s is None:
        return None
    if len(s) == 4 and s[1] == ":":
        s = "0" + s
    if not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM (24-hour)")
    return s


def datetime_(value: Any, label: str, *, required: bool = False) -> str | None:
    """``YYYY-MM-DD HH:MM`` (a bare date means 00:00 that day)."""
    s = text(value, label, limit=16, required=required)
    if s is None:
        return None
    if _DATE_RE.match(s):
        s = f"{s} 00:00"
    s = s.replace("T", " ")
    if not _DATETIME_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD HH:MM")
    return s


def integer(value: Any, label: str, *, lo: int | None = None,
            hi: int | None = None, required: bool = False) -> int | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number") from None
    if lo is not None and n < lo:
        raise ValidationError(f"{label} must be at least {lo}")
    if hi is not None and n > hi:
        raise ValidationError(f"{label} must be at most {hi}")
    return n


def money(value: Any, label: str) -> float | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        f = float(str(value).strip().lstrip("£"))
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if f < 0 or f > 100000:
        raise ValidationError(f"{label} must be between 0 and 100,000")
    return round(f, 2)


def choice(value: Any, label: str, options: Iterable[str], *,
           default: str | None = None, required: bool = True) -> str | None:
    opts = tuple(options)
    s = text(value, label, limit=120) or default
    if s is None:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    for o in opts:
        if s.lower() == o.lower():
            return o
    raise ValidationError(f"{label} must be one of: {', '.join(opts)}")


def flag(value: Any) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in ("1", "y", "yes", "true", "on") else 0
    return 1 if value else 0


def season_year(season: Any, year: Any) -> tuple[str, int]:
    s = choice(season, "Season", _entries.SEASONS, default=_entries.DEFAULT_SEASON)
    y = integer(year, "Year", lo=2000, hi=2099, required=True)
    return s, y  # type: ignore[return-value]


def board(value: Any, *, required: bool = True) -> str | None:
    from education_system.systems.sixth_form.domain.assessment.exams_office.boards import (
        EXAM_BOARDS, normalise_board,
    )
    s = text(value, "Exam board", limit=40)
    if s is None:
        if required:
            raise ValidationError("Exam board is required")
        return None
    b = normalise_board(s)
    if b is None:
        raise ValidationError(f"Exam board must be one of: {', '.join(EXAM_BOARDS)}")
    return b


def student(value: Any) -> str:
    sid = text(value, "Student ID", limit=40, required=True)
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid  # type: ignore[return-value]


# ── Context ─────────────────────────────────────────────────────────

def today() -> str:
    return _dt.date.today().isoformat()


def now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def actor(explicit: str | None = None) -> str | None:
    """Who is doing this: *explicit*, else the signed-in principal."""
    if explicit and explicit.strip():
        return explicit.strip()
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or None
    except Exception:
        return None


def add_months(iso: str, months: int) -> str:
    """*iso* date plus *months* calendar months (day clamped to month end)."""
    d = _dt.date.fromisoformat(iso)
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    for day in (d.day, 30, 29, 28):
        try:
            return _dt.date(y, m, day).isoformat()
        except ValueError:
            continue
    return _dt.date(y, m, 28).isoformat()


def add_minutes(hhmm: str, minutes: int) -> str:
    h, m = hhmm.split(":")
    total = int(h) * 60 + int(m) + int(minutes)
    return f"{(total // 60) % 24:02d}:{total % 60:02d}"


def minutes_between(start: str, end: str) -> int:
    sh, sm = start.split(":")
    eh, em = end.split(":")
    return (int(eh) * 60 + int(em)) - (int(sh) * 60 + int(sm))


def student_names() -> dict[str, str]:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    return {s.student_id: s.full_name for s in _students.list_students()}
