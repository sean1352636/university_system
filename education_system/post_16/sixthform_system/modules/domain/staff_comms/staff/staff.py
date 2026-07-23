"""Staff Directory data layer for the Sixth Form System.

One staff record per teacher / tutor / pastoral / admin etc.
Auto-allocates a unique ``staff_id`` like ``T1234567`` (T + 7 digits)
and a derived sixth-form email ``t1234567@sixthform.ac.uk``.

Distinct from students. No login auto-provisioning happens here —
staff user accounts are administered separately via the shared auth
system.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.post_16.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.STAFF_DB
ID_PREFIX = "T"
ID_DIGITS = 7
EMAIL_DOMAIN = "sixthform.ac.uk"

ROLES: tuple[str, ...] = (
    "Principal", "Vice Principal", "Head of Sixth Form",
    "Head of Year", "Head of Department", "Subject Lead",
    "Teacher", "Tutor", "Cover Teacher", "Teaching Assistant",
    "Librarian", "Exams Officer", "Careers Adviser",
    "Counsellor", "Pastoral Manager", "Safeguarding Lead (DSL)",
    "Deputy DSL", "SENCO", "Administrator", "Receptionist",
    "Finance Officer", "IT Support", "Caretaker", "Other",
)
DEFAULT_ROLE: str = "Teacher"

DEPARTMENTS: tuple[str, ...] = (
    "English", "Mathematics", "Sciences", "Biology", "Chemistry",
    "Physics", "Computer Science", "Economics", "Business Studies",
    "Geography", "History", "Politics", "Psychology", "Sociology",
    "Religious Studies", "Philosophy", "Modern Languages",
    "Classics", "Art & Design", "Photography", "Music",
    "Drama", "Media Studies", "Physical Education",
    "Sixth Form Office", "Pastoral", "Safeguarding",
    "Careers", "Library", "Exams", "Admin", "Finance",
    "IT", "Estates", "Other",
)
DEFAULT_DEPARTMENT: str = "Other"

EMPLOYMENT_STATUSES: tuple[str, ...] = (
    "Full-time", "Part-time", "Fractional", "Job Share",
    "Supply", "Probation", "Maternity Cover", "Sabbatical",
    "On Leave", "Left",
)
DEFAULT_EMPLOYMENT_STATUS: str = "Full-time"
ACTIVE_STATUSES: tuple[str, ...] = tuple(
    s for s in EMPLOYMENT_STATUSES if s not in ("Left", "Sabbatical"))

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[+0-9 ()\-]{5,25}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS staff (
    staff_id          TEXT PRIMARY KEY,
    first_name        TEXT NOT NULL,
    last_name         TEXT NOT NULL,
    title             TEXT,
    role              TEXT NOT NULL DEFAULT 'Teacher',
    department        TEXT NOT NULL DEFAULT 'Other',
    employment_status TEXT NOT NULL DEFAULT 'Full-time',
    email             TEXT NOT NULL,
    work_phone        TEXT,
    personal_phone    TEXT,
    room              TEXT,
    line_manager      TEXT,
    start_date        TEXT,
    end_date          TEXT,
    is_tutor          INTEGER NOT NULL DEFAULT 0,
    is_dsl            INTEGER NOT NULL DEFAULT 0,
    is_examiner       INTEGER NOT NULL DEFAULT 0,
    qualifications    TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (line_manager) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_staff_email ON staff(email);
CREATE INDEX IF NOT EXISTS idx_staff_role       ON staff(role);
CREATE INDEX IF NOT EXISTS idx_staff_department ON staff(department);
CREATE INDEX IF NOT EXISTS idx_staff_status     ON staff(employment_status);
"""


@dataclass
class Staff:
    staff_id: str
    first_name: str
    last_name: str
    title: str | None
    role: str
    department: str
    employment_status: str
    email: str
    work_phone: str | None
    personal_phone: str | None
    room: str | None
    line_manager: str | None
    start_date: str | None
    end_date: str | None
    is_tutor: bool
    is_dsl: bool
    is_examiner: bool
    qualifications: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def full_name(self) -> str:
        parts = [p for p in (self.title, self.first_name, self.last_name) if p]
        return " ".join(parts)

    @property
    def is_active(self) -> bool:
        return self.employment_status in ACTIVE_STATUSES


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
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Staff schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> Staff:
    return Staff(
        staff_id=r["staff_id"], first_name=r["first_name"],
        last_name=r["last_name"], title=r["title"], role=r["role"],
        department=r["department"],
        employment_status=r["employment_status"],
        email=r["email"], work_phone=r["work_phone"],
        personal_phone=r["personal_phone"], room=r["room"],
        line_manager=r["line_manager"],
        start_date=r["start_date"], end_date=r["end_date"],
        is_tutor=bool(r["is_tutor"]), is_dsl=bool(r["is_dsl"]),
        is_examiner=bool(r["is_examiner"]),
        qualifications=r["qualifications"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── ID + email helpers ────────────────────────────────────────────

def generate_staff_id() -> str:
    init_db()
    with _connect() as conn:
        for _ in range(50):
            n = random.randint(10 ** (ID_DIGITS - 1), 10 ** ID_DIGITS - 1)
            sid = f"{ID_PREFIX}{n}"
            r = conn.execute(
                "SELECT 1 FROM staff WHERE staff_id = ?", (sid,)).fetchone()
            if r is None:
                return sid
    raise RuntimeError("Could not allocate a unique staff id")


def generate_staff_email(staff_id: str) -> str:
    return f"{staff_id.lower()}@{EMAIL_DOMAIN}"


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(v, label: str):
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _validate_date(v: Any, label: str) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_phone(v: Any, label: str) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    s = str(v).strip()
    if not _PHONE_RE.match(s):
        raise ValidationError(
            f"{label} can only contain digits, spaces, "
            f"+, (), and -")
    return s


def _validate_email(v: Any) -> str:
    s = _require(v, "Email").strip()
    if not _EMAIL_RE.match(s):
        raise ValidationError("Email is not a valid address")
    return s.lower()


def _validate_role(v: Any) -> str:
    s = _require(v, "Role").strip()
    if s not in ROLES:
        raise ValidationError(f"Role must be one of: {', '.join(ROLES)}")
    return s


def _validate_department(v: Any) -> str:
    s = _require(v, "Department").strip()
    if s not in DEPARTMENTS:
        raise ValidationError(
            f"Department must be one of: {', '.join(DEPARTMENTS)}")
    return s


def _validate_employment_status(v: Any) -> str:
    s = _require(v, "Employment status").strip()
    if s not in EMPLOYMENT_STATUSES:
        raise ValidationError(
            f"Employment status must be one of: "
            f"{', '.join(EMPLOYMENT_STATUSES)}")
    return s


def _validate_line_manager(v: Any, *,
                             current_id: str | None = None) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    s = str(v).strip().upper()
    if current_id and s == current_id:
        raise ValidationError("Line manager cannot be the same as the staff member")
    with _connect() as conn:
        r = conn.execute(
            "SELECT 1 FROM staff WHERE staff_id = ?", (s,)).fetchone()
        if r is None:
            raise ValidationError(f"No staff with id {s}")
    return s


def _validate_payload(data: dict[str, Any], *,
                        existing: Staff | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["first_name"] = _require(data.get("first_name"),
                                    "First name").strip()
    out["last_name"]  = _require(data.get("last_name"),
                                    "Last name").strip()
    out["title"]      = (data.get("title") or "").strip() or None

    out["role"]              = _validate_role(data.get("role")
                                                 or DEFAULT_ROLE)
    out["department"]        = _validate_department(
        data.get("department") or DEFAULT_DEPARTMENT)
    out["employment_status"] = _validate_employment_status(
        data.get("employment_status") or DEFAULT_EMPLOYMENT_STATUS)

    out["work_phone"]     = _validate_phone(data.get("work_phone"),
                                              "Work phone")
    out["personal_phone"] = _validate_phone(data.get("personal_phone"),
                                              "Personal phone")
    out["room"]           = (data.get("room") or "").strip() or None
    out["line_manager"]   = _validate_line_manager(
        data.get("line_manager"),
        current_id=existing.staff_id if existing else None)
    out["start_date"] = _validate_date(data.get("start_date"),
                                          "Start date")
    out["end_date"]   = _validate_date(data.get("end_date"),
                                          "End date")
    if out["start_date"] and out["end_date"] \
            and out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")

    out["is_tutor"]    = bool(data.get("is_tutor"))
    out["is_dsl"]      = bool(data.get("is_dsl"))
    out["is_examiner"] = bool(data.get("is_examiner"))
    out["qualifications"] = (data.get("qualifications") or "").strip() or None
    out["notes"]          = (data.get("notes") or "").strip() or None
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_staff(data: dict[str, Any]) -> Staff:
    init_db()
    try:
        p = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_staff validation failed: %s", e)
        raise
    sid = generate_staff_id()
    email = data.get("email") or generate_staff_email(sid)
    email = _validate_email(email)
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM staff WHERE email = ?", (email,)).fetchone()
        if exists:
            raise ValidationError(f"A staff member with email {email} "
                                  f"already exists")
        conn.execute(
            """INSERT INTO staff (
                   staff_id, first_name, last_name, title, role, department,
                   employment_status, email, work_phone, personal_phone,
                   room, line_manager, start_date, end_date,
                   is_tutor, is_dsl, is_examiner, qualifications, notes,
                   created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (sid, p["first_name"], p["last_name"], p["title"],
             p["role"], p["department"], p["employment_status"],
             email, p["work_phone"], p["personal_phone"], p["room"],
             p["line_manager"], p["start_date"], p["end_date"],
             int(p["is_tutor"]), int(p["is_dsl"]), int(p["is_examiner"]),
             p["qualifications"], p["notes"]),
        )
        conn.commit()
    out = get_staff(sid)
    assert out is not None
    logger.info("Created staff %s (%s %s, %s)",
                sid, out.first_name, out.last_name, out.role)
    # Register into the shared cross-system staff directory so a person who
    # works across systems is one HR identity (best-effort; never blocks).
    try:
        from education_system.shared.staff_directory import (
            staff_directory_service,
        )
        staff_directory_service.register_local_staff(
            "college", staff_id=sid, first_name=out.first_name,
            last_name=out.last_name, email=out.email, role=out.role)
    except Exception:
        logger.debug("Staff directory registration skipped for %s", sid,
                     exc_info=True)
    return out


def get_staff(staff_id: str) -> Staff | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM staff WHERE staff_id = ?",
            (staff_id.strip().upper(),)).fetchone()
        return _row(r) if r else None


def list_staff(
    *,
    role: str | None = None,
    department: str | None = None,
    employment_status: str | None = None,
    is_tutor: bool | None = None,
    is_dsl: bool | None = None,
    is_examiner: bool | None = None,
    active_only: bool = False,
) -> list[Staff]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if role:
        if role not in ROLES:
            raise ValidationError(f"Role must be one of: {', '.join(ROLES)}")
        clauses.append("role = ?")
        args.append(role)
    if department:
        if department not in DEPARTMENTS:
            raise ValidationError(
                f"Department must be one of: {', '.join(DEPARTMENTS)}")
        clauses.append("department = ?")
        args.append(department)
    if employment_status:
        if employment_status not in EMPLOYMENT_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(EMPLOYMENT_STATUSES)}")
        clauses.append("employment_status = ?")
        args.append(employment_status)
    if is_tutor is not None:
        clauses.append("is_tutor = ?")
        args.append(int(is_tutor))
    if is_dsl is not None:
        clauses.append("is_dsl = ?")
        args.append(int(is_dsl))
    if is_examiner is not None:
        clauses.append("is_examiner = ?")
        args.append(int(is_examiner))
    if active_only:
        ph = ",".join("?" * len(ACTIVE_STATUSES))
        clauses.append(f"employment_status IN ({ph})")
        args.extend(ACTIVE_STATUSES)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM staff {where} "
           "ORDER BY last_name, first_name, staff_id")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def search_staff(q: str) -> list[Staff]:
    init_db()
    q = (q or "").strip()
    if not q:
        return list_staff()
    like = f"%{q}%"
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM staff
                WHERE staff_id LIKE ?
                   OR first_name LIKE ?
                   OR last_name  LIKE ?
                   OR email      LIKE ?
                   OR role       LIKE ?
                   OR department LIKE ?
                ORDER BY last_name, first_name""",
            (like, like, like, like, like, like),
        ).fetchall()
    return [_row(r) for r in rows]


def update_staff(staff_id: str, data: dict[str, Any]) -> Staff:
    init_db()
    existing = get_staff(staff_id)
    if existing is None:
        raise ValidationError(f"No staff with id {staff_id}")
    merged = {
        "first_name":        data.get("first_name", existing.first_name),
        "last_name":         data.get("last_name", existing.last_name),
        "title":             data.get("title", existing.title),
        "role":              data.get("role", existing.role),
        "department":        data.get("department", existing.department),
        "employment_status": data.get("employment_status",
                                        existing.employment_status),
        "work_phone":        data.get("work_phone", existing.work_phone),
        "personal_phone":    data.get("personal_phone",
                                        existing.personal_phone),
        "room":              data.get("room", existing.room),
        "line_manager":      data.get("line_manager",
                                        existing.line_manager),
        "start_date":        data.get("start_date", existing.start_date),
        "end_date":          data.get("end_date", existing.end_date),
        "is_tutor":          data.get("is_tutor", existing.is_tutor),
        "is_dsl":            data.get("is_dsl", existing.is_dsl),
        "is_examiner":       data.get("is_examiner", existing.is_examiner),
        "qualifications":    data.get("qualifications",
                                        existing.qualifications),
        "notes":             data.get("notes", existing.notes),
    }
    p = _validate_payload(merged, existing=existing)
    email = data.get("email", existing.email)
    email = _validate_email(email)
    with _connect() as conn:
        if email != existing.email:
            clash = conn.execute(
                "SELECT 1 FROM staff WHERE email = ? AND staff_id <> ?",
                (email, existing.staff_id)).fetchone()
            if clash:
                raise ValidationError(
                    f"Another staff member already has email {email}")
        conn.execute(
            """UPDATE staff SET
                  first_name=?, last_name=?, title=?, role=?, department=?,
                  employment_status=?, email=?, work_phone=?, personal_phone=?,
                  room=?, line_manager=?, start_date=?, end_date=?,
                  is_tutor=?, is_dsl=?, is_examiner=?, qualifications=?,
                  notes=?, updated_at=datetime('now')
               WHERE staff_id=?""",
            (p["first_name"], p["last_name"], p["title"], p["role"],
             p["department"], p["employment_status"], email,
             p["work_phone"], p["personal_phone"], p["room"],
             p["line_manager"], p["start_date"], p["end_date"],
             int(p["is_tutor"]), int(p["is_dsl"]), int(p["is_examiner"]),
             p["qualifications"], p["notes"], existing.staff_id),
        )
        conn.commit()
    out = get_staff(existing.staff_id)
    assert out is not None
    logger.info("Updated staff %s", existing.staff_id)
    return out


def mark_left(staff_id: str, end_date: str | None = None) -> Staff:
    """Convenience: set employment_status='Left' + end_date."""
    import datetime as _dt
    end = end_date or _dt.date.today().isoformat()
    return update_staff(staff_id, {"employment_status": "Left",
                                     "end_date": end})


def delete_staff(staff_id: str) -> bool:
    init_db()
    sid = staff_id.strip().upper()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM staff WHERE staff_id = ?", (sid,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted staff %s", sid)
            return True
        return False


def reports_to(staff_id: str) -> list[Staff]:
    """Staff whose line_manager is the given staff_id."""
    init_db()
    sid = staff_id.strip().upper()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM staff WHERE line_manager = ? "
            "ORDER BY last_name, first_name", (sid,)
        ).fetchall()
    return [_row(r) for r in rows]


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class Summary:
    total: int
    active: int
    left: int
    tutors: int
    dsls: int
    examiners: int
    by_role: dict[str, int]
    by_department: dict[str, int]
    by_status: dict[str, int]
    unfilled_critical: list[str]  # role names that have zero active staff


_CRITICAL_ROLES: tuple[str, ...] = (
    "Principal", "Safeguarding Lead (DSL)", "Exams Officer", "SENCO",
)


def summary() -> Summary:
    init_db()
    rows = list_staff()
    active = [s for s in rows if s.is_active]
    by_role = {r: 0 for r in ROLES}
    by_dept = {d: 0 for d in DEPARTMENTS}
    by_status = {s: 0 for s in EMPLOYMENT_STATUSES}
    tutors = dsls = examiners = 0
    for s in rows:
        by_role[s.role] = by_role.get(s.role, 0) + 1
        by_dept[s.department] = by_dept.get(s.department, 0) + 1
        by_status[s.employment_status] = (
            by_status.get(s.employment_status, 0) + 1)
        if s.is_active:
            if s.is_tutor:
                tutors += 1
            if s.is_dsl:
                dsls += 1
            if s.is_examiner:
                examiners += 1
    active_role_counts = {r: 0 for r in ROLES}
    for s in active:
        active_role_counts[s.role] = active_role_counts.get(s.role, 0) + 1
    unfilled = [r for r in _CRITICAL_ROLES if active_role_counts.get(r, 0) == 0]

    return Summary(
        total=len(rows),
        active=len(active),
        left=sum(1 for s in rows if s.employment_status == "Left"),
        tutors=tutors, dsls=dsls, examiners=examiners,
        by_role=by_role, by_department=by_dept, by_status=by_status,
        unfilled_critical=unfilled,
    )
