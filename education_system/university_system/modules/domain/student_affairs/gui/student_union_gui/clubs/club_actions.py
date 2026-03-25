import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
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
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    

def join_selected_club(self):
    """Join the selected club"""
    selection = self.clubs_listbox.curselection()
    if not selection:
        messagebox.showwarning(_t("common.warning"), _t("student_union.clubs.select_to_join"))
        return
    
    # Get club name from selection
    club_text = self.clubs_listbox.get(selection[0])
    club_name = club_text.split(' (')[0]  # Extract name before member count
    
    response = messagebox.askyesno(_t("student_union.clubs.join_club"), _t("student_union.clubs.confirm_join", name=club_name))
    if response:
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Get club_id from the selected club
            cursor.execute('SELECT club_id FROM student_clubs WHERE club_name = ? AND status = "active"', (club_name,))
            club = cursor.fetchone()
            
            if club:
                club_id = club[0]
                # Get current user's student_id
                cursor.execute('SELECT s.student_id FROM students s JOIN users u ON s.student_id = u.username WHERE u.id = ?', (self.current_user['id'],))
                student = cursor.fetchone()
                
                if student:
                    student_id = student[0]
                    # Insert membership
                    cursor.execute('INSERT INTO club_members (club_id, student_id, join_date) VALUES (?, ?, ?)',
                                   (club_id, student_id, datetime.now().strftime('%Y-%m-%d')))
                    # Update member count
                    cursor.execute('UPDATE student_clubs SET member_count = member_count + 1 WHERE club_id = ?', (club_id,))
                    conn.commit()
                    # Get user details for email
                    cursor.execute('SELECT first_name, last_name, email FROM students WHERE student_id = ?', (student_id,))
                    user_result = cursor.fetchone()
                    conn.close()  # Close connection before sending email
                    # Send confirmation email
                    if user_result:
                        first_name, last_name, email = user_result
                        if email:
                            self.send_club_join_confirmation(club_name, email, f"{first_name} {last_name}")
                    self.update_status(_t("student_union.clubs.join_requested", name=club_name))
                    messagebox.showinfo(_t("common.success"), _t("student_union.clubs.join_success", name=club_name))
                    # Show club integration buttons
                    self.add_integration_buttons_to_club_view(club_name)
                    
        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("student_union.clubs.join_failed", error=str(e)))
        finally:
            if 'conn' in locals() and conn:
                conn.close()
            

def create_club_dialog(self):
    """Show dialog to create a new club"""
    create_window = tk.Toplevel(self.root)
    create_window.title(_t("student_union.clubs.create_title"))
    create_window.geometry("500x600")
    create_window.transient(self.root)
    create_window.grab_set()
    
    # Create club form
    form_frame = ttk.Frame(create_window)
    form_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
    
    ttk.Label(form_frame, text=_t("student_union.clubs.create_header"),
             font=('Arial', 14, 'bold')).pack(pady=10)
    
    # Form fields
    fields = {}
    
    ttk.Label(form_frame, text=_t("student_union.clubs.club_name")).pack(anchor=tk.W, pady=(10,0))
    fields['name'] = ttk.Entry(form_frame, width=50)
    fields['name'].pack(fill=tk.X, pady=(0,10))

    ttk.Label(form_frame, text=_t("common.category")).pack(anchor=tk.W)
    fields['category'] = ttk.Combobox(form_frame, values=[
        'Academic', 'Sports', 'Arts', 'Technology', 'Social', 'Volunteer', 'Other'
    ], width=47)
    fields['category'].pack(fill=tk.X, pady=(0,10))

    ttk.Label(form_frame, text=_t("common.description")).pack(anchor=tk.W)
    fields['description'] = scrolledtext.ScrolledText(form_frame, height=8, width=50)
    fields['description'].pack(fill=tk.BOTH, expand=True, pady=(0,10))
    
    # Buttons
    button_frame = ttk.Frame(form_frame)
    button_frame.pack(pady=20)
    
    def create_club():
        name = fields['name'].get().strip()
        category = fields['category'].get().strip()
        description = fields['description'].get(1.0, tk.END).strip()
        
        if not name:
            messagebox.showerror(_t("common.error"), _t("student_union.clubs.name_required"))
            return
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Check if club name already exists
            cursor.execute('SELECT COUNT(*) FROM student_clubs WHERE club_name = ?', (name,))
            if cursor.fetchone()[0] > 0:
                messagebox.showerror(_t("common.error"), _t("student_union.clubs.name_exists"))
                return
            
            # Insert new club
            cursor.execute('''
                INSERT INTO student_clubs (club_name, description, category, created_date, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, description, category, datetime.now().strftime('%Y-%m-%d'), 'active'))
            
            conn.commit()
            conn.close()
            # Send new club announcement to all students
            self.send_new_club_announcement(name, description)
            messagebox.showinfo(_t("common.success"), _t("student_union.clubs.create_success", name=name))
            create_window.destroy()
            self.refresh_clubs_list()

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("student_union.clubs.create_failed", error=str(e)))
    
    ttk.Button(button_frame, text=_t("student_union.clubs.create_btn"), command=create_club).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.cancel"), command=create_window.destroy).pack(side=tk.LEFT, padx=5)
    
    fields['name'].focus()


def join_club_gui(self):
    """GUI for joining a club"""
    dialog = ClubJoinDialog(self.master, self.auth)
    self.master.wait_window(dialog.dialog)
    
    if dialog.result:
        self.update_status("Joined club successfully")
        # Refresh club list
        self.view_my_clubs()


def create_club_gui(self):
    """GUI for creating a club"""
    dialog = ClubCreateDialog(self.master, self.auth)
    self.master.wait_window(dialog.dialog)
    
    if dialog.result:
        self.update_status("Club created successfully")
        # Refresh club list
        self.view_clubs()


def manage_club_gui(self):
    """GUI for managing clubs"""
    dialog = ClubManageDialog(self.master, self.auth)
    self.master.wait_window(dialog.dialog)

# Event Management GUI Methods

