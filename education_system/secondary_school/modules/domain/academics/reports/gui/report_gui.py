"""Reports and analytics GUI."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.secondary_school.modules.domain.academics.reports.services.report_service import ReportService

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class ReportFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._svc = ReportService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)

        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Reports & Analytics", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)

        for label, cmd in [
            ("Year Overview", self._show_year_overview),
            ("Attendance", self._show_attendance),
            ("Grades", self._show_grades),
            ("Behaviour", self._show_behaviour),
            ("Subject Performance", self._show_subject_perf),
        ]:
            ttk.Button(toolbar, text=label, command=cmd).pack(side="left", padx=4)

        tk.Label(toolbar, text="Year:", bg=MAIN_BG).pack(side="left", padx=(20, 4))
        self._year_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._year_var,
                     values=["All", "7", "8", "9", "10", "11"],
                     state="readonly", width=5).pack(side="left", padx=4)

        self._tree_frame = tk.Frame(self)
        self._tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self._tree = None
        self._status_var = tk.StringVar(value="Select a report")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        pass

    def _make_tree(self, columns, headings, widths):
        for w in self._tree_frame.winfo_children():
            w.destroy()
        tree = ttk.Treeview(self._tree_frame, columns=columns, show="headings", selectmode="browse")
        for col, heading, w in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(self._tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._tree = tree
        return tree

    def _get_year(self):
        y = self._year_var.get()
        return y if y != "All" else None

    def _show_year_overview(self):
        tree = self._make_tree(
            ("year", "total", "active", "sen", "pp"),
            ("Year", "Total", "Active", "SEN", "Pupil Premium"),
            (60, 60, 60, 60, 80),
        )
        try:
            data = self._svc.year_group_overview()
            for d in data:
                tree.insert("", "end", values=(
                    d["year_group"], d["total"], d["active"], d["sen"], d["pp"]))
            self._status_var.set(f"Year group overview — {len(data)} groups")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _show_attendance(self):
        tree = self._make_tree(
            ("student", "year", "total", "present", "absent", "late", "pct"),
            ("Student", "Year", "Total", "Present", "Absent", "Late", "Attendance %"),
            (150, 40, 50, 55, 50, 40, 80),
        )
        try:
            data = self._svc.attendance_summary(self._get_year())
            for d in data:
                tree.insert("", "end", values=(
                    f"{d['first_name']} {d['last_name']}", d["year_group"],
                    d["total"], d["present"], d["absent"], d["late"], f"{d['pct']}%"))
            self._status_var.set(f"Attendance report — {len(data)} students")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _show_grades(self):
        tree = self._make_tree(
            ("student", "year", "subject", "avg", "count"),
            ("Student", "Year", "Subject", "Avg Score", "Assessments"),
            (150, 40, 140, 70, 70),
        )
        try:
            data = self._svc.grade_summary(self._get_year())
            for d in data:
                tree.insert("", "end", values=(
                    f"{d['first_name']} {d['last_name']}", d["year_group"],
                    d["subject_title"], d["avg_score"] or "", d["assessments"]))
            self._status_var.set(f"Grade report — {len(data)} records")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _show_behaviour(self):
        tree = self._make_tree(
            ("student", "year", "positive", "negative", "total"),
            ("Student", "Year", "Positive Pts", "Negative Pts", "Incidents"),
            (150, 40, 80, 80, 60),
        )
        try:
            data = self._svc.behaviour_summary(self._get_year())
            for d in data:
                tree.insert("", "end", values=(
                    f"{d['first_name']} {d['last_name']}", d["year_group"],
                    d["positive_pts"], d["negative_pts"], d["total_incidents"]))
            self._status_var.set(f"Behaviour report — {len(data)} students")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _show_subject_perf(self):
        tree = self._make_tree(
            ("code", "subject", "students", "avg", "min", "max"),
            ("Code", "Subject", "Students", "Avg", "Min", "Max"),
            (70, 160, 60, 60, 50, 50),
        )
        try:
            data = self._svc.subject_performance()
            for d in data:
                tree.insert("", "end", values=(
                    d["subject_code"], d["title"], d["students"],
                    d["avg_score"] or "", d["min_score"] or "", d["max_score"] or ""))
            self._status_var.set(f"Subject performance — {len(data)} subjects")
        except Exception as e:
            messagebox.showerror("Error", str(e))
