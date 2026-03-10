"""Data Export & ILR GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.data_export.services.data_export_service import DataExportService


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
        tk.Label(header, text="Data Export & ILR",
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
        self._nb.add(tab, text="Export Jobs")

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 6))
        tk.Label(filt, text="Type:", bg="#ecf0f1").pack(side="left")
        self._job_type_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._job_type_var,
                     values=self.EXPORT_TYPES, width=14,
                     state="readonly").pack(side="left", padx=5)
        tk.Label(filt, text="Status:", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._job_status_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._job_status_var,
                     values=self.STATUSES, width=12,
                     state="readonly").pack(side="left", padx=5)
        ttk.Button(filt, text="Filter", command=self._load_jobs).pack(side="left", padx=5)

        # Toolbar
        tb = tk.Frame(tab, bg="#ecf0f1")
        tb.pack(fill="x", pady=(0, 6))
        ttk.Button(tb, text="New Job", command=self._new_job).pack(side="left", padx=2)
        ttk.Button(tb, text="View", command=self._view_job).pack(side="left", padx=2)
        ttk.Button(tb, text="Start", command=self._start_job).pack(side="left", padx=2)
        ttk.Button(tb, text="Complete", command=self._complete_job).pack(side="left", padx=2)
        ttk.Button(tb, text="Delete", command=self._delete_job).pack(side="left", padx=2)

        # Treeview
        cols = ("id", "export_type", "academic_year", "description",
                "record_count", "validation_errors", "status",
                "started_at", "completed_at")
        self._job_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                      selectmode="browse")
        for c, h, w in [
            ("id", "ID", 40), ("export_type", "Type", 100),
            ("academic_year", "Year", 70), ("description", "Description", 180),
            ("record_count", "Records", 65), ("validation_errors", "Errors", 55),
            ("status", "Status", 80), ("started_at", "Started", 130),
            ("completed_at", "Completed", 130),
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
            messagebox.showerror("Error", str(e))

    def _selected_job_id(self):
        sel = self._job_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select an export job.")
            return None
        return int(sel[0])

    def _new_job(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Export Job")
        dlg.geometry("400x300")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        frm = tk.Frame(dlg, bg="#ecf0f1", padx=15, pady=15)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="Export Type:", bg="#ecf0f1").grid(row=0, column=0, sticky="w", pady=4)
        type_var = tk.StringVar()
        ttk.Combobox(frm, textvariable=type_var,
                     values=self.EXPORT_TYPES[1:], width=20,
                     state="readonly").grid(row=0, column=1, pady=4)

        tk.Label(frm, text="Academic Year:", bg="#ecf0f1").grid(row=1, column=0, sticky="w", pady=4)
        year_var = tk.StringVar()
        ttk.Entry(frm, textvariable=year_var, width=22).grid(row=1, column=1, pady=4)

        tk.Label(frm, text="Description:", bg="#ecf0f1").grid(row=2, column=0, sticky="w", pady=4)
        desc_text = tk.Text(frm, width=22, height=4)
        desc_text.grid(row=2, column=1, pady=4)

        def _save():
            etype = type_var.get()
            if not etype:
                messagebox.showwarning("Required", "Export Type is required.", parent=dlg)
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
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(frm, text="Create", command=_save).grid(row=3, column=1, pady=10, sticky="e")

    def _view_job(self):
        jid = self._selected_job_id()
        if jid is None:
            return
        try:
            j = self._svc.get_job(jid)
            if not j:
                messagebox.showinfo("Not Found", "Job not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Export Job #{j['id']}")
        dlg.geometry("450x400")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)

        frm = tk.Frame(dlg, bg="#ecf0f1", padx=15, pady=15)
        frm.pack(fill="both", expand=True)
        fields = [
            ("ID", j.get("id")), ("Type", j.get("export_type")),
            ("Academic Year", j.get("academic_year", "")),
            ("Description", j.get("description", "")),
            ("Status", j.get("status")),
            ("Records", j.get("record_count", 0)),
            ("Errors", j.get("validation_errors", 0)),
            ("Warnings", j.get("validation_warnings", 0)),
            ("File Path", j.get("file_path", "")),
            ("Started", j.get("started_at", "")),
            ("Completed", j.get("completed_at", "")),
            ("Created", j.get("created_at", "")),
        ]
        for i, (label, val) in enumerate(fields):
            tk.Label(frm, text=f"{label}:", bg="#ecf0f1",
                     font=("Helvetica", 10, "bold")).grid(row=i, column=0, sticky="w", pady=2)
            tk.Label(frm, text=str(val or ""), bg="#ecf0f1",
                     wraplength=280, justify="left").grid(row=i, column=1, sticky="w", padx=8, pady=2)

        if j.get("validation_log"):
            tk.Label(frm, text="Validation Log:", bg="#ecf0f1",
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
            messagebox.showerror("Error", str(e))

    def _complete_job(self):
        jid = self._selected_job_id()
        if jid is None:
            return

        dlg = tk.Toplevel(self)
        dlg.title("Complete Export Job")
        dlg.geometry("380x250")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        frm = tk.Frame(dlg, bg="#ecf0f1", padx=15, pady=15)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="Record Count:", bg="#ecf0f1").grid(row=0, column=0, sticky="w", pady=4)
        count_var = tk.StringVar(value="0")
        ttk.Entry(frm, textvariable=count_var, width=22).grid(row=0, column=1, pady=4)

        tk.Label(frm, text="File Path:", bg="#ecf0f1").grid(row=1, column=0, sticky="w", pady=4)
        path_var = tk.StringVar()
        ttk.Entry(frm, textvariable=path_var, width=22).grid(row=1, column=1, pady=4)

        tk.Label(frm, text="Errors:", bg="#ecf0f1").grid(row=2, column=0, sticky="w", pady=4)
        err_var = tk.StringVar(value="0")
        ttk.Entry(frm, textvariable=err_var, width=22).grid(row=2, column=1, pady=4)

        tk.Label(frm, text="Warnings:", bg="#ecf0f1").grid(row=3, column=0, sticky="w", pady=4)
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
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(frm, text="Complete", command=_save).grid(row=4, column=1, pady=10, sticky="e")

    def _delete_job(self):
        jid = self._selected_job_id()
        if jid is None:
            return
        if not messagebox.askyesno("Confirm", f"Delete export job #{jid}?"):
            return
        try:
            self._svc.delete_job(jid)
            self._load_jobs()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Tab 2: Templates ─────────────────────────────────────────────

    def _build_templates_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Templates")

        # Filter
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 6))
        tk.Label(filt, text="Type:", bg="#ecf0f1").pack(side="left")
        self._tpl_type_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._tpl_type_var,
                     values=self.EXPORT_TYPES, width=14,
                     state="readonly").pack(side="left", padx=5)
        ttk.Button(filt, text="Filter", command=self._load_templates).pack(side="left", padx=5)

        # Toolbar
        tb = tk.Frame(tab, bg="#ecf0f1")
        tb.pack(fill="x", pady=(0, 6))
        ttk.Button(tb, text="New Template", command=self._new_template).pack(side="left", padx=2)
        ttk.Button(tb, text="Edit", command=self._edit_template).pack(side="left", padx=2)
        ttk.Button(tb, text="Toggle Active", command=self._toggle_template).pack(side="left", padx=2)
        ttk.Button(tb, text="Delete", command=self._delete_template).pack(side="left", padx=2)

        # Treeview
        cols = ("id", "template_name", "export_type", "field_mapping", "is_active")
        self._tpl_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                      selectmode="browse")
        for c, h, w in [
            ("id", "ID", 40), ("template_name", "Name", 180),
            ("export_type", "Type", 100), ("field_mapping", "Fields", 200),
            ("is_active", "Active", 60),
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
            for t in templates:
                active_str = "Yes" if t.get("is_active") else "No"
                self._tpl_tree.insert("", "end", iid=t["id"], values=(
                    t["id"], t.get("template_name", ""),
                    t.get("export_type", ""),
                    t.get("field_mapping", "") or "",
                    active_str,
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_tpl_id(self):
        sel = self._tpl_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select a template.")
            return None
        return int(sel[0])

    def _new_template(self):
        self._template_dialog()

    def _edit_template(self):
        tid = self._selected_tpl_id()
        if tid is None:
            return
        try:
            t = self._svc.get_template(tid)
            if not t:
                messagebox.showinfo("Not Found", "Template not found.")
                return
            self._template_dialog(t)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _template_dialog(self, existing=None):
        dlg = tk.Toplevel(self)
        dlg.title("Edit Template" if existing else "New Template")
        dlg.geometry("420x320")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        frm = tk.Frame(dlg, bg="#ecf0f1", padx=15, pady=15)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="Name:", bg="#ecf0f1").grid(row=0, column=0, sticky="w", pady=4)
        name_var = tk.StringVar(value=existing.get("template_name", "") if existing else "")
        ttk.Entry(frm, textvariable=name_var, width=28).grid(row=0, column=1, pady=4)

        tk.Label(frm, text="Export Type:", bg="#ecf0f1").grid(row=1, column=0, sticky="w", pady=4)
        type_var = tk.StringVar(value=existing.get("export_type", "") if existing else "")
        ttk.Combobox(frm, textvariable=type_var,
                     values=self.EXPORT_TYPES[1:], width=26,
                     state="readonly").grid(row=1, column=1, pady=4)

        tk.Label(frm, text="Field Mapping:", bg="#ecf0f1").grid(row=2, column=0, sticky="nw", pady=4)
        field_text = tk.Text(frm, width=28, height=4)
        field_text.grid(row=2, column=1, pady=4)
        if existing and existing.get("field_mapping"):
            field_text.insert("1.0", existing["field_mapping"])

        tk.Label(frm, text="Filters:", bg="#ecf0f1").grid(row=3, column=0, sticky="nw", pady=4)
        filt_text = tk.Text(frm, width=28, height=3)
        filt_text.grid(row=3, column=1, pady=4)
        if existing and existing.get("filters"):
            filt_text.insert("1.0", existing["filters"])

        def _save():
            name = name_var.get().strip()
            etype = type_var.get()
            if not name or not etype:
                messagebox.showwarning("Required", "Name and Type are required.", parent=dlg)
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
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(frm, text="Save", command=_save).grid(row=4, column=1, pady=10, sticky="e")

    def _toggle_template(self):
        tid = self._selected_tpl_id()
        if tid is None:
            return
        try:
            self._svc.toggle_active(tid)
            self._load_templates()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_template(self):
        tid = self._selected_tpl_id()
        if tid is None:
            return
        if not messagebox.askyesno("Confirm", f"Delete template #{tid}?"):
            return
        try:
            self._svc.delete_template(tid)
            self._load_templates()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Tab 3: Statistics ────────────────────────────────────────────

    def _build_stats_tab(self):
        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(self._stats_tab, text="Statistics")

        self._stats_text = tk.Text(self._stats_tab, wrap="word",
                                   font=("Courier", 11), state="disabled")
        self._stats_text.pack(fill="both", expand=True)

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        self._stats_text.configure(state="normal")
        self._stats_text.delete("1.0", "end")

        lines = [
            "=== Data Export Statistics ===\n",
            f"Total Export Jobs:     {stats['total_jobs']}",
            "",
            "Jobs by Status:",
        ]
        for s, c in stats.get("by_status", {}).items():
            lines.append(f"  {s:<16} {c}")
        lines.append("")
        lines.append("Jobs by Type:")
        for t, c in stats.get("by_type", {}).items():
            lines.append(f"  {t:<16} {c}")
        lines.append("")
        lines.append(f"Total Templates:      {stats['total_templates']}")
        lines.append(f"Active Templates:     {stats['active_templates']}")

        self._stats_text.insert("1.0", "\n".join(lines))
        self._stats_text.configure(state="disabled")

    # ── Refresh ──────────────────────────────────────────────────────

    def refresh(self):
        self._load_jobs()
        self._load_templates()
        self._load_stats()
