"""Staff Directory: the school's record of everyone who works here.

Built on the staff logins that already exist (``accounts.staff_logins()``,
read-only from the shared ``auth.db``): a record is keyed on the login's
username, and a record may have no login at all (support staff, a caretaker,
someone not yet set up).

Kept from the old Staff Directory:

* Staff code (the old staff ID, ``T`` + 7 digits made up when left blank),
  title, first and last name, role (the old list), department, employment
  status (the old list, ``Left`` included), work e-mail, work phone, personal
  phone, room, line manager, start and end dates, the Tutor / DSL / Examiner
  flags, qualifications and notes.
* List active / all, filter (role, department, status, active only, tutors,
  DSL), search, view (with direct reports), new, edit, mark as left, delete,
  and the summary (by role / department / status, tutors, DSLs, examiners,
  critical roles nobody fills).
* From the old Staff HR record: contract type, FTE, salary scale, spine
  point, salary, holiday entitlement, probation and contract end, pension and
  union (HR-only fields, like the personal ones below).

New:

* **Login link.** ``username`` ties a record to its login (one record per
  login); :func:`import_logins` makes records for logins that have none and
  :func:`link_login` links one later. The e-mail falls back to the login's.
* **More of the job.** Preferred name, job title, role type (teaching /
  support / leadership), extension, leaving reason, QTS (date, TRN), ECT
  status with induction start and mentor.
* **Personal fields** (home address, personal e-mail, date of birth,
  emergency contact) and the HR fields are only for :data:`STAFF_EDITORS`;
  everyone else gets :meth:`StaffMember.redacted` copies.
* **Leavers are kept.** Marking someone as left keeps the record (and their
  history); reinstate undoes it. Delete is only for a record made in error
  with nothing pointing at it (:func:`register_reference`).
* **Profile** (:func:`profile`): what the system already knows - forms they
  tutor, teaching groups and timetable, cover done, departments, reports,
  mentees - read-only.
* Every change goes in ``staff_audit`` and the activity log (ids only). CSV
  export.

Other modules read it through :func:`get`, :func:`find`, :func:`for_username`,
:func:`list_staff` and :class:`StaffMember`.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import logging
import re
import secrets
from collections import Counter
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from education_system.systems.secondary.core.exceptions import errors
from education_system.systems.secondary.core.permissions.access import STAFF_EDITORS, STAFF_ROLES, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

logger = logging.getLogger(__name__)

ValidationError = errors.ValidationError
PermissionDenied = errors.PermissionDenied
NotFound = errors.NotFound

ID_PREFIX = "T"
ID_DIGITS = 7

TITLES: tuple[str, ...] = ("Mr", "Mrs", "Ms", "Miss", "Mx", "Dr", "Prof")

#: The old role list, plus a few the school also has.
ROLES: tuple[str, ...] = (
    "Principal", "Vice Principal", "Assistant Principal", "Head of Key Stage 3",
    "Head of Key Stage 4", "Head of Year", "Head of Department", "Subject Lead",
    "Teacher", "Tutor", "Cover Teacher", "Cover Supervisor", "Teaching Assistant",
    "Librarian", "Exams Officer", "Careers Adviser", "Counsellor", "Pastoral Manager",
    "Safeguarding Lead (DSL)", "Deputy DSL", "SENCO", "Administrator", "Receptionist",
    "Finance Officer", "Business Manager", "IT Support", "Technician", "Caretaker", "Other")
DEFAULT_ROLE = "Teacher"

ROLE_TYPES: tuple[str, ...] = ("teaching", "support", "leadership")
_LEADERSHIP = frozenset({"Principal", "Vice Principal", "Assistant Principal",
                         "Business Manager"})
_TEACHING = frozenset({"Head of Key Stage 3", "Head of Key Stage 4", "Head of Year",
                       "Head of Department", "Subject Lead", "Teacher", "Tutor",
                       "Cover Teacher", "SENCO"})

#: The old department list (Departments may hold more; any name is allowed).
DEPARTMENTS: tuple[str, ...] = (
    "English", "Mathematics", "Sciences", "Biology", "Chemistry", "Physics",
    "Computer Science", "Economics", "Business Studies", "Geography", "History",
    "Politics", "Psychology", "Sociology", "Religious Studies", "Philosophy",
    "Modern Languages", "Classics", "Art & Design", "Photography", "Music", "Drama",
    "Media Studies", "Physical Education", "School Office", "Pastoral", "Safeguarding",
    "Careers", "Library", "Exams", "Admin", "Finance", "IT", "Estates", "Other")
DEFAULT_DEPARTMENT = "Other"

EMPLOYMENT_STATUSES: tuple[str, ...] = (
    "Full-time", "Part-time", "Fractional", "Job Share", "Supply", "Probation",
    "Maternity Cover", "Sabbatical", "On Leave", "Left")
DEFAULT_EMPLOYMENT_STATUS = "Full-time"
ACTIVE_STATUSES = tuple(s for s in EMPLOYMENT_STATUSES if s not in ("Left", "Sabbatical"))

#: From the old Staff HR record.
CONTRACT_TYPES: tuple[str, ...] = (
    "Full-time", "Part-time", "Term-time", "Compressed Hours", "Job Share", "Zero Hours",
    "Sessional", "Other")
DEFAULT_CONTRACT_TYPE = "Full-time"
SALARY_SCALES: tuple[str, ...] = (
    "MPS", "UPS", "Leadership", "TLR", "Support Staff", "Administrative", "Technician",
    "Premises", "Senior Leader", "Other")

ECT_STATUSES: tuple[str, ...] = (
    "Not applicable", "ECT year 1", "ECT year 2", "Induction extended", "Induction passed",
    "Induction failed")
ECT_IN_INDUCTION = frozenset({"ECT year 1", "ECT year 2", "Induction extended"})
LEAVING_REASONS: tuple[str, ...] = (
    "Resigned", "Retired", "End of contract", "Dismissed", "Redundancy", "Moved school",
    "Deceased", "Other")

#: Roles a school must have someone in (the old "unfilled critical" check).
CRITICAL_ROLES: tuple[str, ...] = ("Principal", "Safeguarding Lead (DSL)", "Exams Officer",
                                   "SENCO")

#: Seen and changed only by STAFF_EDITORS.
PERSONAL_FIELDS: tuple[str, ...] = (
    "personal_phone", "personal_email", "home_address", "date_of_birth",
    "emergency_contact_name", "emergency_contact_relationship", "emergency_contact_phone")
HR_FIELDS: tuple[str, ...] = (
    "salary_scale", "spine_point", "salary_amount", "holiday_entitlement_days",
    "probation_end", "contract_end", "pension_enrolled", "union_member")
PRIVATE_FIELDS = PERSONAL_FIELDS + HR_FIELDS

_SCHEMA = """
CREATE TABLE IF NOT EXISTS staff_members (
    staff_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_code              TEXT NOT NULL UNIQUE COLLATE NOCASE,
    username                TEXT UNIQUE COLLATE NOCASE,
    title                   TEXT,
    first_name              TEXT NOT NULL,
    last_name               TEXT NOT NULL,
    preferred_name          TEXT,
    job_title               TEXT,
    role                    TEXT NOT NULL DEFAULT 'Teacher',
    role_type               TEXT NOT NULL DEFAULT 'teaching'
                            CHECK (role_type IN ('teaching', 'support', 'leadership')),
    department              TEXT,
    employment_status       TEXT NOT NULL DEFAULT 'Full-time',
    contract_type           TEXT NOT NULL DEFAULT 'Full-time',
    fte                     REAL NOT NULL DEFAULT 1.0 CHECK (fte > 0 AND fte <= 1),
    start_date              TEXT,
    leave_date              TEXT,
    leaving_reason          TEXT,
    room                    TEXT,
    extension               TEXT,
    work_email              TEXT,
    work_phone              TEXT,
    qts                     INTEGER NOT NULL DEFAULT 0,
    qts_date                TEXT,
    trn                     TEXT,
    ect_status              TEXT NOT NULL DEFAULT 'Not applicable',
    ect_start               TEXT,
    ect_mentor_id           INTEGER REFERENCES staff_members (staff_id) ON DELETE SET NULL,
    qualifications          TEXT,
    line_manager_id         INTEGER REFERENCES staff_members (staff_id) ON DELETE SET NULL,
    is_tutor                INTEGER NOT NULL DEFAULT 0,
    is_dsl                  INTEGER NOT NULL DEFAULT 0,
    is_examiner             INTEGER NOT NULL DEFAULT 0,
    personal_phone          TEXT,
    personal_email          TEXT,
    home_address            TEXT,
    date_of_birth           TEXT,
    emergency_contact_name  TEXT,
    emergency_contact_relationship TEXT,
    emergency_contact_phone TEXT,
    salary_scale            TEXT,
    spine_point             TEXT,
    salary_amount           REAL,
    holiday_entitlement_days REAL,
    probation_end           TEXT,
    contract_end            TEXT,
    pension_enrolled        INTEGER NOT NULL DEFAULT 1,
    union_member            TEXT,
    notes                   TEXT,
    created_by              TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by              TEXT,
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_staff_members_name ON staff_members (last_name, first_name);
CREATE INDEX IF NOT EXISTS ix_staff_members_manager ON staff_members (line_manager_id);
CREATE TABLE IF NOT EXISTS staff_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id   INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_staff_audit ON staff_audit (staff_id, audit_id);
"""
database.register_schema("staff_directory", _SCHEMA)


@dataclass(frozen=True)
class StaffMember:
    staff_id: int
    staff_code: str
    username: str | None
    title: str | None
    first_name: str
    last_name: str
    preferred_name: str | None
    job_title: str | None
    role: str
    role_type: str
    department: str | None
    employment_status: str
    contract_type: str
    fte: float
    start_date: str | None
    leave_date: str | None
    leaving_reason: str | None
    room: str | None
    extension: str | None
    work_email: str | None
    work_phone: str | None
    qts: bool
    qts_date: str | None
    trn: str | None
    ect_status: str
    ect_start: str | None
    ect_mentor_id: int | None
    qualifications: str | None
    line_manager_id: int | None
    is_tutor: bool
    is_dsl: bool
    is_examiner: bool
    personal_phone: str | None
    personal_email: str | None
    home_address: str | None
    date_of_birth: str | None
    emergency_contact_name: str | None
    emergency_contact_relationship: str | None
    emergency_contact_phone: str | None
    salary_scale: str | None
    spine_point: str | None
    salary_amount: float | None
    holiday_entitlement_days: float | None
    probation_end: str | None
    contract_end: str | None
    pension_enrolled: bool
    union_member: str | None
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    #: Filled in from the login / line manager when read.
    login_email: str | None = None
    line_manager_name: str | None = None
    mentor_name: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.preferred_name or self.first_name} {self.last_name}"

    @property
    def formal_name(self) -> str:
        return f"{self.title} {self.last_name}" if self.title else self.full_name

    @property
    def sort_name(self) -> str:
        return f"{self.last_name}, {self.preferred_name or self.first_name}"

    @property
    def label(self) -> str:
        """``"Ann Smith (T1234567)"`` - what a picker shows."""
        return f"{self.full_name} ({self.staff_code})"

    @property
    def email(self) -> str | None:
        return self.work_email or self.login_email

    @property
    def is_leaver(self) -> bool:
        if self.employment_status == "Left":
            return True
        return bool(self.leave_date and self.leave_date <= _today().isoformat())

    @property
    def is_active(self) -> bool:
        return not self.is_leaver and self.employment_status in ACTIVE_STATUSES

    @property
    def flags(self) -> str:
        return "".join(c for c, on in (("T", self.is_tutor), ("D", self.is_dsl),
                                       ("E", self.is_examiner)) if on)

    @property
    def in_induction(self) -> bool:
        return self.ect_status in ECT_IN_INDUCTION

    def names(self) -> set[str]:
        """Lower-case ways other records may name this person (matching)."""
        out = {self.full_name, f"{self.first_name} {self.last_name}", self.formal_name,
               self.username or "", self.work_email or "", self.login_email or "",
               self.staff_code}
        return {x.strip().lower() for x in out if x and x.strip()}

    def redacted(self) -> StaffMember:
        """A copy without the personal and HR fields (for non-editors)."""
        blank: dict[str, Any] = {k: None for k in PRIVATE_FIELDS}
        blank["pension_enrolled"] = False
        return replace(self, **blank)


_BASE = tuple(f.name for f in fields(StaffMember)
              if f.name not in ("login_email", "line_manager_name", "mentor_name"))
_SELECT = """
SELECT s.*, m.first_name AS m_first, m.preferred_name AS m_pref, m.last_name AS m_last,
       e.first_name AS e_first, e.preferred_name AS e_pref, e.last_name AS e_last
FROM staff_members s
LEFT JOIN staff_members m ON m.staff_id = s.line_manager_id
LEFT JOIN staff_members e ON e.staff_id = s.ect_mentor_id
"""


def _logins() -> list[dict]:
    from education_system.systems.secondary.infrastructure.authentication import accounts
    try:
        return accounts.staff_logins()
    except Exception:  # noqa: BLE001 - the login list is a help, not a gate
        logger.warning("Could not read the staff logins", exc_info=True)
        return []


def _login_emails() -> dict[str, str]:
    return {s["username"].lower(): s.get("email") or "" for s in _logins()}


def _row(r, emails: dict[str, str] | None = None) -> StaffMember:
    d = {k: r[k] for k in _BASE}
    for k in ("qts", "is_tutor", "is_dsl", "is_examiner", "pension_enrolled"):
        d[k] = bool(d[k])
    d["fte"] = float(d["fte"])
    mgr = f"{r['m_pref'] or r['m_first']} {r['m_last']}" if r["m_last"] else None
    men = f"{r['e_pref'] or r['e_first']} {r['e_last']}" if r["e_last"] else None
    email = (emails or {}).get((d["username"] or "").lower()) or None
    return StaffMember(**d, login_email=email, line_manager_name=mgr, mentor_name=men)


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in STAFF_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"staff.{action}", target=target, outcome="denied", principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can see the staff directory.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only HR / the school office can change staff records.")


def _audit(conn, action: str, actor: Principal, staff_id: int | None, **detail: Any) -> None:
    conn.execute("INSERT INTO staff_audit (staff_id, action, detail, actor) VALUES (?, ?, ?, ?)",
                 (staff_id, action, json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(staff_id: int | None = None, *, limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM staff_audit", []
    if staff_id is not None:
        sql += " WHERE staff_id = ?"
        params.append(int(staff_id))
    with database.connect() as conn:
        return [{"at": r["at"], "staff_id": r["staff_id"], "action": r["action"],
                 "actor": r["actor"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


#: (table, column, what it is) - rows that point at a staff record. Other
#: modules add theirs; delete refuses while any row uses the record.
_REFERENCES: list[tuple[str, str, str]] = []


def register_reference(table: str, column: str, label: str) -> None:
    if not (re.fullmatch(r"[a-z_][a-z0-9_]*", table)
            and re.fullmatch(r"[a-z_][a-z0-9_]*", column)):
        raise ValueError("bad table/column name")
    if (table, column, label) not in _REFERENCES:
        _REFERENCES.append((table, column, label))


register_reference("staff_members", "line_manager_id", "direct report(s)")
register_reference("staff_members", "ect_mentor_id", "ECT mentee(s)")


#: Tables that hold a person by their staff *login* (username) rather than
#: by staff_id - staff absence, the single central record ...
_LOGIN_REFERENCES: list[tuple[str, str, str]] = []

#: The modules that register references when imported: :func:`usage` loads
#: them first, so the delete guard never depends on which screens were opened.
_REFERRERS = (
    "education_system.systems.secondary.modules.staff.domain.departments",
    "education_system.systems.secondary.modules.staff.domain.appraisals",
    "education_system.systems.secondary.modules.staff.domain.appraisals_cpd",
    "education_system.systems.secondary.modules.staff.domain.staff_absence",
    "education_system.systems.secondary.modules.staff.domain.single_central_record",
)


def register_login_reference(table: str, column: str, label: str) -> None:
    """Like :func:`register_reference` for a column holding the username."""
    if not (re.fullmatch(r"[a-z_][a-z0-9_]*", table)
            and re.fullmatch(r"[a-z_][a-z0-9_]*", column)):
        raise ValueError("bad table/column name")
    if (table, column, label) not in _LOGIN_REFERENCES:
        _LOGIN_REFERENCES.append((table, column, label))


def _load_referrers() -> None:
    import importlib
    for name in _REFERRERS:
        try:
            importlib.import_module(name)
        except ImportError:
            logger.exception("Staff reference module %s could not be loaded", name)


def usage(staff_id: int) -> list[tuple[str, int]]:
    """[(what, rows)] pointing at this record (by staff_id, or by its login)."""
    _load_referrers()
    username = None
    out = []
    with database.connect() as conn:
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        for table, column, label in _REFERENCES:
            if table in have:
                n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = ?",  # nosec B608 - names checked in register_reference
                                 (int(staff_id),)).fetchone()[0]
                if n:
                    out.append((label, n))
        if _LOGIN_REFERENCES:
            row = conn.execute("SELECT username FROM staff_members WHERE staff_id = ?",
                               (int(staff_id),)).fetchone()
            username = row[0] if row else None
        for table, column, label in _LOGIN_REFERENCES if username else ():
            if table in have:
                n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE lower({column}) = lower(?)",  # nosec B608 - names checked in register_login_reference
                                 (username,)).fetchone()[0]
                if n:
                    out.append((label, n))
    return out


# ── Field cleaning (shared with departments / appraisals) ────────────

def clean_date(value: Any, label: str, problems: list[str]) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def clean_choice(value: Any, options: tuple[str, ...], label: str, problems: list[str],
                 default: str | None) -> str | None:
    v = str(value or "").strip()
    if not v:
        return default
    hit = next((o for o in options if o.lower() == v.lower()), None)
    if hit is None:
        problems.append(f"{label} must be one of {', '.join(options)}")
        return default
    return hit


def clean_text(value: Any, limit: int = 200) -> str | None:
    return (str(value or "").strip()[:limit]) or None


def clean_number(value: Any, label: str, problems: list[str], lo: float, hi: float
                 ) -> float | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        n = float(str(value).strip().replace(",", "").lstrip("£"))
    except ValueError:
        problems.append(f"{label} must be a number")
        return None
    if not lo <= n <= hi:
        problems.append(f"{label} must be between {lo:g} and {hi:g}")
        return None
    return n


def clean_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "y", "yes", "true", "on"}
    return bool(value)


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^[+0-9 ()\-]{3,25}$")
_CODE = re.compile(r"^[A-Za-z0-9]{2,10}$")


# ── Reading ──────────────────────────────────────────────────────────

def _one(where: str, value: Any) -> StaffMember | None:
    with database.connect() as conn:
        r = conn.execute(_SELECT + f" WHERE {where} LIMIT 1", (value,)).fetchone()  # nosec B608 - fixed
    return _row(r, _login_emails()) if r else None


def find(ref: Any) -> StaffMember | None:
    """A record by id, staff code, username or a picker label ("Name (code)");
    None if there is none."""
    if isinstance(ref, StaffMember):
        return ref
    if ref in (None, ""):
        return None
    if isinstance(ref, int):
        return _one("s.staff_id = ?", ref)
    text = str(ref).strip()
    if text.endswith(")") and "(" in text:
        text = text[text.rindex("(") + 1:-1].strip()
    if text.isdigit():
        hit = _one("s.staff_id = ?", int(text))
        if hit:
            return hit
    return (_one("s.staff_code = ?", text) or _one("s.username = ?", text)
            or _one("lower(s.work_email) = lower(?)", text))


def get(ref: Any) -> StaffMember:
    """Like :func:`find` but raises :class:`NotFound`."""
    m = find(ref)
    if m is None:
        raise NotFound(f"No staff record {ref}")
    return m


get_staff = get


def for_username(username: str | None) -> StaffMember | None:
    """The record linked to a login, or None."""
    return _one("s.username = ?", username.strip()) if username and username.strip() else None


def me(actor: Principal) -> StaffMember | None:
    return for_username(actor.username)


def list_staff(*, search: str | None = None, role: str | None = None,
               role_type: str | None = None, department: str | None = None,
               employment_status: str | None = None, include_leavers: bool = False,
               leavers_only: bool = False, tutors: bool = False, dsl: bool = False,
               line_manager_id: int | None = None, actor: Principal | None = None
               ) -> list[StaffMember]:
    """Staff by surname. Current staff unless *include_leavers* / *leavers_only*.
    With *actor* who isn't an editor, records come back :meth:`redacted`."""
    sql, params = _SELECT + " WHERE 1=1", []
    if search and search.strip():
        q = f"%{search.strip()}%"
        sql += (" AND (s.staff_code LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ? OR "
                "s.preferred_name LIKE ? OR s.username LIKE ? OR s.work_email LIKE ? OR "
                "s.role LIKE ? OR s.job_title LIKE ? OR s.department LIKE ? OR "
                "(coalesce(s.preferred_name, s.first_name) || ' ' || s.last_name) LIKE ?)")
        params += [q] * 10
    for col, val in (("s.role", role), ("s.role_type", role_type),
                     ("s.employment_status", employment_status)):
        if val:
            sql += f" AND {col} = ?"
            params.append(val)
    if department:
        sql += " AND lower(s.department) = lower(?)"
        params.append(department)
    if tutors:
        sql += " AND s.is_tutor = 1"
    if dsl:
        sql += " AND s.is_dsl = 1"
    if line_manager_id is not None:
        sql += " AND s.line_manager_id = ?"
        params.append(int(line_manager_id))
    sql += " ORDER BY s.last_name COLLATE NOCASE, s.first_name COLLATE NOCASE"
    emails = _login_emails()
    with database.connect() as conn:
        rows = [_row(r, emails) for r in conn.execute(sql, params)]
    if leavers_only:
        rows = [m for m in rows if m.is_leaver]
    elif not include_leavers:
        rows = [m for m in rows if not m.is_leaver]
    if actor is not None and not is_editor(actor):
        rows = [m.redacted() for m in rows]
    return rows


def search_staff(q: str, *, actor: Principal | None = None) -> list[StaffMember]:
    return list_staff(search=q, include_leavers=True, actor=actor)


def choices(*, include_leavers: bool = False) -> list[str]:
    """Picker labels, ``"Name (code)"``."""
    return [m.label for m in list_staff(include_leavers=include_leavers)]


def display_name(ref: Any) -> str:
    m = find(ref) if ref not in (None, "") else None
    return m.full_name if m else ""


def reports_to(staff_id: int) -> list[StaffMember]:
    """Current staff whose line manager is *staff_id*."""
    return list_staff(line_manager_id=staff_id)


def mentees(staff_id: int) -> list[StaffMember]:
    with database.connect() as conn:
        ids = [r[0] for r in conn.execute(
            "SELECT staff_id FROM staff_members WHERE ect_mentor_id = ?", (int(staff_id),))]
    return [m for m in (find(i) for i in ids) if m and not m.is_leaver]


def unlinked_logins() -> list[dict]:
    """Staff logins with no staff record yet."""
    with database.connect() as conn:
        have = {(r[0] or "").lower() for r in conn.execute(
            "SELECT username FROM staff_members WHERE username IS NOT NULL")}
    return [s for s in _logins() if s["username"].lower() not in have]


# ── Changing ─────────────────────────────────────────────────────────

FIELDS = (
    "staff_code", "username", "title", "first_name", "last_name", "preferred_name",
    "job_title", "role", "role_type", "department", "employment_status", "contract_type",
    "fte", "start_date", "leave_date", "leaving_reason", "room", "extension", "work_email",
    "work_phone", "qts", "qts_date", "trn", "ect_status", "ect_start", "ect_mentor_id",
    "qualifications", "line_manager_id", "is_tutor", "is_dsl", "is_examiner",
    *PRIVATE_FIELDS, "notes")

LABELS = {
    "staff_code": "Staff code", "username": "Login (username)", "title": "Title",
    "first_name": "First name", "last_name": "Last name", "preferred_name": "Preferred name",
    "job_title": "Job title", "role": "Role", "role_type": "Role type",
    "department": "Department", "employment_status": "Employment status",
    "contract_type": "Contract", "fte": "FTE", "start_date": "Start date",
    "leave_date": "Leave date", "leaving_reason": "Leaving reason", "room": "Room",
    "extension": "Extension", "work_email": "Work e-mail", "work_phone": "Work phone",
    "qts": "QTS", "qts_date": "QTS date", "trn": "Teacher reference no.",
    "ect_status": "ECT status", "ect_start": "Induction start", "ect_mentor_id": "ECT mentor",
    "qualifications": "Qualifications", "line_manager_id": "Line manager",
    "is_tutor": "Tutor", "is_dsl": "DSL", "is_examiner": "Examiner",
    "personal_phone": "Personal phone", "personal_email": "Personal e-mail",
    "home_address": "Home address", "date_of_birth": "Date of birth",
    "emergency_contact_name": "Emergency contact", "emergency_contact_relationship":
    "Emergency contact relationship", "emergency_contact_phone": "Emergency contact phone",
    "salary_scale": "Salary scale", "spine_point": "Spine point", "salary_amount": "Salary (£)",
    "holiday_entitlement_days": "Holiday entitlement (days)", "probation_end": "Probation ends",
    "contract_end": "Contract ends", "pension_enrolled": "Pension enrolled",
    "union_member": "Union", "notes": "Notes"}


def default_role_type(role: str | None) -> str:
    if role in _LEADERSHIP:
        return "leadership"
    return "teaching" if role in _TEACHING else "support"


def _staff_ref(value: Any, label: str, problems: list[str]) -> int | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    m = find(value)
    if m is None:
        problems.append(f"{label}: no staff record {value}")
        return None
    return m.staff_id


def _would_loop(staff_id: int, manager_id: int) -> bool:
    seen, cur = {staff_id}, manager_id
    with database.connect() as conn:
        while cur is not None:
            if cur in seen:
                return True
            seen.add(cur)
            r = conn.execute("SELECT line_manager_id FROM staff_members WHERE staff_id = ?",
                             (cur,)).fetchone()
            cur = r[0] if r else None
    return False


def _new_code(conn) -> str:
    for _ in range(200):
        code = ID_PREFIX + "".join(str(secrets.randbelow(10)) for _ in range(ID_DIGITS))
        if not conn.execute("SELECT 1 FROM staff_members WHERE staff_code = ?",
                            (code,)).fetchone():
            return code
    raise RuntimeError("Could not allocate a unique staff code")


def _clean(data: dict[str, Any], current: StaffMember | None) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in FIELDS})
    out: dict[str, Any] = {}
    code = clean_text(merged.get("staff_code"), 10)
    if code and not _CODE.match(code):
        problems.append("Staff code must be 2-10 letters or digits")
    out["staff_code"] = code.upper() if code else None
    out["username"] = clean_text(merged.get("username"), 64)
    title = clean_text(merged.get("title"), 10)
    out["title"] = clean_choice(title, TITLES, "Title", problems, None) if title else None
    for k in ("first_name", "last_name"):
        out[k] = clean_text(merged.get(k), 60)
        if not out[k]:
            problems.append(f"{LABELS[k]} is required")
    out["preferred_name"] = clean_text(merged.get("preferred_name"), 60)
    out["job_title"] = clean_text(merged.get("job_title"), 100)
    out["role"] = clean_choice(merged.get("role"), ROLES, "Role", problems, DEFAULT_ROLE)
    out["role_type"] = clean_choice(merged.get("role_type"), ROLE_TYPES, "Role type", problems,
                                    default_role_type(out["role"]))
    out["department"] = clean_text(merged.get("department"), 60)
    out["employment_status"] = clean_choice(merged.get("employment_status"), EMPLOYMENT_STATUSES,
                                            "Employment status", problems,
                                            DEFAULT_EMPLOYMENT_STATUS)
    out["contract_type"] = clean_choice(merged.get("contract_type"), CONTRACT_TYPES, "Contract",
                                        problems, DEFAULT_CONTRACT_TYPE)
    fte = clean_number(merged.get("fte"), "FTE", problems, 0.01, 1.0)
    out["fte"] = fte if fte is not None else (1.0 if out["contract_type"] == "Full-time" else None)
    if out["fte"] is None:
        if not any(p.startswith("FTE") for p in problems):
            problems.append("FTE is required for a part-time contract (e.g. 0.6)")
        out["fte"] = 1.0
    elif out["contract_type"] == "Full-time" and out["fte"] < 1:
        problems.append("A full-time contract is 1.0 FTE - choose Part-time for less")
    for k in ("start_date", "leave_date", "qts_date", "ect_start", "date_of_birth",
              "probation_end", "contract_end"):
        out[k] = clean_date(merged.get(k), LABELS[k], problems)
    if out["start_date"] and out["leave_date"] and out["leave_date"] < out["start_date"]:
        problems.append("Leave date can't be before the start date")
    if out["employment_status"] == "Left" and not out["leave_date"]:
        problems.append("A leaver needs a leave date (use Mark as left)")
    reason = clean_text(merged.get("leaving_reason"), 60)
    out["leaving_reason"] = clean_choice(reason, LEAVING_REASONS, "Leaving reason", problems,
                                         None) if reason else None
    out["room"] = clean_text(merged.get("room"), 20)
    out["extension"] = clean_text(merged.get("extension"), 15)
    for k in ("work_email", "personal_email"):
        out[k] = clean_text(merged.get(k), 254)
        if out[k] and not _EMAIL.match(out[k]):
            problems.append(f"{LABELS[k]} doesn't look like an e-mail address")
    for k in ("work_phone", "personal_phone", "emergency_contact_phone"):
        out[k] = clean_text(merged.get(k), 25)
        if out[k] and not _PHONE.match(out[k]):
            problems.append(f"{LABELS[k]} doesn't look like a phone number")
    for k in ("qts", "is_tutor", "is_dsl", "is_examiner"):
        out[k] = clean_bool(merged.get(k))
    out["pension_enrolled"] = clean_bool(merged.get("pension_enrolled", True)
                                         if current is None else merged.get("pension_enrolled"))
    trn = clean_text(merged.get("trn"), 10)
    if trn and not re.fullmatch(r"\d{7}", trn):
        problems.append("Teacher reference number is 7 digits")
    out["trn"] = trn
    if out["qts_date"] and not out["qts"]:
        out["qts"] = True
    out["ect_status"] = clean_choice(merged.get("ect_status"), ECT_STATUSES, "ECT status",
                                     problems, "Not applicable")
    if out["ect_status"] in ECT_IN_INDUCTION and out["role_type"] != "teaching":
        problems.append("Only teaching staff have ECT induction")
    out["ect_mentor_id"] = _staff_ref(merged.get("ect_mentor_id"), "ECT mentor", problems)
    out["line_manager_id"] = _staff_ref(merged.get("line_manager_id"), "Line manager", problems)
    if current is not None:
        for k, label in (("ect_mentor_id", "mentor"), ("line_manager_id", "line manager")):
            if out[k] == current.staff_id:
                problems.append(f"Someone can't be their own {label}")
        if out["line_manager_id"] and out["line_manager_id"] != current.line_manager_id \
                and _would_loop(current.staff_id, out["line_manager_id"]):
            problems.append("That line manager reports (directly or not) to this person")
    out["qualifications"] = clean_text(merged.get("qualifications"), 2000)
    out["home_address"] = clean_text(merged.get("home_address"), 300)
    out["emergency_contact_name"] = clean_text(merged.get("emergency_contact_name"), 100)
    out["emergency_contact_relationship"] = clean_text(
        merged.get("emergency_contact_relationship"), 40)
    scale = clean_text(merged.get("salary_scale"), 30)
    out["salary_scale"] = clean_choice(scale, SALARY_SCALES, "Salary scale", problems,
                                       None) if scale else None
    out["spine_point"] = clean_text(merged.get("spine_point"), 20)
    out["salary_amount"] = clean_number(merged.get("salary_amount"), "Salary", problems, 0,
                                        500000)
    out["holiday_entitlement_days"] = clean_number(merged.get("holiday_entitlement_days"),
                                                   "Holiday entitlement", problems, 0, 100)
    out["union_member"] = clean_text(merged.get("union_member"), 60)
    out["notes"] = clean_text(merged.get("notes"), 4000)
    return out, problems


def _check_login(username: str | None, current: StaffMember | None, problems: list[str]) -> str | None:
    """A new / changed username must be an active staff login with no record."""
    if not username or (current and (current.username or "").lower() == username.lower()):
        return username
    login = next((s for s in _logins() if s["username"].lower() == username.lower()), None)
    if login is None:
        problems.append(f"No active staff login '{username}' - leave the login blank for "
                        "staff without one")
        return username
    other = for_username(login["username"])
    if other and (current is None or other.staff_id != current.staff_id):
        problems.append(f"Login '{login['username']}' already has a record ({other.label})")
    return login["username"]


def create(data: dict[str, Any], *, actor: Principal) -> StaffMember:
    """The old New staff."""
    _require_editor(actor, "create")
    c, problems = _clean(data, None)
    c["username"] = _check_login(c["username"], None, problems)
    with database.connect() as conn:
        if c["staff_code"] and conn.execute("SELECT 1 FROM staff_members WHERE staff_code = ?",
                                            (c["staff_code"],)).fetchone():
            problems.append(f"Staff code {c['staff_code']} is already used")
        if problems:
            activity_log.record("staff.create", outcome="invalid", principal=actor,
                                problems=len(problems))
            raise ValidationError(problems)
        c["staff_code"] = c["staff_code"] or _new_code(conn)
        cols = list(FIELDS)
        sid = conn.execute(
            f"INSERT INTO staff_members ({', '.join(cols)}, created_by, updated_by) "  # nosec B608 - fixed columns
            f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
            (*(c[k] for k in cols), actor.username, actor.username)).lastrowid
        _audit(conn, "create", actor, sid, code=c["staff_code"], login=bool(c["username"]))
    activity_log.record("staff.create", target=c["staff_code"], principal=actor, staff=sid)
    return get(sid)


create_staff = create


def update(staff_id: int, changes: dict[str, Any], *, actor: Principal) -> StaffMember:
    """The old Edit staff. Returns the record as saved."""
    cur = get(int(staff_id))
    _require_editor(actor, "update", cur.staff_code)
    c, problems = _clean(changes, cur)
    c["username"] = _check_login(c["username"], cur, problems)
    if not c["staff_code"]:
        c["staff_code"] = cur.staff_code
    with database.connect() as conn:
        if c["staff_code"].lower() != cur.staff_code.lower() and conn.execute(
                "SELECT 1 FROM staff_members WHERE staff_code = ? AND staff_id != ?",
                (c["staff_code"], cur.staff_id)).fetchone():
            problems.append(f"Staff code {c['staff_code']} is already used")
        if problems:
            raise ValidationError(problems)
        changed = [k for k in FIELDS if c[k] != getattr(cur, k)]
        if not changed:
            return cur
        conn.execute("UPDATE staff_members SET " + ", ".join(f"{k} = ?" for k in changed)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE staff_id = ?",
                     (*(c[k] for k in changed), actor.username, cur.staff_id))
        _audit(conn, "update", actor, cur.staff_id,
               **{k: ("changed" if k in PRIVATE_FIELDS or k == "notes"
                      else {"from": getattr(cur, k), "to": c[k]}) for k in changed})
    activity_log.record("staff.update", target=cur.staff_code, principal=actor,
                        fields=changed)
    return get(cur.staff_id)


update_staff = update


def mark_left(staff_id: int, leave_date: str | None = None, *, actor: Principal,
              reason: str | None = None) -> StaffMember:
    """The old Mark as left. The record and its history stay."""
    cur = get(int(staff_id))
    _require_editor(actor, "leave", cur.staff_code)
    problems: list[str] = []
    day = clean_date(leave_date, "Leave date", problems) or _today().isoformat()
    if cur.start_date and day < cur.start_date:
        problems.append("Leave date can't be before the start date")
    if reason:
        reason = clean_choice(reason, LEAVING_REASONS, "Leaving reason", problems, None)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE staff_members SET employment_status = 'Left', leave_date = ?, "
                     "leaving_reason = coalesce(?, leaving_reason), updated_by = ?, "
                     "updated_at = datetime('now') WHERE staff_id = ?",
                     (day, reason, actor.username, cur.staff_id))
        _audit(conn, "leave", actor, cur.staff_id, leave_date=day, reason=reason)
    activity_log.record("staff.leave", target=cur.staff_code, principal=actor)
    return get(cur.staff_id)


def reinstate(staff_id: int, *, actor: Principal, status: str = DEFAULT_EMPLOYMENT_STATUS
              ) -> StaffMember:
    """Undo Mark as left (a returner, or a mistake)."""
    cur = get(int(staff_id))
    _require_editor(actor, "reinstate", cur.staff_code)
    if not cur.is_leaver:
        raise ValidationError([f"{cur.full_name} hasn't left"])
    problems: list[str] = []
    st = clean_choice(status, EMPLOYMENT_STATUSES, "Employment status", problems,
                      DEFAULT_EMPLOYMENT_STATUS)
    if st == "Left":
        problems.append("Choose the status they come back on")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE staff_members SET employment_status = ?, leave_date = NULL, "
                     "leaving_reason = NULL, updated_by = ?, updated_at = datetime('now') "
                     "WHERE staff_id = ?", (st, actor.username, cur.staff_id))
        _audit(conn, "reinstate", actor, cur.staff_id, was=cur.leave_date)
    activity_log.record("staff.reinstate", target=cur.staff_code, principal=actor)
    return get(cur.staff_id)


def delete(staff_id: int, *, actor: Principal) -> bool:
    """The old Delete: only for a record made in error. Anyone with history
    (a login, reports, departments, appraisals ...) is marked as left instead."""
    cur = get(int(staff_id))
    _require_editor(actor, "delete", cur.staff_code)
    used = usage(cur.staff_id)
    problems = [f"{cur.full_name} has {n} {label}" for label, n in used]
    if cur.is_leaver:
        problems.append(f"{cur.full_name} is a leaver - leavers' records are kept")
    if problems:
        raise ValidationError([*problems, "Mark them as left instead - the record is kept"])
    with database.connect() as conn:
        conn.execute("DELETE FROM staff_members WHERE staff_id = ?", (cur.staff_id,))
        _audit(conn, "delete", actor, cur.staff_id, code=cur.staff_code)
    activity_log.record("staff.delete", target=cur.staff_code, principal=actor)
    return True


delete_staff = delete


def _split(display: str, username: str) -> tuple[str | None, str, str]:
    parts = [p for p in re.split(r"\s+", (display or "").strip()) if p]
    title = None
    if parts and parts[0].rstrip(".").title() in TITLES and len(parts) > 1:
        title = parts.pop(0).rstrip(".").title()
    if len(parts) >= 2:
        return title, " ".join(parts[:-1]), parts[-1]
    if parts:
        return title, parts[0], parts[0] if title else "(surname)"
    return None, username, "(surname)"


def import_logins(*, actor: Principal, usernames: list[str] | None = None
                  ) -> list[StaffMember]:
    """A record for every staff login without one (or just *usernames*), named
    from the login and using its e-mail."""
    _require_editor(actor, "import")
    wanted = {u.lower() for u in usernames} if usernames else None
    made = []
    for s in unlinked_logins():
        if wanted is not None and s["username"].lower() not in wanted:
            continue
        title, first, last = _split(s.get("display_name") or "", s["username"])
        role = "Administrator" if s.get("role") in ("admin", "superadmin") else DEFAULT_ROLE
        made.append(create({"username": s["username"], "title": title, "first_name": first,
                            "last_name": last, "role": role}, actor=actor))
    activity_log.record("staff.import", principal=actor, rows=len(made))
    return made


def link_login(staff_id: int, username: str | None, *, actor: Principal) -> StaffMember:
    """Link a record to a staff login (``None`` / "" unlinks it)."""
    return update(staff_id, {"username": username or None}, actor=actor)


# ── Profile and summary ──────────────────────────────────────────────

def _matches(m: StaffMember, name: str | None, username: str | None = None,
             email: str | None = None) -> bool:
    keys = m.names()
    return any(v and v.strip().lower() in keys for v in (username, name, email))


def profile(ref: Any, *, actor: Principal) -> dict[str, Any]:
    """Everything the system knows about a member of staff (read-only).

    Keys: member, reports, mentees, departments, forms, tutor_assignments,
    groups, lessons, cover. Personal and HR fields only for editors."""
    _require_staff(actor, "profile")
    m = get(ref)
    out: dict[str, Any] = {"member": m if is_editor(actor) else m.redacted(),
                           "reports": reports_to(m.staff_id), "mentees": mentees(m.staff_id),
                           "departments": [], "forms": [], "tutor_assignments": [],
                           "groups": [], "lessons": [], "cover": []}
    from education_system.systems.secondary.modules.curriculum.domain import cover as CV
    from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
    from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
    from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
    from education_system.systems.secondary.modules.staff.domain import departments as DP
    out["departments"] = DP.memberships_for_staff(m.staff_id)
    for f in FG.list_forms():
        if _matches(m, f.tutor_name, email=f.tutor_email):
            out["forms"].append((f, "Tutor"))
        elif _matches(m, f.co_tutor_name):
            out["forms"].append((f, "Co-tutor"))
    try:
        from education_system.systems.secondary.modules.curriculum.domain import form_tutors as FT
        out["tutor_assignments"] = [
            a for a in FT.list_assignments()
            if _matches(m, a.tutor_name, a.tutor_username, a.contact_email)]
    except ImportError:  # pragma: no cover - the pastoral area is optional
        pass
    out["groups"] = [g for g in TG.list_groups()
                     if _matches(m, g.teacher_name, g.teacher_username, g.teacher_email)
                     or _matches(m, g.second_teacher)]
    out["lessons"] = [x for x in TT.list_lessons() if _matches(m, x.teacher, x.teacher_username)]
    out["cover"] = [c for c in CV.list_covers(include_cancelled=False)
                    if _matches(m, c.cover_name, c.cover_username)]
    activity_log.record("staff.profile", target=m.staff_code, principal=actor)
    return out


def profile_text(ref: Any, *, actor: Principal) -> str:
    """The profile as text (CLI and the GUI's text window)."""
    p = profile(ref, actor=actor)
    m: StaffMember = p["member"]
    lines = [f"{m.formal_name}  -  {m.full_name} ({m.staff_code})", ""]
    show = ["username", "job_title", "role", "role_type", "department", "employment_status",
            "contract_type", "fte", "start_date", "leave_date", "leaving_reason", "room",
            "extension", "work_phone"]
    for k in show:
        v = getattr(m, k)
        if v not in (None, ""):
            lines.append(f"  {LABELS[k] + ':':<28} {v}")
    if m.email:
        lines.append(f"  {'E-mail:':<28} {m.email}")
    lines.append(f"  {'Line manager:':<28} {m.line_manager_name or '-'}")
    lines.append(f"  {'QTS:':<28} {'yes' if m.qts else 'no'}"
                 + (f" ({m.qts_date})" if m.qts_date else "")
                 + (f", TRN {m.trn}" if m.trn else ""))
    if m.ect_status != "Not applicable":
        lines.append(f"  {'ECT:':<28} {m.ect_status}"
                     + (f" from {m.ect_start}" if m.ect_start else "")
                     + f", mentor {m.mentor_name or '(none)'}")
    lines.append(f"  {'Tutor / DSL / Examiner:':<28} "
                 + " / ".join("yes" if x else "no" for x in (m.is_tutor, m.is_dsl,
                                                               m.is_examiner)))
    if m.qualifications:
        lines += ["", "  Qualifications:", *(f"    {x}" for x in m.qualifications.splitlines())]
    if is_editor(actor):
        private = [(LABELS[k], getattr(m, k)) for k in PRIVATE_FIELDS
                   if getattr(m, k) not in (None, "")]
        if private:
            lines += ["", "  Personal / HR (HR only):"]
            lines += [f"    {lab + ':':<30} {v}" for lab, v in private]
    if m.notes:
        lines += ["", "  Notes:", *(f"    {x}" for x in m.notes.splitlines())]

    def section(title: str, items: list[str]) -> None:
        lines.extend(["", f"  {title} ({len(items)}):"] + [f"    {x}" for x in items]
                     if items else ["", f"  {title}: none"])

    section("Direct reports", [r.label + f" - {r.role}" for r in p["reports"]])
    section("ECT mentees", [r.label for r in p["mentees"]])
    section("Departments", [f"{d.department_name} - {d.role_in_department}"
                            + (" (primary)" if d.is_primary else "")
                            + (f", left {d.left_on}" if d.left_on else "")
                            for d in p["departments"]])
    section("Forms tutored", [f"{f.label} - {role}" for f, role in p["forms"]]
            + [f"{a.form_label} {a.academic_year} - {a.role} ({a.status})"
               for a in p["tutor_assignments"]])
    section("Teaching groups", [f"{g.code} (Year {g.year_group}, {g.academic_year})"
                                + (f", room {g.room}" if g.room else "") for g in p["groups"]])
    section("Timetable", [f"{x.slot_label}: {x.cell}" for x in p["lessons"]])
    done = [c for c in p["cover"] if c.status == "Completed"]
    section(f"Cover ({len(done)} completed)", [f"{c.date} P{c.period} {c.group_code} for "
                                                f"{c.absent_name} - {c.status}"
                                                for c in p["cover"][-30:]])
    return "\n".join(lines)


def summary() -> dict[str, Any]:
    """The old summary, plus role types, ECTs without a mentor and logins
    without a record."""
    rows = list_staff(include_leavers=True)
    current = [m for m in rows if not m.is_leaver]
    active = [m for m in current if m.is_active]
    roles_filled = Counter(m.role for m in active)
    return {
        "total": len(rows), "current": len(current), "active": len(active),
        "left": sum(1 for m in rows if m.is_leaver),
        "tutors": sum(1 for m in active if m.is_tutor),
        "dsls": sum(1 for m in active if m.is_dsl),
        "examiners": sum(1 for m in active if m.is_examiner),
        "fte": round(sum(m.fte for m in current), 2),
        "by_role": dict(Counter(m.role for m in current).most_common()),
        "by_role_type": dict(Counter(m.role_type for m in current).most_common()),
        "by_department": dict(Counter(m.department or "(none)" for m in current).most_common()),
        "by_status": dict(Counter(m.employment_status for m in rows).most_common()),
        "unfilled_critical": [r for r in CRITICAL_ROLES if not roles_filled.get(r)],
        "ects_without_mentor": [m for m in current if m.in_induction and not m.ect_mentor_id],
        "without_login": sum(1 for m in current if not m.username),
        "logins_without_record": len(unlinked_logins()),
    }


# ── Export ───────────────────────────────────────────────────────────

_EXPORT = ("staff_code", "title", "first_name", "last_name", "preferred_name", "job_title",
           "role", "role_type", "department", "employment_status", "contract_type", "fte",
           "start_date", "leave_date", "room", "extension", "work_phone", "qts", "ect_status")


def export_csv(path: str | Path, *, actor: Principal, include_personal: bool = False,
               **filters: Any) -> int:
    """The directory as CSV. *include_personal* (editors only) adds the
    personal and HR fields."""
    _require_staff(actor, "export")
    if include_personal:
        _require_editor(actor, "export_personal")
    rows = list_staff(**filters)
    cols = list(_EXPORT) + (["line_manager", "email", "username"]) + (
        list(PRIVATE_FIELDS) if include_personal else [])
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for m in rows:
            vals = [getattr(m, k) for k in _EXPORT] + [m.line_manager_name, m.email, m.username]
            if include_personal:
                vals += [getattr(m, k) for k in PRIVATE_FIELDS]
            w.writerow([_safe(v) if not isinstance(v, bool) else ("yes" if v else "no")
                        for v in vals])
    activity_log.record("staff.export", principal=actor, rows=len(rows),
                        personal=include_personal)
    return len(rows)
