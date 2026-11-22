"""The Run tab: operation picker, student selection and parameter-form switch.

Split out of ``bulk_operations_views.py``, which re-exports every name here.
"""

from __future__ import annotations

from tkinter import ttk
import tkinter as tk

from education_system.systems.sixth_form.domain.learners.bulk_operations.base import OPERATIONS
from education_system.systems.sixth_form.domain.learners.students import students as student_data

from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.view_common import (
    OPERATION_LABELS,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.forms_records import (
    RecordsFormsMixin,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.forms_attendance import (
    AttendanceFormsMixin,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.forms_academic import (
    AcademicFormsMixin,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.forms_pastoral import (
    PastoralFormsMixin,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.forms_comms import (
    CommsFormsMixin,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.forms_finance import (
    FinanceFormsMixin,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.run_tab.runner import (
    RunnerMixin,
)


# ══ Run tab ════════════════════════════════════════════════════════

class RunTab(RecordsFormsMixin, AttendanceFormsMixin, AcademicFormsMixin, PastoralFormsMixin, CommsFormsMixin, FinanceFormsMixin, RunnerMixin):
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

    # ── Attendance / slot helpers ─────────────────────────────────
    def _slot_options(self) -> list[tuple[int, str]]:
        from education_system.systems.sixth_form.domain.academics.timetable import (
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

    # ── Academic / pastoral form builders ─────────────────────────
    def _group_options(self) -> list[tuple[int, str]]:
        from education_system.systems.sixth_form.domain.academics.class_groups import (
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

    # ── Lifecycle / admin / meta form builders ────────────────────
    def _file_picker(self, parent: tk.Widget, row: int, label: str,
                       *, save: bool = False, dir_only: bool = False
                       ) -> ttk.Entry:
        from education_system.platform.delivery.gui.parented_dialogs import filedialog
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
