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

@dataclass(frozen=True)
class FeatureSpec:
    number: int
    category: str
    label: str
    method: Callable[[StaffServices], Callable[[], None]]


def _build_feature_registry() -> list[FeatureSpec]:
    return [
        # Roll-call
        FeatureSpec( 1, "Roll-call", "Today's classes",
                    lambda s: s.roll_call.show_today_dashboard),
        FeatureSpec( 2, "Roll-call", "Generate sessions",
                    lambda s: s.roll_call.generate_session_dates),
        FeatureSpec( 3, "Roll-call", "Session notes",
                    lambda s: s.roll_call.add_session_note),
        FeatureSpec( 4, "Roll-call", "Cancel session",
                    lambda s: s.roll_call.cancel_session),
        FeatureSpec( 5, "Roll-call", "Substitute mode",
                    lambda s: s.roll_call.substitute_for_colleague),
        FeatureSpec( 6, "Roll-call", "All-present (with excepts)",
                    lambda s: s.roll_call.mark_all_present_except),
        FeatureSpec( 7, "Roll-call", "Late log",
                    lambda s: s.roll_call.log_late_arrival),
        FeatureSpec( 8, "Roll-call", "Early-leave log",
                    lambda s: s.roll_call.log_early_leave),
        FeatureSpec( 9, "Roll-call", "Session QR code",
                    lambda s: s.roll_call.generate_session_qr),
        FeatureSpec(10, "Roll-call", "Correct roll after session",
                    lambda s: s.roll_call.correct_roll_row),

        # Roster
        FeatureSpec(11, "Roster", "Roster (+ contacts)",
                    lambda s: s.roster.show_roster_with_contacts),
        FeatureSpec(12, "Roster", "Search my students",
                    lambda s: s.roster.search_my_students),
        FeatureSpec(13, "Roster", "Filter by risk",
                    lambda s: s.roster.filter_students_by_risk),
        FeatureSpec(14, "Roster", "Groups",
                    lambda s: s.roster.manage_module_groups),
        FeatureSpec(15, "Roster", "Roster export",
                    lambda s: s.roster.export_roster),

        # Requests
        FeatureSpec(16, "Requests", "Triage queue",
                    lambda s: s.requests.show_triage_queue),
        FeatureSpec(17, "Requests", "Preview evidence",
                    lambda s: s.requests.preview_request_evidence),
        FeatureSpec(18, "Requests", "Staff comment + decide",
                    lambda s: s.requests.decide_with_comment),
        FeatureSpec(19, "Requests", "Approve with modification",
                    lambda s: s.requests.approve_with_modification),
        FeatureSpec(20, "Requests", "SLA dashboard",
                    lambda s: s.requests.show_sla_dashboard),
        FeatureSpec(21, "Requests", "Route to dept head",
                    lambda s: s.requests.route_to_department_head),

        # Analytics
        FeatureSpec(22, "Analytics", "My heatmap",
                    lambda s: s.analytics.show_my_heatmap),
        FeatureSpec(23, "Analytics", "Drop-off detector",
                    lambda s: s.analytics.show_dropoff_students),
        FeatureSpec(24, "Analytics", "Compare my modules",
                    lambda s: s.analytics.compare_my_modules),
        FeatureSpec(25, "Analytics", "Historical cohort",
                    lambda s: s.analytics.compare_terms_for_module),
        FeatureSpec(26, "Analytics", "Module report export",
                    lambda s: s.analytics.export_module_report),
        FeatureSpec(27, "Analytics", "Student profile",
                    lambda s: s.analytics.show_student_profile),
        FeatureSpec(28, "Analytics", "Attendance vs grade",
                    lambda s: s.analytics.show_attendance_vs_grade),

        # Communication
        FeatureSpec(29, "Communication", "Email student",
                    lambda s: s.communication.email_single_student),
        FeatureSpec(30, "Communication", "Email at-risk list",
                    lambda s: s.communication.email_at_risk_summary),
        FeatureSpec(31, "Communication", "Module announcement",
                    lambda s: s.communication.post_module_announcement),
        FeatureSpec(32, "Communication", "Catch-up message (absent)",
                    lambda s: s.communication.send_catchup_to_absentees),
        FeatureSpec(33, "Communication", "Parent outreach",
                    lambda s: s.communication.notify_parents_of_low_attendance),
        FeatureSpec(34, "Communication", "Publish office hours",
                    lambda s: s.communication.publish_office_hours),

        # Pastoral
        FeatureSpec(35, "Pastoral", "Flag pastoral",
                    lambda s: s.pastoral.flag_pastoral_concern),
        FeatureSpec(36, "Pastoral", "Check-in log",
                    lambda s: s.pastoral.log_checkin_conversation),
        FeatureSpec(37, "Pastoral", "Escalate safeguarding",
                    lambda s: s.pastoral.escalate_safeguarding_incident),
        FeatureSpec(38, "Pastoral", "Meeting scheduler",
                    lambda s: s.pastoral.schedule_student_meeting),
        FeatureSpec(39, "Pastoral", "Intervention tracker",
                    lambda s: s.pastoral.show_intervention_history),

        # Assessment
        FeatureSpec(40, "Assessment", "Assignment ↔ absence",
                    lambda s: s.assessment.show_pre_deadline_absence_risk),
        FeatureSpec(41, "Assessment", "Exam eligibility",
                    lambda s: s.assessment.show_exam_ineligible_students),
        FeatureSpec(42, "Assessment", "Lab safety briefing check",
                    lambda s: s.assessment.show_missing_safety_briefing),

        # Collaboration
        FeatureSpec(43, "Collaboration", "Co-teacher",
                    lambda s: s.collaboration.grant_co_teacher_access),
        FeatureSpec(44, "Collaboration", "TA handoff note",
                    lambda s: s.collaboration.leave_ta_handoff_note),
        FeatureSpec(45, "Collaboration", "Peer observation",
                    lambda s: s.collaboration.log_peer_observation),

        # Config
        FeatureSpec(46, "Config", "Module policy quick-edit",
                    lambda s: s.configuration.edit_module_policy),
        FeatureSpec(47, "Config", "Excuse date range",
                    lambda s: s.configuration.excuse_date_range),
        FeatureSpec(48, "Config", "Seating chart",
                    lambda s: s.configuration.import_seating_chart),

        # Productivity
        FeatureSpec(49, "Productivity", "My KPIs",
                    lambda s: s.productivity.show_my_kpis),
        FeatureSpec(50, "Productivity", "My to-do list",
                    lambda s: s.productivity.show_my_todo_list),

        # Leave
        FeatureSpec(51, "Requests", "Request time off (date picker)",
                    lambda s: s.leave.request_time_off),
    ]


FEATURES: list[FeatureSpec] = _build_feature_registry()
