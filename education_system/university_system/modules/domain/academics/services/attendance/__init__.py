"""
Advanced Attendance System Service Module

Re-exports the public surface of the comprehensive attendance_tracker
module (QRAttendanceSystem, GeofencingSystem, FaceRecognitionSystem,
…). Loading that module is expensive (it transitively pulls in every
attendance CLI submodule), so the re-exports use PEP 562 lazy
``__getattr__`` — the heavy import only fires when one of the names is
actually looked up.

This means importing a *neighbour* sub-package (e.g. ``absence_tracking``)
no longer pays the multi-second startup penalty for code paths that
don't use the CLI/dashboard surface.
"""

from __future__ import annotations

# Public names. Kept in sync with the legacy eager import block — anything
# listed here will be loaded from `attendance_tracker` on first attribute
# access.
_LAZY_NAMES = {
    "QRAttendanceSystem",
    "GeofencingSystem",
    "FaceRecognitionSystem",
    "AttendancePredictiveAnalytics",
    "EnhancedNotificationSystem",
    "AttendanceDashboard",
    "AttendanceAPI",
    "BackupRecoverySystem",
    # `display_attendance_menu` is re-exported under the legacy alias
    # `display_advanced_attendance_menu` — handled specially below.
    "launch_advanced_attendance_gui",
    "init_enhanced_attendance_db",
    "create_missing_tables",
    "get_modules",
    "get_student_attendance",
    "get_module_attendance",
    "record_attendance",
}

_ALIASES = {
    # public name -> name in attendance_tracker
    "display_advanced_attendance_menu": "display_attendance_menu",
}


def _load_attendance_tracker():
    from education_system.university_system.modules.domain.academics.services.attendance import (  # noqa: E501
        attendance_tracker as _at,
    )
    return _at


def __getattr__(name: str):
    """PEP 562 lazy attribute access — defers the expensive
    ``attendance_tracker`` import to the first real lookup."""
    if name in _LAZY_NAMES:
        value = getattr(_load_attendance_tracker(), name)
    elif name in _ALIASES:
        value = getattr(_load_attendance_tracker(), _ALIASES[name])
    else:
        raise AttributeError(
            f"module 'education_system.university_system.modules.domain."
            f"academics.services.attendance' has no attribute {name!r}")
    # Cache on the module so subsequent lookups skip __getattr__.
    globals()[name] = value
    return value


def __dir__():
    return sorted(__all__)


__all__ = sorted(_LAZY_NAMES | set(_ALIASES))
