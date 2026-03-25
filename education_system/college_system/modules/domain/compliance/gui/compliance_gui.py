"""Compliance GUI for managing funding, resits, and destinations."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.compliance.services.compliance_service import ComplianceService
from education_system.college_system.core.i18n import t


class ComplianceFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ComplianceService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("compliance.management"), font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Funding tab
        self._fund_tab = tk.Frame(self._nb)
        self._nb.add(self._fund_tab, text=t("compliance.tab_funding", default="Funding Records"))
        self._build_funding_tab()

        # Resits tab
        self._resit_tab = tk.Frame(self._nb)
        self._nb.add(self._resit_tab, text=t("compliance.tab_resits", default="Resit Tracking"))
        self._build_resit_tab()

        # Destinations tab
        self._dest_tab = tk.Frame(self._nb)
        self._nb.add(self._dest_tab, text=t("compliance.tab_destinations", default="Destinations"))
        self._build_dest_tab()

    def _build_funding_tab(self):
        toolbar = tk.Frame(self._fund_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_funding).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("compliance.new_record", default="New Record"), command=self._new_funding).pack(side="right", padx=5)
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side="left", padx=5)

        cols = ("id", "student", "body", "type", "ilr_ref", "status", "hours")
        self._fund_tree = ttk.Treeview(self._fund_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 100, 100, 100, 80, 60)):
            self._fund_tree.heading(c, text=c.replace("_", " ").title())
            self._fund_tree.column(c, width=w)
        self._fund_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_resit_tab(self):
        toolbar = tk.Frame(self._resit_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_resits).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("compliance.new_resit", default="New Resit"), command=self._new_resit).pack(side="right", padx=5)

        cols = ("id", "student", "subject", "gcse_grade", "target", "status")
        self._resit_tree = ttk.Treeview(self._resit_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 100, 70, 70, 80)):
            self._resit_tree.heading(c, text=c.title())
            self._resit_tree.column(c, width=w)
        self._resit_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_dest_tab(self):
        toolbar = tk.Frame(self._dest_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_destinations).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("compliance.new_destination", default="New Destination"), command=self._new_destination).pack(side="right", padx=5)

        cols = ("id", "student", "type", "institution_name", "course", "contact_made")
        self._dest_tree = ttk.Treeview(self._dest_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 100, 150, 150, 80)):
            self._dest_tree.heading(c, text=c.title())
            self._dest_tree.column(c, width=w)
        self._dest_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_funding(self):
        for item in self._fund_tree.get_children():
            self._fund_tree.delete(item)
        try:
            records = self._svc.list_funding_records()
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                self._fund_tree.insert("", "end", values=(
                    r["id"], name, r.get("learning_aim", ""), r.get("funding_model", ""),
                    r.get("aim_type", ""), r.get("completion_status", ""),
                    r.get("planned_hours", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_resits(self):
        for item in self._resit_tree.get_children():
            self._resit_tree.delete(item)
        try:
            resits = self._svc.list_resits()
            for r in resits:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                self._resit_tree.insert("", "end", values=(
                    r["id"], name, r.get("subject", ""), r.get("gcse_grade_on_entry", ""),
                    r.get("target_grade", ""), r.get("status", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_destinations(self):
        for item in self._dest_tree.get_children():
            self._dest_tree.delete(item)
        try:
            dests = self._svc.list_destinations()
            for d in dests:
                name = f"{d.get('first_name', '')} {d.get('last_name', '')}".strip() or str(d.get("student_id", ""))
                self._dest_tree.insert("", "end", values=(
                    d["id"], name, d.get("destination_type", ""),
                    d.get("institution_name", ""), d.get("course_title", ""),
                    "Yes" if d.get("contact_made") else "No"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _new_funding(self):
        win = tk.Toplevel(self)
        win.title(t("compliance.new_record", default="New Funding Record"))
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [("Student ID*:", "student_id"), ("Learning Aim*:", "learning_aim"),
                           ("Funding Model*:", "funding_model"), ("Aim Type:", "aim_type"),
                           ("Start Date:", "start_date"), ("Planned Hours:", "planned_hours")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        def save():
            try:
                ph = fields["planned_hours"].get().strip()
                self._svc.create_funding_record(
                    student_id=int(fields["student_id"].get().strip()),
                    learning_aim=fields["learning_aim"].get().strip(),
                    funding_model=fields["funding_model"].get().strip(),
                    aim_type=fields["aim_type"].get().strip() or None,
                    start_date=fields["start_date"].get().strip() or None,
                    planned_hours=int(ph) if ph else None)
                messagebox.showinfo(t("common.success"), t("compliance.funding_created", default="Funding record created"))
                win.destroy()
                self._load_funding()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _new_resit(self):
        win = tk.Toplevel(self)
        win.title(t("compliance.new_resit", default="New Resit"))
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [("Student ID*:", "student_id"), ("Subject*:", "subject"),
                           ("GCSE Grade on Entry:", "gcse_grade_on_entry"),
                           ("Target Grade:", "target_grade")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        cof_var = tk.BooleanVar()
        ttk.Checkbutton(win, text="Condition of Funding", variable=cof_var).grid(
            row=row, column=1, sticky="w", padx=10)
        row += 1

        def save():
            try:
                self._svc.create_resit(
                    student_id=int(fields["student_id"].get().strip()),
                    subject=fields["subject"].get().strip(),
                    gcse_grade_on_entry=fields["gcse_grade_on_entry"].get().strip() or None,
                    target_grade=fields["target_grade"].get().strip() or None,
                    resit_required=1 if cof_var.get() else 0)
                messagebox.showinfo(t("common.success"), t("compliance.resit_created", default="Resit record created"))
                win.destroy()
                self._load_resits()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _new_destination(self):
        win = tk.Toplevel(self)
        win.title(t("compliance.new_destination", default="New Destination"))
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [("Student ID*:", "student_id"), ("Institution Name:", "institution_name"),
                           ("Course Title:", "course_title")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        tk.Label(win, text="Type:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        type_var = tk.StringVar(value="university")
        ttk.Combobox(win, textvariable=type_var,
                      values=["university", "apprenticeship", "employment", "gap_year", "other"],
                      state="readonly", width=22).grid(row=row, column=1, padx=10, pady=5)
        row += 1
        conf_var = tk.BooleanVar()
        ttk.Checkbutton(win, text="Confirmed", variable=conf_var).grid(
            row=row, column=1, sticky="w", padx=10)
        row += 1

        def save():
            try:
                self._svc.create_destination(
                    student_id=int(fields["student_id"].get().strip()),
                    destination_type=type_var.get(),
                    institution_name=fields["institution_name"].get().strip() or None,
                    course_title=fields["course_title"].get().strip() or None,
                    contact_made=1 if conf_var.get() else 0)
                messagebox.showinfo(t("common.success"), t("compliance.destination_recorded", default="Destination recorded"))
                win.destroy()
                self._load_destinations()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._fund_tree, "compliance_funding.csv")

    def refresh(self):
        self._load_funding()
        self._load_resits()
        self._load_destinations()
