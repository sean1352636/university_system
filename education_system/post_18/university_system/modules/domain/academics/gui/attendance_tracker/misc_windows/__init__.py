"""Attendance-tracker misc windows subpackage — canonical aggregator.

Re-exports the 10 window classes (geofencing, LMS integration, calendar sync,
gamification, custom report, import data, export data, report, attendance
policies, help), 3 short-form aliases preserved from the original module,
and 2 feature flags. This is the public API for the subpackage, not a
deprecated shim.
"""

from .geofencing          import GeofencingWindow
from .lms_integration     import LMSIntegrationWindow
from .calendar_sync       import CalendarSyncWindow
from .gamification        import GamificationWindow
from .custom_report       import CustomReportWindow
from .import_data         import ImportDataWindow
from .export_data         import ExportDataWindow
from .report              import ReportWindow
from .attendance_policies import AttendancePoliciesWindow
from .help                import HelpWindow

# Backwards-compat aliases (preserved from the original module tail).
ReportPreviewWindow = ReportWindow
CustomReportDialog = CustomReportWindow
ImportPreviewWindow = ImportDataWindow

# Feature flags (preserved from the original module-level constants).
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True

__all__ = [
    "GeofencingWindow", "LMSIntegrationWindow", "CalendarSyncWindow",
    "GamificationWindow", "CustomReportWindow", "ImportDataWindow",
    "ExportDataWindow", "ReportWindow", "AttendancePoliciesWindow",
    "HelpWindow",
    "ReportPreviewWindow", "CustomReportDialog", "ImportPreviewWindow",
    "GEOFENCING_SUPPORT", "FACE_RECOGNITION_SUPPORT",
]
