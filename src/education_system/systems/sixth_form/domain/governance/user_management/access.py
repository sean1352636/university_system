"""Who may open what in the Sixth Form System.

Before this module, only the ``parent`` role was kept out of the staff
window: students, teachers and teaching assistants all got the whole
college, including safeguarding, medical, SEND, finance and HR. The
permissions overlay in :mod:`permissions` existed but nothing checked it.

A :class:`Principal` is resolved once per session (GUI/CLI) or request
(API) and carries a set of *capabilities*. Capabilities come from:

1. the shared-auth role for ``sixth_form`` (admin gets everything);
2. the linked ``staff`` record's job role and designations (DSL, SENCO,
   exams officer, finance officer ...), linked by ``staff.username``,
   then by e-mail;
3. per-user grant/revoke overrides from the permissions overlay.

Safeguarding is special-cased (KCSIE): role defaults never grant it.
It comes only from admin, a DSL/deputy DSL designation, or an explicit
per-user grant an administrator made in User Management.

Every menu label maps to one capability in :data:`MENU_CAPABILITIES`;
a label missing from the map is admin-only, so a new menu entry fails
closed until someone decides who should see it.
"""

from __future__ import annotations

import contextvars
import logging
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass, field
from typing import Any, Iterable

from education_system import paths

logger = logging.getLogger(__name__)

SYSTEM_KEY = "sixth_form"

# ── Capabilities ──────────────────────────────────────────────────────
STUDENTS_VIEW = "students.view"
STUDENTS_MANAGE = "students.manage"
ADMISSIONS = "admissions"
TEACHING = "teaching"
ASSESSMENT = "assessment"
PASTORAL = "pastoral"
SAFEGUARDING = "safeguarding"
MEDICAL = "medical"
SEND = "send"
EXAMS = "exams"
FINANCE = "finance"
FUNDING = "funding"
HR = "hr"
STAFF_DIRECTORY = "staff.directory"
CAREERS = "careers"
COMMS = "comms"
REPORTS = "reports"
OPERATIONS = "operations"
GOVERNANCE = "governance"
ACCOUNT = "account"          # change own password / MFA / about
ADMIN = "admin"

ALL_CAPABILITIES: frozenset[str] = frozenset({
    STUDENTS_VIEW, STUDENTS_MANAGE, ADMISSIONS, TEACHING, ASSESSMENT,
    PASTORAL, SAFEGUARDING, MEDICAL, SEND, EXAMS, FINANCE, FUNDING, HR,
    STAFF_DIRECTORY, CAREERS, COMMS, REPORTS, OPERATIONS, GOVERNANCE,
    ACCOUNT, ADMIN,
})

#: What every member of staff gets, whatever their job.
STAFF_BASE: frozenset[str] = frozenset({
    STUDENTS_VIEW, TEACHING, ASSESSMENT, COMMS, CAREERS, STAFF_DIRECTORY,
    ACCOUNT,
})

#: Extra capabilities by ``staff.role`` (job title).
JOB_ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    "Principal": frozenset(ALL_CAPABILITIES - {SAFEGUARDING, ADMIN}),
    "Vice Principal": frozenset(ALL_CAPABILITIES - {SAFEGUARDING, ADMIN}),
    "Head of Sixth Form": frozenset({
        STUDENTS_MANAGE, ADMISSIONS, PASTORAL, MEDICAL, SEND, EXAMS,
        REPORTS, FUNDING, OPERATIONS}),
    "Head of Year": frozenset({PASTORAL, MEDICAL, REPORTS}),
    "Head of Department": frozenset({REPORTS}),
    "Subject Lead": frozenset({REPORTS}),
    "Teacher": frozenset(),
    "Tutor": frozenset({PASTORAL}),
    "Cover Teacher": frozenset(),
    "Teaching Assistant": frozenset(),
    "Librarian": frozenset(),
    "Exams Officer": frozenset({EXAMS, REPORTS}),
    "Careers Adviser": frozenset({REPORTS}),
    "Counsellor": frozenset({PASTORAL, MEDICAL}),
    "Pastoral Manager": frozenset({PASTORAL, MEDICAL, SEND, REPORTS}),
    "Safeguarding Lead (DSL)": frozenset({
        SAFEGUARDING, PASTORAL, MEDICAL, SEND, REPORTS}),
    "Deputy DSL": frozenset({SAFEGUARDING, PASTORAL, MEDICAL, SEND}),
    "SENCO": frozenset({SEND, MEDICAL, PASTORAL, EXAMS}),
    "Administrator": frozenset({
        STUDENTS_MANAGE, ADMISSIONS, OPERATIONS, REPORTS}),
    "Receptionist": frozenset({OPERATIONS}),
    "Finance Officer": frozenset({FINANCE, FUNDING, REPORTS}),
    "IT Support": frozenset({OPERATIONS}),
    "Caretaker": frozenset({OPERATIONS}),
    "Other": frozenset(),
}

#: Teaching assistants and cover staff see less than teachers.
_LIMITED_JOB_ROLES = {"Teaching Assistant", "Cover Teacher", "Caretaker",
                      "Receptionist", "IT Support"}

#: Shared-auth roles that count as staff.
STAFF_AUTH_ROLES = {"staff", "teacher", "instructor", "teaching_assistant",
                    "faculty"}

#: Overlay permission -> capability, for per-user grants and revokes.
OVERLAY_TO_CAPABILITY: dict[str, str] = {
    "manage_users": GOVERNANCE,
    "manage_roles": GOVERNANCE,
    "view_user_audit": GOVERNANCE,
    "manage_students": STUDENTS_MANAGE,
    "view_students": STUDENTS_VIEW,
    "manage_attendance": TEACHING,
    "manage_gradebook": ASSESSMENT,
    "view_gradebook": ASSESSMENT,
    "manage_behaviour": PASTORAL,
    "view_safeguarding": SAFEGUARDING,
    "manage_safeguarding": SAFEGUARDING,
    "manage_finance": FINANCE,
    "view_finance": FINANCE,
    "manage_reports": REPORTS,
    "manage_settings": GOVERNANCE,
    "manage_comms": COMMS,
}

# ── Menu labels -> capability (shared by GUI and CLI) ─────────────────
# LADO is shown to HR as well as the safeguarding team because the
# Principal (HR, not safeguarding) manages allegations against staff;
# the register itself still admits only the DSL, Principal and admin.
MENU_CAPABILITIES: dict[str, str | tuple[str, ...]] = {
    # Student Management
    "Student Directory": STUDENTS_VIEW,
    "Add Student": STUDENTS_MANAGE,
    "Search Students": STUDENTS_VIEW,
    "Advanced Search": STUDENTS_VIEW,
    "Student Profile": STUDENTS_VIEW,
    # Safeguarding too: a DSL without admissions access opens the
    # Admissions DSL queue from this entry (gui_main.open_admissions).
    "Admissions": (ADMISSIONS, SAFEGUARDING),
    "Enrolment": (ADMISSIONS, STUDENTS_MANAGE),
    "Onboarding": (ADMISSIONS, STUDENTS_MANAGE),
    "Bulk Operations": STUDENTS_MANAGE,
    "Alumni": CAREERS,
    "Parent Portal": STUDENTS_MANAGE,
    # Academic Management
    "Academic Year & Calendar": TEACHING,
    "Courses": TEACHING,
    "Subjects & A-Levels": TEACHING,
    "Class Groups": TEACHING,
    "Timetable": TEACHING,
    "Timetable Optimiser": STUDENTS_MANAGE,
    "Attendance": TEACHING,
    "Lesson Plans": TEACHING,
    "Cover": TEACHING,
    "Cover Agency": HR,
    "Homework & Coursework": TEACHING,
    "Assignments": TEACHING,
    "Enrichment": TEACHING,
    "Library": TEACHING,
    "Study Planner": TEACHING,
    "EPQ": TEACHING,
    "Work Experience": CAREERS,
    "Room Booking": TEACHING,
    # Assessment & Grades
    "Gradebook": ASSESSMENT,
    "Predicted Grades": ASSESSMENT,
    "Baseline Assessment": ASSESSMENT,
    "Target Setting": ASSESSMENT,
    "ILP": ASSESSMENT,
    "Intervention Tracking": ASSESSMENT,
    "Early Warning": ASSESSMENT,
    "Risk Analytics": ASSESSMENT,
    "Value Added": REPORTS,
    "Mock Exams": ASSESSMENT,
    "Exam Entries": EXAMS,
    "Results Day": EXAMS,
    "Exams Office": EXAMS,
    "Report Cards": (ASSESSMENT, REPORTS),
    "Study Programme": (STUDENTS_VIEW, TEACHING),
    "Observations": HR,
    "Self Assessment": REPORTS,
    "Quality Assurance": REPORTS,
    "SEF Builder": REPORTS,
    # UCAS & Careers
    "University & UCAS": CAREERS,
    "University Visits": CAREERS,
    "Apprenticeships": CAREERS,
    "Careers Guidance": CAREERS,
    "Destinations": CAREERS,
    # Pastoral & Wellbeing
    "Tutor Groups": TEACHING,
    "Behaviour Log": TEACHING,
    "Disciplinary": PASTORAL,
    "Safeguarding": SAFEGUARDING,
    "Report a Safeguarding Concern": STUDENTS_VIEW,
    "LADO Allegations": (SAFEGUARDING, HR),
    "SEND": SEND,
    "Accessibility": SEND,
    "Wellbeing": PASTORAL,
    "Student Wellbeing": PASTORAL,
    "Student Support": PASTORAL,
    "Peer Mentoring": PASTORAL,
    "Attendance Concerns": PASTORAL,
    "Absence Requests": TEACHING,
    "First Aid": MEDICAL,
    "Medical Records": MEDICAL,
    "Emergency": OPERATIONS,
    "Prevent Duty": SAFEGUARDING,
    "Equality & Diversity": GOVERNANCE,
    "Complaints": PASTORAL,
    "Feedback": COMMS,
    "Surveys": COMMS,
    "Student Council": PASTORAL,
    "Transport": OPERATIONS,
    # Staff & Communication
    "Staff Directory": STAFF_DIRECTORY,
    "Departments": STAFF_DIRECTORY,
    "Staff HR": HR,
    "Staff Absence": HR,
    "Staff Wellbeing": HR,
    "Recruitment": HR,
    "Appraisals": HR,
    "CPD": STAFF_DIRECTORY,
    "DBS Checks": HR,
    "Single Central Record": (HR, SAFEGUARDING),
    "Visitors": OPERATIONS,
    "Parent Contacts": STUDENTS_VIEW,
    "Parents' Evenings": TEACHING,
    "Notices & Bulletins": COMMS,
    "Announcements": COMMS,
    "Notifications": ACCOUNT,
    "Activity Feed": COMMS,
    "Email / Messaging": COMMS,
    "Letter Templates": COMMS,
    "Document Hub": COMMS,
    "Attachments": COMMS,
    # Finance & Bursaries
    "Finance Dashboard": FINANCE,
    "Fees": FINANCE,
    "Bursary Applications": FINANCE,
    "Trips & Payments": FINANCE,
    "Receipts": FINANCE,
    "Expense Claims": STAFF_DIRECTORY,
    "Funding": FUNDING,
    "Census ILR": FUNDING,
    # Operations
    "Lockers": OPERATIONS,
    "Parking Permits": OPERATIONS,
    "Catering": OPERATIONS,
    "ID Cards": OPERATIONS,
    # Reports & Analytics
    "Attendance Report": REPORTS,
    "Grades Report": REPORTS,
    "Progress Tracking": ASSESSMENT,
    "KPI Dashboard": REPORTS,
    "Data Dashboard": REPORTS,
    "Progress Dashboard": ASSESSMENT,
    "Mobile Dashboard": REPORTS,
    "Audit Reports": GOVERNANCE,
    "Data Export": REPORTS,
    "Custom Export": REPORTS,
    # Cross-System
    "Student Journey": STUDENTS_VIEW,
    "Refer to FE College": STUDENTS_MANAGE,
    "Incoming FE Applications": ADMISSIONS,
    "Analytics Dashboard": REPORTS,
    "Cross-System Calendar": TEACHING,
    "Central Admin Portal": ADMIN,
    "GDPR Compliance": GOVERNANCE,
    "Shared Documents": COMMS,
    "Student Self-Service": STUDENTS_MANAGE,
    "Certificates": EXAMS,
    "University Visits → CRM": CAREERS,
    "Promote to Next System": STUDENTS_MANAGE,
    # System
    "Change Password": ACCOUNT,
    "Multi-Factor Authentication": ACCOUNT,
    "User Accounts": GOVERNANCE,
    "User Management": GOVERNANCE,
    "Settings": GOVERNANCE,
    "Integrations & Backups": ADMIN,
    "Compliance": GOVERNANCE,
    "Governance": GOVERNANCE,
    "Policies": STAFF_DIRECTORY,
    "GDPR": GOVERNANCE,
    "Risk Management": GOVERNANCE,
    "Automation Rules": GOVERNANCE,
    "Health & Safety": OPERATIONS,
    "Assets": OPERATIONS,
    "Multi-Language": ACCOUNT,
    "Online Learning Space": TEACHING,
    "Staff Timetables & Directed Time": TEACHING,
    "Mandatory Training": HR,
    "Staff Exit Interviews": HR,
    "My Area": STAFF_DIRECTORY,
    "Site & IT Helpdesk": STAFF_DIRECTORY,
    "Device Loans": OPERATIONS,
    "Fire Drills & Premises Checks": (OPERATIONS, GOVERNANCE, REPORTS),
    "Scheduled Jobs": GOVERNANCE,
    "Online Payments": FINANCE,
    "Cashless Catering": OPERATIONS,
    "Looked-After & Care Leavers": PASTORAL,
    "Young Carers": PASTORAL,
    "Tutorial & PSHE Programme": PASTORAL,
    "Contact Log": (COMMS, PASTORAL),
    "Student Exit Interviews": (PASTORAL, STUDENTS_MANAGE),
    "To-Do": ACCOUNT,
    "About": ACCOUNT,
}


class AccessDenied(PermissionError):
    """Raised when a principal lacks the capability for an action."""


@dataclass(frozen=True)
class Principal:
    username: str
    user_id: int | None
    role: str                         # shared-auth role for sixth_form
    is_superadmin: bool = False
    staff_id: str | None = None
    staff_name: str | None = None
    job_role: str | None = None
    designations: frozenset[str] = frozenset()
    student_id: str | None = None
    capabilities: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_admin(self) -> bool:
        return self.is_superadmin or self.role == "admin"

    @property
    def is_staff(self) -> bool:
        return self.is_admin or self.role in STAFF_AUTH_ROLES

    @property
    def is_student(self) -> bool:
        return self.role == "student"

    @property
    def is_parent(self) -> bool:
        return self.role == "parent"

    def can(self, capability: str) -> bool:
        return self.is_admin or capability in self.capabilities

    def require(self, capability: str, action: str = "") -> None:
        if not self.can(capability):
            what = action or capability
            raise AccessDenied(
                f"{self.username or 'This account'} is not allowed to "
                f"access {what}.")

    def can_open(self, menu_label: str) -> bool:
        """A tuple entry means any one of those capabilities is enough."""
        needed = MENU_CAPABILITIES.get(menu_label, ADMIN)
        if isinstance(needed, tuple):
            return any(self.can(c) for c in needed)
        return self.can(needed)


ANONYMOUS = Principal(username="", user_id=None, role="")


# ── Staff / student links ─────────────────────────────────────────────

def _connect() -> _sql.Connection:
    conn = _sql.connect(str(paths.SIXTH_FORM_STAFF_DB))
    conn.row_factory = _sql.Row
    return conn


def _columns(conn: _sql.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}  # DBW001: table is a literal at every call site


_LINK_READY = False


def ensure_staff_login_link() -> None:
    """Add ``staff.username`` (the shared-auth login) if missing. Idempotent."""
    global _LINK_READY
    if _LINK_READY:
        return
    try:
        from education_system.systems.sixth_form.domain.staff import staff as staff_mod
        staff_mod.init_db()
        with _connect() as conn:
            if "username" not in _columns(conn, "staff"):
                conn.execute("ALTER TABLE staff ADD COLUMN username TEXT")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_staff_username "
                "ON staff(username) WHERE username IS NOT NULL")
        _LINK_READY = True
    except _sql.Error:
        logger.exception("Could not add staff.username login link")


def link_staff_login(staff_id: str, username: str | None) -> None:
    """Record which shared-auth login belongs to a staff record."""
    ensure_staff_login_link()
    with _connect() as conn:
        conn.execute("UPDATE staff SET username = ? WHERE staff_id = ?",
                     ((username or "").strip() or None, staff_id))


def _staff_row(username: str, email: str | None) -> _sql.Row | None:
    ensure_staff_login_link()
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM staff WHERE username = ? COLLATE NOCASE",
                (username,)).fetchone()
            if row is None and email:
                row = conn.execute(
                    "SELECT * FROM staff WHERE email = ? COLLATE NOCASE "
                    "AND (username IS NULL OR username = '')",
                    (email,)).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM staff WHERE staff_id = ? COLLATE NOCASE",
                    (username,)).fetchone()
            return row
    except _sql.Error:
        logger.exception("Staff lookup failed for %s", username)
        return None


def _student_exists(student_id: str) -> bool:
    try:
        conn = _sql.connect(str(paths.SIXTH_FORM_STUDENTS_DB))
        try:
            return conn.execute(
                "SELECT 1 FROM students WHERE student_id = ?",
                (student_id,)).fetchone() is not None
        finally:
            conn.close()
    except _sql.Error:
        return False


def designations_for(row: _sql.Row | None) -> frozenset[str]:
    if row is None:
        return frozenset()
    keys = row.keys()
    out: set[str] = set()
    job = row["role"] if "role" in keys else None
    if "is_dsl" in keys and row["is_dsl"]:
        out.add("dsl")
    if job == "Deputy DSL":
        out.add("deputy_dsl")
    if job == "Safeguarding Lead (DSL)":
        out.add("dsl")
    if "is_tutor" in keys and row["is_tutor"]:
        out.add("tutor")
    if "is_examiner" in keys and row["is_examiner"]:
        out.add("examiner")
    if job == "SENCO":
        out.add("senco")
    if job == "Exams Officer":
        out.add("exams_officer")
    return frozenset(out)


def _overlay_overrides(user_id: int | None) -> list[dict]:
    if user_id is None:
        return []
    try:
        from education_system.platform.identity.auth import db as auth_db
        with auth_db.connect() as conn:
            conn.row_factory = _sql.Row
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='user_permission_overrides'").fetchone()
            if not exists:
                return []
            return [dict(r) for r in conn.execute(
                "SELECT permission, mode FROM user_permission_overrides "
                "WHERE user_id = ? AND system_key = ?",
                (user_id, SYSTEM_KEY))]
    except Exception:
        logger.exception("Could not read permission overrides for %s", user_id)
        return []


def capabilities_for(role: str, *, job_role: str | None,
                     designations: Iterable[str],
                     overrides: Iterable[dict] = ()) -> frozenset[str]:
    role = (role or "").lower()
    if role == "admin":
        return ALL_CAPABILITIES
    caps: set[str] = set()
    if role in STAFF_AUTH_ROLES:
        caps |= STAFF_BASE
        if job_role in _LIMITED_JOB_ROLES or role == "teaching_assistant":
            caps -= {CAREERS}
        caps |= JOB_ROLE_CAPABILITIES.get(job_role or "", frozenset())
        des = set(designations)
        if des & {"dsl", "deputy_dsl"}:
            caps |= {SAFEGUARDING, PASTORAL, MEDICAL, SEND}
        if "senco" in des:
            caps |= {SEND, MEDICAL}
        if "exams_officer" in des:
            caps |= {EXAMS}
        if "tutor" in des:
            caps |= {PASTORAL}
        # A role default can never grant safeguarding; only a
        # designation or an explicit per-user grant can.
        if not des & {"dsl", "deputy_dsl"} and job_role not in (
                "Safeguarding Lead (DSL)", "Deputy DSL"):
            caps.discard(SAFEGUARDING)
    elif role in ("student", "parent", "alumni"):
        caps |= {ACCOUNT}
    for ov in overrides:
        cap = OVERLAY_TO_CAPABILITY.get(ov.get("permission", ""))
        if not cap:
            continue
        if ov.get("mode") == "grant" and role in STAFF_AUTH_ROLES:
            caps.add(cap)
        elif ov.get("mode") == "revoke":
            caps.discard(cap)
    return frozenset(caps)


def resolve(username: str, role: str | None, *, user_id: int | None = None,
            email: str | None = None,
            is_superadmin: bool = False) -> Principal:
    """Build the :class:`Principal` for a signed-in user."""
    username = (username or "").strip()
    role = (role or "").strip().lower()
    if is_superadmin:
        role = role or "admin"
    if not username or not role:
        return ANONYMOUS
    staff_row = _staff_row(username, email) if role in STAFF_AUTH_ROLES | {"admin"} else None
    job_role = staff_row["role"] if staff_row is not None else None
    des = designations_for(staff_row)
    student_id = username if role == "student" and _student_exists(username) else None
    caps = capabilities_for(
        "admin" if is_superadmin else role, job_role=job_role,
        designations=des, overrides=_overlay_overrides(user_id))
    return Principal(
        username=username, user_id=user_id, role=role,
        is_superadmin=is_superadmin,
        staff_id=staff_row["staff_id"] if staff_row is not None else None,
        staff_name=(f"{staff_row['first_name']} {staff_row['last_name']}"
                    if staff_row is not None else None),
        job_role=job_role, designations=des, student_id=student_id,
        capabilities=caps)


def for_username(username: str) -> Principal:
    """Principal for an account by username alone, read from auth.db: for
    work done on someone's behalf with nobody signed in (a scheduled
    search alerting its subscriber). Inactive or unknown accounts get
    :data:`ANONYMOUS`."""
    username = (username or "").strip()
    if not username:
        return ANONYMOUS
    try:
        from education_system.platform.identity.auth import db as auth_db
        with auth_db.connect() as conn:
            conn.row_factory = _sql.Row
            u = conn.execute("SELECT id, email, is_active FROM users "
                             "WHERE username = ?", (username,)).fetchone()
            if u is None or not u["is_active"]:
                return ANONYMOUS
            systems = [dict(r) for r in conn.execute(
                "SELECT system_key, role FROM user_systems WHERE user_id = ?",
                (u["id"],))]
    except Exception:
        logger.exception("Could not resolve account %s", username)
        return ANONYMOUS
    role = next((s["role"] for s in systems if s["system_key"] == SYSTEM_KEY),
                None)
    superadmin = _superadmin_from_systems(systems)
    if role is None and not superadmin:
        return ANONYMOUS
    return resolve(username, role, user_id=u["id"], email=u["email"],
                   is_superadmin=superadmin)


def _superadmin_from_systems(systems: Any) -> bool:
    try:
        from education_system.launcher.roles import is_superadmin
        return bool(is_superadmin({"systems": systems or []}))
    except Exception:
        return False


def from_auth(auth: Any, role: str | None = None) -> Principal:
    """Principal for a GUI/CLI session's shared ``UserAuth``."""
    cu = getattr(auth, "current_user", None) or {}
    if not isinstance(cu, dict):
        return ANONYMOUS
    systems = cu.get("systems") or []
    if role is None:
        role = cu.get("role")
        for s in systems:
            if isinstance(s, dict) and s.get("system_key") == SYSTEM_KEY:
                role = s.get("role") or role
                break
    return resolve(cu.get("username", ""), role,
                   user_id=cu.get("id") or cu.get("user_id"),
                   email=cu.get("email"),
                   is_superadmin=_superadmin_from_systems(systems))


def from_request_user(user: dict | None) -> Principal:
    """Principal for an API request's ``flask.g.current_user``."""
    user = user or {}
    if user.get("role") == "service":
        # Shared-secret service token: trusted integration, staff-level
        # but never safeguarding/medical/HR.
        return Principal(
            username="service", user_id=None, role="staff",
            capabilities=frozenset(STAFF_BASE | {REPORTS}))
    systems = user.get("systems") or []
    role = user.get("role")
    for s in systems:
        if isinstance(s, dict) and s.get("system_key") == SYSTEM_KEY:
            role = s.get("role") or role
            break
    return resolve(user.get("username") or user.get("sub") or "", role,
                   user_id=user.get("user_id"),
                   is_superadmin=_superadmin_from_systems(systems))


# ── Object scope ──────────────────────────────────────────────────────

def _staff_match_values(p: Principal) -> list[str]:
    vals = [v for v in (p.staff_id, p.staff_name, p.username) if v]
    return list(dict.fromkeys(vals))


def taught_student_ids(p: Principal) -> set[str]:
    """Students in the principal's tutor groups and class groups."""
    vals = _staff_match_values(p)
    if not vals:
        return set()
    marks = ",".join("?" * len(vals))
    out: set[str] = set()
    try:
        conn = _sql.connect(str(paths.SIXTH_FORM_STUDENTS_DB))
        try:
            for sql in (
                f"SELECT s.student_id FROM tutor_group_students s "
                f"JOIN tutor_groups g ON g.tutor_group_id = s.tutor_group_id "
                f"WHERE g.tutor IN ({marks}) OR g.co_tutor IN ({marks})",
                f"SELECT s.student_id FROM class_group_students s "
                f"JOIN class_groups g ON g.group_id = s.group_id "
                f"WHERE g.teacher IN ({marks})",
            ):
                args = vals * sql.count(f"({marks})")
                try:
                    out.update(r[0] for r in conn.execute(sql, args))  # DBW001: only placeholders are interpolated
                except _sql.OperationalError:
                    continue
        finally:
            conn.close()
    except _sql.Error:
        logger.exception("Could not resolve taught students for %s", p.username)
    return out


def can_see_student(p: Principal, student_id: str, *,
                    capability: str = STUDENTS_VIEW) -> bool:
    """Object-level check: may *p* see this student's *capability* data?

    Staff with the capability see every student for directory-level
    data. For pastoral data, staff whose only route to PASTORAL is
    being a tutor see their own tutees and taught students only.
    Students see themselves; parents go through the parent portal's own
    linked-children check.
    """
    allowed = visible_student_ids(p, capability=capability)
    return allowed is None or student_id in allowed


def visible_student_ids(p: Principal, *,
                        capability: str = STUDENTS_VIEW) -> set[str] | None:
    """The students whose *capability* data *p* may see: ``None`` means
    every student, a set means only those. The list form of
    :func:`can_see_student`, for screens that filter many rows at once."""
    if p.is_admin:
        return None
    if p.is_student:
        return {p.student_id} if p.student_id else set()
    if not p.is_staff or not p.can(capability):
        return set()
    if capability == PASTORAL and p.job_role in (None, "Teacher", "Tutor") \
            and not p.designations & {"dsl", "deputy_dsl"}:
        return taught_student_ids(p)
    return None


# ── Audit of sensitive reads ──────────────────────────────────────────

_AUDIT_READY = False

_AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS sensitive_access_log (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL DEFAULT (datetime('now')),
    username    TEXT NOT NULL,
    area        TEXT NOT NULL,
    action      TEXT NOT NULL,
    student_id  TEXT,
    record_ref  TEXT,
    allowed     INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_sal_student ON sensitive_access_log(student_id);
CREATE INDEX IF NOT EXISTS idx_sal_at      ON sensitive_access_log(at);
"""


def log_sensitive_access(p: Principal, area: str, action: str, *,
                         student_id: str | None = None,
                         record_ref: str | None = None,
                         allowed: bool = True) -> None:
    """Record who opened or changed a safeguarding/medical/SEND record.

    Never raises: a logging failure must not block a DSL mid-incident,
    but it is logged loudly.
    """
    global _AUDIT_READY
    try:
        conn = _sql.connect(str(paths.SIXTH_FORM_STUDENTS_DB))
        try:
            if not _AUDIT_READY:
                conn.executescript(_AUDIT_SCHEMA)
                _AUDIT_READY = True
            conn.execute(
                "INSERT INTO sensitive_access_log "
                "(username, area, action, student_id, record_ref, allowed) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (p.username or "?", area, action, student_id,
                 record_ref, int(allowed)))
            conn.commit()
        finally:
            conn.close()
    except _sql.Error:
        logger.exception("Could not write sensitive access log (%s %s)",
                         area, action)


def list_sensitive_access(*, student_id: str | None = None,
                          area: str | None = None,
                          limit: int = 500) -> list[dict]:
    clauses, args = [], []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    if area:
        clauses.append("area = ?")
        args.append(area)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    try:
        conn = _sql.connect(str(paths.SIXTH_FORM_STUDENTS_DB))
        conn.row_factory = _sql.Row
        try:
            conn.executescript(_AUDIT_SCHEMA)
            return [dict(r) for r in conn.execute(
                f"SELECT * FROM sensitive_access_log {where} "  # DBW001: where is built from fixed clauses
                f"ORDER BY log_id DESC LIMIT ?", (*args, int(limit)))]
        finally:
            conn.close()
    except _sql.Error:
        logger.exception("Could not read sensitive access log")
        return []


# ── Current principal ─────────────────────────────────────────────────
# The GUI and CLI are one user per process, so they set a process-wide
# principal. The API serves many users at once, so each request binds
# its own principal in a context variable, which takes precedence.

_current: Principal = ANONYMOUS
_request_principal: contextvars.ContextVar[Principal | None] = (
    contextvars.ContextVar("sixth_form_principal", default=None))


def set_current(p: Principal) -> None:
    """Remember the signed-in principal for domain code that has no auth."""
    global _current
    _current = p


def bind_request(p: Principal) -> contextvars.Token:
    """Bind *p* for the current API request; pass the token to unbind."""
    return _request_principal.set(p)


def unbind_request(token: contextvars.Token) -> None:
    _request_principal.reset(token)


def current() -> Principal:
    bound = _request_principal.get()
    return bound if bound is not None else _current
