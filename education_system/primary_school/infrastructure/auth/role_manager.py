"""Primary school role and permission management.

Extends the shared :class:`~education_system.shared.auth.role_manager.RoleManager`
with granular, permission-based access control specific to the primary
school domain.

Permissions are composed via ``ROLE_HIERARCHY`` — higher roles
automatically inherit every permission granted to roles below them, so
adding a new permission to ``teaching_assistant`` is automatically
available to ``teacher`` and ``admin``.

.. note::

   ``student`` is intentionally omitted.  Pupils in a primary school
   (ages 4-11) do not log in directly; their data is managed by staff
   and viewed by parents.  ``headteacher`` / ``deputy`` are covered by
   the ``admin`` role for now.
"""

from __future__ import annotations

import types
from typing import Any

from education_system.shared.auth.role_manager import (
    ROLE_HIERARCHY,
    RoleManager as _SharedRoleManager,
)

# ── Per-role permissions ─────────────────────────────────────────────────
# Only list permissions *introduced* at each level.  Higher roles inherit
# everything below them via ROLE_HIERARCHY (see _build_permissions).

_BASE_PERMISSIONS: dict[str, frozenset[str]] = {
    "parent": frozenset({
        "view_own_child", "view_assessments", "view_attendance", "view_behaviour",
        "view_homework", "view_calendar", "view_announcements", "view_reports",
        "view_parents_evening", "view_communication",
    }),
    "teaching_assistant": frozenset({
        "view_pupils",
        "manage_attendance", "view_attendance",
        "view_behaviour", "manage_behaviour",
        "view_send", "manage_rewards",
        "manage_reading", "view_pastoral", "view_medical", "manage_library",
        "manage_phonics", "view_assessments",
    }),
    "teacher": frozenset({
        "manage_pupils", "manage_classes", "manage_assessments",
        "manage_attendance", "manage_behaviour",
        "view_safeguarding", "view_reports", "manage_homework",
        "manage_progress", "manage_pastoral", "manage_clubs", "view_finance",
        "manage_trips", "manage_library", "view_medical", "manage_calendar",
        "view_announcements", "manage_communication", "manage_parents_evening",
        "manage_room_bookings", "manage_cover", "manage_sats",
        "manage_reading", "manage_phonics", "manage_rewards",
    }),
    "admin": frozenset({
        "manage_users", "manage_staff", "manage_subjects", "manage_timetable",
        "view_safeguarding", "manage_safeguarding", "manage_send",
        "view_finance", "manage_finance", "manage_admissions", "manage_settings",
        "manage_policies", "manage_documents", "view_audit_log",
        "manage_meals", "manage_transport",
        "manage_announcements", "manage_room_bookings",
        "manage_assets", "manage_visitors", "manage_incidents", "manage_hr",
        "manage_cpd", "manage_consent", "data_export",
    }),
}

# Roles ordered from lowest to highest privilege for inheritance.
_INHERITANCE_ORDER: list[str] = ["parent", "teaching_assistant", "teacher", "admin"]


def _build_permissions() -> types.MappingProxyType[str, frozenset[str]]:
    """Compose final permission sets by walking the hierarchy bottom-up.

    Each role inherits every permission from roles with a lower
    ``ROLE_HIERARCHY`` level.  The result is an immutable mapping.
    """
    resolved: dict[str, frozenset[str]] = {}
    accumulated: frozenset[str] = frozenset()

    for role in _INHERITANCE_ORDER:
        own = _BASE_PERMISSIONS.get(role, frozenset())
        # parent is a lateral role — it doesn't inherit from TA/teacher
        if role == "parent":
            resolved[role] = own
        else:
            accumulated = accumulated | own
            resolved[role] = accumulated

    return types.MappingProxyType(resolved)


ROLE_PERMISSIONS: types.MappingProxyType[str, frozenset[str]] = _build_permissions()


# ── Module-to-permission mapping ─────────────────────────────────────────
# Maps UI module/feature names (used by CLI and GUI) to the permission(s)
# that grant access.  A role can see a module if it holds ANY of the
# listed permissions.  Modules not in this mapping (e.g. "Dashboard",
# "MFA Settings", "Security Questions") are visible to all authenticated
# users.

MODULE_PERMISSIONS: types.MappingProxyType[str, frozenset[str]] = types.MappingProxyType({
    # Academics
    "Pupils":           frozenset({"manage_pupils", "view_pupils"}),
    "Subjects":         frozenset({"manage_subjects"}),
    "Classes":          frozenset({"manage_classes"}),
    "Assessment":       frozenset({"view_assessments", "manage_assessments"}),
    "Attendance":       frozenset({"view_attendance", "manage_attendance"}),
    "Timetable":        frozenset({"manage_timetable"}),
    "Homework":         frozenset({"manage_homework", "view_homework"}),
    "SATs":             frozenset({"manage_sats"}),
    "Phonics":          frozenset({"manage_phonics"}),
    "Reading Records":  frozenset({"manage_reading"}),
    "Progress":         frozenset({"manage_progress"}),
    "Portfolio":        frozenset({"manage_progress"}),
    "Skills Tracker":   frozenset({"manage_progress"}),
    "LMS":              frozenset({"manage_classes"}),
    # Pastoral care
    "Behaviour":        frozenset({"view_behaviour", "manage_behaviour"}),
    "Rewards":          frozenset({"manage_rewards"}),
    "Safeguarding":     frozenset({"view_safeguarding", "manage_safeguarding"}),
    "SEND":             frozenset({"view_send", "manage_send"}),
    "Pastoral":         frozenset({"view_pastoral", "manage_pastoral"}),
    "Pupil Wellbeing":  frozenset({"view_pastoral", "manage_pastoral"}),
    # Staff
    "Staff Directory":  frozenset({"manage_staff", "manage_hr"}),
    "HR":               frozenset({"manage_hr"}),
    "CPD":              frozenset({"manage_cpd"}),
    "Cover":            frozenset({"manage_cover"}),
    "Appraisals":       frozenset({"manage_hr"}),
    "Observations":     frozenset({"manage_hr"}),
    "Staff Wellbeing":  frozenset({"manage_hr"}),
    "Lesson Plans":     frozenset({"manage_classes"}),
    # Pupil life
    "Class Groups":     frozenset({"manage_classes", "manage_pupils"}),
    "Clubs":            frozenset({"manage_clubs"}),
    "Meals":            frozenset({"manage_meals"}),
    "Library":          frozenset({"manage_library"}),
    "Medical":          frozenset({"view_medical"}),
    "Transport":        frozenset({"manage_transport"}),
    "Trips":            frozenset({"manage_trips"}),
    "Consent":          frozenset({"manage_consent"}),
    # Communication
    "Email":            frozenset({"manage_communication"}),
    "Notifications":    frozenset({"manage_communication", "view_announcements"}),
    "Announcements":    frozenset({"view_announcements", "manage_announcements"}),
    "Calendar":         frozenset({"view_calendar", "manage_calendar"}),
    "Parents Evening":  frozenset({"manage_parents_evening", "view_parents_evening"}),
    "Communication Log": frozenset({"manage_communication", "view_communication"}),
    "Feedback":         frozenset({"manage_communication"}),
    # Administration
    "Users":            frozenset({"manage_users"}),
    "Settings":         frozenset({"manage_settings"}),
    "Admissions":       frozenset({"manage_admissions"}),
    "Finance":          frozenset({"view_finance", "manage_finance"}),
    "Payroll":          frozenset({"manage_finance"}),
    "Audit Log":        frozenset({"view_audit_log"}),
    "Data Export":      frozenset({"data_export"}),
    "Policies":         frozenset({"manage_policies"}),
    "Documents":        frozenset({"manage_documents"}),
    "Complaints":       frozenset({"manage_users"}),
    "GDPR":             frozenset({"data_export"}),
    "Data Dashboard":   frozenset({"view_reports"}),
    "Academic Misconduct": frozenset({"manage_behaviour"}),
    # Facilities
    "Room Bookings":    frozenset({"manage_room_bookings"}),
    "Assets":           frozenset({"manage_assets"}),
    "Visitors":         frozenset({"manage_visitors"}),
    "Incidents":        frozenset({"manage_incidents"}),
    # Cross-system (admin-level tools)
    "Central Admin Portal": frozenset({"manage_users"}),
    "GDPR Compliance":  frozenset({"data_export"}),
})

# CLI sections → the permissions that make a section visible.
# A role sees the section if it holds ANY of these permissions.
_SECTION_PERMISSIONS: dict[str, frozenset[str]] = {
    "Academics": frozenset({
        "manage_pupils", "manage_classes", "manage_subjects",
        "view_assessments", "manage_assessments",
        "view_attendance", "manage_attendance", "manage_timetable",
        "manage_homework", "manage_sats", "manage_phonics",
        "manage_reading", "manage_progress",
    }),
    "Pastoral Care": frozenset({
        "view_behaviour", "manage_behaviour", "manage_rewards",
        "view_safeguarding", "manage_safeguarding",
        "view_send", "manage_send", "view_pastoral", "manage_pastoral",
    }),
    "Staff": frozenset({
        "manage_staff", "manage_hr", "manage_cpd", "manage_cover",
    }),
    "Administration": frozenset({
        "manage_users", "manage_settings", "manage_admissions",
        "manage_finance", "view_audit_log",
        "manage_policies", "manage_documents", "data_export",
    }),
    "Pupil Life": frozenset({
        "manage_clubs", "manage_meals", "manage_transport", "manage_trips",
        "manage_library", "view_medical", "manage_consent",
    }),
    "Communication": frozenset({
        "view_announcements", "manage_announcements", "view_calendar",
        "manage_calendar", "manage_communication", "manage_parents_evening",
    }),
    "Facilities": frozenset({
        "manage_room_bookings", "manage_assets", "manage_visitors",
        "manage_incidents",
    }),
    "Cross-System Tools": frozenset({
        "manage_users", "data_export",
    }),
}


class RoleManager(_SharedRoleManager):
    """Primary school role manager with granular permission checks.

    Permissions are resolved at import time via hierarchy inheritance,
    so ``has_permission("admin", p)`` is ``True`` for any permission
    granted to ``teacher`` or ``teaching_assistant``.
    """

    def has_permission(self, role: str, permission: str) -> bool:
        """Check whether *role* holds *permission*."""
        return permission in ROLE_PERMISSIONS.get(role, frozenset())

    def get_permissions(self, role: str) -> set[str]:
        """Return a **mutable copy** of the permission set for *role*.

        Returns an empty set for unknown roles.
        """
        return set(ROLE_PERMISSIONS.get(role, frozenset()))

    def get_all_roles(self) -> list[str]:
        """Return all known roles ordered by hierarchy level (ascending)."""
        return sorted(ROLE_PERMISSIONS, key=lambda r: ROLE_HIERARCHY.get(r, 0))

    def can_access_module(self, role: str, module_name: str) -> bool:
        """Check whether *role* can access the named UI module.

        Modules not listed in ``MODULE_PERMISSIONS`` (e.g. "Dashboard",
        "MFA Settings") are accessible to all authenticated users.
        """
        required = MODULE_PERMISSIONS.get(module_name)
        if required is None:
            return True  # no restriction
        role_perms = ROLE_PERMISSIONS.get(role, frozenset())
        return bool(role_perms & required)

    def accessible_sections(self, role: str) -> list[str]:
        """Return the CLI section names accessible to *role*, in order."""
        role_perms = ROLE_PERMISSIONS.get(role, frozenset())
        return [
            section for section, required in _SECTION_PERMISSIONS.items()
            if role_perms & required
        ]


__all__ = [
    "ROLE_HIERARCHY",
    "ROLE_PERMISSIONS",
    "MODULE_PERMISSIONS",
    "RoleManager",
]
