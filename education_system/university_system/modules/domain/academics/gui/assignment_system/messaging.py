"""Messaging system"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
import json
import csv
from PIL import Image, ImageTk
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.shared.constants import paths
from collections import deque



class MessagingManager:
    """Messaging system"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def load_assignments_for_message(self, combo):
        """Load assignments for message reference"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT id, title, module_code FROM assignments WHERE is_active = 1 ORDER BY due_date DESC')
            assignments = cursor.fetchall()

            assignment_list = ["None"] + [f"{title} ({module})" for aid, title, module in assignments]
            combo['values'] = assignment_list
            combo.set("None")

            # Create mapping for assignment IDs
            self.message_assignment_map = {"None": None}
            for aid, title, module in assignments:
                self.message_assignment_map[f"{title} ({module})"] = aid

            conn.close()

        except Exception as e:
            print(f"Error loading assignments: {e}")

    def _load_assignments_for_compose(self, assignment_combo):
        """Load assignments for message compose"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, title, module_code
                FROM assignments
                WHERE is_active = 1
                ORDER BY due_date DESC
                LIMIT 50
            ''')

            assignments = cursor.fetchall()
            conn.close()

            values = ["(No Assignment)"] + [f"{a[0]}: {a[1]} ({a[2]})" for a in assignments]
            assignment_combo['values'] = values
            assignment_combo.current(0)

        except Exception as e:
            print(f"Error loading assignments: {e}")

    def show_send_messages(self):
        """Show message sending interface"""
        if not self._check_permission('manage_assignments'):
            return
        
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="Send Messages", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Message composition frame
        compose_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Compose Message", padding=20)
        compose_frame.pack(fill='both', expand=True)
        
        # Recipient type
        ttk.Label(compose_frame, text="Send To:", font=('Arial', 12, 'bold')).grid(row=0, column=0, sticky='w', pady=(0, 10))
        
        self.recipient_type_var = tk.StringVar(value="module")
        recipient_frame = ttk.Frame(compose_frame)
        recipient_frame.grid(row=1, column=0, columnspan=2, sticky='w', pady=(0, 20))
        
        ttk.Radiobutton(recipient_frame, text="All students in module", 
                       variable=self.recipient_type_var, value="module").pack(anchor='w')
        ttk.Radiobutton(recipient_frame, text="Specific student", 
                       variable=self.recipient_type_var, value="student").pack(anchor='w')
        ttk.Radiobutton(recipient_frame, text="All instructors", 
                       variable=self.recipient_type_var, value="instructors").pack(anchor='w')
        
        # Module/Student selection
        selection_frame = ttk.Frame(compose_frame)
        selection_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(0, 20))
        
        ttk.Label(selection_frame, text="Module/Student:").pack(side='left')
        self.recipient_selection_var = tk.StringVar()
        self.recipient_combo = ttk.Combobox(selection_frame, textvariable=self.recipient_selection_var, width=40)
        self.recipient_combo.pack(side='left', padx=(10, 0))
        
        # Bind recipient type change to update combo options
        for widget in recipient_frame.winfo_children():
            if isinstance(widget, ttk.Radiobutton):
                widget.configure(command=self.update_recipient_options)
        
        # Subject
        ttk.Label(compose_frame, text="Subject:").grid(row=3, column=0, sticky='w', pady=5)
        self.message_subject_var = tk.StringVar()
        ttk.Entry(compose_frame, textvariable=self.message_subject_var, width=60).grid(row=3, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # Message body
        ttk.Label(compose_frame, text="Message:").grid(row=4, column=0, sticky='nw', pady=5)
        self.message_body_text = scrolledtext.ScrolledText(compose_frame, height=10, width=60)
        self.message_body_text.grid(row=4, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # Assignment reference (optional)
        ttk.Label(compose_frame, text="Related Assignment (optional):").grid(row=5, column=0, sticky='w', pady=5)
        self.message_assignment_var = tk.StringVar()
        assignment_combo = ttk.Combobox(compose_frame, textvariable=self.message_assignment_var, width=40)
        assignment_combo.grid(row=5, column=1, sticky='w', pady=5, padx=(10, 0))
        self.load_assignments_for_message(assignment_combo)
        
        # Send button
        ttk.Button(compose_frame, text="Send Message", 
                  command=self.send_message_gui).grid(row=6, column=1, sticky='e', pady=(20, 0))
        
        compose_frame.grid_columnconfigure(1, weight=1)
        
        # Initialize recipient options
        self.update_recipient_options()
    

    def update_recipient_options(self):
        """Update recipient options based on selection type"""
        recipient_type = self.recipient_type_var.get()
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            if recipient_type == "module":
                cursor.execute('SELECT module_code, module_name FROM modules ORDER BY module_code')
                options = [f"{code} - {name}" for code, name in cursor.fetchall()]
            elif recipient_type == "student":
                cursor.execute('SELECT student_id, first_name, last_name FROM students ORDER BY last_name, first_name')
                options = [f"{sid} - {fname} {lname}" for sid, fname, lname in cursor.fetchall()]
            else:  # instructors
                options = ["All Instructors"]
            
            self.recipient_combo['values'] = options
            if options:
                self.recipient_combo.set(options[0])
            
            conn.close()
            
        except Exception as e:
            print(f"Error updating recipient options: {e}")
    

    def send_message_gui(self):
        """Send message through GUI"""
        try:
            subject = self.message_subject_var.get().strip()
            message = self.message_body_text.get(1.0, tk.END).strip()
            
            if not subject or not message:
                messagebox.showerror("Error", "Subject and message are required")
                return
            
            recipient_type = self.recipient_type_var.get()
            selection = self.recipient_selection_var.get()
            
            if not selection:
                messagebox.showerror("Error", "Please select a recipient")
                return
            
            # Get assignment ID if selected
            assignment_id = self.message_assignment_map.get(self.message_assignment_var.get())
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            recipients = []
            
            if recipient_type == "module":
                # Get module code
                module_code = selection.split(' - ')[0]
                cursor.execute('''
                SELECT u.id FROM users u
                JOIN students s ON u.student_id = s.student_id
                JOIN student_modules sm ON s.student_id = sm.student_id
                WHERE sm.module_code = ?
                ''', (module_code,))
                recipients = [row[0] for row in cursor.fetchall()]
                
            elif recipient_type == "student":
                # Get specific student
                student_id = selection.split(' - ')[0]
                cursor.execute('SELECT u.id FROM users u WHERE u.student_id = ?', (student_id,))
                result = cursor.fetchone()
                if result:
                    recipients = [result[0]]
                    
            elif recipient_type == "instructors":
                # Get all instructors
                cursor.execute("SELECT id FROM users WHERE role IN ('instructor', 'admin')")
                recipients = [row[0] for row in cursor.fetchall()]
            
            if not recipients:
                messagebox.showerror("Error", "No recipients found")
                conn.close()
                return
            
            # Send messages
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sender_id = self.auth.current_user['id']

            # Get sender name for email
            cursor.execute('SELECT first_name, last_name FROM users WHERE id = ?', (sender_id,))
            sender_result = cursor.fetchone()
            sender_name = f"{sender_result[0]} {sender_result[1]}" if sender_result else "Instructor"

            emails_sent = 0
            emails_failed = 0

            for recipient_id in recipients:
                # Save message to database
                cursor.execute('''
                INSERT INTO messages (sender_id, recipient_id, subject, message, assignment_id, sent_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (sender_id, recipient_id, subject, message, assignment_id, timestamp))

                # Send actual email
                try:
                    # Get recipient email
                    cursor.execute('SELECT email, first_name FROM users WHERE id = ?', (recipient_id,))
                    recipient_result = cursor.fetchone()

                    if recipient_result and recipient_result[0]:
                        recipient_email = recipient_result[0]
                        recipient_fname = recipient_result[1]

                        # Use email template
                        try:
                            from education_system.university_system.infrastructure.email.template_utils import render_template
                            assignment_note = "This message is related to an assignment.\n\n" if assignment_id else ""
                            email_subject, email_body = render_template("assignment_system_message", {
                                "recipient_name": recipient_fname,
                                "sender_name": sender_name,
                                "subject": subject,
                                "message": message,
                                "assignment_note": assignment_note,
                                "timestamp": timestamp
                            })
                        except Exception as template_error:
                            # Fallback to hardcoded email
                            email_body = f"Hello {recipient_fname},\n\n"
                            email_body += f"You have received a new message from {sender_name}:\n\n"
                            email_body += f"Subject: {subject}\n\n"
                            email_body += f"{message}\n\n"
                            if assignment_id:
                                email_body += f"This message is related to an assignment.\n\n"
                            email_body += f"Please log in to the Assignment System to view and respond to this message.\n\n"
                            email_body += f"Sent: {timestamp}\n"
                            email_subject = f"[Assignment System] {subject}"

                        # Send email
                        from education_system.university_system.infrastructure.email.email_service import send_email
                        send_email(
                            recipient_email=recipient_email,
                            subject=email_subject,
                            body=email_body
                        )
                        emails_sent += 1
                except Exception as email_error:
                    print(f"Failed to send email to recipient {recipient_id}: {email_error}")
                    emails_failed += 1

            conn.commit()
            conn.close()

            # Show success message with email status
            success_msg = f"Message saved for {len(recipients)} recipients!"
            if emails_sent > 0:
                success_msg += f"\n✓ {emails_sent} email(s) sent successfully"
            if emails_failed > 0:
                success_msg += f"\n⚠ {emails_failed} email(s) failed to send"

            messagebox.showinfo("Success", success_msg)

            # Clear form
            self.message_subject_var.set('')
            self.message_body_text.delete(1.0, tk.END)
            self.message_assignment_var.set("None")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send message: {e}")
    
    # GROUP ASSIGNMENT CREATION (enhanced GUI)

    def view_messages(self, *args, **kwargs):
        """View and manage all messages for the current user.
    
        Features:
        - Display inbox with all received messages
        - View sent messages
        - Show message details with sender, subject, date, and read status
        - Mark messages as read/unread
        - Reply to messages
        - Delete messages
        - Search and filter messages
        """
        try:
            # Create messages window
            messages_window = tk.Toplevel(self.root)
            messages_window.title("Messages")
            messages_window.geometry("1000x700")
            messages_window.configure(bg='#f0f0f0')
    
            # Get current user ID
            user_id = self.auth.current_user.get('id')
            if not user_id:
                messagebox.showerror("Error", "User not authenticated")
                messages_window.destroy()
                return
    
            # Ensure messages table exists
            self.gui.db._ensure_messages_table()
    
            # Create notebook for tabs
            notebook = ttk.Notebook(messages_window)
            notebook.pack(fill='both', expand=True, padx=10, pady=10)
    
            # Inbox tab
            inbox_frame = ttk.Frame(notebook)
            notebook.add(inbox_frame, text="Inbox")
            self._create_inbox_view(inbox_frame, user_id)
    
            # Sent messages tab
            sent_frame = ttk.Frame(notebook)
            notebook.add(sent_frame, text="Sent")
            self._create_sent_view(sent_frame, user_id)
    
            # Compose message tab
            compose_frame = ttk.Frame(notebook)
            notebook.add(compose_frame, text="Compose")
            self._create_compose_view(compose_frame, user_id)
    
            # Archive tab
            archive_frame = ttk.Frame(notebook)
            notebook.add(archive_frame, text="Archive")
            self._create_archive_view(archive_frame, user_id)
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load messages: {str(e)}")
            print(f"Error in view_messages: {e}")
    

    def _create_inbox_view(self, parent, user_id):
        """Create inbox view with message list"""
        # Search frame
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill='x', padx=10, pady=10)
    
        ttk.Label(search_frame, text="Search:").pack(side='left', padx=5)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side='left', padx=5)
    
        # Filter options
        filter_var = tk.StringVar(value="all")
        ttk.Radiobutton(search_frame, text="All", variable=filter_var, value="all").pack(side='left', padx=5)
        ttk.Radiobutton(search_frame, text="Unread", variable=filter_var, value="unread").pack(side='left', padx=5)
        ttk.Radiobutton(search_frame, text="Read", variable=filter_var, value="read").pack(side='left', padx=5)
    
        # Refresh button
        refresh_btn = ttk.Button(search_frame, text="Refresh",
                                command=lambda: self._refresh_inbox(tree, user_id, search_var.get(), filter_var.get()))
        refresh_btn.pack(side='right', padx=5)
    
        # Messages list
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
    
        # Treeview for messages
        columns = ('Status', 'From', 'Subject', 'Date')
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)
    
        tree.heading('#0', text='ID')
        tree.heading('Status', text='Status')
        tree.heading('From', text='From')
        tree.heading('Subject', text='Subject')
        tree.heading('Date', text='Date')
    
        tree.column('#0', width=50)
        tree.column('Status', width=80)
        tree.column('From', width=150)
        tree.column('Subject', width=400)
        tree.column('Date', width=150)
    
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
    
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
    
        # Action buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill='x', padx=10, pady=10)
    
        ttk.Button(button_frame, text="View Message",
                  command=lambda: self._view_message_details(tree, user_id)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Mark as Read",
                  command=lambda: self._mark_message_read(tree, user_id, True)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Mark as Unread",
                  command=lambda: self._mark_message_read(tree, user_id, False)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Archive",
                  command=lambda: self._archive_message(tree, user_id)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Delete",
                  command=lambda: self._delete_message(tree, user_id, 'recipient')).pack(side='left', padx=5)
    
        # Load messages
        self._refresh_inbox(tree, user_id, search_var.get(), filter_var.get())
    
        # Bind double-click to view message
        tree.bind('<Double-1>', lambda e: self._view_message_details(tree, user_id))
    

    def _refresh_inbox(self, tree, user_id, search_text="", filter_type="all"):
        """Refresh inbox with messages"""
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Build query
            query = '''
                SELECT m.id, m.sender_id, u.username, m.subject, m.sent_at, m.is_read
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.recipient_id = ? AND m.is_deleted_by_recipient = 0 AND m.is_archived = 0
            '''
            params = [user_id]
    
            if filter_type == "unread":
                query += " AND m.is_read = 0"
            elif filter_type == "read":
                query += " AND m.is_read = 1"
    
            if search_text:
                query += " AND (m.subject LIKE ? OR u.username LIKE ?)"
                params.extend([f"%{search_text}%", f"%{search_text}%"])
    
            query += " ORDER BY m.sent_at DESC"
    
            cursor.execute(query, params)
            messages = cursor.fetchall()
    
            for msg in messages:
                msg_id, sender_id, sender_name, subject, sent_at, is_read = msg
                status = "Read" if is_read else "Unread"
    
                # Format date
                try:
                    date_obj = datetime.fromisoformat(sent_at)
                    formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    formatted_date = sent_at
    
                # Insert into tree with bold font for unread
                item_id = tree.insert('', 'end', text=msg_id,
                                     values=(status, sender_name, subject, formatted_date),
                                     tags=('unread',) if not is_read else ())
    
            # Configure tag for unread messages
            tree.tag_configure('unread', font=('TkDefaultFont', 10, 'bold'))
    
            conn.close()
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load messages: {str(e)}")
            print(f"Error refreshing inbox: {e}")
    

    def _create_sent_view(self, parent, user_id):
        """Create sent messages view"""
        # Search frame
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill='x', padx=10, pady=10)
    
        ttk.Label(search_frame, text="Search:").pack(side='left', padx=5)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side='left', padx=5)
    
        # Refresh button
        refresh_btn = ttk.Button(search_frame, text="Refresh",
                                command=lambda: self._refresh_sent(tree, user_id, search_var.get()))
        refresh_btn.pack(side='right', padx=5)
    
        # Messages list
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
    
        columns = ('To', 'Subject', 'Date', 'Read')
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)
    
        tree.heading('#0', text='ID')
        tree.heading('To', text='To')
        tree.heading('Subject', text='Subject')
        tree.heading('Date', text='Date')
        tree.heading('Read', text='Status')
    
        tree.column('#0', width=50)
        tree.column('To', width=150)
        tree.column('Subject', width=400)
        tree.column('Date', width=150)
        tree.column('Read', width=100)
    
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
    
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
    
        # Action buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill='x', padx=10, pady=10)
    
        ttk.Button(button_frame, text="View Message",
                  command=lambda: self._view_sent_message_details(tree, user_id)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Delete",
                  command=lambda: self._delete_message(tree, user_id, 'sender')).pack(side='left', padx=5)
    
        # Load messages
        self._refresh_sent(tree, user_id, search_var.get())
    
        # Bind double-click
        tree.bind('<Double-1>', lambda e: self._view_sent_message_details(tree, user_id))
    

    def _refresh_sent(self, tree, user_id, search_text=""):
        """Refresh sent messages"""
        for item in tree.get_children():
            tree.delete(item)
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            query = '''
                SELECT m.id, u.username, m.subject, m.sent_at, m.is_read
                FROM messages m
                JOIN users u ON m.recipient_id = u.id
                WHERE m.sender_id = ? AND m.is_deleted_by_sender = 0
            '''
            params = [user_id]
    
            if search_text:
                query += " AND (m.subject LIKE ? OR u.username LIKE ?)"
                params.extend([f"%{search_text}%", f"%{search_text}%"])
    
            query += " ORDER BY m.sent_at DESC"
    
            cursor.execute(query, params)
            messages = cursor.fetchall()
    
            for msg in messages:
                msg_id, recipient_name, subject, sent_at, is_read = msg
                status = "Read by recipient" if is_read else "Unread"
    
                try:
                    date_obj = datetime.fromisoformat(sent_at)
                    formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    formatted_date = sent_at

                tree.insert('', 'end', text=msg_id,
                           values=(recipient_name, subject, formatted_date, status))
    
            conn.close()
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load sent messages: {str(e)}")
            print(f"Error refreshing sent messages: {e}")
    

    def _create_compose_view(self, parent, user_id):
        """Create compose message view"""
        # Main frame with scrollbar
        canvas = tk.Canvas(parent, bg='#f0f0f0')
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
    
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
    
        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
    
        canvas.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar.pack(side='right', fill='y')
    
        # Compose form
        form_frame = ttk.LabelFrame(scrollable_frame, text="New Message", padding=20)
        form_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
        # Recipient
        ttk.Label(form_frame, text="To (Username):").grid(row=0, column=0, sticky='w', pady=5)
        recipient_var = tk.StringVar()
        recipient_entry = ttk.Entry(form_frame, textvariable=recipient_var, width=50)
        recipient_entry.grid(row=0, column=1, sticky='ew', pady=5, padx=5)
    
        # Browse recipients button
        ttk.Button(form_frame, text="Browse Users",
                  command=lambda: self._browse_users(recipient_var)).grid(row=0, column=2, padx=5)
    
        # Subject
        ttk.Label(form_frame, text="Subject:").grid(row=1, column=0, sticky='w', pady=5)
        subject_var = tk.StringVar()
        subject_entry = ttk.Entry(form_frame, textvariable=subject_var, width=50)
        subject_entry.grid(row=1, column=1, columnspan=2, sticky='ew', pady=5, padx=5)
    
        # Message body
        ttk.Label(form_frame, text="Message:").grid(row=2, column=0, sticky='nw', pady=5)
        message_text = scrolledtext.ScrolledText(form_frame, width=50, height=15, wrap=tk.WORD)
        message_text.grid(row=2, column=1, columnspan=2, sticky='ew', pady=5, padx=5)
    
        # Attachment (optional)
        ttk.Label(form_frame, text="Attachment:").grid(row=3, column=0, sticky='w', pady=5)
        attachment_var = tk.StringVar()
        attachment_entry = ttk.Entry(form_frame, textvariable=attachment_var, width=50, state='readonly')
        attachment_entry.grid(row=3, column=1, sticky='ew', pady=5, padx=5)
        ttk.Button(form_frame, text="Browse",
                  command=lambda: self._browse_attachment(attachment_var)).grid(row=3, column=2, padx=5)
    
        # Assignment reference (optional)
        ttk.Label(form_frame, text="Assignment:").grid(row=4, column=0, sticky='w', pady=5)
        assignment_var = tk.StringVar()
        assignment_combo = ttk.Combobox(form_frame, textvariable=assignment_var, width=48, state='readonly')
        assignment_combo.grid(row=4, column=1, columnspan=2, sticky='ew', pady=5, padx=5)
    
        # Load assignments
        self._load_assignments_for_compose(assignment_combo)
    
        form_frame.columnconfigure(1, weight=1)
    
        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill='x', padx=10, pady=10)
    
        ttk.Button(button_frame, text="Send Message",
                  command=lambda: self._send_composed_message(
                      user_id, recipient_var.get(), subject_var.get(),
                      message_text.get('1.0', 'end-1c'), attachment_var.get(),
                      assignment_var.get(), recipient_entry, subject_entry, message_text
                  )).pack(side='left', padx=5)
    
        ttk.Button(button_frame, text="Clear Form",
                  command=lambda: self._clear_compose_form(
                      recipient_entry, subject_entry, message_text, attachment_var, assignment_combo
                  )).pack(side='left', padx=5)
    

    def _create_archive_view(self, parent, user_id):
        """Create archive view"""
        # Messages list
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
        columns = ('From', 'Subject', 'Date')
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)
    
        tree.heading('#0', text='ID')
        tree.heading('From', text='From')
        tree.heading('Subject', text='Subject')
        tree.heading('Date', text='Date')
    
        tree.column('#0', width=50)
        tree.column('From', width=200)
        tree.column('Subject', width=450)
        tree.column('Date', width=150)
    
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
    
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
    
        # Action buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill='x', padx=10, pady=10)
    
        ttk.Button(button_frame, text="View Message",
                  command=lambda: self._view_message_details(tree, user_id)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Unarchive",
                  command=lambda: self._unarchive_message(tree, user_id)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Delete",
                  command=lambda: self._delete_message(tree, user_id, 'recipient')).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Refresh",
                  command=lambda: self._refresh_archive(tree, user_id)).pack(side='right', padx=5)
    
        # Load archived messages
        self._refresh_archive(tree, user_id)
    
        tree.bind('<Double-1>', lambda e: self._view_message_details(tree, user_id))
    

    def _refresh_archive(self, tree, user_id):
        """Refresh archived messages"""
        for item in tree.get_children():
            tree.delete(item)
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
                SELECT m.id, u.username, m.subject, m.sent_at
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.recipient_id = ? AND m.is_archived = 1 AND m.is_deleted_by_recipient = 0
                ORDER BY m.sent_at DESC
            ''', (user_id,))
    
            messages = cursor.fetchall()
    
            for msg in messages:
                msg_id, sender_name, subject, sent_at = msg
    
                try:
                    date_obj = datetime.fromisoformat(sent_at)
                    formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    formatted_date = sent_at

                tree.insert('', 'end', text=msg_id,
                           values=(sender_name, subject, formatted_date))
    
            conn.close()
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load archived messages: {str(e)}")
            print(f"Error refreshing archive: {e}")
    

    def _view_message_details(self, tree, user_id):
        """View full message details"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a message to view")
            return
    
        msg_id = tree.item(selection[0])['text']
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
                SELECT m.*, u1.username as sender_name, u2.username as recipient_name
                FROM messages m
                JOIN users u1 ON m.sender_id = u1.id
                JOIN users u2 ON m.recipient_id = u2.id
                WHERE m.id = ?
            ''', (msg_id,))
    
            message = cursor.fetchone()
    
            if not message:
                messagebox.showerror("Error", "Message not found")
                conn.close()
                return
    
            # Mark as read if recipient is viewing
            if message[2] == user_id and not message[8]:  # recipient_id and is_read
                cursor.execute('''
                    UPDATE messages SET is_read = 1, read_at = ? WHERE id = ?
                ''', (datetime.now().isoformat(), msg_id))
                conn.commit()
    
            conn.close()
    
            # Create detail window
            detail_window = tk.Toplevel(self.root)
            detail_window.title("Message Details")
            detail_window.geometry("800x600")
            detail_window.configure(bg='#f0f0f0')
    
            # Message info frame
            info_frame = ttk.LabelFrame(detail_window, text="Message Information", padding=10)
            info_frame.pack(fill='x', padx=10, pady=10)
    
            ttk.Label(info_frame, text="From:").grid(row=0, column=0, sticky='w', padx=5, pady=2)
            ttk.Label(info_frame, text=message[15], font=('TkDefaultFont', 10, 'bold')).grid(row=0, column=1, sticky='w', padx=5, pady=2)
    
            ttk.Label(info_frame, text="To:").grid(row=1, column=0, sticky='w', padx=5, pady=2)
            ttk.Label(info_frame, text=message[16], font=('TkDefaultFont', 10, 'bold')).grid(row=1, column=1, sticky='w', padx=5, pady=2)
    
            ttk.Label(info_frame, text="Subject:").grid(row=2, column=0, sticky='w', padx=5, pady=2)
            ttk.Label(info_frame, text=message[3], font=('TkDefaultFont', 10, 'bold')).grid(row=2, column=1, sticky='w', padx=5, pady=2)
    
            ttk.Label(info_frame, text="Date:").grid(row=3, column=0, sticky='w', padx=5, pady=2)
            try:
                date_obj = datetime.fromisoformat(message[12])
                formatted_date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                formatted_date = message[12]
            ttk.Label(info_frame, text=formatted_date).grid(row=3, column=1, sticky='w', padx=5, pady=2)
    
            # Message content frame
            content_frame = ttk.LabelFrame(detail_window, text="Message Content", padding=10)
            content_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
            message_content = message[4] or message[5] or "No content"
            content_text = scrolledtext.ScrolledText(content_frame, width=70, height=15, wrap=tk.WORD)
            content_text.pack(fill='both', expand=True)
            content_text.insert('1.0', message_content)
            content_text.config(state='disabled')
    
            # Attachment info
            if message[6]:  # attachment_path
                ttk.Label(content_frame, text=f"Attachment: {message[6]}",
                         font=('TkDefaultFont', 9, 'italic')).pack(pady=5)
    
            # Action buttons
            button_frame = ttk.Frame(detail_window)
            button_frame.pack(fill='x', padx=10, pady=10)
    
            if message[2] == user_id:  # If current user is recipient
                ttk.Button(button_frame, text="Reply",
                          command=lambda: self._reply_to_message(msg_id, message[1], message[3])).pack(side='left', padx=5)
    
            ttk.Button(button_frame, text="Close",
                      command=detail_window.destroy).pack(side='right', padx=5)
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to view message: {str(e)}")
            print(f"Error viewing message: {e}")
    

    def _view_sent_message_details(self, tree, user_id):
        """View sent message details"""
        self._view_message_details(tree, user_id)
    

    def _mark_message_read(self, tree, user_id, is_read):
        """Mark message as read or unread"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a message")
            return
    
        msg_id = tree.item(selection[0])['text']
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            read_at = datetime.now().isoformat() if is_read else None
            cursor.execute('''
                UPDATE messages SET is_read = ?, read_at = ? WHERE id = ? AND recipient_id = ?
            ''', (1 if is_read else 0, read_at, msg_id, user_id))
    
            conn.commit()
            conn.close()
    
            # Refresh the tree
            self._refresh_inbox(tree, user_id)
    
            status = "read" if is_read else "unread"
            messagebox.showinfo("Success", f"Message marked as {status}")
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update message: {str(e)}")
            print(f"Error marking message: {e}")
    

    def _archive_message(self, tree, user_id):
        """Archive a message"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a message to archive")
            return
    
        msg_id = tree.item(selection[0])['text']
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
                UPDATE messages SET is_archived = 1 WHERE id = ? AND recipient_id = ?
            ''', (msg_id, user_id))
    
            conn.commit()
            conn.close()
    
            self._refresh_inbox(tree, user_id)
            messagebox.showinfo("Success", "Message archived")
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to archive message: {str(e)}")
            print(f"Error archiving message: {e}")
    

    def _unarchive_message(self, tree, user_id):
        """Unarchive a message"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a message to unarchive")
            return
    
        msg_id = tree.item(selection[0])['text']
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
                UPDATE messages SET is_archived = 0 WHERE id = ? AND recipient_id = ?
            ''', (msg_id, user_id))
    
            conn.commit()
            conn.close()
    
            self._refresh_archive(tree, user_id)
            messagebox.showinfo("Success", "Message moved to inbox")
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to unarchive message: {str(e)}")
            print(f"Error unarchiving message: {e}")
    

    def _delete_message(self, tree, user_id, user_type):
        """Delete a message"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a message to delete")
            return
    
        if not messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this message?"):
            return
    
        msg_id = tree.item(selection[0])['text']
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            if user_type == 'recipient':
                cursor.execute('''
                    UPDATE messages SET is_deleted_by_recipient = 1 WHERE id = ? AND recipient_id = ?
                ''', (msg_id, user_id))
            else:  # sender
                cursor.execute('''
                    UPDATE messages SET is_deleted_by_sender = 1 WHERE id = ? AND sender_id = ?
                ''', (msg_id, user_id))
    
            conn.commit()
            conn.close()
    
            # Refresh the appropriate view
            if user_type == 'recipient':
                self._refresh_inbox(tree, user_id)
            else:
                self._refresh_sent(tree, user_id)
    
            messagebox.showinfo("Success", "Message deleted")
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete message: {str(e)}")
            print(f"Error deleting message: {e}")
    

    def _browse_users(self, recipient_var):
        """Browse and select users"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
                SELECT id, username, first_name, last_name, role
                FROM users
                WHERE is_active = 1
                ORDER BY username
            ''')
    
            users = cursor.fetchall()
            conn.close()
    
            # Create selection window
            select_window = tk.Toplevel(self.root)
            select_window.title("Select Recipient")
            select_window.geometry("600x400")
    
            # Search frame
            search_frame = ttk.Frame(select_window)
            search_frame.pack(fill='x', padx=10, pady=10)
    
            ttk.Label(search_frame, text="Search:").pack(side='left', padx=5)
            search_var = tk.StringVar()
            search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
            search_entry.pack(side='left', padx=5)
    
            # Users list
            list_frame = ttk.Frame(select_window)
            list_frame.pack(fill='both', expand=True, padx=10, pady=5)
    
            columns = ('Username', 'Name', 'Role')
            tree = ttk.Treeview(list_frame, columns=columns, show='tree headings')
    
            tree.heading('#0', text='ID')
            tree.heading('Username', text='Username')
            tree.heading('Name', text='Name')
            tree.heading('Role', text='Role')
    
            tree.column('#0', width=50)
            tree.column('Username', width=150)
            tree.column('Name', width=200)
            tree.column('Role', width=100)
    
            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
    
            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
    
            # Populate users
            def populate_users(search_text=""):
                for item in tree.get_children():
                    tree.delete(item)
    
                for user in users:
                    user_id, username, first_name, last_name, role = user
                    full_name = f"{first_name} {last_name}"
    
                    if search_text.lower() in username.lower() or search_text.lower() in full_name.lower():
                        tree.insert('', 'end', text=user_id,
                                   values=(username, full_name, role))
    
            populate_users()
    
            # Search functionality
            search_var.trace('w', lambda *args: populate_users(search_var.get()))
    
            # Select button
            def select_user():
                selection = tree.selection()
                if selection:
                    username = tree.item(selection[0])['values'][0]
                    recipient_var.set(username)
                    select_window.destroy()
                else:
                    messagebox.showwarning("No Selection", "Please select a user")
    
            button_frame = ttk.Frame(select_window)
            button_frame.pack(fill='x', padx=10, pady=10)
    
            ttk.Button(button_frame, text="Select", command=select_user).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=select_window.destroy).pack(side='left', padx=5)
    
            tree.bind('<Double-1>', lambda e: select_user())
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load users: {str(e)}")
            print(f"Error browsing users: {e}")
    

    def _browse_attachment(self, attachment_var):
        """Browse for file attachment"""
        file_path = filedialog.askopenfilename(
            title="Select Attachment",
            filetypes=[("All Files", "*.*")]
        )
    
        if file_path:
            attachment_var.set(file_path)
    

    def _send_composed_message(self, sender_id, recipient_username, subject, message_body,
                               attachment_path, assignment_ref, recipient_entry, subject_entry, message_text):
        """Send a composed message"""
        # Validate inputs
        if not recipient_username:
            messagebox.showerror("Error", "Please specify a recipient")
            return
    
        if not subject:
            messagebox.showerror("Error", "Please enter a subject")
            return
    
        if not message_body.strip():
            messagebox.showerror("Error", "Please enter a message")
            return
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Get recipient ID
            cursor.execute('SELECT id FROM users WHERE username = ?', (recipient_username,))
            recipient = cursor.fetchone()
    
            if not recipient:
                messagebox.showerror("Error", f"User '{recipient_username}' not found")
                conn.close()
                return
    
            recipient_id = recipient[0]
    
            # Parse assignment ID if provided
            assignment_id = None
            if assignment_ref and assignment_ref != "(No Assignment)":
                try:
                    assignment_id = int(assignment_ref.split(':')[0])
                except (ValueError, IndexError):
                    pass
    
            # Insert message
            cursor.execute('''
                INSERT INTO messages (sender_id, recipient_id, subject, message, content,
                                    attachment_path, assignment_id, sent_at, is_read)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', (sender_id, recipient_id, subject, message_body, message_body,
                  attachment_path if attachment_path else None, assignment_id,
                  datetime.now().isoformat()))
    
            conn.commit()
            conn.close()
    
            messagebox.showinfo("Success", "Message sent successfully!")
    
            # Clear form
            self._clear_compose_form(recipient_entry, subject_entry, message_text, None, None)
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send message: {str(e)}")
            print(f"Error sending message: {e}")
    

    def _send_message_and_close(self, window, sender_id, recipient_username, subject,
                                message_body, attachment_path, assignment_ref):
        """Send message and close the window"""
        # Validate inputs
        if not recipient_username:
            messagebox.showerror("Error", "Please specify a recipient")
            return
    
        if not subject:
            messagebox.showerror("Error", "Please enter a subject")
            return
    
        if not message_body.strip():
            messagebox.showerror("Error", "Please enter a message")
            return
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Get recipient ID
            cursor.execute('SELECT id FROM users WHERE username = ?', (recipient_username,))
            recipient = cursor.fetchone()
    
            if not recipient:
                messagebox.showerror("Error", f"User '{recipient_username}' not found")
                conn.close()
                return
    
            recipient_id = recipient[0]
    
            # Parse assignment ID if provided
            assignment_id = None
            if assignment_ref and assignment_ref != "(No Assignment)":
                try:
                    assignment_id = int(assignment_ref.split(':')[0])
                except (ValueError, IndexError):
                    pass
    
            # Insert message
            cursor.execute('''
                INSERT INTO messages (sender_id, recipient_id, subject, message, content,
                                    attachment_path, assignment_id, sent_at, is_read)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', (sender_id, recipient_id, subject, message_body, message_body,
                  attachment_path if attachment_path else None, assignment_id,
                  datetime.now().isoformat()))
    
            conn.commit()
            conn.close()
    
            messagebox.showinfo("Success", "Message sent successfully!")
            window.destroy()
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send message: {str(e)}")
            print(f"Error sending message: {e}")
    

    def _load_recent_contacts(self, parent, recipient_var, user_id):
        """Load recent message contacts for quick selection"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Get recent contacts (both sent to and received from)
            cursor.execute('''
                SELECT DISTINCT u.username, u.first_name, u.last_name
                FROM (
                    SELECT recipient_id as contact_id FROM messages WHERE sender_id = ?
                    UNION
                    SELECT sender_id as contact_id FROM messages WHERE recipient_id = ?
                ) as contacts
                JOIN users u ON contacts.contact_id = u.id
                WHERE u.is_active = 1
                ORDER BY u.username
                LIMIT 10
            ''', (user_id, user_id))
    
            contacts = cursor.fetchall()
            conn.close()
    
            if contacts:
                ttk.Label(parent, text="Click to select:").pack(side='left', padx=5)
    
                for username, first_name, last_name in contacts:
                    btn = ttk.Button(parent, text=username,
                                    command=lambda u=username: recipient_var.set(u))
                    btn.pack(side='left', padx=2)
            else:
                ttk.Label(parent, text="No recent contacts",
                         foreground='#666666').pack(side='left', padx=5)
    
        except Exception as e:
            print(f"Error loading recent contacts: {e}")
    
    

    def _clear_compose_form(self, recipient_entry, subject_entry, message_text, attachment_var, assignment_combo):
        """Clear the compose form"""
        recipient_entry.delete(0, tk.END)
        subject_entry.delete(0, tk.END)
        message_text.delete('1.0', tk.END)
    
        if attachment_var:
            attachment_var.set("")
    
        if assignment_combo:
            assignment_combo.current(0)
    

    def _reply_to_message(self, original_msg_id, original_sender_id, original_subject):
        """Reply to a message"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Get original sender username
            cursor.execute('SELECT username FROM users WHERE id = ?', (original_sender_id,))
            sender = cursor.fetchone()
            conn.close()
    
            if not sender:
                messagebox.showerror("Error", "Original sender not found")
                return
    
            sender_username = sender[0]
    
            # Create reply window
            reply_window = tk.Toplevel(self.root)
            reply_window.title("Reply to Message")
            reply_window.geometry("700x500")
            reply_window.configure(bg='#f0f0f0')
    
            form_frame = ttk.LabelFrame(reply_window, text="Reply", padding=20)
            form_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
            # Recipient (read-only)
            ttk.Label(form_frame, text="To:").grid(row=0, column=0, sticky='w', pady=5)
            recipient_label = ttk.Label(form_frame, text=sender_username, font=('TkDefaultFont', 10, 'bold'))
            recipient_label.grid(row=0, column=1, sticky='w', pady=5)
    
            # Subject
            ttk.Label(form_frame, text="Subject:").grid(row=1, column=0, sticky='w', pady=5)
            reply_subject = f"Re: {original_subject}" if not original_subject.startswith("Re:") else original_subject
            subject_label = ttk.Label(form_frame, text=reply_subject, font=('TkDefaultFont', 10, 'bold'))
            subject_label.grid(row=1, column=1, sticky='w', pady=5)
    
            # Message
            ttk.Label(form_frame, text="Message:").grid(row=2, column=0, sticky='nw', pady=5)
            message_text = scrolledtext.ScrolledText(form_frame, width=60, height=15, wrap=tk.WORD)
            message_text.grid(row=2, column=1, sticky='ew', pady=5, padx=5)
    
            form_frame.columnconfigure(1, weight=1)
    
            # Buttons
            button_frame = ttk.Frame(reply_window)
            button_frame.pack(fill='x', padx=10, pady=10)
    
            def send_reply():
                user_id = self.auth.current_user.get('id')
                message_body = message_text.get('1.0', 'end-1c')
    
                if not message_body.strip():
                    messagebox.showerror("Error", "Please enter a message")
                    return
    
                try:
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()
    
                    cursor.execute('''
                        INSERT INTO messages (sender_id, recipient_id, subject, message, content,
                                            sent_at, is_read, reply_to)
                        VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                    ''', (user_id, original_sender_id, reply_subject, message_body, message_body,
                          datetime.now().isoformat(), original_msg_id))
    
                    conn.commit()
                    conn.close()
    
                    messagebox.showinfo("Success", "Reply sent successfully!")
                    reply_window.destroy()
    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to send reply: {str(e)}")
                    print(f"Error sending reply: {e}")
    
            ttk.Button(button_frame, text="Send Reply", command=send_reply).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=reply_window.destroy).pack(side='left', padx=5)
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create reply: {str(e)}")
            print(f"Error creating reply: {e}")
    

    def send_message(self, *args, **kwargs):
        """Open a dialog to compose and send a message.
    
        Features:
        - Quick compose message dialog
        - Recipient selection with user browser
        - Subject and message body fields
        - Optional attachment support
        - Assignment reference option
        - Validation and error handling
        """
        try:
            # Get current user ID
            user_id = self.auth.current_user.get('id')
            if not user_id:
                messagebox.showerror("Error", "User not authenticated")
                return
    
            # Ensure messages table exists
            self.gui.db._ensure_messages_table()
    
            # Create compose message window
            compose_window = tk.Toplevel(self.root)
            compose_window.title("Send Message")
            compose_window.geometry("800x600")
            compose_window.configure(bg='#f0f0f0')
    
            # Header
            header_frame = ttk.Frame(compose_window)
            header_frame.pack(fill='x', padx=10, pady=10)
    
            ttk.Label(header_frame, text="Compose New Message",
                     font=('TkDefaultFont', 16, 'bold')).pack(side='left')
    
            # Form frame
            form_frame = ttk.LabelFrame(compose_window, text="Message Details", padding=20)
            form_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
            # Recipient
            ttk.Label(form_frame, text="To (Username):").grid(row=0, column=0, sticky='w', pady=5)
            recipient_var = tk.StringVar()
            recipient_entry = ttk.Entry(form_frame, textvariable=recipient_var, width=50)
            recipient_entry.grid(row=0, column=1, sticky='ew', pady=5, padx=5)
    
            # Browse recipients button
            ttk.Button(form_frame, text="Browse Users",
                      command=lambda: self._browse_users(recipient_var)).grid(row=0, column=2, padx=5)
    
            # Subject
            ttk.Label(form_frame, text="Subject:").grid(row=1, column=0, sticky='w', pady=5)
            subject_var = tk.StringVar()
            subject_entry = ttk.Entry(form_frame, textvariable=subject_var, width=50)
            subject_entry.grid(row=1, column=1, columnspan=2, sticky='ew', pady=5, padx=5)
    
            # Priority (optional)
            ttk.Label(form_frame, text="Priority:").grid(row=2, column=0, sticky='w', pady=5)
            priority_var = tk.StringVar(value="normal")
            priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, width=48,
                                         values=["low", "normal", "high", "urgent"], state='readonly')
            priority_combo.grid(row=2, column=1, columnspan=2, sticky='ew', pady=5, padx=5)
    
            # Message body
            ttk.Label(form_frame, text="Message:").grid(row=3, column=0, sticky='nw', pady=5)
            message_text = scrolledtext.ScrolledText(form_frame, width=50, height=12, wrap=tk.WORD)
            message_text.grid(row=3, column=1, columnspan=2, sticky='ew', pady=5, padx=5)
    
            # Attachment (optional)
            ttk.Label(form_frame, text="Attachment:").grid(row=4, column=0, sticky='w', pady=5)
            attachment_var = tk.StringVar()
            attachment_entry = ttk.Entry(form_frame, textvariable=attachment_var, width=50, state='readonly')
            attachment_entry.grid(row=4, column=1, sticky='ew', pady=5, padx=5)
            ttk.Button(form_frame, text="Browse",
                      command=lambda: self._browse_attachment(attachment_var)).grid(row=4, column=2, padx=5)
    
            # Assignment reference (optional)
            ttk.Label(form_frame, text="Assignment:").grid(row=5, column=0, sticky='w', pady=5)
            assignment_var = tk.StringVar()
            assignment_combo = ttk.Combobox(form_frame, textvariable=assignment_var, width=48, state='readonly')
            assignment_combo.grid(row=5, column=1, columnspan=2, sticky='ew', pady=5, padx=5)
    
            # Load assignments
            self._load_assignments_for_compose(assignment_combo)
    
            form_frame.columnconfigure(1, weight=1)
    
            # Buttons
            button_frame = ttk.Frame(compose_window)
            button_frame.pack(fill='x', padx=10, pady=10)
    
            ttk.Button(button_frame, text="Send Message",
                      command=lambda: self._send_message_and_close(
                          compose_window, user_id, recipient_var.get(), subject_var.get(),
                          message_text.get('1.0', 'end-1c'), attachment_var.get(),
                          assignment_var.get()
                      ), style='Accent.TButton').pack(side='left', padx=5)
    
            ttk.Button(button_frame, text="Cancel",
                      command=compose_window.destroy).pack(side='left', padx=5)
    
            # Quick recipients frame (recent contacts)
            quick_frame = ttk.LabelFrame(compose_window, text="Recent Contacts", padding=10)
            quick_frame.pack(fill='x', padx=10, pady=5)
    
            self._load_recent_contacts(quick_frame, recipient_var, user_id)
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open compose dialog: {str(e)}")
            print(f"Error in send_message: {e}")


    def _read_message(self, message_id):
        """Read single message and mark as read"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Mark as read
            cursor.execute('UPDATE messages SET is_read = 1 WHERE id = ?', (message_id,))
            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Error marking message as read: {e}")


    def _send_reply(self, message_id):
        """Send reply to message (wrapper for _reply_to_message)"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT sender_id, subject FROM messages WHERE id = ?', (message_id,))
            message = cursor.fetchone()
            conn.close()

            if message:
                self._reply_to_message(message_id, message[0], message[1])

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send reply: {e}")


    def _send_module_message(self, module_code, subject, message_body):
        """Send message to all students in a module"""
        try:
            user_id = self.auth.current_user.get('id')
            if not user_id:
                messagebox.showerror("Error", "User not authenticated")
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get all students enrolled in the module
            cursor.execute('''
            SELECT DISTINCT s.student_id
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.module_code = ?
            ''', (module_code,))

            students = cursor.fetchall()

            if not students:
                messagebox.showinfo("No Students", f"No students found for module {module_code}")
                conn.close()
                return

            # Send message to each student
            timestamp = datetime.now().isoformat()
            count = 0

            for student_id_tuple in students:
                student_id = student_id_tuple[0]

                cursor.execute('''
                INSERT INTO messages (sender_id, recipient_id, subject, message, content,
                                    sent_at, is_read)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                ''', (user_id, student_id, subject, message_body, message_body, timestamp))

                count += 1

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Message sent to {count} students in {module_code}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send module message: {e}")


    def _send_individual_message(self, recipient_username, subject, message_body):
        """Send message to individual user (wrapper for send_message)"""
        # This is handled by the main send_message() function
        # Just call it
        self.send_message()


    def _send_instructor_broadcast(self, subject, message_body):
        """Send broadcast message to all instructors/admins"""
        try:
            user_id = self.auth.current_user.get('id')
            if not user_id:
                messagebox.showerror("Error", "User not authenticated")
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get all instructors and admins
            cursor.execute('''
            SELECT id FROM users
            WHERE (role = 'Faculty' OR role = 'Admin')
            AND is_active = 1
            AND id != ?
            ''', (user_id,))

            recipients = cursor.fetchall()

            if not recipients:
                messagebox.showinfo("No Recipients", "No instructors/admins found")
                conn.close()
                return

            # Send message to each recipient
            timestamp = datetime.now().isoformat()
            count = 0

            for recipient_id_tuple in recipients:
                recipient_id = recipient_id_tuple[0]

                cursor.execute('''
                INSERT INTO messages (sender_id, recipient_id, subject, message, content,
                                    sent_at, is_read)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                ''', (user_id, recipient_id, subject, message_body, message_body, timestamp))

                count += 1

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Broadcast message sent to {count} instructors/admins")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send broadcast: {e}")


    def _launch_gui_feature(self, callback, feature_name):
        """Helper to launch GUI features with error handling"""
        try:
            callback()
        except Exception as e:
            messagebox.showerror("Error", f"Error launching {feature_name}: {str(e)}")


