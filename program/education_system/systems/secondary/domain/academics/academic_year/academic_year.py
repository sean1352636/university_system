"""Academic Year — calendar metadata for the Sixth Form System.

Three related tables:

* ``academic_years``     — one row per year (e.g. "2025/26"). One row
                            may be flagged ``is_current`` at a time.
* ``academic_terms``     — terms within a year (Autumn / Spring / Summer
                            or finer-grained half-terms).
* ``academic_breaks``    — holidays, half-term breaks, INSET days, bank
                            holidays — anything that is *not* a teaching
                            day inside a year's overall range.

The aim is a single source of truth for "what year are we in?", "what
term is today in?", and "how many teaching days are in this window?" —
all of which are useful for attendance %, reports, and timetable
scheduling.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system.systems.secondary.infrastructure import paths
from education_system.systems.secondary.domain.academics.academic_year import (
    academic_year as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.ACADEMIC_YEAR_DB

YEAR_STATUSES: tuple[str, ...] = ("Planning", "Active", "Archived")
DEFAULT_YEAR_STATUS: str = "Planning"

TERM_NAMES: tuple[str, ...] = (
    "Autumn", "Autumn 1", "Autumn 2",
    "Spring", "Spring 1", "Spring 2",
    "Summer", "Summer 1", "Summer 2",
)
DEFAULT_TERM_NAME: str = "Autumn"

BREAK_TYPES: tuple[str, ...] = (
    "Holiday", "Half-Term", "INSET", "Bank Holiday",
    "Exam Period", "Other",
)
DEFAULT_BREAK_TYPE: str = "Holiday"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_YEAR_NAME_RE = re.compile(r"^[A-Za-z0-9 /._\-]{2,32}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS academic_years (
    year_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    start_date   TEXT NOT NULL,
    end_date     TEXT NOT NULL,
    is_current   INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'Planning',
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS academic_terms (
    term_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    year_id      INTEGER NOT NULL,
    name         TEXT NOT NULL,
    start_date   TEXT NOT NULL,
    end_date     TEXT NOT NULL,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (year_id) REFERENCES academic_years(year_id)
        ON DELETE CASCADE,
    UNIQUE (year_id, name)
);

CREATE TABLE IF NOT EXISTS academic_breaks (
    break_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    year_id      INTEGER NOT NULL,
    name         TEXT NOT NULL,
    start_date   TEXT NOT NULL,
    end_date     TEXT NOT NULL,
    type         TEXT NOT NULL DEFAULT 'Holiday',
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (year_id) REFERENCES academic_years(year_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ay_current   ON academic_years(is_current);
CREATE INDEX IF NOT EXISTS idx_at_year      ON academic_terms(year_id);
CREATE INDEX IF NOT EXISTS idx_ab_year      ON academic_breaks(year_id);
CREATE INDEX IF NOT EXISTS idx_ab_start     ON academic_breaks(start_date);
"""


@dataclass
class AcademicYear:
    year_id: int
    name: str
    start_date: str
    end_date: str
    is_current: bool
    status: str
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def day_count(self) -> int:
        try:
            sd = _dt.date.fromisoformat(self.start_date)
            ed = _dt.date.fromisoformat(self.end_date)
            return max(0, (ed - sd).days) + 1
        except Exception:
            return 0


@dataclass
class Term:
    term_id: int
    year_id: int
    name: str
    start_date: str
    end_date: str
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def day_count(self) -> int:
        try:
            sd = _dt.date.fromisoformat(self.start_date)
            ed = _dt.date.fromisoformat(self.end_date)
            return max(0, (ed - sd).days) + 1
        except Exception:
            return 0


@dataclass
class Break:
    break_id: int
    year_id: int
    name: str
    start_date: str
    end_date: str
    type: str
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def day_count(self) -> int:
        try:
            sd = _dt.date.fromisoformat(self.start_date)
            ed = _dt.date.fromisoformat(self.end_date)
            return max(0, (ed - sd).days) + 1
        except Exception:
            return 0


@dataclass
class YearSummary:
    year: AcademicYear
    terms: list[Term] = field(default_factory=list)
    breaks: list[Break] = field(default_factory=list)
    teaching_days: int = 0
    non_teaching_days: int = 0
    weekend_days: int = 0


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Academic-year schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_year(r: sqlite3.Row) -> AcademicYear:
    return AcademicYear(
        year_id=r["year_id"], name=r["name"],
        start_date=r["start_date"], end_date=r["end_date"],
        is_current=bool(r["is_current"]),
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_term(r: sqlite3.Row) -> Term:
    return Term(
        term_id=r["term_id"], year_id=r["year_id"], name=r["name"],
        start_date=r["start_date"], end_date=r["end_date"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_break(r: sqlite3.Row) -> Break:
    return Break(
        break_id=r["break_id"], year_id=r["year_id"], name=r["name"],
        start_date=r["start_date"], end_date=r["end_date"],
        type=r["type"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_year_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = _require(payload.get("name"), "Name").strip()
    if not _YEAR_NAME_RE.match(name):
        raise ValidationError(
            "Name must be 2–32 chars (letters, digits, space, / . _ -)")
    out["name"] = name
    out["start_date"] = _validate_date(payload.get("start_date"),
                                          "Start date")
    out["end_date"] = _validate_date(payload.get("end_date"),
                                        "End date")
    if out["end_date"] <= out["start_date"]:
        raise ValidationError("End date must be after start date")
    status = (payload.get("status") or DEFAULT_YEAR_STATUS).strip()
    if status not in YEAR_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(YEAR_STATUSES)}")
    out["status"] = status
    out["is_current"] = bool(payload.get("is_current"))
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


def _validate_term_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    year_id = payload.get("year_id")
    if year_id in (None, ""):
        raise ValidationError("Year is required")
    try:
        out["year_id"] = int(year_id)
    except (TypeError, ValueError):
        raise ValidationError("Year id must be a number") from None
    year = get_year(out["year_id"])
    if year is None:
        raise ValidationError(f"No academic year #{out['year_id']}")

    name = _require(payload.get("name"), "Term name").strip()
    if name not in TERM_NAMES:
        # Accept custom names too — schools differ — but enforce length.
        if not (1 <= len(name) <= 32):
            raise ValidationError("Term name must be 1–32 chars")
    out["name"] = name

    out["start_date"] = _validate_date(payload.get("start_date"),
                                          "Start date")
    out["end_date"] = _validate_date(payload.get("end_date"),
                                        "End date")
    if out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")
    if (out["start_date"] < year.start_date
            or out["end_date"] > year.end_date):
        raise ValidationError(
            f"Term must lie within the year "
            f"({year.start_date} → {year.end_date})")
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


def _validate_break_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    year_id = payload.get("year_id")
    if year_id in (None, ""):
        raise ValidationError("Year is required")
    try:
        out["year_id"] = int(year_id)
    except (TypeError, ValueError):
        raise ValidationError("Year id must be a number") from None
    year = get_year(out["year_id"])
    if year is None:
        raise ValidationError(f"No academic year #{out['year_id']}")

    out["name"] = _require(payload.get("name"), "Name").strip()

    out["start_date"] = _validate_date(payload.get("start_date"),
                                          "Start date")
    out["end_date"] = _validate_date(payload.get("end_date"),
                                        "End date")
    if out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")
    if (out["start_date"] < year.start_date
            or out["end_date"] > year.end_date):
        raise ValidationError(
            f"Break must lie within the year "
            f"({year.start_date} → {year.end_date})")

    btype = (payload.get("type") or DEFAULT_BREAK_TYPE).strip()
    if btype not in BREAK_TYPES:
        raise ValidationError(
            f"Type must be one of: {', '.join(BREAK_TYPES)}")
    out["type"] = btype
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


# ── Year CRUD ─────────────────────────────────────────────────────

def create_year(payload: dict[str, Any]) -> AcademicYear:
    init_db()
    p = _validate_year_payload(payload)
    with _connect() as conn:
        # Name uniqueness pre-check (sqlite IntegrityError -> friendlier
        # message)
        if conn.execute(
                "SELECT 1 FROM academic_years WHERE name = ?",
                (p["name"],)).fetchone():
            raise ValidationError(
                f"An academic year named {p['name']!r} already exists")
        if p["is_current"]:
            conn.execute("UPDATE academic_years SET is_current = 0")
        cur = conn.execute(
            """INSERT INTO academic_years
                   (name, start_date, end_date, is_current,
                    status, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["name"], p["start_date"], p["end_date"],
             1 if p["is_current"] else 0, p["status"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_year(new_id)
    assert out is not None
    logger.info("Created academic year #%d %r (%s..%s, current=%s)",
                new_id, p["name"], p["start_date"], p["end_date"],
                p["is_current"])
    return out


def get_year(year_id: int) -> AcademicYear | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_years WHERE year_id = ?",
            (year_id,),
        ).fetchone()
        return _row_year(r) if r else None


def get_year_by_name(name: str) -> AcademicYear | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_years WHERE name = ?",
            (name.strip(),),
        ).fetchone()
        return _row_year(r) if r else None


def list_years(*, status: str | None = None) -> list[AcademicYear]:
    init_db()
    clauses, args = [], []
    if status:
        if status not in YEAR_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(YEAR_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_years {where} "
           "ORDER BY start_date DESC, year_id DESC")
    with _connect() as conn:
        return [_row_year(r) for r in conn.execute(sql, args).fetchall()]


def current_year() -> AcademicYear | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_years WHERE is_current = 1 "
            "LIMIT 1").fetchone()
        return _row_year(r) if r else None


def update_year(year_id: int, payload: dict[str, Any]) -> AcademicYear:
    init_db()
    existing = get_year(year_id)
    if existing is None:
        raise ValidationError(f"No academic year #{year_id}")
    merged = {
        "name":        payload.get("name", existing.name),
        "start_date":  payload.get("start_date", existing.start_date),
        "end_date":    payload.get("end_date", existing.end_date),
        "status":      payload.get("status", existing.status),
        "is_current":  payload.get("is_current", existing.is_current),
        "notes":       payload.get("notes", existing.notes),
    }
    p = _validate_year_payload(merged)
    with _connect() as conn:
        # Name uniqueness — allow same name on the same row.
        row = conn.execute(
            "SELECT year_id FROM academic_years WHERE name = ?",
            (p["name"],)).fetchone()
        if row and row["year_id"] != year_id:
            raise ValidationError(
                f"An academic year named {p['name']!r} already exists")
        if p["is_current"]:
            conn.execute(
                "UPDATE academic_years SET is_current = 0 "
                "WHERE year_id <> ?", (year_id,))
        conn.execute(
            """UPDATE academic_years SET
                   name = ?, start_date = ?, end_date = ?,
                   is_current = ?, status = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE year_id = ?""",
            (p["name"], p["start_date"], p["end_date"],
             1 if p["is_current"] else 0, p["status"], p["notes"],
             year_id),
        )
        conn.commit()
    out = get_year(year_id)
    assert out is not None
    logger.info("Updated academic year #%d %r (current=%s, status=%s)",
                year_id, out.name, out.is_current, out.status)
    return out


def set_current(year_id: int) -> AcademicYear:
    init_db()
    if get_year(year_id) is None:
        raise ValidationError(f"No academic year #{year_id}")
    with _connect() as conn:
        conn.execute("UPDATE academic_years SET is_current = 0")
        conn.execute(
            "UPDATE academic_years SET is_current = 1, "
            "updated_at = datetime('now') WHERE year_id = ?",
            (year_id,))
        conn.commit()
    out = get_year(year_id)
    assert out is not None
    logger.info("Set current academic year → #%d %r", year_id, out.name)
    return out


def clear_current() -> None:
    init_db()
    with _connect() as conn:
        conn.execute("UPDATE academic_years SET is_current = 0")
        conn.commit()
    logger.info("Cleared current academic year")


def delete_year(year_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM academic_years WHERE year_id = ?",
            (year_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted academic year #%d (cascade: terms+breaks)",
                        year_id)
            return True
        return False


# ── Term CRUD ─────────────────────────────────────────────────────

def create_term(payload: dict[str, Any]) -> Term:
    init_db()
    p = _validate_term_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM academic_terms "
                "WHERE year_id = ? AND name = ?",
                (p["year_id"], p["name"])).fetchone():
            raise ValidationError(
                f"Term {p['name']!r} already exists for this year")
        cur = conn.execute(
            """INSERT INTO academic_terms
                   (year_id, name, start_date, end_date, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["year_id"], p["name"], p["start_date"], p["end_date"],
             p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_term(new_id)
    assert out is not None
    logger.info("Created term #%d %r in year #%d", new_id, p["name"],
                p["year_id"])
    return out


def get_term(term_id: int) -> Term | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_terms WHERE term_id = ?",
            (term_id,)).fetchone()
        return _row_term(r) if r else None


def list_terms(*, year_id: int | None = None) -> list[Term]:
    init_db()
    clauses, args = [], []
    if year_id is not None:
        clauses.append("year_id = ?")
        args.append(year_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_terms {where} "
           "ORDER BY start_date ASC, term_id ASC")
    with _connect() as conn:
        return [_row_term(r) for r in conn.execute(sql, args).fetchall()]


def update_term(term_id: int, payload: dict[str, Any]) -> Term:
    init_db()
    existing = get_term(term_id)
    if existing is None:
        raise ValidationError(f"No term #{term_id}")
    merged = {
        "year_id":    existing.year_id,
        "name":       payload.get("name", existing.name),
        "start_date": payload.get("start_date", existing.start_date),
        "end_date":   payload.get("end_date", existing.end_date),
        "notes":      payload.get("notes", existing.notes),
    }
    p = _validate_term_payload(merged)
    with _connect() as conn:
        row = conn.execute(
            "SELECT term_id FROM academic_terms "
            "WHERE year_id = ? AND name = ?",
            (p["year_id"], p["name"])).fetchone()
        if row and row["term_id"] != term_id:
            raise ValidationError(
                f"Term {p['name']!r} already exists for this year")
        conn.execute(
            """UPDATE academic_terms SET
                   name = ?, start_date = ?, end_date = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE term_id = ?""",
            (p["name"], p["start_date"], p["end_date"], p["notes"],
             term_id),
        )
        conn.commit()
    out = get_term(term_id)
    assert out is not None
    logger.info("Updated term #%d %r", term_id, out.name)
    return out


def delete_term(term_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM academic_terms WHERE term_id = ?",
            (term_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted term #%d", term_id)
            return True
        return False


# ── Break CRUD ────────────────────────────────────────────────────

def create_break(payload: dict[str, Any]) -> Break:
    init_db()
    p = _validate_break_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO academic_breaks
                   (year_id, name, start_date, end_date, type, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["year_id"], p["name"], p["start_date"], p["end_date"],
             p["type"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_break(new_id)
    assert out is not None
    logger.info("Created break #%d %r (%s) in year #%d",
                new_id, p["name"], p["type"], p["year_id"])
    return out


def get_break(break_id: int) -> Break | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_breaks WHERE break_id = ?",
            (break_id,)).fetchone()
        return _row_break(r) if r else None


def list_breaks(*, year_id: int | None = None,
                 type: str | None = None) -> list[Break]:
    init_db()
    clauses, args = [], []
    if year_id is not None:
        clauses.append("year_id = ?")
        args.append(year_id)
    if type:
        if type not in BREAK_TYPES:
            raise ValidationError(
                f"Type must be one of: {', '.join(BREAK_TYPES)}")
        clauses.append("type = ?")
        args.append(type)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_breaks {where} "
           "ORDER BY start_date ASC, break_id ASC")
    with _connect() as conn:
        return [_row_break(r) for r in conn.execute(sql, args).fetchall()]


def update_break(break_id: int, payload: dict[str, Any]) -> Break:
    init_db()
    existing = get_break(break_id)
    if existing is None:
        raise ValidationError(f"No break #{break_id}")
    merged = {
        "year_id":    existing.year_id,
        "name":       payload.get("name", existing.name),
        "start_date": payload.get("start_date", existing.start_date),
        "end_date":   payload.get("end_date", existing.end_date),
        "type":       payload.get("type", existing.type),
        "notes":      payload.get("notes", existing.notes),
    }
    p = _validate_break_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE academic_breaks SET
                   name = ?, start_date = ?, end_date = ?,
                   type = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE break_id = ?""",
            (p["name"], p["start_date"], p["end_date"],
             p["type"], p["notes"], break_id),
        )
        conn.commit()
    out = get_break(break_id)
    assert out is not None
    logger.info("Updated break #%d %r", break_id, out.name)
    return out


def delete_break(break_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM academic_breaks WHERE break_id = ?",
            (break_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted break #%d", break_id)
            return True
        return False


# ── Lookups ───────────────────────────────────────────────────────

def find_term_on(year_id: int, date_iso: str) -> Term | None:
    """Return the term containing ``date_iso`` (if any)."""
    init_db()
    s = _validate_date(date_iso, "Date")
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_terms "
            "WHERE year_id = ? AND start_date <= ? AND end_date >= ? "
            "ORDER BY start_date ASC LIMIT 1",
            (year_id, s, s)).fetchone()
        return _row_term(r) if r else None


def is_break(year_id: int, date_iso: str) -> Break | None:
    """Return the break covering ``date_iso`` (if any)."""
    init_db()
    s = _validate_date(date_iso, "Date")
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_breaks "
            "WHERE year_id = ? AND start_date <= ? AND end_date >= ? "
            "ORDER BY start_date ASC LIMIT 1",
            (year_id, s, s)).fetchone()
        return _row_break(r) if r else None


def teaching_days_in(
    year_id: int, *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> int:
    """Count Mon–Fri days within [from, to] that aren't covered by a
    break row. Defaults to the full year span."""
    year = get_year(year_id)
    if year is None:
        raise ValidationError(f"No academic year #{year_id}")
    df = _validate_date(date_from or year.start_date, "From")
    dt = _validate_date(date_to or year.end_date, "To")
    if dt < df:
        return 0
    breaks = list_breaks(year_id=year_id)
    break_ranges = [(b.start_date, b.end_date) for b in breaks]

    def _in_break(d_iso: str) -> bool:
        return any(s <= d_iso <= e for (s, e) in break_ranges)

    start = _dt.date.fromisoformat(df)
    end = _dt.date.fromisoformat(dt)
    days = 0
    cur = start
    one = _dt.timedelta(days=1)
    while cur <= end:
        # Mon=0..Fri=4; exclude Sat=5 / Sun=6
        if cur.weekday() < 5 and not _in_break(cur.isoformat()):
            days += 1
        cur += one
    return days


def year_summary(year_id: int) -> YearSummary:
    year = get_year(year_id)
    if year is None:
        raise ValidationError(f"No academic year #{year_id}")
    terms = list_terms(year_id=year_id)
    breaks = list_breaks(year_id=year_id)

    teaching = teaching_days_in(year_id)
    # Total Mon-Fri count, regardless of breaks
    start = _dt.date.fromisoformat(year.start_date)
    end = _dt.date.fromisoformat(year.end_date)
    weekdays = 0
    weekends = 0
    cur, one = start, _dt.timedelta(days=1)
    while cur <= end:
        if cur.weekday() < 5:
            weekdays += 1
        else:
            weekends += 1
        cur += one
    non_teaching = weekdays - teaching

    return YearSummary(
        year=year,
        terms=terms,
        breaks=breaks,
        teaching_days=teaching,
        non_teaching_days=non_teaching,
        weekend_days=weekends,
    )
