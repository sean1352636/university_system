"""Who may do what in student wellbeing casework.

Built on the Disability & Accessibility rules (``domain/disability/access``:
the signed-in ``actor``, the student number by username, never the account
id) and the health portal's (``health.application.health.access`` through
``services/bus/wellbeing_bus``: ``scope_area('counselling')`` and the
fail-closed view audit).

* **Counselling team** — counsellors (``AREA_ROLES['counselling']``), the
  health team and administrators: ``scope_area`` returns ``None`` for them.
  Only they see triage, the waiting list, sessions, outcome measures and
  clinical notes. A student sees their own referral and appointments, never
  the notes.
* **Referrers** — any signed-in member of staff may refer a student to
  counselling (and sees nothing of it afterwards); a student refers
  themselves.
* **Support staff** — wellbeing practitioners, disability services, the
  safeguarding leads, administrators and anyone with
  ``manage_support_to_study`` / ``manage_trusted_contacts``: Support to Study
  cases and trusted contacts.
* **Contact approvers** — safeguarding leads, health administrators,
  administrators and ``approve_trusted_contact_use``: they approve a use of a
  trusted contact.
* **PEEP viewers** — estates and health-and-safety staff, disability
  services, the health team, administrators and ``view_peeps`` /
  ``manage_peeps``; anyone sees their own plan.
"""

from __future__ import annotations

from education_system.systems.university.domains.student_support.domain.disability import (
    access as disability_access,
)
from education_system.systems.university.services.bus import wellbeing_bus

NON_STAFF_ROLES = ("student", "alumni", "parent", "guest", "applicant")
SUPPORT_ROLES = ("wellbeing_officer", "wellness_officer", "student_support", "support_staff",
                 "mental_health_adviser", "mental_health_advisor", "student_services")
APPROVER_ROLES = ("health_admin", "designated_safeguarding_lead", "safeguarding_lead",
                  "head_of_student_services")
PEEP_ROLES = ("estates", "estates_manager", "estates_officer", "facilities_manager",
              "health_safety_officer", "health_and_safety_officer", "fire_safety_officer",
              "fire_warden")

current_user = disability_access.current_user
has_permission = disability_access.has_permission
own_student_id = disability_access.own_student_id
who = disability_access.who


def role(actor) -> str:
    return str((current_user(actor) or {}).get("role") or "").lower()


def username(actor) -> str:
    name = (current_user(actor) or {}).get("username")
    if not name:
        raise PermissionError("Sign in first.")
    return str(name)


def _signed_in(actor) -> None:
    if not current_user(actor):
        raise PermissionError("Sign in first.")


def is_admin(actor) -> bool:
    return role(actor) in wellbeing_bus.admin_roles()


# ------------------------------------------------------------------ counselling

def counselling_scope(actor) -> str | None:
    """``None`` for the counselling team; the student's own number for a
    student; ``PermissionError`` for anyone else."""
    _signed_in(actor)
    person = who(actor)
    try:
        scoped = wellbeing_bus.counselling_scope(person)
    except PermissionError:
        # A student whose session lacks the student number still sees their own.
        own = own_student_id(actor)
        if own:
            return own
        raise PermissionError("Counselling records are for the counselling team and the "
                              "student themselves.") from None
    if scoped is None:
        return None
    return own_student_id(actor) or scoped


def is_counselling_team(actor) -> bool:
    try:
        return counselling_scope(actor) is None
    except PermissionError:
        return False


def require_counselling_team(actor) -> None:
    if not is_counselling_team(actor):
        raise PermissionError("Only the counselling team can do this.")


def is_staff(actor) -> bool:
    user = current_user(actor)
    return bool(user) and role(actor) not in NON_STAFF_ROLES


def require_referrer(actor, student_id) -> str:
    """Staff may refer anyone; a student only themselves. Returns ``'self'``
    or ``'staff'``."""
    _signed_in(actor)
    own = own_student_id(actor)
    if own:
        if str(student_id) != own:
            raise PermissionError("You can only refer yourself.")
        return "self"
    if not is_staff(actor):
        raise PermissionError("Only students and staff can make a counselling referral.")
    return "staff"


def record_view(actor, area, *, student_id=None, record_id=None, reason=None) -> None:
    """Audit a look at special-category data; refuses if it cannot be written."""
    person = who(actor)
    if person is None:
        raise PermissionError("Sign in first.")
    wellbeing_bus.record_view(person, area, student_id=student_id, record_id=record_id,
                              reason=reason)


# ------------------------------------------------------------------ support staff

def is_support_staff(actor) -> bool:
    if not current_user(actor):
        return False
    r = role(actor)
    if r in SUPPORT_ROLES or r in wellbeing_bus.wellbeing_roles() or is_admin(actor):
        return True
    if r in wellbeing_bus.clinical_roles() or r in disability_access.DISABILITY_ROLES:
        return True
    if r in {x.lower() for x in wellbeing_bus.safeguarding_lead_roles()}:
        return True
    return any(has_permission(actor, p) for p in
               ("manage_support_to_study", "manage_trusted_contacts"))


def require_support_staff(actor) -> None:
    _signed_in(actor)
    if not is_support_staff(actor):
        raise PermissionError("Only student support staff can do this.")


def support_scope(actor) -> str | None:
    """``None`` for support staff; a student's own number; else refused."""
    _signed_in(actor)
    if is_support_staff(actor):
        return None
    own = own_student_id(actor)
    if own:
        return own
    raise PermissionError("These records are for student support staff and the student "
                          "themselves.")


def require_student_access(actor, student_id) -> None:
    scoped = support_scope(actor)
    if scoped is not None and str(student_id) != scoped:
        raise PermissionError("That record belongs to another student.")


def may_approve_contact_use(actor) -> bool:
    r = role(actor)
    return (is_admin(actor) or r in APPROVER_ROLES
            or r in {x.lower() for x in wellbeing_bus.safeguarding_lead_roles()}
            or has_permission(actor, "approve_trusted_contact_use"))


# ------------------------------------------------------------------ PEEPs

def is_peep_viewer(actor) -> bool:
    if not current_user(actor):
        return False
    r = role(actor)
    return (r in PEEP_ROLES or is_admin(actor) or r in wellbeing_bus.clinical_roles()
            or r in disability_access.DISABILITY_ROLES
            or any(has_permission(actor, p) for p in ("view_peeps", "manage_peeps")))


def may_manage_peeps(actor) -> bool:
    r = role(actor)
    return (r in PEEP_ROLES or is_admin(actor) or r in disability_access.DISABILITY_ROLES
            or has_permission(actor, "manage_peeps"))


def require_peep_manager(actor) -> None:
    _signed_in(actor)
    if not may_manage_peeps(actor):
        raise PermissionError("Only disability services, estates and health & safety staff "
                              "can change evacuation plans.")
