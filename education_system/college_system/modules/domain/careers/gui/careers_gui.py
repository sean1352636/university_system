"""Careers GUI for managing careers activities, UCAS, and work experience."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.careers.services.careers_service import CareersService
from education_system.college_system.core.i18n import t


class CareersFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = CareersService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("careers.title"), font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._act_tab = tk.Frame(self._nb)
        self._nb.add(self._act_tab, text=t("careers.activities_tab"))
        self._build_activities_tab()

        self._ucas_tab = tk.Frame(self._nb)
        self._nb.add(self._ucas_tab, text=t("careers.ucas_tab"))
        self._build_ucas_tab()

        self._we_tab = tk.Frame(self._nb)
        self._nb.add(self._we_tab, text=t("careers.work_experience_tab"))
        self._build_we_tab()

    def _build_activities_tab(self):
        toolbar = tk.Frame(self._act_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_activities).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("careers.new_activity"), command=self._new_activity).pack(side="right", padx=5)
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side="left", padx=5)

        cols = ("id", "student", "type", "title", "date", "gatsby")
        self._act_tree = ttk.Treeview(self._act_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 100, 200, 100, 60)):
            self._act_tree.heading(c, text=c.title())
            self._act_tree.column(c, width=w)
        self._act_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_ucas_tab(self):
        toolbar = tk.Frame(self._ucas_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_ucas).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("careers.new_ucas_record"), command=self._new_ucas).pack(side="right", padx=5)

        cols = ("id", "student", "ucas_id", "ps_status", "ref_status", "app_status")
        self._ucas_tree = ttk.Treeview(self._ucas_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 100, 120, 120, 100)):
            self._ucas_tree.heading(c, text=c.replace("_", " ").title())
            self._ucas_tree.column(c, width=w)
        self._ucas_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_we_tab(self):
        toolbar = tk.Frame(self._we_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_we).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("careers.new_placement"), command=self._new_we).pack(side="right", padx=5)

        cols = ("id", "student", "employer", "role", "start", "end", "status")
        self._we_tree = ttk.Treeview(self._we_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 150, 100, 100, 100, 80)):
            self._we_tree.heading(c, text=c.title())
            self._we_tree.column(c, width=w)
        self._we_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_activities(self):
        for item in self._act_tree.get_children():
            self._act_tree.delete(item)
        try:
            activities = self._svc.list_activities()
            for a in activities:
                name = f"{a.get('first_name', '')} {a.get('last_name', '')}".strip() or str(a.get("student_id", ""))
                self._act_tree.insert("", "end", values=(
                    a["id"], name, a.get("activity_type", ""), a.get("title", ""),
                    a.get("activity_date", ""), a.get("gatsby_benchmark", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_ucas(self):
        for item in self._ucas_tree.get_children():
            self._ucas_tree.delete(item)
        try:
            records = self._svc.list_ucas_records()
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                self._ucas_tree.insert("", "end", values=(
                    r["id"], name, r.get("ucas_id", ""),
                    r.get("personal_statement_status", ""),
                    r.get("reference_status", ""), r.get("application_status", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_we(self):
        for item in self._we_tree.get_children():
            self._we_tree.delete(item)
        try:
            records = self._svc.list_work_experience()
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                self._we_tree.insert("", "end", values=(
                    r["id"], name, r.get("employer", ""), r.get("role", ""),
                    r.get("start_date", ""), r.get("end_date", ""), r.get("status", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _new_activity(self):
        win = tk.Toplevel(self)
        win.title(t("careers.new_activity"))
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [("Student ID*:", "student_id"), ("Title*:", "title"),
                           ("Type:", "activity_type"), ("Date:", "activity_date"),
                           ("Gatsby Benchmark:", "gatsby_benchmark"), ("Provider:", "provider")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        def save():
            try:
                gb = fields["gatsby_benchmark"].get().strip()
                self._svc.create_activity(
                    student_id=int(fields["student_id"].get().strip()),
                    activity_type=fields["activity_type"].get().strip() or "careers_talk",
                    title=fields["title"].get().strip(),
                    activity_date=fields["activity_date"].get().strip() or None,
                    gatsby_benchmark=int(gb) if gb else None,
                    provider=fields["provider"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("careers.activity_created"))
                win.destroy()
                self._load_activities()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _new_ucas(self):
        win = tk.Toplevel(self)
        win.title(t("careers.new_ucas_record"))
        win.geometry("400x250")
        fields = {}
        row = 0
        for label, key in [("Student ID*:", "student_id"), ("UCAS ID:", "ucas_id"),
                           ("Predicted Grades:", "predicted_grades"), ("Choices:", "choices")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        def save():
            try:
                self._svc.create_ucas_record(
                    student_id=int(fields["student_id"].get().strip()),
                    ucas_id=fields["ucas_id"].get().strip() or None,
                    predicted_grades=fields["predicted_grades"].get().strip() or None,
                    choices=fields["choices"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("careers.ucas_record_created"))
                win.destroy()
                self._load_ucas()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _new_we(self):
        win = tk.Toplevel(self)
        win.title(t("careers.new_placement"))
        win.geometry("400x350")
        fields = {}
        row = 0
        for label, key in [("Student ID*:", "student_id"), ("Employer*:", "employer"),
                           ("Role:", "role"), ("Start Date:", "start_date"),
                           ("End Date:", "end_date"), ("Supervisor:", "supervisor"),
                           ("Contact:", "contact_details")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        ra_var = tk.BooleanVar()
        ttk.Checkbutton(win, text="Risk Assessment Completed", variable=ra_var).grid(
            row=row, column=1, sticky="w", padx=10)
        row += 1

        def save():
            try:
                self._svc.create_work_experience(
                    student_id=int(fields["student_id"].get().strip()),
                    employer=fields["employer"].get().strip(),
                    role=fields["role"].get().strip() or None,
                    start_date=fields["start_date"].get().strip() or None,
                    end_date=fields["end_date"].get().strip() or None,
                    supervisor=fields["supervisor"].get().strip() or None,
                    contact_details=fields["contact_details"].get().strip() or None,
                    risk_assessment_completed=1 if ra_var.get() else 0)
                messagebox.showinfo(t("common.success"), t("careers.work_experience_created"))
                win.destroy()
                self._load_we()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._act_tree, "careers_activities.csv")

    def refresh(self):
        self._load_activities()
        self._load_ucas()
        self._load_we()
