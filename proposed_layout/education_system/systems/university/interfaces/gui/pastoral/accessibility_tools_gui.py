"""
Accessibility & Accommodation Tools GUI

Comprehensive interface for managing accessibility profiles, accommodation requests,
exam accommodations, and assistive technology.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional, List, Dict, Any
import traceback
import json

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.activity_logger import log_activity

# Import i18n for language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)
from education_system.systems.university.domain.pastoral.services.accessibility_tools import (
    AccessibilityProfileManager, AccommodationRequestManager,
    ExamAccommodationManager, AssistiveTechManager
)


class AccessibilityToolsGUI:
    """Main GUI for Accessibility & Accommodation Tools"""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_container=None):
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.auth = auth
        self.window = None
        self.parent_container = parent_container
        self._is_embedded = parent_container is not None
        self.current_user = auth.current_user if auth and auth.current_user else None

        # Theme mapping between database values and display values
        self.theme_db_to_display = {
            'standard': lambda: _t("accessibility.themes.standard"),
            'high_contrast': lambda: _t("accessibility.themes.high_contrast"),
            'dark': lambda: _t("accessibility.themes.dark")
        }
        self.theme_display_to_db = {}  # Will be populated dynamically

        # Status mapping between database values and display values
        self.status_db_to_display = {
            'pending': lambda: _t("accessibility.status_values.pending"),
            'approved': lambda: _t("accessibility.status_values.approved"),
            'denied': lambda: _t("accessibility.status_values.denied"),
            'active': lambda: _t("accessibility.status_values.active"),
            'fulfilled': lambda: _t("accessibility.status_values.fulfilled")
        }
        self.status_display_to_db = {}  # Will be populated dynamically

        # Permission check
        if not self.current_user:
            messagebox.showerror(_t("common.error"), _t("accessibility.error.login_required"))
            return

        self.create_main_window()

    def create_main_window(self):
        """Create the main accessibility tools window"""
        try:
            if self._is_embedded:
                self.window = self.parent_container
            else:
                self.window = tk.Toplevel(self.root)
                self.window.title(_t("accessibility.title"))
                self.window.geometry("1400x900")
                self.window.minsize(1200, 700)

            # Configure style
            style = ttk.Style()
            style.configure('Header.TLabel', font=('Arial', 16, 'bold'))
            style.configure('Section.TLabel', font=('Arial', 12, 'bold'))

            if not self._is_embedded:
                # Bottom frame with close button - pack FIRST to reserve space
                bottom_frame = ttk.Frame(self.window)
                bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)

                ttk.Button(bottom_frame, text=_t("accessibility.btn.close"),
                          command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

                # Status bar
                self.status_bar = ttk.Label(self.window, text=_t("accessibility.status.ready"), relief=tk.SUNKEN, anchor=tk.W)
                self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
            else:
                self.status_bar = ttk.Label(self.window, text=_t("accessibility.status.ready"), relief=tk.SUNKEN, anchor=tk.W)
                self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

            # Main container with tabs
            self.notebook = ttk.Notebook(self.window)
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Create tabs
            self.create_profiles_tab()
            self.create_requests_tab()
            self.create_exam_accommodations_tab()
            self.create_assistive_tech_tab()
            self.create_settings_tab()

            # Log activity
            username = self.current_user.get('username') or self.current_user.get('id')
            log_activity("Opened Accessibility Tools GUI", user=username)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("accessibility.error.create_window", error=str(e)))
            traceback.print_exc()

    def create_profiles_tab(self):
        """Create accessibility profiles tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("accessibility.tabs.profiles"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("accessibility.header.profiles"),
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        if self.current_user.get('role') in ['admin', 'staff']:
            ttk.Button(header_frame, text=_t("accessibility.btn.create_profile"),
                      command=self.create_profile).pack(side=tk.RIGHT, padx=5)
            ttk.Button(header_frame, text=_t("accessibility.btn.refresh"),
                      command=self.load_profiles).pack(side=tk.RIGHT, padx=5)

        # Profiles list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        self.profiles_tree = ttk.Treeview(tree_frame,
                                         columns=('ID', 'User ID', 'Disabilities',
                                                 'Accommodations', 'Assistive Tech', 'Updated'),
                                         show='tree headings',
                                         yscrollcommand=v_scroll.set)

        v_scroll.config(command=self.profiles_tree.yview)

        self.profiles_tree.heading('#0', text='')
        self.profiles_tree.column('#0', width=30)

        columns_config = [
            ('ID', 60, _t("accessibility.columns.id")),
            ('User ID', 100, _t("accessibility.columns.user_id")),
            ('Disabilities', 250, _t("accessibility.columns.disabilities")),
            ('Accommodations', 250, _t("accessibility.columns.accommodations")),
            ('Assistive Tech', 200, _t("accessibility.columns.assistive_tech")),
            ('Updated', 150, _t("accessibility.columns.updated"))
        ]

        for col, width, header in columns_config:
            self.profiles_tree.heading(col, text=header)
            self.profiles_tree.column(col, width=width)

        self.profiles_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.profiles_tree.bind('<Double-1>', self.view_profile)

        self.load_profiles()

    def create_requests_tab(self):
        """Create accommodation requests tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("accessibility.tabs.requests"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("accessibility.header.requests"),
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        # Filter by status
        ttk.Label(header_frame, text=_t("accessibility.filter.status")).pack(side=tk.LEFT, padx=(20, 5))
        self.request_status_filter = ttk.Combobox(header_frame,
                                                  values=[_t("accessibility.filter.all"),
                                                         _t("accessibility.status_values.pending"),
                                                         _t("accessibility.status_values.approved"),
                                                         _t("accessibility.status_values.denied")],
                                                  width=15, state='readonly')
        self.request_status_filter.pack(side=tk.LEFT, padx=5)
        self.request_status_filter.current(0)
        self.request_status_filter.bind('<<ComboboxSelected>>', lambda e: self.load_requests())

        ttk.Button(header_frame, text=_t("accessibility.btn.submit_request"),
                  command=self.submit_request).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text=_t("accessibility.btn.refresh"),
                  command=self.load_requests).pack(side=tk.RIGHT, padx=5)

        # Requests list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        self.requests_tree = ttk.Treeview(tree_frame,
                                         columns=('ID', 'Student ID', 'Type', 'Description',
                                                 'Status', 'Requested', 'Reviewed By'),
                                         show='tree headings',
                                         yscrollcommand=v_scroll.set)

        v_scroll.config(command=self.requests_tree.yview)

        self.requests_tree.heading('#0', text='')
        self.requests_tree.column('#0', width=30)

        columns_config = [
            ('ID', 60, _t("accessibility.columns.id")),
            ('Student ID', 100, _t("accessibility.columns.student_id")),
            ('Type', 200, _t("accessibility.columns.type")),
            ('Description', 300, _t("accessibility.columns.description")),
            ('Status', 100, _t("accessibility.columns.status")),
            ('Requested', 150, _t("accessibility.columns.requested")),
            ('Reviewed By', 100, _t("accessibility.columns.reviewed_by"))
        ]

        for col, width, header in columns_config:
            self.requests_tree.heading(col, text=header)
            self.requests_tree.column(col, width=width)

        self.requests_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.requests_tree.bind('<Double-1>', self.review_request)

        # Color code by status
        self.requests_tree.tag_configure('pending', background='#ffffcc')
        self.requests_tree.tag_configure('approved', background='#ccffcc')
        self.requests_tree.tag_configure('denied', background='#ffcccc')

        self.load_requests()

    def create_exam_accommodations_tab(self):
        """Create exam accommodations tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("accessibility.tabs.exam_accommodations"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("accessibility.header.exam_accommodations"),
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(header_frame, text=_t("accessibility.btn.add_accommodation"),
                  command=self.add_exam_accommodation).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text=_t("accessibility.btn.refresh"),
                  command=self.load_exam_accommodations).pack(side=tk.RIGHT, padx=5)

        # Accommodations list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        self.exam_tree = ttk.Treeview(tree_frame,
                                     columns=('ID', 'Student ID', 'Exam ID', 'Extended Time',
                                             'Separate Room', 'Assistive Tech', 'Reader/Scribe', 'Status'),
                                     show='tree headings',
                                     yscrollcommand=v_scroll.set)

        v_scroll.config(command=self.exam_tree.yview)

        self.exam_tree.heading('#0', text='')
        self.exam_tree.column('#0', width=30)

        columns_config = [
            ('ID', 60, _t("accessibility.columns.id")),
            ('Student ID', 100, _t("accessibility.columns.student_id")),
            ('Exam ID', 100, _t("accessibility.columns.exam_id")),
            ('Extended Time', 130, _t("accessibility.columns.extended_time")),
            ('Separate Room', 120, _t("accessibility.columns.separate_room")),
            ('Assistive Tech', 200, _t("accessibility.columns.assistive_tech")),
            ('Reader/Scribe', 120, _t("accessibility.columns.reader_scribe")),
            ('Status', 80, _t("accessibility.columns.status"))
        ]

        for col, width, header in columns_config:
            self.exam_tree.heading(col, text=header)
            self.exam_tree.column(col, width=width)

        self.exam_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.exam_tree.bind('<Double-1>', self.view_exam_accommodation)

        self.load_exam_accommodations()

    def create_assistive_tech_tab(self):
        """Create assistive technology requests tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("accessibility.tabs.assistive_tech"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("accessibility.header.assistive_tech"),
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(header_frame, text=_t("accessibility.btn.request_tech"),
                  command=self.request_assistive_tech).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text=_t("accessibility.btn.refresh"),
                  command=self.load_assistive_tech_requests).pack(side=tk.RIGHT, padx=5)

        # Requests list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        self.tech_tree = ttk.Treeview(tree_frame,
                                     columns=('ID', 'Student ID', 'Technology Type',
                                             'Status', 'Requested', 'Fulfilled'),
                                     show='tree headings',
                                     yscrollcommand=v_scroll.set)

        v_scroll.config(command=self.tech_tree.yview)

        self.tech_tree.heading('#0', text='')
        self.tech_tree.column('#0', width=30)

        columns_config = [
            ('ID', 60, _t("accessibility.columns.id")),
            ('Student ID', 150, _t("accessibility.columns.student_id")),
            ('Technology Type', 300, _t("accessibility.columns.technology_type")),
            ('Status', 120, _t("accessibility.columns.status")),
            ('Requested', 200, _t("accessibility.columns.requested")),
            ('Fulfilled', 200, _t("accessibility.columns.fulfilled"))
        ]

        for col, width, header in columns_config:
            self.tech_tree.heading(col, text=header)
            self.tech_tree.column(col, width=width)

        self.tech_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tech_tree.bind('<Double-1>', self.manage_tech_request)

        self.load_assistive_tech_requests()

    def create_settings_tab(self):
        """Create accessibility settings tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("accessibility.tabs.settings"))

        ttk.Label(tab, text=_t("accessibility.header.settings"),
                 style='Header.TLabel').pack(pady=20)

        # Settings form
        form_frame = ttk.LabelFrame(tab, text=_t("accessibility.settings.preferences"), padding="20")
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Theme
        row1 = ttk.Frame(form_frame)
        row1.pack(fill=tk.X, pady=10)
        ttk.Label(row1, text=_t("accessibility.settings.theme"), width=20).pack(side=tk.LEFT)
        self.theme_var = tk.StringVar(value=_t("accessibility.themes.standard"))
        themes = ttk.Combobox(row1, textvariable=self.theme_var,
                             values=[_t("accessibility.themes.standard"), _t("accessibility.themes.high_contrast"), _t("accessibility.themes.dark")], state='readonly')
        themes.pack(side=tk.LEFT, padx=10)

        # Font size
        row2 = ttk.Frame(form_frame)
        row2.pack(fill=tk.X, pady=10)
        ttk.Label(row2, text=_t("accessibility.settings.font_size"), width=20).pack(side=tk.LEFT)
        self.font_size_var = tk.IntVar(value=16)
        ttk.Spinbox(row2, from_=12, to=32, textvariable=self.font_size_var, width=10).pack(side=tk.LEFT, padx=10)

        # Screen reader
        row3 = ttk.Frame(form_frame)
        row3.pack(fill=tk.X, pady=10)
        self.screen_reader_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row3, text=_t("accessibility.settings.screen_reader"),
                       variable=self.screen_reader_var).pack(anchor=tk.W)

        # Keyboard navigation
        row4 = ttk.Frame(form_frame)
        row4.pack(fill=tk.X, pady=10)
        self.keyboard_nav_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row4, text=_t("accessibility.settings.keyboard_nav"),
                       variable=self.keyboard_nav_var).pack(anchor=tk.W)

        # Save button
        ttk.Button(form_frame, text=_t("accessibility.btn.save_settings"),
                  command=self.save_accessibility_settings).pack(pady=20)

        self.load_accessibility_settings()

    # Data loading methods
    def load_profiles(self):
        """Load accessibility profiles"""
        try:
            self.profiles_tree.delete(*self.profiles_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()

                if self.current_user.get('role') in ['admin', 'staff']:
                    # Show all profiles
                    cursor.execute('''
                        SELECT * FROM accessibility_profiles
                        ORDER BY updated_at DESC
                    ''')
                else:
                    # Show only user's profile
                    user_id = self.current_user.get('user_id') or self.current_user.get('id')
                    cursor.execute('''
                        SELECT * FROM accessibility_profiles
                        WHERE user_id = ?
                    ''', (user_id,))

                for row in cursor.fetchall():
                    disabilities = json.loads(row['disabilities'] or '[]')
                    accommodations = json.loads(row['accommodations'] or '[]')
                    assistive_tech = json.loads(row['assistive_technologies'] or '[]')

                    values = (
                        row['profile_id'],
                        row['user_id'],
                        ', '.join(disabilities) if disabilities else _t("common.none"),
                        ', '.join(accommodations) if accommodations else _t("common.none"),
                        ', '.join(assistive_tech) if assistive_tech else _t("common.none"),
                        row['updated_at']
                    )
                    self.profiles_tree.insert('', 'end', values=values)

            self.update_status(_t("accessibility.status.loaded_profiles", count=len(self.profiles_tree.get_children())))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("accessibility.error.load_profiles", error=str(e)))
            traceback.print_exc()

    def load_requests(self):
        """Load accommodation requests"""
        try:
            # Build reverse mapping for status values
            self.status_display_to_db = {func(): key for key, func in self.status_db_to_display.items()}

            self.requests_tree.delete(*self.requests_tree.get_children())

            status_filter = self.request_status_filter.get()

            with get_connection() as conn:
                cursor = conn.cursor()

                if status_filter == _t("accessibility.filter.all"):
                    cursor.execute('''
                        SELECT * FROM accommodation_requests
                        ORDER BY requested_date DESC
                        LIMIT 500
                    ''')
                else:
                    # Convert display value to database value
                    db_status = self.status_display_to_db.get(status_filter, status_filter)
                    cursor.execute('''
                        SELECT * FROM accommodation_requests
                        WHERE status = ?
                        ORDER BY requested_date DESC
                        LIMIT 500
                    ''', (db_status,))

                for row in cursor.fetchall():
                    values = (
                        row['request_id'],
                        row['student_id'],
                        row['accommodation_type'],
                        (row['description'][:50] + '...') if len(row['description'] or '') > 50 else (row['description'] or ''),
                        row['status'],
                        row['requested_date'],
                        row['reviewed_by'] or _t("accessibility.defaults.pending")
                    )
                    item = self.requests_tree.insert('', 'end', values=values, tags=(row['status'],))

            self.update_status(_t("accessibility.status.loaded_requests", count=len(self.requests_tree.get_children())))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("accessibility.error.load_requests", error=str(e)))
            traceback.print_exc()

    def load_exam_accommodations(self):
        """Load exam accommodations"""
        try:
            self.exam_tree.delete(*self.exam_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM exam_accommodations
                    WHERE status = 'active'
                    ORDER BY accommodation_id DESC
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['accommodation_id'],
                        row['student_id'],
                        row['exam_id'] or _t("accessibility.defaults.all_exams"),
                        _t("accessibility.defaults.mins", mins=row['extended_time']) if row['extended_time'] else _t("common.no"),
                        _t("common.yes") if row['separate_room'] else _t("common.no"),
                        row['assistive_technology'] or _t("common.none"),
                        _t("common.yes") if row['reader_scribe'] else _t("common.no"),
                        row['status']
                    )
                    self.exam_tree.insert('', 'end', values=values)

            self.update_status(_t("accessibility.status.loaded_exam_accommodations", count=len(self.exam_tree.get_children())))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("accessibility.error.load_exam_accommodations", error=str(e)))
            traceback.print_exc()

    def load_assistive_tech_requests(self):
        """Load assistive technology requests"""
        try:
            self.tech_tree.delete(*self.tech_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM assistive_tech_requests
                    ORDER BY requested_date DESC
                    LIMIT 500
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['request_id'],
                        row['student_id'],
                        row['technology_type'],
                        row['status'],
                        row['requested_date'],
                        row['fulfilled_date'] or _t("accessibility.defaults.pending")
                    )
                    self.tech_tree.insert('', 'end', values=values)

            self.update_status(_t("accessibility.status.loaded_tech_requests", count=len(self.tech_tree.get_children())))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("accessibility.error.load_tech_requests", error=str(e)))
            traceback.print_exc()

    def load_accessibility_settings(self):
        """Load user's accessibility settings"""
        try:
            # Build reverse mapping for themes
            self.theme_display_to_db = {func(): key for key, func in self.theme_db_to_display.items()}

            user_id = self.current_user.get('user_id') or self.current_user.get('id')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM accessibility_settings
                    WHERE user_id = ?
                ''', (user_id,))
                row = cursor.fetchone()

                if row:
                    # Convert database theme value to display value
                    db_theme = row['theme']
                    display_theme = self.theme_db_to_display.get(db_theme, lambda: db_theme)()
                    self.theme_var.set(display_theme)
                    self.font_size_var.set(row['font_size'])
                    self.screen_reader_var.set(bool(row['screen_reader_enabled']))
                    self.keyboard_nav_var.set(bool(row['keyboard_navigation']))

        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_accessibility_settings(self):
        """Save user's accessibility settings"""
        try:
            # Build reverse mapping for themes if not already built
            if not self.theme_display_to_db:
                self.theme_display_to_db = {func(): key for key, func in self.theme_db_to_display.items()}

            user_id = self.current_user.get('user_id') or self.current_user.get('id')

            # Convert display theme to database theme
            display_theme = self.theme_var.get()
            db_theme = self.theme_display_to_db.get(display_theme, display_theme)

            with transaction() as conn:
                cursor = conn.cursor()

                # Check if settings exist
                cursor.execute('SELECT setting_id FROM accessibility_settings WHERE user_id = ?',
                             (user_id,))
                existing = cursor.fetchone()

                if existing:
                    cursor.execute('''
                        UPDATE accessibility_settings
                        SET theme = ?, font_size = ?, screen_reader_enabled = ?,
                            keyboard_navigation = ?
                        WHERE user_id = ?
                    ''', (db_theme, self.font_size_var.get(),
                         self.screen_reader_var.get(), self.keyboard_nav_var.get(),
                         user_id))
                else:
                    cursor.execute('''
                        INSERT INTO accessibility_settings
                        (user_id, theme, font_size, screen_reader_enabled, keyboard_navigation)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (user_id, db_theme,
                         self.font_size_var.get(), self.screen_reader_var.get(),
                         self.keyboard_nav_var.get()))

            messagebox.showinfo(_t("common.success"), _t("accessibility.messages.settings_saved"))
            username = self.current_user.get('username') or str(user_id)
            log_activity("Updated accessibility settings", user=username)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("accessibility.error.save_settings", error=str(e)))

    # Lookup helper methods
    def lookup_student(self, entry_widget):
        """Open student lookup dialog and populate entry widget"""
        lookup_dialog = tk.Toplevel(self.window)
        lookup_dialog.title("Student Lookup")
        lookup_dialog.geometry("700x500")
        lookup_dialog.transient(self.window)
        lookup_dialog.grab_set()

        main_frame = ttk.Frame(lookup_dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student Lookup", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Search frame
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=5)

        # Student list
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        v_scroll = ttk.Scrollbar(tree_frame)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        student_tree = ttk.Treeview(tree_frame, columns=('Student ID', 'Name', 'Email', 'Course'),
                                    show='headings', yscrollcommand=v_scroll.set)
        v_scroll.config(command=student_tree.yview)

        student_tree.heading('Student ID', text='Student ID')
        student_tree.heading('Name', text='Name')
        student_tree.heading('Email', text='Email')
        student_tree.heading('Course', text='Course')

        student_tree.column('Student ID', width=120)
        student_tree.column('Name', width=200)
        student_tree.column('Email', width=250)
        student_tree.column('Course', width=150)

        student_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def load_students(search_term=''):
            """Load students from database"""
            student_tree.delete(*student_tree.get_children())

            try:
                with get_connection() as conn:
                    cursor = conn.cursor()

                    if search_term:
                        cursor.execute('''
                            SELECT student_id, first_name, last_name, email_address, course
                            FROM students
                            WHERE student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR email_address LIKE ?
                            ORDER BY student_id
                            LIMIT 100
                        ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                    else:
                        cursor.execute('''
                            SELECT student_id, first_name, last_name, email_address, course
                            FROM students
                            ORDER BY student_id
                            LIMIT 100
                        ''')

                    for row in cursor.fetchall():
                        student_tree.insert('', 'end', values=(
                            row['student_id'],
                            f"{row['first_name']} {row['last_name']}",
                            row['email_address'] or '',
                            row['course'] or ''
                        ))

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load students: {e}")

        def search_students(*args):
            load_students(search_var.get().strip())

        search_var.trace('w', search_students)
        load_students()

        def select_student():
            """Select student and populate entry"""
            selection = student_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a student")
                return

            item = student_tree.item(selection[0])
            values = item['values']
            student_id = values[0]  # Student ID column (now first column)

            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, student_id)
            lookup_dialog.destroy()

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Select", command=select_student).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=lookup_dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Double-click to select
        student_tree.bind('<Double-1>', lambda e: select_student())

    def lookup_user(self, entry_widget):
        """Open user lookup dialog and populate entry widget"""
        lookup_dialog = tk.Toplevel(self.window)
        lookup_dialog.title("User Lookup")
        lookup_dialog.geometry("700x500")
        lookup_dialog.transient(self.window)
        lookup_dialog.grab_set()

        main_frame = ttk.Frame(lookup_dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="User Lookup", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Search frame
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=5)

        # User list
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        v_scroll = ttk.Scrollbar(tree_frame)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        user_tree = ttk.Treeview(tree_frame, columns=('ID', 'Username', 'Name', 'Email', 'Role'),
                                show='headings', yscrollcommand=v_scroll.set)
        v_scroll.config(command=user_tree.yview)

        user_tree.heading('ID', text='ID')
        user_tree.heading('Username', text='Username')
        user_tree.heading('Name', text='Name')
        user_tree.heading('Email', text='Email')
        user_tree.heading('Role', text='Role')

        user_tree.column('ID', width=50)
        user_tree.column('Username', width=120)
        user_tree.column('Name', width=180)
        user_tree.column('Email', width=200)
        user_tree.column('Role', width=100)

        user_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def load_users(search_term=''):
            """Load users from database"""
            user_tree.delete(*user_tree.get_children())

            try:
                with get_connection() as conn:
                    cursor = conn.cursor()

                    if search_term:
                        cursor.execute('''
                            SELECT id, username, first_name, last_name, email, role
                            FROM users
                            WHERE username LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR email LIKE ?
                            ORDER BY username
                            LIMIT 100
                        ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                    else:
                        cursor.execute('''
                            SELECT id, username, first_name, last_name, email, role
                            FROM users
                            ORDER BY username
                            LIMIT 100
                        ''')

                    for row in cursor.fetchall():
                        user_tree.insert('', 'end', values=(
                            row['id'],
                            row['username'],
                            f"{row['first_name']} {row['last_name']}",
                            row['email'],
                            row['role']
                        ))

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load users: {e}")

        def search_users(*args):
            load_users(search_var.get().strip())

        search_var.trace('w', search_users)
        load_users()

        def select_user():
            """Select user and populate entry"""
            selection = user_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a user")
                return

            item = user_tree.item(selection[0])
            values = item['values']
            user_id = values[0]  # User ID column

            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, user_id)
            lookup_dialog.destroy()

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Select", command=select_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=lookup_dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Double-click to select
        user_tree.bind('<Double-1>', lambda e: select_user())

    def lookup_exam(self, student_id_var, exam_entry_widget):
        """Open exam lookup dialog filtered by student and populate entry widget"""
        student_id = student_id_var.get().strip()
        if not student_id:
            messagebox.showwarning("Student ID Required", "Please enter a student ID first")
            return

        lookup_dialog = tk.Toplevel(self.window)
        lookup_dialog.title("Exam Lookup")
        lookup_dialog.geometry("900x600")
        lookup_dialog.transient(self.window)
        lookup_dialog.grab_set()

        main_frame = ttk.Frame(lookup_dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Exams for Student: {student_id}",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Info label
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(info_frame, text="Double-click an exam to select it, or click 'Open Exam Scheduler' to view all exams",
                 foreground='blue').pack()

        # Exam list
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        v_scroll = ttk.Scrollbar(tree_frame)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        exam_tree = ttk.Treeview(tree_frame,
                                columns=('Exam ID', 'Module', 'Date', 'Time', 'Room', 'Duration'),
                                show='headings', yscrollcommand=v_scroll.set)
        v_scroll.config(command=exam_tree.yview)

        exam_tree.heading('Exam ID', text='Exam ID')
        exam_tree.heading('Module', text='Module')
        exam_tree.heading('Date', text='Date')
        exam_tree.heading('Time', text='Time')
        exam_tree.heading('Room', text='Room')
        exam_tree.heading('Duration', text='Duration (mins)')

        exam_tree.column('Exam ID', width=80)
        exam_tree.column('Module', width=200)
        exam_tree.column('Date', width=120)
        exam_tree.column('Time', width=100)
        exam_tree.column('Room', width=100)
        exam_tree.column('Duration', width=100)

        exam_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def load_exams():
            """Load exams for the student"""
            exam_tree.delete(*exam_tree.get_children())

            try:
                with get_connection() as conn:
                    cursor = conn.cursor()

                    # Get exams from the exams table where student is enrolled
                    cursor.execute('''
                        SELECT id, module_code, module_name, date, start_time, end_time, room
                        FROM exams
                        WHERE enrolled_student_ids LIKE ?
                        ORDER BY date, start_time
                        LIMIT 100
                    ''', (f'%"{student_id}"%',))

                    rows = cursor.fetchall()

                    if not rows:
                        # If no exams found, show message
                        messagebox.showinfo("No Exams",
                                          f"No scheduled exams found for student {student_id}.\n" +
                                          "Click 'Open Exam Scheduler' to view all exams.")
                        return

                    for row in rows:
                        # Calculate duration from start and end time
                        try:
                            from datetime import datetime
                            start = datetime.strptime(row['start_time'], '%H:%M')
                            end = datetime.strptime(row['end_time'], '%H:%M')
                            duration = int((end - start).total_seconds() / 60)
                        except (ValueError, TypeError):
                            duration = 'N/A'

                        exam_tree.insert('', 'end', values=(
                            row['id'],
                            f"{row['module_code']} - {row['module_name']}",
                            row['date'],
                            row['start_time'],
                            row['room'] or 'TBD',
                            duration
                        ))

            except Exception as e:
                # Table might not exist, show info message
                messagebox.showinfo("Exam Data",
                                  f"Failed to load exam data: {e}\n" +
                                  "Click 'Open Exam Scheduler' to manage exams.")

        load_exams()

        def select_exam():
            """Select exam and populate entry"""
            selection = exam_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select an exam")
                return

            item = exam_tree.item(selection[0])
            values = item['values']
            exam_id = values[0]  # Exam ID column

            exam_entry_widget.delete(0, tk.END)
            exam_entry_widget.insert(0, exam_id)
            lookup_dialog.destroy()

        def open_exam_scheduler():
            """Open exam scheduler GUI"""
            try:
                from education_system.systems.university.interfaces.gui.academics.exam_management import ExamSchedulerApp
                scheduler_window = tk.Toplevel(self.window)
                scheduler_window.title("Exam Scheduler")
                scheduler_window.geometry("1200x800")
                ExamSchedulerApp(scheduler_window, self.auth)
            except ImportError as e:
                messagebox.showerror("Import Error",
                                   f"Exam Scheduler GUI not available: {e}")
            except Exception as e:
                messagebox.showerror("Error",
                                   f"Failed to open Exam Scheduler: {e}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Select Exam", command=select_exam).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Open Exam Scheduler", command=open_exam_scheduler).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=lookup_dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Double-click to select
        exam_tree.bind('<Double-1>', lambda e: select_exam())

    # Action methods - Full implementations
    def create_profile(self):
        """Create accessibility profile dialog"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("accessibility.dialogs.create_profile"))
        dialog.geometry("500x600")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("accessibility.dialogs.create_profile"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # User ID
        row1 = ttk.Frame(main_frame)
        row1.pack(fill=tk.X, pady=5)
        ttk.Label(row1, text=_t("accessibility.labels.user_id"), width=20).pack(side=tk.LEFT)
        user_id_var = tk.StringVar()
        user_id_entry = ttk.Entry(row1, textvariable=user_id_var, width=20)
        user_id_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row1, text="🔍 Lookup", command=lambda: self.lookup_user(user_id_entry), width=10).pack(side=tk.LEFT)

        # Disabilities
        ttk.Label(main_frame, text=_t("accessibility.labels.disabilities_one_per_line")).pack(anchor=tk.W, pady=(10, 5))
        disabilities_text = scrolledtext.ScrolledText(main_frame, height=4, width=50)
        disabilities_text.pack(fill=tk.X, pady=5)

        # Accommodations needed
        ttk.Label(main_frame, text=_t("accessibility.labels.accommodations_one_per_line")).pack(anchor=tk.W, pady=(10, 5))
        accommodations_text = scrolledtext.ScrolledText(main_frame, height=4, width=50)
        accommodations_text.pack(fill=tk.X, pady=5)

        # Assistive technologies
        ttk.Label(main_frame, text=_t("accessibility.labels.assistive_tech_one_per_line")).pack(anchor=tk.W, pady=(10, 5))
        tech_text = scrolledtext.ScrolledText(main_frame, height=4, width=50)
        tech_text.pack(fill=tk.X, pady=5)

        def save_profile():
            user_id = user_id_var.get().strip()
            if not user_id:
                messagebox.showerror(_t("common.error"), _t("accessibility.error.user_id_required"))
                return

            disabilities = [d.strip() for d in disabilities_text.get('1.0', tk.END).strip().split('\n') if d.strip()]
            accommodations = [a.strip() for a in accommodations_text.get('1.0', tk.END).strip().split('\n') if a.strip()]
            technologies = [t.strip() for t in tech_text.get('1.0', tk.END).strip().split('\n') if t.strip()]

            try:
                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO accessibility_profiles
                        (user_id, disabilities, accommodations, assistive_technologies, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, json.dumps(disabilities), json.dumps(accommodations),
                         json.dumps(technologies), datetime.now().isoformat(), datetime.now().isoformat()))

                messagebox.showinfo(_t("common.success"), _t("accessibility.messages.profile_created"))
                log_activity(f"Created accessibility profile for user {user_id}",
                           user=self.current_user.get('username'))
                dialog.destroy()
                self.load_profiles()

            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("accessibility.error.create_profile", error=str(e)))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t("accessibility.btn.save_profile"), command=save_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def view_profile(self, event=None):
        """View profile details dialog"""
        selection = self.profiles_tree.selection()
        if not selection:
            return

        item = self.profiles_tree.item(selection[0])
        values = item['values']
        profile_id = values[0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM accessibility_profiles WHERE profile_id = ?', (profile_id,))
                row = cursor.fetchone()

                if not row:
                    messagebox.showerror(_t("common.error"), _t("accessibility.error.profile_not_found"))
                    return

            dialog = tk.Toplevel(self.window)
            dialog.title(_t("accessibility.dialogs.view_profile"))
            dialog.geometry("500x500")
            dialog.transient(self.window)

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=_t("accessibility.dialogs.profile_details"),
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            info_frame = ttk.LabelFrame(main_frame, text=_t("accessibility.labels.profile_info"), padding="10")
            info_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(info_frame, text=_t("accessibility.labels.profile_id_value", id=row['profile_id'])).pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=_t("accessibility.labels.user_id_value", id=row['user_id'])).pack(anchor=tk.W, pady=2)

            disabilities = json.loads(row['disabilities'] or '[]')
            ttk.Label(info_frame, text=_t("accessibility.labels.disabilities_label"), font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10, 2))
            for d in disabilities:
                ttk.Label(info_frame, text=f"  • {d}").pack(anchor=tk.W)

            accommodations = json.loads(row['accommodations'] or '[]')
            ttk.Label(info_frame, text=_t("accessibility.labels.accommodations_label"), font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10, 2))
            for a in accommodations:
                ttk.Label(info_frame, text=f"  • {a}").pack(anchor=tk.W)

            technologies = json.loads(row['assistive_technologies'] or '[]')
            ttk.Label(info_frame, text=_t("accessibility.labels.assistive_tech_label"), font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10, 2))
            for t in technologies:
                ttk.Label(info_frame, text=f"  • {t}").pack(anchor=tk.W)

            ttk.Label(info_frame, text=_t("accessibility.labels.last_updated", date=row['updated_at'])).pack(anchor=tk.W, pady=(10, 2))

            ttk.Button(main_frame, text=_t("common.close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("accessibility.error.load_profile", error=str(e)))

    def submit_request(self):
        """Submit accommodation request dialog"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("accessibility.dialogs.submit_request"))
        dialog.geometry("500x450")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("accessibility.dialogs.submit_request"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Student ID (auto-fill for students)
        row1 = ttk.Frame(main_frame)
        row1.pack(fill=tk.X, pady=5)
        ttk.Label(row1, text=_t("accessibility.labels.student_id"), width=20).pack(side=tk.LEFT)
        student_id_var = tk.StringVar(value=self.current_user.get('student_id') or self.current_user.get('username', ''))
        student_entry = ttk.Entry(row1, textvariable=student_id_var, width=30)
        student_entry.pack(side=tk.LEFT)
        if self.current_user.get('role') == 'student':
            student_entry.config(state='readonly')

        # Accommodation Type
        row2 = ttk.Frame(main_frame)
        row2.pack(fill=tk.X, pady=5)
        ttk.Label(row2, text=_t("accessibility.labels.accommodation_type"), width=20).pack(side=tk.LEFT)
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(row2, textvariable=type_var, width=27, values=[
            _t("accessibility.acc_types.extended_test_time"), _t("accessibility.acc_types.separate_room"),
            _t("accessibility.acc_types.note_taking"), _t("accessibility.acc_types.sign_language"),
            _t("accessibility.acc_types.captioning"), _t("accessibility.acc_types.audio_books"),
            _t("accessibility.acc_types.screen_reader"), _t("accessibility.acc_types.large_print"),
            _t("accessibility.acc_types.mobility"), _t("accessibility.acc_types.flexible_attendance"),
            _t("accessibility.acc_types.recording_lectures"), _t("accessibility.acc_types.priority_seating"),
            _t("accessibility.acc_types.other")
        ])
        type_combo.pack(side=tk.LEFT)

        # Description
        ttk.Label(main_frame, text=_t("accessibility.labels.description_justification")).pack(anchor=tk.W, pady=(15, 5))
        desc_text = scrolledtext.ScrolledText(main_frame, height=8, width=50)
        desc_text.pack(fill=tk.X, pady=5)

        def submit():
            student_id = student_id_var.get().strip()
            acc_type = type_var.get().strip()
            description = desc_text.get('1.0', tk.END).strip()

            if not student_id or not acc_type:
                messagebox.showerror(_t("common.error"), _t("accessibility.error.required_fields"))
                return

            try:
                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO accommodation_requests
                        (student_id, accommodation_type, description, status, requested_date)
                        VALUES (?, ?, ?, 'pending', ?)
                    ''', (student_id, acc_type, description, datetime.now().isoformat()))

                messagebox.showinfo(_t("common.success"), _t("accessibility.messages.request_submitted"))
                log_activity(f"Submitted accommodation request: {acc_type}",
                           user=self.current_user.get('username'))
                dialog.destroy()
                self.load_requests()

            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("accessibility.error.submit_request", error=str(e)))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t("accessibility.btn.submit_request"), command=submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def review_request(self, event=None):
        """Review accommodation request dialog"""
        selection = self.requests_tree.selection()
        if not selection:
            return

        item = self.requests_tree.item(selection[0])
        values = item['values']
        request_id = values[0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM accommodation_requests WHERE request_id = ?', (request_id,))
                row = cursor.fetchone()

                if not row:
                    messagebox.showerror(_t("common.error"), _t("accessibility.error.request_not_found"))
                    return

            dialog = tk.Toplevel(self.window)
            dialog.title(_t("accessibility.dialogs.review_request"))
            dialog.geometry("550x550")
            dialog.transient(self.window)

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=_t("accessibility.titles.request_details"),
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            info_frame = ttk.LabelFrame(main_frame, text=_t("accessibility.sections.request_info"), padding="10")
            info_frame.pack(fill=tk.X, pady=5)

            ttk.Label(info_frame, text=f"{_t('accessibility.labels.request_id')}: {row['request_id']}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.student_id')}: {row['student_id']}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.type')}: {row['accommodation_type']}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.status')}: {row['status']}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.requested')}: {row['requested_date']}").pack(anchor=tk.W, pady=2)

            ttk.Label(main_frame, text=_t("accessibility.labels.description") + ":").pack(anchor=tk.W, pady=(10, 5))
            desc_text = scrolledtext.ScrolledText(main_frame, height=5, width=50)
            desc_text.insert('1.0', row['description'] or '')
            desc_text.config(state='disabled')
            desc_text.pack(fill=tk.X, pady=5)

            # Review section for admin/staff
            if self.current_user.get('role') in ['admin', 'staff']:
                review_frame = ttk.LabelFrame(main_frame, text=_t("accessibility.sections.review_decision"), padding="10")
                review_frame.pack(fill=tk.X, pady=10)

                ttk.Label(review_frame, text=_t("accessibility.labels.review_notes") + ":").pack(anchor=tk.W, pady=2)
                notes_text = scrolledtext.ScrolledText(review_frame, height=3, width=50)
                notes_text.insert('1.0', row['review_notes'] or '')
                notes_text.pack(fill=tk.X, pady=5)

                def approve():
                    try:
                        with transaction() as conn:
                            conn.execute('''
                                UPDATE accommodation_requests
                                SET status = 'approved', reviewed_by = ?, review_date = ?, review_notes = ?
                                WHERE request_id = ?
                            ''', (self.current_user.get('username'), datetime.now().isoformat(),
                                 notes_text.get('1.0', tk.END).strip(), request_id))
                        messagebox.showinfo(_t("common.success"), _t("accessibility.messages.request_approved"))
                        log_activity(f"Approved accommodation request {request_id}",
                                   user=self.current_user.get('username'))
                        dialog.destroy()
                        self.load_requests()
                    except Exception as e:
                        messagebox.showerror(_t("common.error"), _t("accessibility.error.approve_failed", error=str(e)))

                def deny():
                    try:
                        with transaction() as conn:
                            conn.execute('''
                                UPDATE accommodation_requests
                                SET status = 'denied', reviewed_by = ?, review_date = ?, review_notes = ?
                                WHERE request_id = ?
                            ''', (self.current_user.get('username'), datetime.now().isoformat(),
                                 notes_text.get('1.0', tk.END).strip(), request_id))
                        messagebox.showinfo(_t("common.success"), _t("accessibility.messages.request_denied"))
                        log_activity(f"Denied accommodation request {request_id}",
                                   user=self.current_user.get('username'))
                        dialog.destroy()
                        self.load_requests()
                    except Exception as e:
                        messagebox.showerror(_t("common.error"), _t("accessibility.error.deny_failed", error=str(e)))

                btn_frame = ttk.Frame(review_frame)
                btn_frame.pack(pady=10)
                ttk.Button(btn_frame, text=_t("accessibility.btn.approve"), command=approve).pack(side=tk.LEFT, padx=5)
                ttk.Button(btn_frame, text=_t("accessibility.btn.deny"), command=deny).pack(side=tk.LEFT, padx=5)

            ttk.Button(main_frame, text=_t("common.close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("accessibility.error.load_request", error=str(e)))

    def add_exam_accommodation(self):
        """Add exam accommodation dialog"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("accessibility.dialogs.add_exam_accommodation"))
        dialog.geometry("500x500")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("accessibility.titles.add_exam_accommodation"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Student ID
        row1 = ttk.Frame(main_frame)
        row1.pack(fill=tk.X, pady=5)
        ttk.Label(row1, text=_t("accessibility.labels.student_id") + ":", width=20).pack(side=tk.LEFT)
        student_id_var = tk.StringVar()
        student_id_entry = ttk.Entry(row1, textvariable=student_id_var, width=20)
        student_id_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row1, text="🔍 Lookup", command=lambda: self.lookup_student(student_id_entry), width=10).pack(side=tk.LEFT)

        # Exam ID (optional)
        row2 = ttk.Frame(main_frame)
        row2.pack(fill=tk.X, pady=5)
        ttk.Label(row2, text=_t("accessibility.labels.exam_id_optional") + ":", width=20).pack(side=tk.LEFT)
        exam_id_var = tk.StringVar()
        exam_id_entry = ttk.Entry(row2, textvariable=exam_id_var, width=20)
        exam_id_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row2, text="🔍 Lookup", command=lambda: self.lookup_exam(student_id_var, exam_id_entry), width=10).pack(side=tk.LEFT)

        # Extended Time
        row3 = ttk.Frame(main_frame)
        row3.pack(fill=tk.X, pady=5)
        ttk.Label(row3, text=_t("accessibility.labels.extended_time_mins") + ":", width=20).pack(side=tk.LEFT)
        extended_time_var = tk.IntVar(value=0)
        ttk.Spinbox(row3, from_=0, to=120, textvariable=extended_time_var, width=10).pack(side=tk.LEFT)

        # Separate Room
        separate_room_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text=_t("accessibility.labels.separate_room_required"),
                       variable=separate_room_var).pack(anchor=tk.W, pady=5)

        # Reader/Scribe
        reader_scribe_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text=_t("accessibility.labels.reader_scribe_required"),
                       variable=reader_scribe_var).pack(anchor=tk.W, pady=5)

        # Assistive Technology
        row4 = ttk.Frame(main_frame)
        row4.pack(fill=tk.X, pady=5)
        ttk.Label(row4, text=_t("accessibility.labels.assistive_technology") + ":", width=20).pack(side=tk.LEFT)
        tech_var = tk.StringVar()
        ttk.Combobox(row4, textvariable=tech_var, width=27, values=[
            _t("common.none"), _t("accessibility.tech.screen_reader"), _t("accessibility.tech.magnification"),
            _t("accessibility.tech.speech_to_text"), _t("accessibility.tech.braille_display"),
            _t("accessibility.tech.calculator"), _t("accessibility.tech.spell_checker"), _t("common.other")
        ]).pack(side=tk.LEFT)

        # Notes
        ttk.Label(main_frame, text=_t("accessibility.labels.additional_notes") + ":").pack(anchor=tk.W, pady=(10, 5))
        notes_text = scrolledtext.ScrolledText(main_frame, height=4, width=50)
        notes_text.pack(fill=tk.X, pady=5)

        def save():
            student_id = student_id_var.get().strip()
            if not student_id:
                messagebox.showerror(_t("common.error"), _t("accessibility.error.student_id_required"))
                return

            try:
                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO exam_accommodations
                        (student_id, exam_id, extended_time, separate_room, reader_scribe,
                         assistive_technology, notes, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
                    ''', (student_id, exam_id_var.get().strip() or None, extended_time_var.get(),
                         separate_room_var.get(), reader_scribe_var.get(),
                         tech_var.get() if tech_var.get() != _t("common.none") else None,
                         notes_text.get('1.0', tk.END).strip(), datetime.now().isoformat()))

                messagebox.showinfo(_t("common.success"), _t("accessibility.messages.exam_accommodation_added"))
                log_activity(f"Added exam accommodation for {student_id}",
                           user=self.current_user.get('username'))
                dialog.destroy()
                self.load_exam_accommodations()

            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("accessibility.error.add_accommodation", error=str(e)))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t("common.save"), command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def view_exam_accommodation(self, event=None):
        """View exam accommodation details dialog"""
        selection = self.exam_tree.selection()
        if not selection:
            return

        item = self.exam_tree.item(selection[0])
        values = item['values']
        accommodation_id = values[0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM exam_accommodations WHERE accommodation_id = ?', (accommodation_id,))
                row = cursor.fetchone()

                if not row:
                    messagebox.showerror(_t("common.error"), _t("accessibility.error.accommodation_not_found"))
                    return

            dialog = tk.Toplevel(self.window)
            dialog.title(_t("accessibility.dialogs.exam_accommodation_details"))
            dialog.geometry("450x400")
            dialog.transient(self.window)

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=_t("accessibility.titles.exam_accommodation_details"),
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            info_frame = ttk.LabelFrame(main_frame, text=_t("accessibility.sections.accommodation_info"), padding="10")
            info_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(info_frame, text=f"{_t('accessibility.labels.accommodation_id')}: {row['accommodation_id']}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.student_id')}: {row['student_id']}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.exam_id')}: {row['exam_id'] or _t('accessibility.defaults.all_exams')}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.extended_time')}: {row['extended_time']} {_t('common.minutes')}" if row['extended_time'] else f"{_t('accessibility.labels.extended_time')}: {_t('common.none')}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.separate_room')}: {_t('common.yes') if row['separate_room'] else _t('common.no')}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.reader_scribe')}: {_t('common.yes') if row['reader_scribe'] else _t('common.no')}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.assistive_technology')}: {row['assistive_technology'] or _t('common.none')}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.status')}: {row['status']}").pack(anchor=tk.W, pady=2)

            # Check if notes exist and display them
            try:
                if row['notes']:
                    ttk.Label(info_frame, text=f"{_t('accessibility.labels.notes')}: {row['notes']}").pack(anchor=tk.W, pady=2)
            except (KeyError, IndexError):
                pass  # notes column doesn't exist or is empty

            ttk.Button(main_frame, text=_t("common.close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("accessibility.error.load_accommodation", error=str(e)))

    def request_assistive_tech(self):
        """Request assistive technology dialog"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("accessibility.dialogs.request_assistive_tech"))
        dialog.geometry("500x400")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("accessibility.titles.request_assistive_tech"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Student ID
        row1 = ttk.Frame(main_frame)
        row1.pack(fill=tk.X, pady=5)
        ttk.Label(row1, text=_t("accessibility.labels.student_id") + ":", width=20).pack(side=tk.LEFT)
        student_id_var = tk.StringVar(value=self.current_user.get('student_id') or self.current_user.get('username', ''))
        student_entry = ttk.Entry(row1, textvariable=student_id_var, width=30)
        student_entry.pack(side=tk.LEFT)
        if self.current_user.get('role') == 'student':
            student_entry.config(state='readonly')

        # Technology Type
        row2 = ttk.Frame(main_frame)
        row2.pack(fill=tk.X, pady=5)
        ttk.Label(row2, text=_t("accessibility.labels.technology_type") + ":", width=20).pack(side=tk.LEFT)
        tech_type_var = tk.StringVar()
        ttk.Combobox(row2, textvariable=tech_type_var, width=27, values=[
            _t("accessibility.tech_types.screen_reader_jaws"),
            _t("accessibility.tech_types.screen_reader_nvda"),
            _t("accessibility.tech_types.screen_magnifier"),
            _t("accessibility.tech_types.speech_to_text"),
            _t("accessibility.tech_types.text_to_speech"),
            _t("accessibility.tech_types.braille_display"),
            _t("accessibility.tech_types.hearing_loop"),
            _t("accessibility.tech_types.fm_listening"),
            _t("accessibility.tech_types.voice_amplifier"),
            _t("accessibility.tech_types.ergonomic_keyboard"),
            _t("accessibility.tech_types.alternative_mouse"),
            _t("accessibility.tech_types.head_pointer"),
            _t("accessibility.tech_types.eye_tracking"),
            _t("accessibility.tech_types.switch_access"),
            _t("common.other")
        ]).pack(side=tk.LEFT)

        # Justification
        ttk.Label(main_frame, text=_t("accessibility.labels.justification_reason") + ":").pack(anchor=tk.W, pady=(15, 5))
        justification_text = scrolledtext.ScrolledText(main_frame, height=6, width=50)
        justification_text.pack(fill=tk.X, pady=5)

        def submit():
            student_id = student_id_var.get().strip()
            tech_type = tech_type_var.get().strip()
            justification = justification_text.get('1.0', tk.END).strip()

            if not student_id or not tech_type:
                messagebox.showerror(_t("common.error"), _t("accessibility.error.student_tech_required"))
                return

            try:
                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO assistive_tech_requests
                        (student_id, technology_type, justification, status, requested_date)
                        VALUES (?, ?, ?, 'pending', ?)
                    ''', (student_id, tech_type, justification, datetime.now().isoformat()))

                messagebox.showinfo(_t("common.success"), _t("accessibility.messages.tech_request_submitted"))
                log_activity(f"Requested assistive tech: {tech_type}",
                           user=self.current_user.get('username'))
                dialog.destroy()
                self.load_assistive_tech_requests()

            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("accessibility.error.submit_tech_request", error=str(e)))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t("accessibility.btn.submit_request"), command=submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def manage_tech_request(self, event=None):
        """Manage tech request dialog"""
        selection = self.tech_tree.selection()
        if not selection:
            return

        item = self.tech_tree.item(selection[0])
        values = item['values']
        request_id = values[0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM assistive_tech_requests WHERE request_id = ?', (request_id,))
                row = cursor.fetchone()

                if not row:
                    messagebox.showerror(_t("common.error"), _t("accessibility.error.request_not_found"))
                    return

            dialog = tk.Toplevel(self.window)
            dialog.title(_t("accessibility.dialogs.manage_tech_request"))
            dialog.geometry("500x450")
            dialog.transient(self.window)

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=_t("accessibility.titles.tech_request_details"),
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            info_frame = ttk.LabelFrame(main_frame, text=_t("accessibility.sections.request_info"), padding="10")
            info_frame.pack(fill=tk.X, pady=5)

            ttk.Label(info_frame, text=f"{_t('accessibility.labels.request_id')}: {row['request_id']}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.student_id')}: {row['student_id']}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.technology')}: {row['technology_type']}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.status')}: {row['status']}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"{_t('accessibility.labels.requested')}: {row['requested_date']}").pack(anchor=tk.W, pady=2)
            if row['fulfilled_date']:
                ttk.Label(info_frame, text=f"{_t('accessibility.labels.fulfilled')}: {row['fulfilled_date']}").pack(anchor=tk.W, pady=2)

            if row.get('justification'):
                ttk.Label(main_frame, text=_t("accessibility.labels.justification") + ":").pack(anchor=tk.W, pady=(10, 5))
                just_text = scrolledtext.ScrolledText(main_frame, height=4, width=50)
                just_text.insert('1.0', row['justification'])
                just_text.config(state='disabled')
                just_text.pack(fill=tk.X, pady=5)

            # Management section for admin/staff
            if self.current_user.get('role') in ['admin', 'staff'] and row['status'] == 'pending':
                manage_frame = ttk.LabelFrame(main_frame, text=_t("accessibility.sections.manage_request"), padding="10")
                manage_frame.pack(fill=tk.X, pady=10)

                def fulfill():
                    try:
                        with transaction() as conn:
                            conn.execute('''
                                UPDATE assistive_tech_requests
                                SET status = 'fulfilled', fulfilled_date = ?
                                WHERE request_id = ?
                            ''', (datetime.now().isoformat(), request_id))
                        messagebox.showinfo(_t("common.success"), _t("accessibility.messages.request_fulfilled"))
                        log_activity(f"Fulfilled assistive tech request {request_id}",
                                   user=self.current_user.get('username'))
                        dialog.destroy()
                        self.load_assistive_tech_requests()
                    except Exception as e:
                        messagebox.showerror(_t("common.error"), _t("accessibility.error.update_failed", error=str(e)))

                def deny():
                    try:
                        with transaction() as conn:
                            conn.execute('''
                                UPDATE assistive_tech_requests SET status = 'denied' WHERE request_id = ?
                            ''', (request_id,))
                        messagebox.showinfo(_t("common.success"), _t("accessibility.messages.request_denied"))
                        log_activity(f"Denied assistive tech request {request_id}",
                                   user=self.current_user.get('username'))
                        dialog.destroy()
                        self.load_assistive_tech_requests()
                    except Exception as e:
                        messagebox.showerror(_t("common.error"), _t("accessibility.error.update_failed", error=str(e)))

                btn_frame = ttk.Frame(manage_frame)
                btn_frame.pack(pady=10)
                ttk.Button(btn_frame, text=_t("accessibility.btn.mark_fulfilled"), command=fulfill).pack(side=tk.LEFT, padx=5)
                ttk.Button(btn_frame, text=_t("accessibility.btn.deny_request"), command=deny).pack(side=tk.LEFT, padx=5)

            ttk.Button(main_frame, text=_t("common.close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("accessibility.error.load_tech_request", error=str(e)))

    def update_status(self, message):
        """Update status bar"""
        if hasattr(self, 'status_bar') and self.status_bar:
            self.status_bar.config(text=message)


def launch_accessibility_tools_gui(root, auth):
    """Launch the Accessibility Tools GUI"""
    try:
        gui = AccessibilityToolsGUI(root, auth)
        print("✅ Accessibility & Accommodation Tools GUI opened successfully")
    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("accessibility.error.launch_failed", error=str(e)))
        traceback.print_exc()


__all__ = ['AccessibilityToolsGUI', 'launch_accessibility_tools_gui']
