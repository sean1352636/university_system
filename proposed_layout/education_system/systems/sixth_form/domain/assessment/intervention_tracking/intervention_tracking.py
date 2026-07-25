"""Intervention Tracking — time-bound targeted interventions per student.

One ``interventions`` row per intervention plus a 1:N
``intervention_sessions`` table for per-session attendance and notes.

Two-stage measurement: a **baseline_indicator** captured at the start
(attendance %, current grade, behaviour points, etc.) and an
**exit_indicator** at the end; the difference plus a 1–4
**impact_grade** (OFSTED-style — 4=very strong impact, 1=no impact)
let pastoral staff see whether the intervention actually shifted the
needle.

Cascade: deleting a student wipes their interventions; deleting an
intervention wipes its sessions.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths
from education_system.systems.sixth_form.domain.assessment.intervention_tracking import (
    intervention_tracking as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.INTERVENTION_TRACKING_DB


INTERVENTION_TYPES: tuple[str, ...] = (
    "Academic Support",
    "Subject Tutoring",
    "Literacy",
    "Numeracy",
    "Study Skills",
    "Behaviour",
    "Attendance",
    "Mentoring",
    "Counselling",
    "SEMH",
    "EAL",
    "SEND",
    "Careers / Aspirations",
    "Re-engagement",
    "Other",
)
DEFAULT_INTERVENTION_TYPE: str = "Academic Support"

STATUSES: tuple[str, ...] = (
    "Planned", "Active", "Paused", "Completed",
    "Withdrawn", "Cancelled",
)
DEFAULT_STATUS: str = "Planned"
OPEN_STATUSES: tuple[str, ...] = ("Planned", "Active", "Paused")

FREQUENCIES: tuple[str, ...] = (
    "Daily", "Twice Weekly", "Weekly",
    "Fortnightly", "Monthly", "One-Off", "Ad-hoc",
)
DEFAULT_FREQUENCY: str = "Weekly"

DELIVERY_MODES: tuple[str, ...] = (
    "1:1", "Small Group", "Whole Class", "Online", "Self-Study",
    "Drop-In", "Other",
)
DEFAULT_DELIVERY_MODE: str = "1:1"

# OFSTED-style impact grade.
IMPACT_GRADES: tuple[int, ...] = (1, 2, 3, 4)
_IMPACT_LABELS: dict[int, str] = {
    4: "Very strong impact",
    3: "Strong impact",
    2: "Some impact",
    1: "No / negative impact",
}

SESSION_STATUSES: tuple[str, ...] = (
    "Attended", "Late", "Partial", "Absent",
    "Cancelled", "Rescheduled",
)
DEFAULT_SESSION_STATUS: str = "Attended"
ATTENDED_SESSION_STATUSES: tuple[str, ...] = (
    "Attended", "Late", "Partial",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS interventions (
    intervention_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         TEXT NOT NULL,
    title              TEXT NOT NULL,
    intervention_type  TEXT NOT NULL DEFAULT 'Academic Support',
    subject_name       TEXT,
    lead_staff         TEXT,
    delivery_mode      TEXT,
    frequency          TEXT,
    location           TEXT,
    start_date         TEXT,
    end_date           TEXT,
    sessions_planned   INTEGER,
    status             TEXT NOT NULL DEFAULT 'Planned',
    referral_source    TEXT,
    rationale          TEXT,
    success_criteria   TEXT,
    baseline_indicator TEXT,
    exit_indicator     TEXT,
    impact_grade       INTEGER,
    impact_summary     TEXT,
    funding_source     TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS intervention_sessions (
    session_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    intervention_id    INTEGER NOT NULL,
    session_date       TEXT NOT NULL,
    duration_minutes   INTEGER,
    status             TEXT NOT NULL DEFAULT 'Attended',
    delivered_by       TEXT,
    topic              TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (intervention_id) REFERENCES interventions(intervention_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_iv_student ON interventions(student_id);
CREATE INDEX IF NOT EXISTS idx_iv_type    ON interventions(intervention_type);
CREATE INDEX IF NOT EXISTS idx_iv_status  ON interventions(status);
CREATE INDEX IF NOT EXISTS idx_iv_subject ON interventions(subject_name);
CREATE INDEX IF NOT EXISTS idx_iv_lead    ON interventions(lead_staff);
CREATE INDEX IF NOT EXISTS idx_is_iv      ON intervention_sessions(intervention_id);
CREATE INDEX IF NOT EXISTS idx_is_date    ON intervention_sessions(session_date);
CREATE INDEX IF NOT EXISTS idx_is_status  ON intervention_sessions(status);
"""


@dataclass
class Intervention:
    intervention_id: int
    student_id: str
    title: str
    intervention_type: str
    subject_name: str | None
    lead_staff: str | None
    delivery_mode: str | None
    frequency: str | None
    location: str | None
    start_date: str | None
    end_date: str | None
    sessions_planned: int | None
    status: str
    referral_source: str | None
    rationale: str | None
    success_criteria: str | None
    baseline_indicator: str | None
    exit_indicator: str | None
    impact_grade: int | None
    impact_summary: str | None
    funding_source: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def impact_label(self) -> str:
        return (_IMPACT_LABELS.get(self.impact_grade, "—")
                if self.impact_grade else "—")


@dataclass
class Session:
    session_id: int
    intervention_id: int
    session_date: str
    duration_minutes: int | None
    status: str
    delivered_by: str | None
    topic: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def attended(self) -> bool:
        return self.status in ATTENDED_SESSION_STATUSES


@dataclass
class InterventionDetail:
    intervention: Intervention
    sessions: list[Session] = field(default_factory=list)
    student_name: str = ""

    @property
    def sessions_attended(self) -> int:
        return sum(1 for s in self.sessions if s.attended)

    @property
    def total_minutes(self) -> int:
        return sum((s.duration_minutes or 0)
                    for s in self.sessions if s.attended)

    @property
    def attendance_pct(self) -> float | None:
        relevant = [s for s in self.sessions
                     if s.status != "Cancelled"
                       and s.status != "Rescheduled"]
        if not relevant:
            return None
        return round(100.0 * sum(1 for s in relevant if s.attended)
                       / len(relevant), 1)


@dataclass
class InterventionRow:
    intervention: Intervention
    student_name: str
    sessions_total: int = 0
    sessions_attended: int = 0


@dataclass
class SessionRow:
    session: Session
    student_id: str
    intervention_title: str


@dataclass
class Summary:
    total: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    open_count: int
    distinct_students: int
    total_sessions: int
    attended_sessions: int
    total_minutes: int
    by_impact: dict[int, int]
    average_impact: float | None


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
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Intervention-tracking schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_iv(r: sqlite3.Row) -> Intervention:
    return Intervention(
        intervention_id=r["intervention_id"],
        student_id=r["student_id"], title=r["title"],
        intervention_type=r["intervention_type"],
        subject_name=r["subject_name"],
        lead_staff=r["lead_staff"],
        delivery_mode=r["delivery_mode"],
        frequency=r["frequency"], location=r["location"],
        start_date=r["start_date"], end_date=r["end_date"],
        sessions_planned=r["sessions_planned"],
        status=r["status"], referral_source=r["referral_source"],
        rationale=r["rationale"],
        success_criteria=r["success_criteria"],
        baseline_indicator=r["baseline_indicator"],
        exit_indicator=r["exit_indicator"],
        impact_grade=r["impact_grade"],
        impact_summary=r["impact_summary"],
        funding_source=r["funding_source"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_session(r: sqlite3.Row) -> Session:
    return Session(
        session_id=r["session_id"],
        intervention_id=r["intervention_id"],
        session_date=r["session_date"],
        duration_minutes=r["duration_minutes"],
        status=r["status"], delivered_by=r["delivered_by"],
        topic=r["topic"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
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


def _validate_int(value: Any, label: str, *,
                   min_val: int | None = None,
                   max_val: int | None = None) -> int | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number") from None
    if min_val is not None and n < min_val:
        raise ValidationError(f"{label} must be at least {min_val}")
    if max_val is not None and n > max_val:
        raise ValidationError(f"{label} must be at most {max_val}")
    return n


def _validate_student(value: Any) -> str:
    sid = _require(value, "Student").strip()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_iv_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(payload.get("student_id"))
    out["title"] = _require(payload.get("title"), "Title").strip()

    itype = (payload.get("intervention_type")
              or DEFAULT_INTERVENTION_TYPE).strip()
    if itype not in INTERVENTION_TYPES:
        raise ValidationError(
            f"Type must be one of: "
            f"{', '.join(INTERVENTION_TYPES)}")
    out["intervention_type"] = itype

    status = (payload.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    freq = (payload.get("frequency") or "").strip()
    if freq and freq not in FREQUENCIES:
        raise ValidationError(
            f"Frequency must be one of: {', '.join(FREQUENCIES)}")
    out["frequency"] = freq or None

    mode = (payload.get("delivery_mode") or "").strip()
    if mode and mode not in DELIVERY_MODES:
        raise ValidationError(
            f"Delivery mode must be one of: "
            f"{', '.join(DELIVERY_MODES)}")
    out["delivery_mode"] = mode or None

    out["start_date"] = _validate_date(payload.get("start_date"),
                                            "Start date")
    out["end_date"]   = _validate_date(payload.get("end_date"),
                                            "End date")
    if (out["start_date"] and out["end_date"]
            and out["end_date"] < out["start_date"]):
        raise ValidationError(
            "End date cannot be before start date")

    out["sessions_planned"] = _validate_int(
        payload.get("sessions_planned"),
        "Sessions planned", min_val=0, max_val=1000)

    impact = payload.get("impact_grade")
    if impact in (None, ""):
        out["impact_grade"] = None
    else:
        try:
            n = int(impact)
        except (TypeError, ValueError):
            raise ValidationError(
                "Impact grade must be a whole number") from None
        if n not in IMPACT_GRADES:
            raise ValidationError(
                f"Impact grade must be one of: "
                f"{', '.join(str(g) for g in IMPACT_GRADES)}")
        out["impact_grade"] = n

    out["subject_name"]       = (payload.get("subject_name")
                                    or "").strip() or None
    out["lead_staff"]         = (payload.get("lead_staff")
                                    or "").strip() or None
    out["location"]           = (payload.get("location")
                                    or "").strip() or None
    out["referral_source"]    = (payload.get("referral_source")
                                    or "").strip() or None
    out["rationale"]          = (payload.get("rationale")
                                    or "").strip() or None
    out["success_criteria"]   = (payload.get("success_criteria")
                                    or "").strip() or None
    out["baseline_indicator"] = (payload.get("baseline_indicator")
                                    or "").strip() or None
    out["exit_indicator"]     = (payload.get("exit_indicator")
                                    or "").strip() or None
    out["impact_summary"]     = (payload.get("impact_summary")
                                    or "").strip() or None
    out["funding_source"]     = (payload.get("funding_source")
                                    or "").strip() or None
    out["notes"]              = (payload.get("notes")
                                    or "").strip() or None
    return out


def _validate_session_payload(payload: dict[str, Any]
                               ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    iid = payload.get("intervention_id")
    if iid in (None, ""):
        raise ValidationError("Intervention id is required")
    try:
        out["intervention_id"] = int(iid)
    except (TypeError, ValueError):
        raise ValidationError(
            "Intervention id must be a number") from None
    if get_intervention(out["intervention_id"]) is None:
        raise ValidationError(
            f"No intervention #{out['intervention_id']}")

    out["session_date"] = _validate_date(
        payload.get("session_date"), "Session date",
        required=True)
    out["duration_minutes"] = _validate_int(
        payload.get("duration_minutes"),
        "Duration (mins)", min_val=0, max_val=24 * 60)

    status = (payload.get("status")
               or DEFAULT_SESSION_STATUS).strip()
    if status not in SESSION_STATUSES:
        raise ValidationError(
            f"Session status must be one of: "
            f"{', '.join(SESSION_STATUSES)}")
    out["status"] = status

    out["delivered_by"] = (payload.get("delivered_by")
                              or "").strip() or None
    out["topic"]        = (payload.get("topic") or "").strip() or None
    out["notes"]        = (payload.get("notes") or "").strip() or None
    return out


# ── Intervention CRUD ─────────────────────────────────────────────

def create_intervention(payload: dict[str, Any]) -> Intervention:
    init_db()
    p = _validate_iv_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO interventions
                   (student_id, title, intervention_type,
                    subject_name, lead_staff, delivery_mode,
                    frequency, location, start_date, end_date,
                    sessions_planned, status, referral_source,
                    rationale, success_criteria, baseline_indicator,
                    exit_indicator, impact_grade, impact_summary,
                    funding_source, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["title"], p["intervention_type"],
             p["subject_name"], p["lead_staff"],
             p["delivery_mode"], p["frequency"], p["location"],
             p["start_date"], p["end_date"],
             p["sessions_planned"], p["status"],
             p["referral_source"], p["rationale"],
             p["success_criteria"], p["baseline_indicator"],
             p["exit_indicator"], p["impact_grade"],
             p["impact_summary"], p["funding_source"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_intervention(new_id)
    assert out is not None
    logger.info(
        "Created intervention #%d for %s (%s, status=%s)",
        new_id, p["student_id"], p["intervention_type"],
        p["status"])
    return out


def get_intervention(intervention_id: int) -> Intervention | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM interventions WHERE intervention_id = ?",
            (intervention_id,)).fetchone()
        return _row_iv(r) if r else None


def list_interventions(
    *,
    student_id: str | None = None,
    intervention_type: str | None = None,
    subject_name: str | None = None,
    status: str | None = None,
    lead_like: str | None = None,
    open_only: bool = False,
    impact_grade: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Intervention]:
    init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if intervention_type:
        if intervention_type not in INTERVENTION_TYPES:
            raise ValidationError(
                f"Type must be one of: "
                f"{', '.join(INTERVENTION_TYPES)}")
        clauses.append("intervention_type = ?")
        args.append(intervention_type)
    if subject_name:
        clauses.append("subject_name = ?")
        args.append(subject_name.strip())
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if lead_like:
        clauses.append("lead_staff LIKE ?")
        args.append(f"%{lead_like.strip()}%")
    if open_only:
        ph = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_STATUSES)
    if impact_grade is not None:
        if impact_grade not in IMPACT_GRADES:
            raise ValidationError(
                f"Impact grade must be one of: "
                f"{', '.join(str(g) for g in IMPACT_GRADES)}")
        clauses.append("impact_grade = ?")
        args.append(int(impact_grade))
    if date_from:
        clauses.append("start_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("start_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM interventions {where} "
           "ORDER BY CASE status "
           "  WHEN 'Active'    THEN 0 "
           "  WHEN 'Planned'   THEN 1 "
           "  WHEN 'Paused'    THEN 2 "
           "  WHEN 'Completed' THEN 3 "
           "  WHEN 'Withdrawn' THEN 4 "
           "  WHEN 'Cancelled' THEN 5 "
           "  ELSE 6 END, "
           "start_date DESC NULLS LAST, intervention_id ASC")
    with _connect() as conn:
        return [_row_iv(r)
                for r in conn.execute(sql, args).fetchall()]


def list_interventions_with_detail(**kwargs) -> list[InterventionRow]:
    rows = list_interventions(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name
              for s in _students.list_students()}
    out: list[InterventionRow] = []
    with _connect() as conn:
        for iv in rows:
            stats = conn.execute(
                f"SELECT COUNT(*) total, "
                f"  SUM(CASE WHEN status IN "
                f"  ({','.join('?' * len(ATTENDED_SESSION_STATUSES))}) "
                f"  THEN 1 ELSE 0 END) AS attended "
                f"FROM intervention_sessions "
                f"WHERE intervention_id = ?",
                (*ATTENDED_SESSION_STATUSES,
                  iv.intervention_id)).fetchone()
            out.append(InterventionRow(
                intervention=iv,
                student_name=names.get(iv.student_id, "(unknown)"),
                sessions_total=stats["total"] or 0,
                sessions_attended=stats["attended"] or 0,
            ))
    return out


def get_intervention_detail(intervention_id: int
                              ) -> InterventionDetail | None:
    init_db()
    iv = get_intervention(intervention_id)
    if iv is None:
        return None
    sessions = list_sessions(intervention_id=intervention_id)
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student(iv.student_id)
    name = student.full_name if student else "(unknown)"
    return InterventionDetail(intervention=iv,
                                 sessions=sessions,
                                 student_name=name)


def update_intervention(intervention_id: int,
                          payload: dict[str, Any]) -> Intervention:
    init_db()
    existing = get_intervention(intervention_id)
    if existing is None:
        raise ValidationError(
            f"No intervention #{intervention_id}")
    merged = {
        "student_id":         existing.student_id,
        "title":              payload.get("title", existing.title),
        "intervention_type":  payload.get("intervention_type",
                                           existing.intervention_type),
        "subject_name":       payload.get("subject_name",
                                           existing.subject_name),
        "lead_staff":         payload.get("lead_staff",
                                           existing.lead_staff),
        "delivery_mode":      payload.get("delivery_mode",
                                           existing.delivery_mode),
        "frequency":          payload.get("frequency",
                                           existing.frequency),
        "location":           payload.get("location",
                                           existing.location),
        "start_date":         payload.get("start_date",
                                           existing.start_date),
        "end_date":           payload.get("end_date",
                                           existing.end_date),
        "sessions_planned":   payload.get("sessions_planned",
                                           existing.sessions_planned),
        "status":             payload.get("status", existing.status),
        "referral_source":    payload.get("referral_source",
                                           existing.referral_source),
        "rationale":          payload.get("rationale",
                                           existing.rationale),
        "success_criteria":   payload.get("success_criteria",
                                           existing.success_criteria),
        "baseline_indicator": payload.get("baseline_indicator",
                                           existing.baseline_indicator),
        "exit_indicator":     payload.get("exit_indicator",
                                           existing.exit_indicator),
        "impact_grade":       payload.get("impact_grade",
                                           existing.impact_grade),
        "impact_summary":     payload.get("impact_summary",
                                           existing.impact_summary),
        "funding_source":     payload.get("funding_source",
                                           existing.funding_source),
        "notes":              payload.get("notes", existing.notes),
    }
    p = _validate_iv_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE interventions SET
                   title = ?, intervention_type = ?, subject_name = ?,
                   lead_staff = ?, delivery_mode = ?, frequency = ?,
                   location = ?, start_date = ?, end_date = ?,
                   sessions_planned = ?, status = ?,
                   referral_source = ?, rationale = ?,
                   success_criteria = ?, baseline_indicator = ?,
                   exit_indicator = ?, impact_grade = ?,
                   impact_summary = ?, funding_source = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE intervention_id = ?""",
            (p["title"], p["intervention_type"], p["subject_name"],
             p["lead_staff"], p["delivery_mode"], p["frequency"],
             p["location"], p["start_date"], p["end_date"],
             p["sessions_planned"], p["status"],
             p["referral_source"], p["rationale"],
             p["success_criteria"], p["baseline_indicator"],
             p["exit_indicator"], p["impact_grade"],
             p["impact_summary"], p["funding_source"], p["notes"],
             intervention_id),
        )
        conn.commit()
    out = get_intervention(intervention_id)
    assert out is not None
    return out


def set_status(intervention_id: int, status: str) -> Intervention:
    return update_intervention(intervention_id, {"status": status})


def complete_intervention(intervention_id: int, *,
                            exit_indicator: str | None = None,
                            impact_grade: int | None = None,
                            impact_summary: str | None = None,
                            end_date: str | None = None
                            ) -> Intervention:
    payload: dict[str, Any] = {
        "status": "Completed",
        "end_date": end_date or _dt.date.today().isoformat(),
    }
    if exit_indicator is not None:
        payload["exit_indicator"] = exit_indicator
    if impact_grade is not None:
        payload["impact_grade"] = impact_grade
    if impact_summary is not None:
        payload["impact_summary"] = impact_summary
    return update_intervention(intervention_id, payload)


def delete_intervention(intervention_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM interventions WHERE intervention_id = ?",
            (intervention_id,))
        conn.commit()
        if cur.rowcount:
            logger.info(
                "Deleted intervention #%d (cascade: sessions)",
                intervention_id)
            return True
        return False


# ── Session CRUD ──────────────────────────────────────────────────

def create_session(payload: dict[str, Any]) -> Session:
    init_db()
    p = _validate_session_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO intervention_sessions
                   (intervention_id, session_date, duration_minutes,
                    status, delivered_by, topic, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["intervention_id"], p["session_date"],
             p["duration_minutes"], p["status"],
             p["delivered_by"], p["topic"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_session(new_id)
    assert out is not None
    return out


def log_session(intervention_id: int, *,
                 session_date: str | None = None,
                 duration_minutes: int | None = None,
                 status: str = DEFAULT_SESSION_STATUS,
                 delivered_by: str | None = None,
                 topic: str | None = None,
                 notes: str | None = None) -> Session:
    """Convenience wrapper to log a session in one call."""
    return create_session({
        "intervention_id": intervention_id,
        "session_date":    session_date
                              or _dt.date.today().isoformat(),
        "duration_minutes": duration_minutes,
        "status":           status,
        "delivered_by":     delivered_by,
        "topic":            topic,
        "notes":            notes,
    })


def get_session(session_id: int) -> Session | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM intervention_sessions WHERE session_id = ?",
            (session_id,)).fetchone()
        return _row_session(r) if r else None


def list_sessions(*, intervention_id: int | None = None,
                   status: str | None = None,
                   attended_only: bool = False,
                   date_from: str | None = None,
                   date_to: str | None = None) -> list[Session]:
    init_db()
    clauses, args = [], []
    if intervention_id is not None:
        clauses.append("intervention_id = ?")
        args.append(int(intervention_id))
    if status:
        if status not in SESSION_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(SESSION_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if attended_only:
        ph = ",".join("?" * len(ATTENDED_SESSION_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(ATTENDED_SESSION_STATUSES)
    if date_from:
        clauses.append("session_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("session_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM intervention_sessions {where} "
           "ORDER BY session_date ASC, session_id ASC")
    with _connect() as conn:
        return [_row_session(r)
                for r in conn.execute(sql, args).fetchall()]


def list_sessions_with_detail(**kwargs) -> list[SessionRow]:
    rows = list_sessions(**kwargs)
    if not rows:
        return []
    iv_map: dict[int, tuple[str, str]] = {}
    with _connect() as conn:
        for r in conn.execute(
                "SELECT intervention_id, student_id, title "
                "FROM interventions").fetchall():
            iv_map[r["intervention_id"]] = (r["student_id"],
                                               r["title"])
    out: list[SessionRow] = []
    for s in rows:
        sid, title = iv_map.get(s.intervention_id,
                                   ("", f"#{s.intervention_id}"))
        out.append(SessionRow(session=s, student_id=sid,
                                intervention_title=title))
    return out


def update_session(session_id: int,
                    payload: dict[str, Any]) -> Session:
    init_db()
    existing = get_session(session_id)
    if existing is None:
        raise ValidationError(f"No session #{session_id}")
    merged = {
        "intervention_id":  existing.intervention_id,
        "session_date":     payload.get("session_date",
                                         existing.session_date),
        "duration_minutes": payload.get("duration_minutes",
                                         existing.duration_minutes),
        "status":           payload.get("status", existing.status),
        "delivered_by":     payload.get("delivered_by",
                                         existing.delivered_by),
        "topic":            payload.get("topic", existing.topic),
        "notes":            payload.get("notes", existing.notes),
    }
    p = _validate_session_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE intervention_sessions SET
                   session_date = ?, duration_minutes = ?,
                   status = ?, delivered_by = ?, topic = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE session_id = ?""",
            (p["session_date"], p["duration_minutes"],
             p["status"], p["delivered_by"], p["topic"],
             p["notes"], session_id),
        )
        conn.commit()
    out = get_session(session_id)
    assert out is not None
    return out


def set_session_status(session_id: int, status: str) -> Session:
    return update_session(session_id, {"status": status})


def delete_session(session_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM intervention_sessions WHERE session_id = ?",
            (session_id,))
        conn.commit()
        return bool(cur.rowcount)


# ── Summary ───────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    rows = list_interventions()
    by_status = {s: 0 for s in STATUSES}
    by_type = {t: 0 for t in INTERVENTION_TYPES}
    by_impact = {g: 0 for g in IMPACT_GRADES}
    open_count = 0
    students: set[str] = set()
    impact_sum = 0
    impact_count = 0
    for iv in rows:
        by_status[iv.status] = by_status.get(iv.status, 0) + 1
        by_type[iv.intervention_type] = by_type.get(
            iv.intervention_type, 0) + 1
        students.add(iv.student_id)
        if iv.is_open:
            open_count += 1
        if iv.impact_grade is not None:
            by_impact[iv.impact_grade] = by_impact.get(
                iv.impact_grade, 0) + 1
            impact_sum += iv.impact_grade
            impact_count += 1

    with _connect() as conn:
        total_sess = conn.execute(
            "SELECT COUNT(*) FROM intervention_sessions"
        ).fetchone()[0]
        attended = conn.execute(
            f"SELECT COUNT(*) FROM intervention_sessions "
            f"WHERE status IN "
            f"({','.join('?' * len(ATTENDED_SESSION_STATUSES))})",
            ATTENDED_SESSION_STATUSES).fetchone()[0]
        total_mins = conn.execute(
            f"SELECT COALESCE(SUM(duration_minutes), 0) "
            f"FROM intervention_sessions WHERE status IN "
            f"({','.join('?' * len(ATTENDED_SESSION_STATUSES))})",
            ATTENDED_SESSION_STATUSES).fetchone()[0]

    return Summary(
        total=len(rows),
        by_status=by_status,
        by_type=by_type,
        open_count=open_count,
        distinct_students=len(students),
        total_sessions=total_sess,
        attended_sessions=attended,
        total_minutes=total_mins or 0,
        by_impact=by_impact,
        average_impact=(round(impact_sum / impact_count, 2)
                          if impact_count else None),
    )


# ── Helpers ───────────────────────────────────────────────────────

def impact_label(grade: int | None) -> str:
    return _IMPACT_LABELS.get(grade, "—") if grade else "—"
