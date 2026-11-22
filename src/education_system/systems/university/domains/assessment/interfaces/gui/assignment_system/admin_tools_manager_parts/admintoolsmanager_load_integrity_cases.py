"""Methods show_grade_audit_log through _clear_audit_filters (integrity cases moved to
plagiarism_main_gui.cases_panel)."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk
from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import messagebox
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH

from .. import admin_tools_manager_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})
from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import make_toplevel
from education_system.systems.university.infrastructure.ui.field_pickers import attach_picker


class AdminToolsManager:
    def show_grade_audit_log(self):
        """View grade change audit trail with filters"""
        if not self._check_permission('view_audit_logs'):
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.access_denied', default="Access Denied"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.you_do_not_have_permission_to_view_the_audit_log', default="You do not have permission to view the audit log."))
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.grade_change_audit_log', default="Grade Change Audit Log"), style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Filters
        filter_frame = ttk.LabelFrame(content, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.filters', default="Filters"), padding=10)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.student_id', default="Student ID:")).pack(side='left', padx=(0, 5))
        self.audit_student_var = tk.StringVar()
        attach_picker(filter_frame, 'student', id_var=self.audit_student_var,
                      width=28).pack(side='left', padx=5)

        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.assignment_id', default="Assignment ID:")).pack(side='left', padx=(15, 5))
        self.audit_assignment_var = tk.StringVar()
        attach_picker(filter_frame, 'assignment', id_var=self.audit_assignment_var,
                      width=26).pack(side='left', padx=5)

        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.labels.changed_by', default="Changed By:")).pack(side='left', padx=(15, 5))
        self.audit_changed_by_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.audit_changed_by_var, width=15).pack(side='left', padx=5)

        ttk.Button(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.buttons.search', default="Search"), command=self._load_audit_log).pack(side='left', padx=15)
        ttk.Button(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.buttons.clear', default="Clear"), command=self._clear_audit_filters).pack(side='left', padx=5)

        # Audit log treeview
        log_frame = ttk.Frame(content)
        log_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Submission', 'Student', 'Assignment', 'Old Grade', 'New Grade', 'Changed By', 'Reason', 'Date')
        self.audit_tree = ttk.Treeview(log_frame, columns=columns, show='headings', height=16)

        col_widths = {'ID': 40, 'Submission': 80, 'Student': 90, 'Assignment': 80,
                      'Old Grade': 75, 'New Grade': 75, 'Changed By': 100, 'Reason': 160, 'Date': 140}
        for col in columns:
            self.audit_tree.heading(col, text=col)
            self.audit_tree.column(col, width=col_widths.get(col, 100))

        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.audit_tree.yview)
        self.audit_tree.configure(yscrollcommand=scrollbar.set)
        self.audit_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self._load_audit_log()

    def _load_audit_log(self):
        """Load audit log entries with current filters"""
        for item in self.audit_tree.get_children():
            self.audit_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            query = '''
                SELECT id, submission_id, student_id, assignment_id,
                       old_grade, new_grade, changed_by, reason, changed_at
                FROM grade_audit_log WHERE 1=1
            '''
            params = []

            student_filter = self.audit_student_var.get().strip()
            if student_filter:
                query += ' AND student_id = ?'
                params.append(student_filter)

            assignment_filter = self.audit_assignment_var.get().strip()
            if assignment_filter:
                query += ' AND assignment_id = ?'
                params.append(assignment_filter)

            changed_by_filter = self.audit_changed_by_var.get().strip()
            if changed_by_filter:
                query += ' AND changed_by LIKE ?'
                params.append(f'%{changed_by_filter}%')

            query += ' ORDER BY changed_at DESC LIMIT 200'

            cursor.execute(query, params)
            for row in cursor.fetchall():
                self.audit_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_load_integrity_cases.dialogs.error', default="Error"), f"Failed to load audit log: {e}")

    def _clear_audit_filters(self):
        """Clear audit log filters and reload"""
        self.audit_student_var.set('')
        self.audit_assignment_var.set('')
        self.audit_changed_by_var.set('')
        self._load_audit_log()
