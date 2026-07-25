import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
import shutil
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.email.email_service.core import send_email
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.domain.pastoral.student_life.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class AcademicConferencesDialog:
    """Dialog for organizing academic conferences"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Academic Conferences")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🎓 Academic Conferences & Research",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Upcoming conferences
        upcoming_frame = ttk.Frame(notebook)
        notebook.add(upcoming_frame, text="Upcoming Conferences")

        columns = ('Conference', 'Date', 'Papers', 'Speakers', 'Attendees')
        tree = ttk.Treeview(upcoming_frame, columns=columns, show='tree headings')

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True, padx=10, pady=10)

        tree.insert('', 'end', values=("AI & Machine Learning Symposium", "May 15, 2025", "12", "5", "150"))
        tree.insert('', 'end', values=("Sustainability Conference", "June 2, 2025", "8", "3", "100"))

        self._upcoming_tree = tree

        ttk.Button(upcoming_frame, text="Register",
                  command=self._register_for_conference).pack(anchor='w', padx=10, pady=(0, 10))

        # Paper submissions
        papers_frame = ttk.Frame(notebook)
        notebook.add(papers_frame, text="Submit Paper")

        form = ttk.Frame(papers_frame)
        form.pack(padx=15, pady=15, fill='both', expand=True)

        ttk.Label(form, text="Paper Title:").pack(anchor='w', pady=(0, 5))
        self._paper_title_entry = ttk.Entry(form, width=60)
        self._paper_title_entry.pack(fill='x', pady=(0, 15))

        ttk.Label(form, text="Abstract:").pack(anchor='w', pady=(0, 5))
        self._abstract_text = scrolledtext.ScrolledText(form, height=10, wrap=tk.WORD)
        self._abstract_text.pack(fill='both', expand=True, pady=(0, 15))

        # File upload section
        self._selected_file_path = None
        upload_frame = ttk.Frame(form)
        upload_frame.pack(fill='x', pady=(0, 15))
        ttk.Label(upload_frame, text="Or upload file:").pack(side='left', padx=(0, 10))
        self._file_label = ttk.Label(upload_frame, text="No file selected")
        self._file_label.pack(side='left', padx=(0, 10))
        ttk.Button(upload_frame, text="Browse",
                  command=self._browse_paper_file).pack(side='left')

        ttk.Button(form, text="Submit Paper",
                  command=self._submit_paper).pack(anchor='w')

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def _get_user_email(self):
        """Look up the current user's email address."""
        user = self.auth.current_user
        if user and user.get('email'):
            return user['email']
        try:
            with get_connection() as conn:
                # Try users table first
                cursor = conn.execute(
                    "SELECT email FROM users WHERE id = ?",
                    (user.get('id'),)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return row[0]
                # Try students table
                cursor = conn.execute(
                    "SELECT email_address FROM students WHERE student_id = ?",
                    (user.get('student_id', user.get('id')),)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return row[0]
        except Exception:
            pass
        return None

    def _register_for_conference(self):
        """Register for the selected conference."""
        selected = self._upcoming_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a conference to register for.")
            return
        values = self._upcoming_tree.item(selected[0], 'values')
        conf_name = values[0] if values else "Unknown"
        if not messagebox.askyesno("Confirm Registration",
                                   f"Register for '{conf_name}'?"):
            return
        email = self._get_user_email()
        if email:
            try:
                send_email(
                    email,
                    f"Conference Registration Confirmation: {conf_name}",
                    f"You have been successfully registered for '{conf_name}'.\n\n"
                    f"Date: {values[1] if len(values) > 1 else 'TBA'}\n\n"
                    "Thank you for registering!"
                )
            except Exception:
                pass
        messagebox.showinfo("Success",
                           f"You have been registered for '{conf_name}'.\n"
                           "A confirmation email has been sent.")

    def _browse_paper_file(self):
        """Browse for a paper file to upload."""
        from tkinter import filedialog
        filename = filedialog.askopenfilename(
            title="Select Paper File",
            filetypes=[("PDF files", "*.pdf"), ("Word documents", "*.docx"), ("All files", "*.*")]
        )
        if filename:
            self._selected_file_path = filename
            self._file_label.config(text=os.path.basename(filename))

    def _submit_paper(self):
        """Submit the paper with optional file upload."""
        title = self._paper_title_entry.get().strip()
        if not title:
            messagebox.showwarning("Validation Error", "Please enter a paper title.")
            return

        # Handle file upload if selected
        if self._selected_file_path:
            upload_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', '..', '..', '..', '..', 'data', 'uploads'
            )
            upload_dir = os.path.normpath(upload_dir)
            os.makedirs(upload_dir, exist_ok=True)
            dest = os.path.join(upload_dir, os.path.basename(self._selected_file_path))
            try:
                shutil.copy2(self._selected_file_path, dest)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to upload file: {e}")
                return

        # Send confirmation email
        email = self._get_user_email()
        if email:
            try:
                send_email(
                    email,
                    f"Paper Submission Confirmation: {title}",
                    f"Your paper '{title}' has been successfully submitted.\n\n"
                    "You will receive further updates on the review process.\n\n"
                    "Thank you for your submission!"
                )
            except Exception:
                pass

        messagebox.showinfo("Success",
                           f"Paper '{title}' submitted successfully.\n"
                           "A confirmation email has been sent.")


# ============================================================================
# INTER-CLUB COMPETITIONS DIALOGS
# ============================================================================


class AcademicConferencesOrganizerDialog:
    """Organize and manage academic conferences"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Academic Conference Organization")
        self.dialog.geometry("1200x800")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📚 Academic Conference Organization",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create notebook for conference management
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Conferences tab
        conferences_frame = ttk.Frame(notebook)
        notebook.add(conferences_frame, text="Conferences")
        self.create_conferences_tab(conferences_frame)

        # Paper Submissions tab
        submissions_frame = ttk.Frame(notebook)
        notebook.add(submissions_frame, text="Paper Submissions")
        self.create_submissions_tab(submissions_frame)

        # Speakers tab
        speakers_frame = ttk.Frame(notebook)
        notebook.add(speakers_frame, text="Speakers")
        self.create_speakers_tab(speakers_frame)

        # Schedule tab
        schedule_frame = ttk.Frame(notebook)
        notebook.add(schedule_frame, text="Session Schedule")
        self.create_schedule_tab(schedule_frame)

        # Registration tab
        registration_frame = ttk.Frame(notebook)
        notebook.add(registration_frame, text="Attendee Registration")
        self.create_registration_tab(registration_frame)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def create_conferences_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Upcoming Conferences",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        # Conferences list
        columns = ('Conference', 'Date', 'Venue', 'Papers', 'Attendees', 'Status')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Conference':
                tree.column(col, width=250)

        tree.pack(fill='both', expand=True, pady=(0, 10))

        # Sample conferences
        conferences = [
            ("Annual Student Research Symposium 2025", "May 15, 2025", "Main Auditorium", "45", "300", "Open"),
            ("Undergraduate Innovation Conference", "Jun 10, 2025", "Conference Center", "32", "180", "Planning"),
            ("Interdisciplinary Research Forum", "Jul 5, 2025", "Science Building", "28", "150", "Call for Papers")
        ]

        for conf in conferences:
            tree.insert('', 'end', values=conf)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')

        ttk.Button(btn_frame, text="➕ Create Conference",
                  command=self.create_conference).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="📝 Edit Details",
                  command=self.edit_conference).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="📊 View Analytics",
                  command=self.conference_analytics).pack(side='left')

    def create_submissions_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Paper Submissions",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        columns = ('Title', 'Author', 'Track', 'Submitted', 'Status', 'Reviews')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Title':
                tree.column(col, width=280)

        tree.pack(fill='both', expand=True, pady=(0, 10))

        # Sample submissions
        submissions = [
            ("Machine Learning in Healthcare", "Dr. Sarah Chen", "Computer Science", "Mar 15", "Under Review", "2/3"),
            ("Sustainable Energy Solutions", "Prof. Michael Green", "Engineering", "Mar 18", "Accepted", "3/3"),
            ("Social Media Impact on Mental Health", "Emily Rodriguez", "Psychology", "Mar 20", "Revision Requested", "3/3"),
            ("Quantum Computing Applications", "David Kim", "Physics", "Mar 22", "Under Review", "1/3")
        ]

        for sub in submissions:
            tree.insert('', 'end', values=sub)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')

        ttk.Button(btn_frame, text="✅ Accept Paper",
                  command=self.accept_paper).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Reject Paper",
                  command=self.reject_paper).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="📧 Request Revisions",
                  command=self.request_revisions).pack(side='left')

    def create_speakers_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Conference Speakers",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        columns = ('Name', 'Institution', 'Topic', 'Session', 'Status')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True, pady=(0, 10))

        # Sample speakers
        speakers = [
            ("Dr. Jane Smith", "MIT", "AI Ethics", "Keynote", "Confirmed"),
            ("Prof. John Doe", "Stanford", "Climate Change Solutions", "Session A", "Confirmed"),
            ("Dr. Maria Garcia", "Oxford", "Neuroscience Breakthroughs", "Session B", "Pending"),
            ("Prof. Ahmed Hassan", "Cambridge", "Quantum Physics", "Session C", "Invited")
        ]

        for speaker in speakers:
            tree.insert('', 'end', values=speaker)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')

        ttk.Button(btn_frame, text="➕ Invite Speaker",
                  command=self.invite_speaker).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="📧 Send Details",
                  command=self.send_speaker_details).pack(side='left')

    def create_schedule_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill='both', expand=True)

        schedule = """CONFERENCE SCHEDULE - Annual Student Research Symposium 2025
================================================================================

DAY 1 - Friday, May 15, 2025

08:00 - 09:00  Registration & Coffee
               Location: Main Lobby

09:00 - 10:00  Opening Keynote: "The Future of Student Research"
               Speaker: Dr. Jane Smith (MIT)
               Location: Main Auditorium

10:00 - 10:30  Coffee Break

10:30 - 12:00  PARALLEL SESSIONS A

               Session A1: Computer Science & AI
               Location: Room 101
               • Machine Learning in Healthcare (S. Chen)
               • Natural Language Processing Advances (M. Lee)
               • Computer Vision Applications (J. Park)

               Session A2: Engineering & Technology
               Location: Room 102
               • Sustainable Energy Solutions (M. Green)
               • Smart Cities Infrastructure (R. Brown)
               • Robotics Innovation (L. Wang)

               Session A3: Social Sciences
               Location: Room 103
               • Social Media Impact Study (E. Rodriguez)
               • Educational Technology Research (T. Johnson)
               • Community Engagement Models (A. Patel)

12:00 - 13:30  Lunch & Poster Session
               Location: Exhibition Hall
               45 poster presentations available for viewing

13:30 - 15:00  PARALLEL SESSIONS B

               Session B1: Physical Sciences
               Location: Room 201
               • Quantum Computing Applications (D. Kim)
               • Materials Science Innovations (Y. Zhang)
               • Astrophysics Research (C. Martinez)

               Session B2: Life Sciences
               Location: Room 202
               • Neuroscience Breakthroughs (M. Garcia)
               • Genetics Research (S. Taylor)
               • Environmental Biology (K. Anderson)

               Session B3: Humanities
               Location: Room 203
               • Digital Humanities Projects (L. Chen)
               • Historical Analysis Methods (R. Williams)
               • Literature & Society (N. Thompson)

15:00 - 15:30  Coffee Break

15:30 - 17:00  Panel Discussion: "Interdisciplinary Research Opportunities"
               Moderator: Prof. Ahmed Hassan (Cambridge)
               Location: Main Auditorium

17:00 - 18:30  Reception & Networking
               Location: Terrace

18:30          End of Day 1

---

DAY 2 - Saturday, May 16, 2025

09:00 - 10:30  Workshop Sessions (Registration Required)
               • Research Methodology
               • Grant Writing
               • Publication Strategies

10:30 - 11:00  Coffee Break

11:00 - 12:30  Best Paper Presentations
               Top 5 papers from each track
               Location: Main Auditorium

12:30 - 13:00  Awards Ceremony & Closing Remarks
               Location: Main Auditorium

13:00          Conference End
"""
        text.insert(1.0, schedule)
        text.config(state='disabled')

    def create_registration_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Attendee Registration",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        # Statistics
        stats_frame = ttk.LabelFrame(frame, text="Registration Statistics")
        stats_frame.pack(fill='x', pady=(0, 15))

        stats_text = """Total Registrations: 287 / 300 capacity
Student Attendees: 215 (75%)
Faculty Attendees: 52 (18%)
External Attendees: 20 (7%)

By Track:
  Computer Science: 85
  Engineering: 68
  Social Sciences: 52
  Physical Sciences: 45
  Life Sciences: 37
"""
        ttk.Label(stats_frame, text=stats_text, justify='left',
                 font=('Courier', 9)).pack(padx=15, pady=10)

        # Registration list
        list_frame = ttk.LabelFrame(frame, text="Recent Registrations")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Name', 'Affiliation', 'Type', 'Track', 'Registered')
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=8)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True)

        # Sample registrations
        registrations = [
            ("Alice Johnson", "University A", "Student", "Computer Science", "Apr 1, 2025"),
            ("Bob Smith", "University B", "Faculty", "Engineering", "Apr 2, 2025"),
            ("Carol Davis", "Tech Corp", "External", "AI Track", "Apr 3, 2025")
        ]

        for reg in registrations:
            tree.insert('', 'end', values=reg)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')

        ttk.Button(btn_frame, text="📊 Export List",
                  command=self.export_registrations).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="📧 Send Update",
                  command=self.send_registration_update).pack(side='left')

    def create_conference(self):
        messagebox.showinfo("Create Conference",
                           "Conference creation wizard:\n\n"
                           "1. Conference details\n"
                           "2. Venue and dates\n"
                           "3. Call for papers\n"
                           "4. Registration setup")

    def edit_conference(self):
        messagebox.showinfo("Edit Conference", "Conference details editor opened.")

    def conference_analytics(self):
        messagebox.showinfo("Conference Analytics",
                           "Conference metrics:\n\n"
                           "• Submission rate: 45 papers\n"
                           "• Acceptance rate: 67%\n"
                           "• Registration: 287/300 (96%)\n"
                           "• Budget status: On track")

    def accept_paper(self):
        messagebox.showinfo("Accept Paper", "Paper accepted. Notification sent to author.")

    def reject_paper(self):
        if messagebox.askyesno("Reject Paper", "Reject this paper submission?"):
            messagebox.showinfo("Rejected", "Paper rejected. Notification sent with reviewer feedback.")

    def request_revisions(self):
        messagebox.showinfo("Request Revisions",
                           "Revision request sent to author with reviewer comments.")

    def invite_speaker(self):
        messagebox.showinfo("Invite Speaker",
                           "Speaker invitation form:\n\n"
                           "• Speaker name and contact\n"
                           "• Proposed topic\n"
                           "• Session preference\n"
                           "• Travel arrangements")

    def send_speaker_details(self):
        messagebox.showinfo("Speaker Details", "Conference details sent to confirmed speakers.")

    def export_registrations(self):
        messagebox.showinfo("Export", "Registration list exported to CSV.")

    def send_registration_update(self):
        messagebox.showinfo("Send Update", "Update email sent to all registered attendees.")



class ResearchPresentationDialog:
    """Research presentation and poster session platform"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Research Presentation Platform")
        self.dialog.geometry("1100x800")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🔬 Research Presentation Platform",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Presentations tab
        presentations_frame = ttk.Frame(notebook)
        notebook.add(presentations_frame, text="Presentations")
        self.create_presentations_tab(presentations_frame)

        # Poster Sessions tab
        posters_frame = ttk.Frame(notebook)
        notebook.add(posters_frame, text="Poster Sessions")
        self.create_posters_tab(posters_frame)

        # Q&A Forum tab
        qa_frame = ttk.Frame(notebook)
        notebook.add(qa_frame, text="Q&A Forum")
        self.create_qa_tab(qa_frame)

        # Feedback tab
        feedback_frame = ttk.Frame(notebook)
        notebook.add(feedback_frame, text="Feedback")
        self.create_feedback_tab(feedback_frame)

        # Awards tab
        awards_frame = ttk.Frame(notebook)
        notebook.add(awards_frame, text="Research Awards")
        self.create_awards_tab(awards_frame)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def create_presentations_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Top buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(btn_frame, text="➕ Submit Presentation",
                  command=self.submit_presentation).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="📊 My Presentations",
                  command=self.my_presentations).pack(side='left')

        # Presentations list
        columns = ('Title', 'Presenter', 'Field', 'Date', 'Attendees', 'Rating')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Title':
                tree.column(col, width=280)

        tree.pack(fill='both', expand=True)

        # Sample presentations
        presentations = [
            ("AI in Medical Diagnosis", "Sarah Chen", "Computer Science", "May 15, 10:30 AM", "45", "4.8/5"),
            ("Renewable Energy Innovations", "Michael Green", "Engineering", "May 15, 11:00 AM", "38", "4.9/5"),
            ("Cognitive Psychology Research", "Emily Rodriguez", "Psychology", "May 15, 2:00 PM", "52", "4.7/5")
        ]

        for pres in presentations:
            tree.insert('', 'end', values=pres)

    def create_posters_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Poster Session Schedule",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill='both', expand=True, pady=(0, 10))

        content = """POSTER SESSION SCHEDULE
================================================================================

Session 1: 12:00 PM - 2:00 PM
Location: Exhibition Hall A

Computer Science & Engineering (Posters 1-15)
  P001: Deep Learning for Image Recognition - Alice Wang
  P002: Blockchain Security Analysis - Bob Chen
  P003: IoT Smart Home Systems - Carol Davis
  P004: Cloud Computing Optimization - David Lee
  P005: Cybersecurity Threat Detection - Emily Park

Life Sciences & Medicine (Posters 16-30)
  P016: Cancer Biomarker Discovery - Dr. Sarah Johnson
  P017: Vaccine Development Methods - Dr. Michael Brown
  P018: Genetic Engineering Applications - Dr. Lisa Garcia
  P019: Neuroscience Brain Mapping - Dr. John Smith
  P020: Microbiome Research - Dr. Maria Lopez

Session 2: 2:30 PM - 4:30 PM
Location: Exhibition Hall B

Physical Sciences (Posters 31-45)
  P031: Quantum Entanglement Study - Prof. Ahmed Hassan
  P032: Materials Science Innovation - Prof. Yuki Tanaka
  P033: Astrophysics Dark Matter - Prof. Carlos Martinez
  P034: Nanotechnology Applications - Prof. Sophie Dubois
  P035: Climate Modeling Research - Prof. James Wilson

POSTER GUIDELINES:
• Size: 48" x 36" (portrait orientation)
• Setup: 11:00 AM - 12:00 PM
• Presenter must be present during assigned session
• Q&A encouraged throughout session
• Judging: 1:00 PM - 3:00 PM
"""
        text.insert(1.0, content)
        text.config(state='disabled')

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')

        ttk.Button(btn_frame, text="📤 Upload Poster",
                  command=self.upload_poster).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="📝 Register for Session",
                  command=self.register_poster).pack(side='left')

    def create_qa_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Research Q&A Forum",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        # Q&A list
        columns = ('Question', 'Asker', 'Research Topic', 'Answers', 'Date')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Question':
                tree.column(col, width=300)

        tree.pack(fill='both', expand=True, pady=(0, 10))

        # Sample Q&A
        qa_items = [
            ("What dataset did you use for training?", "John Doe", "AI Medical Diagnosis", "2", "1 hour ago"),
            ("How do you handle scalability?", "Jane Smith", "Cloud Computing", "3", "2 hours ago"),
            ("Can this be applied to other fields?", "Bob Johnson", "Quantum Research", "1", "3 hours ago")
        ]

        for item in qa_items:
            tree.insert('', 'end', values=item)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')

        ttk.Button(btn_frame, text="❓ Ask Question",
                  command=self.ask_question).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="💬 View Thread",
                  command=self.view_qa_thread).pack(side='left')

    def create_feedback_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Presentation Feedback Collection",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        # Feedback stats
        stats_frame = ttk.LabelFrame(frame, text="Feedback Statistics")
        stats_frame.pack(fill='x', pady=(0, 15))

        stats_text = """Average Presentation Rating: 4.7 / 5.0
Total Feedback Responses: 287
Response Rate: 82%

Top Rated Presentations:
  1. "Renewable Energy Innovations" - 4.9/5 (38 responses)
  2. "AI in Medical Diagnosis" - 4.8/5 (45 responses)
  3. "Cognitive Psychology Research" - 4.7/5 (52 responses)

Feedback Categories:
  Content Quality: 4.8/5
  Presentation Skills: 4.6/5
  Visual Materials: 4.7/5
  Q&A Engagement: 4.5/5
"""
        ttk.Label(stats_frame, text=stats_text, justify='left',
                 font=('Courier', 9)).pack(padx=15, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')

        ttk.Button(btn_frame, text="📝 Submit Feedback",
                  command=self.submit_feedback).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="📊 View My Feedback",
                  command=self.view_my_feedback).pack(side='left')

    def create_awards_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill='both', expand=True)

        content = """RESEARCH AWARDS & RECOGNITION
================================================================================

2025 STUDENT RESEARCH AWARDS

🏆 Best Overall Research
   Winner: "Renewable Energy Innovations"
   Researcher: Michael Green (Engineering)
   Prize: £2,000 + Publication Support

🥇 Best Oral Presentation
   Winner: "AI in Medical Diagnosis"
   Researcher: Sarah Chen (Computer Science)
   Prize: £1,500

🥈 Best Poster Presentation
   Winner: "Quantum Entanglement Study"
   Researcher: Prof. Ahmed Hassan (Physics)
   Prize: £1,000

🥉 People's Choice Award
   Winner: "Cognitive Psychology Research"
   Researcher: Emily Rodriguez (Psychology)
   Prize: £500

CATEGORY AWARDS:

Computer Science & AI
  🌟 "Deep Learning Image Recognition" - Alice Wang
     £750 + Conference Travel Grant

Engineering & Technology
  🌟 "IoT Smart Home Systems" - Carol Davis
     £750 + Research Equipment Grant

Life Sciences & Medicine
  🌟 "Cancer Biomarker Discovery" - Dr. Sarah Johnson
     £750 + Lab Funding Support

Physical Sciences
  🌟 "Climate Modeling Research" - Prof. James Wilson
     £750 + Computational Resources

Social Sciences & Humanities
  🌟 "Digital Humanities Projects" - Dr. Lisa Chen
     £750 + Archival Access Grant

SPECIAL RECOGNITION:

🌟 Innovation Award: "Blockchain Security Analysis" - Bob Chen
🌟 Impact Award: "Vaccine Development Methods" - Dr. Michael Brown
🌟 Emerging Researcher: "Nanotechnology Applications" - Prof. Sophie Dubois

AWARD CRITERIA:
• Research Originality (30%)
• Methodology & Rigor (25%)
• Presentation Quality (20%)
• Practical Impact (15%)
• Peer Feedback (10%)

Total Awards Distributed: £15,000
Number of Winners: 15
Selection Committee: 12 faculty members

Awards Ceremony: May 16, 2025, 12:30 PM, Main Auditorium
"""
        text.insert(1.0, content)
        text.config(state='disabled')

    def submit_presentation(self):
        messagebox.showinfo("Submit Presentation",
                           "Presentation submission form:\n\n"
                           "• Research title and abstract\n"
                           "• Presenter information\n"
                           "• Field/track selection\n"
                           "• Upload slides (PDF/PPT)")

    def my_presentations(self):
        messagebox.showinfo("My Presentations",
                           "Your presentations:\n\n"
                           "Upcoming:\n"
                           "• \"Student Engagement Study\" - May 15, 3:00 PM\n\n"
                           "Past:\n"
                           "• \"Social Media Analysis\" - Apr 10 (Rated 4.6/5)")

    def upload_poster(self):
        messagebox.showinfo("Upload Poster",
                           "Poster upload:\n\n"
                           "• File format: PDF (max 10MB)\n"
                           "• Required size: 48\" x 36\"\n"
                           "• Include: Title, authors, abstract, methods, results")

    def register_poster(self):
        messagebox.showinfo("Register", "Poster session registration complete!")

    def ask_question(self):
        messagebox.showinfo("Ask Question",
                           "Post your question:\n\n"
                           "• Select research presentation\n"
                           "• Enter question text\n"
                           "• Submit (anonymous option available)")

    def view_qa_thread(self):
        messagebox.showinfo("Q&A Thread",
                           "Question: What dataset did you use?\n\n"
                           "Answer 1: We used the publicly available ImageNet dataset...\n"
                           "Answer 2: Additionally, we created a custom dataset...")

    def submit_feedback(self):
        messagebox.showinfo("Submit Feedback",
                           "Feedback form:\n\n"
                           "• Rate presentation (1-5 stars)\n"
                           "• Content quality\n"
                           "• Presentation skills\n"
                           "• Comments (optional)")

    def view_my_feedback(self):
        messagebox.showinfo("My Feedback Received",
                           "Feedback on your presentation:\n\n"
                           "Average Rating: 4.7/5\n"
                           "Total Responses: 28\n\n"
                           "Comments:\n"
                           "\"Excellent research!\"\n"
                           "\"Very clear presentation\"")



def open_academic_conferences_dialog(self):
    """Open academic conferences dialog"""
    dialog = AcademicConferencesDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


