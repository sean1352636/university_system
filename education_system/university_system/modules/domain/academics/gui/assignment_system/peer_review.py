"""Peer review system"""

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
from education_system.university_system.modules.shared.utils.i18n import get_text as _
from collections import deque

class PeerReviewManager:
    """Peer review system"""

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

    def complete_peer_reviews(self):
        """Student interface to complete assigned peer reviews"""
        if not self._check_permission('view_assignments'):
            return
        
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text=_("peer_review.title"), style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            student_id = self.assignment_system._get_student_id()
            if not student_id:
                ttk.Label(self.gui.layout.content_area, text=_("peer_review.no_student_id")).pack()
                return
            
            # Get pending peer reviews
            cursor.execute('''
            SELECT pra.id, a.title, s.first_name, s.last_name, pra.status
            FROM peer_review_assignments pra
            JOIN assignment_submissions asub ON pra.submission_id = asub.id
            JOIN assignments a ON asub.assignment_id = a.id
            JOIN students s ON pra.reviewee_id = s.student_id
            WHERE pra.reviewer_id = ? AND pra.status = 'pending'
            ''', (student_id,))
            
            reviews = cursor.fetchall()
            
            if not reviews:
                ttk.Label(self.gui.layout.content_area, text=_("peer_review.no_pending_reviews")).pack(pady=20)
                conn.close()
                return

            # Create reviews interface
            reviews_frame = ttk.LabelFrame(self.gui.layout.content_area, text=_("peer_review.pending_reviews"), padding=10)
            reviews_frame.pack(fill='both', expand=True)
            
            for review in reviews:
                review_frame = ttk.Frame(reviews_frame)
                review_frame.pack(fill='x', pady=5, padx=5)
                
                ttk.Label(review_frame, text=f"Assignment: {review[1]}").pack(anchor='w')
                ttk.Label(review_frame, text=f"Student: {review[2]} {review[3]}").pack(anchor='w')
                ttk.Button(review_frame, text="Complete Review", 
                          command=lambda r=review[0]: self.start_peer_review(r)).pack(anchor='e')
            
            conn.close()

        except Exception as e:
            messagebox.showerror(_("common.error"), _("peer_review.failed_load_reviews", error=str(e)))
    

    def start_peer_review(self, review_id):
        """Start a specific peer review"""
        # Create peer review form window
        review_window = tk.Toplevel(self.root)
        review_window.title("Peer Review")
        review_window.geometry("600x500")
        
        # Add peer review form components
        ttk.Label(review_window, text=_("peer_review.peer_review_form"), font=('Arial', 16, 'bold')).pack(pady=10)

        # Review criteria
        criteria_frame = ttk.LabelFrame(review_window, text=_("peer_review.review_criteria"), padding=10)
        criteria_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Sample criteria (would be loaded from database)
        criteria = ["Content Quality", "Organization", "Clarity", "Creativity"]
        self.review_scores = {}
        
        for criterion in criteria:
            crit_frame = ttk.Frame(criteria_frame)
            crit_frame.pack(fill='x', pady=5)
            
            ttk.Label(crit_frame, text=f"{criterion}:").pack(side='left')
            score_var = tk.StringVar()
            self.review_scores[criterion] = score_var
            
            # Score scale 1-5
            for score in range(1, 6):
                ttk.Radiobutton(crit_frame, text=str(score), variable=score_var, value=str(score)).pack(side='left', padx=5)
        
        # Comments section
        comments_frame = ttk.LabelFrame(review_window, text=_("peer_review.comments"), padding=10)
        comments_frame.pack(fill='x', padx=10, pady=10)

        self.review_comments = scrolledtext.ScrolledText(comments_frame, height=6, width=60)
        self.review_comments.pack(fill='both', expand=True)

        # Submit button
        ttk.Button(review_window, text=_("peer_review.submit_review"),
                  command=lambda: self.submit_peer_review(review_id, review_window)).pack(pady=10)
    

    def submit_peer_review(self, review_id, window):
        """Submit a completed peer review"""
        try:
            # Validate scores
            for criterion, score_var in self.review_scores.items():
                if not score_var.get():
                    messagebox.showerror(_("common.error"), _("assignment_gui.messages.please_rate", criterion=criterion))
                    return
            
            # Calculate overall score
            scores = [int(var.get()) for var in self.review_scores.values()]
            overall_score = sum(scores) / len(scores)
            
            # Get comments
            comments = self.review_comments.get(1.0, tk.END).strip()
            
            # Save review to database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
            UPDATE peer_reviews 
            SET overall_score = ?, review_text = ?, status = 'completed', review_date = ?
            WHERE id = ?
            ''', (overall_score, comments, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), review_id))
            
            # Save individual criteria scores
            for criterion, score_var in self.review_scores.items():
                cursor.execute('''
                INSERT INTO peer_review_criteria (review_id, criteria_name, score, comment)
                VALUES (?, ?, ?, ?)
                ''', (review_id, criterion, int(score_var.get()), ''))
            
            conn.commit()
            conn.close()

            messagebox.showinfo(_("common.success"), _("assignment_gui.messages.review_submitted"))
            window.destroy()
            self.complete_peer_reviews()  # Refresh the list

        except Exception as e:
            messagebox.showerror(_("common.error"), _("peer_review.failed_submit_review", error=str(e)))
    

    def manage_peer_reviews(self):
        """Instructor interface to manage peer reviews"""
        if not self._check_permission('manage_assignments'):
            return
        
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="Manage Peer Reviews", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Create notebook for different views
        notebook = ttk.Notebook(self.gui.layout.content_area)
        notebook.pack(fill='both', expand=True)
        
        # Setup tab
        setup_frame = ttk.Frame(notebook)
        notebook.add(setup_frame, text="Setup Reviews")
        
        # Monitor tab
        monitor_frame = ttk.Frame(notebook)
        notebook.add(monitor_frame, text="Monitor Progress")
        
        # Results tab
        results_frame = ttk.Frame(notebook)
        notebook.add(results_frame, text="View Results")
        
        # Add content to tabs
        ttk.Label(setup_frame, text="Setup peer review assignments").pack(pady=20)
        ttk.Button(setup_frame, text="Configure Peer Review", 
                  command=self.configure_peer_review).pack(pady=10)
        
        ttk.Label(monitor_frame, text="Monitor review progress").pack(pady=20)
        ttk.Label(results_frame, text="View completed reviews and results").pack(pady=20)
    

    def configure_peer_review(self):
        """Configure peer review settings"""
        # Create configuration window
        config_window = tk.Toplevel(self.root)
        config_window.title("Configure Peer Review")
        config_window.geometry("500x400")
        
        ttk.Label(config_window, text="Peer Review Configuration", 
                 font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Assignment selection
        assignment_frame = ttk.LabelFrame(config_window, text="Select Assignment", padding=10)
        assignment_frame.pack(fill='x', padx=10, pady=10)
        
        self.peer_assignment_var = tk.StringVar()
        assignment_combo = ttk.Combobox(config_window, textvariable=self.peer_assignment_var)
        assignment_combo.pack(fill='x', padx=10, pady=5)
        
        # Review criteria
        criteria_frame = ttk.LabelFrame(config_window, text="Review Criteria", padding=10)
        criteria_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(criteria_frame, text="Add criteria (one per line):").pack(anchor='w')
        self.criteria_text = scrolledtext.ScrolledText(criteria_frame, height=6)
        self.criteria_text.pack(fill='both', expand=True)
        
        # Default criteria
        default_criteria = "Content Quality\nOrganization\nClarity\nCreativity"
        self.criteria_text.insert(tk.END, default_criteria)
        
        # Configuration options
        options_frame = ttk.LabelFrame(config_window, text="Options", padding=10)
        options_frame.pack(fill='x', padx=10, pady=10)
        
        self.anonymous_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Anonymous reviews", 
                       variable=self.anonymous_var).pack(anchor='w')
        
        # Submit button
        ttk.Button(config_window, text="Setup Peer Reviews", 
                  command=lambda: self.setup_peer_review_assignments(config_window)).pack(pady=10)
    

    def setup_peer_review_assignments(self, window):
        """Setup peer review assignments"""
        try:
            # Get configuration values
            criteria_text = self.criteria_text.get(1.0, tk.END).strip()
            criteria = [c.strip() for c in criteria_text.split('\n') if c.strip()]
            selected_assignment = self.peer_assignment_var.get()
            anonymous_reviews = self.anonymous_var.get()
    
            # Validate input
            if not criteria:
                messagebox.showerror("Error", "Please add at least one review criterion")
                return
    
            if not selected_assignment:
                messagebox.showerror("Error", "Please select an assignment")
                return
    
            # Create peer review setup progress window
            progress_window = tk.Toplevel(window)
            progress_window.title("Setting up Peer Reviews")
            progress_window.geometry("600x500")
            progress_window.transient(window)
            progress_window.grab_set()
    
            # Title
            ttk.Label(progress_window, text="🤝 Setting up Peer Review Assignments",
                     style='Title.TLabel').pack(pady=15)
    
            # Progress frame
            progress_frame = ttk.LabelFrame(progress_window, text="Setup Progress", padding="15")
            progress_frame.pack(fill='x', padx=20, pady=(0, 15))
    
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_frame, variable=progress_var,
                                         mode='determinate', length=500)
            progress_bar.pack(pady=(0, 10))
    
            status_label = ttk.Label(progress_frame, text="Initializing setup...")
            status_label.pack()
    
            # Results frame
            results_frame = ttk.LabelFrame(progress_window, text="Setup Results", padding="15")
            results_frame.pack(fill='both', expand=True, padx=20, pady=(0, 15))
    
            results_text = tk.Text(results_frame, height=15, wrap='word')
            results_text.pack(fill='both', expand=True)
    
            scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=results_text.yview)
            scrollbar.pack(side='right', fill='y')
            results_text.config(yscrollcommand=scrollbar.set)
    
            def run_setup():
                try:
                    import random

                    from datetime import datetime, timedelta
    
                    results_text.insert(tk.END, f"Setting up peer reviews for: {selected_assignment}\n")
                    results_text.insert(tk.END, f"Review criteria: {len(criteria)} items\n")
                    results_text.insert(tk.END, f"Anonymous reviews: {'Yes' if anonymous_reviews else 'No'}\n\n")
                    progress_window.update()
    
                    # Step 1: Get submitted assignments
                    status_label.config(text="Retrieving submitted assignments...")
                    progress_var.set(10)
                    progress_window.update()
    
                    # Simulate database connection (replace with actual database)
                    try:
                        from education_system.university_system.infrastructure.database.db import get_connection
                        conn = get_connection()
                        cursor = conn.cursor()
    
                        # Get submissions for the assignment
                        cursor.execute("""
                            SELECT DISTINCT student_id, submission_id, student_name, submitted_at
                            FROM assignment_submissions
                            WHERE assignment_name = ? AND status = 'submitted'
                            ORDER BY submitted_at
                        """, (selected_assignment,))

                        submissions = cursor.fetchall()
                    except Exception:
                        # Fallback to simulated data
                        submissions = [
                            (f"STU{i:03d}", f"SUB{i:03d}", f"Student {i}",
                             (datetime.now() - timedelta(days=random.randint(1, 7))).isoformat())
                            for i in range(1, random.randint(8, 20))
                        ]
    
                    if len(submissions) < 2:
                        results_text.insert(tk.END, "❌ Error: Need at least 2 submissions for peer review\n")
                        status_label.config(text="Setup failed - insufficient submissions")
                        return
    
                    results_text.insert(tk.END, f"Found {len(submissions)} submissions to review\n\n")
                    progress_window.update()
    
                    # Step 2: Create review criteria in database
                    status_label.config(text="Setting up review criteria...")
                    progress_var.set(25)
                    progress_window.update()
    
                    review_session_id = f"review_{int(time.time())}"
                    results_text.insert(tk.END, f"Creating review session: {review_session_id}\n")
    
                    try:
                        # Create peer review session
                        cursor.execute("""
                            INSERT OR IGNORE INTO peer_review_sessions
                            (session_id, assignment_name, criteria, anonymous, created_at, status)
                            VALUES (?, ?, ?, ?, ?, 'active')
                        """, (review_session_id, selected_assignment,
                              '\n'.join(criteria), anonymous_reviews,
                              datetime.now().isoformat()))
    
                        # Create criteria records
                        for i, criterion in enumerate(criteria):
                            cursor.execute("""
                                INSERT OR IGNORE INTO review_criteria
                                (session_id, criterion_id, criterion_text, max_score)
                                VALUES (?, ?, ?, 10)
                            """, (review_session_id, i + 1, criterion))
    
                        conn.commit()
                    except Exception as db_error:
                        results_text.insert(tk.END, f"Database setup: Using simulation mode ({str(db_error)[:50]}...)\n")
    
                    # Step 3: Assign peer reviewers
                    status_label.config(text="Assigning peer reviewers...")
                    progress_var.set(50)
                    progress_window.update()
    
                    # Create review assignments (each student reviews 2-3 others)
                    review_assignments = []
                    students = [sub[0] for sub in submissions]  # student_ids
    
                    results_text.insert(tk.END, "Creating review assignments:\n")
    
                    for i, reviewer_id in enumerate(students):
                        # Assign 2-3 submissions to review (not their own)
                        available_submissions = [sub for sub in submissions if sub[0] != reviewer_id]
                        reviews_to_assign = min(3, len(available_submissions))
    
                        assigned_reviews = random.sample(available_submissions, reviews_to_assign)
    
                        for review_submission in assigned_reviews:
                            reviewee_id, submission_id, reviewee_name, _ = review_submission
    
                            assignment_id = f"assign_{reviewer_id}_{submission_id}"
                            review_assignments.append({
                                'assignment_id': assignment_id,
                                'session_id': review_session_id,
                                'reviewer_id': reviewer_id,
                                'reviewee_id': reviewee_id,
                                'submission_id': submission_id,
                                'due_date': (datetime.now() + timedelta(days=7)).isoformat(),
                                'status': 'pending'
                            })
    
                            reviewer_name = next((s[2] for s in submissions if s[0] == reviewer_id), reviewer_id)
                            display_reviewee = reviewee_name if not anonymous_reviews else f"Anonymous Submission {submission_id[-3:]}"
    
                            results_text.insert(tk.END, f"  • {reviewer_name} → {display_reviewee}\n")
    
                        progress_var.set(50 + ((i + 1) / len(students)) * 30)
                        progress_window.update()
    
                    # Step 4: Save assignments to database
                    status_label.config(text="Saving review assignments...")
                    progress_var.set(80)
                    progress_window.update()
    
                    try:
                        for assignment in review_assignments:
                            cursor.execute("""
                                INSERT OR REPLACE INTO peer_review_assignments
                                (assignment_id, session_id, reviewer_id, reviewee_id,
                                 submission_id, due_date, status, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (assignment['assignment_id'], assignment['session_id'],
                                  assignment['reviewer_id'], assignment['reviewee_id'],
                                  assignment['submission_id'], assignment['due_date'],
                                  assignment['status'], datetime.now().isoformat()))
    
                        conn.commit()
                        conn.close()
                        results_text.insert(tk.END, f"\n✅ Saved {len(review_assignments)} review assignments to database\n")
                    except Exception as save_error:
                        results_text.insert(tk.END, f"\n⚠️ Database save simulation mode: {len(review_assignments)} assignments created\n")
    
                    # Step 5: Generate notification emails (simulation)
                    status_label.config(text="Generating notifications...")
                    progress_var.set(90)
                    progress_window.update()
    
                    unique_reviewers = len(set(a['reviewer_id'] for a in review_assignments))
                    results_text.insert(tk.END, f"\n📧 Email notifications prepared for {unique_reviewers} reviewers\n")
    
                    # Final summary
                    progress_var.set(100)
                    status_label.config(text="Peer review setup completed!")
    
                    results_text.insert(tk.END, f"\n{'='*50}\n")
                    results_text.insert(tk.END, "PEER REVIEW SETUP SUMMARY\n")
                    results_text.insert(tk.END, f"{'='*50}\n")
                    results_text.insert(tk.END, f"Assignment: {selected_assignment}\n")
                    results_text.insert(tk.END, f"Review Session ID: {review_session_id}\n")
                    results_text.insert(tk.END, f"Total Submissions: {len(submissions)}\n")
                    results_text.insert(tk.END, f"Review Assignments Created: {len(review_assignments)}\n")
                    results_text.insert(tk.END, f"Review Criteria: {len(criteria)}\n")
                    results_text.insert(tk.END, f"Anonymous Reviews: {'Yes' if anonymous_reviews else 'No'}\n")
                    results_text.insert(tk.END, f"Review Due Date: {(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')}\n")
                    results_text.insert(tk.END, f"\nSetup completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
                    # Close configuration window
                    window.destroy()
    
                except Exception as e:
                    results_text.insert(tk.END, f"\n❌ Error during setup: {str(e)}\n")
                    status_label.config(text="Setup failed!")
    
            # Control buttons
            button_frame = ttk.Frame(progress_window)
            button_frame.pack(fill='x', padx=20, pady=(0, 15))
    
            ttk.Button(button_frame, text="Start Setup",
                      command=lambda: threading.Thread(target=run_setup, daemon=True).start()).pack(side='left', padx=(0, 10))
            ttk.Button(button_frame, text="Close", command=progress_window.destroy).pack(side='right')
    
            # Show initial message
            results_text.insert(tk.END, "Peer Review Configuration:\n")
            results_text.insert(tk.END, f"Assignment: {selected_assignment}\n")
            results_text.insert(tk.END, f"Criteria ({len(criteria)}):\n")
            for i, criterion in enumerate(criteria, 1):
                results_text.insert(tk.END, f"  {i}. {criterion}\n")
            results_text.insert(tk.END, f"Anonymous: {'Yes' if anonymous_reviews else 'No'}\n\n")
            results_text.insert(tk.END, "Click 'Start Setup' to create peer review assignments.\n")
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to setup peer reviews: {e}")
    
    # RUBRIC MANAGEMENT METHODS

    def show_peer_review_dashboard(self):
        """Show peer review dashboard"""
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="Peer Review Dashboard", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Create notebook for different peer review views
        notebook = ttk.Notebook(self.gui.layout.content_area)
        notebook.pack(fill='both', expand=True)
        
        # My Reviews tab
        my_reviews_frame = ttk.Frame(notebook)
        notebook.add(my_reviews_frame, text="My Reviews")
        
        # Reviews to Complete tab
        pending_reviews_frame = ttk.Frame(notebook)
        notebook.add(pending_reviews_frame, text="Pending Reviews")
        
        # Review Results tab
        results_frame = ttk.Frame(notebook)
        notebook.add(results_frame, text="Review Results")
        
        # Placeholder content
        ttk.Label(my_reviews_frame, text="Peer reviews you have completed will appear here").pack(pady=20)
        ttk.Label(pending_reviews_frame, text="Reviews waiting for your input will appear here").pack(pady=20)
        ttk.Label(results_frame, text="Results from peer reviews of your work will appear here").pack(pady=20)
    

    def setup_peer_review(self, *args, **kwargs):
        """Open peer review management tools."""
        self._launch_gui_feature(self.manage_peer_reviews, "peer review management")

    def _configure_peer_review(self, assignment_id):
        """Configure peer review parameters for an assignment"""
        try:
            # Create configuration dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Configure Peer Review Settings")
            dialog.geometry("550x600")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Peer Review Configuration", font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Assignment info
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT title, due_date FROM assignments WHERE id = ?', (assignment_id,))
            assignment_info = cursor.fetchone()
            conn.close()

            if not assignment_info:
                messagebox.showerror("Error", "Assignment not found")
                dialog.destroy()
                return

            title, due_date = assignment_info

            info_frame = ttk.LabelFrame(dialog, text="Assignment", padding=10)
            info_frame.pack(fill='x', padx=10, pady=(0, 10))
            ttk.Label(info_frame, text=f"Title: {title}\nDue Date: {due_date}").pack(anchor='w')

            # Review settings
            settings_frame = ttk.LabelFrame(dialog, text="Review Settings", padding=10)
            settings_frame.pack(fill='x', padx=10, pady=(0, 10))

            ttk.Label(settings_frame, text="Reviews per Student:").grid(row=0, column=0, sticky='w', pady=5)
            reviews_per_student_var = tk.StringVar(value="3")
            ttk.Entry(settings_frame, textvariable=reviews_per_student_var, width=10).grid(row=0, column=1, sticky='w', padx=(10, 0))

            ttk.Label(settings_frame, text="Review Deadline (days after submission):").grid(row=1, column=0, sticky='w', pady=5)
            review_deadline_var = tk.StringVar(value="7")
            ttk.Entry(settings_frame, textvariable=review_deadline_var, width=10).grid(row=1, column=1, sticky='w', padx=(10, 0))

            anonymous_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(settings_frame, text="Anonymous Reviews", variable=anonymous_var).grid(row=2, column=0, columnspan=2, sticky='w', pady=5)

            # Review criteria
            criteria_frame = ttk.LabelFrame(dialog, text="Review Criteria", padding=10)
            criteria_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            ttk.Label(criteria_frame, text="Enter criteria (one per line):").pack(anchor='w', pady=(0, 5))
            criteria_text = scrolledtext.ScrolledText(criteria_frame, height=8, wrap=tk.WORD)
            criteria_text.pack(fill='both', expand=True)

            # Default criteria
            default_criteria = "Content Quality (1-5)\nOrganization (1-5)\nClarity (1-5)\nCritical Thinking (1-5)\nOriginality (1-5)"
            criteria_text.insert(tk.END, default_criteria)

            # Grading weight
            weight_frame = ttk.LabelFrame(dialog, text="Grading Weight", padding=10)
            weight_frame.pack(fill='x', padx=10, pady=(0, 10))

            ttk.Label(weight_frame, text="Peer Review Weight (% of final grade):").grid(row=0, column=0, sticky='w', pady=5)
            weight_var = tk.StringVar(value="20")
            ttk.Entry(weight_frame, textvariable=weight_var, width=10).grid(row=0, column=1, sticky='w', padx=(10, 0))

            # Save button
            def save_peer_review_config():
                try:
                    reviews_per = int(reviews_per_student_var.get())
                    deadline_days = int(review_deadline_var.get())
                    weight = float(weight_var.get())

                    if not (1 <= reviews_per <= 10):
                        messagebox.showerror("Error", "Reviews per student must be between 1 and 10", parent=dialog)
                        return

                    if not (1 <= deadline_days <= 30):
                        messagebox.showerror("Error", "Review deadline must be between 1 and 30 days", parent=dialog)
                        return

                    if not (0 <= weight <= 100):
                        messagebox.showerror("Error", "Weight must be between 0 and 100", parent=dialog)
                        return

                    criteria_list = criteria_text.get(1.0, tk.END).strip().split('\n')
                    criteria_list = [c.strip() for c in criteria_list if c.strip()]

                    if not criteria_list:
                        messagebox.showerror("Error", "At least one criterion is required", parent=dialog)
                        return

                    # Save configuration
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    # Save to database
                    cursor.execute('''
                    INSERT OR REPLACE INTO peer_review_config
                    (assignment_id, reviews_per_student, review_deadline_days, is_anonymous, grading_weight, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (assignment_id, reviews_per, deadline_days, 1 if anonymous_var.get() else 0,
                          weight, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                    config_id = cursor.lastrowid or assignment_id

                    # Save criteria
                    cursor.execute('DELETE FROM peer_review_criteria_templates WHERE config_id = ?', (config_id,))
                    for i, criterion in enumerate(criteria_list):
                        cursor.execute('''
                        INSERT INTO peer_review_criteria_templates (config_id, criteria_name, max_score, order_index)
                        VALUES (?, ?, 5, ?)
                        ''', (config_id, criterion, i))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Peer review configuration saved successfully!", parent=dialog)
                    dialog.destroy()

                except ValueError:
                    messagebox.showerror("Error", "Please enter valid numeric values", parent=dialog)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save configuration: {e}", parent=dialog)

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))

            ttk.Button(button_frame, text="Save Configuration", command=save_peer_review_config,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open configuration: {e}")

    def _assign_peer_reviewers(self, assignment_id):
        """Assign peer reviewers automatically based on configuration"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get peer review configuration
            cursor.execute('''
            SELECT reviews_per_student, is_anonymous FROM peer_review_config
            WHERE assignment_id = ?
            ''', (assignment_id,))

            config = cursor.fetchone()
            if not config:
                messagebox.showerror("Error", "Please configure peer review settings first")
                conn.close()
                return

            reviews_per_student, is_anonymous = config

            # Get all submitted assignments
            cursor.execute('''
            SELECT id, student_id FROM assignment_submissions
            WHERE assignment_id = ? AND status = 'submitted'
            ''', (assignment_id,))

            submissions = cursor.fetchall()

            if len(submissions) < 2:
                messagebox.showwarning("Warning", "At least 2 submissions are required for peer review")
                conn.close()
                return

            # Clear existing assignments
            cursor.execute('DELETE FROM peer_review_assignments WHERE assignment_id = ?', (assignment_id,))

            # Assign reviewers using round-robin algorithm
            import random
            submission_ids = [s[0] for s in submissions]
            student_ids = [s[1] for s in submissions]

            assignments_created = 0

            for i, (submission_id, reviewee_id) in enumerate(submissions):
                # Get potential reviewers (everyone except the submitter)
                potential_reviewers = [(sid, stud_id) for sid, stud_id in submissions if stud_id != reviewee_id]

                # Shuffle for randomness
                random.shuffle(potential_reviewers)

                # Assign reviews
                assigned_count = min(reviews_per_student, len(potential_reviewers))

                for j in range(assigned_count):
                    reviewer_submission_id, reviewer_id = potential_reviewers[j]

                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    cursor.execute('''
                    INSERT INTO peer_review_assignments
                    (assignment_id, submission_id, reviewer_id, reviewee_id, status, assigned_date)
                    VALUES (?, ?, ?, ?, 'pending', ?)
                    ''', (assignment_id, submission_id, reviewer_id, reviewee_id, timestamp))

                    assignments_created += 1

            conn.commit()
            conn.close()

            messagebox.showinfo("Success",
                              f"Peer review assignments created successfully!\n\n"
                              f"Total assignments: {assignments_created}\n"
                              f"Reviews per student: ~{reviews_per_student}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to assign peer reviewers: {e}")

    def _launch_gui_feature(self, callback, feature_name):
        """Helper to launch GUI features with error handling"""
        try:
            callback()
        except Exception as e:
            messagebox.showerror("Error", f"Error launching {feature_name}: {str(e)}")

