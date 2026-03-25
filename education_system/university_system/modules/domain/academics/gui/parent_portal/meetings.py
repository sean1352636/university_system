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

def show_meeting_interface(self):
    """Show schedule meeting interface"""
    self.clear_content()
    self.update_status("Schedule Meeting")

    title = ttk.Label(self.content_frame, text="Schedule Meeting", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Meeting request form
    form_frame = ttk.LabelFrame(self.content_frame, text="Meeting Request", padding=20)
    form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    # Meeting with
    ttk.Label(form_frame, text="Meeting With:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
    meeting_with_var = tk.StringVar()
    meeting_combo = ttk.Combobox(form_frame, textvariable=meeting_with_var, width=40)
    meeting_combo['values'] = ["Select...", "Instructor", "Department Head", "Academic Advisor", "Accessibility Services", "University Health Services"]
    meeting_combo.grid(row=0, column=1, pady=5, sticky='ew')

    # Regarding child
    ttk.Label(form_frame, text="Regarding Child:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
    child_var = tk.StringVar()
    child_combo = ttk.Combobox(form_frame, textvariable=child_var, width=40)
    if self.children:
        child_combo['values'] = [f"{child[1]} {child[3]}" for child in self.children]
    child_combo.grid(row=1, column=1, pady=5, sticky='ew')

    # Preferred date
    ttk.Label(form_frame, text="Preferred Date:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
    date_entry = ttk.Entry(form_frame, width=40)
    date_entry.insert(0, "YYYY-MM-DD")
    date_entry.grid(row=2, column=1, pady=5, sticky='ew')

    # Preferred time
    ttk.Label(form_frame, text="Preferred Time:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=5)
    time_var = tk.StringVar()
    time_combo = ttk.Combobox(form_frame, textvariable=time_var, width=40)
    time_combo['values'] = ["Morning (8:00-12:00)", "Afternoon (12:00-16:00)", "Evening (16:00-18:00)"]
    time_combo.grid(row=3, column=1, pady=5, sticky='ew')

    # Meeting type
    ttk.Label(form_frame, text="Meeting Type:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='w', pady=5)
    type_var = tk.StringVar()
    type_combo = ttk.Combobox(form_frame, textvariable=type_var, width=40)
    type_combo['values'] = ["In-Person", "Video Call", "Phone Call"]
    type_combo.grid(row=4, column=1, pady=5, sticky='ew')

    # Purpose
    ttk.Label(form_frame, text="Purpose:", font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky='nw', pady=5)
    purpose_text = scrolledtext.ScrolledText(form_frame, height=8, width=40, wrap=tk.WORD)
    purpose_text.grid(row=5, column=1, pady=5, sticky='ew')

    form_frame.columnconfigure(1, weight=1)

    # Buttons
    btn_frame = ttk.Frame(self.content_frame)
    btn_frame.pack(pady=10)

    def submit_meeting_request():
        meeting_with = meeting_with_var.get()
        child = child_var.get()
        date = date_entry.get()
        time = time_var.get()
        meeting_type = type_var.get()
        purpose = purpose_text.get('1.0', tk.END).strip()

        if not all([meeting_with, child, date, time, meeting_type, purpose]) or meeting_with == "Select...":
            messagebox.showwarning("Incomplete Form", "Please fill in all fields.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='meeting_requests'
            """)

            if cursor.fetchone():
                cursor.execute("""
                INSERT INTO meeting_requests (parent_id, meeting_with, student_name, preferred_date,
                                             preferred_time, meeting_type, purpose, status, request_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (self.parent_id, meeting_with, child, date, time, meeting_type, purpose, "Pending",
                     datetime.datetime.now().isoformat()))
                conn.commit()

            conn.close()
            messagebox.showinfo("Success", "Meeting request submitted successfully!\n\n"
                                          "You will receive confirmation once the meeting is scheduled.")
            self.show_dashboard()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit meeting request: {str(e)}")

    ttk.Button(btn_frame, text="Submit Request", command=submit_meeting_request).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=self.show_dashboard).pack(side=tk.LEFT, padx=5)

    # Show existing meetings
    existing_frame = ttk.LabelFrame(self.content_frame, text="Upcoming Meetings", padding=15)
    existing_frame.pack(fill=tk.X, padx=20, pady=10)

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='meetings'
        """)

        if cursor.fetchone():
            cursor.execute("""
            SELECT date, time, with_person, location, status
            FROM meetings
            WHERE parent_id = ? AND date >= date('now')
            ORDER BY date
            LIMIT 10
            """, (self.parent_id,))

            meetings = cursor.fetchall()

            if meetings:
                for meeting in meetings:
                    meeting_info = f"{meeting[0]} at {meeting[1]} - {meeting[2]} ({meeting[3]}) - Status: {meeting[4]}"
                    ttk.Label(existing_frame, text=meeting_info).pack(anchor='w', pady=2)
            else:
                ttk.Label(existing_frame, text="No upcoming meetings scheduled").pack()
        else:
            ttk.Label(existing_frame, text="No meetings scheduled").pack()

        conn.close()

    except Exception as e:
        ttk.Label(existing_frame, text=f"Error loading meetings: {str(e)}").pack()
ParentPortalGUI.show_meeting_interface = show_meeting_interface

def show_report_issue_interface(self):
    """Show report issue interface"""
    self.clear_content()
    self.update_status("Report Issue")

    title = ttk.Label(self.content_frame, text="Report Issue", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Issue report form
    form_frame = ttk.LabelFrame(self.content_frame, text="Report an Issue to University Administration", padding=20)
    form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    # Category
    ttk.Label(form_frame, text="Category:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
    category_var = tk.StringVar()
    category_combo = ttk.Combobox(form_frame, textvariable=category_var, width=40, state='readonly')
    category_combo['values'] = ["Academic concern", "Behavioral concern", "Facility issue",
                                 "Safety concern", "Billing/Administrative", "Other"]
    category_combo.grid(row=0, column=1, pady=5, sticky='ew')

    # Subject
    ttk.Label(form_frame, text="Subject:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
    subject_entry = ttk.Entry(form_frame, width=40)
    subject_entry.grid(row=1, column=1, pady=5, sticky='ew')

    # Priority
    ttk.Label(form_frame, text="Priority:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
    priority_var = tk.StringVar()
    priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, width=40, state='readonly')
    priority_combo['values'] = ["Low", "Medium", "High"]
    priority_combo.current(1)  # Default to Medium
    priority_combo.grid(row=2, column=1, pady=5, sticky='ew')

    # Description
    ttk.Label(form_frame, text="Description:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='nw', pady=5)
    description_text = scrolledtext.ScrolledText(form_frame, height=10, width=40, wrap=tk.WORD)
    description_text.grid(row=3, column=1, pady=5, sticky='ew')

    form_frame.columnconfigure(1, weight=1)

    # Buttons
    btn_frame = ttk.Frame(self.content_frame)
    btn_frame.pack(pady=10)

    def submit_issue():
        category = category_var.get()
        subject = subject_entry.get().strip()
        priority = priority_var.get().lower()
        description = description_text.get('1.0', tk.END).strip()

        if not category:
            messagebox.showwarning("Validation Error", "Please select a category.")
            return

        if not subject:
            messagebox.showwarning("Validation Error", "Please enter a subject.")
            return

        if not description:
            messagebox.showwarning("Validation Error", "Please enter a detailed description.")
            return

        if not self.parent_id:
            messagebox.showerror("Error", "Parent ID not found. Please log in again.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                category TEXT,
                subject TEXT,
                description TEXT,
                priority TEXT,
                status TEXT DEFAULT 'open',
                created_date TEXT,
                resolved_date TEXT,
                response TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            )
            ''')

            # Insert issue
            cursor.execute('''
            INSERT INTO parent_issues (parent_id, category, subject, description, priority, created_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (self.parent_id, category, subject, description, priority,
                  datetime.datetime.now().isoformat()))

            conn.commit()
            issue_id = cursor.lastrowid

            # Get parent name for email
            parent_name = self.parent_name if hasattr(self, 'parent_name') else 'Parent'

            # Send email notification to admin
            if EMAIL_SERVICE_AVAILABLE:
                try:
                    # Get admin email
                    cursor.execute("""
                    SELECT email FROM users WHERE role = 'admin' LIMIT 1
                    """)
                    admin_result = cursor.fetchone()
                    admin_email = admin_result[0] if admin_result else 'admin@university.edu'

                    # Render email from template
                    from education_system.university_system.infrastructure.email.template_utils import render_template

                    email_subject, email_body = render_template('parent_portal/parent_issue_report', {
                        'issue_id': issue_id,
                        'parent_name': parent_name,
                        'parent_id': self.parent_id,
                        'category': category,
                        'priority': priority.upper(),
                        'subject': subject,
                        'description': description
                    })

                    # Fallback if template not found
                    if not email_subject or not email_body:
                        email_subject = f"[Parent Issue #{issue_id}] {category}: {subject}"
                        email_body = f"New Parent Issue Report\n\nTracking ID: #{issue_id}\nSubmitted by: {parent_name} (Parent ID: {self.parent_id})\nCategory: {category}\nPriority: {priority.upper()}\nSubject: {subject}\n\nDescription:\n{description}\n\n---\nPlease respond to this issue within 24-48 hours."

                    send_email(admin_email, email_subject, email_body)
                except Exception as email_error:
                    print(f"Failed to send admin notification: {email_error}")

            conn.close()

            messagebox.showinfo("Success",
                f"Issue reported successfully!\n\nTracking ID: #{issue_id}\n\n"
                "University administration has been notified and will respond within 24-48 hours.")
            self.update_status("Issue reported successfully")
            self.show_communication_menu()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit issue: {str(e)}")

    ttk.Button(btn_frame, text="Submit Issue", command=submit_issue).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=self.show_communication_menu).pack(side=tk.LEFT, padx=5)

    # Show recent issues
    recent_frame = ttk.LabelFrame(self.content_frame, text="Your Recent Issues", padding=15)
    recent_frame.pack(fill=tk.X, padx=20, pady=10)

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='parent_issues'
        """)

        if cursor.fetchone() and self.parent_id:
            cursor.execute("""
            SELECT id, category, subject, priority, status, created_date
            FROM parent_issues
            WHERE parent_id = ?
            ORDER BY created_date DESC
            LIMIT 5
            """, (self.parent_id,))

            issues = cursor.fetchall()

            if issues:
                columns = ("ID", "Category", "Subject", "Priority", "Status", "Date")
                tree = ttk.Treeview(recent_frame, columns=columns, show="headings", height=5)

                for col in columns:
                    tree.heading(col, text=col)
                    tree.column(col, width=100)

                for issue in issues:
                    # Format date
                    created_date = issue[5][:10] if issue[5] else "N/A"
                    tree.insert("", tk.END, values=(
                        f"#{issue[0]}", issue[1], issue[2], issue[3].upper(),
                        issue[4].upper(), created_date
                    ))

                tree.pack(fill=tk.X, pady=5)
            else:
                ttk.Label(recent_frame, text="No issues reported yet").pack()
        else:
            ttk.Label(recent_frame, text="No issues reported yet").pack()

        conn.close()

    except Exception as e:
        ttk.Label(recent_frame, text=f"Error loading recent issues: {str(e)}").pack()
ParentPortalGUI.show_report_issue_interface = show_report_issue_interface
