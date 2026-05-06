"""UI layout and styling management"""

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



class LayoutManager:
    """UI layout and styling management"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

        # Initialize attributes that will be set later
        self.content_area = None
        self.scrollable_frame = None
        self.content_canvas = None
        self.content_scrollbar = None
        self.canvas_frame = None

    def create_layout(self, root):
        """Header on top; left sidebar; right content."""
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(1, weight=1)

        # Top header (full width)
        header_holder = ttk.Frame(root)
        header_holder.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        self.create_header(header_holder)

        # Left sidebar
        sidebar_holder = ttk.Frame(root)
        sidebar_holder.grid(row=1, column=0, sticky="nsw", padx=(10, 5), pady=(0, 10))
        self.create_sidebar(sidebar_holder)

        # Right content
        content_holder = ttk.Frame(root)
        content_holder.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=(0, 10))
        self.create_scrollable_content_area(content_holder)

        # Start on dashboard
        self.gui.show_dashboard()


    def configure_styles(self):
        """Configure custom styles for the interface"""
        self.style.configure('Title.TLabel', font=('Arial', 16, 'bold'), background='#f0f0f0')
        self.style.configure('Header.TLabel', font=('Arial', 12, 'bold'), background='#f0f0f0')
        self.style.configure('Success.TLabel', foreground='green', background='#f0f0f0')
        self.style.configure('Error.TLabel', foreground='red', background='#f0f0f0')
        self.style.configure('Warning.TLabel', foreground='orange', background='#f0f0f0')
        self.style.configure('Info.TLabel', foreground='#1565c0', background='#f0f0f0')

        # Special styles for important buttons
        self.style.configure('CreateAssignment.TButton', font=('Arial', 11, 'bold'),
                           background='#4CAF50', foreground='white')
        self.style.map('CreateAssignment.TButton',
                      background=[('active', '#45a049'), ('pressed', '#3e8e41')])

        self.style.configure('Accent.TButton', font=('Arial', 10, 'bold'))
        self.style.map('Accent.TButton',
                      background=[('active', '#e0e0e0'), ('pressed', '#d0d0d0')])


    def create_main_interface(self):
        """Create the main GUI interface"""
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill='both', expand=True)

        # Toolbar
        toolbar = ttk.Frame(main_container, padding=(10, 8))
        toolbar.pack(fill='x')
        ttk.Button(toolbar, text="Return to Main Menu", command=self.return_to_main_menu).pack(side='left')

        # Header frame
        header_holder = ttk.Frame(main_container)
        header_holder.pack(fill='x', padx=10)
        self.create_header(header_holder)

        # Main content area with sidebar and content
        content_frame = ttk.Frame(main_container)
        content_frame.pack(fill='both', expand=True, pady=(10, 0))

        # Sidebar
        self.create_sidebar(content_frame)

        # Main content area with scrollbar
        self.create_scrollable_content_area(content_frame)

        # Show dashboard by default
        self.gui.show_dashboard()


    def create_header(self, parent):
        """Create the header with user info and notifications"""
        header_frame = ttk.Frame(parent, style='Header.TFrame')
        header_frame.pack(fill='x', pady=(0, 10))

        # Title
        title_label = ttk.Label(header_frame, text="Assignment Management System",
                               style='Title.TLabel')
        title_label.pack(side='left')

        # User info and controls
        user_frame = ttk.Frame(header_frame)
        user_frame.pack(side='right')
        ttk.Button(user_frame, text="Return to Main Menu", command=self.return_to_main_menu).pack(side='right', padx=(0, 10))

        # Notifications button
        self.notification_btn = ttk.Button(user_frame, text="🔔 Notifications (0)",
                                          command=self.gui.show_notifications)
        self.notification_btn.pack(side='right', padx=(0, 10))

        # User info
        user_info = f"Welcome, {self.auth.current_user.get('username', 'User')} ({self.auth.current_user.get('role', 'user')})"
        user_label = ttk.Label(user_frame, text=user_info)
        user_label.pack(side='right', padx=(0, 10))


    def return_to_main_menu(self):
        """Close this window so the launcher regains focus."""
        try:
            self.root.destroy()
        except Exception:
            self.root.quit()


    def create_sidebar(self, parent):
        """Create the navigation sidebar (scrollable, Linux-friendly)"""
        # Fixed-width container
        sidebar_container = ttk.Frame(parent, width=250)
        sidebar_container.pack(side='left', fill='y', padx=(0, 10))
        sidebar_container.pack_propagate(False)

        # Canvas + scrollbar
        self.sidebar_canvas = tk.Canvas(sidebar_container, highlightthickness=0, bg='#f0f0f0', width=230)
        self.sidebar_scrollbar = ttk.Scrollbar(
            sidebar_container, orient="vertical", command=self.sidebar_canvas.yview
        )
        self.sidebar_inner = ttk.Frame(self.sidebar_canvas)
        self.sidebar_window = self.sidebar_canvas.create_window(
            (0, 0), window=self.sidebar_inner, anchor="nw"
        )
        self.sidebar_canvas.configure(yscrollcommand=self.sidebar_scrollbar.set)
        self.sidebar_canvas.pack(side='left', fill='both', expand=True)
        self.sidebar_scrollbar.pack(side='right', fill='y')

        # Keep inner width synced with canvas
        def _on_canvas_configure(e):
            self.sidebar_canvas.itemconfig(self.sidebar_window, width=e.width)
            self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))
        self.sidebar_canvas.bind("<Configure>", _on_canvas_configure)

        # Update scrollregion when content changes
        def _on_inner_configure(e):
            self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))
            self._update_sidebar_scrollbar_visibility()
        self.sidebar_inner.bind("<Configure>", _on_inner_configure)

        # Header
        ttk.Label(self.sidebar_inner, text="Navigation", style='Header.TLabel').pack(anchor='w', pady=(0, 10))

        # Sections/buttons
        for section_name, buttons in self.get_navigation_sections():
            ttk.Label(self.sidebar_inner, text=section_name, font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
            for text, cmd in buttons:
                # Special styling for Create Assignment button
                if "Create Assignment" in text:
                    btn = ttk.Button(self.sidebar_inner, text=text, command=cmd, width=30,
                                   style='CreateAssignment.TButton')
                    btn.pack(anchor='w', pady=4, padx=(10, 0))  # Extra padding for prominence
                else:
                    ttk.Button(self.sidebar_inner, text=text, command=cmd, width=30).pack(anchor='w', pady=2, padx=(10, 0))

        # Force scroll region update after all navigation content is added
        self.sidebar_inner.update_idletasks()
        self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))

        def _wheel(event):
            if getattr(event, "delta", 0):
                self.sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                if getattr(event, "num", None) == 4:
                    self.sidebar_canvas.yview_scroll(-1, "units")
                elif getattr(event, "num", None) == 5:
                    self.sidebar_canvas.yview_scroll(1, "units")

        self.sidebar_canvas.bind("<MouseWheel>", _wheel)   # Win/Mac
        self.sidebar_canvas.bind("<Button-4>", _wheel)     # Linux up
        self.sidebar_canvas.bind("<Button-5>", _wheel)     # Linux down


    def _update_sidebar_scrollbar_visibility(self):
        """
        Update sidebar scrollbar visibility

        No-op method to maintain consistent scrollbar visibility.
        Unlike some implementations that hide/show scrollbars dynamically,
        this keeps the sidebar scrollbar always visible for consistency
        with the Grade Tracking system's behavior.

        This method exists to maintain API compatibility with other managers
        that may call it, but intentionally does nothing to preserve the
        always-visible scrollbar design pattern.
        """
        # Intentionally empty - scrollbar remains always visible
        pass


    def get_navigation_sections(self):
        """Get navigation sections based on user role"""
        sections = []

        is_admin = self.gui.is_admin()
        is_staff = self.gui.is_staff()
        is_student = self.gui.is_student()

        # Dashboard (always available to everyone)
        sections.append(("DASHBOARD", [
            ("📊 Dashboard", self.gui.show_dashboard),
            ("📅 Calendar", self.gui.show_calendar)
        ]))

        # AI Tools - Available to all users
        ai_tools_buttons = [
            ("🔍 Plagiarism Checker", self.gui.show_plagiarism_checker),
            ("🤖 AI Content Detector", self.gui.show_ai_detector),
            ("🧠 AI Dashboard", self.gui.show_ai_dashboard),
            ("📝 AI Draft Feedback", self.gui.show_draft_feedback),
            ("❓ Practice Question Generator", self.gui.show_practice_generator),
        ]
        sections.append(("AI TOOLS", ai_tools_buttons))

        # Student features - Available to all users (students, staff, admin)
        if is_student or is_staff or is_admin:
            student_buttons = [
                ("📄 My Assignments", self.gui.show_my_assignments),
                ("📤 Submit Assignment", self.gui.show_submit_assignment),
                ("📋 My Submissions", self.gui.show_my_submissions),
                ("💾 My Drafts", self.gui.show_draft_manager),
                ("⏰ Request Extension", self.gui.show_extension_request),
                ("⚖️ Submit Grade Dispute", self.gui.show_dispute_form),
                ("📜 My Disputes", self.gui.show_my_disputes),
                ("👥 Peer Review Dashboard", self.gui.show_peer_review_dashboard),
                ("✅ Complete Peer Reviews", self.gui.complete_peer_reviews),
                ("🔗 External Submissions", self.gui.show_external_submissions),
                ("♿ Accessibility Settings", self.gui.show_accessibility_settings),
                ("💬 View Messages", self.gui.view_messages),
                ("🔔 Manage Notifications", self.gui.manage_notifications)
            ]
            sections.append(("STUDENT", student_buttons))

        # Instructor features - Staff and Admin only
        if is_staff or is_admin:
            instructor_buttons = [
                ("➕ Create Assignment", self.gui.show_create_assignment),
                ("📝 Create Assessment", self.gui.show_create_assessment),
                ("👥 Create Group Assignment", self.gui.show_create_group_assignment),
                ("📶 Create Multi-Stage Assignment", self.gui.create_multi_stage_assignment),
                ("📊 Manage Assignments", self.gui.show_manage_assignments),
                ("🎯 Manage Assessments", self.gui.show_manage_assessments),
                ("📶 Multi-Stage Assignments", self.gui.show_multi_stage_assignments),
                ("✅ Grade Submissions", self.gui.show_grade_submissions),
                ("⭐ Grade with Rubrics", self.gui.grade_with_rubrics),
                ("🤖 Auto-Grading", self.gui.show_auto_grading),
                ("📋 View All Submissions", self.gui.view_all_submissions),
                ("✏️ Annotate Submissions", self.gui.show_annotation_summary),
                ("📑 Annotation Templates", self.gui.show_annotation_templates),
                ("⚖️ Regrade Queue", self.gui.show_regrade_queue),
                ("⚖️ Dispute History", self.gui.show_dispute_history),
                ("⏱️ Late Policies", self.gui.show_late_policies),
                ("📋 Late Submission Report", self.gui.show_late_submission_report),
                ("👥 Manage Groups", self.gui.show_manage_groups),
                ("🎓 External Examiners", self.gui.show_external_examiners),
                ("👥 Manage Peer Reviews", self.gui.manage_peer_reviews),
                ("🔧 Send Messages", self.gui.show_send_messages)
            ]
            sections.append(("INSTRUCTOR", instructor_buttons))

        # Exam Integrity - Staff and Admin only
        if is_staff or is_admin:
            integrity_buttons = [
                ("🔒 Exam Integrity Settings", self.gui.show_exam_integrity_settings),
                ("📡 Proctoring Dashboard", self.gui.show_proctoring_dashboard),
                ("📋 Integrity Logs", self.gui.view_integrity_logs),
                ("🔎 Collusion Detector", self.gui.show_collusion_detector),
                ("🎫 Late Pass Advisor", self.gui.show_late_pass_advisor),
            ]
            sections.append(("EXAM INTEGRITY", integrity_buttons))

        # Analytics - Staff and Admin only
        if is_staff or is_admin:
            analytics_buttons = [
                ("📈 Analytics Dashboard", self.gui.show_analytics),
                ("🔍 Advanced Analytics", self.gui.generate_advanced_analytics),
                ("📊 Custom Reports", self.gui.generate_custom_reports),
                ("📊 Question Bank Stats", self.gui.show_question_bank_stats),
                ("👁️ Preview Files", self.gui.show_file_preview)
            ]
            sections.append(("ANALYTICS", analytics_buttons))

        # Administration - Admin only
        if is_admin:
            admin_buttons = [
                ("📋 View All Assignments (Admin)", self.gui.show_admin_all_assignments),
                ("📝 Create Rubric", self.gui.show_create_rubric),
                ("📋 Manage Rubrics", self.gui.manage_rubrics),
                ("📋 Question Banks", self.gui.manage_question_banks),
                ("📄 Assignment Templates", self.gui.show_templates),
                ("📝 Review Extensions", self.gui.show_review_extensions),
                ("🔄 SIS Roster Sync", self.gui.show_sis_sync),
                ("⚠️ Academic Misconduct", self.gui.show_academic_misconduct),
                ("📝 Grade Audit Log", self.gui.show_grade_audit_log),
                ("♿ Accommodations", self.gui.show_accommodations),
                ("👥 TA Management", self.gui.show_ta_management),
                ("🔧 System Maintenance", self.gui.system_maintenance),
                ("💾 System Backup", self.gui.show_system_backup),
                ("🧹 Data Cleanup", self.gui.cleanup_old_data)
            ]
            sections.append(("ADMIN", admin_buttons))

        return sections


    def create_scrollable_content_area(self, parent):
        """Create a scrollable main content area"""
        # Container frame for the scrollable area
        content_container = ttk.Frame(parent)
        content_container.pack(side='right', fill='both', expand=True, padx=(10, 0))

        # Create canvas and scrollbar
        self.content_canvas = tk.Canvas(content_container, highlightthickness=0)
        self.content_scrollbar = ttk.Scrollbar(content_container, orient="vertical", command=self.content_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.content_canvas)

        # Configure the scrollable frame
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.update_scroll_region()
        )

        # Create the window in the canvas
        self.canvas_frame = self.content_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # Configure canvas scrolling
        self.content_canvas.configure(yscrollcommand=self.content_scrollbar.set)

        # Pack canvas and scrollbar
        self.content_canvas.pack(side="left", fill="both", expand=True)
        self.content_scrollbar.pack(side="right", fill="y")

        # Bind mousewheel scrolling
        self.bind_mousewheel_to_canvas()

        # Configure canvas to resize content frame width
        self.content_canvas.bind('<Configure>', self.on_canvas_configure)

        # Set content_area to the scrollable frame for compatibility
        self.content_area = self.scrollable_frame


    def bind_mousewheel_to_canvas(self):
        """Bind mouse wheel scrolling to the content canvas (Win/Mac/Linux)."""
        def _on_mousewheel(event):
            try:
                if not self.content_scrollbar.winfo_viewable():
                    return
            except tk.TclError:
                return
            # Windows / macOS generate event.delta; Linux uses Button-4/5
            if getattr(event, "delta", 0):
                self.content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                if getattr(event, "num", None) == 4:
                    self.content_canvas.yview_scroll(-1, "units")
                elif getattr(event, "num", None) == 5:
                    self.content_canvas.yview_scroll(1, "units")

        def _on_keypress(event):
            try:
                if not self.content_scrollbar.winfo_viewable():
                    return
            except tk.TclError:
                return
            k = event.keysym
            if k == 'Up':
                self.content_canvas.yview_scroll(-1, "units")
            elif k == 'Down':
                self.content_canvas.yview_scroll(1, "units")
            elif k == 'Page_Up':
                self.content_canvas.yview_scroll(-1, "pages")
            elif k == 'Page_Down':
                self.content_canvas.yview_scroll(1, "pages")
            elif k == 'Home':
                self.content_canvas.yview_moveto(0)
            elif k == 'End':
                self.content_canvas.yview_moveto(1)

        def _bind_all(_):
            # Mouse wheel
            self.content_canvas.bind_all("<MouseWheel>", _on_mousewheel)   # Win/Mac
            self.content_canvas.bind_all("<Button-4>", _on_mousewheel)     # Linux up
            self.content_canvas.bind_all("<Button-5>", _on_mousewheel)     # Linux down
            # Keys
            self.content_canvas.bind_all("<Key>", _on_keypress)
            self.content_canvas.focus_set()

        def _unbind_all(_):
            self.content_canvas.unbind_all("<MouseWheel>")
            self.content_canvas.unbind_all("<Button-4>")
            self.content_canvas.unbind_all("<Button-5>")
            self.content_canvas.unbind_all("<Key>")

        # Activate bindings on focus/hover (prevents global hijack)
        self.content_canvas.bind('<Enter>', _bind_all)
        self.content_canvas.bind('<Leave>', _unbind_all)
        self.content_canvas.bind('<FocusIn>', _bind_all)
        self.content_canvas.bind('<FocusOut>', _unbind_all)



    def _bind_sidebar_scroll_events(self):
        """Linux + cross-platform scrolling and keyboard navigation"""
        c = self.sidebar_canvas
        inner = self.sidebar_inner

        try:
            c.configure(takefocus=1)
        except Exception:
            pass

        def scroll_units(n):
            c.yview_scroll(n, "units")

        # Mouse wheel
        def on_wheel_linux(event):
            if event.num == 4:
                scroll_units(-3)
            elif event.num == 5:
                scroll_units(+3)

        def on_wheel_generic(event):
            if event.delta > 0:
                scroll_units(-3)
            elif event.delta < 0:
                scroll_units(+3)

        # Keyboard
        def on_key(event):
            k = event.keysym
            if k == 'Up':
                scroll_units(-1)
            elif k == 'Down':
                scroll_units(+1)
            elif k == 'Page_Up':
                c.yview_scroll(-1, "pages")
            elif k == 'Page_Down':
                c.yview_scroll(+1, "pages")
            elif k == 'Home':
                c.yview_moveto(0)
            elif k == 'End':
                c.yview_moveto(1)

        # Bind on both canvas and inner frame
        for w in (c, inner):
            w.bind("<Enter>", lambda e: c.focus_set())
            w.bind("<Button-4>", on_wheel_linux)     # Linux up
            w.bind("<Button-5>", on_wheel_linux)     # Linux down
            w.bind("<MouseWheel>", on_wheel_generic) # Mac/Windows
            w.bind("<Key>", on_key)

        # smoother wheel increments
        try:
            c.configure(yscrollincrement=20)
        except Exception:
            pass

        def _on_keypress(event):
            if self.sidebar_scrollbar.winfo_viewable():
                if event.keysym == 'Up':
                    self.sidebar_canvas.yview_scroll(-1, "units")
                elif event.keysym == 'Down':
                    self.sidebar_canvas.yview_scroll(1, "units")
                elif event.keysym == 'Page_Up':
                    self.sidebar_canvas.yview_scroll(-1, "pages")
                elif event.keysym == 'Page_Down':
                    self.sidebar_canvas.yview_scroll(1, "pages")
                elif event.keysym == 'Home':
                    self.sidebar_canvas.yview_moveto(0)
                elif event.keysym == 'End':
                    self.sidebar_canvas.yview_moveto(1)

        def bind_all_events(_):
            # Windows/Mac wheel
            self.sidebar_canvas.bind_all("<MouseWheel>", on_wheel_generic)
            # Linux wheel up/down
            self.sidebar_canvas.bind_all("<Button-4>", on_wheel_linux)
            self.sidebar_canvas.bind_all("<Button-5>", on_wheel_linux)
            self.sidebar_canvas.bind_all("<Key>", _on_keypress)
            self.sidebar_canvas.focus_set()

        def unbind_all_events(_):
            self.sidebar_canvas.unbind_all("<MouseWheel>")
            self.sidebar_canvas.unbind_all("<Button-4>")
            self.sidebar_canvas.unbind_all("<Button-5>")
            self.sidebar_canvas.unbind_all("<Key>")

        self.sidebar_canvas.bind("<Enter>", bind_all_events)
        self.sidebar_canvas.bind("<Leave>", unbind_all_events)
        self.sidebar_canvas.bind("<FocusIn>", bind_all_events)
        self.sidebar_canvas.bind("<FocusOut>", unbind_all_events)



    def _bind_content_scroll_events(self):
        """Bind mouse wheel and keys to content scrolling"""

        def _on_mousewheel(event):
            # Only scroll if bar is visible (i.e., content taller than viewport)
            if self.content_scrollbar.winfo_viewable():
                if event.delta:  # Windows
                    self.content_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                else:            # Linux
                    if event.num == 4:
                        self.content_canvas.yview_scroll(-1, "units")
                    elif event.num == 5:
                        self.content_canvas.yview_scroll(1, "units")

        def _on_keypress(event):
            # Handle keyboard scrolling
            if self.content_scrollbar.winfo_viewable():
                if event.keysym == 'Up':
                    self.content_canvas.yview_scroll(-1, "units")
                elif event.keysym == 'Down':
                    self.content_canvas.yview_scroll(1, "units")
                elif event.keysym == 'Page_Up':
                    self.content_canvas.yview_scroll(-1, "pages")
                elif event.keysym == 'Page_Down':
                    self.content_canvas.yview_scroll(1, "pages")
                elif event.keysym == 'Home':
                    self.content_canvas.yview_moveto(0)
                elif event.keysym == 'End':
                    self.content_canvas.yview_moveto(1)

        def bind_to_mousewheel(event):
            # Bind mouse wheel events
            self.content_canvas.bind_all("<MouseWheel>", _on_mousewheel)  # Windows
            self.content_canvas.bind_all("<Button-4>", _on_mousewheel)    # Linux scroll up
            self.content_canvas.bind_all("<Button-5>", _on_mousewheel)    # Linux scroll down

            # Bind keyboard events
            self.content_canvas.bind_all("<Key>", _on_keypress)
            # Make sure the canvas can receive focus for keyboard events
            self.content_canvas.focus_set()

        def unbind_from_mousewheel(event):
            self.content_canvas.unbind_all("<MouseWheel>")
            self.content_canvas.unbind_all("<Button-4>")
            self.content_canvas.unbind_all("<Button-5>")
            self.content_canvas.unbind_all("<Key>")

        # Bind when mouse enters canvas area
        self.content_canvas.bind('<Enter>', bind_to_mousewheel)
        self.content_canvas.bind('<Leave>', unbind_from_mousewheel)

        # Also bind focus events
        self.content_canvas.bind('<FocusIn>', bind_to_mousewheel)
        self.content_canvas.bind('<FocusOut>', unbind_from_mousewheel)


    def on_canvas_configure(self, event):
        """Handle canvas configuration changes"""
        # Update the scrollable frame width to match canvas width
        canvas_width = event.width
        self.content_canvas.itemconfig(self.canvas_frame, width=canvas_width)


    def clear_content_area(self):
        """Clear the current content area"""
        for widget in self.content_area.winfo_children():
            widget.destroy()
        # Scroll to top when content changes
        self.scroll_to_top()


    def update_scroll_region(self):
        """Update the scroll region and manage scrollbar visibility"""
        if hasattr(self, 'content_canvas') and hasattr(self, 'content_scrollbar'):
            # Update scroll region
            self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))

            # Auto-hide scrollbar when not needed
            canvas_height = self.content_canvas.winfo_height()
            content_height = self.content_canvas.bbox("all")[3] if self.content_canvas.bbox("all") else 0

            if content_height > canvas_height:
                # Content is larger than canvas, show scrollbar
                self.content_scrollbar.pack(side="right", fill="y")
            else:
                # Content fits in canvas, hide scrollbar
                self.content_scrollbar.pack_forget()


    def scroll_to_top(self):
        """Scroll the content area to the top"""
        if hasattr(self, 'content_canvas'):
            self.content_canvas.yview_moveto(0)

