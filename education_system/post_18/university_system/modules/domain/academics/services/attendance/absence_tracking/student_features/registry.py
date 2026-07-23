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

from education_system.post_18.university_system.modules.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name="absence_tracker.student")
except Exception:
    logger = logging.getLogger("absence_tracker.student")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

from .context import StudentContext

from .facade import StudentServices

@dataclass(frozen=True)
class FeatureSpec:
    number: int
    category: str
    label: str
    method: Callable[[StudentServices], Callable[[], None]]


def _build_feature_registry() -> list[FeatureSpec]:
    """One row per student feature; method picks the bound method off StudentServices."""
    return [
        # Visibility
        FeatureSpec( 1, "Visibility", "Calendar view",
                    lambda s: s.visibility.show_calendar),
        FeatureSpec( 2, "Visibility", "Attendance gauges",
                    lambda s: s.visibility.show_gauges),
        FeatureSpec( 3, "Visibility", "Streak tracker",
                    lambda s: s.visibility.show_streak),
        FeatureSpec( 4, "Visibility", "Personal timeline",
                    lambda s: s.visibility.show_timeline),
        FeatureSpec( 5, "Visibility", "Export my data (CSV/JSON)",
                    lambda s: s.visibility.export_my_data),
        FeatureSpec( 6, "Visibility", "Compare to module average",
                    lambda s: s.visibility.compare_to_module_average),
        FeatureSpec( 7, "Visibility", "Absence-budget projection",
                    lambda s: s.visibility.project_absence_budget),
        FeatureSpec( 8, "Visibility", "Personal heatmap",
                    lambda s: s.visibility.show_personal_heatmap),

        # Requests
        FeatureSpec( 9, "Requests", "Quick-submit from template",
                    lambda s: s.requests.quick_submit_from_template),
        FeatureSpec(10, "Requests", "Attach evidence",
                    lambda s: s.requests.attach_evidence),
        FeatureSpec(11, "Requests", "Status tracker",
                    lambda s: s.requests.show_status_tracker),
        FeatureSpec(12, "Requests", "Withdraw pending",
                    lambda s: s.requests.withdraw_pending),
        FeatureSpec(13, "Requests", "Resubmit rejected",
                    lambda s: s.requests.resubmit_rejected),
        FeatureSpec(14, "Requests", "Bulk multi-day request",
                    lambda s: s.requests.bulk_multi_day_request),
        FeatureSpec(15, "Requests", "Save draft",
                    lambda s: s.requests.save_draft),
        FeatureSpec(16, "Requests", "Export request history",
                    lambda s: s.requests.export_request_history),

        # Reminders
        FeatureSpec(17, "Reminders", "Class reminder minutes",
                    lambda s: s.notifications.set_class_reminder),
        FeatureSpec(18, "Reminders", "Low-attendance self-alert",
                    lambda s: s.notifications.set_low_attendance_alert),
        FeatureSpec(19, "Reminders", "Upcoming deadlines",
                    lambda s: s.notifications.show_upcoming_deadlines),
        FeatureSpec(20, "Reminders", "Parent-notification log",
                    lambda s: s.notifications.show_parent_notifications_log),
        FeatureSpec(21, "Reminders", "Channel preferences",
                    lambda s: s.notifications.edit_channel_preferences),
        FeatureSpec(22, "Reminders", "Do-not-disturb hours",
                    lambda s: s.notifications.set_dnd_hours),

        # Planning
        FeatureSpec(23, "Planning", "Per-module goals",
                    lambda s: s.planning.set_per_module_goal),
        FeatureSpec(24, "Planning", "Attendance budget",
                    lambda s: s.planning.show_attendance_budget),
        FeatureSpec(25, "Planning", "Term forecast",
                    lambda s: s.planning.show_term_forecast),
        FeatureSpec(26, "Planning", "Calendar sync (ICS)",
                    lambda s: s.planning.export_calendar_ics),
        FeatureSpec(27, "Planning", "Recovery planner",
                    lambda s: s.planning.show_recovery_plan),
        FeatureSpec(28, "Planning", "Wellbeing check-in",
                    lambda s: s.planning.log_wellbeing_checkin),

        # Support
        FeatureSpec(29, "Support", "Request notes from classmates",
                    lambda s: s.support.request_classmate_notes),
        FeatureSpec(30, "Support", "Book office hours",
                    lambda s: s.support.book_office_hours),
        FeatureSpec(31, "Support", "Study buddy matchmaker",
                    lambda s: s.support.join_study_buddy_pool),
        FeatureSpec(32, "Support", "Recorded lectures",
                    lambda s: s.support.show_recorded_lectures),
        FeatureSpec(33, "Support", "Confidential wellbeing flag",
                    lambda s: s.support.submit_wellbeing_flag),
        FeatureSpec(34, "Support", "Support resources",
                    lambda s: s.support.show_support_resources),
        FeatureSpec(35, "Support", "Self-refer to advising",
                    lambda s: s.support.self_refer_to_advising),

        # Social
        FeatureSpec(36, "Social", "Find study group",
                    lambda s: s.social.find_or_create_study_group),
        FeatureSpec(37, "Social", "Note-share marketplace",
                    lambda s: s.social.share_or_browse_notes),
        FeatureSpec(38, "Social", "Attendance badges",
                    lambda s: s.social.claim_attendance_badges),
        FeatureSpec(39, "Social", "Weekly digest",
                    lambda s: s.social.show_weekly_digest),

        # Appeals
        FeatureSpec(40, "Appeals", "Dispute a record",
                    lambda s: s.appeals.dispute_attendance_record),
        FeatureSpec(41, "Appeals", "My dispute history",
                    lambda s: s.appeals.show_dispute_history),
        FeatureSpec(42, "Appeals", "Appeal a rejected request",
                    lambda s: s.appeals.appeal_rejected_request),

        # Integrations
        FeatureSpec(43, "Integrations", "My timetable",
                    lambda s: s.integrations.show_my_timetable),
        FeatureSpec(44, "Integrations", "Grade vs attendance impact",
                    lambda s: s.integrations.show_grade_vs_attendance),
        FeatureSpec(45, "Integrations", "My assignments",
                    lambda s: s.integrations.show_my_assignments),
        FeatureSpec(46, "Integrations", "Library resources",
                    lambda s: s.integrations.search_library),
        FeatureSpec(47, "Integrations", "Exam-day check",
                    lambda s: s.integrations.show_exam_day_check),

        # Accessibility
        FeatureSpec(48, "Accessibility", "Accessibility mode (toggle)",
                    lambda s: s.customisation.toggle_accessibility_mode),
        FeatureSpec(49, "Accessibility", "Language",
                    lambda s: s.customisation.set_language),
        FeatureSpec(50, "Accessibility", "Dashboard layout",
                    lambda s: s.customisation.edit_dashboard_layout),

        # Bonus
        FeatureSpec(51, "Requests", "Request time off (date picker)",
                    lambda s: s.requests.request_time_off),
    ]


FEATURES: list[FeatureSpec] = _build_feature_registry()
