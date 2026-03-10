"""Primary school role management - delegates to shared auth module.

The primary school also maintains its own ROLE_PERMISSIONS for
fine-grained permission checks within the primary school system.
"""

from education_system.shared.auth.role_manager import RoleManager as _SharedRoleManager
from education_system.shared.auth.role_manager import ROLE_HIERARCHY  # noqa: F401

# Primary-school-specific granular permissions
ROLE_PERMISSIONS = {
    "admin": {
        "manage_users", "manage_staff", "manage_pupils", "manage_classes",
        "manage_subjects", "manage_timetable", "view_assessments", "manage_assessments",
        "view_attendance", "manage_attendance", "view_behaviour", "manage_behaviour",
        "view_safeguarding", "manage_safeguarding", "view_send", "manage_send",
        "view_finance", "manage_finance", "manage_admissions", "manage_settings",
        "view_reports", "manage_policies", "manage_documents", "view_audit_log",
        "manage_clubs", "manage_meals", "manage_transport", "manage_trips",
        "manage_library", "manage_medical", "manage_calendar", "manage_announcements",
        "manage_communication", "manage_parents_evening", "manage_room_bookings",
        "manage_assets", "manage_visitors", "manage_incidents", "manage_hr",
        "manage_cpd", "manage_cover", "manage_rewards", "manage_homework",
        "manage_phonics", "manage_sats", "manage_reading", "manage_progress",
        "view_pastoral", "manage_pastoral", "manage_consent", "data_export",
    },
    "teacher": {
        "manage_pupils", "manage_classes", "view_assessments", "manage_assessments",
        "view_attendance", "manage_attendance", "view_behaviour", "manage_behaviour",
        "view_safeguarding", "view_send", "view_reports", "manage_homework",
        "manage_rewards", "manage_phonics", "manage_reading", "manage_progress",
        "view_pastoral", "manage_pastoral", "manage_clubs", "view_finance",
        "manage_trips", "manage_library", "view_medical", "manage_calendar",
        "view_announcements", "manage_communication", "manage_parents_evening",
        "manage_room_bookings", "manage_cover", "manage_sats",
    },
    "teaching_assistant": {
        "view_assessments", "manage_attendance", "view_attendance",
        "view_behaviour", "manage_behaviour", "view_send", "manage_rewards",
        "manage_reading", "view_pastoral", "view_medical", "manage_library",
        "manage_phonics",
    },
    "parent": {
        "view_own_child", "view_assessments", "view_attendance", "view_behaviour",
        "view_homework", "view_calendar", "view_announcements", "view_reports",
    },
}


class RoleManager(_SharedRoleManager):
    """Primary school role manager with local permission checks."""

    def has_permission(self, role: str, permission: str) -> bool:
        """Check using the primary-school-specific permission sets."""
        perms = ROLE_PERMISSIONS.get(role, set())
        return permission in perms

    def get_permissions(self, role: str) -> set:
        """Return the set of permissions for a role."""
        return ROLE_PERMISSIONS.get(role, set()).copy()
