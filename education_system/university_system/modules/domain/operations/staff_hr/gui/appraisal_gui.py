"""
Performance Appraisal GUI

Provides interface for:
- Viewing appraisal cycles
- Self-assessment forms
- Goal setting (OKRs)
- Manager reviews
- Performance history
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.core.activity_logger import log_activity


class AppraisalGUI:
    """GUI for managing performance appraisals."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Performance Appraisals")
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Appraisals")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Performance Appraisal System")
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

        self._create_cycles_tab()
        self._create_my_appraisals_tab()
        self._create_goals_tab()
        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_team_reviews_tab()
            self._create_manage_tab()

    def _create_cycles_tab(self):
        """Create the appraisal cycles tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Appraisal Cycles")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Appraisal Cycles", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_cycles).pack(side=tk.RIGHT, padx=5)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Name', 'Start Date', 'End Date', 'Self Review Due', 'Manager Review Due', 'Status')
        self.cycles_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                        yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.cycles_tree.yview)

        for col in columns:
            self.cycles_tree.heading(col, text=col)
            self.cycles_tree.column(col, width=120, anchor=tk.CENTER)

        self.cycles_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status tags
        self.cycles_tree.tag_configure('draft', background='#e2e3e5')
        self.cycles_tree.tag_configure('active', background='#d4edda')
        self.cycles_tree.tag_configure('completed', background='#cce5ff')

        # Current cycle info
        info_frame = ttk.LabelFrame(tab, text="Current Active Cycle", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        self.current_cycle_label = ttk.Label(info_frame, text="No active cycle", font=('Arial', 11))
        self.current_cycle_label.pack(side=tk.LEFT, padx=20)

        self.cycle_deadline_label = ttk.Label(info_frame, text="", font=('Arial', 11))
        self.cycle_deadline_label.pack(side=tk.LEFT, padx=20)

        self._load_cycles()

    def _create_my_appraisals_tab(self):
        """Create the my appraisals tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Appraisals")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="My Performance Appraisals", style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Complete Self-Review", command=self._complete_self_review).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_my_appraisals).pack(side=tk.LEFT, padx=5)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Cycle', 'Self Rating', 'Manager Rating', 'Final Rating', 'Status')
        self.appraisals_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                            yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.appraisals_tree.yview)

        for col in columns:
            self.appraisals_tree.heading(col, text=col)
            self.appraisals_tree.column(col, width=120, anchor=tk.CENTER)

        self.appraisals_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status tags
        self.appraisals_tree.tag_configure('pending', background='#fff3cd')
        self.appraisals_tree.tag_configure('self_review', background='#cce5ff')
        self.appraisals_tree.tag_configure('manager_review', background='#d1ecf1')
        self.appraisals_tree.tag_configure('completed', background='#d4edda')

        # Bind double-click
        self.appraisals_tree.bind('<Double-1>', self._view_appraisal)

        self._load_my_appraisals()

    def _create_goals_tab(self):
        """Create the goals/OKRs tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Goals")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Performance Goals & Objectives", style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Add Goal", command=self._add_goal).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Update Progress", command=self._update_goal_progress).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_goals).pack(side=tk.LEFT, padx=5)

        # Filter
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.goal_status_filter = ttk.Combobox(filter_frame, values=['All', 'Active', 'Completed', 'Cancelled'],
                                               width=12, state='readonly')
        self.goal_status_filter.set('Active')
        self.goal_status_filter.pack(side=tk.LEFT, padx=5)
        self.goal_status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_goals())

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Title', 'Category', 'Target Date', 'Progress', 'Weight', 'Status')
        self.goals_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                       yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.goals_tree.yview)

        col_widths = {'ID': 50, 'Title': 200, 'Category': 100, 'Target Date': 100,
                      'Progress': 80, 'Weight': 60, 'Status': 80}
        for col in columns:
            self.goals_tree.heading(col, text=col)
            self.goals_tree.column(col, width=col_widths.get(col, 100))

        self.goals_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Progress summary
        summary_frame = ttk.LabelFrame(tab, text="Goals Summary", padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)

        self.total_goals_label = ttk.Label(summary_frame, text="Total Goals: 0")
        self.total_goals_label.pack(side=tk.LEFT, padx=20)

        self.completed_goals_label = ttk.Label(summary_frame, text="Completed: 0")
        self.completed_goals_label.pack(side=tk.LEFT, padx=20)

        self.avg_progress_label = ttk.Label(summary_frame, text="Average Progress: 0%")
        self.avg_progress_label.pack(side=tk.LEFT, padx=20)

        self._load_goals()

    def _create_team_reviews_tab(self):
        """Create the team reviews tab (managers only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Team Reviews")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Team Member Reviews", style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Complete Review", command=self._complete_manager_review).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_team_reviews).pack(side=tk.LEFT, padx=5)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Employee', 'Cycle', 'Self Rating', 'Manager Rating', 'Status')
        self.team_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                      yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.team_tree.yview)

        for col in columns:
            self.team_tree.heading(col, text=col)
            self.team_tree.column(col, width=120, anchor=tk.CENTER)

        self.team_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status tags
        self.team_tree.tag_configure('pending_review', background='#fff3cd')
        self.team_tree.tag_configure('reviewed', background='#d4edda')

        self._load_team_reviews()

    def _create_manage_tab(self):
        """Create the manage cycles tab (admin only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Manage Cycles")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Manage Appraisal Cycles", style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Create Cycle", command=self._create_cycle).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Start Cycle", command=self._start_cycle).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Complete Cycle", command=self._complete_cycle).pack(side=tk.LEFT, padx=5)

        # Info text
        ttk.Label(tab, text="Use this tab to create and manage performance appraisal cycles.",
                  font=('Arial', 10)).pack(padx=10, pady=10, anchor=tk.W)

    def _load_cycles(self):
        """Load appraisal cycles."""
        try:
            self.cycles_tree.delete(*self.cycles_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT cycle_id, name, start_date, end_date,
                           self_review_deadline, manager_review_deadline, status
                    FROM appraisal_cycles
                    ORDER BY start_date DESC
                ''')

                active_cycle = None

                for row in cursor.fetchall():
                    status = row[6]
                    values = (row[0], row[1], row[2], row[3],
                              row[4] or '-', row[5] or '-', status.capitalize())
                    self.cycles_tree.insert('', 'end', values=values, tags=(status,))

                    if status == 'active':
                        active_cycle = row

            if active_cycle:
                self.current_cycle_label.config(text=f"Current Cycle: {active_cycle[1]}")
                if active_cycle[4]:
                    self.cycle_deadline_label.config(text=f"Self-Review Due: {active_cycle[4]}")
            else:
                self.current_cycle_label.config(text="No active cycle")
                self.cycle_deadline_label.config(text="")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load cycles: {e}")

    def _load_my_appraisals(self):
        """Load user's appraisals."""
        try:
            self.appraisals_tree.delete(*self.appraisals_tree.get_children())

            user_id = self.current_user.get('id') or self.current_user.get('username')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.appraisal_id, c.name, a.self_rating, a.manager_rating,
                           a.final_rating, a.status
                    FROM appraisal_records a
                    JOIN appraisal_cycles c ON a.cycle_id = c.cycle_id
                    WHERE a.user_id = ?
                    ORDER BY c.start_date DESC
                ''', (user_id,))

                for row in cursor.fetchall():
                    values = (row[0], row[1],
                              f"{row[2]:.1f}" if row[2] else '-',
                              f"{row[3]:.1f}" if row[3] else '-',
                              f"{row[4]:.1f}" if row[4] else '-',
                              row[5].replace('_', ' ').capitalize())
                    self.appraisals_tree.insert('', 'end', values=values, tags=(row[5],))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load appraisals: {e}")

    def _load_goals(self):
        """Load user's goals."""
        try:
            self.goals_tree.delete(*self.goals_tree.get_children())

            user_id = self.current_user.get('id') or self.current_user.get('username')
            status_filter = self.goal_status_filter.get()

            with get_connection() as conn:
                cursor = conn.cursor()

                query = '''
                    SELECT goal_id, title, category, target_date, progress, weight, status
                    FROM appraisal_goals
                    WHERE user_id = ?
                '''
                params = [user_id]

                if status_filter != 'All':
                    query += ' AND status = ?'
                    params.append(status_filter.lower())

                query += ' ORDER BY target_date ASC'

                cursor.execute(query, params)

                total = 0
                completed = 0
                total_progress = 0

                for row in cursor.fetchall():
                    total += 1
                    if row[6] == 'completed':
                        completed += 1
                    total_progress += row[4] or 0

                    values = (row[0], row[1], row[2] or '-', row[3] or '-',
                              f"{row[4]}%", f"{row[5]:.1f}", row[6].capitalize())
                    self.goals_tree.insert('', 'end', values=values)

            self.total_goals_label.config(text=f"Total Goals: {total}")
            self.completed_goals_label.config(text=f"Completed: {completed}")

            avg_progress = total_progress / total if total > 0 else 0
            self.avg_progress_label.config(text=f"Average Progress: {avg_progress:.0f}%")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load goals: {e}")

    def _load_team_reviews(self):
        """Load team reviews for manager."""
        try:
            self.team_tree.delete(*self.team_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.appraisal_id, a.user_id, c.name, a.self_rating,
                           a.manager_rating, a.status
                    FROM appraisal_records a
                    JOIN appraisal_cycles c ON a.cycle_id = c.cycle_id
                    WHERE c.status = 'active'
                    AND a.status IN ('self_review', 'manager_review')
                    ORDER BY a.user_id
                ''')

                for row in cursor.fetchall():
                    tag = 'pending_review' if row[5] == 'self_review' else 'reviewed'
                    values = (row[0], row[1], row[2],
                              f"{row[3]:.1f}" if row[3] else '-',
                              f"{row[4]:.1f}" if row[4] else '-',
                              row[5].replace('_', ' ').capitalize())
                    self.team_tree.insert('', 'end', values=values, tags=(tag,))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load team reviews: {e}")

    def _complete_self_review(self):
        """Complete self-review for current appraisal."""
        selection = self.appraisals_tree.selection()
        if not selection:
            # Find pending appraisal
            for item_id in self.appraisals_tree.get_children():
                item = self.appraisals_tree.item(item_id)
                if item['values'][5].lower() == 'pending':
                    self.appraisals_tree.selection_set(item_id)
                    selection = [item_id]
                    break

        if not selection:
            messagebox.showwarning("Warning", "No pending appraisal found")
            return

        item = self.appraisals_tree.item(selection[0])
        appraisal_id = item['values'][0]

        dialog = tk.Toplevel(self.root)
        dialog.title("Self-Review")
        dialog.geometry("600x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Complete Your Self-Review", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Rating scale
        rating_frame = ttk.LabelFrame(main_frame, text="Self-Rating (1-5)", padding=10)
        rating_frame.pack(fill=tk.X, pady=10)

        ttk.Label(rating_frame, text="1=Needs Improvement, 3=Meets Expectations, 5=Exceeds Expectations").pack()

        rating_var = tk.DoubleVar(value=3.0)
        rating_scale = ttk.Scale(rating_frame, from_=1, to=5, variable=rating_var, orient=tk.HORIZONTAL, length=300)
        rating_scale.pack(pady=10)

        rating_label = ttk.Label(rating_frame, text="3.0", font=('Arial', 12, 'bold'))
        rating_label.pack()

        def update_rating_label(*args):
            rating_label.config(text=f"{rating_var.get():.1f}")
        rating_var.trace_add('write', update_rating_label)

        # Self comments
        ttk.Label(main_frame, text="Self-Assessment Comments:", anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        comments_text = scrolledtext.ScrolledText(main_frame, height=6, width=50)
        comments_text.pack(fill=tk.X)

        # Strengths
        ttk.Label(main_frame, text="Key Strengths:", anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        strengths_text = scrolledtext.ScrolledText(main_frame, height=4, width=50)
        strengths_text.pack(fill=tk.X)

        # Areas for improvement
        ttk.Label(main_frame, text="Areas for Improvement:", anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        improve_text = scrolledtext.ScrolledText(main_frame, height=4, width=50)
        improve_text.pack(fill=tk.X)

        def submit():
            try:
                with transaction() as conn:
                    conn.execute('''
                        UPDATE appraisal_records
                        SET self_rating = ?, self_comments = ?, strengths = ?,
                            areas_for_improvement = ?, status = 'self_review',
                            self_submitted_date = ?, updated_at = ?
                        WHERE appraisal_id = ?
                    ''', (rating_var.get(), comments_text.get('1.0', tk.END).strip(),
                          strengths_text.get('1.0', tk.END).strip(),
                          improve_text.get('1.0', tk.END).strip(),
                          datetime.now().isoformat(), datetime.now().isoformat(), appraisal_id))

                log_activity('update', 'appraisal_record', appraisal_id=appraisal_id,
                             details={'action': 'self_review_completed'})
                messagebox.showinfo("Success", "Self-review submitted successfully")
                dialog.destroy()
                self._load_my_appraisals()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Submit Review", command=submit).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _add_goal(self):
        """Add a new goal."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Goal")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Add New Goal", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Title
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Goal Title:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        title_var = tk.StringVar()
        ttk.Entry(row, textvariable=title_var, width=35).pack(side=tk.LEFT)

        # Category
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Category:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        category_var = tk.StringVar(value='Performance')
        ttk.Combobox(row, textvariable=category_var,
                     values=['Performance', 'Development', 'Learning', 'Project', 'Other'],
                     width=20, state='readonly').pack(side=tk.LEFT)

        # Target date
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Target Date:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        target_var = tk.StringVar()
        ttk.Entry(row, textvariable=target_var, width=15).pack(side=tk.LEFT)
        ttk.Label(row, text="(YYYY-MM-DD)", font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # Weight
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Weight:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        weight_var = tk.StringVar(value="1.0")
        ttk.Entry(row, textvariable=weight_var, width=10).pack(side=tk.LEFT)

        # Description
        ttk.Label(main_frame, text="Description:", anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        desc_text = scrolledtext.ScrolledText(main_frame, height=6, width=45)
        desc_text.pack(fill=tk.X)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save():
            if not title_var.get().strip():
                error_label.config(text="Goal title is required")
                return

            user_id = self.current_user.get('id') or self.current_user.get('username')

            try:
                weight = float(weight_var.get()) if weight_var.get() else 1.0

                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO appraisal_goals
                        (user_id, title, description, category, target_date, weight, status)
                        VALUES (?, ?, ?, ?, ?, ?, 'active')
                    ''', (user_id, title_var.get().strip(), desc_text.get('1.0', tk.END).strip(),
                          category_var.get(), target_var.get().strip() or None, weight))

                log_activity('create', 'appraisal_goal', user_id=user_id,
                             details={'title': title_var.get().strip()})
                messagebox.showinfo("Success", "Goal added successfully")
                dialog.destroy()
                self._load_goals()

            except Exception as e:
                error_label.config(text=f"Error: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Save Goal", command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _update_goal_progress(self):
        """Update progress on selected goal."""
        selection = self.goals_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a goal to update")
            return

        item = self.goals_tree.item(selection[0])
        goal_id = item['values'][0]
        current_progress = int(item['values'][4].replace('%', ''))

        dialog = tk.Toplevel(self.root)
        dialog.title("Update Progress")
        dialog.geometry("350x200")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Update Goal Progress", font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        progress_var = tk.IntVar(value=current_progress)

        ttk.Label(main_frame, text="Progress:").pack()
        progress_scale = ttk.Scale(main_frame, from_=0, to=100, variable=progress_var,
                                   orient=tk.HORIZONTAL, length=250)
        progress_scale.pack(pady=10)

        progress_label = ttk.Label(main_frame, text=f"{current_progress}%", font=('Arial', 14, 'bold'))
        progress_label.pack()

        def update_label(*args):
            progress_label.config(text=f"{progress_var.get()}%")
        progress_var.trace_add('write', update_label)

        mark_complete = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text="Mark as Complete", variable=mark_complete).pack(pady=10)

        def save():
            try:
                status = 'completed' if mark_complete.get() or progress_var.get() == 100 else 'active'

                with transaction() as conn:
                    conn.execute('''
                        UPDATE appraisal_goals
                        SET progress = ?, status = ?, updated_at = ?
                        WHERE goal_id = ?
                    ''', (progress_var.get(), status, datetime.now().isoformat(), goal_id))

                messagebox.showinfo("Success", "Progress updated")
                dialog.destroy()
                self._load_goals()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _view_appraisal(self, event=None):
        """View appraisal details."""
        selection = self.appraisals_tree.selection()
        if not selection:
            return

        item = self.appraisals_tree.item(selection[0])
        appraisal_id = item['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.*, c.name FROM appraisal_records a
                    JOIN appraisal_cycles c ON a.cycle_id = c.cycle_id
                    WHERE a.appraisal_id = ?
                ''', (appraisal_id,))
                row = cursor.fetchone()

            if row:
                details = f"""
Cycle: {row[-1]}
Self Rating: {row[4] or 'N/A'}
Manager Rating: {row[5] or 'N/A'}
Final Rating: {row[6] or 'N/A'}
Status: {row[11].replace('_', ' ').capitalize()}

Self Comments:
{row[7] or 'None'}

Manager Comments:
{row[8] or 'None'}

Strengths:
{row[9] or 'None'}

Areas for Improvement:
{row[10] or 'None'}
                """
                messagebox.showinfo("Appraisal Details", details.strip())

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load details: {e}")

    def _complete_manager_review(self):
        """Complete manager review for selected appraisal."""
        selection = self.team_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an appraisal to review")
            return

        item = self.team_tree.item(selection[0])
        appraisal_id = item['values'][0]
        employee = item['values'][1]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Manager Review - {employee}")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Manager Review for {employee}",
                  font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Rating
        rating_frame = ttk.LabelFrame(main_frame, text="Manager Rating (1-5)", padding=10)
        rating_frame.pack(fill=tk.X, pady=10)

        rating_var = tk.DoubleVar(value=3.0)
        ttk.Scale(rating_frame, from_=1, to=5, variable=rating_var, orient=tk.HORIZONTAL, length=300).pack(pady=10)

        rating_label = ttk.Label(rating_frame, text="3.0", font=('Arial', 12, 'bold'))
        rating_label.pack()

        def update_rating(*args):
            rating_label.config(text=f"{rating_var.get():.1f}")
        rating_var.trace_add('write', update_rating)

        # Comments
        ttk.Label(main_frame, text="Manager Comments:", anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        comments_text = scrolledtext.ScrolledText(main_frame, height=6, width=50)
        comments_text.pack(fill=tk.X)

        # Development plan
        ttk.Label(main_frame, text="Development Plan:", anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        plan_text = scrolledtext.ScrolledText(main_frame, height=4, width=50)
        plan_text.pack(fill=tk.X)

        def submit():
            try:
                reviewer_id = self.current_user.get('id') or self.current_user.get('username')

                with transaction() as conn:
                    # Get self rating to calculate final
                    cursor = conn.cursor()
                    cursor.execute('SELECT self_rating FROM appraisal_records WHERE appraisal_id = ?', (appraisal_id,))
                    self_rating = cursor.fetchone()[0] or 3.0

                    final_rating = (self_rating + rating_var.get()) / 2

                    conn.execute('''
                        UPDATE appraisal_records
                        SET manager_rating = ?, final_rating = ?, manager_comments = ?,
                            development_plan = ?, reviewer_id = ?, status = 'completed',
                            manager_submitted_date = ?, updated_at = ?
                        WHERE appraisal_id = ?
                    ''', (rating_var.get(), final_rating, comments_text.get('1.0', tk.END).strip(),
                          plan_text.get('1.0', tk.END).strip(), reviewer_id,
                          datetime.now().isoformat(), datetime.now().isoformat(), appraisal_id))

                log_activity('update', 'appraisal_record', appraisal_id=appraisal_id,
                             details={'action': 'manager_review_completed'})
                messagebox.showinfo("Success", "Manager review completed")
                dialog.destroy()
                self._load_team_reviews()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Submit Review", command=submit).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _create_cycle(self):
        """Create a new appraisal cycle."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Appraisal Cycle")
        dialog.geometry("450x400")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Create New Appraisal Cycle", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        fields = {}

        # Name
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Cycle Name:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['name'] = ttk.Entry(row, width=25)
        fields['name'].pack(side=tk.LEFT)

        # Start date
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Start Date:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['start'] = ttk.Entry(row, width=15)
        fields['start'].pack(side=tk.LEFT)

        # End date
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="End Date:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['end'] = ttk.Entry(row, width=15)
        fields['end'].pack(side=tk.LEFT)

        # Self review deadline
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Self Review Due:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['self_due'] = ttk.Entry(row, width=15)
        fields['self_due'].pack(side=tk.LEFT)

        # Manager review deadline
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text="Manager Review Due:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['mgr_due'] = ttk.Entry(row, width=15)
        fields['mgr_due'].pack(side=tk.LEFT)

        # Description
        ttk.Label(main_frame, text="Description:", anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        desc_text = scrolledtext.ScrolledText(main_frame, height=4, width=40)
        desc_text.pack(fill=tk.X)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save():
            if not fields['name'].get().strip():
                error_label.config(text="Cycle name is required")
                return

            created_by = self.current_user.get('username') or self.current_user.get('id')

            try:
                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO appraisal_cycles
                        (name, description, start_date, end_date, self_review_deadline,
                         manager_review_deadline, status, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, 'draft', ?)
                    ''', (fields['name'].get().strip(), desc_text.get('1.0', tk.END).strip(),
                          fields['start'].get().strip(), fields['end'].get().strip(),
                          fields['self_due'].get().strip() or None,
                          fields['mgr_due'].get().strip() or None, created_by))

                log_activity('create', 'appraisal_cycle', details={'name': fields['name'].get().strip()})
                messagebox.showinfo("Success", "Appraisal cycle created")
                dialog.destroy()
                self._load_cycles()

            except Exception as e:
                error_label.config(text=f"Error: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Create Cycle", command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _start_cycle(self):
        """Start selected appraisal cycle."""
        selection = self.cycles_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a cycle to start")
            return

        item = self.cycles_tree.item(selection[0])
        cycle_id = item['values'][0]
        status = item['values'][6].lower()

        if status != 'draft':
            messagebox.showwarning("Warning", "Only draft cycles can be started")
            return

        if not messagebox.askyesno("Confirm", "Start this appraisal cycle?"):
            return

        try:
            with transaction() as conn:
                conn.execute('UPDATE appraisal_cycles SET status = ? WHERE cycle_id = ?', ('active', cycle_id))

            messagebox.showinfo("Success", "Appraisal cycle started")
            self._load_cycles()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start cycle: {e}")

    def _complete_cycle(self):
        """Complete selected appraisal cycle."""
        selection = self.cycles_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a cycle to complete")
            return

        item = self.cycles_tree.item(selection[0])
        cycle_id = item['values'][0]

        if not messagebox.askyesno("Confirm", "Complete this appraisal cycle?"):
            return

        try:
            with transaction() as conn:
                conn.execute('UPDATE appraisal_cycles SET status = ? WHERE cycle_id = ?', ('completed', cycle_id))

            messagebox.showinfo("Success", "Appraisal cycle completed")
            self._load_cycles()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to complete cycle: {e}")


def launch_appraisal_gui(root, auth):
    """Launch Performance Appraisal GUI."""
    try:
        return AppraisalGUI(root, auth)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Appraisal GUI: {e}")
        return None
