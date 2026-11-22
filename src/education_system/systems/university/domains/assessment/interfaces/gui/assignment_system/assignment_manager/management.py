"""Faculty assignment management - CRUD, editing, status toggling"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.infrastructure.sql_safety import escape_like
import tkinter as tk
from tkinter import ttk, scrolledtext
from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import messagebox
from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import make_toplevel
from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.ui.field_pickers import attach_datetime
from education_system.systems.university.domains.assessment.domain.assignments.assignment_rules import (
    runner as assignment_runner,
    scope as staff_scope,
    visibility as assignment_visibility,
)


class ManagementMixin:
    """Assignment management operations for faculty"""

    def show_manage_assignments(self):
        """Show assignment management interface"""
        if not self._check_permission('manage_assignments'):
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.manage_assignments', default="Manage Assignments"), style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Filter and search frame
        filter_frame = ttk.LabelFrame(self.gui.layout.content_area, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.filters_search', default="Filters & Search"), padding=10)
        filter_frame.pack(fill='x', pady=(0, 10))

        # Module filter
        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.module', default="Module:")).grid(row=0, column=0, sticky='w', padx=5)
        self.manage_module_filter_var = tk.StringVar()
        module_combo = ttk.Combobox(filter_frame, textvariable=self.manage_module_filter_var, width=20)
        module_combo.grid(row=0, column=1, padx=5)
        self.load_modules_for_filter(module_combo)

        # Status filter
        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.status', default="Status:")).grid(row=0, column=2, sticky='w', padx=5)
        self.manage_status_filter_var = tk.StringVar(value=_t('gui.academics.assignment_system.assignment_manager.management.values.all', default="All"))
        status_combo = ttk.Combobox(filter_frame, textvariable=self.manage_status_filter_var,
                                   values=["All", "Active", "Inactive", "Upcoming", "Overdue"], width=15)
        status_combo.grid(row=0, column=3, padx=5)

        # Search
        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.search', default="Search:")).grid(row=0, column=4, sticky='w', padx=5)
        self.manage_search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self.manage_search_var, width=20)
        search_entry.grid(row=0, column=5, padx=5)

        # Apply filter button
        ttk.Button(filter_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.apply_filters', default="Apply Filters"),
                  command=self.load_managed_assignments).grid(row=0, column=6, padx=10)

        # Assignments table
        assignments_frame = ttk.Frame(self.gui.layout.content_area)
        assignments_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Title', 'Module', 'Type', 'Due Date', 'Submissions', 'Status')
        self.manage_assignments_tree = ttk.Treeview(assignments_frame, columns=columns, show='headings')

        for col in columns:
            self.manage_assignments_tree.heading(col, text=col)
            self.manage_assignments_tree.column(col, width=100)

        # Scrollbars
        v_scroll = ttk.Scrollbar(assignments_frame, orient='vertical', command=self.manage_assignments_tree.yview)
        h_scroll = ttk.Scrollbar(assignments_frame, orient='horizontal', command=self.manage_assignments_tree.xview)
        self.manage_assignments_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.manage_assignments_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        assignments_frame.grid_rowconfigure(0, weight=1)
        assignments_frame.grid_columnconfigure(0, weight=1)

        # Bind selection event
        self.manage_assignments_tree.bind('<<TreeviewSelect>>', self.on_manage_assignment_select)

        # Action buttons - Row 1
        action_frame = ttk.Frame(self.gui.layout.content_area)
        action_frame.pack(fill='x', pady=(10, 0))

        ttk.Label(action_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.single_assignment_actions', default="Single Assignment Actions:"), font=('TkDefaultFont', 9, 'bold')).pack(side='left', padx=(0, 10))

        ttk.Button(action_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.edit_assignment', default="Edit Assignment"),
                  command=self.edit_selected_assignment).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.clone', default="Clone"),
                  command=self.duplicate_selected_assignment).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.publish', default="Publish"),
                  command=self.publish_selected_assignment).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.toggle_status', default="Toggle Status"),
                  command=self.toggle_assignment_status).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.view_submissions', default="View Submissions"),
                  command=self.view_assignment_submissions).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.export_data', default="Export Data"),
                  command=self.export_assignment_data).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.download_all', default="Download All"),
                  command=self.download_all_submissions).pack(side='left', padx=(0, 5))

        # Action buttons - Row 2: Bulk Operations
        bulk_frame = ttk.Frame(self.gui.layout.content_area)
        bulk_frame.pack(fill='x', pady=(5, 0))

        ttk.Label(bulk_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.bulk_actions', default="Bulk Actions:"), font=('TkDefaultFont', 9, 'bold')).pack(side='left', padx=(0, 10))

        ttk.Button(bulk_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.archive_selected', default="Archive Selected"),
                  command=self.bulk_archive_assignments).pack(side='left', padx=(0, 5))
        ttk.Button(bulk_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.delete_selected', default="Delete Selected"),
                  command=self.bulk_delete_assignments).pack(side='left', padx=(0, 5))
        ttk.Button(bulk_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.change_due_dates', default="Change Due Dates"),
                  command=self.bulk_change_due_dates).pack(side='left', padx=(0, 5))
        ttk.Button(bulk_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.export_selected', default="Export Selected"),
                  command=self.bulk_export_assignments).pack(side='left', padx=(0, 5))
        ttk.Button(bulk_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.send_reminders', default="Send Reminders"),
                  command=self.bulk_send_reminders).pack(side='left', padx=(0, 5))

        # Statistics button
        ttk.Button(bulk_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.view_statistics', default="View Statistics"),
                  command=self.show_assignment_statistics).pack(side='right', padx=(0, 5))

        # Assignment details frame
        self.assignment_details_frame = ttk.LabelFrame(self.gui.layout.content_area, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.assignment_details', default="Assignment Details"), padding=10)
        self.assignment_details_frame.pack(fill='both', expand=True, pady=(10, 0))

        # Load assignments
        self.load_managed_assignments()


    def _visible_modules(self, conn):
        """The modules this person can manage; ``None`` means all of them."""
        user = self.auth.current_user or {}
        return staff_scope.modules_for(conn, user.get('username'), user.get('id'), user.get('role'))

    def publish_selected_assignment(self):
        """Make the selected assignment visible and tell its students."""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning("Publish", "Please select an assignment to publish")
            return
        assignment_id, title = self.manage_assignments_tree.item(selection[0])['values'][:2]
        if not messagebox.askyesno("Publish", f"Publish '{title}'? Students on the module will "
                                              "see it and be told about it if they haven't been already."):
            return
        self._apply_visibility(assignment_id, "published")
        self.load_managed_assignments()

    def _apply_visibility(self, assignment_id, visibility, available_from=None):
        """Set visibility, then tell students if it has just opened. ``True`` when saved."""
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        try:
            tell = assignment_visibility.set_visibility(conn, assignment_id, visibility, available_from)
            conn.commit()
        except ValueError as e:
            messagebox.showwarning("Visibility", str(e))
            return False
        finally:
            conn.close()
        if tell:
            assignment_runner.announce(assignment_id)
        return True

    def load_managed_assignments(self):
        """Load assignments for management"""
        # Clear existing data
        for item in self.manage_assignments_tree.get_children():
            self.manage_assignments_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Build query based on filters
            query = '''
            SELECT a.id, a.title, a.module_code, a.assignment_type, a.due_date,
                   COUNT(s.id) as submission_count,
                   CASE
                       WHEN a.is_active = 0 AND LOWER(COALESCE(a.status, '')) = 'draft' THEN 'Draft'
                       WHEN a.is_active = 0 AND LOWER(COALESCE(a.status, '')) = 'hidden' THEN 'Hidden'
                       WHEN a.is_active = 0 AND LOWER(COALESCE(a.status, '')) = 'scheduled' THEN 'Scheduled'
                       WHEN a.is_active = 0 THEN 'Inactive'
                       WHEN a.due_date < datetime('now') THEN 'Overdue'
                       WHEN a.due_date > datetime('now', '+7 days') THEN 'Upcoming'
                       ELSE 'Active'
                   END as status
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
                 AND COALESCE(s.is_final_submission, 1) = 1 AND COALESCE(s.status, '') <> 'withdrawn'
            '''

            conditions = []
            params = []

            # Staff see the modules they teach; admins see them all.
            modules = self._visible_modules(conn)
            if modules is not None:
                clause, scope_params = staff_scope.sql_filter(modules)
                conditions.append("1 = 1" + clause)
                params.extend(scope_params)

            # Apply filters
            module_filter = self.manage_module_filter_var.get()
            if module_filter and module_filter != "All Modules":
                module_code = module_filter.split(' - ')[0]
                conditions.append("a.module_code = ?")
                params.append(module_code)

            status_filter = self.manage_status_filter_var.get()
            if status_filter != "All":
                if status_filter == "Active":
                    conditions.append("a.is_active = 1 AND a.due_date >= datetime('now')")
                elif status_filter == "Inactive":
                    conditions.append("a.is_active = 0")
                elif status_filter == "Upcoming":
                    conditions.append("a.due_date > datetime('now', '+7 days')")
                elif status_filter == "Overdue":
                    conditions.append("a.due_date < datetime('now') AND a.is_active = 1")

            search_term = self.manage_search_var.get().strip()
            if search_term:
                conditions.append("(a.title LIKE ? OR a.description LIKE ?)")
                params.extend([f"%{escape_like(search_term)}%", f"%{escape_like(search_term)}%"])

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " GROUP BY a.id ORDER BY a.due_date DESC"

            cursor.execute(query, params)
            assignments = cursor.fetchall()

            for assignment in assignments:
                aid, title, module, atype, due_date, submissions, status = assignment

                # Color coding
                tags = []
                if status in ('Inactive', 'Draft', 'Hidden', 'Scheduled'):
                    tags = ['inactive']
                elif status == 'Overdue':
                    tags = ['overdue']
                elif status == 'Upcoming':
                    tags = ['upcoming']

                self.manage_assignments_tree.insert('', 'end',
                                                   values=(aid, title, module, atype, due_date, submissions, status),
                                                   tags=tags)

            # Configure tags
            self.manage_assignments_tree.tag_configure('inactive', background='#f5f5f5', foreground='#666666')
            self.manage_assignments_tree.tag_configure('overdue', background='#ffebee')
            self.manage_assignments_tree.tag_configure('upcoming', background='#e3f2fd')

            conn.close()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.error', default="Error"), f"Failed to load assignments: {e}")


    def on_manage_assignment_select(self, event):
        """Handle assignment selection in management view"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            return

        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]

        self.show_assignment_management_details(assignment_id)


    def show_assignment_management_details(self, assignment_id):
        """Show detailed assignment information for management"""
        # Clear existing details
        for widget in self.assignment_details_frame.winfo_children():
            widget.destroy()

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT a.*, m.module_name,
                   COUNT(s.id) as total_submissions,
                   COUNT(CASE WHEN s.grade IS NOT NULL THEN 1 END) as graded_submissions,
                   COUNT(CASE WHEN s.late_submission = 1 THEN 1 END) as late_submissions,
                   AVG(s.grade) as avg_grade
            FROM assignments a
            JOIN modules m ON a.module_code = m.module_code
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
            WHERE a.id = ?
            GROUP BY a.id
            ''', (assignment_id,))

            assignment = cursor.fetchone()
            if not assignment:
                return

            # Create details display
            details_notebook = ttk.Notebook(self.assignment_details_frame)
            details_notebook.pack(fill='both', expand=True)

            # Basic info tab
            basic_frame = ttk.Frame(details_notebook)
            details_notebook.add(basic_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.tabs.basic_info', default="Basic Info"))

            # Display basic info
            ttk.Label(basic_frame, text=f"Title: {assignment[2]}").pack(pady=5)

            conn.close()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.error', default="Error"), f"Failed to load assignment details: {e}")

    def edit_selected_assignment(self):
        """Edit the selected assignment"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.assignment_manager.management.dialogs.please_select_an_assignment_to_edit', default="Please select an assignment to edit"))
            return

        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]

        try:
            # Fetch assignment data
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,))
            assignment = cursor.fetchone()
            assignment = dict(assignment) if assignment else None
            conn.close()

            if not assignment:
                messagebox.showerror(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.error', default="Error"), _t('gui.academics.assignment_system.assignment_manager.management.dialogs.assignment_not_found', default="Assignment not found"))
                return

            # Create edit window
            edit_window = make_toplevel(self.root)
            edit_window.title(f"Edit Assignment - {assignment['title']}")
            edit_window.geometry("700x700")
            edit_window.transient(self.root)
            edit_window.grab_set()

            # Scrollable frame
            canvas = tk.Canvas(edit_window)
            scrollbar = ttk.Scrollbar(edit_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Form fields
            form_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.assignment_details', default="Assignment Details"), padding=20)
            form_frame.pack(fill='x', padx=10, pady=10)

            # Title
            ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.title', default="Title:")).grid(row=0, column=0, sticky='w', pady=5)
            title_var = tk.StringVar(value=assignment['title'])
            ttk.Entry(form_frame, textvariable=title_var, width=50).grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))

            # Module
            ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.module', default="Module:")).grid(row=1, column=0, sticky='w', pady=5)
            module_var = tk.StringVar(value=assignment['module_code'])
            ttk.Label(form_frame, text=assignment['module_code']).grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))

            # Due Date
            ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.due_date_yyyy_mm_dd_hh_mm', default="Due Date (YYYY-MM-DD HH:MM):")).grid(row=2, column=0, sticky='w', pady=5)
            due_var = tk.StringVar(value=assignment['due_date'])
            attach_datetime(form_frame, id_var=due_var).grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))

            # Max Marks
            ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.max_marks', default="Max Marks:")).grid(row=3, column=0, sticky='w', pady=5)
            marks_var = tk.StringVar(value=str(assignment['max_marks']))
            ttk.Entry(form_frame, textvariable=marks_var, width=10).grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))

            # Description
            ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.description', default="Description:")).grid(row=4, column=0, sticky='nw', pady=5)
            desc_text = scrolledtext.ScrolledText(form_frame, height=5, width=50)
            desc_text.grid(row=4, column=1, sticky='ew', pady=5, padx=(10, 0))
            desc_text.insert('1.0', assignment['description'] or '')

            # Instructions
            ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.instructions', default="Instructions:")).grid(row=5, column=0, sticky='nw', pady=5)
            instr_text = scrolledtext.ScrolledText(form_frame, height=5, width=50)
            instr_text.grid(row=5, column=1, sticky='ew', pady=5, padx=(10, 0))
            instr_text.insert('1.0', assignment.get('instructions', ''))

            # Assignment Type
            ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.labels.type', default="Type:")).grid(row=6, column=0, sticky='w', pady=5)
            type_var = tk.StringVar(value=assignment.get('assignment_type', 'individual'))
            type_combo = ttk.Combobox(form_frame, textvariable=type_var,
                                     values=['individual', 'group'], state='readonly', width=15)
            type_combo.grid(row=6, column=1, sticky='w', pady=5, padx=(10, 0))

            form_frame.grid_columnconfigure(1, weight=1)

            # The same settings as Create Assignment
            settings = ttk.LabelFrame(scrollable_frame, text="Submission Settings", padding=10)
            settings.pack(fill='x', padx=10, pady=10)
            keys = assignment.keys()

            def saved(name, default=None):
                return assignment[name] if name in keys and assignment[name] is not None else default

            ttk.Label(settings, text="Visibility:").grid(row=0, column=0, sticky='w', pady=3)
            visibility_var = tk.StringVar(value=assignment_visibility.visibility_of(
                saved('status'), saved('is_active', 1)))
            ttk.Combobox(settings, textvariable=visibility_var, state='readonly', width=15,
                         values=list(assignment_visibility.VISIBILITIES)).grid(row=0, column=1, sticky='w')
            ttk.Label(settings, text="Opens On (scheduled):").grid(row=1, column=0, sticky='w', pady=3)
            opens_var = tk.StringVar(value=str(saved('available_from', ''))[:16])
            ttk.Entry(settings, textvariable=opens_var, width=18).grid(row=1, column=1, sticky='w')
            ttk.Label(settings, text="Max Late Days (0 = unlimited):").grid(row=2, column=0, sticky='w', pady=3)
            late_var = tk.StringVar(value=str(saved('max_late_days', 0)))
            ttk.Entry(settings, textvariable=late_var, width=8).grid(row=2, column=1, sticky='w')
            ttk.Label(settings, text="Max Attempts (0 = unlimited):").grid(row=3, column=0, sticky='w', pady=3)
            attempts_var = tk.StringVar(value=str(saved('max_attempts', 0)))
            ttk.Entry(settings, textvariable=attempts_var, width=8).grid(row=3, column=1, sticky='w')
            ttk.Label(settings, text="Reminder Before Due (days, 0 = none):").grid(row=4, column=0, sticky='w', pady=3)
            reminder_var = tk.StringVar(value=str(saved('reminder_days', 0)))
            ttk.Entry(settings, textvariable=reminder_var, width=8).grid(row=4, column=1, sticky='w')
            ttk.Label(settings, text="Course Weight (%):").grid(row=5, column=0, sticky='w', pady=3)
            weight_var = tk.StringVar(value=str(saved('module_weight_pct', 0)))
            ttk.Entry(settings, textvariable=weight_var, width=8).grid(row=5, column=1, sticky='w')
            rubric_map = self._load_rubric_choices()
            current_rubric = next((label for label, rid in rubric_map.items()
                                   if rid == saved('rubric_id')), "None")
            ttk.Label(settings, text="Rubric:").grid(row=6, column=0, sticky='w', pady=3)
            rubric_var = tk.StringVar(value=current_rubric)
            ttk.Combobox(settings, textvariable=rubric_var, state='readonly', width=30,
                         values=["None", *rubric_map]).grid(row=6, column=1, sticky='w')
            checks_var = tk.BooleanVar(value=bool(saved('automatic_checks', 1)))
            ttk.Checkbutton(settings, text="Enable Plagiarism Check",
                            variable=checks_var).grid(row=7, column=0, sticky='w', pady=3)
            notify_var = tk.BooleanVar(value=bool(saved('notify_on_submission', 1)))
            ttk.Checkbutton(settings, text="Email on submission",
                            variable=notify_var).grid(row=7, column=1, sticky='w', pady=3)

            def save_changes():
                try:
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    cursor.execute('''
                    UPDATE assignments
                    SET title = ?, due_date = ?, max_marks = ?, description = ?,
                        instructions = ?, assignment_type = ?, updated_at = datetime('now')
                    WHERE id = ?
                    ''', (
                        title_var.get().strip(),
                        due_var.get().strip(),
                        int(marks_var.get()),
                        desc_text.get('1.0', tk.END).strip(),
                        instr_text.get('1.0', tk.END).strip(),
                        type_var.get(),
                        assignment_id
                    ))

                    weight = float(weight_var.get() or 0)
                    if not 0 <= weight <= 100:
                        conn.close()
                        messagebox.showerror("Edit Assignment", "Course weight must be between 0 and 100")
                        return
                    cursor.execute(
                        "UPDATE assignments SET max_late_days = ?, max_attempts = ?, reminder_days = ?, "
                        "module_weight_pct = ?, rubric_id = ?, automatic_checks = ?, "
                        "notify_on_submission = ? WHERE id = ?",
                        (max(int(late_var.get() or 0), 0) or None,
                         max(int(attempts_var.get() or 0), 0) or None,
                         max(int(reminder_var.get() or 0), 0), weight or None,
                         rubric_map.get(rubric_var.get()), 1 if checks_var.get() else 0,
                         1 if notify_var.get() else 0, assignment_id))
                    was = assignment_visibility.visibility_of(saved('status'), saved('is_active', 1))
                    tell = False
                    if visibility_var.get() != was or visibility_var.get() == 'scheduled':
                        try:
                            tell = assignment_visibility.set_visibility(
                                conn, assignment_id, visibility_var.get(), opens_var.get())
                        except ValueError as e:
                            conn.close()
                            messagebox.showwarning("Edit Assignment", str(e))
                            return

                    conn.commit()
                    conn.close()
                    if tell:
                        assignment_runner.announce(assignment_id)

                    messagebox.showinfo(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.success', default="Success"), _t('gui.academics.assignment_system.assignment_manager.management.dialogs.assignment_updated_successfully', default="Assignment updated successfully"))
                    edit_window.destroy()
                    self.load_managed_assignments()

                except ValueError:
                    messagebox.showerror(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.error', default="Error"), _t('gui.academics.assignment_system.assignment_manager.management.dialogs.max_marks_must_be_a_valid_number', default="Max marks must be a valid number"))
                except Exception as e:
                    messagebox.showerror(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.error', default="Error"), f"Failed to update assignment: {e}")

            # Buttons
            button_frame = ttk.Frame(scrollable_frame)
            button_frame.pack(fill='x', padx=10, pady=10)
            ttk.Button(button_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.save_changes', default="Save Changes"), command=save_changes,
                      style='Accent.TButton').pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.cancel', default="Cancel"), command=edit_window.destroy).pack(side='right', padx=5)

            canvas.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.error', default="Error"), f"Failed to open edit window: {e}")

    def duplicate_selected_assignment(self):
        """Duplicate the selected assignment"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.assignment_manager.management.dialogs.please_select_an_assignment_to_duplicate', default="Please select an assignment to duplicate"))
            return

        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Temporarily disable foreign key checks to avoid module_code issues
            cursor.execute("PRAGMA foreign_keys = OFF")

            # Get original assignment with named columns
            cursor.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,))
            original = cursor.fetchone()

            if not original:
                messagebox.showerror(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.error', default="Error"), _t('gui.academics.assignment_system.assignment_manager.management.dialogs.assignment_not_found', default="Assignment not found"))
                conn.close()
                return

            # Helper to safely get column values with defaults
            cols = original.keys()
            def col(name, default=None):
                return original[name] if name in cols else default

            # Create duplicate
            new_title = f"{original['title']} (Copy)"
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO assignments
            (module_code, title, description, instructions, due_date, max_marks,
             file_types_allowed, max_file_size_mb, assignment_type,
             group_size_min, group_size_max, allow_late_submission,
             late_penalty_per_day, auto_release_grades, peer_review_enabled,
             rubric_id, is_active, status, created_by, created_at, updated_at,
             max_late_days, max_attempts, automatic_checks, notify_on_submission,
             reminder_days, module_weight_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                original['module_code'], new_title, original['description'],
                col('instructions', ''), original['due_date'],
                original['max_marks'], col('file_types_allowed', ''),
                col('max_file_size_mb', 10), col('assignment_type', 'individual'),
                col('group_size_min', 1), col('group_size_max', 1),
                col('allow_late_submission', 1), col('late_penalty_per_day', 0),
                col('auto_release_grades', 0), col('peer_review_enabled', 0),
                col('rubric_id'), self.auth.current_user['id'],
                timestamp, timestamp, col('max_late_days'), col('max_attempts'),
                col('automatic_checks', 1), col('notify_on_submission', 1),
                col('reminder_days', 2), col('module_weight_pct'),
            ))

            # Re-enable foreign key checks
            cursor.execute("PRAGMA foreign_keys = ON")

            conn.commit()
            conn.close()

            messagebox.showinfo(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.success', default="Success"), f"Assignment duplicated as '{new_title}'")
            self.load_managed_assignments()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.error', default="Error"), f"Failed to duplicate assignment: {e}")


    def toggle_assignment_status(self):
        """Toggle assignment active/inactive status"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.assignment_manager.management.dialogs.please_select_an_assignment', default="Please select an assignment"))
            return

        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]
        assignment_title = item['values'][1]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get current status
            cursor.execute('SELECT is_active FROM assignments WHERE id = ?', (assignment_id,))
            current_status = cursor.fetchone()[0]

            new_status = 0 if current_status else 1
            action = "activate" if new_status else "deactivate"

            if messagebox.askyesno(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.confirm', default="Confirm"), f"Are you sure you want to {action} '{assignment_title}'?"):
                self._apply_visibility(assignment_id, "published" if new_status else "hidden")

                messagebox.showinfo(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.success', default="Success"), f"Assignment {action}d successfully")
                self.load_managed_assignments()

            conn.close()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.error', default="Error"), f"Failed to toggle status: {e}")


    def view_assignment_submissions(self):
        """View submissions for selected assignment"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.assignment_manager.management.dialogs.please_select_an_assignment', default="Please select an assignment"))
            return

        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]

        # Switch to submissions view with filter
        self.show_assignment_specific_submissions(assignment_id)


    def show_assignment_specific_submissions(self, assignment_id):
        """Show submissions for a specific assignment"""
        self.gui.layout.clear_content_area()

        # Get assignment title
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT title FROM assignments WHERE id = ?', (assignment_id,))
            assignment_title = cursor.fetchone()[0]
            conn.close()
        except Exception:
            assignment_title = "Unknown Assignment"

        title = ttk.Label(self.gui.layout.content_area, text=f"Submissions: {assignment_title}", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Submissions table
        submissions_frame = ttk.Frame(self.gui.layout.content_area)
        submissions_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Student', 'Submitted', 'Status', 'Grade', 'Late')
        submissions_tree = ttk.Treeview(submissions_frame, columns=columns, show='headings')

        for col in columns:
            submissions_tree.heading(col, text=col)
            submissions_tree.column(col, width=120)

        submissions_tree.pack(fill='both', expand=True)

        # Load submissions for this assignment
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.id, st.first_name, st.last_name, s.submission_date, s.status,
                   CASE WHEN s.grade IS NULL THEN 'Not Graded' ELSE CAST(s.grade AS TEXT) || '%' END,
                   CASE WHEN s.late_submission = 1 THEN 'Yes' ELSE 'No' END
            FROM assignment_submissions s
            JOIN students st ON s.student_id = st.student_id
            WHERE s.assignment_id = ?
            ORDER BY s.submission_date DESC
            ''', (assignment_id,))

            submissions = cursor.fetchall()

            for submission in submissions:
                sid, fname, lname, date, status, grade, late = submission
                student_name = f"{fname} {lname}"

                tags = []
                if late == 'Yes':
                    tags = ['late']
                elif grade != 'Not Graded':
                    tags = ['graded']

                submissions_tree.insert('', 'end', values=(sid, student_name, date, status, grade, late), tags=tags)

            submissions_tree.tag_configure('late', background='#ffebee')
            submissions_tree.tag_configure('graded', background='#e8f5e8')

            conn.close()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.assignment_manager.management.dialogs.error', default="Error"), f"Failed to load submissions: {e}")

        # Back button
        ttk.Button(self.gui.layout.content_area, text=_t('gui.academics.assignment_system.assignment_manager.management.buttons.back_to_manage_assignments', default="Back to Manage Assignments"),
                  command=self.show_manage_assignments).pack(pady=(10, 0))
