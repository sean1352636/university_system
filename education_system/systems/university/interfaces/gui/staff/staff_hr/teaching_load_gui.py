"""
Teaching Load Management GUI

Provides interface for:
- Viewing personal teaching load summaries with bar chart
- Semester-by-semester comparison
- Release time management
- Department load overview (admin)
- Course assignment management (admin)
- Teaching load standards configuration (admin)
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.domain.staff.staff_hr.services.managers.teaching_load_manager import TeachingLoadManager
from education_system.systems.university.interfaces.gui.staff.staff_hr.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_combobox, validate_number_entry, validate_integer_entry,
    show_validation_error
)


class TeachingLoadGUI:
    """GUI for teaching load management."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Teaching Load Management")
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
        notebook.add(self.tab_frame, text="Teaching Load")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Teaching Load Management")
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

        self._create_my_load_tab()
        self._create_semester_comparison_tab()
        self._create_release_time_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_department_view_tab()
            self._create_course_assignments_tab()
            self._create_standards_tab()

    # ==================== TAB 1: MY TEACHING LOAD ====================

    def _create_my_load_tab(self):
        """Create my teaching load tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Teaching Load")

        # Header with filters
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="My Teaching Load", style='Header.TLabel').pack(side=tk.LEFT)

        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)

        ttk.Label(filter_frame, text="Year:").pack(side=tk.LEFT, padx=5)
        self.load_year_entry = ttk.Entry(filter_frame, width=12)
        self.load_year_entry.insert(0, "2025-2026")
        self.load_year_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="Semester:").pack(side=tk.LEFT, padx=5)
        self.load_semester_combo = ttk.Combobox(
            filter_frame, values=['Fall', 'Spring', 'Summer'],
            width=10, state='readonly'
        )
        self.load_semester_combo.set('Fall')
        self.load_semester_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(filter_frame, text="Load", command=self._load_my_teaching_load).pack(side=tk.LEFT, padx=5)

        # Scrollable content area
        canvas_outer = tk.Canvas(tab)
        scrollbar_outer = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas_outer.yview)
        self.load_scroll_frame = ttk.Frame(canvas_outer)

        self.load_scroll_frame.bind(
            '<Configure>', lambda e: canvas_outer.configure(scrollregion=canvas_outer.bbox('all')))
        canvas_outer.create_window((0, 0), window=self.load_scroll_frame, anchor='nw')
        canvas_outer.configure(yscrollcommand=scrollbar_outer.set)

        canvas_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_outer.pack(side=tk.RIGHT, fill=tk.Y)

        # Summary stat cards
        self.load_stats_frame = ttk.LabelFrame(self.load_scroll_frame, text="Load Summary", padding=10)
        self.load_stats_frame.pack(fill=tk.X, padx=10, pady=10)

        self.stat_total_courses = tk.StringVar(value="0")
        self.stat_total_credits = tk.StringVar(value="0")
        self.stat_net_load = tk.StringVar(value="0")
        self.stat_status = tk.StringVar(value="--")

        stats = [
            ("Total Courses", self.stat_total_courses),
            ("Total Credits", self.stat_total_credits),
            ("Net Load", self.stat_net_load),
            ("Status", self.stat_status),
        ]

        for col_idx, (label, var) in enumerate(stats):
            card = ttk.LabelFrame(self.load_stats_frame, text=label, padding=10)
            card.grid(row=0, column=col_idx, padx=10, pady=5, sticky='nsew')
            ttk.Label(card, textvariable=var, font=('Arial', 16, 'bold')).pack()
            self.load_stats_frame.columnconfigure(col_idx, weight=1)

        # Bar chart canvas
        self.chart_frame = ttk.LabelFrame(self.load_scroll_frame, text="Credit Hours by Course", padding=10)
        self.chart_frame.pack(fill=tk.X, padx=10, pady=10)

        self.load_chart_canvas = tk.Canvas(self.chart_frame, height=200, bg='white',
                                           highlightthickness=1, highlightbackground='#ccc')
        self.load_chart_canvas.pack(fill=tk.X, padx=5, pady=5)

        # Course assignments treeview
        tree_frame = ttk.Frame(self.load_scroll_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('Code', 'Name', 'Section', 'Credits', 'Contact Hrs', 'Students',
                   'Weighted', 'Status')
        self.load_courses_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.load_courses_tree.yview)

        widths = {'Code': 90, 'Name': 200, 'Section': 70, 'Credits': 70,
                  'Contact Hrs': 90, 'Students': 70, 'Weighted': 80, 'Status': 80}
        for col in columns:
            self.load_courses_tree.heading(col, text=col)
            self.load_courses_tree.column(col, width=widths.get(col, 80))

        self.load_courses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.load_courses_tree.tag_configure('active', background='#d4edda')
        self.load_courses_tree.tag_configure('overloaded', background='#f8d7da')

        self._load_my_teaching_load()

    def _load_my_teaching_load(self):
        """Load the current user's teaching load summary."""
        for item in self.load_courses_tree.get_children():
            self.load_courses_tree.delete(item)

        year = self.load_year_entry.get().strip()
        semester = self.load_semester_combo.get()
        user_id = self._get_user_id()

        try:
            summary = TeachingLoadManager.get_user_load_summary(user_id, year, semester)
        except Exception:
            summary = {}

        total_courses = summary.get('total_courses', 0) or 0
        total_credits = summary.get('total_credits', 0) or 0
        net_load = summary.get('net_load', 0) or 0
        standard_credits = summary.get('standard_credits', 12) or 12
        is_overloaded = net_load > standard_credits
        status_text = "Overloaded" if is_overloaded else "OK"

        self.stat_total_courses.set(str(total_courses))
        self.stat_total_credits.set(str(total_credits))
        self.stat_net_load.set(str(net_load))
        self.stat_status.set(status_text)

        # Draw bar chart
        courses = summary.get('courses', [])
        self._draw_load_bar_chart(courses, standard_credits)

        # Populate treeview
        for c in courses:
            status = c.get('status', 'active')
            tag = 'active'
            self.load_courses_tree.insert('', tk.END, values=(
                c.get('course_code', ''),
                c.get('course_name', ''),
                c.get('section', ''),
                c.get('credit_hours', ''),
                c.get('contact_hours', ''),
                c.get('enrolled_students', ''),
                c.get('weighted_credits', ''),
                status.replace('_', ' ').title()
            ), tags=(tag,))

    def _draw_load_bar_chart(self, courses, standard_credits):
        """Draw horizontal bar chart of credit hours per course on the canvas."""
        self.load_chart_canvas.delete('all')

        if not courses:
            self.load_chart_canvas.create_text(
                400, 100, text="No course data available",
                font=('Arial', 12), fill='#999')
            return

        canvas_width = self.load_chart_canvas.winfo_width()
        if canvas_width < 100:
            canvas_width = 800

        bar_height = 25
        bar_gap = 8
        left_margin = 160
        right_margin = 60
        top_margin = 20
        chart_width = canvas_width - left_margin - right_margin

        # Find max credit value for scaling
        max_credits = max(
            (float(c.get('credit_hours', 0) or 0) for c in courses),
            default=1
        )
        max_val = max(max_credits, float(standard_credits), 1)

        total_height = top_margin + len(courses) * (bar_height + bar_gap) + 30
        self.load_chart_canvas.config(height=max(total_height, 150))

        # Color palette for bars
        colors = ['#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
                  '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac']

        for i, course in enumerate(courses):
            credit_val = float(course.get('credit_hours', 0) or 0)
            bar_width = (credit_val / max_val) * chart_width if max_val > 0 else 0

            y_top = top_margin + i * (bar_height + bar_gap)
            y_bottom = y_top + bar_height

            color = colors[i % len(colors)]

            # Course label
            label = course.get('course_code', 'N/A')
            self.load_chart_canvas.create_text(
                left_margin - 10, y_top + bar_height // 2,
                text=label, anchor='e', font=('Arial', 9))

            # Bar rectangle
            self.load_chart_canvas.create_rectangle(
                left_margin, y_top, left_margin + bar_width, y_bottom,
                fill=color, outline='')

            # Credit value label on bar
            self.load_chart_canvas.create_text(
                left_margin + bar_width + 5, y_top + bar_height // 2,
                text=str(credit_val), anchor='w', font=('Arial', 9, 'bold'))

        # Draw standard credits threshold line (vertical red dashed line)
        if standard_credits and max_val > 0:
            threshold_x = left_margin + (float(standard_credits) / max_val) * chart_width
            chart_bottom = top_margin + len(courses) * (bar_height + bar_gap)
            self.load_chart_canvas.create_line(
                threshold_x, top_margin - 5, threshold_x, chart_bottom + 5,
                fill='red', dash=(4, 4), width=2)
            self.load_chart_canvas.create_text(
                threshold_x, top_margin - 10,
                text=f"Std: {standard_credits}", anchor='s',
                font=('Arial', 8), fill='red')

    # ==================== TAB 2: SEMESTER COMPARISON ====================

    def _create_semester_comparison_tab(self):
        """Create semester comparison tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Semester Comparison")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Semester Comparison", style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Refresh", command=self._load_semester_comparison).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Snapshot Current",
                   command=self._snapshot_semester).pack(side=tk.LEFT, padx=5)

        # Semester comparison treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('Year', 'Semester', 'Courses', 'Credits', 'Contact Hrs',
                   'Students', 'Release', 'Net Load', 'Overloaded')
        self.semester_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.semester_tree.yview)

        widths = {'Year': 100, 'Semester': 80, 'Courses': 70, 'Credits': 70,
                  'Contact Hrs': 90, 'Students': 70, 'Release': 70,
                  'Net Load': 80, 'Overloaded': 80}
        for col in columns:
            self.semester_tree.heading(col, text=col)
            self.semester_tree.column(col, width=widths.get(col, 80))

        self.semester_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Color tags
        self.semester_tree.tag_configure('overloaded', background='#f8d7da')
        self.semester_tree.tag_configure('normal', background='#d4edda')

        self._load_semester_comparison()

    def _load_semester_comparison(self):
        """Load semester comparison data."""
        for item in self.semester_tree.get_children():
            self.semester_tree.delete(item)

        user_id = self._get_user_id()

        try:
            semesters = TeachingLoadManager.get_semester_comparison(user_id)
        except Exception:
            semesters = []

        for s in semesters:
            is_overloaded = s.get('is_overloaded', False)
            overloaded_text = 'Yes' if is_overloaded else 'No'
            tag = 'overloaded' if is_overloaded else 'normal'

            self.semester_tree.insert('', tk.END, values=(
                s.get('academic_year', ''),
                s.get('semester', ''),
                s.get('total_courses', 0),
                s.get('total_credits', 0),
                s.get('contact_hours', 0),
                s.get('total_students', 0),
                s.get('release_credits', 0),
                s.get('net_load', 0),
                overloaded_text
            ), tags=(tag,))

    def _snapshot_semester(self):
        """Take a snapshot of the current semester's load."""
        year = self.load_year_entry.get().strip() if hasattr(self, 'load_year_entry') else '2025-2026'
        semester = self.load_semester_combo.get() if hasattr(self, 'load_semester_combo') else 'Fall'
        user_id = self._get_user_id()

        if not messagebox.askyesno("Confirm",
                                    f"Snapshot current load for {year} {semester}?"):
            return

        try:
            TeachingLoadManager.snapshot_semester(
                user_id=user_id,
                academic_year=year,
                semester=semester
            )
            messagebox.showinfo("Success", "Semester snapshot saved.")
            self._load_semester_comparison()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 3: RELEASE TIME ====================

    def _create_release_time_tab(self):
        """Create release time tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Release Time")

        # Header with filters
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Release Time", style='Header.TLabel').pack(side=tk.LEFT)

        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)

        ttk.Label(filter_frame, text="Year:").pack(side=tk.LEFT, padx=5)
        self.release_year_entry = ttk.Entry(filter_frame, width=12)
        self.release_year_entry.insert(0, "2025-2026")
        self.release_year_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="Semester:").pack(side=tk.LEFT, padx=5)
        self.release_semester_combo = ttk.Combobox(
            filter_frame, values=['', 'Fall', 'Spring', 'Summer'],
            width=10, state='readonly'
        )
        self.release_semester_combo.set('')
        self.release_semester_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(filter_frame, text="Refresh", command=self._load_release_time).pack(side=tk.LEFT, padx=5)

        # Release time treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Type', 'Title', 'Hours/Week', 'Credit Equiv', 'Status', 'Approved By')
        self.release_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.release_tree.yview)

        widths = {'ID': 50, 'Type': 120, 'Title': 200, 'Hours/Week': 90,
                  'Credit Equiv': 90, 'Status': 80, 'Approved By': 120}
        for col in columns:
            self.release_tree.heading(col, text=col)
            self.release_tree.column(col, width=widths.get(col, 80))

        self.release_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.release_tree.tag_configure('approved', background='#d4edda')
        self.release_tree.tag_configure('pending', background='#fff3cd')
        self.release_tree.tag_configure('denied', background='#f8d7da')

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Add Release",
                   command=self._add_release_time_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit",
                   command=self._edit_release_time_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete",
                   command=self._delete_release_time).pack(side=tk.LEFT, padx=5)

        self._load_release_time()

    def _load_release_time(self):
        """Load release time entries."""
        for item in self.release_tree.get_children():
            self.release_tree.delete(item)

        user_id = self._get_user_id()
        year = self.release_year_entry.get().strip() or None
        semester = self.release_semester_combo.get() or None

        try:
            releases = TeachingLoadManager.get_release_time(
                user_id=user_id, academic_year=year, semester=semester)
        except Exception:
            releases = []

        for r in releases:
            status = r.get('status', 'pending').lower()
            display_type = r.get('release_type', '').replace('_', ' ').title()
            display_status = status.replace('_', ' ').title()

            self.release_tree.insert('', tk.END, values=(
                r.get('id', ''),
                display_type,
                r.get('title', ''),
                r.get('hours_per_week', ''),
                r.get('credit_equivalent', ''),
                display_status,
                r.get('approved_by', '') or ''
            ), tags=(status,))

    def _add_release_time_dialog(self):
        """Open dialog to add release time."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Release Time")
        dialog.geometry("500x550")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Type
        ttk.Label(frame, text="Type:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        type_combo = ttk.Combobox(
            frame, values=['research_grant', 'admin_duty', 'sabbatical',
                           'department_chair', 'program_director',
                           'course_development', 'other'],
            width=25, state='readonly'
        )
        type_combo.set('research_grant')
        type_combo.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        # Title
        ttk.Label(frame, text="Title:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        title_entry = ttk.Entry(frame, width=30)
        title_entry.grid(row=1, column=1, padx=10, pady=8)

        # Hours per week
        ttk.Label(frame, text="Hours/Week:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        hours_entry = ttk.Entry(frame, width=10)
        hours_entry.insert(0, "0")
        hours_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Credit equivalent
        ttk.Label(frame, text="Credit Equiv:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        credit_entry = ttk.Entry(frame, width=10)
        credit_entry.insert(0, "3")
        credit_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Start date
        ttk.Label(frame, text="Start Date (YYYY-MM-DD):").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        start_entry = ttk.Entry(frame, width=15)
        start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        start_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # End date
        ttk.Label(frame, text="End Date (YYYY-MM-DD):").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        end_entry = ttk.Entry(frame, width=15)
        end_entry.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Funding source
        ttk.Label(frame, text="Funding Source:").grid(row=6, column=0, sticky='e', padx=10, pady=8)
        funding_entry = ttk.Entry(frame, width=30)
        funding_entry.grid(row=6, column=1, padx=10, pady=8)

        # Notes
        ttk.Label(frame, text="Notes:").grid(row=7, column=0, sticky='ne', padx=10, pady=8)
        notes_text = tk.Text(frame, width=30, height=3)
        notes_text.grid(row=7, column=1, padx=10, pady=8)

        def save():
            try:
                release_type = validate_combobox(type_combo, "Type")
                title = validate_entry(title_entry, "Title")
                hours = validate_number_entry(hours_entry, "Hours/Week", min_value=0)
                credit_equiv = validate_number_entry(credit_entry, "Credit Equivalent", min_value=0)
                start_date = validate_date_entry(start_entry, "Start Date")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            end_date = end_entry.get().strip() or None
            if end_date:
                try:
                    validate_date_entry(end_entry, "End Date")
                except ValidationError as e:
                    show_validation_error(e, dialog)
                    return

            funding_source = funding_entry.get().strip() or None
            notes = notes_text.get("1.0", "end-1c").strip() or None

            try:
                release_id = TeachingLoadManager.add_release_time(
                    user_id=self._get_user_id(),
                    release_type=release_type,
                    title=title,
                    hours_per_week=hours,
                    credit_equivalent=credit_equiv,
                    start_date=start_date,
                    end_date=end_date,
                    funding_source=funding_source,
                    notes=notes,
                    academic_year=self.release_year_entry.get().strip() or None,
                    semester=self.release_semester_combo.get() or None
                )
                messagebox.showinfo("Success",
                                    f"Release time added. ID: {release_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_release_time()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=8, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Add", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        title_entry.focus_set()

    def _edit_release_time_dialog(self):
        """Open dialog to edit selected release time entry."""
        selection = self.release_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a release time entry to edit.")
            return

        item = self.release_tree.item(selection[0])
        values = item['values']
        release_id = values[0]

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Release Time")
        dialog.geometry("500x550")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Type
        ttk.Label(frame, text="Type:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        type_combo = ttk.Combobox(
            frame, values=['research_grant', 'admin_duty', 'sabbatical',
                           'department_chair', 'program_director',
                           'course_development', 'other'],
            width=25, state='readonly'
        )
        current_type = str(values[1]).lower().replace(' ', '_')
        type_combo.set(current_type)
        type_combo.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        # Title
        ttk.Label(frame, text="Title:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        title_entry = ttk.Entry(frame, width=30)
        title_entry.insert(0, str(values[2]))
        title_entry.grid(row=1, column=1, padx=10, pady=8)

        # Hours per week
        ttk.Label(frame, text="Hours/Week:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        hours_entry = ttk.Entry(frame, width=10)
        hours_entry.insert(0, str(values[3]))
        hours_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Credit equivalent
        ttk.Label(frame, text="Credit Equiv:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        credit_entry = ttk.Entry(frame, width=10)
        credit_entry.insert(0, str(values[4]))
        credit_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Status
        ttk.Label(frame, text="Status:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        status_combo = ttk.Combobox(
            frame, values=['pending', 'approved', 'denied'],
            width=15, state='readonly'
        )
        current_status = str(values[5]).lower().replace(' ', '_')
        status_combo.set(current_status)
        status_combo.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        def save():
            try:
                release_type = validate_combobox(type_combo, "Type")
                title = validate_entry(title_entry, "Title")
                hours = validate_number_entry(hours_entry, "Hours/Week", min_value=0)
                credit_equiv = validate_number_entry(credit_entry, "Credit Equivalent", min_value=0)
                status = validate_combobox(status_combo, "Status")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                TeachingLoadManager.update_release_time(
                    release_id=release_id,
                    release_type=release_type,
                    title=title,
                    hours_per_week=hours,
                    credit_equivalent=credit_equiv,
                    status=status
                )
                messagebox.showinfo("Success", "Release time updated.", parent=dialog)
                dialog.destroy()
                self._load_release_time()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        title_entry.focus_set()

    def _delete_release_time(self):
        """Delete the selected release time entry."""
        selection = self.release_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a release time entry to delete.")
            return

        item = self.release_tree.item(selection[0])
        release_id = item['values'][0]

        if not messagebox.askyesno("Confirm",
                                    f"Delete release time entry #{release_id}?"):
            return

        try:
            TeachingLoadManager.delete_release_time(release_id)
            messagebox.showinfo("Success", "Release time entry deleted.")
            self._load_release_time()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 4: DEPARTMENT VIEW (admin) ====================

    def _create_department_view_tab(self):
        """Create department view tab (admin only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Department View")

        # Header with filters
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Department Teaching Loads", style='Header.TLabel').pack(side=tk.LEFT)

        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)

        ttk.Label(filter_frame, text="Department:").pack(side=tk.LEFT, padx=5)
        self.dept_view_dept_entry = ttk.Entry(filter_frame, width=20)
        self.dept_view_dept_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="Year:").pack(side=tk.LEFT, padx=5)
        self.dept_view_year_entry = ttk.Entry(filter_frame, width=12)
        self.dept_view_year_entry.insert(0, "2025-2026")
        self.dept_view_year_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="Semester:").pack(side=tk.LEFT, padx=5)
        self.dept_view_semester_combo = ttk.Combobox(
            filter_frame, values=['Fall', 'Spring', 'Summer'],
            width=10, state='readonly'
        )
        self.dept_view_semester_combo.set('Fall')
        self.dept_view_semester_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(filter_frame, text="Load",
                   command=self._load_department_view).pack(side=tk.LEFT, padx=5)

        # Department loads treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('User ID', 'Courses', 'Credits', 'Net Load', 'Overloaded')
        self.dept_loads_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.dept_loads_tree.yview)

        widths = {'User ID': 200, 'Courses': 80, 'Credits': 80,
                  'Net Load': 80, 'Overloaded': 80}
        for col in columns:
            self.dept_loads_tree.heading(col, text=col)
            self.dept_loads_tree.column(col, width=widths.get(col, 80))

        self.dept_loads_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.dept_loads_tree.tag_configure('overloaded', background='#f8d7da')
        self.dept_loads_tree.tag_configure('normal', background='#d4edda')

        # Suggestions button
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Suggestions",
                   command=self._show_load_balance_suggestions).pack(side=tk.LEFT, padx=5)

    def _load_department_view(self):
        """Load department teaching loads."""
        for item in self.dept_loads_tree.get_children():
            self.dept_loads_tree.delete(item)

        department = self.dept_view_dept_entry.get().strip()
        if not department:
            messagebox.showinfo("Info", "Please enter a department name.")
            return

        year = self.dept_view_year_entry.get().strip()
        semester = self.dept_view_semester_combo.get()

        try:
            loads = TeachingLoadManager.get_department_loads(
                department=department, academic_year=year, semester=semester)
        except Exception:
            loads = []

        for load in loads:
            is_overloaded = load.get('is_overloaded', False)
            overloaded_text = 'Yes' if is_overloaded else 'No'
            tag = 'overloaded' if is_overloaded else 'normal'

            self.dept_loads_tree.insert('', tk.END, values=(
                load.get('user_id', ''),
                load.get('total_courses', 0),
                load.get('total_credits', 0),
                load.get('net_load', 0),
                overloaded_text
            ), tags=(tag,))

    def _show_load_balance_suggestions(self):
        """Show load balance suggestions in a dialog."""
        department = self.dept_view_dept_entry.get().strip()
        if not department:
            messagebox.showinfo("Info", "Please enter a department and load data first.")
            return

        year = self.dept_view_year_entry.get().strip()
        semester = self.dept_view_semester_combo.get()

        try:
            suggestions = TeachingLoadManager.get_load_balance_suggestions(
                department=department, academic_year=year, semester=semester)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load suggestions: {e}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Load Balance Suggestions")
        dialog.geometry("700x500")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Load Balance Suggestions - {department}",
                  font=('Arial', 12, 'bold')).pack(anchor='w', pady=(0, 10))

        if not suggestions:
            ttk.Label(frame, text="No suggestions available. Load is balanced.",
                      font=('Arial', 10)).pack(anchor='w', pady=10)
        else:
            # Suggestions treeview
            tree_frame = ttk.Frame(frame)
            tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)

            y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
            columns = ('Priority', 'Type', 'Description', 'From', 'To')
            suggestion_tree = ttk.Treeview(
                tree_frame, columns=columns, show='headings',
                yscrollcommand=y_scroll.set)
            y_scroll.config(command=suggestion_tree.yview)

            s_widths = {'Priority': 70, 'Type': 100, 'Description': 300,
                        'From': 100, 'To': 100}
            for col in columns:
                suggestion_tree.heading(col, text=col)
                suggestion_tree.column(col, width=s_widths.get(col, 100))

            suggestion_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

            for s in suggestions:
                suggestion_tree.insert('', tk.END, values=(
                    s.get('priority', ''),
                    s.get('suggestion_type', '').replace('_', ' ').title(),
                    s.get('description', ''),
                    s.get('from_user', ''),
                    s.get('to_user', '')
                ))

        # Close button
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # ==================== TAB 5: COURSE ASSIGNMENTS (admin) ====================

    def _create_course_assignments_tab(self):
        """Create course assignments admin tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Course Assignments")

        # Header with search filters
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Course Assignments", style='Header.TLabel').pack(side=tk.LEFT)

        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)

        ttk.Label(filter_frame, text="User ID:").pack(side=tk.LEFT, padx=5)
        self.assign_user_entry = ttk.Entry(filter_frame, width=15)
        self.assign_user_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="Year:").pack(side=tk.LEFT, padx=5)
        self.assign_year_entry = ttk.Entry(filter_frame, width=12)
        self.assign_year_entry.insert(0, "2025-2026")
        self.assign_year_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="Semester:").pack(side=tk.LEFT, padx=5)
        self.assign_semester_combo = ttk.Combobox(
            filter_frame, values=['Fall', 'Spring', 'Summer'],
            width=10, state='readonly'
        )
        self.assign_semester_combo.set('Fall')
        self.assign_semester_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(filter_frame, text="Search",
                   command=self._load_course_assignments).pack(side=tk.LEFT, padx=5)

        # Assignments treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Code', 'Name', 'Section', 'Credits', 'Students',
                   'Weighted', 'Status')
        self.assignments_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.assignments_tree.yview)

        widths = {'ID': 50, 'Code': 90, 'Name': 200, 'Section': 70,
                  'Credits': 70, 'Students': 70, 'Weighted': 80, 'Status': 80}
        for col in columns:
            self.assignments_tree.heading(col, text=col)
            self.assignments_tree.column(col, width=widths.get(col, 80))

        self.assignments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.assignments_tree.tag_configure('active', background='#d4edda')
        self.assignments_tree.tag_configure('cancelled', background='#f8d7da')

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Add",
                   command=self._add_assignment_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit",
                   command=self._edit_assignment_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete",
                   command=self._delete_assignment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Import CSV",
                   command=self._import_csv_dialog).pack(side=tk.LEFT, padx=5)

    def _load_course_assignments(self):
        """Load course assignments for the specified user."""
        for item in self.assignments_tree.get_children():
            self.assignments_tree.delete(item)

        user_id = self.assign_user_entry.get().strip()
        if not user_id:
            messagebox.showinfo("Info", "Please enter a User ID to search.")
            return

        year = self.assign_year_entry.get().strip()
        semester = self.assign_semester_combo.get()

        try:
            assignments = TeachingLoadManager.get_user_course_assignments(
                user_id=user_id, academic_year=year, semester=semester)
        except Exception:
            assignments = []

        for a in assignments:
            status = a.get('status', 'active').lower()
            tag = 'cancelled' if status == 'cancelled' else 'active'

            self.assignments_tree.insert('', tk.END, values=(
                a.get('id', ''),
                a.get('course_code', ''),
                a.get('course_name', ''),
                a.get('section', ''),
                a.get('credit_hours', ''),
                a.get('enrolled_students', ''),
                a.get('weighted_credits', ''),
                status.replace('_', ' ').title()
            ), tags=(tag,))

    def _add_assignment_dialog(self):
        """Open dialog to add a course assignment."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Course Assignment")
        dialog.geometry("500x600")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # User ID
        ttk.Label(frame, text="User ID:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        user_entry = ttk.Entry(frame, width=25)
        user_val = self.assign_user_entry.get().strip()
        if user_val:
            user_entry.insert(0, user_val)
        user_entry.grid(row=0, column=1, padx=10, pady=8)

        # Course code
        ttk.Label(frame, text="Course Code:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        code_entry = ttk.Entry(frame, width=15)
        code_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        # Course name
        ttk.Label(frame, text="Course Name:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        name_entry = ttk.Entry(frame, width=30)
        name_entry.grid(row=2, column=1, padx=10, pady=8)

        # Section
        ttk.Label(frame, text="Section:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        section_entry = ttk.Entry(frame, width=10)
        section_entry.insert(0, "001")
        section_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Credits
        ttk.Label(frame, text="Credits:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        credits_entry = ttk.Entry(frame, width=10)
        credits_entry.insert(0, "3")
        credits_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Contact hours
        ttk.Label(frame, text="Contact Hours:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        contact_entry = ttk.Entry(frame, width=10)
        contact_entry.insert(0, "3")
        contact_entry.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Enrolled students
        ttk.Label(frame, text="Enrolled Students:").grid(row=6, column=0, sticky='e', padx=10, pady=8)
        enrolled_entry = ttk.Entry(frame, width=10)
        enrolled_entry.insert(0, "30")
        enrolled_entry.grid(row=6, column=1, padx=10, pady=8, sticky='w')

        # Department
        ttk.Label(frame, text="Department:").grid(row=7, column=0, sticky='e', padx=10, pady=8)
        dept_entry = ttk.Entry(frame, width=25)
        dept_entry.grid(row=7, column=1, padx=10, pady=8)

        # Is new prep
        new_prep_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="New Prep", variable=new_prep_var).grid(
            row=8, column=1, padx=10, pady=4, sticky='w')

        # Is team taught
        team_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Team Taught", variable=team_var).grid(
            row=9, column=1, padx=10, pady=4, sticky='w')

        # Team share percentage
        ttk.Label(frame, text="Team Share %:").grid(row=10, column=0, sticky='e', padx=10, pady=8)
        share_entry = ttk.Entry(frame, width=10)
        share_entry.insert(0, "100")
        share_entry.grid(row=10, column=1, padx=10, pady=8, sticky='w')

        def save():
            try:
                uid = validate_entry(user_entry, "User ID")
                course_code = validate_entry(code_entry, "Course Code")
                course_name = validate_entry(name_entry, "Course Name")
                section = validate_entry(section_entry, "Section")
                credits = validate_number_entry(credits_entry, "Credits", min_value=0)
                contact_hours = validate_number_entry(contact_entry, "Contact Hours", min_value=0)
                enrolled = validate_integer_entry(enrolled_entry, "Enrolled Students", min_value=0)
                share_pct = validate_number_entry(share_entry, "Team Share %",
                                                   min_value=0, max_value=100)
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            department = dept_entry.get().strip() or None

            try:
                assignment_id = TeachingLoadManager.add_course_assignment(
                    user_id=uid,
                    course_code=course_code,
                    course_name=course_name,
                    section=section,
                    credit_hours=credits,
                    contact_hours=contact_hours,
                    enrolled_students=enrolled,
                    department=department,
                    is_new_prep=new_prep_var.get(),
                    is_team_taught=team_var.get(),
                    team_share_pct=share_pct,
                    academic_year=self.assign_year_entry.get().strip() or None,
                    semester=self.assign_semester_combo.get() or None
                )
                messagebox.showinfo("Success",
                                    f"Course assignment added. ID: {assignment_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_course_assignments()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=11, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Add", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        code_entry.focus_set()

    def _edit_assignment_dialog(self):
        """Open dialog to edit the selected course assignment."""
        selection = self.assignments_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an assignment to edit.")
            return

        item = self.assignments_tree.item(selection[0])
        values = item['values']
        assignment_id = values[0]

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Course Assignment")
        dialog.geometry("500x500")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Course code
        ttk.Label(frame, text="Course Code:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        code_entry = ttk.Entry(frame, width=15)
        code_entry.insert(0, str(values[1]))
        code_entry.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        # Course name
        ttk.Label(frame, text="Course Name:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        name_entry = ttk.Entry(frame, width=30)
        name_entry.insert(0, str(values[2]))
        name_entry.grid(row=1, column=1, padx=10, pady=8)

        # Section
        ttk.Label(frame, text="Section:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        section_entry = ttk.Entry(frame, width=10)
        section_entry.insert(0, str(values[3]))
        section_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Credits
        ttk.Label(frame, text="Credits:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        credits_entry = ttk.Entry(frame, width=10)
        credits_entry.insert(0, str(values[4]))
        credits_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Enrolled students
        ttk.Label(frame, text="Enrolled Students:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        enrolled_entry = ttk.Entry(frame, width=10)
        enrolled_entry.insert(0, str(values[5]))
        enrolled_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Status
        ttk.Label(frame, text="Status:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        status_combo = ttk.Combobox(
            frame, values=['active', 'cancelled', 'completed'],
            width=15, state='readonly'
        )
        current_status = str(values[7]).lower().replace(' ', '_')
        status_combo.set(current_status)
        status_combo.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        def save():
            try:
                course_code = validate_entry(code_entry, "Course Code")
                course_name = validate_entry(name_entry, "Course Name")
                section = validate_entry(section_entry, "Section")
                credits = validate_number_entry(credits_entry, "Credits", min_value=0)
                enrolled = validate_integer_entry(enrolled_entry, "Enrolled Students", min_value=0)
                status = validate_combobox(status_combo, "Status")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                TeachingLoadManager.update_course_assignment(
                    assignment_id=assignment_id,
                    course_code=course_code,
                    course_name=course_name,
                    section=section,
                    credit_hours=credits,
                    enrolled_students=enrolled,
                    status=status
                )
                messagebox.showinfo("Success", "Assignment updated.", parent=dialog)
                dialog.destroy()
                self._load_course_assignments()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        code_entry.focus_set()

    def _delete_assignment(self):
        """Delete the selected course assignment."""
        selection = self.assignments_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an assignment to delete.")
            return

        item = self.assignments_tree.item(selection[0])
        assignment_id = item['values'][0]

        if not messagebox.askyesno("Confirm",
                                    f"Delete course assignment #{assignment_id}?"):
            return

        try:
            TeachingLoadManager.delete_course_assignment(assignment_id)
            messagebox.showinfo("Success", "Course assignment deleted.")
            self._load_course_assignments()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _import_csv_dialog(self):
        """Open dialog to import course assignments from CSV."""
        from tkinter import filedialog

        file_path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            parent=self.root
        )

        if not file_path:
            return

        year = self.assign_year_entry.get().strip() or None
        semester = self.assign_semester_combo.get() or None

        try:
            result = TeachingLoadManager.import_course_assignments(
                file_path=file_path,
                academic_year=year,
                semester=semester
            )
            imported = result.get('imported', 0) if isinstance(result, dict) else result
            messagebox.showinfo("Success", f"Imported {imported} course assignments.")
            self._load_course_assignments()
        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {e}")

    # ==================== TAB 6: STANDARDS (admin) ====================

    def _create_standards_tab(self):
        """Create teaching load standards admin tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Standards")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Teaching Load Standards", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh",
                   command=self._load_standards).pack(side=tk.RIGHT, padx=5)

        # Standards treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Department', 'Role', 'Std Credits', 'Std Courses',
                   'Max Credits', 'Max New Preps')
        self.standards_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.standards_tree.yview)

        widths = {'ID': 50, 'Department': 150, 'Role': 120, 'Std Credits': 90,
                  'Std Courses': 90, 'Max Credits': 90, 'Max New Preps': 100}
        for col in columns:
            self.standards_tree.heading(col, text=col)
            self.standards_tree.column(col, width=widths.get(col, 80))

        self.standards_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Add",
                   command=self._add_standard_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit",
                   command=self._edit_standard_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete",
                   command=self._delete_standard).pack(side=tk.LEFT, padx=5)

        self._load_standards()

    def _load_standards(self):
        """Load teaching load standards."""
        for item in self.standards_tree.get_children():
            self.standards_tree.delete(item)

        try:
            standards = TeachingLoadManager.get_standards()
        except Exception:
            standards = []

        for s in standards:
            self.standards_tree.insert('', tk.END, values=(
                s.get('id', ''),
                s.get('department', ''),
                s.get('role', ''),
                s.get('standard_credits', ''),
                s.get('standard_courses', ''),
                s.get('max_credits', ''),
                s.get('max_new_preps', '')
            ))

    def _add_standard_dialog(self):
        """Open dialog to add a teaching load standard."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Teaching Load Standard")
        dialog.geometry("500x550")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Department
        ttk.Label(frame, text="Department:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        dept_entry = ttk.Entry(frame, width=25)
        dept_entry.grid(row=0, column=1, padx=10, pady=8)

        # Role
        ttk.Label(frame, text="Role:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        role_entry = ttk.Entry(frame, width=25)
        role_entry.grid(row=1, column=1, padx=10, pady=8)

        # Standard credits
        ttk.Label(frame, text="Standard Credits:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        std_credits_entry = ttk.Entry(frame, width=10)
        std_credits_entry.insert(0, "12")
        std_credits_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Standard courses
        ttk.Label(frame, text="Standard Courses:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        std_courses_entry = ttk.Entry(frame, width=10)
        std_courses_entry.insert(0, "4")
        std_courses_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Max credits
        ttk.Label(frame, text="Max Credits:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        max_credits_entry = ttk.Entry(frame, width=10)
        max_credits_entry.insert(0, "15")
        max_credits_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Max new preps
        ttk.Label(frame, text="Max New Preps:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        max_preps_entry = ttk.Entry(frame, width=10)
        max_preps_entry.insert(0, "2")
        max_preps_entry.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Large class threshold
        ttk.Label(frame, text="Large Class Threshold:").grid(row=6, column=0, sticky='e', padx=10, pady=8)
        threshold_entry = ttk.Entry(frame, width=10)
        threshold_entry.insert(0, "50")
        threshold_entry.grid(row=6, column=1, padx=10, pady=8, sticky='w')

        # Large class factor
        ttk.Label(frame, text="Large Class Factor:").grid(row=7, column=0, sticky='e', padx=10, pady=8)
        factor_entry = ttk.Entry(frame, width=10)
        factor_entry.insert(0, "1.5")
        factor_entry.grid(row=7, column=1, padx=10, pady=8, sticky='w')

        # Overload rate
        ttk.Label(frame, text="Overload Rate:").grid(row=8, column=0, sticky='e', padx=10, pady=8)
        rate_entry = ttk.Entry(frame, width=10)
        rate_entry.insert(0, "0")
        rate_entry.grid(row=8, column=1, padx=10, pady=8, sticky='w')

        def save():
            try:
                department = validate_entry(dept_entry, "Department")
                role = validate_entry(role_entry, "Role")
                std_credits = validate_number_entry(std_credits_entry, "Standard Credits", min_value=0)
                std_courses = validate_integer_entry(std_courses_entry, "Standard Courses", min_value=0)
                max_credits = validate_number_entry(max_credits_entry, "Max Credits", min_value=0)
                max_preps = validate_integer_entry(max_preps_entry, "Max New Preps", min_value=0)
                threshold = validate_integer_entry(threshold_entry, "Large Class Threshold", min_value=0)
                factor = validate_number_entry(factor_entry, "Large Class Factor", min_value=0)
                overload_rate = validate_number_entry(rate_entry, "Overload Rate", min_value=0)
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                standard_id = TeachingLoadManager.create_standard(
                    department=department,
                    role=role,
                    standard_credits=std_credits,
                    standard_courses=std_courses,
                    max_credits=max_credits,
                    max_new_preps=max_preps,
                    large_class_threshold=threshold,
                    large_class_factor=factor,
                    overload_rate=overload_rate
                )
                messagebox.showinfo("Success",
                                    f"Standard created. ID: {standard_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_standards()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=9, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Add", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        dept_entry.focus_set()

    def _edit_standard_dialog(self):
        """Open dialog to edit the selected teaching load standard."""
        selection = self.standards_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a standard to edit.")
            return

        item = self.standards_tree.item(selection[0])
        values = item['values']
        standard_id = values[0]

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Teaching Load Standard")
        dialog.geometry("500x550")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Department
        ttk.Label(frame, text="Department:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        dept_entry = ttk.Entry(frame, width=25)
        dept_entry.insert(0, str(values[1]))
        dept_entry.grid(row=0, column=1, padx=10, pady=8)

        # Role
        ttk.Label(frame, text="Role:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        role_entry = ttk.Entry(frame, width=25)
        role_entry.insert(0, str(values[2]))
        role_entry.grid(row=1, column=1, padx=10, pady=8)

        # Standard credits
        ttk.Label(frame, text="Standard Credits:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        std_credits_entry = ttk.Entry(frame, width=10)
        std_credits_entry.insert(0, str(values[3]))
        std_credits_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Standard courses
        ttk.Label(frame, text="Standard Courses:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        std_courses_entry = ttk.Entry(frame, width=10)
        std_courses_entry.insert(0, str(values[4]))
        std_courses_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Max credits
        ttk.Label(frame, text="Max Credits:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        max_credits_entry = ttk.Entry(frame, width=10)
        max_credits_entry.insert(0, str(values[5]))
        max_credits_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Max new preps
        ttk.Label(frame, text="Max New Preps:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        max_preps_entry = ttk.Entry(frame, width=10)
        max_preps_entry.insert(0, str(values[6]))
        max_preps_entry.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Large class threshold
        ttk.Label(frame, text="Large Class Threshold:").grid(row=6, column=0, sticky='e', padx=10, pady=8)
        threshold_entry = ttk.Entry(frame, width=10)
        threshold_entry.insert(0, "50")
        threshold_entry.grid(row=6, column=1, padx=10, pady=8, sticky='w')

        # Large class factor
        ttk.Label(frame, text="Large Class Factor:").grid(row=7, column=0, sticky='e', padx=10, pady=8)
        factor_entry = ttk.Entry(frame, width=10)
        factor_entry.insert(0, "1.5")
        factor_entry.grid(row=7, column=1, padx=10, pady=8, sticky='w')

        # Overload rate
        ttk.Label(frame, text="Overload Rate:").grid(row=8, column=0, sticky='e', padx=10, pady=8)
        rate_entry = ttk.Entry(frame, width=10)
        rate_entry.insert(0, "0")
        rate_entry.grid(row=8, column=1, padx=10, pady=8, sticky='w')

        def save():
            try:
                department = validate_entry(dept_entry, "Department")
                role = validate_entry(role_entry, "Role")
                std_credits = validate_number_entry(std_credits_entry, "Standard Credits", min_value=0)
                std_courses = validate_integer_entry(std_courses_entry, "Standard Courses", min_value=0)
                max_credits = validate_number_entry(max_credits_entry, "Max Credits", min_value=0)
                max_preps = validate_integer_entry(max_preps_entry, "Max New Preps", min_value=0)
                threshold = validate_integer_entry(threshold_entry, "Large Class Threshold", min_value=0)
                factor = validate_number_entry(factor_entry, "Large Class Factor", min_value=0)
                overload_rate = validate_number_entry(rate_entry, "Overload Rate", min_value=0)
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                TeachingLoadManager.update_standard(
                    standard_id=standard_id,
                    department=department,
                    role=role,
                    standard_credits=std_credits,
                    standard_courses=std_courses,
                    max_credits=max_credits,
                    max_new_preps=max_preps,
                    large_class_threshold=threshold,
                    large_class_factor=factor,
                    overload_rate=overload_rate
                )
                messagebox.showinfo("Success", "Standard updated.", parent=dialog)
                dialog.destroy()
                self._load_standards()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=9, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        dept_entry.focus_set()

    def _delete_standard(self):
        """Delete the selected teaching load standard."""
        selection = self.standards_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a standard to delete.")
            return

        item = self.standards_tree.item(selection[0])
        standard_id = item['values'][0]

        if not messagebox.askyesno("Confirm",
                                    f"Delete standard #{standard_id}?"):
            return

        try:
            TeachingLoadManager.delete_standard(standard_id)
            messagebox.showinfo("Success", "Standard deleted.")
            self._load_standards()
        except Exception as e:
            messagebox.showerror("Error", str(e))
