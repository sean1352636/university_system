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

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from education_system.post_18.university_system.infrastructure.database.db import (
    get_connection,
    transaction,
)

from education_system.post_18.university_system.modules.domain.academics.services.course_management.instructors import (
    _generate_university_email,
    _generate_temp_password,
    _create_instructor_account,
    _register_instructor_as_staff,
    _send_instructor_welcome_email,
)
from education_system.post_18.university_system.modules.domain.academics.services.course_management.validation import (
    validate_email,
)

try:
    from education_system.post_18.university_system.core.defaults import UNIVERSITY_EMAIL_DOMAIN
except ImportError:  # pragma: no cover - defensive fallback
    UNIVERSITY_EMAIL_DOMAIN = "university.edu"


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
