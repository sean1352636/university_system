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

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.performance_manager import (
    PerformanceManager,
)
from education_system.systems.university.domains.staff.interfaces.gui.staff_hr import _access as _hr


class AppraisalGUI:
    """GUI for managing performance appraisals."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None
        self.username = _hr.user_key(self) if self.current_user else None

        if not self.current_user:
            messagebox.showerror(_t('gui.staff.staff_hr.appraisal.dialogs.error', default="Error"), _t('gui.staff.staff_hr.appraisal.dialogs.login_required_to_access_performance_appraisals', default="Login required to access Performance Appraisals"))
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text=_t('gui.staff.staff_hr.appraisal.tabs.appraisals', default="Appraisals"))
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title(_t('gui.staff.staff_hr.appraisal.windows.performance_appraisal_system', default="Performance Appraisal System"))
        self.window.geometry("1400x900")
        self.window.minsize(1200, 800)

        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.close', default="Close"), command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_bar = ttk.Label(self.window, text=_t('gui.staff.staff_hr.appraisal.labels.ready', default="Ready"), relief=tk.SUNKEN, anchor=tk.W)
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
        # Reviews: line managers (their reports) and HR; cycles: HR only.
        if _hr.can(self, 'manager'):
            self._create_team_reviews_tab()
        if _hr.can(self, 'hr'):
            self._create_manage_tab()

    def _actor(self):
        return _hr.actor(self)

    def _create_cycles_tab(self):
        """Create the appraisal cycles tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.appraisal.tabs.appraisal_cycles', default="Appraisal Cycles"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.appraisal.labels.appraisal_cycles', default="Appraisal Cycles"), style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.refresh', default="Refresh"), command=self._load_cycles).pack(side=tk.RIGHT, padx=5)

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
        info_frame = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.appraisal.labels.current_active_cycle', default="Current Active Cycle"), padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        self.current_cycle_label = ttk.Label(info_frame, text=_t('gui.staff.staff_hr.appraisal.labels.no_active_cycle', default="No active cycle"), font=('Arial', 11))
        self.current_cycle_label.pack(side=tk.LEFT, padx=20)

        self.cycle_deadline_label = ttk.Label(info_frame, text="", font=('Arial', 11))
        self.cycle_deadline_label.pack(side=tk.LEFT, padx=20)

        self._load_cycles()

    def _create_my_appraisals_tab(self):
        """Create the my appraisals tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.appraisal.tabs.my_appraisals', default="My Appraisals"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.appraisal.labels.my_performance_appraisals', default="My Performance Appraisals"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.complete_self_review', default="Complete Self-Review"), command=self._complete_self_review).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.refresh', default="Refresh"), command=self._load_my_appraisals).pack(side=tk.LEFT, padx=5)

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
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.appraisal.tabs.my_goals', default="My Goals"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.appraisal.labels.performance_goals_objectives', default="Performance Goals & Objectives"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.add_goal', default="Add Goal"), command=self._add_goal).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.update_progress', default="Update Progress"), command=self._update_goal_progress).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.refresh', default="Refresh"), command=self._load_goals).pack(side=tk.LEFT, padx=5)

        # Filter
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.appraisal.labels.status', default="Status:")).pack(side=tk.LEFT, padx=5)
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
        summary_frame = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.appraisal.labels.goals_summary', default="Goals Summary"), padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)

        self.total_goals_label = ttk.Label(summary_frame, text=_t('gui.staff.staff_hr.appraisal.labels.total_goals_0', default="Total Goals: 0"))
        self.total_goals_label.pack(side=tk.LEFT, padx=20)

        self.completed_goals_label = ttk.Label(summary_frame, text=_t('gui.staff.staff_hr.appraisal.labels.completed_0', default="Completed: 0"))
        self.completed_goals_label.pack(side=tk.LEFT, padx=20)

        self.avg_progress_label = ttk.Label(summary_frame, text=_t('gui.staff.staff_hr.appraisal.labels.average_progress_0', default="Average Progress: 0%"))
        self.avg_progress_label.pack(side=tk.LEFT, padx=20)

        self._load_goals()

    def _create_team_reviews_tab(self):
        """Create the team reviews tab (managers only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.appraisal.tabs.team_reviews', default="Team Reviews"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.appraisal.labels.team_member_reviews', default="Team Member Reviews"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.complete_review', default="Complete Review"), command=self._complete_manager_review).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.refresh', default="Refresh"), command=self._load_team_reviews).pack(side=tk.LEFT, padx=5)

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
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.appraisal.tabs.manage_cycles', default="Manage Cycles"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.appraisal.labels.manage_appraisal_cycles', default="Manage Appraisal Cycles"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.create_cycle', default="Create Cycle"), command=self._create_cycle).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.start_cycle', default="Start Cycle"), command=self._start_cycle).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.complete_cycle', default="Complete Cycle"), command=self._complete_cycle).pack(side=tk.LEFT, padx=5)

        # Info text
        ttk.Label(tab, text=_t('gui.staff.staff_hr.appraisal.labels.use_this_tab_to_create_and_manage_performance_appraisal_cycles', default="Use this tab to create and manage performance appraisal cycles."),
                  font=('Arial', 10)).pack(padx=10, pady=10, anchor=tk.W)

    def _load_cycles(self):
        """Load appraisal cycles."""
        try:
            self.cycles_tree.delete(*self.cycles_tree.get_children())
            active_cycle = None
            for cycle in PerformanceManager.get_cycles():
                status = cycle.get('status') or 'draft'
                values = (cycle['cycle_id'], cycle['name'], cycle.get('start_date'), cycle.get('end_date'),
                          cycle.get('self_review_deadline') or '-',
                          cycle.get('manager_review_deadline') or '-', status.capitalize())
                self.cycles_tree.insert('', 'end', values=values, tags=(status,))
                if status == 'active' and active_cycle is None:
                    active_cycle = cycle

            if active_cycle:
                self.current_cycle_label.config(text=f"Current Cycle: {active_cycle['name']}")
                if active_cycle.get('self_review_deadline'):
                    self.cycle_deadline_label.config(text=f"Self-Review Due: {active_cycle['self_review_deadline']}")
            else:
                self.current_cycle_label.config(text=_t('gui.staff.staff_hr.appraisal.text.no_active_cycle', default="No active cycle"))
                self.cycle_deadline_label.config(text="")

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.appraisal.dialogs.error', default="Error"), f"Failed to load cycles: {e}")

    def _load_my_appraisals(self):
        """Load user's appraisals."""
        try:
            self.appraisals_tree.delete(*self.appraisals_tree.get_children())
            for rec in PerformanceManager.get_appraisals(self.username, actor=self._actor()):
                status = rec.get('status') or 'pending'
                values = (rec['appraisal_id'], rec.get('cycle_name'),
                          f"{rec['self_rating']:.1f}" if rec.get('self_rating') else '-',
                          f"{rec['manager_rating']:.1f}" if rec.get('manager_rating') else '-',
                          f"{rec['final_rating']:.1f}" if rec.get('final_rating') else '-',
                          status.replace('_', ' ').capitalize())
                tag = 'self_review' if status.startswith('self_review') else status
                self.appraisals_tree.insert('', 'end', values=values, tags=(tag,))

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.appraisal.dialogs.error', default="Error"), f"Failed to load appraisals: {e}")

    def _load_goals(self):
        """Load user's goals."""
        try:
            self.goals_tree.delete(*self.goals_tree.get_children())
            status_filter = self.goal_status_filter.get()
            goals = PerformanceManager.get_goals(
                self.username, status=None if status_filter == 'All' else status_filter.lower(),
                actor=self._actor())

            total = 0
            completed = 0
            total_progress = 0
            for goal in goals:
                total += 1
                if goal.get('status') == 'completed':
                    completed += 1
                total_progress += goal.get('progress') or 0
                values = (goal['goal_id'], goal['title'], goal.get('category') or '-',
                          goal.get('target_date') or '-', f"{goal.get('progress') or 0}%",
                          f"{float(goal.get('weight') or 1.0):.1f}",
                          (goal.get('status') or 'active').capitalize())
                self.goals_tree.insert('', 'end', values=values)

            self.total_goals_label.config(text=f"Total Goals: {total}")
            self.completed_goals_label.config(text=f"Completed: {completed}")

            avg_progress = total_progress / total if total > 0 else 0
            self.avg_progress_label.config(text=f"Average Progress: {avg_progress:.0f}%")

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.appraisal.dialogs.error', default="Error"), f"Failed to load goals: {e}")

    def _load_team_reviews(self):
        """Load team reviews for manager: their reports' appraisals (all for HR)."""
        try:
            self.team_tree.delete(*self.team_tree.get_children())
            for rec in PerformanceManager.get_team_reviews(self._actor(), include_done=True):
                status = rec.get('status') or ''
                tag = 'reviewed' if status == 'completed' else 'pending_review'
                values = (rec['appraisal_id'], rec['user_id'], rec.get('cycle_name'),
                          f"{rec['self_rating']:.1f}" if rec.get('self_rating') else '-',
                          f"{rec['manager_rating']:.1f}" if rec.get('manager_rating') else '-',
                          status.replace('_', ' ').capitalize())
                self.team_tree.insert('', 'end', values=values, tags=(tag,))

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.appraisal.dialogs.error', default="Error"), f"Failed to load team reviews: {e}")

    def _complete_self_review(self):
        """Complete self-review for current appraisal."""
        selection = self.appraisals_tree.selection()
        if not selection:
            # Find pending appraisal
            for item_id in self.appraisals_tree.get_children():
                item = self.appraisals_tree.item(item_id)
                if str(item['values'][5]).lower() == 'pending':
                    self.appraisals_tree.selection_set(item_id)
                    selection = [item_id]
                    break

        appraisal_id = self.appraisals_tree.item(selection[0])['values'][0] if selection else None
        cycle = None
        if appraisal_id is None:
            # No appraisal opened for you yet: review against the active cycle.
            cycle = PerformanceManager.get_active_cycle()
            if not cycle:
                messagebox.showwarning(_t('gui.staff.staff_hr.appraisal.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.appraisal.dialogs.no_pending_appraisal_found', default="No pending appraisal found"))
                return

        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.appraisal.windows.self_review', default="Self-Review"))
        dialog.geometry("600x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.appraisal.labels.complete_your_self_review', default="Complete Your Self-Review"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Rating scale
        rating_frame = ttk.LabelFrame(main_frame, text=_t('gui.staff.staff_hr.appraisal.labels.self_rating_1_5', default="Self-Rating (1-5)"), padding=10)
        rating_frame.pack(fill=tk.X, pady=10)

        ttk.Label(rating_frame, text=_t('gui.staff.staff_hr.appraisal.labels.value_1_needs_improvement_3_meets_expectations_5_exceeds_expecta', default="1=Needs Improvement, 3=Meets Expectations, 5=Exceeds Expectations")).pack()

        rating_var = tk.DoubleVar(value=3.0)
        rating_scale = ttk.Scale(rating_frame, from_=1, to=5, variable=rating_var, orient=tk.HORIZONTAL, length=300)
        rating_scale.pack(pady=10)

        rating_label = ttk.Label(rating_frame, text="3.0", font=('Arial', 12, 'bold'))
        rating_label.pack()

        def update_rating_label(*args):
            rating_label.config(text=f"{rating_var.get():.1f}")
        rating_var.trace_add('write', update_rating_label)

        # Self comments
        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.appraisal.labels.self_assessment_comments', default="Self-Assessment Comments:"), anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        comments_text = scrolledtext.ScrolledText(main_frame, height=6, width=50)
        comments_text.pack(fill=tk.X)

        # Strengths
        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.appraisal.labels.key_strengths', default="Key Strengths:"), anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        strengths_text = scrolledtext.ScrolledText(main_frame, height=4, width=50)
        strengths_text.pack(fill=tk.X)

        # Areas for improvement
        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.appraisal.labels.areas_for_improvement', default="Areas for Improvement:"), anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        improve_text = scrolledtext.ScrolledText(main_frame, height=4, width=50)
        improve_text.pack(fill=tk.X)

        def submit():
            review = dict(strengths=strengths_text.get('1.0', tk.END).strip(),
                          areas_for_improvement=improve_text.get('1.0', tk.END).strip())
            try:
                if appraisal_id is not None:
                    PerformanceManager.self_review_by_id(appraisal_id, self._actor(), rating_var.get(),
                                                         comments_text.get('1.0', tk.END).strip(), **review)
                else:
                    PerformanceManager.submit_self_review(self.username, cycle['cycle_id'], rating_var.get(),
                                                          comments_text.get('1.0', tk.END).strip(),
                                                          actor=self._actor(), **review)
                messagebox.showinfo(_t('gui.staff.staff_hr.appraisal.dialogs.success', default="Success"), _t('gui.staff.staff_hr.appraisal.dialogs.self_review_submitted_successfully', default="Self-review submitted successfully"))
                dialog.destroy()
                self._load_my_appraisals()

            except Exception as e:
                messagebox.showerror(_t('gui.staff.staff_hr.appraisal.dialogs.error', default="Error"), f"Failed to submit: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.submit_review', default="Submit Review"), command=submit).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _add_goal(self):
        """Add a new goal."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.appraisal.windows.add_goal', default="Add Goal"))
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.appraisal.labels.add_new_goal', default="Add New Goal"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Title
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.appraisal.labels.goal_title', default="Goal Title:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        title_var = tk.StringVar()
        ttk.Entry(row, textvariable=title_var, width=35).pack(side=tk.LEFT)

        # Category
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.appraisal.labels.category', default="Category:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        category_var = tk.StringVar(value=_t('gui.staff.staff_hr.appraisal.values.performance', default='Performance'))
        ttk.Combobox(row, textvariable=category_var,
                     values=['Performance', 'Development', 'Learning', 'Project', 'Other'],
                     width=20, state='readonly').pack(side=tk.LEFT)

        # Target date
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.appraisal.labels.target_date', default="Target Date:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        target_var = tk.StringVar()
        ttk.Entry(row, textvariable=target_var, width=15).pack(side=tk.LEFT)
        ttk.Label(row, text=_t('gui.staff.staff_hr.appraisal.labels.yyyy_mm_dd', default="(YYYY-MM-DD)"), font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # Weight
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.appraisal.labels.weight', default="Weight:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        weight_var = tk.StringVar(value="1.0")
        ttk.Entry(row, textvariable=weight_var, width=10).pack(side=tk.LEFT)

        # Description
        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.appraisal.labels.description', default="Description:"), anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        desc_text = scrolledtext.ScrolledText(main_frame, height=6, width=45)
        desc_text.pack(fill=tk.X)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save():
            if not title_var.get().strip():
                error_label.config(text=_t('gui.staff.staff_hr.appraisal.text.goal_title_is_required', default="Goal title is required"))
                return

            try:
                weight = float(weight_var.get()) if weight_var.get() else 1.0
                active = PerformanceManager.get_active_cycle()
                PerformanceManager.add_goal(self.username, title_var.get().strip(), actor=self._actor(),
                                            description=desc_text.get('1.0', tk.END).strip(),
                                            category=category_var.get(),
                                            target_date=target_var.get().strip() or None, weight=weight,
                                            cycle_id=active['cycle_id'] if active else None)
                messagebox.showinfo(_t('gui.staff.staff_hr.appraisal.dialogs.success', default="Success"), _t('gui.staff.staff_hr.appraisal.dialogs.goal_added_successfully', default="Goal added successfully"))
                dialog.destroy()
                self._load_goals()

            except Exception as e:
                error_label.config(text=f"Error: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.save_goal', default="Save Goal"), command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _update_goal_progress(self):
        """Update progress on selected goal."""
        selection = self.goals_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.staff.staff_hr.appraisal.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.appraisal.dialogs.please_select_a_goal_to_update', default="Please select a goal to update"))
            return

        item = self.goals_tree.item(selection[0])
        goal_id = item['values'][0]
        current_progress = int(str(item['values'][4]).replace('%', ''))

        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.appraisal.windows.update_progress', default="Update Progress"))
        dialog.geometry("350x200")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.appraisal.labels.update_goal_progress', default="Update Goal Progress"), font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        progress_var = tk.IntVar(value=current_progress)

        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.appraisal.labels.progress', default="Progress:")).pack()
        progress_scale = ttk.Scale(main_frame, from_=0, to=100, variable=progress_var,
                                   orient=tk.HORIZONTAL, length=250)
        progress_scale.pack(pady=10)

        progress_label = ttk.Label(main_frame, text=f"{current_progress}%", font=('Arial', 14, 'bold'))
        progress_label.pack()

        def update_label(*args):
            progress_label.config(text=f"{progress_var.get()}%")
        progress_var.trace_add('write', update_label)

        mark_complete = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.mark_as_complete', default="Mark as Complete"), variable=mark_complete).pack(pady=10)

        def save():
            try:
                PerformanceManager.update_goal_progress(goal_id, progress_var.get(), actor=self._actor(),
                                                        completed=mark_complete.get())

                messagebox.showinfo(_t('gui.staff.staff_hr.appraisal.dialogs.success', default="Success"), _t('gui.staff.staff_hr.appraisal.dialogs.progress_updated', default="Progress updated"))
                dialog.destroy()
                self._load_goals()

            except Exception as e:
                messagebox.showerror(_t('gui.staff.staff_hr.appraisal.dialogs.error', default="Error"), f"Failed to update: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.save', default="Save"), command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _view_appraisal(self, event=None):
        """View appraisal details."""
        selection = self.appraisals_tree.selection()
        if not selection:
            return

        item = self.appraisals_tree.item(selection[0])
        appraisal_id = item['values'][0]

        try:
            rec = PerformanceManager.get_appraisal_by_id(appraisal_id, actor=self._actor())

            if rec:
                details = f"""
Cycle: {rec.get('cycle_name')}
Reviewer: {rec.get('reviewer_id') or 'N/A'}
Self Rating: {rec.get('self_rating') or 'N/A'}
Manager Rating: {rec.get('manager_rating') or 'N/A'}
Final Rating: {rec.get('final_rating') or 'N/A'}
Status: {(rec.get('status') or 'pending').replace('_', ' ').capitalize()}

Self Comments:
{rec.get('self_comments') or 'None'}

Manager Comments:
{rec.get('manager_comments') or 'None'}

Strengths:
{rec.get('strengths') or 'None'}

Areas for Improvement:
{rec.get('areas_for_improvement') or 'None'}

Development Plan:
{rec.get('development_plan') or 'None'}
                """
                messagebox.showinfo(_t('gui.staff.staff_hr.appraisal.dialogs.appraisal_details', default="Appraisal Details"), details.strip())

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.appraisal.dialogs.error', default="Error"), f"Failed to load details: {e}")

    def _complete_manager_review(self):
        """Complete manager review for selected appraisal."""
        selection = self.team_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.staff.staff_hr.appraisal.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.appraisal.dialogs.please_select_an_appraisal_to_review', default="Please select an appraisal to review"))
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
        rating_frame = ttk.LabelFrame(main_frame, text=_t('gui.staff.staff_hr.appraisal.labels.manager_rating_1_5', default="Manager Rating (1-5)"), padding=10)
        rating_frame.pack(fill=tk.X, pady=10)

        rating_var = tk.DoubleVar(value=3.0)
        ttk.Scale(rating_frame, from_=1, to=5, variable=rating_var, orient=tk.HORIZONTAL, length=300).pack(pady=10)

        rating_label = ttk.Label(rating_frame, text="3.0", font=('Arial', 12, 'bold'))
        rating_label.pack()

        def update_rating(*args):
            rating_label.config(text=f"{rating_var.get():.1f}")
        rating_var.trace_add('write', update_rating)

        # Comments
        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.appraisal.labels.manager_comments', default="Manager Comments:"), anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        comments_text = scrolledtext.ScrolledText(main_frame, height=6, width=50)
        comments_text.pack(fill=tk.X)

        # Development plan
        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.appraisal.labels.development_plan', default="Development Plan:"), anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        plan_text = scrolledtext.ScrolledText(main_frame, height=4, width=50)
        plan_text.pack(fill=tk.X)

        def submit():
            try:
                PerformanceManager.manager_review_by_id(appraisal_id, self._actor(), rating_var.get(),
                                                        comments_text.get('1.0', tk.END).strip(),
                                                        development_plan=plan_text.get('1.0', tk.END).strip())
                messagebox.showinfo(_t('gui.staff.staff_hr.appraisal.dialogs.success', default="Success"), _t('gui.staff.staff_hr.appraisal.dialogs.manager_review_completed', default="Manager review completed"))
                dialog.destroy()
                self._load_team_reviews()

            except Exception as e:
                messagebox.showerror(_t('gui.staff.staff_hr.appraisal.dialogs.error', default="Error"), f"Failed to submit: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.submit_review', default="Submit Review"), command=submit).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _create_cycle(self):
        """Create a new appraisal cycle."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.appraisal.windows.create_appraisal_cycle', default="Create Appraisal Cycle"))
        dialog.geometry("450x400")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.appraisal.labels.create_new_appraisal_cycle', default="Create New Appraisal Cycle"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        fields = {}

        # Name
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.appraisal.labels.cycle_name', default="Cycle Name:"), width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['name'] = ttk.Entry(row, width=25)
        fields['name'].pack(side=tk.LEFT)

        # Start date
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.appraisal.labels.start_date', default="Start Date:"), width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['start'] = ttk.Entry(row, width=15)
        fields['start'].pack(side=tk.LEFT)

        # End date
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.appraisal.labels.end_date', default="End Date:"), width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['end'] = ttk.Entry(row, width=15)
        fields['end'].pack(side=tk.LEFT)

        # Self review deadline
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.appraisal.labels.self_review_due', default="Self Review Due:"), width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['self_due'] = ttk.Entry(row, width=15)
        fields['self_due'].pack(side=tk.LEFT)

        # Manager review deadline
        row = ttk.Frame(main_frame)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=_t('gui.staff.staff_hr.appraisal.labels.manager_review_due', default="Manager Review Due:"), width=18, anchor=tk.W).pack(side=tk.LEFT)
        fields['mgr_due'] = ttk.Entry(row, width=15)
        fields['mgr_due'].pack(side=tk.LEFT)

        # Description
        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.appraisal.labels.description', default="Description:"), anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        desc_text = scrolledtext.ScrolledText(main_frame, height=4, width=40)
        desc_text.pack(fill=tk.X)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save():
            if not fields['name'].get().strip():
                error_label.config(text=_t('gui.staff.staff_hr.appraisal.text.cycle_name_is_required', default="Cycle name is required"))
                return

            try:
                PerformanceManager.create_cycle(fields['name'].get().strip(), fields['start'].get().strip(),
                                                fields['end'].get().strip(), actor=self._actor(),
                                                description=desc_text.get('1.0', tk.END).strip(),
                                                self_review_deadline=fields['self_due'].get().strip() or None,
                                                manager_review_deadline=fields['mgr_due'].get().strip() or None,
                                                status='draft')
                messagebox.showinfo(_t('gui.staff.staff_hr.appraisal.dialogs.success', default="Success"), _t('gui.staff.staff_hr.appraisal.dialogs.appraisal_cycle_created', default="Appraisal cycle created"))
                dialog.destroy()
                self._load_cycles()

            except Exception as e:
                error_label.config(text=f"Error: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.create_cycle', default="Create Cycle"), command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.appraisal.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _start_cycle(self):
        """Start selected appraisal cycle."""
        selection = self.cycles_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.staff.staff_hr.appraisal.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.appraisal.dialogs.please_select_a_cycle_to_start', default="Please select a cycle to start"))
            return

        item = self.cycles_tree.item(selection[0])
        cycle_id = item['values'][0]
        status = str(item['values'][6]).lower()

        if status != 'draft':
            messagebox.showwarning(_t('gui.staff.staff_hr.appraisal.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.appraisal.dialogs.only_draft_cycles_can_be_started', default="Only draft cycles can be started"))
            return

        if not messagebox.askyesno(_t('gui.staff.staff_hr.appraisal.dialogs.confirm', default="Confirm"), _t('gui.staff.staff_hr.appraisal.dialogs.start_this_appraisal_cycle', default="Start this appraisal cycle?")):
            return

        try:
            opened = PerformanceManager.start_cycle(cycle_id, actor=self._actor())

            messagebox.showinfo(_t('gui.staff.staff_hr.appraisal.dialogs.success', default="Success"),
                                _t('gui.staff.staff_hr.appraisal.dialogs.appraisal_cycle_started', default="Appraisal cycle started")
                                + f" ({opened})")
            self._load_my_appraisals()
            self._load_cycles()

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.appraisal.dialogs.error', default="Error"), f"Failed to start cycle: {e}")

    def _complete_cycle(self):
        """Complete selected appraisal cycle."""
        selection = self.cycles_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.staff.staff_hr.appraisal.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.appraisal.dialogs.please_select_a_cycle_to_complete', default="Please select a cycle to complete"))
            return

        item = self.cycles_tree.item(selection[0])
        cycle_id = item['values'][0]

        if not messagebox.askyesno(_t('gui.staff.staff_hr.appraisal.dialogs.confirm', default="Confirm"), _t('gui.staff.staff_hr.appraisal.dialogs.complete_this_appraisal_cycle', default="Complete this appraisal cycle?")):
            return

        try:
            PerformanceManager.complete_cycle(cycle_id, actor=self._actor())

            messagebox.showinfo(_t('gui.staff.staff_hr.appraisal.dialogs.success', default="Success"), _t('gui.staff.staff_hr.appraisal.dialogs.appraisal_cycle_completed', default="Appraisal cycle completed"))
            self._load_cycles()

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.appraisal.dialogs.error', default="Error"), f"Failed to complete cycle: {e}")


def launch_appraisal_gui(root, auth):
    """Launch Performance Appraisal GUI."""
    try:
        return AppraisalGUI(root, auth)
    except Exception as e:
        messagebox.showerror(_t('gui.staff.staff_hr.appraisal.dialogs.error', default="Error"), f"Failed to launch Appraisal GUI: {e}")
        return None
