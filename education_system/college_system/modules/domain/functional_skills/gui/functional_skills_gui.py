"""Functional Skills & GCSE Resits GUI module."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
from education_system.college_system.modules.domain.functional_skills.services.functional_skills_service import (
    FunctionalSkillsService,
)


class FunctionalSkillsFrame(tk.Frame):
    """Functional Skills & GCSE Resits management frame."""

    SUBJECTS = ["", "Maths", "English", "English Language", "ICT", "Digital"]
    QUAL_TYPES = ["", "gcse_resit", "functional_skills", "stepping_stone"]
    LEVELS = ["", "entry1", "entry2", "entry3", "1", "2"]
    STATUSES = ["", "enrolled", "in_progress", "exam_booked", "completed", "withdrawn"]
    ASSESSMENT_TYPES = ["", "mock", "coursework", "exam", "practice", "diagnostic"]

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = FunctionalSkillsService(db_path)
        self._build_ui()

    # ------------------------------------------------------------------ #
    # UI Construction
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text=t("functional_skills.management"),
            font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_enrollments_tab()
        self._build_assessments_tab()
        self._build_stats_tab()

    # -- Enrollments Tab ------------------------------------------------ #

    def _build_enrollments_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("enrollment.enrollments"))

        # Filters
        filt_frame = tk.Frame(tab, bg="#ecf0f1")
        filt_frame.pack(fill="x", pady=(0, 8))

        tk.Label(filt_frame, text=t("functional_skills.subject") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._enr_subject_var = tk.StringVar()
        ttk.Combobox(filt_frame, textvariable=self._enr_subject_var,
                     values=self.SUBJECTS, width=14, state="readonly").pack(side="left", padx=(0, 10))

        tk.Label(filt_frame, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._enr_status_var = tk.StringVar()
        ttk.Combobox(filt_frame, textvariable=self._enr_status_var,
                     values=self.STATUSES, width=12, state="readonly").pack(side="left", padx=(0, 10))

        tk.Label(filt_frame, text=t("course.qualification_type") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._enr_qual_var = tk.StringVar()
        ttk.Combobox(filt_frame, textvariable=self._enr_qual_var,
                     values=self.QUAL_TYPES, width=16, state="readonly").pack(side="left", padx=(0, 10))

        ttk.Button(filt_frame, text=t("common.filter"), command=self._load_enrollments).pack(side="left", padx=4)
        ttk.Button(filt_frame, text=t("common.clear"), command=self._clear_enr_filters).pack(side="left", padx=4)

        # Treeview
        cols = ("id", "student_id", "subject", "qual_type", "level",
                "entry_grade", "target", "current", "exam_date", "status")
        tree_frame = tk.Frame(tab, bg="#ecf0f1")
        tree_frame.pack(fill="both", expand=True)
        self._enr_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [
            ("id", t("common.id"), 40), ("student_id", t("common.student_id"), 70),
            ("subject", t("functional_skills.subject"), 100), ("qual_type", t("course.qualification_type"), 110),
            ("level", t("functional_skills.level"), 50), ("entry_grade", "Entry Grade", 80),
            ("target", "Target", 60), ("current", "Current", 60),
            ("exam_date", "Exam Date", 90), ("status", t("common.status"), 90),
        ]:
            self._enr_tree.heading(c, text=h)
            self._enr_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._enr_tree.yview)
        self._enr_tree.configure(yscrollcommand=vsb.set)
        self._enr_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(8, 0))
        for txt, cmd in [
            (t("common.create"), self._new_enrollment), (t("common.view"), self._view_enrollment),
            (t("common.update"), self._update_enrollment), ("Book Exam", self._book_exam),
            ("Record Result", self._record_result), (t("common.delete"), self._delete_enrollment),
            ("Export CSV", self._export_csv),
        ]:
            ttk.Button(btn_frame, text=txt, command=cmd).pack(side="left", padx=4)

    # -- Assessments Tab ------------------------------------------------ #

    def _build_assessments_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Assessments")

        # Filter
        filt_frame = tk.Frame(tab, bg="#ecf0f1")
        filt_frame.pack(fill="x", pady=(0, 8))

        tk.Label(filt_frame, text="Enrollment ID:", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._asmt_enr_var = tk.StringVar()
        ttk.Entry(filt_frame, textvariable=self._asmt_enr_var, width=10).pack(side="left", padx=(0, 10))

        ttk.Button(filt_frame, text=t("common.filter"), command=self._load_assessments).pack(side="left", padx=4)
        ttk.Button(filt_frame, text=t("common.clear"), command=self._clear_asmt_filters).pack(side="left", padx=4)

        # Treeview
        cols = ("id", "enrollment_id", "type", "date", "score", "grade", "feedback")
        tree_frame = tk.Frame(tab, bg="#ecf0f1")
        tree_frame.pack(fill="both", expand=True)
        self._asmt_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [
            ("id", t("common.id"), 40), ("enrollment_id", "Enrollment ID", 90),
            ("type", t("common.type"), 90), ("date", t("common.date"), 90),
            ("score", t("common.score"), 60), ("grade", t("common.grade"), 60),
            ("feedback", "Feedback", 200),
        ]:
            self._asmt_tree.heading(c, text=h)
            self._asmt_tree.column(c, width=w, anchor="center" if w < 150 else "w")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._asmt_tree.yview)
        self._asmt_tree.configure(yscrollcommand=vsb.set)
        self._asmt_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(8, 0))
        for txt, cmd in [
            (t("common.create"), self._new_assessment),
            (t("common.update"), self._update_assessment),
            (t("common.delete"), self._delete_assessment),
            ("Export CSV", self._export_assessments_csv),
        ]:
            ttk.Button(btn_frame, text=txt, command=cmd).pack(side="left", padx=4)

    # -- Statistics Tab ------------------------------------------------- #

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("common.summary"))

        self._stats_frame = tk.Frame(tab, bg="#ecf0f1")
        self._stats_frame.pack(fill="both", expand=True)

        ttk.Button(tab, text=t("common.refresh"),
                   command=self._load_stats).pack(pady=(8, 0))

    # ------------------------------------------------------------------ #
    # Data Loading
    # ------------------------------------------------------------------ #

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._enr_tree, "functional_skills_enrollments_export.csv")

    def _export_assessments_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._asmt_tree, "functional_skills_assessments_export.csv")

    def refresh(self):
        self._load_enrollments()
        self._load_assessments()
        self._load_stats()

    def _clear_enr_filters(self):
        self._enr_subject_var.set("")
        self._enr_status_var.set("")
        self._enr_qual_var.set("")
        self._load_enrollments()

    def _clear_asmt_filters(self):
        self._asmt_enr_var.set("")
        self._load_assessments()

    def _load_enrollments(self):
        self._enr_tree.delete(*self._enr_tree.get_children())
        try:
            subject = self._enr_subject_var.get() or None
            status = self._enr_status_var.get() or None
            qual_type = self._enr_qual_var.get() or None
            rows = self._svc.list_enrollments(subject=subject, status=status,
                                              qualification_type=qual_type)
            for r in rows:
                self._enr_tree.insert("", "end", values=(
                    r["id"], r["student_id"], r.get("subject", "-"),
                    r.get("qualification_type", "-"), r.get("level", "-"),
                    r.get("entry_grade") or "-", r.get("target_grade") or "-",
                    r.get("current_grade") or "-", r.get("exam_date") or "-",
                    r.get("status", "-"),
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_assessments(self):
        self._asmt_tree.delete(*self._asmt_tree.get_children())
        try:
            enr_id_str = self._asmt_enr_var.get().strip()
            enr_id = int(enr_id_str) if enr_id_str else None
            rows = self._svc.list_assessments(enrollment_id=enr_id)
            for r in rows:
                self._asmt_tree.insert("", "end", values=(
                    r["id"], r["enrollment_id"],
                    r.get("assessment_type", "-"),
                    r.get("assessment_date") or "-",
                    r.get("score") if r.get("score") is not None else "-",
                    r.get("grade") or "-",
                    r.get("feedback") or "-",
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_stats(self):
        for w in self._stats_frame.winfo_children():
            w.destroy()
        try:
            stats = self._svc.get_stats()

            row = 0
            tk.Label(self._stats_frame, text=t("common.summary"),
                     font=("Helvetica", 13, "bold"), bg="#ecf0f1").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(0, 6))
            row += 1

            for label, value in [
                ("Total Enrollments:", stats["total_enrollments"]),
                ("Total Assessments:", stats["total_assessments"]),
                (t("common.average") + " " + t("common.score") + ":", stats["avg_score"]),
                ("Pass Rate:", f"{stats['pass_rate']}%"),
            ]:
                tk.Label(self._stats_frame, text=label, bg="#ecf0f1",
                         font=("Helvetica", 10, "bold")).grid(row=row, column=0, sticky="w", padx=(0, 10))
                tk.Label(self._stats_frame, text=str(value), bg="#ecf0f1",
                         font=("Helvetica", 10)).grid(row=row, column=1, sticky="w")
                row += 1

            row += 1
            tk.Label(self._stats_frame, text="By " + t("functional_skills.subject"),
                     font=("Helvetica", 12, "bold"), bg="#ecf0f1").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(6, 4))
            row += 1
            for subj, cnt in stats["by_subject"].items():
                tk.Label(self._stats_frame, text=f"  {subj}:", bg="#ecf0f1").grid(
                    row=row, column=0, sticky="w")
                tk.Label(self._stats_frame, text=str(cnt), bg="#ecf0f1").grid(
                    row=row, column=1, sticky="w")
                row += 1

            row += 1
            tk.Label(self._stats_frame, text="By " + t("common.status"),
                     font=("Helvetica", 12, "bold"), bg="#ecf0f1").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(6, 4))
            row += 1
            for st, cnt in stats["by_status"].items():
                tk.Label(self._stats_frame, text=f"  {st}:", bg="#ecf0f1").grid(
                    row=row, column=0, sticky="w")
                tk.Label(self._stats_frame, text=str(cnt), bg="#ecf0f1").grid(
                    row=row, column=1, sticky="w")
                row += 1

            row += 1
            tk.Label(self._stats_frame, text="By " + t("course.qualification_type"),
                     font=("Helvetica", 12, "bold"), bg="#ecf0f1").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(6, 4))
            row += 1
            for qt, cnt in stats["by_qualification_type"].items():
                tk.Label(self._stats_frame, text=f"  {qt}:", bg="#ecf0f1").grid(
                    row=row, column=0, sticky="w")
                tk.Label(self._stats_frame, text=str(cnt), bg="#ecf0f1").grid(
                    row=row, column=1, sticky="w")
                row += 1

        except Exception as e:
            tk.Label(self._stats_frame, text=f"{t('common.error')}: {e}", bg="#ecf0f1",
                     fg="red").pack(anchor="w")

    # ------------------------------------------------------------------ #
    # Enrollment Actions
    # ------------------------------------------------------------------ #

    def _get_selected_enrollment_id(self):
        sel = self._enr_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return None
        return self._enr_tree.item(sel[0], "values")[0]

    def _new_enrollment(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("enrollment.enroll"))
        dlg.geometry("400x450")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        r = 0
        for label, key, widget_type, options in [
            (t("common.student_id") + ":", "student_id", "entry", None),
            (t("functional_skills.subject") + ":", "subject", "combo", self.SUBJECTS[1:]),
            (t("course.qualification_type") + ":", "qualification_type", "combo", self.QUAL_TYPES[1:]),
            (t("functional_skills.level") + ":", "level", "combo", self.LEVELS[1:]),
            ("Entry Grade:", "entry_grade", "entry", None),
            ("Target Grade:", "target_grade", "entry", None),
            ("Exam Board:", "exam_board", "entry", None),
            (t("common.notes") + ":", "notes", "entry", None),
        ]:
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=r, column=0, sticky="w", padx=10, pady=4)
            var = tk.StringVar()
            if widget_type == "combo":
                w = ttk.Combobox(dlg, textvariable=var, values=options, width=25, state="readonly")
            else:
                w = ttk.Entry(dlg, textvariable=var, width=28)
            w.grid(row=r, column=1, padx=10, pady=4)
            fields[key] = var
            r += 1

        def _save():
            try:
                sid = int(fields["student_id"].get().strip())
                subj = fields["subject"].get().strip()
                if not subj:
                    messagebox.showerror(t("common.error"), t("common.field_required"), parent=dlg)
                    return
                kwargs = {}
                for k in ("qualification_type", "level", "entry_grade",
                          "target_grade", "exam_board", "notes"):
                    val = fields[k].get().strip()
                    if val:
                        kwargs[k] = val
                self._svc.create_enrollment(sid, subj, **kwargs)
                dlg.destroy()
                self._load_enrollments()
                messagebox.showinfo(t("common.success"), t("common.created_success"))
            except ValueError:
                messagebox.showerror(t("common.error"), t("common.invalid_input"), parent=dlg)
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e), parent=dlg)

        ttk.Button(dlg, text=t("common.save"), command=_save).grid(row=r, column=0, columnspan=2, pady=12)

    def _view_enrollment(self):
        eid = self._get_selected_enrollment_id()
        if not eid:
            return
        try:
            enr = self._svc.get_enrollment(int(eid))
            if not enr:
                messagebox.showerror(t("common.error"), t("common.no_data"))
                return

            dlg = tk.Toplevel(self)
            dlg.title(f"Enrollment #{eid}")
            dlg.geometry("450x500")
            dlg.configure(bg="#ecf0f1")
            dlg.transient(self)

            canvas = tk.Canvas(dlg, bg="#ecf0f1")
            scrollbar = ttk.Scrollbar(dlg, orient="vertical", command=canvas.yview)
            inner = tk.Frame(canvas, bg="#ecf0f1")
            inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=inner, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            r = 0
            name = f"{enr.get('first_name', '')} {enr.get('last_name', '')}".strip() or "-"
            for label, value in [
                (t("common.id") + ":", enr["id"]),
                (t("functional_skills.student") + ":", f"{enr['student_id']} - {name}"),
                (t("functional_skills.subject") + ":", enr.get("subject", "-")),
                (t("course.qualification_type") + ":", enr.get("qualification_type", "-")),
                (t("functional_skills.level") + ":", enr.get("level", "-")),
                ("Entry Grade:", enr.get("entry_grade") or "-"),
                ("Target Grade:", enr.get("target_grade") or "-"),
                ("Current Grade:", enr.get("current_grade") or "-"),
                ("Exam Board:", enr.get("exam_board") or "-"),
                ("Exam Series:", enr.get("exam_series") or "-"),
                ("Exam Date:", enr.get("exam_date") or "-"),
                (t("functional_skills.result") + ":", enr.get("result") or "-"),
                ("Attendance %:", enr.get("attendance_pct") if enr.get("attendance_pct") is not None else "-"),
                (t("common.status") + ":", enr.get("status", "-")),
                (t("common.notes") + ":", enr.get("notes") or "-"),
                (t("common.created_at") + ":", enr.get("created_at") or "-"),
                (t("common.updated_at") + ":", enr.get("updated_at") or "-"),
            ]:
                tk.Label(inner, text=label, bg="#ecf0f1",
                         font=("Helvetica", 10, "bold")).grid(row=r, column=0, sticky="nw", padx=10, pady=2)
                tk.Label(inner, text=str(value), bg="#ecf0f1",
                         wraplength=280).grid(row=r, column=1, sticky="w", padx=10, pady=2)
                r += 1

            ttk.Button(dlg, text=t("common.close"), command=dlg.destroy).pack(pady=8)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _update_enrollment(self):
        eid = self._get_selected_enrollment_id()
        if not eid:
            return
        try:
            enr = self._svc.get_enrollment(int(eid))
            if not enr:
                messagebox.showerror(t("common.error"), t("common.no_data"))
                return
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Update Enrollment #{eid}")
        dlg.geometry("400x500")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        r = 0
        for label, key, widget_type, options, default in [
            (t("functional_skills.subject") + ":", "subject", "combo", self.SUBJECTS[1:], enr.get("subject", "")),
            (t("course.qualification_type") + ":", "qualification_type", "combo", self.QUAL_TYPES[1:], enr.get("qualification_type", "")),
            (t("functional_skills.level") + ":", "level", "combo", self.LEVELS[1:], enr.get("level", "")),
            ("Entry Grade:", "entry_grade", "entry", None, enr.get("entry_grade") or ""),
            ("Target Grade:", "target_grade", "entry", None, enr.get("target_grade") or ""),
            ("Current Grade:", "current_grade", "entry", None, enr.get("current_grade") or ""),
            ("Exam Board:", "exam_board", "entry", None, enr.get("exam_board") or ""),
            ("Attendance %:", "attendance_pct", "entry", None, str(enr.get("attendance_pct") or "")),
            (t("common.status") + ":", "status", "combo", self.STATUSES[1:], enr.get("status", "")),
            (t("common.notes") + ":", "notes", "entry", None, enr.get("notes") or ""),
        ]:
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=r, column=0, sticky="w", padx=10, pady=4)
            var = tk.StringVar(value=default)
            if widget_type == "combo":
                w = ttk.Combobox(dlg, textvariable=var, values=options, width=25, state="readonly")
            else:
                w = ttk.Entry(dlg, textvariable=var, width=28)
            w.grid(row=r, column=1, padx=10, pady=4)
            fields[key] = var
            r += 1

        def _save():
            try:
                kwargs = {}
                for k, var in fields.items():
                    val = var.get().strip()
                    if val:
                        if k == "attendance_pct":
                            kwargs[k] = float(val)
                        else:
                            kwargs[k] = val
                if not kwargs:
                    messagebox.showwarning(t("common.warning"), t("common.no_data"), parent=dlg)
                    return
                self._svc.update_enrollment(int(eid), **kwargs)
                dlg.destroy()
                self._load_enrollments()
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e), parent=dlg)

        ttk.Button(dlg, text=t("common.save"), command=_save).grid(row=r, column=0, columnspan=2, pady=12)

    def _book_exam(self):
        eid = self._get_selected_enrollment_id()
        if not eid:
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Book Exam - Enrollment #{eid}")
        dlg.geometry("350x180")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Exam Date (YYYY-MM-DD):", bg="#ecf0f1").grid(
            row=0, column=0, sticky="w", padx=10, pady=8)
        date_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=date_var, width=20).grid(row=0, column=1, padx=10, pady=8)

        tk.Label(dlg, text="Exam Series:", bg="#ecf0f1").grid(
            row=1, column=0, sticky="w", padx=10, pady=8)
        series_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=series_var, width=20).grid(row=1, column=1, padx=10, pady=8)

        def _save():
            try:
                exam_date = date_var.get().strip()
                if not exam_date:
                    messagebox.showerror(t("common.error"), t("common.field_required"), parent=dlg)
                    return
                series = series_var.get().strip() or None
                self._svc.book_exam(int(eid), exam_date, series)
                dlg.destroy()
                self._load_enrollments()
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e), parent=dlg)

        ttk.Button(dlg, text=t("common.save"), command=_save).grid(row=2, column=0, columnspan=2, pady=12)

    def _record_result(self):
        eid = self._get_selected_enrollment_id()
        if not eid:
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Record Result - Enrollment #{eid}")
        dlg.geometry("350x180")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text=t("functional_skills.result") + ":", bg="#ecf0f1").grid(
            row=0, column=0, sticky="w", padx=10, pady=8)
        result_var = tk.StringVar()
        ttk.Combobox(dlg, textvariable=result_var,
                     values=["Pass", "Fail", "Achieved", "Not Achieved", "Distinction", "Merit"],
                     width=18, state="readonly").grid(row=0, column=1, padx=10, pady=8)

        tk.Label(dlg, text=t("common.grade") + ":", bg="#ecf0f1").grid(
            row=1, column=0, sticky="w", padx=10, pady=8)
        grade_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=grade_var, width=20).grid(row=1, column=1, padx=10, pady=8)

        def _save():
            try:
                result = result_var.get().strip()
                if not result:
                    messagebox.showerror(t("common.error"), t("common.field_required"), parent=dlg)
                    return
                grade = grade_var.get().strip() or None
                self._svc.record_result(int(eid), result, grade)
                dlg.destroy()
                self._load_enrollments()
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e), parent=dlg)

        ttk.Button(dlg, text=t("common.save"), command=_save).grid(row=2, column=0, columnspan=2, pady=12)

    def _delete_enrollment(self):
        eid = self._get_selected_enrollment_id()
        if not eid:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_enrollment(int(eid))
            self._load_enrollments()
            self._load_assessments()
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ------------------------------------------------------------------ #
    # Assessment Actions
    # ------------------------------------------------------------------ #

    def _get_selected_assessment_id(self):
        sel = self._asmt_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return None
        return self._asmt_tree.item(sel[0], "values")[0]

    def _new_assessment(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("functional_skills.add"))
        dlg.geometry("400x350")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        r = 0
        for label, key, widget_type, options in [
            ("Enrollment ID:", "enrollment_id", "entry", None),
            (t("common.type") + ":", "assessment_type", "combo", self.ASSESSMENT_TYPES[1:]),
            (t("common.date") + " (YYYY-MM-DD):", "assessment_date", "entry", None),
            (t("common.score") + ":", "score", "entry", None),
            (t("common.grade") + ":", "grade", "entry", None),
            ("Feedback:", "feedback", "entry", None),
        ]:
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=r, column=0, sticky="w", padx=10, pady=4)
            var = tk.StringVar()
            if widget_type == "combo":
                w = ttk.Combobox(dlg, textvariable=var, values=options, width=25, state="readonly")
            else:
                w = ttk.Entry(dlg, textvariable=var, width=28)
            w.grid(row=r, column=1, padx=10, pady=4)
            fields[key] = var
            r += 1

        # Pre-fill enrollment ID from filter if set
        enr_filter = self._asmt_enr_var.get().strip()
        if enr_filter:
            fields["enrollment_id"].set(enr_filter)

        def _save():
            try:
                enr_id = int(fields["enrollment_id"].get().strip())
                kwargs = {}
                for k in ("assessment_type", "assessment_date", "grade", "feedback"):
                    val = fields[k].get().strip()
                    if val:
                        kwargs[k] = val
                score_str = fields["score"].get().strip()
                if score_str:
                    kwargs["score"] = float(score_str)
                self._svc.create_assessment(enr_id, **kwargs)
                dlg.destroy()
                self._load_assessments()
                messagebox.showinfo(t("common.success"), t("common.created_success"))
            except ValueError:
                messagebox.showerror(t("common.error"), t("common.invalid_input"), parent=dlg)
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e), parent=dlg)

        ttk.Button(dlg, text=t("common.save"), command=_save).grid(row=r, column=0, columnspan=2, pady=12)

    def _update_assessment(self):
        aid = self._get_selected_assessment_id()
        if not aid:
            return
        try:
            asmt = self._svc.get_assessment(int(aid))
            if not asmt:
                messagebox.showerror(t("common.error"), t("common.no_data"))
                return
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Update Assessment #{aid}")
        dlg.geometry("400x300")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        r = 0
        for label, key, widget_type, options, default in [
            (t("common.type") + ":", "assessment_type", "combo", self.ASSESSMENT_TYPES[1:], asmt.get("assessment_type", "")),
            (t("common.date") + " (YYYY-MM-DD):", "assessment_date", "entry", None, asmt.get("assessment_date") or ""),
            (t("common.score") + ":", "score", "entry", None, str(asmt.get("score") or "")),
            (t("common.grade") + ":", "grade", "entry", None, asmt.get("grade") or ""),
            ("Feedback:", "feedback", "entry", None, asmt.get("feedback") or ""),
        ]:
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=r, column=0, sticky="w", padx=10, pady=4)
            var = tk.StringVar(value=default)
            if widget_type == "combo":
                w = ttk.Combobox(dlg, textvariable=var, values=options, width=25, state="readonly")
            else:
                w = ttk.Entry(dlg, textvariable=var, width=28)
            w.grid(row=r, column=1, padx=10, pady=4)
            fields[key] = var
            r += 1

        def _save():
            try:
                kwargs = {}
                for k, var in fields.items():
                    val = var.get().strip()
                    if val:
                        if k == "score":
                            kwargs[k] = float(val)
                        else:
                            kwargs[k] = val
                if not kwargs:
                    messagebox.showwarning(t("common.warning"), t("common.no_data"), parent=dlg)
                    return
                self._svc.update_assessment(int(aid), **kwargs)
                dlg.destroy()
                self._load_assessments()
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e), parent=dlg)

        ttk.Button(dlg, text=t("common.save"), command=_save).grid(row=r, column=0, columnspan=2, pady=12)

    def _delete_assessment(self):
        aid = self._get_selected_assessment_id()
        if not aid:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_assessment(int(aid))
            self._load_assessments()
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
