"""
Exit Management GUI

Provides interface for:
- Exit checklist management
- Exit interview scheduling and conducting
- Knowledge transfer tracking
- Turnover analytics and reports
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.exit_manager import ExitManager
from education_system.university_system.modules.domain.operations.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_combobox, validate_rating_entry, show_validation_error
)


class ExitGUI:
    """GUI for managing exit processes and turnover analytics."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Exit Management")
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def _get_user_id(self):
        """Get user ID from current user dict."""
        return self.current_user.get('id') or self.current_user.get('username')

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Exit Management")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Exit Management & Turnover Analytics")
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

        self._create_my_checklist_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_initiate_exit_tab()
            self._create_manage_exits_tab()
            self._create_interviews_tab()
            self._create_knowledge_transfer_tab()
            self._create_analytics_tab()

    def _create_my_checklist_tab(self):
        """Create my exit checklist tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Checklist")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="My Exit Checklist", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_my_checklist).pack(side=tk.RIGHT)

        # Progress
        self.progress_frame = ttk.Frame(tab)
        self.progress_frame.pack(fill=tk.X, padx=10, pady=5)

        self.progress_label = ttk.Label(self.progress_frame, text="No active exit process")
        self.progress_label.pack(side=tk.LEFT)

        self.progress_bar = ttk.Progressbar(self.progress_frame, length=300, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, padx=20)

        # Checklist
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('ID', 'Task', 'Category', 'Assigned To', 'Due Date', 'Status')
        self.my_checklist_tree = ttk.Treeview(tree_frame, columns=columns, show='headings')

        widths = {'ID': 50, 'Task': 250, 'Category': 100, 'Assigned To': 100, 'Due Date': 100, 'Status': 80}
        for col in columns:
            self.my_checklist_tree.heading(col, text=col)
            self.my_checklist_tree.column(col, width=widths.get(col, 100))

        self.my_checklist_tree.pack(fill=tk.BOTH, expand=True)

        self.my_checklist_tree.tag_configure('completed', background='#d4edda')
        self.my_checklist_tree.tag_configure('required', background='#fff3cd')

        # Complete button
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Mark Selected as Complete", command=self._complete_my_item).pack(side=tk.LEFT)

        self._load_my_checklist()

    def _load_my_checklist(self):
        """Load my exit checklist."""
        for item in self.my_checklist_tree.get_children():
            self.my_checklist_tree.delete(item)

        user_id = self._get_user_id()
        items = ExitManager.get_user_checklist(user_id)

        if not items:
            self.progress_label.config(text="No active exit process")
            self.progress_bar['value'] = 0
            return

        completed = sum(1 for i in items if i.get('completed'))
        total = len(items)
        pct = (completed / total * 100) if total > 0 else 0

        self.progress_label.config(text=f"Progress: {completed}/{total} tasks completed")
        self.progress_bar['value'] = pct

        for i in items:
            status = 'Completed' if i.get('completed') else 'Pending'
            tag = 'completed' if i.get('completed') else 'required' if i.get('is_required') else ''

            self.my_checklist_tree.insert('', tk.END, values=(
                i.get('checklist_id'),
                i.get('task_name'),
                i.get('category', '').title(),
                i.get('assigned_to', '-'),
                i.get('due_date', '-'),
                status
            ), tags=(tag,))

    def _complete_my_item(self):
        """Complete a checklist item."""
        selection = self.my_checklist_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an item to complete")
            return

        item = self.my_checklist_tree.item(selection[0])
        if item['values'][5] == 'Completed':
            messagebox.showinfo("Info", "This item is already completed")
            return

        item_id = item['values'][0]
        notes = tk.simpledialog.askstring("Notes", "Completion notes (optional):", parent=self.root)

        ExitManager.complete_checklist_item(item_id, self._get_user_id(), notes or '')
        messagebox.showinfo("Success", "Item marked as complete")
        self._load_my_checklist()

    def _create_initiate_exit_tab(self):
        """Create initiate exit tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Initiate Exit")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Initiate Exit Process", style='Header.TLabel').pack(side=tk.LEFT)

        # Form
        form_frame = ttk.LabelFrame(tab, text="Exit Details", padding=15)
        form_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 1
        ttk.Label(form_frame, text="Employee User ID:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.exit_user_id = ttk.Entry(form_frame, width=20)
        self.exit_user_id.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(form_frame, text="Exit Type:").grid(row=0, column=2, sticky='e', padx=10, pady=8)
        self.exit_type = ttk.Combobox(form_frame, values=[
            'resignation', 'retirement', 'termination', 'end_of_contract', 'redundancy', 'other'
        ], width=15, state='readonly')
        self.exit_type.set('resignation')
        self.exit_type.grid(row=0, column=3, padx=10, pady=8, sticky='w')

        # Row 2
        ttk.Label(form_frame, text="Last Working Day:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        self.exit_last_day = ttk.Entry(form_frame, width=15)
        self.exit_last_day.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(form_frame, text="Department:").grid(row=1, column=2, sticky='e', padx=10, pady=8)
        self.exit_dept = ttk.Entry(form_frame, width=20)
        self.exit_dept.grid(row=1, column=3, padx=10, pady=8, sticky='w')

        # Row 3
        ttk.Label(form_frame, text="Manager ID:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        self.exit_manager = ttk.Entry(form_frame, width=20)
        self.exit_manager.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Row 4
        ttk.Label(form_frame, text="Reason:").grid(row=3, column=0, sticky='ne', padx=10, pady=8)
        self.exit_reason = scrolledtext.ScrolledText(form_frame, width=50, height=4)
        self.exit_reason.grid(row=3, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Template selection
        template_frame = ttk.LabelFrame(tab, text="Checklist Template", padding=10)
        template_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(template_frame, text="Apply Template:").pack(side=tk.LEFT, padx=10)
        self.exit_template = ttk.Combobox(template_frame, width=30, state='readonly')
        self._load_templates_combo()
        self.exit_template.pack(side=tk.LEFT, padx=10)

        # Submit
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Initiate Exit Process", command=self._initiate_exit).pack()

    def _load_templates_combo(self):
        """Load templates into combo."""
        templates = ExitManager.get_all_templates()
        self.templates_data = {t['name']: t for t in templates}
        values = ['(No Template)'] + [t['name'] for t in templates]
        self.exit_template['values'] = values
        self.exit_template.set('(No Template)')

    def _initiate_exit(self):
        """Initiate exit process."""
        user_id = self.exit_user_id.get().strip()
        if not user_id:
            messagebox.showerror("Error", "Employee User ID is required")
            return

        last_day = self.exit_last_day.get().strip()
        if not last_day:
            messagebox.showerror("Error", "Last working day is required")
            return

        try:
            exit_id = ExitManager.initiate_exit(
                user_id=user_id,
                exit_type=self.exit_type.get(),
                last_working_day=last_day,
                reason=self.exit_reason.get("1.0", tk.END).strip(),
                department=self.exit_dept.get().strip(),
                manager_id=self.exit_manager.get().strip()
            )

            # Apply template if selected
            template_name = self.exit_template.get()
            if template_name != '(No Template)' and template_name in self.templates_data:
                template_id = self.templates_data[template_name]['template_id']
                ExitManager.apply_template(user_id, template_id)

            messagebox.showinfo("Success", f"Exit process initiated.\nReference: EXIT-{exit_id}")

            # Clear form
            self.exit_user_id.delete(0, tk.END)
            self.exit_last_day.delete(0, tk.END)
            self.exit_dept.delete(0, tk.END)
            self.exit_manager.delete(0, tk.END)
            self.exit_reason.delete("1.0", tk.END)

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _create_manage_exits_tab(self):
        """Create manage exits tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Manage")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Manage Exit Processes", style='Header.TLabel').pack(side=tk.LEFT)

        # Filter
        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)
        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.exit_status_filter = ttk.Combobox(filter_frame,
            values=['All', 'In Progress', 'Completed'], width=12, state='readonly')
        self.exit_status_filter.set('In Progress')
        self.exit_status_filter.pack(side=tk.LEFT, padx=5)
        self.exit_status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_exit_records())
        ttk.Button(filter_frame, text="Refresh", command=self._load_exit_records).pack(side=tk.LEFT, padx=10)

        # Exit records list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('User', 'Type', 'Last Day', 'Department', 'Status', 'Progress')
        self.exits_tree = ttk.Treeview(tree_frame, columns=columns, show='headings')

        for col in columns:
            self.exits_tree.heading(col, text=col)
            self.exits_tree.column(col, width=120)

        self.exits_tree.pack(fill=tk.BOTH, expand=True)

        self.exits_tree.bind('<Double-1>', self._view_exit_details)

        # Actions
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(action_frame, text="View Checklist", command=self._view_exit_checklist).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Add Checklist Item", command=self._add_checklist_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Complete Exit", command=self._complete_exit).pack(side=tk.LEFT, padx=5)

        self._load_exit_records()

    def _load_exit_records(self):
        """Load exit records."""
        for item in self.exits_tree.get_children():
            self.exits_tree.delete(item)

        status_filter = self.exit_status_filter.get().lower()
        if status_filter == 'all':
            status = None
        elif status_filter == 'in progress':
            status = 'in_progress'
        else:
            status = status_filter

        records = ExitManager.search_exits(status=status)

        for r in records:
            # Calculate progress
            checklist = ExitManager.get_user_checklist(r.get('user_id'))
            if checklist:
                completed = sum(1 for i in checklist if i.get('completed'))
                progress = f"{completed}/{len(checklist)}"
            else:
                progress = "No checklist"

            self.exits_tree.insert('', tk.END, values=(
                r.get('user_id'),
                r.get('exit_type', '').replace('_', ' ').title(),
                r.get('last_working_day', ''),
                r.get('department', ''),
                r.get('status', '').replace('_', ' ').title(),
                progress
            ))

    def _view_exit_details(self, event):
        """View exit details."""
        selection = self.exits_tree.selection()
        if not selection:
            return

        item = self.exits_tree.item(selection[0])
        user_id = item['values'][0]

        record = ExitManager.get_exit_record(user_id)
        if not record:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Exit Details - {user_id}")
        dialog.geometry("500x400")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        fields = [
            ('Employee', record.get('user_id')),
            ('Exit Type', record.get('exit_type', '').replace('_', ' ').title()),
            ('Last Working Day', record.get('last_working_day')),
            ('Department', record.get('department')),
            ('Manager', record.get('manager_id')),
            ('Status', record.get('status', '').replace('_', ' ').title()),
            ('Initiated', record.get('created_at', '')[:10] if record.get('created_at') else ''),
        ]

        for i, (label, value) in enumerate(fields):
            ttk.Label(frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='e', padx=10, pady=5)
            ttk.Label(frame, text=str(value or '-')).grid(row=i, column=1, sticky='w', padx=10, pady=5)

        ttk.Label(frame, text="Reason:", font=('Arial', 10, 'bold')).grid(
            row=len(fields), column=0, sticky='ne', padx=10, pady=5)
        reason_text = scrolledtext.ScrolledText(frame, width=40, height=5, state='normal')
        reason_text.insert("1.0", record.get('reason', ''))
        reason_text.config(state='disabled')
        reason_text.grid(row=len(fields), column=1, padx=10, pady=5)

        ttk.Button(frame, text="Close", command=dialog.destroy).grid(
            row=len(fields)+1, column=0, columnspan=2, pady=20)

    def _view_exit_checklist(self):
        """View exit checklist for selected employee."""
        selection = self.exits_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an exit record")
            return

        item = self.exits_tree.item(selection[0])
        user_id = item['values'][0]

        items = ExitManager.get_user_checklist(user_id)

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Exit Checklist - {user_id}")
        dialog.geometry("700x500")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Task', 'Category', 'Assigned', 'Status')
        tree = ttk.Treeview(frame, columns=columns, show='headings')

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)

        tree.column('Task', width=250)
        tree.pack(fill=tk.BOTH, expand=True)

        tree.tag_configure('completed', background='#d4edda')

        for i in items:
            tag = 'completed' if i.get('completed') else ''
            tree.insert('', tk.END, values=(
                i.get('checklist_id'),
                i.get('task_name'),
                i.get('category', '').title(),
                i.get('assigned_to', '-'),
                'Completed' if i.get('completed') else 'Pending'
            ), tags=(tag,))

        def complete_item():
            sel = tree.selection()
            if not sel:
                return
            item_id = tree.item(sel[0])['values'][0]
            ExitManager.complete_checklist_item(item_id, self._get_user_id())
            dialog.destroy()
            self._view_exit_checklist()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="Complete Selected", command=complete_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def _add_checklist_item(self):
        """Add checklist item to selected exit."""
        selection = self.exits_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an exit record")
            return

        item = self.exits_tree.item(selection[0])
        user_id = item['values'][0]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Add Checklist Item - {user_id}")
        dialog.geometry("400x300")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Task Name:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        task_entry = ttk.Entry(frame, width=30)
        task_entry.grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(frame, text="Category:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        cat_combo = ttk.Combobox(frame, values=['it', 'hr', 'finance', 'facilities', 'other'], width=15)
        cat_combo.set('other')
        cat_combo.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(frame, text="Assign To:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        assign_entry = ttk.Entry(frame, width=20)
        assign_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(frame, text="Due Date:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        due_entry = ttk.Entry(frame, width=15)
        due_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        required_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Required", variable=required_var).grid(
            row=4, column=1, sticky='w', padx=10, pady=5)

        def save():
            task_name = task_entry.get().strip()
            if not task_name:
                messagebox.showerror("Error", "Task name is required")
                return

            try:
                ExitManager.add_checklist_item(
                    user_id,
                    task_name=task_name,
                    category=cat_combo.get(),
                    assigned_to=assign_entry.get().strip() or None,
                    due_date=due_entry.get().strip() or None,
                    is_required=required_var.get()
                )
                messagebox.showinfo("Success", "Checklist item added")
                dialog.destroy()
                self._load_exit_records()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(frame, text="Add Item", command=save).grid(row=5, column=0, columnspan=2, pady=20)

    def _complete_exit(self):
        """Complete exit process."""
        selection = self.exits_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an exit record")
            return

        item = self.exits_tree.item(selection[0])
        user_id = item['values'][0]

        # Check if all required items completed
        checklist = ExitManager.get_user_checklist(user_id)
        required_pending = [i for i in checklist if i.get('is_required') and not i.get('completed')]

        if required_pending:
            if not messagebox.askyesno("Warning",
                f"{len(required_pending)} required items are not completed.\nComplete exit anyway?"):
                return

        ExitManager.complete_exit(user_id)
        messagebox.showinfo("Success", "Exit process marked as complete")
        self._load_exit_records()

    def _create_interviews_tab(self):
        """Create exit interviews tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Interviews")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Exit Interviews", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Schedule Interview", command=self._schedule_interview).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Refresh", command=self._load_interviews).pack(side=tk.RIGHT, padx=5)

        # Interviews list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('ID', 'Employee', 'Interviewer', 'Date', 'Status', 'Reason')
        self.interviews_tree = ttk.Treeview(tree_frame, columns=columns, show='headings')

        for col in columns:
            self.interviews_tree.heading(col, text=col)
            self.interviews_tree.column(col, width=120)

        self.interviews_tree.pack(fill=tk.BOTH, expand=True)

        self.interviews_tree.tag_configure('pending', background='#fff3cd')
        self.interviews_tree.tag_configure('completed', background='#d4edda')

        # Actions
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(action_frame, text="Conduct Interview", command=self._conduct_interview).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="View Details", command=self._view_interview_details).pack(side=tk.LEFT, padx=5)

        self._load_interviews()

    def _load_interviews(self):
        """Load interviews."""
        for item in self.interviews_tree.get_children():
            self.interviews_tree.delete(item)

        interviews = ExitManager.get_all_interviews()

        for i in interviews:
            status = 'Completed' if i.get('completed') else 'Scheduled'
            tag = 'completed' if i.get('completed') else 'pending'

            self.interviews_tree.insert('', tk.END, values=(
                i.get('interview_id'),
                i.get('user_id'),
                i.get('interviewer_id'),
                i.get('interview_date'),
                status,
                i.get('reason_for_leaving', '-')[:30] if i.get('reason_for_leaving') else '-'
            ), tags=(tag,))

    def _schedule_interview(self):
        """Schedule exit interview."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Schedule Exit Interview")
        dialog.geometry("400x250")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Employee User ID:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        user_entry = ttk.Entry(frame, width=20)
        user_entry.grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(frame, text="Interviewer ID:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        interviewer_entry = ttk.Entry(frame, width=20)
        interviewer_entry.insert(0, self._get_user_id())
        interviewer_entry.grid(row=1, column=1, padx=10, pady=8)

        ttk.Label(frame, text="Date (YYYY-MM-DD):").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        date_entry = ttk.Entry(frame, width=15)
        date_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(frame, text="Time (HH:MM):").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        time_entry = ttk.Entry(frame, width=10)
        time_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        def save():
            try:
                interview_id = ExitManager.schedule_interview(
                    user_id=user_entry.get().strip(),
                    interviewer_id=interviewer_entry.get().strip(),
                    interview_date=date_entry.get().strip(),
                    interview_time=time_entry.get().strip()
                )
                messagebox.showinfo("Success", f"Interview scheduled. ID: {interview_id}")
                dialog.destroy()
                self._load_interviews()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(frame, text="Schedule", command=save).grid(row=4, column=0, columnspan=2, pady=20)

    def _conduct_interview(self):
        """Conduct exit interview."""
        selection = self.interviews_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an interview")
            return

        item = self.interviews_tree.item(selection[0])
        if item['values'][4] == 'Completed':
            messagebox.showinfo("Info", "This interview is already completed")
            return

        interview_id = item['values'][0]

        # Interview form dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Conduct Exit Interview")
        dialog.geometry("600x600")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Reason for leaving
        ttk.Label(frame, text="Primary Reason for Leaving:").grid(row=0, column=0, sticky='e', padx=10, pady=5)
        reason_combo = ttk.Combobox(frame, values=[
            'better_opportunity', 'career_advancement', 'compensation',
            'work_life_balance', 'management_issues', 'company_culture',
            'relocation', 'personal', 'retirement', 'other'
        ], width=25)
        reason_combo.grid(row=0, column=1, padx=10, pady=5, sticky='w')

        # Ratings
        ratings = {}
        rating_labels = [
            ('job', 'Job Satisfaction'),
            ('mgmt', 'Management'),
            ('env', 'Work Environment'),
            ('growth', 'Growth Opportunities')
        ]

        for i, (key, label) in enumerate(rating_labels):
            ttk.Label(frame, text=f"{label} (1-5):").grid(row=i+1, column=0, sticky='e', padx=10, pady=5)
            ratings[key] = ttk.Spinbox(frame, from_=1, to=5, width=5)
            ratings[key].set(3)
            ratings[key].grid(row=i+1, column=1, padx=10, pady=5, sticky='w')

        # Yes/No questions
        recommend_var = tk.BooleanVar()
        return_var = tk.BooleanVar()

        ttk.Checkbutton(frame, text="Would recommend as employer", variable=recommend_var).grid(
            row=5, column=0, columnspan=2, pady=5)
        ttk.Checkbutton(frame, text="Would consider returning", variable=return_var).grid(
            row=6, column=0, columnspan=2, pady=5)

        # Feedback
        ttk.Label(frame, text="Positive Feedback:").grid(row=7, column=0, sticky='ne', padx=10, pady=5)
        positive_text = scrolledtext.ScrolledText(frame, width=40, height=4)
        positive_text.grid(row=7, column=1, padx=10, pady=5)

        ttk.Label(frame, text="Areas for Improvement:").grid(row=8, column=0, sticky='ne', padx=10, pady=5)
        negative_text = scrolledtext.ScrolledText(frame, width=40, height=4)
        negative_text.grid(row=8, column=1, padx=10, pady=5)

        def save():
            try:
                ExitManager.complete_interview(
                    interview_id,
                    reason_for_leaving=reason_combo.get(),
                    job_satisfaction=int(ratings['job'].get()),
                    management_rating=int(ratings['mgmt'].get()),
                    work_environment_rating=int(ratings['env'].get()),
                    growth_opportunities_rating=int(ratings['growth'].get()),
                    would_recommend=recommend_var.get(),
                    would_return=return_var.get(),
                    feedback_positive=positive_text.get("1.0", tk.END).strip(),
                    feedback_negative=negative_text.get("1.0", tk.END).strip()
                )
                messagebox.showinfo("Success", "Interview completed")
                dialog.destroy()
                self._load_interviews()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(frame, text="Complete Interview", command=save).grid(row=9, column=0, columnspan=2, pady=20)

    def _view_interview_details(self):
        """View interview details."""
        selection = self.interviews_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an interview")
            return

        item = self.interviews_tree.item(selection[0])
        interview_id = item['values'][0]

        interview = ExitManager.get_interview(interview_id)
        if not interview:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Interview Details - {interview.get('user_id')}")
        dialog.geometry("500x400")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        details = f"""Employee: {interview.get('user_id')}
Interviewer: {interview.get('interviewer_id')}
Date: {interview.get('interview_date')}
Status: {'Completed' if interview.get('completed') else 'Scheduled'}

Reason for Leaving: {interview.get('reason_for_leaving', 'N/A')}

Ratings:
  Job Satisfaction: {interview.get('job_satisfaction', '-')}/5
  Management: {interview.get('management_rating', '-')}/5
  Work Environment: {interview.get('work_environment_rating', '-')}/5
  Growth Opportunities: {interview.get('growth_opportunities_rating', '-')}/5

Would Recommend: {'Yes' if interview.get('would_recommend') else 'No'}
Would Return: {'Yes' if interview.get('would_return') else 'No'}

Positive Feedback:
{interview.get('feedback_positive', 'N/A')}

Areas for Improvement:
{interview.get('feedback_negative', 'N/A')}
"""
        text = scrolledtext.ScrolledText(frame, state='normal')
        text.insert("1.0", details)
        text.config(state='disabled')
        text.pack(fill=tk.BOTH, expand=True)

        ttk.Button(frame, text="Close", command=dialog.destroy).pack(pady=10)

    def _create_knowledge_transfer_tab(self):
        """Create knowledge transfer tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Knowledge Transfer")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Knowledge Transfer", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Create New", command=self._create_knowledge_transfer).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Refresh", command=self._load_knowledge_transfers).pack(side=tk.RIGHT, padx=5)

        # Transfers list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('ID', 'Topic', 'From', 'To', 'Priority', 'Due Date', 'Status')
        self.kt_tree = ttk.Treeview(tree_frame, columns=columns, show='headings')

        for col in columns:
            self.kt_tree.heading(col, text=col)
            self.kt_tree.column(col, width=100)

        self.kt_tree.column('Topic', width=200)
        self.kt_tree.pack(fill=tk.BOTH, expand=True)

        self.kt_tree.tag_configure('critical', background='#f8d7da')
        self.kt_tree.tag_configure('high', background='#fff3cd')
        self.kt_tree.tag_configure('completed', background='#d4edda')

        # Actions
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(action_frame, text="Mark Complete", command=self._complete_kt).pack(side=tk.LEFT, padx=5)

        self._load_knowledge_transfers()

    def _load_knowledge_transfers(self):
        """Load knowledge transfers."""
        for item in self.kt_tree.get_children():
            self.kt_tree.delete(item)

        transfers = ExitManager.get_knowledge_transfers()

        for t in transfers:
            priority = t.get('priority', 'medium').lower()
            status = t.get('status', 'pending').lower()

            if status == 'completed':
                tag = 'completed'
            elif priority == 'critical':
                tag = 'critical'
            elif priority == 'high':
                tag = 'high'
            else:
                tag = ''

            self.kt_tree.insert('', tk.END, values=(
                t.get('transfer_id'),
                t.get('topic'),
                t.get('from_user_id'),
                t.get('to_user_id'),
                t.get('priority', 'medium').title(),
                t.get('due_date', '-'),
                t.get('status', 'pending').title()
            ), tags=(tag,))

    def _create_knowledge_transfer(self):
        """Create knowledge transfer dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Knowledge Transfer")
        dialog.geometry("500x350")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="From (Departing):").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        from_entry = ttk.Entry(frame, width=20)
        from_entry.grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(frame, text="To (Receiving):").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        to_entry = ttk.Entry(frame, width=20)
        to_entry.grid(row=1, column=1, padx=10, pady=8)

        ttk.Label(frame, text="Topic:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        topic_entry = ttk.Entry(frame, width=30)
        topic_entry.grid(row=2, column=1, padx=10, pady=8)

        ttk.Label(frame, text="Priority:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        priority_combo = ttk.Combobox(frame, values=['low', 'medium', 'high', 'critical'], width=15)
        priority_combo.set('medium')
        priority_combo.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(frame, text="Due Date:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        due_entry = ttk.Entry(frame, width=15)
        due_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(frame, text="Description:").grid(row=5, column=0, sticky='ne', padx=10, pady=8)
        desc_text = scrolledtext.ScrolledText(frame, width=35, height=4)
        desc_text.grid(row=5, column=1, padx=10, pady=8)

        def save():
            try:
                transfer_id = ExitManager.create_knowledge_transfer(
                    from_user_id=from_entry.get().strip(),
                    to_user_id=to_entry.get().strip(),
                    topic=topic_entry.get().strip(),
                    description=desc_text.get("1.0", tk.END).strip(),
                    priority=priority_combo.get(),
                    due_date=due_entry.get().strip() or None
                )
                messagebox.showinfo("Success", f"Transfer created. ID: {transfer_id}")
                dialog.destroy()
                self._load_knowledge_transfers()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(frame, text="Create", command=save).grid(row=6, column=0, columnspan=2, pady=20)

    def _complete_kt(self):
        """Complete knowledge transfer."""
        selection = self.kt_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a transfer")
            return

        item = self.kt_tree.item(selection[0])
        transfer_id = item['values'][0]

        ExitManager.complete_knowledge_transfer(transfer_id)
        messagebox.showinfo("Success", "Transfer marked as complete")
        self._load_knowledge_transfers()

    def _create_analytics_tab(self):
        """Create analytics tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Analytics")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Turnover Analytics", style='Header.TLabel').pack(side=tk.LEFT)

        ttk.Label(header_frame, text="Year:").pack(side=tk.RIGHT, padx=5)
        self.analytics_year = ttk.Spinbox(header_frame, from_=2020, to=2030, width=6)
        self.analytics_year.set(datetime.now().year)
        self.analytics_year.pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Load", command=self._load_analytics).pack(side=tk.RIGHT, padx=10)

        # Summary stats
        stats_frame = ttk.LabelFrame(tab, text="Summary", padding=15)
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        self.analytics_stats = {}
        for key, label in [('total', 'Total Exits'), ('voluntary', 'Voluntary'), ('rate', 'Turnover Rate')]:
            frame = ttk.Frame(stats_frame)
            frame.pack(side=tk.LEFT, padx=40, pady=10)
            self.analytics_stats[key] = ttk.Label(frame, text="0", font=('Arial', 20, 'bold'))
            self.analytics_stats[key].pack()
            ttk.Label(frame, text=label).pack()

        # By department
        dept_frame = ttk.LabelFrame(tab, text="By Department", padding=10)
        dept_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Department', 'Exits', 'Turnover Rate', 'Avg Tenure')
        self.dept_analytics_tree = ttk.Treeview(dept_frame, columns=columns, show='headings', height=8)

        for col in columns:
            self.dept_analytics_tree.heading(col, text=col)
            self.dept_analytics_tree.column(col, width=150)

        self.dept_analytics_tree.pack(fill=tk.BOTH, expand=True)

        self._load_analytics()

    def _load_analytics(self):
        """Load analytics data."""
        year = int(self.analytics_year.get())
        analytics = ExitManager.get_turnover_analytics(year)

        self.analytics_stats['total'].config(text=str(analytics.get('total_exits', 0)))
        self.analytics_stats['voluntary'].config(text=str(analytics.get('voluntary_exits', 0)))
        self.analytics_stats['rate'].config(text=f"{analytics.get('turnover_rate', 0):.1f}%")

        # By department
        for item in self.dept_analytics_tree.get_children():
            self.dept_analytics_tree.delete(item)

        for dept, data in analytics.get('by_department', {}).items():
            self.dept_analytics_tree.insert('', tk.END, values=(
                dept,
                data.get('exits', 0),
                f"{data.get('rate', 0):.1f}%",
                f"{data.get('avg_tenure', 0):.1f} months"
            ))


# Add simpledialog import
try:
    from tkinter import simpledialog
    tk.simpledialog = simpledialog
except ImportError:
    pass
