import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
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
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class MentorshipBrowseDialog:
    """Dialog for finding a mentor or becoming one"""

    def __init__(self, parent, auth_manager, mode='find'):
        self.parent = parent
        self.auth = auth_manager
        self.mode = mode  # 'find' or 'become'

        self.dialog = tk.Toplevel(parent)
        if mode == 'find':
            self.dialog.title("Find a Mentor")
        else:
            self.dialog.title("Become a Mentor")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        if mode == 'find':
            self.load_mentors()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        if self.mode == 'find':
            title_label = ttk.Label(main_frame, text="Find a Mentor", font=('Arial', 14, 'bold'))
            title_label.pack(pady=(0, 10))

            list_frame = ttk.LabelFrame(main_frame, text="Available Mentors")
            list_frame.pack(fill='both', expand=True, pady=(0, 10))

            columns = ('Mentor', 'Skill Area', 'Rating', 'Active Mentees')
            self.mentors_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

            for col in columns:
                self.mentors_tree.heading(col, text=col)
                if col == 'Mentor':
                    self.mentors_tree.column(col, width=200)
                elif col == 'Skill Area':
                    self.mentors_tree.column(col, width=200)
                else:
                    self.mentors_tree.column(col, width=100)

            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.mentors_tree.yview)
            self.mentors_tree.configure(yscrollcommand=scrollbar.set)

            self.mentors_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x')

            ttk.Button(button_frame, text="Request Mentorship", command=self.request_mentor).pack(side='left', padx=(0, 10))
            ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')
        else:
            title_label = ttk.Label(main_frame, text="Become a Mentor", font=('Arial', 12, 'bold'))
            title_label.pack(pady=(0, 20))

            ttk.Label(main_frame, text="Skill Area:").pack(anchor='w', pady=(0, 5))
            self.skill_var = tk.StringVar()
            skill_combo = ttk.Combobox(main_frame, textvariable=self.skill_var, width=47)
            skill_combo['values'] = ('Academic - Math', 'Academic - Science', 'Academic - English',
                                    'Career - Resume Building', 'Career - Interview Prep',
                                    'Campus Life', 'Programming', 'Study Skills', 'Other')
            skill_combo.pack(fill='x', pady=(0, 10))

            ttk.Label(main_frame, text="Experience/Qualifications:").pack(anchor='w', pady=(0, 5))
            self.experience_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD)
            self.experience_text.pack(fill='both', expand=True, pady=(0, 10))

            ttk.Label(main_frame, text="Max Mentees:").pack(anchor='w', pady=(0, 5))
            self.max_var = tk.StringVar(value="3")
            ttk.Entry(main_frame, textvariable=self.max_var, width=10).pack(anchor='w', pady=(0, 10))

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x')

            ttk.Button(button_frame, text="Submit", command=self.become_mentor).pack(side='left', padx=(0, 10))
            ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def load_mentors(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT DISTINCT s.first_name || ' ' || s.last_name, mr.skill_area,
                   COALESCE(mr.mentor_rating, 0),
                   (SELECT COUNT(*) FROM mentorship_relationships
                    WHERE mentor_id = mr.mentor_id AND status = 'active') as mentee_count,
                   mr.mentor_id
            FROM mentorship_relationships mr
            INNER JOIN students s ON mr.mentor_id = s.student_id
            WHERE mr.status = 'active'
            GROUP BY mr.mentor_id, mr.skill_area
            ORDER BY mr.mentor_rating DESC
            ''')

            mentors = cursor.fetchall()

            for mentor in mentors:
                self.mentors_tree.insert('', 'end', values=mentor[:4], tags=(mentor[4],))

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load mentors: {str(e)}")

    def request_mentor(self):
        selection = self.mentors_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a mentor.")
            return

        item = self.mentors_tree.item(selection[0])
        mentor_id = item['tags'][0] if item['tags'] else None
        mentor_name = item['values'][0]
        skill_area = item['values'][1]

        if messagebox.askyesno("Confirm", f"Request mentorship from {mentor_name} for {skill_area}?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
                student_id = cursor.fetchone()[0]

                cursor.execute('''
                INSERT INTO mentorship_relationships (mentor_id, mentee_id, skill_area,
                                                     start_date, status)
                VALUES (?, ?, ?, ?, 'active')
                ''', (mentor_id, student_id, skill_area, datetime.now().isoformat()))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Mentorship request submitted!")
                self.dialog.destroy()
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to request mentorship: {str(e)}")

    def become_mentor(self):
        skill = self.skill_var.get().strip()
        experience = self.experience_text.get(1.0, tk.END).strip()
        max_mentees = self.max_var.get().strip()

        if not all([skill, experience, max_mentees]):
            messagebox.showwarning("Warning", "Please fill in all fields.")
            return

        messagebox.showinfo("Success", "Your mentor application has been submitted!\n\nYou will be notified once your application is approved.")
        self.dialog.destroy()



class MyMentorshipsDialog:
    """Dialog for viewing mentorship relationships"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Mentorships")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text="My Mentorships", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 10))

        # As Mentee tab
        mentee_frame = ttk.Frame(notebook)
        notebook.add(mentee_frame, text="As Mentee")

        columns = ('Mentor', 'Skill Area', 'Start Date', 'Status', 'Rating')
        self.mentee_tree = ttk.Treeview(mentee_frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            self.mentee_tree.heading(col, text=col)
            self.mentee_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(mentee_frame, orient='vertical', command=self.mentee_tree.yview)
        self.mentee_tree.configure(yscrollcommand=scrollbar.set)

        self.mentee_tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y')

        # As Mentor tab
        mentor_frame = ttk.Frame(notebook)
        notebook.add(mentor_frame, text="As Mentor")

        columns = ('Mentee', 'Skill Area', 'Start Date', 'Status', 'Rating')
        self.mentor_tree = ttk.Treeview(mentor_frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            self.mentor_tree.heading(col, text=col)
            self.mentor_tree.column(col, width=150)

        scrollbar2 = ttk.Scrollbar(mentor_frame, orient='vertical', command=self.mentor_tree.yview)
        self.mentor_tree.configure(yscrollcommand=scrollbar2.set)

        self.mentor_tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar2.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Schedule Session", command=self.schedule_session).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View Sessions", command=self.view_sessions).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return

            student_id = result[0]

            # As mentee
            cursor.execute('''
            SELECT s.first_name || ' ' || s.last_name, mr.skill_area, mr.start_date,
                   mr.status, COALESCE(mr.mentor_rating, 'Not rated')
            FROM mentorship_relationships mr
            INNER JOIN students s ON mr.mentor_id = s.student_id
            WHERE mr.mentee_id = ?
            ORDER BY mr.start_date DESC
            ''', (student_id,))

            mentee_relationships = cursor.fetchall()
            for item in mentee_relationships:
                self.mentee_tree.insert('', 'end', values=item)

            # As mentor
            cursor.execute('''
            SELECT s.first_name || ' ' || s.last_name, mr.skill_area, mr.start_date,
                   mr.status, COALESCE(mr.mentee_rating, 'Not rated')
            FROM mentorship_relationships mr
            INNER JOIN students s ON mr.mentee_id = s.student_id
            WHERE mr.mentor_id = ?
            ORDER BY mr.start_date DESC
            ''', (student_id,))

            mentor_relationships = cursor.fetchall()
            for item in mentor_relationships:
                self.mentor_tree.insert('', 'end', values=item)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load mentorships: {str(e)}")

    def schedule_session(self):
        messagebox.showinfo("Schedule Session", "This would open a dialog to schedule a mentorship session with date, time, and agenda.")

    def view_sessions(self):
        dialog = MentorshipSessionsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



class MentorshipSessionsDialog:
    """Dialog for viewing mentorship sessions"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Mentorship Sessions")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text="Mentorship Sessions", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        list_frame = ttk.LabelFrame(main_frame, text="Sessions")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Date', 'Duration', 'With', 'Role', 'Progress', 'Notes')
        self.sessions_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=18)

        for col in columns:
            self.sessions_tree.heading(col, text=col)
            if col in ('Notes', 'With'):
                self.sessions_tree.column(col, width=200)
            else:
                self.sessions_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.sessions_tree.yview)
        self.sessions_tree.configure(yscrollcommand=scrollbar.set)

        self.sessions_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return

            student_id = result[0]

            cursor.execute('''
            SELECT ms.session_date, ms.duration_minutes,
                   CASE
                       WHEN mr.mentor_id = ? THEN s1.first_name || ' ' || s1.last_name
                       ELSE s2.first_name || ' ' || s2.last_name
                   END as other_person,
                   CASE WHEN mr.mentor_id = ? THEN 'Mentor' ELSE 'Mentee' END as role,
                   COALESCE(ms.progress_rating, 0),
                   COALESCE(ms.notes, '')
            FROM mentorship_sessions ms
            INNER JOIN mentorship_relationships mr ON ms.relationship_id = mr.relationship_id
            LEFT JOIN students s1 ON mr.mentee_id = s1.student_id
            LEFT JOIN students s2 ON mr.mentor_id = s2.student_id
            WHERE mr.mentor_id = ? OR mr.mentee_id = ?
            ORDER BY ms.session_date DESC
            ''', (student_id, student_id, student_id, student_id))

            sessions = cursor.fetchall()

            for session in sessions:
                values = (session[0], f"{session[1]} min", session[2], session[3],
                         f"{session[4]}/5", session[5])
                self.sessions_tree.insert('', 'end', values=values)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load sessions: {str(e)}")
# Main execution

class ScheduleMentorshipSessionDialog:
    """Dialog for scheduling mentorship sessions"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Schedule Mentorship Session")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_relationships()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Schedule Mentorship Session", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Select relationship
        ttk.Label(main_frame, text="Select Mentorship Relationship:").pack(anchor='w', pady=(0, 5))
        self.relationship_var = tk.StringVar()
        self.relationship_combo = ttk.Combobox(main_frame, textvariable=self.relationship_var, state='readonly', width=55)
        self.relationship_combo.pack(fill='x', pady=(0, 15))

        # Date and time
        datetime_frame = ttk.Frame(main_frame)
        datetime_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(datetime_frame, text="Date:").grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.date_entry = ttk.Entry(datetime_frame, width=15)
        self.date_entry.grid(row=0, column=1, sticky='w')
        self.date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        ttk.Label(datetime_frame, text="Time:").grid(row=0, column=2, sticky='w', padx=(20, 10))
        self.time_entry = ttk.Entry(datetime_frame, width=10)
        self.time_entry.grid(row=0, column=3, sticky='w')
        self.time_entry.insert(0, "14:00")

        # Duration
        ttk.Label(datetime_frame, text="Duration (min):").grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(10, 0))
        self.duration_entry = ttk.Entry(datetime_frame, width=10)
        self.duration_entry.grid(row=1, column=1, sticky='w', pady=(10, 0))
        self.duration_entry.insert(0, "60")

        # Location
        ttk.Label(main_frame, text="Location/Meeting Link:").pack(anchor='w', pady=(10, 5))
        self.location_entry = ttk.Entry(main_frame, width=55)
        self.location_entry.pack(fill='x', pady=(0, 10))
        self.location_entry.insert(0, "Zoom Meeting (link to be sent)")

        # Agenda
        ttk.Label(main_frame, text="Agenda/Topics:").pack(anchor='w', pady=(0, 5))
        self.agenda_text = scrolledtext.ScrolledText(main_frame, height=8, wrap=tk.WORD)
        self.agenda_text.pack(fill='both', expand=True, pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Schedule Session", command=self.schedule_session).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def load_relationships(self):
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return

            student_id = result[0]

            # Get all mentorship relationships (both as mentor and mentee)
            cursor.execute('''
            SELECT mr.relationship_id,
                   CASE
                       WHEN mr.mentor_id = ? THEN 'Mentoring: ' || m.first_name || ' ' || m.last_name
                       ELSE 'Learning from: ' || mentor.first_name || ' ' || mentor.last_name
                   END as relationship_name,
                   mr.skill_area
            FROM mentorship_relationships mr
            LEFT JOIN students m ON mr.mentee_id = m.student_id
            LEFT JOIN students mentor ON mr.mentor_id = mentor.student_id
            WHERE (mr.mentor_id = ? OR mr.mentee_id = ?) AND mr.status = 'active'
            ORDER BY relationship_name
            ''', (student_id, student_id, student_id))

            relationships = cursor.fetchall()

            if relationships:
                rel_list = [f"{r[1]} ({r[2]})" for r in relationships]
                self.relationship_combo['values'] = rel_list
                self.relationship_data = relationships
                if rel_list:
                    self.relationship_combo.current(0)
            else:
                self.relationship_combo['values'] = ["No active mentorship relationships"]

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load relationships: {str(e)}")

    def schedule_session(self):
        if not self.relationship_combo.current() >= 0 or not hasattr(self, 'relationship_data'):
            messagebox.showwarning("Warning", "Please select a mentorship relationship.")
            return

        date = self.date_entry.get().strip()
        time = self.time_entry.get().strip()
        duration = self.duration_entry.get().strip()
        location = self.location_entry.get().strip()
        agenda = self.agenda_text.get(1.0, tk.END).strip()

        if not all([date, time, location]):
            messagebox.showwarning("Warning", "Please fill in all required fields.")
            return

        try:
            selected_index = self.relationship_combo.current()
            relationship_id = self.relationship_data[selected_index][0]

            session_datetime = f"{date} {time}:00"

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO mentorship_sessions (
                relationship_id, session_date, duration_minutes, location,
                agenda, status, created_date
            ) VALUES (?, ?, ?, ?, ?, 'scheduled', ?)
            ''', (relationship_id, session_datetime, int(duration or 60), location,
                  agenda, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Mentorship session scheduled successfully!\n\nBoth parties will be notified.")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to schedule session: {str(e)}")



class RateMentorshipDialog:
    """Dialog for rating mentorship experiences"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Rate Mentorship Experience")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_sessions()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Rate Mentorship Experience", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Select session
        ttk.Label(main_frame, text="Select Completed Session:").pack(anchor='w', pady=(0, 5))
        self.session_var = tk.StringVar()
        self.session_combo = ttk.Combobox(main_frame, textvariable=self.session_var, state='readonly', width=55)
        self.session_combo.pack(fill='x', pady=(0, 15))

        # Rating
        rating_frame = ttk.LabelFrame(main_frame, text="Your Rating")
        rating_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(rating_frame, text="Overall Experience:", font=('Arial', 10, 'bold')).pack(pady=(10, 5))

        # Star rating
        stars_frame = ttk.Frame(rating_frame)
        stars_frame.pack(pady=(0, 10))

        self.rating_var = tk.IntVar(value=5)
        for i in range(1, 6):
            ttk.Radiobutton(stars_frame, text=f"{'⭐' * i}", variable=self.rating_var, value=i).pack(side='left', padx=5)

        # Feedback
        ttk.Label(main_frame, text="Feedback (optional):").pack(anchor='w', pady=(0, 5))
        self.feedback_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD)
        self.feedback_text.pack(fill='both', expand=True, pady=(0, 10))
        self.feedback_text.insert(1.0, "Share your experience, what went well, and suggestions for improvement...")

        # Anonymous option
        self.anonymous_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Submit anonymously", variable=self.anonymous_var).pack(anchor='w', pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Submit Rating", command=self.submit_rating).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def load_sessions(self):
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return

            student_id = result[0]

            # Get completed sessions
            cursor.execute('''
            SELECT ms.session_id, ms.session_date, mr.skill_area,
                   CASE
                       WHEN mr.mentor_id = ? THEN m.first_name || ' ' || m.last_name
                       ELSE mentor.first_name || ' ' || mentor.last_name
                   END as other_person
            FROM mentorship_sessions ms
            JOIN mentorship_relationships mr ON ms.relationship_id = mr.relationship_id
            LEFT JOIN students m ON mr.mentee_id = m.student_id
            LEFT JOIN students mentor ON mr.mentor_id = mentor.student_id
            WHERE (mr.mentor_id = ? OR mr.mentee_id = ?)
            AND ms.status = 'completed'
            AND ms.session_id NOT IN (SELECT session_id FROM mentorship_ratings WHERE rater_id = ?)
            ORDER BY ms.session_date DESC
            ''', (student_id, student_id, student_id, student_id))

            sessions = cursor.fetchall()

            if sessions:
                session_list = [f"{s[1][:10]} - {s[2]} with {s[3]}" for s in sessions]
                self.session_combo['values'] = session_list
                self.session_data = sessions
                if session_list:
                    self.session_combo.current(0)
            else:
                self.session_combo['values'] = ["No completed sessions to rate"]

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load sessions: {str(e)}")

    def submit_rating(self):
        if not self.session_combo.current() >= 0 or not hasattr(self, 'session_data'):
            messagebox.showwarning("Warning", "Please select a session to rate.")
            return

        rating = self.rating_var.get()
        feedback = self.feedback_text.get(1.0, tk.END).strip()
        is_anonymous = self.anonymous_var.get()

        try:
            selected_index = self.session_combo.current()
            session_id = self.session_data[selected_index][0]

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            rater_id = cursor.fetchone()[0]

            cursor.execute('''
            INSERT INTO mentorship_ratings (
                session_id, rater_id, rating, feedback, is_anonymous, rating_date
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (session_id, rater_id, rating, feedback, is_anonymous, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Thank you for your feedback!\n\nYour rating has been submitted.")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to submit rating: {str(e)}")



def create_mentorship_tab(self):
    """Create mentorship tab"""
    mentorship_frame = ttk.Frame(self.notebook)
    self.notebook.add(mentorship_frame, text="Mentorship")

    # Left panel
    left_panel = ttk.LabelFrame(mentorship_frame, text="Mentorship Actions")
    left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)

    ttk.Button(left_panel, text="Find a Mentor",
              command=self.find_mentor_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Become a Mentor",
              command=self.become_mentor_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="My Relationships",
              command=self.view_my_mentorship_relationships).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Schedule Session",
              command=self.schedule_mentorship_session_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="View Sessions",
              command=self.view_mentorship_sessions).pack(fill='x', pady=2)

    # Right panel
    right_panel = ttk.LabelFrame(mentorship_frame, text="Mentorship Information")
    right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)

    self.mentorship_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD,
                                                    height=30, width=80)
    self.mentorship_text.pack(fill='both', expand=True, padx=5, pady=5)



def schedule_mentorship_session_enhanced(self):
    """Enhanced mentorship session scheduling"""
    try:
        dialog = ScheduleMentorshipSessionDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def rate_mentorship_experience(self):
    """Rate a mentorship session"""
    try:
        dialog = RateMentorshipDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def find_mentor_gui(self):
    """Find a mentor"""
    try:
        dialog = MentorshipBrowseDialog(self.root, self.auth_manager, mode='find')
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def become_mentor_gui(self):
    """Become a mentor"""
    try:
        dialog = MentorshipBrowseDialog(self.root, self.auth_manager, mode='become')
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def view_my_mentorship_relationships(self):
    """View my mentorship relationships"""
    try:
        dialog = MyMentorshipsDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def schedule_mentorship_session_gui(self):
    """Schedule mentorship session"""
    try:
        dialog = MyMentorshipsDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def view_mentorship_sessions(self):
    """View mentorship sessions"""
    try:
        dialog = MentorshipSessionsDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


