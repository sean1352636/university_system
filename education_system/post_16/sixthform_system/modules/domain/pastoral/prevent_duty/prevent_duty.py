"""Prevent Duty data layer for the Sixth Form System.

The Prevent Duty (Counter-Terrorism and Security Act 2015) requires
schools and colleges to have due regard to the need to prevent people
from being drawn into terrorism. This module captures the three records
that satisfy a typical sixth-form audit:

* **Concerns** — a logged Prevent concern about a student
  (radicalisation indicator, online activity, peer influence, etc.)
  with a risk grading and a workflow from Reported → Reviewed →
  Channel Referred → Closed (or No Further Action).
* **Referrals** — a Channel referral that escalates one concern.
  Tracks date, referring agency, decision and panel outcome.
* **Training records** — per-staff Prevent training (WRAP / Prevent
  Awareness / Channel Awareness / Refresher) with completion and
  expiry dates so the DSL can audit who is in date.

Cascade rules:
* Deleting a concern cascades its referrals.
* Deleting a student deletes their concerns (and via above, referrals).
* Deleting a staff member deletes their training records.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.post_16.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.PREVENT_DUTY_DB


CONCERN_TYPES: tuple[str, ...] = (
    "Radicalisation indicator", "Extremist material",
    "Online activity", "Peer / family influence",
    "Behavioural change", "Disclosure",
    "Hate-motivated incident", "Other",
)
DEFAULT_CONCERN_TYPE: str = "Radicalisation indicator"

RISK_LEVELS: tuple[str, ...] = ("Low", "Medium", "High")
DEFAULT_RISK_LEVEL: str = "Low"

CONCERN_STATUSES: tuple[str, ...] = (
    "Reported", "Under Review", "Channel Referred",
    "No Further Action", "Closed",
)
DEFAULT_CONCERN_STATUS: str = "Reported"

REFERRAL_AUTHORITIES: tuple[str, ...] = (
    "School", "Local Authority", "Police", "Other",
)
DEFAULT_REFERRAL_AUTHORITY: str = "School"

REFERRAL_STATUSES: tuple[str, ...] = (
    "Submitted", "Accepted", "Declined",
    "Channel Panel", "Supported", "Closed",
)
DEFAULT_REFERRAL_STATUS: str = "Submitted"

TRAINING_TYPES: tuple[str, ...] = (
    "WRAP", "Prevent Awareness", "Channel Awareness",
    "Refresher", "Other",
)
DEFAULT_TRAINING_TYPE: str = "WRAP"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prevent_concerns (
    concern_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    report_date  TEXT NOT NULL,
    concern_type TEXT NOT NULL DEFAULT 'Radicalisation indicator',
    risk_level   TEXT NOT NULL DEFAULT 'Low',
    summary      TEXT NOT NULL,
    details      TEXT,
    reported_by  TEXT,
    status       TEXT NOT NULL DEFAULT 'Reported',
    closed_date  TEXT,
    outcome      TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prevent_referrals (
    referral_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    concern_id      INTEGER NOT NULL,
    referral_date   TEXT NOT NULL,
    authority       TEXT NOT NULL DEFAULT 'School',
    case_officer    TEXT,
    panel_date      TEXT,
    status          TEXT NOT NULL DEFAULT 'Submitted',
    outcome         TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (concern_id) REFERENCES prevent_concerns(concern_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prevent_training (
    training_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id        TEXT NOT NULL,
    training_type   TEXT NOT NULL DEFAULT 'WRAP',
    completed_date  TEXT NOT NULL,
    expiry_date     TEXT,
    provider        TEXT,
    certificate_ref TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pc_student ON prevent_concerns(student_id);
CREATE INDEX IF NOT EXISTS idx_pc_status  ON prevent_concerns(status);
CREATE INDEX IF NOT EXISTS idx_pc_date    ON prevent_concerns(report_date);
CREATE INDEX IF NOT EXISTS idx_pr_concern ON prevent_referrals(concern_id);
CREATE INDEX IF NOT EXISTS idx_pr_status  ON prevent_referrals(status);
CREATE INDEX IF NOT EXISTS idx_pr_date    ON prevent_referrals(referral_date);
CREATE INDEX IF NOT EXISTS idx_pt_staff   ON prevent_training(staff_id);
CREATE INDEX IF NOT EXISTS idx_pt_type    ON prevent_training(training_type);
CREATE INDEX IF NOT EXISTS idx_pt_expiry  ON prevent_training(expiry_date);
"""


# ── Dataclasses ────────────────────────────────────────────────────

@dataclass
class Concern:
    concern_id: int
    student_id: str
    report_date: str
    concern_type: str
    risk_level: str
    summary: str
    details: str | None
    reported_by: str | None
    status: str
    closed_date: str | None
    outcome: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status not in ("No Further Action", "Closed")


@dataclass
class Referral:
    referral_id: int
    concern_id: int
    referral_date: str
    authority: str
    case_officer: str | None
    panel_date: str | None
    status: str
    outcome: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status not in ("Closed", "Declined")


@dataclass
class Training:
    training_id: int
    staff_id: str
    training_type: str
    completed_date: str
    expiry_date: str | None
    provider: str | None
    certificate_ref: str | None
    notes: str | None
    created_at: str
    updated_at: str

    def is_expired(self, *, today: str | None = None) -> bool:
        if self.expiry_date is None:
            return False
        import datetime as _dt
        ref = today or _dt.date.today().isoformat()
        return self.expiry_date < ref

    def days_to_expiry(self, *, today: str | None = None) -> int | None:
        if self.expiry_date is None:
            return None
        import datetime as _dt
        ref = (_dt.date.fromisoformat(today) if today
               else _dt.date.today())
        try:
            exp = _dt.date.fromisoformat(self.expiry_date)
        except ValueError:
            return None
        return (exp - ref).days


@dataclass
class ConcernRow:
    concern: Concern
    student_name: str
    referral_count: int


@dataclass
class ReferralRow:
    referral: Referral
    student_id: str
    student_name: str


@dataclass
class TrainingRow:
    training: Training
    staff_name: str
    expired: bool
    days_to_expiry: int | None


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
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.staff import (
        staff as _staff,
    )
    _students.init_db()
    _staff.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Prevent Duty schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_concern(r: sqlite3.Row) -> Concern:
    return Concern(
        concern_id=r["concern_id"], student_id=r["student_id"],
        report_date=r["report_date"], concern_type=r["concern_type"],
        risk_level=r["risk_level"], summary=r["summary"],
        details=r["details"], reported_by=r["reported_by"],
        status=r["status"], closed_date=r["closed_date"],
        outcome=r["outcome"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_referral(r: sqlite3.Row) -> Referral:
    return Referral(
        referral_id=r["referral_id"], concern_id=r["concern_id"],
        referral_date=r["referral_date"], authority=r["authority"],
        case_officer=r["case_officer"], panel_date=r["panel_date"],
        status=r["status"], outcome=r["outcome"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_training(r: sqlite3.Row) -> Training:
    return Training(
        training_id=r["training_id"], staff_id=r["staff_id"],
        training_type=r["training_type"],
        completed_date=r["completed_date"],
        expiry_date=r["expiry_date"], provider=r["provider"],
        certificate_ref=r["certificate_ref"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation helpers ─────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid Prevent Duty input."""


def _require(value: Any, label: str) -> Any:
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


def _validate_choice(value: Any, label: str,
                     choices: tuple[str, ...], default: str) -> str:
    raw = (value or default)
    s = str(raw).strip() or default
    if s not in choices:
        raise ValidationError(
            f"{label} must be one of: {', '.join(choices)}")
    return s


def _validate_student(value: Any) -> str:
    sid = str(_require(value, "Student ID")).strip()
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_staff(value: Any) -> str:
    sid = str(_require(value, "Staff ID")).strip()
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.staff import (
        staff as _staff,
    )
    if _staff.get_staff(sid) is None:
        raise ValidationError(f"No staff member with id {sid}")
    return sid


# ── Concerns ───────────────────────────────────────────────────────

def _validate_concern_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"]  = _validate_student(data.get("student_id"))
    out["report_date"] = _validate_date(
        data.get("report_date"), "Report date", required=True)
    out["concern_type"] = _validate_choice(
        data.get("concern_type"), "Concern type",
        CONCERN_TYPES, DEFAULT_CONCERN_TYPE)
    out["risk_level"] = _validate_choice(
        data.get("risk_level"), "Risk level",
        RISK_LEVELS, DEFAULT_RISK_LEVEL)
    out["summary"] = _require(data.get("summary"), "Summary").strip()
    if len(out["summary"]) > 200:
        raise ValidationError("Summary must be 200 characters or fewer")
    out["details"]     = (data.get("details") or "").strip() or None
    out["reported_by"] = (data.get("reported_by") or "").strip() or None
    out["status"] = _validate_choice(
        data.get("status"), "Status",
        CONCERN_STATUSES, DEFAULT_CONCERN_STATUS)
    out["closed_date"] = _validate_date(
        data.get("closed_date"), "Closed date")
    if out["status"] in ("No Further Action", "Closed"):
        if out["closed_date"] is None:
            import datetime as _dt
            out["closed_date"] = _dt.date.today().isoformat()
    else:
        if out["closed_date"] is not None:
            # Closed-date set but status open → consistency error
            raise ValidationError(
                "Clear the closed date when status is not Closed / NFA")
    out["outcome"] = (data.get("outcome") or "").strip() or None
    if out["closed_date"] and out["closed_date"] < out["report_date"]:
        raise ValidationError(
            "Closed date cannot be before report date")
    return out


def create_concern(data: dict[str, Any]) -> Concern:
    init_db()
    try:
        p = _validate_concern_payload(data)
    except ValidationError as e:
        logger.warning("create_concern validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO prevent_concerns
                   (student_id, report_date, concern_type, risk_level,
                    summary, details, reported_by, status, closed_date,
                    outcome, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["report_date"], p["concern_type"],
             p["risk_level"], p["summary"], p["details"],
             p["reported_by"], p["status"], p["closed_date"],
             p["outcome"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_concern(new_id)
    assert out is not None
    logger.info(
        "Created Prevent concern #%d for %s (risk=%s, status=%s)",
        new_id, p["student_id"], p["risk_level"], p["status"])
    return out


def get_concern(concern_id: int) -> Concern | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM prevent_concerns WHERE concern_id = ?",
            (concern_id,),
        ).fetchone()
        return _row_concern(r) if r else None


def list_concerns(
    *,
    student_id: str | None = None,
    status: str | None = None,
    risk_level: str | None = None,
    concern_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    open_only: bool = False,
) -> list[Concern]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if status:
        if status not in CONCERN_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(CONCERN_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if risk_level:
        if risk_level not in RISK_LEVELS:
            raise ValidationError(
                f"Risk level must be one of: {', '.join(RISK_LEVELS)}")
        clauses.append("risk_level = ?")
        args.append(risk_level)
    if concern_type:
        if concern_type not in CONCERN_TYPES:
            raise ValidationError(
                f"Concern type must be one of: {', '.join(CONCERN_TYPES)}")
        clauses.append("concern_type = ?")
        args.append(concern_type)
    if date_from:
        clauses.append("report_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("report_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    if open_only:
        clauses.append("status NOT IN ('No Further Action', 'Closed')")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM prevent_concerns {where} "
           "ORDER BY report_date DESC, concern_id DESC")
    with _connect() as conn:
        return [_row_concern(r) for r in conn.execute(sql, args).fetchall()]


def list_concerns_with_detail(**kwargs) -> list[ConcernRow]:
    rows = list_concerns(**kwargs)
    if not rows:
        return []
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    with _connect() as conn:
        counts = dict(conn.execute(
            "SELECT concern_id, COUNT(*) FROM prevent_referrals "
            "GROUP BY concern_id").fetchall())
    return [ConcernRow(
                concern=c,
                student_name=names.get(c.student_id, "(unknown)"),
                referral_count=counts.get(c.concern_id, 0))
            for c in rows]


def update_concern(concern_id: int, data: dict[str, Any]) -> Concern:
    init_db()
    existing = get_concern(concern_id)
    if existing is None:
        raise ValidationError(f"No concern with id {concern_id}")
    merged = {
        "student_id":   existing.student_id,
        "report_date":  data.get("report_date", existing.report_date),
        "concern_type": data.get("concern_type", existing.concern_type),
        "risk_level":   data.get("risk_level", existing.risk_level),
        "summary":      data.get("summary", existing.summary),
        "details":      data.get("details", existing.details),
        "reported_by":  data.get("reported_by", existing.reported_by),
        "status":       data.get("status", existing.status),
        "closed_date":  data.get("closed_date", existing.closed_date),
        "outcome":      data.get("outcome", existing.outcome),
    }
    # If transitioning to a closed status without an explicit closed_date,
    # let the validator default to today.
    if (merged["status"] in ("No Further Action", "Closed")
            and existing.status not in ("No Further Action", "Closed")
            and merged["closed_date"] == existing.closed_date
            and existing.closed_date is None):
        merged["closed_date"] = None
    # If transitioning to an open status, clear the old closed_date.
    if (merged["status"] not in ("No Further Action", "Closed")
            and existing.status in ("No Further Action", "Closed")
            and "closed_date" not in data):
        merged["closed_date"] = None
    p = _validate_concern_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE prevent_concerns SET
                   report_date = ?, concern_type = ?, risk_level = ?,
                   summary = ?, details = ?, reported_by = ?,
                   status = ?, closed_date = ?, outcome = ?,
                   updated_at = datetime('now')
               WHERE concern_id = ?""",
            (p["report_date"], p["concern_type"], p["risk_level"],
             p["summary"], p["details"], p["reported_by"],
             p["status"], p["closed_date"], p["outcome"], concern_id),
        )
        conn.commit()
    out = get_concern(concern_id)
    assert out is not None
    logger.info("Updated Prevent concern #%d (status=%s)",
                concern_id, out.status)
    return out


def close_concern(concern_id: int, *,
                  outcome: str | None = None,
                  closed_date: str | None = None) -> Concern:
    upd: dict[str, Any] = {"status": "Closed"}
    if closed_date is not None:
        upd["closed_date"] = closed_date
    if outcome is not None:
        upd["outcome"] = outcome
    return update_concern(concern_id, upd)


def delete_concern(concern_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM prevent_concerns WHERE concern_id = ?",
            (concern_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted Prevent concern #%d", concern_id)
            return True
        return False


# ── Referrals ──────────────────────────────────────────────────────

def _validate_referral_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    cid = _require(data.get("concern_id"), "Concern id")
    try:
        cid_int = int(cid)
    except (TypeError, ValueError):
        raise ValidationError("Concern id must be a number") from None
    if get_concern(cid_int) is None:
        raise ValidationError(f"No concern with id {cid_int}")
    out["concern_id"] = cid_int
    out["referral_date"] = _validate_date(
        data.get("referral_date"), "Referral date", required=True)
    out["authority"] = _validate_choice(
        data.get("authority"), "Authority",
        REFERRAL_AUTHORITIES, DEFAULT_REFERRAL_AUTHORITY)
    out["case_officer"] = (data.get("case_officer") or "").strip() or None
    out["panel_date"] = _validate_date(
        data.get("panel_date"), "Panel date")
    out["status"] = _validate_choice(
        data.get("status"), "Status",
        REFERRAL_STATUSES, DEFAULT_REFERRAL_STATUS)
    out["outcome"] = (data.get("outcome") or "").strip() or None
    out["notes"]   = (data.get("notes") or "").strip() or None
    if out["panel_date"] and out["panel_date"] < out["referral_date"]:
        raise ValidationError(
            "Panel date cannot be before referral date")
    return out


def create_referral(data: dict[str, Any]) -> Referral:
    init_db()
    try:
        p = _validate_referral_payload(data)
    except ValidationError as e:
        logger.warning("create_referral validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO prevent_referrals
                   (concern_id, referral_date, authority, case_officer,
                    panel_date, status, outcome, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["concern_id"], p["referral_date"], p["authority"],
             p["case_officer"], p["panel_date"], p["status"],
             p["outcome"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_referral(new_id)
    assert out is not None
    # When a referral is opened, bump the concern to "Channel Referred"
    # if it's still in an earlier stage.
    parent = get_concern(p["concern_id"])
    if parent is not None and parent.status in ("Reported", "Under Review"):
        update_concern(parent.concern_id, {"status": "Channel Referred"})
    logger.info(
        "Created Prevent referral #%d for concern #%d (status=%s)",
        new_id, p["concern_id"], p["status"])
    return out


def get_referral(referral_id: int) -> Referral | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM prevent_referrals WHERE referral_id = ?",
            (referral_id,),
        ).fetchone()
        return _row_referral(r) if r else None


def list_referrals(
    *,
    concern_id: int | None = None,
    status: str | None = None,
    authority: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    open_only: bool = False,
) -> list[Referral]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if concern_id is not None:
        clauses.append("concern_id = ?")
        args.append(concern_id)
    if status:
        if status not in REFERRAL_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(REFERRAL_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if authority:
        if authority not in REFERRAL_AUTHORITIES:
            raise ValidationError(
                f"Authority must be one of: {', '.join(REFERRAL_AUTHORITIES)}")
        clauses.append("authority = ?")
        args.append(authority)
    if date_from:
        clauses.append("referral_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("referral_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    if open_only:
        clauses.append("status NOT IN ('Closed', 'Declined')")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM prevent_referrals {where} "
           "ORDER BY referral_date DESC, referral_id DESC")
    with _connect() as conn:
        return [_row_referral(r) for r in conn.execute(sql, args).fetchall()]


def list_referrals_with_detail(**kwargs) -> list[ReferralRow]:
    rows = list_referrals(**kwargs)
    if not rows:
        return []
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    concern_to_student = {c.concern_id: c.student_id
                           for c in list_concerns()}
    result = []
    for r in rows:
        sid = concern_to_student.get(r.concern_id, "")
        result.append(ReferralRow(
            referral=r, student_id=sid,
            student_name=names.get(sid, "(unknown)")))
    return result


def update_referral(referral_id: int, data: dict[str, Any]) -> Referral:
    init_db()
    existing = get_referral(referral_id)
    if existing is None:
        raise ValidationError(f"No referral with id {referral_id}")
    p = _validate_referral_payload({
        "concern_id":    existing.concern_id,
        "referral_date": data.get("referral_date", existing.referral_date),
        "authority":     data.get("authority", existing.authority),
        "case_officer":  data.get("case_officer", existing.case_officer),
        "panel_date":    data.get("panel_date", existing.panel_date),
        "status":        data.get("status", existing.status),
        "outcome":       data.get("outcome", existing.outcome),
        "notes":         data.get("notes", existing.notes),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE prevent_referrals SET
                   referral_date = ?, authority = ?, case_officer = ?,
                   panel_date = ?, status = ?, outcome = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE referral_id = ?""",
            (p["referral_date"], p["authority"], p["case_officer"],
             p["panel_date"], p["status"], p["outcome"], p["notes"],
             referral_id),
        )
        conn.commit()
    out = get_referral(referral_id)
    assert out is not None
    logger.info("Updated Prevent referral #%d (status=%s)",
                referral_id, out.status)
    return out


def delete_referral(referral_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM prevent_referrals WHERE referral_id = ?",
            (referral_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted Prevent referral #%d", referral_id)
            return True
        return False


# ── Training ──────────────────────────────────────────────────────

def _validate_training_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["staff_id"] = _validate_staff(data.get("staff_id"))
    out["training_type"] = _validate_choice(
        data.get("training_type"), "Training type",
        TRAINING_TYPES, DEFAULT_TRAINING_TYPE)
    out["completed_date"] = _validate_date(
        data.get("completed_date"), "Completed date", required=True)
    out["expiry_date"] = _validate_date(
        data.get("expiry_date"), "Expiry date")
    if out["expiry_date"] and out["expiry_date"] < out["completed_date"]:
        raise ValidationError(
            "Expiry date cannot be before completed date")
    out["provider"]        = (data.get("provider") or "").strip() or None
    out["certificate_ref"] = (data.get("certificate_ref") or "").strip() or None
    out["notes"]           = (data.get("notes") or "").strip() or None
    return out


def create_training(data: dict[str, Any]) -> Training:
    init_db()
    try:
        p = _validate_training_payload(data)
    except ValidationError as e:
        logger.warning("create_training validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO prevent_training
                   (staff_id, training_type, completed_date, expiry_date,
                    provider, certificate_ref, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["staff_id"], p["training_type"], p["completed_date"],
             p["expiry_date"], p["provider"], p["certificate_ref"],
             p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_training(new_id)
    assert out is not None
    logger.info(
        "Created Prevent training #%d for %s (%s, completed %s)",
        new_id, p["staff_id"], p["training_type"], p["completed_date"])
    return out


def get_training(training_id: int) -> Training | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM prevent_training WHERE training_id = ?",
            (training_id,),
        ).fetchone()
        return _row_training(r) if r else None


def list_training(
    *,
    staff_id: str | None = None,
    training_type: str | None = None,
    expired_only: bool = False,
    expiring_within_days: int | None = None,
) -> list[Training]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if staff_id:
        clauses.append("staff_id = ?")
        args.append(staff_id.strip())
    if training_type:
        if training_type not in TRAINING_TYPES:
            raise ValidationError(
                f"Training type must be one of: {', '.join(TRAINING_TYPES)}")
        clauses.append("training_type = ?")
        args.append(training_type)
    import datetime as _dt
    today = _dt.date.today().isoformat()
    if expired_only:
        clauses.append("expiry_date IS NOT NULL AND expiry_date < ?")
        args.append(today)
    if expiring_within_days is not None:
        cutoff = (_dt.date.today()
                  + _dt.timedelta(days=expiring_within_days)).isoformat()
        clauses.append(
            "expiry_date IS NOT NULL "
            "AND expiry_date >= ? AND expiry_date <= ?")
        args.extend([today, cutoff])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM prevent_training {where} "
           "ORDER BY expiry_date IS NULL, expiry_date, training_id DESC")
    with _connect() as conn:
        return [_row_training(r) for r in conn.execute(sql, args).fetchall()]


def list_training_with_detail(**kwargs) -> list[TrainingRow]:
    rows = list_training(**kwargs)
    if not rows:
        return []
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.staff import (
        staff as _staff,
    )
    names = {s.staff_id: s.full_name for s in _staff.list_staff()}
    return [TrainingRow(
                training=t,
                staff_name=names.get(t.staff_id, "(unknown)"),
                expired=t.is_expired(),
                days_to_expiry=t.days_to_expiry())
            for t in rows]


def update_training(training_id: int, data: dict[str, Any]) -> Training:
    init_db()
    existing = get_training(training_id)
    if existing is None:
        raise ValidationError(f"No training record with id {training_id}")
    p = _validate_training_payload({
        "staff_id":        existing.staff_id,
        "training_type":   data.get("training_type", existing.training_type),
        "completed_date":  data.get("completed_date",
                                     existing.completed_date),
        "expiry_date":     data.get("expiry_date", existing.expiry_date),
        "provider":        data.get("provider", existing.provider),
        "certificate_ref": data.get("certificate_ref",
                                     existing.certificate_ref),
        "notes":           data.get("notes", existing.notes),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE prevent_training SET
                   training_type = ?, completed_date = ?, expiry_date = ?,
                   provider = ?, certificate_ref = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE training_id = ?""",
            (p["training_type"], p["completed_date"], p["expiry_date"],
             p["provider"], p["certificate_ref"], p["notes"],
             training_id),
        )
        conn.commit()
    out = get_training(training_id)
    assert out is not None
    logger.info("Updated Prevent training #%d", training_id)
    return out


def delete_training(training_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM prevent_training WHERE training_id = ?",
            (training_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted Prevent training #%d", training_id)
            return True
        return False


# ── Summaries ─────────────────────────────────────────────────────

@dataclass
class StaffTrainingSummary:
    staff_id: str
    record_count: int
    latest_type: str | None
    latest_completed: str | None
    latest_expiry: str | None
    expired: bool
    in_date: bool


def per_staff_training(staff_id: str) -> StaffTrainingSummary:
    rows = list_training(staff_id=staff_id)
    if not rows:
        return StaffTrainingSummary(
            staff_id=staff_id, record_count=0,
            latest_type=None, latest_completed=None,
            latest_expiry=None, expired=False, in_date=False)
    # Pick the most recently completed
    latest = max(rows, key=lambda t: t.completed_date)
    expired = latest.is_expired()
    in_date = latest.expiry_date is None or not expired
    return StaffTrainingSummary(
        staff_id=staff_id, record_count=len(rows),
        latest_type=latest.training_type,
        latest_completed=latest.completed_date,
        latest_expiry=latest.expiry_date,
        expired=expired, in_date=in_date)


@dataclass
class Summary:
    total_concerns: int
    concerns_open: int
    concerns_by_status: dict[str, int]
    concerns_by_risk: dict[str, int]
    concerns_by_type: dict[str, int]
    total_referrals: int
    referrals_open: int
    referrals_by_status: dict[str, int]
    total_training: int
    training_expired: int
    training_expiring_soon: int       # within 60 days
    staff_with_training: int
    high_risk_open: int


def summary(*, expiring_within_days: int = 60) -> Summary:
    init_db()
    concerns = list_concerns()
    referrals = list_referrals()
    training = list_training()

    by_status_c = {s: 0 for s in CONCERN_STATUSES}
    by_risk    = {r: 0 for r in RISK_LEVELS}
    by_type    = {t: 0 for t in CONCERN_TYPES}
    for c in concerns:
        by_status_c[c.status] = by_status_c.get(c.status, 0) + 1
        by_risk[c.risk_level] = by_risk.get(c.risk_level, 0) + 1
        by_type[c.concern_type] = by_type.get(c.concern_type, 0) + 1
    concerns_open = sum(1 for c in concerns if c.is_open)
    high_risk_open = sum(1 for c in concerns
                          if c.is_open and c.risk_level == "High")

    by_status_r = {s: 0 for s in REFERRAL_STATUSES}
    for r in referrals:
        by_status_r[r.status] = by_status_r.get(r.status, 0) + 1
    referrals_open = sum(1 for r in referrals if r.is_open)

    expired_n = sum(1 for t in training if t.is_expired())
    expiring_n = sum(
        1 for t in training
        if t.expiry_date is not None
        and not t.is_expired()
        and (t.days_to_expiry() or 0) <= expiring_within_days)
    staff_with_training = len({t.staff_id for t in training})

    return Summary(
        total_concerns=len(concerns),
        concerns_open=concerns_open,
        concerns_by_status=by_status_c,
        concerns_by_risk=by_risk,
        concerns_by_type=by_type,
        total_referrals=len(referrals),
        referrals_open=referrals_open,
        referrals_by_status=by_status_r,
        total_training=len(training),
        training_expired=expired_n,
        training_expiring_soon=expiring_n,
        staff_with_training=staff_with_training,
        high_risk_open=high_risk_open,
    )
