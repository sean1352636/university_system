"""CLI flows for Sixth Form Bulk Operations."""

from __future__ import annotations

import json
import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.learners.bulk_operations import (
    base as bulk_base,
    ops_academic as bulk_ops_academic,
    ops_attendance as bulk_ops_attendance,
    ops_behaviour as bulk_ops_behaviour,
    ops_comms as bulk_ops_comms,
    ops_finance as bulk_ops_finance,
    ops_records as bulk_ops_records,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import (
    BulkResult,
    Job,
    OPERATIONS,
    SAFE_STUDENT_FIELDS,
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations.cli_flows.prompts import (
    _input,
    _pause,
    _pick_from,
    _pick_group,
    _pick_slot,
    _pick_slots,
    _pick_students,
    _pick_subject,
    _print_jobs,
    _print_result,
    _UserAbort,
    _yes_no,
)
from education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations.cli_flows.records import (
    bulk_anonymise_flow,
    bulk_archive_flow,
    bulk_contacts_csv_flow,
    bulk_export_records_flow,
    bulk_gdpr_flow,
    bulk_inventory_flow,
    bulk_leavers_flow,
    bulk_photos_flow,
    bulk_promote_flow,
    bulk_pwreset_flag_flow,
    bulk_reinstate_flow,
    bulk_update_field,
)
from education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations.cli_flows.attendance import (
    bulk_attendance_letters_flow,
    bulk_authorise_flow,
    bulk_clear_attendance_flow,
    bulk_flag_low_attendance_flow,
    bulk_import_csv_flow,
    bulk_late_to_unauth_flow,
    bulk_lateness_flow,
    bulk_mark_attendance_flow,
    bulk_mark_holiday_flow,
    bulk_punctuality_report_flow,
    bulk_recalc_flow,
    bulk_register_closure_flow,
    bulk_signoff_flow,
)
from education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations.cli_flows.academic import (
    bulk_assign_subjects_flow,
    bulk_enrol_flow,
    bulk_exam_access_flow,
    bulk_exam_entries_flow,
    bulk_exam_timetables_flow,
    bulk_export_progress_flow,
    bulk_grade_boundaries_flow,
    bulk_import_marks_flow,
    bulk_import_timetable_csv_flow,
    bulk_move_group_flow,
    bulk_predicted_grades_flow,
    bulk_publish_reports_flow,
    bulk_recalc_grades_flow,
    bulk_set_teaching_set_flow,
    bulk_ucas_export_flow,
    bulk_ucas_status_flow,
    bulk_withdraw_subjects_flow,
)
from education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations.cli_flows.pastoral import (
    bulk_accommodation,
    bulk_behaviour,
    bulk_detention_flow,
    bulk_escalate_flow,
    bulk_mentors_flow,
    bulk_merits_flow,
    bulk_reset_points_flow,
    bulk_safeguarding_flow,
)
from education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations.cli_flows.comms import (
    bulk_letters_flow,
    bulk_meeting_invites_flow,
    bulk_message_flow,
    bulk_password_reset_flow,
    bulk_schedule_msg_flow,
    bulk_sms_flow,
    bulk_ucas_reminders_flow,
)
from education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations.cli_flows.finance import (
    bulk_bursary_flow,
    bulk_discount_flow,
    bulk_invoices_flow,
    bulk_payments_csv_flow,
    bulk_statements_flow,
)
from education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations.cli_flows.jobs import (
    bulk_logs_clear_flow,
    bulk_logs_flow,
    bulk_schedule_create_flow,
    bulk_schedule_delete_flow,
    bulk_schedule_list_flow,
    bulk_schedule_toggle_flow,
    bulk_undo_job_flow,
    delete_job_flow,
    list_jobs_flow,
    summary_flow,
    view_job,
)

logger = logging.getLogger(__name__)


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Bulk log behaviour",           bulk_behaviour),
    ("Bulk add accommodation",       bulk_accommodation),
    ("Bulk update student field",    bulk_update_field),
    ("Bulk message students",        bulk_message_flow),
    ("Bulk archive to alumni",       bulk_archive_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk mark attendance",         bulk_mark_attendance_flow),
    ("Bulk authorise absences",      bulk_authorise_flow),
    ("Bulk apply lateness",          bulk_lateness_flow),
    ("Bulk import attendance CSV",   bulk_import_csv_flow),
    ("Bulk recalculate attendance",  bulk_recalc_flow),
    ("Bulk flag low attendance",     bulk_flag_low_attendance_flow),
    ("Bulk register sign-off",       bulk_signoff_flow),
    ("Bulk mark holiday",            bulk_mark_holiday_flow),
    ("Bulk clear attendance",        bulk_clear_attendance_flow),
    ("Bulk late → unauthorised",     bulk_late_to_unauth_flow),
    ("Bulk attendance letters",      bulk_attendance_letters_flow),
    ("Bulk punctuality report",      bulk_punctuality_report_flow),
    ("Bulk register closure",        bulk_register_closure_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk enrol students",          bulk_enrol_flow),
    ("Bulk assign subjects",         bulk_assign_subjects_flow),
    ("Bulk withdraw subjects",       bulk_withdraw_subjects_flow),
    ("Bulk set teaching set",        bulk_set_teaching_set_flow),
    ("Bulk import timetable CSV",    bulk_import_timetable_csv_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk move class group",        bulk_move_group_flow),
    ("Bulk assign predicted grades", bulk_predicted_grades_flow),
    ("Bulk import assessment marks", bulk_import_marks_flow),
    ("Bulk recalc grade reports",    bulk_recalc_grades_flow),
    ("Bulk export progress reports", bulk_export_progress_flow),
    ("Bulk publish report cards",    bulk_publish_reports_flow),
    ("Bulk apply grade boundaries",  bulk_grade_boundaries_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk issue detentions",        bulk_detention_flow),
    ("Bulk award merits",            bulk_merits_flow),
    ("Bulk escalate behaviour",      bulk_escalate_flow),
    ("Bulk safeguarding flag",       bulk_safeguarding_flow),
    ("Bulk assign mentors",          bulk_mentors_flow),
    ("Bulk reset behaviour points",  bulk_reset_points_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk SMS",                     bulk_sms_flow),
    ("Bulk send letters",            bulk_letters_flow),
    ("Bulk parents-evening invites", bulk_meeting_invites_flow),
    ("Bulk UCAS reference reminders", bulk_ucas_reminders_flow),
    ("Bulk password reset emails",   bulk_password_reset_flow),
    ("Bulk schedule message",        bulk_schedule_msg_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk bursary award",           bulk_bursary_flow),
    ("Bulk raise invoices",          bulk_invoices_flow),
    ("Bulk fee discount",            bulk_discount_flow),
    ("Bulk import payments CSV",     bulk_payments_csv_flow),
    ("Bulk financial statements",    bulk_statements_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk exam entries",            bulk_exam_entries_flow),
    ("Bulk exam access arrangements", bulk_exam_access_flow),
    ("Bulk export exam timetables",  bulk_exam_timetables_flow),
    ("Bulk UCAS export predictions", bulk_ucas_export_flow),
    ("Bulk update UCAS status",      bulk_ucas_status_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk promote year group",      bulk_promote_flow),
    ("Bulk mark leavers",            bulk_leavers_flow),
    ("Bulk reinstate alumni",        bulk_reinstate_flow),
    ("Bulk GDPR redact",             bulk_gdpr_flow),
    ("Bulk export student records",  bulk_export_records_flow),
    ("Bulk anonymise alumni",        bulk_anonymise_flow),
    ("─" * 6,                        lambda: None),
    ("Bulk assign inventory",        bulk_inventory_flow),
    ("Bulk upload photos",           bulk_photos_flow),
    ("Bulk import contacts CSV",     bulk_contacts_csv_flow),
    ("Bulk force password reset",    bulk_pwreset_flag_flow),
    ("─" * 6,                        lambda: None),
    ("Undo job",                     bulk_undo_job_flow),
    ("Create recurring schedule",    bulk_schedule_create_flow),
    ("List schedules",               bulk_schedule_list_flow),
    ("Toggle schedule",              bulk_schedule_toggle_flow),
    ("Delete schedule",              bulk_schedule_delete_flow),
    ("─" * 6,                        lambda: None),
    ("View logs",                    bulk_logs_flow),
    ("Clear logs",                   bulk_logs_clear_flow),
    ("─" * 6,                        lambda: None),
    ("Job log",                      list_jobs_flow),
    ("View job",                     view_job),
    ("Delete job",                   delete_job_flow),
    ("Summary",                      summary_flow),
]


def run() -> None:
    # Make sure the SQLite log handler is up before we field any input.
    try:
        bulk_base.init_db()
    except Exception as e:  # noqa: BLE001 — non-fatal at the menu level
        print(f"\n  ⚠ Bulk-operations DB not ready: {e}")
    while True:
        print("\n── Bulk Operations ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
                print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except ValidationError as e:
            bulk_base.log_event(logging.WARNING,
                            f"CLI validation error in {label!r}: {e}",
                            operation=label)
            print(f"\n  ✗ {e}")
            _pause()
        except Exception as e:  # noqa: BLE001
            bulk_base.log_event(logging.ERROR,
                            f"CLI handler {label!r} crashed: {e}",
                            operation=label, exc_info=True)
            logger.exception("Bulk-operations CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Bulk Operations":
        return False
    try:
        run()
    except Exception as e:  # noqa: BLE001
        try:
            bulk_base.log_event(logging.CRITICAL,
                            f"Bulk-operations submenu crashed: {e}",
                            exc_info=True)
        except Exception:  # noqa: BLE001 — last-resort
            pass
        logger.exception("Bulk-operations CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
