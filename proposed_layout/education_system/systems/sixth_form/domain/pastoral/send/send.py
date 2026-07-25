"""SEND register data layer for Sixth Form System.

One row per student per active register entry. Tracks register
status (Monitoring / SEN Support / EHCP / Exited), primary &
secondary need, assess-plan-do-review cycle progression, provision
summary, key worker / SENCo, external agencies and review schedule.
There is at most one open entry per student.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.systems.sixth_form.infrastructure import paths as _paths

logger = logging.getLogger(__name__)

REGISTER_STATUSES: tuple[str, ...] = (
    "Monitoring",
    "SEN Support",
    "EHCP",
    "Awaiting Assessment",
    "Exited",
)
DEFAULT_REGISTER_STATUS = "SEN Support"

NEED_TYPES: tuple[str, ...] = (
    "Cognition & Learning",
    "Communication & Interaction",
    "Social, Emotional & Mental Health",
    "Sensory or Physical",
    "Multiple Needs",
    "Other",
)
DEFAULT_NEED_TYPE = "Cognition & Learning"

CYCLE_STAGES: tuple[str, ...] = ("Assess", "Plan", "Do", "Review")
DEFAULT_CYCLE_STAGE = "Assess"

STATUSES: tuple[str, ...] = (
    "Active",
    "Awaiting Review",
    "Under Review",
    "Exited",
    "Archived",
)
DEFAULT_STATUS = "Active"


class ValidationError(Exception):
    pass


@dataclass
class SENDEntry:
    entry_id: int
    student_id: str
    register_status: str
    primary_need: str
    secondary_need: str | None
    ehcp_reference: str | None
    ehcp_issued_on: str | None
    date_added: str
    cycle_number: int
    cycle_stage: str
    next_review_due: str | None
    last_review_on: str | None
    provision_summary: str | None
    outcomes: str | None
    strategies: str | None
    external_agencies: str | None
    key_worker: str | None
    senco: str | None
    parent_consent: bool
    pupil_voice: str | None
    status: str
    exit_reason: str | None
    exit_on: str | None
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status not in ("Exited", "Archived")

    @property
    def has_ehcp(self) -> bool:
        return self.register_status == "EHCP"

    @property
    def review_overdue(self) -> bool:
        if not self.is_open or not self.next_review_due:
            return False
        return self.next_review_due < _dt.date.today().isoformat()


@dataclass
class SENDSummary:
    total: int = 0
    open_count: int = 0
    ehcp_count: int = 0
    overdue_reviews: int = 0
    distinct_students: int = 0
    by_register_status: dict[str, int] = field(default_factory=dict)
    by_primary_need: dict[str, int] = field(default_factory=dict)
    by_cycle_stage: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.SEND_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS send_register (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                register_status TEXT NOT NULL,
                primary_need TEXT NOT NULL,
                secondary_need TEXT,
                ehcp_reference TEXT,
                ehcp_issued_on TEXT,
                date_added TEXT NOT NULL,
                cycle_number INTEGER NOT NULL DEFAULT 1,
                cycle_stage TEXT NOT NULL,
                next_review_due TEXT,
                last_review_on TEXT,
                provision_summary TEXT,
                outcomes TEXT,
                strategies TEXT,
                external_agencies TEXT,
                key_worker TEXT,
                senco TEXT,
                parent_consent INTEGER NOT NULL DEFAULT 0,
                pupil_voice TEXT,
                status TEXT NOT NULL,
                exit_reason TEXT,
                exit_on TEXT,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(student_id)
                  ON DELETE CASCADE
            )
        """)


# ── Validation ─────────────────────────────────────────────────────

def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _student_exists(student_id: str) -> bool:
    with _connect() as conn:
        try:
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_id=?",
                (student_id,)).fetchone()
        except sqlite3.OperationalError:
            return False
    return row is not None


def _validate_payload(p: dict[str, Any], *,
                          existing_id: int | None = None) -> dict[str, Any]:
    out = dict(p)
    out["student_id"] = (out.get("student_id") or "").strip()
    if not out["student_id"]:
        raise ValidationError("Student is required")
    if not _student_exists(out["student_id"]):
        raise ValidationError(
            f"No student with id {out['student_id']}")

    rs = (out.get("register_status") or "").strip()
    if rs not in REGISTER_STATUSES:
        raise ValidationError(
            f"Register status must be one of: "
            f"{', '.join(REGISTER_STATUSES)}")
    out["register_status"] = rs

    pn = (out.get("primary_need") or "").strip()
    if pn not in NEED_TYPES:
        raise ValidationError(
            f"Primary need must be one of: {', '.join(NEED_TYPES)}")
    out["primary_need"] = pn

    sn = (out.get("secondary_need") or "").strip()
    if sn and sn not in NEED_TYPES:
        raise ValidationError(
            f"Secondary need must be one of: {', '.join(NEED_TYPES)}")
    out["secondary_need"] = sn or None

    out["date_added"] = (out.get("date_added") or "").strip()
    if not out["date_added"]:
        raise ValidationError("Date added is required (YYYY-MM-DD)")
    _check_date("Date added", out["date_added"])
    _check_date("EHCP issued", out.get("ehcp_issued_on"))
    _check_date("Next review", out.get("next_review_due"))
    _check_date("Last review", out.get("last_review_on"))
    _check_date("Exit date",   out.get("exit_on"))

    try:
        cyc = int(out.get("cycle_number") or 1)
    except (TypeError, ValueError):
        raise ValidationError("Cycle number must be an integer >= 1")
    if cyc < 1:
        raise ValidationError("Cycle number must be >= 1")
    out["cycle_number"] = cyc

    stage = (out.get("cycle_stage") or DEFAULT_CYCLE_STAGE).strip()
    if stage not in CYCLE_STAGES:
        raise ValidationError(
            f"Cycle stage must be one of: {', '.join(CYCLE_STAGES)}")
    out["cycle_stage"] = stage

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    for k in ("ehcp_reference", "provision_summary", "outcomes",
               "strategies", "external_agencies", "key_worker",
               "senco", "pupil_voice", "exit_reason", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("ehcp_issued_on", "next_review_due",
               "last_review_on", "exit_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    out["parent_consent"] = bool(out.get("parent_consent"))

    # At most one open entry per student
    if status not in ("Exited", "Archived"):
        with _connect() as conn:
            row = conn.execute(
                "SELECT entry_id FROM send_register "
                "WHERE student_id=? AND status NOT IN "
                "('Exited','Archived')",
                (out["student_id"],)).fetchone()
        if row and row["entry_id"] != existing_id:
            raise ValidationError(
                f"Student {out['student_id']} already has an "
                f"open SEND entry (#{row['entry_id']})")
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def _row(r: sqlite3.Row) -> SENDEntry:
    return SENDEntry(
        entry_id=r["entry_id"],
        student_id=r["student_id"],
        register_status=r["register_status"],
        primary_need=r["primary_need"],
        secondary_need=r["secondary_need"],
        ehcp_reference=r["ehcp_reference"],
        ehcp_issued_on=r["ehcp_issued_on"],
        date_added=r["date_added"],
        cycle_number=r["cycle_number"],
        cycle_stage=r["cycle_stage"],
        next_review_due=r["next_review_due"],
        last_review_on=r["last_review_on"],
        provision_summary=r["provision_summary"],
        outcomes=r["outcomes"],
        strategies=r["strategies"],
        external_agencies=r["external_agencies"],
        key_worker=r["key_worker"],
        senco=r["senco"],
        parent_consent=bool(r["parent_consent"]),
        pupil_voice=r["pupil_voice"],
        status=r["status"],
        exit_reason=r["exit_reason"],
        exit_on=r["exit_on"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_entry(payload: dict[str, Any]) -> SENDEntry:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO send_register (
              student_id, register_status, primary_need,
              secondary_need, ehcp_reference, ehcp_issued_on,
              date_added, cycle_number, cycle_stage,
              next_review_due, last_review_on,
              provision_summary, outcomes, strategies,
              external_agencies, key_worker, senco,
              parent_consent, pupil_voice, status,
              exit_reason, exit_on, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["student_id"], p["register_status"], p["primary_need"],
            p["secondary_need"], p["ehcp_reference"],
            p["ehcp_issued_on"],
            p["date_added"], p["cycle_number"], p["cycle_stage"],
            p["next_review_due"], p["last_review_on"],
            p["provision_summary"], p["outcomes"], p["strategies"],
            p["external_agencies"], p["key_worker"], p["senco"],
            1 if p["parent_consent"] else 0,
            p["pupil_voice"], p["status"],
            p["exit_reason"], p["exit_on"], p["notes"],
            now, now,
        ))
        new_id = cur.lastrowid
    return get_entry(new_id)


def update_entry(entry_id: int,
                    payload: dict[str, Any]) -> SENDEntry:
    init_db()
    if get_entry(entry_id) is None:
        raise ValidationError(f"No SEND entry with id {entry_id}")
    p = _validate_payload(payload, existing_id=entry_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE send_register SET
              student_id=?, register_status=?, primary_need=?,
              secondary_need=?, ehcp_reference=?, ehcp_issued_on=?,
              date_added=?, cycle_number=?, cycle_stage=?,
              next_review_due=?, last_review_on=?,
              provision_summary=?, outcomes=?, strategies=?,
              external_agencies=?, key_worker=?, senco=?,
              parent_consent=?, pupil_voice=?, status=?,
              exit_reason=?, exit_on=?, notes=?,
              updated_on=?
            WHERE entry_id=?
        """, (
            p["student_id"], p["register_status"], p["primary_need"],
            p["secondary_need"], p["ehcp_reference"],
            p["ehcp_issued_on"],
            p["date_added"], p["cycle_number"], p["cycle_stage"],
            p["next_review_due"], p["last_review_on"],
            p["provision_summary"], p["outcomes"], p["strategies"],
            p["external_agencies"], p["key_worker"], p["senco"],
            1 if p["parent_consent"] else 0,
            p["pupil_voice"], p["status"],
            p["exit_reason"], p["exit_on"], p["notes"],
            now, entry_id,
        ))
    return get_entry(entry_id)


def delete_entry(entry_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM send_register WHERE entry_id=?",
            (entry_id,))
        return cur.rowcount > 0


def get_entry(entry_id: int) -> SENDEntry | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM send_register WHERE entry_id=?",
            (entry_id,)).fetchone()
        return _row(r) if r else None


def list_entries(*,
                    student_id: str | None = None,
                    register_status: str | None = None,
                    primary_need: str | None = None,
                    cycle_stage: str | None = None,
                    status: str | None = None,
                    open_only: bool = False,
                    overdue_only: bool = False,
                    key_worker_like: str | None = None,
                    senco_like: str | None = None,
                    ) -> list[SENDEntry]:
    init_db()
    sql = "SELECT * FROM send_register WHERE 1=1"
    params: list[Any] = []
    if student_id:
        sql += " AND student_id=?"
        params.append(student_id)
    if register_status:
        sql += " AND register_status=?"
        params.append(register_status)
    if primary_need:
        sql += " AND primary_need=?"
        params.append(primary_need)
    if cycle_stage:
        sql += " AND cycle_stage=?"
        params.append(cycle_stage)
    if status:
        sql += " AND status=?"
        params.append(status)
    if open_only:
        sql += " AND status NOT IN ('Exited','Archived')"
    if overdue_only:
        today = _dt.date.today().isoformat()
        sql += (" AND next_review_due IS NOT NULL"
                  " AND next_review_due < ?"
                  " AND status NOT IN ('Exited','Archived')")
        params.append(today)
    if key_worker_like:
        sql += " AND key_worker LIKE ?"
        params.append(f"%{key_worker_like}%")
    if senco_like:
        sql += " AND senco LIKE ?"
        params.append(f"%{senco_like}%")
    sql += " ORDER BY date_added DESC, entry_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


def entries_for_student(student_id: str) -> list[SENDEntry]:
    return list_entries(student_id=student_id)


# ── Workflow helpers ──────────────────────────────────────────────

def _to_dict(e: SENDEntry) -> dict[str, Any]:
    return {
        "student_id": e.student_id,
        "register_status": e.register_status,
        "primary_need": e.primary_need,
        "secondary_need": e.secondary_need,
        "ehcp_reference": e.ehcp_reference,
        "ehcp_issued_on": e.ehcp_issued_on,
        "date_added": e.date_added,
        "cycle_number": e.cycle_number,
        "cycle_stage": e.cycle_stage,
        "next_review_due": e.next_review_due,
        "last_review_on": e.last_review_on,
        "provision_summary": e.provision_summary,
        "outcomes": e.outcomes,
        "strategies": e.strategies,
        "external_agencies": e.external_agencies,
        "key_worker": e.key_worker,
        "senco": e.senco,
        "parent_consent": e.parent_consent,
        "pupil_voice": e.pupil_voice,
        "status": e.status,
        "exit_reason": e.exit_reason,
        "exit_on": e.exit_on,
        "notes": e.notes,
    }


def advance_cycle(entry_id: int) -> SENDEntry:
    e = get_entry(entry_id)
    if e is None:
        raise ValidationError(f"No SEND entry with id {entry_id}")
    data = _to_dict(e)
    idx = CYCLE_STAGES.index(e.cycle_stage)
    if idx == len(CYCLE_STAGES) - 1:
        data["cycle_stage"] = CYCLE_STAGES[0]
        data["cycle_number"] = e.cycle_number + 1
    else:
        data["cycle_stage"] = CYCLE_STAGES[idx + 1]
    return update_entry(entry_id, data)


def record_review(entry_id: int, *,
                      next_review_due: str | None = None,
                      outcomes: str | None = None,
                      reviewed_on: str | None = None) -> SENDEntry:
    e = get_entry(entry_id)
    if e is None:
        raise ValidationError(f"No SEND entry with id {entry_id}")
    data = _to_dict(e)
    data["last_review_on"] = (reviewed_on
                                   or _dt.date.today().isoformat())
    if next_review_due is not None:
        data["next_review_due"] = next_review_due
    if outcomes:
        data["outcomes"] = outcomes
    data["cycle_stage"] = "Review"
    return update_entry(entry_id, data)


def set_status(entry_id: int, new_status: str) -> SENDEntry:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    e = get_entry(entry_id)
    if e is None:
        raise ValidationError(f"No SEND entry with id {entry_id}")
    return update_entry(entry_id,
                            {**_to_dict(e), "status": new_status})


def exit_register(entry_id: int, *, reason: str,
                       exit_on: str | None = None) -> SENDEntry:
    if not reason:
        raise ValidationError("Exit reason is required")
    e = get_entry(entry_id)
    if e is None:
        raise ValidationError(f"No SEND entry with id {entry_id}")
    data = _to_dict(e)
    data["status"] = "Exited"
    data["exit_reason"] = reason
    data["exit_on"] = exit_on or _dt.date.today().isoformat()
    return update_entry(entry_id, data)


# ── Summary ───────────────────────────────────────────────────────

def summary() -> SENDSummary:
    rows = list_entries()
    out = SENDSummary(total=len(rows))
    students: set[str] = set()
    today = _dt.date.today().isoformat()
    for e in rows:
        students.add(e.student_id)
        if e.is_open:
            out.open_count += 1
        if e.register_status == "EHCP":
            out.ehcp_count += 1
        if (e.is_open and e.next_review_due
                and e.next_review_due < today):
            out.overdue_reviews += 1
        out.by_register_status[e.register_status] = (
            out.by_register_status.get(e.register_status, 0) + 1)
        out.by_primary_need[e.primary_need] = (
            out.by_primary_need.get(e.primary_need, 0) + 1)
        out.by_cycle_stage[e.cycle_stage] = (
            out.by_cycle_stage.get(e.cycle_stage, 0) + 1)
        out.by_status[e.status] = out.by_status.get(e.status, 0) + 1
    out.distinct_students = len(students)
    return out


__all__ = [
    "REGISTER_STATUSES", "DEFAULT_REGISTER_STATUS",
    "NEED_TYPES", "DEFAULT_NEED_TYPE",
    "CYCLE_STAGES", "DEFAULT_CYCLE_STAGE",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "SENDEntry", "SENDSummary",
    "init_db",
    "create_entry", "update_entry", "delete_entry",
    "get_entry", "list_entries", "entries_for_student",
    "advance_cycle", "record_review",
    "set_status", "exit_register",
    "summary",
]
