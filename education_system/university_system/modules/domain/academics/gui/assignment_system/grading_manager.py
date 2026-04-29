"""Grade management and rubric grading"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
import json
import csv
from PIL import Image, ImageTk
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.shared.constants import paths
from collections import deque



class GradingManager:
    """Grade management and rubric grading"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def show_grade_submissions(self):
        """Show grading interface"""
        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text="Grade Submissions", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Create main grading interface
        grading_frame = ttk.PanedWindow(self.gui.layout.content_area, orient='horizontal')
        grading_frame.pack(fill='both', expand=True)

        # Left panel - submissions list
        left_panel = ttk.Frame(grading_frame)
        grading_frame.add(left_panel, weight=1)

        ttk.Label(left_panel, text="Ungraded Submissions", style='Header.TLabel').pack(anchor='w', pady=(0, 10))

        # Submissions tree
        columns = ('ID', 'Student', 'Assignment', 'Submitted')
        self.grading_tree = ttk.Treeview(left_panel, columns=columns, show='headings', height=15)

        for col in columns:
            self.grading_tree.heading(col, text=col)
            self.grading_tree.column(col, width=120)

        self.grading_tree.pack(fill='both', expand=True)
        self.grading_tree.bind('<<TreeviewSelect>>', self.on_submission_select)

        # Right panel - grading interface
        right_panel = ttk.Frame(grading_frame)
        grading_frame.add(right_panel, weight=1)

        self.grading_details_frame = ttk.LabelFrame(right_panel, text="Grading Details", padding=10)
        self.grading_details_frame.pack(fill='both', expand=True)

        # Load ungraded submissions
        self.load_ungraded_submissions()

        # Refresh button
        refresh_btn = ttk.Button(left_panel, text="Refresh", command=self.load_ungraded_submissions)
        refresh_btn.pack(pady=(10, 0))


    def load_ungraded_submissions(self):
        """Load ungraded submissions"""
        # Clear existing items
        for item in self.grading_tree.get_children():
            self.grading_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.id, s.student_id, st.first_name, st.last_name, a.title, s.submission_date
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN students st ON s.student_id = st.student_id
            WHERE s.grade IS NULL AND s.status = 'submitted'
            ORDER BY s.submission_date
            ''')

            submissions = cursor.fetchall()

            for submission in submissions:
                sid, student_id, fname, lname, title, date = submission
                student_name = f"{fname} {lname}"
                self.grading_tree.insert('', 'end', values=(sid, student_name, title, date))

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load submissions: {e}")


    def on_submission_select(self, event):
        """Handle submission selection for grading"""
        selection = self.grading_tree.selection()
        if not selection:
            return

        item = self.grading_tree.item(selection[0])
        submission_id = item['values'][0]

        self.show_grading_interface(submission_id)


    def show_grading_interface(self, submission_id):
        """Show grading interface for selected submission"""
        # Clear existing grading interface
        for widget in self.grading_details_frame.winfo_children():
            widget.destroy()

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get submission details
            cursor.execute('''
            SELECT s.*, a.title, a.max_marks, st.first_name, st.last_name, a.module_code
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN students st ON s.student_id = st.student_id
            WHERE s.id = ?
            ''', (submission_id,))

            submission = cursor.fetchone()
            if not submission:
                return

            # Cache identifiers used by the attendance integration
            student_id_for_attendance = submission[1]
            module_code_for_attendance = submission[16]

            # Display submission details
            details_text = f"Student: {submission[14]} {submission[15]}\n"
            details_text += f"Assignment: {submission[11]}\n"
            details_text += f"Module: {module_code_for_attendance}\n"
            details_text += f"File: {submission[6]}\n"
            details_text += f"Submitted: {submission[4]}\n"
            details_text += f"Max Marks: {submission[12]}"

            ttk.Label(self.grading_details_frame, text=details_text, justify='left').pack(anchor='w', pady=(0, 10))

            # Inline attendance warning (rendered only when below threshold)
            try:
                warning = self.gui.attendance_warning(
                    student_id_for_attendance, module_code_for_attendance
                )
            except Exception:
                warning = None
            if warning:
                tk.Label(
                    self.grading_details_frame,
                    text=f"⚠ {warning}",
                    fg='#c0392b',
                    wraplength=520,
                    justify='left',
                    anchor='w',
                ).pack(fill='x', pady=(0, 10))

            # File / context actions
            file_frame = ttk.Frame(self.grading_details_frame)
            file_frame.pack(fill='x', pady=(0, 20))

            ttk.Button(file_frame, text="Open File",
                      command=lambda: self.open_submission_file(submission[5])).pack(side='left', padx=(0, 10))
            ttk.Button(file_frame, text="Download File",
                      command=lambda: self.download_file(submission[5])).pack(side='left', padx=(0, 10))
            ttk.Button(
                file_frame, text="Attendance",
                command=lambda: self.gui.show_student_attendance(
                    student_id_for_attendance, module_code_for_attendance,
                ),
            ).pack(side='left', padx=(0, 10))
            ttk.Button(
                file_frame, text="Module Resources",
                command=lambda: self.gui.show_module_resources(
                    module_code_for_attendance, student_id=student_id_for_attendance,
                ),
            ).pack(side='left')

            # Grading form
            grading_form = ttk.LabelFrame(self.grading_details_frame, text="Grade Assignment", padding=10)
            grading_form.pack(fill='x', pady=(0, 20))

            # Grade input
            ttk.Label(grading_form, text=f"Grade (0-{submission[12]}):").grid(row=0, column=0, sticky='w', pady=5)
            self.grade_var = tk.StringVar()
            grade_entry = ttk.Entry(grading_form, textvariable=self.grade_var, width=10)
            grade_entry.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))

            # Percentage display
            self.percentage_var = tk.StringVar()
            percentage_label = ttk.Label(grading_form, textvariable=self.percentage_var)
            percentage_label.grid(row=0, column=2, sticky='w', pady=5, padx=(10, 0))

            # Update percentage when grade changes
            grade_entry.bind('<KeyRelease>', lambda e: self.update_percentage(submission[12]))

            # Feedback
            ttk.Label(grading_form, text="Feedback:").grid(row=1, column=0, sticky='nw', pady=5)
            self.feedback_text = scrolledtext.ScrolledText(grading_form, height=6, width=50)
            self.feedback_text.grid(row=1, column=1, columnspan=2, sticky='ew', pady=5, padx=(10, 0))

            grading_form.grid_columnconfigure(1, weight=1)

            # Submit grade button
            submit_grade_btn = ttk.Button(grading_form, text="Submit Grade",
                                        command=lambda: self.submit_grade(submission_id, submission[12]))
            submit_grade_btn.grid(row=2, column=1, sticky='e', pady=(20, 0))

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load submission details: {e}")


    def update_percentage(self, max_marks):
        """Update percentage display"""
        try:
            grade = float(self.grade_var.get()) if self.grade_var.get() else 0
            percentage = (grade / max_marks) * 100
            self.percentage_var.set(f"({percentage:.1f}%)")
        except ValueError:
            self.percentage_var.set("(0.0%)")


    def submit_grade(self, submission_id, max_marks):
        """Submit grade for submission"""
        try:
            grade = float(self.grade_var.get())
            if not (0 <= grade <= max_marks):
                messagebox.showerror("Error", f"Grade must be between 0 and {max_marks}")
                return
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid grade")
            return

        feedback = self.feedback_text.get(1.0, tk.END).strip()
        percentage = (grade / max_marks) * 100

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            UPDATE assignment_submissions
            SET grade = ?, graded_by = ?, graded_date = ?, feedback = ?
            WHERE id = ?
            ''', (percentage, self.auth.current_user['id'],
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), feedback, submission_id))

            # Get submission details for email
            cursor.execute('''
                SELECT s.student_id, s.first_name, s.last_name, s.email_address,
                       a.title, a.module_code, m.module_name
                FROM assignment_submissions asub
                JOIN students s ON asub.student_id = s.student_id
                JOIN assignments a ON asub.assignment_id = a.id
                JOIN modules m ON a.module_code = m.module_code
                WHERE asub.id = ?
            ''', (submission_id,))

            submission_details = cursor.fetchone()

            conn.commit()
            conn.close()

            # Send grade release email
            if submission_details:
                try:
                    self._send_grade_release_email(
                        student_id=submission_details[0],
                        student_name=f"{submission_details[1]} {submission_details[2]}",
                        student_email=submission_details[3],
                        assignment_title=submission_details[4],
                        module_code=submission_details[5],
                        module_name=submission_details[6],
                        grade=percentage,
                        max_marks=max_marks,
                        feedback=feedback
                    )
                except Exception as email_error:
                    print(f"Warning: Failed to send grade email: {email_error}")

            # Mirror final grade into the gradebook so transcripts pick it up
            if submission_details:
                try:
                    from education_system.university_system.modules.domain.academics.gui.assignment_system.integrations import (
                        sync_grade_to_gradebook,
                        push_assignment_kpi,
                    )
                    grader = (
                        self.auth.current_user.get('username')
                        if self.auth and self.auth.current_user else None
                    )
                    sync_grade_to_gradebook(
                        student_id=submission_details[0],
                        module_code=submission_details[5],
                        assessment_name=submission_details[4],
                        grade_value=grade,
                        max_marks=max_marks,
                        instructor=grader,
                        is_final=True,
                    )
                    # Best-effort KPI push — runs only if a matching KPI is registered
                    push_assignment_kpi("Average Assignment Grade", percentage)
                except Exception as gradebook_err:
                    print(f"Warning: gradebook/KPI sync failed: {gradebook_err}")

            messagebox.showinfo("Success", f"Grade submitted: {percentage:.1f}% ({grade}/{max_marks})")

            # Refresh the submissions list
            self.load_ungraded_submissions()

            # Clear grading interface
            for widget in self.grading_details_frame.winfo_children():
                widget.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit grade: {e}")


    def grade_with_rubrics(self):
        """Enhanced grading interface with rubric support"""
        if not self._check_permission('manage_assignments'):
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text="Grade with Rubrics", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Create grading interface with rubric selection
        grading_frame = ttk.PanedWindow(self.gui.layout.content_area, orient='horizontal')
        grading_frame.pack(fill='both', expand=True)

        # Left panel - submissions
        left_panel = ttk.Frame(grading_frame)
        grading_frame.add(left_panel, weight=1)

        ttk.Label(left_panel, text="Ungraded Submissions", style='Header.TLabel').pack(anchor='w', pady=(0, 10))

        # Submissions tree
        columns = ('ID', 'Student', 'Assignment', 'Submitted')
        self.rubric_grading_tree = ttk.Treeview(left_panel, columns=columns, show='headings', height=15)

        for col in columns:
            self.rubric_grading_tree.heading(col, text=col)
            self.rubric_grading_tree.column(col, width=120)

        self.rubric_grading_tree.pack(fill='both', expand=True)
        self.rubric_grading_tree.bind('<<TreeviewSelect>>', self.on_rubric_submission_select)

        # Right panel - rubric grading
        right_panel = ttk.Frame(grading_frame)
        grading_frame.add(right_panel, weight=2)

        self.rubric_grading_frame = ttk.LabelFrame(right_panel, text="Rubric Grading", padding=10)
        self.rubric_grading_frame.pack(fill='both', expand=True)

        # Load submissions
        self.load_rubric_grading_submissions()


    def load_rubric_grading_submissions(self):
        """Load submissions for rubric grading"""
        # Clear existing items
        for item in self.rubric_grading_tree.get_children():
            self.rubric_grading_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.id, s.student_id, st.first_name, st.last_name, a.title, s.submission_date, a.rubric_id
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN students st ON s.student_id = st.student_id
            WHERE s.grade IS NULL AND s.status = 'submitted' AND a.rubric_id IS NOT NULL
            ORDER BY s.submission_date
            ''')

            submissions = cursor.fetchall()

            for submission in submissions:
                sid, student_id, fname, lname, title, date, rubric_id = submission
                student_name = f"{fname} {lname}"
                self.rubric_grading_tree.insert('', 'end', values=(sid, student_name, title, date))

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load submissions: {e}")


    def on_rubric_submission_select(self, event):
        """Handle submission selection for rubric grading"""
        selection = self.rubric_grading_tree.selection()
        if not selection:
            return

        item = self.rubric_grading_tree.item(selection[0])
        submission_id = item['values'][0]

        self.show_rubric_grading_interface(submission_id)


    def show_rubric_grading_interface(self, submission_id):
        """Show rubric grading interface for selected submission"""
        # Clear existing interface
        for widget in self.rubric_grading_frame.winfo_children():
            widget.destroy()

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get submission and rubric details
            cursor.execute('''
            SELECT s.*, a.title, a.rubric_id, st.first_name, st.last_name
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN students st ON s.student_id = st.student_id
            WHERE s.id = ?
            ''', (submission_id,))

            submission = cursor.fetchone()
            if not submission:
                return

            rubric_id = submission[12]  # rubric_id from assignments table

            # Display submission info
            info_text = f"Student: {submission[13]} {submission[14]}\nAssignment: {submission[11]}\nFile: {submission[6]}"
            ttk.Label(self.rubric_grading_frame, text=info_text, justify='left').pack(anchor='w', pady=(0, 20))

            # Get rubric criteria
            cursor.execute('''
            SELECT id, criteria_name, criteria_description, max_points
            FROM rubric_criteria
            WHERE rubric_id = ?
            ORDER BY order_index
            ''', (rubric_id,))

            criteria = cursor.fetchall()

            if not criteria:
                ttk.Label(self.rubric_grading_frame, text="No rubric criteria found").pack()
                conn.close()
                return

            # Create rubric grading interface
            criteria_frame = ttk.LabelFrame(self.rubric_grading_frame, text="Grading Criteria", padding=10)
            criteria_frame.pack(fill='both', expand=True)

            self.criteria_scores = {}
            self.criteria_feedback = {}

            for criterion in criteria:
                crit_id, name, desc, max_points = criterion

                crit_frame = ttk.LabelFrame(criteria_frame, text=f"{name} (Max: {max_points} points)", padding=5)
                crit_frame.pack(fill='x', pady=5)

                if desc:
                    ttk.Label(crit_frame, text=desc, font=('Arial', 9)).pack(anchor='w')

                # Score input
                score_frame = ttk.Frame(crit_frame)
                score_frame.pack(fill='x', pady=5)

                ttk.Label(score_frame, text="Score:").pack(side='left')
                score_var = tk.StringVar()
                self.criteria_scores[crit_id] = score_var
                ttk.Entry(score_frame, textvariable=score_var, width=8).pack(side='left', padx=5)
                ttk.Label(score_frame, text=f"/ {max_points}").pack(side='left')

                # Feedback
                ttk.Label(crit_frame, text="Feedback:").pack(anchor='w', pady=(5, 0))
                feedback_text = tk.Text(crit_frame, height=2, width=50)
                feedback_text.pack(fill='x', pady=2)
                self.criteria_feedback[crit_id] = feedback_text

            # Overall feedback
            overall_frame = ttk.LabelFrame(self.rubric_grading_frame, text="Overall Feedback", padding=10)
            overall_frame.pack(fill='x', pady=(10, 0))

            self.overall_feedback_text = scrolledtext.ScrolledText(overall_frame, height=4, width=50)
            self.overall_feedback_text.pack(fill='x')

            # Submit button
            submit_frame = ttk.Frame(self.rubric_grading_frame)
            submit_frame.pack(fill='x', pady=(10, 0))

            ttk.Button(submit_frame, text="Calculate Total & Submit Grade",
                      command=lambda: self.submit_rubric_grade(submission_id, criteria)).pack(side='right')

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load rubric grading interface: {e}")


    def submit_rubric_grade(self, submission_id, criteria):
        """Submit grade using rubric"""
        try:
            total_earned = 0
            total_possible = 0

            # Validate and calculate scores
            for criterion in criteria:
                crit_id, name, desc, max_points = criterion
                score_var = self.criteria_scores[crit_id]

                try:
                    score = float(score_var.get() or 0)
                    if not (0 <= score <= max_points):
                        messagebox.showerror("Error", f"Score for {name} must be between 0 and {max_points}")
                        return
                    total_earned += score
                    total_possible += max_points
                except ValueError:
                    messagebox.showerror("Error", f"Invalid score for {name}")
                    return

            if total_possible == 0:
                messagebox.showerror("Error", "No criteria points available")
                return

            # Calculate percentage
            percentage = (total_earned / total_possible) * 100

            # Confirm grade submission
            result = messagebox.askyesno("Confirm Grade",
                                        f"Total Score: {total_earned}/{total_possible} ({percentage:.1f}%)\n\n"
                                        f"Submit this grade?")
            if not result:
                return

            # Save to database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                overall_feedback = self.overall_feedback_text.get(1.0, tk.END).strip()

                # Update main submission
                cursor.execute('''
                UPDATE assignment_submissions
                SET grade = ?, graded_by = ?, graded_date = ?, feedback = ?
                WHERE id = ?
                ''', (percentage, self.auth.current_user['id'], timestamp, overall_feedback, submission_id))

                # Save individual criterion grades
                for criterion in criteria:
                    crit_id, name, desc, max_points = criterion
                    score = float(self.criteria_scores[crit_id].get() or 0)
                    feedback = self.criteria_feedback[crit_id].get(1.0, tk.END).strip()

                    cursor.execute('''
                    INSERT INTO grades (submission_id, rubric_criteria_id, points_earned, max_points,
                                      percentage, feedback, graded_by, graded_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (submission_id, crit_id, score, max_points,
                          (score/max_points)*100, feedback, self.auth.current_user['id'], timestamp))

                conn.commit()

                # Send grade notification email
                try:
                    # Get student email and assignment details
                    cursor.execute('''
                    SELECT s.email_address, a.title, a.module_code
                    FROM assignment_submissions sub
                    JOIN students s ON sub.student_id = s.student_id
                    JOIN assignments a ON sub.assignment_id = a.id
                    WHERE sub.id = ?
                    ''', (submission_id,))
                    result = cursor.fetchone()

                    if result:
                        student_email, assignment_title, module_code = result
                        from education_system.university_system.infrastructure.email.email_service import send_grade_notification
                        import logging
                        send_grade_notification(
                            student_email,
                            assignment_title,
                            module_code,
                            f"{percentage:.1f}%",
                            overall_feedback if overall_feedback else None
                        )
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to send grade notification email: {e}")

            finally:
                conn.close()

            messagebox.showinfo("Success", f"Grade submitted: {percentage:.1f}% ({total_earned}/{total_possible})")

            # Refresh submissions list
            self.load_rubric_grading_submissions()

            # Clear grading interface
            for widget in self.rubric_grading_frame.winfo_children():
                widget.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit grade: {e}")

    # SYSTEM MAINTENANCE METHOD

    def show_detailed_grading(self):
        """Show detailed grading interface with rubric support"""
        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text="Detailed Grading", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Create main grading interface with rubric support
        grading_frame = ttk.PanedWindow(self.gui.layout.content_area, orient='horizontal')
        grading_frame.pack(fill='both', expand=True)

        # Left panel - submissions list (same as existing)
        left_panel = ttk.Frame(grading_frame)
        grading_frame.add(left_panel, weight=1)

        ttk.Label(left_panel, text="Submissions to Grade", style='Header.TLabel').pack(anchor='w', pady=(0, 10))

        # Right panel - enhanced grading with rubric
        right_panel = ttk.Frame(grading_frame)
        grading_frame.add(right_panel, weight=2)

        # Rubric selection
        rubric_frame = ttk.LabelFrame(right_panel, text="Select Grading Rubric", padding=10)
        rubric_frame.pack(fill='x', pady=(0, 10))

        self.rubric_var = tk.StringVar()
        rubric_combo = ttk.Combobox(rubric_frame, textvariable=self.rubric_var, width=40)
        rubric_combo.pack(side='left', padx=(0, 10))

        ttk.Button(rubric_frame, text="Load Rubric", command=self.load_rubric_for_grading).pack(side='left')

        # Detailed grading area
        self.detailed_grading_frame = ttk.Frame(right_panel)
        self.detailed_grading_frame.pack(fill='both', expand=True)


    def load_rubric_for_grading(self):
        """Load rubric criteria for detailed grading"""
        # Clear existing grading interface
        for widget in self.detailed_grading_frame.winfo_children():
            widget.destroy()

        if not self.rubric_var.get():
            ttk.Label(self.detailed_grading_frame, text="Please select a rubric").pack(pady=20)
            return

        # Create rubric-based grading interface
        criteria_frame = ttk.LabelFrame(self.detailed_grading_frame, text="Grading Criteria", padding=10)
        criteria_frame.pack(fill='both', expand=True)

        # Sample criteria (would be loaded from database)
        sample_criteria = [
            ("Content Quality", 25, "Quality and accuracy of content"),
            ("Organization", 20, "Structure and logical flow"),
            ("Writing Style", 15, "Grammar, clarity, and style"),
            ("Citations", 10, "Proper use of references")
        ]

        self.criteria_scores = {}
        total_frame = ttk.Frame(criteria_frame)

        for i, (name, max_points, description) in enumerate(sample_criteria):
            criterion_frame = ttk.LabelFrame(criteria_frame, text=f"{name} (Max: {max_points} points)", padding=5)
            criterion_frame.pack(fill='x', pady=5)

            ttk.Label(criterion_frame, text=description, font=('Arial', 9)).pack(anchor='w')

            score_frame = ttk.Frame(criterion_frame)
            score_frame.pack(fill='x', pady=5)

            ttk.Label(score_frame, text="Score:").pack(side='left')
            score_var = tk.StringVar()
            self.criteria_scores[name] = score_var
            ttk.Entry(score_frame, textvariable=score_var, width=8).pack(side='left', padx=5)
            ttk.Label(score_frame, text=f"/ {max_points}").pack(side='left')

            # Feedback for this criterion
            ttk.Label(criterion_frame, text="Feedback:").pack(anchor='w', pady=(5, 0))
            feedback_text = tk.Text(criterion_frame, height=2, width=50)
            feedback_text.pack(fill='x', pady=2)

        # Total score frame
        total_frame.pack(fill='x', pady=10)
        ttk.Button(total_frame, text="Calculate Total & Submit Grade",
                  command=self.calculate_and_submit_grade).pack(side='right')


    def calculate_and_submit_grade(self):
        """Calculate total grade from rubric scores"""
        total_score = 0
        max_total = 70  # Sum of sample max points

        for criterion, score_var in self.criteria_scores.items():
            try:
                score = float(score_var.get() or 0)
                total_score += score
            except ValueError:
                messagebox.showerror("Error", f"Invalid score for {criterion}")
                return

        percentage = (total_score / max_total) * 100

        result = messagebox.askyesno("Confirm Grade",
                                    f"Total Score: {total_score}/{max_total} ({percentage:.1f}%)\n\n"
                                    f"Submit this grade?")
        if result:
            messagebox.showinfo("Success", "Grade submitted successfully!")
            self.load_ungraded_submissions()  # Refresh list


    def grade_submission(self, submission_id=None):
        """Interactive grading interface for a specific submission or open grading workspace"""
        if submission_id:
            # Grade specific submission
            self.show_grading_interface(submission_id)
        else:
            # Show grading workspace
            self.show_grade_submissions()


    def _grade_simple(self, submission_id):
        """Simple grading without rubric - basic points-based grading"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get submission details
            cursor.execute('''
            SELECT s.*, a.title, a.max_marks, st.first_name, st.last_name
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN students st ON s.student_id = st.student_id
            WHERE s.id = ?
            ''', (submission_id,))

            submission = cursor.fetchone()
            conn.close()

            if not submission:
                messagebox.showerror("Error", "Submission not found")
                return

            # Create simple grading dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Grade Submission - {submission[11]}")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            # Submission info
            info_frame = ttk.LabelFrame(dialog, text="Submission Details", padding=10)
            info_frame.pack(fill='x', padx=10, pady=10)

            info_text = f"Student: {submission[14]} {submission[15]}\n"
            info_text += f"Assignment: {submission[11]}\n"
            info_text += f"File: {submission[6]}\n"
            info_text += f"Submitted: {submission[4]}\n"
            info_text += f"Max Marks: {submission[12]}"

            ttk.Label(info_frame, text=info_text, justify='left').pack(anchor='w')

            # File actions
            file_frame = ttk.Frame(info_frame)
            file_frame.pack(fill='x', pady=(10, 0))

            ttk.Button(file_frame, text="Open File",
                      command=lambda: self.open_submission_file(submission[5])).pack(side='left', padx=(0, 10))
            ttk.Button(file_frame, text="Download File",
                      command=lambda: self.download_file(submission[5])).pack(side='left')

            # Grading section
            grade_frame = ttk.LabelFrame(dialog, text="Grade", padding=10)
            grade_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            ttk.Label(grade_frame, text=f"Score (out of {submission[12]}):").pack(anchor='w', pady=(0, 5))

            score_frame = ttk.Frame(grade_frame)
            score_frame.pack(fill='x', pady=(0, 10))

            score_var = tk.StringVar()
            ttk.Entry(score_frame, textvariable=score_var, width=10).pack(side='left')
            ttk.Label(score_frame, text=f" / {submission[12]}").pack(side='left', padx=(5, 0))

            # Percentage display
            percentage_var = tk.StringVar()
            percentage_label = ttk.Label(score_frame, textvariable=percentage_var, font=('Arial', 10, 'bold'))
            percentage_label.pack(side='left', padx=(20, 0))

            def update_percentage(*args):
                try:
                    score = float(score_var.get()) if score_var.get() else 0
                    percentage = (score / submission[12]) * 100
                    percentage_var.set(f"({percentage:.1f}%)")
                except ValueError:
                    percentage_var.set("(0.0%)")

            score_var.trace('w', update_percentage)

            # Feedback
            ttk.Label(grade_frame, text="Feedback:").pack(anchor='w', pady=(10, 5))
            feedback_text = scrolledtext.ScrolledText(grade_frame, height=8, width=50)
            feedback_text.pack(fill='both', expand=True)

            # Submit button
            def submit_simple_grade():
                try:
                    score = float(score_var.get())
                    max_marks = submission[12]

                    if not (0 <= score <= max_marks):
                        messagebox.showerror("Error", f"Score must be between 0 and {max_marks}", parent=dialog)
                        return

                    feedback = feedback_text.get(1.0, tk.END).strip()
                    percentage = (score / max_marks) * 100

                    # Save to database
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    try:
                        cursor = conn.cursor()

                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        cursor.execute('''
                        UPDATE assignment_submissions
                        SET grade = ?, graded_by = ?, graded_date = ?, feedback = ?
                        WHERE id = ?
                        ''', (percentage, self.auth.current_user['id'], timestamp, feedback, submission_id))

                        conn.commit()
                    finally:
                        conn.close()

                    messagebox.showinfo("Success", f"Grade submitted: {percentage:.1f}% ({score}/{max_marks})", parent=dialog)
                    dialog.destroy()

                    # Refresh grading list if available
                    if hasattr(self, 'grading_tree'):
                        self.load_ungraded_submissions()

                except ValueError:
                    messagebox.showerror("Error", "Please enter a valid score", parent=dialog)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to submit grade: {e}", parent=dialog)

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))

            ttk.Button(button_frame, text="Submit Grade", command=submit_simple_grade,
                      style='Accent.TButton').pack(side='right')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=(0, 10))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open grading interface: {e}")


    def _launch_gui_feature(self, callback, feature_name):
        """Helper to launch GUI features with error handling"""
        try:
            callback()
        except Exception as e:
            messagebox.showerror("Error", f"Error launching {feature_name}: {str(e)}")


    def open_submission_file(self, file_path):
        """Open submission file with default application"""
        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("Error", "File not found")
            return

        try:
            import platform
            import subprocess

            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', file_path])
            else:  # Linux
                subprocess.run(['xdg-open', file_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}")


    def download_file(self, file_path):
        """Download (copy) submission file to user-selected location"""
        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("Error", "File not found")
            return

        try:
            # Get file name
            file_name = os.path.basename(file_path)

            # Ask user where to save
            save_path = filedialog.asksaveasfilename(
                initialfile=file_name,
                defaultextension=os.path.splitext(file_name)[1],
                filetypes=[("All files", "*.*")]
            )

            if save_path:
                shutil.copy2(file_path, save_path)
                messagebox.showinfo("Success", f"File saved to:\n{save_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to download file: {e}")

    def _send_grade_release_email(self, student_id, student_name, student_email,
                                   assignment_title, module_code, module_name,
                                   grade, max_marks, feedback):
        """Send email notification when grade is released"""
        if not student_email:
            print(f"Warning: No email address for student {student_id}")
            return

        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            # Use email template
            try:
                from education_system.university_system.infrastructure.email.template_utils import render_template
                subject, body = render_template("assignment_grade_released", {
                    "first_name": student_name.split()[0],
                    "module_code": module_code,
                    "module_name": module_name,
                    "assignment_title": assignment_title,
                    "grade_percentage": f"{grade:.1f}",
                    "grade_points": f"{grade * max_marks / 100:.1f}",
                    "max_marks": str(max_marks),
                    "feedback": feedback or 'No additional feedback provided.'
                })
            except Exception as template_error:
                # Fallback to hardcoded email
                subject = f"Grade Released: {assignment_title}"
                body = f"""Dear {student_name.split()[0]},

Your grade has been released for the following assignment:

Module: {module_code} - {module_name}
Assignment: {assignment_title}
Grade: {grade:.1f}% ({grade * max_marks / 100:.1f}/{max_marks})

Feedback:
{feedback or 'No additional feedback provided.'}

You can view your complete submission and grading details in the Assignment System.

Best regards,
Academic Administration Team
"""

            send_email(student_email, subject, body)
            print(f"Grade release email sent to {student_email}")

        except Exception as e:
            print(f"Failed to send grade release email: {e}")
            import traceback
            traceback.print_exc()


