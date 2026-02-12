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
from university_system.core.sql_safety import validate_table_name

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
    

def show_profile(self):
    """Show user profile"""
    # Check if GUI was properly initialized
    if not self.initialized or not self.current_user:
        messagebox.showerror(_t("common.error"), _t("auth.login_required", action="view profile"))
        return
    profile_window = tk.Toplevel(self.root)
    profile_window.title(_t("student_union.profile.title"))
    profile_window.geometry("400x300")
    profile_window.transient(self.root)
    profile_window.grab_set()
    profile_frame = ttk.Frame(profile_window)
    profile_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    ttk.Label(profile_frame, text=_t("student_union.profile.title"), font=('Arial', 14, 'bold')).pack(pady=10)
    # Profile information
    info_frame = ttk.Frame(profile_frame)
    info_frame.pack(fill=tk.X, pady=10)
    ttk.Label(info_frame, text=_t("auth.username"), font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)
    ttk.Label(info_frame, text=self.current_user['username']).grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

    ttk.Label(info_frame, text=_t("student_union.profile.email"), font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)
    ttk.Label(info_frame, text=self.current_user['email'] or _t("student_union.profile.not_set")).grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

    ttk.Label(info_frame, text=_t("student_union.profile.role"), font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=5)
    ttk.Label(info_frame, text=self.current_user['role'].title()).grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)

    # Buttons
    button_frame = ttk.Frame(profile_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text=_t("auth.change_password"), command=self.change_password).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.close"), command=profile_window.destroy).pack(side=tk.LEFT, padx=5)
# ====================================================================
# NEW FEATURE INTEGRATION METHODS
# ====================================================================


def change_password(self):
    """Change user password"""
    password_window = tk.Toplevel(self.root)
    password_window.title(_t("auth.change_password"))
    password_window.geometry("350x250")
    password_window.transient(self.root)
    password_window.grab_set()

    form_frame = ttk.Frame(password_window)
    form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    ttk.Label(form_frame, text=_t("auth.change_password"), font=('Arial', 12, 'bold')).pack(pady=10)

    # Current password
    ttk.Label(form_frame, text=_t("auth.current_password")).pack(anchor=tk.W, pady=(10,0))
    current_pw_entry = ttk.Entry(form_frame, show="*", width=30)
    current_pw_entry.pack(fill=tk.X, pady=(0,10))

    # New password
    ttk.Label(form_frame, text=_t("auth.new_password")).pack(anchor=tk.W)
    new_pw_entry = ttk.Entry(form_frame, show="*", width=30)
    new_pw_entry.pack(fill=tk.X, pady=(0,10))

    # Confirm new password
    ttk.Label(form_frame, text=_t("auth.confirm_password")).pack(anchor=tk.W)
    confirm_pw_entry = ttk.Entry(form_frame, show="*", width=30)
    confirm_pw_entry.pack(fill=tk.X, pady=(0,20))
    
    def update_password():
        current_pw = current_pw_entry.get()
        new_pw = new_pw_entry.get()
        confirm_pw = confirm_pw_entry.get()
        
        if not all([current_pw, new_pw, confirm_pw]):
            messagebox.showerror(_t("common.error"), _t("auth.all_fields_required"))
            return

        if new_pw != confirm_pw:
            messagebox.showerror(_t("common.error"), _t("auth.passwords_dont_match"))
            return

        if len(new_pw) < 6:
            messagebox.showerror(_t("common.error"), _t("student_union.profile.password_min_length"))
            return
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Verify current password
            current_hash = hashlib.sha256(current_pw.encode()).hexdigest()
            cursor.execute('SELECT id FROM users WHERE id = ? AND password_hash = ?', 
                         (self.current_user['id'], current_hash))
            
            if not cursor.fetchone():
                messagebox.showerror(_t("common.error"), _t("auth.current_password_incorrect"))
                return
            
            # Update password
            new_hash = hashlib.sha256(new_pw.encode()).hexdigest()
            cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', 
                         (new_hash, self.current_user['id']))
            
            conn.commit()
            conn.close()

            messagebox.showinfo(_t("common.success"), _t("auth.password_changed"))
            password_window.destroy()

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("student_union.profile.password_change_failed", error=str(e)))
    
    # Buttons
    button_frame = ttk.Frame(form_frame)
    button_frame.pack()
    
    ttk.Button(button_frame, text=_t("student_union.profile.update_password"), command=update_password).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.cancel"), command=password_window.destroy).pack(side=tk.LEFT, padx=5)
    
    current_pw_entry.focus()


def show_database_info(self):
    """Show database information"""
    info_window = tk.Toplevel(self.root)
    info_window.title(_t("student_union.profile.db_info_title"))
    info_window.geometry("500x400")
    info_window.transient(self.root)
    
    info_text = scrolledtext.ScrolledText(info_window, height=20, width=60)
    info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        
        info = _t("student_union.profile.db_info_header") + "\n"
        info += "=" * 30 + "\n\n"

        # Database schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        info += _t("student_union.profile.db_tables") + "\n"
        for table in tables:
            table_name = table[0]
            safe_table = validate_table_name(table_name, conn=conn)
            cursor.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
            count = cursor.fetchone()[0]
            info += f"  {table_name}: {count} records\n"

            # Show table structure
            cursor.execute("PRAGMA table_info([" + safe_table + "])")
            columns = cursor.fetchall()
            info += "    Columns: "
            info += ", ".join([col[1] for col in columns])
            info += "\n\n"
        
        info_text.insert(1.0, info)
        conn.close()
        
    except sqlite3.Error as e:
        info_text.insert(1.0, _t("student_union.profile.db_info_error", error=str(e)))


def show_about(self):
    """Show about dialog"""
    about_text = _t("student_union.profile.about_text")

    messagebox.showinfo(_t("student_union.profile.about_title"), about_text)


