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

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.activity_logger import log_activity


class OnboardingGUI:
    """GUI for managing onboarding and offboarding processes."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Onboarding")
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Onboarding")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Onboarding & Offboarding System")
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)

        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._build_interface(self.window)

    def _build_interface(self, parent):
        """Build the main interface."""
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_my_tasks_tab()
        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_assignments_tab()
            self._create_templates_tab()
            self._create_progress_tab()

    def _create_my_tasks_tab(self):
        """Create the my tasks tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Onboarding Tasks")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="My Onboarding/Offboarding Tasks", style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Mark Complete", command=self._mark_task_complete).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_my_tasks).pack(side=tk.LEFT, padx=5)

        # Filter
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="Show:").pack(side=tk.LEFT, padx=5)
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
        summary_frame = ttk.LabelFrame(tab, text="Progress Summary", padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)

        self.total_tasks_label = ttk.Label(summary_frame, text="Total Tasks: 0")
        self.total_tasks_label.pack(side=tk.LEFT, padx=20)

        self.completed_tasks_label = ttk.Label(summary_frame, text="Completed: 0")
        self.completed_tasks_label.pack(side=tk.LEFT, padx=20)

        self.pending_tasks_label = ttk.Label(summary_frame, text="Pending: 0")
        self.pending_tasks_label.pack(side=tk.LEFT, padx=20)

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        ttk.Label(summary_frame, text="Progress:").pack(side=tk.LEFT, padx=20)
        ttk.Progressbar(summary_frame, variable=self.progress_var, length=200, mode='determinate').pack(side=tk.LEFT)

        self._load_my_tasks()

    def _create_assignments_tab(self):
        """Create the assignments tab (admin/staff only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Manage Assignments")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Onboarding Assignments", style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="New Assignment", command=self._create_assignment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_assignments).pack(side=tk.LEFT, padx=5)

        # Filter
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="Type:").pack(side=tk.LEFT, padx=5)
        self.assign_type_filter = ttk.Combobox(filter_frame, values=['All', 'Onboarding', 'Offboarding'],
                                               width=12, state='readonly')
        self.assign_type_filter.set('All')
        self.assign_type_filter.pack(side=tk.LEFT, padx=5)
        self.assign_type_filter.bind('<<ComboboxSelected>>', lambda e: self._load_assignments())

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=15)
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
        self.notebook.add(tab, text="Templates")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Onboarding/Offboarding Templates", style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Create Template", command=self._create_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit Template", command=self._edit_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Manage Tasks", command=self._manage_template_tasks).pack(side=tk.LEFT, padx=5)

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
        self.notebook.add(tab, text="Progress Overview")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Onboarding Progress Overview", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_progress_overview).pack(side=tk.RIGHT, padx=5)

        # Stats frame
        stats_frame = ttk.LabelFrame(tab, text="Statistics", padding=15)
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        self.active_onboarding_label = ttk.Label(stats_frame, text="Active Onboarding: 0", font=('Arial', 11))
        self.active_onboarding_label.pack(side=tk.LEFT, padx=30)

        self.active_offboarding_label = ttk.Label(stats_frame, text="Active Offboarding: 0", font=('Arial', 11))
        self.active_offboarding_label.pack(side=tk.LEFT, padx=30)

        self.completed_this_month_label = ttk.Label(stats_frame, text="Completed This Month: 0", font=('Arial', 11))
        self.completed_this_month_label.pack(side=tk.LEFT, padx=30)

        self.avg_completion_label = ttk.Label(stats_frame, text="Avg. Completion: 0 days", font=('Arial', 11))
        self.avg_completion_label.pack(side=tk.LEFT, padx=30)

        # Recent completions
        ttk.Label(tab, text="Recent Completions:", style='Header.TLabel').pack(anchor=tk.W, padx=10, pady=(20, 5))

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
        """Load user's onboarding tasks."""
        try:
            self.tasks_tree.delete(*self.tasks_tree.get_children())

            user_id = self.current_user.get('id') or self.current_user.get('username')
            status_filter = self.task_filter.get()
            today = datetime.now().strftime("%Y-%m-%d")

            with get_connection() as conn:
                cursor = conn.cursor()

                # Get tasks assigned to user (either as employee or assigned_to)
                query = '''
                    SELECT p.progress_id, t.title, t.category, p.due_date, p.status,
                           te.name as template_name
                    FROM onboarding_task_progress p
                    JOIN onboarding_template_tasks t ON p.task_id = t.task_id
                    JOIN onboarding_assignments a ON p.assignment_id = a.assignment_id
                    JOIN onboarding_templates te ON a.template_id = te.template_id
                    WHERE (a.user_id = ? OR p.assigned_to = ?)
                '''
                params = [user_id, user_id]

                if status_filter != 'All':
                    query += ' AND p.status = ?'
                    params.append(status_filter.lower().replace(' ', '_'))

                query += ' ORDER BY p.due_date ASC'

                cursor.execute(query, params)

                total = 0
                completed = 0
                pending = 0

                for row in cursor.fetchall():
                    total += 1
                    status = row[4]

                    if status == 'completed':
                        completed += 1
                    else:
                        pending += 1

                    # Check if overdue
                    tag = status
                    if row[3] and row[3] < today and status != 'completed':
                        tag = 'overdue'

                    values = (row[0], row[1], row[2] or '-', row[3] or '-',
                              status.replace('_', ' ').capitalize(), row[5])
                    self.tasks_tree.insert('', 'end', values=values, tags=(tag,))

            self.total_tasks_label.config(text=f"Total Tasks: {total}")
            self.completed_tasks_label.config(text=f"Completed: {completed}")
            self.pending_tasks_label.config(text=f"Pending: {pending}")

            progress = (completed / total * 100) if total > 0 else 0
            self.progress_var.set(progress)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tasks: {e}")

    def _load_assignments(self):
        """Load onboarding assignments."""
        try:
            self.assignments_tree.delete(*self.assignments_tree.get_children())

            type_filter = self.assign_type_filter.get()
            status_filter = self.assign_status_filter.get()

            with get_connection() as conn:
                cursor = conn.cursor()

                query = '''
                    SELECT a.assignment_id, a.user_id, t.name, t.template_type,
                           a.start_date, a.target_completion_date, a.status,
                           (SELECT COUNT(*) FROM onboarding_task_progress WHERE assignment_id = a.assignment_id) as total,
                           (SELECT COUNT(*) FROM onboarding_task_progress WHERE assignment_id = a.assignment_id AND status = 'completed') as done
                    FROM onboarding_assignments a
                    JOIN onboarding_templates t ON a.template_id = t.template_id
                    WHERE 1=1
                '''
                params = []

                if type_filter != 'All':
                    query += ' AND t.template_type = ?'
                    params.append(type_filter.lower())

                if status_filter != 'All':
                    query += ' AND a.status = ?'
                    params.append(status_filter.lower().replace(' ', '_'))

                query += ' ORDER BY a.start_date DESC'

                cursor.execute(query, params)

                for row in cursor.fetchall():
                    total = row[7] or 0
                    done = row[8] or 0
                    progress = f"{done}/{total}" if total > 0 else "0/0"

                    values = (row[0], row[1], row[2], row[3].capitalize(),
                              row[4], row[5] or '-', progress,
                              row[6].replace('_', ' ').capitalize())
                    self.assignments_tree.insert('', 'end', values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assignments: {e}")

    def _load_templates(self):
        """Load onboarding templates."""
        try:
            self.templates_tree.delete(*self.templates_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT t.template_id, t.name, t.template_type, t.role, t.department,
                           t.estimated_days, t.is_active,
                           (SELECT COUNT(*) FROM onboarding_template_tasks WHERE template_id = t.template_id)
                    FROM onboarding_templates t
                    ORDER BY t.name
                ''')

                for row in cursor.fetchall():
                    values = (row[0], row[1], row[2].capitalize(), row[3] or '-',
                              row[4] or '-', row[5] or '-', row[7],
                              'Yes' if row[6] else 'No')
                    self.templates_tree.insert('', 'end', values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {e}")

    def _load_progress_overview(self):
        """Load progress overview statistics."""
        try:
            today = datetime.now()
            month_start = today.replace(day=1).strftime("%Y-%m-%d")

            with get_connection() as conn:
                cursor = conn.cursor()

                # Active onboarding
                cursor.execute('''
                    SELECT COUNT(*) FROM onboarding_assignments a
                    JOIN onboarding_templates t ON a.template_id = t.template_id
                    WHERE a.status = 'in_progress' AND t.template_type = 'onboarding'
                ''')
                active_onboarding = cursor.fetchone()[0]

                # Active offboarding
                cursor.execute('''
                    SELECT COUNT(*) FROM onboarding_assignments a
                    JOIN onboarding_templates t ON a.template_id = t.template_id
                    WHERE a.status = 'in_progress' AND t.template_type = 'offboarding'
                ''')
                active_offboarding = cursor.fetchone()[0]

                # Completed this month
                cursor.execute('''
                    SELECT COUNT(*) FROM onboarding_assignments
                    WHERE status = 'completed' AND actual_completion_date >= ?
                ''', (month_start,))
                completed_month = cursor.fetchone()[0]

                # Average completion time
                cursor.execute('''
                    SELECT AVG(julianday(actual_completion_date) - julianday(start_date))
                    FROM onboarding_assignments
                    WHERE status = 'completed' AND actual_completion_date IS NOT NULL
                ''')
                avg_days = cursor.fetchone()[0] or 0

                # Recent completions
                self.recent_tree.delete(*self.recent_tree.get_children())
                cursor.execute('''
                    SELECT a.user_id, t.name, t.template_type, a.actual_completion_date,
                           julianday(a.actual_completion_date) - julianday(a.start_date)
                    FROM onboarding_assignments a
                    JOIN onboarding_templates t ON a.template_id = t.template_id
                    WHERE a.status = 'completed'
                    ORDER BY a.actual_completion_date DESC
                    LIMIT 10
                ''')

                for row in cursor.fetchall():
                    duration = f"{int(row[4])} days" if row[4] else '-'
                    values = (row[0], row[1], row[2].capitalize(), row[3], duration)
                    self.recent_tree.insert('', 'end', values=values)

            self.active_onboarding_label.config(text=f"Active Onboarding: {active_onboarding}")
            self.active_offboarding_label.config(text=f"Active Offboarding: {active_offboarding}")
            self.completed_this_month_label.config(text=f"Completed This Month: {completed_month}")
            self.avg_completion_label.config(text=f"Avg. Completion: {avg_days:.1f} days")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load overview: {e}")

    def _mark_task_complete(self):
        """Mark selected task as complete."""
        selection = self.tasks_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a task to mark complete")
            return

        item = self.tasks_tree.item(selection[0])
        progress_id = item['values'][0]
        status = item['values'][4].lower()

        if status == 'completed':
            messagebox.showwarning("Warning", "Task is already completed")
            return

        if not messagebox.askyesno("Confirm", "Mark this task as complete?"):
            return

        completed_by = self.current_user.get('username') or self.current_user.get('id')

        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE onboarding_task_progress
                    SET status = 'completed', completed_by = ?, completed_date = ?, updated_at = ?
                    WHERE progress_id = ?
                ''', (completed_by, datetime.now().strftime("%Y-%m-%d"),
                      datetime.now().isoformat(), progress_id))

                # Check if all tasks are complete for this assignment
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT assignment_id FROM onboarding_task_progress WHERE progress_id = ?
                ''', (progress_id,))
                assignment_id = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT COUNT(*), SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)
                    FROM onboarding_task_progress WHERE assignment_id = ?
                ''', (assignment_id,))
                total, completed = cursor.fetchone()

                if total == completed:
                    # All tasks complete — but before flipping the
                    # assignment to 'completed' we require a contract
                    # document to be present in DM (#9). Without it,
                    # the new starter shouldn't be considered active.
                    cursor.execute(
                        "SELECT staff_id FROM onboarding_assignments "
                        "WHERE assignment_id = ?",
                        (assignment_id,),
                    )
                    staff_row = cursor.fetchone()
                    staff_id = staff_row[0] if staff_row else None

                    contract_present = True
                    try:
                        from education_system.systems.university.services.bus.document_bus import (
                            has_document,
                        )
                        contract_present = has_document(
                            "contract", staff_id,
                            document_type="contract",
                        )
                    except Exception:
                        contract_present = True

                    if not contract_present:
                        messagebox.showwarning(
                            "Contract not on file",
                            f"All onboarding tasks complete, but no signed "
                            f"contract is linked in Document Manager for "
                            f"staff {staff_id}. The assignment will stay "
                            f"in progress until the contract is uploaded.",
                        )
                    else:
                        conn.execute('''
                            UPDATE onboarding_assignments
                            SET status = 'completed', actual_completion_date = ?, updated_at = ?
                            WHERE assignment_id = ?
                        ''', (datetime.now().strftime("%Y-%m-%d"), datetime.now().isoformat(), assignment_id))

            log_activity('update', 'onboarding_task', progress_id=progress_id, details={'action': 'completed'})
            messagebox.showinfo("Success", "Task marked as complete")
            self._load_my_tasks()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update task: {e}")

    def _view_task_details(self, event=None):
        """View task details."""
        selection = self.tasks_tree.selection()
        if not selection:
            return

        item = self.tasks_tree.item(selection[0])
        progress_id = item['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT t.title, t.description, t.category, p.due_date, p.status,
                           p.notes, p.completed_by, p.completed_date
                    FROM onboarding_task_progress p
                    JOIN onboarding_template_tasks t ON p.task_id = t.task_id
                    WHERE p.progress_id = ?
                ''', (progress_id,))
                row = cursor.fetchone()

            if row:
                details = f"""
Task: {row[0]}
Description: {row[1] or 'No description'}
Category: {row[2] or 'General'}
Due Date: {row[3] or 'Not set'}
Status: {row[4].replace('_', ' ').capitalize()}
Notes: {row[5] or 'None'}
Completed By: {row[6] or 'N/A'}
Completed Date: {row[7] or 'N/A'}
                """
                messagebox.showinfo("Task Details", details.strip())

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load details: {e}")

    def _create_assignment(self):
        """Create a new onboarding assignment."""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Onboarding Assignment")
        dialog.geometry("450x350")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Create Onboarding Assignment", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Employee
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Employee ID:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        user_var = tk.StringVar()
        ttk.Entry(row, textvariable=user_var, width=25).pack(side=tk.LEFT)

        # Template
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Template:", width=15, anchor=tk.W).pack(side=tk.LEFT)

        templates = self._get_active_templates()
        template_var = tk.StringVar()
        ttk.Combobox(row, textvariable=template_var, values=list(templates.keys()),
                     width=25, state='readonly').pack(side=tk.LEFT)

        # Start date
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Start Date:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        start_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(row, textvariable=start_var, width=15).pack(side=tk.LEFT)

        # Target date
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Target Completion:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        target_var = tk.StringVar(value=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"))
        ttk.Entry(row, textvariable=target_var, width=15).pack(side=tk.LEFT)

        # Notes
        ttk.Label(main_frame, text="Notes:", anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        notes_text = scrolledtext.ScrolledText(main_frame, height=4, width=40)
        notes_text.pack(fill=tk.X)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save():
            if not user_var.get().strip():
                error_label.config(text="Employee ID is required")
                return
            if not template_var.get():
                error_label.config(text="Please select a template")
                return

            template_id = templates[template_var.get()]
            assigned_by = self.current_user.get('username') or self.current_user.get('id')

            try:
                with transaction() as conn:
                    cursor = conn.cursor()

                    # Create assignment
                    cursor.execute('''
                        INSERT INTO onboarding_assignments
                        (user_id, template_id, assigned_by, start_date, target_completion_date, notes, status)
                        VALUES (?, ?, ?, ?, ?, ?, 'in_progress')
                    ''', (user_var.get().strip(), template_id, assigned_by,
                          start_var.get(), target_var.get(), notes_text.get('1.0', tk.END).strip()))

                    assignment_id = cursor.lastrowid

                    # Get template tasks and create progress records
                    cursor.execute('''
                        SELECT task_id, due_days, assigned_to_role
                        FROM onboarding_template_tasks
                        WHERE template_id = ?
                        ORDER BY order_num
                    ''', (template_id,))

                    start_date = datetime.strptime(start_var.get(), "%Y-%m-%d")

                    for task in cursor.fetchall():
                        due_date = (start_date + timedelta(days=task[1])).strftime("%Y-%m-%d") if task[1] else None

                        cursor.execute('''
                            INSERT INTO onboarding_task_progress
                            (assignment_id, task_id, status, due_date)
                            VALUES (?, ?, 'pending', ?)
                        ''', (assignment_id, task[0], due_date))

                log_activity('create', 'onboarding_assignment',
                             details={'user_id': user_var.get(), 'template': template_var.get()})
                messagebox.showinfo("Success", "Onboarding assignment created")
                dialog.destroy()
                self._load_assignments()

            except Exception as e:
                error_label.config(text=f"Error: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Create Assignment", command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _create_template(self):
        """Create a new onboarding template."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Template")
        dialog.geometry("450x400")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Create Onboarding Template", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Name
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Template Name:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        name_var = tk.StringVar()
        ttk.Entry(row, textvariable=name_var, width=25).pack(side=tk.LEFT)

        # Type
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Type:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        type_var = tk.StringVar(value='Onboarding')
        ttk.Combobox(row, textvariable=type_var, values=['Onboarding', 'Offboarding'],
                     width=15, state='readonly').pack(side=tk.LEFT)

        # Role
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="For Role:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        role_var = tk.StringVar()
        ttk.Entry(row, textvariable=role_var, width=20).pack(side=tk.LEFT)

        # Department
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Department:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        dept_var = tk.StringVar()
        ttk.Entry(row, textvariable=dept_var, width=20).pack(side=tk.LEFT)

        # Estimated days
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Est. Days:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        days_var = tk.StringVar(value="30")
        ttk.Entry(row, textvariable=days_var, width=10).pack(side=tk.LEFT)

        # Description
        ttk.Label(main_frame, text="Description:", anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        desc_text = scrolledtext.ScrolledText(main_frame, height=4, width=40)
        desc_text.pack(fill=tk.X)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save():
            if not name_var.get().strip():
                error_label.config(text="Template name is required")
                return

            created_by = self.current_user.get('username') or self.current_user.get('id')

            try:
                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO onboarding_templates
                        (name, description, template_type, role, department, estimated_days, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (name_var.get().strip(), desc_text.get('1.0', tk.END).strip(),
                          type_var.get().lower(), role_var.get().strip() or None,
                          dept_var.get().strip() or None, int(days_var.get() or 30), created_by))

                log_activity('create', 'onboarding_template', details={'name': name_var.get()})
                messagebox.showinfo("Success", "Template created. Now add tasks using 'Manage Tasks'.")
                dialog.destroy()
                self._load_templates()

            except Exception as e:
                error_label.config(text=f"Error: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Create Template", command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _edit_template(self):
        """Edit selected template."""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to edit")
            return
        messagebox.showinfo("Edit", "Template edit dialog would open here")

    def _manage_template_tasks(self):
        """Manage tasks for selected template."""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to manage tasks")
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
        ttk.Button(header, text="Add Task", command=lambda: self._add_template_task(template_id, tasks_tree)).pack(side=tk.RIGHT)

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
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT task_id, title, category, assigned_to_role, due_days, is_required, order_num
                        FROM onboarding_template_tasks
                        WHERE template_id = ?
                        ORDER BY order_num
                    ''', (template_id,))

                    for row in cursor.fetchall():
                        values = (row[0], row[1], row[2] or '-', row[3] or '-',
                                  row[4] or '-', 'Yes' if row[5] else 'No', row[6])
                        tasks_tree.insert('', 'end', values=values)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load tasks: {e}")

        load_tasks()

        # Delete button
        ttk.Button(main_frame, text="Delete Selected Task",
                   command=lambda: self._delete_template_task(tasks_tree, load_tasks)).pack(pady=10)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def _add_template_task(self, template_id, tasks_tree):
        """Add a task to template."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Task")
        dialog.geometry("400x350")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Task Title:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        title_var = tk.StringVar()
        ttk.Entry(row, textvariable=title_var, width=25).pack(side=tk.LEFT)

        # Category
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Category:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        category_var = tk.StringVar(value='General')
        ttk.Combobox(row, textvariable=category_var,
                     values=['General', 'HR', 'IT', 'Training', 'Admin', 'Other'],
                     width=15, state='readonly').pack(side=tk.LEFT)

        # Assigned to role
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Assigned To:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        assigned_var = tk.StringVar(value='Employee')
        ttk.Combobox(row, textvariable=assigned_var,
                     values=['Employee', 'HR', 'Manager', 'IT', 'Admin'],
                     width=15, state='readonly').pack(side=tk.LEFT)

        # Due days
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Due Days:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        days_var = tk.StringVar(value="7")
        ttk.Entry(row, textvariable=days_var, width=10).pack(side=tk.LEFT)
        ttk.Label(row, text="(days from start)", font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # Required
        required_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Required task", variable=required_var).pack(anchor=tk.W, pady=10)

        # Description
        ttk.Label(main_frame, text="Description:", anchor=tk.W).pack(fill=tk.X, pady=(10, 5))
        desc_text = scrolledtext.ScrolledText(main_frame, height=4, width=35)
        desc_text.pack(fill=tk.X)

        def save():
            if not title_var.get().strip():
                messagebox.showwarning("Warning", "Task title is required")
                return

            try:
                with transaction() as conn:
                    # Get next order number
                    cursor = conn.cursor()
                    cursor.execute('SELECT MAX(order_num) FROM onboarding_template_tasks WHERE template_id = ?',
                                   (template_id,))
                    max_order = cursor.fetchone()[0] or 0

                    conn.execute('''
                        INSERT INTO onboarding_template_tasks
                        (template_id, title, description, category, assigned_to_role, due_days, is_required, order_num)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (template_id, title_var.get().strip(), desc_text.get('1.0', tk.END).strip(),
                          category_var.get(), assigned_var.get().lower(),
                          int(days_var.get() or 0), required_var.get(), max_order + 1))

                messagebox.showinfo("Success", "Task added")
                dialog.destroy()

                # Reload tasks
                tasks_tree.delete(*tasks_tree.get_children())
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT task_id, title, category, assigned_to_role, due_days, is_required, order_num
                        FROM onboarding_template_tasks WHERE template_id = ? ORDER BY order_num
                    ''', (template_id,))
                    for row in cursor.fetchall():
                        values = (row[0], row[1], row[2] or '-', row[3] or '-',
                                  row[4] or '-', 'Yes' if row[5] else 'No', row[6])
                        tasks_tree.insert('', 'end', values=values)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add task: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Add Task", command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _delete_template_task(self, tasks_tree, reload_func):
        """Delete selected template task."""
        selection = tasks_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a task to delete")
            return

        if not messagebox.askyesno("Confirm", "Delete this task?"):
            return

        item = tasks_tree.item(selection[0])
        task_id = item['values'][0]

        try:
            with transaction() as conn:
                conn.execute('DELETE FROM onboarding_template_tasks WHERE task_id = ?', (task_id,))

            messagebox.showinfo("Success", "Task deleted")
            reload_func()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete task: {e}")

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
        messagebox.showinfo("Assignment Details", details.strip())

    def _get_active_templates(self) -> dict:
        """Get active templates as {name: id} dict."""
        templates = {}
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT template_id, name FROM onboarding_templates WHERE is_active = 1 ORDER BY name')
                for row in cursor.fetchall():
                    templates[row[1]] = row[0]
        except Exception:
            pass
        return templates


def launch_onboarding_gui(root, auth):
    """Launch Onboarding GUI."""
    try:
        return OnboardingGUI(root, auth)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Onboarding GUI: {e}")
        return None
