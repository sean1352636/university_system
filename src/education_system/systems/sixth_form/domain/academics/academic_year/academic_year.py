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
    cycle_weeks: int = DEFAULT_CYCLE_WEEKS
    cycle_anchor: str | None = None
    inset_allowance: int = DEFAULT_INSET_ALLOWANCE

    @property
    def effective_cycle_anchor(self) -> str:
        """The Monday Week A starts on. Falls back to the Monday of
        the week the year starts in."""
        if self.cycle_anchor:
            return self.cycle_anchor
        try:
            d = _dt.date.fromisoformat(self.start_date)
        except ValueError:
            return self.start_date
        return (d - _dt.timedelta(days=d.weekday())).isoformat()

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
    group_label: str | None = None
    is_teaching: bool = True

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
    group_label: str | None = None

    @property
    def day_count(self) -> int:
        try:
            sd = _dt.date.fromisoformat(self.start_date)
            ed = _dt.date.fromisoformat(self.end_date or self.start_date)
            return max(0, (ed - sd).days) + 1
        except Exception:
            return 0


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
    group_label: str | None = None
    owner: str | None = None
    department: str | None = None
    location: str | None = None
    capacity: int | None = None
    repeat_rule: str | None = None
    repeat_interval: int = 1
    repeat_until: str | None = None

    @property
    def day_count(self) -> int:
        try:
            sd = _dt.date.fromisoformat(self.date)
            ed = _dt.date.fromisoformat(self.end_date or self.date)
            return max(0, (ed - sd).days) + 1
        except Exception:
            return 0

    @property
    def is_recurring(self) -> bool:
        return bool(self.repeat_rule)


@dataclass
class Period:
    """One slot in the shape of a teaching day."""
    period_id: int
    year_id: int
    name: str
    weekday: int
    start_time: str
    end_time: str
    cycle_week: int | None
    is_teaching: bool
    sort_order: int
    notes: str | None
    deleted_at: str | None
    created_at: str
    updated_at: str

    @property
    def weekday_name(self) -> str:
        return WEEKDAY_NAMES[self.weekday] if 0 <= self.weekday < 7 else "?"

    @property
    def minutes(self) -> int:
        try:
            sh, sm = (int(x) for x in self.start_time.split(":"))
            eh, em = (int(x) for x in self.end_time.split(":"))
            return max(0, (eh * 60 + em) - (sh * 60 + sm))
        except Exception:
            return 0


@dataclass
class EventOccurrence:
    """One materialised instance of a (possibly recurring) event."""
    event: CalendarEvent
    date: str
    end_date: str

    @property
    def name(self) -> str:
        return self.event.name

    @property
    def kind(self) -> str:
        return self.event.kind


@dataclass
class YearNote:
    """A policy note, decision, or risk recorded against a year."""
    note_id: int
    year_id: int
    category: str
    title: str
    body: str | None
    author: str | None
    pinned: bool
    deleted_at: str | None
    created_at: str
    updated_at: str


@dataclass
class InsetStatus:
    """How the year's INSET days stand against its allowance."""
    year_id: int
    allowance: int
    planned: float
    remaining: float

    @property
    def over(self) -> bool:
        return self.planned > self.allowance

    @property
    def under(self) -> bool:
        return self.planned < self.allowance

    @property
    def message(self) -> str:
        if self.over:
            return (f"{self.planned:g} INSET days planned — "
                    f"{abs(self.remaining):g} over the allowance of "
                    f"{self.allowance}")
        if self.under:
            return (f"{self.planned:g} of {self.allowance} INSET days "
                    f"planned — {self.remaining:g} still to schedule")
        return f"All {self.allowance} INSET days scheduled"


@dataclass
class CalendarGap:
    """A stretch of weekdays inside the year covered by no term."""
    start_date: str
    end_date: str
    weekdays: int
    group_label: str | None = None


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


def _note_to_dict(n: YearNote) -> dict:
    return {
        "note_id": n.note_id, "year_id": n.year_id,
        "category": n.category, "title": n.title, "body": n.body,
        "author": n.author, "pinned": n.pinned,
    }


def _year_to_dict(y: AcademicYear) -> dict:
    return {
        "year_id": y.year_id, "name": y.name,
        "start_date": y.start_date, "end_date": y.end_date,
        "is_current": y.is_current, "status": y.status,
        "notes": y.notes, "campus_id": y.campus_id,
        "cycle_weeks": y.cycle_weeks, "cycle_anchor": y.cycle_anchor,
        "inset_allowance": y.inset_allowance,
    }


def _term_to_dict(t: Term) -> dict:
    return {
        "term_id": t.term_id, "year_id": t.year_id, "name": t.name,
        "start_date": t.start_date, "end_date": t.end_date,
        "kind": t.kind, "notes": t.notes,
        "group_label": t.group_label, "is_teaching": t.is_teaching,
    }


def _break_to_dict(b: Break) -> dict:
    return {
        "break_id": b.break_id, "year_id": b.year_id, "name": b.name,
        "start_date": b.start_date, "end_date": b.end_date,
        "type": b.type, "am_pm": b.am_pm, "notes": b.notes,
        "group_label": b.group_label,
    }


def _event_to_dict(e: CalendarEvent) -> dict:
    return {
        "event_id": e.event_id, "year_id": e.year_id, "name": e.name,
        "kind": e.kind, "date": e.date, "end_date": e.end_date,
        "notes": e.notes, "group_label": e.group_label,
        "owner": e.owner, "department": e.department,
        "location": e.location, "capacity": e.capacity,
        "repeat_rule": e.repeat_rule,
        "repeat_interval": e.repeat_interval,
        "repeat_until": e.repeat_until,
    }


def _period_to_dict(p: Period) -> dict:
    return {
        "period_id": p.period_id, "year_id": p.year_id, "name": p.name,
        "weekday": p.weekday, "start_time": p.start_time,
        "end_time": p.end_time, "cycle_week": p.cycle_week,
        "is_teaching": p.is_teaching, "sort_order": p.sort_order,
        "notes": p.notes,
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


def _validate_time(value: Any, label: str) -> str:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    s = str(value).strip()
    if not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM (24-hour)")
    return s


def _validate_group_label(year_id: int, value: Any) -> str | None:
    """Normalise an optional year-group scope.

    ``None``/blank means "the whole college". A label must match one
    of the year's ``academic_year_groups`` rows, so a typo can't
    silently create a calendar nobody sees.
    """
    if value in (None, "") or (isinstance(value, str)
                                and not value.strip()):
        return None
    label = str(value).strip()
    known = {g.label for g in list_year_groups(year_id)}
    if label not in known:
        if not known:
            raise ValidationError(
                f"No year groups defined for year #{year_id} — create "
                f"{label!r} first (e.g. Y12 / Y13)")
        raise ValidationError(
            f"Unknown year group {label!r}. Known: "
            f"{', '.join(sorted(known))}")
    return label


def _assert_no_term_overlap(year_id: int, kind: str,
                             group_label: str | None,
                             start: str, end: str,
                             *, exclude_term_id: int | None = None
                             ) -> None:
    """Terms of the same kind and the same group scope must not
    overlap. Different kinds may (a Mock-Exam Week sits inside a
    Term), and so may different year groups (Y13 study leave runs
    while Y12 is still taught).
    """
    for t in list_terms(year_id=year_id, kind=kind):
        if exclude_term_id is not None and t.term_id == exclude_term_id:
            continue
        if t.group_label != group_label:
            continue
        if t.start_date <= end and start <= t.end_date:
            raise ValidationError(
                f"Overlaps existing {kind.lower()} {t.name!r} "
                f"({t.start_date} → {t.end_date})")


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

    cw = payload.get("cycle_weeks", DEFAULT_CYCLE_WEEKS)
    if cw in (None, ""):
        cw = DEFAULT_CYCLE_WEEKS
    try:
        cw = int(cw)
    except (TypeError, ValueError):
        raise ValidationError("Cycle weeks must be a number") from None
    if not (1 <= cw <= MAX_CYCLE_WEEKS):
        raise ValidationError(
            f"Cycle weeks must be between 1 and {MAX_CYCLE_WEEKS}")
    out["cycle_weeks"] = cw

    anchor = _validate_date(payload.get("cycle_anchor"), "Cycle anchor",
                              required=False)
    if anchor is not None:
        if _dt.date.fromisoformat(anchor).weekday() != 0:
            raise ValidationError("Cycle anchor must be a Monday")
        if anchor > out["end_date"]:
            raise ValidationError(
                "Cycle anchor must not be after the year ends")
    out["cycle_anchor"] = anchor

    allow = payload.get("inset_allowance", DEFAULT_INSET_ALLOWANCE)
    if allow in (None, ""):
        allow = DEFAULT_INSET_ALLOWANCE
    try:
        allow = int(allow)
    except (TypeError, ValueError):
        raise ValidationError("INSET allowance must be a number") from None
    if not (0 <= allow <= MAX_INSET_ALLOWANCE):
        raise ValidationError(
            f"INSET allowance must be between 0 and {MAX_INSET_ALLOWANCE}")
    out["inset_allowance"] = allow
    return out


def _validate_term_payload(payload: dict[str, Any], *,
                             term_id: int | None = None
                             ) -> dict[str, Any]:
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
    # Study leave is on the calendar but isn't taught. Callers can
    # override either way; unset follows the kind.
    teaching = payload.get("is_teaching")
    out["is_teaching"] = (kind not in NON_TEACHING_KINDS
                          if teaching is None else bool(teaching))

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
    out["group_label"] = _validate_group_label(
        out["year_id"], payload.get("group_label"))
    _assert_no_term_overlap(
        out["year_id"], out["kind"], out["group_label"],
        out["start_date"], out["end_date"], exclude_term_id=term_id)
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
    out["group_label"] = _validate_group_label(
        out["year_id"], payload.get("group_label"))
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


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
            _clear_current(conn, campus_id=p.get("campus_id"))
        cur = conn.execute(
            """INSERT INTO academic_years
                   (name, start_date, end_date, is_current,
                    status, notes, campus_id,
                    cycle_weeks, cycle_anchor, inset_allowance,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["name"], p["start_date"], p["end_date"],
             1 if p["is_current"] else 0, p["status"], p["notes"],
             p.get("campus_id"), p["cycle_weeks"], p["cycle_anchor"],
             p["inset_allowance"]),
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
                campus_id: Any = UNSET,
                include_deleted: bool = False) -> list[AcademicYear]:
    """List years. Omit ``campus_id`` for every campus; pass ``None``
    for the years with no campus set, or a string for one campus."""
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
    if not isinstance(campus_id, _Unset):
        clauses.append("campus_id IS ?")
        args.append(campus_id or None)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_years {where} "
           "ORDER BY start_date DESC, year_id DESC")
    with _connect() as conn:
        return [_row_year(r) for r in conn.execute(sql, args).fetchall()]


def current_year(*, campus_id: Any = UNSET) -> AcademicYear | None:
    """The current year. Omit ``campus_id`` to take whichever campus's
    year is current (warning if several are), pass ``None`` for the
    un-sited year, or a string for one campus."""
    init_db()
    args: list[Any] = []
    extra = ""
    if not isinstance(campus_id, _Unset):
        extra = " AND campus_id IS ?"
        args.append(campus_id or None)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM academic_years "
            "WHERE is_current = 1 AND deleted_at IS NULL"
            + extra + " ORDER BY campus_id IS NULL DESC, year_id ASC",
            args).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        logger.warning(
            "%d years are flagged current (campuses: %s) — returning "
            "%r. Pass campus_id= to disambiguate.",
            len(rows), ", ".join(str(r["campus_id"]) for r in rows),
            rows[0]["name"])
    return _row_year(rows[0])


def current_years() -> list[AcademicYear]:
    """Every campus's current year, one row per campus."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM academic_years "
            "WHERE is_current = 1 AND deleted_at IS NULL "
            "ORDER BY campus_id IS NULL DESC, campus_id ASC").fetchall()
    return [_row_year(r) for r in rows]


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
        "cycle_weeks": payload.get("cycle_weeks", existing.cycle_weeks),
        "cycle_anchor": payload.get("cycle_anchor",
                                     existing.cycle_anchor),
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
            _clear_current(conn, campus_id=p.get("campus_id"),
                            exclude_year_id=year_id)
        conn.execute(
            """UPDATE academic_years SET
                   name = ?, start_date = ?, end_date = ?,
                   is_current = ?, status = ?, notes = ?,
                   campus_id = ?, cycle_weeks = ?, cycle_anchor = ?,
                   updated_at = datetime('now')
               WHERE year_id = ?""",
            (p["name"], p["start_date"], p["end_date"],
             1 if p["is_current"] else 0, p["status"], p["notes"],
             p.get("campus_id"), p["cycle_weeks"], p["cycle_anchor"],
             year_id),
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
    """Flag a year current for its campus. Other campuses keep theirs."""
    init_db()
    _check_write()
    existing = get_year(year_id)
    if existing is None:
        raise ValidationError(f"No academic year #{year_id}")
    if existing.status == "Archived":
        raise ValidationError(
            "An archived year cannot be the current year")
    with _connect() as conn:
        _clear_current(conn, campus_id=existing.campus_id,
                        exclude_year_id=year_id)
        conn.execute(
            "UPDATE academic_years SET is_current = 1, "
            "updated_at = datetime('now') "
            "WHERE year_id = ? AND deleted_at IS NULL",
            (year_id,))
        _audit(conn, entity="year", entity_id=year_id,
                 action="set-current",
                 old={"is_current": existing.is_current},
                 new={"is_current": True,
                       "campus_id": existing.campus_id})
        conn.commit()
    out = get_year(year_id)
    assert out is not None
    logger.info("Set current academic year → #%d %r (campus %s)",
                year_id, out.name, out.campus_id or "-")
    return out


def clear_current(*, campus_id: Any = UNSET) -> int:
    """Clear the current-year flag. Omit ``campus_id`` to clear every
    campus. Returns how many rows were cleared."""
    init_db()
    _check_write()
    with _connect() as conn:
        if isinstance(campus_id, _Unset):
            cleared = conn.execute(
                "UPDATE academic_years SET is_current = 0 "
                "WHERE deleted_at IS NULL AND is_current = 1").rowcount
        else:
            cleared = _clear_current(conn, campus_id=campus_id or None)
        _audit(conn, entity="year", entity_id=0, action="clear-current",
                 new={"campus_id": (None
                                     if isinstance(campus_id, _Unset)
                                     else campus_id),
                       "cleared": cleared})
        conn.commit()
    logger.info("Cleared current academic year (%d row(s))", cleared)
    return cleared


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
            for table in ("academic_breaks", "academic_periods",
                            "academic_year_notes"):
                conn.execute(
                    f"UPDATE {table} SET deleted_at = {now_sql}, "
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
                    group_label, is_teaching, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["year_id"], p["name"], p["start_date"], p["end_date"],
             p["notes"], p["kind"], p["group_label"],
             1 if p["is_teaching"] else 0),
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
                group_label: str | None = None,
                include_shared: bool = True,
                include_deleted: bool = False) -> list[Term]:
    """List terms. ``group_label`` narrows to one year group; with
    ``include_shared`` (the default) college-wide terms come back too.
    """
    init_db()
    clauses, args = [], []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if year_id is not None:
        clauses.append("year_id = ?")
        args.append(year_id)
    if group_label is not None:
        if include_shared:
            clauses.append("(group_label IS NULL OR group_label = ?)")
        else:
            clauses.append("group_label = ?")
        args.append(group_label)
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
        "group_label": payload.get("group_label", existing.group_label),
        "is_teaching": payload.get("is_teaching", existing.is_teaching),
    }
    p = _validate_term_payload(merged, term_id=term_id)
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
                   kind = ?, notes = ?, group_label = ?,
                   is_teaching = ?, updated_at = datetime('now')
               WHERE term_id = ?""",
            (p["name"], p["start_date"], p["end_date"], p["kind"],
             p["notes"], p["group_label"],
             1 if p["is_teaching"] else 0, term_id),
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
                 group_label: str | None = None,
                 include_shared: bool = True,
                 include_deleted: bool = False) -> list[Break]:
    """List breaks. ``group_label`` narrows to one year group; with
    ``include_shared`` (the default) college-wide breaks come back too.
    """
    init_db()
    clauses, args = [], []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if year_id is not None:
        clauses.append("year_id = ?")
        args.append(year_id)
    if group_label is not None:
        if include_shared:
            clauses.append("(group_label IS NULL OR group_label = ?)")
        else:
            clauses.append("group_label = ?")
        args.append(group_label)
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
        "group_label": payload.get("group_label", existing.group_label),
    }
    p = _validate_break_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE academic_breaks SET
                   name = ?, start_date = ?, end_date = ?,
                   type = ?, am_pm = ?, notes = ?, group_label = ?,
                   updated_at = datetime('now')
               WHERE break_id = ?""",
            (p["name"], p["start_date"], p["end_date"],
             p["type"], p["am_pm"], p["notes"], p["group_label"],
             break_id),
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


# ── INSET allowance ───────────────────────────────────────────────

def inset_days_planned(year_id: int, *,
                        group_label: str | None = None) -> float:
    """How many INSET days are on the calendar, counting an AM/PM
    closure as half a day and ignoring any that land at a weekend."""
    total = 0.0
    for b in list_breaks(year_id=year_id, type="INSET",
                           group_label=group_label):
        if group_label is None and b.group_label is not None:
            continue
        try:
            cur = _dt.date.fromisoformat(b.start_date)
            end = _dt.date.fromisoformat(b.end_date or b.start_date)
        except ValueError:
            continue
        one = _dt.timedelta(days=1)
        while cur <= end:
            if cur.weekday() < 5:
                total += 0.5 if b.am_pm in ("AM", "PM") else 1.0
            cur += one
    return total


def inset_status(year_id: int, *,
                  group_label: str | None = None) -> InsetStatus:
    """Compare planned INSET against the year's allowance.

    Sixth forms get a fixed number of staff-development days a year
    (five in England). Scheduling a sixth by accident is a payroll
    and parent-communication problem, and leaving one unbooked in
    July is worse — so surface both.
    """
    year = get_year(year_id)
    if year is None:
        raise ValidationError(f"No academic year #{year_id}")
    planned = inset_days_planned(year_id, group_label=group_label)
    return InsetStatus(
        year_id=year_id,
        allowance=year.inset_allowance,
        planned=planned,
        remaining=year.inset_allowance - planned,
    )


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


def add_note(payload: dict[str, Any]) -> YearNote:
    init_db()
    _check_write()
    p = _validate_note_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO academic_year_notes
                   (year_id, category, title, body, author, pinned)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (p["year_id"], p["category"], p["title"], p["body"],
             p["author"], 1 if p["pinned"] else 0))
        new_id = cur.lastrowid
        _audit(conn, entity="note", entity_id=new_id,
                 action="create", new=p)
        conn.commit()
    out = get_note(new_id)
    assert out is not None
    return out


def get_note(note_id: int, *,
              include_deleted: bool = False) -> YearNote | None:
    init_db()
    extra = "" if include_deleted else " AND deleted_at IS NULL"
    with _connect() as conn:
        r = conn.execute(
            f"SELECT * FROM academic_year_notes "
            f"WHERE note_id = ?{extra}", (note_id,)).fetchone()
        return _row_note(r) if r else None


def list_notes(*, year_id: int | None = None,
                category: str | None = None,
                pinned_only: bool = False,
                include_deleted: bool = False) -> list[YearNote]:
    init_db()
    clauses, args = [], []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if year_id is not None:
        clauses.append("year_id = ?")
        args.append(year_id)
    if category is not None:
        if category not in NOTE_CATEGORIES:
            raise ValidationError(
                f"Category must be one of: {', '.join(NOTE_CATEGORIES)}")
        clauses.append("category = ?")
        args.append(category)
    if pinned_only:
        clauses.append("pinned = 1")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_year_notes {where} "
           "ORDER BY pinned DESC, note_id DESC")
    with _connect() as conn:
        return [_row_note(r) for r in conn.execute(sql, args).fetchall()]


def update_note(note_id: int, payload: dict[str, Any]) -> YearNote:
    init_db()
    _check_write()
    existing = get_note(note_id)
    if existing is None:
        raise ValidationError(f"No note #{note_id}")
    current = _note_to_dict(existing)
    merged = {k: payload.get(k, current[k]) for k in current}
    merged["year_id"] = existing.year_id
    p = _validate_note_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE academic_year_notes SET
                   category = ?, title = ?, body = ?, author = ?,
                   pinned = ?, updated_at = datetime('now')
               WHERE note_id = ?""",
            (p["category"], p["title"], p["body"], p["author"],
             1 if p["pinned"] else 0, note_id))
        _audit(conn, entity="note", entity_id=note_id,
                 action="update", old=current, new=p)
        conn.commit()
    out = get_note(note_id)
    assert out is not None
    return out


def delete_note(note_id: int, *, hard: bool = False) -> bool:
    init_db()
    _check_write()
    existing = get_note(note_id, include_deleted=True)
    if existing is None:
        return False
    with _connect() as conn:
        if hard:
            cur = conn.execute(
                "DELETE FROM academic_year_notes WHERE note_id = ?",
                (note_id,))
        else:
            cur = conn.execute(
                "UPDATE academic_year_notes SET "
                "deleted_at = datetime('now'), "
                "updated_at = datetime('now') WHERE note_id = ?",
                (note_id,))
        if cur.rowcount:
            _audit(conn, entity="note", entity_id=note_id,
                     action="hard-delete" if hard else "delete",
                     old=_note_to_dict(existing))
            conn.commit()
            return True
        return False


def restore_note(note_id: int) -> YearNote:
    init_db()
    _check_write()
    with _connect() as conn:
        conn.execute(
            "UPDATE academic_year_notes SET deleted_at = NULL, "
            "updated_at = datetime('now') WHERE note_id = ?",
            (note_id,))
        _audit(conn, entity="note", entity_id=note_id, action="restore")
        conn.commit()
    out = get_note(note_id, include_deleted=True)
    if out is None:
        raise ValidationError(f"No note #{note_id}")
    return out


# ── Events ────────────────────────────────────────────────────────

def _validate_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    yid_raw = payload.get("year_id")
    if yid_raw in (None, ""):
        raise ValidationError("Year is required")
    try:
        yid = int(yid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Year id must be a number") from None
    year = get_year(yid)
    if year is None:
        raise ValidationError(f"No academic year #{yid}")
    out["year_id"] = yid

    out["name"] = _require(payload.get("name"), "Name").strip()
    kind = (payload.get("kind") or DEFAULT_EVENT_KIND).strip()
    if kind not in EVENT_KINDS:
        raise ValidationError(
            f"Event kind must be one of: {', '.join(EVENT_KINDS)}")
    out["kind"] = kind

    s = _validate_date(payload.get("date"), "Date")
    e = _validate_date(payload.get("end_date"), "End date",
                          required=False)
    if e is not None and e < s:
        raise ValidationError("End date cannot be before start date")
    if s < year.start_date or s > year.end_date:
        raise ValidationError(
            f"Event must fall inside the year "
            f"({year.start_date} → {year.end_date})")
    if e is not None and e > year.end_date:
        raise ValidationError(
            f"Event must end inside the year (by {year.end_date})")
    out["date"], out["end_date"] = s, e

    out["group_label"] = _validate_group_label(
        yid, payload.get("group_label"))

    for field_name, label, limit in (
        ("owner", "Owner", 64),
        ("department", "Department", 64),
        ("location", "Location", 96),
    ):
        raw = payload.get(field_name)
        val = str(raw).strip() if raw not in (None, "") else None
        if val is not None and len(val) > limit:
            raise ValidationError(f"{label} must be {limit} chars or fewer")
        out[field_name] = val or None

    cap = payload.get("capacity")
    if cap in (None, ""):
        out["capacity"] = None
    else:
        try:
            cap = int(cap)
        except (TypeError, ValueError):
            raise ValidationError("Capacity must be a number") from None
        if cap < 0:
            raise ValidationError("Capacity cannot be negative")
        out["capacity"] = cap

    # ── Recurrence ────────────────────────────────────────────────
    rule = payload.get("repeat_rule")
    rule = str(rule).strip().upper() if rule not in (None, "") else None
    if rule is not None and rule not in REPEAT_RULES:
        raise ValidationError(
            f"Repeat rule must be one of: {', '.join(REPEAT_RULES)}")
    out["repeat_rule"] = rule

    interval = payload.get("repeat_interval", 1)
    if interval in (None, ""):
        interval = 1
    try:
        interval = int(interval)
    except (TypeError, ValueError):
        raise ValidationError("Repeat interval must be a number") from None
    if interval < 1:
        raise ValidationError("Repeat interval must be at least 1")
    out["repeat_interval"] = interval

    until = _validate_date(payload.get("repeat_until"), "Repeat until",
                              required=False)
    if rule is None:
        if until is not None:
            raise ValidationError(
                "Repeat until needs a repeat rule")
        out["repeat_until"] = None
    else:
        # An open-ended series stops at the end of the year.
        if until is None:
            until = year.end_date
        if until < s:
            raise ValidationError(
                "Repeat until cannot be before the first date")
        if until > year.end_date:
            raise ValidationError(
                f"Repeat until must fall inside the year "
                f"(by {year.end_date})")
        out["repeat_until"] = until

    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


_EVENT_COLUMNS = (
    "year_id", "name", "kind", "date", "end_date", "notes",
    "group_label", "owner", "department", "location", "capacity",
    "repeat_rule", "repeat_interval", "repeat_until",
)


def create_event(payload: dict[str, Any]) -> CalendarEvent:
    init_db()
    _check_write()
    p = _validate_event_payload(payload)
    cols = ", ".join(_EVENT_COLUMNS)
    marks = ", ".join("?" for _ in _EVENT_COLUMNS)
    with _connect() as conn:
        cur = conn.execute(
            f"INSERT INTO academic_events ({cols}) VALUES ({marks})",
            tuple(p[c] for c in _EVENT_COLUMNS))
        new_id = cur.lastrowid
        _audit(conn, entity="event", entity_id=new_id,
                 action="create", new=p)
        conn.commit()
    out = get_event(new_id)
    assert out is not None
    logger.info("Created event #%d %r (%s) in year #%d",
                new_id, p["name"], p["kind"], p["year_id"])
    return out


def update_event(event_id: int, payload: dict[str, Any]) -> CalendarEvent:
    init_db()
    _check_write()
    existing = get_event(event_id)
    if existing is None:
        raise ValidationError(f"No event #{event_id}")
    current = _event_to_dict(existing)
    merged = {c: payload.get(c, current.get(c)) for c in _EVENT_COLUMNS}
    merged["year_id"] = existing.year_id  # events don't move years
    merged["notes"] = payload.get("notes", existing.notes)
    p = _validate_event_payload(merged)
    sets = ", ".join(f"{c} = ?" for c in _EVENT_COLUMNS
                      if c != "year_id")
    with _connect() as conn:
        conn.execute(
            f"UPDATE academic_events SET {sets}, "
            f"updated_at = datetime('now') WHERE event_id = ?",
            tuple(p[c] for c in _EVENT_COLUMNS if c != "year_id")
            + (event_id,))
        _audit(conn, entity="event", entity_id=event_id,
                 action="update", old=current, new=p)
        conn.commit()
    out = get_event(event_id)
    assert out is not None
    logger.info("Updated event #%d %r", event_id, out.name)
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
                 kind: str | None = None,
                 group_label: str | None = None,
                 include_shared: bool = True,
                 owner: str | None = None,
                 department: str | None = None) -> list[CalendarEvent]:
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
    if group_label is not None:
        if include_shared:
            clauses.append("(group_label IS NULL OR group_label = ?)")
        else:
            clauses.append("group_label = ?")
        args.append(group_label)
    if owner is not None:
        clauses.append("owner = ?")
        args.append(owner)
    if department is not None:
        clauses.append("department = ?")
        args.append(department)
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


# ── Recurring events ──────────────────────────────────────────────

def _add_months(d: _dt.date, months: int) -> _dt.date:
    """Shift by whole months, clamping to the end of short months
    (31 Jan + 1 month → 28/29 Feb)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day = [31,
                 29 if (year % 4 == 0 and (year % 100 != 0
                                             or year % 400 == 0)) else 28,
                 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return _dt.date(year, month, min(d.day, last_day))


def expand_event_occurrences(
    event: CalendarEvent, *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[EventOccurrence]:
    """Materialise a (possibly recurring) event into occurrences.

    A non-recurring event yields exactly itself. Recurring events
    repeat every ``repeat_interval`` days/weeks/months up to and
    including ``repeat_until``, preserving the event's duration.
    Capped at ``MAX_OCCURRENCES``.
    """
    try:
        first = _dt.date.fromisoformat(event.date)
    except ValueError:
        return []
    try:
        last = _dt.date.fromisoformat(event.end_date or event.date)
    except ValueError:
        last = first
    span = max(0, (last - first).days)

    if not event.repeat_rule:
        starts = [first]
    else:
        until_iso = event.repeat_until or event.date
        try:
            until = _dt.date.fromisoformat(until_iso)
        except ValueError:
            until = first
        rule = event.repeat_rule.upper()
        step = max(1, event.repeat_interval)
        starts, cur, guard = [], first, 0
        while cur <= until and guard < MAX_OCCURRENCES:
            starts.append(cur)
            guard += 1
            if rule == "DAILY":
                cur = cur + _dt.timedelta(days=step)
            elif rule == "WEEKLY":
                cur = cur + _dt.timedelta(weeks=step)
            elif rule == "MONTHLY":
                cur = _add_months(first, step * guard)
            else:  # unknown rule stored by an older version
                break
        if guard >= MAX_OCCURRENCES:
            logger.warning(
                "Event #%s hit the %d-occurrence cap",
                event.event_id, MAX_OCCURRENCES)

    out: list[EventOccurrence] = []
    for s in starts:
        e = s + _dt.timedelta(days=span)
        s_iso, e_iso = s.isoformat(), e.isoformat()
        if date_from and e_iso < date_from:
            continue
        if date_to and s_iso > date_to:
            continue
        out.append(EventOccurrence(event=event, date=s_iso,
                                     end_date=e_iso))
    return out


def events_on(year_id: int, date_iso: str, *,
               group_label: str | None = None) -> list[EventOccurrence]:
    """Every event occurrence covering ``date_iso``."""
    s = _validate_date(date_iso, "Date")
    out: list[EventOccurrence] = []
    for ev in list_events(year_id=year_id, group_label=group_label):
        out.extend(expand_event_occurrences(ev, date_from=s, date_to=s))
    return sorted(out, key=lambda o: (o.date, o.event.event_id))


def events_between(year_id: int, date_from: str, date_to: str, *,
                    group_label: str | None = None,
                    kind: str | None = None) -> list[EventOccurrence]:
    """Every event occurrence overlapping [from, to], expanded."""
    df = _validate_date(date_from, "From")
    dt = _validate_date(date_to, "To")
    out: list[EventOccurrence] = []
    for ev in list_events(year_id=year_id, kind=kind,
                            group_label=group_label):
        out.extend(expand_event_occurrences(ev, date_from=df,
                                              date_to=dt))
    return sorted(out, key=lambda o: (o.date, o.event.event_id))


# ── Timetable cycle (Week A / Week B) ─────────────────────────────

def cycle_week_on(year_id: int, date_iso: str) -> int | None:
    """Which week of the timetable cycle ``date_iso`` falls in.

    Returns 1..``cycle_weeks``, or ``None`` if the date is outside
    the year. A year with ``cycle_weeks == 1`` always returns 1.
    """
    year = get_year(year_id)
    if year is None:
        raise ValidationError(f"No academic year #{year_id}")
    s = _validate_date(date_iso, "Date")
    if s < year.start_date or s > year.end_date:
        return None
    anchor = _dt.date.fromisoformat(year.effective_cycle_anchor)
    d = _dt.date.fromisoformat(s)
    # Compare Monday-of-week to Monday-anchor so any day in the same
    # week gets the same cycle position.
    monday = d - _dt.timedelta(days=d.weekday())
    weeks = (monday - anchor).days // 7
    return int(weeks % max(1, year.cycle_weeks)) + 1


def cycle_week_label(year_id: int, date_iso: str) -> str | None:
    """``cycle_week_on`` as 'A' / 'B' / …. ``None`` outside the year."""
    n = cycle_week_on(year_id, date_iso)
    if n is None:
        return None
    return CYCLE_LABELS[n - 1] if n <= len(CYCLE_LABELS) else str(n)


def week_number_on(year_id: int, date_iso: str, *,
                    group_label: str | None = None
                    ) -> dict[str, Any] | None:
    """Teaching-week numbering for a date.

    Returns ``{"year_week", "term_week", "term", "cycle_week",
    "cycle_label"}`` — where ``year_week`` counts weeks containing at
    least one teaching day since the start of the year, and
    ``term_week`` does the same within the containing term. Weeks
    that are entirely break/weekend are not counted, so "Week 7"
    means the seventh week students were actually in.

    ``None`` if the date is outside the year.
    """
    year = get_year(year_id)
    if year is None:
        raise ValidationError(f"No academic year #{year_id}")
    s = _validate_date(date_iso, "Date")
    if s < year.start_date or s > year.end_date:
        return None

    term = find_term_on(year_id, s, group_label=group_label,
                          kind=DEFAULT_TERM_KIND)
    target = _dt.date.fromisoformat(s)
    target_monday = target - _dt.timedelta(days=target.weekday())

    def _teaching_weeks_upto(from_iso: str) -> int:
        """Count Mondays whose week holds >= 1 teaching day, from
        ``from_iso`` up to and including the target's week."""
        start = _dt.date.fromisoformat(from_iso)
        monday = start - _dt.timedelta(days=start.weekday())
        breaks = _break_ranges(year_id, group_label=group_label)
        count = 0
        week = monday
        while week <= target_monday:
            for offset in range(5):  # Mon..Fri
                day = week + _dt.timedelta(days=offset)
                iso = day.isoformat()
                if iso < year.start_date or iso > year.end_date:
                    continue
                if from_iso and iso < from_iso:
                    continue
                if not _covered_by_break(iso, breaks):
                    count += 1
                    break
            week += _dt.timedelta(days=7)
        return count

    return {
        "date": s,
        "year_week": _teaching_weeks_upto(year.start_date) or None,
        "term_week": (_teaching_weeks_upto(term.start_date)
                      if term else None),
        "term": term.name if term else None,
        "cycle_week": cycle_week_on(year_id, s),
        "cycle_label": cycle_week_label(year_id, s),
    }


# ── Periods (the shape of a teaching day) ─────────────────────────

def _validate_period_payload(payload: dict[str, Any]
                              ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    yid_raw = payload.get("year_id")
    if yid_raw in (None, ""):
        raise ValidationError("Year is required")
    try:
        yid = int(yid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Year id must be a number") from None
    year = get_year(yid)
    if year is None:
        raise ValidationError(f"No academic year #{yid}")
    out["year_id"] = yid

    name = _require(payload.get("name"), "Period name").strip()
    if len(name) > 32:
        raise ValidationError("Period name must be 32 chars or fewer")
    out["name"] = name

    wd = payload.get("weekday")
    if wd in (None, ""):
        raise ValidationError("Weekday is required (0=Mon … 6=Sun)")
    if isinstance(wd, str) and not wd.strip().lstrip("-").isdigit():
        match = [i for i, n in enumerate(WEEKDAY_NAMES)
                  if n.lower() == wd.strip().lower()]
        if not match:
            raise ValidationError(
                f"Weekday must be 0-6 or one of: "
                f"{', '.join(WEEKDAY_NAMES)}")
        wd = match[0]
    try:
        wd = int(wd)
    except (TypeError, ValueError):
        raise ValidationError("Weekday must be a number 0-6") from None
    if not (0 <= wd <= 6):
        raise ValidationError("Weekday must be 0 (Mon) … 6 (Sun)")
    out["weekday"] = wd

    out["start_time"] = _validate_time(payload.get("start_time"),
                                          "Start time")
    out["end_time"] = _validate_time(payload.get("end_time"),
                                        "End time")
    if out["end_time"] <= out["start_time"]:
        raise ValidationError("End time must be after start time")

    cw = payload.get("cycle_week")
    if cw in (None, ""):
        out["cycle_week"] = None
    else:
        try:
            cw = int(cw)
        except (TypeError, ValueError):
            raise ValidationError("Cycle week must be a number") from None
        if not (1 <= cw <= year.cycle_weeks):
            raise ValidationError(
                f"Cycle week must be 1..{year.cycle_weeks} for this year")
        out["cycle_week"] = cw

    out["is_teaching"] = bool(payload.get("is_teaching", True))
    try:
        out["sort_order"] = int(payload.get("sort_order") or 0)
    except (TypeError, ValueError):
        raise ValidationError("Sort order must be a number") from None
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


def _assert_no_period_clash(p: dict[str, Any], *,
                             exclude_period_id: int | None = None
                             ) -> None:
    """Two periods on the same weekday and cycle week must not share
    wall-clock time."""
    for other in list_periods(year_id=p["year_id"],
                                weekday=p["weekday"]):
        if exclude_period_id is not None \
                and other.period_id == exclude_period_id:
            continue
        # NULL cycle_week means "every week", so it clashes with all.
        if (other.cycle_week is not None
                and p["cycle_week"] is not None
                and other.cycle_week != p["cycle_week"]):
            continue
        if (other.start_time < p["end_time"]
                and p["start_time"] < other.end_time):
            raise ValidationError(
                f"Clashes with {other.name!r} "
                f"({other.start_time}-{other.end_time}) on "
                f"{WEEKDAY_NAMES[p['weekday']]}")


def create_period(payload: dict[str, Any]) -> Period:
    init_db()
    _check_write()
    p = _validate_period_payload(payload)
    _assert_no_period_clash(p)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO academic_periods
                   (year_id, name, weekday, start_time, end_time,
                    cycle_week, is_teaching, sort_order, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["year_id"], p["name"], p["weekday"], p["start_time"],
             p["end_time"], p["cycle_week"],
             1 if p["is_teaching"] else 0, p["sort_order"], p["notes"]))
        new_id = cur.lastrowid
        _audit(conn, entity="period", entity_id=new_id,
                 action="create", new=p)
        conn.commit()
    out = get_period(new_id)
    assert out is not None
    return out


def get_period(period_id: int, *,
                include_deleted: bool = False) -> Period | None:
    init_db()
    extra = "" if include_deleted else " AND deleted_at IS NULL"
    with _connect() as conn:
        r = conn.execute(
            f"SELECT * FROM academic_periods "
            f"WHERE period_id = ?{extra}", (period_id,)).fetchone()
        return _row_period(r) if r else None


def list_periods(*, year_id: int | None = None,
                  weekday: int | None = None,
                  cycle_week: int | None = None,
                  teaching_only: bool = False,
                  include_deleted: bool = False) -> list[Period]:
    init_db()
    clauses, args = [], []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if year_id is not None:
        clauses.append("year_id = ?")
        args.append(year_id)
    if weekday is not None:
        clauses.append("weekday = ?")
        args.append(int(weekday))
    if cycle_week is not None:
        # NULL means "every week", so it matches any requested week.
        clauses.append("(cycle_week IS NULL OR cycle_week = ?)")
        args.append(int(cycle_week))
    if teaching_only:
        clauses.append("is_teaching = 1")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_periods {where} "
           "ORDER BY weekday ASC, sort_order ASC, start_time ASC")
    with _connect() as conn:
        return [_row_period(r) for r in conn.execute(sql, args).fetchall()]


def update_period(period_id: int, payload: dict[str, Any]) -> Period:
    init_db()
    _check_write()
    existing = get_period(period_id)
    if existing is None:
        raise ValidationError(f"No period #{period_id}")
    current = _period_to_dict(existing)
    merged = {k: payload.get(k, current[k]) for k in current}
    merged["year_id"] = existing.year_id
    p = _validate_period_payload(merged)
    _assert_no_period_clash(p, exclude_period_id=period_id)
    with _connect() as conn:
        conn.execute(
            """UPDATE academic_periods SET
                   name = ?, weekday = ?, start_time = ?, end_time = ?,
                   cycle_week = ?, is_teaching = ?, sort_order = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE period_id = ?""",
            (p["name"], p["weekday"], p["start_time"], p["end_time"],
             p["cycle_week"], 1 if p["is_teaching"] else 0,
             p["sort_order"], p["notes"], period_id))
        _audit(conn, entity="period", entity_id=period_id,
                 action="update", old=current, new=p)
        conn.commit()
    out = get_period(period_id)
    assert out is not None
    return out


def delete_period(period_id: int, *, hard: bool = False) -> bool:
    init_db()
    _check_write()
    existing = get_period(period_id, include_deleted=True)
    if existing is None:
        return False
    with _connect() as conn:
        if hard:
            cur = conn.execute(
                "DELETE FROM academic_periods WHERE period_id = ?",
                (period_id,))
        else:
            cur = conn.execute(
                "UPDATE academic_periods SET "
                "deleted_at = datetime('now'), "
                "updated_at = datetime('now') WHERE period_id = ?",
                (period_id,))
        if cur.rowcount:
            _audit(conn, entity="period", entity_id=period_id,
                     action="hard-delete" if hard else "delete",
                     old=_period_to_dict(existing))
            conn.commit()
            return True
        return False


def restore_period(period_id: int) -> Period:
    init_db()
    _check_write()
    with _connect() as conn:
        conn.execute(
            "UPDATE academic_periods SET deleted_at = NULL, "
            "updated_at = datetime('now') WHERE period_id = ?",
            (period_id,))
        _audit(conn, entity="period", entity_id=period_id,
                 action="restore")
        conn.commit()
    out = get_period(period_id, include_deleted=True)
    if out is None:
        raise ValidationError(f"No period #{period_id}")
    return out


def periods_on(year_id: int, date_iso: str, *,
                teaching_only: bool = False) -> list[Period]:
    """The day's shape: periods for that weekday and cycle week.

    Returns [] on a weekend with no periods defined, or on a day the
    college is closed (a full-day break).
    """
    s = _validate_date(date_iso, "Date")
    d = _dt.date.fromisoformat(s)
    cw = cycle_week_on(year_id, s)
    return list_periods(year_id=year_id, weekday=d.weekday(),
                          cycle_week=cw, teaching_only=teaching_only)


def day_shape(year_id: int, date_iso: str, *,
               group_label: str | None = None) -> dict[str, Any]:
    """Everything about one day: term, break, cycle week, periods,
    events. The single call an attendance or timetable screen needs.
    """
    s = _validate_date(date_iso, "Date")
    brk = is_break(year_id, s, group_label=group_label)
    term = find_term_on(year_id, s, group_label=group_label)
    weight = _day_weight(
        s, _break_ranges(year_id, group_label=group_label),
        _non_teaching_term_ranges(year_id, group_label=group_label),
        half_days=True)
    periods = [] if weight == 0 else periods_on(year_id, s)
    if brk and brk.am_pm in ("AM", "PM"):
        # Half day: keep only the sessions that still run.
        periods = [p for p in periods
                    if (p.start_time >= "12:00") == (brk.am_pm == "AM")]
    return {
        "date": s,
        "term": term.name if term else None,
        "term_kind": term.kind if term else None,
        "break": brk.name if brk else None,
        "break_type": brk.type if brk else None,
        "am_pm": brk.am_pm if brk else None,
        "cycle_week": cycle_week_on(year_id, s),
        "cycle_label": cycle_week_label(year_id, s),
        "periods": periods,
        "events": events_on(year_id, s, group_label=group_label),
        "notes": list_notes(year_id=year_id, pinned_only=True),
        "day_weight": (weight
                       if _dt.date.fromisoformat(s).weekday() < 5
                       else 0.0),
        "is_teaching_day": bool(
            _dt.date.fromisoformat(s).weekday() < 5 and weight > 0),
    }


# ── Coverage gaps ─────────────────────────────────────────────────

def find_calendar_gaps(year_id: int, *,
                        group_label: str | None = None,
                        ignore_breaks: bool = False
                        ) -> list[CalendarGap]:
    """Weekdays inside the year that no term covers.

    By default a gap that is entirely accounted for by a break (a
    holiday between terms) is not reported — those are expected. Set
    ``ignore_breaks=True`` to see every uncovered stretch.
    """
    year = get_year(year_id)
    if year is None:
        raise ValidationError(f"No academic year #{year_id}")
    terms = [t for t in list_terms(year_id=year_id,
                                     kind=DEFAULT_TERM_KIND,
                                     group_label=group_label)]
    term_ranges = [(t.start_date, t.end_date) for t in terms]
    breaks = ([] if ignore_breaks
              else _break_ranges(year_id, group_label=group_label))

    gaps: list[CalendarGap] = []
    run: list[str] = []
    cur = _dt.date.fromisoformat(year.start_date)
    end = _dt.date.fromisoformat(year.end_date)
    one = _dt.timedelta(days=1)

    def _flush() -> None:
        if not run:
            return
        gaps.append(CalendarGap(
            start_date=run[0], end_date=run[-1], weekdays=len(run),
            group_label=group_label))
        run.clear()

    while cur <= end:
        iso = cur.isoformat()
        if cur.weekday() >= 5:
            cur += one
            continue          # weekends are never a gap
        covered = any(s <= iso <= e for (s, e) in term_ranges) \
            or _covered_by_break(iso, breaks)
        if covered:
            _flush()
        else:
            run.append(iso)
        cur += one
    _flush()
    return gaps


# ── Lookups ───────────────────────────────────────────────────────

def _break_ranges(year_id: int, *, group_label: str | None = None
                   ) -> list[tuple[str, str, str]]:
    """(start, end, am_pm) for the breaks that apply to a group."""
    return [(b.start_date, b.end_date, b.am_pm)
            for b in list_breaks(year_id=year_id,
                                   group_label=group_label)
            if group_label is not None or b.group_label is None]


def _covered_by_break(date_iso: str,
                       ranges: list[tuple[str, str, str]]) -> bool:
    """True only for a *full*-day closure — an AM/PM half day still
    counts as a day the college was open."""
    return any(s <= date_iso <= e and ap == "FULL"
               for (s, e, ap) in ranges)


def find_term_on(year_id: int, date_iso: str, *,
                  group_label: str | None = None,
                  kind: str | None = None) -> Term | None:
    """Return the term containing ``date_iso`` (if any).

    Pass ``kind='Term'`` to ignore nested Mock-Exam Weeks and Study
    Leave. ``group_label`` prefers a term scoped to that year group
    over the college-wide one.
    """
    init_db()
    s = _validate_date(date_iso, "Date")
    clauses = ["year_id = ?", "deleted_at IS NULL",
               "start_date <= ?", "end_date >= ?"]
    args: list[Any] = [year_id, s, s]
    if kind is not None:
        clauses.append("kind = ?")
        args.append(kind)
    if group_label is not None:
        clauses.append("(group_label IS NULL OR group_label = ?)")
        args.append(group_label)
    else:
        clauses.append("group_label IS NULL")
    with _connect() as conn:
        r = conn.execute(
            f"SELECT * FROM academic_terms WHERE {' AND '.join(clauses)} "
            # A group-specific row wins over the college-wide one.
            "ORDER BY group_label IS NULL ASC, start_date ASC LIMIT 1",
            args).fetchone()
        return _row_term(r) if r else None


def is_break(year_id: int, date_iso: str, *,
              group_label: str | None = None) -> Break | None:
    """Return the break covering ``date_iso`` (if any)."""
    init_db()
    s = _validate_date(date_iso, "Date")
    clauses = ["year_id = ?", "deleted_at IS NULL",
               "start_date <= ?", "end_date >= ?"]
    args: list[Any] = [year_id, s, s]
    if group_label is not None:
        clauses.append("(group_label IS NULL OR group_label = ?)")
        args.append(group_label)
    else:
        clauses.append("group_label IS NULL")
    with _connect() as conn:
        r = conn.execute(
            f"SELECT * FROM academic_breaks WHERE {' AND '.join(clauses)} "
            # Prefer a full-day closure over a half day, and a
            # group-specific row over the college-wide one.
            "ORDER BY am_pm = 'FULL' DESC, group_label IS NULL ASC, "
            "start_date ASC LIMIT 1",
            args).fetchone()
        return _row_break(r) if r else None


def teaching_days_in(
    year_id: int, *,
    date_from: str | None = None,
    date_to: str | None = None,
    group_label: str | None = None,
    half_days: bool = False,
) -> float:
    """Teaching days in [from, to] — Mon–Fri, minus closures. Defaults
    to the full year span.

    A day is worth 1.0 when the college is open all day, 0.5 when an
    AM- or PM-only break closes half of it, and 0.0 when a full-day
    break covers it or it falls inside a term marked non-teaching
    (study leave). With ``half_days=False`` (the default) the halves
    are rounded back up to whole days, so the return value is a whole
    number; pass ``half_days=True`` for the exact figure an attendance
    denominator wants.

    With no ``group_label`` only college-wide rows apply, so a
    Y13-only study-leave block doesn't shrink the whole college's
    denominator. Pass a label to count that group's own calendar.
    """
    year = get_year(year_id)
    if year is None:
        raise ValidationError(f"No academic year #{year_id}")
    df = _validate_date(date_from or year.start_date, "From")
    dt = _validate_date(date_to or year.end_date, "To")
    if dt < df:
        return 0.0
    breaks = _break_ranges(year_id, group_label=group_label)
    closed = _non_teaching_term_ranges(year_id, group_label=group_label)

    start = _dt.date.fromisoformat(df)
    end = _dt.date.fromisoformat(dt)
    total = 0.0
    cur = start
    one = _dt.timedelta(days=1)
    while cur <= end:
        # Mon=0..Fri=4; exclude Sat=5 / Sun=6
        if cur.weekday() < 5:
            total += _day_weight(cur.isoformat(), breaks, closed,
                                   half_days=half_days)
        cur += one
    return total if half_days else int(total)


def _day_weight(date_iso: str,
                 breaks: list[tuple[str, str, str]],
                 closed: list[tuple[str, str]], *,
                 half_days: bool) -> float:
    """How much of one weekday is taught: 1.0, 0.5, or 0.0."""
    if any(s <= date_iso <= e for (s, e) in closed):
        return 0.0
    covering = [ap for (s, e, ap) in breaks if s <= date_iso <= e]
    if not covering:
        return 1.0
    if "FULL" in covering:
        return 0.0
    if not half_days:
        # An AM-only INSET still leaves an afternoon of teaching —
        # don't drop the whole day from a whole-day count.
        return 1.0
    # AM and PM breaks on the same day add up to a full closure.
    return 0.0 if {"AM", "PM"} <= set(covering) else 0.5


def _non_teaching_term_ranges(year_id: int, *,
                               group_label: str | None = None
                               ) -> list[tuple[str, str]]:
    """Ranges covered by a term flagged ``is_teaching = 0``."""
    return [(t.start_date, t.end_date)
            for t in list_terms(year_id=year_id,
                                  group_label=group_label)
            if not t.is_teaching
            and (group_label is not None or t.group_label is None)]


def teaching_sessions_in(
    year_id: int, *,
    date_from: str | None = None,
    date_to: str | None = None,
    group_label: str | None = None,
) -> int:
    """The same window counted in AM/PM sessions — two per full day,
    one per half day. The unit an attendance register actually uses.
    """
    days = teaching_days_in(year_id, date_from=date_from,
                              date_to=date_to, group_label=group_label,
                              half_days=True)
    return int(round(days * 2))


def year_summary(year_id: int, *,
                  group_label: str | None = None) -> YearSummary:
    year = get_year(year_id)
    if year is None:
        raise ValidationError(f"No academic year #{year_id}")
    terms = list_terms(year_id=year_id, group_label=group_label)
    breaks = list_breaks(year_id=year_id, group_label=group_label)

    teaching = teaching_days_in(year_id, group_label=group_label)
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
