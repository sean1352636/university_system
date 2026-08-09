"""Split from course_planning_gui.py — provides mixins assembled in
course_planning_gui/__init__.py into the final CoursePlanningGUI class."""
from __future__ import annotations

from education_system.systems.university.infrastructure.i18n import get_text as _t

import json
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from typing import Optional, Dict, List

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.domains.academics.domain.course_planning.services.planning_service import PlanningService
from education_system.systems.university.domains.assessment.domain.grading.grade_calculation.gpa import calculate_student_gpa
from education_system.systems.university.infrastructure.activity_logger import log_activity


class _RecommendationsMixin:
    """Methods extracted from CoursePlanningGUI.recommendations responsibility."""

    def _create_recommendations_tab(self):
        """Add the recommendations tab frame (content built lazily on first view)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.recommendations.tabs.recommendations', default="Recommendations"))
        self._register_lazy_tab(tab, self._populate_recommendations_tab)

    def _populate_recommendations_tab(self, tab):
        """Build the recommendations tab's content."""
        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.recommendations.labels.target_semester', default="Target Semester:"), font=('Arial', 11)).pack(side=tk.LEFT, padx=5)
        self.rec_semester_entry = ttk.Entry(control_frame, width=15, font=('Arial', 11))
        self.rec_semester_entry.insert(0, "Fall 2026")
        self.rec_semester_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.recommendations.buttons.get_recommendations', default="Get Recommendations"),
                  command=self._get_recommendations).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.recommendations.buttons.refresh', default="Refresh"),
                  command=self._get_recommendations).pack(side=tk.LEFT, padx=5)

        # Recommendations display
        rec_frame = ttk.LabelFrame(tab, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.recommendations.labels.recommended_courses', default="Recommended Courses"), padding=10)
        rec_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create treeview for recommendations
        columns = ('Course ID', 'Course Name', 'Credits', 'Score', 'Reason')
        self.rec_tree = ttk.Treeview(rec_frame, columns=columns, show='tree headings', height=20)

        for col in columns:
            self.rec_tree.heading(col, text=col)
            self.rec_tree.column(col, width=150)

        self.rec_tree.pack(fill=tk.BOTH, expand=True)

        # Scrollbar
        rec_scrollbar = ttk.Scrollbar(rec_frame, orient=tk.VERTICAL, command=self.rec_tree.yview)
        rec_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.rec_tree.configure(yscrollcommand=rec_scrollbar.set)

        # Button to add to plan
        ttk.Button(rec_frame, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.recommendations.buttons.add_selected_to_plan', default="Add Selected to Plan"),
                  command=self._add_recommended_course).pack(pady=10)

    def _get_recommendations(self):
        """Get course recommendations."""
        semester = self.rec_semester_entry.get().strip() or "Fall 2026"

        try:
            recommendations = self.planning_service.recommend_courses(
                self.student_id, semester, max_recommendations=20
            )

            # Clear tree
            for item in self.rec_tree.get_children():
                self.rec_tree.delete(item)

            if not recommendations:
                self.rec_tree.insert('', tk.END, text="No recommendations available")
                return

            # Populate tree
            for rec in recommendations:
                score_stars = "★" * int(rec['relevance_score']) + "☆" * (5 - int(rec['relevance_score']))
                self.rec_tree.insert('', tk.END, values=(
                    rec['course_id'],
                    rec['course_name'],
                    rec['credits'],
                    f"{score_stars} ({rec['relevance_score']})",
                    rec['reason']
                ))

            self.status_bar.config(text=f"Loaded {len(recommendations)} recommendations")

        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.course_planning_gui.mixins.recommendations.dialogs.error', default="Error"), f"Failed to get recommendations: {e}")

    def _add_recommended_course(self):
        """Add selected recommended course to plan."""
        if not self.current_plan_id:
            messagebox.showwarning(_t('gui.academics.course_management_gui.course_planning_gui.mixins.recommendations.dialogs.warning', default="Warning"), _t('gui.academics.course_management_gui.course_planning_gui.mixins.recommendations.dialogs.please_load_a_plan_first', default="Please load a plan first."))
            return

        selection = self.rec_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.course_management_gui.course_planning_gui.mixins.recommendations.dialogs.warning', default="Warning"), _t('gui.academics.course_management_gui.course_planning_gui.mixins.recommendations.dialogs.please_select_a_course_to_add', default="Please select a course to add."))
            return

        item = selection[0]
        values = self.rec_tree.item(item, 'values')
        course_id = values[0]

        # Simple dialog for semester
        semester_num = tk.simpledialog.askinteger(
            "Add Course",
            f"Add {course_id} to which semester?",
            minvalue=1, maxvalue=10
        )

        if not semester_num:
            return

        semester_name = tk.simpledialog.askstring(
            "Add Course",
            "Semester name (e.g., Fall 2026):"
        )

        if not semester_name:
            return

        try:
            self.planning_service.add_course_to_plan(
                plan_id=self.current_plan_id,
                course_id=course_id,
                semester_number=semester_num,
                semester_name=semester_name
            )

            messagebox.showinfo(_t('gui.academics.course_management_gui.course_planning_gui.mixins.recommendations.dialogs.success', default="Success"), f"Course {course_id} added to Semester {semester_num}!")
            self.current_plan_data = self.planning_service.get_semester_plan(self.current_plan_id)
            self._display_planner_content()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.course_planning_gui.mixins.recommendations.dialogs.error', default="Error"), f"Failed to add course: {e}")

