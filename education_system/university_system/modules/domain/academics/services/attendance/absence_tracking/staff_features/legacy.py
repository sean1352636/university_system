"""Split from staff_features.py — see package __init__.py for public API."""
from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Iterable, Optional

from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name="absence_tracker.staff")
except Exception:
    logger = logging.getLogger("absence_tracker.staff")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

from .context import StaffContext
from .facade import StaffServices

def _wrap(method_picker: Callable[[StaffServices], Callable[[], None]]
          ) -> Callable[[StaffContext], None]:
    def runner(ctx: StaffContext) -> None:
        services = StaffServices.for_context(ctx)
        method_picker(services)()
    return runner


_LEGACY_ALIASES: dict[str, Callable] = {
    "stf_01_today_dashboard":     _wrap(lambda s: s.roll_call.show_today_dashboard),
    "stf_02_generate_sessions":   _wrap(lambda s: s.roll_call.generate_session_dates),
    "stf_03_session_note":        _wrap(lambda s: s.roll_call.add_session_note),
    "stf_04_cancel_session":      _wrap(lambda s: s.roll_call.cancel_session),
    "stf_05_substitute_mode":     _wrap(lambda s: s.roll_call.substitute_for_colleague),
    "stf_06_all_present_except":  _wrap(lambda s: s.roll_call.mark_all_present_except),
    "stf_07_late_log":            _wrap(lambda s: s.roll_call.log_late_arrival),
    "stf_08_early_leave":         _wrap(lambda s: s.roll_call.log_early_leave),
    "stf_09_session_qr":          _wrap(lambda s: s.roll_call.generate_session_qr),
    "stf_10_correct_roll":        _wrap(lambda s: s.roll_call.correct_roll_row),
    "stf_11_roster_with_photos":  _wrap(lambda s: s.roster.show_roster_with_contacts),
    "stf_12_search_my_students":  _wrap(lambda s: s.roster.search_my_students),
    "stf_13_filter_by_risk":      _wrap(lambda s: s.roster.filter_students_by_risk),
    "stf_14_groups":              _wrap(lambda s: s.roster.manage_module_groups),
    "stf_15_roster_export":       _wrap(lambda s: s.roster.export_roster),
    "stf_16_triage_queue":        _wrap(lambda s: s.requests.show_triage_queue),
    "stf_17_preview_evidence":    _wrap(lambda s: s.requests.preview_request_evidence),
    "stf_18_decision_comment":    _wrap(lambda s: s.requests.decide_with_comment),
    "stf_19_approve_with_mod":    _wrap(lambda s: s.requests.approve_with_modification),
    "stf_20_sla_dashboard":       _wrap(lambda s: s.requests.show_sla_dashboard),
    "stf_21_route_to_dept":       _wrap(lambda s: s.requests.route_to_department_head),
    "stf_22_my_heatmap":          _wrap(lambda s: s.analytics.show_my_heatmap),
    "stf_23_dropoff":             _wrap(lambda s: s.analytics.show_dropoff_students),
    "stf_24_compare_my_modules":  _wrap(lambda s: s.analytics.compare_my_modules),
    "stf_25_historical_cohort":   _wrap(lambda s: s.analytics.compare_terms_for_module),
    "stf_26_module_report":       _wrap(lambda s: s.analytics.export_module_report),
    "stf_27_student_profile":     _wrap(lambda s: s.analytics.show_student_profile),
    "stf_28_correlation":         _wrap(lambda s: s.analytics.show_attendance_vs_grade),
    "stf_29_email_student":       _wrap(lambda s: s.communication.email_single_student),
    "stf_30_email_at_risk":       _wrap(lambda s: s.communication.email_at_risk_summary),
    "stf_31_announcement":        _wrap(lambda s: s.communication.post_module_announcement),
    "stf_32_catchup_message":     _wrap(lambda s: s.communication.send_catchup_to_absentees),
    "stf_33_parent_outreach":     _wrap(lambda s: s.communication.notify_parents_of_low_attendance),
    "stf_34_office_hours":        _wrap(lambda s: s.communication.publish_office_hours),
    "stf_35_flag_pastoral":       _wrap(lambda s: s.pastoral.flag_pastoral_concern),
    "stf_36_checkin_log":         _wrap(lambda s: s.pastoral.log_checkin_conversation),
    "stf_37_escalate_safeguarding": _wrap(lambda s: s.pastoral.escalate_safeguarding_incident),
    "stf_38_meeting_scheduler":   _wrap(lambda s: s.pastoral.schedule_student_meeting),
    "stf_39_intervention_tracker": _wrap(lambda s: s.pastoral.show_intervention_history),
    "stf_40_assignment_link":     _wrap(lambda s: s.assessment.show_pre_deadline_absence_risk),
    "stf_41_exam_eligibility":    _wrap(lambda s: s.assessment.show_exam_ineligible_students),
    "stf_42_lab_safety":          _wrap(lambda s: s.assessment.show_missing_safety_briefing),
    "stf_43_co_teacher":          _wrap(lambda s: s.collaboration.grant_co_teacher_access),
    "stf_44_ta_handoff":          _wrap(lambda s: s.collaboration.leave_ta_handoff_note),
    "stf_45_peer_observation":    _wrap(lambda s: s.collaboration.log_peer_observation),
    "stf_46_policy_quick_edit":   _wrap(lambda s: s.configuration.edit_module_policy),
    "stf_47_excuse_range":        _wrap(lambda s: s.configuration.excuse_date_range),
    "stf_48_seating_chart":       _wrap(lambda s: s.configuration.import_seating_chart),
    "stf_49_my_kpis":             _wrap(lambda s: s.productivity.show_my_kpis),
    "stf_50_todo":                _wrap(lambda s: s.productivity.show_my_todo_list),
    "stf_51_request_time_off":    _wrap(lambda s: s.leave.request_time_off),
}
