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
    

def show_clubs_content(self):
    """Display clubs in main content area"""
    self.clear_content()
    clubs_frame = ttk.Frame(self.content_frame)
    clubs_frame.pack(fill=tk.BOTH, expand=True)
    # Create and display clubs content without notebook
    self._render_clubs_tab(clubs_frame)


def _render_clubs_tab(self, parent_frame):
    """Render clubs content in the provided parent frame"""
    # Create paned window for clubs
    clubs_paned = ttk.PanedWindow(parent_frame, orient=tk.HORIZONTAL)
    clubs_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    # Left panel - Club list
    left_panel = ttk.Frame(clubs_paned)
    clubs_paned.add(left_panel, weight=1)
    ttk.Label(left_panel, text=_t("student_union.clubs.title"), font=('Arial', 12, 'bold')).pack(pady=5)
    # Club list with scrollbar
    list_frame = ttk.Frame(left_panel)
    list_frame.pack(fill=tk.BOTH, expand=True)
    scrollbar = ttk.Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    self.clubs_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
    self.clubs_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=self.clubs_listbox.yview)
    # Bind selection event
    self.clubs_listbox.bind('<<ListboxSelect>>', self.on_club_select)
    # Club action buttons
    club_buttons_frame = ttk.Frame(left_panel)
    club_buttons_frame.pack(fill=tk.X, pady=5)
    ttk.Button(club_buttons_frame, text=_t("common.refresh"),
              command=self.refresh_clubs_list).pack(side=tk.LEFT, padx=2)
    ttk.Button(club_buttons_frame, text=_t("student_union.clubs.join_club"),
              command=self.join_selected_club).pack(side=tk.LEFT, padx=2)
    ttk.Button(club_buttons_frame, text=_t("student_union.clubs.create_club"),
              command=self.create_club_dialog).pack(side=tk.LEFT, padx=2)
    # Right panel - Club details
    right_panel = ttk.Frame(clubs_paned)
    clubs_paned.add(right_panel, weight=2)
    ttk.Label(right_panel, text=_t("student_union.clubs.club_details"), font=('Arial', 12, 'bold')).pack(pady=5)
    # Club details text area
    self.club_details_text = scrolledtext.ScrolledText(right_panel, height=20, width=50)
    self.club_details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    # Load clubs initially
    self.refresh_clubs_list()


def show_clubs_tab(self):
    """Legacy method for backwards compatibility - creates tab in notebook if exists"""
    if hasattr(self, 'notebook') and self.notebook:
        clubs_frame = ttk.Frame(self.notebook)
        self.notebook.add(clubs_frame, text=_t("student_union.clubs.tab_title"))
        self._render_clubs_tab(clubs_frame)
    else:
        # Fall back to content display
        self.show_clubs_content()


def refresh_clubs_list(self):
    """Refresh the clubs list"""
    self.clubs_listbox.delete(0, tk.END)
    
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT club_id, club_name, member_count, status
            FROM student_clubs 
            WHERE status = 'active'
            ORDER BY club_name
        ''')
        
        clubs = cursor.fetchall()
        
        for club in clubs:
            display_text = f"{club[1]} ({club[2]} members)"
            self.clubs_listbox.insert(tk.END, display_text)
            
        conn.close()
        self.update_status(_t("student_union.clubs.loaded_clubs", count=len(clubs)))

    except sqlite3.Error as e:
        messagebox.showerror(_t("common.database_error"), _t("student_union.clubs.load_failed", error=str(e)))


def on_club_select(self, event):
    """Handle club selection"""
    selection = self.clubs_listbox.curselection()
    if not selection:
        return
    
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT c.club_name, c.description, c.category, c.member_count, c.status,
                   c.created_date, p.first_name || ' ' || p.last_name as president,
                   t.first_name || ' ' || t.last_name as treasurer,
                   s.first_name || ' ' || s.last_name as secretary
            FROM student_clubs c
            LEFT JOIN students p ON c.president_id = p.student_id
            LEFT JOIN students t ON c.treasurer_id = t.student_id  
            LEFT JOIN students s ON c.secretary_id = s.student_id
            WHERE c.status = 'active'
            ORDER BY c.club_name
            LIMIT 1 OFFSET ?
        ''', (selection[0],))
        
        club = cursor.fetchone()
        
        if club:
            details = f"{_t('student_union.clubs.club_name_label')}: {club[0]}\n"
            details += f"{_t('student_union.clubs.category_label')}: {club[2] or _t('common.not_specified')}\n"
            details += f"{_t('student_union.clubs.members_label')}: {club[3]}\n"
            details += f"{_t('student_union.clubs.status_label')}: {club[4]}\n"
            details += f"{_t('student_union.clubs.created_label')}: {club[5] or _t('common.unknown')}\n\n"
            details += f"{_t('student_union.clubs.officers_label')}:\n"
            details += f"  {_t('student_union.clubs.president_label')}: {club[6] or _t('student_union.clubs.vacant')}\n"
            details += f"  {_t('student_union.clubs.treasurer_label')}: {club[7] or _t('student_union.clubs.vacant')}\n"
            details += f"  {_t('student_union.clubs.secretary_label')}: {club[8] or _t('student_union.clubs.vacant')}\n\n"
            details += f"{_t('student_union.clubs.description_label')}:\n{club[1] or _t('student_union.clubs.no_description')}"
            
            self.club_details_text.delete(1.0, tk.END)
            self.club_details_text.insert(1.0, details)
        
        conn.close()
        
    except sqlite3.Error as e:
        messagebox.showerror(_t("common.database_error"), _t("student_union.clubs.load_details_failed", error=str(e)))


def create_clubs_tab(self):
    """Create clubs management tab"""
    clubs_frame = ttk.Frame(self.notebook)
    self.notebook.add(clubs_frame, text=_t("student_union.clubs.clubs_societies"))
    # Left panel - Actions
    left_panel = ttk.LabelFrame(clubs_frame, text=_t("student_union.clubs.club_actions"))
    left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)
    # Buttons
    ttk.Button(left_panel, text=_t("student_union.clubs.view_all_clubs"),
              command=self.view_clubs).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.clubs.my_clubs"),
              command=self.view_my_clubs).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.clubs.join_club"),
              command=self.join_club_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.clubs.create_club"),
              command=self.create_club_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.clubs.manage_club"),
              command=self.manage_club_gui).pack(fill='x', pady=2)
    ttk.Separator(left_panel, orient='horizontal').pack(fill='x', pady=10)
    ttk.Button(left_panel, text=_t("student_union.clubs.club_directory"),
              command=self.club_member_directory).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.clubs.club_discussions"),
              command=self.manage_club_discussions).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.clubs.club_media"),
              command=self.manage_club_media).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.clubs.book_clubs"),
              command=self.manage_book_clubs).pack(fill='x', pady=2)
    # Right panel - Display area
    right_panel = ttk.LabelFrame(clubs_frame, text=_t("student_union.clubs.club_information"))
    right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)
    # Scrollable text area for displaying results
    self.clubs_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD,
                                               height=30, width=80)
    self.clubs_text.pack(fill='both', expand=True, padx=5, pady=5)


def view_clubs(self):
    """GUI wrapper for viewing clubs"""
    self.update_status(_t("student_union.clubs.loading_clubs"))

    def callback(output, result):
        self.display_result(self.clubs_text, output)
        self.update_status(_t("student_union.clubs.clubs_loaded"))
    
    self.run_in_thread(student_union_cli.view_clubs, callback)


def view_my_clubs(self):
    """GUI wrapper for viewing my clubs"""
    self.update_status(_t("student_union.clubs.loading_my_clubs"))

    def callback(output, result):
        self.display_result(self.clubs_text, output)
        self.update_status(_t("student_union.clubs.my_clubs_loaded"))
    
    self.run_in_thread(student_union_cli.view_my_clubs, callback)


