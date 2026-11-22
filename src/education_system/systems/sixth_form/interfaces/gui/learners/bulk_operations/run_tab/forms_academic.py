"""Parameter forms for academic, exams and UCAS operations.

Split out of ``bulk_operations_views.py``, which re-exports every name here.
"""

from __future__ import annotations

from datetime import date as _date
from tkinter import ttk
import tkinter as tk

from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.view_common import (
    _today,
)


class AcademicFormsMixin:
    """Parameter forms for academic, exams and UCAS operations."""

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
        from education_system.systems.sixth_form.domain.academics.subjects import (
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
        from education_system.platform.delivery.gui.parented_dialogs import filedialog

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
        from education_system.platform.delivery.gui.parented_dialogs import filedialog

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

    def _build_ucas_form(self) -> None:
        f = self.params_frame
        self.p_referee = self._entry(f, 0, "Override referee email:",
                                          width=40)
        self.p_deadline = self._entry(f, 1, "Deadline:", width=14)

    def _build_exam_entries_form(self) -> None:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _sub,
        )
        from education_system.systems.sixth_form.domain.assessment.exam_entries.exam_entries import (
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
        from education_system.platform.delivery.gui.parented_dialogs import filedialog

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

    def _build_ucas_export_form(self) -> None:
        self.p_outpath = self._file_picker(
            self.params_frame, 0, "Output CSV:", save=True)

    def _build_ucas_status_form(self) -> None:
        from education_system.systems.sixth_form.domain.progression.university.ucas import (
            APP_STATUSES,
        )
        self.p_status = self._combo(
            self.params_frame, 0, "Status:",
            list(APP_STATUSES), default=APP_STATUSES[0])

    def _build_assign_subjects_form(self) -> None:
        f = self.params_frame
        from education_system.systems.sixth_form.domain.academics.subjects import (
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
        from education_system.systems.sixth_form.domain.academics.subjects import (
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
        # Withdrawals go through the learning-aim workflow, which records
        # the last day in learning, a reason and an approver, and checks
        # the funding qualifying period.
        self.p_withdraw_date = self._entry(
            f, 1, "Effective date:", _today(), width=14)
        self.p_withdraw_reason = self._entry(
            f, 2, "Reason:", "Bulk withdrawal")
        self.p_withdraw_approver = self._entry(f, 3, "Approved by:")

    def _build_set_set_form(self) -> None:
        f = self.params_frame
        from education_system.systems.sixth_form.domain.academics.class_groups import (
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
        from education_system.platform.delivery.gui.parented_dialogs import filedialog

        def _browse() -> None:
            path = filedialog.askopenfilename(
                title="Pick timetable CSV",
                filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
            if path:
                self.p_csv.delete(0, "end")
                self.p_csv.insert(0, path)

        ttk.Button(f, text="Browse…", command=_browse).grid(
            row=1, column=2, sticky="w", padx=4)
