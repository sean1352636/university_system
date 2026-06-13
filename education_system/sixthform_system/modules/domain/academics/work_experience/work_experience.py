"""Work Experience & Placements data layer.

Two tables:

* ``we_employers`` — employer directory: name, sector, contact
  details, address, notes. Names are unique (case-insensitive).
* ``we_placements`` — one row per student-employer placement, with
  start/end dates, role, hours required (e.g. 315h for T-level
  industry placement), hours completed, safeguarding flags
  (risk-assessment, parental consent), supervisor, status, notes.

Cascade: deleting an employer is blocked if any placements reference
it (so we don't silently lose history); deleting a student wipes
their placements; deleting a placement is a simple row delete.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.WORK_EXPERIENCE_DB

SECTORS: tuple[str, ...] = (
    "Healthcare", "Education", "Engineering", "Finance & Banking",
    "Legal", "Media & Creative", "IT & Digital", "Retail",
    "Hospitality", "Public Sector", "Charity", "Construction",
    "Manufacturing", "Science & Research", "Other",
)
DEFAULT_SECTOR: str = "Other"

PLACEMENT_STATUSES: tuple[str, ...] = (
    "Planned", "In Progress", "Completed", "Cancelled",
)
DEFAULT_PLACEMENT_STATUS: str = "Planned"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS we_employers (
    employer_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    sector           TEXT NOT NULL DEFAULT 'Other',
    contact_name     TEXT,
    contact_email    TEXT,
    contact_phone    TEXT,
    address          TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_we_employers_name
    ON we_employers(LOWER(name));
CREATE INDEX IF NOT EXISTS idx_we_employers_sector
    ON we_employers(sector);

CREATE TABLE IF NOT EXISTS we_placements (
    placement_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id              TEXT NOT NULL,
    employer_id             INTEGER NOT NULL,
    start_date              TEXT NOT NULL,
    end_date                TEXT NOT NULL,
    role                    TEXT,
    hours_required          REAL,
    hours_completed         REAL NOT NULL DEFAULT 0,
    status                  TEXT NOT NULL DEFAULT 'Planned',
    risk_assessment_done    INTEGER NOT NULL DEFAULT 0,
    parental_consent        INTEGER NOT NULL DEFAULT 0,
    supervisor_name         TEXT,
    supervisor_email        TEXT,
    notes                   TEXT,
    created_at              TEXT DEFAULT (datetime('now')),
    updated_at              TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id)  REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (employer_id) REFERENCES we_employers(employer_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_we_pl_student   ON we_placements(student_id);
CREATE INDEX IF NOT EXISTS idx_we_pl_employer  ON we_placements(employer_id);
CREATE INDEX IF NOT EXISTS idx_we_pl_status    ON we_placements(status);
CREATE INDEX IF NOT EXISTS idx_we_pl_dates     ON we_placements(start_date, end_date);
"""


@dataclass
class Employer:
    employer_id: int
    name: str
    sector: str
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    address: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Placement:
    placement_id: int
    student_id: str
    employer_id: int
    start_date: str
    end_date: str
    role: str | None
    hours_required: float | None
    hours_completed: float
    status: str
    risk_assessment_done: bool
    parental_consent: bool
    supervisor_name: str | None
    supervisor_email: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def hours_outstanding(self) -> float | None:
        if self.hours_required is None:
            return None
        return max(0.0, self.hours_required - self.hours_completed)

    @property
    def progress_percent(self) -> int | None:
        if not self.hours_required:
            return None
        return min(100, int(round(
            100 * self.hours_completed / self.hours_required)))


@dataclass
class PlacementRow:
    placement: Placement
    student_name: str
    employer_name: str


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
    logger.debug("Work-experience schema ready at %s", DB_PATH)
    _DB_READY = True


def _row_employer(r: sqlite3.Row) -> Employer:
    return Employer(
        employer_id=r["employer_id"], name=r["name"],
        sector=r["sector"], contact_name=r["contact_name"],
        contact_email=r["contact_email"],
        contact_phone=r["contact_phone"],
        address=r["address"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_placement(r: sqlite3.Row) -> Placement:
    return Placement(
        placement_id=r["placement_id"], student_id=r["student_id"],
        employer_id=r["employer_id"],
        start_date=r["start_date"], end_date=r["end_date"],
        role=r["role"],
        hours_required=r["hours_required"],
        hours_completed=r["hours_completed"],
        status=r["status"],
        risk_assessment_done=bool(r["risk_assessment_done"]),
        parental_consent=bool(r["parental_consent"]),
        supervisor_name=r["supervisor_name"],
        supervisor_email=r["supervisor_email"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid work-experience input."""


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
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real calendar date") from None
    return s


def _coerce_bool(v: Any) -> int:
    if isinstance(v, bool):
        return 1 if v else 0
    if v in (None, ""):
        return 0
    s = str(v).strip().lower()
    if s in ("1", "y", "yes", "true", "t"):
        return 1
    if s in ("0", "n", "no", "false", "f"):
        return 0
    raise ValidationError(f"Expected yes/no, got {v!r}")


def _coerce_hours(v: Any, label: str) -> float | None:
    if v in (None, ""):
        return None
    try:
        h = float(v)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if h < 0 or h > 10000:
        raise ValidationError(f"{label} must be between 0 and 10000")
    return round(h, 2)


def _validate_employer_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["name"] = _require(data.get("name"), "Employer name").strip()
    sector = (data.get("sector") or DEFAULT_SECTOR).strip()
    if sector not in SECTORS:
        raise ValidationError(
            f"Sector must be one of: {', '.join(SECTORS)}")
    out["sector"] = sector
    email = (data.get("contact_email") or "").strip()
    if email and not _EMAIL_RE.match(email):
        raise ValidationError("Contact email is not a valid email address")
    out["contact_email"] = email or None
    out["contact_name"]  = (data.get("contact_name") or "").strip() or None
    out["contact_phone"] = (data.get("contact_phone") or "").strip() or None
    out["address"]       = (data.get("address") or "").strip() or None
    out["notes"]         = (data.get("notes") or "").strip() or None
    return out


def _validate_placement_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sid = _require(data.get("student_id"), "Student ID").strip()
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    emp = data.get("employer_id")
    if emp in (None, ""):
        raise ValidationError("Employer is required")
    try:
        emp_id = int(emp)
    except (TypeError, ValueError):
        raise ValidationError("Employer id must be a number") from None
    if get_employer(emp_id) is None:
        raise ValidationError(f"No employer with id {emp_id}")
    out["employer_id"] = emp_id

    start = _validate_date(_require(data.get("start_date"), "Start date"),
                            "Start date")
    end   = _validate_date(_require(data.get("end_date"), "End date"),
                            "End date")
    if start > end:
        raise ValidationError("End date must be on or after start date")
    out["start_date"] = start
    out["end_date"]   = end

    out["hours_required"]  = _coerce_hours(
        data.get("hours_required"), "Hours required")
    out["hours_completed"] = _coerce_hours(
        data.get("hours_completed"), "Hours completed") or 0.0
    if (out["hours_required"] is not None
            and out["hours_completed"] > out["hours_required"] + 0.001):
        # Allow exceeding (sometimes happens) — warn via logger but
        # don't reject; the field is illustrative, not contractual.
        logger.warning(
            "Placement hours_completed (%.1f) exceeds hours_required (%.1f)",
            out["hours_completed"], out["hours_required"])

    status = (data.get("status") or DEFAULT_PLACEMENT_STATUS).strip()
    if status not in PLACEMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(PLACEMENT_STATUSES)}")
    out["status"] = status

    sup_email = (data.get("supervisor_email") or "").strip()
    if sup_email and not _EMAIL_RE.match(sup_email):
        raise ValidationError(
            "Supervisor email is not a valid email address")
    out["supervisor_email"] = sup_email or None

    out["role"]                  = (data.get("role") or "").strip() or None
    out["supervisor_name"]       = (data.get("supervisor_name") or "").strip() or None
    out["notes"]                 = (data.get("notes") or "").strip() or None
    out["risk_assessment_done"]  = _coerce_bool(
        data.get("risk_assessment_done"))
    out["parental_consent"]      = _coerce_bool(
        data.get("parental_consent"))
    return out


# ── Employer CRUD ─────────────────────────────────────────────────

def create_employer(data: dict[str, Any]) -> Employer:
    init_db()
    try:
        p = _validate_employer_payload(data)
    except ValidationError as e:
        logger.warning("create_employer validation failed: %s", e)
        raise
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO we_employers
                       (name, sector, contact_name, contact_email,
                        contact_phone, address, notes,
                        created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))""",
                (p["name"], p["sector"], p["contact_name"],
                 p["contact_email"], p["contact_phone"],
                 p["address"], p["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e).upper():
            raise ValidationError(
                f"Employer named {p['name']!r} already exists") from None
        logger.exception("create_employer DB error")
        raise
    out = get_employer(new_id)
    assert out is not None
    logger.info("Created employer #%d %s (%s)",
                new_id, p["name"], p["sector"])
    return out


def get_employer(employer_id: int) -> Employer | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM we_employers WHERE employer_id = ?",
            (employer_id,),
        ).fetchone()
        return _row_employer(r) if r else None


def list_employers(
    *,
    sector: str | None = None,
    name_like: str | None = None,
) -> list[Employer]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if sector:
        if sector not in SECTORS:
            raise ValidationError(
                f"Sector must be one of: {', '.join(SECTORS)}")
        clauses.append("sector = ?")
        args.append(sector)
    if name_like:
        clauses.append("name LIKE ?")
        args.append(f"%{name_like.strip()}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM we_employers {where} ORDER BY name COLLATE NOCASE"
    with _connect() as conn:
        return [_row_employer(r) for r in conn.execute(sql, args).fetchall()]


def update_employer(employer_id: int, data: dict[str, Any]) -> Employer:
    init_db()
    existing = get_employer(employer_id)
    if existing is None:
        raise ValidationError(f"No employer with id {employer_id}")
    p = _validate_employer_payload({
        "name":          data.get("name", existing.name),
        "sector":        data.get("sector", existing.sector),
        "contact_name":  data.get("contact_name", existing.contact_name),
        "contact_email": data.get("contact_email", existing.contact_email),
        "contact_phone": data.get("contact_phone", existing.contact_phone),
        "address":       data.get("address", existing.address),
        "notes":         data.get("notes", existing.notes),
    })
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE we_employers SET
                       name = ?, sector = ?, contact_name = ?,
                       contact_email = ?, contact_phone = ?,
                       address = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE employer_id = ?""",
                (p["name"], p["sector"], p["contact_name"],
                 p["contact_email"], p["contact_phone"],
                 p["address"], p["notes"], employer_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e).upper():
            raise ValidationError(
                f"Employer named {p['name']!r} already exists") from None
        raise
    out = get_employer(employer_id)
    assert out is not None
    logger.info("Updated employer #%d (%s)", employer_id, out.name)
    return out


def delete_employer(employer_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM we_employers WHERE employer_id = ?",
                (employer_id,),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        raise ValidationError(
            "Cannot delete employer: placements still reference it. "
            "Delete or reassign those placements first.") from None
    if cur.rowcount:
        logger.info("Deleted employer #%d", employer_id)
        return True
    return False


# ── Placement CRUD ────────────────────────────────────────────────

def create_placement(data: dict[str, Any]) -> Placement:
    init_db()
    p = _validate_placement_payload(data)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO we_placements
                   (student_id, employer_id, start_date, end_date,
                    role, hours_required, hours_completed, status,
                    risk_assessment_done, parental_consent,
                    supervisor_name, supervisor_email, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["employer_id"],
             p["start_date"], p["end_date"], p["role"],
             p["hours_required"], p["hours_completed"], p["status"],
             p["risk_assessment_done"], p["parental_consent"],
             p["supervisor_name"], p["supervisor_email"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_placement(new_id)
    assert out is not None
    logger.info(
        "Created placement #%d: %s @ employer#%d (%s..%s, %s)",
        new_id, p["student_id"], p["employer_id"],
        p["start_date"], p["end_date"], p["status"],
    )
    return out


def get_placement(placement_id: int) -> Placement | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM we_placements WHERE placement_id = ?",
            (placement_id,),
        ).fetchone()
        return _row_placement(r) if r else None


def list_placements(
    *,
    student_id: str | None = None,
    employer_id: int | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    consent_pending: bool = False,
    risk_pending: bool = False,
) -> list[Placement]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if employer_id is not None:
        clauses.append("employer_id = ?")
        args.append(employer_id)
    if status:
        if status not in PLACEMENT_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(PLACEMENT_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if date_from:
        clauses.append("end_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("start_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    if consent_pending:
        clauses.append("parental_consent = 0")
    if risk_pending:
        clauses.append("risk_assessment_done = 0")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM we_placements {where} "
           "ORDER BY start_date DESC, placement_id DESC")
    with _connect() as conn:
        return [_row_placement(r)
                for r in conn.execute(sql, args).fetchall()]


def list_placements_with_detail(**kwargs) -> list[PlacementRow]:
    rows = list_placements(**kwargs)
    if not rows:
        return []
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    snames = {s.student_id: s.full_name for s in _students.list_students()}
    emp_names: dict[int, str] = {}
    with _connect() as conn:
        for r in conn.execute(
                "SELECT employer_id, name FROM we_employers").fetchall():
            emp_names[r["employer_id"]] = r["name"]
    return [PlacementRow(
                placement=p,
                student_name=snames.get(p.student_id, "(unknown)"),
                employer_name=emp_names.get(p.employer_id, "(unknown)"))
            for p in rows]


def update_placement(placement_id: int, data: dict[str, Any]) -> Placement:
    init_db()
    existing = get_placement(placement_id)
    if existing is None:
        raise ValidationError(f"No placement with id {placement_id}")
    p = _validate_placement_payload({
        "student_id":            existing.student_id,
        "employer_id":           data.get("employer_id", existing.employer_id),
        "start_date":            data.get("start_date", existing.start_date),
        "end_date":              data.get("end_date", existing.end_date),
        "role":                  data.get("role", existing.role),
        "hours_required":        data.get("hours_required",
                                            existing.hours_required),
        "hours_completed":       data.get("hours_completed",
                                            existing.hours_completed),
        "status":                data.get("status", existing.status),
        "risk_assessment_done":  data.get("risk_assessment_done",
                                            existing.risk_assessment_done),
        "parental_consent":      data.get("parental_consent",
                                            existing.parental_consent),
        "supervisor_name":       data.get("supervisor_name",
                                            existing.supervisor_name),
        "supervisor_email":      data.get("supervisor_email",
                                            existing.supervisor_email),
        "notes":                 data.get("notes", existing.notes),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE we_placements SET
                   employer_id = ?, start_date = ?, end_date = ?,
                   role = ?, hours_required = ?, hours_completed = ?,
                   status = ?, risk_assessment_done = ?,
                   parental_consent = ?, supervisor_name = ?,
                   supervisor_email = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE placement_id = ?""",
            (p["employer_id"], p["start_date"], p["end_date"],
             p["role"], p["hours_required"], p["hours_completed"],
             p["status"], p["risk_assessment_done"],
             p["parental_consent"], p["supervisor_name"],
             p["supervisor_email"], p["notes"], placement_id),
        )
        conn.commit()
    out = get_placement(placement_id)
    assert out is not None
    logger.info(
        "Updated placement #%d (status=%s, hours=%.1f/%s)",
        placement_id, out.status, out.hours_completed,
        ("%.1f" % out.hours_required) if out.hours_required else "—",
    )
    return out


def log_hours(placement_id: int, hours: float) -> Placement:
    """Convenience: add `hours` to ``hours_completed``."""
    init_db()
    existing = get_placement(placement_id)
    if existing is None:
        raise ValidationError(f"No placement with id {placement_id}")
    try:
        h = float(hours)
    except (TypeError, ValueError):
        raise ValidationError("Hours must be a number") from None
    if h <= 0 or h > 24:
        raise ValidationError("Hours must be between 0 and 24")
    new_total = round(existing.hours_completed + h, 2)
    return update_placement(placement_id, {"hours_completed": new_total})


def delete_placement(placement_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM we_placements WHERE placement_id = ?",
            (placement_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted placement #%d", placement_id)
            return True
        return False


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class WorkExperienceSummary:
    total_employers: int
    total_placements: int
    by_status: dict[str, int]
    by_sector: dict[str, int]
    consent_pending: int
    risk_pending: int
    students_with_placement: int
    total_hours_completed: float
    upcoming_start: int       # placements starting in next 30 days


def summary(*, upcoming_window_days: int = 30) -> WorkExperienceSummary:
    init_db()
    today = _dt.date.today()
    today_iso = today.isoformat()
    upcoming_cutoff = (today + _dt.timedelta(days=upcoming_window_days)
                       ).isoformat()

    placements = list_placements()
    by_status = {s: 0 for s in PLACEMENT_STATUSES}
    by_sector = {s: 0 for s in SECTORS}
    consent_pending = 0
    risk_pending = 0
    total_hours = 0.0
    students: set[str] = set()
    upcoming = 0

    employers = list_employers()
    emp_sectors = {e.employer_id: e.sector for e in employers}

    for p in placements:
        by_status[p.status] = by_status.get(p.status, 0) + 1
        sect = emp_sectors.get(p.employer_id, "Other")
        by_sector[sect] = by_sector.get(sect, 0) + 1
        if not p.parental_consent and p.status != "Cancelled":
            consent_pending += 1
        if not p.risk_assessment_done and p.status != "Cancelled":
            risk_pending += 1
        total_hours += p.hours_completed
        students.add(p.student_id)
        if (p.status in ("Planned", "In Progress")
                and today_iso <= p.start_date <= upcoming_cutoff):
            upcoming += 1

    return WorkExperienceSummary(
        total_employers=len(employers),
        total_placements=len(placements),
        by_status=by_status, by_sector=by_sector,
        consent_pending=consent_pending,
        risk_pending=risk_pending,
        students_with_placement=len(students),
        total_hours_completed=round(total_hours, 2),
        upcoming_start=upcoming,
    )
