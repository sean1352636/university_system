"""Enrolment data layer for the Sixth Form System.

An *enrolment* is a per-academic-year record linking a student to a
year group, tutor group, and status. A student typically gets two
enrolments across their sixth-form career (Year 12 + Year 13) but the
model allows any number (e.g. resit years).

Shares the same SQLite file as `students` so cross-table joins and
``ON DELETE CASCADE`` from ``students.student_id`` just work.

Rules:

* **Reads are open** — the Student Directory, bulk operations, exports
  and the student screens all read enrolments without the admissions
  capability. **Writes** (create / update / withdraw / archive / restore
  / rollover) need ``admissions`` or ``students.manage``.
* **Nothing is hard-deleted.** :func:`archive_enrolment` (and
  :func:`delete_enrolment`, which archives) stamps
  ``archived_at/by/reason``; lists leave archived rows out unless asked,
  and :func:`restore_enrolment` brings the same row (same id) back.
* **Withdrawal** (:func:`withdraw_enrolment`) records the last day in
  learning and an ILR-style reason (:data:`WITHDRAWAL_REASONS`) and ends
  the learner's active learning aims through the learning-aims module.
* **Rollover** (:func:`rollover`) completes Year 13 and moves Year 12
  into Year 13, skipping learners who are no longer on roll.
* ``recorded_by`` is the signed-in user who created the row.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ENROLMENTS_DB

YEAR_GROUPS: tuple[int, ...] = (12, 13)
STATUSES: tuple[str, ...] = ("Enrolled", "Pending", "Withdrawn", "Completed")
DEFAULT_STATUS: str = "Enrolled"

_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}/\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrolments (
    enrolment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    academic_year  TEXT NOT NULL,
    year_group     INTEGER NOT NULL,
    tutor_group    TEXT,
    start_date     TEXT,
    status         TEXT NOT NULL DEFAULT 'Enrolled',
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, academic_year),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_enrolments_student ON enrolments(student_id);
CREATE INDEX IF NOT EXISTS idx_enrolments_year    ON enrolments(academic_year);
CREATE INDEX IF NOT EXISTS idx_enrolments_status  ON enrolments(status);
"""

#: Columns added after the original schema (name, DDL type).
_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("recorded_by", "TEXT"),
    ("updated_at", "TEXT"),
    ("withdrawal_date", "TEXT"),
    ("withdrawal_reason", "TEXT"),
    ("withdrawal_detail", "TEXT"),
    ("withdrawn_by", "TEXT"),
    ("archived_at", "TEXT"),
    ("archived_by", "TEXT"),
    ("archived_reason", "TEXT"),
    ("return_intention", "TEXT"),
    ("return_intention_note", "TEXT"),
    ("completed_at", "TEXT"),
)

#: Tables added with the lifecycle rules (2026-10-27): an audit trail of
#: every enrolment write, the aims each withdrawal ended (so a
#: reinstatement can reopen exactly those) and a log of rollover runs (so
#: a run can be undone).
_LIFECYCLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrolment_history (
    history_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    enrolment_id   INTEGER NOT NULL,
    student_id     TEXT NOT NULL,
    action         TEXT NOT NULL,
    detail         TEXT,
    changed_by     TEXT,
    changed_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (enrolment_id) REFERENCES enrolments(enrolment_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_enrol_hist_enrolment
    ON enrolment_history(enrolment_id);
CREATE INDEX IF NOT EXISTS idx_enrol_hist_student
    ON enrolment_history(student_id);

CREATE TABLE IF NOT EXISTS enrolment_aim_withdrawals (
    enrolment_id   INTEGER NOT NULL,
    aim_id         INTEGER NOT NULL,
    withdrawn_on   TEXT,
    reopened_at    TEXT,
    PRIMARY KEY (enrolment_id, aim_id),
    FOREIGN KEY (enrolment_id) REFERENCES enrolments(enrolment_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS enrolment_rollovers (
    run_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    from_year      TEXT NOT NULL,
    to_year        TEXT NOT NULL,
    run_by         TEXT,
    run_at         TEXT DEFAULT (datetime('now')),
    changes        TEXT NOT NULL,
    undone_at      TEXT,
    undone_by      TEXT
);
"""

#: Status moves an ordinary edit may make. ``Withdrawn`` is reached only
#: through :func:`withdraw_enrolment` (ILR reason, aims ended) and left
#: only through :func:`reinstate_enrolment` (aims reopened);
#: ``Completed`` is set by :func:`rollover` / leaving at the end of the
#: course and undone with :func:`reopen_enrolment`.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "Pending": ("Enrolled",),
    "Enrolled": ("Pending",),
    "Withdrawn": (),
    "Completed": (),
}

#: Statuses an enrolment may be created with. ``Completed`` only for a
#: year that has already ended (entering history).
CREATE_STATUSES: tuple[str, ...] = ("Enrolled", "Pending", "Completed")

#: Statuses that mean the learner is (or is about to be) in learning.
LIVE_STATUSES: tuple[str, ...] = ("Enrolled", "Pending")

#: Year 12 → 13 re-enrolment answers.
RETURN_INTENTIONS: tuple[str, ...] = ("Returning", "Not returning",
                                      "Undecided")

#: ILR ``WithdrawReason`` codes that apply to a 16-19 study programme,
#: as (code, label).
WITHDRAWAL_REASONS: tuple[tuple[str, str], ...] = (
    ("2", "Transferred to another provider"),
    ("3", "Injury or illness"),
    ("7", "Transferred between providers by intervention of / agreement "
          "with the funding agency"),
    ("29", "Made redundant"),
    ("40", "Transferred to a new learning aim with the same provider"),
    ("41", "Transferred to another provider to undertake learning that "
           "meets a specific government strategy"),
    ("43", "Financial reasons"),
    ("44", "Other personal reasons"),
    ("46", "Exclusion"),
    ("97", "Other"),
    ("98", "Reason not known"),
)
_WITHDRAWAL_LABELS: dict[str, str] = dict(WITHDRAWAL_REASONS)


def withdrawal_reason_label(code: str | None) -> str | None:
    """``"44 — Other personal reasons"`` for a stored code (None if unset)."""
    if not code:
        return None
    label = _WITHDRAWAL_LABELS.get(code)
    return f"{code} — {label}" if label else code


@dataclass
class Enrolment:
    enrolment_id: int
    student_id: str
    academic_year: str
    year_group: int
    tutor_group: str | None
    start_date: str | None
    status: str
    notes: str | None
    created_at: str
    recorded_by: str | None = None
    updated_at: str | None = None
    withdrawal_date: str | None = None
    withdrawal_reason: str | None = None
    withdrawal_detail: str | None = None
    withdrawn_by: str | None = None
    archived_at: str | None = None
    archived_by: str | None = None
    archived_reason: str | None = None
    return_intention: str | None = None
    return_intention_note: str | None = None
    completed_at: str | None = None

    @property
    def is_live(self) -> bool:
        """Enrolled or Pending, and not archived."""
        return self.status in LIVE_STATUSES and not self.is_archived

    @property
    def is_archived(self) -> bool:
        return bool(self.archived_at)

    @property
    def withdrawal_reason_label(self) -> str | None:
        return withdrawal_reason_label(self.withdrawal_reason)


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    # Ensure the students schema exists too, since our FK references it.
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        have = {r["name"] for r in conn.execute(
            "PRAGMA table_info(enrolments)").fetchall()}
        for name, ddl in _ADDED_COLUMNS:
            if name not in have:
                conn.execute(
                    f"ALTER TABLE enrolments ADD COLUMN {name} {ddl}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_enrolments_archived "
                     "ON enrolments(archived_at)")
        conn.executescript(_LIFECYCLE_SCHEMA)
        conn.commit()
    logger.debug("Enrolments schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> Enrolment:
    keys = set(r.keys())
    extra = {name: r[name] for name, _ddl in _ADDED_COLUMNS if name in keys}
    return Enrolment(
        enrolment_id=r["enrolment_id"],
        student_id=r["student_id"],
        academic_year=r["academic_year"],
        year_group=r["year_group"],
        tutor_group=r["tutor_group"],
        start_date=r["start_date"],
        status=r["status"],
        notes=r["notes"],
        created_at=r["created_at"],
        **extra,
    )


# ── Who may write ───────────────────────────────────────────────────

def _require_writer(action: str) -> Any:
    """Writes need ``admissions`` or ``students.manage``; reads are open."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return _guard.require_any((access.ADMISSIONS, access.STUDENTS_MANAGE),
                              action)


def _actor() -> str | None:
    from education_system.systems.sixth_form.domain.admissions import _guard
    return _guard.actor()


def can_write() -> bool:
    """Whether the signed-in user may change enrolments (for screens)."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return _guard.can(access.ADMISSIONS) or _guard.can(access.STUDENTS_MANAGE)


def _can_see_detail() -> bool:
    """Withdrawal detail is free text (illness, exclusion…): only staff
    who manage enrolments, or safeguarding, see it."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return can_write() or _guard.can(access.SAFEGUARDING)


RESTRICTED = "(restricted)"


def _visible(e: Enrolment, see_detail: bool) -> Enrolment:
    if e.withdrawal_detail and not see_detail:
        e.withdrawal_detail = RESTRICTED
    return e


def _log(conn: sqlite3.Connection, e: Enrolment | dict[str, Any], action: str,
         detail: str | None = None) -> None:
    """One row in ``enrolment_history`` (same transaction as the write)."""
    eid = e["enrolment_id"] if isinstance(e, dict) else e.enrolment_id
    sid = e["student_id"] if isinstance(e, dict) else e.student_id
    conn.execute(
        "INSERT INTO enrolment_history (enrolment_id, student_id, action, "
        "detail, changed_by) VALUES (?, ?, ?, ?, ?)",
        (eid, sid, action, detail, _actor()))


def enrolment_history(*, enrolment_id: int | None = None,
                      student_id: str | None = None,
                      limit: int = 500) -> list[dict[str, Any]]:
    """The audit trail, newest first."""
    init_db()
    clauses, args = [], []
    if enrolment_id is not None:
        clauses.append("enrolment_id = ?")
        args.append(enrolment_id)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM enrolment_history {where} "  # noqa: S608 — fixed clauses
            "ORDER BY history_id DESC LIMIT ?", (*args, limit)).fetchall()
    return [dict(r) for r in rows]


# ── Academic years ──────────────────────────────────────────────────

def _register_year(academic_year: str):
    try:
        from education_system.systems.sixth_form.domain.academics.academic_year import (
            academic_year as _ay,
        )
        return _ay.get_year_by_name(academic_year)
    except Exception:  # noqa: BLE001 — the register is optional here
        logger.debug("academic year register not read", exc_info=True)
        return None


def academic_year_dates(academic_year: str) -> tuple[str, str]:
    """(first day, last day) of an academic year: the register's dates
    when the year is set up there, else 1 August – 31 July."""
    if not _ACADEMIC_YEAR_RE.match(academic_year or ""):
        raise ValidationError("Academic year must look like '2025/26'")
    y = _register_year(academic_year)
    if y is not None and y.start_date and y.end_date:
        return y.start_date, y.end_date
    first = int(academic_year[:4])
    return f"{first}-08-01", f"{first + 1}-07-31"


def academic_year_for_date(day: str | None = None) -> str:
    d = _dt.date.fromisoformat(day) if day else _dt.date.today()
    first = d.year if d.month >= 8 else d.year - 1
    return f"{first}/{str(first + 1)[-2:]}"


def current_academic_year() -> str:
    """The register's current year when it names one like ``2025/26``,
    else the year today falls in (1 August boundary)."""
    try:
        from education_system.systems.sixth_form.domain.academics.academic_year import (
            academic_year as _ay,
        )
        y = _ay.current_year()
        if y is not None and _ACADEMIC_YEAR_RE.match(y.name or ""):
            return y.name
    except Exception:  # noqa: BLE001
        logger.debug("current academic year not read", exc_info=True)
    return academic_year_for_date()


def known_academic_years() -> list[str]:
    """Years for pickers: the register's, plus any already used, newest
    first."""
    years: set[str] = set()
    try:
        from education_system.systems.sixth_form.domain.academics.academic_year import (
            academic_year as _ay,
        )
        years |= {y.name for y in _ay.list_years()
                  if _ACADEMIC_YEAR_RE.match(y.name or "")}
    except Exception:  # noqa: BLE001
        logger.debug("academic year register not read", exc_info=True)
    init_db()
    with _connect() as conn:
        years |= {r[0] for r in conn.execute(
            "SELECT DISTINCT academic_year FROM enrolments")}
    years.add(current_academic_year())
    return sorted(years, reverse=True)


# ── Tutor groups ────────────────────────────────────────────────────

def _tutor_groups():
    from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
        tutor_groups as _tg,
    )
    return _tg


def _check_tutor_group(name: str | None, year_group: int) -> None:
    """Once tutor groups are set up, an enrolment's group must be one of
    them, for the right year. (Before any exist, free text is kept.)"""
    if not name:
        return
    tg = _tutor_groups()
    groups = tg.list_groups()
    if not groups:
        return
    group = tg.get_group_by_name(name)
    if group is None:
        raise ValidationError(
            f"There is no tutor group called {name!r} — pick one of: "
            + ", ".join(sorted(g.name for g in groups
                               if g.year_group == year_group)))
    if group.year_group != year_group:
        raise ValidationError(
            f"Tutor group {name} is a Year {group.year_group} group, not "
            f"Year {year_group}")


def _sync_tutor_membership(student_id: str) -> str | None:
    """Put the learner in the tutor group named on their current live
    enrolment (the membership table holds one group per learner).
    Returns a note of what changed, or None."""
    try:
        cur = current_enrolment(student_id)
        if cur is None or not cur.is_live or not cur.tutor_group:
            return None
        tg = _tutor_groups()
        group = tg.get_group_by_name(cur.tutor_group)
        if group is None:
            return None
        now = tg.group_for_student(student_id)
        if now is not None and now.tutor_group_id == group.tutor_group_id:
            return None
        tg.assign_student(student_id, group.tutor_group_id)
        return f"{student_id} moved to tutor group {group.name}"
    except Exception:  # noqa: BLE001 — membership is reported, never blocks
        logger.exception("Tutor group membership not synced for %s", student_id)
        return None


def allowed_statuses(e: Enrolment) -> tuple[str, ...]:
    """Statuses an edit form may offer for ``e`` (its own first)."""
    return (e.status, *TRANSITIONS.get(e.status, ()))


# ── Validation ──────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid enrolment-form input."""


def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _validate_payload(data: dict[str, Any], *, expect_student: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if expect_student:
        out["student_id"] = _require(data.get("student_id"), "Student ID")

    year = _require(data.get("academic_year"), "Academic year")
    if not _ACADEMIC_YEAR_RE.match(year) \
            or int(year[5:7]) != (int(year[:4]) + 1) % 100:
        raise ValidationError("Academic year must look like '2025/26'")
    out["academic_year"] = year

    yg_raw = data.get("year_group")
    if yg_raw is None or yg_raw == "":
        raise ValidationError("Year group is required")
    try:
        yg = int(yg_raw)
    except (TypeError, ValueError):
        raise ValidationError("Year group must be a whole number") from None
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(str(y) for y in YEAR_GROUPS)}")
    out["year_group"] = yg

    out["tutor_group"] = (data.get("tutor_group") or "").strip() or None

    sd = (data.get("start_date") or "").strip()
    if sd and not _DATE_RE.match(sd):
        raise ValidationError("Start date must be YYYY-MM-DD")
    out["start_date"] = sd or None

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# ── CRUD ────────────────────────────────────────────────────────────

def _archived_clash(conn: sqlite3.Connection, student_id: str,
                    academic_year: str, exclude_id: int | None = None
                    ) -> int | None:
    row = conn.execute(
        "SELECT enrolment_id FROM enrolments WHERE student_id = ? AND "
        "academic_year = ? AND archived_at IS NOT NULL AND enrolment_id != ?",
        (student_id, academic_year, exclude_id or -1)).fetchone()
    return row["enrolment_id"] if row else None


def _check_dates(payload: dict[str, Any]) -> None:
    sd = payload.get("start_date")
    if not sd:
        return
    try:
        _dt.date.fromisoformat(sd)
    except ValueError:
        raise ValidationError("Start date is not a real date") from None
    first, last = academic_year_dates(payload["academic_year"])
    if not (first <= sd <= last):
        raise ValidationError(
            f"Start date {sd} is outside {payload['academic_year']} "
            f"({first} to {last})")


def _check_year_order(conn: sqlite3.Connection, student_id: str,
                      academic_year: str, year_group: int,
                      exclude_id: int | None = None) -> None:
    """Year 13 can't come before the learner's Year 12, nor Year 12 after
    their Year 13 (resit years repeat a year group, which is fine)."""
    for r in conn.execute(
            "SELECT academic_year, year_group FROM enrolments WHERE "
            "student_id = ? AND archived_at IS NULL AND enrolment_id != ?",
            (student_id, exclude_id or -1)):
        if year_group == 13 and r["year_group"] == 12 \
                and academic_year < r["academic_year"]:
            raise ValidationError(
                f"Year 13 in {academic_year} would come before their Year 12 "
                f"({r['academic_year']})")
        if year_group == 12 and r["year_group"] == 13 \
                and academic_year > r["academic_year"]:
            raise ValidationError(
                f"Year 12 in {academic_year} would come after their Year 13 "
                f"({r['academic_year']})")


def create_enrolment(data: dict[str, Any]) -> Enrolment:
    """Insert a new enrolment row. Raises ``ValidationError`` on bad
    input, when the student doesn't exist or isn't on roll, when the start
    date is outside the academic year, when the year groups would be out
    of order or when the tutor group isn't a real one. Needs
    ``admissions`` or ``students.manage``; ``recorded_by`` is the signed-in
    user (a caller-supplied value is used only when nobody is signed in,
    e.g. an import job)."""
    init_db()
    _require_writer("creating enrolments")
    try:
        payload = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_enrolment validation failed: %s", e)
        raise
    if payload["status"] not in CREATE_STATUSES:
        raise ValidationError(
            f"A new enrolment can't start as {payload['status']} — create it "
            "as Enrolled or Pending, then withdraw it")
    if payload["status"] == "Completed":
        _first, last = academic_year_dates(payload["academic_year"])
        if last >= _dt.date.today().isoformat():
            raise ValidationError(
                f"{payload['academic_year']} hasn't ended, so the enrolment "
                "can't be created as Completed")

    sid = payload["student_id"]
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    student = _students.get_student(sid)
    if student is None:
        logger.warning("create_enrolment: unknown student_id %s", sid)
        raise ValidationError(f"No student with id {sid}")
    if student.status not in _students.ON_ROLL_STATUSES \
            and payload["status"] != "Completed":
        raise ValidationError(
            f"{sid} is {student.status}, not on roll — reinstate the student "
            "before enrolling them")
    _check_dates(payload)
    _check_tutor_group(payload["tutor_group"], payload["year_group"])
    who = _actor() or (data.get("recorded_by") or "").strip() or None

    try:
        with _connect() as conn:
            archived = _archived_clash(conn, sid, payload["academic_year"])
            if archived:
                raise ValidationError(
                    f"{sid} has an archived enrolment for "
                    f"{payload['academic_year']} (#{archived}); restore it "
                    "instead of creating another")
            _check_year_order(conn, sid, payload["academic_year"],
                              payload["year_group"])
            cur = conn.execute(
                """
                INSERT INTO enrolments
                    (student_id, academic_year, year_group, tutor_group,
                     start_date, status, notes, recorded_by, updated_at,
                     completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
                """,
                (
                    sid,
                    payload["academic_year"],
                    payload["year_group"],
                    payload["tutor_group"],
                    payload["start_date"],
                    payload["status"],
                    payload["notes"],
                    who,
                    _dt.date.today().isoformat()
                    if payload["status"] == "Completed" else None,
                ),
            )
            new_id = cur.lastrowid
            _log(conn, {"enrolment_id": new_id, "student_id": sid}, "Created",
                 f"{payload['academic_year']} Year {payload['year_group']} "
                 f"{payload['status']}"
                 + (f", tutor group {payload['tutor_group']}"
                    if payload["tutor_group"] else ""))
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            logger.warning(
                "create_enrolment: duplicate (%s, %s)",
                sid, payload["academic_year"],
            )
            raise ValidationError(
                f"{sid} already has an enrolment for {payload['academic_year']}"
            ) from e
        logger.exception("create_enrolment DB error")
        raise ValidationError(f"Database error: {e}") from e

    enrolment = get_enrolment(new_id)
    assert enrolment is not None
    _sync_tutor_membership(sid)
    logger.info(
        "Created enrolment #%d for %s (%s, Year %d, status=%s, by %s)",
        new_id, sid, payload["academic_year"], payload["year_group"],
        payload["status"], who,
    )
    return enrolment


def get_enrolment(enrolment_id: int) -> Enrolment | None:
    """One enrolment by id, archived or not."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM enrolments WHERE enrolment_id = ?", (enrolment_id,)
        ).fetchone()
    return _visible(_row(row), _can_see_detail()) if row else None


def _get(enrolment_id: int) -> Enrolment | None:
    """Unmasked read for this module's own writes."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM enrolments WHERE enrolment_id = ?", (enrolment_id,)
        ).fetchone()
    return _row(row) if row else None


def list_enrolments(
    *,
    student_id: str | None = None,
    academic_year: str | None = None,
    year_group: int | None = None,
    status: str | None = None,
    include_archived: bool = False,
    archived_only: bool = False,
) -> list[Enrolment]:
    """Enrolments matching the filters; archived rows are left out unless
    ``include_archived`` (or ``archived_only``)."""
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if archived_only:
        clauses.append("archived_at IS NOT NULL")
    elif not include_archived:
        clauses.append("archived_at IS NULL")
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(academic_year)
    if year_group is not None:
        clauses.append("year_group = ?")
        args.append(year_group)
    if status:
        clauses.append("status = ?")
        args.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT * FROM enrolments "
        f"{where} ORDER BY academic_year DESC, year_group, student_id"
    )
    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    see = _can_see_detail()
    return [_visible(_row(r), see) for r in rows]


def list_for_student(student_id: str) -> list[Enrolment]:
    return list_enrolments(student_id=student_id)


def current_enrolment(student_id: str) -> Enrolment | None:
    """Return the student's *current* enrolment, or None if never enrolled.

    "Current" = the most recent academic year, preferring an active
    ``Enrolled`` record over a withdrawn/completed one. This is the source of
    truth for a student's current year group — it is never stored on the
    student record itself, so it can't drift. Archived rows never count.
    """
    enrolments = list_for_student(student_id)  # ordered academic_year DESC
    if not enrolments:
        return None
    for enrolment in enrolments:
        if enrolment.status == "Enrolled":
            return enrolment
    return enrolments[0]


def current_year_group_label(student_id: str) -> str | None:
    """Human label for a student's current year group, e.g.
    ``"Year 13 (2025/26)"``. None if the student has no enrolment.

    A non-active latest enrolment is annotated with its status
    (e.g. ``"Year 13 (2025/26) — Withdrawn"``).
    """
    enrolment = current_enrolment(student_id)
    if enrolment is None:
        return None
    label = f"Year {enrolment.year_group} ({enrolment.academic_year})"
    if enrolment.status != "Enrolled":
        label += f" — {enrolment.status}"
    return label


def _bump_tutor_group(old_year: int, new_year: int,
                      name: str | None) -> str | None:
    """Replace the leading digit run on a tutor-group name with
    ``new_year`` so the group follows the student up (e.g. ``12A`` →
    ``13A``). If the year hasn't changed, or the name has no
    leading-digit prefix, returns it untouched."""
    if not name or old_year == new_year:
        return name
    i = 0
    while i < len(name) and name[i].isdigit():
        i += 1
    if i == 0:
        return name
    return str(new_year) + name[i:]


def _validate_withdrawal(date_value: Any, reason: Any, *,
                         start_date: str | None) -> tuple[str, str | None]:
    wd = (str(date_value or "")).strip() or _dt.date.today().isoformat()
    if not _DATE_RE.match(wd):
        raise ValidationError("Withdrawal date must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(wd)
    except ValueError:
        raise ValidationError("Withdrawal date is not a real date") from None
    if start_date and wd < start_date:
        raise ValidationError(
            f"Withdrawal date {wd} is before the enrolment started "
            f"({start_date})")
    code = (str(reason or "")).strip() or None
    if code and code not in _WITHDRAWAL_LABELS:
        # Accept the label as well as the code.
        code = next((c for c, label in WITHDRAWAL_REASONS
                     if label.lower() == code.lower()), None) or code
        if code not in _WITHDRAWAL_LABELS:
            raise ValidationError(
                "Withdrawal reason must be one of the ILR codes: "
                + ", ".join(f"{c} {label}" for c, label in WITHDRAWAL_REASONS))
    return wd, code


def update_enrolment(enrolment_id: int, data: dict[str, Any]) -> Enrolment:
    """Update an enrolment. ``student_id`` is immutable (see
    :func:`transfer_enrolment`); an archived row must be restored first.

    Status moves follow :data:`TRANSITIONS`: withdrawing goes through
    :func:`withdraw_enrolment`, coming back from a withdrawal through
    :func:`reinstate_enrolment`, and reopening a completed year through
    :func:`reopen_enrolment` — each of those also keeps the learning aims
    and the student record in step, which a plain edit can't. A withdrawn
    enrolment's withdrawal date, reason and detail can still be corrected
    here (``data["withdrawal_date"]`` / ``["withdrawal_reason"]`` /
    ``["withdrawal_detail"]``).
    """
    init_db()
    _require_writer("changing enrolments")
    existing = _get(enrolment_id)
    if existing is None:
        logger.warning("update_enrolment: unknown id %d", enrolment_id)
        raise ValidationError(f"No enrolment with id {enrolment_id}")
    if existing.is_archived:
        raise ValidationError(
            f"Enrolment #{enrolment_id} is archived; restore it first")

    try:
        payload = _validate_payload(data, expect_student=False)
    except ValidationError as e:
        logger.warning("update_enrolment(%d) validation failed: %s", enrolment_id, e)
        raise
    new_status = payload["status"]
    if new_status != existing.status \
            and new_status not in TRANSITIONS.get(existing.status, ()):
        if new_status == "Withdrawn":
            hint = ("use Withdraw, which records the ILR reason and ends the "
                    "learning aims")
        elif existing.status == "Withdrawn":
            hint = "use Reinstate, which reopens the learning aims it ended"
        elif existing.status == "Completed":
            hint = "use Reopen, with a reason"
        else:
            hint = "completing happens at rollover or when the learner leaves"
        raise ValidationError(
            f"Can't change the status from {existing.status} to "
            f"{new_status} here — {hint}")

    # If the year_group changed but tutor_group wasn't manually edited,
    # bump the group prefix (e.g. 12A -> 13A) to follow the student.
    if (payload["year_group"] != existing.year_group
            and payload["tutor_group"] == existing.tutor_group):
        payload["tutor_group"] = _bump_tutor_group(
            existing.year_group, payload["year_group"], existing.tutor_group)
    if payload["tutor_group"] != existing.tutor_group \
            or payload["year_group"] != existing.year_group:
        _check_tutor_group(payload["tutor_group"], payload["year_group"])
    if payload["start_date"] != existing.start_date \
            or payload["academic_year"] != existing.academic_year:
        _check_dates(payload)

    wd, code, detail, by = (existing.withdrawal_date,
                            existing.withdrawal_reason,
                            existing.withdrawal_detail, existing.withdrawn_by)
    if new_status == "Withdrawn" and ("withdrawal_date" in data
                                      or "withdrawal_reason" in data
                                      or "withdrawal_detail" in data):
        wd, code = _validate_withdrawal(
            data.get("withdrawal_date", wd),
            data.get("withdrawal_reason", code),
            start_date=payload["start_date"])
        if not code:
            raise ValidationError("A withdrawal reason is required")
        new_detail = data.get("withdrawal_detail", detail)
        if new_detail != RESTRICTED:
            detail = (new_detail or "").strip() or None

    changes = [f"{label}: {old or '—'} → {new or '—'}"
               for label, old, new in (
                   ("Year", existing.academic_year, payload["academic_year"]),
                   ("Year group", existing.year_group, payload["year_group"]),
                   ("Tutor group", existing.tutor_group, payload["tutor_group"]),
                   ("Start", existing.start_date, payload["start_date"]),
                   ("Status", existing.status, new_status),
                   ("Withdrawn on", existing.withdrawal_date, wd),
                   ("Reason", existing.withdrawal_reason, code))
               if old != new]
    if payload["notes"] != existing.notes:
        changes.append("Notes changed")
    if detail != existing.withdrawal_detail:
        changes.append("Withdrawal detail changed")

    try:
        with _connect() as conn:
            if payload["academic_year"] != existing.academic_year \
                    or payload["year_group"] != existing.year_group:
                _check_year_order(conn, existing.student_id,
                                  payload["academic_year"],
                                  payload["year_group"],
                                  exclude_id=enrolment_id)
            conn.execute(
                """
                UPDATE enrolments SET
                    academic_year = ?, year_group = ?, tutor_group = ?,
                    start_date = ?, status = ?, notes = ?,
                    withdrawal_date = ?, withdrawal_reason = ?,
                    withdrawal_detail = ?, withdrawn_by = ?,
                    updated_at = datetime('now')
                WHERE enrolment_id = ?
                """,
                (
                    payload["academic_year"],
                    payload["year_group"],
                    payload["tutor_group"],
                    payload["start_date"],
                    new_status,
                    payload["notes"],
                    wd, code, detail, by,
                    enrolment_id,
                ),
            )
            if changes:
                _log(conn, existing, "Updated", "; ".join(changes))
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            logger.warning(
                "update_enrolment(%d): duplicate (%s, %s)",
                enrolment_id, existing.student_id, payload["academic_year"],
            )
            raise ValidationError(
                f"{existing.student_id} already has an enrolment for "
                f"{payload['academic_year']}"
            ) from e
        logger.exception("update_enrolment DB error")
        raise ValidationError(f"Database error: {e}") from e

    if payload["tutor_group"] != existing.tutor_group:
        _sync_tutor_membership(existing.student_id)
    enrolment = get_enrolment(enrolment_id)
    assert enrolment is not None
    logger.info("Updated enrolment #%d (status=%s)", enrolment_id, new_status)
    return enrolment


def set_return_intention(enrolment_id: int, intention: str | None, *,
                         note: str | None = None) -> Enrolment:
    """Record a Year 12 learner's answer to "are you coming back for Year
    13?" (:data:`RETURN_INTENTIONS`, or None to clear). :func:`rollover`
    can require ``Returning`` and never moves a ``Not returning`` learner
    up."""
    init_db()
    _require_writer("recording re-enrolment intentions")
    e = _get(enrolment_id)
    if e is None or e.is_archived:
        raise ValidationError(f"No live enrolment with id {enrolment_id}")
    if intention is not None and intention not in RETURN_INTENTIONS:
        raise ValidationError(
            f"Intention must be one of: {', '.join(RETURN_INTENTIONS)}")
    with _connect() as conn:
        conn.execute(
            "UPDATE enrolments SET return_intention = ?, "
            "return_intention_note = ?, updated_at = datetime('now') "
            "WHERE enrolment_id = ?",
            (intention, (note or "").strip() or None, enrolment_id))
        _log(conn, e, "Return intention",
             f"{e.return_intention or '—'} → {intention or '—'}"
             + (f" ({note.strip()})" if note and note.strip() else ""))
        conn.commit()
    out = get_enrolment(enrolment_id)
    assert out is not None
    return out


def reintention_summary(academic_year: str) -> dict[str, int]:
    """Counts of Year 12 return intentions for a year (``Unanswered``
    for none recorded)."""
    out = {k: 0 for k in (*RETURN_INTENTIONS, "Unanswered")}
    for e in list_enrolments(academic_year=academic_year, year_group=12):
        if e.status != "Enrolled":
            continue
        out[e.return_intention or "Unanswered"] += 1
    return out


# ── Withdrawal ──────────────────────────────────────────────────────

@dataclass
class WithdrawalResult:
    enrolment: Enrolment
    aims_ended: list[str] = field(default_factory=list)
    aim_problems: list[str] = field(default_factory=list)
    student_left: bool = False
    student_notes: list[str] = field(default_factory=list)


def _aims_module():
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims as _aims,
    )
    return _aims


def aims_for_enrolment(e: Enrolment, *, active_only: bool = True) -> list[Any]:
    """The learning aims that belong to an enrolment's year.

    Aims carry no enrolment id, so this is by date: an aim belongs to the
    enrolment when it started on or before the end of the enrolment's
    year — except that an aim running on past the year end is left to
    the learner's *later* live enrolment when there is one (a two-year
    A level withdrawn from in Year 12 stays with Year 13 if that is still
    open), and aims that started after the year belong to a later one.
    """
    aims = _aims_module()
    _first, last = academic_year_dates(e.academic_year)
    later_live = any(o.is_live and o.academic_year > e.academic_year
                     for o in list_for_student(e.student_id)
                     if o.enrolment_id != e.enrolment_id)
    rows = (aims.active_aims(e.student_id) if active_only
            else aims.list_aims(e.student_id))
    out = []
    for aim in rows:
        if aim.start_date and aim.start_date > last:
            continue
        if later_live and aim.planned_end_date and aim.planned_end_date > last:
            continue
        out.append(aim)
    return out


def withdraw_enrolment(enrolment_id: int, *, withdrawal_date: str | None,
                       reason: str, detail: str | None = None,
                       approved_by: str | None = None,
                       update_student: bool = True) -> WithdrawalResult:
    """Withdraw a learner from an enrolment.

    ``withdrawal_date`` is the last day in learning (default today) and
    ``reason`` an ILR withdrawal-reason code (or its label, see
    :data:`WITHDRAWAL_REASONS`). The enrolment's active learning aims
    (:func:`aims_for_enrolment`) that started on or before that date are
    withdrawn through ``learning_aims.withdraw_aim``, which sets their
    actual end date and keeps the qualifying-period check; the aims ended
    are remembered so :func:`reinstate_enrolment` can reopen them. Aims
    that could not be ended are listed in ``aim_problems``.

    When ``update_student`` and this was the learner's last live
    enrolment, the student record is marked as having left
    (``students.withdraw_student``: leaving date, tutor group, logins,
    class groups and the other leaver steps).
    """
    init_db()
    _require_writer("withdrawing enrolments")
    e = _get(enrolment_id)
    if e is None:
        raise ValidationError(f"No enrolment with id {enrolment_id}")
    if e.is_archived:
        raise ValidationError(
            f"Enrolment #{enrolment_id} is archived; restore it first")
    if e.status == "Withdrawn":
        raise ValidationError(f"Enrolment #{enrolment_id} is already withdrawn")
    if e.status == "Completed":
        raise ValidationError(
            f"Enrolment #{enrolment_id} is completed — reopen it before "
            "withdrawing")
    if not (str(reason or "")).strip():
        raise ValidationError("A withdrawal reason is required")
    wd, code = _validate_withdrawal(withdrawal_date, reason,
                                    start_date=e.start_date)
    detail = (detail or "").strip() or None
    try:
        own_aims = aims_for_enrolment(e)
    except Exception as exc:  # noqa: BLE001 — reported, the withdrawal stands
        logger.exception("withdraw_enrolment(%d): learning aims", enrolment_id)
        own_aims = None
        aims_error = str(exc)
    who = _actor()
    with _connect() as conn:
        conn.execute(
            "UPDATE enrolments SET status = 'Withdrawn', withdrawal_date = ?, "
            "withdrawal_reason = ?, withdrawal_detail = ?, withdrawn_by = ?, "
            "updated_at = datetime('now') WHERE enrolment_id = ?",
            (wd, code, detail, who, enrolment_id))
        _log(conn, e, "Withdrawn",
             f"{wd}, {withdrawal_reason_label(code)}")
        conn.commit()
    out = get_enrolment(enrolment_id)
    assert out is not None
    result = WithdrawalResult(enrolment=out)
    why = f"Enrolment withdrawn: {withdrawal_reason_label(code)}" + (
        f" — {detail}" if detail else "")
    if own_aims is None:
        result.aim_problems.append(f"Learning aims not read: {aims_error}")
        own_aims = []
    aims = _aims_module() if own_aims else None
    for aim in own_aims:
        if aim.start_date and aim.start_date > wd:
            result.aim_problems.append(
                f"{aim.label}: starts {aim.start_date}, after the "
                "withdrawal date — change or delete it in Learning aims")
            continue
        try:
            aims.withdraw_aim(aim.aim_id, effective_date=wd, reason=why,
                              approved_by=approved_by or who or "system",
                              recorded_by=who)
            result.aims_ended.append(f"{aim.label} (ended {wd})")
            with _connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO enrolment_aim_withdrawals "
                    "(enrolment_id, aim_id, withdrawn_on, reopened_at) "
                    "VALUES (?, ?, ?, NULL)", (enrolment_id, aim.aim_id, wd))
                conn.commit()
        except Exception as exc:  # noqa: BLE001 — reported per aim
            result.aim_problems.append(f"{aim.label}: {exc}")

    if update_student:
        others = [o for o in list_for_student(e.student_id)
                  if o.enrolment_id != enrolment_id and o.is_live]
        if not others:
            from education_system.systems.sixth_form.domain.learners.students import (
                students as _students,
            )
            st = _students.get_student(e.student_id)
            if st is not None and st.status in _students.ON_ROLL_STATUSES:
                try:
                    _students.withdraw_student(
                        e.student_id,
                        reason=f"Withdrawn from enrolment: "
                               f"{withdrawal_reason_label(code)}",
                        leaving_date=wd, withdrawal_reason=code,
                        withdrawal_detail=detail)
                    result.student_left = True
                except Exception as exc:  # noqa: BLE001 — reported
                    logger.exception("withdraw_enrolment(%d): student record",
                                     enrolment_id)
                    result.student_notes.append(
                        f"Student record not marked as left: {exc}")
        else:
            result.student_notes.append(
                "Still on roll — enrolment "
                + ", ".join(f"{o.academic_year} ({o.status})" for o in others)
                + " is open")
    logger.info("Withdrew enrolment #%d (%s) on %s, reason %s; %d aim(s) "
                "ended, %d problem(s)", enrolment_id, e.student_id, wd, code,
                len(result.aims_ended), len(result.aim_problems))
    return result


@dataclass
class ReinstateResult:
    enrolment: Enrolment
    aims_reopened: list[str] = field(default_factory=list)
    aim_problems: list[str] = field(default_factory=list)
    student_reinstated: bool = False
    student_notes: list[str] = field(default_factory=list)


def reinstate_enrolment(enrolment_id: int, *, reason: str,
                        reinstate_student: bool = True) -> ReinstateResult:
    """Undo a withdrawal: the enrolment goes back to Enrolled, the aims
    its withdrawal ended are reopened, and (``reinstate_student``) a
    student record marked as left is put back on roll. The old withdrawal
    stays in :func:`enrolment_history`."""
    init_db()
    _require_writer("reinstating enrolments")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("A reason for the reinstatement is required")
    e = _get(enrolment_id)
    if e is None:
        raise ValidationError(f"No enrolment with id {enrolment_id}")
    if e.is_archived:
        raise ValidationError(
            f"Enrolment #{enrolment_id} is archived; restore it first")
    if e.status != "Withdrawn":
        raise ValidationError(
            f"Enrolment #{enrolment_id} is {e.status}, not withdrawn")
    with _connect() as conn:
        conn.execute(
            "UPDATE enrolments SET status = 'Enrolled', withdrawal_date = NULL, "
            "withdrawal_reason = NULL, withdrawal_detail = NULL, "
            "withdrawn_by = NULL, updated_at = datetime('now') "
            "WHERE enrolment_id = ?", (enrolment_id,))
        _log(conn, e, "Reinstated",
             f"was withdrawn {e.withdrawal_date or '?'} "
             f"({withdrawal_reason_label(e.withdrawal_reason) or 'no reason'})"
             f"; {reason}")
        aim_ids = [r["aim_id"] for r in conn.execute(
            "SELECT aim_id FROM enrolment_aim_withdrawals WHERE "
            "enrolment_id = ? AND reopened_at IS NULL", (enrolment_id,))]
        conn.commit()

    result = ReinstateResult(enrolment=e)
    if reinstate_student:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        st = _students.get_student(e.student_id)
        if st is not None and st.status == "Left":
            try:
                _students.reinstate_student(
                    e.student_id, reason=f"Enrolment reinstated: {reason}")
                result.student_reinstated = True
            except Exception as exc:  # noqa: BLE001 — reported
                logger.exception("reinstate_enrolment(%d): student", enrolment_id)
                result.student_notes.append(f"Student not reinstated: {exc}")

    aims = _aims_module() if aim_ids else None
    for aim_id in aim_ids:
        try:
            aim = aims.reinstate_aim(aim_id, reason=f"Enrolment reinstated: "
                                                    f"{reason}",
                                     recorded_by=_actor())
            result.aims_reopened.append(aim.label)
            with _connect() as conn:
                conn.execute(
                    "UPDATE enrolment_aim_withdrawals SET reopened_at = "
                    "datetime('now') WHERE enrolment_id = ? AND aim_id = ?",
                    (enrolment_id, aim_id))
                conn.commit()
        except Exception as exc:  # noqa: BLE001 — reported per aim
            result.aim_problems.append(f"Aim #{aim_id}: {exc}")
    note = _sync_tutor_membership(e.student_id)
    if note:
        result.student_notes.append(note)
    if result.student_reinstated:
        try:
            from education_system.systems.sixth_form.domain.admissions.enrolments import (
                leaver_effects,
            )
            result.student_notes += leaver_effects.on_returned(e.student_id)
        except Exception as exc:  # noqa: BLE001 — a to-do list, never blocks
            logger.exception("reinstate_enrolment(%d): leaver steps", enrolment_id)
            result.student_notes.append(f"Leaver steps not listed: {exc}")
    out = get_enrolment(enrolment_id)
    assert out is not None
    result.enrolment = out
    logger.info("Reinstated enrolment #%d (%s); %d aim(s) reopened",
                enrolment_id, e.student_id, len(result.aims_reopened))
    return result


def reopen_enrolment(enrolment_id: int, *, reason: str) -> Enrolment:
    """Put a Completed enrolment back to Enrolled (e.g. completed by a
    rollover by mistake). Aims are left as they are — reopen those in
    Learning aims if they were completed too."""
    init_db()
    _require_writer("reopening enrolments")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("A reason is required")
    e = _get(enrolment_id)
    if e is None or e.is_archived:
        raise ValidationError(f"No live enrolment with id {enrolment_id}")
    if e.status != "Completed":
        raise ValidationError(f"Enrolment #{enrolment_id} is {e.status}, "
                              "not Completed")
    with _connect() as conn:
        conn.execute(
            "UPDATE enrolments SET status = 'Enrolled', completed_at = NULL, "
            "updated_at = datetime('now') WHERE enrolment_id = ?",
            (enrolment_id,))
        _log(conn, e, "Reopened", reason)
        conn.commit()
    out = get_enrolment(enrolment_id)
    assert out is not None
    return out


def complete_enrolment(enrolment_id: int, *, completed_on: str | None = None,
                       complete_aims: bool = True) -> tuple[Enrolment, list[str]]:
    """Mark an Enrolled enrolment Completed (end of course). With
    ``complete_aims`` the enrolment's active aims are completed too.
    Returns the enrolment and any aim problems."""
    init_db()
    _require_writer("completing enrolments")
    e = _get(enrolment_id)
    if e is None or e.is_archived:
        raise ValidationError(f"No live enrolment with id {enrolment_id}")
    if e.status != "Enrolled":
        raise ValidationError(f"Enrolment #{enrolment_id} is {e.status}, "
                              "not Enrolled")
    day = completed_on or _dt.date.today().isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE enrolments SET status = 'Completed', completed_at = ?, "
            "updated_at = datetime('now') WHERE enrolment_id = ?",
            (day, enrolment_id))
        _log(conn, e, "Completed", day)
        conn.commit()
    problems = _complete_aims(e, day)[1] if complete_aims else []
    out = get_enrolment(enrolment_id)
    assert out is not None
    return out, problems


def _complete_aims(e: Enrolment, day: str) -> tuple[list[int], list[str]]:
    done: list[int] = []
    problems: list[str] = []
    try:
        own = aims_for_enrolment(e)
    except Exception as exc:  # noqa: BLE001
        return done, [f"Learning aims not read: {exc}"]
    aims = _aims_module() if own else None
    for aim in own:
        end = aim.planned_end_date if aim.planned_end_date \
            and aim.planned_end_date <= day else day
        if end < aim.start_date:
            end = aim.start_date
        try:
            aims.complete_aim(aim.aim_id, end_date=end, recorded_by=_actor())
            done.append(aim.aim_id)
        except Exception as exc:  # noqa: BLE001 — reported per aim
            problems.append(f"{e.student_id} {aim.label}: {exc}")
    return done, problems


# ── Archive (never hard-delete) ─────────────────────────────────────

def archive_enrolment(enrolment_id: int, *, reason: str | None = None) -> bool:
    """Take an enrolment out of every list without losing it. Returns
    False when there is no such (unarchived) enrolment."""
    init_db()
    _require_writer("archiving enrolments")
    e = _get(enrolment_id)
    if e is None or e.is_archived:
        logger.warning("archive_enrolment: no live enrolment #%d", enrolment_id)
        return False
    with _connect() as conn:
        conn.execute(
            "UPDATE enrolments SET archived_at = datetime('now'), "
            "archived_by = ?, archived_reason = ?, "
            "updated_at = datetime('now') WHERE enrolment_id = ?",
            (_actor(), (reason or "").strip() or None, enrolment_id))
        _log(conn, e, "Archived", (reason or "").strip() or None)
        conn.commit()
    logger.info("Archived enrolment #%d (%s %s)", enrolment_id,
                e.student_id, e.academic_year)
    return True


def delete_enrolment(enrolment_id: int, *, reason: str | None = None) -> bool:
    """"Delete" from the screens: archives the row (see
    :func:`archive_enrolment`) so :func:`restore_enrolment` can undo it."""
    return archive_enrolment(enrolment_id, reason=reason or "Deleted")


def restore_enrolment(enrolment_id: int) -> Enrolment:
    """Undo an archive: the same row, same id, comes back."""
    init_db()
    _require_writer("restoring enrolments")
    e = _get(enrolment_id)
    if e is None:
        raise ValidationError(f"No enrolment with id {enrolment_id}")
    if not e.is_archived:
        return get_enrolment(enrolment_id) or e
    with _connect() as conn:
        conn.execute(
            "UPDATE enrolments SET archived_at = NULL, archived_by = NULL, "
            "archived_reason = NULL, updated_at = datetime('now') "
            "WHERE enrolment_id = ?", (enrolment_id,))
        _log(conn, e, "Restored", f"archived {e.archived_at}"
             + (f" ({e.archived_reason})" if e.archived_reason else ""))
        conn.commit()
    logger.info("Restored enrolment #%d", enrolment_id)
    out = get_enrolment(enrolment_id)
    assert out is not None
    return out


# ── Correcting the learner ──────────────────────────────────────────

@dataclass
class TransferResult:
    enrolment: Enrolment
    aims_moved: int = 0


def transfer_enrolment(enrolment_id: int, to_student_id: str, *,
                       reason: str) -> TransferResult:
    """Move an enrolment entered against the wrong learner to the right
    one, in one transaction: the same row (id, withdrawal details,
    history) changes owner, and the learning aims that started in that
    enrolment's year (with their change history) go with it."""
    init_db()
    _require_writer("moving enrolments between learners")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("A reason is required")
    e = _get(enrolment_id)
    if e is None or e.is_archived:
        raise ValidationError(f"No live enrolment with id {enrolment_id}")
    to = (to_student_id or "").strip()
    if not to or to == e.student_id:
        raise ValidationError("Choose a different learner")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(to) is None:
        raise ValidationError(f"No student with id {to}")
    aims = _aims_module()
    aims.init_db()
    first, last = academic_year_dates(e.academic_year)
    aim_ids = [a.aim_id for a in aims.list_aims(e.student_id)
               if a.start_date and first <= a.start_date <= last]
    with _connect() as conn:
        clash = conn.execute(
            "SELECT enrolment_id, archived_at FROM enrolments WHERE "
            "student_id = ? AND academic_year = ?",
            (to, e.academic_year)).fetchone()
        if clash:
            raise ValidationError(
                f"{to} already has {'an archived' if clash['archived_at'] else 'an'}"
                f" enrolment for {e.academic_year} (#{clash['enrolment_id']})")
        _check_year_order(conn, to, e.academic_year, e.year_group)
        conn.execute("UPDATE enrolments SET student_id = ?, "
                     "updated_at = datetime('now') WHERE enrolment_id = ?",
                     (to, enrolment_id))
        conn.execute("UPDATE enrolment_history SET student_id = ? "
                     "WHERE enrolment_id = ?", (to, enrolment_id))
        for aim_id in aim_ids:
            conn.execute("UPDATE learning_aims SET student_id = ?, "
                         "updated_at = datetime('now') WHERE aim_id = ?",
                         (to, aim_id))
            conn.execute("UPDATE learning_aim_changes SET student_id = ? "
                         "WHERE aim_id = ?", (to, aim_id))
        _log(conn, {"enrolment_id": enrolment_id, "student_id": to},
             "Moved", f"from {e.student_id} to {to} with {len(aim_ids)} "
             f"aim(s): {reason}")
        aims.sync_mirror(e.student_id, conn)
        aims.sync_mirror(to, conn)
        conn.commit()
    _sync_tutor_membership(to)
    out = get_enrolment(enrolment_id)
    assert out is not None
    logger.info("Moved enrolment #%d from %s to %s (%d aims)", enrolment_id,
                e.student_id, to, len(aim_ids))
    return TransferResult(enrolment=out, aims_moved=len(aim_ids))


# ── Year 12 → 13 rollover ───────────────────────────────────────────

def next_academic_year(academic_year: str) -> str:
    if not _ACADEMIC_YEAR_RE.match(academic_year or ""):
        raise ValidationError("Academic year must look like '2025/26'")
    first = int(academic_year[:4]) + 1
    return f"{first}/{str(first + 1)[-2:]}"


@dataclass
class RolloverResult:
    from_year: str
    to_year: str
    completed: list[str] = field(default_factory=list)
    progressed: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    aim_problems: list[str] = field(default_factory=list)
    run_id: int | None = None


def _one_year_programme(student_id: str, year_end: str) -> bool:
    """Every active aim is planned to end by ``year_end`` (AS, GCSE
    resit, one-year vocational) — nothing to come back to Year 13 for."""
    try:
        active = _aims_module().active_aims(student_id)
    except Exception:  # noqa: BLE001
        return False
    return bool(active) and all(a.planned_end_date and a.planned_end_date
                                <= year_end for a in active)


def rollover(from_year: str, to_year: str | None = None, *,
             complete_year13: bool = True, progress_year12: bool = True,
             require_intention: bool = False,
             dry_run: bool = False) -> RolloverResult:
    """End-of-year rollover.

    * Year 13 ``Enrolled`` rows in ``from_year`` become ``Completed``, and
      their aims are completed (``complete_year13``);
    * Year 12 ``Enrolled`` rows get a Year 13 enrolment in ``to_year``
      (default the following year) with the tutor group bumped
      (``12A`` → ``13A``), and the Year 12 row itself becomes
      ``Completed`` (``progress_year12``). A Year 12 learner whose aims
      all end this year (one-year programme) is completed, not moved up.

    A learner is **skipped**, with the reason, when their student record
    is missing or not on roll, when they already have a ``to_year``
    enrolment, when their re-enrolment answer is ``Not returning`` (or,
    with ``require_intention``, anything but ``Returning``), or when their
    ``from_year`` enrolment is withdrawn or still Pending.

    The enrolment changes are one transaction and the run is logged, so
    :func:`undo_rollover` can put it back. Aim completion and tutor-group
    moves follow the commit and report their problems. ``dry_run``
    reports what would happen without writing.
    """
    import json

    init_db()
    _require_writer("rolling enrolments over")
    tgt = to_year or next_academic_year(from_year)
    if not _ACADEMIC_YEAR_RE.match(tgt):
        raise ValidationError("Academic year must look like '2025/26'")
    if tgt <= from_year:
        raise ValidationError("The new academic year must follow the old one")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _first, year_end = academic_year_dates(from_year)
    result = RolloverResult(from_year=from_year, to_year=tgt)
    rows = list_enrolments(academic_year=from_year)
    with _connect() as conn:
        nxt = {r["student_id"]: dict(r) for r in conn.execute(
            "SELECT student_id, enrolment_id, archived_reason, archived_at "
            "FROM enrolments WHERE academic_year = ?", (tgt,))}

    def blocked(e: Enrolment) -> str | None:
        st = _students.get_student(e.student_id)
        if st is None:
            return "no student record"
        if st.status not in _students.ON_ROLL_STATUSES:
            return f"student status is {st.status} (not on roll)"
        return None

    to_complete: list[Enrolment] = []
    to_progress: list[tuple[Enrolment, int | None]] = []   # (row, restore id)
    for e in rows:
        if e.status == "Withdrawn":
            result.skipped.append((e.student_id, (
                f"enrolment for {from_year} is withdrawn"
                + (f" ({e.withdrawal_date})" if e.withdrawal_date else ""))))
            continue
        if e.status == "Pending":
            result.skipped.append((e.student_id,
                                   f"enrolment for {from_year} is Pending"))
            continue
        if e.status != "Enrolled":
            continue
        why = blocked(e)
        if e.year_group == 13 and complete_year13:
            if why:
                result.skipped.append((e.student_id, why))
                continue
            to_complete.append(e)
        elif e.year_group == 12 and progress_year12:
            restore_id = None
            if not why and e.return_intention == "Not returning":
                why = "not returning for Year 13 — record them as a leaver"
            if not why and require_intention \
                    and e.return_intention != "Returning":
                why = ("re-enrolment not confirmed ("
                       f"{e.return_intention or 'no answer'})")
            if not why and e.student_id in nxt:
                n = nxt[e.student_id]
                if n["archived_at"] and n["archived_reason"] == "Rollover undone":
                    restore_id = n["enrolment_id"]
                else:
                    why = f"already has a {tgt} enrolment"
            if why:
                result.skipped.append((e.student_id, why))
                continue
            if _one_year_programme(e.student_id, year_end):
                to_complete.append(e)
                continue
            to_progress.append((e, restore_id))

    result.completed = [e.student_id for e in to_complete]
    result.progressed = [e.student_id for e, _r in to_progress]
    if dry_run or not (to_complete or to_progress):
        logger.info("Rollover %s → %s: %d to complete, %d to progress, "
                    "%d skipped%s", from_year, tgt, len(to_complete),
                    len(to_progress), len(result.skipped),
                    " (dry run)" if dry_run else "")
        return result

    changes: dict[str, Any] = {"completed": [], "created": [], "restored": [],
                               "aims_completed": []}
    today = _dt.date.today().isoformat()
    try:
        with _connect() as conn:
            for e in to_complete:
                conn.execute(
                    "UPDATE enrolments SET status = 'Completed', "
                    "completed_at = ?, updated_at = datetime('now') "
                    "WHERE enrolment_id = ?", (today, e.enrolment_id))
                _log(conn, e, "Completed", f"rollover {from_year} → {tgt}")
                changes["completed"].append(e.enrolment_id)
            for e, restore_id in to_progress:
                group = _bump_tutor_group(12, 13, e.tutor_group)
                if restore_id:
                    conn.execute(
                        "UPDATE enrolments SET archived_at = NULL, "
                        "archived_by = NULL, archived_reason = NULL, "
                        "status = 'Enrolled', tutor_group = ?, "
                        "updated_at = datetime('now') WHERE enrolment_id = ?",
                        (group, restore_id))
                    _log(conn, {"enrolment_id": restore_id,
                                "student_id": e.student_id}, "Restored",
                         f"rollover {from_year} → {tgt} run again")
                    changes["restored"].append(restore_id)
                else:
                    cur = conn.execute(
                        "INSERT INTO enrolments (student_id, academic_year, "
                        "year_group, tutor_group, start_date, status, notes, "
                        "recorded_by, updated_at) VALUES (?, ?, 13, ?, NULL, "
                        "'Enrolled', ?, ?, datetime('now'))",
                        (e.student_id, tgt, group,
                         f"Rolled over from Year 12 {from_year}", _actor()))
                    _log(conn, {"enrolment_id": cur.lastrowid,
                                "student_id": e.student_id}, "Created",
                         f"rollover {from_year} → {tgt}")
                    changes["created"].append(cur.lastrowid)
                conn.execute(
                    "UPDATE enrolments SET status = 'Completed', "
                    "completed_at = ?, updated_at = datetime('now') "
                    "WHERE enrolment_id = ?", (today, e.enrolment_id))
                _log(conn, e, "Completed", f"moved up to Year 13 {tgt}")
                changes["completed"].append(e.enrolment_id)
            cur = conn.execute(
                "INSERT INTO enrolment_rollovers (from_year, to_year, run_by, "
                "changes) VALUES (?, ?, ?, ?)",
                (from_year, tgt, _actor(), json.dumps(changes)))
            result.run_id = cur.lastrowid
            conn.commit()
    except sqlite3.Error as exc:
        logger.exception("Rollover %s → %s failed", from_year, tgt)
        result.failed = [(e.student_id, str(exc)) for e in to_complete] + [
            (e.student_id, str(exc)) for e, _r in to_progress]
        result.completed, result.progressed = [], []
        return result

    # After the commit: Year 13 aims end, and tutor groups follow.
    for e in to_complete:
        if e.year_group == 13 or _one_year_programme(e.student_id, year_end):
            done, problems = _complete_aims(e, min(today, year_end))
            changes["aims_completed"] += done
            result.aim_problems += problems
    for e, _r in to_progress:
        _sync_tutor_membership(e.student_id)
    if changes["aims_completed"]:
        with _connect() as conn:
            conn.execute("UPDATE enrolment_rollovers SET changes = ? "
                         "WHERE run_id = ?",
                         (json.dumps(changes), result.run_id))
            conn.commit()
    logger.info("Rollover %s → %s (run %s): %d completed, %d progressed, "
                "%d skipped, %d aim problem(s)", from_year, tgt,
                result.run_id, len(result.completed), len(result.progressed),
                len(result.skipped), len(result.aim_problems))
    return result


def list_rollovers(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    import json
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM enrolment_rollovers ORDER BY "
                            "run_id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        c = json.loads(d.pop("changes") or "{}")
        d.update({k: len(v) for k, v in c.items()})
        out.append(d)
    return out


@dataclass
class UndoRolloverResult:
    run_id: int
    reverted: int = 0
    kept: list[str] = field(default_factory=list)
    aim_problems: list[str] = field(default_factory=list)


def undo_rollover(run_id: int) -> UndoRolloverResult:
    """Put a rollover run back: the Year 13 rows it created are archived
    ("Rollover undone" — running the rollover again brings them back),
    the rows it completed go back to Enrolled and the aims it completed
    are reopened. A row changed since the run is left alone and listed in
    ``kept``."""
    import json

    init_db()
    _require_writer("undoing a rollover")
    with _connect() as conn:
        run = conn.execute("SELECT * FROM enrolment_rollovers WHERE run_id = ?",
                           (run_id,)).fetchone()
        if run is None:
            raise ValidationError(f"No rollover run #{run_id}")
        if run["undone_at"]:
            raise ValidationError(f"Rollover run #{run_id} was already undone")
        later = conn.execute("SELECT run_id FROM enrolment_rollovers WHERE "
                             "run_id > ? AND undone_at IS NULL", (run_id,)
                             ).fetchone()
        if later:
            raise ValidationError(
                f"Undo the later rollover run #{later['run_id']} first")
        changes = json.loads(run["changes"])
        result = UndoRolloverResult(run_id=run_id)

        def touched_since(eid: int) -> bool:
            return conn.execute(
                "SELECT 1 FROM enrolment_history WHERE enrolment_id = ? AND "
                "changed_at > ? AND action NOT IN ('Created', 'Completed', "
                "'Restored')", (eid, run["run_at"])).fetchone() is not None

        for eid in changes.get("created", []) + changes.get("restored", []):
            row = conn.execute("SELECT * FROM enrolments WHERE enrolment_id = ?",
                               (eid,)).fetchone()
            if row is None or row["archived_at"]:
                continue
            if touched_since(eid) or row["status"] != "Enrolled":
                result.kept.append(f"#{eid} {row['student_id']}: changed since")
                continue
            conn.execute("UPDATE enrolments SET archived_at = datetime('now'), "
                         "archived_by = ?, archived_reason = 'Rollover undone', "
                         "updated_at = datetime('now') WHERE enrolment_id = ?",
                         (_actor(), eid))
            _log(conn, dict(row), "Archived", f"rollover run #{run_id} undone")
            result.reverted += 1
        for eid in changes.get("completed", []):
            row = conn.execute("SELECT * FROM enrolments WHERE enrolment_id = ?",
                               (eid,)).fetchone()
            if row is None or row["status"] != "Completed":
                continue
            if touched_since(eid):
                result.kept.append(f"#{eid} {row['student_id']}: changed since")
                continue
            conn.execute("UPDATE enrolments SET status = 'Enrolled', "
                         "completed_at = NULL, updated_at = datetime('now') "
                         "WHERE enrolment_id = ?", (eid,))
            _log(conn, dict(row), "Reopened", f"rollover run #{run_id} undone")
            result.reverted += 1
        conn.execute("UPDATE enrolment_rollovers SET undone_at = "
                     "datetime('now'), undone_by = ? WHERE run_id = ?",
                     (_actor(), run_id))
        conn.commit()
    aim_ids = changes.get("aims_completed", [])
    aims = _aims_module() if aim_ids else None
    for aim_id in aim_ids:
        try:
            aims.reinstate_aim(aim_id, reason=f"Rollover run #{run_id} undone",
                               recorded_by=_actor())
        except Exception as exc:  # noqa: BLE001 — reported per aim
            result.aim_problems.append(f"Aim #{aim_id}: {exc}")
    logger.info("Undid rollover run #%d: %d reverted, %d kept", run_id,
                result.reverted, len(result.kept))
    return result
