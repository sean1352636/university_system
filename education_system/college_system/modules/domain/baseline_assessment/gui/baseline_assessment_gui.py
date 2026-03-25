"""Baseline Assessment GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
from education_system.college_system.modules.domain.baseline_assessment.services.baseline_assessment_service import BaselineAssessmentService


class BaselineAssessmentFrame(tk.Frame):
    """Baseline Assessment management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = BaselineAssessmentService(db_path)
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("baseline_assessment.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_baselines_tab()
        self._build_checkpoints_tab()
        self._build_stats_tab()

    # ── Tab 1: Baselines ───────────────────────────────────────────────

    def _build_baselines_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("baseline_assessment.baselines"))

        # Toolbar
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("baseline_assessment.year") + ":", bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._bl_year_var = tk.StringVar()
        tk.Entry(toolbar, textvariable=self._bl_year_var, width=10).pack(side="left", padx=2)

        tk.Label(toolbar, text=t("baseline_assessment.type") + ":", bg="#ecf0f1").pack(side="left", padx=(10, 2))
        self._bl_type_var = tk.StringVar()
        ttk.Combobox(toolbar, textvariable=self._bl_type_var,
                     values=["", "initial", "mid-year", "end-of-year", "diagnostic"],
                     state="readonly", width=12).pack(side="left", padx=2)

        tk.Label(toolbar, text=t("common.search") + ":", bg="#ecf0f1").pack(side="left", padx=(10, 2))
        self._bl_search_var = tk.StringVar()
        tk.Entry(toolbar, textvariable=self._bl_search_var, width=15).pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("common.search"), command=self._load_baselines).pack(side="left", padx=5)

        ttk.Button(toolbar, text=t("common.delete"), command=self._delete_baseline).pack(side="right", padx=2)
        ttk.Button(toolbar, text=t("common.edit"), command=self._edit_baseline).pack(side="right", padx=2)
        ttk.Button(toolbar, text=t("common.view"), command=self._view_baseline).pack(side="right", padx=2)
        ttk.Button(toolbar, text=t("common.create"), command=self._new_baseline).pack(side="right", padx=2)
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side="right", padx=2)

        # Treeview
        cols = ("id", "student", "year", "type", "english", "maths", "ict",
                "overall", "date")
        self._bl_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                     selectmode="browse", height=16)
        headings = (t("common.id"), t("baseline_assessment.student"),
                    t("baseline_assessment.year"), t("baseline_assessment.type"),
                    t("baseline_assessment.english"), t("baseline_assessment.maths"),
                    t("baseline_assessment.ict"), t("baseline_assessment.overall"),
                    t("common.date"))
        widths = (40, 150, 80, 90, 70, 70, 70, 80, 100)
        for c, h, w in zip(cols, headings, widths):
            self._bl_tree.heading(c, text=h)
            self._bl_tree.column(c, width=w, anchor="center")
        self._bl_tree.column("student", anchor="w")

        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._bl_tree.yview)
        self._bl_tree.configure(yscrollcommand=vsb.set)
        self._bl_tree.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    # ── Tab 2: Progress Checkpoints ───────────────────────────────────

    def _build_checkpoints_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("baseline_assessment.progress_checkpoints"))

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("baseline_assessment.student_id") + ":", bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._cp_sid_var = tk.StringVar()
        tk.Entry(toolbar, textvariable=self._cp_sid_var, width=8).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.search"), command=self._load_checkpoints).pack(side="left", padx=5)

        ttk.Button(toolbar, text=t("common.delete"), command=self._delete_checkpoint).pack(side="right", padx=2)
        ttk.Button(toolbar, text=t("common.edit"), command=self._edit_checkpoint).pack(side="right", padx=2)
        ttk.Button(toolbar, text=t("common.create"), command=self._new_checkpoint).pack(side="right", padx=2)

        cols = ("id", "student", "course_id", "cp_num", "date", "current",
                "target", "effort", "att_pct")
        self._cp_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                     selectmode="browse", height=16)
        headings = (t("common.id"), t("baseline_assessment.student"),
                    t("baseline_assessment.course"), t("baseline_assessment.checkpoint_num"),
                    t("common.date"), t("baseline_assessment.current_grade"),
                    t("baseline_assessment.target_grade"), t("baseline_assessment.effort"),
                    t("baseline_assessment.attendance_pct"))
        widths = (40, 140, 70, 45, 100, 70, 70, 55, 55)
        for c, h, w in zip(cols, headings, widths):
            self._cp_tree.heading(c, text=h)
            self._cp_tree.column(c, width=w, anchor="center")
        self._cp_tree.column("student", anchor="w")

        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._cp_tree.yview)
        self._cp_tree.configure(yscrollcommand=vsb.set)
        self._cp_tree.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    # ── Tab 3: Statistics ──────────────────────────────────────────────

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("common.summary"))

        self._stats_text = tk.Text(tab, font=("Consolas", 11), state="disabled",
                                   bg="white", wrap="word")
        self._stats_text.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Button(tab, text=t("common.refresh"),
                   command=self._load_stats).pack(pady=(0, 10))

    # ── Data loading ───────────────────────────────────────────────────

    def _load_baselines(self):
        for item in self._bl_tree.get_children():
            self._bl_tree.delete(item)
        try:
            year = self._bl_year_var.get().strip() or None
            atype = self._bl_type_var.get().strip() or None
            search = self._bl_search_var.get().strip() or None
            rows = self._svc.list_baselines(academic_year=year,
                                            assessment_type=atype,
                                            search=search)
            for r in rows:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                self._bl_tree.insert("", "end", iid=str(r["id"]), values=(
                    r["id"], name,
                    r.get("academic_year", ""),
                    r.get("assessment_type", ""),
                    r.get("english_score", ""),
                    r.get("maths_score", ""),
                    r.get("ict_score", ""),
                    r.get("overall_baseline", ""),
                    r.get("assessment_date", ""),
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_checkpoints(self):
        for item in self._cp_tree.get_children():
            self._cp_tree.delete(item)
        try:
            sid_text = self._cp_sid_var.get().strip()
            sid = int(sid_text) if sid_text else None
            rows = self._svc.list_checkpoints(student_id=sid)
            for r in rows:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                att = r.get("attendance_pct", "")
                if att not in ("", None):
                    att = f"{att:.0f}"
                self._cp_tree.insert("", "end", iid=str(r["id"]), values=(
                    r["id"], name,
                    r.get("course_id", ""),
                    r.get("checkpoint_number", ""),
                    r.get("checkpoint_date", ""),
                    r.get("current_grade", ""),
                    r.get("target_grade", ""),
                    r.get("effort_grade", ""),
                    att,
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
            self._stats_text.configure(state="normal")
            self._stats_text.delete("1.0", "end")
            lines = [
                f"=== {t('baseline_assessment.management')} - {t('common.summary')} ===\n",
                f"{t('baseline_assessment.total_baselines')}:     {stats['total_baselines']}",
                f"{t('baseline_assessment.total_checkpoints')}:   {stats['total_checkpoints']}\n",
                f"--- {t('baseline_assessment.average_scores')} ---",
                f"  {t('baseline_assessment.english')}:  {stats['avg_english'] or 'N/A'}",
                f"  {t('baseline_assessment.maths')}:    {stats['avg_maths'] or 'N/A'}",
                f"  {t('baseline_assessment.ict')}:      {stats['avg_ict'] or 'N/A'}\n",
                f"--- {t('baseline_assessment.by_type')} ---",
            ]
            for btype, cnt in stats.get("by_type", {}).items():
                lines.append(f"  {btype or 'unspecified':20s} {cnt}")
            self._stats_text.insert("end", "\n".join(lines))
            self._stats_text.configure(state="disabled")
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ── Baseline dialogs ──────────────────────────────────────────────

    def _new_baseline(self):
        self._baseline_dialog(t("baseline_assessment.new_baseline"))

    def _edit_baseline(self):
        sel = self._bl_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        record = self._svc.get_baseline(int(sel[0]))
        if not record:
            messagebox.showerror(t("common.error"), t("common.not_found"))
            return
        self._baseline_dialog(t("baseline_assessment.edit_baseline"), record)

    def _view_baseline(self):
        sel = self._bl_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        record = self._svc.get_baseline(int(sel[0]))
        if not record:
            messagebox.showerror(t("common.error"), t("common.not_found"))
            return
        win = tk.Toplevel(self)
        win.title(t("baseline_assessment.baseline_details"))
        win.geometry("450x500")
        text = tk.Text(win, font=("Consolas", 10), state="disabled", wrap="word")
        text.pack(fill="both", expand=True, padx=10, pady=10)
        text.configure(state="normal")
        for k, v in record.items():
            text.insert("end", f"{k}: {v}\n")
        text.configure(state="disabled")
        ttk.Button(win, text=t("common.close"), command=win.destroy).pack(pady=5)

    def _baseline_dialog(self, title, record=None):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("450x550")
        win.configure(bg="#ecf0f1")

        canvas = tk.Canvas(win, bg="#ecf0f1")
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        form = tk.Frame(canvas, bg="#ecf0f1", padx=15, pady=15)

        form.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        entries = {}
        row = 0
        field_defs = [
            (t("baseline_assessment.student_id") + "*", "student_id", "entry"),
            (t("baseline_assessment.year"), "academic_year", "entry"),
            (t("baseline_assessment.type"), "assessment_type", "combo",
             ["initial", "mid-year", "end-of-year", "diagnostic"]),
            (t("baseline_assessment.assessment_date"), "assessment_date", "entry"),
            (t("baseline_assessment.english") + " " + t("baseline_assessment.score"), "english_score", "entry"),
            (t("baseline_assessment.maths") + " " + t("baseline_assessment.score"), "maths_score", "entry"),
            (t("baseline_assessment.ict") + " " + t("baseline_assessment.score"), "ict_score", "entry"),
            (t("baseline_assessment.learning_style"), "learning_style", "combo",
             ["visual", "auditory", "kinesthetic", "read-write"]),
            (t("baseline_assessment.prior_attainment"), "prior_attainment", "entry"),
            (t("baseline_assessment.gcse_english"), "gcse_english_grade", "entry"),
            (t("baseline_assessment.gcse_maths"), "gcse_maths_grade", "entry"),
            (t("baseline_assessment.overall"), "overall_baseline", "entry"),
            (t("baseline_assessment.additional_needs"), "additional_needs_identified", "entry"),
            (t("baseline_assessment.assessor_id"), "assessor_id", "entry"),
            (t("common.notes"), "notes", "text"),
        ]
        for fdef in field_defs:
            label_text, key = fdef[0], fdef[1]
            widget_type = fdef[2]
            tk.Label(form, text=f"{label_text}:", bg="#ecf0f1").grid(
                row=row, column=0, sticky="ne", padx=5, pady=4)
            if widget_type == "combo":
                var = tk.StringVar(value=str(record.get(key, "") or "") if record else "")
                cb = ttk.Combobox(form, textvariable=var, values=fdef[3],
                                  state="readonly", width=25)
                cb.grid(row=row, column=1, sticky="w", padx=5, pady=4)
                entries[key] = var
            elif widget_type == "text":
                txt_widget = tk.Text(form, width=30, height=4)
                txt_widget.grid(row=row, column=1, sticky="w", padx=5, pady=4)
                if record and record.get(key):
                    txt_widget.insert("1.0", str(record[key]))
                entries[key] = txt_widget
            else:
                e = tk.Entry(form, width=28)
                e.grid(row=row, column=1, sticky="w", padx=5, pady=4)
                if record and record.get(key) is not None:
                    e.insert(0, str(record[key]))
                entries[key] = e
            row += 1

        def save():
            try:
                kwargs = {}
                for fdef in field_defs:
                    key = fdef[1]
                    widget = entries[key]
                    if isinstance(widget, tk.StringVar):
                        val = widget.get().strip()
                    elif isinstance(widget, tk.Text):
                        val = widget.get("1.0", "end").strip()
                    else:
                        val = widget.get().strip()
                    if val:
                        if key in ("english_score", "maths_score", "ict_score"):
                            kwargs[key] = float(val)
                        elif key in ("student_id", "assessor_id"):
                            kwargs[key] = int(val)
                        else:
                            kwargs[key] = val

                if record:
                    kwargs.pop("student_id", None)
                    self._svc.update_baseline(record["id"], **kwargs)
                    messagebox.showinfo(t("common.success"), t("common.updated_success"))
                else:
                    if "student_id" not in kwargs:
                        messagebox.showerror(t("common.error"), t("common.field_required"))
                        return
                    sid = kwargs.pop("student_id")
                    self._svc.create_baseline(sid, **kwargs)
                    messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_baselines()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(form, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=15)

    def _delete_baseline(self):
        sel = self._bl_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        if not messagebox.askyesno(t("common.confirm_delete"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_baseline(int(sel[0]))
            self._load_baselines()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ── Checkpoint dialogs ────────────────────────────────────────────

    def _new_checkpoint(self):
        self._checkpoint_dialog(t("baseline_assessment.new_checkpoint"))

    def _edit_checkpoint(self):
        sel = self._cp_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        record = self._svc.get_checkpoint(int(sel[0]))
        if not record:
            messagebox.showerror(t("common.error"), t("common.not_found"))
            return
        self._checkpoint_dialog(t("baseline_assessment.edit_checkpoint"), record)

    def _checkpoint_dialog(self, title, record=None):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("420x480")
        win.configure(bg="#ecf0f1")

        form = tk.Frame(win, bg="#ecf0f1", padx=15, pady=15)
        form.pack(fill="both", expand=True)

        entries = {}
        row = 0
        field_defs = [
            (t("baseline_assessment.student_id") + "*", "student_id", "entry"),
            (t("baseline_assessment.course") + " ID", "course_id", "entry"),
            (t("baseline_assessment.checkpoint_num"), "checkpoint_number", "entry"),
            (t("baseline_assessment.checkpoint_date") + "*", "checkpoint_date", "entry"),
            (t("baseline_assessment.current_grade"), "current_grade", "entry"),
            (t("baseline_assessment.target_grade"), "target_grade", "entry"),
            (t("baseline_assessment.effort"), "effort_grade", "combo",
             ["1", "2", "3", "4", "5"]),
            (t("baseline_assessment.attendance_pct"), "attendance_pct", "entry"),
            (t("baseline_assessment.concerns"), "concerns", "text"),
            (t("baseline_assessment.actions"), "actions", "text"),
            (t("baseline_assessment.reviewer_id"), "reviewer_id", "entry"),
        ]
        for fdef in field_defs:
            label_text, key = fdef[0], fdef[1]
            widget_type = fdef[2]
            tk.Label(form, text=f"{label_text}:", bg="#ecf0f1").grid(
                row=row, column=0, sticky="ne", padx=5, pady=4)
            if widget_type == "combo":
                var = tk.StringVar(value=str(record.get(key, "") or "") if record else "")
                cb = ttk.Combobox(form, textvariable=var, values=fdef[3],
                                  state="readonly", width=25)
                cb.grid(row=row, column=1, sticky="w", padx=5, pady=4)
                entries[key] = var
            elif widget_type == "text":
                txt_widget = tk.Text(form, width=30, height=3)
                txt_widget.grid(row=row, column=1, sticky="w", padx=5, pady=4)
                if record and record.get(key):
                    txt_widget.insert("1.0", str(record[key]))
                entries[key] = txt_widget
            else:
                e = tk.Entry(form, width=28)
                e.grid(row=row, column=1, sticky="w", padx=5, pady=4)
                if record and record.get(key) is not None:
                    e.insert(0, str(record[key]))
                entries[key] = e
            row += 1

        def save():
            try:
                kwargs = {}
                for fdef in field_defs:
                    key = fdef[1]
                    widget = entries[key]
                    if isinstance(widget, tk.StringVar):
                        val = widget.get().strip()
                    elif isinstance(widget, tk.Text):
                        val = widget.get("1.0", "end").strip()
                    else:
                        val = widget.get().strip()
                    if val:
                        if key in ("student_id", "course_id", "checkpoint_number",
                                   "reviewer_id"):
                            kwargs[key] = int(val)
                        elif key == "attendance_pct":
                            kwargs[key] = float(val)
                        else:
                            kwargs[key] = val

                if record:
                    kwargs.pop("student_id", None)
                    kwargs.pop("checkpoint_date", None)
                    self._svc.update_checkpoint(record["id"], **kwargs)
                    messagebox.showinfo(t("common.success"), t("common.updated_success"))
                else:
                    if "student_id" not in kwargs:
                        messagebox.showerror(t("common.error"), t("common.field_required"))
                        return
                    if "checkpoint_date" not in kwargs:
                        messagebox.showerror(t("common.error"), t("common.field_required"))
                        return
                    sid = kwargs.pop("student_id")
                    cp_date = kwargs.pop("checkpoint_date")
                    self._svc.create_checkpoint(sid, cp_date, **kwargs)
                    messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_checkpoints()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(form, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=15)

    def _delete_checkpoint(self):
        sel = self._cp_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        if not messagebox.askyesno(t("common.confirm_delete"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_checkpoint(int(sel[0]))
            self._load_checkpoints()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._bl_tree, "baseline_assessments.csv")

    # ── Public refresh ─────────────────────────────────────────────────

    def refresh(self):
        self._load_baselines()
        self._load_checkpoints()
        self._load_stats()
