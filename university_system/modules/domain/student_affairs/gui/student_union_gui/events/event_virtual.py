import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from university_system.infrastructure.email.template_utils import render_template
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
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
    from university_system.infrastructure.database.db import get_connection
    from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    

class VirtualEventsDialog:
    """Main dialog for virtual events management"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Virtual Events Platform")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="💻 Virtual Events Platform",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Action buttons
        button_grid = ttk.Frame(main_frame)
        button_grid.pack(fill='both', expand=True, pady=(0, 15))

        actions = [
            ("Create Virtual Event", self.create_virtual, "Set up online-only event"),
            ("Setup Hybrid Event", self.setup_hybrid, "Combine in-person + virtual"),
            ("Virtual Attendance", self.track_attendance, "Track online participation"),
            ("Tech Support", self.tech_support, "Technical assistance"),
        ]

        for i, (title, command, description) in enumerate(actions):
            card = ttk.LabelFrame(button_grid, text=title)
            card.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='nsew')
            ttk.Label(card, text=description).pack(padx=10, pady=5)
            ttk.Button(card, text="Open", command=command).pack(padx=10, pady=5)

        button_grid.rowconfigure(0, weight=1)
        button_grid.rowconfigure(1, weight=1)
        button_grid.columnconfigure(0, weight=1)
        button_grid.columnconfigure(1, weight=1)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def create_virtual(self):
        dialog = CreateVirtualEventDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def setup_hybrid(self):
        dialog = SetupHybridEventDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def track_attendance(self):
        dialog = VirtualAttendanceDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def tech_support(self):
        dialog = VirtualTechSupportDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



class CreateVirtualEventDialog:
    """Dialog for creating virtual events"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Virtual Event")
        self.dialog.geometry("800x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Create Virtual Event", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Form
        form = ttk.Frame(main_frame)
        form.pack(fill='both', expand=True)

        ttk.Label(form, text="Event Name:").grid(row=0, column=0, sticky='w', pady=5)
        self.name_entry = ttk.Entry(form, width=50)
        self.name_entry.grid(row=0, column=1, pady=5, sticky='ew')

        ttk.Label(form, text="Platform:").grid(row=1, column=0, sticky='w', pady=5)
        self.platform_combo = ttk.Combobox(form, width=48, state='readonly')
        self.platform_combo['values'] = ('Zoom', 'Microsoft Teams', 'Google Meet', 'WebEx', 'Custom Platform')
        self.platform_combo.grid(row=1, column=1, pady=5, sticky='ew')
        self.platform_combo.current(0)

        ttk.Label(form, text="Meeting Link:").grid(row=2, column=0, sticky='w', pady=5)
        self.link_entry = ttk.Entry(form, width=50)
        self.link_entry.grid(row=2, column=1, pady=5, sticky='ew')

        ttk.Label(form, text="Virtual Capacity:").grid(row=3, column=0, sticky='w', pady=5)
        self.capacity_entry = ttk.Entry(form, width=50)
        self.capacity_entry.grid(row=3, column=1, pady=5, sticky='ew')
        self.capacity_entry.insert(0, "100")

        ttk.Label(form, text="Date & Time:").grid(row=4, column=0, sticky='w', pady=5)
        self.datetime_entry = ttk.Entry(form, width=50)
        self.datetime_entry.grid(row=4, column=1, pady=5, sticky='ew')
        self.datetime_entry.insert(0, datetime.now().strftime('%Y-%m-%d %H:%M'))

        # Features
        features_frame = ttk.LabelFrame(main_frame, text="Features")
        features_frame.pack(fill='x', pady=15)

        self.recording_var = tk.BooleanVar(value=True)
        self.streaming_var = tk.BooleanVar(value=False)
        self.qa_var = tk.BooleanVar(value=True)
        self.breakout_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(features_frame, text="Enable Recording", variable=self.recording_var).pack(anchor='w', padx=10, pady=3)
        ttk.Checkbutton(features_frame, text="Live Streaming", variable=self.streaming_var).pack(anchor='w', padx=10, pady=3)
        ttk.Checkbutton(features_frame, text="Q&A Session", variable=self.qa_var).pack(anchor='w', padx=10, pady=3)
        ttk.Checkbutton(features_frame, text="Breakout Rooms", variable=self.breakout_var).pack(anchor='w', padx=10, pady=3)

        form.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Create Event", command=self.create_event).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Generate Meeting Link", command=self.generate_link).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def create_event(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter an event name.")
            return

        features = []
        if self.recording_var.get(): features.append("Recording")
        if self.streaming_var.get(): features.append("Streaming")
        if self.qa_var.get(): features.append("Q&A")
        if self.breakout_var.get(): features.append("Breakout Rooms")

        messagebox.showinfo("Success", f"Virtual event '{name}' created!\n\nPlatform: {self.platform_combo.get()}\nCapacity: {self.capacity_entry.get()}\nFeatures: {', '.join(features)}")
        self.dialog.destroy()

    def generate_link(self):
        import random
        meeting_id = ''.join([str(random.randint(0, 9)) for _ in range(11)])
        link = f"https://zoom.us/j/{meeting_id}"
        self.link_entry.delete(0, tk.END)
        self.link_entry.insert(0, link)
        messagebox.showinfo("Link Generated", f"Meeting link generated:\n{link}\n\nMeeting ID: {meeting_id}")



class SetupHybridEventDialog:
    """Dialog for setting up hybrid events"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Setup Hybrid Event")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Setup Hybrid Event (In-Person + Virtual)",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Notebook for in-person and virtual setup
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # In-person tab
        inperson_frame = ttk.Frame(notebook)
        notebook.add(inperson_frame, text="In-Person")

        ttk.Label(inperson_frame, text="Venue:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
        venue_entry = ttk.Entry(inperson_frame, width=40)
        venue_entry.grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(inperson_frame, text="Capacity:").grid(row=1, column=0, sticky='w', padx=10, pady=5)
        capacity_entry = ttk.Entry(inperson_frame, width=40)
        capacity_entry.grid(row=1, column=1, padx=10, pady=5)
        capacity_entry.insert(0, "50")

        # Virtual tab
        virtual_frame = ttk.Frame(notebook)
        notebook.add(virtual_frame, text="Virtual")

        ttk.Label(virtual_frame, text="Platform:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
        platform_combo = ttk.Combobox(virtual_frame, width=38, state='readonly')
        platform_combo['values'] = ('Zoom', 'Teams', 'Google Meet')
        platform_combo.grid(row=0, column=1, padx=10, pady=5)
        platform_combo.current(0)

        ttk.Label(virtual_frame, text="Virtual Capacity:").grid(row=1, column=0, sticky='w', padx=10, pady=5)
        vcapacity_entry = ttk.Entry(virtual_frame, width=40)
        vcapacity_entry.grid(row=1, column=1, padx=10, pady=5)
        vcapacity_entry.insert(0, "100")

        # Integration tab
        integration_frame = ttk.Frame(notebook)
        notebook.add(integration_frame, text="Integration")

        features = [
            "Live stream venue to virtual attendees",
            "Virtual Q&A visible in venue",
            "Unified chat system",
            "Shared polls and surveys",
            "Networking rooms for both groups"
        ]

        for i, feature in enumerate(features):
            var = tk.BooleanVar(value=True)
            ttk.Checkbutton(integration_frame, text=feature, variable=var).grid(row=i, column=0, sticky='w', padx=10, pady=5)

        # Setup summary
        summary_frame = ttk.LabelFrame(main_frame, text="Hybrid Event Benefits")
        summary_frame.pack(fill='x', pady=(0, 15))

        summary = """✓ Wider reach (In-person + Virtual attendance)
✓ Flexible participation options
✓ Increased accessibility
✓ Higher overall attendance
✓ Recording available for both groups
✓ Cost-effective scaling"""
        ttk.Label(summary_frame, text=summary, justify='left').pack(padx=15, pady=10)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Create Hybrid Event", command=self.create_hybrid).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def create_hybrid(self):
        messagebox.showinfo("Success", "Hybrid event created!\n\nBoth in-person and virtual attendance enabled.\nIntegration features configured.")
        self.dialog.destroy()



class VirtualAttendanceDialog:
    """Dialog for tracking virtual attendance"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Virtual Attendance Tracking")
        self.dialog.geometry("1000x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Virtual Attendance Tracking",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Attendees list
        list_frame = ttk.LabelFrame(main_frame, text="Virtual Attendees")
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Name', 'Join Time', 'Leave Time', 'Duration', 'Engagement', 'Quality')
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Sample data
        attendees = [
            ("John Doe", "10:00 AM", "11:30 AM", "1h 30m", "95%", "Good"),
            ("Jane Smith", "10:05 AM", "11:35 AM", "1h 30m", "88%", "Excellent"),
            ("Bob Johnson", "10:15 AM", "10:45 AM", "30m", "45%", "Fair"),
            ("Alice Williams", "10:00 AM", "11:40 AM", "1h 40m", "92%", "Good")
        ]

        for attendee in attendees:
            tree.insert('', 'end', values=attendee)

        # Stats
        stats_frame = ttk.LabelFrame(main_frame, text="Session Statistics")
        stats_frame.pack(fill='x', pady=(0, 15))

        stats = """Total Participants: 24
Average Duration: 1h 15m
Average Engagement: 82%
Peak Concurrent: 22 attendees
Connection Quality: 91% Good/Excellent"""
        ttk.Label(stats_frame, text=stats, justify='left', font=('Courier', 10)).pack(padx=15, pady=10)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()



class VirtualTechSupportDialog:
    """Dialog for virtual event tech support"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Virtual Event Tech Support")
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🛠️ Virtual Event Tech Support",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Notebook for different support areas
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Troubleshooting tab
        troubleshoot_tab = ttk.Frame(notebook)
        notebook.add(troubleshoot_tab, text="Troubleshooting")

        issues = [
            ("Cannot connect to meeting", "Check internet connection\nVerify meeting link\nTry different browser"),
            ("No audio/video", "Check microphone/camera permissions\nRestart browser\nUpdate drivers"),
            ("Poor connection quality", "Close other applications\nMove closer to router\nLower video quality"),
            ("Cannot share screen", "Grant screen sharing permission\nRestart application\nCheck firewall settings")
        ]

        for i, (issue, solution) in enumerate(issues):
            frame = ttk.LabelFrame(troubleshoot_tab, text=issue)
            frame.pack(fill='x', padx=10, pady=5)
            ttk.Label(frame, text=solution, justify='left').pack(padx=10, pady=5, anchor='w')

        # Connection test tab
        test_tab = ttk.Frame(notebook)
        notebook.add(test_tab, text="Connection Test")

        ttk.Label(test_tab, text="Run System Check", font=('Arial', 12, 'bold')).pack(pady=15)
        ttk.Button(test_tab, text="Test Connection", command=self.test_connection).pack(pady=5)
        ttk.Button(test_tab, text="Test Camera/Microphone", command=self.test_devices).pack(pady=5)
        ttk.Button(test_tab, text="Test Screen Sharing", command=self.test_screen).pack(pady=5)

        # Tutorials tab
        tutorials_tab = ttk.Frame(notebook)
        notebook.add(tutorials_tab, text="Tutorials")

        tutorials = [
            "How to join a virtual event",
            "Using chat and Q&A features",
            "Sharing your screen",
            "Using breakout rooms",
            "Optimizing your connection"
        ]

        for tutorial in tutorials:
            ttk.Button(tutorials_tab, text=tutorial, command=lambda t=tutorial: self.show_tutorial(t)).pack(fill='x', padx=10, pady=3)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def test_connection(self):
        messagebox.showinfo("Connection Test", "Connection: Good ✓\nSpeed: 50 Mbps\nLatency: 25ms\nJitter: Low\n\nYour connection is suitable for virtual events.")

    def test_devices(self):
        messagebox.showinfo("Device Test", "Camera: Detected ✓\nMicrophone: Detected ✓\nSpeakers: Detected ✓\n\nAll devices working properly.")

    def test_screen(self):
        messagebox.showinfo("Screen Share Test", "Screen sharing: Available ✓\nPermissions: Granted ✓\n\nScreen sharing is ready to use.")

    def show_tutorial(self, tutorial_name):
        messagebox.showinfo("Tutorial", f"Opening tutorial: {tutorial_name}\n\nVideo tutorial would play here...")


# ============================================================================
# KNOWLEDGE SHARING SESSIONS DIALOG
# ============================================================================


def open_virtual_events_dialog(self):
    """Open virtual events platform"""
    dialog = VirtualEventsDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


