"""Self-Assessment & Ofsted GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.self_assessment.services.self_assessment_service import SelfAssessmentService


class SelfAssessmentFrame(tk.Frame):
    """Self-Assessment & Ofsted management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = SelfAssessmentService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Self-Assessment & Ofsted",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_sections_tab()
        self._build_actions_tab()
        self._build_checklist_tab()
        self._build_stats_tab()

    # ---- SEF Sections Tab ----

    def _build_sections_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="SEF Sections")

        # Filters
        filt_frame = tk.Frame(tab, bg="#ecf0f1")
        filt_frame.pack(fill="x", pady=(0, 5))

        tk.Label(filt_frame, text="Year:", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._sec_year_var = tk.StringVar()
        self._sec_year_entry = tk.Entry(filt_frame, textvariable=self._sec_year_var, width=12)
        self._sec_year_entry.pack(side="left", padx=(0, 10))

        tk.Label(filt_frame, text="Status:", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._sec_status_var = tk.StringVar()
        sec_status_cb = ttk.Combobox(filt_frame, textvariable=self._sec_status_var, width=10,
                                     values=["", "draft", "final"], state="readonly")
        sec_status_cb.pack(side="left", padx=(0, 10))

        ttk.Button(filt_frame, text="Filter", command=self._load_sections).pack(side="left")

        # Toolbar
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text="New", command=self._new_section).pack(side="left", padx=2)
        ttk.Button(toolbar, text="View", command=self._view_section).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Edit", command=self._edit_section).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Delete", command=self._delete_section).pack(side="left", padx=2)

        # Treeview
        cols = ("year", "section", "number", "grade", "status")
        self._sec_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("year", "Year", 80), ("section", "Section", 200),
                         ("number", "Number", 60), ("grade", "Grade", 80), ("status", "Status", 80)]:
            self._sec_tree.heading(c, text=h)
            self._sec_tree.column(c, width=w, anchor="center")
        self._sec_tree.pack(fill="both", expand=True)
        self._sec_ids: list[int] = []

    def _load_sections(self):
        self._sec_tree.delete(*self._sec_tree.get_children())
        self._sec_ids.clear()
        try:
            year = self._sec_year_var.get().strip() or None
            status = self._sec_status_var.get().strip() or None
            for r in self._svc.list_sections(academic_year=year, status=status):
                self._sec_tree.insert("", "end", values=(
                    r.get("academic_year") or "-",
                    r["section_name"],
                    r.get("section_number") or "-",
                    r.get("self_grade") or "-",
                    r.get("status") or "draft",
                ))
                self._sec_ids.append(r["id"])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_section_id(self):
        sel = self._sec_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a section first.")
            return None
        idx = self._sec_tree.index(sel[0])
        return self._sec_ids[idx]

    def _new_section(self):
        dlg = tk.Toplevel(self)
        dlg.title("New SEF Section")
        dlg.geometry("500x520")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, widget_type in [
            ("Section Name*:", "section_name", "entry"),
            ("Section Number:", "section_number", "entry"),
            ("Academic Year:", "academic_year", "entry"),
            ("Self Grade:", "self_grade", "entry"),
            ("Status:", "status", "combo"),
            ("Strengths:", "strengths", "text"),
            ("Areas for Improvement:", "areas_for_improvement", "text"),
            ("Evidence:", "evidence", "text"),
        ]:
            tk.Label(dlg, text=label).grid(row=row, column=0, sticky="nw", padx=10, pady=4)
            if widget_type == "entry":
                var = tk.StringVar()
                tk.Entry(dlg, textvariable=var, width=40).grid(row=row, column=1, padx=10, pady=4, sticky="w")
                fields[key] = var
            elif widget_type == "combo":
                var = tk.StringVar(value="draft")
                ttk.Combobox(dlg, textvariable=var, values=["draft", "final"], width=37,
                             state="readonly").grid(row=row, column=1, padx=10, pady=4, sticky="w")
                fields[key] = var
            elif widget_type == "text":
                txt = tk.Text(dlg, width=38, height=3)
                txt.grid(row=row, column=1, padx=10, pady=4, sticky="w")
                fields[key] = txt
            row += 1

        def _save():
            name = fields["section_name"].get().strip()
            if not name:
                messagebox.showwarning("Warning", "Section name is required.", parent=dlg)
                return
            kwargs = {
                "section_name": name,
                "section_number": fields["section_number"].get().strip() or None,
                "academic_year": fields["academic_year"].get().strip() or None,
                "self_grade": fields["self_grade"].get().strip() or None,
                "status": fields["status"].get(),
                "strengths": fields["strengths"].get("1.0", "end-1c").strip() or None,
                "areas_for_improvement": fields["areas_for_improvement"].get("1.0", "end-1c").strip() or None,
                "evidence": fields["evidence"].get("1.0", "end-1c").strip() or None,
            }
            try:
                self._svc.create_section(**kwargs)
                messagebox.showinfo("Success", "SEF section created.", parent=dlg)
                dlg.destroy()
                self._load_sections()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=_save).grid(row=row, column=0, columnspan=2, pady=10)

    def _view_section(self):
        sec_id = self._selected_section_id()
        if not sec_id:
            return
        try:
            r = self._svc.get_section(sec_id)
            if not r:
                messagebox.showwarning("Warning", "Section not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"SEF Section: {r['section_name']}")
        dlg.geometry("550x480")
        dlg.transient(self)
        dlg.grab_set()

        info_items = [
            ("Section Name", r.get("section_name") or "-"),
            ("Section Number", r.get("section_number") or "-"),
            ("Academic Year", r.get("academic_year") or "-"),
            ("Self Grade", r.get("self_grade") or "-"),
            ("Status", r.get("status") or "-"),
            ("Strengths", r.get("strengths") or "-"),
            ("Areas for Improvement", r.get("areas_for_improvement") or "-"),
            ("Evidence", r.get("evidence") or "-"),
            ("Last Updated", r.get("updated_at") or r.get("created_at") or "-"),
        ]
        for i, (lbl, val) in enumerate(info_items):
            tk.Label(dlg, text=f"{lbl}:", font=("Helvetica", 10, "bold")).grid(
                row=i, column=0, sticky="nw", padx=10, pady=3)
            tk.Label(dlg, text=val, wraplength=380, justify="left").grid(
                row=i, column=1, sticky="nw", padx=10, pady=3)

        ttk.Button(dlg, text="Close", command=dlg.destroy).grid(
            row=len(info_items), column=0, columnspan=2, pady=10)

    def _edit_section(self):
        sec_id = self._selected_section_id()
        if not sec_id:
            return
        try:
            r = self._svc.get_section(sec_id)
            if not r:
                messagebox.showwarning("Warning", "Section not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title("Edit SEF Section")
        dlg.geometry("500x520")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, widget_type in [
            ("Section Name*:", "section_name", "entry"),
            ("Section Number:", "section_number", "entry"),
            ("Academic Year:", "academic_year", "entry"),
            ("Self Grade:", "self_grade", "entry"),
            ("Status:", "status", "combo"),
            ("Strengths:", "strengths", "text"),
            ("Areas for Improvement:", "areas_for_improvement", "text"),
            ("Evidence:", "evidence", "text"),
        ]:
            tk.Label(dlg, text=label).grid(row=row, column=0, sticky="nw", padx=10, pady=4)
            if widget_type == "entry":
                var = tk.StringVar(value=r.get(key) or "")
                tk.Entry(dlg, textvariable=var, width=40).grid(row=row, column=1, padx=10, pady=4, sticky="w")
                fields[key] = var
            elif widget_type == "combo":
                var = tk.StringVar(value=r.get(key) or "draft")
                ttk.Combobox(dlg, textvariable=var, values=["draft", "final"], width=37,
                             state="readonly").grid(row=row, column=1, padx=10, pady=4, sticky="w")
                fields[key] = var
            elif widget_type == "text":
                txt = tk.Text(dlg, width=38, height=3)
                txt.insert("1.0", r.get(key) or "")
                txt.grid(row=row, column=1, padx=10, pady=4, sticky="w")
                fields[key] = txt
            row += 1

        def _save():
            name = fields["section_name"].get().strip()
            if not name:
                messagebox.showwarning("Warning", "Section name is required.", parent=dlg)
                return
            kwargs = {
                "section_name": name,
                "section_number": fields["section_number"].get().strip() or None,
                "academic_year": fields["academic_year"].get().strip() or None,
                "self_grade": fields["self_grade"].get().strip() or None,
                "status": fields["status"].get(),
                "strengths": fields["strengths"].get("1.0", "end-1c").strip() or None,
                "areas_for_improvement": fields["areas_for_improvement"].get("1.0", "end-1c").strip() or None,
                "evidence": fields["evidence"].get("1.0", "end-1c").strip() or None,
            }
            try:
                self._svc.update_section(sec_id, **kwargs)
                messagebox.showinfo("Success", "SEF section updated.", parent=dlg)
                dlg.destroy()
                self._load_sections()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=_save).grid(row=row, column=0, columnspan=2, pady=10)

    def _delete_section(self):
        sec_id = self._selected_section_id()
        if not sec_id:
            return
        if not messagebox.askyesno("Confirm", "Delete this section and all its improvement actions?"):
            return
        try:
            self._svc.delete_section(sec_id)
            messagebox.showinfo("Success", "Section deleted.")
            self._load_sections()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Improvement Actions Tab ----

    def _build_actions_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Improvement Actions")

        # Filters
        filt_frame = tk.Frame(tab, bg="#ecf0f1")
        filt_frame.pack(fill="x", pady=(0, 5))

        tk.Label(filt_frame, text="Section ID:", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._act_sec_var = tk.StringVar()
        tk.Entry(filt_frame, textvariable=self._act_sec_var, width=8).pack(side="left", padx=(0, 10))

        tk.Label(filt_frame, text="Status:", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._act_status_var = tk.StringVar()
        ttk.Combobox(filt_frame, textvariable=self._act_status_var, width=12,
                     values=["", "not_started", "in_progress", "completed"],
                     state="readonly").pack(side="left", padx=(0, 10))

        ttk.Button(filt_frame, text="Filter", command=self._load_actions).pack(side="left")

        # Toolbar
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text="New", command=self._new_action).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Edit", command=self._edit_action).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Delete", command=self._delete_action).pack(side="left", padx=2)

        # Treeview
        cols = ("section", "action", "responsible", "target_date", "status")
        self._act_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("section", "Section", 140), ("action", "Action", 200),
                         ("responsible", "Responsible", 120), ("target_date", "Target Date", 100),
                         ("status", "Status", 90)]:
            self._act_tree.heading(c, text=h)
            self._act_tree.column(c, width=w, anchor="center")
        self._act_tree.pack(fill="both", expand=True)
        self._act_ids: list[int] = []

    def _load_actions(self):
        self._act_tree.delete(*self._act_tree.get_children())
        self._act_ids.clear()
        try:
            sec_id_str = self._act_sec_var.get().strip()
            sec_id = int(sec_id_str) if sec_id_str else None
            status = self._act_status_var.get().strip() or None
            for r in self._svc.list_actions(sef_section_id=sec_id, status=status):
                self._act_tree.insert("", "end", values=(
                    r.get("section_name") or f"Section {r['sef_section_id']}",
                    r["action_description"][:60],
                    r.get("responsible_person") or "-",
                    r.get("target_date") or "-",
                    r.get("status") or "not_started",
                ))
                self._act_ids.append(r["id"])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_action_id(self):
        sel = self._act_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select an action first.")
            return None
        idx = self._act_tree.index(sel[0])
        return self._act_ids[idx]

    def _new_action(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Improvement Action")
        dlg.geometry("500x480")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, widget_type in [
            ("SEF Section ID*:", "sef_section_id", "entry"),
            ("Action Description*:", "action_description", "text"),
            ("Responsible Person:", "responsible_person", "entry"),
            ("Start Date (YYYY-MM-DD):", "start_date", "entry"),
            ("Target Date (YYYY-MM-DD):", "target_date", "entry"),
            ("Success Criteria:", "success_criteria", "text"),
            ("Cost:", "cost", "entry"),
            ("Status:", "status", "combo"),
        ]:
            tk.Label(dlg, text=label).grid(row=row, column=0, sticky="nw", padx=10, pady=4)
            if widget_type == "entry":
                var = tk.StringVar()
                if key == "cost":
                    var.set("0")
                tk.Entry(dlg, textvariable=var, width=40).grid(row=row, column=1, padx=10, pady=4, sticky="w")
                fields[key] = var
            elif widget_type == "combo":
                var = tk.StringVar(value="not_started")
                ttk.Combobox(dlg, textvariable=var, values=["not_started", "in_progress", "completed"],
                             width=37, state="readonly").grid(row=row, column=1, padx=10, pady=4, sticky="w")
                fields[key] = var
            elif widget_type == "text":
                txt = tk.Text(dlg, width=38, height=3)
                txt.grid(row=row, column=1, padx=10, pady=4, sticky="w")
                fields[key] = txt
            row += 1

        def _save():
            sec_id_str = fields["sef_section_id"].get().strip()
            if not sec_id_str:
                messagebox.showwarning("Warning", "Section ID is required.", parent=dlg)
                return
            desc = fields["action_description"].get("1.0", "end-1c").strip()
            if not desc:
                messagebox.showwarning("Warning", "Action description is required.", parent=dlg)
                return
            try:
                cost_val = float(fields["cost"].get().strip() or "0")
            except ValueError:
                messagebox.showwarning("Warning", "Cost must be a number.", parent=dlg)
                return
            kwargs = {
                "sef_section_id": int(sec_id_str),
                "action_description": desc,
                "responsible_person": fields["responsible_person"].get().strip() or None,
                "start_date": fields["start_date"].get().strip() or None,
                "target_date": fields["target_date"].get().strip() or None,
                "success_criteria": fields["success_criteria"].get("1.0", "end-1c").strip() or None,
                "cost": cost_val,
                "status": fields["status"].get(),
            }
            try:
                self._svc.create_action(**kwargs)
                messagebox.showinfo("Success", "Action created.", parent=dlg)
                dlg.destroy()
                self._load_actions()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=_save).grid(row=row, column=0, columnspan=2, pady=10)

    def _edit_action(self):
        act_id = self._selected_action_id()
        if not act_id:
            return
        try:
            r = self._svc.get_action(act_id)
            if not r:
                messagebox.showwarning("Warning", "Action not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title("Edit Improvement Action")
        dlg.geometry("500x520")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, widget_type in [
            ("Action Description*:", "action_description", "text"),
            ("Responsible Person:", "responsible_person", "entry"),
            ("Start Date (YYYY-MM-DD):", "start_date", "entry"),
            ("Target Date (YYYY-MM-DD):", "target_date", "entry"),
            ("Success Criteria:", "success_criteria", "text"),
            ("Progress:", "progress", "text"),
            ("Impact:", "impact", "text"),
            ("Cost:", "cost", "entry"),
            ("Status:", "status", "combo"),
        ]:
            tk.Label(dlg, text=label).grid(row=row, column=0, sticky="nw", padx=10, pady=4)
            if widget_type == "entry":
                var = tk.StringVar(value=str(r.get(key) or ""))
                tk.Entry(dlg, textvariable=var, width=40).grid(row=row, column=1, padx=10, pady=4, sticky="w")
                fields[key] = var
            elif widget_type == "combo":
                var = tk.StringVar(value=r.get(key) or "not_started")
                ttk.Combobox(dlg, textvariable=var, values=["not_started", "in_progress", "completed"],
                             width=37, state="readonly").grid(row=row, column=1, padx=10, pady=4, sticky="w")
                fields[key] = var
            elif widget_type == "text":
                txt = tk.Text(dlg, width=38, height=3)
                txt.insert("1.0", r.get(key) or "")
                txt.grid(row=row, column=1, padx=10, pady=4, sticky="w")
                fields[key] = txt
            row += 1

        def _save():
            desc = fields["action_description"].get("1.0", "end-1c").strip()
            if not desc:
                messagebox.showwarning("Warning", "Action description is required.", parent=dlg)
                return
            try:
                cost_val = float(fields["cost"].get().strip() or "0")
            except ValueError:
                messagebox.showwarning("Warning", "Cost must be a number.", parent=dlg)
                return
            kwargs = {
                "action_description": desc,
                "responsible_person": fields["responsible_person"].get().strip() or None,
                "start_date": fields["start_date"].get().strip() or None,
                "target_date": fields["target_date"].get().strip() or None,
                "success_criteria": fields["success_criteria"].get("1.0", "end-1c").strip() or None,
                "progress": fields["progress"].get("1.0", "end-1c").strip() or None,
                "impact": fields["impact"].get("1.0", "end-1c").strip() or None,
                "cost": cost_val,
                "status": fields["status"].get(),
            }
            try:
                self._svc.update_action(act_id, **kwargs)
                messagebox.showinfo("Success", "Action updated.", parent=dlg)
                dlg.destroy()
                self._load_actions()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=_save).grid(row=row, column=0, columnspan=2, pady=10)

    def _delete_action(self):
        act_id = self._selected_action_id()
        if not act_id:
            return
        if not messagebox.askyesno("Confirm", "Delete this improvement action?"):
            return
        try:
            self._svc.delete_action(act_id)
            messagebox.showinfo("Success", "Action deleted.")
            self._load_actions()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Ofsted Prep Checklist Tab ----

    def _build_checklist_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Ofsted Prep Checklist")

        # Filters
        filt_frame = tk.Frame(tab, bg="#ecf0f1")
        filt_frame.pack(fill="x", pady=(0, 5))

        tk.Label(filt_frame, text="Category:", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._chk_cat_var = tk.StringVar()
        tk.Entry(filt_frame, textvariable=self._chk_cat_var, width=16).pack(side="left", padx=(0, 10))

        ttk.Button(filt_frame, text="Filter", command=self._load_checklist).pack(side="left")

        # Toolbar
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text="New", command=self._new_checklist_item).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Edit", command=self._edit_checklist_item).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Delete", command=self._delete_checklist_item).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Toggle Ready", command=self._toggle_ready).pack(side="left", padx=2)

        # Treeview
        cols = ("category", "item", "responsible", "ready", "last_checked")
        self._chk_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("category", "Category", 120), ("item", "Item", 200),
                         ("responsible", "Responsible", 120), ("ready", "Ready", 60),
                         ("last_checked", "Last Checked", 120)]:
            self._chk_tree.heading(c, text=h)
            self._chk_tree.column(c, width=w, anchor="center")
        self._chk_tree.pack(fill="both", expand=True)
        self._chk_ids: list[int] = []

    def _load_checklist(self):
        self._chk_tree.delete(*self._chk_tree.get_children())
        self._chk_ids.clear()
        try:
            category = self._chk_cat_var.get().strip() or None
            for r in self._svc.list_checklist(category=category):
                self._chk_tree.insert("", "end", values=(
                    r["category"],
                    r["item"][:60],
                    r.get("responsible_person") or "-",
                    "Yes" if r.get("is_ready") else "No",
                    r.get("last_checked") or "-",
                ))
                self._chk_ids.append(r["id"])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_checklist_id(self):
        sel = self._chk_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a checklist item first.")
            return None
        idx = self._chk_tree.index(sel[0])
        return self._chk_ids[idx]

    def _new_checklist_item(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Checklist Item")
        dlg.geometry("460x320")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key in [("Category*:", "category"), ("Item*:", "item"),
                            ("Responsible Person:", "responsible_person"),
                            ("Document Location:", "document_location"),
                            ("Notes:", "notes")]:
            tk.Label(dlg, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=4)
            var = tk.StringVar()
            tk.Entry(dlg, textvariable=var, width=40).grid(row=row, column=1, padx=10, pady=4, sticky="w")
            fields[key] = var
            row += 1

        def _save():
            cat = fields["category"].get().strip()
            item = fields["item"].get().strip()
            if not cat or not item:
                messagebox.showwarning("Warning", "Category and item are required.", parent=dlg)
                return
            try:
                self._svc.create_checklist_item(
                    category=cat,
                    item=item,
                    responsible_person=fields["responsible_person"].get().strip() or None,
                    document_location=fields["document_location"].get().strip() or None,
                    notes=fields["notes"].get().strip() or None,
                )
                messagebox.showinfo("Success", "Checklist item created.", parent=dlg)
                dlg.destroy()
                self._load_checklist()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=_save).grid(row=row, column=0, columnspan=2, pady=10)

    def _edit_checklist_item(self):
        item_id = self._selected_checklist_id()
        if not item_id:
            return
        try:
            r = self._svc.get_checklist_item(item_id)
            if not r:
                messagebox.showwarning("Warning", "Checklist item not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title("Edit Checklist Item")
        dlg.geometry("460x320")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key in [("Category*:", "category"), ("Item*:", "item"),
                            ("Responsible Person:", "responsible_person"),
                            ("Document Location:", "document_location"),
                            ("Notes:", "notes")]:
            tk.Label(dlg, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=4)
            var = tk.StringVar(value=r.get(key) or "")
            tk.Entry(dlg, textvariable=var, width=40).grid(row=row, column=1, padx=10, pady=4, sticky="w")
            fields[key] = var
            row += 1

        def _save():
            cat = fields["category"].get().strip()
            item = fields["item"].get().strip()
            if not cat or not item:
                messagebox.showwarning("Warning", "Category and item are required.", parent=dlg)
                return
            try:
                self._svc.update_checklist_item(
                    item_id,
                    category=cat,
                    item=item,
                    responsible_person=fields["responsible_person"].get().strip() or None,
                    document_location=fields["document_location"].get().strip() or None,
                    notes=fields["notes"].get().strip() or None,
                )
                messagebox.showinfo("Success", "Checklist item updated.", parent=dlg)
                dlg.destroy()
                self._load_checklist()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=_save).grid(row=row, column=0, columnspan=2, pady=10)

    def _delete_checklist_item(self):
        item_id = self._selected_checklist_id()
        if not item_id:
            return
        if not messagebox.askyesno("Confirm", "Delete this checklist item?"):
            return
        try:
            self._svc.delete_checklist_item(item_id)
            messagebox.showinfo("Success", "Checklist item deleted.")
            self._load_checklist()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _toggle_ready(self):
        item_id = self._selected_checklist_id()
        if not item_id:
            return
        try:
            result = self._svc.toggle_ready(item_id)
            status = "Ready" if result.get("is_ready") else "Not Ready"
            messagebox.showinfo("Success", f"Item marked as {status}.")
            self._load_checklist()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Statistics Tab ----

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Statistics")
        self._stats_frame = tk.Frame(tab, bg="#ecf0f1")
        self._stats_frame.pack(fill="both", expand=True)

        self._stats_labels: dict[str, tk.Label] = {}
        stat_items = [
            ("SEF Sections", "total_sections"),
            ("Draft Sections", "draft_count"),
            ("Final Sections", "final_count"),
            ("", ""),
            ("Total Actions", "total_actions"),
            ("Not Started", "not_started"),
            ("In Progress", "in_progress"),
            ("Completed", "completed"),
            ("", ""),
            ("Total Checklist Items", "total_checklist"),
            ("Ready", "ready_count"),
            ("Not Ready", "not_ready_count"),
        ]
        for i, (label, key) in enumerate(stat_items):
            if not label:
                tk.Label(self._stats_frame, text="", bg="#ecf0f1").grid(row=i, column=0, pady=2)
                continue
            tk.Label(self._stats_frame, text=f"{label}:", font=("Helvetica", 11, "bold"),
                     bg="#ecf0f1", anchor="w").grid(row=i, column=0, sticky="w", padx=20, pady=3)
            lbl = tk.Label(self._stats_frame, text="0", font=("Helvetica", 11),
                           bg="#ecf0f1", anchor="w")
            lbl.grid(row=i, column=1, sticky="w", padx=10, pady=3)
            self._stats_labels[key] = lbl

        ttk.Button(self._stats_frame, text="Refresh Stats", command=self._load_stats).grid(
            row=len(stat_items), column=0, columnspan=2, pady=15)

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
            for key, lbl in self._stats_labels.items():
                lbl.configure(text=str(stats.get(key, 0)))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Refresh All ----

    def refresh(self):
        self._load_sections()
        self._load_actions()
        self._load_checklist()
        self._load_stats()
