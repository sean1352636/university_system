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
from education_system.university_system.core.i18n import (
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

def show_dashboard(self):
    """Show the main dashboard"""
    self.clear_content()
    self.update_status(_t("parent_portal.dashboard.status"))

    # Dashboard title
    title = ttk.Label(self.content_frame, text=_t("parent_portal.dashboard.title"), style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Add personalized welcome
    current_user = self.get_current_user()
    if current_user:
        first_name = current_user.get('first_name', '')
        last_name = current_user.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip() or current_user.get('username', 'User')

        welcome_label = ttk.Label(
            self.content_frame,
            text=f"Welcome back, {full_name}!",
            font=('Arial', 14),
            foreground='#2c3e50'
        )
        welcome_label.pack(pady=(0, 10))

    # User info card
    user_frame = ttk.LabelFrame(self.content_frame, text="Your Account", padding=15)
    user_frame.pack(fill=tk.X, padx=20, pady=10)

    if current_user:
        # Create two columns
        left_col = ttk.Frame(user_frame)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right_col = ttk.Frame(user_frame)
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Left column
        ttk.Label(left_col, text=f"Name: {full_name}", font=('Arial', 10)).pack(anchor='w', pady=2)
        ttk.Label(left_col, text=f"Email: {current_user.get('email', 'Not set')}", font=('Arial', 10)).pack(anchor='w', pady=2)

        # Right column
        ttk.Label(right_col, text=f"Role: {current_user.get('role', 'parent').title()}", font=('Arial', 10)).pack(anchor='w', pady=2)
        if self.parent_id:
            ttk.Label(right_col, text=f"Parent ID: {self.parent_id}", font=('Arial', 10)).pack(anchor='w', pady=2)

    # Create dashboard widgets
    dashboard_container = ttk.Frame(self.content_frame)
    dashboard_container.pack(fill=tk.BOTH, expand=True, padx=20)

    # Quick stats cards
    self.create_stats_cards(dashboard_container)

    # Recent activity and alerts
    activity_frame = ttk.Frame(dashboard_container)
    activity_frame.pack(fill=tk.BOTH, expand=True, pady=20)

    # Left column - Recent alerts
    left_column = ttk.Frame(activity_frame)
    left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

    alerts_label = ttk.Label(left_column, text="Recent Alerts", style='Heading.TLabel')
    alerts_label.pack(anchor='w')

    alerts_text = scrolledtext.ScrolledText(left_column, height=15, width=40)
    alerts_text.pack(fill=tk.BOTH, expand=True, pady=5)

    # Right column - Children overview
    right_column = ttk.Frame(activity_frame)
    right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

    children_label = ttk.Label(right_column, text="My Students", style='Heading.TLabel')
    children_label.pack(anchor='w')

    children_frame = ttk.Frame(right_column)
    children_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    # Load dashboard data
    self.load_dashboard_data(alerts_text, children_frame)
ParentPortalGUI.show_dashboard = show_dashboard

def create_stats_cards(self, parent):
    """Create quick stats cards - using ttk widgets to reduce X pixmap usage"""
    stats_frame = ttk.Frame(parent)
    stats_frame.pack(fill=tk.X, pady=10)

    # Sample stats (in real implementation, these would be dynamic)
    stats = [
        ("Children", len(self.children)),
        ("Unread Messages", "2"),
        ("Upcoming Events", "3"),
        ("Pending Fees", "£0.00")
    ]

    for i, (title, value) in enumerate(stats):
        # Use ttk.LabelFrame instead of colored tk.Frame to reduce pixmap allocation
        card = ttk.LabelFrame(stats_frame, text=title, padding=10)
        card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        value_label = ttk.Label(card, text=str(value), font=('Arial', 18, 'bold'))
        value_label.pack()
ParentPortalGUI.create_stats_cards = create_stats_cards

def load_dashboard_data(self, alerts_text, children_frame):
    """Load dashboard data in background"""
    is_admin = self.is_admin()

    def load_data():
        try:
            # Load alerts
            alerts_text.insert(tk.END, "Loading alerts...\n")

            # Load children data
            if self.children:
                # For admin users, limit dashboard display to first 10 students
                display_limit = 10 if is_admin else len(self.children)
                display_children = self.children[:display_limit]

                if is_admin and len(self.children) > display_limit:
                    admin_label = ttk.Label(
                        children_frame,
                        text=f"📋 Admin: Showing {display_limit} of {len(self.children)} students (view all in 'My Students')",
                        font=('Arial', 9),
                        foreground='#27ae60'
                    )
                    admin_label.pack(pady=(0, 5))

                for i, child in enumerate(display_children):
                    child_card = self.create_child_card(children_frame, child)
                    child_card.pack(fill=tk.X, pady=5)
            else:
                no_children_label = ttk.Label(children_frame, text="No students linked to your account")
                no_children_label.pack()

            alerts_text.delete(1.0, tk.END)
            alerts_text.insert(tk.END, "✓ System ready\n")
            if is_admin:
                alerts_text.insert(tk.END, f"👨‍💼 Admin Mode: Full access enabled\n")
                alerts_text.insert(tk.END, f"📊 Total students: {len(self.children)}\n")
            alerts_text.insert(tk.END, "📧 2 unread messages\n")
            alerts_text.insert(tk.END, "📅 Parent-instructor conference scheduled\n")

        except Exception as e:
            alerts_text.insert(tk.END, f"Error loading data: {str(e)}\n")

    # Load data in background thread
    threading.Thread(target=load_data, daemon=True).start()
ParentPortalGUI.load_dashboard_data = load_dashboard_data

def create_child_card(self, parent, child):
    """Create a card widget for a child"""
    card = ttk.LabelFrame(parent, text=f"{child[1]} {child[3]}", padding=10)

    info_text = f"ID: {child[0]}\nCourse: {child[4]}\nRelationship: {child[5]}"
    info_label = ttk.Label(card, text=info_text, style='Info.TLabel')
    info_label.pack(anchor='w')

    # Quick action buttons
    btn_frame = ttk.Frame(card)
    btn_frame.pack(fill=tk.X, pady=5)

    view_grades_btn = ttk.Button(btn_frame, text="Grades",
                               command=lambda c=child: self.view_child_grades(c))
    view_grades_btn.pack(side=tk.LEFT, padx=2)

    view_attendance_btn = ttk.Button(btn_frame, text="Attendance",
                                   command=lambda c=child: self.view_child_attendance(c))
    view_attendance_btn.pack(side=tk.LEFT, padx=2)

    return card
ParentPortalGUI.create_child_card = create_child_card

def show_quick_actions(self):
    """Show quick actions menu"""
    self.clear_content()
    self.update_status("Quick Actions")

    title = ttk.Label(self.content_frame, text="Quick Actions", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    actions_frame = ttk.Frame(self.content_frame)
    actions_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    # Quick action buttons
    actions = [
        ("📝 Report Absence", self.quick_absence_report),
        ("📞 Update Emergency Contact", self.emergency_contact_update),
        ("🚨 View Today's Alerts", self.view_todays_alerts),
        ("💳 Check Meal Balance", self.check_meal_balance),
        ("📨 View Urgent Messages", self.view_urgent_messages),
    ]

    for i, (text, command) in enumerate(actions):
        row = i // 2
        col = i % 2

        btn = ttk.Button(
            actions_frame,
            text=text,
            command=command,
            width=30
        )
        btn.grid(row=row, column=col, padx=10, pady=10, sticky='ew')

    actions_frame.grid_columnconfigure(0, weight=1)
    actions_frame.grid_columnconfigure(1, weight=1)
ParentPortalGUI.show_quick_actions = show_quick_actions

def view_todays_alerts(self):
    """View today's alerts from email system and notifications"""
    alerts_window = tk.Toplevel(self.root)
    alerts_window.title("Today's Alerts")
    alerts_window.geometry("700x500")

    title = ttk.Label(alerts_window, text="Today's Alerts", font=('Arial', 16, 'bold'))
    title.pack(pady=10)

    # Get current user info
    current_user = self.get_current_user()
    user_email = current_user.get('email', '') if current_user else ''

    # Create notebook for different alert types
    notebook = ttk.Notebook(alerts_window)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    # Emails tab
    emails_frame = ttk.Frame(notebook)
    notebook.add(emails_frame, text="Emails")

    emails_tree = ttk.Treeview(emails_frame, columns=("Time", "Subject", "Status"), show='headings', height=10)
    emails_tree.heading("Time", text="Time")
    emails_tree.heading("Subject", text="Subject")
    emails_tree.heading("Status", text="Status")
    emails_tree.column("Time", width=120)
    emails_tree.column("Subject", width=350)
    emails_tree.column("Status", width=80)

    emails_scroll = ttk.Scrollbar(emails_frame, orient="vertical", command=emails_tree.yview)
    emails_tree.configure(yscrollcommand=emails_scroll.set)
    emails_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    emails_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # Notifications tab
    notif_frame = ttk.Frame(notebook)
    notebook.add(notif_frame, text="Notifications")

    notif_tree = ttk.Treeview(notif_frame, columns=("Time", "Type", "Content", "Read"), show='headings', height=10)
    notif_tree.heading("Time", text="Time")
    notif_tree.heading("Type", text="Type")
    notif_tree.heading("Content", text="Content")
    notif_tree.heading("Read", text="Read")
    notif_tree.column("Time", width=120)
    notif_tree.column("Type", width=100)
    notif_tree.column("Content", width=300)
    notif_tree.column("Read", width=50)

    notif_scroll = ttk.Scrollbar(notif_frame, orient="vertical", command=notif_tree.yview)
    notif_tree.configure(yscrollcommand=notif_scroll.set)
    notif_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    notif_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # Emergency alerts tab
    emergency_frame = ttk.Frame(notebook)
    notebook.add(emergency_frame, text="Emergency Alerts")

    emergency_text = scrolledtext.ScrolledText(emergency_frame, height=12)
    emergency_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Load alerts from database
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    email_count = 0
    notif_count = 0
    emergency_count = 0

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        cursor = conn.cursor()

        # Get emails for current user (today)
        cursor.execute('''
            SELECT sent_date, subject, status, recipient
            FROM email_log
            WHERE recipient = ? AND DATE(sent_date) = DATE(?)
            ORDER BY sent_date DESC
            LIMIT 50
        ''', (user_email, today))

        emails = cursor.fetchall()
        for email in emails:
            sent_date, subject, status, recipient = email
            time_str = sent_date[:16] if sent_date else "Unknown"
            emails_tree.insert("", tk.END, values=(time_str, subject or "No Subject", status or "sent"))
            email_count += 1

        # Get parent notifications (if parent_id exists)
        if self.parent_id:
            cursor.execute('''
                SELECT created_date, notification_type, notification_content, read_status
                FROM parent_notifications
                WHERE parent_id = ? AND DATE(created_date) = DATE(?)
                ORDER BY created_date DESC
                LIMIT 50
            ''', (self.parent_id, today))

            notifications = cursor.fetchall()
            for notif in notifications:
                created_date, notif_type, content, read_status = notif
                time_str = created_date[:16] if created_date else "Unknown"
                read_text = "Yes" if read_status else "No"
                # Truncate content for display
                display_content = (content[:50] + "...") if content and len(content) > 50 else (content or "")
                notif_tree.insert("", tk.END, values=(time_str, notif_type or "General", display_content, read_text))
                notif_count += 1

        # Get emergency alerts (active ones from today)
        cursor.execute('''
            SELECT alert_title, alert_message, alert_type, created_date
            FROM emergency_alerts
            WHERE active = 1 AND DATE(created_date) >= DATE(?, '-7 days')
            ORDER BY created_date DESC
            LIMIT 10
        ''', (today,))

        emergency_alerts = cursor.fetchall()
        emergency_text.insert(tk.END, f"Active Emergency Alerts\n")
        emergency_text.insert(tk.END, "=" * 40 + "\n\n")

        if emergency_alerts:
            for alert in emergency_alerts:
                alert_title, alert_msg, alert_type, created = alert
                emergency_text.insert(tk.END, f"[{alert_type or 'ALERT'}] {alert_title}\n")
                emergency_text.insert(tk.END, f"Date: {created[:16] if created else 'Unknown'}\n")
                emergency_text.insert(tk.END, f"{alert_msg}\n")
                emergency_text.insert(tk.END, "-" * 40 + "\n\n")
                emergency_count += 1
        else:
            emergency_text.insert(tk.END, "No emergency alerts.\n")

        conn.close()

    except Exception as e:
        emails_tree.insert("", tk.END, values=("Error", f"Could not load: {e}", ""))

    # Summary label
    summary = ttk.Label(
        alerts_window,
        text=f"Today's Summary: {email_count} emails, {notif_count} notifications, {emergency_count} emergency alerts",
        font=('Arial', 10)
    )
    summary.pack(pady=5)

    # Refresh button
    btn_frame = ttk.Frame(alerts_window)
    btn_frame.pack(pady=10)

    def refresh_alerts():
        alerts_window.destroy()
        self.view_todays_alerts()

    ttk.Button(btn_frame, text="Refresh", command=refresh_alerts).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Close", command=alerts_window.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.view_todays_alerts = view_todays_alerts

def view_urgent_messages(self):
    """View urgent messages from email system and parent messages"""
    messages_window = tk.Toplevel(self.root)
    messages_window.title("Urgent Messages")
    messages_window.geometry("750x550")

    title = ttk.Label(messages_window, text="Urgent Messages", font=('Arial', 16, 'bold'))
    title.pack(pady=10)

    # Create notebook for message types
    notebook = ttk.Notebook(messages_window)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    # Parent messages tab (from teachers/staff)
    parent_msg_frame = ttk.Frame(notebook)
    notebook.add(parent_msg_frame, text="Instructor Messages")

    msg_tree = ttk.Treeview(parent_msg_frame,
        columns=("Date", "From", "Student", "Message", "Read"),
        show='headings', height=12)

    msg_tree.heading("Date", text="Date")
    msg_tree.heading("From", text="From")
    msg_tree.heading("Student", text="Student")
    msg_tree.heading("Message", text="Message")
    msg_tree.heading("Read", text="Read")

    msg_tree.column("Date", width=100)
    msg_tree.column("From", width=120)
    msg_tree.column("Student", width=100)
    msg_tree.column("Message", width=280)
    msg_tree.column("Read", width=50)

    msg_scroll = ttk.Scrollbar(parent_msg_frame, orient="vertical", command=msg_tree.yview)
    msg_tree.configure(yscrollcommand=msg_scroll.set)
    msg_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    msg_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # High priority emails tab
    email_frame = ttk.Frame(notebook)
    notebook.add(email_frame, text="Important Emails")

    email_tree = ttk.Treeview(email_frame,
        columns=("Date", "Subject", "Related To"),
        show='headings', height=12)

    email_tree.heading("Date", text="Date")
    email_tree.heading("Subject", text="Subject")
    email_tree.heading("Related To", text="Related To")

    email_tree.column("Date", width=120)
    email_tree.column("Subject", width=350)
    email_tree.column("Related To", width=120)

    email_scroll = ttk.Scrollbar(email_frame, orient="vertical", command=email_tree.yview)
    email_tree.configure(yscrollcommand=email_scroll.set)
    email_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    email_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # Message details frame
    details_frame = ttk.LabelFrame(messages_window, text="Message Details", padding=10)
    details_frame.pack(fill=tk.X, padx=10, pady=5)

    details_text = scrolledtext.ScrolledText(details_frame, height=6)
    details_text.pack(fill=tk.BOTH, expand=True)

    # Get current user info
    current_user = self.get_current_user()
    user_email = current_user.get('email', '') if current_user else ''

    # Store messages for detail viewing
    messages_data = {}
    emails_data = {}

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        cursor = conn.cursor()

        # Get parent messages (incoming from teachers)
        if self.parent_id:
            cursor.execute('''
                SELECT pm.id, pm.created_date, u.first_name || ' ' || u.last_name as instructor_name,
                       s.first_name || ' ' || s.last_name as student_name,
                       pm.message_content, pm.is_read
                FROM parent_messages pm
                LEFT JOIN users u ON pm.teacher_id = u.id
                LEFT JOIN students s ON pm.student_id = s.student_id
                WHERE pm.parent_id = ? AND pm.is_from_parent = 0
                ORDER BY pm.created_date DESC
                LIMIT 50
            ''', (self.parent_id,))

            messages = cursor.fetchall()
            for msg in messages:
                msg_id, created, teacher, student, content, is_read = msg
                date_str = created[:16] if created else "Unknown"
                teacher = teacher or "Staff"
                student = student or "Unknown"
                read_text = "Yes" if is_read else "No"
                # Truncate for display
                display_content = (content[:40] + "...") if content and len(content) > 40 else (content or "")

                item_id = msg_tree.insert("", tk.END, values=(
                    date_str, teacher, student, display_content, read_text
                ))
                messages_data[item_id] = {
                    'id': msg_id,
                    'date': created,
                    'from': teacher,
                    'student': student,
                    'content': content,
                    'is_read': is_read
                }

        # Get important emails (last 7 days, filtered by keywords)
        seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT id, sent_date, subject, related_to, message
            FROM email_log
            WHERE recipient = ?
              AND DATE(sent_date) >= DATE(?)
              AND (
                  subject LIKE '%urgent%'
                  OR subject LIKE '%important%'
                  OR subject LIKE '%alert%'
                  OR subject LIKE '%attendance%'
                  OR subject LIKE '%grade%'
                  OR subject LIKE '%absent%'
                  OR subject LIKE '%meeting%'
                  OR subject LIKE '%deadline%'
                  OR subject LIKE '%reminder%'
                  OR related_to IN ('attendance', 'grade_alert', 'urgent', 'absence', 'meal_topup')
              )
            ORDER BY sent_date DESC
            LIMIT 30
        ''', (user_email, seven_days_ago))

        emails = cursor.fetchall()
        for email in emails:
            email_id, sent_date, subject, related_to, message = email
            date_str = sent_date[:16] if sent_date else "Unknown"
            related = related_to or "General"

            item_id = email_tree.insert("", tk.END, values=(
                date_str, subject or "No Subject", related
            ))
            emails_data[item_id] = {
                'id': email_id,
                'date': sent_date,
                'subject': subject,
                'related_to': related_to,
                'message': message
            }

        conn.close()

    except Exception as e:
        details_text.insert(tk.END, f"Error loading messages: {e}")

    def show_message_details(event):
        """Show details of selected message"""
        selection = msg_tree.selection()
        if selection:
            item_id = selection[0]
            if item_id in messages_data:
                msg = messages_data[item_id]
                details_text.delete(1.0, tk.END)
                details_text.insert(tk.END, f"From: {msg['from']}\n")
                details_text.insert(tk.END, f"Regarding: {msg['student']}\n")
                details_text.insert(tk.END, f"Date: {msg['date']}\n")
                details_text.insert(tk.END, "-" * 40 + "\n")
                details_text.insert(tk.END, msg['content'] or "No content")

                # Mark as read in database
                if not msg['is_read']:
                    try:
                        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                        cursor = conn.cursor()
                        cursor.execute("UPDATE parent_messages SET is_read = 1 WHERE id = ?", (msg['id'],))
                        conn.commit()
                        conn.close()
                        # Update display
                        current_values = list(msg_tree.item(item_id, 'values'))
                        current_values[4] = "Yes"
                        msg_tree.item(item_id, values=current_values)
                        messages_data[item_id]['is_read'] = True
                    except Exception:
                        pass

    def show_email_details(event):
        """Show details of selected email"""
        selection = email_tree.selection()
        if selection:
            item_id = selection[0]
            if item_id in emails_data:
                email = emails_data[item_id]
                details_text.delete(1.0, tk.END)
                details_text.insert(tk.END, f"Subject: {email['subject']}\n")
                details_text.insert(tk.END, f"Date: {email['date']}\n")
                details_text.insert(tk.END, f"Category: {email['related_to'] or 'General'}\n")
                details_text.insert(tk.END, "-" * 40 + "\n")
                details_text.insert(tk.END, email['message'] or "No content")

    msg_tree.bind("<<TreeviewSelect>>", show_message_details)
    email_tree.bind("<<TreeviewSelect>>", show_email_details)

    # Summary and buttons
    msg_count = len(messages_data)
    email_count = len(emails_data)
    unread_count = sum(1 for m in messages_data.values() if not m.get('is_read'))

    summary = ttk.Label(
        messages_window,
        text=f"Total: {msg_count} teacher messages ({unread_count} unread), {email_count} important emails",
        font=('Arial', 10)
    )
    summary.pack(pady=5)

    btn_frame = ttk.Frame(messages_window)
    btn_frame.pack(pady=10)

    def refresh():
        messages_window.destroy()
        self.view_urgent_messages()

    def mark_all_read():
        if not self.parent_id:
            return
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            cursor = conn.cursor()
            cursor.execute("UPDATE parent_messages SET is_read = 1 WHERE parent_id = ?", (self.parent_id,))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "All messages marked as read.")
            refresh()
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

    ttk.Button(btn_frame, text="Mark All Read", command=mark_all_read).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Refresh", command=refresh).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Close", command=messages_window.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.view_urgent_messages = view_urgent_messages
