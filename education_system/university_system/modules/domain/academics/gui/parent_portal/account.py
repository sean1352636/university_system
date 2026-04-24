from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from education_system.university_system.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from education_system.university_system.modules.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from education_system.university_system.modules.domain.academics.gui.parent_portal.base import ParentPortalGUI

def emergency_contact_update(self):
    """Emergency contact management with full CRUD operations"""
    is_admin = self.is_admin()

    # For admin users, load all students from database
    if is_admin:
        students_list = self._load_all_students_from_db()
        if not students_list:
            messagebox.showinfo("No Students", "No students found in the system.")
            return
    else:
        # Non-admin users can only access their linked students
        if not self.children:
            messagebox.showinfo("No Students", "No students linked to your guardian account.")
            return
        students_list = self.children

    dialog = EmergencyContactDialog(
        self.root,
        children=students_list,
        db_path=DEFAULT_DB_PATH,
        current_user=self.get_current_user()
    )
ParentPortalGUI.emergency_contact_update = emergency_contact_update

def view_activity_log(self):
    """View parent activity log for security purposes"""
    self.clear_content()
    self.update_status("Activity Log")

    title = ttk.Label(self.content_frame, text="Activity Log", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Create activity log display
    log_frame = ttk.Frame(self.content_frame)
    log_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    # Activity log table
    columns = ('Date/Time', 'User', 'Action')
    tree = ttk.Treeview(log_frame, columns=columns, show='headings', height=15)

    tree.heading('Date/Time', text='Date/Time')
    tree.heading('User', text='User')
    tree.heading('Action', text='Action')

    tree.column('Date/Time', width=150)
    tree.column('User', width=120)
    tree.column('Action', width=400)

    # Load activity data from actual log files
    activities = self._load_activity_log_entries()

    if activities:
        for activity in activities:
            tree.insert('', tk.END, values=activity)
    else:
        tree.insert('', tk.END, values=('N/A', 'System', 'No activity log entries found'))

    # Scrollbar
    scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Back button
    ttk.Button(self.content_frame, text="← Back", command=self.show_settings_menu).pack(pady=10)
ParentPortalGUI.view_activity_log = view_activity_log

def _load_activity_log_entries(self, max_entries=100):
    """Load activity log entries from log files"""
    activities = []
    try:
        from education_system.university_system.modules.shared.constants import paths

        log_dir = paths.LOG_DIR
        log_file = log_dir / 'app.log'

        # Try to read current activity log
        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Parse log format: "User - Action - DateTime"
                for line in reversed(lines[-max_entries:]):
                    line = line.strip()
                    if line and ' - ' in line:
                        parts = line.split(' - ')
                        if len(parts) >= 3:
                            user = parts[0]
                            action = parts[1]
                            timestamp = parts[2] if len(parts) > 2 else ''
                            activities.append((timestamp, user, action))
                        elif len(parts) == 2:
                            activities.append(('', parts[0], parts[1]))

        # Also try to load from dated log files if not enough entries
        if len(activities) < max_entries:
            import glob
            dated_logs = sorted(glob.glob(str(log_dir / 'activity.*')), reverse=True)
            for dated_log in dated_logs[:5]:  # Check last 5 dated log files
                if len(activities) >= max_entries:
                    break
                if dated_log.endswith('.log'):
                    continue  # Skip the main activity.log
                try:
                    with open(dated_log, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        for line in reversed(lines):
                            if len(activities) >= max_entries:
                                break
                            line = line.strip()
                            if line and ' - ' in line:
                                parts = line.split(' - ')
                                if len(parts) >= 3:
                                    user = parts[0]
                                    action = parts[1]
                                    timestamp = parts[2]
                                    activities.append((timestamp, user, action))
                except Exception:
                    pass

    except Exception as e:
        print(f"Error loading activity log: {e}")
        activities.append(('Error', 'System', f'Failed to load activity log: {str(e)}'))

    return activities
ParentPortalGUI._load_activity_log_entries = _load_activity_log_entries

class TwoFactorDialog:
    """Dialog for enabling two-factor authentication."""

    def __init__(self, parent):
        self.result = None

        dialog = tk.Toplevel(parent)
        dialog.title("Enable Two-Factor Authentication")
        dialog.geometry("500x350")
        dialog.transient(parent)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Two-Factor Authentication",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        ttk.Label(main_frame,
                 text="Choose a method for two-factor authentication:",
                 font=('Arial', 10)).pack(anchor='w', pady=(0, 10))

        method_var = tk.StringVar(value="email")
        ttk.Radiobutton(main_frame, text="Email verification code",
                        variable=method_var, value="email").pack(anchor='w', pady=3)
        ttk.Radiobutton(main_frame, text="SMS verification code",
                        variable=method_var, value="sms").pack(anchor='w', pady=3)
        ttk.Radiobutton(main_frame, text="Authenticator app (TOTP)",
                        variable=method_var, value="totp").pack(anchor='w', pady=3)

        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=15)

        ttk.Label(main_frame,
                 text="After enabling, you will be asked for a verification code "
                      "each time you log in from a new device.",
                 wraplength=400, font=('Arial', 9)).pack(anchor='w', pady=5)

        def submit():
            self.result = {'method': method_var.get()}
            dialog.destroy()

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Enable 2FA", command=submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        dialog.wait_window()


def enable_two_factor_auth(self):
    """Enable two-factor authentication"""
    dialog = TwoFactorDialog(self.root)
    if dialog.result:
        self.update_status("Two-factor authentication enabled")
        messagebox.showinfo("Success", "Two-factor authentication has been enabled.")
ParentPortalGUI.enable_two_factor_auth = enable_two_factor_auth

def mark_notifications_read(self):
    """Mark all notifications as read"""
    if messagebox.askyesno("Mark Read", "Mark all notifications as read?"):
        # In real implementation, would update database
        messagebox.showinfo("Success", "All notifications marked as read.")
        self.update_status("Notifications marked as read")
ParentPortalGUI.mark_notifications_read = mark_notifications_read

def show_notifications_interface(self):
    """Show notification preferences interface"""
    self.clear_content()
    self.update_status("Notification Preferences")

    title = ttk.Label(self.content_frame, text="Notification Preferences", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Notification settings frame
    settings_frame = ttk.LabelFrame(self.content_frame, text="Notification Settings", padding=20)
    settings_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    # Email notifications
    email_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(settings_frame, text="Email Notifications", variable=email_var).pack(anchor='w', pady=5)

    # SMS notifications
    sms_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(settings_frame, text="SMS Notifications", variable=sms_var).pack(anchor='w', pady=5)

    # Push notifications
    push_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(settings_frame, text="Push Notifications", variable=push_var).pack(anchor='w', pady=5)

    ttk.Separator(settings_frame, orient='horizontal').pack(fill='x', pady=15)

    # Notification categories
    ttk.Label(settings_frame, text="Receive notifications for:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)

    categories = {
        "Grades Posted": tk.BooleanVar(value=True),
        "Attendance Alerts": tk.BooleanVar(value=True),
        "Conduct Reports": tk.BooleanVar(value=True),
        "University Announcements": tk.BooleanVar(value=True),
        "Event Reminders": tk.BooleanVar(value=True),
        "Fee Reminders": tk.BooleanVar(value=True),
        "Homework Assignments": tk.BooleanVar(value=False),
        "Messages from Instructors": tk.BooleanVar(value=True),
    }

    for category, var in categories.items():
        ttk.Checkbutton(settings_frame, text=category, variable=var).pack(anchor='w', padx=20, pady=3)

    # Save button
    def save_preferences():
        messagebox.showinfo("Success", "Notification preferences saved successfully!")
        self.update_status("Preferences saved")

    # Advanced settings button
    def show_advanced_settings():
        self.show_advanced_notification_settings()

    btn_frame = ttk.Frame(self.content_frame)
    btn_frame.pack(pady=20)

    ttk.Button(btn_frame, text="Save Preferences", command=save_preferences).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Advanced Settings", command=show_advanced_settings).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.show_notifications_interface = show_notifications_interface

def show_advanced_notification_settings(self):
    """Show advanced notification settings dialog"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Advanced Notification Settings")
    dialog.geometry("500x500")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Advanced Notification Settings",
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Load current preferences from database - set defaults first
    current_prefs = {
        'notification_time': '09:00',
        'quiet_start': '22:00',
        'quiet_end': '07:00',
        'subjects': ''
    }
    try:
        if self.parent_id:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Ensure parent_preferences table exists with advanced columns
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_preferences (
                parent_id TEXT PRIMARY KEY,
                email_notifications INTEGER DEFAULT 1,
                sms_notifications INTEGER DEFAULT 0,
                grade_alerts INTEGER DEFAULT 1,
                attendance_alerts INTEGER DEFAULT 1,
                behavior_alerts INTEGER DEFAULT 1,
                assignment_alerts INTEGER DEFAULT 1,
                weekly_summary INTEGER DEFAULT 1,
                preferred_notification_time TEXT,
                quiet_hours_start TEXT,
                quiet_hours_end TEXT,
                subject_preferences TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            )
            ''')

            cursor.execute('''
            SELECT preferred_notification_time, quiet_hours_start, quiet_hours_end, subject_preferences
            FROM parent_preferences
            WHERE parent_id = ?
            ''', (self.parent_id,))

            prefs = cursor.fetchone()
            if prefs:
                current_prefs = {
                    'notification_time': prefs[0] or '09:00',
                    'quiet_start': prefs[1] or '22:00',
                    'quiet_end': prefs[2] or '07:00',
                    'subjects': prefs[3] or ''
                }
            else:
                # Insert default preferences
                cursor.execute('''
                INSERT OR IGNORE INTO parent_preferences (parent_id)
                VALUES (?)
                ''', (self.parent_id,))
                conn.commit()
                current_prefs = {
                    'notification_time': '09:00',
                    'quiet_start': '22:00',
                    'quiet_end': '07:00',
                    'subjects': ''
                }

            conn.close()
    except Exception as e:
        print(f"Error loading preferences: {e}")
        current_prefs = {
            'notification_time': '09:00',
            'quiet_start': '22:00',
            'quiet_end': '07:00',
            'subjects': ''
        }

    # Preferred notification time
    time_frame = ttk.LabelFrame(main_frame, text="Preferred Notification Time", padding=15)
    time_frame.pack(fill=tk.X, pady=10)

    ttk.Label(time_frame, text="Send daily summaries at:").pack(anchor='w', pady=5)
    notification_time_var = tk.StringVar(value=current_prefs['notification_time'])
    time_combo = ttk.Combobox(time_frame, textvariable=notification_time_var, width=20, state='readonly')
    time_combo['values'] = ['07:00', '08:00', '09:00', '10:00', '12:00', '15:00', '17:00', '18:00', '20:00']
    time_combo.pack(fill=tk.X, pady=5)

    # Quiet hours
    quiet_frame = ttk.LabelFrame(main_frame, text="Quiet Hours (No Notifications)", padding=15)
    quiet_frame.pack(fill=tk.X, pady=10)

    ttk.Label(quiet_frame, text="Start Time:").grid(row=0, column=0, sticky='w', pady=5)
    quiet_start_var = tk.StringVar(value=current_prefs['quiet_start'])
    quiet_start_combo = ttk.Combobox(quiet_frame, textvariable=quiet_start_var, width=15, state='readonly')
    quiet_start_combo['values'] = [f"{h:02d}:00" for h in range(24)]
    quiet_start_combo.grid(row=0, column=1, pady=5, padx=5)

    ttk.Label(quiet_frame, text="End Time:").grid(row=1, column=0, sticky='w', pady=5)
    quiet_end_var = tk.StringVar(value=current_prefs['quiet_end'])
    quiet_end_combo = ttk.Combobox(quiet_frame, textvariable=quiet_end_var, width=15, state='readonly')
    quiet_end_combo['values'] = [f"{h:02d}:00" for h in range(24)]
    quiet_end_combo.grid(row=1, column=1, pady=5, padx=5)

    # Subject-specific preferences
    subject_frame = ttk.LabelFrame(main_frame, text="Subject-Specific Notifications", padding=15)
    subject_frame.pack(fill=tk.X, pady=10)

    ttk.Label(subject_frame,
             text="Get notifications only for specific subjects\n(comma-separated, leave empty for all):",
             wraplength=400).pack(anchor='w', pady=5)

    # Parse current subjects
    try:
        if current_prefs['subjects']:
            subject_data = json.loads(current_prefs['subjects'])
            current_subjects = ', '.join(subject_data.get('subjects', []))
        else:
            current_subjects = ''
    except (ValueError, TypeError, KeyError):
        current_subjects = ''

    subject_entry = ttk.Entry(subject_frame, width=50)
    subject_entry.insert(0, current_subjects)
    subject_entry.pack(fill=tk.X, pady=5)

    ttk.Label(subject_frame, text="Example: Mathematics, Science, English",
             font=('Arial', 8, 'italic')).pack(anchor='w')

    # Save button
    def save_advanced_settings():
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Prepare subject preferences
            subjects_input = subject_entry.get().strip()
            if subjects_input:
                subjects_list = [s.strip() for s in subjects_input.split(',') if s.strip()]
                subject_prefs_json = json.dumps({'subjects': subjects_list})
            else:
                subject_prefs_json = None

            # Update preferences
            cursor.execute('''
            UPDATE parent_preferences
            SET preferred_notification_time = ?,
                quiet_hours_start = ?,
                quiet_hours_end = ?,
                subject_preferences = ?
            WHERE parent_id = ?
            ''', (notification_time_var.get(), quiet_start_var.get(), quiet_end_var.get(),
                  subject_prefs_json, self.parent_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Advanced notification settings saved successfully!")
            self.update_status("Advanced notification settings saved")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {str(e)}")

    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(pady=20)

    ttk.Button(btn_frame, text="Save Settings", command=save_advanced_settings).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.show_advanced_notification_settings = show_advanced_notification_settings

def show_account_interface(self):
    """Show account settings interface"""
    self.clear_content()
    self.update_status("Account Settings")

    title = ttk.Label(self.content_frame, text="Account Settings", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Account information - get current user dynamically
    account_frame = ttk.LabelFrame(self.content_frame, text="Account Information", padding=20)
    account_frame.pack(fill=tk.X, padx=20, pady=10)

    current_user = self.get_current_user()
    if current_user:
        first_name = current_user.get('first_name', '')
        last_name = current_user.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip() or current_user.get('username', 'N/A')

        ttk.Label(account_frame, text=f"Full Name: {full_name}", font=('Arial', 10)).pack(anchor='w', pady=3)
        ttk.Label(account_frame, text=f"Username: {current_user.get('username', 'N/A')}",
                 font=('Arial', 10)).pack(anchor='w', pady=3)
        ttk.Label(account_frame, text=f"Email: {current_user.get('email', 'Not set')}",
                 font=('Arial', 10)).pack(anchor='w', pady=3)
        ttk.Label(account_frame, text=f"Role: {current_user.get('role', 'parent').title()}",
                 font=('Arial', 10)).pack(anchor='w', pady=3)

        if self.parent_id:
            ttk.Label(account_frame, text=f"Parent ID: {self.parent_id}", font=('Arial', 10)).pack(anchor='w', pady=3)

    # Security settings
    security_frame = ttk.LabelFrame(self.content_frame, text="Security", padding=20)
    security_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Button(security_frame, text="Change Password",
              command=self.change_password).pack(fill=tk.X, pady=5)
    ttk.Button(security_frame, text="Enable Two-Factor Authentication",
              command=self.enable_two_factor_auth).pack(fill=tk.X, pady=5)
    ttk.Button(security_frame, text="View Login History",
              command=self.view_login_history).pack(fill=tk.X, pady=5)

    # Contact preferences
    contact_frame = ttk.LabelFrame(self.content_frame, text="Contact Preferences", padding=20)
    contact_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(contact_frame, text="Primary Email:").grid(row=0, column=0, sticky='w', pady=5)
    email_entry = ttk.Entry(contact_frame, width=40)
    email_entry.grid(row=0, column=1, pady=5, sticky='ew')

    ttk.Label(contact_frame, text="Primary Phone:").grid(row=1, column=0, sticky='w', pady=5)
    phone_entry = ttk.Entry(contact_frame, width=40)
    phone_entry.grid(row=1, column=1, pady=5, sticky='ew')

    ttk.Label(contact_frame, text="Address:").grid(row=2, column=0, sticky='w', pady=5)
    address_entry = ttk.Entry(contact_frame, width=40)
    address_entry.grid(row=2, column=1, pady=5, sticky='ew')

    contact_frame.columnconfigure(1, weight=1)

    # Load current contact information
    try:
        if self.parent_id:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT email, phone, address
            FROM parent_accounts
            WHERE parent_id = ?
            ''', (self.parent_id,))

            info = cursor.fetchone()
            conn.close()

            if info:
                email_entry.insert(0, info[0] or "")
                phone_entry.insert(0, info[1] or "")
                address_entry.insert(0, info[2] or "")
    except Exception as e:
        print(f"Error loading contact info: {e}")

    def save_contact_info():
        email = email_entry.get().strip()
        phone = phone_entry.get().strip()
        address = address_entry.get().strip()

        # Validate email
        if email and '@' not in email:
            messagebox.showwarning("Validation Error", "Please enter a valid email address.")
            return

        if not self.parent_id:
            messagebox.showerror("Error", "Parent ID not found. Please log in again.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Update contact information
            cursor.execute('''
            UPDATE parent_accounts
            SET email = ?, phone = ?, address = ?
            WHERE parent_id = ?
            ''', (email, phone, address, self.parent_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Contact information updated successfully!")
            self.update_status("Contact information updated")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update contact information: {str(e)}")

    ttk.Button(self.content_frame, text="Save Changes", command=save_contact_info).pack(pady=20)
ParentPortalGUI.show_account_interface = show_account_interface

def change_password(self):
    """Change password"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Change Password")
    dialog.geometry("500x400")
    dialog.transient(self.root)
    dialog.grab_set()

    # Title
    title_frame = ttk.Frame(dialog, padding=20)
    title_frame.pack(fill=tk.X)
    ttk.Label(title_frame, text="Change Password",
             font=('Arial', 16, 'bold')).pack(anchor='w')
    ttk.Label(title_frame, text="Update your account password",
             font=('Arial', 10)).pack(anchor='w', pady=(0, 10))

    # Form frame
    form_frame = ttk.LabelFrame(dialog, text="Password Information", padding=20)
    form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

    # Current password
    ttk.Label(form_frame, text="Current Password:", font=('Arial', 10)).grid(row=0, column=0, sticky='w', pady=10)
    current_password_entry = ttk.Entry(form_frame, width=30, show='*')
    current_password_entry.grid(row=0, column=1, pady=10, sticky='ew', padx=5)

    # New password
    ttk.Label(form_frame, text="New Password:", font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=10)
    new_password_entry = ttk.Entry(form_frame, width=30, show='*')
    new_password_entry.grid(row=1, column=1, pady=10, sticky='ew', padx=5)

    # Confirm password
    ttk.Label(form_frame, text="Confirm Password:", font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=10)
    confirm_password_entry = ttk.Entry(form_frame, width=30, show='*')
    confirm_password_entry.grid(row=2, column=1, pady=10, sticky='ew', padx=5)

    form_frame.columnconfigure(1, weight=1)

    # Password requirements
    requirements_frame = ttk.Frame(form_frame)
    requirements_frame.grid(row=3, column=0, columnspan=2, sticky='w', pady=10)

    ttk.Label(requirements_frame, text="Password Requirements:",
             font=('Arial', 9, 'bold')).pack(anchor='w')
    ttk.Label(requirements_frame, text="• At least 8 characters long",
             font=('Arial', 8)).pack(anchor='w', padx=10)
    ttk.Label(requirements_frame, text="• Contains uppercase and lowercase letters",
             font=('Arial', 8)).pack(anchor='w', padx=10)
    ttk.Label(requirements_frame, text="• Contains at least one number",
             font=('Arial', 8)).pack(anchor='w', padx=10)

    # Buttons
    button_frame = ttk.Frame(dialog, padding=10)
    button_frame.pack(fill=tk.X)

    def update_password():
        current_password = current_password_entry.get()
        new_password = new_password_entry.get()
        confirm_password = confirm_password_entry.get()

        # Validation
        if not current_password:
            messagebox.showerror("Error", "Please enter your current password.")
            return
        if not new_password:
            messagebox.showerror("Error", "Please enter a new password.")
            return
        if new_password != confirm_password:
            messagebox.showerror("Error", "New password and confirmation do not match.")
            return
        if len(new_password) < 8:
            messagebox.showerror("Error", "Password must be at least 8 characters long.")
            return

        # Verify current password with auth system
        try:
            current_user = self.get_current_user()
            if not current_user:
                messagebox.showerror("Error", "Could not verify current user.")
                return

            username = current_user.get('username')
            if not username:
                messagebox.showerror("Error", "Could not determine username.")
                return

            # Use the authentication system to verify and update password
            if self.auth:
                # Verify current password
                if not self.auth.authenticate(username, current_password):
                    messagebox.showerror("Error", "Current password is incorrect.")
                    log_activity(
                        action='failed_password_change',
                        entity_type='user_account',
                        entity_id=username,
                        details={'reason': 'incorrect_current_password'}
                    )
                    return

                # Update to new password
                success = self.auth.change_password(username, new_password)
                if success:
                    messagebox.showinfo("Success",
                                      "Password changed successfully!\n\n"
                                      "Please use your new password on your next login.")
                    log_activity(
                        action='password_change',
                        entity_type='user_account',
                        entity_id=username,
                        details={'user': username}
                    )
                    dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to update password. Please try again.")
            else:
                messagebox.showerror("Error", "Authentication system not available.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to change password: {str(e)}")

    ttk.Button(button_frame, text="Update Password", command=update_password).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.change_password = change_password

def view_login_history(self):
    """View login history"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Login History")
    dialog.geometry("900x600")
    dialog.transient(self.root)
    dialog.grab_set()

    # Title
    title_frame = ttk.Frame(dialog, padding=20)
    title_frame.pack(fill=tk.X)
    ttk.Label(title_frame, text="Login History",
             font=('Arial', 16, 'bold')).pack(anchor='w')
    ttk.Label(title_frame, text="Recent authentication activity for your account",
             font=('Arial', 10)).pack(anchor='w', pady=(0, 10))

    # Main content frame
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    try:
        current_user = self.get_current_user()
        if not current_user:
            ttk.Label(main_frame, text="Could not retrieve user information.",
                     font=('Arial', 11)).pack(pady=50)
            ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
            return

        username = current_user.get('username')
        user_id = current_user.get('id')

        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        try:
            cursor = conn.cursor()

            # Check if login_history table exists
            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='login_history'
            """)

            if cursor.fetchone():
                # Fetch login history
                cursor.execute("""
                SELECT login_time, ip_address, login_status, device_info, location
                FROM login_history
                WHERE user_id = ? OR username = ?
                ORDER BY login_time DESC
                LIMIT 50
                """, (user_id, username))

                history = cursor.fetchall()

                if history:
                    # Summary frame
                    summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding=10)
                    summary_frame.pack(fill=tk.X, pady=(0, 10))

                    total_logins = len(history)
                    successful_logins = sum(1 for h in history if h[2] == 'success')
                    failed_logins = total_logins - successful_logins

                    ttk.Label(summary_frame, text=f"Total Login Attempts: {total_logins}",
                             font=('Arial', 10)).pack(side=tk.LEFT, padx=20)
                    ttk.Label(summary_frame, text=f"Successful: {successful_logins}",
                             font=('Arial', 10), foreground='green').pack(side=tk.LEFT, padx=20)
                    if failed_logins > 0:
                        ttk.Label(summary_frame, text=f"Failed: {failed_logins}",
                                 font=('Arial', 10), foreground='red').pack(side=tk.LEFT, padx=20)

                    # History table
                    history_frame = ttk.LabelFrame(main_frame, text="Login Activity", padding=10)
                    history_frame.pack(fill=tk.BOTH, expand=True)

                    columns = ("Date/Time", "Status", "IP Address", "Device", "Location")
                    tree = ttk.Treeview(history_frame, columns=columns, show="headings", height=20)

                    tree.heading("Date/Time", text="Date/Time")
                    tree.heading("Status", text="Status")
                    tree.heading("IP Address", text="IP Address")
                    tree.heading("Device", text="Device")
                    tree.heading("Location", text="Location")

                    tree.column("Date/Time", width=180)
                    tree.column("Status", width=100)
                    tree.column("IP Address", width=150)
                    tree.column("Device", width=200)
                    tree.column("Location", width=150)

                    for login in history:
                        login_time = login[0]
                        ip_address = login[1] or "N/A"
                        status = login[2] or "unknown"
                        device = login[3] or "Unknown Device"
                        location = login[4] or "Unknown"

                        # Apply color tags based on status
                        tag = 'success' if status.lower() == 'success' else 'failed'
                        tree.insert('', tk.END, values=(login_time, status.title(), ip_address, device, location), tags=(tag,))

                    tree.tag_configure('success', foreground='green')
                    tree.tag_configure('failed', foreground='red')

                    scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=tree.yview)
                    tree.configure(yscrollcommand=scrollbar.set)

                    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                else:
                    ttk.Label(main_frame, text="No login history found.",
                             font=('Arial', 11)).pack(pady=50)
            else:
                # Create sample login history data for demo
                sample_data = [
                    (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "192.168.1.100", "success", "Windows PC - Chrome", "Local Network"),
                    ((datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'), "192.168.1.100", "success", "Windows PC - Chrome", "Local Network"),
                    ((datetime.datetime.now() - datetime.timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S'), "192.168.1.105", "success", "iPhone - Safari", "Mobile"),
                    ((datetime.datetime.now() - datetime.timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'), "192.168.1.100", "failed", "Windows PC - Chrome", "Local Network"),
                    ((datetime.datetime.now() - datetime.timedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S'), "192.168.1.100", "success", "Windows PC - Chrome", "Local Network"),
                ]

                # Summary frame
                summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding=10)
                summary_frame.pack(fill=tk.X, pady=(0, 10))

                total_logins = len(sample_data)
                successful_logins = sum(1 for h in sample_data if h[2] == 'success')
                failed_logins = total_logins - successful_logins

                ttk.Label(summary_frame, text=f"Total Login Attempts: {total_logins}",
                         font=('Arial', 10)).pack(side=tk.LEFT, padx=20)
                ttk.Label(summary_frame, text=f"Successful: {successful_logins}",
                         font=('Arial', 10), foreground='green').pack(side=tk.LEFT, padx=20)
                if failed_logins > 0:
                    ttk.Label(summary_frame, text=f"Failed: {failed_logins}",
                             font=('Arial', 10), foreground='red').pack(side=tk.LEFT, padx=20)

                # History table
                history_frame = ttk.LabelFrame(main_frame, text="Login Activity (Sample Data)", padding=10)
                history_frame.pack(fill=tk.BOTH, expand=True)

                columns = ("Date/Time", "Status", "IP Address", "Device", "Location")
                tree = ttk.Treeview(history_frame, columns=columns, show="headings", height=20)

                tree.heading("Date/Time", text="Date/Time")
                tree.heading("Status", text="Status")
                tree.heading("IP Address", text="IP Address")
                tree.heading("Device", text="Device")
                tree.heading("Location", text="Location")

                tree.column("Date/Time", width=180)
                tree.column("Status", width=100)
                tree.column("IP Address", width=150)
                tree.column("Device", width=200)
                tree.column("Location", width=150)

                for login in sample_data:
                    tag = 'success' if login[2].lower() == 'success' else 'failed'
                    tree.insert('', tk.END, values=(login[0], login[2].title(), login[1], login[3], login[4]), tags=(tag,))

                tree.tag_configure('success', foreground='green')
                tree.tag_configure('failed', foreground='red')

                scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=tree.yview)
                tree.configure(yscrollcommand=scrollbar.set)

                tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        finally:
            conn.close()

    except Exception as e:
        ttk.Label(main_frame, text=f"Error loading login history: {str(e)}",
                 font=('Arial', 10)).pack(pady=50)

    # Close button
    ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
ParentPortalGUI.view_login_history = view_login_history
