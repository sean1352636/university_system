"""
Training & Certification GUI

Provides interface for:
- Viewing training course catalog
- Enrolling in training courses
- Tracking certifications
- Certification expiry alerts
- Training completion reports
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Optional
import csv

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.i18n import get_text as get_translation

# Translation helper
_t = get_translation


class TrainingGUI:
    """GUI for managing training and certifications."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror(
                _t("staff_hr.training.errors.error_generic", default="Error"),
                _t("staff_hr.training.errors.login_required", default="Login required to access Training & Certifications")
            )
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text=_t("staff_hr.training.tab_title", default="Training"))
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title(_t("staff_hr.training.window_title", default="Training & Certification System"))
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)

        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text=_t("staff_hr.training.close", default="Close"), command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_bar = ttk.Label(self.window, text=_t("staff_hr.training.ready", default="Ready"), relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._build_interface(self.window)

    def _build_interface(self, parent):
        """Build the main interface."""
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_catalog_tab()
        self._create_my_training_tab()
        self._create_certifications_tab()
        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_manage_tab()

    def _create_catalog_tab(self):
        """Create the training catalog tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_hr.training.tabs.course_catalog", default="Course Catalog"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("staff_hr.training.catalog.header", default="Training Course Catalog"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t("staff_hr.training.catalog.btn_enroll", default="Enroll in Selected"), command=self._enroll_in_course).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_hr.training.catalog.btn_refresh", default="Refresh"), command=self._load_catalog).pack(side=tk.LEFT, padx=5)

        # Filter frame
        filter_frame = ttk.LabelFrame(tab, text=_t("staff_hr.training.catalog.header", default="Filters"), padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text=_t("staff_hr.training.catalog.filter_category", default="Category:")).pack(side=tk.LEFT, padx=5)
        self.category_filter = ttk.Combobox(filter_frame,
                                            values=[
                                                _t("staff_hr.training.catalog.categories.all", default="All"),
                                                _t("staff_hr.training.catalog.categories.compliance", default="Compliance"),
                                                _t("staff_hr.training.catalog.categories.safety", default="Safety"),
                                                _t("staff_hr.training.catalog.categories.it", default="IT"),
                                                _t("staff_hr.training.catalog.categories.development", default="Development"),
                                                _t("staff_hr.training.catalog.categories.other", default="Other")
                                            ],
                                            width=15, state='readonly')
        self.category_filter.set(_t("staff_hr.training.catalog.categories.all", default="All"))
        self.category_filter.pack(side=tk.LEFT, padx=5)
        self.category_filter.bind('<<ComboboxSelected>>', lambda e: self._load_catalog())

        self.mandatory_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text=_t("staff_hr.training.catalog.filter_mandatory_only", default="Mandatory Only"), variable=self.mandatory_only,
                        command=self._load_catalog).pack(side=tk.LEFT, padx=20)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = (
            _t("staff_hr.training.catalog.columns.id", default="ID"),
            _t("staff_hr.training.catalog.columns.name", default="Name"),
            _t("staff_hr.training.catalog.columns.category", default="Category"),
            _t("staff_hr.training.catalog.columns.provider", default="Provider"),
            _t("staff_hr.training.catalog.columns.duration", default="Duration"),
            _t("staff_hr.training.catalog.columns.passing_score", default="Passing Score"),
            _t("staff_hr.training.catalog.columns.mandatory", default="Mandatory")
        )
        self.catalog_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                         yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.catalog_tree.yview)

        col_widths = {
            _t("staff_hr.training.catalog.columns.id", default="ID"): 50,
            _t("staff_hr.training.catalog.columns.name", default="Name"): 200,
            _t("staff_hr.training.catalog.columns.category", default="Category"): 100,
            _t("staff_hr.training.catalog.columns.provider", default="Provider"): 120,
            _t("staff_hr.training.catalog.columns.duration", default="Duration"): 80,
            _t("staff_hr.training.catalog.columns.passing_score", default="Passing Score"): 100,
            _t("staff_hr.training.catalog.columns.mandatory", default="Mandatory"): 80
        }
        for col in columns:
            self.catalog_tree.heading(col, text=col)
            self.catalog_tree.column(col, width=col_widths.get(col, 100))

        self.catalog_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Tag for mandatory courses
        self.catalog_tree.tag_configure('mandatory', background='#fff3cd')

        # Bind double-click to view details
        self.catalog_tree.bind('<Double-1>', self._view_course_details)

        self._load_catalog()

    def _create_my_training_tab(self):
        """Create the my training tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_hr.training.tabs.my_training", default="My Training"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("staff_hr.training.my_training.header", default="My Training Enrollments"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t("staff_hr.training.my_training.btn_mark_complete", default="Mark Complete"), command=self._mark_training_complete).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_hr.training.my_training.btn_refresh", default="Refresh"), command=self._load_my_training).pack(side=tk.LEFT, padx=5)

        # Filter
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text=_t("staff_hr.training.my_training.filter_status", default="Status:")).pack(side=tk.LEFT, padx=5)
        self.training_status_filter = ttk.Combobox(filter_frame,
                                                    values=[
                                                        _t("staff_hr.training.my_training.statuses.all", default="All"),
                                                        _t("staff_hr.training.my_training.statuses.enrolled", default="Enrolled"),
                                                        _t("staff_hr.training.my_training.statuses.in_progress", default="In Progress"),
                                                        _t("staff_hr.training.my_training.statuses.completed", default="Completed"),
                                                        _t("staff_hr.training.my_training.statuses.failed", default="Failed")
                                                    ],
                                                    width=15, state='readonly')
        self.training_status_filter.set(_t("staff_hr.training.my_training.statuses.all", default="All"))
        self.training_status_filter.pack(side=tk.LEFT, padx=5)
        self.training_status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_my_training())

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = (
            _t("staff_hr.training.my_training.columns.id", default="ID"),
            _t("staff_hr.training.my_training.columns.course", default="Course"),
            _t("staff_hr.training.my_training.columns.category", default="Category"),
            _t("staff_hr.training.my_training.columns.enrolled", default="Enrolled"),
            _t("staff_hr.training.my_training.columns.due_date", default="Due Date"),
            _t("staff_hr.training.my_training.columns.status", default="Status"),
            _t("staff_hr.training.my_training.columns.score", default="Score"),
            _t("staff_hr.training.my_training.columns.completed", default="Completed")
        )
        self.training_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                          yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.training_tree.yview)

        for col in columns:
            self.training_tree.heading(col, text=col)
            self.training_tree.column(col, width=100, anchor=tk.CENTER)

        self.training_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status tags
        self.training_tree.tag_configure('enrolled', background='#cce5ff')
        self.training_tree.tag_configure('in_progress', background='#fff3cd')
        self.training_tree.tag_configure('completed', background='#d4edda')
        self.training_tree.tag_configure('failed', background='#f8d7da')
        self.training_tree.tag_configure('overdue', background='#f8d7da')

        # Summary
        summary_frame = ttk.LabelFrame(tab, text=_t("staff_hr.training.my_training.summary.title", default="Training Summary"), padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)

        self.total_courses_label = ttk.Label(summary_frame, text=_t("staff_hr.training.my_training.summary.total_enrolled", default="Total Enrolled: {count}").format(count=0))
        self.total_courses_label.pack(side=tk.LEFT, padx=20)

        self.completed_label = ttk.Label(summary_frame, text=_t("staff_hr.training.my_training.summary.completed", default="Completed: {count}").format(count=0))
        self.completed_label.pack(side=tk.LEFT, padx=20)

        self.pending_label = ttk.Label(summary_frame, text=_t("staff_hr.training.my_training.summary.pending", default="Pending: {count}").format(count=0))
        self.pending_label.pack(side=tk.LEFT, padx=20)

        self.overdue_label = ttk.Label(summary_frame, text=_t("staff_hr.training.my_training.summary.overdue", default="Overdue: {count}").format(count=0), foreground='red')
        self.overdue_label.pack(side=tk.LEFT, padx=20)

        self._load_my_training()

    def _create_certifications_tab(self):
        """Create the certifications tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_hr.training.tabs.my_certifications", default="My Certifications"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("staff_hr.training.certifications.header", default="My Certifications"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t("staff_hr.training.certifications.btn_add", default="Add Certification"), command=self._add_certification).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_hr.training.certifications.btn_refresh", default="Refresh"), command=self._load_certifications).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_hr.training.certifications.btn_export", default="Export"), command=self._export_certifications).pack(side=tk.LEFT, padx=5)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = (
            _t("staff_hr.training.certifications.columns.id", default="ID"),
            _t("staff_hr.training.certifications.columns.name", default="Name"),
            _t("staff_hr.training.certifications.columns.issuing_body", default="Issuing Body"),
            _t("staff_hr.training.certifications.columns.credential_id", default="Credential ID"),
            _t("staff_hr.training.certifications.columns.issue_date", default="Issue Date"),
            _t("staff_hr.training.certifications.columns.expiry_date", default="Expiry Date"),
            _t("staff_hr.training.certifications.columns.status", default="Status")
        )
        self.certs_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                       yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.certs_tree.yview)

        col_widths = {
            _t("staff_hr.training.certifications.columns.id", default="ID"): 50,
            _t("staff_hr.training.certifications.columns.name", default="Name"): 180,
            _t("staff_hr.training.certifications.columns.issuing_body", default="Issuing Body"): 150,
            _t("staff_hr.training.certifications.columns.credential_id", default="Credential ID"): 120,
            _t("staff_hr.training.certifications.columns.issue_date", default="Issue Date"): 100,
            _t("staff_hr.training.certifications.columns.expiry_date", default="Expiry Date"): 100,
            _t("staff_hr.training.certifications.columns.status", default="Status"): 80
        }
        for col in columns:
            self.certs_tree.heading(col, text=col)
            self.certs_tree.column(col, width=col_widths.get(col, 100))

        self.certs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status tags
        self.certs_tree.tag_configure('active', background='#d4edda')
        self.certs_tree.tag_configure('expiring', background='#fff3cd')
        self.certs_tree.tag_configure('expired', background='#f8d7da')

        # Bind double-click
        self.certs_tree.bind('<Double-1>', self._view_certification)

        # Expiry alerts
        alert_frame = ttk.LabelFrame(tab, text=_t("staff_hr.training.certifications.alerts.title", default="Expiry Alerts"), padding=10)
        alert_frame.pack(fill=tk.X, padx=10, pady=10)

        self.expiry_alert_label = ttk.Label(alert_frame, text=_t("staff_hr.training.certifications.alerts.no_expiring", default="No certifications expiring soon"), foreground='green')
        self.expiry_alert_label.pack(side=tk.LEFT, padx=10)

        self._load_certifications()

    def _create_manage_tab(self):
        """Create the manage courses tab (admin/staff only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_hr.training.tabs.manage_courses", default="Manage Courses"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("staff_hr.training.manage.header", default="Manage Training Courses"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t("staff_hr.training.manage.btn_add_course", default="Add Course"), command=self._add_course).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="View Details", command=self._view_manage_course).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_hr.training.manage.btn_edit", default="Edit Selected"), command=self._edit_course).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete", command=self._delete_course).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_hr.training.manage.btn_deactivate", default="Deactivate"), command=self._deactivate_course).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_manage_courses).pack(side=tk.LEFT, padx=5)

        # Filter
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="Show:").pack(side=tk.LEFT, padx=5)
        self.manage_filter = ttk.Combobox(filter_frame,
            values=['All', 'Active Only', 'Inactive Only'], width=14, state='readonly')
        self.manage_filter.set('All')
        self.manage_filter.pack(side=tk.LEFT, padx=5)
        self.manage_filter.bind('<<ComboboxSelected>>', lambda e: self._load_manage_courses())

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Name', 'Category', 'Provider', 'Duration', 'Passing Score',
                   'Mandatory', 'Active', 'Enrollments')
        self.manage_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                        yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.manage_tree.yview)

        col_widths = {'ID': 50, 'Name': 180, 'Category': 100, 'Provider': 120,
                      'Duration': 70, 'Passing Score': 90, 'Mandatory': 75,
                      'Active': 60, 'Enrollments': 85}
        for col in columns:
            self.manage_tree.heading(col, text=col)
            self.manage_tree.column(col, width=col_widths.get(col, 100), anchor=tk.CENTER)

        self.manage_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.manage_tree.tag_configure('inactive', foreground='gray')

        # Double-click to view details
        self.manage_tree.bind('<Double-1>', lambda e: self._view_manage_course())

        self._load_manage_courses()

    def _load_catalog(self):
        """Load training course catalog."""
        try:
            self.catalog_tree.delete(*self.catalog_tree.get_children())

            category = self.category_filter.get()
            mandatory_only = self.mandatory_only.get()

            with get_connection() as conn:
                cursor = conn.cursor()

                query = '''
                    SELECT course_id, name, category, provider, duration_hours,
                           passing_score, is_mandatory
                    FROM training_courses
                    WHERE is_active = 1
                '''
                params = []

                if category != 'All':
                    query += ' AND category = ?'
                    params.append(category)

                if mandatory_only:
                    query += ' AND is_mandatory = 1'

                query += ' ORDER BY name'

                cursor.execute(query, params)

                for row in cursor.fetchall():
                    duration = _t("staff_hr.training.catalog.values.duration_hours", default="{hours}h").format(hours=f"{row[4]:.1f}") if row[4] else _t("staff_hr.training.catalog.values.na", default="-")
                    passing = _t("staff_hr.training.catalog.values.passing_percent", default="{score}%").format(score=row[5]) if row[5] else _t("staff_hr.training.catalog.values.na", default="-")
                    mandatory = _t("staff_hr.training.catalog.values.yes", default="Yes") if row[6] else _t("staff_hr.training.catalog.values.no", default="No")

                    values = (row[0], row[1], row[2] or _t("staff_hr.training.catalog.values.na", default="-"), row[3] or _t("staff_hr.training.catalog.values.na", default="-"),
                              duration, passing, mandatory)

                    tags = ('mandatory',) if row[6] else ()
                    self.catalog_tree.insert('', 'end', values=values, tags=tags)

        except Exception as e:
            messagebox.showerror(
                _t("staff_hr.training.errors.error_generic", default="Error"),
                _t("staff_hr.training.errors.load_catalog_failed", default="Failed to load catalog: {error}").format(error=str(e))
            )

    def _load_my_training(self):
        """Load user's training enrollments."""
        try:
            self.training_tree.delete(*self.training_tree.get_children())

            user_id = self.current_user.get('id') or self.current_user.get('username')
            status_filter = self.training_status_filter.get()
            today = datetime.now().strftime("%Y-%m-%d")

            with get_connection() as conn:
                cursor = conn.cursor()

                query = '''
                    SELECT e.enrollment_id, c.name, c.category, e.enrolled_date,
                           e.due_date, e.status, e.score, e.completed_date
                    FROM training_enrollments e
                    JOIN training_courses c ON e.course_id = c.course_id
                    WHERE e.user_id = ?
                '''
                params = [user_id]

                if status_filter != 'All':
                    query += ' AND e.status = ?'
                    params.append(status_filter.lower().replace(' ', '_'))

                query += ' ORDER BY e.enrolled_date DESC'

                cursor.execute(query, params)

                total = 0
                completed = 0
                pending = 0
                overdue = 0

                for row in cursor.fetchall():
                    total += 1
                    status = row[5]

                    if status == 'completed':
                        completed += 1
                    elif status in ['enrolled', 'in_progress']:
                        pending += 1
                        if row[4] and row[4] < today:
                            overdue += 1
                            status = 'overdue'

                    score = f"{row[6]}%" if row[6] else '-'

                    values = (row[0], row[1], row[2] or '-', row[3][:10] if row[3] else '-',
                              row[4] or '-', status.replace('_', ' ').capitalize(),
                              score, row[7][:10] if row[7] else '-')

                    self.training_tree.insert('', 'end', values=values, tags=(status,))

            self.total_courses_label.config(text=_t("staff_hr.training.my_training.summary.total_enrolled", default="Total Enrolled: {count}").format(count=total))
            self.completed_label.config(text=_t("staff_hr.training.my_training.summary.completed", default="Completed: {count}").format(count=completed))
            self.pending_label.config(text=_t("staff_hr.training.my_training.summary.pending", default="Pending: {count}").format(count=pending))
            self.overdue_label.config(text=_t("staff_hr.training.my_training.summary.overdue", default="Overdue: {count}").format(count=overdue))

        except Exception as e:
            messagebox.showerror(
                _t("staff_hr.training.errors.error_generic", default="Error"),
                _t("staff_hr.training.errors.load_training_failed", default="Failed to load training: {error}").format(error=str(e))
            )

    def _load_certifications(self):
        """Load user's certifications."""
        try:
            self.certs_tree.delete(*self.certs_tree.get_children())

            user_id = self.current_user.get('id') or self.current_user.get('username')
            today = datetime.now()
            warning_date = (today + timedelta(days=30)).strftime("%Y-%m-%d")

            expiring_count = 0

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT cert_id, name, issuing_body, credential_id,
                           issue_date, expiry_date, status
                    FROM certifications
                    WHERE user_id = ?
                    ORDER BY expiry_date ASC
                ''', (user_id,))

                for row in cursor.fetchall():
                    status = row[6]
                    tag = status

                    # Check expiry
                    if row[5]:
                        if row[5] < today.strftime("%Y-%m-%d"):
                            status = _t("staff_hr.training.certifications.statuses.expired", default="Expired")
                            tag = 'expired'
                        elif row[5] <= warning_date:
                            status = _t("staff_hr.training.certifications.statuses.expiring_soon", default="Expiring Soon")
                            tag = 'expiring'
                            expiring_count += 1
                        else:
                            status = _t("staff_hr.training.certifications.statuses.active", default="Active")
                            tag = 'active'

                    values = (row[0], row[1], row[2] or _t("staff_hr.training.catalog.values.na", default="-"), row[3] or _t("staff_hr.training.catalog.values.na", default="-"),
                              row[4] or _t("staff_hr.training.catalog.values.na", default="-"), row[5] or _t("staff_hr.training.certifications.statuses.no_expiry", default="No Expiry"), status)

                    self.certs_tree.insert('', 'end', values=values, tags=(tag,))

            if expiring_count > 0:
                self.expiry_alert_label.config(
                    text=_t("staff_hr.training.certifications.alerts.expiring_soon", default="{count} certification(s) expiring within 30 days!").format(count=expiring_count),
                    foreground='red'
                )
            else:
                self.expiry_alert_label.config(
                    text=_t("staff_hr.training.certifications.alerts.no_expiring", default="No certifications expiring soon"),
                    foreground='green'
                )

        except Exception as e:
            messagebox.showerror(
                _t("staff_hr.training.errors.error_generic", default="Error"),
                _t("staff_hr.training.errors.load_certifications_failed", default="Failed to load certifications: {error}").format(error=str(e))
            )

    def _enroll_in_course(self):
        """Enroll in selected course."""
        selection = self.catalog_tree.selection()
        if not selection:
            messagebox.showwarning(
                _t("staff_hr.training.dialogs.enroll.warning_title", default="Warning"),
                _t("staff_hr.training.dialogs.enroll.warning_select", default="Please select a course to enroll in")
            )
            return

        item = self.catalog_tree.item(selection[0])
        course_id = item['values'][0]
        course_name = item['values'][1]

        if not messagebox.askyesno(
            _t("staff_hr.training.dialogs.enroll.confirm_title", default="Confirm"),
            _t("staff_hr.training.dialogs.enroll.confirm_message", default="Enroll in '{course_name}'?").format(course_name=course_name)
        ):
            return

        user_id = self.current_user.get('id') or self.current_user.get('username')

        try:
            # Check if already enrolled
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT enrollment_id FROM training_enrollments
                    WHERE user_id = ? AND course_id = ? AND status != 'completed'
                ''', (user_id, course_id))

                if cursor.fetchone():
                    messagebox.showwarning(
                        _t("staff_hr.training.dialogs.enroll.warning_title", default="Warning"),
                        _t("staff_hr.training.dialogs.enroll.warning_already_enrolled", default="You are already enrolled in this course")
                    )
                    return

            with transaction() as conn:
                # Default due date is 30 days from now
                due_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

                conn.execute('''
                    INSERT INTO training_enrollments
                    (user_id, course_id, enrolled_date, due_date, status)
                    VALUES (?, ?, ?, ?, 'enrolled')
                ''', (user_id, course_id, datetime.now().strftime("%Y-%m-%d"), due_date))

            log_activity('create', 'training_enrollment', user_id=user_id,
                         details={'course_id': course_id, 'course_name': course_name})

            messagebox.showinfo(
                _t("staff_hr.training.dialogs.enroll.success_title", default="Success"),
                _t("staff_hr.training.dialogs.enroll.success_message", default="Successfully enrolled in '{course_name}'").format(course_name=course_name)
            )
            self._load_my_training()

        except Exception as e:
            messagebox.showerror(
                _t("staff_hr.training.errors.error_generic", default="Error"),
                _t("staff_hr.training.errors.enroll_failed", default="Failed to enroll: {error}").format(error=str(e))
            )

    def _mark_training_complete(self):
        """Mark selected training as complete."""
        selection = self.training_tree.selection()
        if not selection:
            messagebox.showwarning(
                _t("staff_hr.training.dialogs.enroll.warning_title", default="Warning"),
                _t("staff_hr.training.dialogs.mark_complete.warning_select", default="Please select a training to mark complete")
            )
            return

        item = self.training_tree.item(selection[0])
        enrollment_id = item['values'][0]
        status = item['values'][5].lower()

        if status == 'completed':
            messagebox.showwarning(
                _t("staff_hr.training.dialogs.enroll.warning_title", default="Warning"),
                _t("staff_hr.training.dialogs.mark_complete.warning_already_complete", default="This training is already completed")
            )
            return

        # Ask for score
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("staff_hr.training.dialogs.mark_complete.title", default="Complete Training"))
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("staff_hr.training.dialogs.mark_complete.label_score", default="Enter your score (0-100):")).pack(pady=10)
        score_var = tk.StringVar(value="100")
        ttk.Entry(main_frame, textvariable=score_var, width=10).pack(pady=5)

        def complete():
            try:
                score = float(score_var.get())
                if not 0 <= score <= 100:
                    raise ValueError(_t("staff_hr.training.dialogs.mark_complete.error_range", default="Score must be between 0 and 100"))

                with transaction() as conn:
                    conn.execute('''
                        UPDATE training_enrollments
                        SET status = 'completed', score = ?, completed_date = ?, updated_at = ?
                        WHERE enrollment_id = ?
                    ''', (score, datetime.now().strftime("%Y-%m-%d"),
                          datetime.now().isoformat(), enrollment_id))

                messagebox.showinfo(
                    _t("staff_hr.training.dialogs.enroll.success_title", default="Success"),
                    _t("staff_hr.training.dialogs.mark_complete.success", default="Training marked as complete")
                )
                dialog.destroy()
                self._load_my_training()

            except ValueError as e:
                messagebox.showerror(
                    _t("staff_hr.training.errors.error_generic", default="Error"),
                    str(e)
                )
            except Exception as e:
                messagebox.showerror(
                    _t("staff_hr.training.errors.error_generic", default="Error"),
                    _t("staff_hr.training.errors.update_failed", default="Failed to update: {error}").format(error=str(e))
                )

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text=_t("staff_hr.training.dialogs.mark_complete.btn_complete", default="Complete"), command=complete).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("staff_hr.training.dialogs.mark_complete.btn_cancel", default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _add_certification(self):
        """Add a new certification."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("staff_hr.training.dialogs.add_certification.title", default="Add Certification"))
        dialog.geometry("450x450")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("staff_hr.training.dialogs.add_certification.header", default="Add New Certification"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        fields = {}

        # Name
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t("staff_hr.training.dialogs.add_certification.label_name", default="Certification Name:"), width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['name'] = ttk.Entry(row, width=30)
        fields['name'].pack(side=tk.LEFT)

        # Issuing body
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t("staff_hr.training.dialogs.add_certification.label_issuer", default="Issuing Body:"), width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['issuer'] = ttk.Entry(row, width=30)
        fields['issuer'].pack(side=tk.LEFT)

        # Credential ID
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t("staff_hr.training.dialogs.add_certification.label_credential_id", default="Credential ID:"), width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['credential_id'] = ttk.Entry(row, width=30)
        fields['credential_id'].pack(side=tk.LEFT)

        # Issue date
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t("staff_hr.training.dialogs.add_certification.label_issue_date", default="Issue Date:"), width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['issue_date'] = ttk.Entry(row, width=15)
        fields['issue_date'].insert(0, datetime.now().strftime("%Y-%m-%d"))
        fields['issue_date'].pack(side=tk.LEFT)
        ttk.Label(row, text=_t("staff_hr.training.dialogs.add_certification.hint_date_format", default="(YYYY-MM-DD)"), font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # Expiry date
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t("staff_hr.training.dialogs.add_certification.label_expiry_date", default="Expiry Date:"), width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['expiry_date'] = ttk.Entry(row, width=15)
        fields['expiry_date'].pack(side=tk.LEFT)
        ttk.Label(row, text=_t("staff_hr.training.dialogs.add_certification.hint_no_expiry", default="(Leave blank if none)"), font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # Notes
        ttk.Label(main_frame, text=_t("staff_hr.training.dialogs.add_certification.label_notes", default="Notes:"), anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        notes_text = scrolledtext.ScrolledText(main_frame, height=4, width=40)
        notes_text.pack(fill=tk.X)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save():
            name = fields['name'].get().strip()
            if not name:
                error_label.config(text=_t("staff_hr.training.dialogs.add_certification.error_name_required", default="Certification name is required"))
                return

            user_id = self.current_user.get('id') or self.current_user.get('username')
            expiry = fields['expiry_date'].get().strip() or None

            try:
                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO certifications
                        (user_id, name, issuing_body, credential_id, issue_date, expiry_date, notes, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                    ''', (user_id, name, fields['issuer'].get().strip(),
                          fields['credential_id'].get().strip(),
                          fields['issue_date'].get().strip(), expiry,
                          notes_text.get('1.0', tk.END).strip()))

                log_activity('create', 'certification', user_id=user_id, details={'name': name})
                messagebox.showinfo(
                    _t("staff_hr.training.dialogs.enroll.success_title", default="Success"),
                    _t("staff_hr.training.dialogs.add_certification.success", default="Certification added successfully")
                )
                dialog.destroy()
                self._load_certifications()

            except Exception as e:
                error_label.config(text=_t("staff_hr.training.errors.error_with_message", default="Error: {error}").format(error=str(e)))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t("staff_hr.training.dialogs.add_certification.btn_save", default="Save"), command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("staff_hr.training.dialogs.add_certification.btn_cancel", default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _view_course_details(self, event=None):
        """View course details."""
        selection = self.catalog_tree.selection()
        if not selection:
            return

        item = self.catalog_tree.item(selection[0])
        course_id = item['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM training_courses WHERE course_id = ?', (course_id,))
                row = cursor.fetchone()

            if row:
                details = f"""
{_t("staff_hr.training.dialogs.course_details.course_id", default="Course ID: {id}").format(id=row[0])}
{_t("staff_hr.training.dialogs.course_details.name", default="Name: {name}").format(name=row[1])}
{_t("staff_hr.training.dialogs.course_details.description", default="Description: {description}").format(description=row[2] or _t("staff_hr.training.dialogs.course_details.no_description", default="No description"))}
{_t("staff_hr.training.dialogs.course_details.category", default="Category: {category}").format(category=row[3] or _t("staff_hr.training.catalog.values.na", default="N/A"))}
{_t("staff_hr.training.dialogs.course_details.provider", default="Provider: {provider}").format(provider=row[4] or _t("staff_hr.training.catalog.values.na", default="N/A"))}
{_t("staff_hr.training.dialogs.course_details.duration", default="Duration: {duration} hours").format(duration=row[5] or _t("staff_hr.training.catalog.values.na", default="N/A"))}
{_t("staff_hr.training.dialogs.course_details.passing_score", default="Passing Score: {score}%").format(score=row[6] or _t("staff_hr.training.catalog.values.na", default="N/A"))}
{_t("staff_hr.training.dialogs.course_details.mandatory", default="Mandatory: {mandatory}").format(mandatory=_t("staff_hr.training.catalog.values.yes", default="Yes") if row[7] else _t("staff_hr.training.catalog.values.no", default="No"))}
{_t("staff_hr.training.dialogs.course_details.recertification", default="Recertification: {months} months").format(months=row[8] or _t("staff_hr.training.catalog.values.na", default="N/A"))}
                """
                messagebox.showinfo(
                    _t("staff_hr.training.dialogs.course_details.title", default="Course Details"),
                    details.strip()
                )

        except Exception as e:
            messagebox.showerror(
                _t("staff_hr.training.errors.error_generic", default="Error"),
                _t("staff_hr.training.errors.load_details_failed", default="Failed to load details: {error}").format(error=str(e))
            )

    def _view_certification(self, event=None):
        """View certification details."""
        selection = self.certs_tree.selection()
        if not selection:
            return

        item = self.certs_tree.item(selection[0])
        values = item['values']

        details = f"""
{_t("staff_hr.training.dialogs.certification_details.cert_id", default="Certification ID: {id}").format(id=values[0])}
{_t("staff_hr.training.dialogs.certification_details.name", default="Name: {name}").format(name=values[1])}
{_t("staff_hr.training.dialogs.certification_details.issuing_body", default="Issuing Body: {issuer}").format(issuer=values[2])}
{_t("staff_hr.training.dialogs.certification_details.credential_id", default="Credential ID: {credential_id}").format(credential_id=values[3])}
{_t("staff_hr.training.dialogs.certification_details.issue_date", default="Issue Date: {date}").format(date=values[4])}
{_t("staff_hr.training.dialogs.certification_details.expiry_date", default="Expiry Date: {date}").format(date=values[5])}
{_t("staff_hr.training.dialogs.certification_details.status", default="Status: {status}").format(status=values[6])}
        """
        messagebox.showinfo(
            _t("staff_hr.training.dialogs.certification_details.title", default="Certification Details"),
            details.strip()
        )

    def _add_course(self):
        """Add a new training course (admin only)."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("staff_hr.training.dialogs.add_course.title", default="Add Training Course"))
        dialog.geometry("450x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("staff_hr.training.dialogs.add_course.header", default="Add New Training Course"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        fields = {}

        # Name
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t("staff_hr.training.dialogs.add_course.label_name", default="Course Name:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        fields['name'] = ttk.Entry(row, width=30)
        fields['name'].pack(side=tk.LEFT)

        # Category
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t("staff_hr.training.dialogs.add_course.label_category", default="Category:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        fields['category'] = ttk.Combobox(row, values=[
            _t("staff_hr.training.catalog.categories.compliance", default="Compliance"),
            _t("staff_hr.training.catalog.categories.safety", default="Safety"),
            _t("staff_hr.training.catalog.categories.it", default="IT"),
            _t("staff_hr.training.catalog.categories.development", default="Development"),
            _t("staff_hr.training.catalog.categories.other", default="Other")
        ], width=27, state='readonly')
        fields['category'].pack(side=tk.LEFT)

        # Provider
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t("staff_hr.training.dialogs.add_course.label_provider", default="Provider:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        fields['provider'] = ttk.Entry(row, width=30)
        fields['provider'].pack(side=tk.LEFT)

        # Duration
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t("staff_hr.training.dialogs.add_course.label_duration", default="Duration (hours):"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        fields['duration'] = ttk.Entry(row, width=10)
        fields['duration'].pack(side=tk.LEFT)

        # Passing score
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t("staff_hr.training.dialogs.add_course.label_passing_score", default="Passing Score %:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        fields['passing_score'] = ttk.Entry(row, width=10)
        fields['passing_score'].insert(0, "70")
        fields['passing_score'].pack(side=tk.LEFT)

        # Mandatory
        fields['mandatory'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text=_t("staff_hr.training.dialogs.add_course.checkbox_mandatory", default="Mandatory for all staff"), variable=fields['mandatory']).pack(anchor=tk.W, pady=10)

        # Description
        ttk.Label(main_frame, text=_t("staff_hr.training.dialogs.add_course.label_description", default="Description:"), anchor=tk.W).pack(fill=tk.X, pady=(10, 5))
        desc_text = scrolledtext.ScrolledText(main_frame, height=4, width=40)
        desc_text.pack(fill=tk.X)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save():
            name = fields['name'].get().strip()
            if not name:
                error_label.config(text=_t("staff_hr.training.dialogs.add_course.error_name_required", default="Course name is required"))
                return

            try:
                duration = float(fields['duration'].get()) if fields['duration'].get() else None
                passing = float(fields['passing_score'].get()) if fields['passing_score'].get() else 70

                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO training_courses
                        (name, description, category, provider, duration_hours, passing_score, is_mandatory)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (name, desc_text.get('1.0', tk.END).strip(),
                          fields['category'].get(), fields['provider'].get().strip(),
                          duration, passing, fields['mandatory'].get()))

                log_activity('create', 'training_course', details={'name': name})
                messagebox.showinfo(
                    _t("staff_hr.training.dialogs.enroll.success_title", default="Success"),
                    _t("staff_hr.training.dialogs.add_course.success", default="Course added successfully")
                )
                dialog.destroy()
                self._load_catalog()
                self._load_manage_courses()

            except Exception as e:
                error_label.config(text=_t("staff_hr.training.errors.error_with_message", default="Error: {error}").format(error=str(e)))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t("staff_hr.training.dialogs.add_course.btn_save", default="Save"), command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("staff_hr.training.dialogs.add_course.btn_cancel", default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _view_manage_course(self):
        """View full details of selected course."""
        selection = self.manage_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a course to view")
            return

        item = self.manage_tree.item(selection[0])
        course_id = item['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM training_courses WHERE course_id = ?', (course_id,))
                row = cursor.fetchone()

                # Get enrollment stats
                cursor.execute('''
                    SELECT status, COUNT(*) FROM training_enrollments
                    WHERE course_id = ? GROUP BY status
                ''', (course_id,))
                enrollment_stats = {r[0]: r[1] for r in cursor.fetchall()}

            if not row:
                messagebox.showerror("Error", "Course not found")
                return

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Course Details - {row[1]}")
            dialog.geometry("500x480")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=row[1], font=('Arial', 16, 'bold')).pack(anchor=tk.W, pady=(0, 15))

            # Details grid
            details_frame = ttk.LabelFrame(main_frame, text="Course Information", padding=10)
            details_frame.pack(fill=tk.X, pady=5)

            fields = [
                ("Course ID:", str(row[0])),
                ("Category:", row[3] or "N/A"),
                ("Provider:", row[4] or "N/A"),
                ("Duration:", f"{row[5]:.1f} hours" if row[5] else "N/A"),
                ("Passing Score:", f"{row[6]}%" if row[6] else "N/A"),
                ("Mandatory:", "Yes" if row[7] else "No"),
                ("Recertification:", f"Every {row[8]} months" if row[8] else "N/A"),
                ("Active:", "Yes" if row[9] else "No"),
            ]

            for i, (label, value) in enumerate(fields):
                ttk.Label(details_frame, text=label, font=('Arial', 10, 'bold')).grid(
                    row=i // 2, column=(i % 2) * 2, sticky='e', padx=5, pady=3)
                ttk.Label(details_frame, text=value).grid(
                    row=i // 2, column=(i % 2) * 2 + 1, sticky='w', padx=5, pady=3)

            # Description
            desc_frame = ttk.LabelFrame(main_frame, text="Description", padding=10)
            desc_frame.pack(fill=tk.X, pady=5)
            desc_text = scrolledtext.ScrolledText(desc_frame, height=4, state='normal')
            desc_text.insert("1.0", row[2] or "No description provided")
            desc_text.config(state='disabled')
            desc_text.pack(fill=tk.X)

            # Enrollment statistics
            stats_frame = ttk.LabelFrame(main_frame, text="Enrollment Statistics", padding=10)
            stats_frame.pack(fill=tk.X, pady=5)

            total = sum(enrollment_stats.values())
            stats_text = f"Total Enrollments: {total}"
            if enrollment_stats:
                parts = [f"{status.replace('_', ' ').title()}: {count}" for status, count in sorted(enrollment_stats.items())]
                stats_text += "  |  " + "  |  ".join(parts)
            ttk.Label(stats_frame, text=stats_text).pack(anchor='w')

            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=15)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load course details: {e}")

    def _edit_course(self):
        """Edit selected course."""
        selection = self.manage_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a course to edit")
            return

        item = self.manage_tree.item(selection[0])
        course_id = item['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM training_courses WHERE course_id = ?', (course_id,))
                row = cursor.fetchone()

            if not row:
                messagebox.showerror("Error", "Course not found")
                return

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Edit Course - {row[1]}")
            dialog.geometry("450x550")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text="Edit Training Course", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            fields = {}

            # Name
            r = ttk.Frame(main_frame)
            r.pack(fill=tk.X, pady=5)
            ttk.Label(r, text="Course Name:", width=15, anchor=tk.W).pack(side=tk.LEFT)
            fields['name'] = ttk.Entry(r, width=30)
            fields['name'].insert(0, row[1] or '')
            fields['name'].pack(side=tk.LEFT)

            # Category
            r = ttk.Frame(main_frame)
            r.pack(fill=tk.X, pady=5)
            ttk.Label(r, text="Category:", width=15, anchor=tk.W).pack(side=tk.LEFT)
            fields['category'] = ttk.Combobox(r, values=[
                'Compliance', 'Safety', 'IT', 'Development', 'Other'
            ], width=27, state='readonly')
            fields['category'].set(row[3] or '')
            fields['category'].pack(side=tk.LEFT)

            # Provider
            r = ttk.Frame(main_frame)
            r.pack(fill=tk.X, pady=5)
            ttk.Label(r, text="Provider:", width=15, anchor=tk.W).pack(side=tk.LEFT)
            fields['provider'] = ttk.Entry(r, width=30)
            fields['provider'].insert(0, row[4] or '')
            fields['provider'].pack(side=tk.LEFT)

            # Duration
            r = ttk.Frame(main_frame)
            r.pack(fill=tk.X, pady=5)
            ttk.Label(r, text="Duration (hours):", width=15, anchor=tk.W).pack(side=tk.LEFT)
            fields['duration'] = ttk.Entry(r, width=10)
            fields['duration'].insert(0, str(row[5]) if row[5] else '')
            fields['duration'].pack(side=tk.LEFT)

            # Passing score
            r = ttk.Frame(main_frame)
            r.pack(fill=tk.X, pady=5)
            ttk.Label(r, text="Passing Score %:", width=15, anchor=tk.W).pack(side=tk.LEFT)
            fields['passing_score'] = ttk.Entry(r, width=10)
            fields['passing_score'].insert(0, str(row[6]) if row[6] else '70')
            fields['passing_score'].pack(side=tk.LEFT)

            # Recertification months
            r = ttk.Frame(main_frame)
            r.pack(fill=tk.X, pady=5)
            ttk.Label(r, text="Recert. (months):", width=15, anchor=tk.W).pack(side=tk.LEFT)
            fields['recert'] = ttk.Entry(r, width=10)
            fields['recert'].insert(0, str(row[8]) if row[8] else '')
            fields['recert'].pack(side=tk.LEFT)

            # Mandatory
            fields['mandatory'] = tk.BooleanVar(value=bool(row[7]))
            ttk.Checkbutton(main_frame, text="Mandatory for all staff",
                            variable=fields['mandatory']).pack(anchor=tk.W, pady=5)

            # Active
            fields['active'] = tk.BooleanVar(value=bool(row[9]))
            ttk.Checkbutton(main_frame, text="Active",
                            variable=fields['active']).pack(anchor=tk.W, pady=5)

            # Description
            ttk.Label(main_frame, text="Description:", anchor=tk.W).pack(fill=tk.X, pady=(10, 5))
            desc_text = scrolledtext.ScrolledText(main_frame, height=4, width=40)
            desc_text.insert("1.0", row[2] or '')
            desc_text.pack(fill=tk.X)

            error_label = ttk.Label(main_frame, text="", foreground='red')
            error_label.pack(fill=tk.X, pady=5)

            def save():
                name = fields['name'].get().strip()
                if not name:
                    error_label.config(text="Course name is required")
                    return

                try:
                    duration = float(fields['duration'].get()) if fields['duration'].get().strip() else None
                    passing = float(fields['passing_score'].get()) if fields['passing_score'].get().strip() else 70
                    recert = int(fields['recert'].get()) if fields['recert'].get().strip() else None

                    with transaction() as conn:
                        conn.execute('''
                            UPDATE training_courses
                            SET name = ?, description = ?, category = ?, provider = ?,
                                duration_hours = ?, passing_score = ?, is_mandatory = ?,
                                recertification_months = ?, is_active = ?, updated_at = ?
                            WHERE course_id = ?
                        ''', (name, desc_text.get('1.0', tk.END).strip(),
                              fields['category'].get(), fields['provider'].get().strip(),
                              duration, passing, fields['mandatory'].get(),
                              recert, fields['active'].get(),
                              datetime.now().isoformat(), course_id))

                    log_activity('update', 'training_course', details={
                        'course_id': course_id, 'name': name})
                    messagebox.showinfo("Success", "Course updated successfully")
                    dialog.destroy()
                    self._load_catalog()
                    self._load_manage_courses()

                except ValueError:
                    error_label.config(text="Duration and Passing Score must be numbers")
                except Exception as e:
                    error_label.config(text=f"Error: {e}")

            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(pady=15)
            ttk.Button(btn_frame, text="Save Changes", command=save).pack(side=tk.LEFT, padx=10)
            ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load course: {e}")

    def _delete_course(self):
        """Delete selected course permanently."""
        selection = self.manage_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a course to delete")
            return

        item = self.manage_tree.item(selection[0])
        course_id = item['values'][0]
        course_name = item['values'][1]

        # Check for enrollments first
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT COUNT(*) FROM training_enrollments WHERE course_id = ?',
                    (course_id,))
                enrollment_count = cursor.fetchone()[0]

            if enrollment_count > 0:
                if not messagebox.askyesno("Warning",
                    f"'{course_name}' has {enrollment_count} enrollment(s).\n"
                    "Deleting will also remove all enrollment records.\n\n"
                    "Are you sure you want to proceed?"):
                    return
            else:
                if not messagebox.askyesno("Confirm",
                    f"Permanently delete course '{course_name}'?"):
                    return

            with transaction() as conn:
                conn.execute(
                    'DELETE FROM training_enrollments WHERE course_id = ?',
                    (course_id,))
                conn.execute(
                    'DELETE FROM training_courses WHERE course_id = ?',
                    (course_id,))

            log_activity('delete', 'training_course', details={
                'course_id': course_id, 'name': course_name})
            messagebox.showinfo("Success", f"Course '{course_name}' deleted")
            self._load_catalog()
            self._load_manage_courses()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete course: {e}")

    def _deactivate_course(self):
        """Deactivate selected course."""
        selection = self.manage_tree.selection()
        if not selection:
            messagebox.showwarning(
                _t("staff_hr.training.dialogs.enroll.warning_title", default="Warning"),
                _t("staff_hr.training.dialogs.deactivate_course.warning_select", default="Please select a course to deactivate")
            )
            return

        item = self.manage_tree.item(selection[0])
        course_id = item['values'][0]

        if not messagebox.askyesno(
            _t("staff_hr.training.dialogs.deactivate_course.confirm_title", default="Confirm"),
            _t("staff_hr.training.dialogs.deactivate_course.confirm_message", default="Deactivate this course?")
        ):
            return

        try:
            with transaction() as conn:
                conn.execute('UPDATE training_courses SET is_active = 0 WHERE course_id = ?', (course_id,))

            messagebox.showinfo(
                _t("staff_hr.training.dialogs.enroll.success_title", default="Success"),
                _t("staff_hr.training.dialogs.deactivate_course.success", default="Course deactivated")
            )
            self._load_catalog()
            self._load_manage_courses()

        except Exception as e:
            messagebox.showerror(
                _t("staff_hr.training.errors.error_generic", default="Error"),
                _t("staff_hr.training.errors.deactivate_failed", default="Failed to deactivate: {error}").format(error=str(e))
            )

    def _load_manage_courses(self):
        """Load courses for management tab."""
        try:
            self.manage_tree.delete(*self.manage_tree.get_children())

            show_filter = self.manage_filter.get() if hasattr(self, 'manage_filter') else 'All'

            with get_connection() as conn:
                cursor = conn.cursor()

                query = '''
                    SELECT c.course_id, c.name, c.category, c.provider,
                           c.duration_hours, c.passing_score, c.is_mandatory, c.is_active,
                           (SELECT COUNT(*) FROM training_enrollments WHERE course_id = c.course_id)
                    FROM training_courses c
                '''
                if show_filter == 'Active Only':
                    query += ' WHERE c.is_active = 1'
                elif show_filter == 'Inactive Only':
                    query += ' WHERE c.is_active = 0'

                query += ' ORDER BY c.name'
                cursor.execute(query)

                for row in cursor.fetchall():
                    duration = f"{row[4]:.1f}h" if row[4] else "-"
                    passing = f"{row[5]}%" if row[5] else "-"
                    mandatory = "Yes" if row[6] else "No"
                    active = "Yes" if row[7] else "No"
                    tag = '' if row[7] else 'inactive'

                    values = (row[0], row[1], row[2] or "-", row[3] or "-",
                              duration, passing, mandatory, active, row[8])
                    self.manage_tree.insert('', 'end', values=values, tags=(tag,))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load courses: {e}")

    def _export_certifications(self):
        """Export certifications to CSV."""
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile=f"{_t('staff_hr.training.dialogs.export_certifications.filename_prefix', default='certifications')}_{datetime.now().strftime('%Y%m%d')}.csv"
            )

            if not filename:
                return

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    _t("staff_hr.training.dialogs.export_certifications.csv_headers.id", default="ID"),
                    _t("staff_hr.training.dialogs.export_certifications.csv_headers.name", default="Name"),
                    _t("staff_hr.training.dialogs.export_certifications.csv_headers.issuing_body", default="Issuing Body"),
                    _t("staff_hr.training.dialogs.export_certifications.csv_headers.credential_id", default="Credential ID"),
                    _t("staff_hr.training.dialogs.export_certifications.csv_headers.issue_date", default="Issue Date"),
                    _t("staff_hr.training.dialogs.export_certifications.csv_headers.expiry_date", default="Expiry Date"),
                    _t("staff_hr.training.dialogs.export_certifications.csv_headers.status", default="Status")
                ])

                for item_id in self.certs_tree.get_children():
                    item = self.certs_tree.item(item_id)
                    writer.writerow(item['values'])

            messagebox.showinfo(
                _t("staff_hr.training.dialogs.enroll.success_title", default="Success"),
                _t("staff_hr.training.dialogs.export_certifications.success", default="Exported to {filename}").format(filename=filename)
            )

        except Exception as e:
            messagebox.showerror(
                _t("staff_hr.training.errors.error_generic", default="Error"),
                _t("staff_hr.training.errors.export_failed", default="Failed to export: {error}").format(error=str(e))
            )


def launch_training_gui(root, auth):
    """Launch Training & Certification GUI."""
    try:
        return TrainingGUI(root, auth)
    except Exception as e:
        messagebox.showerror(
            _t("staff_hr.training.errors.error_generic", default="Error"),
            f"Failed to launch Training GUI: {e}"
        )
        return None
