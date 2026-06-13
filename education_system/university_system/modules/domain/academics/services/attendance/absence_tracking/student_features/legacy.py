"""Split from student_features.py — see package __init__.py for public API."""
from __future__ import annotations

import calendar
import csv
import functools
import json
import logging
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
    logger = configure_logging(name="absence_tracker.student")
except Exception:
    logger = logging.getLogger("absence_tracker.student")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

from .context import StudentContext
from .facade import StudentServices

def _wrap(method_picker: Callable[[StudentServices], Callable[[], None]]
          ) -> Callable[[StudentContext], None]:
    def runner(ctx: StudentContext) -> None:
        services = StudentServices.for_context(ctx)
        method_picker(services)()
    return runner


_LEGACY_ALIASES: dict[str, Callable] = {
    "stu_01_calendar":             _wrap(lambda s: s.visibility.show_calendar),
    "stu_02_gauge":                _wrap(lambda s: s.visibility.show_gauges),
    "stu_03_streak":               _wrap(lambda s: s.visibility.show_streak),
    "stu_04_timeline":             _wrap(lambda s: s.visibility.show_timeline),
    "stu_05_export_my_data":       _wrap(lambda s: s.visibility.export_my_data),
    "stu_06_compare_module_avg":   _wrap(lambda s: s.visibility.compare_to_module_average),
    "stu_07_projection":           _wrap(lambda s: s.visibility.project_absence_budget),
    "stu_08_personal_heatmap":     _wrap(lambda s: s.visibility.show_personal_heatmap),
    "stu_09_quick_submit":         _wrap(lambda s: s.requests.quick_submit_from_template),
    "stu_10_attach_evidence":      _wrap(lambda s: s.requests.attach_evidence),
    "stu_11_status_tracker":       _wrap(lambda s: s.requests.show_status_tracker),
    "stu_12_withdraw":             _wrap(lambda s: s.requests.withdraw_pending),
    "stu_13_resubmit":             _wrap(lambda s: s.requests.resubmit_rejected),
    "stu_14_bulk_request":         _wrap(lambda s: s.requests.bulk_multi_day_request),
    "stu_15_save_draft":           _wrap(lambda s: s.requests.save_draft),
    "stu_16_history_export":       _wrap(lambda s: s.requests.export_request_history),
    "stu_17_class_reminder":       _wrap(lambda s: s.notifications.set_class_reminder),
    "stu_18_low_attendance_alert": _wrap(lambda s: s.notifications.set_low_attendance_alert),
    "stu_19_deadline_alerts":      _wrap(lambda s: s.notifications.show_upcoming_deadlines),
    "stu_20_parent_notif_log":     _wrap(lambda s: s.notifications.show_parent_notifications_log),
    "stu_21_notification_prefs":   _wrap(lambda s: s.notifications.edit_channel_preferences),
    "stu_22_dnd_hours":            _wrap(lambda s: s.notifications.set_dnd_hours),
    "stu_23_attendance_goals":     _wrap(lambda s: s.planning.set_per_module_goal),
    "stu_24_attendance_budget":    _wrap(lambda s: s.planning.show_attendance_budget),
    "stu_25_term_forecast":        _wrap(lambda s: s.planning.show_term_forecast),
    "stu_26_calendar_sync":        _wrap(lambda s: s.planning.export_calendar_ics),
    "stu_27_recovery_plan":        _wrap(lambda s: s.planning.show_recovery_plan),
    "stu_28_wellbeing_checkin":    _wrap(lambda s: s.planning.log_wellbeing_checkin),
    "stu_29_request_notes":        _wrap(lambda s: s.support.request_classmate_notes),
    "stu_30_book_office_hours":    _wrap(lambda s: s.support.book_office_hours),
    "stu_31_study_buddy":          _wrap(lambda s: s.support.join_study_buddy_pool),
    "stu_32_recorded_lectures":    _wrap(lambda s: s.support.show_recorded_lectures),
    "stu_33_wellbeing_flag":       _wrap(lambda s: s.support.submit_wellbeing_flag),
    "stu_34_support_resources":    _wrap(lambda s: s.support.show_support_resources),
    "stu_35_self_refer_advising":  _wrap(lambda s: s.support.self_refer_to_advising),
    "stu_36_find_study_group":     _wrap(lambda s: s.social.find_or_create_study_group),
    "stu_37_note_share":           _wrap(lambda s: s.social.share_or_browse_notes),
    "stu_38_attendance_badge":     _wrap(lambda s: s.social.claim_attendance_badges),
    "stu_39_weekly_digest":        _wrap(lambda s: s.social.show_weekly_digest),
    "stu_40_dispute_record":       _wrap(lambda s: s.appeals.dispute_attendance_record),
    "stu_41_dispute_history":      _wrap(lambda s: s.appeals.show_dispute_history),
    "stu_42_appeal_request":       _wrap(lambda s: s.appeals.appeal_rejected_request),
    "stu_43_my_timetable":         _wrap(lambda s: s.integrations.show_my_timetable),
    "stu_44_grade_impact":         _wrap(lambda s: s.integrations.show_grade_vs_attendance),
    "stu_45_my_assignments":       _wrap(lambda s: s.integrations.show_my_assignments),
    "stu_46_library_resources":    _wrap(lambda s: s.integrations.search_library),
    "stu_47_exam_day_check":       _wrap(lambda s: s.integrations.show_exam_day_check),
    "stu_48_accessibility_mode":   _wrap(lambda s: s.customisation.toggle_accessibility_mode),
    "stu_49_language":             _wrap(lambda s: s.customisation.set_language),
    "stu_50_dashboard_layout":     _wrap(lambda s: s.customisation.edit_dashboard_layout),
    "stu_51_request_time_off":     _wrap(lambda s: s.requests.request_time_off),
}
globals().update(_LEGACY_ALIASES)
