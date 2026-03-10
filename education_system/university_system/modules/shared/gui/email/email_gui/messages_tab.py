"""
Merged Messages Tab for Email Manager GUI

Combines inbox messaging and system notifications into a unified interface.

Features:
- Inbox for user-to-user messages (compose, reply, delete)
- System notifications with filters (Academic, Social, Financial, Health, Housing, Events)
- Priority color coding for notifications
- Notification preferences (quiet hours, daily digest, bundling)
- Statistics and history for both messages and notifications
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from tkinter.simpledialog import askstring, askinteger
import threading
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import webbrowser
import os
import subprocess
import sys
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
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

from .email_manager_main import EmailManagerGUI
from .chat_dialogs import ComposeMessageDialog, ReplyMessageDialog

# Import notifications service
try:
    from education_system.university_system.modules.domain.notifications.services.notifications_service import (
        NotificationsService,
        NotificationPriority,
        NotificationChannel
    )
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    NotificationsService = None

# Priority colors (darker for text/icons)
PRIORITY_COLORS = {
    'urgent': '#FF4444',
    'high': '#FF9944',
    'medium': '#FFD700',
    'low': '#4A90E2'
}

# Priority background colors (lighter shades for tree rows)
PRIORITY_BG_COLORS = {
    'urgent': '#FFCCCC',
    'high': '#FFE0CC',
    'medium': '#FFF4CC',
    'low': '#CCE5FF'
}


def create_messages_tab(self):
    """Create the unified messages tab with inbox and notifications sub-tabs"""
    # Initialize notifications service if available
    if NOTIFICATIONS_AVAILABLE and not hasattr(self, 'notifications_service'):
        self.notifications_service = NotificationsService()

    # Initialize filter variables for notifications
    self.current_filter_channel = None
    self.current_filter_priority = None
    self.unread_only = tk.BooleanVar(value=False)

    # Create main messages tab
    tab_frame = ttk.Frame(self.notebook)
    self.notebook.add(tab_frame, text=_t("email.tabs.messages", default="Messages"))

    # Create sub-notebook for Inbox and Notifications
    self.messages_notebook = ttk.Notebook(tab_frame)
    self.messages_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Create Inbox sub-tab (user-to-user messages)
    create_inbox_subtab(self)

    # Create Notifications sub-tab (system notifications)
    if NOTIFICATIONS_AVAILABLE:
        create_notifications_subtab(self)
    else:
        # Show placeholder if notifications not available
        placeholder_frame = ttk.Frame(self.messages_notebook)
        self.messages_notebook.add(placeholder_frame, text=_t("email.tabs.notifications", default="Notifications"))
        ttk.Label(
            placeholder_frame,
            text=_t("email.notifications.unavailable", default="Notifications module not available"),
            font=('Arial', 12)
        ).pack(expand=True)


# ==================== INBOX SUB-TAB ====================

def create_inbox_subtab(self):
    """Create the inbox sub-tab for user-to-user messages"""
    inbox_frame = ttk.Frame(self.messages_notebook)
    self.messages_notebook.add(inbox_frame, text=_t("email.inbox", default="Inbox"))

    # Messages toolbar
    toolbar_frame = ttk.Frame(inbox_frame)
    toolbar_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(
        toolbar_frame,
        text=_t("email.compose_message", default="Compose Message"),
        command=self.compose_message
    ).pack(side=tk.LEFT, padx=5)
    ttk.Button(
        toolbar_frame,
        text=_t("email.reply", default="Reply"),
        command=self.reply_message
    ).pack(side=tk.LEFT, padx=5)
    ttk.Button(
        toolbar_frame,
        text=_t("common.delete", default="Delete"),
        command=self.delete_message
    ).pack(side=tk.LEFT, padx=5)
    ttk.Button(
        toolbar_frame,
        text=_t("common.refresh", default="Refresh"),
        command=self.refresh_messages
    ).pack(side=tk.RIGHT, padx=5)

    # Create paned window for inbox and message view
    paned = ttk.PanedWindow(inbox_frame, orient=tk.HORIZONTAL)
    paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Left pane - message list
    left_frame = ttk.Frame(paned)
    paned.add(left_frame, weight=1)

    # Messages list header
    ttk.Label(
        left_frame,
        text=_t("email.inbox", default="Inbox"),
        font=('Arial', 12, 'bold')
    ).pack(pady=(0, 5))

    # Create frame for treeview with scrollbar
    tree_frame = ttk.Frame(left_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    # Scrollbars
    vsb = ttk.Scrollbar(tree_frame, orient="vertical")
    vsb.pack(side=tk.RIGHT, fill=tk.Y)

    hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
    hsb.pack(side=tk.BOTTOM, fill=tk.X)

    self.messages_tree = ttk.Treeview(
        tree_frame,
        columns=("From", "Subject", "Date", "Status"),
        show="headings",
        selectmode='browse',
        yscrollcommand=vsb.set,
        xscrollcommand=hsb.set
    )
    self.messages_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    vsb.config(command=self.messages_tree.yview)
    hsb.config(command=self.messages_tree.xview)

    # Configure columns
    self.messages_tree.heading("From", text="From")
    self.messages_tree.column("From", width=150, minwidth=100)

    self.messages_tree.heading("Subject", text="Subject")
    self.messages_tree.column("Subject", width=250, minwidth=150)

    self.messages_tree.heading("Date", text="Date")
    self.messages_tree.column("Date", width=150, minwidth=120)

    self.messages_tree.heading("Status", text="Status")
    self.messages_tree.column("Status", width=80, minwidth=60)

    # Enable row selection highlighting
    self.messages_tree.tag_configure('unread', background='#E8F4F8')
    self.messages_tree.tag_configure('read', background='white')

    self.messages_tree.bind("<<TreeviewSelect>>", self.on_message_select)
    self.messages_tree.bind("<Double-1>", self.on_message_double_click)
    self.messages_tree.bind("<Button-3>", self.show_message_context_menu)

    # Add helpful label
    help_label = ttk.Label(
        left_frame,
        text=_t("email.help_click_message", default="Click a message to view - Double-click or use Reply button to respond"),
        font=('Arial', 9, 'italic'),
        foreground='#666'
    )
    help_label.pack(pady=(5, 0))

    # Right pane - message viewer
    right_frame = ttk.Frame(paned)
    paned.add(right_frame, weight=2)

    # Header with selection indicator
    header_frame = ttk.Frame(right_frame)
    header_frame.pack(fill=tk.X, pady=(0, 5))

    ttk.Label(
        header_frame,
        text=_t("email.message_content", default="Message Content"),
        font=('Arial', 12, 'bold')
    ).pack(side=tk.LEFT)

    # Selection indicator
    self.selected_message_indicator = ttk.Label(
        header_frame,
        text=_t("email.no_message_selected", default="No message selected"),
        font=('Arial', 9, 'italic'),
        foreground='#666'
    )
    self.selected_message_indicator.pack(side=tk.RIGHT, padx=5)

    self.message_text = scrolledtext.ScrolledText(right_frame, state=tk.DISABLED, wrap=tk.WORD)
    self.message_text.pack(fill=tk.BOTH, expand=True)


# ==================== NOTIFICATIONS SUB-TAB ====================

def create_notifications_subtab(self):
    """Create the notifications sub-tab for system notifications"""
    notif_frame = ttk.Frame(self.messages_notebook)
    self.messages_notebook.add(notif_frame, text=_t("email.tabs.notifications", default="Notifications"))

    # Main container with two panes
    main_paned = ttk.PanedWindow(notif_frame, orient=tk.HORIZONTAL)
    main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Left pane: Notification list and filters
    left_frame = ttk.Frame(main_paned)
    main_paned.add(left_frame, weight=3)

    # Right pane: Details and preferences
    right_frame = ttk.Frame(main_paned)
    main_paned.add(right_frame, weight=2)

    # Setup left pane
    setup_notifications_left_pane(self, left_frame)

    # Setup right pane
    setup_notifications_right_pane(self, right_frame)


def setup_notifications_left_pane(self, parent: ttk.Frame) -> None:
    """Setup left pane with filters and notification list"""
    # Header with unread badge
    header_frame = ttk.Frame(parent)
    header_frame.pack(fill=tk.X, padx=5, pady=5)

    title_label = ttk.Label(
        header_frame,
        text=_t("email.notifications.title", default="Notifications"),
        font=('Arial', 16, 'bold')
    )
    title_label.pack(side=tk.LEFT)

    self.unread_badge = ttk.Label(
        header_frame,
        text="0",
        font=('Arial', 10, 'bold'),
        foreground='white',
        background='#FF4444',
        padding=(8, 2)
    )
    self.unread_badge.pack(side=tk.LEFT, padx=10)

    # Refresh button
    refresh_btn = ttk.Button(
        header_frame,
        text=_t("common.refresh_with_icon", default="🔄 Refresh"),
        command=lambda: refresh_notifications(self)
    )
    refresh_btn.pack(side=tk.RIGHT)

    # Mark all as read button
    mark_all_btn = ttk.Button(
        header_frame,
        text=_t("email.notifications.mark_all_read", default="✓ Mark All Read"),
        command=lambda: mark_all_notifications_as_read(self)
    )
    mark_all_btn.pack(side=tk.RIGHT, padx=5)

    # Filters frame
    filters_frame = ttk.LabelFrame(parent, text=_t("email.notifications.filters", default="Filters"), padding=10)
    filters_frame.pack(fill=tk.X, padx=5, pady=5)

    # Unread only checkbox
    unread_check = ttk.Checkbutton(
        filters_frame,
        text=_t("email.notifications.unread_only", default="Unread only"),
        variable=self.unread_only,
        command=lambda: apply_notification_filters(self)
    )
    unread_check.pack(side=tk.LEFT, padx=5)

    # Channel filter tabs
    channel_frame = ttk.Frame(parent)
    channel_frame.pack(fill=tk.X, padx=5, pady=5)

    # Create channel buttons
    channels = [
        (_t("common.all", default="All"), None),
        (_t("email.notifications.academic", default="Academic"), "academic"),
        (_t("email.notifications.social", default="Social"), "social"),
        (_t("email.notifications.financial", default="Financial"), "financial"),
        (_t("email.notifications.health", default="Health"), "health"),
        (_t("email.notifications.housing", default="Housing"), "housing"),
        (_t("email.notifications.events", default="Events"), "events")
    ]

    self.channel_buttons = {}
    for label, channel in channels:
        btn = ttk.Button(
            channel_frame,
            text=label,
            command=lambda c=channel: set_notification_channel_filter(self, c)
        )
        btn.pack(side=tk.LEFT, padx=2)
        self.channel_buttons[channel] = btn

    # Priority filter
    priority_frame = ttk.Frame(filters_frame)
    priority_frame.pack(side=tk.LEFT, padx=20)

    ttk.Label(priority_frame, text=_t("email.notifications.priority", default="Priority:")).pack(side=tk.LEFT)

    self.priority_var = tk.StringVar(value="all")
    priority_combo = ttk.Combobox(
        priority_frame,
        textvariable=self.priority_var,
        values=[
            _t("common.all", default="All"),
            _t("email.notifications.urgent", default="Urgent"),
            _t("email.notifications.high", default="High"),
            _t("email.notifications.medium", default="Medium"),
            _t("email.notifications.low", default="Low")
        ],
        state='readonly',
        width=10
    )
    priority_combo.pack(side=tk.LEFT, padx=5)
    priority_combo.bind('<<ComboboxSelected>>', lambda e: apply_notification_filters(self))

    # Notifications list with scrollbar
    list_frame = ttk.Frame(parent)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Create treeview for notifications
    columns = ('ID', 'Priority', 'Channel', 'Title', 'Date')
    self.notification_tree = ttk.Treeview(
        list_frame,
        columns=columns,
        show='tree headings',
        selectmode='browse'
    )

    # Configure columns
    self.notification_tree.column('#0', width=30, stretch=False)
    self.notification_tree.column('ID', width=50, stretch=False)
    self.notification_tree.column('Priority', width=80, stretch=False)
    self.notification_tree.column('Channel', width=100, stretch=False)
    self.notification_tree.column('Title', width=300, stretch=True)
    self.notification_tree.column('Date', width=150, stretch=False)

    # Configure headings
    self.notification_tree.heading('ID', text=_t("common.id", default="ID"))
    self.notification_tree.heading('Priority', text=_t("email.notifications.priority", default="Priority"))
    self.notification_tree.heading('Channel', text=_t("email.notifications.channel", default="Channel"))
    self.notification_tree.heading('Title', text=_t("email.notifications.title_col", default="Title"))
    self.notification_tree.heading('Date', text=_t("common.date", default="Date"))

    # Scrollbar
    scrollbar = ttk.Scrollbar(
        list_frame,
        orient=tk.VERTICAL,
        command=self.notification_tree.yview
    )
    self.notification_tree.configure(yscrollcommand=scrollbar.set)

    self.notification_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Bind selection event
    self.notification_tree.bind('<<TreeviewSelect>>', lambda e: on_notification_select(self, e))

    # Configure tags for priority colors
    for priority, bg_color in PRIORITY_BG_COLORS.items():
        self.notification_tree.tag_configure(priority, background=bg_color)


def setup_notifications_right_pane(self, parent: ttk.Frame) -> None:
    """Setup right pane with details and preferences"""
    # Notebook for tabs
    notebook = ttk.Notebook(parent)
    notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Details tab
    details_tab = ttk.Frame(notebook)
    notebook.add(details_tab, text=_t("email.notifications.details", default="Details"))
    setup_notification_details_tab(self, details_tab)

    # Preferences tab
    prefs_tab = ttk.Frame(notebook)
    notebook.add(prefs_tab, text=_t("email.notifications.preferences", default="Preferences"))
    setup_notification_preferences_tab(self, prefs_tab)

    # Statistics tab
    stats_tab = ttk.Frame(notebook)
    notebook.add(stats_tab, text=_t("email.notifications.statistics", default="Statistics"))
    setup_notification_statistics_tab(self, stats_tab)


def setup_notification_details_tab(self, parent: ttk.Frame) -> None:
    """Setup notification details tab"""
    # Notification info
    info_frame = ttk.LabelFrame(parent, text=_t("email.notifications.notification_details", default="Notification Details"), padding=10)
    info_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Title
    self.detail_title = tk.StringVar()
    ttk.Label(info_frame, text=_t("email.notifications.title_label", default="Title:"), font=('Arial', 10, 'bold')).pack(anchor=tk.W)
    title_label = ttk.Label(
        info_frame,
        textvariable=self.detail_title,
        wraplength=400,
        font=('Arial', 12)
    )
    title_label.pack(anchor=tk.W, pady=(0, 10))

    # Message
    ttk.Label(info_frame, text=_t("email.notifications.message", default="Message:"), font=('Arial', 10, 'bold')).pack(anchor=tk.W)
    self.detail_message = scrolledtext.ScrolledText(
        info_frame,
        height=10,
        wrap=tk.WORD,
        state='disabled'
    )
    self.detail_message.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Metadata
    meta_frame = ttk.Frame(info_frame)
    meta_frame.pack(fill=tk.X)

    self.detail_channel = tk.StringVar()
    self.detail_priority = tk.StringVar()
    self.detail_date = tk.StringVar()
    self.detail_source = tk.StringVar()

    ttk.Label(meta_frame, text=_t("email.notifications.channel_label", default="Channel:")).grid(row=0, column=0, sticky=tk.W, pady=2)
    ttk.Label(meta_frame, textvariable=self.detail_channel).grid(row=0, column=1, sticky=tk.W, pady=2)

    ttk.Label(meta_frame, text=_t("email.notifications.priority_label", default="Priority:")).grid(row=1, column=0, sticky=tk.W, pady=2)
    ttk.Label(meta_frame, textvariable=self.detail_priority).grid(row=1, column=1, sticky=tk.W, pady=2)

    ttk.Label(meta_frame, text=_t("common.date_label", default="Date:")).grid(row=2, column=0, sticky=tk.W, pady=2)
    ttk.Label(meta_frame, textvariable=self.detail_date).grid(row=2, column=1, sticky=tk.W, pady=2)

    ttk.Label(meta_frame, text=_t("email.notifications.source", default="Source:")).grid(row=3, column=0, sticky=tk.W, pady=2)
    ttk.Label(meta_frame, textvariable=self.detail_source).grid(row=3, column=1, sticky=tk.W, pady=2)

    # Action buttons
    action_frame = ttk.Frame(info_frame)
    action_frame.pack(fill=tk.X, pady=10)

    self.mark_read_btn = ttk.Button(
        action_frame,
        text=_t("email.notifications.mark_as_read", default="Mark as Read"),
        command=lambda: mark_current_notification_as_read(self)
    )
    self.mark_read_btn.pack(side=tk.LEFT, padx=5)

    self.archive_btn = ttk.Button(
        action_frame,
        text=_t("email.notifications.archive", default="Archive"),
        command=lambda: archive_current_notification(self)
    )
    self.archive_btn.pack(side=tk.LEFT, padx=5)


def setup_notification_preferences_tab(self, parent: ttk.Frame) -> None:
    """Setup preferences tab"""
    # Scrollable frame
    canvas = tk.Canvas(parent)
    scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor=tk.NW)
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Quiet Hours
    quiet_frame = ttk.LabelFrame(scrollable_frame, text=_t("email.notifications.quiet_hours", default="Quiet Hours"), padding=10)
    quiet_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(quiet_frame, text=_t("email.notifications.start_time", default="Start Time:")).grid(row=0, column=0, sticky=tk.W, pady=5)
    self.quiet_start_var = tk.StringVar(value="22:00")
    quiet_start = ttk.Entry(quiet_frame, textvariable=self.quiet_start_var, width=10)
    quiet_start.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

    ttk.Label(quiet_frame, text=_t("email.notifications.end_time", default="End Time:")).grid(row=1, column=0, sticky=tk.W, pady=5)
    self.quiet_end_var = tk.StringVar(value="08:00")
    quiet_end = ttk.Entry(quiet_frame, textvariable=self.quiet_end_var, width=10)
    quiet_end.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)

    # Daily Digest
    digest_frame = ttk.LabelFrame(scrollable_frame, text=_t("email.notifications.daily_digest", default="Daily Digest"), padding=10)
    digest_frame.pack(fill=tk.X, padx=5, pady=5)

    self.digest_enabled_var = tk.BooleanVar(value=False)
    digest_check = ttk.Checkbutton(
        digest_frame,
        text=_t("email.notifications.enable_daily_digest", default="Enable daily digest"),
        variable=self.digest_enabled_var
    )
    digest_check.pack(anchor=tk.W)

    digest_time_frame = ttk.Frame(digest_frame)
    digest_time_frame.pack(fill=tk.X, pady=5)

    ttk.Label(digest_time_frame, text=_t("email.notifications.digest_time", default="Digest Time:")).pack(side=tk.LEFT)
    self.digest_time_var = tk.StringVar(value="08:00")
    digest_time = ttk.Entry(digest_time_frame, textvariable=self.digest_time_var, width=10)
    digest_time.pack(side=tk.LEFT, padx=5)

    # Bundling
    bundle_frame = ttk.LabelFrame(scrollable_frame, text=_t("email.notifications.bundling", default="Notification Bundling"), padding=10)
    bundle_frame.pack(fill=tk.X, padx=5, pady=5)

    self.bundle_enabled_var = tk.BooleanVar(value=True)
    bundle_check = ttk.Checkbutton(
        bundle_frame,
        text=_t("email.notifications.bundle_related", default="Bundle related notifications"),
        variable=self.bundle_enabled_var
    )
    bundle_check.pack(anchor=tk.W)

    bundle_time_frame = ttk.Frame(bundle_frame)
    bundle_time_frame.pack(fill=tk.X, pady=5)

    ttk.Label(bundle_time_frame, text=_t("email.notifications.time_window", default="Time Window (seconds):")).pack(side=tk.LEFT)
    self.bundle_time_var = tk.IntVar(value=300)
    bundle_time = ttk.Spinbox(
        bundle_time_frame,
        from_=60,
        to=3600,
        textvariable=self.bundle_time_var,
        width=10
    )
    bundle_time.pack(side=tk.LEFT, padx=5)

    # Channel Preferences
    channel_frame = ttk.LabelFrame(scrollable_frame, text=_t("email.notifications.channel_settings", default="Channel Settings"), padding=10)
    channel_frame.pack(fill=tk.X, padx=5, pady=5)

    # Create channel toggles
    self.channel_vars = {}
    channels = ['academic', 'social', 'financial', 'health', 'housing', 'events']

    for i, channel in enumerate(channels):
        var = tk.BooleanVar(value=True)
        self.channel_vars[channel] = var

        check = ttk.Checkbutton(
            channel_frame,
            text=channel.title(),
            variable=var
        )
        check.grid(row=i//2, column=i%2, sticky=tk.W, padx=10, pady=2)

    # Save preferences button
    save_btn = ttk.Button(
        scrollable_frame,
        text=_t("email.notifications.save_preferences", default="Save Preferences"),
        command=lambda: save_notification_preferences(self)
    )
    save_btn.pack(pady=10)

    # Maintenance
    maint_frame = ttk.LabelFrame(scrollable_frame, text=_t("email.notifications.maintenance", default="Maintenance"), padding=10)
    maint_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Button(
        maint_frame,
        text=_t("email.notifications.clear_old", default="Clear Old Notifications (30+ days)"),
        command=lambda: clear_old_notifications(self)
    ).pack(fill=tk.X, pady=2)

    ttk.Button(
        maint_frame,
        text=_t("email.notifications.generate_test", default="Generate Test Notification"),
        command=lambda: create_test_notification(self)
    ).pack(fill=tk.X, pady=2)


def setup_notification_statistics_tab(self, parent: ttk.Frame) -> None:
    """Setup statistics tab"""
    stats_frame = ttk.Frame(parent, padding=10)
    stats_frame.pack(fill=tk.BOTH, expand=True)

    # Overall stats
    overall_frame = ttk.LabelFrame(stats_frame, text=_t("email.notifications.overall_stats", default="Overall Statistics"), padding=10)
    overall_frame.pack(fill=tk.X, pady=5)

    self.stats_total = tk.StringVar(value="0")
    self.stats_unread = tk.StringVar(value="0")
    self.stats_urgent = tk.StringVar(value="0")
    self.stats_today = tk.StringVar(value="0")

    ttk.Label(overall_frame, text=_t("email.notifications.total", default="Total:")).grid(row=0, column=0, sticky=tk.W, pady=2)
    ttk.Label(overall_frame, textvariable=self.stats_total).grid(row=0, column=1, sticky=tk.W, pady=2)

    ttk.Label(overall_frame, text=_t("email.notifications.unread", default="Unread:")).grid(row=1, column=0, sticky=tk.W, pady=2)
    ttk.Label(overall_frame, textvariable=self.stats_unread).grid(row=1, column=1, sticky=tk.W, pady=2)

    ttk.Label(overall_frame, text=_t("email.notifications.urgent_label", default="Urgent:")).grid(row=2, column=0, sticky=tk.W, pady=2)
    ttk.Label(overall_frame, textvariable=self.stats_urgent).grid(row=2, column=1, sticky=tk.W, pady=2)

    ttk.Label(overall_frame, text=_t("email.notifications.today", default="Today:")).grid(row=3, column=0, sticky=tk.W, pady=2)
    ttk.Label(overall_frame, textvariable=self.stats_today).grid(row=3, column=1, sticky=tk.W, pady=2)

    # By channel
    channel_frame = ttk.LabelFrame(stats_frame, text=_t("email.notifications.by_channel", default="By Channel"), padding=10)
    channel_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    self.stats_text = scrolledtext.ScrolledText(
        channel_frame,
        height=15,
        state='disabled'
    )
    self.stats_text.pack(fill=tk.BOTH, expand=True)

    # Refresh button
    ttk.Button(
        stats_frame,
        text=_t("email.notifications.refresh_stats", default="Refresh Statistics"),
        command=lambda: refresh_notification_statistics(self)
    ).pack(pady=5)


# ==================== INBOX MESSAGE METHODS ====================

def refresh_messages(self):
    """Refresh the messages list"""
    try:
        # Clear existing items
        for item in self.messages_tree.get_children():
            self.messages_tree.delete(item)

        if self.dashboard:
            inbox = self.dashboard.get_inbox()

            # Handle case where inbox might be a boolean or None
            if isinstance(inbox, dict):
                messages = inbox.get('messages', [])

                if not messages:
                    # Insert a placeholder if no messages
                    self.messages_tree.insert('', tk.END, values=(
                        "No messages",
                        "Your inbox is empty",
                        "",
                        ""
                    ), tags=('empty',))
                else:
                    for message in messages:
                        status = "NEW" if not message['is_read'] else "READ"
                        # Use different tags for styling
                        tag = 'unread' if not message['is_read'] else 'read'

                        self.messages_tree.insert('', tk.END, values=(
                            message['sender'],
                            message['subject'][:40] + ('...' if len(message['subject']) > 40 else ''),
                            message['sent_at'],
                            status
                        ), tags=(str(message['id']), tag))

                self.update_status(f"Messages refreshed - {len(messages)} message(s)")
            else:
                print(f"Warning: inbox is not a dict, it's {type(inbox)}")
                # Show error in tree
                self.messages_tree.insert('', tk.END, values=(
                    "Error",
                    "Failed to load messages",
                    "",
                    ""
                ), tags=('error',))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to refresh messages: {e}")
        import traceback
        traceback.print_exc()


def compose_message(self):
    """Open compose message dialog"""
    ComposeMessageDialog(self.root, self.dashboard)


def reply_message(self):
    """Reply to selected message"""
    selection = self.messages_tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select a message to reply to")
        return

    if not self.dashboard:
        messagebox.showerror("Error", "Dashboard not initialized. Please restart the application.")
        return

    item = self.messages_tree.item(selection[0])
    message_id = item['tags'][0]
    ReplyMessageDialog(self.root, self.dashboard, message_id)


def delete_message(self):
    """Delete selected message"""
    selection = self.messages_tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select a message to delete")
        return

    if not self.dashboard:
        messagebox.showerror("Error", "Dashboard not initialized. Please restart the application.")
        return

    item = self.messages_tree.item(selection[0])
    message_id = item['tags'][0]

    if messagebox.askyesno("Confirm Delete", "Delete this message?"):
        try:
            if self.dashboard.update_message_status(message_id, 'delete'):
                self.refresh_messages()
                self.update_status("Message deleted")
            else:
                messagebox.showerror("Error", "Failed to delete message")
        except Exception as e:
            messagebox.showerror("Error", f"Error deleting message: {e}")


def on_message_select(self, event):
    """Handle message selection"""
    # Prevent recursive calls when restoring selection
    if getattr(self, '_restoring_selection', False):
        return

    selection = self.messages_tree.selection()
    if selection:
        item = self.messages_tree.item(selection[0])
        tags = item['tags']

        # Skip if this is a placeholder message
        if 'empty' in tags or 'error' in tags:
            # Update indicator to show no message selected
            if hasattr(self, 'selected_message_indicator'):
                self.selected_message_indicator.config(
                    text="No message selected",
                    foreground='#666'
                )
            return

        if not tags:
            if hasattr(self, 'selected_message_indicator'):
                self.selected_message_indicator.config(
                    text="No message selected",
                    foreground='#666'
                )
            return

        message_id = tags[0]

        try:
            if self.dashboard:
                message = self.dashboard.read_message(message_id)
                if message:
                    self.message_text.config(state=tk.NORMAL)
                    self.message_text.delete(1.0, tk.END)

                    # Format message content
                    content = f"From: {message['sender']}\n"
                    content += f"To: {message['recipient']}\n"
                    content += f"Subject: {message['subject']}\n"
                    content += f"Date: {message['sent_at']}\n"
                    content += f"Status: {'Read' if message['is_read'] else 'Unread'}\n"
                    content += "-" * 50 + "\n\n"
                    content += message['content']

                    self.message_text.insert(1.0, content)
                    self.message_text.config(state=tk.DISABLED)

                    # Update selection indicator to show message is ready for reply
                    if hasattr(self, 'selected_message_indicator'):
                        self.selected_message_indicator.config(
                            text="✓ Message selected - Ready to reply",
                            foreground='#2E86AB',  # Primary color
                            font=('Arial', 9, 'bold')
                        )

                    # Mark as read - refresh and restore selection
                    self.refresh_messages()
                    # Restore selection after refresh
                    self._select_message_by_id(message_id)
        except Exception as e:
            messagebox.showerror("Error", f"Error loading message: {e}")
            import traceback
            traceback.print_exc()
    else:
        # No selection - reset indicator
        if hasattr(self, 'selected_message_indicator'):
            self.selected_message_indicator.config(
                text="No message selected",
                foreground='#666',
                font=('Arial', 9, 'italic')
            )


def _select_message_by_id(self, message_id):
    """Select a message in the tree by its ID (stored in tags)"""
    self._restoring_selection = True
    try:
        for item in self.messages_tree.get_children():
            item_tags = self.messages_tree.item(item, 'tags')
            if item_tags and str(message_id) in item_tags:
                self.messages_tree.selection_set(item)
                self.messages_tree.see(item)
                break
    finally:
        # Use after_idle to reset the flag AFTER the <<TreeviewSelect>> event is processed
        # This prevents infinite recursion when selection_set triggers the event
        self.root.after_idle(lambda: setattr(self, '_restoring_selection', False))


def on_message_double_click(self, event):
    """Handle double-click on message - open reply dialog"""
    selection = self.messages_tree.selection()
    if selection:
        # Same as clicking Reply button
        self.reply_message()


def show_message_context_menu(self, event):
    """Show context menu for message"""
    # Select the item under cursor
    item = self.messages_tree.identify_row(event.y)
    if item:
        self.messages_tree.selection_set(item)

        # Check if it's a valid message (not placeholder)
        item_data = self.messages_tree.item(item)
        tags = item_data['tags']

        if 'empty' in tags or 'error' in tags:
            return

        # Create context menu
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label="Reply", command=self.reply_message)
        context_menu.add_command(label="Delete", command=self.delete_message)
        context_menu.add_separator()
        context_menu.add_command(label="Mark as Unread", command=lambda: self.mark_message_unread(tags[0]))
        context_menu.add_command(label="Archive", command=lambda: self.archive_message(tags[0]))

        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()


def mark_message_unread(self, message_id):
    """Mark a message as unread"""
    try:
        if self.dashboard:
            # Call dashboard method to mark unread
            from education_system.university_system.infrastructure.database.db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE messages SET is_read = 0, read_at = NULL WHERE id = ?', (message_id,))
            conn.commit()
            conn.close()
            self.refresh_messages()
            self.update_status("Message marked as unread")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to mark as unread: {e}")


def archive_message(self, message_id):
    """Archive a message"""
    try:
        if self.dashboard:
            from education_system.university_system.infrastructure.database.db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE messages SET is_archived = 1 WHERE id = ?', (message_id,))
            conn.commit()
            conn.close()
            self.refresh_messages()
            self.update_status("Message archived")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to archive message: {e}")


def open_messages(self):
    """Switch to messages tab"""
    # Find the messages tab index
    for i in range(self.notebook.index('end')):
        if self.notebook.tab(i, 'text') in ['Messages', _t("email.tabs.messages", default="Messages")]:
            self.notebook.select(i)
            self.refresh_messages()
            return


# ==================== NOTIFICATION METHODS ====================

def load_notification_user_data(self) -> None:
    """Load user data and preferences"""
    if not NOTIFICATIONS_AVAILABLE:
        return

    if not self.auth.current_user:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.notifications.login_required", default="Please log in first."))
        return

    current_user_id = self.auth.get_current_user()['username']

    # Load preferences
    load_notification_preferences(self, current_user_id)

    # Load notifications
    refresh_notifications(self)

    # Load statistics
    refresh_notification_statistics(self)


def load_notification_preferences(self, user_id: str) -> None:
    """Load user preferences"""
    if not NOTIFICATIONS_AVAILABLE:
        return

    try:
        prefs = self.notifications_service.get_preferences(user_id)

        # Set preference values
        if hasattr(self, 'quiet_start_var'):
            self.quiet_start_var.set(prefs.get('quiet_hours_start', '22:00'))
            self.quiet_end_var.set(prefs.get('quiet_hours_end', '08:00'))
            self.digest_enabled_var.set(bool(prefs.get('daily_digest_enabled', 0)))
            self.digest_time_var.set(prefs.get('daily_digest_time', '08:00'))
            self.bundle_enabled_var.set(bool(prefs.get('bundle_notifications', 1)))
            self.bundle_time_var.set(prefs.get('bundle_time_window', 300))

        # Load channel settings
        channel_settings = self.notifications_service.get_channel_settings(user_id)
        if hasattr(self, 'channel_vars'):
            for setting in channel_settings:
                channel = setting['channel']
                if channel in self.channel_vars:
                    self.channel_vars[channel].set(bool(setting['enabled']))
    except Exception as e:
        print(f"Error loading notification preferences: {e}")


def refresh_notifications(self) -> None:
    """Refresh notification list"""
    if not NOTIFICATIONS_AVAILABLE:
        return

    if not self.auth.current_user:
        return

    current_user_id = self.auth.get_current_user()['username']

    try:
        # Clear current list
        for item in self.notification_tree.get_children():
            self.notification_tree.delete(item)

        # Get notifications with filters
        notifications = self.notifications_service.get_notifications(
            current_user_id,
            unread_only=self.unread_only.get(),
            channel=self.current_filter_channel,
            priority=self.current_filter_priority,
            limit=100
        )

        # Populate tree
        for notif in notifications:
            read_symbol = '' if notif['is_read'] else '●'

            values = (
                notif['notification_id'],
                notif['priority'].upper(),
                notif['channel'].upper(),
                notif['title'],
                notif['created_at'][:16]  # Show date/time
            )

            tags = [notif['priority']]
            if not notif['is_read']:
                tags.append('unread')

            self.notification_tree.insert(
                '',
                tk.END,
                text=read_symbol,
                values=values,
                tags=tags
            )

        # Update unread badge
        unread_count = self.notifications_service.get_unread_count(current_user_id)
        if hasattr(self, 'unread_badge'):
            self.unread_badge.config(text=str(unread_count))

        self.update_status(_t("email.notifications.loaded", default="Loaded {count} notifications").format(count=len(notifications)))
    except Exception as e:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.notifications.refresh_failed", default="Failed to refresh notifications: {error}").format(error=str(e)))


def refresh_notification_statistics(self) -> None:
    """Refresh statistics display"""
    if not NOTIFICATIONS_AVAILABLE:
        return

    if not self.auth.current_user:
        return

    current_user_id = self.auth.get_current_user()['username']

    try:
        stats = self.notifications_service.get_notification_stats(current_user_id)

        # Update overall stats
        if hasattr(self, 'stats_total'):
            self.stats_total.set(str(stats['total']))
            self.stats_unread.set(str(stats['unread']))
            self.stats_urgent.set(str(stats['urgent']))
            self.stats_today.set(str(stats['today']))

        # Update channel breakdown
        if hasattr(self, 'stats_text'):
            self.stats_text.config(state='normal')
            self.stats_text.delete(1.0, tk.END)

            for channel, count in sorted(stats['by_channel'].items()):
                self.stats_text.insert(tk.END, f"{channel.upper():<15} {count:>5}\n")

            self.stats_text.config(state='disabled')
    except Exception as e:
        print(f"Error refreshing notification statistics: {e}")


def on_notification_select(self, event) -> None:
    """Handle notification selection"""
    if not NOTIFICATIONS_AVAILABLE:
        return

    selection = self.notification_tree.selection()
    if not selection:
        return

    item = selection[0]
    values = self.notification_tree.item(item)['values']

    if not values:
        return

    notification_id = values[0]
    current_user_id = self.auth.get_current_user()['username']

    # Load full notification details
    notifications = self.notifications_service.get_notifications(current_user_id, limit=1000)
    notification = next(
        (n for n in notifications if n['notification_id'] == notification_id),
        None
    )

    if notification:
        display_notification_details(self, notification)


def display_notification_details(self, notification: Dict[str, Any]) -> None:
    """Display notification details"""
    if not hasattr(self, 'detail_title'):
        return

    self.detail_title.set(notification['title'])
    self.detail_channel.set(notification['channel'].upper())
    self.detail_priority.set(notification['priority'].upper())
    self.detail_date.set(notification['created_at'])
    self.detail_source.set(notification.get('source_system', 'N/A'))

    # Update message
    self.detail_message.config(state='normal')
    self.detail_message.delete(1.0, tk.END)
    self.detail_message.insert(1.0, notification['message'])
    self.detail_message.config(state='disabled')

    # Store current notification ID
    self.current_notification_id = notification['notification_id']


def set_notification_channel_filter(self, channel: Optional[str]) -> None:
    """Set channel filter"""
    self.current_filter_channel = channel
    apply_notification_filters(self)

    # Update button states (visual feedback)
    if hasattr(self, 'channel_buttons'):
        for ch, btn in self.channel_buttons.items():
            if ch == channel:
                btn.state(['pressed'])
            else:
                btn.state(['!pressed'])


def apply_notification_filters(self) -> None:
    """Apply current filters"""
    # Priority filter
    priority_text = self.priority_var.get().lower()
    if priority_text == 'all' or priority_text == _t("common.all", default="all").lower():
        self.current_filter_priority = None
    else:
        self.current_filter_priority = priority_text

    refresh_notifications(self)


def mark_current_notification_as_read(self) -> None:
    """Mark currently selected notification as read"""
    if not NOTIFICATIONS_AVAILABLE:
        return

    if not hasattr(self, 'current_notification_id'):
        messagebox.showwarning(_t("common.warning", default="Warning"), _t("email.notifications.no_selection", default="No notification selected."))
        return

    current_user_id = self.auth.get_current_user()['username']
    success = self.notifications_service.mark_as_read(
        self.current_notification_id,
        current_user_id
    )

    if success:
        self.update_status(_t("email.notifications.marked_read", default="Marked as read"))
        refresh_notifications(self)
    else:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.notifications.mark_read_failed", default="Failed to mark as read."))


def mark_all_notifications_as_read(self) -> None:
    """Mark all notifications as read"""
    if not NOTIFICATIONS_AVAILABLE:
        return

    if not self.auth.current_user:
        return

    current_user_id = self.auth.get_current_user()['username']

    confirm = messagebox.askyesno(
        _t("common.confirm", default="Confirm"),
        _t("email.notifications.mark_all_confirm", default="Mark all notifications as read?")
    )

    if not confirm:
        return

    count = self.notifications_service.mark_all_as_read(
        current_user_id,
        channel=self.current_filter_channel
    )

    self.update_status(_t("email.notifications.marked_all_read", default="Marked {count} notifications as read").format(count=count))
    refresh_notifications(self)


def archive_current_notification(self) -> None:
    """Archive currently selected notification"""
    if not NOTIFICATIONS_AVAILABLE:
        return

    if not hasattr(self, 'current_notification_id'):
        messagebox.showwarning(_t("common.warning", default="Warning"), _t("email.notifications.no_selection", default="No notification selected."))
        return

    current_user_id = self.auth.get_current_user()['username']

    confirm = messagebox.askyesno(
        _t("common.confirm", default="Confirm"),
        _t("email.notifications.archive_confirm", default="Archive this notification?")
    )

    if not confirm:
        return

    success = self.notifications_service.archive_notification(
        self.current_notification_id,
        current_user_id
    )

    if success:
        self.update_status(_t("email.notifications.archived", default="Notification archived"))
        refresh_notifications(self)
    else:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.notifications.archive_failed", default="Failed to archive notification."))


def save_notification_preferences(self) -> None:
    """Save user preferences"""
    if not NOTIFICATIONS_AVAILABLE:
        return

    if not self.auth.current_user:
        return

    current_user_id = self.auth.get_current_user()['username']

    try:
        # Update general preferences
        success = self.notifications_service.update_preferences(
            current_user_id,
            quiet_hours_start=self.quiet_start_var.get(),
            quiet_hours_end=self.quiet_end_var.get(),
            daily_digest_enabled=self.digest_enabled_var.get(),
            daily_digest_time=self.digest_time_var.get(),
            bundle_notifications=self.bundle_enabled_var.get(),
            bundle_time_window=self.bundle_time_var.get()
        )

        # Update channel settings
        if hasattr(self, 'channel_vars'):
            for channel, var in self.channel_vars.items():
                self.notifications_service.update_channel_settings(
                    current_user_id,
                    channel,
                    enabled=var.get()
                )

        if success:
            messagebox.showinfo(_t("common.success", default="Success"), _t("email.notifications.prefs_saved", default="Preferences saved successfully."))
            self.update_status(_t("email.notifications.prefs_saved_short", default="Preferences saved"))
        else:
            messagebox.showerror(_t("common.error", default="Error"), _t("email.notifications.prefs_save_failed", default="Failed to save preferences."))

    except Exception as e:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.notifications.prefs_save_error", default="Failed to save preferences: {error}").format(error=str(e)))


def clear_old_notifications(self) -> None:
    """Clear old read notifications"""
    if not NOTIFICATIONS_AVAILABLE:
        return

    if not self.auth.current_user:
        return

    current_user_id = self.auth.get_current_user()['username']

    confirm = messagebox.askyesno(
        _t("common.confirm", default="Confirm"),
        _t("email.notifications.clear_old_confirm", default="Delete all read notifications older than 30 days?")
    )

    if not confirm:
        return

    count = self.notifications_service.delete_old_notifications(current_user_id, 30)

    messagebox.showinfo(_t("common.success", default="Success"), _t("email.notifications.deleted_old", default="Deleted {count} old notifications.").format(count=count))
    self.update_status(_t("email.notifications.deleted_old_short", default="Deleted {count} old notifications").format(count=count))
    refresh_notifications(self)


def create_test_notification(self) -> None:
    """Create a test notification"""
    if not NOTIFICATIONS_AVAILABLE:
        return

    if not self.auth.current_user:
        return

    current_user_id = self.auth.get_current_user()['username']

    # Simple test notification
    notification_id = self.notifications_service.create_notification(
        user_id=current_user_id,
        channel='system',
        priority='medium',
        title='Test Notification',
        message=f'This is a test notification created at {datetime.now().strftime("%H:%M:%S")}',
        source_system='Email Manager'
    )

    messagebox.showinfo(_t("common.success", default="Success"), _t("email.notifications.test_created", default="Created test notification (ID: {id})").format(id=notification_id))
    refresh_notifications(self)


def show_notifications_tab(self):
    """Switch to notifications sub-tab within messages tab"""
    # First switch to messages tab
    for i in range(self.notebook.index('end')):
        if self.notebook.tab(i, 'text') in ['Messages', _t("email.tabs.messages", default="Messages")]:
            self.notebook.select(i)
            # Then switch to notifications sub-tab
            if hasattr(self, 'messages_notebook'):
                for j in range(self.messages_notebook.index('end')):
                    if self.messages_notebook.tab(j, 'text') in ['Notifications', _t("email.tabs.notifications", default="Notifications")]:
                        self.messages_notebook.select(j)
                        refresh_notifications(self)
                        return
            return

    # If tab doesn't exist, this shouldn't happen but handle gracefully
    messagebox.showwarning(_t("common.warning", default="Warning"), _t("email.notifications.tab_not_found", default="Notifications tab not found"))


def notification_preferences(self):
    """Show notification preferences - switches to notifications sub-tab and preferences section"""
    # Switch to notifications sub-tab
    show_notifications_tab(self)
    # The preferences are already visible in the right pane


# ==================== BIND METHODS TO EmailManagerGUI ====================

# Bind all methods to EmailManagerGUI class
EmailManagerGUI.create_messages_tab = create_messages_tab
EmailManagerGUI.refresh_messages = refresh_messages
EmailManagerGUI.compose_message = compose_message
EmailManagerGUI.reply_message = reply_message
EmailManagerGUI.delete_message = delete_message
EmailManagerGUI.on_message_select = on_message_select
EmailManagerGUI._select_message_by_id = _select_message_by_id
EmailManagerGUI.on_message_double_click = on_message_double_click
EmailManagerGUI.show_message_context_menu = show_message_context_menu
EmailManagerGUI.mark_message_unread = mark_message_unread
EmailManagerGUI.archive_message = archive_message
EmailManagerGUI.open_messages = open_messages

# Bind notification methods
EmailManagerGUI.load_notification_user_data = load_notification_user_data
EmailManagerGUI.load_notification_preferences = load_notification_preferences
EmailManagerGUI.refresh_notifications = refresh_notifications
EmailManagerGUI.refresh_notification_statistics = refresh_notification_statistics
EmailManagerGUI.on_notification_select = on_notification_select
EmailManagerGUI.display_notification_details = display_notification_details
EmailManagerGUI.set_notification_channel_filter = set_notification_channel_filter
EmailManagerGUI.apply_notification_filters = apply_notification_filters
EmailManagerGUI.mark_current_notification_as_read = mark_current_notification_as_read
EmailManagerGUI.mark_all_notifications_as_read = mark_all_notifications_as_read
EmailManagerGUI.archive_current_notification = archive_current_notification
EmailManagerGUI.save_notification_preferences = save_notification_preferences
EmailManagerGUI.clear_old_notifications = clear_old_notifications
EmailManagerGUI.create_test_notification = create_test_notification
EmailManagerGUI.show_notifications_tab = show_notifications_tab
EmailManagerGUI.notification_preferences = notification_preferences
