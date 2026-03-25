"""Data Export & ILR GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.data_export.services.data_export_service import DataExportService
from education_system.college_system.core.i18n import t


class DataExportFrame(tk.Frame):
    """Data Export & ILR management frame."""

    EXPORT_TYPES = ["", "ILR", "school_census", "student_data", "staff_data",
                    "finance", "attendance", "custom"]
    STATUSES = ["", "pending", "running", "completed", "failed"]

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = DataExportService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("data_export.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_jobs_tab()
        self._build_templates_tab()
        self._build_stats_tab()

    # ── Tab 1: Export Jobs ───────────────────────────────────────────

    def _build_jobs_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("data_export.tab_jobs", default="Export Jobs"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 6))
        tk.Label(filt, text=t("common.type"), bg="#ecf0f1").pack(side="left")
        self._job_type_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._job_type_var,
                     values=self.EXPORT_TYPES, width=14,
                     state="readonly").pack(side="left", padx=5)
        tk.Label(filt, text=t("common.status"), bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._job_status_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._job_status_var,
                     values=self.STATUSES, width=12,
                     state="readonly").pack(side="left", padx=5)
        ttk.Button(filt, text=t("common.filter"), command=self._load_jobs).pack(side="left", padx=5)

        # Toolbar
        tb = tk.Frame(tab, bg="#ecf0f1")
        tb.pack(fill="x", pady=(0, 6))
        ttk.Button(tb, text=t("data_export.new_job", default="New Job"), command=self._new_job).pack(side="left", padx=2)
        ttk.Button(tb, text=t("common.view"), command=self._view_job).pack(side="left", padx=2)
        ttk.Button(tb, text=t("data_export.start", default="Start"), command=self._start_job).pack(side="left", padx=2)
        ttk.Button(tb, text=t("data_export.complete", default="Complete"), command=self._complete_job).pack(side="left", padx=2)
        ttk.Button(tb, text=t("common.delete"), command=self._delete_job).pack(side="left", padx=2)
        ttk.Button(tb, text="Export CSV", command=self._export_jobs_csv).pack(side="left", padx=2)

        # Treeview
        cols = ("id", "export_type", "academic_year", "description",
                "record_count", "validation_errors", "status",
                "started_at", "completed_at")
        self._job_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                      selectmode="browse")
        for c, h, w in [
            ("id", t("common.id"), 40), ("export_type", t("common.type"), 100),
            ("academic_year", t("data_export.year", default="Year"), 70), ("description", t("common.description"), 180),
            ("record_count", t("data_export.records", default="Records"), 65), ("validation_errors", t("data_export.errors", default="Errors"), 55),
            ("status", t("common.status"), 80), ("started_at", t("data_export.started", default="Started"), 130),
            ("completed_at", t("common.completed"), 130),
        ]:
            self._job_tree.heading(c, text=h)
            self._job_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._job_tree.yview)
        self._job_tree.configure(yscrollcommand=vsb.set)
        self._job_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _load_jobs(self):
        self._job_tree.delete(*self._job_tree.get_children())
        try:
            etype = self._job_type_var.get() or None
            status = self._job_status_var.get() or None
            jobs = self._svc.list_jobs(export_type=etype, status=status)
            for j in jobs:
                self._job_tree.insert("", "end", iid=j["id"], values=(
                    j["id"], j.get("export_type", ""),
                    j.get("academic_year", ""), j.get("description", ""),
                    j.get("record_count", 0), j.get("validation_errors", 0),
                    j.get("status", ""), j.get("started_at", ""),
                    j.get("completed_at", ""),
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _selected_job_id(self):
        sel = self._job_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("data_export.select_job", default="Please select an export job."))
            return None
        return int(sel[0])

    def _new_job(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("data_export.new_job", default="New Export Job"))
        dlg.geometry("400x300")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        frm = tk.Frame(dlg, bg="#ecf0f1", padx=15, pady=15)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text=t("data_export.export_type_label", default="Export Type:"), bg="#ecf0f1").grid(row=0, column=0, sticky="w", pady=4)
        type_var = tk.StringVar()
        ttk.Combobox(frm, textvariable=type_var,
                     values=self.EXPORT_TYPES[1:], width=20,
                     state="readonly").grid(row=0, column=1, pady=4)

        tk.Label(frm, text=t("data_export.academic_year_label", default="Academic Year:"), bg="#ecf0f1").grid(row=1, column=0, sticky="w", pady=4)
        year_var = tk.StringVar()
        ttk.Entry(frm, textvariable=year_var, width=22).grid(row=1, column=1, pady=4)

        tk.Label(frm, text=t("common.description"), bg="#ecf0f1").grid(row=2, column=0, sticky="w", pady=4)
        desc_text = tk.Text(frm, width=22, height=4)
        desc_text.grid(row=2, column=1, pady=4)

        def _save():
            etype = type_var.get()
            if not etype:
                messagebox.showwarning(t("common.validation"), t("data_export.export_type_required", default="Export Type is required."), parent=dlg)
                return
            try:
                self._svc.create_job(
                    export_type=etype,
                    academic_year=year_var.get().strip() or None,
                    description=desc_text.get("1.0", "end").strip() or None,
                )
                dlg.destroy()
                self._load_jobs()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e), parent=dlg)

        ttk.Button(frm, text=t("common.create"), command=_save).grid(row=3, column=1, pady=10, sticky="e")

    def _view_job(self):
        jid = self._selected_job_id()
        if jid is None:
            return
        try:
            j = self._svc.get_job(jid)
            if not j:
                messagebox.showinfo(t("common.info"), t("data_export.job_not_found", default="Job not found."))
                return
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Export Job #{j['id']}")
        dlg.geometry("450x400")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)

        frm = tk.Frame(dlg, bg="#ecf0f1", padx=15, pady=15)
        frm.pack(fill="both", expand=True)
        fields = [
            (t("common.id"), j.get("id")), (t("common.type"), j.get("export_type")),
            (t("data_export.year", default="Academic Year"), j.get("academic_year", "")),
            (t("common.description"), j.get("description", "")),
            (t("common.status"), j.get("status")),
            (t("data_export.records", default="Records"), j.get("record_count", 0)),
            (t("data_export.errors", default="Errors"), j.get("validation_errors", 0)),
            (t("data_export.warnings", default="Warnings"), j.get("validation_warnings", 0)),
            (t("data_export.file_path", default="File Path"), j.get("file_path", "")),
            (t("data_export.started", default="Started"), j.get("started_at", "")),
            (t("common.completed"), j.get("completed_at", "")),
            (t("common.created_at"), j.get("created_at", "")),
        ]
        for i, (label, val) in enumerate(fields):
            tk.Label(frm, text=f"{label}:", bg="#ecf0f1",
                     font=("Helvetica", 10, "bold")).grid(row=i, column=0, sticky="w", pady=2)
            tk.Label(frm, text=str(val or ""), bg="#ecf0f1",
                     wraplength=280, justify="left").grid(row=i, column=1, sticky="w", padx=8, pady=2)

        if j.get("validation_log"):
            tk.Label(frm, text=t("data_export.validation_log", default="Validation Log") + ":", bg="#ecf0f1",
                     font=("Helvetica", 10, "bold")).grid(
                row=len(fields), column=0, sticky="nw", pady=2)
            log_text = tk.Text(frm, width=35, height=5)
            log_text.grid(row=len(fields), column=1, pady=2)
            log_text.insert("1.0", j["validation_log"])
            log_text.configure(state="disabled")

    def _start_job(self):
        jid = self._selected_job_id()
        if jid is None:
            return
        try:
            self._svc.start_job(jid)
            self._load_jobs()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _complete_job(self):
        jid = self._selected_job_id()
        if jid is None:
            return

        dlg = tk.Toplevel(self)
        dlg.title(t("data_export.complete_job", default="Complete Export Job"))
        dlg.geometry("380x250")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        frm = tk.Frame(dlg, bg="#ecf0f1", padx=15, pady=15)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text=t("data_export.record_count_label", default="Record Count:"), bg="#ecf0f1").grid(row=0, column=0, sticky="w", pady=4)
        count_var = tk.StringVar(value="0")
        ttk.Entry(frm, textvariable=count_var, width=22).grid(row=0, column=1, pady=4)

        tk.Label(frm, text=t("data_export.file_path_label", default="File Path:"), bg="#ecf0f1").grid(row=1, column=0, sticky="w", pady=4)
        path_var = tk.StringVar()
        ttk.Entry(frm, textvariable=path_var, width=22).grid(row=1, column=1, pady=4)

        tk.Label(frm, text=t("data_export.errors_label", default="Errors:"), bg="#ecf0f1").grid(row=2, column=0, sticky="w", pady=4)
        err_var = tk.StringVar(value="0")
        ttk.Entry(frm, textvariable=err_var, width=22).grid(row=2, column=1, pady=4)

        tk.Label(frm, text=t("data_export.warnings_label", default="Warnings:"), bg="#ecf0f1").grid(row=3, column=0, sticky="w", pady=4)
        warn_var = tk.StringVar(value="0")
        ttk.Entry(frm, textvariable=warn_var, width=22).grid(row=3, column=1, pady=4)

        def _save():
            try:
                self._svc.complete_job(
                    jid,
                    record_count=int(count_var.get()),
                    file_path=path_var.get().strip(),
                    errors=int(err_var.get()),
                    warnings=int(warn_var.get()),
                )
                dlg.destroy()
                self._load_jobs()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e), parent=dlg)

        ttk.Button(frm, text=t("data_export.complete", default="Complete"), command=_save).grid(row=4, column=1, pady=10, sticky="e")

    def _delete_job(self):
        jid = self._selected_job_id()
        if jid is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("data_export.delete_job_confirm", default="Delete export job #{id}?").format(id=jid)):
            return
        try:
            self._svc.delete_job(jid)
            self._load_jobs()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ── Tab 2: Templates ─────────────────────────────────────────────

    def _build_templates_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("data_export.tab_templates", default="Templates"))

        # Filter
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 6))
        tk.Label(filt, text=t("common.type"), bg="#ecf0f1").pack(side="left")
        self._tpl_type_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._tpl_type_var,
                     values=self.EXPORT_TYPES, width=14,
                     state="readonly").pack(side="left", padx=5)
        ttk.Button(filt, text=t("common.filter"), command=self._load_templates).pack(side="left", padx=5)

        # Toolbar
        tb = tk.Frame(tab, bg="#ecf0f1")
        tb.pack(fill="x", pady=(0, 6))
        ttk.Button(tb, text=t("data_export.new_template", default="New Template"), command=self._new_template).pack(side="left", padx=2)
        ttk.Button(tb, text=t("common.edit"), command=self._edit_template).pack(side="left", padx=2)
        ttk.Button(tb, text=t("data_export.toggle_active", default="Toggle Active"), command=self._toggle_template).pack(side="left", padx=2)
        ttk.Button(tb, text=t("common.delete"), command=self._delete_template).pack(side="left", padx=2)
        ttk.Button(tb, text="Export CSV", command=self._export_templates_csv).pack(side="left", padx=2)

        # Treeview
        cols = ("id", "template_name", "export_type", "field_mapping", "is_active")
        self._tpl_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                      selectmode="browse")
        for c, h, w in [
            ("id", t("common.id"), 40), ("template_name", t("common.name"), 180),
            ("export_type", t("common.type"), 100), ("field_mapping", t("data_export.fields", default="Fields"), 200),
            ("is_active", t("common.active"), 60),
        ]:
            self._tpl_tree.heading(c, text=h)
            self._tpl_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tpl_tree.yview)
        self._tpl_tree.configure(yscrollcommand=vsb.set)
        self._tpl_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _load_templates(self):
        self._tpl_tree.delete(*self._tpl_tree.get_children())
        try:
            etype = self._tpl_type_var.get() or None
            templates = self._svc.list_templates(export_type=etype)
            for tpl in templates:
                active_str = t("common.yes") if tpl.get("is_active") else t("common.no")
                self._tpl_tree.insert("", "end", iid=tpl["id"], values=(
                    tpl["id"], tpl.get("template_name", ""),
                    tpl.get("export_type", ""),
                    tpl.get("field_mapping", "") or "",
                    active_str,
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _selected_tpl_id(self):
        sel = self._tpl_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("data_export.select_template", default="Please select a template."))
            return None
        return int(sel[0])

    def _new_template(self):
        self._template_dialog()

    def _edit_template(self):
        tid = self._selected_tpl_id()
        if tid is None:
            return
        try:
            tpl = self._svc.get_template(tid)
            if not tpl:
                messagebox.showinfo(t("common.info"), t("data_export.template_not_found", default="Template not found."))
                return
            self._template_dialog(tpl)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _template_dialog(self, existing=None):
        dlg = tk.Toplevel(self)
        dlg.title(t("data_export.edit_template", default="Edit Template") if existing else t("data_export.new_template", default="New Template"))
        dlg.geometry("420x320")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        frm = tk.Frame(dlg, bg="#ecf0f1", padx=15, pady=15)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text=t("common.name"), bg="#ecf0f1").grid(row=0, column=0, sticky="w", pady=4)
        name_var = tk.StringVar(value=existing.get("template_name", "") if existing else "")
        ttk.Entry(frm, textvariable=name_var, width=28).grid(row=0, column=1, pady=4)

        tk.Label(frm, text=t("data_export.export_type_label", default="Export Type:"), bg="#ecf0f1").grid(row=1, column=0, sticky="w", pady=4)
        type_var = tk.StringVar(value=existing.get("export_type", "") if existing else "")
        ttk.Combobox(frm, textvariable=type_var,
                     values=self.EXPORT_TYPES[1:], width=26,
                     state="readonly").grid(row=1, column=1, pady=4)

        tk.Label(frm, text=t("data_export.field_mapping_label", default="Field Mapping:"), bg="#ecf0f1").grid(row=2, column=0, sticky="nw", pady=4)
        field_text = tk.Text(frm, width=28, height=4)
        field_text.grid(row=2, column=1, pady=4)
        if existing and existing.get("field_mapping"):
            field_text.insert("1.0", existing["field_mapping"])

        tk.Label(frm, text=t("data_export.filters_label", default="Filters:"), bg="#ecf0f1").grid(row=3, column=0, sticky="nw", pady=4)
        filt_text = tk.Text(frm, width=28, height=3)
        filt_text.grid(row=3, column=1, pady=4)
        if existing and existing.get("filters"):
            filt_text.insert("1.0", existing["filters"])

        def _save():
            name = name_var.get().strip()
            etype = type_var.get()
            if not name or not etype:
                messagebox.showwarning(t("common.validation"), t("data_export.name_type_required", default="Name and Type are required."), parent=dlg)
                return
            kwargs = {
                "field_mapping": field_text.get("1.0", "end").strip() or None,
                "filters": filt_text.get("1.0", "end").strip() or None,
            }
            try:
                if existing:
                    self._svc.update_template(
                        existing["id"],
                        template_name=name,
                        export_type=etype,
                        **kwargs,
                    )
                else:
                    self._svc.create_template(name, etype, **kwargs)
                dlg.destroy()
                self._load_templates()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e), parent=dlg)

        ttk.Button(frm, text=t("common.save"), command=_save).grid(row=4, column=1, pady=10, sticky="e")

    def _toggle_template(self):
        tid = self._selected_tpl_id()
        if tid is None:
            return
        try:
            self._svc.toggle_active(tid)
            self._load_templates()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _delete_template(self):
        tid = self._selected_tpl_id()
        if tid is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("data_export.delete_template_confirm", default="Delete template #{id}?").format(id=tid)):
            return
        try:
            self._svc.delete_template(tid)
            self._load_templates()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ── Tab 3: Statistics ────────────────────────────────────────────

    def _build_stats_tab(self):
        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(self._stats_tab, text=t("data_export.tab_statistics", default="Statistics"))

        self._stats_text = tk.Text(self._stats_tab, wrap="word",
                                   font=("Courier", 11), state="disabled")
        self._stats_text.pack(fill="both", expand=True)

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        self._stats_text.configure(state="normal")
        self._stats_text.delete("1.0", "end")

        lines = [
            f"=== {t('data_export.statistics_title', default='Data Export Statistics')} ===\n",
            f"{t('data_export.total_export_jobs', default='Total Export Jobs')}:     {stats['total_jobs']}",
            "",
            t("data_export.jobs_by_status", default="Jobs by Status") + ":",
        ]
        for s, c in stats.get("by_status", {}).items():
            lines.append(f"  {s:<16} {c}")
        lines.append("")
        lines.append(t("data_export.jobs_by_type", default="Jobs by Type") + ":")
        for tp, c in stats.get("by_type", {}).items():
            lines.append(f"  {tp:<16} {c}")
        lines.append("")
        lines.append(f"{t('data_export.total_templates', default='Total Templates')}:      {stats['total_templates']}")
        lines.append(f"{t('data_export.active_templates', default='Active Templates')}:     {stats['active_templates']}")

        self._stats_text.insert("1.0", "\n".join(lines))
        self._stats_text.configure(state="disabled")

    # ── Refresh ──────────────────────────────────────────────────────

    def _export_jobs_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._job_tree, "data_export_jobs.csv")

    def _export_templates_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tpl_tree, "data_export_templates.csv")

    def refresh(self):
        self._load_jobs()
        self._load_templates()
        self._load_stats()
