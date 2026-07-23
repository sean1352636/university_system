"""Apprenticeship-application data layer for the Sixth Form System.

Distinct from UCAS:

* Apprenticeships are direct applications to a specific employer — no
  single national tracking number, no fixed 5-choice limit.
* A student can have any number of in-flight applications.
* The status workflow is workplace-shaped:
    Researching → Applied → Interview → Offer → Accepted / Rejected /
    Withdrawn.

Cascade: deleting a student wipes their applications.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.post_16.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.APPRENTICESHIPS_DB

# Apprenticeship levels (England).
LEVELS: tuple[int, ...] = (2, 3, 4, 5, 6, 7)

STATUSES: tuple[str, ...] = (
    "Researching", "Applied", "Interview", "Offer",
    "Accepted", "Rejected", "Withdrawn",
)
DEFAULT_STATUS: str = "Researching"

# A subset of the IfATE sector groupings; staff can leave blank if
# none fit. We keep this short-and-known so the filter combobox stays
# usable.
SECTORS: tuple[str, ...] = (
    "Agriculture, Environmental and Animal Care",
    "Business and Administration",
    "Care Services",
    "Catering and Hospitality",
    "Construction",
    "Creative and Design",
    "Digital",
    "Education and Childcare",
    "Engineering and Manufacturing",
    "Finance and Accounting",
    "Health and Science",
    "Legal",
    "Protective Services",
    "Sales, Marketing and Procurement",
    "Transport and Logistics",
    "Other",
)

# Statuses that we consider "active" for summary purposes.
ACTIVE_STATUSES: tuple[str, ...] = (
    "Researching", "Applied", "Interview", "Offer",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS apprenticeship_applications (
    application_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id          TEXT NOT NULL,
    employer            TEXT NOT NULL,
    apprenticeship_name TEXT NOT NULL,
    level               INTEGER,
    sector              TEXT,
    reference_no        TEXT,
    location            TEXT,
    salary              REAL,
    submitted_at        TEXT,
    deadline            TEXT,
    interview_date      TEXT,
    start_date          TEXT,
    status              TEXT NOT NULL DEFAULT 'Researching',
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_appr_student  ON apprenticeship_applications(student_id);
CREATE INDEX IF NOT EXISTS idx_appr_status   ON apprenticeship_applications(status);
CREATE INDEX IF NOT EXISTS idx_appr_sector   ON apprenticeship_applications(sector);
CREATE INDEX IF NOT EXISTS idx_appr_employer ON apprenticeship_applications(employer);
"""


@dataclass
class Application:
    application_id: int
    student_id: str
    employer: str
    apprenticeship_name: str
    level: int | None
    sector: str | None
    reference_no: str | None
    location: str | None
    salary: float | None
    submitted_at: str | None
    deadline: str | None
    interview_date: str | None
    start_date: str | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class ApplicationRow:
    application: Application
    student_name: str


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
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Apprenticeships schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> Application:
    return Application(
        application_id=r["application_id"], student_id=r["student_id"],
        employer=r["employer"], apprenticeship_name=r["apprenticeship_name"],
        level=r["level"], sector=r["sector"],
        reference_no=r["reference_no"], location=r["location"],
        salary=r["salary"],
        submitted_at=r["submitted_at"], deadline=r["deadline"],
        interview_date=r["interview_date"], start_date=r["start_date"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid apprenticeship input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sid = _require(data.get("student_id"), "Student ID").strip()
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    out["employer"] = _require(data.get("employer"), "Employer").strip()
    out["apprenticeship_name"] = _require(
        data.get("apprenticeship_name"), "Apprenticeship title").strip()

    level = data.get("level")
    if level in (None, ""):
        out["level"] = None
    else:
        try:
            n = int(level)
        except (TypeError, ValueError):
            raise ValidationError("Level must be a whole number") from None
        if n not in LEVELS:
            raise ValidationError(
                f"Level must be one of: {', '.join(str(l) for l in LEVELS)}")
        out["level"] = n

    sector = (data.get("sector") or "").strip()
    if sector and sector not in SECTORS:
        raise ValidationError(
            f"Sector must be blank or one of: {', '.join(SECTORS)}")
    out["sector"] = sector or None

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    salary = data.get("salary")
    if salary in (None, ""):
        out["salary"] = None
    else:
        try:
            f = float(salary)
        except (TypeError, ValueError):
            raise ValidationError("Salary must be a number") from None
        if f < 0 or f > 200000:
            raise ValidationError("Salary must be between 0 and 200,000")
        out["salary"] = round(f, 2)

    out["submitted_at"]   = _validate_date(data.get("submitted_at"),
                                           "Submitted at")
    out["deadline"]       = _validate_date(data.get("deadline"), "Deadline")
    out["interview_date"] = _validate_date(data.get("interview_date"),
                                           "Interview date")
    out["start_date"]     = _validate_date(data.get("start_date"),
                                           "Start date")

    out["reference_no"] = (data.get("reference_no") or "").strip() or None
    out["location"]     = (data.get("location") or "").strip() or None
    out["notes"]        = (data.get("notes") or "").strip() or None
    return out


# ── CRUD ───────────────────────────────────────────────────────────

def create_application(data: dict[str, Any]) -> Application:
    init_db()
    try:
        p = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_application validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO apprenticeship_applications
                   (student_id, employer, apprenticeship_name, level, sector,
                    reference_no, location, salary, submitted_at,
                    deadline, interview_date, start_date, status, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["employer"], p["apprenticeship_name"],
             p["level"], p["sector"], p["reference_no"], p["location"],
             p["salary"], p["submitted_at"], p["deadline"],
             p["interview_date"], p["start_date"], p["status"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_application(new_id)
    assert out is not None
    logger.info(
        "Created apprenticeship application #%d for %s "
        "(%s — %s, status=%s)",
        new_id, p["student_id"], p["employer"],
        p["apprenticeship_name"], p["status"],
    )
    return out


def get_application(application_id: int) -> Application | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM apprenticeship_applications "
            "WHERE application_id = ?", (application_id,),
        ).fetchone()
        return _row(r) if r else None


def list_applications(
    *,
    student_id: str | None = None,
    employer_like: str | None = None,
    level: int | None = None,
    sector: str | None = None,
    status: str | None = None,
) -> list[Application]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if employer_like:
        clauses.append("employer LIKE ?")
        args.append(f"%{employer_like.strip()}%")
    if level is not None:
        if level not in LEVELS:
            raise ValidationError(
                f"Level must be one of: {', '.join(str(l) for l in LEVELS)}")
        clauses.append("level = ?")
        args.append(level)
    if sector:
        if sector not in SECTORS:
            raise ValidationError(
                f"Sector must be one of: {', '.join(SECTORS)}")
        clauses.append("sector = ?")
        args.append(sector)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT * FROM apprenticeship_applications {where} "
        "ORDER BY student_id, updated_at DESC"
    )
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def applications_for_student(student_id: str) -> list[Application]:
    return list_applications(student_id=student_id)


def list_applications_with_detail(**kwargs) -> list[ApplicationRow]:
    apps = list_applications(**kwargs)
    if not apps:
        return []
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [
        ApplicationRow(application=a,
                       student_name=names.get(a.student_id, "(unknown)"))
        for a in apps
    ]


def update_application(application_id: int, data: dict[str, Any]) -> Application:
    init_db()
    existing = get_application(application_id)
    if existing is None:
        logger.warning("update_application: unknown id %d", application_id)
        raise ValidationError(f"No application with id {application_id}")
    p = _validate_payload({
        "student_id":          existing.student_id,
        "employer":            data.get("employer", existing.employer),
        "apprenticeship_name": data.get(
            "apprenticeship_name", existing.apprenticeship_name),
        "level":               data.get("level", existing.level),
        "sector":              data.get("sector", existing.sector),
        "reference_no":        data.get("reference_no", existing.reference_no),
        "location":            data.get("location", existing.location),
        "salary":              data.get("salary", existing.salary),
        "submitted_at":        data.get("submitted_at", existing.submitted_at),
        "deadline":            data.get("deadline", existing.deadline),
        "interview_date":      data.get("interview_date", existing.interview_date),
        "start_date":          data.get("start_date", existing.start_date),
        "status":              data.get("status", existing.status),
        "notes":               data.get("notes", existing.notes),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE apprenticeship_applications SET
                   employer = ?, apprenticeship_name = ?, level = ?,
                   sector = ?, reference_no = ?, location = ?, salary = ?,
                   submitted_at = ?, deadline = ?, interview_date = ?,
                   start_date = ?, status = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE application_id = ?""",
            (p["employer"], p["apprenticeship_name"], p["level"],
             p["sector"], p["reference_no"], p["location"], p["salary"],
             p["submitted_at"], p["deadline"], p["interview_date"],
             p["start_date"], p["status"], p["notes"], application_id),
        )
        conn.commit()
    out = get_application(application_id)
    assert out is not None
    logger.info(
        "Updated apprenticeship application #%d (%s — %s, status=%s)",
        application_id, out.employer, out.apprenticeship_name, out.status,
    )
    return out


def set_status(application_id: int, status: str) -> Application:
    """Shortcut: update only the status (with the validator)."""
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_application(application_id, {"status": status})


def delete_application(application_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM apprenticeship_applications WHERE application_id = ?",
            (application_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted apprenticeship application #%d", application_id)
            return True
        logger.warning("delete_application: unknown id %d", application_id)
        return False


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class Summary:
    total: int
    by_status: dict[str, int]
    by_sector: dict[str, int]
    by_level: dict[int, int]
    active: int
    accepted: int
    upcoming_interviews: int  # within 30 days, status != final
    upcoming_deadlines: int   # within 14 days, status in Researching/Applied


def summary(
    *,
    interview_window_days: int = 30,
    deadline_window_days: int = 14,
) -> Summary:
    import datetime as _dt
    apps = list_applications()
    today = _dt.date.today()
    iv_cutoff = today + _dt.timedelta(days=interview_window_days)
    dl_cutoff = today + _dt.timedelta(days=deadline_window_days)

    by_status: dict[str, int] = {s: 0 for s in STATUSES}
    by_sector: dict[str, int] = {}
    by_level: dict[int, int] = {}
    active = 0
    accepted = 0
    upcoming_iv = 0
    upcoming_dl = 0
    for a in apps:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        if a.sector:
            by_sector[a.sector] = by_sector.get(a.sector, 0) + 1
        if a.level is not None:
            by_level[a.level] = by_level.get(a.level, 0) + 1
        if a.status in ACTIVE_STATUSES:
            active += 1
        if a.status == "Accepted":
            accepted += 1
        # Upcoming interview: has an interview_date, in window, not in
        # a final state.
        if a.interview_date and a.status not in (
                "Accepted", "Rejected", "Withdrawn"):
            try:
                d = _dt.date.fromisoformat(a.interview_date)
            except ValueError:
                continue
            if today <= d <= iv_cutoff:
                upcoming_iv += 1
        # Upcoming deadline: has a deadline, in window, not yet applied.
        if a.deadline and a.status in ("Researching", "Applied"):
            try:
                d = _dt.date.fromisoformat(a.deadline)
            except ValueError:
                continue
            if today <= d <= dl_cutoff:
                upcoming_dl += 1
    return Summary(
        total=len(apps), by_status=by_status, by_sector=by_sector,
        by_level=by_level, active=active, accepted=accepted,
        upcoming_interviews=upcoming_iv,
        upcoming_deadlines=upcoming_dl,
    )
