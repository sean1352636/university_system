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
from education_system import paths
from education_system.systems.sixth_form.domain.academics.academic_year import (
    academic_year as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ACADEMIC_YEAR_DB

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

# Sentinel telling "no campus filter at all" apart from "campus is
# explicitly NULL". ``campus_id=None`` used to mean both, so a caller
# asking for the un-sited year silently got every campus's.
class _Unset:
    def __repr__(self) -> str:      # pragma: no cover - debug aid
        return "<unset>"


UNSET: Any = _Unset()

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
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

# Kinds that default to *not* being taught. Study leave is on the
# calendar but students aren't in, so it must not inflate the
# attendance denominator. Callers can override per term.
NON_TEACHING_KINDS: frozenset[str] = frozenset({"Study Leave"})

# Statutory INSET allowance (England: 5 days a year).
DEFAULT_INSET_ALLOWANCE: int = 5
MAX_INSET_ALLOWANCE: int = 20

NOTE_CATEGORIES: tuple[str, ...] = (
    "General", "Policy", "Decision", "Risk", "Consultation")
DEFAULT_NOTE_CATEGORY: str = "General"

BREAK_AM_PM: tuple[str, ...] = ("FULL", "AM", "PM")
DEFAULT_BREAK_AM_PM: str = "FULL"

EVENT_KINDS: tuple[str, ...] = (
    "General", "Open Evening", "Parents Evening",
    "Results Day", "Enrolment", "Exam", "Trip", "Deadline",
    # Sixth-form specific additions.
    "Interview", "Work Experience", "Enrichment",
    "Mock Results", "UCAS")
DEFAULT_EVENT_KIND: str = "General"

# ── Timetable cycle (Week A / Week B) ─────────────────────────────
#
# ``academic_years.cycle_weeks`` is how many weeks the timetable
# repeats over — 1 for a plain weekly timetable, 2 for the usual
# A/B fortnight, 3 for the rare three-week cycle. The cycle is
# counted from ``cycle_anchor``, which is the Monday that Week A
# starts on; it defaults to the Monday of the year's start week.
MAX_CYCLE_WEEKS: int = 4
DEFAULT_CYCLE_WEEKS: int = 1
CYCLE_LABELS: tuple[str, ...] = ("A", "B", "C", "D")

# ── Periods (the shape of a teaching day) ─────────────────────────
#
# ``weekday`` is 0=Mon … 6=Sun. ``cycle_week`` is NULL for "every
# week" or 1..cycle_weeks to pin a period to one week of the cycle.
WEEKDAY_NAMES: tuple[str, ...] = (
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday")

# ── Recurring events ──────────────────────────────────────────────
REPEAT_RULES: tuple[str, ...] = ("DAILY", "WEEKLY", "MONTHLY")
# Hard cap so a bad ``repeat_until`` can't fan out unboundedly.
MAX_OCCURRENCES: int = 400


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# Which database files have had their schema brought up to date.
# Keyed on the path, not a bare bool — tests (and the multi-campus
# work) repoint ``DB_PATH`` at a fresh file, and a global flag meant
# the new file was never initialised.
_DB_READY: set[str] = set()

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
    (10, """
        -- Timetable cycle: 1 = weekly, 2 = Week A/B fortnight, …
        -- cycle_anchor is the Monday Week A starts on; NULL means
        -- "the Monday of the week the year starts in".
        ALTER TABLE academic_years
            ADD COLUMN cycle_weeks INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE academic_years ADD COLUMN cycle_anchor TEXT;
    """),
    (11, """
        -- The shape of a teaching day: periods per weekday, optionally
        -- pinned to one week of the timetable cycle.
        CREATE TABLE IF NOT EXISTS academic_periods (
            period_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            year_id     INTEGER NOT NULL,
            name        TEXT NOT NULL,     -- 'P1', 'Registration', 'Lunch'
            weekday     INTEGER NOT NULL,  -- 0=Mon .. 6=Sun
            start_time  TEXT NOT NULL,     -- 'HH:MM'
            end_time    TEXT NOT NULL,     -- 'HH:MM'
            cycle_week  INTEGER,           -- NULL = every week
            is_teaching INTEGER NOT NULL DEFAULT 1,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            notes       TEXT,
            deleted_at  TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (year_id) REFERENCES academic_years(year_id)
                ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_period_year
            ON academic_periods(year_id, weekday);
    """),
    (12, """
        -- Per-year-group calendars. NULL = applies to the whole
        -- college; a label (matching academic_year_groups.label)
        -- scopes the row to just that group, so Y13 study leave
        -- doesn't blank out Y12's teaching days.
        ALTER TABLE academic_terms  ADD COLUMN group_label TEXT;
        ALTER TABLE academic_breaks ADD COLUMN group_label TEXT;
        ALTER TABLE academic_events ADD COLUMN group_label TEXT;
    """),
    (13, """
        -- Event detail: who runs it, where, how many, how often.
        ALTER TABLE academic_events ADD COLUMN owner TEXT;
        ALTER TABLE academic_events ADD COLUMN department TEXT;
        ALTER TABLE academic_events ADD COLUMN location TEXT;
        ALTER TABLE academic_events ADD COLUMN capacity INTEGER;
        ALTER TABLE academic_events ADD COLUMN repeat_rule TEXT;
        ALTER TABLE academic_events
            ADD COLUMN repeat_interval INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE academic_events ADD COLUMN repeat_until TEXT;
    """),
    (14, """
        -- Terms are now range-checked for overlap on create/update;
        -- these indexes make the check (and the gap finder) cheap.
        CREATE INDEX IF NOT EXISTS idx_at_start
            ON academic_terms(year_id, start_date);
        CREATE INDEX IF NOT EXISTS idx_at_group
            ON academic_terms(year_id, group_label);
        CREATE INDEX IF NOT EXISTS idx_ab_group
            ON academic_breaks(year_id, group_label);
        CREATE INDEX IF NOT EXISTS idx_ae_group
            ON academic_events(year_id, group_label);
    """),
    (15, """
        -- Not every term is taught: Study Leave is timetabled but
        -- students aren't in, so it must not inflate the attendance
        -- denominator.
        ALTER TABLE academic_terms
            ADD COLUMN is_teaching INTEGER NOT NULL DEFAULT 1;
        UPDATE academic_terms SET is_teaching = 0
            WHERE kind = 'Study Leave';
    """),
    (16, """
        -- Statutory INSET allowance for the year (England: 5 days).
        ALTER TABLE academic_years
            ADD COLUMN inset_allowance INTEGER NOT NULL DEFAULT 5;
    """),
    (17, """
        -- Policy notes / decisions attached to a year. Distinct from
        -- academic_years.notes, which is a single free-text field.
        CREATE TABLE IF NOT EXISTS academic_year_notes (
            note_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            year_id    INTEGER NOT NULL,
            category   TEXT NOT NULL DEFAULT 'General',
            title      TEXT NOT NULL,
            body       TEXT,
            author     TEXT,
            pinned     INTEGER NOT NULL DEFAULT 0,
            deleted_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (year_id) REFERENCES academic_years(year_id)
                ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_note_year
            ON academic_year_notes(year_id, pinned DESC);
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
    # Tolerate the old bool form — callers (and older fixtures) reset
    # this with ``_DB_READY = False`` to force a re-init.
    if not isinstance(_DB_READY, set):
        _DB_READY = set()
    key = str(DB_PATH)
    if key in _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        _apply_migrations(conn)
    logger.debug("Academic-year schema ready at %s", DB_PATH)

    _DB_READY.add(key)


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
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise ValidationError("Limit must be a number") from None
    limit = max(1, min(limit, 10_000))
    sql = (f"SELECT * FROM academic_audit_log {where} "
           f"ORDER BY log_id DESC LIMIT ?")
    with _connect() as conn:
        return [dict(r)
                for r in conn.execute(sql, [*args, limit]).fetchall()]


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
        cycle_weeks=int(_safe(r, "cycle_weeks", DEFAULT_CYCLE_WEEKS)
                        or DEFAULT_CYCLE_WEEKS),
        cycle_anchor=_safe(r, "cycle_anchor"),
        inset_allowance=int(
            _safe(r, "inset_allowance", DEFAULT_INSET_ALLOWANCE)
            if _safe(r, "inset_allowance") is not None
            else DEFAULT_INSET_ALLOWANCE),
    )


def _row_term(r: sqlite3.Row) -> Term:
    return Term(
        term_id=r["term_id"], year_id=r["year_id"], name=r["name"],
        start_date=r["start_date"], end_date=r["end_date"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        deleted_at=_safe(r, "deleted_at"),
        kind=_safe(r, "kind", DEFAULT_TERM_KIND) or DEFAULT_TERM_KIND,
        group_label=_safe(r, "group_label"),
        is_teaching=bool(_safe(r, "is_teaching", 1)
                         if _safe(r, "is_teaching") is not None else 1),
    )


def _row_break(r: sqlite3.Row) -> Break:
    return Break(
        break_id=r["break_id"], year_id=r["year_id"], name=r["name"],
        start_date=r["start_date"], end_date=r["end_date"],
        type=r["type"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        deleted_at=_safe(r, "deleted_at"),
        am_pm=_safe(r, "am_pm", DEFAULT_BREAK_AM_PM) or DEFAULT_BREAK_AM_PM,
        group_label=_safe(r, "group_label"),
    )


def _row_event(r: sqlite3.Row) -> CalendarEvent:
    return CalendarEvent(
        event_id=r["event_id"], year_id=r["year_id"], name=r["name"],
        kind=r["kind"], date=r["date"],
        end_date=_safe(r, "end_date"), notes=r["notes"],
        deleted_at=_safe(r, "deleted_at"),
        created_at=r["created_at"], updated_at=r["updated_at"],
        group_label=_safe(r, "group_label"),
        owner=_safe(r, "owner"),
        department=_safe(r, "department"),
        location=_safe(r, "location"),
        capacity=_safe(r, "capacity"),
        repeat_rule=_safe(r, "repeat_rule"),
        repeat_interval=int(_safe(r, "repeat_interval", 1) or 1),
        repeat_until=_safe(r, "repeat_until"),
    )


def _row_period(r: sqlite3.Row) -> Period:
    return Period(
        period_id=r["period_id"], year_id=r["year_id"], name=r["name"],
        weekday=int(r["weekday"]),
        start_time=r["start_time"], end_time=r["end_time"],
        cycle_week=(int(r["cycle_week"])
                    if r["cycle_week"] is not None else None),
        is_teaching=bool(r["is_teaching"]),
        sort_order=int(r["sort_order"]), notes=r["notes"],
        deleted_at=_safe(r, "deleted_at"),
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_note(r: sqlite3.Row) -> YearNote:
    return YearNote(
        note_id=r["note_id"], year_id=r["year_id"],
        category=r["category"], title=r["title"], body=r["body"],
        author=r["author"], pinned=bool(r["pinned"]),
        deleted_at=_safe(r, "deleted_at"),
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Year CRUD ─────────────────────────────────────────────────────

def _clear_current(conn: sqlite3.Connection, *,
                    campus_id: str | None,
                    exclude_year_id: int | None = None) -> int:
    """Drop the ``is_current`` flag across one campus.

    "Current" is per campus — a two-site college runs a current year
    at each — so this never touches another campus's flag. Deleted
    rows are left alone; restoring one shouldn't resurrect a stale
    current year, and it can't be current while deleted anyway.
    """
    sql = ("UPDATE academic_years SET is_current = 0 "
           "WHERE deleted_at IS NULL AND is_current = 1 "
           "AND campus_id IS ?")
    args: list[Any] = [campus_id]
    if exclude_year_id is not None:
        sql += " AND year_id <> ?"
        args.append(exclude_year_id)
    return conn.execute(sql, args).rowcount


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
                        notes, group_label, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))""",
                (p["year_id"], p["name"], p["start_date"], p["end_date"],
                 p["type"], p["am_pm"], p["notes"], p["group_label"]),
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


# ── Year notes (policy / decisions / risks) ───────────────────────

def _validate_note_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    yid_raw = payload.get("year_id")
    if yid_raw in (None, ""):
        raise ValidationError("Year is required")
    try:
        yid = int(yid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Year id must be a number") from None
    if get_year(yid) is None:
        raise ValidationError(f"No academic year #{yid}")
    out["year_id"] = yid

    title = _require(payload.get("title"), "Title").strip()
    if len(title) > 120:
        raise ValidationError("Title must be 120 chars or fewer")
    out["title"] = title

    category = (payload.get("category")
                or DEFAULT_NOTE_CATEGORY).strip()
    if category not in NOTE_CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(NOTE_CATEGORIES)}")
    out["category"] = category

    body = payload.get("body")
    out["body"] = str(body).strip() if body not in (None, "") else None
    author = payload.get("author", CURRENT_ACTOR)
    out["author"] = (str(author).strip()
                     if author not in (None, "") else None)
    out["pinned"] = bool(payload.get("pinned"))
    return out


# ---------------------------------------------------------------------------
# Feature functions live in parts/; re-exported so every existing import (and
# the package's star import) still works. They call _connect/init_db/_audit/
# _check_write from this module, so patching DB_PATH, CURRENT_ACTOR, ENFORCE_RBAC
# etc. here still takes effect.
# ---------------------------------------------------------------------------
from education_system.systems.sixth_form.domain.academics.academic_year.parts.models import (  # noqa: E402
    AcademicYear,
    Break,
    _break_to_dict,
    CalendarEvent,
    CalendarGap,
    _event_to_dict,
    EventOccurrence,
    InsetStatus,
    _note_to_dict,
    Period,
    _period_to_dict,
    Term,
    _term_to_dict,
    _year_to_dict,
    YearGroup,
    YearNote,
    YearSummary,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.validation import (  # noqa: E402
    _require,
    _validate_date,
    _validate_time,
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.years import (  # noqa: E402
    approve_year,
    clear_current,
    create_year,
    current_year,
    current_years,
    delete_year,
    get_year,
    get_year_by_name,
    list_years,
    restore_year,
    set_current,
    unapprove_year,
    update_year,
    _validate_year_payload,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.year_groups import (  # noqa: E402
    delete_year_group,
    get_year_group,
    list_year_groups,
    _validate_group_label,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.notes import (  # noqa: E402
    add_note,
    delete_note,
    get_note,
    list_notes,
    restore_note,
    update_note,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.terms_breaks import (  # noqa: E402
    _assert_no_term_overlap,
    create_term,
    delete_break,
    delete_term,
    get_break,
    get_term,
    inset_days_planned,
    inset_status,
    list_breaks,
    list_terms,
    restore_break,
    restore_term,
    update_break,
    update_term,
    _validate_break_payload,
    _validate_term_payload,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.events import (  # noqa: E402
    _add_months,
    create_event,
    delete_event,
    _EVENT_COLUMNS,
    events_between,
    events_on,
    expand_event_occurrences,
    get_event,
    list_events,
    update_event,
    _validate_event_payload,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.teaching_days import (  # noqa: E402
    _break_ranges,
    _covered_by_break,
    _day_weight,
    find_calendar_gaps,
    find_term_on,
    is_break,
    _non_teaching_term_ranges,
    teaching_days_in,
    teaching_sessions_in,
    year_summary,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.weeks import (  # noqa: E402
    cycle_week_label,
    cycle_week_on,
    week_number_on,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.periods import (  # noqa: E402
    _assert_no_period_clash,
    create_period,
    day_shape,
    delete_period,
    get_period,
    list_periods,
    periods_on,
    restore_period,
    update_period,
    _validate_period_payload,
)
