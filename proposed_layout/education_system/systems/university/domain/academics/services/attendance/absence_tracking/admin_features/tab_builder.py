"""Feature registry, Tk tab renderer, and legacy ``feat_NN_*`` aliases."""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Callable

import sqlite3

from .context import AdminContext, logger
from .services import AdminServices
from .support_tables import ensure_support_tables, install_soft_delete


@dataclass(frozen=True)
class FeatureSpec:
    number: int
    category: str
    label: str
    method: Callable[[AdminServices], Callable[[], None]]


def _build_feature_registry() -> list[FeatureSpec]:
    return [
        # Data
        FeatureSpec( 1, "Data", "Bulk import CSV",
                    lambda s: s.data.bulk_import_csv),
        FeatureSpec( 2, "Data", "Bulk export CSV",
                    lambda s: s.data.bulk_export_csv),
        FeatureSpec( 3, "Data", "Edit record in place",
                    lambda s: s.data.edit_attendance_row),
        FeatureSpec( 4, "Data", "Undo delete (24h trash)",
                    lambda s: s.data.undo_recent_deletes),
        FeatureSpec( 5, "Data", "Merge duplicate rows",
                    lambda s: s.data.merge_duplicate_rows),
        FeatureSpec( 6, "Data", "Correction audit log",
                    lambda s: s.data.show_correction_audit),
        FeatureSpec( 7, "Data", "Lock past dates",
                    lambda s: s.data.lock_past_dates),
        # Requests
        FeatureSpec( 8, "Requests", "Bulk approve / reject",
                    lambda s: s.requests.bulk_approve_or_reject),
        FeatureSpec( 9, "Requests", "Attach document to request",
                    lambda s: s.requests.attach_document_to_request),
        FeatureSpec(10, "Requests", "Auto-expire old pending",
                    lambda s: s.requests.expire_old_pending_requests),
        FeatureSpec(11, "Requests", "Delegate approval",
                    lambda s: s.requests.delegate_approval_authority),
        FeatureSpec(12, "Requests", "Comment thread on request",
                    lambda s: s.requests.show_request_comment_thread),
        FeatureSpec(13, "Requests", "Manage request templates",
                    lambda s: s.requests.manage_request_templates),
        # Policies
        FeatureSpec(14, "Policies", "Per-module policy",
                    lambda s: s.policy.edit_module_policy),
        FeatureSpec(15, "Policies", "Default university policy",
                    lambda s: s.policy.set_default_min_percent),
        FeatureSpec(16, "Policies", "Status vocabulary",
                    lambda s: s.policy.manage_status_vocabulary),
        FeatureSpec(17, "Policies", "Auto-excuse rules",
                    lambda s: s.policy.add_auto_excuse_rule),
        FeatureSpec(18, "Policies", "Global grace period",
                    lambda s: s.policy.set_global_grace_minutes),
        # Reports
        FeatureSpec(19, "Reports", "At-risk students",
                    lambda s: s.reporting.show_at_risk_students),
        FeatureSpec(20, "Reports", "Module health",
                    lambda s: s.reporting.show_module_health),
        FeatureSpec(21, "Reports", "Cohort comparison",
                    lambda s: s.reporting.compare_cohorts),
        FeatureSpec(22, "Reports", "Weekly trend",
                    lambda s: s.reporting.show_weekly_trend),
        FeatureSpec(23, "Reports", "Term-over-term",
                    lambda s: s.reporting.compare_terms),
        FeatureSpec(24, "Reports", "Schedule recurring report",
                    lambda s: s.reporting.schedule_recurring_report),
        FeatureSpec(25, "Reports", "Top consecutive absences",
                    lambda s: s.reporting.show_top_absentees),
        FeatureSpec(26, "Reports", "Day-of-week heatmap",
                    lambda s: s.reporting.show_dayofweek_heatmap),
        # Notifications
        FeatureSpec(27, "Notifications", "Threshold alerts",
                    lambda s: s.notifications.create_threshold_alerts),
        FeatureSpec(28, "Notifications", "Parent notifications",
                    lambda s: s.notifications.notify_parents_for_student),
        FeatureSpec(29, "Notifications", "Bulk announcement",
                    lambda s: s.notifications.post_bulk_announcement),
        FeatureSpec(30, "Notifications", "SMS fallback queue",
                    lambda s: s.notifications.queue_sms_fallback),
        # Integrations
        FeatureSpec(31, "Integrations", "Calendar events link",
                    lambda s: s.integrations.show_upcoming_calendar_events),
        FeatureSpec(32, "Integrations", "Module schedule sessions",
                    lambda s: s.integrations.show_module_schedule),
        FeatureSpec(33, "Integrations", "Feed student risk model",
                    lambda s: s.integrations.feed_student_risk_assessment),
        FeatureSpec(34, "Integrations", "Grade penalty candidates",
                    lambda s: s.integrations.show_grade_penalty_candidates),
        FeatureSpec(35, "Integrations", "Wellbeing cross-reference",
                    lambda s: s.integrations.show_absences_vs_mood),
        FeatureSpec(36, "Integrations", "Raise disciplinary action",
                    lambda s: s.integrations.raise_disciplinary_action),
        FeatureSpec(37, "Integrations", "Scholarship attendance check",
                    lambda s: s.integrations.show_scholarship_attendance_check),
        # Bulk
        FeatureSpec(38, "Bulk", "Mark whole class present",
                    lambda s: s.bulk.mark_module_all_present),
        FeatureSpec(39, "Bulk", "Copy previous day",
                    lambda s: s.bulk.copy_previous_day_roll),
        FeatureSpec(40, "Bulk", "Recurring absence",
                    lambda s: s.bulk.create_recurring_absence),
        FeatureSpec(41, "Bulk", "Reassign records on transfer",
                    lambda s: s.bulk.reassign_records_on_transfer),
        # Security
        FeatureSpec(42, "Security", "Permission matrix",
                    lambda s: s.security.show_permission_matrix),
        FeatureSpec(43, "Security", "Full audit trail",
                    lambda s: s.security.show_full_audit_trail),
        FeatureSpec(44, "Security", "Impersonate (read-only)",
                    lambda s: s.security.impersonate_user_readonly),
        FeatureSpec(45, "Security", "Retention purge",
                    lambda s: s.security.purge_per_retention_policy),
        FeatureSpec(46, "Security", "GDPR subject export",
                    lambda s: s.security.gdpr_subject_export),
        # Diagnostics
        FeatureSpec(47, "Diagnostics", "Orphan attendance rows",
                    lambda s: s.diagnostics.show_orphan_attendance_rows),
        FeatureSpec(48, "Diagnostics", "Missing sessions",
                    lambda s: s.diagnostics.show_modules_without_attendance),
        FeatureSpec(49, "Diagnostics", "Enrollment mismatch",
                    lambda s: s.diagnostics.show_enrollment_mismatches),
        FeatureSpec(50, "Diagnostics", "Database health",
                    lambda s: s.diagnostics.show_database_health),
    ]


FEATURES: list[FeatureSpec] = _build_feature_registry()




def build_admin_tab(notebook: ttk.Notebook, ctx: AdminContext) -> None:
    """Render all 50 features into a dedicated Admin Tools tab."""
    try:
        ensure_support_tables(ctx.db)
        install_soft_delete(ctx.db)
    except sqlite3.Error:
        logger.exception("could not initialise admin tools")
        messagebox.showerror(
            "Admin Tools",
            "Could not initialise admin-tools tables. See log.",
            parent=ctx.parent)
        return

    services = AdminServices.for_context(ctx)

    frame = ttk.Frame(notebook)
    notebook.add(frame, text="🛠 Admin Tools (50)")

    canvas = tk.Canvas(frame, bg="#f0f4f8", highlightthickness=0)
    vsb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    canvas.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    inner = tk.Frame(canvas, bg="#f0f4f8")
    canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    by_cat: dict[str, list[FeatureSpec]] = {}
    for spec in FEATURES:
        by_cat.setdefault(spec.category, []).append(spec)

    for cat, items in by_cat.items():
        box = tk.LabelFrame(inner, text=cat, padx=10, pady=8,
                            font=("Arial", 11, "bold"), bg="#f0f4f8",
                            fg="#1e3a5f")
        box.pack(fill="x", padx=12, pady=8)
        cols = 3
        for i, spec in enumerate(items):
            try:
                callback = spec.method(services)
            except Exception:
                logger.exception("feature %d binding failed", spec.number)
                continue
            btn = tk.Button(
                box, text=f"{spec.number:02d}. {spec.label}",
                command=callback,
                bg="#2563eb", fg="white", activebackground="#1d4ed8",
                relief="flat", cursor="hand2",
                width=32, anchor="w", padx=8, pady=6,
            )
            btn.grid(row=i // cols, column=i % cols, padx=4, pady=3, sticky="w")

    logger.info("admin tools tab built (%d features)", len(FEATURES))


# ===========================================================================
# Backwards-compat: keep module-level callable aliases for any external caller
# that imported the old `feat_NN_*` names directly.
# ===========================================================================

def _wrap(method_picker: Callable[[AdminServices], Callable[[], None]]
          ) -> Callable[[AdminContext], None]:
    def runner(ctx: AdminContext) -> None:
        services = AdminServices.for_context(ctx)
        method_picker(services)()
    return runner


_LEGACY_ALIASES: dict[str, Callable] = {
    "feat_01_bulk_import":            _wrap(lambda s: s.data.bulk_import_csv),
    "feat_02_bulk_export":            _wrap(lambda s: s.data.bulk_export_csv),
    "feat_03_edit_record":            _wrap(lambda s: s.data.edit_attendance_row),
    "feat_04_undo_delete":            _wrap(lambda s: s.data.undo_recent_deletes),
    "feat_05_merge_duplicates":       _wrap(lambda s: s.data.merge_duplicate_rows),
    "feat_06_correction_audit":       _wrap(lambda s: s.data.show_correction_audit),
    "feat_07_lock_past_dates":        _wrap(lambda s: s.data.lock_past_dates),
    "feat_08_bulk_approve_reject":    _wrap(lambda s: s.requests.bulk_approve_or_reject),
    "feat_09_request_attachment":     _wrap(lambda s: s.requests.attach_document_to_request),
    "feat_10_expire_pending":         _wrap(lambda s: s.requests.expire_old_pending_requests),
    "feat_11_delegate_approval":      _wrap(lambda s: s.requests.delegate_approval_authority),
    "feat_12_request_comment_thread": _wrap(lambda s: s.requests.show_request_comment_thread),
    "feat_13_request_templates":      _wrap(lambda s: s.requests.manage_request_templates),
    "feat_14_module_policy":          _wrap(lambda s: s.policy.edit_module_policy),
    "feat_15_default_policy":         _wrap(lambda s: s.policy.set_default_min_percent),
    "feat_16_status_vocabulary":      _wrap(lambda s: s.policy.manage_status_vocabulary),
    "feat_17_auto_excuse_rules":      _wrap(lambda s: s.policy.add_auto_excuse_rule),
    "feat_18_grace_period":           _wrap(lambda s: s.policy.set_global_grace_minutes),
    "feat_19_at_risk":                _wrap(lambda s: s.reporting.show_at_risk_students),
    "feat_20_module_health":          _wrap(lambda s: s.reporting.show_module_health),
    "feat_21_cohort_compare":         _wrap(lambda s: s.reporting.compare_cohorts),
    "feat_22_trend_chart":            _wrap(lambda s: s.reporting.show_weekly_trend),
    "feat_23_term_compare":           _wrap(lambda s: s.reporting.compare_terms),
    "feat_24_schedule_report":        _wrap(lambda s: s.reporting.schedule_recurring_report),
    "feat_25_consecutive_absences":   _wrap(lambda s: s.reporting.show_top_absentees),
    "feat_26_heatmap":                _wrap(lambda s: s.reporting.show_dayofweek_heatmap),
    "feat_27_threshold_alerts":       _wrap(lambda s: s.notifications.create_threshold_alerts),
    "feat_28_parent_notifications":   _wrap(lambda s: s.notifications.notify_parents_for_student),
    "feat_29_bulk_announcement":      _wrap(lambda s: s.notifications.post_bulk_announcement),
    "feat_30_sms_fallback":           _wrap(lambda s: s.notifications.queue_sms_fallback),
    "feat_31_calendar_link":          _wrap(lambda s: s.integrations.show_upcoming_calendar_events),
    "feat_32_schedule_sessions":      _wrap(lambda s: s.integrations.show_module_schedule),
    "feat_33_risk_feed":              _wrap(lambda s: s.integrations.feed_student_risk_assessment),
    "feat_34_grade_link":             _wrap(lambda s: s.integrations.show_grade_penalty_candidates),
    "feat_35_wellbeing_link":         _wrap(lambda s: s.integrations.show_absences_vs_mood),
    "feat_36_disciplinary_action":    _wrap(lambda s: s.integrations.raise_disciplinary_action),
    "feat_37_finance_link":           _wrap(lambda s: s.integrations.show_scholarship_attendance_check),
    "feat_38_bulk_mark_present":      _wrap(lambda s: s.bulk.mark_module_all_present),
    "feat_39_copy_previous_day":      _wrap(lambda s: s.bulk.copy_previous_day_roll),
    "feat_40_recurring_absence":      _wrap(lambda s: s.bulk.create_recurring_absence),
    "feat_41_reassign_records":       _wrap(lambda s: s.bulk.reassign_records_on_transfer),
    "feat_42_permission_matrix":      _wrap(lambda s: s.security.show_permission_matrix),
    "feat_43_full_audit_trail":       _wrap(lambda s: s.security.show_full_audit_trail),
    "feat_44_impersonate":            _wrap(lambda s: s.security.impersonate_user_readonly),
    "feat_45_retention_purge":        _wrap(lambda s: s.security.purge_per_retention_policy),
    "feat_46_gdpr_export":            _wrap(lambda s: s.security.gdpr_subject_export),
    "feat_47_orphan_rows":            _wrap(lambda s: s.diagnostics.show_orphan_attendance_rows),
    "feat_48_missing_sessions":       _wrap(lambda s: s.diagnostics.show_modules_without_attendance),
    "feat_49_enrollment_mismatch":    _wrap(lambda s: s.diagnostics.show_enrollment_mismatches),
    "feat_50_db_health":              _wrap(lambda s: s.diagnostics.show_database_health),
}
globals().update(_LEGACY_ALIASES)

