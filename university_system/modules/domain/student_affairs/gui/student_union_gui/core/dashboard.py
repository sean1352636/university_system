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
    print(_t("student_union.finance_integration_unavailable"))

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from university_system.infrastructure.database.db import get_connection
    from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print(_t("student_union.cli_system_unavailable"))
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    

def show_main_dashboard(self):
    """Display the main dashboard with sidebar navigation"""
    # Simply show the dashboard content (sidebar is already built)
    self.show_dashboard_content()


def show_dashboard_content(self):
    """Display dashboard in main content area"""
    self.clear_content()
    dashboard_frame = ttk.Frame(self.content_frame)
    dashboard_frame.pack(fill=tk.BOTH, expand=True)
    # Create and display dashboard content without notebook
    self._render_dashboard_tab(dashboard_frame)


def _render_dashboard_tab(self, parent_frame):
    """Render dashboard content in the provided parent frame"""
    # Check if GUI was properly initialized
    if not self.initialized or not self.current_user:
        ttk.Label(parent_frame, text=_t("student_union.dashboard.auth_required"),
                 font=('Arial', 12)).pack(pady=20)
        return
    # Welcome section
    welcome_frame = ttk.LabelFrame(parent_frame, text=_t("common.welcome"))
    welcome_frame.pack(fill=tk.X, padx=10, pady=5)
    welcome_text = _t("student_union.dashboard.welcome_back", username=self.current_user['username'])
    ttk.Label(welcome_frame, text=welcome_text, font=('Arial', 12)).pack(pady=10)
    # Quick stats
    stats_frame = ttk.LabelFrame(parent_frame, text=_t("student_union.dashboard.quick_statistics"))
    stats_frame.pack(fill=tk.X, padx=10, pady=5)
    stats_content = ttk.Frame(stats_frame)
    stats_content.pack(fill=tk.X, padx=10, pady=10)
    # Get statistics from database
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        # Get various counts
        cursor.execute('SELECT COUNT(*) FROM student_clubs WHERE status = "active"')
        active_clubs = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM union_events WHERE status = "upcoming"')
        upcoming_events = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM students')
        total_students = cursor.fetchone()[0]
        # Display stats in a grid
        ttk.Label(stats_content, text=_t("student_union.dashboard.active_clubs"), font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=10)
        ttk.Label(stats_content, text=str(active_clubs)).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(stats_content, text=_t("student_union.dashboard.upcoming_events"), font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky=tk.W, padx=10)
        ttk.Label(stats_content, text=str(upcoming_events)).grid(row=1, column=1, sticky=tk.W)
        ttk.Label(stats_content, text=_t("student_union.dashboard.total_students"), font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, padx=10)
        ttk.Label(stats_content, text=str(total_students)).grid(row=2, column=1, sticky=tk.W)
        conn.close()
    except sqlite3.Error as e:
        ttk.Label(stats_content, text=_t("student_union.dashboard.error_loading_stats", error=str(e))).pack()
    # Quick actions
    actions_frame = ttk.LabelFrame(parent_frame, text=_t("student_union.dashboard.quick_actions"))
    actions_frame.pack(fill=tk.X, padx=10, pady=5)
    actions_content = ttk.Frame(actions_frame)
    actions_content.pack(fill=tk.X, padx=10, pady=10)
    ttk.Button(actions_content, text=_t("student_union.dashboard.view_my_clubs"),
              command=self.show_clubs_content).pack(side=tk.LEFT, padx=5)
    ttk.Button(actions_content, text=_t("student_union.dashboard.browse_events"),
              command=self.show_events_content).pack(side=tk.LEFT, padx=5)
    ttk.Button(actions_content, text=_t("student_union.dashboard.book_facility"),
              command=self.show_facilities_content).pack(side=tk.LEFT, padx=5)


def show_dashboard_tab(self):
    """Legacy method for backwards compatibility - creates tab in notebook if exists"""
    if hasattr(self, 'notebook') and self.notebook:
        dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(dashboard_frame, text=_t("student_union.tabs.dashboard"))
        self._render_dashboard_tab(dashboard_frame)
    else:
        # Fall back to content display
        self.show_dashboard_content()


