"""Study Programmes GUI module."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
from education_system.college_system.modules.domain.study_programmes.services.study_programmes_service import (
    StudyProgrammesService,
)


class StudyProgrammesFrame(tk.Frame):
    """Study Programmes management frame with four tabs."""

    PROG_TYPES = ("", "level3", "level2", "level1", "entry", "traineeship", "t_level")
    STATUSES = ("", "active", "completed", "withdrawn", "transferred")
    REQ_STATUSES = ("not_met", "met", "exempt", "enrolled")
    COMP_TYPES = ("", "qualification", "work_experience", "enrichment",
                  "tutorial", "maths_english", "pastoral")
    COMP_STATUSES = ("active", "completed", "withdrawn")

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self.svc = StudyProgrammesService(db_path)
        self._build_ui()

    # ================================================================
    # UI Construction
    # ================================================================

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text=t("study_programmes.management"),
            font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_programmes_tab()
        self._build_components_tab()
        self._build_reports_tab()
        self._build_stats_tab()

    # -- Tab 1: Programmes -----------------------------------------------

    def _build_programmes_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("study_programmes.programmes"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left")
        self._prog_status_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._prog_status_var,
                     values=self.STATUSES, width=12, state="readonly"
                     ).pack(side="left", padx=(2, 10))

        tk.Label(filt, text=t("common.type") + ":", bg="#ecf0f1").pack(side="left")
        self._prog_type_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._prog_type_var,
                     values=self.PROG_TYPES, width=12, state="readonly"
                     ).pack(side="left", padx=(2, 10))

        tk.Label(filt, text=t("study_programmes.academic_year") + ":", bg="#ecf0f1").pack(side="left")
        self._prog_year_var = tk.StringVar()
        tk.Entry(filt, textvariable=self._prog_year_var, width=12).pack(side="left", padx=(2, 10))

        tk.Button(filt, text=t("common.filter"), command=self._load_programmes).pack(side="left", padx=5)

        # Treeview
        cols = ("id", "student_id", "academic_year", "type", "subst_qual",
                "maths", "english", "planned", "delivered", "valid", "status")
        tree_frame = tk.Frame(tab, bg="#ecf0f1")
        tree_frame.pack(fill="both", expand=True)
        self._prog_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [
            ("id", t("common.id"), 40), ("student_id", t("common.student_id"), 75),
            ("academic_year", t("study_programmes.acad_year"), 80),
            ("type", t("common.type"), 80),
            ("subst_qual", t("study_programmes.substantive_qual"), 150),
            ("maths", t("study_programmes.maths_req"), 75),
            ("english", t("study_programmes.english_req"), 75),
            ("planned", t("study_programmes.planned_hrs"), 80),
            ("delivered", t("study_programmes.delivered_hrs"), 85),
            ("valid", t("study_programmes.valid"), 45),
            ("status", t("common.status"), 80),
        ]:
            self._prog_tree.heading(c, text=h)
            self._prog_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._prog_tree.yview)
        self._prog_tree.configure(yscrollcommand=vsb.set)
        self._prog_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(5, 0))
        for txt, cmd in [
            (t("common.new"), self._new_programme), (t("common.view"), self._view_programme),
            (t("common.update"), self._update_programme),
            (t("study_programmes.validate"), self._validate_programme),
            (t("common.delete"), self._delete_programme),
        ]:
            tk.Button(btn_frame, text=txt, command=cmd, width=10).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="Export CSV", command=self._export_programmes_csv).pack(side="left", padx=3)

    # -- Tab 2: Components -----------------------------------------------

    def _build_components_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("study_programmes.components"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text=t("study_programmes.programme_id") + ":", bg="#ecf0f1").pack(side="left")
        self._comp_prog_var = tk.StringVar()
        tk.Entry(filt, textvariable=self._comp_prog_var, width=8).pack(side="left", padx=(2, 10))

        tk.Label(filt, text=t("common.type") + ":", bg="#ecf0f1").pack(side="left")
        self._comp_type_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._comp_type_var,
                     values=self.COMP_TYPES, width=16, state="readonly"
                     ).pack(side="left", padx=(2, 10))

        tk.Button(filt, text=t("common.filter"), command=self._load_components).pack(side="left", padx=5)

        # Treeview
        cols = ("id", "programme_id", "type", "name", "planned", "delivered", "status")
        tree_frame = tk.Frame(tab, bg="#ecf0f1")
        tree_frame.pack(fill="both", expand=True)
        self._comp_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [
            ("id", t("common.id"), 40),
            ("programme_id", t("study_programmes.programme_id"), 90),
            ("type", t("common.type"), 120), ("name", t("common.name"), 200),
            ("planned", t("study_programmes.planned_hrs"), 85),
            ("delivered", t("study_programmes.delivered_hrs"), 85),
            ("status", t("common.status"), 80),
        ]:
            self._comp_tree.heading(c, text=h)
            self._comp_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._comp_tree.yview)
        self._comp_tree.configure(yscrollcommand=vsb.set)
        self._comp_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(5, 0))
        for txt, cmd in [
            (t("common.new"), self._new_component), (t("common.update"), self._update_component),
            (t("common.delete"), self._delete_component),
        ]:
            tk.Button(btn_frame, text=txt, command=cmd, width=10).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="Export CSV", command=self._export_components_csv).pack(side="left", padx=3)

    # -- Tab 3: Reports --------------------------------------------------

    def _build_reports_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("study_programmes.reports"))

        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(0, 5))
        tk.Button(btn_frame, text=t("study_programmes.cof_check"),
                  command=self._report_cof, width=25).pack(side="left", padx=3)
        tk.Button(btn_frame, text=t("study_programmes.funding_hours_report"),
                  command=self._report_hours, width=25).pack(side="left", padx=3)

        self._report_text = tk.Text(tab, wrap="word", height=25, font=("Courier", 10))
        rsb = ttk.Scrollbar(tab, orient="vertical", command=self._report_text.yview)
        self._report_text.configure(yscrollcommand=rsb.set)
        self._report_text.pack(side="left", fill="both", expand=True)
        rsb.pack(side="right", fill="y")

    # -- Tab 4: Statistics ------------------------------------------------

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("common.summary"))

        self._stats_frame = tk.Frame(tab, bg="#ecf0f1")
        self._stats_frame.pack(fill="both", expand=True)

        tk.Button(tab, text=t("common.refresh"), command=self._load_stats).pack(pady=5)

    # ================================================================
    # Data Loading
    # ================================================================

    def _export_programmes_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._prog_tree, "study_programmes_export.csv")

    def _export_components_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._comp_tree, "study_programme_components_export.csv")

    def refresh(self):
        self._load_programmes()
        self._load_components()
        self._load_stats()

    def _load_programmes(self):
        self._prog_tree.delete(*self._prog_tree.get_children())
        try:
            status = self._prog_status_var.get() or None
            ptype = self._prog_type_var.get() or None
            year = self._prog_year_var.get().strip() or None
            for r in self.svc.list_programmes(status=status, programme_type=ptype,
                                              academic_year=year):
                self._prog_tree.insert("", "end", values=(
                    r["id"], r["student_id"],
                    r.get("academic_year") or "-",
                    r.get("programme_type") or "-",
                    r.get("substantive_qualification") or "-",
                    r.get("maths_requirement") or "-",
                    r.get("english_requirement") or "-",
                    r.get("total_planned_hours", 0),
                    r.get("total_delivered_hours", 0),
                    t("common.yes") if r.get("is_valid") else t("common.no"),
                    r.get("status") or "-",
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_components(self):
        self._comp_tree.delete(*self._comp_tree.get_children())
        try:
            prog_id_str = self._comp_prog_var.get().strip()
            prog_id = int(prog_id_str) if prog_id_str else None
            ctype = self._comp_type_var.get() or None
            for c in self.svc.list_components(programme_id=prog_id, component_type=ctype):
                self._comp_tree.insert("", "end", values=(
                    c["id"], c["programme_id"],
                    c.get("component_type") or "-",
                    c.get("component_name") or "-",
                    c.get("planned_hours", 0),
                    c.get("delivered_hours", 0),
                    c.get("status") or "-",
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_stats(self):
        for w in self._stats_frame.winfo_children():
            w.destroy()
        try:
            stats = self.svc.get_stats()
            labels = [
                (t("study_programmes.total_programmes"), stats["total_programmes"]),
                (t("study_programmes.active_programmes"), stats["active_programmes"]),
                (t("study_programmes.valid_programmes"), stats["valid_programmes"]),
                (t("study_programmes.invalid_programmes"), stats["invalid_programmes"]),
                (t("study_programmes.avg_planned_hours"), stats["avg_planned_hours"]),
                (t("study_programmes.avg_delivered_hours"), stats["avg_delivered_hours"]),
                (t("study_programmes.maths_met_pct"), f"{stats['maths_met_pct']}%"),
                (t("study_programmes.english_met_pct"), f"{stats['english_met_pct']}%"),
            ]
            for i, (label, value) in enumerate(labels):
                row = i // 2
                col = (i % 2) * 2
                tk.Label(self._stats_frame, text=f"{label}:", bg="#ecf0f1",
                         font=("Helvetica", 11, "bold"), anchor="e"
                         ).grid(row=row, column=col, sticky="e", padx=(10, 5), pady=4)
                tk.Label(self._stats_frame, text=str(value), bg="#ecf0f1",
                         font=("Helvetica", 11), anchor="w"
                         ).grid(row=row, column=col + 1, sticky="w", padx=(0, 20), pady=4)

            # By type breakdown
            row_offset = len(labels) // 2 + 1
            tk.Label(self._stats_frame, text=t("study_programmes.by_type") + ":", bg="#ecf0f1",
                     font=("Helvetica", 11, "bold")).grid(
                row=row_offset, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 2))
            for i, (ptype, cnt) in enumerate(stats.get("by_type", {}).items()):
                tk.Label(self._stats_frame, text=f"  {ptype}: {cnt}", bg="#ecf0f1",
                         font=("Helvetica", 10)).grid(
                    row=row_offset + 1 + i, column=0, columnspan=2, sticky="w", padx=20)

            # By status breakdown
            status_offset = row_offset + 1 + len(stats.get("by_type", {}))
            tk.Label(self._stats_frame, text=t("study_programmes.by_status") + ":", bg="#ecf0f1",
                     font=("Helvetica", 11, "bold")).grid(
                row=status_offset, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 2))
            for i, (st, cnt) in enumerate(stats.get("by_status", {}).items()):
                tk.Label(self._stats_frame, text=f"  {st}: {cnt}", bg="#ecf0f1",
                         font=("Helvetica", 10)).grid(
                    row=status_offset + 1 + i, column=0, columnspan=2, sticky="w", padx=20)
        except Exception as e:
            tk.Label(self._stats_frame, text=f"{t('common.error')}: {e}",
                     bg="#ecf0f1", fg="red").pack()

    # ================================================================
    # Programme Actions
    # ================================================================

    def _get_selected_prog_id(self):
        sel = self._prog_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return self._prog_tree.item(sel[0], "values")[0]

    def _new_programme(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("study_programmes.new_programme"))
        dlg.geometry("420x480")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, default, widget_type in [
            (t("common.student_id") + ":", "student_id", "", "entry"),
            (t("study_programmes.academic_year") + ":", "academic_year", "", "entry"),
            (t("study_programmes.programme_type") + ":", "programme_type", "level3", "combo"),
            (t("study_programmes.substantive_qual") + ":", "substantive_qualification", "", "entry"),
            (t("study_programmes.maths_req") + ":", "maths_requirement", "not_met", "reqcombo"),
            (t("study_programmes.english_req") + ":", "english_requirement", "not_met", "reqcombo"),
            (t("study_programmes.maths_enrollment_id") + ":", "maths_enrollment_id", "", "entry"),
            (t("study_programmes.english_enrollment_id") + ":", "english_enrollment_id", "", "entry"),
            (t("study_programmes.work_exp_completed") + ":", "work_experience_completed", "0", "entry"),
            (t("study_programmes.work_exp_hours") + ":", "work_experience_hours", "0", "entry"),
            (t("study_programmes.enrichment_hours") + ":", "enrichment_hours", "0", "entry"),
            (t("study_programmes.tutorial_hours") + ":", "tutorial_hours", "0", "entry"),
            (t("study_programmes.total_planned_hours") + ":", "total_planned_hours", "0", "entry"),
        ]:
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, sticky="e", padx=5, pady=3)
            var = tk.StringVar(value=default)
            if widget_type == "combo":
                w = ttk.Combobox(dlg, textvariable=var,
                                 values=list(self.PROG_TYPES[1:]), width=18, state="readonly")
            elif widget_type == "reqcombo":
                w = ttk.Combobox(dlg, textvariable=var,
                                 values=list(self.REQ_STATUSES), width=18, state="readonly")
            else:
                w = tk.Entry(dlg, textvariable=var, width=20)
            w.grid(row=row, column=1, sticky="w", padx=5, pady=3)
            fields[key] = var
            row += 1

        def _save():
            try:
                sid = int(fields["student_id"].get().strip())
                kwargs = {}
                for k, v_var in fields.items():
                    if k == "student_id":
                        continue
                    val = v_var.get().strip()
                    if not val:
                        continue
                    if k in ("maths_enrollment_id", "english_enrollment_id",
                             "work_experience_completed", "work_experience_hours",
                             "enrichment_hours", "tutorial_hours", "total_planned_hours"):
                        kwargs[k] = int(val)
                    else:
                        kwargs[k] = val
                self.svc.create_programme(sid, **kwargs)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                dlg.destroy()
                self._load_programmes()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        tk.Button(dlg, text=t("common.save"), command=_save, width=12).grid(
            row=row, column=0, columnspan=2, pady=10)

    def _view_programme(self):
        pid = self._get_selected_prog_id()
        if pid is None:
            return
        try:
            prog = self.svc.get_programme(int(pid))
            if not prog:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return

            dlg = tk.Toplevel(self)
            dlg.title(f"{t('study_programmes.programme')} #{pid}")
            dlg.geometry("500x520")
            dlg.configure(bg="#ecf0f1")
            dlg.transient(self)

            text_widget = tk.Text(dlg, wrap="word", font=("Courier", 10))
            text_widget.pack(fill="both", expand=True, padx=10, pady=10)

            text_widget.insert("end", f"{t('study_programmes.programme_id')}: {prog['id']}\n")
            text_widget.insert("end", f"{t('common.student_id')}: {prog['student_id']}\n")
            text_widget.insert("end", f"{t('tutorial.student')}: {prog.get('first_name', '')} {prog.get('last_name', '')}\n")
            text_widget.insert("end", f"{t('study_programmes.academic_year')}: {prog.get('academic_year') or '-'}\n")
            text_widget.insert("end", f"{t('study_programmes.programme_type')}: {prog.get('programme_type') or '-'}\n")
            text_widget.insert("end", f"{t('study_programmes.substantive_qual')}: {prog.get('substantive_qualification') or '-'}\n")
            text_widget.insert("end", f"{t('study_programmes.maths_req')}: {prog.get('maths_requirement') or '-'}\n")
            text_widget.insert("end", f"{t('study_programmes.english_req')}: {prog.get('english_requirement') or '-'}\n")
            text_widget.insert("end", f"{t('study_programmes.work_exp_completed')}: {t('common.yes') if prog.get('work_experience_completed') else t('common.no')}\n")
            text_widget.insert("end", f"{t('study_programmes.work_exp_hours')}: {prog.get('work_experience_hours', 0)}\n")
            text_widget.insert("end", f"{t('study_programmes.enrichment_hours')}: {prog.get('enrichment_hours', 0)}\n")
            text_widget.insert("end", f"{t('study_programmes.tutorial_hours')}: {prog.get('tutorial_hours', 0)}\n")
            text_widget.insert("end", f"{t('study_programmes.total_planned_hours')}: {prog.get('total_planned_hours', 0)}\n")
            text_widget.insert("end", f"{t('study_programmes.total_delivered_hours')}: {prog.get('total_delivered_hours', 0)}\n")
            text_widget.insert("end", f"{t('study_programmes.valid')}: {t('common.yes') if prog.get('is_valid') else t('common.no')}\n")
            text_widget.insert("end", f"{t('study_programmes.validation_notes')}: {prog.get('validation_notes') or '-'}\n")
            text_widget.insert("end", f"{t('common.status')}: {prog.get('status') or '-'}\n")
            text_widget.insert("end", f"\n{t('common.created_at')}: {prog.get('created_at') or '-'}\n")
            text_widget.insert("end", f"{t('common.updated_at')}: {prog.get('updated_at') or '-'}\n")

            # Show components
            comps = self.svc.list_components(programme_id=int(pid))
            if comps:
                text_widget.insert("end", f"\n--- {t('study_programmes.components')} ({len(comps)}) ---\n")
                for c in comps:
                    text_widget.insert("end",
                                f"  [{c['id']}] {c['component_type']}: {c['component_name']} "
                                f"({c.get('planned_hours', 0)}h {t('study_programmes.planned')}, "
                                f"{c.get('delivered_hours', 0)}h {t('study_programmes.delivered')}, "
                                f"{c.get('status', '-')})\n")

            text_widget.configure(state="disabled")
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _update_programme(self):
        pid = self._get_selected_prog_id()
        if pid is None:
            return
        try:
            prog = self.svc.get_programme(int(pid))
            if not prog:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('study_programmes.update_programme')} #{pid}")
        dlg.geometry("420x520")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, widget_type in [
            (t("study_programmes.academic_year") + ":", "academic_year", "entry"),
            (t("study_programmes.programme_type") + ":", "programme_type", "combo"),
            (t("study_programmes.substantive_qual") + ":", "substantive_qualification", "entry"),
            (t("study_programmes.maths_req") + ":", "maths_requirement", "reqcombo"),
            (t("study_programmes.english_req") + ":", "english_requirement", "reqcombo"),
            (t("study_programmes.maths_enrollment_id") + ":", "maths_enrollment_id", "entry"),
            (t("study_programmes.english_enrollment_id") + ":", "english_enrollment_id", "entry"),
            (t("study_programmes.work_exp_completed") + " (0/1):", "work_experience_completed", "entry"),
            (t("study_programmes.work_exp_hours") + ":", "work_experience_hours", "entry"),
            (t("study_programmes.enrichment_hours") + ":", "enrichment_hours", "entry"),
            (t("study_programmes.tutorial_hours") + ":", "tutorial_hours", "entry"),
            (t("study_programmes.total_planned_hours") + ":", "total_planned_hours", "entry"),
            (t("common.status") + ":", "status", "statuscombo"),
        ]:
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, sticky="e", padx=5, pady=3)
            current = prog.get(key) or ""
            var = tk.StringVar(value=str(current))
            if widget_type == "combo":
                w = ttk.Combobox(dlg, textvariable=var,
                                 values=list(self.PROG_TYPES[1:]), width=18, state="readonly")
            elif widget_type == "reqcombo":
                w = ttk.Combobox(dlg, textvariable=var,
                                 values=list(self.REQ_STATUSES), width=18, state="readonly")
            elif widget_type == "statuscombo":
                w = ttk.Combobox(dlg, textvariable=var,
                                 values=list(self.STATUSES[1:]), width=18, state="readonly")
            else:
                w = tk.Entry(dlg, textvariable=var, width=20)
            w.grid(row=row, column=1, sticky="w", padx=5, pady=3)
            fields[key] = var
            row += 1

        def _save():
            try:
                kwargs = {}
                for k, v_var in fields.items():
                    val = v_var.get().strip()
                    if not val:
                        continue
                    if k in ("maths_enrollment_id", "english_enrollment_id",
                             "work_experience_completed", "work_experience_hours",
                             "enrichment_hours", "tutorial_hours", "total_planned_hours"):
                        kwargs[k] = int(val)
                    else:
                        kwargs[k] = val
                if not kwargs:
                    messagebox.showwarning(t("common.warning"), t("study_programmes.no_changes"))
                    return
                self.svc.update_programme(int(pid), **kwargs)
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
                dlg.destroy()
                self._load_programmes()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        tk.Button(dlg, text=t("common.save"), command=_save, width=12).grid(
            row=row, column=0, columnspan=2, pady=10)

    def _validate_programme(self):
        pid = self._get_selected_prog_id()
        if pid is None:
            return
        try:
            result = self.svc.validate_programme(int(pid))
            valid = t("study_programmes.valid_result") if result.get("is_valid") else t("study_programmes.invalid_result")
            notes = result.get("validation_notes") or "-"
            messagebox.showinfo(t("study_programmes.validation_result"),
                                f"{t('study_programmes.programme')} #{pid}: {valid}\n\n{notes}")
            self._load_programmes()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _delete_programme(self):
        pid = self._get_selected_prog_id()
        if pid is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self.svc.delete_programme(int(pid))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_programmes()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ================================================================
    # Component Actions
    # ================================================================

    def _get_selected_comp_id(self):
        sel = self._comp_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return self._comp_tree.item(sel[0], "values")[0]

    def _new_component(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("study_programmes.new_component"))
        dlg.geometry("400x280")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, default, widget_type in [
            (t("study_programmes.programme_id") + ":", "programme_id", "", "entry"),
            (t("study_programmes.component_type") + ":", "component_type", "qualification", "typecombo"),
            (t("study_programmes.component_name") + ":", "component_name", "", "entry"),
            (t("study_programmes.planned_hrs") + ":", "planned_hours", "0", "entry"),
            (t("study_programmes.delivered_hrs") + ":", "delivered_hours", "0", "entry"),
            (t("common.status") + ":", "status", "active", "statuscombo"),
        ]:
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, sticky="e", padx=5, pady=3)
            var = tk.StringVar(value=default)
            if widget_type == "typecombo":
                w = ttk.Combobox(dlg, textvariable=var,
                                 values=list(self.COMP_TYPES[1:]), width=18, state="readonly")
            elif widget_type == "statuscombo":
                w = ttk.Combobox(dlg, textvariable=var,
                                 values=list(self.COMP_STATUSES), width=18, state="readonly")
            else:
                w = tk.Entry(dlg, textvariable=var, width=20)
            w.grid(row=row, column=1, sticky="w", padx=5, pady=3)
            fields[key] = var
            row += 1

        def _save():
            try:
                prog_id = int(fields["programme_id"].get().strip())
                ctype = fields["component_type"].get().strip()
                cname = fields["component_name"].get().strip()
                if not ctype or not cname:
                    messagebox.showwarning(t("common.validation"), t("common.both_required"))
                    return
                kwargs = {}
                ph = fields["planned_hours"].get().strip()
                if ph:
                    kwargs["planned_hours"] = int(ph)
                dh = fields["delivered_hours"].get().strip()
                if dh:
                    kwargs["delivered_hours"] = int(dh)
                st = fields["status"].get().strip()
                if st:
                    kwargs["status"] = st
                self.svc.create_component(prog_id, ctype, cname, **kwargs)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                dlg.destroy()
                self._load_components()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        tk.Button(dlg, text=t("common.save"), command=_save, width=12).grid(
            row=row, column=0, columnspan=2, pady=10)

    def _update_component(self):
        cid = self._get_selected_comp_id()
        if cid is None:
            return
        try:
            comp = self.svc.get_component(int(cid))
            if not comp:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('study_programmes.update_component')} #{cid}")
        dlg.geometry("400x250")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, widget_type in [
            (t("study_programmes.component_type") + ":", "component_type", "typecombo"),
            (t("study_programmes.component_name") + ":", "component_name", "entry"),
            (t("study_programmes.planned_hrs") + ":", "planned_hours", "entry"),
            (t("study_programmes.delivered_hrs") + ":", "delivered_hours", "entry"),
            (t("common.status") + ":", "status", "statuscombo"),
        ]:
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, sticky="e", padx=5, pady=3)
            current = comp.get(key) or ""
            var = tk.StringVar(value=str(current))
            if widget_type == "typecombo":
                w = ttk.Combobox(dlg, textvariable=var,
                                 values=list(self.COMP_TYPES[1:]), width=18, state="readonly")
            elif widget_type == "statuscombo":
                w = ttk.Combobox(dlg, textvariable=var,
                                 values=list(self.COMP_STATUSES), width=18, state="readonly")
            else:
                w = tk.Entry(dlg, textvariable=var, width=20)
            w.grid(row=row, column=1, sticky="w", padx=5, pady=3)
            fields[key] = var
            row += 1

        def _save():
            try:
                kwargs = {}
                for k, v_var in fields.items():
                    val = v_var.get().strip()
                    if not val:
                        continue
                    if k in ("planned_hours", "delivered_hours"):
                        kwargs[k] = int(val)
                    else:
                        kwargs[k] = val
                if not kwargs:
                    messagebox.showwarning(t("common.warning"), t("study_programmes.no_changes"))
                    return
                self.svc.update_component(int(cid), **kwargs)
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
                dlg.destroy()
                self._load_components()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        tk.Button(dlg, text=t("common.save"), command=_save, width=12).grid(
            row=row, column=0, columnspan=2, pady=10)

    def _delete_component(self):
        cid = self._get_selected_comp_id()
        if cid is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self.svc.delete_component(int(cid))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_components()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ================================================================
    # Reports
    # ================================================================

    def _report_cof(self):
        self._report_text.delete("1.0", "end")
        try:
            rows = self.svc.condition_of_funding_check()
            if not rows:
                self._report_text.insert("end", t("study_programmes.cof_all_met") + "\n")
                return
            self._report_text.insert("end",
                f"{t('study_programmes.cof_check')} - {len(rows)} {t('study_programmes.programmes_unmet')}\n")
            self._report_text.insert("end", "=" * 80 + "\n\n")
            self._report_text.insert("end",
                f"{t('common.id'):<6}{t('tutorial.student'):<25}{t('common.type'):<12}"
                f"{t('study_programmes.maths_req'):<12}{t('study_programmes.english_req'):<12}"
                f"{t('study_programmes.acad_year')}\n")
            self._report_text.insert("end", "-" * 80 + "\n")
            for r in rows:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or "-"
                self._report_text.insert("end",
                    f"{r['id']:<6}{name:<25}{r.get('programme_type', '-'):<12}"
                    f"{r.get('maths_requirement', '-'):<12}"
                    f"{r.get('english_requirement', '-'):<12}"
                    f"{r.get('academic_year') or '-'}\n")
        except Exception as e:
            self._report_text.insert("end", f"{t('common.error')}: {e}\n")

    def _report_hours(self):
        self._report_text.delete("1.0", "end")
        try:
            rows = self.svc.funding_hours_report()
            if not rows:
                self._report_text.insert("end", t("common.no_data") + "\n")
                return
            self._report_text.insert("end",
                f"{t('study_programmes.funding_hours_report')} - {len(rows)} {t('study_programmes.programme_count')}\n")
            self._report_text.insert("end", "=" * 90 + "\n\n")
            self._report_text.insert("end",
                f"{t('common.id'):<6}{t('tutorial.student'):<25}{t('common.type'):<12}"
                f"{t('study_programmes.acad_year'):<10}"
                f"{t('study_programmes.planned'):<10}{t('study_programmes.delivered'):<10}"
                f"{t('study_programmes.valid'):<8}{t('common.status')}\n")
            self._report_text.insert("end", "-" * 90 + "\n")
            total_planned = 0
            total_delivered = 0
            for r in rows:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or "-"
                planned = r.get("total_planned_hours", 0)
                delivered = r.get("total_delivered_hours", 0)
                total_planned += planned
                total_delivered += delivered
                self._report_text.insert("end",
                    f"{r['id']:<6}{name:<25}{r.get('programme_type', '-'):<12}"
                    f"{(r.get('academic_year') or '-'):<10}"
                    f"{planned:<10}{delivered:<10}"
                    f"{t('common.yes') if r.get('is_valid') else t('common.no'):<8}"
                    f"{r.get('status') or '-'}\n")
            self._report_text.insert("end", "-" * 90 + "\n")
            self._report_text.insert("end",
                f"{t('common.total').upper():<53}{total_planned:<10}{total_delivered}\n")
        except Exception as e:
            self._report_text.insert("end", f"{t('common.error')}: {e}\n")


# Backward-compatible alias for existing imports
StudyProgrammeFrame = StudyProgrammesFrame
