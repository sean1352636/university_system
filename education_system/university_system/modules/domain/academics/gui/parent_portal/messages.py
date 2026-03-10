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



from .base import ParentPortalGUI

def message_teachers(self, child):
    """Message teachers for a specific child - sends actual emails"""
    self.clear_content()
    self.update_status(f"Messaging teachers for {child[1]} {child[3]}")

    title = ttk.Label(self.content_frame, text=f"Message Instructors - {child[1]} {child[3]}",
                     style='Title.TLabel', font=('Arial', 18, 'bold'))
    title.pack(pady=20)

    message_frame = ttk.Frame(self.content_frame)
    message_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    # Load actual instructors from database
    student_id = child[0]
    instructors = self._get_student_instructors(student_id)

    # Instructor selection
    teacher_frame = ttk.LabelFrame(message_frame, text="Select Instructor", padding=10)
    teacher_frame.pack(fill=tk.X, pady=10)

    teacher_var = tk.StringVar()

    # Create instructor options with email info stored
    instructor_data = {}  # Maps display name to email
    if instructors:
        for inst in instructors:
            inst_id, first_name, last_name, email, department, course = inst
            display_name = f"{first_name} {last_name} ({department or course})"
            instructor_data[display_name] = email
            rb = ttk.Radiobutton(teacher_frame, text=display_name, variable=teacher_var, value=display_name)
            rb.pack(anchor='w')

        # Add "All Instructors" option
        instructor_data["All Instructors"] = [inst[3] for inst in instructors]  # List of all emails
        rb = ttk.Radiobutton(teacher_frame, text="All Instructors", variable=teacher_var, value="All Instructors")
        rb.pack(anchor='w')

        teacher_var.set(list(instructor_data.keys())[0])
    else:
        ttk.Label(teacher_frame, text="No instructors found in the system.").pack(anchor='w')

    # Store instructor data for send function
    self._current_instructor_data = instructor_data

    # Message composition
    compose_frame = ttk.LabelFrame(message_frame, text="Compose Message", padding=10)
    compose_frame.pack(fill=tk.BOTH, expand=True, pady=10)

    ttk.Label(compose_frame, text="Subject:").pack(anchor='w')
    subject_entry = ttk.Entry(compose_frame, width=80)
    subject_entry.pack(fill=tk.X, pady=5)

    ttk.Label(compose_frame, text="Message:").pack(anchor='w', pady=(10, 0))
    message_text = scrolledtext.ScrolledText(compose_frame, height=10)
    message_text.pack(fill=tk.BOTH, expand=True, pady=5)

    # Get current user info for email signature
    current_user = self.get_current_user()
    sender_name = "Parent/Guardian"
    sender_email = ""
    if current_user:
        first = current_user.get('first_name', '')
        last = current_user.get('last_name', '')
        sender_name = f"{first} {last}".strip() or current_user.get('username', 'Parent/Guardian')
        sender_email = current_user.get('email', '')

    # Send button
    def send_message():
        subject = subject_entry.get().strip()
        message_body = message_text.get(1.0, tk.END).strip()
        teacher = teacher_var.get()

        if not subject or not message_body:
            messagebox.showwarning("Missing Information", "Please fill in both subject and message.")
            return

        if not teacher or teacher not in self._current_instructor_data:
            messagebox.showwarning("No Recipient", "Please select an instructor.")
            return

        # Build full email body with student info and sender signature
        full_body = f"""Dear Instructor,

{message_body}

---
Regarding student: {child[1]} {child[3]} (ID: {child[0]})
Sent by: {sender_name}
Contact: {sender_email if sender_email else 'Via Guardian Portal'}

This message was sent through the University Guardian Portal.
"""

        recipient_emails = self._current_instructor_data[teacher]
        if isinstance(recipient_emails, str):
            recipient_emails = [recipient_emails]

        # Send actual emails
        success_count = 0
        fail_count = 0

        for email in recipient_emails:
            try:
                if EMAIL_SERVICE_AVAILABLE:
                    result = send_email(email, subject, full_body)
                    if result:
                        success_count += 1
                    else:
                        fail_count += 1
                else:
                    # Fallback: Store in database only
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                    cursor = conn.cursor()
                    # Use correct schema: sender_id, recipient_id, subject, content, sent_at
                    # Get recipient_id from users table if possible
                    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
                    recipient = cursor.fetchone()
                    recipient_id = recipient[0] if recipient else 0
                    cursor.execute('''
                        INSERT INTO messages (sender_id, recipient_id, subject, content, sent_at, is_read)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (self.parent_id or 0, recipient_id, subject, full_body, datetime.datetime.now().isoformat(), 0))
                    conn.commit()
                    conn.close()
                    success_count += 1
            except Exception as e:
                print(f"Error sending email to {email}: {e}")
                fail_count += 1

        if success_count > 0 and fail_count == 0:
            messagebox.showinfo("Success", f"Message sent successfully to {success_count} instructor(s)!")
            subject_entry.delete(0, tk.END)
            message_text.delete(1.0, tk.END)
        elif success_count > 0:
            messagebox.showwarning("Partial Success", f"Sent to {success_count} instructor(s), failed for {fail_count}.")
        else:
            messagebox.showerror("Failed", "Failed to send message. Please try again.")

    send_btn = ttk.Button(compose_frame, text="Send Message", command=send_message)
    send_btn.pack(pady=10)

    # Back button
    back_btn = ttk.Button(self.content_frame, text="← Back", command=self.show_children)
    back_btn.pack(pady=10)
ParentPortalGUI.message_teachers = message_teachers

def show_messages_interface(self):
    """Show messages interface"""
    self.clear_content()
    self.update_status("Messages")

    title = ttk.Label(self.content_frame, text="Messages", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Message categories
    categories_frame = ttk.Frame(self.content_frame)
    categories_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Button(categories_frame, text="Inbox",
              command=lambda: self.show_message_category("inbox")).pack(side=tk.LEFT, padx=5)
    ttk.Button(categories_frame, text="Sent",
              command=lambda: self.show_message_category("sent")).pack(side=tk.LEFT, padx=5)
    ttk.Button(categories_frame, text="Compose New",
              command=self.show_send_message_interface).pack(side=tk.LEFT, padx=5)

    # Messages display frame
    messages_frame = ttk.LabelFrame(self.content_frame, text="Inbox", padding=15)
    messages_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='messages'
        """)

        if cursor.fetchone():
            # Correct schema: id, sender_id, subject, sent_at, is_read (join users for sender name)
            cursor.execute("""
            SELECT m.id, COALESCE(u.first_name || ' ' || u.last_name, 'Unknown'), m.subject, m.sent_at, m.is_read
            FROM messages m
            LEFT JOIN users u ON m.sender_id = u.id
            WHERE m.recipient_id = ?
            ORDER BY m.sent_at DESC
            LIMIT 50
            """, (self.parent_id,))

            messages = cursor.fetchall()

            if messages:
                columns = ("From", "Subject", "Date", "Status")
                tree = ttk.Treeview(messages_frame, columns=columns, show="headings", height=15)

                tree.heading("From", text="From")
                tree.heading("Subject", text="Subject")
                tree.heading("Date", text="Date")
                tree.heading("Status", text="Status")

                tree.column("From", width=150)
                tree.column("Subject", width=300)
                tree.column("Date", width=150)
                tree.column("Status", width=100)

                for msg in messages:
                    status = "Read" if msg[4] else "Unread"
                    tree.insert('', tk.END, values=(msg[1], msg[2], msg[3], status), tags=(status,))

                tree.tag_configure('Unread', font=('Arial', 10, 'bold'))

                scrollbar = ttk.Scrollbar(messages_frame, orient=tk.VERTICAL, command=tree.yview)
                tree.configure(yscrollcommand=scrollbar.set)

                tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                def view_message():
                    selected = tree.selection()
                    if selected:
                        item = tree.item(selected[0])
                        messagebox.showinfo("Message", f"From: {item['values'][0]}\n"
                                                      f"Subject: {item['values'][1]}\n"
                                                      f"Date: {item['values'][2]}\n\n"
                                                      "Full message content would be displayed here.")

                ttk.Button(messages_frame, text="View Message", command=view_message).pack(pady=10)
            else:
                ttk.Label(messages_frame, text="No messages found", font=('Arial', 11)).pack(pady=50)
        else:
            ttk.Label(messages_frame, text="Messaging system not configured",
                     font=('Arial', 11)).pack(pady=20)

        conn.close()

    except Exception as e:
        ttk.Label(messages_frame, text=f"Error loading messages: {str(e)}",
                 font=('Arial', 10)).pack(pady=20)
ParentPortalGUI.show_messages_interface = show_messages_interface

def show_message_category(self, category):
    """Show specific message category"""
    self.clear_content()
    self.update_status(f"{category.capitalize()} Messages")

    title = ttk.Label(self.content_frame, text=f"{category.capitalize()} Messages",
                     style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Message categories buttons
    categories_frame = ttk.Frame(self.content_frame)
    categories_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Button(categories_frame, text="Inbox",
              command=lambda: self.show_message_category("inbox")).pack(side=tk.LEFT, padx=5)
    ttk.Button(categories_frame, text="Sent",
              command=lambda: self.show_message_category("sent")).pack(side=tk.LEFT, padx=5)
    ttk.Button(categories_frame, text="Compose New",
              command=self.show_send_message_interface).pack(side=tk.LEFT, padx=5)

    # Messages display frame
    messages_frame = ttk.LabelFrame(self.content_frame, text=category.capitalize(), padding=15)
    messages_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='messages'
        """)

        if cursor.fetchone():
            if category.lower() == "inbox":
                # Show received messages (correct schema: id, sender_id, subject, sent_at, is_read)
                cursor.execute("""
                SELECT m.id, COALESCE(u.first_name || ' ' || u.last_name, 'Unknown'), m.subject, m.sent_at, m.is_read
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                WHERE m.recipient_id = ?
                ORDER BY m.sent_at DESC
                LIMIT 50
                """, (self.parent_id,))
            elif category.lower() == "sent":
                # Show sent messages from multiple tables
                current_user = self.get_current_user()
                user_id = current_user.get('id') if current_user else self.parent_id
                user_email = current_user.get('email', '') if current_user else ''

                # First try messages table with sender_id
                cursor.execute("""
                    SELECT m.id, COALESCE(u.first_name || ' ' || u.last_name, 'Unknown') as recipient,
                           m.subject, m.sent_at as sent_date, 1
                    FROM messages m
                    LEFT JOIN users u ON m.recipient_id = u.id
                    WHERE m.sender_id = ? OR m.sender_id = ?
                    ORDER BY m.sent_at DESC
                    LIMIT 50
                """, (self.parent_id, user_id))
                messages_list = list(cursor.fetchall())

                # Also check email_log for sent emails
                if user_email:
                    cursor.execute("""
                        SELECT id, recipient, subject, sent_date, 1
                        FROM email_log
                        WHERE sender_email = ? OR sender_name LIKE ?
                        ORDER BY sent_date DESC
                        LIMIT 50
                    """, (user_email, f'%{current_user.get("username", "")}%'))
                    email_logs = cursor.fetchall()
                    for log in email_logs:
                        messages_list.append(log)

                # Sort combined results by date
                messages_list.sort(key=lambda x: x[3] if x[3] else '', reverse=True)
                messages = messages_list[:50]
            else:
                conn.close()
                return

            # For inbox, fetch messages normally
            if category.lower() == "inbox":
                messages = cursor.fetchall()

            if messages:
                if category.lower() == "inbox":
                    columns = ("From", "Subject", "Date", "Status")
                    tree = ttk.Treeview(messages_frame, columns=columns, show="headings", height=15)
                    tree.heading("From", text="From")
                    tree.heading("Subject", text="Subject")
                    tree.heading("Date", text="Date")
                    tree.heading("Status", text="Status")
                    tree.column("From", width=150)
                    tree.column("Subject", width=300)
                    tree.column("Date", width=150)
                    tree.column("Status", width=100)
                else:  # sent
                    columns = ("To", "Subject", "Date")
                    tree = ttk.Treeview(messages_frame, columns=columns, show="headings", height=15)
                    tree.heading("To", text="To")
                    tree.heading("Subject", text="Subject")
                    tree.heading("Date", text="Date")
                    tree.column("To", width=150)
                    tree.column("Subject", width=300)
                    tree.column("Date", width=150)

                for msg in messages:
                    if category.lower() == "inbox":
                        status = "Read" if msg[4] else "Unread"
                        tree.insert('', tk.END, values=(msg[1], msg[2], msg[3], status), tags=(status,))
                        tree.tag_configure('Unread', font=('Arial', 10, 'bold'))
                    else:
                        tree.insert('', tk.END, values=(msg[1], msg[2], msg[3]))

                scrollbar = ttk.Scrollbar(messages_frame, orient=tk.VERTICAL, command=tree.yview)
                tree.configure(yscrollcommand=scrollbar.set)

                tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                def view_message():
                    selected = tree.selection()
                    if selected:
                        item = tree.item(selected[0])
                        msg_id = messages[tree.index(selected[0])][0]

                        # Fetch full message (correct column: message or content, not message_body)
                        cursor.execute("SELECT COALESCE(message, content, '') FROM messages WHERE id = ?", (msg_id,))
                        result = cursor.fetchone()
                        body = result[0] if result else "Message body not available."

                        # Mark as read if inbox
                        if category.lower() == "inbox":
                            cursor.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (msg_id,))
                            conn.commit()

                        if category.lower() == "inbox":
                            messagebox.showinfo("Message", f"From: {item['values'][0]}\n"
                                                          f"Subject: {item['values'][1]}\n"
                                                          f"Date: {item['values'][2]}\n\n"
                                                          f"{body}")
                        else:
                            messagebox.showinfo("Message", f"To: {item['values'][0]}\n"
                                                          f"Subject: {item['values'][1]}\n"
                                                          f"Date: {item['values'][2]}\n\n"
                                                          f"{body}")

                        # Refresh the view
                        self.show_message_category(category)

                ttk.Button(messages_frame, text="View Message", command=view_message).pack(pady=10)
            else:
                ttk.Label(messages_frame, text=f"No {category} messages found",
                         font=('Arial', 11)).pack(pady=50)
        else:
            ttk.Label(messages_frame, text="Messaging system not configured",
                     font=('Arial', 11)).pack(pady=20)

        conn.close()

    except Exception as e:
        ttk.Label(messages_frame, text=f"Error loading messages: {str(e)}",
                 font=('Arial', 10)).pack(pady=20)
ParentPortalGUI.show_message_category = show_message_category

def _get_all_recipients(self):
    """Get all possible message recipients from database"""
    recipients = {}  # Maps display name to email
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        cursor = conn.cursor()

        # Get instructors
        cursor.execute('''
            SELECT first_name, last_name, email, department
            FROM instructors
            WHERE is_active = 1 AND email IS NOT NULL
            ORDER BY last_name, first_name
            LIMIT 50
        ''')
        for row in cursor.fetchall():
            first, last, email, dept = row
            display = f"{first} {last} - Instructor ({dept or 'General'})"
            recipients[display] = email

        # Get admin users
        cursor.execute('''
            SELECT first_name, last_name, email, role
            FROM users
            WHERE role IN ('admin', 'staff') AND email IS NOT NULL AND email != ''
            ORDER BY role, last_name, first_name
            LIMIT 20
        ''')
        for row in cursor.fetchall():
            first, last, email, role = row
            display = f"{first or ''} {last or ''} - {role.title()}".strip()
            if display and email:
                recipients[display] = email

        conn.close()
    except Exception as e:
        print(f"Error loading recipients: {e}")

    return recipients
ParentPortalGUI._get_all_recipients = _get_all_recipients

def show_send_message_interface(self):
    """Show send message interface - sends actual emails"""
    self.clear_content()
    self.update_status("Send Message")

    title = ttk.Label(self.content_frame, text="Compose Message", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Load recipients from database
    recipients = self._get_all_recipients()
    self._send_msg_recipients = recipients

    # Message form
    form_frame = ttk.LabelFrame(self.content_frame, text="New Message", padding=20)
    form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    # Recipient
    ttk.Label(form_frame, text="To:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
    recipient_var = tk.StringVar()
    recipient_combo = ttk.Combobox(form_frame, textvariable=recipient_var, width=60)
    recipient_values = ["-- Select Recipient --"] + list(recipients.keys())
    recipient_combo['values'] = recipient_values
    recipient_combo.set("-- Select Recipient --")
    recipient_combo.grid(row=0, column=1, pady=5, sticky='ew')

    # Or enter email directly
    ttk.Label(form_frame, text="Or Email:", font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=5)
    direct_email_entry = ttk.Entry(form_frame, width=50)
    direct_email_entry.grid(row=1, column=1, pady=5, sticky='ew')

    # Subject
    ttk.Label(form_frame, text="Subject:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
    subject_entry = ttk.Entry(form_frame, width=50)
    subject_entry.grid(row=2, column=1, pady=5, sticky='ew')

    # Message body
    ttk.Label(form_frame, text="Message:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='nw', pady=5)
    message_text = scrolledtext.ScrolledText(form_frame, height=12, width=50, wrap=tk.WORD)
    message_text.grid(row=3, column=1, pady=5, sticky='ew')

    form_frame.columnconfigure(1, weight=1)

    # Get sender info
    current_user = self.get_current_user()
    sender_name = "Parent/Guardian"
    sender_email = ""
    if current_user:
        first = current_user.get('first_name', '')
        last = current_user.get('last_name', '')
        sender_name = f"{first} {last}".strip() or current_user.get('username', 'Parent/Guardian')
        sender_email = current_user.get('email', '')

    # Buttons
    btn_frame = ttk.Frame(self.content_frame)
    btn_frame.pack(pady=10)

    def send_message():
        recipient_display = recipient_var.get()
        direct_email = direct_email_entry.get().strip()
        subject = subject_entry.get().strip()
        message = message_text.get('1.0', tk.END).strip()

        # Determine recipient email
        recipient_email = None
        recipient_name = ""

        if direct_email and '@' in direct_email:
            recipient_email = direct_email
            recipient_name = direct_email
        elif recipient_display and recipient_display != "-- Select Recipient --":
            recipient_email = self._send_msg_recipients.get(recipient_display)
            recipient_name = recipient_display

        if not recipient_email:
            messagebox.showwarning("Missing Recipient", "Please select a recipient or enter an email address.")
            return
        if not subject:
            messagebox.showwarning("Missing Subject", "Please enter a subject.")
            return
        if not message:
            messagebox.showwarning("Missing Message", "Please enter a message.")
            return

        # Build full email body with signature
        full_body = f"""{message}

---
Sent by: {sender_name}
Contact: {sender_email if sender_email else 'Via Guardian Portal'}

This message was sent through the University Guardian Portal.
"""

        # Send actual email
        try:
            success = False
            if EMAIL_SERVICE_AVAILABLE:
                success = send_email(recipient_email, subject, full_body)
            else:
                # Fallback: Store in database
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master WHERE type='table' AND name='messages'
                """)
                if cursor.fetchone():
                    # Use correct schema: sender_id, recipient_id, subject, content, sent_at
                    # Get recipient_id from users table if possible
                    cursor.execute("SELECT id FROM users WHERE email = ?", (recipient_email,))
                    recipient = cursor.fetchone()
                    recipient_id = recipient[0] if recipient else 0
                    cursor.execute("""
                        INSERT INTO messages (sender_id, recipient_id, subject, content, sent_at, is_read)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (self.parent_id or 0, recipient_id, subject, full_body, datetime.datetime.now().isoformat(), 0))
                    conn.commit()
                    success = True
                conn.close()

            if success:
                messagebox.showinfo("Success", f"Message sent to {recipient_name}!")
                subject_entry.delete(0, tk.END)
                message_text.delete('1.0', tk.END)
                direct_email_entry.delete(0, tk.END)
                recipient_combo.set("-- Select Recipient --")
            else:
                messagebox.showerror("Failed", "Failed to send message. Please try again.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send message: {str(e)}")

    ttk.Button(btn_frame, text="Send", command=send_message).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=self.show_messages_interface).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.show_send_message_interface = show_send_message_interface

def show_group_message_interface(self):
    """Show group messages interface"""
    self.clear_content()
    self.update_status("Group Messages")

    title = ttk.Label(self.content_frame, text="Group Messages", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Group selection
    groups_frame = ttk.LabelFrame(self.content_frame, text="Select Group", padding=15)
    groups_frame.pack(fill=tk.X, padx=20, pady=10)

    groups = ["All Instructors", "Course Guardians", "Sports Team", "Music Department", "Special Education Team"]

    for group in groups:
        btn = ttk.Button(groups_frame, text=group,
                       command=lambda g=group: self.view_group_messages(g))
        btn.pack(pady=5, fill=tk.X)

    # Recent group messages
    messages_frame = ttk.LabelFrame(self.content_frame, text="Recent Group Messages", padding=15)
    messages_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='group_messages'
        """)

        if cursor.fetchone():
            # Correct schema: id, sender_id, group_type, group_id, subject, content, sent_at
            cursor.execute("""
            SELECT gm.group_type, gm.subject, COALESCE(u.first_name || ' ' || u.last_name, 'Unknown'), gm.sent_at, 1
            FROM group_messages gm
            LEFT JOIN users u ON gm.sender_id = u.id
            ORDER BY gm.sent_at DESC
            LIMIT 20
            """, ())

            messages = cursor.fetchall()

            if messages:
                columns = ("Group", "Subject", "From", "Date", "Replies")
                tree = ttk.Treeview(messages_frame, columns=columns, show="headings", height=10)

                for col in columns:
                    tree.heading(col, text=col)
                    tree.column(col, width=120)

                for msg in messages:
                    tree.insert('', tk.END, values=msg)

                scrollbar = ttk.Scrollbar(messages_frame, orient=tk.VERTICAL, command=tree.yview)
                tree.configure(yscrollcommand=scrollbar.set)

                tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            else:
                ttk.Label(messages_frame, text="No group messages found", font=('Arial', 11)).pack(pady=50)
        else:
            ttk.Label(messages_frame, text="Group messaging not configured",
                     font=('Arial', 11)).pack(pady=20)

        conn.close()

    except Exception as e:
        ttk.Label(messages_frame, text=f"Error loading group messages: {str(e)}",
                 font=('Arial', 10)).pack(pady=20)
ParentPortalGUI.show_group_message_interface = show_group_message_interface

def view_group_messages(self, group_name):
    """View messages for a specific group"""
    self.clear_content()
    self.update_status(f"Group Messages - {group_name}")

    title = ttk.Label(self.content_frame, text=f"Group: {group_name}",
                     style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Back button
    ttk.Button(self.content_frame, text="← Back to Group Messages",
              command=self.show_group_message_interface).pack(anchor='w', padx=20, pady=5)

    # Messages display frame
    messages_frame = ttk.LabelFrame(self.content_frame, text=f"{group_name} Messages", padding=15)
    messages_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Check if group_messages table exists
        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='group_messages'
        """)

        if cursor.fetchone():
            # Fetch messages for this group (correct schema: id, sender_id, group_type, subject, content, sent_at)
            cursor.execute("""
            SELECT gm.id, gm.subject, COALESCE(u.first_name || ' ' || u.last_name, 'Unknown'), gm.content, gm.sent_at, 1
            FROM group_messages gm
            LEFT JOIN users u ON gm.sender_id = u.id
            WHERE gm.group_type = ?
            ORDER BY gm.sent_at DESC
            LIMIT 50
            """, (group_name,))

            messages = cursor.fetchall()

            if messages:
                # Create treeview
                columns = ("Subject", "From", "Date", "Replies")
                tree = ttk.Treeview(messages_frame, columns=columns, show="headings", height=15)

                tree.heading("Subject", text="Subject")
                tree.heading("From", text="From")
                tree.heading("Date", text="Date")
                tree.heading("Replies", text="Replies")

                tree.column("Subject", width=300)
                tree.column("From", width=150)
                tree.column("Date", width=150)
                tree.column("Replies", width=100)

                for msg in messages:
                    tree.insert('', tk.END, values=(msg[1], msg[2], msg[4], msg[5]))

                scrollbar = ttk.Scrollbar(messages_frame, orient=tk.VERTICAL, command=tree.yview)
                tree.configure(yscrollcommand=scrollbar.set)

                tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                def view_message():
                    selected = tree.selection()
                    if selected:
                        item = tree.item(selected[0])
                        msg = messages[tree.index(selected[0])]

                        messagebox.showinfo("Group Message",
                                          f"Subject: {msg[1]}\n"
                                          f"From: {msg[2]}\n"
                                          f"Date: {msg[4]}\n"
                                          f"Replies: {msg[5]}\n\n"
                                          f"{msg[3]}")

                ttk.Button(messages_frame, text="View Message", command=view_message).pack(pady=10)
            else:
                ttk.Label(messages_frame, text=f"No messages found for {group_name}",
                         font=('Arial', 11)).pack(pady=50)
        else:
            ttk.Label(messages_frame, text="Group messaging not configured",
                     font=('Arial', 11)).pack(pady=20)

        conn.close()

    except Exception as e:
        ttk.Label(messages_frame, text=f"Error loading group messages: {str(e)}",
                 font=('Arial', 10)).pack(pady=20)
ParentPortalGUI.view_group_messages = view_group_messages

def show_announcements_interface(self):
    """Show university announcements interface"""
    self.clear_content()
    self.update_status("University Announcements")

    title = ttk.Label(self.content_frame, text="University Announcements", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Filter options
    filter_frame = ttk.Frame(self.content_frame)
    filter_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=5)
    filter_var = tk.StringVar(value="All")
    categories = ["All", "Academic", "Events", "Emergency", "General", "Sports", "Arts"]

    for cat in categories:
        ttk.Radiobutton(filter_frame, text=cat, value=cat, variable=filter_var).pack(side=tk.LEFT, padx=5)

    # Announcements display
    announcements_frame = ttk.LabelFrame(self.content_frame, text="Recent Announcements", padding=15)
    announcements_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='announcements'
        """)

        if cursor.fetchone():
            # Use correct column names from the announcements table schema
            cursor.execute("""
            SELECT a.title, a.target_audience, a.content, a.created_at,
                   COALESCE(u.username, 'System'), a.is_urgent
            FROM announcements a
            LEFT JOIN users u ON a.creator_id = u.id
            WHERE a.is_active = 1
            ORDER BY a.is_urgent DESC, a.created_at DESC
            LIMIT 30
            """)

            announcements = cursor.fetchall()

            if announcements:
                # Create scrollable frame for announcements
                canvas = tk.Canvas(announcements_frame)
                scrollbar = ttk.Scrollbar(announcements_frame, orient="vertical", command=canvas.yview)
                scrollable_frame = ttk.Frame(canvas)

                scrollable_frame.bind(
                    "<Configure>",
                    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
                )

                canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
                canvas.configure(yscrollcommand=scrollbar.set)

                for announcement in announcements:
                    category = announcement[1] or 'General'
                    ann_card = ttk.LabelFrame(scrollable_frame, text=f"{announcement[0]} [{category}]", padding=10)
                    ann_card.pack(fill=tk.X, padx=5, pady=5)

                    posted_date = announcement[3] or 'Unknown'
                    posted_by = announcement[4] or 'System'
                    ttk.Label(ann_card, text=f"Posted by: {posted_by} on {posted_date}",
                             font=('Arial', 8, 'italic')).pack(anchor='w')
                    ttk.Label(ann_card, text=announcement[2], wraplength=600).pack(anchor='w', pady=5)

                    # is_urgent is 1 for urgent, 0 for not urgent
                    if announcement[5] == 1:
                        priority_label = ttk.Label(ann_card, text="URGENT", foreground='red', font=('Arial', 9, 'bold'))
                        priority_label.pack(anchor='w')

                canvas.pack(side="left", fill="both", expand=True)
                scrollbar.pack(side="right", fill="y")
            else:
                ttk.Label(announcements_frame, text="No announcements at this time",
                         font=('Arial', 11)).pack(pady=50)
        else:
            ttk.Label(announcements_frame, text="Announcements system not configured",
                     font=('Arial', 11)).pack(pady=20)

        conn.close()

    except Exception as e:
        ttk.Label(announcements_frame, text=f"Error loading announcements: {str(e)}",
                 font=('Arial', 10)).pack(pady=20)
ParentPortalGUI.show_announcements_interface = show_announcements_interface
