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
from education_system.systems.university.domains.curriculum.domain.course_planning.services.planning_service import PlanningService
from education_system.systems.university.domains.assessment.domain.grading.grade_calculation.gpa import calculate_student_gpa
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.ui.field_pickers import attach_picker


class _PrerequisitesMixin:
    """Methods extracted from CoursePlanningGUI.prerequisites responsibility."""

    def _create_prerequisites_tab(self):
        """Add the prerequisites tab frame (content built lazily on first view)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.prerequisites.tabs.prerequisites', default="Prerequisites"))
        self._register_lazy_tab(tab, self._populate_prerequisites_tab)

    def _populate_prerequisites_tab(self, tab):
        """Build the prerequisites tab's content."""
        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.prerequisites.labels.course_id', default="Course ID:"), font=('Arial', 11)).pack(side=tk.LEFT, padx=5)
        # IdPicker.get() returns the course id, so the two call sites
        # below keep working unchanged.
        self.prereq_course_entry = attach_picker(control_frame, 'course', width=34)
        self.prereq_course_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.prerequisites.buttons.visualize_prerequisites', default="Visualize Prerequisites"),
                  command=self._visualize_prerequisites).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.prerequisites.buttons.check_eligibility', default="Check Eligibility"),
                  command=self._check_eligibility).pack(side=tk.LEFT, padx=5)

        # Display area
        display_frame = ttk.LabelFrame(tab, text=_t('gui.academics.course_management_gui.course_planning_gui.mixins.prerequisites.labels.prerequisite_visualization', default="Prerequisite Visualization"), padding=10)
        display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.prereq_text = scrolledtext.ScrolledText(display_frame, wrap=tk.WORD,
                                                     font=('Courier', 10), height=30)
        self.prereq_text.pack(fill=tk.BOTH, expand=True)

    def _visualize_prerequisites(self):
        """Visualize prerequisite chain."""
        course_id = self.prereq_course_entry.get().strip().upper()
        if not course_id:
            messagebox.showwarning(_t('gui.academics.course_management_gui.course_planning_gui.mixins.prerequisites.dialogs.warning', default="Warning"), _t('gui.academics.course_management_gui.course_planning_gui.mixins.prerequisites.dialogs.please_enter_a_course_id', default="Please enter a course ID."))
            return

        try:
            chain = self.planning_service.visualize_prerequisite_chain(course_id)
            tree = self.planning_service.build_prerequisite_tree(course_id)
            all_prereqs = self.planning_service.get_all_prerequisites(course_id)

            # Clear text
            self.prereq_text.delete(1.0, tk.END)

            # Display visualization
            self.prereq_text.insert(tk.END, f"=== Prerequisite Chain for {course_id} ===\n\n")
            self.prereq_text.insert(tk.END, f"Total Prerequisites: {len(all_prereqs)}\n")
            self.prereq_text.insert(tk.END, f"Prerequisite Depth: {tree.get('total_depth', 0)}\n\n")

            if len(chain) <= 1:
                self.prereq_text.insert(tk.END, "✓ No prerequisites required\n")
            else:
                self.prereq_text.insert(tk.END, "Prerequisite Levels (Foundation → Advanced):\n\n")
                for level, courses in enumerate(chain):
                    if level == len(chain) - 1:
                        self.prereq_text.insert(tk.END, f"Level {level} (Target):\n")
                    else:
                        self.prereq_text.insert(tk.END, f"Level {level}:\n")

                    for course in courses:
                        self.prereq_text.insert(tk.END, f"  • {course}\n")
                    self.prereq_text.insert(tk.END, "\n")

            self.status_bar.config(text=f"Visualized prerequisites for {course_id}")

        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.course_planning_gui.mixins.prerequisites.dialogs.error', default="Error"), f"Failed to visualize prerequisites: {e}")

    def _check_eligibility(self):
        """Check prerequisite eligibility."""
        course_id = self.prereq_course_entry.get().strip().upper()
        if not course_id:
            messagebox.showwarning(_t('gui.academics.course_management_gui.course_planning_gui.mixins.prerequisites.dialogs.warning', default="Warning"), _t('gui.academics.course_management_gui.course_planning_gui.mixins.prerequisites.dialogs.please_enter_a_course_id', default="Please enter a course ID."))
            return

        try:
            eligibility = self.planning_service.check_prerequisite_eligibility(
                self.student_id, course_id
            )

            # Clear text
            self.prereq_text.delete(1.0, tk.END)

            # Display eligibility
            self.prereq_text.insert(tk.END, f"=== Eligibility Check for {course_id} ===\n\n")

            if eligibility['eligible']:
                self.prereq_text.insert(tk.END, "✓ ELIGIBLE - You can take this course!\n\n")
            else:
                self.prereq_text.insert(tk.END, "✗ NOT ELIGIBLE - Prerequisites not met\n\n")

            self.prereq_text.insert(tk.END, f"Total Prerequisites: {eligibility['total_prerequisites']}\n\n")

            if eligibility['met_prerequisites']:
                self.prereq_text.insert(tk.END, f"✓ Met Prerequisites ({len(eligibility['met_prerequisites'])}):\n")
                for prereq in eligibility['met_prerequisites']:
                    self.prereq_text.insert(tk.END,
                        f"  • {prereq['course_id']}: Grade {prereq['grade']} "
                        f"(Required: {prereq['required_grade']})\n")
                self.prereq_text.insert(tk.END, "\n")

            if eligibility['missing_prerequisites']:
                self.prereq_text.insert(tk.END, f"✗ Missing Prerequisites ({len(eligibility['missing_prerequisites'])}):\n")
                for prereq in eligibility['missing_prerequisites']:
                    self.prereq_text.insert(tk.END,
                        f"  • {prereq['course_id']}: {prereq['reason']} ({prereq['status']})\n")

            self.status_bar.config(text=f"Checked eligibility for {course_id}")

        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.course_planning_gui.mixins.prerequisites.dialogs.error', default="Error"), f"Failed to check eligibility: {e}")

