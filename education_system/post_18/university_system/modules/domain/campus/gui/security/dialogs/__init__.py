"""Dialog classes for the Campus Public Safety Management System."""

from education_system.post_18.university_system.modules.domain.campus.gui.security.dialogs.case_details import CaseDetailsDialog, WitnessDialog
from education_system.post_18.university_system.modules.domain.campus.gui.security.dialogs.complaint_form import ComplaintFormDialog
from education_system.post_18.university_system.modules.domain.campus.gui.security.dialogs.emergency_alert import EmergencyAlertDialog
from education_system.post_18.university_system.modules.domain.campus.gui.security.dialogs.patrol_log import PatrolLogDialog
from education_system.post_18.university_system.modules.domain.campus.gui.security.dialogs.report_preview import ReportPreviewDialog
from education_system.post_18.university_system.modules.domain.campus.gui.security.dialogs.officer import OfficerDialog
from education_system.post_18.university_system.modules.domain.campus.gui.security.dialogs.criminal import CriminalDialog
from education_system.post_18.university_system.modules.domain.campus.gui.security.dialogs.evidence import EvidenceDialog

__all__ = [
    'CaseDetailsDialog', 'WitnessDialog', 'ComplaintFormDialog',
    'EmergencyAlertDialog', 'PatrolLogDialog', 'ReportPreviewDialog',
    'OfficerDialog', 'CriminalDialog', 'EvidenceDialog',
]
