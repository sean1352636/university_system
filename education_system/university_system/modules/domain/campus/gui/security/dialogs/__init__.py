"""Dialog classes for the Campus Public Safety Management System."""

from .case_details import CaseDetailsDialog, WitnessDialog
from .complaint_form import ComplaintFormDialog
from .emergency_alert import EmergencyAlertDialog
from .patrol_log import PatrolLogDialog
from .report_preview import ReportPreviewDialog
from .officer import OfficerDialog
from .criminal import CriminalDialog
from .evidence import EvidenceDialog

__all__ = [
    'CaseDetailsDialog', 'WitnessDialog', 'ComplaintFormDialog',
    'EmergencyAlertDialog', 'PatrolLogDialog', 'ReportPreviewDialog',
    'OfficerDialog', 'CriminalDialog', 'EvidenceDialog',
]
