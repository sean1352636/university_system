"""Who may open what in the Primary School System (GUI and CLI).

The matrix is in ``docs/primary/security/SECURITY.md``. The staff menu screens
are whole-school and read-write, so none of them is safe to give a student or
parent, even where the matrix allows that kind of record. Students and parents
get their own account settings and the own-record screens in :data:`OWN_MENUS`,
all of which read through ``domain/learners/own_records``.

Teachers keep everything except user management, settings, finance, audit logs
and data export. They can raise a safeguarding concern but read concerns only
if their staff record is flagged as a safeguarding lead.
"""

from __future__ import annotations

from education_system.platform.identity.menu_access import MenuPolicy, Principal

__all__ = ["POLICY", "Principal", "from_auth", "set_current", "current_for", "current",
           "YEAR6_TRANSITION", "can_approve_year6_handover",
           "can_manage_year6_safeguarding_files"]

SYSTEM_KEY = "primary"

FINANCE_LABELS = frozenset({
    "Dinner Money", "Trips & Payments", "Receipts", "Expense Claims",
    "Funding", "School Census",
})

ADMIN_ONLY = FINANCE_LABELS | {
    "User Accounts", "User Management", "Central Admin Portal", "Settings",
    "Audit Reports", "Data Export", "Custom Export",
    # Referrals carry exclusion, SEN and medical details and can take a
    # pupil off roll: the head's decision.
    "Referrals to Alternative Provision",
    # Requests to the SEND service: SEN, medical and support details (the
    # head / SENCO).
    "SEND Service Requests",
    # Notifications to the local authority: exclusions, children missing
    # education, attendance, SEN (the head / admissions).
    "Local Authority",
}


def _superadmin(user_info) -> bool:
    from education_system.launcher.roles import is_superadmin
    return is_superadmin(user_info)


def _is_dsl(username: str, email: str | None) -> bool:
    """Staff records have no login column, so match on staff id, then e-mail."""
    from education_system.systems.primary.domain.staff import staff

    wanted = {username.casefold()}
    if email:
        wanted.add(email.casefold())
    return any(
        s.staff_id.casefold() in wanted or (s.email or "").casefold() in wanted
        for s in staff.list_staff(is_dsl=True))


OWN_MENUS = {
    "student": [("My School", [
        ("My Timetable", "open_own_timetable"),
        ("My Homework", "open_own_homework"),
        ("My Reading Log", "open_own_reading_log"),
    ])],
    "parent": [("My Child", [
        ("Child Attendance", "open_child_attendance"),
        ("Child Assessment", "open_child_assessment"),
        ("Child Reports", "open_child_reports"),
        ("Consent Forms", "open_child_consent"),
        ("Parents' Evening Booking", "open_child_evening"),
    ])],
}

POLICY = MenuPolicy(
    SYSTEM_KEY,
    superadmin_check=_superadmin,
    admin_only=ADMIN_ONLY,
    dsl_only={"Prevent Duty"},
    raise_only={"Safeguarding"},
    dsl_check=_is_dsl,
    own_menus=OWN_MENUS,
    messages={
        "student": (
            "Your timetable, homework and reading log are under My School in "
            "the menu. Pupil accounts cannot open the staff screens. For "
            "anything else, please ask your class teacher or the school office."),
        "parent": (
            "Your child's attendance, assessment and reports, consent forms "
            "and parents' evening booking are under My Child in the menu. "
            "Parent accounts cannot open the staff screens. For anything else, "
            "please contact the school office."),
        "": ("Your account does not have a role that can use the Primary "
             "School System. Please contact the school office."),
    },
)

# ── Year 6 Transition ───────────────────────────────────────────────
# The screen itself is a staff screen (not admin_only): class teachers
# write the transition reports and record visits. Two parts are narrower,
# checked inside the screen rather than as menu labels:
#
# * approving the handover releases data to the secondary school, so it
#   is for an administrator (the head / office) or a designated lead;
# * the safeguarding-file transfer record is for a designated
#   safeguarding lead only (or a superadmin). An administrator who is the
#   DSL qualifies through their staff record's DSL flag.

YEAR6_TRANSITION = "Year 6 Transition"


def _designated_lead(principal: Principal) -> bool:
    if principal.is_superadmin or principal.is_dsl:
        return True
    if principal.role == "admin" and principal.username:
        try:
            return _is_dsl(principal.username, None)
        except Exception:  # noqa: BLE001 - fail closed
            return False
    return False


def can_manage_year6_safeguarding_files(principal: Principal) -> bool:
    """The Safeguarding Files tab: designated safeguarding leads only."""
    return principal.can_open(YEAR6_TRANSITION) and _designated_lead(principal)


def can_approve_year6_handover(principal: Principal) -> bool:
    """Releasing the handover to the secondary: admin (head) or a DSL."""
    return principal.can_open(YEAR6_TRANSITION) and (
        principal.is_admin or _designated_lead(principal))


def current() -> Principal:
    """The session's principal (the CLI's screens have no auth to hand)."""
    return POLICY._current


from_auth = POLICY.from_auth
set_current = POLICY.set_current
current_for = POLICY.current_for
