"""Split from course_planning_gui.py — provides mixins assembled in
course_planning_gui/__init__.py into the final CoursePlanningGUI class."""
from __future__ import annotations

import json
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from typing import Optional, Dict, List

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.modules.domain.academics.course_planning.services.planning_service import PlanningService
from education_system.post_18.university_system.modules.domain.academics.grading.grade_calculation.gpa import calculate_student_gpa
from education_system.post_18.university_system.core.activity_logger import log_activity


class _PrerequisitesMixin:
    """Methods extracted from CoursePlanningGUI.prerequisites responsibility."""

    def _create_prerequisites_tab(self):
        """Add the prerequisites tab frame (content built lazily on first view)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Prerequisites")
        self._register_lazy_tab(tab, self._populate_prerequisites_tab)

    def _populate_prerequisites_tab(self, tab):
        """Build the prerequisites tab's content."""
        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text="Course ID:", font=('Arial', 11)).pack(side=tk.LEFT, padx=5)
        self.prereq_course_entry = ttk.Entry(control_frame, width=15, font=('Arial', 11))
        self.prereq_course_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="Visualize Prerequisites",
                  command=self._visualize_prerequisites).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Check Eligibility",
                  command=self._check_eligibility).pack(side=tk.LEFT, padx=5)

        # Display area
        display_frame = ttk.LabelFrame(tab, text="Prerequisite Visualization", padding=10)
        display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.prereq_text = scrolledtext.ScrolledText(display_frame, wrap=tk.WORD,
                                                     font=('Courier', 10), height=30)
        self.prereq_text.pack(fill=tk.BOTH, expand=True)

    def _visualize_prerequisites(self):
        """Visualize prerequisite chain."""
        course_id = self.prereq_course_entry.get().strip().upper()
        if not course_id:
            messagebox.showwarning("Warning", "Please enter a course ID.")
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
            messagebox.showerror("Error", f"Failed to visualize prerequisites: {e}")

    def _check_eligibility(self):
        """Check prerequisite eligibility."""
        course_id = self.prereq_course_entry.get().strip().upper()
        if not course_id:
            messagebox.showwarning("Warning", "Please enter a course ID.")
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
            messagebox.showerror("Error", f"Failed to check eligibility: {e}")

