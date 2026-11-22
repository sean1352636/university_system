"""SEND register data layer for Sixth Form System.

One row per student per active register entry. Tracks register
status (Monitoring / SEN Support / EHCP / Exited), primary &
secondary need, assess-plan-do-review cycle progression, provision
summary, key worker / SENCo, external agencies and review schedule.
There is at most one open entry per student.

The register is the **single source of truth for SEND status**. The
Accessibility module keeps its ``accessibility_profiles.send_status``
column (other screens and the exams office read it) but every change
here is pushed into it by :func:`sync_accessibility_profile`.

EHCP detail added on top of the register entry:

* local authority and named LA caseworker (columns on the entry);
* ``send_ehcp_reviews`` — the annual review history (date, attendees,
  outcomes, amendments requested, report to the LA, LA decision);
* ``send_hn_funding`` — high-needs funding records (element 2 / 3,
  LA, academic year). The funding module is Finance's; this only
  records what the LA agreed.

New EHCP functions require the SEND capability and are audited.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system import paths as _paths
from education_system.systems.sixth_form.infrastructure import soft_delete as _soft
from education_system.systems.sixth_form.domain.pastoral import _records

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
    local_authority: str | None = None
    la_caseworker: str | None = None
    la_caseworker_email: str | None = None
    la_caseworker_phone: str | None = None
    #: Archive (soft delete) — set by delete_*, cleared by restore_*.
    archived_at: str | None = None
    archived_by: str | None = None
    archive_reason: str | None = None

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
    _paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(_paths.SIXTH_FORM_SEND_DB)
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
        _records.ensure_columns(conn, "send_register", {
            "local_authority": "TEXT",
            "la_caseworker": "TEXT",
            "la_caseworker_email": "TEXT",
            "la_caseworker_phone": "TEXT",
        })
        conn.executescript(_EHCP_SCHEMA)
        _soft.ensure_columns(conn, "send_register")


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
               "senco", "pupil_voice", "exit_reason", "notes",
               "local_authority", "la_caseworker", "la_caseworker_email",
               "la_caseworker_phone"):
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
        local_authority=_opt(r, "local_authority"),
        la_caseworker=_opt(r, "la_caseworker"),
        la_caseworker_email=_opt(r, "la_caseworker_email"),
        la_caseworker_phone=_opt(r, "la_caseworker_phone"),
        archived_at=r["archived_at"] if "archived_at" in r.keys() else None,
        archived_by=r["archived_by"] if "archived_by" in r.keys() else None,
        archive_reason=r["archive_reason"] if "archive_reason" in r.keys() else None,
    )


def _opt(r: sqlite3.Row, key: str) -> Any:
    return r[key] if key in r.keys() else None


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
        _write_la_fields(conn, new_id, p)
    sync_accessibility_profile(p["student_id"])
    return get_entry(new_id)


def _write_la_fields(conn: sqlite3.Connection, entry_id: int,
                     p: dict[str, Any]) -> None:
    conn.execute(
        "UPDATE send_register SET local_authority=?, la_caseworker=?, "
        "la_caseworker_email=?, la_caseworker_phone=? WHERE entry_id=?",
        (p.get("local_authority"), p.get("la_caseworker"),
         p.get("la_caseworker_email"), p.get("la_caseworker_phone"),
         entry_id))


def update_entry(entry_id: int,
                    payload: dict[str, Any]) -> SENDEntry:
    init_db()
    before = get_entry(entry_id)
    if before is None:
        raise ValidationError(f"No SEND entry with id {entry_id}")
    # Callers that predate the LA columns pass the old field set only.
    payload = dict(payload)
    for k in ("local_authority", "la_caseworker", "la_caseworker_email",
              "la_caseworker_phone"):
        payload.setdefault(k, getattr(before, k))
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
        _write_la_fields(conn, entry_id, p)
    sync_accessibility_profile(p["student_id"])
    if before.student_id != p["student_id"]:
        sync_accessibility_profile(before.student_id)
    return get_entry(entry_id)


def delete_entry(entry_id: int, *, reason: str | None = None) -> bool:
    """Archive the SEND register entry (a soft delete: UK retention rules expect it to
    be kept). It drops out of :func:`list_entries` unless
    ``include_archived=True``, keeps who/when/why, and can be brought
    back with :func:`restore_entry`. Nothing is
    hard-deleted. Returns False if unknown or already archived."""
    init_db()
    before = get_entry(entry_id)
    with _connect() as conn:
        ok = _soft.archive(conn, "send_register", "entry_id", entry_id,
                           by=_archive_actor(), reason=reason)
        if ok:
            # Also closed in the status every other reader already
            # honours (directory, wellbeing, duplicate check).
            conn.execute("UPDATE send_register SET status='Archived' "
                         "WHERE entry_id=?", (entry_id,))
    if ok and before is not None:
        sync_accessibility_profile(before.student_id)
    return ok


def restore_entry(entry_id: int) -> bool:
    """Undo :func:`delete_entry` (archive)."""
    init_db()
    before = get_entry(entry_id)
    with _connect() as conn:
        ok = _soft.restore(conn, "send_register", "entry_id", entry_id)
        if ok and before is not None and not conn.execute(
                "SELECT 1 FROM send_register WHERE student_id=? "
                "AND entry_id<>? AND archived_at IS NULL AND status NOT IN "
                "('Exited','Archived')", (before.student_id, entry_id)
                ).fetchone():
            # Reopen it, unless the student has since got another open
            # entry (at most one open entry per student).
            conn.execute("UPDATE send_register SET status=? "
                         "WHERE entry_id=? AND status='Archived'",
                         (DEFAULT_STATUS, entry_id))
    if ok and before is not None:
        sync_accessibility_profile(before.student_id)
    return ok


def _archive_actor() -> str | None:
    """Username recorded on archive (the signed-in principal)."""
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or None
    except Exception:
        return None


def get_entry(entry_id: int) -> SENDEntry | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM send_register WHERE entry_id=?",
            (entry_id,)).fetchone()
        return _row(r) if r else None


def list_entries(*,
                    include_archived: bool = False,
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
    if not include_archived:
        sql += " AND archived_at IS NULL"
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
        "local_authority": e.local_authority,
        "la_caseworker": e.la_caseworker,
        "la_caseworker_email": e.la_caseworker_email,
        "la_caseworker_phone": e.la_caseworker_phone,
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
    # Single source of truth for SEND status
    "ACCESSIBILITY_STATUS_MAP", "accessibility_status_for",
    "sync_accessibility_profile", "sync_all_accessibility_profiles",
    # EHCP
    "EHCP_REVIEW_TYPES", "EHCP_RECOMMENDATIONS", "LA_DECISIONS",
    "EHCPReview", "HighNeedsFunding", "EHCP_REVIEW_SPEC", "HN_FUNDING_SPEC",
    "set_la_details", "record_ehcp_review", "list_ehcp_reviews",
    "get_ehcp_review", "update_ehcp_review", "delete_ehcp_review",
    "record_la_decision", "ehcp_reviews_due", "EHCPReviewDue",
    "create_hn_funding", "list_hn_funding", "get_hn_funding",
    "update_hn_funding", "delete_hn_funding",
]


# ══ Single source of truth → Accessibility profile ════════════════

#: Register status -> accessibility_profiles.send_status value.
ACCESSIBILITY_STATUS_MAP: dict[str, str] = {
    "Monitoring": "Monitoring",
    "SEN Support": "SEN Support",
    "EHCP": "EHCP",
    "Awaiting Assessment": "Monitoring",
    "Exited": "Exited",
}


def accessibility_status_for(student_id: str
                             ) -> tuple[str, SENDEntry] | None:
    """The send_status an accessibility profile should show, derived
    from the register: the open entry's status, or 'Exited' when the
    student only has closed entries. ``None`` = not on the register."""
    rows = list_entries(student_id=student_id)
    if not rows:
        return None
    open_rows = [e for e in rows if e.is_open]
    if open_rows:
        e = open_rows[0]
        return ACCESSIBILITY_STATUS_MAP.get(e.register_status,
                                            "Monitoring"), e
    return "Exited", rows[0]


def sync_accessibility_profile(student_id: str) -> bool:
    """Copy the register's status into the student's accessibility
    profile (if they have one). Returns True when a row was updated.
    Students not on the register keep whatever the profile says."""
    derived = accessibility_status_for(student_id)
    if derived is None:
        return False
    status, e = derived
    with _connect() as conn:
        if not _records.table_exists(conn, "accessibility_profiles"):
            return False
        cur = conn.execute(
            "UPDATE accessibility_profiles SET send_status = ?, "
            "has_ehcp = ?, "
            "ehcp_reference = COALESCE(?, ehcp_reference), "
            "primary_need = COALESCE(?, primary_need), "
            "updated_at = datetime('now') "
            "WHERE student_id = ? AND (send_status IS NOT ? "
            "  OR has_ehcp IS NOT ? "
            "  OR (? IS NOT NULL AND ehcp_reference IS NOT ?) "
            "  OR (? IS NOT NULL AND primary_need IS NOT ?))",
            (status, 1 if status == "EHCP" else 0,
             e.ehcp_reference, e.primary_need if e.is_open else None,
             student_id, status, 1 if status == "EHCP" else 0,
             e.ehcp_reference, e.ehcp_reference,
             e.primary_need if e.is_open else None,
             e.primary_need if e.is_open else None))
        changed = cur.rowcount > 0
    if changed:
        logger.info("Accessibility profile for %s synced from SEND "
                    "register (%s)", student_id, status)
    return changed


def sync_all_accessibility_profiles() -> int:
    """Run :func:`sync_accessibility_profile` for every student on the
    register. Returns how many profiles changed."""
    init_db()
    with _connect() as conn:
        sids = [r[0] for r in conn.execute(
            "SELECT DISTINCT student_id FROM send_register")]
    return sum(1 for sid in sids if sync_accessibility_profile(sid))


# ══ EHCP annual reviews and high-needs funding ═════════════════════

EHCP_REVIEW_TYPES: tuple[str, ...] = (
    "Annual Review", "Interim Review", "Phase Transfer Review",
    "Emergency Review",
)
EHCP_RECOMMENDATIONS: tuple[str, ...] = (
    "Maintain unchanged", "Amend", "Cease",
)
LA_DECISIONS: tuple[str, ...] = (
    "Pending", "Maintain unchanged", "Amend (draft issued)",
    "Amended plan issued", "Cease", "Cease (appealed)",
)

_EHCP_SCHEMA = """
CREATE TABLE IF NOT EXISTS send_ehcp_reviews (
    review_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id              INTEGER NOT NULL,
    student_id            TEXT NOT NULL,
    review_date           TEXT NOT NULL,
    review_type           TEXT NOT NULL DEFAULT 'Annual Review',
    attendees             TEXT,
    local_authority       TEXT,
    la_officer_attended   INTEGER NOT NULL DEFAULT 0,
    student_views         TEXT,
    parent_views          TEXT,
    outcomes_progress     TEXT,
    recommendation        TEXT,
    amendments_requested  TEXT,
    report_sent_to_la_on  TEXT,
    la_decision           TEXT NOT NULL DEFAULT 'Pending',
    la_decision_date      TEXT,
    next_review_due       TEXT,
    recorded_by           TEXT,
    notes                 TEXT,
    created_at            TEXT DEFAULT (datetime('now')),
    updated_at            TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (entry_id) REFERENCES send_register(entry_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS send_hn_funding (
    funding_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id          INTEGER NOT NULL,
    student_id        TEXT NOT NULL,
    academic_year     TEXT NOT NULL,
    local_authority   TEXT NOT NULL,
    element2_amount   REAL,
    element3_amount   REAL,
    funding_band      TEXT,
    agreed_on         TEXT,
    start_date        TEXT,
    end_date          TEXT,
    la_reference      TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (entry_id) REFERENCES send_register(entry_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ehcp_rev_entry ON send_ehcp_reviews(entry_id);
CREATE INDEX IF NOT EXISTS idx_ehcp_rev_date  ON send_ehcp_reviews(review_date);
CREATE INDEX IF NOT EXISTS idx_hnf_entry      ON send_hn_funding(entry_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_hnf_entry_year
    ON send_hn_funding(entry_id, academic_year);
"""


@dataclass
class EHCPReview:
    review_id: int
    entry_id: int
    student_id: str
    review_date: str
    review_type: str
    attendees: str | None
    local_authority: str | None
    la_officer_attended: bool
    student_views: str | None
    parent_views: str | None
    outcomes_progress: str | None
    recommendation: str | None
    amendments_requested: str | None
    report_sent_to_la_on: str | None
    la_decision: str
    la_decision_date: str | None
    next_review_due: str | None
    recorded_by: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def report_overdue(self) -> bool:
        """SEND Code of Practice: the review report goes to the LA
        within two weeks of the meeting."""
        if self.report_sent_to_la_on:
            return False
        due = (_dt.date.fromisoformat(self.review_date)
               + _dt.timedelta(days=14)).isoformat()
        return due < _dt.date.today().isoformat()

    @property
    def decision_overdue(self) -> bool:
        """The LA must decide within four weeks of the meeting."""
        if self.la_decision != "Pending":
            return False
        due = (_dt.date.fromisoformat(self.review_date)
               + _dt.timedelta(days=28)).isoformat()
        return due < _dt.date.today().isoformat()


@dataclass
class HighNeedsFunding:
    funding_id: int
    entry_id: int
    student_id: str
    academic_year: str
    local_authority: str
    element2_amount: float | None
    element3_amount: float | None
    funding_band: str | None
    agreed_on: str | None
    start_date: str | None
    end_date: str | None
    la_reference: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def total(self) -> float:
        return round((self.element2_amount or 0)
                     + (self.element3_amount or 0), 2)


_C = _records.Col

EHCP_REVIEW_SPEC = _records.TableSpec(
    table="send_ehcp_reviews", id_col="review_id", row_type=EHCPReview,
    label="EHCP review", order_by="review_date DESC, review_id DESC",
    cols=(
        _C("entry_id", "SEND entry #", "int", required=True, fixed=True),
        _C("student_id", "Student", "student", fixed=True, hidden=True),
        _C("review_date", "Review date", "date", required=True,
           default=_records.today),
        _C("review_type", "Type", "choice", choices=EHCP_REVIEW_TYPES,
           default="Annual Review"),
        _C("attendees", "Attendees"),
        _C("local_authority", "Local authority"),
        _C("la_officer_attended", "LA officer attended", "bool",
           listed=False),
        _C("student_views", "Student views", "multiline", listed=False),
        _C("parent_views", "Parent / carer views", "multiline",
           listed=False),
        _C("outcomes_progress", "Progress towards outcomes", "multiline",
           listed=False),
        _C("recommendation", "Recommendation", "choice",
           choices=EHCP_RECOMMENDATIONS),
        _C("amendments_requested", "Amendments requested", "multiline"),
        _C("report_sent_to_la_on", "Report sent to LA", "date"),
        _C("la_decision", "LA decision", "choice", choices=LA_DECISIONS,
           default="Pending"),
        _C("la_decision_date", "LA decision date", "date"),
        _C("next_review_due", "Next review due", "date"),
        _C("recorded_by", "Recorded by", listed=False),
        _C("notes", "Notes", "multiline", listed=False),
    ))

_YEAR_RE = re.compile(r"^\d{4}/\d{2}$")

HN_FUNDING_SPEC = _records.TableSpec(
    table="send_hn_funding", id_col="funding_id", row_type=HighNeedsFunding,
    label="High-needs funding", order_by="academic_year DESC, funding_id DESC",
    cols=(
        _C("entry_id", "SEND entry #", "int", required=True, fixed=True),
        _C("student_id", "Student", "student", fixed=True, hidden=True),
        _C("academic_year", "Academic year (YYYY/YY)", required=True),
        _C("local_authority", "Funding LA (blank = entry's LA)"),
        _C("element2_amount", "Element 2 (£)", "money"),
        _C("element3_amount", "Element 3 top-up (£)", "money"),
        _C("funding_band", "Band / matrix level"),
        _C("agreed_on", "Agreed on", "date"),
        _C("start_date", "Start", "date", listed=False),
        _C("end_date", "End", "date", listed=False),
        _C("la_reference", "LA reference"),
        _C("notes", "Notes", "multiline", listed=False),
    ))


def _send_guard(action: str, student_id: str | None = None,
                ref: str | None = None) -> Any:
    return _records.guard("SEND", "send", action, student_id=student_id,
                          record_ref=ref)


def _entry_or_error(entry_id: int) -> SENDEntry:
    e = get_entry(entry_id)
    if e is None:
        raise ValidationError(f"No SEND entry with id {entry_id}")
    return e


def set_la_details(entry_id: int, *, local_authority: str | None,
                   caseworker: str | None = None,
                   caseworker_email: str | None = None,
                   caseworker_phone: str | None = None) -> SENDEntry:
    """Set the responsible local authority and named EHCP caseworker."""
    e = _entry_or_error(entry_id)
    _send_guard("set LA details", e.student_id, f"send:{entry_id}")
    return update_entry(entry_id, {
        **_to_dict(e),
        "local_authority": local_authority,
        "la_caseworker": caseworker,
        "la_caseworker_email": caseworker_email,
        "la_caseworker_phone": caseworker_phone,
    })


def _review_rules(p: dict[str, Any]) -> None:
    for k, label in (("la_decision_date", "LA decision date"),
                     ("report_sent_to_la_on", "Report sent date"),
                     ("next_review_due", "Next review")):
        if p.get(k) and p[k] < p["review_date"]:
            raise ValidationError(f"{label} cannot be before the review")
    if p.get("la_decision") and p["la_decision"] != "Pending" \
            and not p.get("la_decision_date"):
        p["la_decision_date"] = _records.today()


def record_ehcp_review(data: dict[str, Any]) -> EHCPReview:
    """Log an EHCP review meeting. Rolls the register entry's
    last/next review dates forward when it is the latest review."""
    init_db()
    p = _records.validate(EHCP_REVIEW_SPEC, data, error=ValidationError)
    e = _entry_or_error(p["entry_id"])
    if e.register_status != "EHCP":
        raise ValidationError(
            f"SEND entry #{e.entry_id} is not an EHCP entry "
            f"({e.register_status})")
    actor = _send_guard("record EHCP review", e.student_id,
                        f"send:{e.entry_id}")
    p["student_id"] = e.student_id
    p["local_authority"] = p["local_authority"] or e.local_authority
    p["recorded_by"] = (p["recorded_by"] or actor.staff_name
                        or actor.username or None)
    if not p["next_review_due"] and p["review_type"] == "Annual Review":
        d = _dt.date.fromisoformat(p["review_date"])
        try:
            p["next_review_due"] = d.replace(year=d.year + 1).isoformat()
        except ValueError:          # 29 February
            p["next_review_due"] = (d + _dt.timedelta(days=365)).isoformat()
    _review_rules(p)
    with _connect() as conn:
        new_id = _records.insert(conn, EHCP_REVIEW_SPEC, p)
    _roll_review_dates(e.entry_id)
    logger.info("Recorded %s #%d for SEND entry #%d", p["review_type"],
                new_id, e.entry_id)
    return get_ehcp_review(new_id)


def _roll_review_dates(entry_id: int) -> None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT review_date, next_review_due FROM send_ehcp_reviews "
            "WHERE entry_id = ? ORDER BY review_date DESC, review_id DESC "
            "LIMIT 1", (entry_id,)).fetchone()
        if r is None:
            return
        conn.execute(
            "UPDATE send_register SET last_review_on = ?, "
            "next_review_due = COALESCE(?, next_review_due), "
            "updated_on = ? WHERE entry_id = ?",
            (r["review_date"], r["next_review_due"],
             _dt.datetime.now().isoformat(timespec="seconds"), entry_id))


def get_ehcp_review(review_id: int) -> EHCPReview | None:
    init_db()
    with _connect() as conn:
        r = _records.fetch(conn, EHCP_REVIEW_SPEC, review_id)
    if r is not None:
        _send_guard("view EHCP review", r.student_id, f"ehcp_rev:{review_id}")
    return r


def list_ehcp_reviews(*, entry_id: int | None = None,
                      student_id: str | None = None,
                      decision_pending: bool = False) -> list[EHCPReview]:
    init_db()
    _send_guard("list EHCP reviews", student_id)
    where = ["la_decision = 'Pending'"] if decision_pending else []
    with _connect() as conn:
        rows = _records.select(
            conn, EHCP_REVIEW_SPEC,
            equals={"entry_id": entry_id, "student_id": student_id},
            where=where)
    return _records.visible_filter("SEND", rows)


def update_ehcp_review(review_id: int, data: dict[str, Any]) -> EHCPReview:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, EHCP_REVIEW_SPEC, review_id)
    if existing is None:
        raise ValidationError(f"No EHCP review #{review_id}")
    p = _records.validate(EHCP_REVIEW_SPEC, data, error=ValidationError,
                          existing=existing)
    _review_rules(p)
    _send_guard("update EHCP review", existing.student_id,
                f"ehcp_rev:{review_id}")
    with _connect() as conn:
        _records.update(conn, EHCP_REVIEW_SPEC, review_id, p)
    _roll_review_dates(existing.entry_id)
    return get_ehcp_review(review_id)


def record_la_decision(review_id: int, *, decision: str,
                       decision_date: str | None = None,
                       notes: str | None = None) -> EHCPReview:
    if decision not in LA_DECISIONS:
        raise ValidationError(
            f"LA decision must be one of: {', '.join(LA_DECISIONS)}")
    payload: dict[str, Any] = {
        "la_decision": decision,
        "la_decision_date": decision_date or _records.today(),
    }
    if notes:
        existing = get_ehcp_review(review_id)
        if existing is None:
            raise ValidationError(f"No EHCP review #{review_id}")
        line = f"[LA decision {payload['la_decision_date']}] {notes.strip()}"
        payload["notes"] = (f"{existing.notes}\n{line}"
                            if existing.notes else line)
    return update_ehcp_review(review_id, payload)


def delete_ehcp_review(review_id: int) -> bool:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, EHCP_REVIEW_SPEC, review_id)
        if existing is None:
            return False
        _send_guard("delete EHCP review", existing.student_id,
                    f"ehcp_rev:{review_id}")
        ok = _records.delete(conn, EHCP_REVIEW_SPEC, review_id)
    _roll_review_dates(existing.entry_id)
    return ok


@dataclass
class EHCPReviewDue:
    entry: SENDEntry
    last_annual_review: str | None
    due_on: str | None
    overdue: bool
    reason: str


def ehcp_reviews_due(*, within_days: int = 30) -> list[EHCPReviewDue]:
    """Open EHCP entries whose annual review is overdue or due within
    *within_days*. An EHCP must be reviewed at least every 12 months;
    with no review on record the due date is 12 months after the plan
    was issued (or the student joined the register)."""
    init_db()
    _send_guard("list EHCP reviews due")
    today = _dt.date.today()
    horizon = (today + _dt.timedelta(days=within_days)).isoformat()
    with _connect() as conn:
        last = {r[0]: r[1] for r in conn.execute(
            "SELECT entry_id, MAX(review_date) FROM send_ehcp_reviews "
            "WHERE review_type IN ('Annual Review','Phase Transfer Review') "
            "GROUP BY entry_id")}
    out: list[EHCPReviewDue] = []
    for e in list_entries(register_status="EHCP", open_only=True):
        base = last.get(e.entry_id)
        reason = "12 months since last annual review"
        if base is None:
            base = e.ehcp_issued_on or e.date_added
            reason = "no annual review recorded"
        try:
            d = _dt.date.fromisoformat(base)
            due12 = d.replace(year=d.year + 1).isoformat()
        except ValueError:
            due12 = (_dt.date.fromisoformat(base)
                     + _dt.timedelta(days=365)).isoformat()
        due = min(x for x in (due12, e.next_review_due) if x)
        if due == e.next_review_due and due != due12:
            reason = "next review date on the register"
        if due <= horizon:
            out.append(EHCPReviewDue(
                entry=e, last_annual_review=last.get(e.entry_id),
                due_on=due, overdue=due < today.isoformat(),
                reason=reason))
    out.sort(key=lambda x: x.due_on or "")
    visible = {e.entry_id for e in _records.visible_filter(
        "SEND", [x.entry for x in out])}
    return [x for x in out if x.entry.entry_id in visible]


# ── High-needs funding ────────────────────────────────────────────

def _funding_rules(p: dict[str, Any]) -> None:
    if not p.get("local_authority"):
        raise ValidationError("Funding local authority is required")
    if not _YEAR_RE.match(p["academic_year"]):
        raise ValidationError("Academic year must look like 2026/27")
    y1, y2 = int(p["academic_year"][:4]), int(p["academic_year"][5:])
    if (y1 + 1) % 100 != y2:
        raise ValidationError("Academic year must be consecutive, "
                              "e.g. 2026/27")
    if p["element2_amount"] is None and p["element3_amount"] is None:
        raise ValidationError("Enter an element 2 and/or element 3 amount")
    if p["start_date"] and p["end_date"] and p["end_date"] < p["start_date"]:
        raise ValidationError("End date cannot be before start date")


def create_hn_funding(data: dict[str, Any]) -> HighNeedsFunding:
    init_db()
    p = _records.validate(HN_FUNDING_SPEC, data, error=ValidationError)
    e = _entry_or_error(p["entry_id"])
    p["student_id"] = e.student_id
    if not p.get("local_authority") and e.local_authority:
        p["local_authority"] = e.local_authority
    _funding_rules(p)
    _send_guard("create high-needs funding", e.student_id,
                f"send:{e.entry_id}")
    try:
        with _connect() as conn:
            new_id = _records.insert(conn, HN_FUNDING_SPEC, p)
    except sqlite3.IntegrityError as exc:
        raise ValidationError(
            f"SEND entry #{e.entry_id} already has a funding record for "
            f"{p['academic_year']} — edit it instead") from exc
    logger.info("Recorded high-needs funding #%d (%s, £%.2f) for entry #%d",
                new_id, p["academic_year"],
                (p["element2_amount"] or 0) + (p["element3_amount"] or 0),
                e.entry_id)
    return get_hn_funding(new_id)


def get_hn_funding(funding_id: int) -> HighNeedsFunding | None:
    init_db()
    with _connect() as conn:
        r = _records.fetch(conn, HN_FUNDING_SPEC, funding_id)
    if r is not None:
        _send_guard("view high-needs funding", r.student_id,
                    f"hnf:{funding_id}")
    return r


def list_hn_funding(*, entry_id: int | None = None,
                    student_id: str | None = None,
                    academic_year: str | None = None
                    ) -> list[HighNeedsFunding]:
    init_db()
    _send_guard("list high-needs funding", student_id)
    with _connect() as conn:
        rows = _records.select(conn, HN_FUNDING_SPEC, equals={
            "entry_id": entry_id, "student_id": student_id,
            "academic_year": academic_year})
    return _records.visible_filter("SEND", rows)


def update_hn_funding(funding_id: int,
                      data: dict[str, Any]) -> HighNeedsFunding:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, HN_FUNDING_SPEC, funding_id)
    if existing is None:
        raise ValidationError(f"No funding record #{funding_id}")
    p = _records.validate(HN_FUNDING_SPEC, data, error=ValidationError,
                          existing=existing)
    _funding_rules(p)
    _send_guard("update high-needs funding", existing.student_id,
                f"hnf:{funding_id}")
    try:
        with _connect() as conn:
            _records.update(conn, HN_FUNDING_SPEC, funding_id, p)
    except sqlite3.IntegrityError as exc:
        raise ValidationError(
            f"Another funding record exists for {p['academic_year']}"
        ) from exc
    return get_hn_funding(funding_id)


def delete_hn_funding(funding_id: int) -> bool:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, HN_FUNDING_SPEC, funding_id)
        if existing is None:
            return False
        _send_guard("delete high-needs funding", existing.student_id,
                    f"hnf:{funding_id}")
        return _records.delete(conn, HN_FUNDING_SPEC, funding_id)
