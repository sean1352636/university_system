"""Split from course_planning_gui.py — provides mixins assembled in
course_planning_gui/__init__.py into the final CoursePlanningGUI class."""
from __future__ import annotations

import json
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from typing import Optional, Dict, List

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.domain.academics.course_planning.services.planning_service import PlanningService
from education_system.systems.university.domain.assessment.grading.grade_calculation.gpa import calculate_student_gpa
from education_system.systems.university.infrastructure.activity_logger import log_activity


class _DashboardMixin:
    """Methods extracted from CoursePlanningGUI.dashboard responsibility."""

    def _create_dashboard_tab(self):
        """Create the dashboard overview tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Dashboard")

        # Welcome section
        welcome_frame = ttk.Frame(tab)
        welcome_frame.pack(fill=tk.X, padx=20, pady=20)

        ttk.Label(welcome_frame, text="Course Planning Dashboard",
                 font=('Arial', 18, 'bold')).pack(anchor=tk.W)
        ttk.Label(welcome_frame, text="Plan your academic journey with intelligent course scheduling",
                 font=('Arial', 11)).pack(anchor=tk.W, pady=5)

        # Quick stats
        stats_frame = ttk.LabelFrame(tab, text="Your Planning Overview", padding=15)
        stats_frame.pack(fill=tk.X, padx=20, pady=10)

        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X)

        # Get stats
        try:
            plans = self._student_plans()
            active_plans = [p for p in plans if p['status'] == 'Active']
        except Exception:
            plans = []
            active_plans = []

        try:
            recommendations_count = len(
                self.planning_service.get_student_recommendations(
                    self.student_id, conn=self._read_conn()))
        except Exception:
            recommendations_count = 0

        self._create_stat_card(stats_grid, "Total Plans", len(plans), 0, 0)
        self._create_stat_card(stats_grid, "Active Plans", len(active_plans), 0, 1)
        self._create_stat_card(stats_grid, "Recommendations", recommendations_count, 0, 2)

        # Recent plans
        recent_frame = ttk.LabelFrame(tab, text="Recent Course Plans", padding=15)
        recent_frame.pack(fill=tk.X, padx=20, pady=10)

        # BUTTONS FIRST - at the TOP so they're always visible
        button_frame = ttk.Frame(recent_frame, relief=tk.RAISED, borderwidth=2)
        button_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10), ipady=5)
        ttk.Button(button_frame, text="Create New Plan",
                  command=self._create_new_plan).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="Load Plan",
                  command=self._load_selected_plan).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="Auto-Generate Plan",
                  command=self._auto_generate_plan).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="Duplicate Plan",
                  command=self._duplicate_plan).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="Delete Plan",
                  command=self._delete_plan).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="Refresh",
                  command=self._refresh_plans_list).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="Programme Curriculum Map",
                  command=self._show_programme_curriculum_map).pack(side=tk.LEFT, padx=5, pady=5)

        # Admin-only button to switch students
        if self.viewing_as_admin:
            ttk.Button(button_frame, text="Switch Student",
                      command=self._switch_student).pack(side=tk.RIGHT, padx=5, pady=5)

        # Force geometry update to ensure buttons are visible
        button_frame.update_idletasks()
        recent_frame.update_idletasks()

        # Plans listbox with scrollbar - AFTER buttons so buttons stay on top
        list_frame = ttk.Frame(recent_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.plans_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                        font=('Arial', 10), height=6)
        self.plans_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.plans_listbox.yview)

        self.plans_listbox.bind('<Double-Button-1>', self._on_plan_double_click)

        try:
            self._refresh_plans_list()
        except Exception:
            import traceback
            traceback.print_exc()

    def _create_stat_card(self, parent, title, value, row, col):
        """Create a statistics card."""
        card = ttk.Frame(parent, relief=tk.RIDGE, borderwidth=1, padding=15)
        card.grid(row=row, column=col, padx=10, pady=5, sticky='nsew')
        parent.columnconfigure(col, weight=1)

        ttk.Label(card, text=title, font=('Arial', 10)).pack()
        ttk.Label(card, text=str(value), font=('Arial', 18, 'bold')).pack(pady=5)

