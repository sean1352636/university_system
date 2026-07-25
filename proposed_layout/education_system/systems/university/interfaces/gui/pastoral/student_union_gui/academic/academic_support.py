import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog, filedialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.systems.university.infrastructure.email.template_utils import render_template
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

# Import academic dialog classes
from education_system.systems.university.interfaces.gui.pastoral.student_union_gui.academic.resources import SharedResourcesDialog
from education_system.systems.university.interfaces.gui.pastoral.student_union_gui.academic.tutoring import PeerTutoringDialog, AcademicWorkshopsDialog
from education_system.systems.university.interfaces.gui.pastoral.student_union_gui.academic.study_groups import StudyGroupsDialog, ExamPrepGroupsDialog


class AcademicSupportDialog:
    """Main hub for academic support features"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Academic Support Hub")
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="🎓 Academic Support Hub",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Info banner
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill='x', pady=(0, 15))

        info_text = ("Access peer tutoring, study groups, shared academic resources, "
                    "exam preparation support, and academic workshops.")
        ttk.Label(info_frame, text=info_text, wraplength=1000,
                 justify='left', font=('Arial', 10)).pack(padx=10, pady=10)

        # Create grid of support options
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill='both', expand=True, pady=(0, 10))

        options = [
            ("Study Groups", "study_groups", "📚 Join or create study groups", "blue"),
            ("Peer Tutoring", "tutoring", "👨‍🏫 Find tutors or become one", "green"),
            ("Shared Resources", "resources", "📂 Notes, textbooks, study guides", "orange"),
            ("Exam Prep Groups", "exam_prep", "📝 Prepare for exams together", "purple"),
            ("Academic Workshops", "workshops", "🎯 Skill-building workshops", "teal"),
            ("My Academic Activity", "my_activity", "📊 Track my participation", "gray")
        ]

        for i, (title, key, description, color) in enumerate(options):
            card = ttk.LabelFrame(buttons_frame, text=title)
            card.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='nsew')

            ttk.Label(card, text=description, wraplength=450,
                     foreground=color).pack(padx=10, pady=5)

            command_map = {
                'study_groups': self.manage_study_groups,
                'tutoring': self.manage_peer_tutoring,
                'resources': self.manage_shared_resources,
                'exam_prep': self.exam_preparation_groups,
                'workshops': self.view_academic_workshops,
                'my_activity': self.view_my_activity
            }

            ttk.Button(card, text="Open",
                      command=command_map[key]).pack(padx=10, pady=5)

        for i in range(3):
            buttons_frame.rowconfigure(i, weight=1)
        for i in range(2):
            buttons_frame.columnconfigure(i, weight=1)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def manage_study_groups(self):
        dialog = StudyGroupsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def manage_peer_tutoring(self):
        dialog = PeerTutoringDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def manage_shared_resources(self):
        dialog = SharedResourcesDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def exam_preparation_groups(self):
        dialog = ExamPrepGroupsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def view_academic_workshops(self):
        dialog = AcademicWorkshopsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def view_my_activity(self):
        dialog = MyAcademicActivityDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



class MyAcademicActivityDialog:
    """View student's academic support activity"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Academic Activity")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📊 My Academic Support Activity",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create notebook for different activity areas
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Study groups tab
        study_groups_frame = ttk.Frame(notebook)
        notebook.add(study_groups_frame, text="Study Groups")
        self.create_study_groups_tab(study_groups_frame)

        # Tutoring tab
        tutoring_frame = ttk.Frame(notebook)
        notebook.add(tutoring_frame, text="Tutoring")
        self.create_tutoring_tab(tutoring_frame)

        # Resources tab
        resources_frame = ttk.Frame(notebook)
        notebook.add(resources_frame, text="My Resources")
        self.create_resources_tab(resources_frame)

        # Workshops tab
        workshops_frame = ttk.Frame(notebook)
        notebook.add(workshops_frame, text="Workshops")
        self.create_workshops_tab(workshops_frame)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def _ensure_study_groups_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_study_groups (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT NOT NULL,
                subject TEXT,
                description TEXT,
                max_members INTEGER DEFAULT 10,
                current_members INTEGER DEFAULT 1,
                meeting_schedule TEXT,
                location TEXT,
                created_by TEXT,
                created_at TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_study_group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id TEXT,
                joined_at TEXT,
                FOREIGN KEY (group_id) REFERENCES academic_study_groups (group_id)
            )
        ''')

    def create_study_groups_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="My Study Groups",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        columns = ('Group', 'Subject', 'Members', 'Schedule', 'Location', 'Status')
        self.sg_tree = ttk.Treeview(frame, columns=columns, show='headings', height=8)

        for col in columns:
            self.sg_tree.heading(col, text=col)
            if col in ('Group', 'Schedule'):
                self.sg_tree.column(col, width=180)
            elif col == 'Members':
                self.sg_tree.column(col, width=80)
            else:
                self.sg_tree.column(col, width=120)

        self.sg_tree.pack(fill='both', expand=True)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_frame, text="Create Study Group",
                  command=self._create_study_group).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Join Group",
                  command=self._join_study_group).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh",
                  command=self._load_study_groups).pack(side='left', padx=5)

        self.sg_stats_label = ttk.Label(frame, text="", font=('Arial', 10))
        self.sg_stats_label.pack(pady=(10, 0))

        self._load_study_groups()

    def _load_study_groups(self):
        for item in self.sg_tree.get_children():
            self.sg_tree.delete(item)
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_study_groups_table(cursor)
            user_id = str(self.auth.current_user.get('id', ''))
            cursor.execute('''
                SELECT g.group_id, g.group_name, g.subject,
                       g.current_members || '/' || g.max_members,
                       g.meeting_schedule, g.location, g.status
                FROM academic_study_groups g
                LEFT JOIN academic_study_group_members m ON g.group_id = m.group_id
                WHERE g.created_by = ? OR m.user_id = ?
                GROUP BY g.group_id
                ORDER BY g.created_at DESC
            ''', (user_id, user_id))
            rows = cursor.fetchall()
            for row in rows:
                self.sg_tree.insert('', 'end', iid=str(row[0]),
                                   values=(row[1], row[2], row[3], row[4], row[5], row[6]))
            count = len(rows)
            self.sg_stats_label.config(text=f"Groups joined: {count}")
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load study groups: {e}")

    def _create_study_group(self):
        create_win = tk.Toplevel(self.dialog)
        create_win.title("Create Study Group")
        create_win.geometry("450x400")
        create_win.transient(self.dialog)
        create_win.grab_set()

        fields_frame = ttk.Frame(create_win)
        fields_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(fields_frame, text="Group Name:").grid(row=0, column=0, sticky='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=name_var, width=40).grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(fields_frame, text="Subject:").grid(row=1, column=0, sticky='w', pady=5)
        subject_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=subject_var, width=40).grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(fields_frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=5)
        desc_text = tk.Text(fields_frame, width=30, height=4)
        desc_text.grid(row=2, column=1, pady=5, padx=5)

        ttk.Label(fields_frame, text="Max Members:").grid(row=3, column=0, sticky='w', pady=5)
        max_var = tk.StringVar(value="10")
        ttk.Entry(fields_frame, textvariable=max_var, width=10).grid(row=3, column=1, sticky='w', pady=5, padx=5)

        ttk.Label(fields_frame, text="Schedule:").grid(row=4, column=0, sticky='w', pady=5)
        sched_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=sched_var, width=40).grid(row=4, column=1, pady=5, padx=5)

        ttk.Label(fields_frame, text="Location:").grid(row=5, column=0, sticky='w', pady=5)
        loc_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=loc_var, width=40).grid(row=5, column=1, pady=5, padx=5)

        def save_group():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Warning", "Group name is required.", parent=create_win)
                return
            try:
                max_m = int(max_var.get())
            except ValueError:
                messagebox.showwarning("Warning", "Max members must be a number.", parent=create_win)
                return
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                self._ensure_study_groups_table(cursor)
                user_id = str(self.auth.current_user.get('id', ''))
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO academic_study_groups
                    (group_name, subject, description, max_members, current_members,
                     meeting_schedule, location, created_by, created_at, status)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, 'active')
                ''', (name, subject_var.get().strip(), desc_text.get('1.0', 'end').strip(),
                      max_m, sched_var.get().strip(), loc_var.get().strip(), user_id, now))
                group_id = cursor.lastrowid
                cursor.execute('''
                    INSERT INTO academic_study_group_members (group_id, user_id, joined_at)
                    VALUES (?, ?, ?)
                ''', (group_id, user_id, now))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success", "Study group created!", parent=create_win)
                create_win.destroy()
                self._load_study_groups()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create group: {e}", parent=create_win)

        ttk.Button(fields_frame, text="Create", command=save_group).grid(row=6, column=1, sticky='e', pady=15)

    def _join_study_group(self):
        join_win = tk.Toplevel(self.dialog)
        join_win.title("Join Study Group")
        join_win.geometry("700x450")
        join_win.transient(self.dialog)
        join_win.grab_set()

        ttk.Label(join_win, text="Available Study Groups", font=('Arial', 11, 'bold')).pack(pady=10)

        columns = ('ID', 'Group', 'Subject', 'Members', 'Schedule', 'Location')
        join_tree = ttk.Treeview(join_win, columns=columns, show='headings', height=10)
        for col in columns:
            join_tree.heading(col, text=col)
            if col == 'ID':
                join_tree.column(col, width=40)
        join_tree.pack(fill='both', expand=True, padx=10, pady=5)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_study_groups_table(cursor)
            user_id = str(self.auth.current_user.get('id', ''))
            cursor.execute('''
                SELECT g.group_id, g.group_name, g.subject,
                       g.current_members || '/' || g.max_members,
                       g.meeting_schedule, g.location
                FROM academic_study_groups g
                WHERE g.status = 'active' AND g.current_members < g.max_members
                  AND g.group_id NOT IN (
                      SELECT group_id FROM academic_study_group_members WHERE user_id = ?
                  )
                ORDER BY g.created_at DESC
            ''', (user_id,))
            for row in cursor.fetchall():
                join_tree.insert('', 'end', iid=str(row[0]), values=row)
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load groups: {e}", parent=join_win)

        def do_join():
            sel = join_tree.selection()
            if not sel:
                messagebox.showwarning("Warning", "Select a group to join.", parent=join_win)
                return
            group_id = int(sel[0])
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                user_id = str(self.auth.current_user.get('id', ''))
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO academic_study_group_members (group_id, user_id, joined_at)
                    VALUES (?, ?, ?)
                ''', (group_id, user_id, now))
                cursor.execute('''
                    UPDATE academic_study_groups SET current_members = current_members + 1
                    WHERE group_id = ?
                ''', (group_id,))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success", "You have joined the study group!", parent=join_win)
                join_win.destroy()
                self._load_study_groups()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to join group: {e}", parent=join_win)

        ttk.Button(join_win, text="Join Selected Group", command=do_join).pack(pady=10)

    def _ensure_tutoring_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS peer_tutoring_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tutor_id TEXT NOT NULL,
                subject TEXT,
                description TEXT,
                availability TEXT,
                rate TEXT DEFAULT 'Free',
                status TEXT DEFAULT 'available',
                created_at TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS peer_tutoring_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                student_id TEXT NOT NULL,
                message TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                FOREIGN KEY (session_id) REFERENCES peer_tutoring_sessions (session_id)
            )
        ''')

    def create_tutoring_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Tutoring Activity",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        # Treeview for available tutors
        columns = ('Tutor', 'Subject', 'Availability', 'Rate', 'Status')
        self.tutor_tree = ttk.Treeview(frame, columns=columns, show='headings', height=8)
        for col in columns:
            self.tutor_tree.heading(col, text=col)
            if col == 'Tutor':
                self.tutor_tree.column(col, width=150)
            elif col == 'Subject':
                self.tutor_tree.column(col, width=200)
            else:
                self.tutor_tree.column(col, width=120)

        self.tutor_tree.pack(fill='both', expand=True)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_frame, text="Request Tutoring",
                  command=self._request_tutoring).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Offer Tutoring",
                  command=self._offer_tutoring).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh",
                  command=self._load_tutoring).pack(side='left', padx=5)

        self._load_tutoring()

    def _load_tutoring(self):
        for item in self.tutor_tree.get_children():
            self.tutor_tree.delete(item)
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_tutoring_table(cursor)
            cursor.execute('''
                SELECT session_id, tutor_id, subject, availability, rate, status
                FROM peer_tutoring_sessions
                WHERE status = 'available'
                ORDER BY created_at DESC
            ''')
            for row in cursor.fetchall():
                self.tutor_tree.insert('', 'end', iid=str(row[0]),
                                      values=(row[1], row[2], row[3], row[4], row[5]))
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tutors: {e}")

    def _request_tutoring(self):
        sel = self.tutor_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a tutor to request tutoring from.")
            return
        session_id = int(sel[0])

        msg = simpledialog.askstring("Request Tutoring",
                                     "Enter a message for the tutor:",
                                     parent=self.dialog)
        if msg is None:
            return
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            user_id = str(self.auth.current_user.get('id', ''))
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO peer_tutoring_requests (session_id, student_id, message, status, created_at)
                VALUES (?, ?, ?, 'pending', ?)
            ''', (session_id, user_id, msg, now))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "Tutoring request submitted!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit request: {e}")

    def _offer_tutoring(self):
        offer_win = tk.Toplevel(self.dialog)
        offer_win.title("Offer Tutoring")
        offer_win.geometry("450x350")
        offer_win.transient(self.dialog)
        offer_win.grab_set()

        fields_frame = ttk.Frame(offer_win)
        fields_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(fields_frame, text="Subject:").grid(row=0, column=0, sticky='w', pady=5)
        subject_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=subject_var, width=35).grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(fields_frame, text="Description:").grid(row=1, column=0, sticky='nw', pady=5)
        desc_text = tk.Text(fields_frame, width=27, height=4)
        desc_text.grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(fields_frame, text="Availability:").grid(row=2, column=0, sticky='w', pady=5)
        avail_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=avail_var, width=35).grid(row=2, column=1, pady=5, padx=5)

        ttk.Label(fields_frame, text="Rate:").grid(row=3, column=0, sticky='w', pady=5)
        rate_var = tk.StringVar(value="Free")
        ttk.Entry(fields_frame, textvariable=rate_var, width=15).grid(row=3, column=1, sticky='w', pady=5, padx=5)

        def save_offer():
            subject = subject_var.get().strip()
            if not subject:
                messagebox.showwarning("Warning", "Subject is required.", parent=offer_win)
                return
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                self._ensure_tutoring_table(cursor)
                user_id = str(self.auth.current_user.get('id', ''))
                username = self.auth.current_user.get('username', user_id)
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO peer_tutoring_sessions
                    (tutor_id, subject, description, availability, rate, status, created_at)
                    VALUES (?, ?, ?, ?, ?, 'available', ?)
                ''', (username, subject, desc_text.get('1.0', 'end').strip(),
                      avail_var.get().strip(), rate_var.get().strip(), now))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success", "Tutoring offer created!", parent=offer_win)
                offer_win.destroy()
                self._load_tutoring()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create offer: {e}", parent=offer_win)

        ttk.Button(fields_frame, text="Offer", command=save_offer).grid(row=4, column=1, sticky='e', pady=15)

    def _ensure_resources_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shared_academic_resources (
                resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                subject TEXT,
                resource_type TEXT,
                description TEXT,
                file_path TEXT,
                uploaded_by TEXT,
                upload_date TEXT,
                downloads INTEGER DEFAULT 0
            )
        ''')

    def create_resources_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="My Shared Resources",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        columns = ('Title', 'Subject', 'Type', 'Downloads', 'Upload Date')
        self.res_tree = ttk.Treeview(frame, columns=columns, show='headings', height=6)

        for col in columns:
            self.res_tree.heading(col, text=col)
            if col == 'Title':
                self.res_tree.column(col, width=250)
            elif col == 'Upload Date':
                self.res_tree.column(col, width=140)
            else:
                self.res_tree.column(col, width=100)

        self.res_tree.pack(fill='both', expand=True)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_frame, text="Upload Resource",
                  command=self._upload_resource).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh",
                  command=self._load_resources).pack(side='left', padx=5)

        self.res_stats_label = ttk.Label(frame, text="", font=('Arial', 10))
        self.res_stats_label.pack(pady=(10, 0))

        self._load_resources()

    def _load_resources(self):
        for item in self.res_tree.get_children():
            self.res_tree.delete(item)
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_resources_table(cursor)
            user_id = str(self.auth.current_user.get('id', ''))
            cursor.execute('''
                SELECT resource_id, title, subject, resource_type, downloads, upload_date
                FROM shared_academic_resources
                WHERE uploaded_by = ?
                ORDER BY upload_date DESC
            ''', (user_id,))
            rows = cursor.fetchall()
            total_downloads = 0
            for row in rows:
                self.res_tree.insert('', 'end', iid=str(row[0]),
                                    values=(row[1], row[2], row[3], row[4], row[5]))
                total_downloads += (row[4] or 0)
            count = len(rows)
            self.res_stats_label.config(
                text=f"Total uploads: {count} | Total downloads: {total_downloads}")
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load resources: {e}")

    def _upload_resource(self):
        upload_win = tk.Toplevel(self.dialog)
        upload_win.title("Upload Resource")
        upload_win.geometry("500x400")
        upload_win.transient(self.dialog)
        upload_win.grab_set()

        fields_frame = ttk.Frame(upload_win)
        fields_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(fields_frame, text="Title:").grid(row=0, column=0, sticky='w', pady=5)
        title_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=title_var, width=40).grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(fields_frame, text="Subject:").grid(row=1, column=0, sticky='w', pady=5)
        subject_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=subject_var, width=40).grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(fields_frame, text="Type:").grid(row=2, column=0, sticky='w', pady=5)
        type_var = tk.StringVar(value="Notes")
        ttk.Combobox(fields_frame, textvariable=type_var, width=20,
                     values=["Notes", "Study Guide", "Past Exam", "Textbook", "Other"],
                     state='readonly').grid(row=2, column=1, sticky='w', pady=5, padx=5)

        ttk.Label(fields_frame, text="Description:").grid(row=3, column=0, sticky='nw', pady=5)
        desc_text = tk.Text(fields_frame, width=30, height=3)
        desc_text.grid(row=3, column=1, pady=5, padx=5)

        ttk.Label(fields_frame, text="File:").grid(row=4, column=0, sticky='w', pady=5)
        file_var = tk.StringVar()
        file_entry = ttk.Entry(fields_frame, textvariable=file_var, width=30, state='readonly')
        file_entry.grid(row=4, column=1, sticky='w', pady=5, padx=5)

        def browse_file():
            path = filedialog.askopenfilename(
                title="Select Resource File",
                parent=upload_win,
                filetypes=[("All Files", "*.*"), ("PDF", "*.pdf"),
                           ("Documents", "*.docx *.doc"), ("Text", "*.txt")]
            )
            if path:
                file_var.set(path)

        ttk.Button(fields_frame, text="Browse...", command=browse_file).grid(row=4, column=1, sticky='e', pady=5, padx=5)

        def save_resource():
            title = title_var.get().strip()
            if not title:
                messagebox.showwarning("Warning", "Title is required.", parent=upload_win)
                return
            src_path = file_var.get().strip()
            dest_path = ""
            if src_path and os.path.isfile(src_path):
                uploads_dir = os.path.join(os.path.dirname(str(DEFAULT_DB_PATH)), 'uploads')
                os.makedirs(uploads_dir, exist_ok=True)
                filename = os.path.basename(src_path)
                dest_path = os.path.join(uploads_dir, filename)
                import shutil
                shutil.copy2(src_path, dest_path)
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                self._ensure_resources_table(cursor)
                user_id = str(self.auth.current_user.get('id', ''))
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO shared_academic_resources
                    (title, subject, resource_type, description, file_path, uploaded_by, upload_date, downloads)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                ''', (title, subject_var.get().strip(), type_var.get(),
                      desc_text.get('1.0', 'end').strip(), dest_path, user_id, now))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success", "Resource uploaded!", parent=upload_win)
                upload_win.destroy()
                self._load_resources()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to upload resource: {e}", parent=upload_win)

        ttk.Button(fields_frame, text="Upload", command=save_resource).grid(row=5, column=1, sticky='e', pady=15)

    def _ensure_workshops_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_workshops (
                workshop_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                instructor TEXT,
                date TEXT,
                time TEXT,
                location TEXT,
                max_participants INTEGER DEFAULT 30,
                registered INTEGER DEFAULT 0,
                status TEXT DEFAULT 'upcoming',
                created_at TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_workshop_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workshop_id INTEGER,
                user_id TEXT,
                registered_at TEXT,
                attended INTEGER DEFAULT 0,
                FOREIGN KEY (workshop_id) REFERENCES academic_workshops (workshop_id)
            )
        ''')

    def create_workshops_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="My Workshops",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        columns = ('Title', 'Instructor', 'Date', 'Time', 'Location', 'Status')
        self.ws_tree = ttk.Treeview(frame, columns=columns, show='headings', height=8)
        for col in columns:
            self.ws_tree.heading(col, text=col)
            if col == 'Title':
                self.ws_tree.column(col, width=200)
            elif col in ('Instructor', 'Location'):
                self.ws_tree.column(col, width=140)
            else:
                self.ws_tree.column(col, width=100)

        self.ws_tree.pack(fill='both', expand=True)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_frame, text="Register for Workshop",
                  command=self._register_workshop).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh",
                  command=self._load_workshops).pack(side='left', padx=5)

        self.ws_stats_label = ttk.Label(frame, text="", font=('Arial', 10))
        self.ws_stats_label.pack(pady=(10, 0))

        self._load_workshops()

    def _load_workshops(self):
        for item in self.ws_tree.get_children():
            self.ws_tree.delete(item)
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_workshops_table(cursor)
            user_id = str(self.auth.current_user.get('id', ''))
            cursor.execute('''
                SELECT w.workshop_id, w.title, w.instructor, w.date, w.time,
                       w.location, w.status
                FROM academic_workshops w
                JOIN academic_workshop_registrations r ON w.workshop_id = r.workshop_id
                WHERE r.user_id = ?
                ORDER BY w.date DESC
            ''', (user_id,))
            rows = cursor.fetchall()
            for row in rows:
                self.ws_tree.insert('', 'end', iid=str(row[0]),
                                   values=(row[1], row[2], row[3], row[4], row[5], row[6]))
            self.ws_stats_label.config(text=f"Workshops registered: {len(rows)}")
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load workshops: {e}")

    def _register_workshop(self):
        reg_win = tk.Toplevel(self.dialog)
        reg_win.title("Register for Workshop")
        reg_win.geometry("750x450")
        reg_win.transient(self.dialog)
        reg_win.grab_set()

        ttk.Label(reg_win, text="Available Workshops", font=('Arial', 11, 'bold')).pack(pady=10)

        columns = ('ID', 'Title', 'Instructor', 'Date', 'Time', 'Location', 'Spots')
        reg_tree = ttk.Treeview(reg_win, columns=columns, show='headings', height=10)
        for col in columns:
            reg_tree.heading(col, text=col)
            if col == 'ID':
                reg_tree.column(col, width=40)
            elif col == 'Title':
                reg_tree.column(col, width=180)
        reg_tree.pack(fill='both', expand=True, padx=10, pady=5)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_workshops_table(cursor)
            user_id = str(self.auth.current_user.get('id', ''))
            cursor.execute('''
                SELECT w.workshop_id, w.title, w.instructor, w.date, w.time,
                       w.location, (w.max_participants - w.registered) as spots
                FROM academic_workshops w
                WHERE w.status = 'upcoming' AND w.registered < w.max_participants
                  AND w.workshop_id NOT IN (
                      SELECT workshop_id FROM academic_workshop_registrations WHERE user_id = ?
                  )
                ORDER BY w.date ASC
            ''', (user_id,))
            for row in cursor.fetchall():
                reg_tree.insert('', 'end', iid=str(row[0]), values=row)
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load workshops: {e}", parent=reg_win)

        def do_register():
            sel = reg_tree.selection()
            if not sel:
                messagebox.showwarning("Warning", "Select a workshop to register.", parent=reg_win)
                return
            workshop_id = int(sel[0])
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                user_id = str(self.auth.current_user.get('id', ''))
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO academic_workshop_registrations (workshop_id, user_id, registered_at)
                    VALUES (?, ?, ?)
                ''', (workshop_id, user_id, now))
                cursor.execute('''
                    UPDATE academic_workshops SET registered = registered + 1
                    WHERE workshop_id = ?
                ''', (workshop_id,))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success", "Registered for workshop!", parent=reg_win)
                reg_win.destroy()
                self._load_workshops()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to register: {e}", parent=reg_win)

        ttk.Button(reg_win, text="Register", command=do_register).pack(pady=10)


# ============================================================================
# LEARNING INTEGRATION SYSTEM - 4 Features
# ============================================================================


class LearningIntegrationDialog:
    """Main hub for learning integration and academic event features"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Learning Integration")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="🎓 Learning Integration Hub",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Info banner
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill='x', pady=(0, 15))

        info_text = ("Integrate academic learning with student union activities. Organize conferences, "
                    "showcase research, earn course credit, and track learning outcomes.")
        ttk.Label(info_frame, text=info_text, wraplength=950,
                 justify='left', font=('Arial', 10)).pack(padx=10, pady=10)

        # Create grid of learning options
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill='both', expand=True, pady=(0, 10))

        options = [
            ("Academic Conferences", "conferences", "📚 Organize and attend academic conferences", "blue"),
            ("Research Presentations", "research", "🔬 Showcase research and poster sessions", "green"),
            ("Learning Analytics", "analytics", "📊 Track learning outcomes and skills", "purple"),
            ("Course Credit Events", "credit", "🎯 Events eligible for course credit", "orange")
        ]

        for i, (title, key, description, color) in enumerate(options):
            card = ttk.LabelFrame(buttons_frame, text=title)
            card.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='nsew')

            ttk.Label(card, text=description, wraplength=420,
                     foreground=color).pack(padx=10, pady=5)

            command_map = {
                'conferences': self.organize_academic_conferences,
                'research': self.research_presentation_platform,
                'analytics': self.learning_analytics_dashboard,
                'credit': self.course_credit_events
            }

            ttk.Button(card, text="Open",
                      command=command_map[key]).pack(padx=10, pady=5)

        for i in range(2):
            buttons_frame.rowconfigure(i, weight=1)
            buttons_frame.columnconfigure(i, weight=1)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def organize_academic_conferences(self):
        from education_system.systems.university.interfaces.gui.pastoral.student_union_gui.conferences.conferences import AcademicConferencesOrganizerDialog
        dialog = AcademicConferencesOrganizerDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def research_presentation_platform(self):
        from education_system.systems.university.interfaces.gui.pastoral.student_union_gui.conferences.conferences import ResearchPresentationDialog
        dialog = ResearchPresentationDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def learning_analytics_dashboard(self):
        from education_system.systems.university.interfaces.gui.pastoral.student_union_gui.analytics.analytics import LearningAnalyticsDashboardDialog
        dialog = LearningAnalyticsDashboardDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def course_credit_events(self):
        cce_win = tk.Toplevel(self.dialog)
        cce_win.title("Course Credit Events")
        cce_win.geometry("850x550")
        cce_win.transient(self.dialog)
        cce_win.grab_set()

        main_frame = ttk.Frame(cce_win)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Events Eligible for Course Credit",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        columns = ('Event', 'Date', 'Category', 'Credits', 'Status')
        cce_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)
        for col in columns:
            cce_tree.heading(col, text=col)
            if col == 'Event':
                cce_tree.column(col, width=250)
            elif col == 'Date':
                cce_tree.column(col, width=120)
            elif col == 'Credits':
                cce_tree.column(col, width=70)
            else:
                cce_tree.column(col, width=120)

        cce_tree.pack(fill='both', expand=True)

        # Create credit_events tracking table and load events from union_events
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS course_credit_registrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER,
                    user_id TEXT,
                    credits INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'registered',
                    registered_at TEXT
                )
            ''')
            conn.commit()
            user_id = str(self.auth.current_user.get('id', ''))

            # Find credit-bearing events from union_events (academic/course categories)
            cursor.execute('''
                SELECT e.event_id, e.event_name, e.event_date, e.category,
                       CASE
                           WHEN cr.status IS NOT NULL THEN cr.status
                           ELSE 'available'
                       END as reg_status
                FROM union_events e
                LEFT JOIN course_credit_registrations cr
                    ON e.event_id = cr.event_id AND cr.user_id = ?
                WHERE LOWER(e.category) IN ('academic', 'course', 'conference',
                      'workshop', 'seminar', 'research', 'leadership')
                   OR LOWER(e.category) LIKE '%credit%'
                   OR LOWER(e.category) LIKE '%academic%'
                ORDER BY e.event_date ASC
            ''', (user_id,))
            rows = cursor.fetchall()
            for row in rows:
                credits = 1  # default credit value
                cat = (row[3] or '').lower()
                if 'leadership' in cat or 'conference' in cat:
                    credits = 2
                if 'research' in cat:
                    credits = 3
                cce_tree.insert('', 'end', iid=str(row[0]),
                               values=(row[1], row[2], row[3], credits, row[4]))
            conn.close()
        except Exception as e:
            # If union_events doesn't exist yet, show informational message
            ttk.Label(main_frame,
                     text=f"No credit-bearing events found. ({e})",
                     foreground='gray').pack(pady=5)

        def register_credit():
            sel = cce_tree.selection()
            if not sel:
                messagebox.showwarning("Warning", "Select an event to register for credit.",
                                       parent=cce_win)
                return
            event_id = int(sel[0])
            values = cce_tree.item(sel[0], 'values')
            if values and values[4] == 'registered':
                messagebox.showinfo("Info", "You are already registered for this event.",
                                    parent=cce_win)
                return
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                user_id = str(self.auth.current_user.get('id', ''))
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                credits = int(values[3]) if values else 1
                cursor.execute('''
                    INSERT INTO course_credit_registrations
                    (event_id, user_id, credits, status, registered_at)
                    VALUES (?, ?, ?, 'registered', ?)
                ''', (event_id, user_id, credits, now))
                conn.commit()
                conn.close()
                cce_tree.set(sel[0], 'Status', 'registered')
                messagebox.showinfo("Success",
                                    f"Registered for {values[0]} ({credits} credit(s)).",
                                    parent=cce_win)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to register: {e}", parent=cce_win)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text="Register for Credit",
                  command=register_credit).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close",
                  command=cce_win.destroy).pack(side='right', padx=5)



def open_academic_support_dialog(self):
    """Open academic support hub"""
    dialog = AcademicSupportDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


