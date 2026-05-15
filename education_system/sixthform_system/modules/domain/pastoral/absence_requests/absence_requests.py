"""Absence Requests — planned-absence workflow for the Sixth Form System.

A student (or parent / form tutor) submits a request to be excused from
school over a date range. Pastoral staff review and approve or deny.

This table is *separate* from `attendance_records` (the post-hoc daily
register) and from `attendance_concerns` (interventions on top of poor
attendance). When an approved request overlaps a register date, staff
typically mark the matching attendance rows as ``Authorised``.

Cascade: deleting a student wipes their pending/historical requests.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.pastoral.absence_requests import (
    absence_requests as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.ABSENCE_REQUESTS_DB

REASONS: tuple[str, ...] = (
    "Medical Appointment",
    "Illness",
    "University Open Day",
    "University Interview",
    "Apprenticeship Interview",
    "Work Experience",
    "Family Bereavement",
    "Family Emergency",
    "Religious Observance",
    "Sports / Competition",
    "Driving Test",
    "DBS / Passport Appointment",
    "Other",
)
DEFAULT_REASON: str = "Medical Appointment"

STATUSES: tuple[str, ...] = (
    "Pending",
    "Approved",
    "Denied",
    "Cancelled",
    "Withdrawn",
)
DEFAULT_STATUS: str = "Pending"
OPEN_STATUSES: tuple[str, ...] = ("Pending",)
DECIDED_STATUSES: tuple[str, ...] = ("Approved", "Denied")

SUBMITTERS: tuple[str, ...] = ("Student", "Parent", "Staff", "Other")
DEFAULT_SUBMITTER: str = "Student"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS absence_requests (
    request_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT NOT NULL,
    request_date     TEXT NOT NULL,
    start_date       TEXT NOT NULL,
    end_date         TEXT NOT NULL,
    reason           TEXT NOT NULL,
    description      TEXT,
    status           TEXT NOT NULL DEFAULT 'Pending',
    submitted_by     TEXT,
    submitter_type   TEXT,
    contact_phone    TEXT,
    supporting_doc   TEXT,
    decision_date    TEXT,
    decided_by       TEXT,
    decision_notes   TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_abs_student  ON absence_requests(student_id);
CREATE INDEX IF NOT EXISTS idx_abs_status   ON absence_requests(status);
CREATE INDEX IF NOT EXISTS idx_abs_start    ON absence_requests(start_date);
CREATE INDEX IF NOT EXISTS idx_abs_end      ON absence_requests(end_date);
"""


@dataclass
class AbsenceRequest:
    request_id: int
    student_id: str
    request_date: str
    start_date: str
    end_date: str
    reason: str
    description: str | None
    status: str
    submitted_by: str | None
    submitter_type: str | None
    contact_phone: str | None
    supporting_doc: str | None
    decision_date: str | None
    decided_by: str | None
    decision_notes: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def is_decided(self) -> bool:
        return self.status in DECIDED_STATUSES

    @property
    def day_count(self) -> int:
        try:
            import datetime as _dt
            sd = _dt.date.fromisoformat(self.start_date)
            ed = _dt.date.fromisoformat(self.end_date)
            return max(0, (ed - sd).days) + 1
        except Exception:
            return 0


@dataclass
class RequestRow:
    request: AbsenceRequest
    student_name: str


@dataclass
class Summary:
    total: int
    by_status: dict[str, int]
    by_reason: dict[str, int]
    pending_count: int
    approved_count: int
    denied_count: int
    upcoming_approved: int       # approved & start_date in [today, today+window]
    in_progress: int             # status=Approved & today within [start, end]
    overdue_pending: int         # pending & start_date <= today


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
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Absence-requests schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> AbsenceRequest:
    return AbsenceRequest(
        request_id=r["request_id"],
        student_id=r["student_id"],
        request_date=r["request_date"],
        start_date=r["start_date"],
        end_date=r["end_date"],
        reason=r["reason"],
        description=r["description"],
        status=r["status"],
        submitted_by=r["submitted_by"],
        submitter_type=r["submitter_type"],
        contact_phone=r["contact_phone"],
        supporting_doc=r["supporting_doc"],
        decision_date=r["decision_date"],
        decided_by=r["decided_by"],
        decision_notes=r["decision_notes"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_student(value: Any) -> str:
    sid = _require(value, "Student ID").strip()
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(payload.get("student_id"))
    out["request_date"] = _validate_date(
        payload.get("request_date"), "Request date", required=True)
    out["start_date"] = _validate_date(
        payload.get("start_date"), "Start date", required=True)
    out["end_date"] = _validate_date(
        payload.get("end_date"), "End date", required=True)
    if out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")

    reason = _require(payload.get("reason"), "Reason").strip()
    if reason not in REASONS:
        raise ValidationError(
            f"Reason must be one of: {', '.join(REASONS)}")
    out["reason"] = reason

    status = (payload.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    submitter_type = (payload.get("submitter_type") or "").strip()
    if submitter_type and submitter_type not in SUBMITTERS:
        raise ValidationError(
            f"Submitter type must be one of: {', '.join(SUBMITTERS)}")
    out["submitter_type"] = submitter_type or None

    out["description"]    = (payload.get("description") or "").strip() or None
    out["submitted_by"]   = (payload.get("submitted_by") or "").strip() or None
    out["contact_phone"]  = (payload.get("contact_phone") or "").strip() or None
    out["supporting_doc"] = (payload.get("supporting_doc") or "").strip() or None
    out["decision_date"]  = _validate_date(
        payload.get("decision_date"), "Decision date")
    out["decided_by"]     = (payload.get("decided_by") or "").strip() or None
    out["decision_notes"] = (payload.get("decision_notes") or "").strip() or None
    out["notes"]          = (payload.get("notes") or "").strip() or None

    # Decided statuses imply a decision date / decider.
    if out["status"] in DECIDED_STATUSES:
        if not out["decision_date"]:
            import datetime as _dt
            out["decision_date"] = _dt.date.today().isoformat()
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_request(payload: dict[str, Any]) -> AbsenceRequest:
    init_db()
    p = _validate_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO absence_requests
                   (student_id, request_date, start_date, end_date,
                    reason, description, status,
                    submitted_by, submitter_type, contact_phone,
                    supporting_doc, decision_date, decided_by,
                    decision_notes, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["request_date"], p["start_date"],
             p["end_date"], p["reason"], p["description"], p["status"],
             p["submitted_by"], p["submitter_type"], p["contact_phone"],
             p["supporting_doc"], p["decision_date"], p["decided_by"],
             p["decision_notes"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_request(new_id)
    assert out is not None
    logger.info(
        "Created absence request #%d for %s (%s..%s, reason=%s, status=%s)",
        new_id, p["student_id"], p["start_date"], p["end_date"],
        p["reason"], p["status"],
    )
    return out


def get_request(request_id: int) -> AbsenceRequest | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM absence_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        return _row(r) if r else None


def list_requests(
    *,
    student_id: str | None = None,
    status: str | None = None,
    reason: str | None = None,
    pending_only: bool = False,
    decided_only: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
    overlaps_from: str | None = None,
    overlaps_to: str | None = None,
) -> list[AbsenceRequest]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if reason:
        if reason not in REASONS:
            raise ValidationError(
                f"Reason must be one of: {', '.join(REASONS)}")
        clauses.append("reason = ?")
        args.append(reason)
    if pending_only:
        ph = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_STATUSES)
    if decided_only:
        ph = ",".join("?" * len(DECIDED_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(DECIDED_STATUSES)
    if date_from:
        clauses.append("request_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("request_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    if overlaps_from and overlaps_to:
        # [start, end] overlaps [from, to] iff start <= to AND end >= from
        clauses.append("start_date <= ? AND end_date >= ?")
        args.append(_validate_date(overlaps_to, "overlaps_to"))
        args.append(_validate_date(overlaps_from, "overlaps_from"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM absence_requests {where} "
           "ORDER BY CASE status "
           "  WHEN 'Pending'    THEN 0 "
           "  WHEN 'Approved'   THEN 1 "
           "  WHEN 'Denied'     THEN 2 "
           "  WHEN 'Cancelled'  THEN 3 "
           "  ELSE 4 END, "
           "start_date DESC, request_id DESC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def list_requests_with_detail(**kwargs) -> list[RequestRow]:
    rows = list_requests(**kwargs)
    if not rows:
        return []
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [RequestRow(request=r,
                       student_name=names.get(r.student_id, "(unknown)"))
            for r in rows]


def requests_for_student(student_id: str) -> list[AbsenceRequest]:
    return list_requests(student_id=student_id)


def update_request(request_id: int,
                   payload: dict[str, Any]) -> AbsenceRequest:
    init_db()
    existing = get_request(request_id)
    if existing is None:
        raise ValidationError(f"No absence request with id {request_id}")
    merged = {
        "student_id":     existing.student_id,
        "request_date":   payload.get("request_date", existing.request_date),
        "start_date":     payload.get("start_date", existing.start_date),
        "end_date":       payload.get("end_date", existing.end_date),
        "reason":         payload.get("reason", existing.reason),
        "description":    payload.get("description", existing.description),
        "status":         payload.get("status", existing.status),
        "submitted_by":   payload.get("submitted_by", existing.submitted_by),
        "submitter_type": payload.get("submitter_type",
                                     existing.submitter_type),
        "contact_phone":  payload.get("contact_phone", existing.contact_phone),
        "supporting_doc": payload.get("supporting_doc",
                                     existing.supporting_doc),
        "decision_date":  payload.get("decision_date", existing.decision_date),
        "decided_by":     payload.get("decided_by", existing.decided_by),
        "decision_notes": payload.get("decision_notes",
                                     existing.decision_notes),
        "notes":          payload.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE absence_requests SET
                   request_date = ?, start_date = ?, end_date = ?,
                   reason = ?, description = ?, status = ?,
                   submitted_by = ?, submitter_type = ?, contact_phone = ?,
                   supporting_doc = ?, decision_date = ?, decided_by = ?,
                   decision_notes = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE request_id = ?""",
            (p["request_date"], p["start_date"], p["end_date"],
             p["reason"], p["description"], p["status"],
             p["submitted_by"], p["submitter_type"], p["contact_phone"],
             p["supporting_doc"], p["decision_date"], p["decided_by"],
             p["decision_notes"], p["notes"], request_id),
        )
        conn.commit()
    out = get_request(request_id)
    assert out is not None
    logger.info("Updated absence request #%d (status=%s)",
                request_id, out.status)
    return out


def set_status(
    request_id: int,
    status: str,
    *,
    decided_by: str | None = None,
    decision_notes: str | None = None,
    decision_date: str | None = None,
) -> AbsenceRequest:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    payload: dict[str, Any] = {"status": status}
    if status in DECIDED_STATUSES:
        if decision_date:
            payload["decision_date"] = decision_date
        if decided_by is not None:
            payload["decided_by"] = decided_by
        if decision_notes is not None:
            payload["decision_notes"] = decision_notes
    return update_request(request_id, payload)


def approve(request_id: int, *, decided_by: str | None = None,
            decision_notes: str | None = None) -> AbsenceRequest:
    return set_status(request_id, "Approved",
                       decided_by=decided_by,
                       decision_notes=decision_notes)


def deny(request_id: int, *, decided_by: str | None = None,
         decision_notes: str | None = None) -> AbsenceRequest:
    return set_status(request_id, "Denied",
                       decided_by=decided_by,
                       decision_notes=decision_notes)


def delete_request(request_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM absence_requests WHERE request_id = ?",
            (request_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted absence request #%d", request_id)
            return True
        return False


# ── Summary ───────────────────────────────────────────────────────

def summary(*, upcoming_window_days: int = 14) -> Summary:
    import datetime as _dt
    init_db()
    today = _dt.date.today().isoformat()
    horizon = (_dt.date.today()
                + _dt.timedelta(days=upcoming_window_days)).isoformat()

    rows = list_requests()
    by_status = {st: 0 for st in STATUSES}
    by_reason = {r: 0 for r in REASONS}
    upcoming = 0
    in_progress = 0
    overdue = 0
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_reason[r.reason] = by_reason.get(r.reason, 0) + 1
        if r.status == "Approved":
            if r.start_date <= today <= r.end_date:
                in_progress += 1
            elif today <= r.start_date <= horizon:
                upcoming += 1
        elif r.status == "Pending" and r.start_date <= today:
            overdue += 1

    return Summary(
        total=len(rows),
        by_status=by_status,
        by_reason=by_reason,
        pending_count=by_status.get("Pending", 0),
        approved_count=by_status.get("Approved", 0),
        denied_count=by_status.get("Denied", 0),
        upcoming_approved=upcoming,
        in_progress=in_progress,
        overdue_pending=overdue,
    )
