"""Compliance GUI for managing funding, resits, and destinations."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.compliance.services.compliance_service import ComplianceService


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
        tk.Label(header, text="Compliance & Funding", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Funding tab
        self._fund_tab = tk.Frame(self._nb)
        self._nb.add(self._fund_tab, text="Funding Records")
        self._build_funding_tab()

        # Resits tab
        self._resit_tab = tk.Frame(self._nb)
        self._nb.add(self._resit_tab, text="Resit Tracking")
        self._build_resit_tab()

        # Destinations tab
        self._dest_tab = tk.Frame(self._nb)
        self._nb.add(self._dest_tab, text="Destinations")
        self._build_dest_tab()

    def _build_funding_tab(self):
        toolbar = tk.Frame(self._fund_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text="Refresh", command=self._load_funding).pack(side="left", padx=5)
        ttk.Button(toolbar, text="New Record", command=self._new_funding).pack(side="right", padx=5)

        cols = ("id", "student", "body", "type", "ilr_ref", "status", "hours")
        self._fund_tree = ttk.Treeview(self._fund_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 100, 100, 100, 80, 60)):
            self._fund_tree.heading(c, text=c.replace("_", " ").title())
            self._fund_tree.column(c, width=w)
        self._fund_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_resit_tab(self):
        toolbar = tk.Frame(self._resit_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text="Refresh", command=self._load_resits).pack(side="left", padx=5)
        ttk.Button(toolbar, text="New Resit", command=self._new_resit).pack(side="right", padx=5)

        cols = ("id", "student", "subject", "original", "target", "resit_date", "status")
        self._resit_tree = ttk.Treeview(self._resit_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 100, 70, 70, 100, 80)):
            self._resit_tree.heading(c, text=c.title())
            self._resit_tree.column(c, width=w)
        self._resit_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_dest_tab(self):
        toolbar = tk.Frame(self._dest_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text="Refresh", command=self._load_destinations).pack(side="left", padx=5)
        ttk.Button(toolbar, text="New Destination", command=self._new_destination).pack(side="right", padx=5)

        cols = ("id", "student", "type", "institution", "course", "confirmed")
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
                    r["id"], name, r.get("funding_body", ""), r.get("funding_type", ""),
                    r.get("ilr_reference", ""), r.get("funding_status", ""),
                    r.get("planned_hours", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_resits(self):
        for item in self._resit_tree.get_children():
            self._resit_tree.delete(item)
        try:
            resits = self._svc.list_resits()
            for r in resits:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                self._resit_tree.insert("", "end", values=(
                    r["id"], name, r.get("subject", ""), r.get("original_grade", ""),
                    r.get("target_grade", ""), r.get("resit_date", ""), r.get("status", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_destinations(self):
        for item in self._dest_tree.get_children():
            self._dest_tree.delete(item)
        try:
            dests = self._svc.list_destinations()
            for d in dests:
                name = f"{d.get('first_name', '')} {d.get('last_name', '')}".strip() or str(d.get("student_id", ""))
                self._dest_tree.insert("", "end", values=(
                    d["id"], name, d.get("destination_type", ""),
                    d.get("institution", ""), d.get("course_title", ""),
                    "Yes" if d.get("confirmed") else "No"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _new_funding(self):
        win = tk.Toplevel(self)
        win.title("New Funding Record")
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [("Student ID*:", "student_id"), ("Funding Body*:", "funding_body"),
                           ("Funding Type*:", "funding_type"), ("ILR Reference:", "ilr_reference"),
                           ("Programme Type:", "programme_type"), ("Planned Hours:", "planned_hours")]:
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
                    funding_body=fields["funding_body"].get().strip(),
                    funding_type=fields["funding_type"].get().strip(),
                    ilr_reference=fields["ilr_reference"].get().strip() or None,
                    programme_type=fields["programme_type"].get().strip() or None,
                    planned_hours=int(ph) if ph else None)
                messagebox.showinfo("Success", "Funding record created")
                win.destroy()
                self._load_funding()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _new_resit(self):
        win = tk.Toplevel(self)
        win.title("New Resit")
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [("Student ID*:", "student_id"), ("Subject*:", "subject"),
                           ("Original Grade:", "original_grade"), ("Target Grade:", "target_grade"),
                           ("Resit Date:", "resit_date")]:
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
                    original_grade=fields["original_grade"].get().strip() or None,
                    target_grade=fields["target_grade"].get().strip() or None,
                    resit_date=fields["resit_date"].get().strip() or None,
                    is_condition_of_funding=1 if cof_var.get() else 0)
                messagebox.showinfo("Success", "Resit record created")
                win.destroy()
                self._load_resits()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _new_destination(self):
        win = tk.Toplevel(self)
        win.title("New Destination")
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [("Student ID*:", "student_id"), ("Institution:", "institution"),
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
                    institution=fields["institution"].get().strip() or None,
                    course_title=fields["course_title"].get().strip() or None,
                    confirmed=1 if conf_var.get() else 0)
                messagebox.showinfo("Success", "Destination recorded")
                win.destroy()
                self._load_destinations()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def refresh(self):
        self._load_funding()
        self._load_resits()
        self._load_destinations()
