"""Make ``staff`` the canonical register of people who work here.

The university kept three disconnected staff registers with no overlap
at all:

* ``staff`` — the HR register the Research Portal, Staff HR API, chatbot
  and email bus read;
* ``users`` — login accounts, which most GUIs read;
* ``instructors`` — teaching profiles, which timetabling, evaluations and
  the module screens read.

None of the ten people in ``staff`` had a login, and none of them
appeared as an instructor, so the Research Portal listed ten members of
staff the rest of the system had never heard of.

This makes ``staff`` the register and the other two derived from it:

* every staff member gets a ``users`` row (and a shared-auth account) so
  they can sign in and appear on the screens that read ``users``;
* a staff member who teaches gets an ``instructors`` row linked back by
  ``instructors.staff_id``.

``instructors.id`` is left alone: eight tables hold foreign keys to it
(``module_schedule``, ``exams``, ``virtual_classrooms``,
``lecturer_evaluations`` and four more), so the teaching profile keeps
its own identity and gains a link rather than being merged away.
"""

from __future__ import annotations

import logging
import secrets
import string
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "TEACHING_ROLES", "ensure_link_column", "unlinked_staff",
    "staff_without_login", "staff_without_instructor",
    "provision_staff_login", "provision_instructor_profile",
    "reconcile", "split_name",
]

#: staff.role values that imply the person teaches, so they should also
#: exist as an instructor and appear in the module/evaluation screens.
TEACHING_ROLES = ("staff", "lecturer", "instructor", "teacher", "professor",
                  "tutor", "reader", "academic")


def _connect(db_path: Optional[str] = None):
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )
    return get_connection(db_path) if db_path else get_connection()


def split_name(full_name: str) -> tuple:
    """'Priya Sundaram' -> ('Priya', 'Sundaram').

    The HR register stores one ``name`` field; ``users`` and
    ``instructors`` both want the halves separately.
    """
    parts = [p for p in str(full_name or "").strip().split() if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def ensure_link_column(db_path: Optional[str] = None) -> None:
    """Add ``instructors.staff_id`` if it isn't there yet."""
    try:
        with _connect(db_path) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(instructors)")}
            if "staff_id" not in cols:
                conn.execute("ALTER TABLE instructors ADD COLUMN staff_id INTEGER")
                conn.commit()
                logger.info("Added instructors.staff_id")
    except Exception:
        logger.exception("Could not add instructors.staff_id")


# --------------------------------------------------------------------------
# What is out of step
# --------------------------------------------------------------------------

def staff_without_login(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Active staff with no ``users`` row — they cannot sign in."""
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                "SELECT s.id, s.username, s.name, s.email, s.role "
                "FROM staff s "
                "LEFT JOIN users u ON u.username = s.username "
                "WHERE u.id IS NULL "
                "  AND COALESCE(s.status,'active') != 'inactive' "
                "  AND TRIM(COALESCE(s.username,'')) != '' "
                "ORDER BY s.name").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("Could not list staff without a login")
        return []


def staff_without_instructor(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Teaching staff with no ``instructors`` row.

    Matched on the link column first, then on email — the two registers
    were populated independently, so an existing instructor may already
    be the same person without being linked.
    """
    placeholders = ",".join("?" * len(TEACHING_ROLES))
    try:
        with _connect(db_path) as conn:
            # Before the migration adds staff_id there is nothing to join
            # on but email. Without this the query errored and the dry run
            # reported "0 to do", which is exactly the wrong answer.
            has_link = "staff_id" in {
                r[1] for r in conn.execute("PRAGMA table_info(instructors)")}
            link = ("i.staff_id = s.id OR " if has_link else "") + (
                "(TRIM(COALESCE(s.email,'')) != '' "
                " AND LOWER(i.email) = LOWER(s.email))")
            rows = conn.execute(
                "SELECT s.id, s.username, s.name, s.email, s.role "
                "FROM staff s "
                f"LEFT JOIN instructors i ON {link} "
                "WHERE i.id IS NULL "
                "  AND COALESCE(s.status,'active') != 'inactive' "
                f"  AND LOWER(COALESCE(s.role,'staff')) IN ({placeholders}) "
                "ORDER BY s.name", TEACHING_ROLES).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("Could not list staff without an instructor profile")
        return []


def unlinked_staff(db_path: Optional[str] = None) -> Dict[str, Any]:
    """A summary of what reconciliation would do."""
    no_login = staff_without_login(db_path)
    no_instructor = staff_without_instructor(db_path)
    try:
        with _connect(db_path) as conn:
            totals = {
                "staff": conn.execute(
                    "SELECT COUNT(*) FROM staff "
                    "WHERE COALESCE(status,'active') != 'inactive'").fetchone()[0],
                "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                "instructors": conn.execute(
                    "SELECT COUNT(*) FROM instructors").fetchone()[0],
            }
    except Exception:
        totals = {}
    return {"totals": totals, "without_login": no_login,
            "without_instructor": no_instructor}


# --------------------------------------------------------------------------
# Provisioning
# --------------------------------------------------------------------------

def _temporary_password() -> str:
    """A random first password; the account is flagged to change it."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(14)) + "!aA1"


def provision_staff_login(member: Dict[str, Any], auth=None) -> Dict[str, Any]:
    """Give one staff member a login in both auth stores.

    Mirrors ``student_provisioning.provision_staff_login``: the legacy
    ``users`` row is what the GUIs read, the shared-auth account is what
    actually lets them sign in. Idempotent and never raises.
    """
    username = (member.get("username") or "").strip()
    if not username:
        return {"username": "", "legacy_ok": False, "shared_ok": False,
                "reason": "no username on the staff record"}

    first, last = split_name(member.get("name"))
    email = (member.get("email") or "").strip()
    role = (member.get("role") or "staff").strip().lower()
    if role not in ("staff", "admin"):
        role = "staff"
    password = _temporary_password()

    legacy_ok = False
    if auth is None:
        try:
            from education_system.systems.university.infrastructure.auth import UserAuth
            auth = UserAuth()
        except Exception:
            logger.warning("No auth manager available for %s", username)
    if auth is not None:
        try:
            auth.create_user(username=username, password=password, email=email,
                             first_name=first, last_name=last, role=role,
                             password_reset_required=True)
            legacy_ok = True
        except Exception as exc:
            # An existing row is success for our purposes.
            legacy_ok = "exist" in str(exc).lower()
            if not legacy_ok:
                logger.warning("Legacy user creation failed for %s: %s", username, exc)

    shared_ok = False
    try:
        from education_system.platform.identity.auth.core import UserAuth as _Shared
        from education_system.platform.identity.auth.exceptions import AuthError
        shared = _Shared()
        try:
            shared.create_user(username=username, password=password,
                               display_name=f"{first} {last}".strip(),
                               email=email, systems=[("university", role)])
            shared_ok = True
        except AuthError as exc:
            shared_ok = "already exists" in str(exc).lower()
            if not shared_ok:
                raise
    except Exception as exc:
        logger.warning("Shared-auth creation failed for %s: %s", username, exc)

    return {"username": username, "legacy_ok": legacy_ok,
            "shared_ok": shared_ok, "reason": None}


def provision_instructor_profile(member: Dict[str, Any],
                                 db_path: Optional[str] = None) -> Optional[int]:
    """Give one teaching staff member an ``instructors`` row.

    Returns the instructor id. If a matching instructor already exists
    (same email), it is linked rather than duplicated — the two
    registers were populated independently.
    """
    first, last = split_name(member.get("name"))
    email = (member.get("email") or "").strip()
    staff_id = member.get("id")
    try:
        with _connect(db_path) as conn:
            existing = None
            if email:
                existing = conn.execute(
                    "SELECT id FROM instructors WHERE LOWER(email) = LOWER(?)",
                    (email,)).fetchone()
            if existing:
                conn.execute("UPDATE instructors SET staff_id = ? WHERE id = ?",
                             (staff_id, existing[0]))
                conn.commit()
                return existing[0]

            # Department lives on staff_profiles, keyed on username rather
            # than staff.id. Carrying it over means the new instructor
            # shows a department in the pickers instead of a bare name.
            department = ""
            try:
                row = conn.execute(
                    "SELECT COALESCE(department,'') FROM staff_profiles "
                    "WHERE user_id = ?", (member.get("username"),)).fetchone()
                if row:
                    department = row[0] or ""
            except Exception:
                logger.debug("no staff_profiles department for %s",
                             member.get("username"), exc_info=True)

            cursor = conn.execute(
                "INSERT INTO instructors "
                "(first_name, last_name, email, department, staff_id, "
                " is_active, status) "
                "VALUES (?, ?, ?, ?, ?, 1, 'Active')",
                (first, last, email, department, staff_id))
            conn.commit()
            return cursor.lastrowid
    except Exception:
        logger.exception("Could not create an instructor profile for %s",
                         member.get("username"))
        return None


def reconcile(*, apply: bool = False, db_path: Optional[str] = None,
              auth=None) -> Dict[str, Any]:
    """Bring ``users`` and ``instructors`` into line with ``staff``.

    Reports what it would do unless *apply* is true. Idempotent: running
    it twice provisions nothing the second time.
    """
    if apply:
        ensure_link_column(db_path)

    summary = unlinked_staff(db_path)
    result = {"totals": summary["totals"], "applied": apply,
              "logins": [], "instructors": []}

    for member in summary["without_login"]:
        if not apply:
            result["logins"].append({"username": member["username"],
                                     "name": member["name"], "planned": True})
            continue
        result["logins"].append(dict(provision_staff_login(member, auth=auth),
                                     name=member["name"]))

    for member in summary["without_instructor"]:
        if not apply:
            result["instructors"].append({"username": member["username"],
                                          "name": member["name"], "planned": True})
            continue
        instructor_id = provision_instructor_profile(member, db_path)
        result["instructors"].append({"username": member["username"],
                                      "name": member["name"],
                                      "instructor_id": instructor_id})
    return result
