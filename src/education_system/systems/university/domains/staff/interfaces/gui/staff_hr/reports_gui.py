"""
Reports & Analytics GUI

HR reporting hub wired to the same manager classes the reports CLI menu
uses (Employee / Leave / Time / Training / Performance managers). Each
report button drives a real manager query and renders the results.
"""

from __future__ import annotations

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.systems.university.domains.staff.interfaces.gui.staff_hr import _access
from education_system.systems.university.domains.staff.domain.staff_hr.services import (
    EmployeeManager,
    LeaveManager,
    TimeManager,
    TrainingManager,
    PerformanceManager,
)


class ReportsGUI:
    """GUI hub for HR reports and analytics."""

    def __init__(self, root, auth=None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror(_t('gui.staff.staff_hr.reports.dialogs.error', default="Error"), _t('gui.staff.staff_hr.reports.dialogs.login_required_to_access_reports', default="Login required to access Reports"))
            return

        # The Staff HR key is the username, never current_user['id'].
        self.user_id = _access.user_key(self) or self.current_user.get('username')

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    # ------------------------------------------------------------------
    def create_as_tab(self, notebook: ttk.Notebook):
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text=_t('gui.staff.staff_hr.reports.tabs.reports', default="Reports"))
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        self.window = tk.Toplevel(self.root)
        self.window.title(_t('gui.staff.staff_hr.reports.windows.reports_analytics', default="Reports & Analytics"))
        self.window.geometry("1100x700")
        self.window.minsize(900, 600)
        ttk.Button(self.window, text=_t('gui.staff.staff_hr.reports.buttons.close', default="Close"), command=self.window.destroy).pack(
            side=tk.BOTTOM, anchor=tk.E, padx=10, pady=5)
        self._build_interface(self.window)

    def _build_interface(self, parent):
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        header = ttk.Frame(parent)
        header.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header, text=_t('gui.staff.staff_hr.reports.labels.reports_analytics', default="Reports & Analytics"), style='Header.TLabel').pack(side=tk.LEFT)

        body = ttk.Frame(parent)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Left: report selector
        left = ttk.LabelFrame(body, text=_t('gui.staff.staff_hr.reports.labels.reports', default="Reports"), padding=10)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        self._reports = [
            ("Headcount", self._report_headcount),
            ("Department Breakdown", self._report_departments),
            ("Leave Usage Summary", self._report_leave),
            ("Attendance Report", self._report_attendance),
            ("Certification Status", self._report_certs),
            ("Appraisal Cycles", self._report_appraisals),
            ("Pending Reviews", self._report_pending_reviews),
        ]
        for label, cmd in self._reports:
            ttk.Button(left, text=label, width=22, command=cmd).pack(fill=tk.X, pady=2)

        # Compliance: equality, gender pay gap, HESA, retention. Buttons the
        # signed-in person may not use stay visible but disabled.
        ttk.Separator(left).pack(fill=tk.X, pady=8)
        ttk.Label(left, text="Compliance", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        hr = _access.can(self, 'reports')
        pay = hr or _access.can(self, 'payroll')
        admin = _access.can(self, 'hr_admin')
        self._compliance = [
            ("Equality Monitoring", 'EqualityReportWindow', hr),
            ("Gender Pay Gap", 'PayGapWindow', pay),
            ("HESA Staff Return", 'HesaStaffWindow', hr),
            ("HR Retention", 'RetentionWindow', admin),
            ("My Equality Information", 'MyEqualityWindow', True),
        ]
        for label, window, allowed in self._compliance:
            ttk.Button(left, text=label, width=22, state=tk.NORMAL if allowed else tk.DISABLED,
                       command=lambda w=window: self._open_compliance(w)).pack(fill=tk.X, pady=2)

        # Right: output
        right = ttk.Frame(body)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.output = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=('Courier New', 10))
        self.output.pack(fill=tk.BOTH, expand=True)
        self._write("Select a report from the left to run it.")

    # ------------------------------------------------------------------
    def _write(self, text):
        self.output.config(state=tk.NORMAL)
        self.output.delete('1.0', tk.END)
        self.output.insert(tk.END, text)
        self.output.config(state=tk.DISABLED)

    def _open_compliance(self, name):
        from education_system.systems.university.domains.staff.interfaces.gui.staff_hr import (
            compliance_gui,
        )
        parent = self.window or getattr(self, 'tab_frame', None) or self.root
        try:
            getattr(compliance_gui, name)(parent.winfo_toplevel(), self)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open {name}: {e}", parent=parent)

    def _run(self, title, fn, hr_only=True):
        if hr_only and not _access.can(self, 'reports'):
            self._write(f"{title}\n{'=' * 50}\n\nOrganisation-wide reports are available to HR only.")
            return
        try:
            body = fn()
        except Exception as e:
            self._write(f"{title}\n{'=' * 50}\n\nError: {e}")
            return
        self._write(f"{title}\n{'=' * 50}\n\n{body}")

    # ------------------------------------------------------------------
    # Individual reports (real manager calls)
    # ------------------------------------------------------------------
    def _report_headcount(self):
        def build():
            total = EmployeeManager.get_directory_count()
            depts = EmployeeManager.get_departments()
            lines = [f"Current Headcount: {total}", f"Departments: {len(depts)}", ""]
            for d in depts:
                lines.append(f"  {d}: {EmployeeManager.get_directory_count(department=d)}")
            return "\n".join(lines)
        self._run("Headcount Report", build)

    def _report_departments(self):
        def build():
            depts = EmployeeManager.get_departments()
            if not depts:
                return "No departments found."
            lines = []
            for d in depts:
                lines.append(f"  {d}: {EmployeeManager.get_directory_count(department=d)} staff")
            return "\n".join(lines)
        self._run("Department Breakdown", build)

    def _report_leave(self):
        def build():
            rows = LeaveManager.get_leave_summary(year=datetime.now().year)
            if not rows:
                return "No leave data available."
            lines = [f"{'Department':<20}{'Type':<18}{'Alloc':>8}{'Used':>8}{'Remain':>8}", "-" * 62]
            for r in rows:
                lines.append(
                    f"{str(r.get('department') or 'N/A'):<20}"
                    f"{str(r.get('leave_type') or ''):<18}"
                    f"{r.get('total_allocated') or 0:>8}"
                    f"{r.get('total_used') or 0:>8}"
                    f"{r.get('total_remaining') or 0:>8}")
            return "\n".join(lines)
        self._run("Leave Usage Summary", build)

    def _report_attendance(self):
        def build():
            rows = TimeManager.get_attendance_report()
            if not rows:
                return "No attendance data available."
            lines = [f"{'User':<15}{'Department':<20}{'Days Worked':>12}", "-" * 47]
            for r in rows:
                lines.append(
                    f"{str(r.get('user_id') or ''):<15}"
                    f"{str(r.get('department') or 'N/A'):<20}"
                    f"{r.get('days_worked') or 0:>12}")
            return "\n".join(lines)
        self._run("Attendance Report (last 30 days)", build)

    def _report_certs(self):
        def build():
            rows = TrainingManager.get_expiring_certs(days=30)
            header = f"Certifications expiring within 30 days: {len(rows)}\n"
            if not rows:
                return header + "\nNone expiring soon."
            lines = [header, f"{'Name':<30}{'User':<15}{'Expiry':<12}", "-" * 57]
            for r in rows:
                lines.append(
                    f"{str(r.get('name') or r.get('certification_name') or ''):<30}"
                    f"{str(r.get('user_id') or ''):<15}"
                    f"{str(r.get('expiry_date') or ''):<12}")
            return "\n".join(lines)
        self._run("Certification Status", build)

    def _report_appraisals(self):
        def build():
            cycles = PerformanceManager.get_cycles()
            if not cycles:
                return "No appraisal cycles found."
            lines = [f"{'Cycle':<28}{'Status':<16}{'Start':<12}{'End':<12}", "-" * 68]
            for c in cycles:
                lines.append(
                    f"{str(c.get('name') or ''):<28}"
                    f"{str(c.get('status') or ''):<16}"
                    f"{str(c.get('start_date') or ''):<12}"
                    f"{str(c.get('end_date') or ''):<12}")
            return "\n".join(lines)
        self._run("Appraisal Cycles", build)

    def _report_pending_reviews(self):
        def build():
            rows = PerformanceManager.get_pending_reviews(self.user_id)
            header = f"Appraisals pending your review: {len(rows)}\n"
            if not rows:
                return header + "\nNothing pending."
            lines = [header, f"{'User':<15}{'Department':<20}{'Cycle':<24}", "-" * 59]
            for r in rows:
                lines.append(
                    f"{str(r.get('user_id') or ''):<15}"
                    f"{str(r.get('department') or 'N/A'):<20}"
                    f"{str(r.get('cycle_name') or ''):<24}")
            return "\n".join(lines)
        self._run("Pending Reviews", build, hr_only=False)
