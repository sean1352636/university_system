"""Reports GUI for managing progress reports and report entries."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.reports.services.reports_service import ReportsService


class ReportsFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ReportsService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Progress Reports", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Reports tab
        self._reports_tab = tk.Frame(self._nb)
        self._nb.add(self._reports_tab, text="Reports")
        self._build_reports_tab()

        # Entries tab
        self._entries_tab = tk.Frame(self._nb)
        self._nb.add(self._entries_tab, text="Report Entries")
        self._build_entries_tab()

    def _build_reports_tab(self):
        toolbar = tk.Frame(self._reports_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text="Refresh", command=self._load_reports).pack(side="left", padx=5)
        ttk.Button(toolbar, text="New Report", command=self._new_report).pack(side="right", padx=5)

        cols = ("id", "title", "type", "academic_year", "term", "status", "due_date")
        self._rep_tree = ttk.Treeview(self._reports_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 200, 80, 100, 60, 80, 100)):
            self._rep_tree.heading(c, text=c.replace("_", " ").title())
            self._rep_tree.column(c, width=w)
        self._rep_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_entries_tab(self):
        toolbar = tk.Frame(self._entries_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        tk.Label(toolbar, text="Report ID:").pack(side="left", padx=5)
        self._ent_rid = tk.Entry(toolbar, width=10)
        self._ent_rid.pack(side="left", padx=5)
        ttk.Button(toolbar, text="Load Entries", command=self._load_entries).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Add Entry", command=self._new_entry).pack(side="right", padx=5)

        cols = ("id", "student", "course", "current", "target", "effort", "attendance")
        self._ent_tree = ttk.Treeview(self._entries_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 120, 70, 70, 60, 80)):
            self._ent_tree.heading(c, text=c.title())
            self._ent_tree.column(c, width=w)
        self._ent_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_reports(self):
        for item in self._rep_tree.get_children():
            self._rep_tree.delete(item)
        try:
            reports = self._svc.list_reports()
            for r in reports:
                self._rep_tree.insert("", "end", values=(
                    r["id"], r.get("title", ""), r.get("report_type", ""),
                    r.get("academic_year", ""), r.get("term", ""),
                    r.get("status", ""), r.get("due_date", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_entries(self):
        for item in self._ent_tree.get_children():
            self._ent_tree.delete(item)
        try:
            rid = self._ent_rid.get().strip()
            if not rid:
                return
            entries = self._svc.list_entries(int(rid))
            for e in entries:
                name = f"{e.get('first_name', '')} {e.get('last_name', '')}".strip() or str(e.get("student_id", ""))
                self._ent_tree.insert("", "end", values=(
                    e["id"], name, e.get("course_name", ""),
                    e.get("current_grade", ""), e.get("target_grade", ""),
                    e.get("effort_grade", ""), e.get("attendance_pct", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _new_report(self):
        win = tk.Toplevel(self)
        win.title("New Progress Report")
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [("Title*:", "title"), ("Academic Year:", "academic_year"),
                           ("Term:", "term"), ("Due Date:", "due_date")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        tk.Label(win, text="Type:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        type_var = tk.StringVar(value="interim")
        ttk.Combobox(win, textvariable=type_var,
                      values=["interim", "full", "final"],
                      state="readonly", width=22).grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            try:
                user_id = self._auth.current_user["user_id"] if self._auth and self._auth.current_user else None
                self._svc.create_report(
                    title=fields["title"].get().strip(),
                    report_type=type_var.get(),
                    academic_year=fields["academic_year"].get().strip() or None,
                    term=fields["term"].get().strip() or None,
                    due_date=fields["due_date"].get().strip() or None,
                    created_by=user_id)
                messagebox.showinfo("Success", "Report created")
                win.destroy()
                self._load_reports()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _new_entry(self):
        win = tk.Toplevel(self)
        win.title("Add Report Entry")
        win.geometry("400x400")
        fields = {}
        row = 0
        for label, key in [("Report ID*:", "report_id"), ("Student ID*:", "student_id"),
                           ("Course ID*:", "course_id"), ("Current Grade:", "current_grade"),
                           ("Target Grade:", "target_grade"), ("Effort Grade:", "effort_grade"),
                           ("Attendance %:", "attendance_pct")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        tk.Label(win, text="Comment:").grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        comment = tk.Text(win, width=30, height=3)
        comment.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            try:
                user_id = self._auth.current_user["user_id"] if self._auth and self._auth.current_user else 1
                att = fields["attendance_pct"].get().strip()
                self._svc.add_entry(
                    report_id=int(fields["report_id"].get().strip()),
                    student_id=int(fields["student_id"].get().strip()),
                    course_id=int(fields["course_id"].get().strip()),
                    teacher_id=user_id,
                    current_grade=fields["current_grade"].get().strip() or None,
                    target_grade=fields["target_grade"].get().strip() or None,
                    effort_grade=fields["effort_grade"].get().strip() or None,
                    attendance_pct=float(att) if att else None,
                    comment=comment.get("1.0", "end").strip() or None)
                messagebox.showinfo("Success", "Entry added")
                win.destroy()
                self._load_entries()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def refresh(self):
        self._load_reports()
