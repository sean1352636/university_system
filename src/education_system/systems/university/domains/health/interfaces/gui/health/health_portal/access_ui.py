"""Health Portal screens' side of ``application/health/access``.

Every list or record a screen shows goes through :func:`scoped_student`
(who may see which student) and :func:`record_view` (the audit entry,
refused if it can't be written):

* a clinician (or administrator) sees whoever they filter on, or everyone;
* a student always sees only their own record — their filter field is set
  to their own student number and locked;
* anyone else is refused, and offered break-glass access for one named
  student with a written reason (logged and reported to the health
  administrators).
"""

from __future__ import annotations

import logging
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import messagebox, simpledialog

from education_system.systems.university.domains.health.application.health import access

logger = logging.getLogger(__name__)

TITLE = "Health Portal"


def current_user(auth) -> dict | None:
    if isinstance(auth, dict):
        return auth
    user = getattr(auth, "current_user", None) if auth is not None else None
    if callable(user):
        try:
            user = user()
        except Exception:
            user = None
    return user if isinstance(user, dict) else None


def who(auth) -> access.HealthUser | None:
    return access.from_user(current_user(auth))


def is_clinician(auth) -> bool:
    person = who(auth)
    return bool(person and person.is_clinician)


def is_practitioner(auth, area) -> bool:
    """A clinician, or one of ``area``'s own practitioners (counsellors,
    wellbeing officers — ``access.AREA_ROLES``)."""
    try:
        return access.scope_area(who(auth), area) is None
    except PermissionError:
        return False


def own_student_id(auth) -> str | None:
    person = who(auth)
    return str(person.student_id) if person and person.is_student and person.student_id else None


def lock_to_own(auth, var, widget=None) -> None:
    """Fill a student-number field with the student's own number and lock
    it (students only)."""
    own = own_student_id(auth)
    if own is None or var is None:
        return
    var.set(own)
    if widget is not None:
        try:
            widget.configure(state="readonly")
        except Exception:
            logger.debug("Could not lock the student field", exc_info=True)


def request_break_glass(parent, auth, student_id) -> bool:
    """Ask for the emergency reason and grant one student's record."""
    person = who(auth)
    if person is None:
        messagebox.showerror(TITLE, "Sign in to use the health portal.", parent=parent)
        return False
    if not student_id:
        messagebox.showinfo(TITLE, "Health records are for the health team and the student "
                                   "themselves. In an emergency, enter the student number in "
                                   "the filter and refresh to request break-glass access.",
                            parent=parent)
        return False
    if not messagebox.askyesno(
            TITLE, f"You are not in the health team. Open student {student_id}'s health "
                   "record with break-glass (emergency) access?\n\nYour reason is recorded and "
                   "the health administrators are told.", parent=parent):
        return False
    reason = simpledialog.askstring(TITLE, "Why do you need this record now?", parent=parent)
    if not reason:
        return False
    try:
        emails = access.break_glass(person, student_id, reason)
    except (PermissionError, ValueError) as exc:
        messagebox.showerror(TITLE, str(exc), parent=parent)
        return False
    try:
        from education_system.systems.university.infrastructure.ui.record_screens import (
            send_emails,
        )
        send_emails(emails)
    except Exception:
        logger.debug("Break-glass notice not sent", exc_info=True)
    return True


def scoped_student(parent, auth, typed="", var=None, widget=None, area=None):
    """The student filter this person may use: ``''`` = everyone (health
    team only), a student number, or ``None`` = refused (already told).
    ``area`` (``'counselling'`` / ``'wellbeing'``) also admits that area's
    practitioners (``access.scope_area``)."""
    typed = str(typed or "").strip()
    person = who(auth)
    try:
        allowed = access.scope_area(person, area) if area else access.scope(person)
    except PermissionError:
        if typed and access.may_view(person, typed):
            return typed
        if request_break_glass(parent, auth, typed):
            return typed
        return None
    if allowed is None:
        return typed
    lock_to_own(auth, var, widget)
    return allowed


def record_view(parent, auth, area, student_id=None, record_id=None) -> bool:
    """Audit the view; ``False`` (and an error shown) when it can't be."""
    person = who(auth)
    if person is None:
        messagebox.showerror(TITLE, "Sign in to use the health portal.", parent=parent)
        return False
    try:
        access.record_view(person, area, student_id=student_id or "(all)", record_id=record_id)
        return True
    except PermissionError as exc:
        messagebox.showerror(TITLE, str(exc), parent=parent)
        return False


def require_clinician(parent, auth, what="do this") -> bool:
    try:
        access.require_clinician(who(auth), what)
        return True
    except PermissionError as exc:
        messagebox.showerror(TITLE, str(exc), parent=parent)
        return False


def may_view(auth, student_id) -> bool:
    return access.may_view(who(auth), student_id)
