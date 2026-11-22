"""Window size, operation labels and small helpers shared by the bulk operations views.

Split out of ``bulk_operations_views.py``, which re-exports every name here.
"""

from __future__ import annotations

from datetime import date as _date
import logging

# Same logger name as before the split, so log routing is unchanged.
logger = logging.getLogger("education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.bulk_operations_views")


WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


# Friendly labels per operation.
OPERATION_LABELS: dict[str, str] = {
    "log_behaviour":         "Log behaviour entry",
    "add_accommodation":     "Add accommodation",
    "update_student":        "Update student field",
    "message":               "Send message",
    "archive_to_alumni":     "Archive → alumni",
    "mark_attendance":       "Mark attendance",
    "authorise_absences":    "Authorise absences",
    "apply_lateness":        "Apply lateness",
    "import_attendance_csv": "Import attendance CSV",
    "recalc_attendance":     "Recalculate attendance %",
    "flag_low_attendance":   "Flag low attendance",
    "signoff_register":      "Register sign-off",
    "enrol":                     "Enrol students",
    "move_class_group":          "Move class group",
    "assign_predicted_grades":   "Assign predicted grades",
    "import_assessment_marks":   "Import assessment marks",
    "recalc_grade_reports":      "Recalculate grade reports",
    "export_progress_reports":   "Export progress reports",
    "publish_report_cards":      "Publish report cards",
    "apply_grade_boundaries":    "Apply grade boundaries",
    "issue_detentions":          "Issue detentions",
    "award_merits":              "Award merits",
    "escalate_behaviour":        "Escalate behaviour",
    "safeguarding_flag":         "Safeguarding flag",
    "assign_mentors":            "Assign mentors",
    "reset_behaviour_points":    "Reset behaviour points",
    "send_sms":                  "Send SMS",
    "send_letters":              "Send templated letters",
    "meeting_invites":           "Parents-evening invites",
    "ucas_reference_reminders":  "UCAS reference reminders",
    "password_reset_emails":     "Password / MFA emails",
    "schedule_message":          "Schedule message",
    "bursary_award":             "Bursary award",
    "raise_invoices":            "Raise invoices",
    "fee_discount":              "Fee discount / waiver",
    "import_payments":           "Import payments CSV",
    "financial_statements":      "Financial statements",
    "exam_entries":              "Exam entries",
    "exam_access_arrangements":  "Exam access arrangements",
    "exam_timetables":           "Export exam timetables",
    "ucas_export_predictions":   "UCAS export predictions",
    "ucas_update_status":        "UCAS update status",
    "promote_year_group":        "Promote year group",
    "mark_leavers":              "Mark leavers",
    "reinstate_alumni":          "Reinstate alumni",
    "gdpr_redact":               "GDPR redact",
    "export_student_records":    "Export student records",
    "anonymise_alumni":          "Anonymise alumni",
    "assign_inventory":          "Assign inventory",
    "upload_photos":             "Upload photos",
    "import_contacts_csv":       "Import contacts CSV",
    "force_password_reset":      "Force password reset",
    "undo_job":                  "Undo job",
    "schedule_recurring":        "Schedule recurring job",
    # Items 1–10
    "mark_holiday":              "Mark holiday (authorised)",
    "clear_attendance":          "Clear attendance",
    "late_to_unauth":            "Late → unauthorised",
    "attendance_letters":        "Attendance letters",
    "punctuality_report":        "Punctuality report",
    "register_closure":          "Register closure (lock)",
    "assign_subjects":           "Assign subjects",
    "withdraw_subjects":         "Withdraw subjects",
    "set_teaching_set":          "Set teaching set",
    "import_timetable_csv":      "Import timetable CSV",
}

# Ops that don't operate on a list of selected students.
_NO_STUDENTS_OPS: frozenset[str] = frozenset({
    "import_attendance_csv", "signoff_register",
    "import_assessment_marks", "apply_grade_boundaries",
    "import_payments",
    "reinstate_alumni", "anonymise_alumni",
    "upload_photos", "import_contacts_csv",
    "undo_job", "schedule_recurring",
    "register_closure", "import_timetable_csv",
})


def _today() -> str:
    return _date.today().isoformat()
