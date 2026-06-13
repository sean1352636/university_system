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
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.academics.academic_year import (
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


TERM_KINDS: tuple[str, ...] = (
    "Term", "Half-Term", "Mock-Exam Week", "Study Leave")
DEFAULT_TERM_KIND: str = "Term"

BREAK_AM_PM: tuple[str, ...] = ("FULL", "AM", "PM")
DEFAULT_BREAK_AM_PM: str = "FULL"

EVENT_KINDS: tuple[str, ...] = (
    "General", "Open Evening", "Parents Evening",
    "Results Day", "Enrolment", "Exam", "Trip")
DEFAULT_EVENT_KIND: str = "General"


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
    deleted_at: str | None = None
    campus_id: str | None = None
    approved_at: str | None = None
    approved_by: str | None = None

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
    deleted_at: str | None = None
    kind: str = DEFAULT_TERM_KIND

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
    deleted_at: str | None = None
    am_pm: str = DEFAULT_BREAK_AM_PM


@dataclass
class YearGroup:
    group_id: int
    year_id: int
    label: str
    notes: str | None
    created_at: str


@dataclass
class CalendarEvent:
    event_id: int
    year_id: int
    name: str
    kind: str
    date: str
    end_date: str | None
    notes: str | None
    deleted_at: str | None
    created_at: str
    updated_at: str

    @property
    def day_count(self) -> int:
        try:
            sd = _dt.date.fromisoformat(self.date)
            ed = _dt.date.fromisoformat(self.end_date or self.date)
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

# ── Schema migrations ────────────────────────────────────────────
#
# Each migration is (version, sql). On init_db() we run any whose
# version is greater than what's stored in `schema_version`. New
# columns must use ``ALTER TABLE`` + defaults so existing rows stay
# valid. Order matters — never edit a past migration; add a new one.

_MIGRATIONS: list[tuple[int, str]] = [
    (1, """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL
        );
        INSERT INTO schema_version(version, applied_at)
            VALUES (1, datetime('now'));
    """),
    (2, """
        -- Soft delete on every primary table.
        ALTER TABLE academic_years  ADD COLUMN deleted_at TEXT;
        ALTER TABLE academic_terms  ADD COLUMN deleted_at TEXT;
        ALTER TABLE academic_breaks ADD COLUMN deleted_at TEXT;
    """),
    (3, """
        -- Half-day breaks: 'FULL' (default), 'AM', 'PM'.
        ALTER TABLE academic_breaks
            ADD COLUMN am_pm TEXT NOT NULL DEFAULT 'FULL';
    """),
    (4, """
        -- Term kind: Term / Half-Term / Mock-Exam Week / Study Leave.
        ALTER TABLE academic_terms
            ADD COLUMN kind TEXT NOT NULL DEFAULT 'Term';
    """),
    (5, """
        CREATE TABLE IF NOT EXISTS academic_year_groups (
            group_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            year_id    INTEGER NOT NULL,
            label      TEXT NOT NULL,  -- 'Y12', 'Y13'
            notes      TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (year_id) REFERENCES academic_years(year_id)
                ON DELETE CASCADE,
            UNIQUE (year_id, label)
        );
    """),
    (6, """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_break_window
            ON academic_breaks(year_id, start_date, end_date, type, am_pm)
            WHERE deleted_at IS NULL;
    """),
    (7, """
        CREATE TABLE IF NOT EXISTS academic_audit_log (
            log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            entity      TEXT NOT NULL,    -- 'year' | 'term' | 'break' | 'event'
            entity_id   INTEGER NOT NULL,
            action      TEXT NOT NULL,    -- 'create' | 'update' | 'delete' | 'restore'
            actor       TEXT,
            old_json    TEXT,
            new_json    TEXT,
            at          TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_audit_entity
            ON academic_audit_log(entity, entity_id);
    """),
    (8, """
        CREATE TABLE IF NOT EXISTS academic_events (
            event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            year_id      INTEGER NOT NULL,
            name         TEXT NOT NULL,
            kind         TEXT NOT NULL DEFAULT 'General',
            date         TEXT NOT NULL,
            end_date     TEXT,            -- nullable: single-day if null
            notes        TEXT,
            deleted_at   TEXT,
            created_at   TEXT DEFAULT (datetime('now')),
            updated_at   TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (year_id) REFERENCES academic_years(year_id)
                ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_event_year
            ON academic_events(year_id);
        CREATE INDEX IF NOT EXISTS idx_event_date
            ON academic_events(date);
    """),
    (9, """
        -- Multi-campus and sign-off workflow scaffolding.
        ALTER TABLE academic_years ADD COLUMN campus_id TEXT;
        ALTER TABLE academic_years
            ADD COLUMN approved_at TEXT;
        ALTER TABLE academic_years
            ADD COLUMN approved_by TEXT;
    """),
]

# Optional: caller can stash the current user here so audit rows
# get attributed. Defaults to None (CLI / batch jobs).
CURRENT_ACTOR: str | None = None

# RBAC scaffolding (item 45).
#
# Default behaviour is permissive — callers may opt in by setting
# ENFORCE_RBAC = True and stashing the role in CURRENT_ACTOR_ROLE.
# The API blueprint flips ENFORCE_RBAC on at request time once a
# JWT has been validated.
ENFORCE_RBAC: bool = False
CURRENT_ACTOR_ROLE: str | None = None
READ_ONLY_ROLES: set[str] = {"reception", "student", "parent"}


class PermissionDenied(PermissionError):
    pass


def _check_write() -> None:
    if not ENFORCE_RBAC:
        return
    role = (CURRENT_ACTOR_ROLE or "").lower()
    if role in READ_ONLY_ROLES:
        raise PermissionDenied(
            f"Role {role!r} is read-only and cannot write to the "
            f"academic year.")


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Run any migrations newer than the stored version."""
    try:
        row = conn.execute(
            "SELECT MAX(version) AS v FROM schema_version").fetchone()
        current = int(row["v"]) if row and row["v"] is not None else 0
    except sqlite3.OperationalError:
        current = 0
    for ver, sql in _MIGRATIONS:
        if ver <= current:
            continue
        try:
            conn.executescript(sql)
            if ver > 1:  # v1's script seeds the row itself
                conn.execute(
                    "INSERT INTO schema_version(version, applied_at) "
                    "VALUES (?, datetime('now'))", (ver,))
            conn.commit()
            logger.info("Applied academic-year migration v%d", ver)
        except sqlite3.OperationalError as e:
            # Idempotent recovery: ALTER TABLE will fail if the column
            # already exists. We still want to record the version.
            if "duplicate column name" in str(e).lower():
                conn.execute(
                    "INSERT INTO schema_version(version, applied_at) "
                    "VALUES (?, datetime('now'))", (ver,))
                conn.commit()
                logger.warning(
                    "Migration v%d already partially applied (%s)",
                    ver, e)
            else:
                raise


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        _apply_migrations(conn)
    logger.debug("Academic-year schema ready at %s", DB_PATH)

    _DB_READY = True


# ── Audit log helpers ────────────────────────────────────────────

def _audit(conn: sqlite3.Connection, *, entity: str, entity_id: int,
            action: str, old: Any | None = None,
            new: Any | None = None) -> None:
    """Best-effort audit write. Never raises into callers."""
    import json
    try:
        conn.execute(
            "INSERT INTO academic_audit_log "
            "(entity, entity_id, action, actor, old_json, new_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (entity, entity_id, action, CURRENT_ACTOR,
             json.dumps(old, default=str) if old is not None else None,
             json.dumps(new, default=str) if new is not None else None))
    except sqlite3.OperationalError as e:
        logger.warning("Audit insert failed: %s", e)


def audit_log(*, entity: str | None = None,
               entity_id: int | None = None,
               limit: int = 200) -> list[dict[str, Any]]:
    """Return recent audit rows newest first. Filter optional."""
    init_db()
    clauses, args = [], []
    if entity:
        clauses.append("entity = ?")
        args.append(entity)
    if entity_id is not None:
        clauses.append("entity_id = ?")
        args.append(entity_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_audit_log {where} "
           f"ORDER BY log_id DESC LIMIT {int(limit)}")
    with _connect() as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def _safe(r: sqlite3.Row, key: str, default=None):
    try:
        return r[key]
    except (IndexError, KeyError):
        return default


def _row_year(r: sqlite3.Row) -> AcademicYear:
    return AcademicYear(
        year_id=r["year_id"], name=r["name"],
        start_date=r["start_date"], end_date=r["end_date"],
        is_current=bool(r["is_current"]),
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        deleted_at=_safe(r, "deleted_at"),
        campus_id=_safe(r, "campus_id"),
        approved_at=_safe(r, "approved_at"),
        approved_by=_safe(r, "approved_by"),
    )


def _row_term(r: sqlite3.Row) -> Term:
    return Term(
        term_id=r["term_id"], year_id=r["year_id"], name=r["name"],
        start_date=r["start_date"], end_date=r["end_date"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        deleted_at=_safe(r, "deleted_at"),
        kind=_safe(r, "kind", DEFAULT_TERM_KIND) or DEFAULT_TERM_KIND,
    )


def _row_break(r: sqlite3.Row) -> Break:
    return Break(
        break_id=r["break_id"], year_id=r["year_id"], name=r["name"],
        start_date=r["start_date"], end_date=r["end_date"],
        type=r["type"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        deleted_at=_safe(r, "deleted_at"),
        am_pm=_safe(r, "am_pm", DEFAULT_BREAK_AM_PM) or DEFAULT_BREAK_AM_PM,
    )


def _row_event(r: sqlite3.Row) -> CalendarEvent:
    return CalendarEvent(
        event_id=r["event_id"], year_id=r["year_id"], name=r["name"],
        kind=r["kind"], date=r["date"],
        end_date=_safe(r, "end_date"), notes=r["notes"],
        deleted_at=_safe(r, "deleted_at"),
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _year_to_dict(y: AcademicYear) -> dict:
    return {
        "year_id": y.year_id, "name": y.name,
        "start_date": y.start_date, "end_date": y.end_date,
        "is_current": y.is_current, "status": y.status,
        "notes": y.notes, "campus_id": y.campus_id,
    }


def _term_to_dict(t: Term) -> dict:
    return {
        "term_id": t.term_id, "year_id": t.year_id, "name": t.name,
        "start_date": t.start_date, "end_date": t.end_date,
        "kind": t.kind, "notes": t.notes,
    }


def _break_to_dict(b: Break) -> dict:
    return {
        "break_id": b.break_id, "year_id": b.year_id, "name": b.name,
        "start_date": b.start_date, "end_date": b.end_date,
        "type": b.type, "am_pm": b.am_pm, "notes": b.notes,
    }


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
    if out["is_current"] and out["status"] == "Archived":
        raise ValidationError(
            "A year cannot be both Archived and current.")
    out["notes"] = (payload.get("notes") or "").strip() or None
    cid = payload.get("campus_id")
    out["campus_id"] = (cid.strip() if isinstance(cid, str) and cid.strip()
                          else None)
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
    kind = (payload.get("kind") or DEFAULT_TERM_KIND).strip()
    if kind not in TERM_KINDS:
        raise ValidationError(
            f"Term kind must be one of: {', '.join(TERM_KINDS)}")
    out["kind"] = kind

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
    am_pm = (payload.get("am_pm") or DEFAULT_BREAK_AM_PM).strip().upper()
    if am_pm not in BREAK_AM_PM:
        raise ValidationError(
            f"am_pm must be one of: {', '.join(BREAK_AM_PM)}")
    out["am_pm"] = am_pm
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


# ── Year CRUD ─────────────────────────────────────────────────────

def create_year(payload: dict[str, Any]) -> AcademicYear:
    init_db()
    _check_write()
    p = _validate_year_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM academic_years "
                "WHERE name = ? AND deleted_at IS NULL",
                (p["name"],)).fetchone():
            raise ValidationError(
                f"An academic year named {p['name']!r} already exists")
        if p["is_current"]:
            conn.execute(
                "UPDATE academic_years SET is_current = 0 "
                "WHERE deleted_at IS NULL")
        cur = conn.execute(
            """INSERT INTO academic_years
                   (name, start_date, end_date, is_current,
                    status, notes, campus_id,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["name"], p["start_date"], p["end_date"],
             1 if p["is_current"] else 0, p["status"], p["notes"],
             p.get("campus_id")),
        )
        new_id = cur.lastrowid
        _audit(conn, entity="year", entity_id=new_id,
                 action="create", new=p)
        conn.commit()
    out = get_year(new_id)
    assert out is not None
    logger.info("Created academic year #%d %r (%s..%s, current=%s)",
                new_id, p["name"], p["start_date"], p["end_date"],
                p["is_current"])
    return out


def get_year(year_id: int, *,
              include_deleted: bool = False) -> AcademicYear | None:
    init_db()
    extra = "" if include_deleted else " AND deleted_at IS NULL"
    with _connect() as conn:
        r = conn.execute(
            f"SELECT * FROM academic_years "
            f"WHERE year_id = ?{extra}", (year_id,)).fetchone()
        return _row_year(r) if r else None


def get_year_by_name(name: str) -> AcademicYear | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_years "
            "WHERE name = ? AND deleted_at IS NULL",
            (name.strip(),),
        ).fetchone()
        return _row_year(r) if r else None


def list_years(*, status: str | None = None,
                campus_id: str | None = None,
                include_deleted: bool = False) -> list[AcademicYear]:
    init_db()
    clauses, args = [], []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if status:
        if status not in YEAR_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(YEAR_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if campus_id is not None:
        clauses.append("campus_id IS ?")
        args.append(campus_id or None)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_years {where} "
           "ORDER BY start_date DESC, year_id DESC")
    with _connect() as conn:
        return [_row_year(r) for r in conn.execute(sql, args).fetchall()]


def current_year(*, campus_id: str | None = None
                  ) -> AcademicYear | None:
    init_db()
    args = []
    extra = ""
    if campus_id is not None:
        extra = " AND campus_id IS ?"
        args.append(campus_id or None)
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_years "
            "WHERE is_current = 1 AND deleted_at IS NULL"
            + extra + " LIMIT 1", args).fetchone()
        return _row_year(r) if r else None


def update_year(year_id: int, payload: dict[str, Any]) -> AcademicYear:
    init_db()
    _check_write()
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
        "campus_id":   payload.get("campus_id", existing.campus_id),
    }
    p = _validate_year_payload(merged)
    with _connect() as conn:
        row = conn.execute(
            "SELECT year_id FROM academic_years "
            "WHERE name = ? AND deleted_at IS NULL",
            (p["name"],)).fetchone()
        if row and row["year_id"] != year_id:
            raise ValidationError(
                f"An academic year named {p['name']!r} already exists")
        if p["is_current"]:
            conn.execute(
                "UPDATE academic_years SET is_current = 0 "
                "WHERE year_id <> ? AND deleted_at IS NULL",
                (year_id,))
        conn.execute(
            """UPDATE academic_years SET
                   name = ?, start_date = ?, end_date = ?,
                   is_current = ?, status = ?, notes = ?,
                   campus_id = ?, updated_at = datetime('now')
               WHERE year_id = ?""",
            (p["name"], p["start_date"], p["end_date"],
             1 if p["is_current"] else 0, p["status"], p["notes"],
             p.get("campus_id"), year_id),
        )
        _audit(conn, entity="year", entity_id=year_id,
                 action="update", old=_year_to_dict(existing), new=p)
        conn.commit()
    out = get_year(year_id)
    assert out is not None
    logger.info("Updated academic year #%d %r (current=%s, status=%s)",
                year_id, out.name, out.is_current, out.status)
    return out


def approve_year(year_id: int, *, approver: str) -> AcademicYear:
    """Stamp a year as approved (sign-off workflow). Status must be
    'Planning' or 'Active'."""
    init_db()
    _check_write()
    existing = get_year(year_id)
    if existing is None:
        raise ValidationError(f"No academic year #{year_id}")
    if existing.status == "Archived":
        raise ValidationError("Cannot approve an archived year")
    with _connect() as conn:
        conn.execute(
            "UPDATE academic_years SET "
            "approved_at = datetime('now'), approved_by = ?, "
            "updated_at = datetime('now') WHERE year_id = ?",
            (approver, year_id))
        _audit(conn, entity="year", entity_id=year_id,
                 action="approve", new={"approved_by": approver})
        conn.commit()
    out = get_year(year_id)
    assert out is not None
    return out


def unapprove_year(year_id: int) -> AcademicYear:
    init_db()
    _check_write()
    if get_year(year_id) is None:
        raise ValidationError(f"No academic year #{year_id}")
    with _connect() as conn:
        conn.execute(
            "UPDATE academic_years SET "
            "approved_at = NULL, approved_by = NULL, "
            "updated_at = datetime('now') WHERE year_id = ?",
            (year_id,))
        _audit(conn, entity="year", entity_id=year_id,
                 action="unapprove")
        conn.commit()
    out = get_year(year_id)
    assert out is not None
    return out


def restore_year(year_id: int) -> AcademicYear:
    init_db()
    _check_write()
    with _connect() as conn:
        conn.execute(
            "UPDATE academic_years SET deleted_at = NULL, "
            "updated_at = datetime('now') WHERE year_id = ?",
            (year_id,))
        _audit(conn, entity="year", entity_id=year_id,
                 action="restore")
        conn.commit()
    out = get_year(year_id, include_deleted=True)
    if out is None:
        raise ValidationError(f"No academic year #{year_id}")
    return out


def set_current(year_id: int) -> AcademicYear:
    init_db()
    _check_write()
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
    _check_write()
    with _connect() as conn:
        conn.execute("UPDATE academic_years SET is_current = 0")
        conn.commit()
    logger.info("Cleared current academic year")


def delete_year(year_id: int, *, hard: bool = False) -> bool:
    """Soft-delete by default — sets ``deleted_at`` on the year and
    cascades the same to its terms/breaks. Pass ``hard=True`` to
    physically delete (the original FK cascade applies)."""
    init_db()
    _check_write()
    existing = get_year(year_id, include_deleted=True)
    if existing is None:
        return False
    with _connect() as conn:
        if hard:
            cur = conn.execute(
                "DELETE FROM academic_years WHERE year_id = ?",
                (year_id,))
        else:
            now_sql = "datetime('now')"
            cur = conn.execute(
                f"UPDATE academic_years SET deleted_at = {now_sql}, "
                f"is_current = 0, updated_at = {now_sql} "
                f"WHERE year_id = ?", (year_id,))
            conn.execute(
                f"UPDATE academic_terms SET deleted_at = {now_sql}, "
                f"updated_at = {now_sql} "
                f"WHERE year_id = ? AND deleted_at IS NULL",
                (year_id,))
            conn.execute(
                f"UPDATE academic_breaks SET deleted_at = {now_sql}, "
                f"updated_at = {now_sql} "
                f"WHERE year_id = ? AND deleted_at IS NULL",
                (year_id,))
        if cur.rowcount:
            _audit(conn, entity="year", entity_id=year_id,
                     action="hard-delete" if hard else "delete",
                     old=_year_to_dict(existing))
            conn.commit()
            logger.info(
                "%s academic year #%d (cascade: terms+breaks)",
                "Hard-deleted" if hard else "Soft-deleted", year_id)
            return True
        return False


# ── Term CRUD ─────────────────────────────────────────────────────

def create_term(payload: dict[str, Any]) -> Term:
    init_db()
    _check_write()
    p = _validate_term_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM academic_terms "
                "WHERE year_id = ? AND name = ? AND deleted_at IS NULL",
                (p["year_id"], p["name"])).fetchone():
            raise ValidationError(
                f"Term {p['name']!r} already exists for this year")
        cur = conn.execute(
            """INSERT INTO academic_terms
                   (year_id, name, start_date, end_date, notes, kind,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["year_id"], p["name"], p["start_date"], p["end_date"],
             p["notes"], p["kind"]),
        )
        new_id = cur.lastrowid
        _audit(conn, entity="term", entity_id=new_id,
                 action="create", new=p)
        conn.commit()
    out = get_term(new_id)
    assert out is not None
    logger.info("Created term #%d %r in year #%d", new_id, p["name"],
                p["year_id"])
    return out


def get_term(term_id: int, *,
              include_deleted: bool = False) -> Term | None:
    init_db()
    extra = "" if include_deleted else " AND deleted_at IS NULL"
    with _connect() as conn:
        r = conn.execute(
            f"SELECT * FROM academic_terms "
            f"WHERE term_id = ?{extra}", (term_id,)).fetchone()
        return _row_term(r) if r else None


def list_terms(*, year_id: int | None = None,
                kind: str | None = None,
                include_deleted: bool = False) -> list[Term]:
    init_db()
    clauses, args = [], []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if year_id is not None:
        clauses.append("year_id = ?")
        args.append(year_id)
    if kind is not None:
        if kind not in TERM_KINDS:
            raise ValidationError(
                f"Term kind must be one of: {', '.join(TERM_KINDS)}")
        clauses.append("kind = ?")
        args.append(kind)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_terms {where} "
           "ORDER BY start_date ASC, term_id ASC")
    with _connect() as conn:
        return [_row_term(r) for r in conn.execute(sql, args).fetchall()]


def update_term(term_id: int, payload: dict[str, Any]) -> Term:
    init_db()
    _check_write()
    existing = get_term(term_id)
    if existing is None:
        raise ValidationError(f"No term #{term_id}")
    merged = {
        "year_id":    existing.year_id,
        "name":       payload.get("name", existing.name),
        "start_date": payload.get("start_date", existing.start_date),
        "end_date":   payload.get("end_date", existing.end_date),
        "kind":       payload.get("kind", existing.kind),
        "notes":      payload.get("notes", existing.notes),
    }
    p = _validate_term_payload(merged)
    with _connect() as conn:
        row = conn.execute(
            "SELECT term_id FROM academic_terms "
            "WHERE year_id = ? AND name = ? AND deleted_at IS NULL",
            (p["year_id"], p["name"])).fetchone()
        if row and row["term_id"] != term_id:
            raise ValidationError(
                f"Term {p['name']!r} already exists for this year")
        conn.execute(
            """UPDATE academic_terms SET
                   name = ?, start_date = ?, end_date = ?,
                   kind = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE term_id = ?""",
            (p["name"], p["start_date"], p["end_date"], p["kind"],
             p["notes"], term_id),
        )
        _audit(conn, entity="term", entity_id=term_id,
                 action="update", old=_term_to_dict(existing), new=p)
        conn.commit()
    out = get_term(term_id)
    assert out is not None
    logger.info("Updated term #%d %r", term_id, out.name)
    return out


def delete_term(term_id: int, *, hard: bool = False) -> bool:
    init_db()
    _check_write()
    existing = get_term(term_id, include_deleted=True)
    if existing is None:
        return False
    with _connect() as conn:
        if hard:
            cur = conn.execute(
                "DELETE FROM academic_terms WHERE term_id = ?",
                (term_id,))
        else:
            cur = conn.execute(
                "UPDATE academic_terms SET "
                "deleted_at = datetime('now'), "
                "updated_at = datetime('now') WHERE term_id = ?",
                (term_id,))
        if cur.rowcount:
            _audit(conn, entity="term", entity_id=term_id,
                     action="hard-delete" if hard else "delete",
                     old=_term_to_dict(existing))
            conn.commit()
            logger.info("%s term #%d",
                          "Hard-deleted" if hard else "Soft-deleted",
                          term_id)
            return True
        return False


def restore_term(term_id: int) -> Term:
    init_db()
    _check_write()
    with _connect() as conn:
        conn.execute(
            "UPDATE academic_terms SET deleted_at = NULL, "
            "updated_at = datetime('now') WHERE term_id = ?",
            (term_id,))
        _audit(conn, entity="term", entity_id=term_id,
                 action="restore")
        conn.commit()
    out = get_term(term_id, include_deleted=True)
    if out is None:
        raise ValidationError(f"No term #{term_id}")
    return out


# ── Break CRUD ────────────────────────────────────────────────────

def create_break(payload: dict[str, Any]) -> Break:
    init_db()
    _check_write()
    p = _validate_break_payload(payload)
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO academic_breaks
                       (year_id, name, start_date, end_date, type, am_pm,
                        notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))""",
                (p["year_id"], p["name"], p["start_date"], p["end_date"],
                 p["type"], p["am_pm"], p["notes"]),
            )
        except sqlite3.IntegrityError as e:
            raise ValidationError(
                f"Duplicate break in this window: {e}") from None
        new_id = cur.lastrowid
        _audit(conn, entity="break", entity_id=new_id,
                 action="create", new=p)
        conn.commit()
    out = get_break(new_id)
    assert out is not None
    logger.info("Created break #%d %r (%s) in year #%d",
                new_id, p["name"], p["type"], p["year_id"])
    return out


def get_break(break_id: int, *,
               include_deleted: bool = False) -> Break | None:
    init_db()
    extra = "" if include_deleted else " AND deleted_at IS NULL"
    with _connect() as conn:
        r = conn.execute(
            f"SELECT * FROM academic_breaks "
            f"WHERE break_id = ?{extra}", (break_id,)).fetchone()
        return _row_break(r) if r else None


def list_breaks(*, year_id: int | None = None,
                 type: str | None = None,
                 am_pm: str | None = None,
                 include_deleted: bool = False) -> list[Break]:
    init_db()
    clauses, args = [], []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if year_id is not None:
        clauses.append("year_id = ?")
        args.append(year_id)
    if type:
        if type not in BREAK_TYPES:
            raise ValidationError(
                f"Type must be one of: {', '.join(BREAK_TYPES)}")
        clauses.append("type = ?")
        args.append(type)
    if am_pm:
        if am_pm not in BREAK_AM_PM:
            raise ValidationError(
                f"am_pm must be one of: {', '.join(BREAK_AM_PM)}")
        clauses.append("am_pm = ?")
        args.append(am_pm)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_breaks {where} "
           "ORDER BY start_date ASC, break_id ASC")
    with _connect() as conn:
        return [_row_break(r) for r in conn.execute(sql, args).fetchall()]


def update_break(break_id: int, payload: dict[str, Any]) -> Break:
    init_db()
    _check_write()
    existing = get_break(break_id)
    if existing is None:
        raise ValidationError(f"No break #{break_id}")
    merged = {
        "year_id":    existing.year_id,
        "name":       payload.get("name", existing.name),
        "start_date": payload.get("start_date", existing.start_date),
        "end_date":   payload.get("end_date", existing.end_date),
        "type":       payload.get("type", existing.type),
        "am_pm":      payload.get("am_pm", existing.am_pm),
        "notes":      payload.get("notes", existing.notes),
    }
    p = _validate_break_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE academic_breaks SET
                   name = ?, start_date = ?, end_date = ?,
                   type = ?, am_pm = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE break_id = ?""",
            (p["name"], p["start_date"], p["end_date"],
             p["type"], p["am_pm"], p["notes"], break_id),
        )
        _audit(conn, entity="break", entity_id=break_id,
                 action="update", old=_break_to_dict(existing), new=p)
        conn.commit()
    out = get_break(break_id)
    assert out is not None
    logger.info("Updated break #%d %r", break_id, out.name)
    return out


def delete_break(break_id: int, *, hard: bool = False) -> bool:
    init_db()
    _check_write()
    existing = get_break(break_id, include_deleted=True)
    if existing is None:
        return False
    with _connect() as conn:
        if hard:
            cur = conn.execute(
                "DELETE FROM academic_breaks WHERE break_id = ?",
                (break_id,))
        else:
            cur = conn.execute(
                "UPDATE academic_breaks SET "
                "deleted_at = datetime('now'), "
                "updated_at = datetime('now') WHERE break_id = ?",
                (break_id,))
        if cur.rowcount:
            _audit(conn, entity="break", entity_id=break_id,
                     action="hard-delete" if hard else "delete",
                     old=_break_to_dict(existing))
            conn.commit()
            return True
        return False


def restore_break(break_id: int) -> Break:
    init_db()
    _check_write()
    with _connect() as conn:
        conn.execute(
            "UPDATE academic_breaks SET deleted_at = NULL, "
            "updated_at = datetime('now') WHERE break_id = ?",
            (break_id,))
        _audit(conn, entity="break", entity_id=break_id,
                 action="restore")
        conn.commit()
    out = get_break(break_id, include_deleted=True)
    if out is None:
        raise ValidationError(f"No break #{break_id}")
    return out


# ── Year groups (Y12/Y13) ─────────────────────────────────────────

def create_year_group(year_id: int, label: str,
                        notes: str | None = None) -> YearGroup:
    init_db()
    _check_write()
    if get_year(year_id) is None:
        raise ValidationError(f"No academic year #{year_id}")
    label = (label or "").strip()
    if not label or len(label) > 16:
        raise ValidationError("Year-group label must be 1-16 chars")
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO academic_year_groups (year_id, label, notes) "
                "VALUES (?, ?, ?)", (year_id, label, notes))
            new_id = cur.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValidationError(
                f"Year group {label!r} already exists for this year"
                ) from None
    return get_year_group(new_id)


def get_year_group(group_id: int) -> YearGroup | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_year_groups WHERE group_id = ?",
            (group_id,)).fetchone()
        if r is None:
            return None
        return YearGroup(group_id=r["group_id"], year_id=r["year_id"],
                          label=r["label"], notes=r["notes"],
                          created_at=r["created_at"])


def list_year_groups(year_id: int) -> list[YearGroup]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM academic_year_groups "
            "WHERE year_id = ? ORDER BY label",
            (year_id,)).fetchall()
    return [YearGroup(group_id=r["group_id"], year_id=r["year_id"],
                       label=r["label"], notes=r["notes"],
                       created_at=r["created_at"]) for r in rows]


def delete_year_group(group_id: int) -> bool:
    init_db()
    _check_write()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM academic_year_groups WHERE group_id = ?",
            (group_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Events ────────────────────────────────────────────────────────

def create_event(payload: dict[str, Any]) -> CalendarEvent:
    init_db()
    _check_write()
    yid = int(payload["year_id"])
    year = get_year(yid)
    if year is None:
        raise ValidationError(f"No academic year #{yid}")
    name = _require(payload.get("name"), "Name").strip()
    kind = (payload.get("kind") or DEFAULT_EVENT_KIND).strip()
    if kind not in EVENT_KINDS:
        raise ValidationError(
            f"Event kind must be one of: {', '.join(EVENT_KINDS)}")
    s = _validate_date(payload.get("date"), "Date")
    e = _validate_date(payload.get("end_date"), "End date",
                          required=False)
    if e is not None and e < s:
        raise ValidationError("End date cannot be before start date")
    if s < year.start_date or s > year.end_date:
        raise ValidationError(
            f"Event must fall inside the year "
            f"({year.start_date} → {year.end_date})")
    notes = (payload.get("notes") or "").strip() or None
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO academic_events "
            "(year_id, name, kind, date, end_date, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (yid, name, kind, s, e, notes))
        new_id = cur.lastrowid
        _audit(conn, entity="event", entity_id=new_id,
                 action="create",
                 new={"year_id": yid, "name": name, "kind": kind,
                       "date": s, "end_date": e})
        conn.commit()
    out = get_event(new_id)
    assert out is not None
    return out


def get_event(event_id: int) -> CalendarEvent | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_events "
            "WHERE event_id = ? AND deleted_at IS NULL",
            (event_id,)).fetchone()
        return _row_event(r) if r else None


def list_events(*, year_id: int | None = None,
                 kind: str | None = None) -> list[CalendarEvent]:
    init_db()
    clauses = ["deleted_at IS NULL"]
    args: list[Any] = []
    if year_id is not None:
        clauses.append("year_id = ?")
        args.append(year_id)
    if kind is not None:
        if kind not in EVENT_KINDS:
            raise ValidationError(
                f"Event kind must be one of: {', '.join(EVENT_KINDS)}")
        clauses.append("kind = ?")
        args.append(kind)
    where = " AND ".join(clauses)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM academic_events WHERE {where} "
            "ORDER BY date ASC, event_id ASC", args).fetchall()
    return [_row_event(r) for r in rows]


def delete_event(event_id: int, *, hard: bool = False) -> bool:
    init_db()
    _check_write()
    existing = get_event(event_id)
    if existing is None:
        return False
    with _connect() as conn:
        if hard:
            cur = conn.execute(
                "DELETE FROM academic_events WHERE event_id = ?",
                (event_id,))
        else:
            cur = conn.execute(
                "UPDATE academic_events SET "
                "deleted_at = datetime('now') WHERE event_id = ?",
                (event_id,))
        if cur.rowcount:
            _audit(conn, entity="event", entity_id=event_id,
                     action="hard-delete" if hard else "delete")
            conn.commit()
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
