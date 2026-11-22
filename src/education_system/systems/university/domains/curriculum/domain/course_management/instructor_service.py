"""Unified instructor-creation service.

Single source of truth for creating an instructor across the stores the
concept is fragmented over:

* ``instructors`` table        — scheduling / course-management pickers
* local ``users`` + ``user_accounts`` — the staff directory + legacy local login
* shared ``auth.db``           — the unified-launcher login

Every GUI/CLI that creates an instructor should call :func:`create_instructor`
instead of hand-rolling its own INSERT, so the paths can't drift. Which stores
get populated is controlled by the ``create_login`` / ``register_as_staff`` /
``send_welcome_email`` flags (all default on = a "complete" instructor).

The function is deliberately UI-free (no tkinter, no ``input()``) so it is
unit-testable and reusable from any front end.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.infrastructure.utils.activity_logger import (
    log_delete,
    log_update,
)

from education_system.systems.university.domains.curriculum.domain.course_management.instructors import (
    _generate_university_email,
    _generate_temp_password,
    _create_instructor_account,
    _register_instructor_as_staff,
    _send_instructor_welcome_email,
)
from education_system.systems.university.domains.curriculum.domain.course_management.validation import (
    validate_email,
)

try:
    from education_system.systems.university.infrastructure.defaults import UNIVERSITY_EMAIL_DOMAIN
except ImportError:  # pragma: no cover - defensive fallback
    UNIVERSITY_EMAIL_DOMAIN = "university.edu"

logger = logging.getLogger(__name__)


@dataclass
class InstructorCreateResult:
    """Outcome of :func:`create_instructor`.

    ``ok`` reports whether the core ``instructors`` record was created. The
    optional stores each set their own flag and append a human-readable note to
    ``warnings`` when they soft-fail — they never abort the instructor.
    """

    ok: bool = False
    instructor_id: Optional[int] = None   # instructors.id (scheduling record)
    user_id: Optional[int] = None         # local users.id (staff table + local login)
    username: str = ""
    email: str = ""
    temp_password: Optional[str] = None
    account_created: bool = False         # shared auth.db account
    staff_registered: bool = False        # local users + user_accounts rows
    welcome_email_sent: bool = False
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None


_INSTRUCTORS_SCHEMA = """
CREATE TABLE IF NOT EXISTS instructors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    department TEXT DEFAULT '',
    specialization TEXT DEFAULT '',
    max_courses_per_semester INTEGER DEFAULT 4,
    max_hours_per_week INTEGER DEFAULT 40,
    preferred_days TEXT,
    preferred_times TEXT,
    status TEXT DEFAULT 'Active',
    is_active BOOLEAN DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _email_exists(conn, email: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM instructors WHERE email = ?", (email,)
    ).fetchone() is not None


def _next_available_email(conn, first_name: str, last_name: str) -> str:
    """Return an unused university email, appending a counter on collision."""
    clean_first = first_name.lower().strip().replace(" ", "")
    clean_last = last_name.lower().strip().replace(" ", "")
    candidate = f"{clean_first}.{clean_last}@{UNIVERSITY_EMAIL_DOMAIN}"
    counter = 1
    while _email_exists(conn, candidate):
        candidate = f"{clean_first}.{clean_last}{counter}@{UNIVERSITY_EMAIL_DOMAIN}"
        counter += 1
    return candidate


def create_instructor(
    *,
    first_name: str,
    last_name: str,
    email: Optional[str] = None,
    department: str = "",
    specialization: str = "",
    max_courses: int = 4,
    max_hours: int = 40,
    preferred_days: str = "",
    preferred_times: str = "",
    status: str = "Active",
    auth=None,
    temp_password: Optional[str] = None,
    create_login: bool = True,
    register_as_staff: bool = True,
    send_welcome_email: bool = True,
) -> InstructorCreateResult:
    """Create an instructor across every relevant store.

    Parameters
    ----------
    email:
        If ``None``/blank, a ``firstname.lastname@university.edu`` address is
        generated (and de-duplicated with a counter). If supplied, it is used
        as-is and a collision is reported as an error (the caller's chosen
        address is never silently rewritten).
    auth:
        Auth context passed through to shared-auth account creation. Only used
        when ``create_login`` is True.
    create_login / register_as_staff / send_welcome_email:
        Toggle the optional stores. All default on. A lightweight caller (e.g.
        a scheduling-only dialog) can flip these off.
    """
    r = InstructorCreateResult()

    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    if not first_name or not last_name:
        r.error = "First name and last name are required."
        return r

    auto_email = not (email and email.strip())
    email = _generate_university_email(first_name, last_name) if auto_email else email.strip()

    if not validate_email(email):
        r.error = f"Invalid email address: {email}"
        return r

    try:
        max_courses = int(max_courses)
        max_hours = int(max_hours)
    except (TypeError, ValueError):
        r.error = "Max courses and max hours must be numbers."
        return r

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- Core record: the instructors row (its own transaction) ---
    try:
        with transaction() as conn:
            conn.execute(_INSTRUCTORS_SCHEMA)
            if _email_exists(conn, email):
                if auto_email:
                    email = _next_available_email(conn, first_name, last_name)
                else:
                    r.error = f"Email '{email}' already exists."
                    return r
            cursor = conn.execute(
                """INSERT INTO instructors
                   (first_name, last_name, email, department, specialization,
                    max_courses_per_semester, max_hours_per_week, preferred_days,
                    preferred_times, status, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (first_name, last_name, email, department, specialization,
                 max_courses, max_hours, preferred_days, preferred_times,
                 status, now, now),
            )
            r.instructor_id = cursor.lastrowid
    except Exception as e:  # noqa: BLE001 - report failure to caller, don't crash the GUI
        r.error = f"Failed to create instructor record: {e}"
        return r

    r.email = email
    r.username = email.split("@")[0]
    r.temp_password = temp_password or _generate_temp_password()
    display_name = f"{first_name} {last_name}"

    # --- Optional stores: each soft-fails into warnings ---
    if register_as_staff:
        uid = _register_instructor_as_staff(
            r.username, first_name, last_name, email, r.temp_password
        )
        r.user_id = uid
        r.staff_registered = uid is not None
        if uid is None:
            r.warnings.append("Could not add the instructor to the staff directory.")

    if create_login:
        account_uid = _create_instructor_account(
            auth, r.username, r.temp_password, display_name, email
        )
        r.account_created = account_uid is not None
        if account_uid is None:
            r.warnings.append("Could not create a unified-launcher login account.")

    if send_welcome_email:
        r.welcome_email_sent = _send_instructor_welcome_email(
            first_name, last_name, r.username, email,
            department, specialization, r.temp_password,
        )
        if not r.welcome_email_sent:
            r.warnings.append("Welcome email could not be sent.")

    r.ok = True
    return r


# ---------------------------------------------------------------------------
# Choices for the instructor forms
# ---------------------------------------------------------------------------

#: The days the timetabling code schedules (module_scheduling.DAYS_OF_WEEK).
TEACHING_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
MAX_PREFERRED_DAYS = 4
INSTRUCTOR_STATUSES = ("Active", "Inactive", "On Leave")

#: (label shown, value stored). The stored HH:MM-HH:MM form is what the
#: timetabling warnings and the auto-scheduler parse.
PREFERRED_TIME_WINDOWS = (
    ("9am-5pm", "09:00-17:00"),
    ("8am-4pm", "08:00-16:00"),
    ("10am-6pm", "10:00-18:00"),
    ("9am-12pm", "09:00-12:00"),
    ("9am-1pm", "09:00-13:00"),
    ("10am-1pm", "10:00-13:00"),
    ("10am-4pm", "10:00-16:00"),
    ("12pm-5pm", "12:00-17:00"),
    ("1pm-5pm", "13:00-17:00"),
    ("2pm-6pm", "14:00-18:00"),
    ("5pm-9pm", "17:00-21:00"),
)


def time_label(stored: Optional[str]) -> str:
    """The label for a stored window; anything older is shown as it was typed."""
    stored = (stored or "").strip()
    return next((lab for lab, val in PREFERRED_TIME_WINDOWS if val == stored), stored)


def time_value(label: Optional[str]) -> str:
    """The value to store for a label; an older free-text value is kept as is."""
    label = (label or "").strip()
    return next((val for lab, val in PREFERRED_TIME_WINDOWS if lab == label), label)


def parse_preferred_days(raw: Optional[str]) -> List[str]:
    """Known days in a stored value, in order, once each, at most four."""
    by_prefix = {d.lower()[:3]: d for d in TEACHING_DAYS}
    days: List[str] = []
    for token in str(raw or "").replace(";", ",").split(","):
        day = by_prefix.get(token.strip().lower()[:3])
        if day and day not in days:
            days.append(day)
    return days[:MAX_PREFERRED_DAYS]


def department_specialisms() -> "dict[str, List[str]]":
    """Each department with its specialisms, read from the course catalogue.

    The ``departments`` table holds helpdesk teams (IT Support, Wellbeing …),
    so the teaching departments are the ones courses belong to, and a specialism
    is a subject taught there. A new course adds its own choices.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT TRIM(department), TRIM(COALESCE(course_name, name)) FROM courses "
            "WHERE TRIM(COALESCE(department, '')) != '' "
            "AND TRIM(COALESCE(course_name, name, '')) != '' "
            "ORDER BY 1 COLLATE NOCASE, 2 COLLATE NOCASE"
        ).fetchall()
    finally:
        conn.close()
    out: "dict[str, List[str]]" = {}
    for department, subject in rows:
        out.setdefault(department, []).append(subject)
    return out


def _specialism_matches(specialization: str, course_name: str) -> bool:
    spec, name = specialization.strip().casefold(), course_name.strip().casefold()
    return bool(spec and name) and (spec in name or name in spec)


def suitable_courses(department: Optional[str], specialization: Optional[str]) -> List[dict]:
    """Active courses an instructor could teach, best first.

    A course qualifies when it matches their specialism (in any department) or
    belongs to their department. ``specialism_match`` says which.
    """
    department = (department or "").strip()
    specialization = (specialization or "").strip()
    if not department and not specialization:
        return []
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, COALESCE(course_code, code), COALESCE(course_name, name), department "
            "FROM courses WHERE COALESCE(course_code, code) IS NOT NULL "
            "AND COALESCE(course_name, name) IS NOT NULL "
            "AND LOWER(COALESCE(status, 'active')) = 'active' "
            "ORDER BY 2 COLLATE NOCASE"
        ).fetchall()
    finally:
        conn.close()
    found = []
    for course_id, code, name, course_department in rows:
        same_department = bool(department) and (
            (course_department or "").strip().casefold() == department.casefold())
        match = _specialism_matches(specialization, name)
        if same_department or match:
            found.append({
                "id": course_id, "code": code, "name": name,
                "department": course_department,
                "specialism_match": match, "same_department": same_department,
            })
    found.sort(key=lambda c: (not c["specialism_match"], not c["same_department"]))
    return found


def send_assignment_email(instructor: dict, course: dict, semester: str, year) -> str:
    """Tell an instructor about a course assignment; returns a line for the
    success message. A failed send never undoes the assignment."""
    recipient = (instructor.get("email") or "").strip()
    if not recipient:
        return "\n\n(No email on file for this instructor — notification not sent.)"
    try:
        from education_system.systems.university.infrastructure.email import send_template_email

        sent = send_template_email(
            "academics/teaching/courses/course_assignment_notification",
            recipient,
            {
                "instructor_name": instructor.get("name") or "Instructor",
                "course_code": course.get("code") or "N/A",
                "course_name": course.get("name") or "N/A",
                "department": course.get("department") or "Not specified",
                "semester": semester,
                "year": str(year),
                "email_domain": UNIVERSITY_EMAIL_DOMAIN,
                "assigned_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
    except Exception as e:  # noqa: BLE001 - reported to the user, the assignment stands
        return f"\n\nNotification email could not be sent: {e}"
    if sent:
        return f"\n\nNotification email sent to {recipient}"
    return f"\n\nNotification email could not be sent to {recipient}."


# ---------------------------------------------------------------------------
# Editing
# ---------------------------------------------------------------------------

#: Form field -> (column, label used in the e-mail and the confirmation).
_EDITABLE_FIELDS = {
    "first_name": ("first_name", "First name"),
    "last_name": ("last_name", "Last name"),
    "department": ("department", "Department"),
    "specialization": ("specialization", "Specialisation"),
    "max_courses": ("max_courses_per_semester", "Maximum courses per semester"),
    "max_hours": ("max_hours_per_week", "Maximum hours per week"),
    "preferred_days": ("preferred_days", "Preferred days"),
    "preferred_times": ("preferred_times", "Preferred times"),
    "status": ("status", "Status"),
}


@dataclass
class InstructorUpdateResult:
    ok: bool = False
    changes: List[str] = field(default_factory=list)  # "Department: A → B"
    email: str = ""
    email_sent: Optional[bool] = None  # None: nothing changed, so nothing to send
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None


def _shown(column: str, value) -> str:
    text = str(value if value is not None else "").strip()
    if column == "preferred_days":
        text = ", ".join(parse_preferred_days(text)) or text
    elif column == "preferred_times":
        text = time_label(text)
    return text or "Not set"


def _send_update_email(name: str, email: str, changes: List[str], updated_by: str) -> bool:
    from education_system.systems.university.infrastructure.email import send_template_email

    return bool(send_template_email(
        "user_management/instructor_record_updated",
        email,
        {
            "instructor_name": name,
            "changes": "\n".join(f"- {line}" for line in changes),
            "updated_by": updated_by or "An administrator",
            "updated_at": datetime.now().strftime("%d %B %Y %H:%M"),
            "email_domain": UNIVERSITY_EMAIL_DOMAIN,
        },
    ))


def _sync_login_name(email: str, first_name: str, last_name: str) -> None:
    """Carry a name change to the staff directory and the login account."""
    username = None
    with transaction() as conn:
        row = conn.execute(
            "SELECT username FROM users WHERE email = ? AND role = 'instructor'", (email,)
        ).fetchone()
        if row:
            username = row[0]
            conn.execute(
                "UPDATE users SET first_name = ?, last_name = ?, updated_at = ? WHERE email = ? "
                "AND role = 'instructor'",
                (first_name, last_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email),
            )
    if username:
        from education_system.platform.identity.auth.core import UserAuth as SharedUserAuth

        SharedUserAuth().set_display_name(username, email, f"{first_name} {last_name}")


@log_update(module="course_management", description="Updating instructor")
def update_instructor(
    instructor_id: int,
    *,
    updated_by: str = "",
    notify: bool = True,
    sync_login: bool = True,
    **fields,
) -> InstructorUpdateResult:
    """Apply the given form fields and e-mail the instructor what changed.

    Only fields that really differ are written or mentioned, so saving an
    untouched form sends nothing. Takes any of the keys of ``_EDITABLE_FIELDS``.
    """
    r = InstructorUpdateResult()
    unknown = set(fields) - set(_EDITABLE_FIELDS)
    if unknown:
        r.error = f"Unknown instructor fields: {', '.join(sorted(unknown))}"
        return r

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT first_name, last_name, email, department, specialization, "
            "max_courses_per_semester, max_hours_per_week, preferred_days, "
            "preferred_times, status FROM instructors WHERE id = ?",
            (instructor_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        r.error = "Instructor not found."
        return r
    current = dict(zip(
        ("first_name", "last_name", "email", "department", "specialization",
         "max_courses_per_semester", "max_hours_per_week", "preferred_days",
         "preferred_times", "status"), tuple(row)))
    r.email = (current["email"] or "").strip()

    updates, changes = {}, []
    for key, value in fields.items():
        column, label = _EDITABLE_FIELDS[key]
        if key in ("max_courses", "max_hours"):
            try:
                value = int(value)
            except (TypeError, ValueError):
                r.error = f"{label} must be a number."
                return r
            if value < 1:
                r.error = f"{label} must be at least 1."
                return r
        else:
            value = str(value or "").strip()
        if key in ("first_name", "last_name") and not value:
            r.error = "First name and last name are required."
            return r
        if key == "status" and value not in INSTRUCTOR_STATUSES:
            r.error = f"Status must be one of: {', '.join(INSTRUCTOR_STATUSES)}."
            return r
        if key == "preferred_days":
            tokens = [t.strip() for t in value.replace(";", ",").split(",") if t.strip()]
            days = parse_preferred_days(value)
            if len(days) != len(tokens):  # an unknown day, a repeat, or more than four
                r.error = (f"Choose up to {MAX_PREFERRED_DAYS} different days "
                           f"from {', '.join(TEACHING_DAYS)}.")
                return r
            value = ",".join(days)
        old = current[column]
        same = (int(old) == value) if key in ("max_courses", "max_hours") and old is not None \
            else str(old if old is not None else "").strip() == str(value)
        if not same:
            updates[column] = value
            changes.append(f"{label}: {_shown(column, old)} → {_shown(column, value)}")

    if not updates:
        r.ok = True
        return r

    if "status" in updates:
        # The auto-scheduler goes by is_active and the assign lists by status,
        # so someone made Inactive or On Leave must drop out of both.
        updates["is_active"] = 1 if updates["status"] == "Active" else 0

    from education_system.systems.university.services.bus.staff_hr_bus import (
        update_instructor as write_instructor,
    )
    if not write_instructor(instructor_id, **updates):
        r.error = "The instructor record could not be saved."
        return r
    r.ok = True
    r.changes = changes

    first = updates.get("first_name", current["first_name"])
    last = updates.get("last_name", current["last_name"])
    if sync_login and ("first_name" in updates or "last_name" in updates):
        try:
            _sync_login_name(r.email, first, last)
        except Exception:  # noqa: BLE001 - the instructor record is already saved
            logger.warning("Could not carry the name change to the login", exc_info=True)
            r.warnings.append("The staff directory or login name could not be updated.")

    if notify:
        r.email_sent = False
        if not r.email:
            r.warnings.append("No email on file for this instructor.")
        else:
            try:
                r.email_sent = _send_update_email(f"{first} {last}", r.email, changes, updated_by)
            except Exception:  # noqa: BLE001 - the change stands, the user is told
                logger.warning("Instructor update e-mail failed", exc_info=True)
            if not r.email_sent:
                r.warnings.append(f"The update email could not be sent to {r.email}.")
    return r


# ---------------------------------------------------------------------------
# Deleting
# ---------------------------------------------------------------------------

_REFERENCE_LABELS = {
    "module_schedule": "timetabled module sessions",
    "instructor_modules": "module allocations",
    "instructor_schedules": "schedule entries",
    "student_timetables": "student timetable entries",
    "exams": "exams",
    "virtual_classrooms": "virtual classrooms",
}


@dataclass
class InstructorDeleteResult:
    ok: bool = False
    name: str = ""
    blockers: "dict[str, int]" = field(default_factory=dict)
    released_assignments: int = 0
    login_disabled: bool = False
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None


def _table_exists(conn, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone() is not None


def _assignment_count(conn, instructor_id: int) -> int:
    if not _table_exists(conn, "course_schedule"):
        return 0
    return conn.execute(
        "SELECT COUNT(*) FROM course_schedule WHERE instructor_id = ?", (instructor_id,)
    ).fetchone()[0]


def _delete_blockers(conn, instructor_id: int) -> "dict[str, int]":
    """Records that need this instructor, by what to call them.

    Taken from the schema's foreign keys, which are what would refuse the delete,
    so a new referencing table is covered without a change here. Course
    assignments are left out: they are released rather than blocking.
    """
    blockers: "dict[str, int]" = {}
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]
    for table in tables:
        if table == "course_schedule":
            continue
        quoted = '"' + table.replace('"', '""') + '"'
        for fk in conn.execute(f"PRAGMA foreign_key_list({quoted})").fetchall():
            if fk[2] != "instructors":
                continue
            column = '"' + fk[3].replace('"', '""') + '"'
            count = conn.execute(
                f"SELECT COUNT(*) FROM {quoted} WHERE {column} = ?",  # nosec B608 - names from the schema
                (instructor_id,),
            ).fetchone()[0]
            if count:
                label = _REFERENCE_LABELS.get(table, table.replace("_", " "))
                blockers[label] = blockers.get(label, 0) + count
    return blockers


def instructor_delete_check(instructor_id: int) -> "tuple[dict[str, int], int]":
    """(records that prevent deletion, course assignments deletion would release)."""
    conn = get_connection()
    try:
        return _delete_blockers(conn, instructor_id), _assignment_count(conn, instructor_id)
    finally:
        conn.close()


@log_delete(module="course_management", description="Deleting instructor")
def delete_instructor(instructor_id: int, *, disable_login: bool = True) -> InstructorDeleteResult:
    """Delete an instructor who has no teaching records, and close their login.

    Course assignments are released so the slot can be given to someone else.
    Anything else that references them (timetabled sessions, exams …) refuses the
    delete, because removing the person would orphan that history; they can be
    marked Inactive instead. The ``users`` row stays, since deleting it cascades
    into other tables, but its local login is switched off.
    """
    r = InstructorDeleteResult()
    username = email = None
    try:
        with transaction() as conn:
            row = conn.execute(
                "SELECT TRIM(first_name || ' ' || last_name), email FROM instructors WHERE id = ?",
                (instructor_id,),
            ).fetchone()
            if row is None:
                r.error = "Instructor not found."
                return r
            r.name, email = row[0], row[1]
            r.blockers = _delete_blockers(conn, instructor_id)
            if r.blockers:
                r.error = "This instructor still has teaching records."
                return r
            r.released_assignments = _assignment_count(conn, instructor_id)
            if r.released_assignments:
                conn.execute(
                    "UPDATE course_schedule SET instructor_id = NULL WHERE instructor_id = ?",
                    (instructor_id,),
                )
            conn.execute("DELETE FROM instructors WHERE id = ?", (instructor_id,))
            if disable_login:
                user = conn.execute(
                    "SELECT id, username FROM users WHERE email = ? AND role = 'instructor'",
                    (email,),
                ).fetchone()
                if user:
                    username = user[1]
                    conn.execute(
                        "UPDATE user_accounts SET is_active = 0 WHERE user_id = ?", (user[0],)
                    )
    except Exception as e:  # noqa: BLE001 - report failure to caller, don't crash the GUI
        r.error = f"Failed to delete instructor: {e}"
        return r

    r.ok = True
    if username:
        try:
            from education_system.platform.identity.auth.core import UserAuth as SharedUserAuth

            r.login_disabled = SharedUserAuth().revoke_system_access(
                username, email, "university", "instructor")
        except Exception:  # noqa: BLE001 - the record is gone; say the login is still open
            logger.warning("Could not close the instructor's login", exc_info=True)
        if not r.login_disabled:
            r.warnings.append(f"The shared login '{username}' could not be closed; check it by hand.")
    return r
