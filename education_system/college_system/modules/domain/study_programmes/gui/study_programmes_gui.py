"""Study Programmes GUI module."""

import tkinter as tk
from tkinter import ttk, messagebox

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
            header, text="Study Programmes",
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
        self._nb.add(tab, text="Programmes")

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text="Status:", bg="#ecf0f1").pack(side="left")
        self._prog_status_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._prog_status_var,
                     values=self.STATUSES, width=12, state="readonly"
                     ).pack(side="left", padx=(2, 10))

        tk.Label(filt, text="Type:", bg="#ecf0f1").pack(side="left")
        self._prog_type_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._prog_type_var,
                     values=self.PROG_TYPES, width=12, state="readonly"
                     ).pack(side="left", padx=(2, 10))

        tk.Label(filt, text="Academic Year:", bg="#ecf0f1").pack(side="left")
        self._prog_year_var = tk.StringVar()
        tk.Entry(filt, textvariable=self._prog_year_var, width=12).pack(side="left", padx=(2, 10))

        tk.Button(filt, text="Filter", command=self._load_programmes).pack(side="left", padx=5)

        # Treeview
        cols = ("id", "student_id", "academic_year", "type", "subst_qual",
                "maths", "english", "planned", "delivered", "valid", "status")
        tree_frame = tk.Frame(tab, bg="#ecf0f1")
        tree_frame.pack(fill="both", expand=True)
        self._prog_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [
            ("id", "ID", 40), ("student_id", "Student ID", 75),
            ("academic_year", "Acad Year", 80), ("type", "Type", 80),
            ("subst_qual", "Substantive Qual", 150),
            ("maths", "Maths Req", 75), ("english", "English Req", 75),
            ("planned", "Planned Hrs", 80), ("delivered", "Delivered Hrs", 85),
            ("valid", "Valid", 45), ("status", "Status", 80),
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
        for text, cmd in [
            ("New", self._new_programme), ("View", self._view_programme),
            ("Update", self._update_programme), ("Validate", self._validate_programme),
            ("Delete", self._delete_programme),
        ]:
            tk.Button(btn_frame, text=text, command=cmd, width=10).pack(side="left", padx=3)

    # -- Tab 2: Components -----------------------------------------------

    def _build_components_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Components")

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text="Programme ID:", bg="#ecf0f1").pack(side="left")
        self._comp_prog_var = tk.StringVar()
        tk.Entry(filt, textvariable=self._comp_prog_var, width=8).pack(side="left", padx=(2, 10))

        tk.Label(filt, text="Type:", bg="#ecf0f1").pack(side="left")
        self._comp_type_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._comp_type_var,
                     values=self.COMP_TYPES, width=16, state="readonly"
                     ).pack(side="left", padx=(2, 10))

        tk.Button(filt, text="Filter", command=self._load_components).pack(side="left", padx=5)

        # Treeview
        cols = ("id", "programme_id", "type", "name", "planned", "delivered", "status")
        tree_frame = tk.Frame(tab, bg="#ecf0f1")
        tree_frame.pack(fill="both", expand=True)
        self._comp_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [
            ("id", "ID", 40), ("programme_id", "Programme ID", 90),
            ("type", "Type", 120), ("name", "Name", 200),
            ("planned", "Planned Hrs", 85), ("delivered", "Delivered Hrs", 85),
            ("status", "Status", 80),
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
        for text, cmd in [
            ("New", self._new_component), ("Update", self._update_component),
            ("Delete", self._delete_component),
        ]:
            tk.Button(btn_frame, text=text, command=cmd, width=10).pack(side="left", padx=3)

    # -- Tab 3: Reports --------------------------------------------------

    def _build_reports_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Reports")

        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(0, 5))
        tk.Button(btn_frame, text="Condition of Funding Check",
                  command=self._report_cof, width=25).pack(side="left", padx=3)
        tk.Button(btn_frame, text="Funding Hours Report",
                  command=self._report_hours, width=25).pack(side="left", padx=3)

        self._report_text = tk.Text(tab, wrap="word", height=25, font=("Courier", 10))
        rsb = ttk.Scrollbar(tab, orient="vertical", command=self._report_text.yview)
        self._report_text.configure(yscrollcommand=rsb.set)
        self._report_text.pack(side="left", fill="both", expand=True)
        rsb.pack(side="right", fill="y")

    # -- Tab 4: Statistics ------------------------------------------------

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Statistics")

        self._stats_frame = tk.Frame(tab, bg="#ecf0f1")
        self._stats_frame.pack(fill="both", expand=True)

        tk.Button(tab, text="Refresh Statistics", command=self._load_stats).pack(pady=5)

    # ================================================================
    # Data Loading
    # ================================================================

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
                    "Yes" if r.get("is_valid") else "No",
                    r.get("status") or "-",
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

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
            messagebox.showerror("Error", str(e))

    def _load_stats(self):
        for w in self._stats_frame.winfo_children():
            w.destroy()
        try:
            stats = self.svc.get_stats()
            labels = [
                ("Total Programmes", stats["total_programmes"]),
                ("Active Programmes", stats["active_programmes"]),
                ("Valid Programmes", stats["valid_programmes"]),
                ("Invalid Programmes", stats["invalid_programmes"]),
                ("Avg Planned Hours", stats["avg_planned_hours"]),
                ("Avg Delivered Hours", stats["avg_delivered_hours"]),
                ("Maths Met %", f"{stats['maths_met_pct']}%"),
                ("English Met %", f"{stats['english_met_pct']}%"),
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
            tk.Label(self._stats_frame, text="By Programme Type:", bg="#ecf0f1",
                     font=("Helvetica", 11, "bold")).grid(
                row=row_offset, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 2))
            for i, (ptype, cnt) in enumerate(stats.get("by_type", {}).items()):
                tk.Label(self._stats_frame, text=f"  {ptype}: {cnt}", bg="#ecf0f1",
                         font=("Helvetica", 10)).grid(
                    row=row_offset + 1 + i, column=0, columnspan=2, sticky="w", padx=20)

            # By status breakdown
            status_offset = row_offset + 1 + len(stats.get("by_type", {}))
            tk.Label(self._stats_frame, text="By Status:", bg="#ecf0f1",
                     font=("Helvetica", 11, "bold")).grid(
                row=status_offset, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 2))
            for i, (st, cnt) in enumerate(stats.get("by_status", {}).items()):
                tk.Label(self._stats_frame, text=f"  {st}: {cnt}", bg="#ecf0f1",
                         font=("Helvetica", 10)).grid(
                    row=status_offset + 1 + i, column=0, columnspan=2, sticky="w", padx=20)
        except Exception as e:
            tk.Label(self._stats_frame, text=f"Error loading stats: {e}",
                     bg="#ecf0f1", fg="red").pack()

    # ================================================================
    # Programme Actions
    # ================================================================

    def _get_selected_prog_id(self):
        sel = self._prog_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "No programme selected.")
            return None
        return self._prog_tree.item(sel[0], "values")[0]

    def _new_programme(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Study Programme")
        dlg.geometry("420x480")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, default, widget_type in [
            ("Student ID (PK):", "student_id", "", "entry"),
            ("Academic Year:", "academic_year", "", "entry"),
            ("Programme Type:", "programme_type", "level3", "combo"),
            ("Substantive Qualification:", "substantive_qualification", "", "entry"),
            ("Maths Requirement:", "maths_requirement", "not_met", "reqcombo"),
            ("English Requirement:", "english_requirement", "not_met", "reqcombo"),
            ("Maths Enrollment ID:", "maths_enrollment_id", "", "entry"),
            ("English Enrollment ID:", "english_enrollment_id", "", "entry"),
            ("Work Exp Completed:", "work_experience_completed", "0", "entry"),
            ("Work Exp Hours:", "work_experience_hours", "0", "entry"),
            ("Enrichment Hours:", "enrichment_hours", "0", "entry"),
            ("Tutorial Hours:", "tutorial_hours", "0", "entry"),
            ("Total Planned Hours:", "total_planned_hours", "0", "entry"),
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
                messagebox.showinfo("Success", "Programme created.")
                dlg.destroy()
                self._load_programmes()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        tk.Button(dlg, text="Save", command=_save, width=12).grid(
            row=row, column=0, columnspan=2, pady=10)

    def _view_programme(self):
        pid = self._get_selected_prog_id()
        if pid is None:
            return
        try:
            prog = self.svc.get_programme(int(pid))
            if not prog:
                messagebox.showwarning("Warning", "Programme not found.")
                return

            dlg = tk.Toplevel(self)
            dlg.title(f"Programme #{pid}")
            dlg.geometry("500x520")
            dlg.configure(bg="#ecf0f1")
            dlg.transient(self)

            text = tk.Text(dlg, wrap="word", font=("Courier", 10))
            text.pack(fill="both", expand=True, padx=10, pady=10)

            text.insert("end", f"Programme ID: {prog['id']}\n")
            text.insert("end", f"Student ID: {prog['student_id']}\n")
            text.insert("end", f"Student: {prog.get('first_name', '')} {prog.get('last_name', '')}\n")
            text.insert("end", f"Academic Year: {prog.get('academic_year') or '-'}\n")
            text.insert("end", f"Programme Type: {prog.get('programme_type') or '-'}\n")
            text.insert("end", f"Substantive Qual: {prog.get('substantive_qualification') or '-'}\n")
            text.insert("end", f"Maths Requirement: {prog.get('maths_requirement') or '-'}\n")
            text.insert("end", f"English Requirement: {prog.get('english_requirement') or '-'}\n")
            text.insert("end", f"Work Exp Completed: {'Yes' if prog.get('work_experience_completed') else 'No'}\n")
            text.insert("end", f"Work Exp Hours: {prog.get('work_experience_hours', 0)}\n")
            text.insert("end", f"Enrichment Hours: {prog.get('enrichment_hours', 0)}\n")
            text.insert("end", f"Tutorial Hours: {prog.get('tutorial_hours', 0)}\n")
            text.insert("end", f"Total Planned Hours: {prog.get('total_planned_hours', 0)}\n")
            text.insert("end", f"Total Delivered Hours: {prog.get('total_delivered_hours', 0)}\n")
            text.insert("end", f"Valid: {'Yes' if prog.get('is_valid') else 'No'}\n")
            text.insert("end", f"Validation Notes: {prog.get('validation_notes') or '-'}\n")
            text.insert("end", f"Status: {prog.get('status') or '-'}\n")
            text.insert("end", f"\nCreated: {prog.get('created_at') or '-'}\n")
            text.insert("end", f"Updated: {prog.get('updated_at') or '-'}\n")

            # Show components
            comps = self.svc.list_components(programme_id=int(pid))
            if comps:
                text.insert("end", f"\n--- Components ({len(comps)}) ---\n")
                for c in comps:
                    text.insert("end",
                                f"  [{c['id']}] {c['component_type']}: {c['component_name']} "
                                f"({c.get('planned_hours', 0)}h planned, "
                                f"{c.get('delivered_hours', 0)}h delivered, "
                                f"{c.get('status', '-')})\n")

            text.configure(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _update_programme(self):
        pid = self._get_selected_prog_id()
        if pid is None:
            return
        try:
            prog = self.svc.get_programme(int(pid))
            if not prog:
                messagebox.showwarning("Warning", "Programme not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Update Programme #{pid}")
        dlg.geometry("420x520")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, widget_type in [
            ("Academic Year:", "academic_year", "entry"),
            ("Programme Type:", "programme_type", "combo"),
            ("Substantive Qualification:", "substantive_qualification", "entry"),
            ("Maths Requirement:", "maths_requirement", "reqcombo"),
            ("English Requirement:", "english_requirement", "reqcombo"),
            ("Maths Enrollment ID:", "maths_enrollment_id", "entry"),
            ("English Enrollment ID:", "english_enrollment_id", "entry"),
            ("Work Exp Completed (0/1):", "work_experience_completed", "entry"),
            ("Work Exp Hours:", "work_experience_hours", "entry"),
            ("Enrichment Hours:", "enrichment_hours", "entry"),
            ("Tutorial Hours:", "tutorial_hours", "entry"),
            ("Total Planned Hours:", "total_planned_hours", "entry"),
            ("Status:", "status", "statuscombo"),
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
                    messagebox.showwarning("Warning", "No changes to save.")
                    return
                self.svc.update_programme(int(pid), **kwargs)
                messagebox.showinfo("Success", "Programme updated.")
                dlg.destroy()
                self._load_programmes()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        tk.Button(dlg, text="Save", command=_save, width=12).grid(
            row=row, column=0, columnspan=2, pady=10)

    def _validate_programme(self):
        pid = self._get_selected_prog_id()
        if pid is None:
            return
        try:
            result = self.svc.validate_programme(int(pid))
            valid = "VALID" if result.get("is_valid") else "INVALID"
            notes = result.get("validation_notes") or "-"
            messagebox.showinfo("Validation Result",
                                f"Programme #{pid}: {valid}\n\n{notes}")
            self._load_programmes()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_programme(self):
        pid = self._get_selected_prog_id()
        if pid is None:
            return
        if not messagebox.askyesno("Confirm", f"Delete programme #{pid} and all its components?"):
            return
        try:
            self.svc.delete_programme(int(pid))
            messagebox.showinfo("Success", "Programme deleted.")
            self._load_programmes()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ================================================================
    # Component Actions
    # ================================================================

    def _get_selected_comp_id(self):
        sel = self._comp_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "No component selected.")
            return None
        return self._comp_tree.item(sel[0], "values")[0]

    def _new_component(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Component")
        dlg.geometry("400x280")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, default, widget_type in [
            ("Programme ID:", "programme_id", "", "entry"),
            ("Component Type:", "component_type", "qualification", "typecombo"),
            ("Component Name:", "component_name", "", "entry"),
            ("Planned Hours:", "planned_hours", "0", "entry"),
            ("Delivered Hours:", "delivered_hours", "0", "entry"),
            ("Status:", "status", "active", "statuscombo"),
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
                    messagebox.showwarning("Warning", "Type and Name are required.")
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
                messagebox.showinfo("Success", "Component created.")
                dlg.destroy()
                self._load_components()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        tk.Button(dlg, text="Save", command=_save, width=12).grid(
            row=row, column=0, columnspan=2, pady=10)

    def _update_component(self):
        cid = self._get_selected_comp_id()
        if cid is None:
            return
        try:
            comp = self.svc.get_component(int(cid))
            if not comp:
                messagebox.showwarning("Warning", "Component not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Update Component #{cid}")
        dlg.geometry("400x250")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, widget_type in [
            ("Component Type:", "component_type", "typecombo"),
            ("Component Name:", "component_name", "entry"),
            ("Planned Hours:", "planned_hours", "entry"),
            ("Delivered Hours:", "delivered_hours", "entry"),
            ("Status:", "status", "statuscombo"),
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
                    messagebox.showwarning("Warning", "No changes to save.")
                    return
                self.svc.update_component(int(cid), **kwargs)
                messagebox.showinfo("Success", "Component updated.")
                dlg.destroy()
                self._load_components()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        tk.Button(dlg, text="Save", command=_save, width=12).grid(
            row=row, column=0, columnspan=2, pady=10)

    def _delete_component(self):
        cid = self._get_selected_comp_id()
        if cid is None:
            return
        if not messagebox.askyesno("Confirm", f"Delete component #{cid}?"):
            return
        try:
            self.svc.delete_component(int(cid))
            messagebox.showinfo("Success", "Component deleted.")
            self._load_components()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ================================================================
    # Reports
    # ================================================================

    def _report_cof(self):
        self._report_text.delete("1.0", "end")
        try:
            rows = self.svc.condition_of_funding_check()
            if not rows:
                self._report_text.insert("end", "All active programmes meet maths/english requirements.\n")
                return
            self._report_text.insert("end",
                f"Condition of Funding Check - {len(rows)} programme(s) with unmet requirements\n")
            self._report_text.insert("end", "=" * 80 + "\n\n")
            self._report_text.insert("end",
                f"{'ID':<6}{'Student':<25}{'Type':<12}{'Maths':<12}{'English':<12}{'Year'}\n")
            self._report_text.insert("end", "-" * 80 + "\n")
            for r in rows:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or "-"
                self._report_text.insert("end",
                    f"{r['id']:<6}{name:<25}{r.get('programme_type', '-'):<12}"
                    f"{r.get('maths_requirement', '-'):<12}"
                    f"{r.get('english_requirement', '-'):<12}"
                    f"{r.get('academic_year') or '-'}\n")
        except Exception as e:
            self._report_text.insert("end", f"Error: {e}\n")

    def _report_hours(self):
        self._report_text.delete("1.0", "end")
        try:
            rows = self.svc.funding_hours_report()
            if not rows:
                self._report_text.insert("end", "No programmes found.\n")
                return
            self._report_text.insert("end",
                f"Funding Hours Report - {len(rows)} programme(s)\n")
            self._report_text.insert("end", "=" * 90 + "\n\n")
            self._report_text.insert("end",
                f"{'ID':<6}{'Student':<25}{'Type':<12}{'Year':<10}"
                f"{'Planned':<10}{'Delivered':<10}{'Valid':<8}{'Status'}\n")
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
                    f"{'Yes' if r.get('is_valid') else 'No':<8}"
                    f"{r.get('status') or '-'}\n")
            self._report_text.insert("end", "-" * 90 + "\n")
            self._report_text.insert("end",
                f"{'TOTALS':<53}{total_planned:<10}{total_delivered}\n")
        except Exception as e:
            self._report_text.insert("end", f"Error: {e}\n")


# Backward-compatible alias for existing imports
StudyProgrammeFrame = StudyProgrammesFrame
