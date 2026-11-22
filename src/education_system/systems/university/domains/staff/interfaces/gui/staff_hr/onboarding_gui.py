"""
Onboarding & Offboarding GUI

Provides interface for:
- Viewing onboarding checklists
- Creating onboarding templates
- Assigning onboarding to new staff
- Tracking task completion
- Offboarding workflows
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Optional

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.onboarding_manager import (
    OnboardingManager,
)
from education_system.systems.university.domains.staff.interfaces.gui.staff_hr import _access as _hr


def _err():
    return _t('gui.staff.staff_hr.onboarding.dialogs.error', default="Error")


class OnboardingGUI:
    """GUI for managing onboarding and offboarding processes."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None
        self.manager = OnboardingManager()

        if not self.current_user:
            messagebox.showerror(_err(), _t('gui.staff.staff_hr.onboarding.dialogs.login_required_to_access_onboarding', default="Login required to access Onboarding"))
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text=_t('gui.staff.staff_hr.onboarding.tabs.onboarding', default="Onboarding"))
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title(_t('gui.staff.staff_hr.onboarding.windows.onboarding_offboarding_system', default="Onboarding & Offboarding System"))
        self.window.geometry("1400x900")
        self.window.minsize(1200, 800)

        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.close', default="Close"), command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_bar = ttk.Label(self.window, text=_t('gui.staff.staff_hr.onboarding.labels.ready', default="Ready"), relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._build_interface(self.window)

    def _build_interface(self, parent):
        """Build the main interface."""
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_my_tasks_tab()
        # Assigning onboarding and running templates is HR's job.
        if _hr.can(self, 'hr'):
            self._create_assignments_tab()
            self._create_templates_tab()
            self._create_progress_tab()

    def _create_my_tasks_tab(self):
        """Create the my tasks tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.onboarding.tabs.my_onboarding_tasks', default="My Onboarding Tasks"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.onboarding.labels.my_onboarding_offboarding_tasks', default="My Onboarding/Offboarding Tasks"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.mark_complete', default="Mark Complete"), command=self._mark_task_complete).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.refresh', default="Refresh"), command=self._load_my_tasks).pack(side=tk.LEFT, padx=5)

        # Filter
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.onboarding.labels.show', default="Show:")).pack(side=tk.LEFT, padx=5)
        self.task_filter = ttk.Combobox(filter_frame, values=['All', 'Pending', 'In Progress', 'Completed'],
                                        width=15, state='readonly')
        self.task_filter.set('Pending')
        self.task_filter.pack(side=tk.LEFT, padx=5)
        self.task_filter.bind('<<ComboboxSelected>>', lambda e: self._load_my_tasks())

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Task', 'Category', 'Due Date', 'Status', 'Assignment')
        self.tasks_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                       yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.tasks_tree.yview)

        col_widths = {'ID': 50, 'Task': 250, 'Category': 100, 'Due Date': 100, 'Status': 100, 'Assignment': 150}
        for col in columns:
            self.tasks_tree.heading(col, text=col)
            self.tasks_tree.column(col, width=col_widths.get(col, 100))

        self.tasks_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status tags
        self.tasks_tree.tag_configure('pending', background='#fff3cd')
        self.tasks_tree.tag_configure('in_progress', background='#cce5ff')
        self.tasks_tree.tag_configure('completed', background='#d4edda')
        self.tasks_tree.tag_configure('overdue', background='#f8d7da')

        # Bind double-click
        self.tasks_tree.bind('<Double-1>', self._view_task_details)

        # Summary
        summary_frame = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.onboarding.labels.progress_summary', default="Progress Summary"), padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)

        self.total_tasks_label = ttk.Label(summary_frame, text=_t('gui.staff.staff_hr.onboarding.labels.total_tasks_0', default="Total Tasks: 0"))
        self.total_tasks_label.pack(side=tk.LEFT, padx=20)

        self.completed_tasks_label = ttk.Label(summary_frame, text=_t('gui.staff.staff_hr.onboarding.labels.completed_0', default="Completed: 0"))
        self.completed_tasks_label.pack(side=tk.LEFT, padx=20)

        self.pending_tasks_label = ttk.Label(summary_frame, text=_t('gui.staff.staff_hr.onboarding.labels.pending_0', default="Pending: 0"))
        self.pending_tasks_label.pack(side=tk.LEFT, padx=20)

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        ttk.Label(summary_frame, text=_t('gui.staff.staff_hr.onboarding.labels.progress', default="Progress:")).pack(side=tk.LEFT, padx=20)
        ttk.Progressbar(summary_frame, variable=self.progress_var, length=200, mode='determinate').pack(side=tk.LEFT)

        self._load_my_tasks()

    def _create_assignments_tab(self):
        """Create the assignments tab (admin/staff only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.onboarding.tabs.manage_assignments', default="Manage Assignments"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.onboarding.labels.onboarding_assignments', default="Onboarding Assignments"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.new_assignment', default="New Assignment"), command=self._create_assignment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.refresh', default="Refresh"), command=self._load_assignments).pack(side=tk.LEFT, padx=5)

        # Filter
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.onboarding.labels.type', default="Type:")).pack(side=tk.LEFT, padx=5)
        self.assign_type_filter = ttk.Combobox(filter_frame, values=['All', 'Onboarding', 'Offboarding'],
                                               width=12, state='readonly')
        self.assign_type_filter.set('All')
        self.assign_type_filter.pack(side=tk.LEFT, padx=5)
        self.assign_type_filter.bind('<<ComboboxSelected>>', lambda e: self._load_assignments())

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.onboarding.labels.status', default="Status:")).pack(side=tk.LEFT, padx=15)
        self.assign_status_filter = ttk.Combobox(filter_frame,
                                                 values=['All', 'In Progress', 'Completed', 'Cancelled'],
                                                 width=12, state='readonly')
        self.assign_status_filter.set('In Progress')
        self.assign_status_filter.pack(side=tk.LEFT, padx=5)
        self.assign_status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_assignments())

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Employee', 'Template', 'Type', 'Start Date', 'Target Date', 'Progress', 'Status')
        self.assignments_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                             yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.assignments_tree.yview)

        for col in columns:
            self.assignments_tree.heading(col, text=col)
            self.assignments_tree.column(col, width=100, anchor=tk.CENTER)

        self.assignments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click
        self.assignments_tree.bind('<Double-1>', self._view_assignment_details)

        self._load_assignments()

    def _create_templates_tab(self):
        """Create the templates tab (admin only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.onboarding.tabs.templates', default="Templates"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.onboarding.labels.onboarding_offboarding_templates', default="Onboarding/Offboarding Templates"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.create_template', default="Create Template"), command=self._create_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.edit_template', default="Edit Template"), command=self._edit_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.manage_tasks', default="Manage Tasks"), command=self._manage_template_tasks).pack(side=tk.LEFT, padx=5)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Name', 'Type', 'Role', 'Department', 'Est. Days', 'Tasks', 'Active')
        self.templates_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                           yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.templates_tree.yview)

        for col in columns:
            self.templates_tree.heading(col, text=col)
            self.templates_tree.column(col, width=100, anchor=tk.CENTER)

        self.templates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_templates()

    def _create_progress_tab(self):
        """Create the progress overview tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.onboarding.tabs.progress_overview', default="Progress Overview"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.onboarding.labels.onboarding_progress_overview', default="Onboarding Progress Overview"), style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.refresh', default="Refresh"), command=self._load_progress_overview).pack(side=tk.RIGHT, padx=5)

        # Stats frame
        stats_frame = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.onboarding.labels.statistics', default="Statistics"), padding=15)
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        self.active_onboarding_label = ttk.Label(stats_frame, text=_t('gui.staff.staff_hr.onboarding.labels.active_onboarding_0', default="Active Onboarding: 0"), font=('Arial', 11))
        self.active_onboarding_label.pack(side=tk.LEFT, padx=30)

        self.active_offboarding_label = ttk.Label(stats_frame, text=_t('gui.staff.staff_hr.onboarding.labels.active_offboarding_0', default="Active Offboarding: 0"), font=('Arial', 11))
        self.active_offboarding_label.pack(side=tk.LEFT, padx=30)

        self.completed_this_month_label = ttk.Label(stats_frame, text=_t('gui.staff.staff_hr.onboarding.labels.completed_this_month_0', default="Completed This Month: 0"), font=('Arial', 11))
        self.completed_this_month_label.pack(side=tk.LEFT, padx=30)

        self.avg_completion_label = ttk.Label(stats_frame, text=_t('gui.staff.staff_hr.onboarding.labels.avg_completion_0_days', default="Avg. Completion: 0 days"), font=('Arial', 11))
        self.avg_completion_label.pack(side=tk.LEFT, padx=30)

        # Recent completions
        ttk.Label(tab, text=_t('gui.staff.staff_hr.onboarding.labels.recent_completions', default="Recent Completions:"), style='Header.TLabel').pack(anchor=tk.W, padx=10, pady=(20, 5))

        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Employee', 'Template', 'Type', 'Completed Date', 'Duration')
        self.recent_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10)

        for col in columns:
            self.recent_tree.heading(col, text=col)
            self.recent_tree.column(col, width=150, anchor=tk.CENTER)

        self.recent_tree.pack(fill=tk.BOTH, expand=True)

        self._load_progress_overview()

    def _load_my_tasks(self):
        """Load user's onboarding tasks (their own, and those they own for others)."""
        try:
            self.tasks_tree.delete(*self.tasks_tree.get_children())

            status_filter = self.task_filter.get()
            today = datetime.now().strftime("%Y-%m-%d")
            status = None if status_filter == 'All' else status_filter.lower().replace(' ', '_')

            total = completed = pending = 0
            for row in self.manager.get_my_tasks(_hr.actor(self), status=status):
                total += 1
                status = row['status']
                if status == 'completed':
                    completed += 1
                else:
                    pending += 1

                # Check if overdue
                tag = status
                if row['due_date'] and row['due_date'] < today and status != 'completed':
                    tag = 'overdue'

                assignment = row['template_name']
                if row['staff_user'] != _hr.user_key(self):
                    assignment = f"{assignment} ({row['staff_user']})"
                values = (row['progress_id'], row['title'], row['category'] or '-',
                          row['due_date'] or '-', status.replace('_', ' ').capitalize(), assignment)
                self.tasks_tree.insert('', 'end', values=values, tags=(tag,))

            self.total_tasks_label.config(text=f"Total Tasks: {total}")
            self.completed_tasks_label.config(text=f"Completed: {completed}")
            self.pending_tasks_label.config(text=f"Pending: {pending}")

            progress = (completed / total * 100) if total > 0 else 0
            self.progress_var.set(progress)

        except Exception as e:
            messagebox.showerror(_err(), f"Failed to load tasks: {e}")

    def _load_assignments(self):
        """Load onboarding assignments."""
        try:
            self.assignments_tree.delete(*self.assignments_tree.get_children())

            type_filter = self.assign_type_filter.get()
            status_filter = self.assign_status_filter.get()
            rows = self.manager.list_assignments(
                _hr.actor(self),
                template_type=None if type_filter == 'All' else type_filter.lower(),
                status=None if status_filter == 'All' else status_filter.lower().replace(' ', '_'))

            for row in rows:
                total = row['total_tasks'] or 0
                done = row['done_tasks'] or 0
                progress = f"{done}/{total}" if total > 0 else "0/0"

                values = (row['assignment_id'], row['user_id'], row['template_name'],
                          (row['template_type'] or '').capitalize(),
                          row['start_date'], row['target_completion_date'] or '-', progress,
                          (row['status'] or '').replace('_', ' ').capitalize())
                self.assignments_tree.insert('', 'end', values=values)

        except Exception as e:
            messagebox.showerror(_err(), f"Failed to load assignments: {e}")

    def _load_templates(self):
        """Load onboarding templates."""
        try:
            self.templates_tree.delete(*self.templates_tree.get_children())

            for row in self.manager.list_templates(_hr.actor(self)):
                values = (row['template_id'], row['name'], (row['template_type'] or '').capitalize(),
                          row['role'] or '-', row['department'] or '-',
                          row['estimated_days'] or '-', row['task_count'],
                          'Yes' if row['is_active'] else 'No')
                self.templates_tree.insert('', 'end', values=values)

        except Exception as e:
            messagebox.showerror(_err(), f"Failed to load templates: {e}")

    def _load_progress_overview(self):
        """Load progress overview statistics."""
        try:
            stats = self.manager.progress_overview(_hr.actor(self))

            self.recent_tree.delete(*self.recent_tree.get_children())
            for row in stats['recent']:
                duration = f"{int(row['days'])} days" if row['days'] else '-'
                values = (row['user_id'], row['template_name'],
                          (row['template_type'] or '').capitalize(),
                          row['actual_completion_date'], duration)
                self.recent_tree.insert('', 'end', values=values)

            self.active_onboarding_label.config(text=f"Active Onboarding: {stats['active_onboarding']}")
            self.active_offboarding_label.config(text=f"Active Offboarding: {stats['active_offboarding']}")
            self.completed_this_month_label.config(text=f"Completed This Month: {stats['completed_this_month']}")
            self.avg_completion_label.config(text=f"Avg. Completion: {stats['average_days']:.1f} days")

        except Exception as e:
            messagebox.showerror(_err(), f"Failed to load overview: {e}")

    def _mark_task_complete(self):
        """Mark selected task as complete."""
        selection = self.tasks_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.staff.staff_hr.onboarding.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.onboarding.dialogs.please_select_a_task_to_mark_complete', default="Please select a task to mark complete"))
            return

        item = self.tasks_tree.item(selection[0])
        progress_id = item['values'][0]
        status = item['values'][4].lower()

        if status == 'completed':
            messagebox.showwarning(_t('gui.staff.staff_hr.onboarding.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.onboarding.dialogs.task_is_already_completed', default="Task is already completed"))
            return

        if not messagebox.askyesno(_t('gui.staff.staff_hr.onboarding.dialogs.confirm', default="Confirm"), _t('gui.staff.staff_hr.onboarding.dialogs.mark_this_task_as_complete', default="Mark this task as complete?")):
            return

        try:
            result = self.manager.complete_task_for(_hr.actor(self), progress_id)
            if result is None:
                messagebox.showerror(_err(), "Task not found")
                return
            if result['contract_missing']:
                # A new starter isn't active until their contract is on file (#9).
                messagebox.showwarning(
                    _t('gui.staff.staff_hr.onboarding.dialogs.contract_not_on_file', default="Contract not on file"),
                    "All onboarding tasks complete, but no signed "
                    "contract is linked in Document Manager for "
                    "this staff member. The assignment will stay "
                    "in progress until the contract is uploaded.",
                )
            messagebox.showinfo(_t('gui.staff.staff_hr.onboarding.dialogs.success', default="Success"), _t('gui.staff.staff_hr.onboarding.dialogs.task_marked_as_complete', default="Task marked as complete"))
            self._load_my_tasks()

        except Exception as e:
            messagebox.showerror(_err(), f"Failed to update task: {e}")

    def _view_task_details(self, event=None):
        """View task details."""
        selection = self.tasks_tree.selection()
        if not selection:
            return

        item = self.tasks_tree.item(selection[0])
        progress_id = item['values'][0]

        try:
            row = self.manager.get_task(progress_id, actor=_hr.actor(self))

            if row:
                details = f"""
Task: {row['title']}
For: {row['staff_user']}
Description: {row['description'] or 'No description'}
Category: {row['category'] or 'General'}
Owner: {row['assigned_to'] or (row['assigned_to_role'] or 'employee').capitalize()}
Due Date: {row['due_date'] or 'Not set'}
Status: {row['status'].replace('_', ' ').capitalize()}
Notes: {row['notes'] or 'None'}
Completed By: {row['completed_by'] or 'N/A'}
Completed Date: {row['completed_date'] or 'N/A'}
                """
                messagebox.showinfo(_t('gui.staff.staff_hr.onboarding.dialogs.task_details', default="Task Details"), details.strip())

        except Exception as e:
            messagebox.showerror(_err(), f"Failed to load details: {e}")

    def _create_assignment(self):
        """Create a new onboarding assignment."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.onboarding.windows.new_onboarding_assignment', default="New Onboarding Assignment"))
        dialog.geometry("450x350")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.onboarding.labels.create_onboarding_assignment', default="Create Onboarding Assignment"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Employee
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.employee_id', default="Employee ID:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        user_var = tk.StringVar()
        ttk.Entry(row, textvariable=user_var, width=25).pack(side=tk.LEFT)

        # Template
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.template', default="Template:"), width=15, anchor=tk.W).pack(side=tk.LEFT)

        templates = self._get_active_templates()
        template_var = tk.StringVar()
        ttk.Combobox(row, textvariable=template_var, values=list(templates.keys()),
                     width=25, state='readonly').pack(side=tk.LEFT)

        # Start date
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.start_date', default="Start Date:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        start_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(row, textvariable=start_var, width=15).pack(side=tk.LEFT)

        # Target date
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.target_completion', default="Target Completion:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        target_var = tk.StringVar(value=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"))
        ttk.Entry(row, textvariable=target_var, width=15).pack(side=tk.LEFT)

        # Notes
        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.onboarding.labels.notes', default="Notes:"), anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        notes_text = scrolledtext.ScrolledText(main_frame, height=4, width=40)
        notes_text.pack(fill=tk.X)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save():
            if not user_var.get().strip():
                error_label.config(text=_t('gui.staff.staff_hr.onboarding.text.employee_id_is_required', default="Employee ID is required"))
                return
            if not template_var.get():
                error_label.config(text=_t('gui.staff.staff_hr.onboarding.text.please_select_a_template', default="Please select a template"))
                return

            template_id = templates[template_var.get()]

            try:
                datetime.strptime(start_var.get().strip(), "%Y-%m-%d")
                if target_var.get().strip():
                    datetime.strptime(target_var.get().strip(), "%Y-%m-%d")
            except ValueError:
                error_label.config(text="Dates must be YYYY-MM-DD")
                return

            try:
                self.manager.assign_template(
                    user_var.get().strip(), template_id, None,
                    start_date=start_var.get().strip(),
                    target_date=target_var.get().strip() or None,
                    notes=notes_text.get('1.0', tk.END).strip() or None,
                    actor=_hr.actor(self))

                log_activity('create', 'onboarding_assignment',
                             details={'user_id': user_var.get(), 'template': template_var.get()})
                messagebox.showinfo(_t('gui.staff.staff_hr.onboarding.dialogs.success', default="Success"), _t('gui.staff.staff_hr.onboarding.dialogs.onboarding_assignment_created', default="Onboarding assignment created"))
                dialog.destroy()
                self._load_assignments()

            except Exception as e:
                error_label.config(text=f"Error: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.create_assignment', default="Create Assignment"), command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _create_template(self):
        """Create a new onboarding template."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.onboarding.windows.create_template', default="Create Template"))
        dialog.geometry("450x400")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.onboarding.labels.create_onboarding_template', default="Create Onboarding Template"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Name
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.template_name', default="Template Name:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        name_var = tk.StringVar()
        ttk.Entry(row, textvariable=name_var, width=25).pack(side=tk.LEFT)

        # Type
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.type', default="Type:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        type_var = tk.StringVar(value=_t('gui.staff.staff_hr.onboarding.values.onboarding', default='Onboarding'))
        ttk.Combobox(row, textvariable=type_var, values=['Onboarding', 'Offboarding'],
                     width=15, state='readonly').pack(side=tk.LEFT)

        # Role
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.for_role', default="For Role:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        role_var = tk.StringVar()
        ttk.Entry(row, textvariable=role_var, width=20).pack(side=tk.LEFT)

        # Department
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.department', default="Department:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        dept_var = tk.StringVar()
        ttk.Entry(row, textvariable=dept_var, width=20).pack(side=tk.LEFT)

        # Estimated days
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.est_days', default="Est. Days:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        days_var = tk.StringVar(value="30")
        ttk.Entry(row, textvariable=days_var, width=10).pack(side=tk.LEFT)

        # Description
        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.onboarding.labels.description', default="Description:"), anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        desc_text = scrolledtext.ScrolledText(main_frame, height=4, width=40)
        desc_text.pack(fill=tk.X)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save():
            if not name_var.get().strip():
                error_label.config(text=_t('gui.staff.staff_hr.onboarding.text.template_name_is_required', default="Template name is required"))
                return

            try:
                days = int(days_var.get() or 30)
            except ValueError:
                error_label.config(text="Est. Days must be a whole number")
                return

            try:
                self.manager.create_template(
                    name_var.get().strip(), actor=_hr.actor(self),
                    description=desc_text.get('1.0', tk.END).strip(),
                    template_type=type_var.get().lower(),
                    role=role_var.get().strip() or None,
                    department=dept_var.get().strip() or None,
                    estimated_days=days)

                log_activity('create', 'onboarding_template', details={'name': name_var.get()})
                messagebox.showinfo(_t('gui.staff.staff_hr.onboarding.dialogs.success', default="Success"), _t('gui.staff.staff_hr.onboarding.dialogs.template_created_now_add_tasks_using_manage_tasks', default="Template created. Now add tasks using 'Manage Tasks'."))
                dialog.destroy()
                self._load_templates()

            except Exception as e:
                error_label.config(text=f"Error: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.create_template', default="Create Template"), command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _edit_template(self):
        """Edit selected template."""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.staff.staff_hr.onboarding.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.onboarding.dialogs.please_select_a_template_to_edit', default="Please select a template to edit"))
            return

        template_id = self.templates_tree.item(selection[0])['values'][0]
        template = self.manager.get_template(template_id)
        if not template:
            messagebox.showerror(_err(), "Template not found")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.onboarding.dialogs.edit', default="Edit") + f" - {template['name']}")
        dialog.geometry("450x420")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        def field(label, value, width=25):
            row = ttk.Frame(main_frame)
            row.pack(fill=tk.X, pady=5)
            ttk.Label(row, text=label, width=15, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.StringVar(value='' if value is None else str(value))
            ttk.Entry(row, textvariable=var, width=width).pack(side=tk.LEFT)
            return var

        name_var = field(_t('gui.staff.staff_hr.onboarding.labels.template_name', default="Template Name:"), template['name'])
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.type', default="Type:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        type_var = tk.StringVar(value=(template['template_type'] or 'onboarding').capitalize())
        ttk.Combobox(row, textvariable=type_var, values=['Onboarding', 'Offboarding'],
                     width=15, state='readonly').pack(side=tk.LEFT)
        role_var = field(_t('gui.staff.staff_hr.onboarding.labels.for_role', default="For Role:"), template['role'], 20)
        dept_var = field(_t('gui.staff.staff_hr.onboarding.labels.department', default="Department:"), template['department'], 20)
        days_var = field(_t('gui.staff.staff_hr.onboarding.labels.est_days', default="Est. Days:"), template['estimated_days'], 10)
        active_var = tk.BooleanVar(value=bool(template['is_active']))
        ttk.Checkbutton(main_frame, text="Active (can be assigned)", variable=active_var).pack(anchor=tk.W, pady=5)

        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.onboarding.labels.description', default="Description:"), anchor=tk.W).pack(fill=tk.X, pady=(10, 5))
        desc_text = scrolledtext.ScrolledText(main_frame, height=4, width=40)
        desc_text.insert('1.0', template['description'] or '')
        desc_text.pack(fill=tk.X)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save():
            try:
                days = int(days_var.get() or 30)
            except ValueError:
                error_label.config(text="Est. Days must be a whole number")
                return
            try:
                self.manager.update_template(
                    template_id, actor=_hr.actor(self),
                    name=name_var.get().strip(), template_type=type_var.get().lower(),
                    role=role_var.get().strip() or None,
                    department=dept_var.get().strip() or None,
                    estimated_days=days, is_active=1 if active_var.get() else 0,
                    description=desc_text.get('1.0', tk.END).strip())
            except Exception as e:
                error_label.config(text=f"Error: {e}")
                return
            log_activity('update', 'onboarding_template', details={'template_id': template_id})
            dialog.destroy()
            self._load_templates()

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _manage_template_tasks(self):
        """Manage tasks for selected template."""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.staff.staff_hr.onboarding.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.onboarding.dialogs.please_select_a_template_to_manage_tasks', default="Please select a template to manage tasks"))
            return

        item = self.templates_tree.item(selection[0])
        template_id = item['values'][0]
        template_name = item['values'][1]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Manage Tasks - {template_name}")
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header = ttk.Frame(main_frame)
        header.pack(fill=tk.X, pady=10)
        ttk.Label(header, text=f"Tasks for: {template_name}", font=('Arial', 12, 'bold')).pack(side=tk.LEFT)
        ttk.Button(header, text=_t('gui.staff.staff_hr.onboarding.buttons.add_task', default="Add Task"), command=lambda: self._add_template_task(template_id, tasks_tree)).pack(side=tk.RIGHT)

        # Tasks treeview
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Title', 'Category', 'Assigned To', 'Due Days', 'Required', 'Order')
        tasks_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)

        y_scroll.config(command=tasks_tree.yview)

        for col in columns:
            tasks_tree.heading(col, text=col)
            tasks_tree.column(col, width=100, anchor=tk.CENTER)

        tasks_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Load tasks
        def load_tasks():
            tasks_tree.delete(*tasks_tree.get_children())
            try:
                self._fill_template_tasks(tasks_tree, template_id)
            except Exception as e:
                messagebox.showerror(_err(), f"Failed to load tasks: {e}")

        load_tasks()

        # Delete button
        ttk.Button(main_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.delete_selected_task', default="Delete Selected Task"),
                   command=lambda: self._delete_template_task(tasks_tree, load_tasks)).pack(pady=10)

        ttk.Button(main_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.close', default="Close"), command=dialog.destroy).pack(pady=10)

    def _add_template_task(self, template_id, tasks_tree):
        """Add a task to template."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.onboarding.windows.add_task', default="Add Task"))
        dialog.geometry("400x350")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.task_title', default="Task Title:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        title_var = tk.StringVar()
        ttk.Entry(row, textvariable=title_var, width=25).pack(side=tk.LEFT)

        # Category
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.category', default="Category:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        category_var = tk.StringVar(value=_t('gui.staff.staff_hr.onboarding.values.general', default='General'))
        ttk.Combobox(row, textvariable=category_var,
                     values=['General', 'HR', 'IT', 'Training', 'Admin', 'Other'],
                     width=15, state='readonly').pack(side=tk.LEFT)

        # Assigned to role
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.assigned_to', default="Assigned To:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        assigned_var = tk.StringVar(value=_t('gui.staff.staff_hr.onboarding.values.employee', default='Employee'))
        ttk.Combobox(row, textvariable=assigned_var,
                     values=['Employee', 'HR', 'Manager', 'IT', 'Admin'],
                     width=15, state='readonly').pack(side=tk.LEFT)

        # Due days
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.due_days', default="Due Days:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        days_var = tk.StringVar(value="7")
        ttk.Entry(row, textvariable=days_var, width=10).pack(side=tk.LEFT)
        ttk.Label(row, text=_t('gui.staff.staff_hr.onboarding.labels.days_from_start', default="(days from start)"), font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # Required
        required_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.required_task', default="Required task"), variable=required_var).pack(anchor=tk.W, pady=10)

        # Description
        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.onboarding.labels.description', default="Description:"), anchor=tk.W).pack(fill=tk.X, pady=(10, 5))
        desc_text = scrolledtext.ScrolledText(main_frame, height=4, width=35)
        desc_text.pack(fill=tk.X)

        def save():
            if not title_var.get().strip():
                messagebox.showwarning(_t('gui.staff.staff_hr.onboarding.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.onboarding.dialogs.task_title_is_required', default="Task title is required"))
                return

            try:
                days = int(days_var.get() or 0)
            except ValueError:
                messagebox.showwarning(_t('gui.staff.staff_hr.onboarding.dialogs.warning', default="Warning"), "Due Days must be a whole number")
                return

            try:
                self.manager.add_template_task(
                    template_id, title_var.get().strip(), actor=_hr.actor(self),
                    description=desc_text.get('1.0', tk.END).strip(),
                    category=category_var.get(), assigned_to_role=assigned_var.get().lower(),
                    due_days=days, is_required=1 if required_var.get() else 0)

                messagebox.showinfo(_t('gui.staff.staff_hr.onboarding.dialogs.success', default="Success"), _t('gui.staff.staff_hr.onboarding.dialogs.task_added', default="Task added"))
                dialog.destroy()
                self._fill_template_tasks(tasks_tree, template_id)

            except Exception as e:
                messagebox.showerror(_err(), f"Failed to add task: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.add_task', default="Add Task"), command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.onboarding.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _delete_template_task(self, tasks_tree, reload_func):
        """Delete selected template task."""
        selection = tasks_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.staff.staff_hr.onboarding.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.onboarding.dialogs.please_select_a_task_to_delete', default="Please select a task to delete"))
            return

        if not messagebox.askyesno(_t('gui.staff.staff_hr.onboarding.dialogs.confirm', default="Confirm"), _t('gui.staff.staff_hr.onboarding.dialogs.delete_this_task', default="Delete this task?")):
            return

        item = tasks_tree.item(selection[0])
        task_id = item['values'][0]

        try:
            self.manager.delete_template_task(task_id, actor=_hr.actor(self))

            messagebox.showinfo(_t('gui.staff.staff_hr.onboarding.dialogs.success', default="Success"), _t('gui.staff.staff_hr.onboarding.dialogs.task_deleted', default="Task deleted"))
            reload_func()

        except Exception as e:
            messagebox.showerror(_err(), f"Failed to delete task: {e}")

    def _view_assignment_details(self, event=None):
        """View assignment details."""
        selection = self.assignments_tree.selection()
        if not selection:
            return

        item = self.assignments_tree.item(selection[0])
        values = item['values']

        details = f"""
Assignment ID: {values[0]}
Employee: {values[1]}
Template: {values[2]}
Type: {values[3]}
Start Date: {values[4]}
Target Completion: {values[5]}
Progress: {values[6]}
Status: {values[7]}
        """
        messagebox.showinfo(_t('gui.staff.staff_hr.onboarding.dialogs.assignment_details', default="Assignment Details"), details.strip())

    def _fill_template_tasks(self, tasks_tree, template_id):
        """(Re)fill a template's task list."""
        tasks_tree.delete(*tasks_tree.get_children())
        for row in self.manager.get_template_tasks(template_id):
            values = (row['task_id'], row['title'], row['category'] or '-',
                      row['assigned_to_role'] or '-', row['due_days'] or '-',
                      'Yes' if row['is_required'] else 'No', row['order_num'])
            tasks_tree.insert('', 'end', values=values)

    def _get_active_templates(self) -> dict:
        """Get active templates as {name: id} dict."""
        templates = {}
        try:
            for row in self.manager.get_templates():
                templates[row['name']] = row['template_id']
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        return templates


def launch_onboarding_gui(root, auth):
    """Launch Onboarding GUI."""
    try:
        return OnboardingGUI(root, auth)
    except Exception as e:
        messagebox.showerror(_err(), f"Failed to launch Onboarding GUI: {e}")
        return None
