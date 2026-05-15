"""Tkinter views for Sixth Form Bulk Operations.

Notebook tabs:
* Run         — pick operation, pick students, configure parameters,
                preview (dry run) and execute.
* Job log     — recent runs with view-details / delete.
* Schedules   — manage recurring bulk-job definitions.
* Logs        — structured log entries persisted to the bulk DB.
* Summary     — totals + by-operation counts.
"""

from __future__ import annotations

import json
import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, simpledialog, ttk
from typing import Callable
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.students.bulk_operations import (
    bulk_operations as data,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.sixthform_system.modules.domain.students.bulk_operations.bulk_operations import (
    BulkResult,
    Job,
    OPERATIONS,
    SAFE_STUDENT_FIELDS,
    ValidationError,
)

logger = logging.getLogger(__name__)

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


def open_bulk_operations_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Bulk Operations — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    RunTab(nb)
    JobsTab(nb)
    SchedulesTab(nb)
    LogsTab(nb)
    SummaryTab(nb)


def _today() -> str:
    return _date.today().isoformat()


# ══ Run tab ════════════════════════════════════════════════════════

class RunTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Run")
        self._build()
        self._show_op("log_behaviour")

    def _build(self) -> None:
        pane = ttk.Panedwindow(self.frame, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        # ── Left: student picker ──────────────────────────────────
        left = ttk.LabelFrame(pane, text="Target students", padding=6)
        pane.add(left, weight=2)
        sel_bar = ttk.Frame(left)
        sel_bar.pack(fill="x", pady=(0, 4))
        ttk.Button(sel_bar, text="Select all",
                    command=self._select_all).pack(side="left")
        ttk.Button(sel_bar, text="Clear",
                    command=self._select_none).pack(side="left", padx=4)
        ttk.Label(sel_bar, text="Filter:").pack(side="left", padx=(8, 2))
        self.filter_e = ttk.Entry(sel_bar, width=14)
        self.filter_e.pack(side="left")
        self.filter_e.bind("<KeyRelease>", lambda _e: self._apply_filter())

        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)
        cols = ("sid", "name")
        self.students_tree = ttk.Treeview(list_frame, columns=cols,
                                             show="headings",
                                             selectmode="extended")
        self.students_tree.heading("sid", text="ID")
        self.students_tree.heading("name", text="Name")
        self.students_tree.column("sid", width=80, anchor="w")
        self.students_tree.column("name", width=200, anchor="w")
        vs = ttk.Scrollbar(list_frame, orient="vertical",
                            command=self.students_tree.yview)
        self.students_tree.configure(yscrollcommand=vs.set)
        self.students_tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.count_var = tk.StringVar(value="0 selected")
        ttk.Label(left, textvariable=self.count_var,
                   anchor="w").pack(fill="x", pady=(4, 0))
        self.students_tree.bind(
            "<<TreeviewSelect>>", lambda _e: self._update_count())

        self._all_students: list = []
        self._reload_students()

        # ── Right: operation picker + params ──────────────────────
        right = ttk.Frame(pane)
        pane.add(right, weight=3)

        op_bar = ttk.Frame(right)
        op_bar.pack(fill="x", pady=(0, 6))
        ttk.Label(op_bar, text="Operation:").pack(side="left")
        self.op_cb = ttk.Combobox(
            op_bar,
            values=[OPERATION_LABELS[o] for o in OPERATIONS],
            state="readonly", width=28)
        self.op_cb.current(0)
        self.op_cb.bind("<<ComboboxSelected>>",
                          lambda _e: self._on_op_change())
        self.op_cb.pack(side="left", padx=(4, 0))

        self.params_frame = ttk.LabelFrame(right, text="Parameters",
                                              padding=8)
        self.params_frame.pack(fill="both", expand=True)

        run_bar = ttk.Frame(right)
        run_bar.pack(fill="x", pady=(6, 0))
        self.dry_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(run_bar, text="Dry run (preview only)",
                          variable=self.dry_var).pack(side="left")
        ttk.Button(run_bar, text="Preview with diff",
                    command=self._preview).pack(side="left", padx=(8, 4))
        ttk.Button(run_bar, text="Run",
                    command=self._run).pack(side="left", padx=4)

        self.result_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.result_var,
                   foreground="#444",
                   anchor="w", wraplength=700,
                   justify="left").pack(fill="x", pady=(8, 0))

    def _reload_students(self) -> None:
        for i in self.students_tree.get_children():
            self.students_tree.delete(i)
        self._all_students = sorted(student_data.list_students(),
                                       key=lambda s: s.student_id)
        for s in self._all_students:
            self.students_tree.insert("", "end", iid=s.student_id,
                                          values=(s.student_id, s.full_name))
        self._update_count()

    def _apply_filter(self) -> None:
        token = self.filter_e.get().strip().lower()
        for i in self.students_tree.get_children():
            self.students_tree.delete(i)
        for s in self._all_students:
            if (not token
                    or token in s.student_id.lower()
                    or token in s.full_name.lower()):
                self.students_tree.insert("", "end", iid=s.student_id,
                                              values=(s.student_id,
                                                       s.full_name))
        self._update_count()

    def _select_all(self) -> None:
        self.students_tree.selection_set(
            self.students_tree.get_children())
        self._update_count()

    def _select_none(self) -> None:
        self.students_tree.selection_remove(
            self.students_tree.selection())
        self._update_count()

    def _update_count(self) -> None:
        n = len(self.students_tree.selection())
        self.count_var.set(f"{n} selected")

    def _selected_ids(self) -> list[str]:
        return list(self.students_tree.selection())

    # ── Operation parameter forms ─────────────────────────────────
    def _on_op_change(self) -> None:
        label = self.op_cb.get()
        op_key = next((k for k, v in OPERATION_LABELS.items()
                        if v == label), OPERATIONS[0])
        self._show_op(op_key)

    def _show_op(self, op_key: str) -> None:
        self._op_key = op_key
        for w in self.params_frame.winfo_children():
            w.destroy()
        builder = {
            "log_behaviour":         self._build_behaviour_form,
            "add_accommodation":     self._build_accommodation_form,
            "update_student":        self._build_update_form,
            "message":               self._build_message_form,
            "archive_to_alumni":     self._build_archive_form,
            "mark_attendance":       self._build_mark_attendance_form,
            "authorise_absences":    self._build_authorise_form,
            "apply_lateness":        self._build_lateness_form,
            "import_attendance_csv": self._build_import_csv_form,
            "recalc_attendance":     self._build_recalc_form,
            "flag_low_attendance":   self._build_flag_low_form,
            "signoff_register":      self._build_signoff_form,
            "enrol":                     self._build_enrol_form,
            "move_class_group":          self._build_move_group_form,
            "assign_predicted_grades":   self._build_predicted_form,
            "import_assessment_marks":   self._build_import_marks_form,
            "recalc_grade_reports":      self._build_recalc_grades_form,
            "export_progress_reports":   self._build_export_progress_form,
            "publish_report_cards":      self._build_publish_form,
            "apply_grade_boundaries":    self._build_grade_boundaries_form,
            "issue_detentions":          self._build_detention_form,
            "award_merits":              self._build_merits_form,
            "escalate_behaviour":        self._build_escalate_form,
            "safeguarding_flag":         self._build_safeguarding_form,
            "assign_mentors":            self._build_mentors_form,
            "reset_behaviour_points":    self._build_reset_points_form,
            "send_sms":                  self._build_sms_form,
            "send_letters":              self._build_letters_form,
            "meeting_invites":           self._build_meeting_form,
            "ucas_reference_reminders":  self._build_ucas_form,
            "password_reset_emails":     self._build_pwreset_form,
            "schedule_message":          self._build_schedule_msg_form,
            "bursary_award":             self._build_bursary_form,
            "raise_invoices":            self._build_invoice_form,
            "fee_discount":              self._build_discount_form,
            "import_payments":           self._build_import_payments_form,
            "financial_statements":      self._build_statements_form,
            "exam_entries":              self._build_exam_entries_form,
            "exam_access_arrangements":  self._build_exam_access_form,
            "exam_timetables":           self._build_exam_timetables_form,
            "ucas_export_predictions":   self._build_ucas_export_form,
            "ucas_update_status":        self._build_ucas_status_form,
            "promote_year_group":        self._build_promote_form,
            "mark_leavers":              self._build_leavers_form,
            "reinstate_alumni":          self._build_reinstate_form,
            "gdpr_redact":               self._build_gdpr_form,
            "export_student_records":    self._build_export_records_form,
            "anonymise_alumni":          self._build_anonymise_form,
            "assign_inventory":          self._build_inventory_form,
            "upload_photos":             self._build_photos_form,
            "import_contacts_csv":       self._build_contacts_csv_form,
            "force_password_reset":      self._build_pwreset_form2,
            "undo_job":                  self._build_undo_form,
            "schedule_recurring":        self._build_schedule_form,
            "mark_holiday":              self._build_mark_holiday_form,
            "clear_attendance":          self._build_clear_attendance_form,
            "late_to_unauth":            self._build_late_unauth_form,
            "attendance_letters":        self._build_attendance_letters_form,
            "punctuality_report":        self._build_punctuality_form,
            "register_closure":          self._build_register_closure_form,
            "assign_subjects":           self._build_assign_subjects_form,
            "withdraw_subjects":         self._build_withdraw_subjects_form,
            "set_teaching_set":          self._build_set_set_form,
            "import_timetable_csv":      self._build_import_tt_csv_form,
        }[op_key]
        builder()
        # Sync the dropdown if needed
        target_label = OPERATION_LABELS[op_key]
        if self.op_cb.get() != target_label:
            self.op_cb.set(target_label)

    def _entry(self, parent: tk.Widget, row: int, label: str,
                default: str = "", *, width: int = 30) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(row=row, column=0,
                                              sticky="e", pady=3)
        e = ttk.Entry(parent, width=width)
        if default:
            e.insert(0, default)
        e.grid(row=row, column=1, sticky="w", padx=6)
        return e

    def _combo(self, parent: tk.Widget, row: int, label: str,
                values: list[str], default: str = "",
                *, readonly: bool = True,
                width: int = 22) -> ttk.Combobox:
        ttk.Label(parent, text=label).grid(row=row, column=0,
                                              sticky="e", pady=3)
        cb = ttk.Combobox(
            parent, values=values,
            state="readonly" if readonly else "normal", width=width)
        cb.set(default)
        cb.grid(row=row, column=1, sticky="w", padx=6)
        return cb

    def _build_behaviour_form(self) -> None:
        f = self.params_frame
        self.p_type   = self._combo(f, 0, "Type:",
                                       ["Positive", "Negative"],
                                       default="Positive")
        self.p_cat    = self._entry(f, 1, "Category:")
        self.p_desc   = self._entry(f, 2, "Description:")
        self.p_date   = self._entry(f, 3, "Date:", _today(), width=14)
        self.p_sev    = self._combo(f, 4, "Severity:",
                                       ["", "Low", "Medium", "High"],
                                       default="")
        self.p_loc    = self._entry(f, 5, "Location:")
        self.p_by     = self._entry(f, 6, "Recorded by:")

    def _build_accommodation_form(self) -> None:
        f = self.params_frame
        self.p_name   = self._entry(f, 0, "Name:")
        self.p_cat    = self._entry(f, 1, "Category:", "Exam Access")
        self.p_desc   = self._entry(f, 2, "Description:")
        self.p_status = self._entry(f, 3, "Status:", "Active", width=14)
        self.p_start  = self._entry(f, 4, "Start date:", _today(), width=14)
        self.p_end    = self._entry(f, 5, "End date:", width=14)
        self.p_appby  = self._entry(f, 6, "Approved by:")
        self.p_appdate = self._entry(f, 7, "Approved date:", width=14)

    def _build_update_form(self) -> None:
        f = self.params_frame
        self.p_field = self._combo(f, 0, "Field:",
                                      list(SAFE_STUDENT_FIELDS),
                                      default=SAFE_STUDENT_FIELDS[0])
        self.p_value = self._entry(f, 1, "New value:")

    def _build_message_form(self) -> None:
        f = self.params_frame
        self.p_subject = self._entry(f, 0, "Subject:")
        ttk.Label(f, text="Body:").grid(row=1, column=0,
                                           sticky="ne", pady=3)
        self.p_body = tk.Text(f, width=44, height=8)
        self.p_body.grid(row=1, column=1, sticky="w", padx=6)
        self.p_channel = self._combo(
            f, 2, "Channel:",
            ["Email", "SMS", "Letter", "Phone Call",
             "In Person", "System"], default="Email")
        self.p_msg_cat = self._entry(f, 3, "Category:", "General")
        self.p_pri = self._combo(f, 4, "Priority:",
                                    ["Low", "Normal", "High", "Urgent"],
                                    default="Normal")
        self.p_status = self._combo(f, 5, "Status:",
                                       ["Draft", "Queued", "Sent"],
                                       default="Sent")

    def _build_archive_form(self) -> None:
        from education_system.sixthform_system.modules.domain.students.alumni.alumni import (
            DESTINATION_TYPES, LEAVING_REASONS, DEFAULT_DESTINATION,
            DEFAULT_LEAVING_REASON,
        )
        f = self.params_frame
        self.p_year   = self._entry(f, 0, "Leaving year:",
                                       str(_date.today().year), width=8)
        self.p_date   = self._entry(f, 1, "Leaving date:",
                                       _today(), width=14)
        self.p_reason = self._combo(f, 2, "Leaving reason:",
                                       list(LEAVING_REASONS),
                                       default=DEFAULT_LEAVING_REASON)
        self.p_dest   = self._combo(f, 3, "Destination:",
                                       list(DESTINATION_TYPES),
                                       default=DEFAULT_DESTINATION)
        self.p_delete = tk.BooleanVar(value=False)
        ttk.Checkbutton(f,
                          text="Also delete student rows "
                                "(cascade-removes history)",
                          variable=self.p_delete).grid(
            row=4, column=1, sticky="w", padx=6, pady=3)

    # ── Attendance / slot helpers ─────────────────────────────────
    def _slot_options(self) -> list[tuple[int, str]]:
        from education_system.sixthform_system.modules.domain.academics.timetable import (
            timetable as _tt,
        )
        out: list[tuple[int, str]] = []
        for s in _tt.list_slots():
            label = (f"#{s.slot_id}  {_tt.day_name(s.day)} P{s.period}  "
                     f"group={s.group_id}  room={s.room or '—'}")
            out.append((s.slot_id, label))
        return out

    def _slot_combo(self, parent: tk.Widget, row: int,
                     label: str) -> ttk.Combobox:
        opts = self._slot_options()
        self._slot_label_to_id = {lbl: sid for sid, lbl in opts}
        labels = [lbl for _sid, lbl in opts]
        ttk.Label(parent, text=label).grid(row=row, column=0,
                                              sticky="e", pady=3)
        cb = ttk.Combobox(parent, values=labels,
                           state="readonly", width=46)
        if labels:
            cb.current(0)
        cb.grid(row=row, column=1, sticky="w", padx=6)
        return cb

    def _build_mark_attendance_form(self) -> None:
        f = self.params_frame
        self.p_slot = self._slot_combo(f, 0, "Slot:")
        self.p_date = self._entry(f, 1, "Date:", _today(), width=14)
        self.p_status = self._combo(
            f, 2, "Status:",
            ["Present", "Late", "Absent", "Authorised"],
            default="Present")
        self.p_minutes = self._entry(f, 3, "Minutes late:", width=8)
        self.p_notes = self._entry(f, 4, "Notes:")

    def _build_authorise_form(self) -> None:
        f = self.params_frame
        self.p_date_from = self._entry(f, 0, "From date:", width=14)
        self.p_date_to = self._entry(f, 1, "To date:",
                                       _today(), width=14)
        self.p_target = self._combo(f, 2, "Target status:",
                                       ["Authorised", "Absent"],
                                       default="Authorised")
        self.p_reason = self._entry(f, 3, "Reason / code:")

    def _build_lateness_form(self) -> None:
        f = self.params_frame
        self.p_slot = self._slot_combo(f, 0, "Slot:")
        self.p_date = self._entry(f, 1, "Date:", _today(), width=14)
        self.p_minutes = self._entry(f, 2, "Minutes late:", "5", width=8)
        self.p_threshold = self._entry(
            f, 3, "Auto-log behaviour at ≥ min (blank=off):", width=8)
        self.p_by = self._entry(f, 4, "Behaviour recorded-by:")

    def _build_import_csv_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text=("Required columns: student_id, slot_id, "
                            "date, status\n"
                            "Optional columns: minutes_late, notes"),
                   foreground="#555").grid(row=0, column=0, columnspan=3,
                                             sticky="w", pady=(0, 6))
        self.p_csv = self._entry(f, 1, "CSV path:", width=46)
        from tkinter import filedialog

        def _browse() -> None:
            path = filedialog.askopenfilename(
                title="Pick attendance CSV",
                filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
            if path:
                self.p_csv.delete(0, "end")
                self.p_csv.insert(0, path)

        ttk.Button(f, text="Browse…", command=_browse).grid(
            row=1, column=2, sticky="w", padx=4)

    def _build_recalc_form(self) -> None:
        f = self.params_frame
        self.p_date_from = self._entry(f, 0,
                                          "From date (blank=all):",
                                          width=14)
        self.p_date_to = self._entry(f, 1,
                                        "To date (blank=all):", width=14)

    def _build_flag_low_form(self) -> None:
        f = self.params_frame
        self.p_threshold = self._entry(f, 0, "Threshold %:",
                                          "90", width=8)
        self.p_window = self._entry(f, 1, "Window (days):",
                                       "28", width=8)
        self.p_level = self._combo(f, 2, "Level:",
                                      ["Low", "Medium", "High", "Critical"],
                                      default="Medium")
        self.p_reason = self._entry(f, 3, "Reason:",
                                       "Low overall attendance")
        self.p_by = self._entry(f, 4, "Raised by:")
        self.p_skip_open = tk.BooleanVar(value=True)
        ttk.Checkbutton(f,
                          text="Skip students who already have an open "
                                "concern",
                          variable=self.p_skip_open).grid(
            row=5, column=1, sticky="w", padx=6, pady=3)

    def _build_signoff_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text="Slots:").grid(row=0, column=0,
                                            sticky="ne", pady=3)
        list_frame = ttk.Frame(f)
        list_frame.grid(row=0, column=1, sticky="w", padx=6, pady=3)
        opts = self._slot_options()
        self._signoff_slot_map: dict[str, int] = {}
        self.p_slots_lb = tk.Listbox(list_frame, selectmode="extended",
                                       height=8, width=52,
                                       exportselection=False)
        for sid, lbl in opts:
            iid = self.p_slots_lb.size()
            self.p_slots_lb.insert("end", lbl)
            self._signoff_slot_map[str(iid)] = sid
        vs = ttk.Scrollbar(list_frame, orient="vertical",
                            command=self.p_slots_lb.yview)
        self.p_slots_lb.configure(yscrollcommand=vs.set)
        self.p_slots_lb.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.p_date = self._entry(f, 1, "Date:", _today(), width=14)
        self.p_default = self._combo(f, 2, "Fill blanks as:",
                                        ["Present", "Absent", "Authorised"],
                                        default="Present")

    # ── Academic / pastoral form builders ─────────────────────────
    def _group_options(self) -> list[tuple[int, str]]:
        from education_system.sixthform_system.modules.domain.academics.class_groups import (
            class_groups as _cg,
        )
        return [(g.group_id,
                 f"#{g.group_id} {g.group_name}"
                 f" ({getattr(g, 'subject_name', '—') or '—'})")
                for g in _cg.list_groups()]

    def _group_combo(self, parent: tk.Widget, row: int,
                       label: str, *, allow_blank: bool = True
                       ) -> ttk.Combobox:
        opts = self._group_options()
        attr = f"_grp_map_{row}"
        labels = ([""] if allow_blank else []) + [lbl for _, lbl in opts]
        mapping: dict[str, int | None] = {"": None}
        for gid, lbl in opts:
            mapping[lbl] = gid
        setattr(self, attr, mapping)
        ttk.Label(parent, text=label).grid(row=row, column=0,
                                              sticky="e", pady=3)
        cb = ttk.Combobox(parent, values=labels, state="readonly",
                           width=40)
        if labels:
            cb.current(0)
        cb.grid(row=row, column=1, sticky="w", padx=6)
        cb._map_attr = attr  # type: ignore[attr-defined]
        return cb

    def _build_enrol_form(self) -> None:
        f = self.params_frame
        self.p_year = self._entry(f, 0, "Academic year:", width=12)
        self.p_yg = self._combo(f, 1, "Year group:",
                                   ["12", "13"], default="12")
        self.p_tutor = self._entry(f, 2, "Tutor group:")
        self.p_start = self._entry(f, 3, "Start date:",
                                       _today(), width=14)
        self.p_status = self._combo(
            f, 4, "Status:",
            ["Enrolled", "Pending", "Withdrawn", "Completed"],
            default="Enrolled")
        self.p_notes = self._entry(f, 5, "Notes:")

    def _build_move_group_form(self) -> None:
        f = self.params_frame
        self.p_from = self._group_combo(f, 0, "From group:")
        self.p_to = self._group_combo(f, 1, "To group:")

    def _build_predicted_form(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.subjects import (
            subjects as _sub,
        )
        names = _sub.get_active_names() or ["(none)"]
        f = self.params_frame
        self.p_subject = self._combo(f, 0, "Subject:", names,
                                        default=names[0])
        self.p_from_baseline = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            f, text="Derive grade from baseline",
            variable=self.p_from_baseline).grid(
            row=1, column=1, sticky="w", padx=6, pady=3)
        self.p_grade = self._combo(
            f, 2, "Grade (fixed):",
            ["", "A*", "A", "B", "C", "D", "E", "U"], default="C")
        self.p_conf = self._combo(f, 3, "Confidence:",
                                     ["High", "Medium", "Low"],
                                     default="Medium")
        self.p_by = self._entry(f, 4, "Predicted by:")

    def _build_import_marks_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text=("Required: student_id, subject_name, "
                            "assessment_type,\n            "
                            "assessment_date, raw_score, max_score"),
                   foreground="#555").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.p_csv = self._entry(f, 1, "CSV path:", width=46)
        from tkinter import filedialog

        def _browse() -> None:
            path = filedialog.askopenfilename(
                title="Pick marks CSV",
                filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
            if path:
                self.p_csv.delete(0, "end")
                self.p_csv.insert(0, path)

        ttk.Button(f, text="Browse…", command=_browse).grid(
            row=1, column=2, sticky="w", padx=4)

    def _build_recalc_grades_form(self) -> None:
        ttk.Label(self.params_frame,
                   text="No parameters — recomputes per-student grade "
                         "reports for selected students.").pack(
            anchor="w", pady=8)

    def _build_export_progress_form(self) -> None:
        f = self.params_frame
        self.p_outdir = self._entry(f, 0, "Output dir:", width=46)
        from tkinter import filedialog

        def _browse() -> None:
            path = filedialog.askdirectory(
                title="Pick output directory")
            if path:
                self.p_outdir.delete(0, "end")
                self.p_outdir.insert(0, path)

        ttk.Button(f, text="Browse…", command=_browse).grid(
            row=0, column=2, sticky="w", padx=4)

    def _build_publish_form(self) -> None:
        f = self.params_frame
        self.p_period = self._entry(f, 0, "Period:", width=18)
        self.p_publish = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            f, text="Publish (uncheck to unpublish)",
            variable=self.p_publish).grid(
            row=1, column=1, sticky="w", padx=6, pady=3)
        self.p_by = self._entry(f, 2, "Published by:")

    def _build_grade_boundaries_form(self) -> None:
        f = self.params_frame
        self.p_assn = self._entry(
            f, 0, "Assignment ids (comma):", width=30)
        self.p_a_star = self._entry(f, 1, "A* threshold:", width=8)
        self.p_a = self._entry(f, 2, "A threshold:", width=8)
        self.p_b = self._entry(f, 3, "B threshold:", width=8)
        self.p_c = self._entry(f, 4, "C threshold:", width=8)
        self.p_d = self._entry(f, 5, "D threshold:", width=8)
        self.p_e = self._entry(f, 6, "E threshold:", width=8)

    def _build_detention_form(self) -> None:
        f = self.params_frame
        self.p_date = self._entry(f, 0, "Date:", _today(), width=14)
        self.p_reason = self._entry(f, 1, "Reason:")
        self.p_duration = self._entry(f, 2, "Duration (min):",
                                          "30", width=8)
        self.p_room = self._entry(f, 3, "Room:")
        self.p_severity = self._combo(f, 4, "Severity:",
                                          ["Low", "Medium", "High"],
                                          default="Low")
        self.p_by = self._entry(f, 5, "Recorded by:")

    def _build_merits_form(self) -> None:
        f = self.params_frame
        self.p_date = self._entry(f, 0, "Date:", _today(), width=14)
        self.p_category = self._combo(
            f, 1, "Category:",
            ["Excellent Work", "Participation", "Helpfulness",
             "Leadership", "Improvement", "Achievement",
             "Attendance", "Effort", "Community Contribution",
             "Other"], default="Achievement")
        self.p_desc = self._entry(f, 2, "Description:")
        self.p_points = self._entry(f, 3, "Points:", "5", width=8)
        self.p_by = self._entry(f, 4, "Recorded by:")

    def _build_escalate_form(self) -> None:
        f = self.params_frame
        self.p_date = self._entry(f, 0, "Date:", _today(), width=14)
        self.p_reason = self._entry(f, 1, "Reason:")
        self.p_to = self._entry(f, 2, "Escalate to:", "Senior Tutor")
        self.p_followup = self._entry(f, 3, "Follow-up date:", width=14)
        self.p_by = self._entry(f, 4, "Recorded by:")

    def _build_safeguarding_form(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.safeguarding.safeguarding import (
            CONCERN_TYPES, CATEGORIES, RISK_LEVELS,
        )
        f = self.params_frame
        self.p_cdate = self._entry(f, 0, "Concern date:",
                                       _today(), width=14)
        self.p_rdate = self._entry(f, 1, "Reported date:",
                                       _today(), width=14)
        self.p_ctype = self._combo(f, 2, "Concern type:",
                                       list(CONCERN_TYPES),
                                       default=CONCERN_TYPES[0])
        self.p_category = self._combo(f, 3, "Category:",
                                          list(CATEGORIES),
                                          default=CATEGORIES[0])
        self.p_risk = self._combo(f, 4, "Risk level:",
                                      list(RISK_LEVELS),
                                      default="Medium")
        self.p_by = self._entry(f, 5, "Reported by:")
        self.p_desc = self._entry(f, 6, "Description:")
        self.p_dsl = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="DSL notified",
                          variable=self.p_dsl).grid(
            row=7, column=1, sticky="w", padx=6, pady=3)
        self.p_dsl_name = self._entry(f, 8, "DSL name:")

    def _build_mentors_form(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.peer_mentoring.peer_mentoring import (
            PROGRAMMES, FREQUENCIES, DEFAULT_FREQUENCY,
        )
        f = self.params_frame
        ttk.Label(f, text="Selected students above are MENTEES.",
                   foreground="#555").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.p_mentor = self._entry(f, 1, "Mentor student id:", width=14)
        self.p_programme = self._combo(f, 2, "Programme:",
                                            list(PROGRAMMES),
                                            default=PROGRAMMES[0])
        self.p_start = self._entry(f, 3, "Start date:",
                                       _today(), width=14)
        self.p_frequency = self._combo(f, 4, "Frequency:",
                                            list(FREQUENCIES),
                                            default=DEFAULT_FREQUENCY)
        self.p_coord = self._entry(f, 5, "Coordinator:")
        self.p_planned = self._entry(f, 6, "Planned end:", width=14)
        self.p_sessions = self._entry(f, 7, "Sessions planned:",
                                          width=8)

    # ── Comms / finance / exams form builders ─────────────────────
    def _build_reset_points_form(self) -> None:
        f = self.params_frame
        self.p_date_from = self._entry(f, 0, "Window from:", width=14)
        self.p_date_to = self._entry(f, 1, "Window to:",
                                       _today(), width=14)
        self.p_reset_date = self._entry(f, 2, "Reset date:",
                                          _today(), width=14)
        self.p_note = self._entry(f, 3, "Note:", "Term reset")
        self.p_by = self._entry(f, 4, "Recorded by:")

    def _build_sms_form(self) -> None:
        f = self.params_frame
        self.p_subject = self._entry(f, 0, "Subject (audit):", "SMS")
        ttk.Label(f, text="Body:").grid(row=1, column=0,
                                            sticky="ne", pady=3)
        self.p_body = tk.Text(f, width=44, height=6)
        self.p_body.grid(row=1, column=1, sticky="w", padx=6)
        self.p_sender = self._entry(f, 2, "Sender staff id:")

    def _build_letters_form(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.letter_templates import (
            letter_templates as _lt,
        )
        templates = _lt.list_templates()
        self._template_map: dict[str, int] = {
            f"#{t.template_id}  {t.name}": t.template_id for t in templates
        }
        f = self.params_frame
        self.p_template = self._combo(
            f, 0, "Template:",
            list(self._template_map.keys()) or ["(none)"],
            default=(next(iter(self._template_map), "(none)")), width=40)
        self.p_ctx = self._entry(
            f, 1, "Extra context (k=v,...):", width=40)

    def _build_meeting_form(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.parents_evenings import (
            parents_evenings as _pe,
        )
        events = _pe.list_events()
        self._event_map: dict[str, int] = {
            f"#{e.event_id}  {e.event_date}  {e.title}": e.event_id
            for e in events
        }
        f = self.params_frame
        self.p_event = self._combo(
            f, 0, "Event:",
            list(self._event_map.keys()) or ["(none)"],
            default=(next(iter(self._event_map), "(none)")), width=46)
        self.p_link = self._entry(f, 1, "Booking link:", width=40)

    def _build_ucas_form(self) -> None:
        f = self.params_frame
        self.p_referee = self._entry(f, 0, "Override referee email:",
                                          width=40)
        self.p_deadline = self._entry(f, 1, "Deadline:", width=14)

    def _build_pwreset_form(self) -> None:
        f = self.params_frame
        self.p_mfa = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            f, text="MFA enrolment (instead of password reset)",
            variable=self.p_mfa).grid(
            row=0, column=1, sticky="w", padx=6, pady=3)
        self.p_url = self._entry(f, 1, "Reset URL:", width=40)

    def _build_schedule_msg_form(self) -> None:
        f = self.params_frame
        self.p_subject = self._entry(f, 0, "Subject:")
        ttk.Label(f, text="Body:").grid(row=1, column=0,
                                            sticky="ne", pady=3)
        self.p_body = tk.Text(f, width=44, height=6)
        self.p_body.grid(row=1, column=1, sticky="w", padx=6)
        self.p_send_at = self._entry(f, 2, "Send at:",
                                       width=20)
        ttk.Label(f, text="  (YYYY-MM-DD HH:MM)",
                   foreground="#555").grid(row=2, column=2, sticky="w")
        self.p_channel = self._combo(f, 3, "Channel:",
                                         ["Email", "SMS", "Letter",
                                          "Portal"], default="Email")
        self.p_msg_cat = self._entry(f, 4, "Category:", "General")
        self.p_pri = self._combo(f, 5, "Priority:",
                                     ["Low", "Normal", "High", "Urgent"],
                                     default="Normal")

    def _build_bursary_form(self) -> None:
        from education_system.sixthform_system.modules.domain.finance.bursaries.bursaries import (
            BURSARY_TYPES, ELIGIBILITY_BASES, DEFAULT_TYPE,
        )
        f = self.params_frame
        self.p_btype = self._combo(f, 0, "Bursary type:",
                                       list(BURSARY_TYPES),
                                       default=DEFAULT_TYPE)
        self.p_amount = self._entry(f, 1, "Amount (£):", width=10)
        self.p_year = self._entry(f, 2, "Academic year:", width=10)
        self.p_basis = self._combo(f, 3, "Eligibility basis:",
                                       [""] + list(ELIGIBILITY_BASES),
                                       default="")
        self.p_note = self._entry(f, 4, "Decision note:")
        self.p_by = self._entry(f, 5, "Assessed by:")

    def _build_invoice_form(self) -> None:
        from education_system.sixthform_system.modules.domain.finance.fees.fees import (
            CATEGORIES, DEFAULT_CATEGORY,
        )
        f = self.params_frame
        self.p_desc = self._entry(f, 0, "Description:")
        self.p_cat = self._combo(f, 1, "Category:", list(CATEGORIES),
                                     default=DEFAULT_CATEGORY)
        self.p_amount = self._entry(f, 2, "Amount (£):", width=10)
        self.p_issued = self._entry(f, 3, "Issued date:",
                                        _today(), width=14)
        self.p_due = self._entry(f, 4, "Due date:", width=14)
        self.p_year = self._entry(f, 5, "Academic year:", width=10)

    def _build_discount_form(self) -> None:
        from education_system.sixthform_system.modules.domain.finance.fees.fees import (
            CATEGORIES, DEFAULT_CATEGORY,
        )
        f = self.params_frame
        self.p_desc = self._entry(f, 0, "Description:")
        self.p_amount = self._entry(
            f, 1, "Discount £ (positive):", width=10)
        self.p_cat = self._combo(f, 2, "Category:", list(CATEGORIES),
                                     default=DEFAULT_CATEGORY)
        self.p_issued = self._entry(f, 3, "Issued date:",
                                        _today(), width=14)
        self.p_year = self._entry(f, 4, "Academic year:", width=10)

    def _build_import_payments_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text=("Required: fee_id, amount, paid_on, method\n"
                            "Optional: reference, notes"),
                   foreground="#555").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.p_csv = self._entry(f, 1, "CSV path:", width=46)
        from tkinter import filedialog

        def _browse() -> None:
            path = filedialog.askopenfilename(
                title="Pick payments CSV",
                filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
            if path:
                self.p_csv.delete(0, "end")
                self.p_csv.insert(0, path)

        ttk.Button(f, text="Browse…", command=_browse).grid(
            row=1, column=2, sticky="w", padx=4)

    def _build_statements_form(self) -> None:
        f = self.params_frame
        self.p_outdir = self._entry(f, 0, "Output dir:", width=46)
        self.p_year = self._entry(f, 1, "Academic year (filter):",
                                      width=10)
        from tkinter import filedialog

        def _browse() -> None:
            path = filedialog.askdirectory(
                title="Pick output directory")
            if path:
                self.p_outdir.delete(0, "end")
                self.p_outdir.insert(0, path)

        ttk.Button(f, text="Browse…", command=_browse).grid(
            row=0, column=2, sticky="w", padx=4)

    def _build_exam_entries_form(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.subjects import (
            subjects as _sub,
        )
        from education_system.sixthform_system.modules.domain.assessment.exam_entries.exam_entries import (
            SEASONS, DEFAULT_SEASON, TIERS,
        )
        names = _sub.get_active_names() or ["(none)"]
        f = self.params_frame
        self.p_subject = self._combo(f, 0, "Subject:", names,
                                         default=names[0])
        self.p_board = self._entry(f, 1, "Exam board:", width=14)
        self.p_code = self._entry(f, 2, "Paper code:", width=14)
        self.p_season = self._combo(f, 3, "Season:", list(SEASONS),
                                        default=DEFAULT_SEASON)
        self.p_year = self._entry(f, 4, "Year:",
                                       str(_date.today().year),
                                       width=8)
        self.p_tier = self._combo(f, 5, "Tier:",
                                      [""] + list(TIERS), default="")
        self.p_fee = self._entry(f, 6, "Fee (£):", width=10)
        self.p_prefix = self._entry(
            f, 7, "Candidate-no prefix:", width=14)

    def _build_exam_access_form(self) -> None:
        f = self.params_frame
        self.p_arrangement = self._combo(
            f, 0, "Arrangement:",
            ["25% Extra Time", "50% Extra Time", "Scribe", "Reader",
             "Rest Breaks", "Word Processor", "Separate Room",
             "Prompter", "Other"], default="25% Extra Time")
        self.p_desc = self._entry(f, 1, "Description:")
        self.p_start = self._entry(f, 2, "Start date:",
                                       _today(), width=14)
        self.p_end = self._entry(f, 3, "End date:", width=14)
        self.p_by = self._entry(f, 4, "Approved by:")

    def _build_exam_timetables_form(self) -> None:
        f = self.params_frame
        self.p_outdir = self._entry(f, 0, "Output dir:", width=46)
        from tkinter import filedialog

        def _browse() -> None:
            path = filedialog.askdirectory(
                title="Pick output directory")
            if path:
                self.p_outdir.delete(0, "end")
                self.p_outdir.insert(0, path)

        ttk.Button(f, text="Browse…", command=_browse).grid(
            row=0, column=2, sticky="w", padx=4)
        self.p_year = self._entry(f, 1, "Year filter:", width=8)
        self.p_season = self._entry(f, 2, "Season filter:", width=14)

    # ── Lifecycle / admin / meta form builders ────────────────────
    def _file_picker(self, parent: tk.Widget, row: int, label: str,
                       *, save: bool = False, dir_only: bool = False
                       ) -> ttk.Entry:
        from tkinter import filedialog
        ttk.Label(parent, text=label).grid(row=row, column=0,
                                              sticky="e", pady=3)
        e = ttk.Entry(parent, width=46)
        e.grid(row=row, column=1, sticky="w", padx=6)

        def _browse() -> None:
            if dir_only:
                p = filedialog.askdirectory()
            elif save:
                p = filedialog.asksaveasfilename(defaultextension=".csv")
            else:
                p = filedialog.askopenfilename()
            if p:
                e.delete(0, "end")
                e.insert(0, p)

        ttk.Button(parent, text="Browse…",
                    command=_browse).grid(row=row, column=2, padx=4)
        return e

    def _build_ucas_export_form(self) -> None:
        self.p_outpath = self._file_picker(
            self.params_frame, 0, "Output CSV:", save=True)

    def _build_ucas_status_form(self) -> None:
        from education_system.sixthform_system.modules.domain.progression.ucas.ucas import (
            APP_STATUSES,
        )
        self.p_status = self._combo(
            self.params_frame, 0, "Status:",
            list(APP_STATUSES), default=APP_STATUSES[0])

    def _build_promote_form(self) -> None:
        f = self.params_frame
        self.p_year = self._entry(f, 0, "New academic year:",
                                       width=14)
        self.p_bump = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Bump year_group +1",
                          variable=self.p_bump).grid(
            row=1, column=1, sticky="w", padx=6, pady=3)

    def _build_leavers_form(self) -> None:
        f = self.params_frame
        self.p_date = self._entry(f, 0, "Leaving date:",
                                       _today(), width=14)
        self.p_reason = self._entry(f, 1, "Leaving reason:")

    def _build_reinstate_form(self) -> None:
        self.p_ids = self._entry(
            self.params_frame, 0, "Alumni ids (comma):", width=30)

    def _build_gdpr_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text=("Blank = phone, personal_email, and "
                            "emergency_contact_*"),
                   foreground="#555").grid(row=0, column=0,
                                              columnspan=2,
                                              sticky="w", pady=(0, 4))
        self.p_fields = self._entry(
            f, 1, "Fields (comma):", width=46)

    def _build_export_records_form(self) -> None:
        self.p_outpath = self._file_picker(
            self.params_frame, 0, "Output CSV:", save=True)

    def _build_anonymise_form(self) -> None:
        self.p_ids = self._entry(
            self.params_frame, 0, "Alumni ids (comma):", width=30)

    def _build_inventory_form(self) -> None:
        f = self.params_frame
        self.p_kind = self._combo(
            f, 0, "Kind:", list(data.VALID_INVENTORY_KINDS),
            default="Locker")
        self.p_start = self._entry(f, 1, "Starting number:",
                                        "1", width=8)
        self.p_prefix = self._entry(f, 2, "Prefix:", width=12)
        self.p_pad = self._entry(f, 3, "Zero-pad digits:",
                                       "4", width=4)
        self.p_by = self._entry(f, 4, "Assigned by:")

    def _build_photos_form(self) -> None:
        f = self.params_frame
        self.p_zip = self._file_picker(f, 0, "ZIP:")
        self.p_outdir = self._file_picker(
            f, 1, "Output dir:", dir_only=True)

    def _build_contacts_csv_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text=("Required: student_id\n"
                            "Optional: phone, "
                            "emergency_contact_name/phone/relation"),
                   foreground="#555").grid(row=0, column=0, columnspan=3,
                                              sticky="w", pady=(0, 6))
        self.p_csv = self._file_picker(f, 1, "CSV:")

    def _build_pwreset_form2(self) -> None:
        f = self.params_frame
        self.p_clear = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            f, text="Clear flag (instead of setting it)",
            variable=self.p_clear).grid(row=0, column=1,
                                            sticky="w", padx=6, pady=3)
        self.p_reason = self._entry(f, 1, "Reason:")
        self.p_by = self._entry(f, 2, "Flagged by:")

    def _build_undo_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text=("Undoable: " + ", ".join(data._UNDOABLE)),
                   foreground="#555", wraplength=520,
                   justify="left").grid(row=0, column=0, columnspan=2,
                                            sticky="w", pady=(0, 6))
        self.p_jid = self._entry(f, 1, "Job id to undo:", width=10)

    def _build_schedule_form(self) -> None:
        f = self.params_frame
        self.p_name = self._entry(f, 0, "Schedule name:")
        self.p_op = self._combo(
            f, 1, "Operation:", list(data.OPERATIONS),
            default="log_behaviour", width=28)
        self.p_cron = self._entry(f, 2,
                                       "Cron (e.g. 0 9 * * 1):",
                                       width=20)
        self.p_next = self._entry(f, 3,
                                       "First run (YYYY-MM-DD HH:MM):",
                                       width=20)
        self.p_params = self._entry(
            f, 4, "Parameters (k=v,...):", width=40)
        self.p_by = self._entry(f, 5, "Created by:")

    # ── Items 1–10 forms ──────────────────────────────────────────

    def _build_mark_holiday_form(self) -> None:
        f = self.params_frame
        self.p_date_from = self._entry(f, 0, "From date:", width=14)
        self.p_date_to = self._entry(f, 1, "To date:", width=14)
        self.p_reason = self._entry(
            f, 2, "Reason:", "Authorised holiday", width=32)

    def _build_clear_attendance_form(self) -> None:
        f = self.params_frame
        self.p_date_from = self._entry(f, 0, "From date:", width=14)
        self.p_date_to = self._entry(f, 1, "To date:", width=14)
        self.p_only_status = self._combo(
            f, 2, "Restrict to (optional):",
            ["", "Present", "Late", "Absent", "Authorised"],
            default="")

    def _build_late_unauth_form(self) -> None:
        f = self.params_frame
        self.p_date_from = self._entry(f, 0, "From date:", width=14)
        self.p_date_to = self._entry(f, 1, "To date:", width=14)
        self.p_over = self._entry(
            f, 2, "Convert when minutes_late >:", "15", width=8)
        self.p_reason = self._entry(
            f, 3, "Reason:",
            "Late > threshold — unauthorised", width=32)

    def _build_attendance_letters_form(self) -> None:
        f = self.params_frame
        self.p_window = self._entry(f, 0, "Window (days):", "28", width=8)
        self.p_s1 = self._entry(f, 1, "Stage 1 below %:", "95", width=8)
        self.p_s2 = self._entry(f, 2, "Stage 2 below %:", "90", width=8)
        self.p_s3 = self._entry(f, 3, "Stage 3 below %:", "85", width=8)
        self.p_sender = self._entry(f, 4, "Sender staff id:")
        self.p_send = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Actually send (uncheck to just queue/log)",
                         variable=self.p_send).grid(
            row=5, column=1, sticky="w", padx=6, pady=3)

    def _build_punctuality_form(self) -> None:
        f = self.params_frame
        self.p_date_from = self._entry(f, 0, "From date:", width=14)
        self.p_date_to = self._entry(
            f, 1, "To date:", _today(), width=14)
        self.p_sender = self._entry(f, 2, "Sender staff id:")

    def _build_register_closure_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text="Slots:").grid(row=0, column=0,
                                           sticky="ne", pady=3)
        list_frame = ttk.Frame(f)
        list_frame.grid(row=0, column=1, sticky="w", padx=6, pady=3)
        opts = self._slot_options()
        self._closure_slot_map: dict[str, int] = {}
        self.p_closure_slots_lb = tk.Listbox(
            list_frame, selectmode="extended",
            height=8, width=52, exportselection=False)
        for sid, lbl in opts:
            iid = self.p_closure_slots_lb.size()
            self.p_closure_slots_lb.insert("end", lbl)
            self._closure_slot_map[str(iid)] = sid
        vs = ttk.Scrollbar(list_frame, orient="vertical",
                            command=self.p_closure_slots_lb.yview)
        self.p_closure_slots_lb.configure(yscrollcommand=vs.set)
        self.p_closure_slots_lb.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.p_date_from = self._entry(f, 1, "From date:", width=14)
        self.p_date_to = self._entry(f, 2, "To date:", width=14)
        self.p_default = self._combo(
            f, 3, "Fill blanks as:",
            ["Present", "Absent", "Authorised"], default="Present")
        self.p_notes = self._entry(f, 4, "Notes:")

    def _build_assign_subjects_form(self) -> None:
        f = self.params_frame
        from education_system.sixthform_system.modules.domain.academics.subjects import (
            subjects as _sub,
        )
        try:
            names = _sub.get_active_names()
        except Exception:  # noqa: BLE001
            names = []
        ttk.Label(f, text="Subjects (max 3):").grid(
            row=0, column=0, sticky="ne", pady=3)
        list_frame = ttk.Frame(f)
        list_frame.grid(row=0, column=1, sticky="w", padx=6, pady=3)
        self.p_subjects_lb = tk.Listbox(
            list_frame, selectmode="extended", height=6, width=30,
            exportselection=False)
        for n in names:
            self.p_subjects_lb.insert("end", n)
        vs = ttk.Scrollbar(list_frame, orient="vertical",
                            command=self.p_subjects_lb.yview)
        self.p_subjects_lb.configure(yscrollcommand=vs.set)
        self.p_subjects_lb.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.p_overwrite = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            f, text="Overwrite existing slots (default: fill blanks only)",
            variable=self.p_overwrite,
        ).grid(row=1, column=1, sticky="w", padx=6, pady=3)

    def _build_withdraw_subjects_form(self) -> None:
        f = self.params_frame
        from education_system.sixthform_system.modules.domain.academics.subjects import (
            subjects as _sub,
        )
        try:
            names = _sub.get_active_names()
        except Exception:  # noqa: BLE001
            names = []
        ttk.Label(f, text="Withdraw from:").grid(
            row=0, column=0, sticky="ne", pady=3)
        list_frame = ttk.Frame(f)
        list_frame.grid(row=0, column=1, sticky="w", padx=6, pady=3)
        self.p_subjects_lb = tk.Listbox(
            list_frame, selectmode="extended", height=6, width=30,
            exportselection=False)
        for n in names:
            self.p_subjects_lb.insert("end", n)
        vs = ttk.Scrollbar(list_frame, orient="vertical",
                            command=self.p_subjects_lb.yview)
        self.p_subjects_lb.configure(yscrollcommand=vs.set)
        self.p_subjects_lb.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

    def _build_set_set_form(self) -> None:
        f = self.params_frame
        from education_system.sixthform_system.modules.domain.academics.class_groups import (
            class_groups as _cg,
        )
        try:
            groups = _cg.list_groups()
        except Exception:  # noqa: BLE001
            groups = []
        self._set_group_map: dict[str, int] = {}
        labels: list[str] = []
        for g in groups:
            lbl = f"#{g.group_id} {g.group_name}"
            self._set_group_map[lbl] = g.group_id
            labels.append(lbl)
        self.p_set_target = self._combo(
            f, 0, "Target group:", labels,
            default=(labels[0] if labels else ""), width=40)

    def _build_import_tt_csv_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text=(
            "Required columns: group_id, day, period\n"
            "Optional: start_time, end_time, room, notes"),
                  foreground="#555").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.p_csv = self._entry(f, 1, "CSV path:", width=46)
        from tkinter import filedialog

        def _browse() -> None:
            path = filedialog.askopenfilename(
                title="Pick timetable CSV",
                filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
            if path:
                self.p_csv.delete(0, "end")
                self.p_csv.insert(0, path)

        ttk.Button(f, text="Browse…", command=_browse).grid(
            row=1, column=2, sticky="w", padx=4)

    # ── Run ───────────────────────────────────────────────────────
    def _run(self, *, _preview_dialog: bool = False) -> None:
        sids = self._selected_ids()
        dry = self.dry_var.get()
        op = self._op_key
        if op not in _NO_STUDENTS_OPS and not sids:
            messagebox.showinfo("Run", "Select at least one student.")
            return
        try:
            if op == "log_behaviour":
                r = data.bulk_log_behaviour(
                    sids,
                    entry_date=self.p_date.get().strip() or _today(),
                    entry_type=self.p_type.get(),
                    category=self.p_cat.get().strip(),
                    description=self.p_desc.get().strip(),
                    severity=self.p_sev.get() or None,
                    location=self.p_loc.get().strip() or None,
                    recorded_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "add_accommodation":
                r = data.bulk_add_accommodation(
                    sids,
                    name=self.p_name.get().strip(),
                    category=self.p_cat.get().strip() or "Exam Access",
                    description=self.p_desc.get().strip() or None,
                    status=self.p_status.get().strip() or "Active",
                    start_date=self.p_start.get().strip() or None,
                    end_date=self.p_end.get().strip() or None,
                    approved_by=self.p_appby.get().strip() or None,
                    approved_date=self.p_appdate.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "update_student":
                r = data.bulk_update_student(
                    sids,
                    field=self.p_field.get(),
                    value=self.p_value.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "message":
                if not dry and not messagebox.askyesno(
                        "Send", f"Send to {len(sids)} student(s)?"):
                    return
                r = data.bulk_message(
                    sids,
                    subject=self.p_subject.get().strip(),
                    body=self.p_body.get("1.0", "end").strip(),
                    channel=self.p_channel.get(),
                    category=self.p_msg_cat.get().strip() or "General",
                    priority=self.p_pri.get(),
                    status=self.p_status.get(),
                    dry_run=dry,
                )
            elif op == "archive_to_alumni":
                delete = self.p_delete.get()
                if not dry and delete and not messagebox.askyesno(
                        "Archive",
                        f"This will DELETE {len(sids)} student row(s). "
                        "Continue?"):
                    return
                r = data.bulk_archive_to_alumni(
                    sids,
                    leaving_year=self.p_year.get().strip() or None,
                    leaving_date=self.p_date.get().strip() or None,
                    leaving_reason=self.p_reason.get() or None,
                    destination_type=self.p_dest.get(),
                    delete_students=delete,
                    dry_run=dry,
                )
            elif op == "mark_attendance":
                slot_id = self._slot_label_to_id.get(self.p_slot.get())
                if slot_id is None:
                    messagebox.showerror("Run", "Pick a slot.")
                    return
                minutes_raw = self.p_minutes.get().strip()
                minutes = int(minutes_raw) if minutes_raw else None
                r = data.bulk_mark_attendance(
                    sids, slot_id=slot_id,
                    date=self.p_date.get().strip() or _today(),
                    status=self.p_status.get(),
                    minutes_late=minutes,
                    notes=self.p_notes.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "authorise_absences":
                r = data.bulk_authorise_absences(
                    sids,
                    date_from=self.p_date_from.get().strip(),
                    date_to=self.p_date_to.get().strip() or _today(),
                    target_status=self.p_target.get(),
                    reason=self.p_reason.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "apply_lateness":
                slot_id = self._slot_label_to_id.get(self.p_slot.get())
                if slot_id is None:
                    messagebox.showerror("Run", "Pick a slot.")
                    return
                threshold_raw = self.p_threshold.get().strip()
                threshold = int(threshold_raw) if threshold_raw else None
                r = data.bulk_apply_lateness(
                    sids, slot_id=slot_id,
                    date=self.p_date.get().strip() or _today(),
                    minutes_late=int(self.p_minutes.get().strip() or 0),
                    auto_log_behaviour_over=threshold,
                    behaviour_recorded_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "import_attendance_csv":
                path = self.p_csv.get().strip()
                if not path:
                    messagebox.showerror("Run", "Pick a CSV file.")
                    return
                r = data.bulk_import_attendance_csv(path, dry_run=dry)
            elif op == "recalc_attendance":
                r = data.bulk_recalc_attendance(
                    sids,
                    date_from=self.p_date_from.get().strip() or None,
                    date_to=self.p_date_to.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "flag_low_attendance":
                r = data.bulk_flag_low_attendance(
                    sids,
                    threshold_pct=float(
                        self.p_threshold.get().strip() or "90"),
                    window_days=int(
                        self.p_window.get().strip() or "28"),
                    level=self.p_level.get(),
                    reason=(self.p_reason.get().strip()
                            or "Low overall attendance"),
                    raised_by=self.p_by.get().strip() or None,
                    skip_if_open_concern=bool(self.p_skip_open.get()),
                    dry_run=dry,
                )
            elif op == "signoff_register":
                picks = self.p_slots_lb.curselection()
                if not picks:
                    messagebox.showerror("Run", "Pick at least one slot.")
                    return
                slot_ids = [self._signoff_slot_map[str(i)] for i in picks]
                r = data.bulk_signoff_register(
                    slot_ids,
                    date=self.p_date.get().strip() or _today(),
                    default_status=self.p_default.get(),
                    dry_run=dry,
                )
            elif op == "enrol":
                r = data.bulk_enrol(
                    sids,
                    academic_year=self.p_year.get().strip(),
                    year_group=int(self.p_yg.get() or "12"),
                    tutor_group=self.p_tutor.get().strip() or None,
                    start_date=self.p_start.get().strip() or None,
                    status=self.p_status.get(),
                    notes=self.p_notes.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "move_class_group":
                from_map = getattr(self, self.p_from._map_attr)
                to_map = getattr(self, self.p_to._map_attr)
                from_id = from_map.get(self.p_from.get())
                to_id = to_map.get(self.p_to.get())
                r = data.bulk_move_class_group(
                    sids, from_group_id=from_id, to_group_id=to_id,
                    dry_run=dry,
                )
            elif op == "assign_predicted_grades":
                fb = bool(self.p_from_baseline.get())
                r = data.bulk_assign_predicted_grades(
                    sids,
                    subject=self.p_subject.get(),
                    grade=(None if fb else
                            (self.p_grade.get() or None)),
                    from_baseline=fb,
                    confidence=self.p_conf.get(),
                    predicted_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "import_assessment_marks":
                path = self.p_csv.get().strip()
                if not path:
                    messagebox.showerror("Run", "Pick a CSV file.")
                    return
                r = data.bulk_import_assessment_marks(path, dry_run=dry)
            elif op == "recalc_grade_reports":
                r = data.bulk_recalc_grade_reports(sids, dry_run=dry)
            elif op == "export_progress_reports":
                out_dir = self.p_outdir.get().strip()
                if not out_dir:
                    messagebox.showerror("Run", "Pick an output dir.")
                    return
                r = data.bulk_export_progress_reports(
                    sids, output_dir=out_dir, dry_run=dry)
            elif op == "publish_report_cards":
                r = data.bulk_publish_report_cards(
                    sids,
                    period=self.p_period.get().strip(),
                    publish=bool(self.p_publish.get()),
                    published_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "apply_grade_boundaries":
                raw_ids = self.p_assn.get().strip()
                try:
                    ids = [int(t) for t in
                            raw_ids.replace(" ", ",").split(",") if t]
                except ValueError:
                    messagebox.showerror(
                        "Run", "Assignment ids must be integers.")
                    return
                def _n(w: ttk.Entry) -> int | None:
                    s = w.get().strip()
                    return int(s) if s else None
                r = data.bulk_apply_grade_boundaries(
                    ids,
                    a_star=_n(self.p_a_star), a=_n(self.p_a),
                    b=_n(self.p_b), c=_n(self.p_c),
                    d=_n(self.p_d), e=_n(self.p_e),
                    dry_run=dry,
                )
            elif op == "issue_detentions":
                r = data.bulk_issue_detentions(
                    sids,
                    date=self.p_date.get().strip() or _today(),
                    reason=self.p_reason.get().strip(),
                    duration_minutes=int(
                        self.p_duration.get().strip() or "30"),
                    room=self.p_room.get().strip() or None,
                    severity=self.p_severity.get(),
                    recorded_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "award_merits":
                r = data.bulk_award_merits(
                    sids,
                    date=self.p_date.get().strip() or _today(),
                    category=self.p_category.get(),
                    description=self.p_desc.get().strip(),
                    points=int(self.p_points.get().strip() or "5"),
                    recorded_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "escalate_behaviour":
                r = data.bulk_escalate_behaviour(
                    sids,
                    date=self.p_date.get().strip() or _today(),
                    reason=self.p_reason.get().strip(),
                    escalate_to=(self.p_to.get().strip()
                                  or "Senior Tutor"),
                    follow_up_date=self.p_followup.get().strip() or None,
                    recorded_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "safeguarding_flag":
                dsl = bool(self.p_dsl.get())
                r = data.bulk_safeguarding_flag(
                    sids,
                    concern_date=self.p_cdate.get().strip() or _today(),
                    reported_date=self.p_rdate.get().strip() or _today(),
                    concern_type=self.p_ctype.get(),
                    category=self.p_category.get(),
                    risk_level=self.p_risk.get(),
                    reported_by=self.p_by.get().strip(),
                    description=self.p_desc.get().strip(),
                    dsl_notified=dsl,
                    dsl_name=(self.p_dsl_name.get().strip()
                                if dsl else None) or None,
                    dry_run=dry,
                )
            elif op == "reset_behaviour_points":
                r = data.bulk_reset_behaviour_points(
                    sids,
                    date_from=self.p_date_from.get().strip(),
                    date_to=self.p_date_to.get().strip() or _today(),
                    reset_date=self.p_reset_date.get().strip() or _today(),
                    note=self.p_note.get().strip() or "Term reset",
                    recorded_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "send_sms":
                r = data.bulk_send_sms(
                    sids,
                    body=self.p_body.get("1.0", "end").strip(),
                    subject=self.p_subject.get().strip() or "SMS",
                    sender_staff_id=self.p_sender.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "send_letters":
                tid = self._template_map.get(self.p_template.get())
                if tid is None:
                    messagebox.showerror("Run", "Pick a template.")
                    return
                ctx: dict[str, str] = {}
                for pair in self.p_ctx.get().split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        ctx[k.strip()] = v.strip()
                r = data.bulk_send_letters(
                    sids, template_id=tid,
                    extra_context=ctx, dry_run=dry,
                )
            elif op == "meeting_invites":
                eid = self._event_map.get(self.p_event.get())
                if eid is None:
                    messagebox.showerror("Run", "Pick an event.")
                    return
                r = data.bulk_meeting_invites(
                    sids, event_id=eid,
                    booking_link=self.p_link.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "ucas_reference_reminders":
                r = data.bulk_ucas_reference_reminders(
                    sids,
                    referee_email=self.p_referee.get().strip() or None,
                    deadline=self.p_deadline.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "password_reset_emails":
                r = data.bulk_password_reset_emails(
                    sids,
                    reset_url=self.p_url.get().strip() or None,
                    mfa_enrolment=bool(self.p_mfa.get()),
                    dry_run=dry,
                )
            elif op == "schedule_message":
                r = data.bulk_schedule_message(
                    sids,
                    subject=self.p_subject.get().strip(),
                    body=self.p_body.get("1.0", "end").strip(),
                    send_at=self.p_send_at.get().strip(),
                    channel=self.p_channel.get(),
                    category=self.p_msg_cat.get().strip() or "General",
                    priority=self.p_pri.get(),
                    dry_run=dry,
                )
            elif op == "bursary_award":
                r = data.bulk_bursary_award(
                    sids,
                    bursary_type=self.p_btype.get(),
                    amount_awarded=float(
                        self.p_amount.get().strip() or "0"),
                    academic_year=self.p_year.get().strip() or None,
                    eligibility_basis=(
                        self.p_basis.get().strip() or None),
                    decision_note=self.p_note.get().strip() or None,
                    assessed_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "raise_invoices":
                r = data.bulk_raise_invoices(
                    sids,
                    description=self.p_desc.get().strip(),
                    category=self.p_cat.get(),
                    amount=float(self.p_amount.get().strip() or "0"),
                    issued_date=self.p_issued.get().strip() or None,
                    due_date=self.p_due.get().strip() or None,
                    academic_year=self.p_year.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "fee_discount":
                r = data.bulk_fee_discount(
                    sids,
                    description=self.p_desc.get().strip(),
                    amount=float(self.p_amount.get().strip() or "0"),
                    category=self.p_cat.get(),
                    issued_date=self.p_issued.get().strip() or None,
                    academic_year=self.p_year.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "import_payments":
                path = self.p_csv.get().strip()
                if not path:
                    messagebox.showerror("Run", "Pick a CSV file.")
                    return
                r = data.bulk_import_payments(path, dry_run=dry)
            elif op == "financial_statements":
                out_dir = self.p_outdir.get().strip()
                if not out_dir:
                    messagebox.showerror("Run", "Pick an output dir.")
                    return
                r = data.bulk_financial_statements(
                    sids, output_dir=out_dir,
                    academic_year=self.p_year.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "exam_entries":
                fee_raw = self.p_fee.get().strip()
                fee = float(fee_raw) if fee_raw else None
                r = data.bulk_exam_entries(
                    sids,
                    subject=self.p_subject.get(),
                    exam_board=self.p_board.get().strip(),
                    paper_code=self.p_code.get().strip(),
                    season=self.p_season.get(),
                    year=int(self.p_year.get().strip() or
                              str(_date.today().year)),
                    tier=(self.p_tier.get().strip() or None),
                    fee=fee,
                    candidate_no_prefix=(
                        self.p_prefix.get().strip() or None),
                    dry_run=dry,
                )
            elif op == "exam_access_arrangements":
                r = data.bulk_exam_access_arrangements(
                    sids,
                    arrangement=self.p_arrangement.get(),
                    description=self.p_desc.get().strip() or None,
                    start_date=self.p_start.get().strip() or None,
                    end_date=self.p_end.get().strip() or None,
                    approved_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "exam_timetables":
                out_dir = self.p_outdir.get().strip()
                if not out_dir:
                    messagebox.showerror("Run", "Pick an output dir.")
                    return
                year_raw = self.p_year.get().strip()
                year = int(year_raw) if year_raw else None
                r = data.bulk_export_exam_timetables(
                    sids, output_dir=out_dir, year=year,
                    season=self.p_season.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "ucas_export_predictions":
                path = self.p_outpath.get().strip()
                if not path:
                    messagebox.showerror("Run", "Pick an output path.")
                    return
                r = data.bulk_ucas_export_predictions(
                    sids, output_path=path, dry_run=dry)
            elif op == "ucas_update_status":
                r = data.bulk_ucas_update_status(
                    sids, status=self.p_status.get(), dry_run=dry)
            elif op == "promote_year_group":
                r = data.bulk_promote_year_group(
                    sids,
                    new_academic_year=self.p_year.get().strip(),
                    bump_year_group=bool(self.p_bump.get()),
                    dry_run=dry,
                )
            elif op == "mark_leavers":
                r = data.bulk_mark_leavers(
                    sids,
                    leaving_date=self.p_date.get().strip() or _today(),
                    leaving_reason=self.p_reason.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "reinstate_alumni":
                raw = self.p_ids.get().strip()
                try:
                    ids = [int(t) for t in
                            raw.replace(" ", ",").split(",") if t]
                except ValueError:
                    messagebox.showerror(
                        "Run", "Alumni ids must be integers.")
                    return
                r = data.bulk_reinstate_alumni(ids, dry_run=dry)
            elif op == "gdpr_redact":
                raw = self.p_fields.get().strip()
                fields = ([f.strip() for f in raw.split(",")
                            if f.strip()] or None)
                r = data.bulk_gdpr_redact(
                    sids, fields=fields, dry_run=dry)
            elif op == "export_student_records":
                path = self.p_outpath.get().strip()
                if not path:
                    messagebox.showerror("Run", "Pick an output path.")
                    return
                r = data.bulk_export_student_records(
                    sids, output_path=path, dry_run=dry)
            elif op == "anonymise_alumni":
                raw = self.p_ids.get().strip()
                try:
                    ids = [int(t) for t in
                            raw.replace(" ", ",").split(",") if t]
                except ValueError:
                    messagebox.showerror(
                        "Run", "Alumni ids must be integers.")
                    return
                r = data.bulk_anonymise_alumni(ids, dry_run=dry)
            elif op == "assign_inventory":
                r = data.bulk_assign_inventory(
                    sids,
                    kind=self.p_kind.get(),
                    starting_number=int(
                        self.p_start.get().strip() or "1"),
                    prefix=self.p_prefix.get().strip(),
                    pad=int(self.p_pad.get().strip() or "4"),
                    assigned_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "upload_photos":
                zip_path = self.p_zip.get().strip()
                out_dir = self.p_outdir.get().strip()
                if not zip_path or not out_dir:
                    messagebox.showerror(
                        "Run", "ZIP and output dir required.")
                    return
                r = data.bulk_upload_photos(
                    zip_path, output_dir=out_dir, dry_run=dry)
            elif op == "import_contacts_csv":
                path = self.p_csv.get().strip()
                if not path:
                    messagebox.showerror("Run", "Pick a CSV file.")
                    return
                r = data.bulk_import_contacts_csv(path, dry_run=dry)
            elif op == "force_password_reset":
                r = data.bulk_force_password_reset(
                    sids,
                    reason=self.p_reason.get().strip() or None,
                    flagged_by=self.p_by.get().strip() or None,
                    clear=bool(self.p_clear.get()),
                    dry_run=dry,
                )
            elif op == "undo_job":
                try:
                    jid = int(self.p_jid.get().strip())
                except ValueError:
                    messagebox.showerror(
                        "Run", "Job id must be an integer.")
                    return
                r = data.bulk_undo_job(jid, dry_run=dry)
            elif op == "schedule_recurring":
                params: dict[str, str] = {}
                for pair in self.p_params.get().split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        params[k.strip()] = v.strip()
                r = data.bulk_schedule_recurring(
                    name=self.p_name.get().strip(),
                    operation=self.p_op.get(),
                    cron_expr=self.p_cron.get().strip(),
                    parameters=params,
                    next_run_at=self.p_next.get().strip() or None,
                    created_by=self.p_by.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "assign_mentors":
                sessions_raw = self.p_sessions.get().strip()
                sessions = int(sessions_raw) if sessions_raw else None
                r = data.bulk_assign_mentors(
                    sids,
                    mentor_id=self.p_mentor.get().strip(),
                    programme=self.p_programme.get(),
                    start_date=self.p_start.get().strip() or _today(),
                    frequency=self.p_frequency.get(),
                    coordinator=self.p_coord.get().strip() or None,
                    planned_end=self.p_planned.get().strip() or None,
                    sessions_planned=sessions,
                    dry_run=dry,
                )
            elif op == "mark_holiday":
                r = data.bulk_mark_holiday(
                    sids,
                    date_from=self.p_date_from.get().strip(),
                    date_to=self.p_date_to.get().strip(),
                    reason=self.p_reason.get().strip()
                           or "Authorised holiday",
                    dry_run=dry,
                )
            elif op == "clear_attendance":
                only = self.p_only_status.get().strip() or None
                if not dry and not messagebox.askyesno(
                        "Clear attendance",
                        f"This will DELETE attendance rows for "
                        f"{len(sids)} student(s). Continue?"):
                    return
                r = data.bulk_clear_attendance(
                    sids,
                    date_from=self.p_date_from.get().strip(),
                    date_to=self.p_date_to.get().strip(),
                    only_status=only,
                    dry_run=dry,
                )
            elif op == "late_to_unauth":
                over_raw = self.p_over.get().strip() or "15"
                try:
                    over = int(over_raw)
                except ValueError:
                    messagebox.showerror(
                        "Run", "Threshold minutes must be an integer.")
                    return
                r = data.bulk_late_to_unauth(
                    sids,
                    date_from=self.p_date_from.get().strip(),
                    date_to=self.p_date_to.get().strip(),
                    over_minutes=over,
                    reason=self.p_reason.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "attendance_letters":
                try:
                    window = int(self.p_window.get().strip() or "28")
                    s1 = float(self.p_s1.get().strip() or "95")
                    s2 = float(self.p_s2.get().strip() or "90")
                    s3 = float(self.p_s3.get().strip() or "85")
                except ValueError:
                    messagebox.showerror(
                        "Run",
                        "Window and thresholds must be numeric.")
                    return
                tiers = (
                    (s1, "Stage 1"), (s2, "Stage 2"), (s3, "Stage 3"),
                )
                r = data.bulk_attendance_letters(
                    sids,
                    window_days=window,
                    stages=tiers,
                    send=self.p_send.get(),
                    sender_staff_id=self.p_sender.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "punctuality_report":
                r = data.bulk_punctuality_report(
                    sids,
                    date_from=self.p_date_from.get().strip(),
                    date_to=self.p_date_to.get().strip() or _today(),
                    sender_staff_id=self.p_sender.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "register_closure":
                picks = self.p_closure_slots_lb.curselection()
                if not picks:
                    messagebox.showerror(
                        "Run", "Pick at least one slot.")
                    return
                slot_ids = [self._closure_slot_map[str(i)] for i in picks]
                r = data.bulk_register_closure(
                    slot_ids,
                    date_from=self.p_date_from.get().strip(),
                    date_to=self.p_date_to.get().strip(),
                    default_status=self.p_default.get(),
                    notes=self.p_notes.get().strip() or None,
                    dry_run=dry,
                )
            elif op == "assign_subjects":
                picks = self.p_subjects_lb.curselection()
                subjects = [self.p_subjects_lb.get(i) for i in picks]
                if not subjects:
                    messagebox.showerror(
                        "Run", "Pick at least one subject.")
                    return
                r = data.bulk_assign_subjects(
                    sids, subjects=subjects,
                    overwrite=self.p_overwrite.get(),
                    dry_run=dry,
                )
            elif op == "withdraw_subjects":
                picks = self.p_subjects_lb.curselection()
                subjects = [self.p_subjects_lb.get(i) for i in picks]
                if not subjects:
                    messagebox.showerror(
                        "Run", "Pick at least one subject to withdraw.")
                    return
                r = data.bulk_withdraw_subjects(
                    sids, subjects=subjects, dry_run=dry,
                )
            elif op == "set_teaching_set":
                target_label = self.p_set_target.get().strip()
                target_id = self._set_group_map.get(target_label)
                if target_id is None:
                    messagebox.showerror(
                        "Run", "Pick a target group.")
                    return
                r = data.bulk_set_teaching_set(
                    sids, target_group_id=target_id, dry_run=dry,
                )
            elif op == "import_timetable_csv":
                path = self.p_csv.get().strip()
                if not path:
                    messagebox.showerror("Run", "Pick a CSV file.")
                    return
                r = data.bulk_import_timetable_csv(
                    path, dry_run=dry,
                )
            else:
                messagebox.showerror("Run", f"Unknown operation {op!r}")
                return
        except ValidationError as e:
            data.log_event(logging.WARNING,
                            f"GUI validation error in {op!r}: {e}",
                            operation=op)
            messagebox.showerror("Run", str(e))
            return
        except Exception as e:  # noqa: BLE001
            data.log_event(logging.ERROR,
                            f"GUI run for {op!r} crashed: {e}",
                            operation=op, exc_info=True)
            logger.exception("Bulk-ops GUI run crashed")
            messagebox.showerror("Run", f"Unexpected error: {e}")
            return
        self._show_result(r, dry_run=dry,
                            _preview_dialog=_preview_dialog)

    def _preview(self) -> None:
        """Force dry-run + show a detailed diff dialog."""
        prev = self.dry_var.get()
        self.dry_var.set(True)
        try:
            self._run(_preview_dialog=True)
        finally:
            self.dry_var.set(prev)

    def _show_result(self, r: BulkResult, *, dry_run: bool,
                       _preview_dialog: bool = False) -> None:
        prefix = "[preview] " if dry_run else ""
        msg = (f"{prefix}{r.operation}: "
               f"{r.success_count}/{r.target_count} ok, "
               f"{r.failure_count} failed")
        if r.job_id:
            msg += f"  (job #{r.job_id})"
        self.result_var.set(msg)
        # In dry-run with no operation-specific diff, fall back to showing
        # the resolved target list so the user can sanity-check scope.
        diff_lines: list[str] = []
        if r.success_ids:
            diff_lines = list(r.success_ids[:50])
            if len(r.success_ids) > 50:
                diff_lines.append(
                    f"... +{len(r.success_ids) - 50} more")
        elif dry_run and r.target_count and not r.failures:
            diff_lines = [f"Would touch {r.target_count} target(s)."]

        if r.failures:
            preview = "\n".join(f"{sid}: {reason}"
                                  for sid, reason in r.failures[:10])
            if len(r.failures) > 10:
                preview += f"\n... +{len(r.failures) - 10} more"
            messagebox.showwarning(
                "Run complete (with failures)",
                f"{msg}\n\nFailures:\n{preview}")
        elif _preview_dialog or (dry_run and diff_lines):
            _ResultDialog(self.frame.winfo_toplevel(), msg, diff_lines)
        else:
            messagebox.showinfo("Run complete", msg)


# ══ Job log tab ════════════════════════════════════════════════════

class JobsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Job log")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Operation:").pack(side="left")
        self.f_op = ttk.Combobox(bar, values=("",) + OPERATIONS,
                                    state="readonly", width=20)
        self.f_op.current(0)
        self.f_op.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Limit:").pack(side="left")
        self.f_limit = ttk.Entry(bar, width=6)
        self.f_limit.insert(0, "100")
        self.f_limit.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "ts", "operation", "targets", "ok",
                "fail", "ran_by", "summary")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 60, "ts": 150, "operation": 140,
                  "targets": 70, "ok": 60, "fail": 60,
                  "ran_by": 120, "summary": 500}
        headings = {"id": "ID", "ts": "When",
                    "operation": "Operation", "targets": "Targets",
                    "ok": "OK", "fail": "Fail",
                    "ran_by": "Ran by", "summary": "Summary"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c in ("targets", "ok", "fail") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("hasfail", background="#fff7d0")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            limit = int(self.f_limit.get().strip() or "100")
        except ValueError:
            messagebox.showerror("Limit", "Must be a number.")
            return
        try:
            rows = data.list_jobs(operation=self.f_op.get() or None,
                                     limit=limit)
        except ValidationError as e:
            messagebox.showerror("Filter", str(e))
            return
        for j in rows:
            tags = ("hasfail",) if j.failure_count else ()
            self.tree.insert("", "end", iid=str(j.job_id), values=(
                j.job_id, j.ran_at, j.operation,
                j.target_count, j.success_count, j.failure_count,
                j.ran_by or "—", j.summary,
            ), tags=tags)
        self.count_var.set(f"{len(rows)} job(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _view_selected(self) -> None:
        jid = self._selected_id()
        if jid is None:
            messagebox.showinfo("View", "Select a job first.")
            return
        j = data.get_job(jid)
        if j is None:
            return
        JobDetailDialog(self.frame.winfo_toplevel(), j)

    def _delete_selected(self) -> None:
        jid = self._selected_id()
        if jid is None:
            messagebox.showinfo("Delete", "Select a job first.")
            return
        if not messagebox.askyesno("Delete", f"Delete job #{jid}?\n"
                                     "(Audit row only — the actions "
                                     "themselves are not undone.)"):
            return
        try:
            data.delete_job(jid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        ttk.Button(self.frame, text="Refresh",
                    command=self.refresh).pack(side="top", anchor="w",
                                                 padx=8, pady=(8, 4))
        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        summ = data.summary()
        lines = [
            f"Total jobs        : {summ.total_jobs}",
            f"Total targets     : {summ.total_targets}",
            f"Total successes   : {summ.total_successes}",
            f"Total failures    : {summ.total_failures}",
            f"Most recent       : {summ.most_recent_ts or '—'}",
            "",
            "By operation:",
        ]
        for op in OPERATIONS:
            n = summ.by_operation.get(op, 0)
            if n:
                lines.append(f"  {OPERATION_LABELS.get(op, op):<24} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Schedules tab ═════════════════════════════════════════════════

class SchedulesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Schedules")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Enable / disable",
                    command=self._toggle).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "on", "name", "operation",
                "cron", "next", "last_job", "by")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "on": 50, "name": 180,
                  "operation": 150, "cron": 140, "next": 130,
                  "last_job": 80, "by": 100}
        heads = {"id": "ID", "on": "Enabled",
                 "name": "Name", "operation": "Operation",
                 "cron": "Cron", "next": "Next run",
                 "last_job": "Last job", "by": "Created by"}
        for c in cols:
            self.tree.heading(c, text=heads[c])
            anchor = "center" if c in ("id", "on", "last_job") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("off", foreground="#888")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = data.list_schedules()
        for s in rows:
            tags = () if s.enabled else ("off",)
            self.tree.insert("", "end", iid=str(s.schedule_id),
                                values=(s.schedule_id,
                                         "yes" if s.enabled else "no",
                                         s.name, s.operation,
                                         s.cron_expr,
                                         s.next_run_at or "—",
                                         s.last_job_id or "—",
                                         s.created_by or "—"),
                                tags=tags)
        self.count_var.set(f"{len(rows)} schedule(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _toggle(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Toggle", "Select a schedule first.")
            return
        s = data.get_schedule(sid)
        if s is None:
            return
        try:
            data.set_schedule_enabled(sid, not s.enabled)
        except ValidationError as e:
            messagebox.showerror("Toggle failed", str(e))
            return
        self.refresh()

    def _delete(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Delete", "Select a schedule first.")
            return
        if not messagebox.askyesno(
                "Delete", f"Delete schedule #{sid}?"):
            return
        data.delete_schedule(sid)
        self.refresh()


# ══ Logs tab ═══════════════════════════════════════════════════════

class LogsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Logs")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Level:").pack(side="left")
        self.f_level = ttk.Combobox(
            bar, state="readonly", width=10,
            values=("", "DEBUG", "INFO", "WARNING", "ERROR",
                    "CRITICAL"))
        self.f_level.current(0)
        self.f_level.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Operation:").pack(side="left")
        self.f_op = ttk.Combobox(
            bar, state="readonly", width=24,
            values=("",) + OPERATIONS)
        self.f_op.current(0)
        self.f_op.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Limit:").pack(side="left")
        self.f_limit = ttk.Entry(bar, width=6)
        self.f_limit.insert(0, "200")
        self.f_limit.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Clear all…",
                    command=self._clear_all).pack(side="right")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "ts", "level", "operation", "job", "message")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 60, "ts": 140, "level": 70,
                  "operation": 160, "job": 60, "message": 520}
        heads = {"id": "ID", "ts": "When", "level": "Level",
                 "operation": "Operation", "job": "Job",
                 "message": "Message"}
        for c in cols:
            self.tree.heading(c, text=heads[c])
            anchor = ("center"
                      if c in ("id", "level", "job") else "w")
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("warn", background="#fff7d0")
        self.tree.tag_configure("err", background="#ffd6d0")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            limit = int(self.f_limit.get().strip() or "200")
        except ValueError:
            messagebox.showerror("Limit", "Must be a number.")
            return
        try:
            rows = data.list_logs(
                level=self.f_level.get() or None,
                operation=self.f_op.get() or None,
                limit=limit)
        except ValidationError as e:
            messagebox.showerror("Filter", str(e))
            return
        for r in rows:
            tag = ()
            if r.level in ("ERROR", "CRITICAL"):
                tag = ("err",)
            elif r.level == "WARNING":
                tag = ("warn",)
            self.tree.insert("", "end", iid=str(r.log_id),
                                values=(r.log_id, r.ts, r.level,
                                         r.operation or "—",
                                         r.job_id or "—",
                                         r.message),
                                tags=tag)
        self.count_var.set(f"{len(rows)} log row(s).")

    def _view_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            rows = data.list_logs(limit=10000)
        except ValidationError:
            return
        target_id = int(sel[0])
        match = next((r for r in rows if r.log_id == target_id), None)
        if not match:
            return
        lines = [
            f"#{match.log_id}  {match.ts}  [{match.level}]",
            f"logger:    {match.logger or '—'}",
            f"operation: {match.operation or '—'}",
            f"job:       {match.job_id or '—'}",
            "",
            "message:",
            "  " + (match.message or ""),
        ]
        if match.exc_info:
            lines += ["", "traceback:", match.exc_info]
        _ResultDialog(self.frame.winfo_toplevel(),
                       f"Log #{match.log_id}", lines)

    def _clear_all(self) -> None:
        days_raw = simpledialog.askstring(
            "Clear logs",
            "Delete logs older than N days "
            "(blank/0 = ALL logs):",
            parent=self.frame.winfo_toplevel())
        if days_raw is None:
            return
        days = None
        days_raw = days_raw.strip()
        if days_raw:
            try:
                d = int(days_raw)
                days = d if d > 0 else None
            except ValueError:
                messagebox.showerror("Clear logs",
                                       "Must be a whole number.")
                return
        label = (f"older than {days} days" if days is not None
                 else "ALL logs")
        if not messagebox.askyesno("Clear logs",
                                       f"Delete {label}?"):
            return
        try:
            n = data.clear_logs(older_than_days=days)
        except ValidationError as e:
            messagebox.showerror("Clear logs", str(e))
            return
        messagebox.showinfo("Clear logs", f"Deleted {n} row(s).")
        self.refresh()


# ══ Dialogs ═══════════════════════════════════════════════════════

class _ResultDialog:
    """Used for the 'Preview with diff' button and rich dry-run output."""

    def __init__(self, parent: tk.Misc, header: str,
                  lines: list[str]) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title("Bulk operation preview")
        self.win.transient(parent)
        self.win.geometry("760x520")
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text=header,
                   font=("", 11, "bold")).pack(anchor="w")
        ttk.Separator(form).pack(fill="x", pady=(4, 8))
        txt = tk.Text(form, wrap="none",
                        font=("TkFixedFont", 10))
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", "\n".join(lines) if lines else
                   "(no per-target detail available)")
        txt.configure(state="disabled")
        ttk.Button(form, text="Close",
                    command=self.win.destroy).pack(
            anchor="e", pady=(8, 0))


class JobDetailDialog:
    def __init__(self, parent: tk.Misc, job: Job) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title(f"Job #{job.job_id}")
        self.win.transient(parent)
        self.win.geometry("760x600")

        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(
            form,
            text=f"#{job.job_id}  ·  {job.ran_at}  ·  {job.operation}",
            font=("", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            form,
            text=(f"Targets: {job.target_count}  ·  "
                   f"OK: {job.success_count}  ·  "
                   f"Fail: {job.failure_count}  ·  "
                   f"Ran by: {job.ran_by or '—'}"),
            foreground="#555",
        ).pack(anchor="w", pady=(0, 8))

        ttk.Label(form, text="Summary:",
                   font=("", 10, "bold")).pack(anchor="w")
        s_t = tk.Text(form, height=3, wrap="word")
        s_t.insert("1.0", job.summary)
        s_t.configure(state="disabled")
        s_t.pack(fill="x", pady=(0, 8))

        ttk.Label(form, text="Parameters:",
                   font=("", 10, "bold")).pack(anchor="w")
        p_t = tk.Text(form, height=8, wrap="none",
                         font=("TkFixedFont", 9))
        p_t.insert("1.0", json.dumps(job.parameters, indent=2)
                    if job.parameters else "(none)")
        p_t.configure(state="disabled")
        p_t.pack(fill="x", pady=(0, 8))

        nb = ttk.Notebook(form)
        nb.pack(fill="both", expand=True)

        succ_frame = ttk.Frame(nb)
        nb.add(succ_frame, text=f"Successes ({len(job.success_ids)})")
        succ_t = tk.Text(succ_frame, wrap="none",
                            font=("TkFixedFont", 9))
        succ_t.insert("1.0",
                        "\n".join(job.success_ids)
                        if job.success_ids else "(none)")
        succ_t.configure(state="disabled")
        succ_t.pack(fill="both", expand=True)

        fail_frame = ttk.Frame(nb)
        nb.add(fail_frame, text=f"Failures ({len(job.failures)})")
        fail_t = tk.Text(fail_frame, wrap="none",
                            font=("TkFixedFont", 9))
        fail_t.insert("1.0",
                        "\n".join(f"{sid}: {reason}"
                                    for sid, reason in job.failures)
                        if job.failures else "(none)")
        fail_t.configure(state="disabled")
        fail_t.pack(fill="both", expand=True)

        ttk.Button(form, text="Close",
                    command=self.win.destroy).pack(pady=(10, 0))
