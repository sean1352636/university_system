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

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.modules.shared.utils.activity_logger import log_activity
from university_system.modules.domain.student_affairs.services.accessibility_tools import (
    AccessibilityProfileManager, AccommodationRequestManager,
    ExamAccommodationManager, AssistiveTechManager
)


class AccessibilityToolsGUI:
    """Main GUI for Accessibility & Accommodation Tools"""

    def __init__(self, root, auth: Optional[UserAuth] = None):
        self.root = root
        self.auth = auth
        self.window = None
        self.current_user = auth.current_user if auth and auth.current_user else None

        # Permission check
        if not self.current_user:
            messagebox.showerror("Error", "You must be logged in to access Accessibility Tools.")
            return

        self.create_main_window()

    def create_main_window(self):
        """Create the main accessibility tools window"""
        try:
            self.window = tk.Toplevel(self.root)
            self.window.title("Accessibility & Accommodation Tools")
            self.window.geometry("1400x900")
            self.window.minsize(1200, 700)

            # Configure style
            style = ttk.Style()
            style.configure('Header.TLabel', font=('Arial', 16, 'bold'))
            style.configure('Section.TLabel', font=('Arial', 12, 'bold'))

            # Main container with tabs
            self.notebook = ttk.Notebook(self.window)
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Create tabs
            self.create_profiles_tab()
            self.create_requests_tab()
            self.create_exam_accommodations_tab()
            self.create_assistive_tech_tab()
            self.create_settings_tab()

            # Status bar
            self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
            self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

            # Log activity
            username = self.current_user.get('username') or self.current_user.get('id')
            log_activity(f"Opened Accessibility Tools GUI", user=username)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create window: {str(e)}")
            traceback.print_exc()

    def create_profiles_tab(self):
        """Create accessibility profiles tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Accessibility Profiles")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Accessibility Profiles",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        if self.current_user.get('role') in ['admin', 'staff']:
            ttk.Button(header_frame, text="Create Profile",
                      command=self.create_profile).pack(side=tk.RIGHT, padx=5)
            ttk.Button(header_frame, text="Refresh",
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
            ('ID', 60), ('User ID', 100), ('Disabilities', 250),
            ('Accommodations', 250), ('Assistive Tech', 200), ('Updated', 150)
        ]

        for col, width in columns_config:
            self.profiles_tree.heading(col, text=col)
            self.profiles_tree.column(col, width=width)

        self.profiles_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.profiles_tree.bind('<Double-1>', self.view_profile)

        self.load_profiles()

    def create_requests_tab(self):
        """Create accommodation requests tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Accommodation Requests")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Accommodation Requests",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        # Filter by status
        ttk.Label(header_frame, text="Status:").pack(side=tk.LEFT, padx=(20, 5))
        self.request_status_filter = ttk.Combobox(header_frame,
                                                  values=['All', 'pending', 'approved', 'denied'],
                                                  width=15, state='readonly')
        self.request_status_filter.pack(side=tk.LEFT, padx=5)
        self.request_status_filter.current(0)
        self.request_status_filter.bind('<<ComboboxSelected>>', lambda e: self.load_requests())

        ttk.Button(header_frame, text="Submit Request",
                  command=self.submit_request).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Refresh",
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
            ('ID', 60), ('Student ID', 100), ('Type', 200),
            ('Description', 300), ('Status', 100), ('Requested', 150), ('Reviewed By', 100)
        ]

        for col, width in columns_config:
            self.requests_tree.heading(col, text=col)
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
        self.notebook.add(tab, text="Exam Accommodations")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Exam Accommodations",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(header_frame, text="Add Accommodation",
                  command=self.add_exam_accommodation).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Refresh",
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
            ('ID', 60), ('Student ID', 100), ('Exam ID', 100), ('Extended Time', 130),
            ('Separate Room', 120), ('Assistive Tech', 200), ('Reader/Scribe', 120), ('Status', 80)
        ]

        for col, width in columns_config:
            self.exam_tree.heading(col, text=col)
            self.exam_tree.column(col, width=width)

        self.exam_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.exam_tree.bind('<Double-1>', self.view_exam_accommodation)

        self.load_exam_accommodations()

    def create_assistive_tech_tab(self):
        """Create assistive technology requests tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Assistive Technology")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Assistive Technology Requests",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(header_frame, text="Request Technology",
                  command=self.request_assistive_tech).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Refresh",
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
            ('ID', 60), ('Student ID', 150), ('Technology Type', 300),
            ('Status', 120), ('Requested', 200), ('Fulfilled', 200)
        ]

        for col, width in columns_config:
            self.tech_tree.heading(col, text=col)
            self.tech_tree.column(col, width=width)

        self.tech_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tech_tree.bind('<Double-1>', self.manage_tech_request)

        self.load_assistive_tech_requests()

    def create_settings_tab(self):
        """Create accessibility settings tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Accessibility Settings")

        ttk.Label(tab, text="User Accessibility Settings",
                 style='Header.TLabel').pack(pady=20)

        # Settings form
        form_frame = ttk.LabelFrame(tab, text="My Accessibility Preferences", padding="20")
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Theme
        row1 = ttk.Frame(form_frame)
        row1.pack(fill=tk.X, pady=10)
        ttk.Label(row1, text="Theme:", width=20).pack(side=tk.LEFT)
        self.theme_var = tk.StringVar(value='standard')
        themes = ttk.Combobox(row1, textvariable=self.theme_var,
                             values=['standard', 'high_contrast', 'dark'], state='readonly')
        themes.pack(side=tk.LEFT, padx=10)

        # Font size
        row2 = ttk.Frame(form_frame)
        row2.pack(fill=tk.X, pady=10)
        ttk.Label(row2, text="Font Size:", width=20).pack(side=tk.LEFT)
        self.font_size_var = tk.IntVar(value=16)
        ttk.Spinbox(row2, from_=12, to=32, textvariable=self.font_size_var, width=10).pack(side=tk.LEFT, padx=10)

        # Screen reader
        row3 = ttk.Frame(form_frame)
        row3.pack(fill=tk.X, pady=10)
        self.screen_reader_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row3, text="Enable Screen Reader Support",
                       variable=self.screen_reader_var).pack(anchor=tk.W)

        # Keyboard navigation
        row4 = ttk.Frame(form_frame)
        row4.pack(fill=tk.X, pady=10)
        self.keyboard_nav_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row4, text="Enhanced Keyboard Navigation",
                       variable=self.keyboard_nav_var).pack(anchor=tk.W)

        # Save button
        ttk.Button(form_frame, text="Save Settings",
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
                    cursor.execute('''
                        SELECT * FROM accessibility_profiles
                        WHERE user_id = ?
                    ''', (self.current_user.get('id'),))

                for row in cursor.fetchall():
                    disabilities = json.loads(row['disabilities'] or '[]')
                    accommodations = json.loads(row['accommodations'] or '[]')
                    assistive_tech = json.loads(row['assistive_technologies'] or '[]')

                    values = (
                        row['profile_id'],
                        row['user_id'],
                        ', '.join(disabilities) if disabilities else 'None',
                        ', '.join(accommodations) if accommodations else 'None',
                        ', '.join(assistive_tech) if assistive_tech else 'None',
                        row['updated_at']
                    )
                    self.profiles_tree.insert('', 'end', values=values)

            self.update_status(f"Loaded {len(self.profiles_tree.get_children())} profiles")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load profiles: {str(e)}")
            traceback.print_exc()

    def load_requests(self):
        """Load accommodation requests"""
        try:
            self.requests_tree.delete(*self.requests_tree.get_children())

            status_filter = self.request_status_filter.get()

            with get_connection() as conn:
                cursor = conn.cursor()

                if status_filter == 'All':
                    cursor.execute('''
                        SELECT * FROM accommodation_requests
                        ORDER BY requested_date DESC
                        LIMIT 500
                    ''')
                else:
                    cursor.execute('''
                        SELECT * FROM accommodation_requests
                        WHERE status = ?
                        ORDER BY requested_date DESC
                        LIMIT 500
                    ''', (status_filter,))

                for row in cursor.fetchall():
                    values = (
                        row['request_id'],
                        row['student_id'],
                        row['accommodation_type'],
                        (row['description'][:50] + '...') if len(row['description'] or '') > 50 else (row['description'] or ''),
                        row['status'],
                        row['requested_date'],
                        row['reviewed_by'] or 'Pending'
                    )
                    item = self.requests_tree.insert('', 'end', values=values, tags=(row['status'],))

            self.update_status(f"Loaded {len(self.requests_tree.get_children())} requests")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load requests: {str(e)}")
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
                        row['exam_id'] or 'All Exams',
                        f"{row['extended_time']} min" if row['extended_time'] else 'No',
                        'Yes' if row['separate_room'] else 'No',
                        row['assistive_technology'] or 'None',
                        'Yes' if row['reader_scribe'] else 'No',
                        row['status']
                    )
                    self.exam_tree.insert('', 'end', values=values)

            self.update_status(f"Loaded {len(self.exam_tree.get_children())} exam accommodations")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load exam accommodations: {str(e)}")
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
                        row['fulfilled_date'] or 'Pending'
                    )
                    self.tech_tree.insert('', 'end', values=values)

            self.update_status(f"Loaded {len(self.tech_tree.get_children())} tech requests")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tech requests: {str(e)}")
            traceback.print_exc()

    def load_accessibility_settings(self):
        """Load user's accessibility settings"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM accessibility_settings
                    WHERE user_id = ?
                ''', (self.current_user.get('id'),))
                row = cursor.fetchone()

                if row:
                    self.theme_var.set(row['theme'])
                    self.font_size_var.set(row['font_size'])
                    self.screen_reader_var.set(bool(row['screen_reader_enabled']))
                    self.keyboard_nav_var.set(bool(row['keyboard_navigation']))

        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_accessibility_settings(self):
        """Save user's accessibility settings"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()

                # Check if settings exist
                cursor.execute('SELECT setting_id FROM accessibility_settings WHERE user_id = ?',
                             (self.current_user.get('id'),))
                existing = cursor.fetchone()

                if existing:
                    cursor.execute('''
                        UPDATE accessibility_settings
                        SET theme = ?, font_size = ?, screen_reader_enabled = ?,
                            keyboard_navigation = ?
                        WHERE user_id = ?
                    ''', (self.theme_var.get(), self.font_size_var.get(),
                         self.screen_reader_var.get(), self.keyboard_nav_var.get(),
                         self.current_user.get('id')))
                else:
                    cursor.execute('''
                        INSERT INTO accessibility_settings
                        (user_id, theme, font_size, screen_reader_enabled, keyboard_navigation)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (self.current_user.get('id'), self.theme_var.get(),
                         self.font_size_var.get(), self.screen_reader_var.get(),
                         self.keyboard_nav_var.get()))

            messagebox.showinfo("Success", "Accessibility settings saved successfully!")
            username = self.current_user.get('username') or self.current_user.get('id')
            log_activity("Updated accessibility settings", user=username)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {str(e)}")

    # Action methods (stubs for dialogs)
    def create_profile(self):
        """Create accessibility profile"""
        messagebox.showinfo("Create Profile", "Profile creation dialog would open here.")

    def view_profile(self, event=None):
        """View profile details"""
        selection = self.profiles_tree.selection()
        if not selection:
            return
        messagebox.showinfo("View Profile", "Profile details dialog would open here.")

    def submit_request(self):
        """Submit accommodation request"""
        messagebox.showinfo("Submit Request", "Request submission dialog would open here.")

    def review_request(self, event=None):
        """Review accommodation request"""
        selection = self.requests_tree.selection()
        if not selection:
            return
        if self.current_user.get('role') in ['admin', 'staff']:
            messagebox.showinfo("Review Request", "Request review dialog would open here.")
        else:
            messagebox.showinfo("View Request", "Request details dialog would open here.")

    def add_exam_accommodation(self):
        """Add exam accommodation"""
        messagebox.showinfo("Add Accommodation", "Exam accommodation dialog would open here.")

    def view_exam_accommodation(self, event=None):
        """View exam accommodation details"""
        selection = self.exam_tree.selection()
        if not selection:
            return
        messagebox.showinfo("View Accommodation", "Accommodation details dialog would open here.")

    def request_assistive_tech(self):
        """Request assistive technology"""
        messagebox.showinfo("Request Technology", "Technology request dialog would open here.")

    def manage_tech_request(self, event=None):
        """Manage tech request"""
        selection = self.tech_tree.selection()
        if not selection:
            return
        messagebox.showinfo("Manage Request", "Tech request management dialog would open here.")

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
        messagebox.showerror("Error", f"Failed to launch Accessibility Tools: {str(e)}")
        traceback.print_exc()


__all__ = ['AccessibilityToolsGUI', 'launch_accessibility_tools_gui']
