"""
Peer Review Management GUI

Provides interface for:
- Submission management with revision tracking
- Review assignments and structured feedback
- Shared resource library with ratings and downloads
- Review cycle viewing and administration
- Admin cycle CRUD, reviewer assignment, and resource approval
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.peer_review_manager import PeerReviewManager
from education_system.post_18.university_system.modules.domain.operations.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_combobox, validate_integer_entry, show_validation_error
)


class PeerReviewGUI:
    """GUI for peer review management."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Peer Review Management")
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
        notebook.add(self.tab_frame, text="Peer Review")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Peer Review Management")
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

        self._create_my_submissions_tab()
        self._create_my_reviews_tab()
        self._create_shared_resources_tab()
        self._create_review_cycles_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_admin_tab()

    # ==================== TAB 1: MY SUBMISSIONS ====================

    def _create_my_submissions_tab(self):
        """Create my submissions tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Submissions")

        # Header with Refresh button
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="My Submissions", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_my_submissions).pack(side=tk.RIGHT, padx=5)

        # Submissions treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Title', 'Cycle', 'Type', 'Version', 'Status', 'Date')
        self.submissions_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.submissions_tree.yview)

        widths = {'ID': 50, 'Title': 220, 'Cycle': 80, 'Type': 120, 'Version': 60, 'Status': 120, 'Date': 140}
        for col in columns:
            self.submissions_tree.heading(col, text=col)
            self.submissions_tree.column(col, width=widths.get(col, 100))

        self.submissions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.submissions_tree.tag_configure('draft', background='#e2e3e5')
        self.submissions_tree.tag_configure('submitted', background='#cce5ff')
        self.submissions_tree.tag_configure('under_review', background='#fff3cd')
        self.submissions_tree.tag_configure('approved', background='#d4edda')
        self.submissions_tree.tag_configure('revisions_requested', background='#f8d7da')

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="New Submission",
                   command=self._new_submission_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Submit for Review",
                   command=self._submit_for_review).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Create Revision",
                   command=self._create_revision_dialog).pack(side=tk.LEFT, padx=5)

        self._load_my_submissions()

    def _load_my_submissions(self):
        """Load current user's submissions."""
        for item in self.submissions_tree.get_children():
            self.submissions_tree.delete(item)

        user_id = self._get_user_id()

        try:
            submissions = PeerReviewManager.get_submissions(submitter_id=user_id)
        except Exception:
            submissions = []

        for s in submissions:
            status = s.get('status', '').lower()
            display_status = status.replace('_', ' ').title()
            display_type = s.get('material_type', '').replace('_', ' ').title()

            self.submissions_tree.insert('', tk.END, values=(
                s.get('submission_id', ''),
                s.get('title', '')[:40],
                s.get('cycle_id', ''),
                display_type,
                s.get('version', 1),
                display_status,
                s.get('created_at', '')
            ), tags=(status,))

    def _new_submission_dialog(self):
        """Open dialog to create a new submission."""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Submission")
        dialog.geometry("550x500")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Cycle selector
        ttk.Label(frame, text="Cycle:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        cycle_combo = ttk.Combobox(frame, width=30, state='readonly')
        cycle_combo.grid(row=0, column=1, padx=10, pady=8)

        cycle_map = {}
        try:
            cycles = PeerReviewManager.get_cycles(status='active')
        except Exception:
            cycles = []

        combo_values = []
        for c in cycles:
            label = f"{c.get('name', '')} (#{c.get('cycle_id')})"
            combo_values.append(label)
            cycle_map[label] = c.get('cycle_id')
        cycle_combo['values'] = combo_values
        if combo_values:
            cycle_combo.current(0)

        # Title
        ttk.Label(frame, text="Title:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        title_entry = ttk.Entry(frame, width=35)
        title_entry.grid(row=1, column=1, padx=10, pady=8)

        # Description
        ttk.Label(frame, text="Description:").grid(row=2, column=0, sticky='ne', padx=10, pady=8)
        desc_text = tk.Text(frame, width=35, height=4)
        desc_text.grid(row=2, column=1, padx=10, pady=8)

        # Material type
        ttk.Label(frame, text="Material Type:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        material_combo = ttk.Combobox(
            frame,
            values=['lecture_notes', 'assessment', 'syllabus', 'lab_manual', 'presentation', 'other'],
            width=20, state='readonly'
        )
        material_combo.set('lecture_notes')
        material_combo.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Course code
        ttk.Label(frame, text="Course Code:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        course_entry = ttk.Entry(frame, width=20)
        course_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # File path
        ttk.Label(frame, text="File Path:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        file_path_entry = ttk.Entry(frame, width=35)
        file_path_entry.grid(row=5, column=1, padx=10, pady=8)

        def save():
            # Validate cycle selection
            try:
                cycle_label = validate_combobox(cycle_combo, "Cycle")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            selected_cycle_id = cycle_map.get(cycle_label)
            if not selected_cycle_id:
                messagebox.showerror("Error", "Please select a valid cycle.", parent=dialog)
                return

            # Validate required fields
            try:
                title = validate_entry(title_entry, "Title")
                description = validate_entry(desc_text, "Description")
                material_type = validate_combobox(material_combo, "Material Type")
                course_code = validate_entry(course_entry, "Course Code")
                file_path = validate_entry(file_path_entry, "File Path")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            # Derive file_name from file_path
            file_name = file_path.split('/')[-1] if '/' in file_path else file_path.split('\\')[-1] if '\\' in file_path else file_path

            try:
                submission_id = PeerReviewManager.create_submission(
                    cycle_id=selected_cycle_id,
                    submitter_id=self._get_user_id(),
                    title=title,
                    description=description,
                    material_type=material_type,
                    course_code=course_code,
                    file_path=file_path,
                    file_name=file_name
                )
                messagebox.showinfo("Success",
                                    f"Submission created. ID: {submission_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_my_submissions()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Create", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        title_entry.focus_set()

    def _submit_for_review(self):
        """Submit the selected draft submission for review."""
        selection = self.submissions_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a submission first.")
            return

        item = self.submissions_tree.item(selection[0])
        submission_id = item['values'][0]
        status = item['values'][5]

        if status.lower() != 'draft':
            messagebox.showinfo("Info", "Only draft submissions can be submitted for review.")
            return

        if not messagebox.askyesno("Confirm",
                                    f"Submit submission #{submission_id} for peer review?"):
            return

        try:
            PeerReviewManager.submit_for_review(submission_id)
            messagebox.showinfo("Success", "Submission sent for review.")
            self._load_my_submissions()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _create_revision_dialog(self):
        """Open dialog to create a revision of the selected submission."""
        selection = self.submissions_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a submission to revise.")
            return

        item = self.submissions_tree.item(selection[0])
        submission_id = item['values'][0]
        submission_title = item['values'][1]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Create Revision - {submission_title}")
        dialog.geometry("500x250")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Creating revision for submission #{submission_id}",
                  font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)

        # File path
        ttk.Label(frame, text="New File Path:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        file_path_entry = ttk.Entry(frame, width=35)
        file_path_entry.grid(row=1, column=1, padx=10, pady=8)

        # File name
        ttk.Label(frame, text="File Name:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        file_name_entry = ttk.Entry(frame, width=35)
        file_name_entry.grid(row=2, column=1, padx=10, pady=8)

        def save():
            try:
                file_path = validate_entry(file_path_entry, "File Path")
                file_name = validate_entry(file_name_entry, "File Name")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                new_id = PeerReviewManager.create_revision(
                    submission_id=submission_id,
                    file_path=file_path,
                    file_name=file_name
                )
                messagebox.showinfo("Success",
                                    f"Revision created. New submission ID: {new_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_my_submissions()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Create Revision", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        file_path_entry.focus_set()

    # ==================== TAB 2: MY REVIEWS ====================

    def _create_my_reviews_tab(self):
        """Create my reviews tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Reviews")

        # Header with Refresh button
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="My Review Assignments", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_my_reviews).pack(side=tk.RIGHT, padx=5)

        # Assignments treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Submission Title', 'Submitter', 'Due Date', 'Status')
        self.reviews_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.reviews_tree.yview)

        widths = {'ID': 50, 'Submission Title': 250, 'Submitter': 150, 'Due Date': 120, 'Status': 120}
        for col in columns:
            self.reviews_tree.heading(col, text=col)
            self.reviews_tree.column(col, width=widths.get(col, 100))

        self.reviews_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.reviews_tree.tag_configure('assigned', background='#cce5ff')
        self.reviews_tree.tag_configure('in_progress', background='#fff3cd')
        self.reviews_tree.tag_configure('completed', background='#d4edda')
        self.reviews_tree.tag_configure('declined', background='#f8d7da')

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Start Review",
                   command=self._start_review).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Submit Feedback",
                   command=self._submit_feedback_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Decline",
                   command=self._decline_assignment).pack(side=tk.LEFT, padx=5)

        # Cache assignment data for lookup
        self._assignments_cache = {}

        self._load_my_reviews()

    def _load_my_reviews(self):
        """Load current user's review assignments."""
        for item in self.reviews_tree.get_children():
            self.reviews_tree.delete(item)

        self._assignments_cache = {}
        user_id = self._get_user_id()

        try:
            assignments = PeerReviewManager.get_assignments(reviewer_id=user_id)
        except Exception:
            assignments = []

        # Build submission cache for titles and submitter info
        submission_cache = {}

        for a in assignments:
            assignment_id = a.get('assignment_id')
            submission_id = a.get('submission_id')
            status = a.get('status', '').lower()
            display_status = status.replace('_', ' ').title()

            # Fetch submission details if not cached
            if submission_id not in submission_cache:
                try:
                    sub = PeerReviewManager.get_submission(submission_id)
                    submission_cache[submission_id] = sub or {}
                except Exception:
                    submission_cache[submission_id] = {}

            sub_data = submission_cache.get(submission_id, {})
            submission_title = sub_data.get('title', '')[:40]
            submitter = sub_data.get('submitter_id', '')

            self.reviews_tree.insert('', tk.END, values=(
                assignment_id,
                submission_title,
                submitter,
                a.get('due_date', ''),
                display_status
            ), tags=(status,))

            self._assignments_cache[assignment_id] = a

    def _start_review(self):
        """Start the selected review assignment."""
        selection = self.reviews_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an assignment first.")
            return

        item = self.reviews_tree.item(selection[0])
        assignment_id = item['values'][0]
        status = item['values'][4]

        if status.lower() != 'assigned':
            messagebox.showinfo("Info", "Only assignments with 'Assigned' status can be started.")
            return

        try:
            PeerReviewManager.start_review(assignment_id)
            messagebox.showinfo("Success", "Review started.")
            self._load_my_reviews()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _submit_feedback_dialog(self):
        """Open dialog to submit feedback for the selected assignment."""
        selection = self.reviews_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an assignment first.")
            return

        item = self.reviews_tree.item(selection[0])
        assignment_id = item['values'][0]
        submission_title = item['values'][1]
        status = item['values'][4]

        if status.lower() not in ('assigned', 'in progress', 'in_progress'):
            messagebox.showinfo("Info", "Can only submit feedback for active assignments.")
            return

        assignment = self._assignments_cache.get(assignment_id, {})
        submission_id = assignment.get('submission_id')

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Submit Feedback - {submission_title}")
        dialog.geometry("600x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Scrollable content
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        frame = ttk.Frame(scroll_frame, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Feedback for: {submission_title}",
                  font=('Arial', 11, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)

        # Rating scales using Spinbox widgets
        ratings_frame = ttk.LabelFrame(frame, text="Ratings (1-5)", padding=10)
        ratings_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=10, pady=8)

        rating_labels = [
            ('Overall Rating:', 'overall_rating'),
            ('Content Quality:', 'content_quality'),
            ('Clarity:', 'clarity'),
            ('Alignment with Outcomes:', 'alignment_with_outcomes'),
            ('Engagement Potential:', 'engagement_potential'),
        ]
        rating_spinboxes = {}

        for i, (label, key) in enumerate(rating_labels):
            ttk.Label(ratings_frame, text=label).grid(row=i, column=0, sticky='e', padx=10, pady=5)
            spinbox = tk.Spinbox(ratings_frame, from_=1, to=5, width=5, state='readonly')
            spinbox.grid(row=i, column=1, sticky='w', padx=10, pady=5)
            rating_spinboxes[key] = spinbox

        # Strengths
        ttk.Label(frame, text="Strengths:").grid(row=2, column=0, sticky='ne', padx=10, pady=8)
        strengths_text = scrolledtext.ScrolledText(frame, width=45, height=4, wrap=tk.WORD)
        strengths_text.grid(row=2, column=1, padx=10, pady=8)

        # Improvements
        ttk.Label(frame, text="Improvements:").grid(row=3, column=0, sticky='ne', padx=10, pady=8)
        improvements_text = scrolledtext.ScrolledText(frame, width=45, height=4, wrap=tk.WORD)
        improvements_text.grid(row=3, column=1, padx=10, pady=8)

        # Detailed comments
        ttk.Label(frame, text="Detailed Comments:").grid(row=4, column=0, sticky='ne', padx=10, pady=8)
        comments_text = scrolledtext.ScrolledText(frame, width=45, height=4, wrap=tk.WORD)
        comments_text.grid(row=4, column=1, padx=10, pady=8)

        # Recommendation
        ttk.Label(frame, text="Recommendation:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        recommendation_combo = ttk.Combobox(
            frame,
            values=['approve', 'minor_revisions', 'major_revisions', 'reject'],
            width=20, state='readonly'
        )
        recommendation_combo.set('approve')
        recommendation_combo.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Confidential checkbox
        confidential_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Confidential feedback", variable=confidential_var).grid(
            row=6, column=1, sticky='w', padx=10, pady=8)

        def save():
            # Gather ratings
            try:
                overall_rating = int(rating_spinboxes['overall_rating'].get())
                content_quality = int(rating_spinboxes['content_quality'].get())
                clarity = int(rating_spinboxes['clarity'].get())
                alignment = int(rating_spinboxes['alignment_with_outcomes'].get())
                engagement = int(rating_spinboxes['engagement_potential'].get())
            except ValueError:
                messagebox.showerror("Validation Error",
                                     "All ratings must be valid numbers.", parent=dialog)
                return

            # Validate text fields
            try:
                strengths = validate_entry(strengths_text, "Strengths")
                improvements = validate_entry(improvements_text, "Improvements")
                detailed_comments = validate_entry(comments_text, "Detailed Comments")
                recommendation = validate_combobox(recommendation_combo, "Recommendation")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                feedback_id = PeerReviewManager.submit_feedback(
                    assignment_id=assignment_id,
                    submission_id=submission_id,
                    reviewer_id=self._get_user_id(),
                    overall_rating=overall_rating,
                    content_quality=content_quality,
                    clarity=clarity,
                    alignment_with_outcomes=alignment,
                    engagement_potential=engagement,
                    strengths=strengths,
                    improvements=improvements,
                    detailed_comments=detailed_comments,
                    recommendation=recommendation,
                    is_confidential=confidential_var.get()
                )
                messagebox.showinfo("Success",
                                    f"Feedback submitted. ID: {feedback_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_my_reviews()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Submit Feedback", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _decline_assignment(self):
        """Decline the selected review assignment."""
        selection = self.reviews_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an assignment first.")
            return

        item = self.reviews_tree.item(selection[0])
        assignment_id = item['values'][0]
        status = item['values'][4]

        if status.lower() not in ('assigned', 'in progress', 'in_progress'):
            messagebox.showinfo("Info", "Only active assignments can be declined.")
            return

        if not messagebox.askyesno("Confirm",
                                    f"Decline assignment #{assignment_id}?"):
            return

        try:
            PeerReviewManager.decline_assignment(assignment_id)
            messagebox.showinfo("Success", "Assignment declined.")
            self._load_my_reviews()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 3: SHARED RESOURCES ====================

    def _create_shared_resources_tab(self):
        """Create shared resources tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Shared Resources")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Shared Resources", style='Header.TLabel').pack(side=tk.LEFT)

        # Filter frame
        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)

        ttk.Label(filter_frame, text="Type:").pack(side=tk.LEFT, padx=5)
        self.resource_type_filter = ttk.Combobox(
            filter_frame,
            values=['All', 'template', 'rubric', 'example', 'lecture_notes',
                    'assessment', 'syllabus', 'lab_manual', 'presentation', 'other'],
            width=15, state='readonly'
        )
        self.resource_type_filter.set('All')
        self.resource_type_filter.pack(side=tk.LEFT, padx=5)
        self.resource_type_filter.bind('<<ComboboxSelected>>', lambda e: self._load_resources())

        ttk.Label(filter_frame, text="Subject:").pack(side=tk.LEFT, padx=5)
        self.resource_subject_filter = ttk.Entry(filter_frame, width=15)
        self.resource_subject_filter.pack(side=tk.LEFT, padx=5)

        ttk.Button(filter_frame, text="Refresh", command=self._load_resources).pack(side=tk.LEFT, padx=5)

        # Resources treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Title', 'Type', 'Subject', 'Shared By', 'Rating', 'Downloads', 'Approved')
        self.resources_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.resources_tree.yview)

        widths = {'ID': 50, 'Title': 200, 'Type': 100, 'Subject': 100,
                  'Shared By': 120, 'Rating': 70, 'Downloads': 70, 'Approved': 70}
        for col in columns:
            self.resources_tree.heading(col, text=col)
            self.resources_tree.column(col, width=widths.get(col, 100))

        self.resources_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Share Resource",
                   command=self._share_resource_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Rate",
                   command=self._rate_resource_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Download",
                   command=self._download_resource).pack(side=tk.LEFT, padx=5)

        self._load_resources()

    def _load_resources(self):
        """Load shared resources based on filters."""
        for item in self.resources_tree.get_children():
            self.resources_tree.delete(item)

        resource_type = self.resource_type_filter.get()
        subject_area = self.resource_subject_filter.get().strip()

        kwargs = {}
        if resource_type and resource_type != 'All':
            kwargs['resource_type'] = resource_type
        if subject_area:
            kwargs['subject_area'] = subject_area

        try:
            resources = PeerReviewManager.get_resources(**kwargs)
        except Exception:
            resources = []

        for r in resources:
            rating_count = r.get('rating_count', 0) or 0
            rating_sum = r.get('rating_sum', 0) or 0
            avg_rating = f"{rating_sum / rating_count:.1f}" if rating_count > 0 else 'N/A'
            is_approved = 'Yes' if r.get('is_approved') else 'No'
            display_type = r.get('resource_type', '').replace('_', ' ').title()

            self.resources_tree.insert('', tk.END, values=(
                r.get('resource_id', ''),
                r.get('title', '')[:35],
                display_type,
                r.get('subject_area', ''),
                r.get('shared_by', ''),
                avg_rating,
                r.get('download_count', 0),
                is_approved
            ))

    def _share_resource_dialog(self):
        """Open dialog to share a new resource."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Share Resource")
        dialog.geometry("550x500")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(frame, text="Title:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        title_entry = ttk.Entry(frame, width=35)
        title_entry.grid(row=0, column=1, padx=10, pady=8)

        # Description
        ttk.Label(frame, text="Description:").grid(row=1, column=0, sticky='ne', padx=10, pady=8)
        desc_text = tk.Text(frame, width=35, height=4)
        desc_text.grid(row=1, column=1, padx=10, pady=8)

        # Resource type
        ttk.Label(frame, text="Type:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        type_combo = ttk.Combobox(
            frame,
            values=['template', 'rubric', 'example', 'lecture_notes',
                    'assessment', 'syllabus', 'lab_manual', 'presentation', 'other'],
            width=20, state='readonly'
        )
        type_combo.set('template')
        type_combo.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Subject area
        ttk.Label(frame, text="Subject Area:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        subject_entry = ttk.Entry(frame, width=25)
        subject_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Course code
        ttk.Label(frame, text="Course Code:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        course_entry = ttk.Entry(frame, width=20)
        course_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # File path
        ttk.Label(frame, text="File Path:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        file_path_entry = ttk.Entry(frame, width=35)
        file_path_entry.grid(row=5, column=1, padx=10, pady=8)

        # File name
        ttk.Label(frame, text="File Name:").grid(row=6, column=0, sticky='e', padx=10, pady=8)
        file_name_entry = ttk.Entry(frame, width=35)
        file_name_entry.grid(row=6, column=1, padx=10, pady=8)

        def save():
            try:
                title = validate_entry(title_entry, "Title")
                description = validate_entry(desc_text, "Description")
                resource_type = validate_combobox(type_combo, "Type")
                subject_area = validate_entry(subject_entry, "Subject Area")
                course_code = validate_entry(course_entry, "Course Code")
                file_path = validate_entry(file_path_entry, "File Path")
                file_name = validate_entry(file_name_entry, "File Name")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                resource_id = PeerReviewManager.share_resource(
                    title=title,
                    description=description,
                    resource_type=resource_type,
                    subject_area=subject_area,
                    course_code=course_code,
                    file_path=file_path,
                    file_name=file_name,
                    shared_by=self._get_user_id()
                )
                messagebox.showinfo("Success",
                                    f"Resource shared. ID: {resource_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_resources()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Share", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        title_entry.focus_set()

    def _rate_resource_dialog(self):
        """Open dialog to rate the selected resource."""
        selection = self.resources_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a resource to rate.")
            return

        item = self.resources_tree.item(selection[0])
        resource_id = item['values'][0]
        resource_title = item['values'][1]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Rate Resource - {resource_title}")
        dialog.geometry("450x300")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Rate: {resource_title}",
                  font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)

        # Rating
        ttk.Label(frame, text="Rating (1-5):").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        rating_spinbox = tk.Spinbox(frame, from_=1, to=5, width=5, state='readonly')
        rating_spinbox.grid(row=1, column=1, sticky='w', padx=10, pady=8)

        # Comment
        ttk.Label(frame, text="Comment:").grid(row=2, column=0, sticky='ne', padx=10, pady=8)
        comment_text = scrolledtext.ScrolledText(frame, width=35, height=4, wrap=tk.WORD)
        comment_text.grid(row=2, column=1, padx=10, pady=8)

        def save():
            try:
                rating = int(rating_spinbox.get())
            except ValueError:
                messagebox.showerror("Validation Error",
                                     "Rating must be a valid number.", parent=dialog)
                return

            if rating < 1 or rating > 5:
                messagebox.showerror("Validation Error",
                                     "Rating must be between 1 and 5.", parent=dialog)
                return

            comment = comment_text.get("1.0", "end-1c").strip() or None

            try:
                PeerReviewManager.rate_resource(
                    resource_id=resource_id,
                    user_id=self._get_user_id(),
                    rating=rating,
                    comment=comment
                )
                messagebox.showinfo("Success", "Rating submitted.", parent=dialog)
                dialog.destroy()
                self._load_resources()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Submit Rating", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _download_resource(self):
        """Increment download count for the selected resource."""
        selection = self.resources_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a resource to download.")
            return

        item = self.resources_tree.item(selection[0])
        resource_id = item['values'][0]
        resource_title = item['values'][1]

        try:
            PeerReviewManager.increment_download(resource_id)
            messagebox.showinfo("Success",
                                f"Download recorded for '{resource_title}'.")
            self._load_resources()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 4: REVIEW CYCLES ====================

    def _create_review_cycles_tab(self):
        """Create review cycles tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Review Cycles")

        # Header with Refresh button
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Review Cycles", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_review_cycles).pack(side=tk.RIGHT, padx=5)

        # Cycles treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Name', 'Type', 'Department', 'Start', 'End', 'Status')
        self.cycles_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.cycles_tree.yview)

        widths = {'ID': 50, 'Name': 200, 'Type': 100, 'Department': 120,
                  'Start': 110, 'End': 110, 'Status': 100}
        for col in columns:
            self.cycles_tree.heading(col, text=col)
            self.cycles_tree.column(col, width=widths.get(col, 100))

        self.cycles_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.cycles_tree.tag_configure('draft', background='#e2e3e5')
        self.cycles_tree.tag_configure('active', background='#d4edda')
        self.cycles_tree.tag_configure('completed', background='#cce5ff')
        self.cycles_tree.tag_configure('archived', background='#e2e3e5')

        # Double-click to view cycle details
        self.cycles_tree.bind('<Double-1>', self._view_cycle_details)

        self._load_review_cycles()

    def _load_review_cycles(self):
        """Load all review cycles."""
        for item in self.cycles_tree.get_children():
            self.cycles_tree.delete(item)

        try:
            cycles = PeerReviewManager.get_cycles()
        except Exception:
            cycles = []

        for c in cycles:
            status = c.get('status', '').lower()
            display_status = status.replace('_', ' ').title()
            display_type = c.get('cycle_type', '').replace('_', ' ').title()

            self.cycles_tree.insert('', tk.END, values=(
                c.get('cycle_id', ''),
                c.get('name', '')[:35],
                display_type,
                c.get('department', ''),
                c.get('start_date', ''),
                c.get('end_date', ''),
                display_status
            ), tags=(status,))

    def _view_cycle_details(self, event):
        """View cycle details and submissions in a popup dialog."""
        selection = self.cycles_tree.selection()
        if not selection:
            return

        item = self.cycles_tree.item(selection[0])
        cycle_id = item['values'][0]
        cycle_name = item['values'][1]

        try:
            cycle = PeerReviewManager.get_cycle(cycle_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load cycle details: {e}")
            return

        if not cycle:
            messagebox.showerror("Error", "Cycle not found")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Cycle #{cycle_id} - {cycle_name}")
        dialog.geometry("750x600")
        dialog.transient(self.root)

        # Scrollable content
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Cycle details
        details_frame = ttk.LabelFrame(scroll_frame, text="Cycle Details", padding=15)
        details_frame.pack(fill=tk.X, padx=10, pady=10)

        fields = [
            ('Cycle ID', cycle.get('cycle_id')),
            ('Name', cycle.get('name', '')),
            ('Type', cycle.get('cycle_type', '').replace('_', ' ').title()),
            ('Department', cycle.get('department', '')),
            ('Start Date', cycle.get('start_date', '')),
            ('End Date', cycle.get('end_date', '')),
            ('Status', cycle.get('status', '').replace('_', ' ').title()),
            ('Description', cycle.get('description', '') or 'N/A'),
            ('Created', cycle.get('created_at', '')),
        ]

        for i, (label, value) in enumerate(fields):
            ttk.Label(details_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='ne', padx=(10, 5), pady=4)
            ttk.Label(details_frame, text=str(value), wraplength=400).grid(
                row=i, column=1, sticky='nw', padx=(5, 10), pady=4)

        # Submissions for this cycle
        subs_frame = ttk.LabelFrame(scroll_frame, text="Submissions in this Cycle", padding=10)
        subs_frame.pack(fill=tk.X, padx=10, pady=10)

        try:
            submissions = PeerReviewManager.get_submissions(cycle_id=cycle_id)
        except Exception:
            submissions = []

        if submissions:
            sub_cols = ('ID', 'Title', 'Submitter', 'Type', 'Version', 'Status')
            sub_tree = ttk.Treeview(subs_frame, columns=sub_cols, show='headings', height=8)

            sub_widths = {'ID': 50, 'Title': 200, 'Submitter': 120,
                          'Type': 100, 'Version': 60, 'Status': 100}
            for col in sub_cols:
                sub_tree.heading(col, text=col)
                sub_tree.column(col, width=sub_widths.get(col, 100))

            for s in submissions:
                sub_status = s.get('status', '').lower()
                sub_tree.insert('', tk.END, values=(
                    s.get('submission_id', ''),
                    s.get('title', '')[:35],
                    s.get('submitter_id', ''),
                    s.get('material_type', '').replace('_', ' ').title(),
                    s.get('version', 1),
                    sub_status.replace('_', ' ').title()
                ))
            sub_tree.pack(fill=tk.X)
        else:
            ttk.Label(subs_frame, text="No submissions in this cycle yet.").pack(anchor='w')

        # Statistics
        try:
            stats = PeerReviewManager.get_cycle_statistics(cycle_id)
        except Exception:
            stats = {}

        if stats:
            stats_frame = ttk.LabelFrame(scroll_frame, text="Cycle Statistics", padding=10)
            stats_frame.pack(fill=tk.X, padx=10, pady=10)

            avg_rating = stats.get('avg_overall_rating')
            avg_display = f"{avg_rating:.2f}" if avg_rating is not None else 'N/A'

            stat_fields = [
                ('Total Submissions', stats.get('total_submissions', 0)),
                ('Completed Reviews', stats.get('completed_reviews', 0)),
                ('Pending Reviews', stats.get('pending_reviews', 0)),
                ('Average Rating', avg_display),
            ]

            for i, (label, value) in enumerate(stat_fields):
                ttk.Label(stats_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                    row=i, column=0, sticky='e', padx=(10, 5), pady=3)
                ttk.Label(stats_frame, text=str(value)).grid(
                    row=i, column=1, sticky='w', padx=(5, 10), pady=3)

        # Close button
        btn_frame = ttk.Frame(scroll_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=15)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # ==================== TAB 5: ADMIN ====================

    def _create_admin_tab(self):
        """Create admin tab for peer review administration (admin only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Admin")

        # Scrollable content
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Cycle CRUD Section ----
        crud_frame = ttk.LabelFrame(scroll_frame, text="Create Review Cycle", padding=15)
        crud_frame.pack(fill=tk.X, padx=10, pady=10)

        # Name
        ttk.Label(crud_frame, text="Name:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.admin_cycle_name_entry = ttk.Entry(crud_frame, width=35)
        self.admin_cycle_name_entry.grid(row=0, column=1, columnspan=2, padx=10, pady=8, sticky='w')

        # Description
        ttk.Label(crud_frame, text="Description:").grid(row=1, column=0, sticky='ne', padx=10, pady=8)
        self.admin_cycle_desc_text = tk.Text(crud_frame, width=40, height=3)
        self.admin_cycle_desc_text.grid(row=1, column=1, columnspan=2, padx=10, pady=8, sticky='w')

        # Type
        ttk.Label(crud_frame, text="Type:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        self.admin_cycle_type_combo = ttk.Combobox(
            crud_frame, values=['annual', 'mid_term', 'ad_hoc'],
            width=20, state='readonly'
        )
        self.admin_cycle_type_combo.set('annual')
        self.admin_cycle_type_combo.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Department
        ttk.Label(crud_frame, text="Department:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        self.admin_cycle_dept_entry = ttk.Entry(crud_frame, width=25)
        self.admin_cycle_dept_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Start date
        ttk.Label(crud_frame, text="Start Date (YYYY-MM-DD):").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        self.admin_cycle_start_entry = ttk.Entry(crud_frame, width=15)
        self.admin_cycle_start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.admin_cycle_start_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # End date
        ttk.Label(crud_frame, text="End Date (YYYY-MM-DD):").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        self.admin_cycle_end_entry = ttk.Entry(crud_frame, width=15)
        self.admin_cycle_end_entry.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Buttons
        cycle_btn_frame = ttk.Frame(crud_frame)
        cycle_btn_frame.grid(row=6, column=0, columnspan=3, pady=15)
        ttk.Button(cycle_btn_frame, text="Create Cycle",
                   command=self._admin_create_cycle).pack(side=tk.LEFT, padx=5)
        ttk.Button(cycle_btn_frame, text="Activate",
                   command=self._admin_activate_cycle).pack(side=tk.LEFT, padx=5)

        # Cycle selector for activation
        activate_frame = ttk.Frame(crud_frame)
        activate_frame.grid(row=7, column=0, columnspan=3, pady=5)
        ttk.Label(activate_frame, text="Cycle to activate:").pack(side=tk.LEFT, padx=5)
        self.admin_activate_cycle_combo = ttk.Combobox(activate_frame, width=35, state='readonly')
        self.admin_activate_cycle_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(activate_frame, text="Refresh Cycles",
                   command=self._refresh_admin_cycle_lists).pack(side=tk.LEFT, padx=5)

        # Store cycle mapping for activation
        self.admin_cycle_map = {}

        # ---- Reviewer Assignment Section ----
        assign_frame = ttk.LabelFrame(scroll_frame, text="Assign Reviewer", padding=15)
        assign_frame.pack(fill=tk.X, padx=10, pady=10)

        # Submission selector
        ttk.Label(assign_frame, text="Submission:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.admin_submission_combo = ttk.Combobox(assign_frame, width=40, state='readonly')
        self.admin_submission_combo.grid(row=0, column=1, columnspan=2, padx=10, pady=8, sticky='w')

        # Store submission mapping
        self.admin_submission_map = {}

        # Reviewer ID
        ttk.Label(assign_frame, text="Reviewer ID:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        self.admin_reviewer_id_entry = ttk.Entry(assign_frame, width=25)
        self.admin_reviewer_id_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        # Due date
        ttk.Label(assign_frame, text="Due Date (YYYY-MM-DD):").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        self.admin_due_date_entry = ttk.Entry(assign_frame, width=15)
        self.admin_due_date_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Assign button
        ttk.Button(assign_frame, text="Assign",
                   command=self._admin_assign_reviewer).grid(row=3, column=1, padx=10, pady=15, sticky='w')

        # ---- Resource Approval Section ----
        approval_frame = ttk.LabelFrame(scroll_frame, text="Resource Approval", padding=15)
        approval_frame.pack(fill=tk.X, padx=10, pady=10)

        # Unapproved resources treeview
        approval_tree_frame = ttk.Frame(approval_frame)
        approval_tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        y_scroll = ttk.Scrollbar(approval_tree_frame, orient=tk.VERTICAL)
        approval_columns = ('ID', 'Title', 'Type', 'Shared By', 'Date')
        self.admin_approval_tree = ttk.Treeview(
            approval_tree_frame, columns=approval_columns, show='headings',
            yscrollcommand=y_scroll.set, height=6)
        y_scroll.config(command=self.admin_approval_tree.yview)

        approval_widths = {'ID': 50, 'Title': 200, 'Type': 120, 'Shared By': 150, 'Date': 140}
        for col in approval_columns:
            self.admin_approval_tree.heading(col, text=col)
            self.admin_approval_tree.column(col, width=approval_widths.get(col, 100))

        self.admin_approval_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Approve button
        approval_btn_frame = ttk.Frame(approval_frame)
        approval_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(approval_btn_frame, text="Approve",
                   command=self._admin_approve_resource).pack(side=tk.LEFT, padx=5)
        ttk.Button(approval_btn_frame, text="Refresh",
                   command=self._load_unapproved_resources).pack(side=tk.LEFT, padx=5)

        # ---- Statistics Section ----
        stats_frame = ttk.LabelFrame(scroll_frame, text="Statistics", padding=15)
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        self.admin_stats_text = tk.Text(stats_frame, width=70, height=10, state='disabled')
        self.admin_stats_text.pack(fill=tk.X, pady=5)

        ttk.Button(stats_frame, text="Refresh Statistics",
                   command=self._load_admin_statistics).pack(side=tk.LEFT, padx=5, pady=5)

        # Load initial data
        self._refresh_admin_cycle_lists()
        self._load_unapproved_resources()
        self._load_admin_statistics()

    def _refresh_admin_cycle_lists(self):
        """Refresh cycle and submission lists in admin panel."""
        # Refresh activation cycle combo
        self.admin_cycle_map = {}

        try:
            cycles = PeerReviewManager.get_cycles()
        except Exception:
            cycles = []

        cycle_display_values = []
        for c in cycles:
            label = f"{c.get('name', '')} (#{c.get('cycle_id')}) - {c.get('status', '')}"
            cycle_display_values.append(label)
            self.admin_cycle_map[label] = c.get('cycle_id')

        self.admin_activate_cycle_combo['values'] = cycle_display_values
        if cycle_display_values:
            self.admin_activate_cycle_combo.set(cycle_display_values[0])
        else:
            self.admin_activate_cycle_combo.set('')

        # Refresh submission combo
        self.admin_submission_map = {}

        try:
            submissions = PeerReviewManager.get_submissions()
        except Exception:
            submissions = []

        sub_display_values = []
        for s in submissions:
            label = (f"#{s.get('submission_id')} - {s.get('title', '')[:30]} "
                     f"({s.get('status', '')})")
            sub_display_values.append(label)
            self.admin_submission_map[label] = s.get('submission_id')

        self.admin_submission_combo['values'] = sub_display_values
        if sub_display_values:
            self.admin_submission_combo.set(sub_display_values[0])
        else:
            self.admin_submission_combo.set('')

    def _admin_create_cycle(self):
        """Create a new review cycle from the admin form."""
        try:
            name = validate_entry(self.admin_cycle_name_entry, "Name")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        description = self.admin_cycle_desc_text.get("1.0", "end-1c").strip()
        if not description:
            messagebox.showerror("Validation Error", "Description is required.")
            return

        try:
            cycle_type = validate_combobox(self.admin_cycle_type_combo, "Type")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            department = validate_entry(self.admin_cycle_dept_entry, "Department")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            start_date = validate_date_entry(self.admin_cycle_start_entry, "Start Date")
            end_date = validate_date_entry(self.admin_cycle_end_entry, "End Date")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        user_id = self._get_user_id()

        try:
            cycle_id = PeerReviewManager.create_cycle(
                name=name,
                description=description,
                cycle_type=cycle_type,
                department=department,
                start_date=start_date,
                end_date=end_date,
                created_by=user_id
            )
            messagebox.showinfo("Success", f"Review cycle created. ID: {cycle_id}")
            # Clear form
            self.admin_cycle_name_entry.delete(0, tk.END)
            self.admin_cycle_desc_text.delete("1.0", tk.END)
            self.admin_cycle_type_combo.set('annual')
            self.admin_cycle_dept_entry.delete(0, tk.END)
            self.admin_cycle_start_entry.delete(0, tk.END)
            self.admin_cycle_start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
            self.admin_cycle_end_entry.delete(0, tk.END)
            # Refresh lists
            self._refresh_admin_cycle_lists()
            self._load_review_cycles()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _admin_activate_cycle(self):
        """Activate the selected cycle."""
        selected = self.admin_activate_cycle_combo.get()
        cycle_id = self.admin_cycle_map.get(selected)

        if not cycle_id:
            messagebox.showinfo("Info", "Please select a cycle to activate.")
            return

        if not messagebox.askyesno("Confirm",
                                    "Activate the selected review cycle?"):
            return

        try:
            PeerReviewManager.activate_cycle(cycle_id)
            messagebox.showinfo("Success", "Cycle activated.")
            self._refresh_admin_cycle_lists()
            self._load_review_cycles()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _admin_assign_reviewer(self):
        """Assign a reviewer to the selected submission."""
        selected_sub = self.admin_submission_combo.get()
        submission_id = self.admin_submission_map.get(selected_sub)

        if not submission_id:
            messagebox.showinfo("Info", "Please select a submission.")
            return

        try:
            reviewer_id = validate_entry(self.admin_reviewer_id_entry, "Reviewer ID")
            due_date = validate_date_entry(self.admin_due_date_entry, "Due Date")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            assignment_id = PeerReviewManager.assign_reviewer(
                submission_id=submission_id,
                reviewer_id=reviewer_id,
                assigned_by=self._get_user_id(),
                due_date=due_date
            )
            messagebox.showinfo("Success",
                                f"Reviewer assigned. Assignment ID: {assignment_id}")
            self.admin_reviewer_id_entry.delete(0, tk.END)
            self.admin_due_date_entry.delete(0, tk.END)
            self._refresh_admin_cycle_lists()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_unapproved_resources(self):
        """Load unapproved resources into the admin approval treeview."""
        for item in self.admin_approval_tree.get_children():
            self.admin_approval_tree.delete(item)

        try:
            resources = PeerReviewManager.get_resources(is_approved=0)
        except Exception:
            resources = []

        for r in resources:
            display_type = r.get('resource_type', '').replace('_', ' ').title()

            self.admin_approval_tree.insert('', tk.END, values=(
                r.get('resource_id', ''),
                r.get('title', '')[:35],
                display_type,
                r.get('shared_by', ''),
                r.get('created_at', '')
            ))

    def _admin_approve_resource(self):
        """Approve the selected resource."""
        selection = self.admin_approval_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a resource to approve.")
            return

        item = self.admin_approval_tree.item(selection[0])
        resource_id = item['values'][0]

        if not messagebox.askyesno("Confirm",
                                    f"Approve resource #{resource_id}?"):
            return

        try:
            PeerReviewManager.approve_resource(resource_id)
            messagebox.showinfo("Success", "Resource approved.")
            self._load_unapproved_resources()
            self._load_resources()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_admin_statistics(self):
        """Load and display statistics in the admin panel."""
        self.admin_stats_text.config(state='normal')
        self.admin_stats_text.delete("1.0", tk.END)

        lines = []
        lines.append("=== Peer Review Statistics ===\n")

        # Cycle statistics
        try:
            cycles = PeerReviewManager.get_cycles()
        except Exception:
            cycles = []

        lines.append(f"Total Cycles: {len(cycles)}")
        active_cycles = [c for c in cycles if c.get('status') == 'active']
        lines.append(f"Active Cycles: {len(active_cycles)}\n")

        for c in active_cycles:
            cycle_id = c.get('cycle_id')
            cycle_name = c.get('name', '')
            try:
                stats = PeerReviewManager.get_cycle_statistics(cycle_id)
            except Exception:
                stats = {}

            avg_rating = stats.get('avg_overall_rating')
            avg_display = f"{avg_rating:.2f}" if avg_rating is not None else 'N/A'

            lines.append(f"--- {cycle_name} (#{cycle_id}) ---")
            lines.append(f"  Submissions: {stats.get('total_submissions', 0)}")
            lines.append(f"  Completed Reviews: {stats.get('completed_reviews', 0)}")
            lines.append(f"  Pending Reviews: {stats.get('pending_reviews', 0)}")
            lines.append(f"  Avg Rating: {avg_display}")
            lines.append("")

        # Reviewer workload
        lines.append("=== Reviewer Workload ===\n")

        try:
            workloads = PeerReviewManager.get_reviewer_workload()
        except Exception:
            workloads = []

        if workloads:
            for w in workloads:
                lines.append(
                    f"  {w.get('reviewer_id', 'Unknown')}: "
                    f"Assigned={w.get('assigned', 0)}, "
                    f"Completed={w.get('completed', 0)}, "
                    f"Pending={w.get('pending', 0)}"
                )
        else:
            lines.append("  No reviewer data available.")

        self.admin_stats_text.insert("1.0", "\n".join(lines))
        self.admin_stats_text.config(state='disabled')
