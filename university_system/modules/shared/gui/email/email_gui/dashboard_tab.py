import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from tkinter.simpledialog import askstring, askinteger
import threading
import json
from datetime import datetime, timedelta
import webbrowser
import os
import subprocess
import sys
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Import internationalisation (i18n) for multi‑language support
try:
    from university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Add the project root to Python path if not already there
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from .email_manager_main import EmailManagerGUI, get_stored_emails

def create_dashboard_tab(self):
    """Create the main dashboard tab"""
    tab_frame = ttk.Frame(self.notebook)
    self.notebook.add(tab_frame, text=_t("email.tabs.dashboard", default="Dashboard"))

    # Welcome section
    welcome_frame = ttk.LabelFrame(tab_frame, text=_t("common.welcome", default="Welcome"), padding=10)
    welcome_frame.pack(fill=tk.X, padx=10, pady=10)

    welcome_text = _t("email.welcome_message", default="Welcome to the University Communication System, {username}!").format(
        username=self.auth.current_user['username']
    )
    ttk.Label(welcome_frame, text=welcome_text, font=('Arial', 12, 'bold')).pack()

    # Quick actions
    actions_frame = ttk.LabelFrame(tab_frame, text=_t("email.quick_actions", default="Quick Actions"), padding=10)
    actions_frame.pack(fill=tk.X, padx=10, pady=10)

    actions_grid = ttk.Frame(actions_frame)
    actions_grid.pack()

    # Create action buttons
    actions = [
        (_t("email.compose_email", default="Compose Email"), self.compose_email),
        (_t("email.check_messages", default="Check Messages"), self.open_messages),
        (_t("email.view_announcements", default="View Announcements"), self.open_announcements),
        (_t("email.chat_rooms", default="Chat Rooms"), self.open_chat_rooms),
        (_t("email.email_reports", default="Email Reports"), self.email_reports),
        (_t("email.settings", default="Settings"), self.email_configuration)
    ]

    for i, (text, command) in enumerate(actions):
        row, col = divmod(i, 3)
        btn = ttk.Button(actions_grid, text=text, command=command, width=20)
        btn.grid(row=row, column=col, padx=5, pady=5)

    # Statistics section
    self.create_stats_section(tab_frame)

# Bind method to EmailManagerGUI
EmailManagerGUI.create_dashboard_tab = create_dashboard_tab

def create_stats_section(self, parent):
    """Create statistics section for dashboard"""
    stats_frame = ttk.LabelFrame(parent, text=_t("email.statistics", default="Statistics"), padding=10)
    stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Create stats grid
    stats_grid = ttk.Frame(stats_frame)
    stats_grid.pack()

    # Stats labels
    self.stats_labels = {}
    stats_items = [
        ("emails_sent", _t("email.stats.emails_sent", default="Emails Sent")),
        ("emails_stored", _t("email.stats.emails_stored", default="Emails Stored")),
        ("messages_received", _t("email.stats.messages_received", default="Messages Received")),
        ("unread_messages", _t("email.stats.unread_messages", default="Unread Messages")),
        ("announcements", _t("email.stats.active_announcements", default="Active Announcements")),
        ("chat_rooms", _t("email.stats.chat_rooms_joined", default="Chat Rooms Joined"))
    ]

    for i, (key, label) in enumerate(stats_items):
        row, col = divmod(i, 3)

        frame = ttk.Frame(stats_grid)
        frame.grid(row=row, column=col, padx=20, pady=10)

        ttk.Label(frame, text=label, font=('Arial', 10)).pack()
        self.stats_labels[key] = ttk.Label(frame, text="0", font=('Arial', 14, 'bold'))
        self.stats_labels[key].pack()

# Bind method to EmailManagerGUI
EmailManagerGUI.create_stats_section = create_stats_section

def update_stats(self):
    """Update dashboard statistics"""
    try:
        # Get email statistics - filter by sender for non-admin users
        if 'get_stored_emails' in globals():
            sender_filter = None
            if self.auth and self.auth.current_user:
                user_role = self.auth.current_user.get('role', '')
                if user_role in ('student', 'staff', 'instructor'):
                    sender_filter = self.auth.current_user.get('email', '')
            emails_data = get_stored_emails(limit=1, sender_filter=sender_filter)
            self.stats_labels['emails_stored'].config(text=str(emails_data['total_count']))

        # Get message statistics
        if self.dashboard:
            inbox = self.dashboard.get_inbox()
            self.stats_labels['unread_messages'].config(text=str(inbox.get('unread_count', 0)))
            self.stats_labels['messages_received'].config(text=str(inbox.get('total_count', 0)))

            # Get announcements
            announcements = self.dashboard.get_announcements()
            self.stats_labels['announcements'].config(text=str(announcements.get('total_count', 0)))

            # Get chat rooms
            rooms = self.dashboard.get_chat_rooms('joined')
            self.stats_labels['chat_rooms'].config(text=str(rooms.get('total_count', 0)))

    except Exception as e:
        print(f"Error updating stats: {e}")

# Bind method to EmailManagerGUI
EmailManagerGUI.update_stats = update_stats

