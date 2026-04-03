import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from tkinter.simpledialog import askstring, askinteger
import threading
import json
from datetime import datetime, timedelta
import webbrowser
import os
import subprocess
import sys
import logging

from education_system.university_system.modules.shared.gui.email.email_gui.email_dialogs import RecipientSelectorDialog

# Configure logging
logger = logging.getLogger(__name__)

# Import internationalisation (i18n) for multi‑language support
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

class AnnouncementDetailsDialog:
    def __init__(self, parent, dashboard, announcement_id):
        self.dashboard = dashboard
        self.announcement_id = announcement_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Announcement Details")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        self.load_announcement()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        self.title_label = ttk.Label(main_frame, text="", font=('Arial', 14, 'bold'))
        self.title_label.pack(anchor=tk.W, pady=(0, 10))

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text="Announcement Details", padding=10)
        details_frame.pack(fill=tk.X, pady=(0, 10))

        self.details_text = tk.Text(details_frame, height=3, wrap=tk.WORD, state=tk.DISABLED)
        self.details_text.pack(fill=tk.X)

        # Content
        content_frame = ttk.LabelFrame(main_frame, text="Content", padding=10)
        content_frame.pack(fill=tk.BOTH, expand=True)

        self.content_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.content_text.pack(fill=tk.BOTH, expand=True)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def load_announcement(self):
        try:
            announcement = get_announcement_by_id(self.dashboard, self.announcement_id)
            if announcement:
                self.title_label.config(text=announcement['title'])

                details = f"Created by: {announcement['creator']}\n"
                details += f"Target: {announcement['target_audience']}\n"
                details += f"Created: {announcement['created_at']}\n"
                details += f"Priority: {'URGENT' if announcement['is_urgent'] else 'Normal'}\n"
                details += f"Status: {'Active' if announcement['is_active'] else 'Inactive'}"

                self.details_text.config(state=tk.NORMAL)
                self.details_text.insert(1.0, details)
                self.details_text.config(state=tk.DISABLED)

                self.content_text.config(state=tk.NORMAL)
                self.content_text.insert(1.0, announcement['content'])
                self.content_text.config(state=tk.DISABLED)

                # Mark as viewed
                mark_announcement_viewed(self.dashboard, self.announcement_id)
        except Exception as e:
            messagebox.showerror("Error", f"Error loading announcement: {e}")


class CreateAnnouncementDialog:
    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Announcement")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=60)
        self.title_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=5)

        # Target audience
        ttk.Label(main_frame, text="Target Audience:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.audience_var = tk.StringVar(value="all")
        audience_frame = ttk.Frame(main_frame)
        audience_frame.grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Radiobutton(audience_frame, text="All Users", variable=self.audience_var, value="all").pack(side=tk.LEFT)
        ttk.Radiobutton(audience_frame, text="Students", variable=self.audience_var, value="students").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(audience_frame, text="Staff", variable=self.audience_var, value="staff").pack(side=tk.LEFT)
        ttk.Radiobutton(audience_frame, text="Instructors", variable=self.audience_var, value="instructors").pack(side=tk.LEFT, padx=10)

        # Urgent checkbox
        self.urgent_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Mark as urgent", variable=self.urgent_var).grid(row=2, column=1, sticky=tk.W, pady=5)

        # Content
        ttk.Label(main_frame, text="Content:").grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.content_text = scrolledtext.ScrolledText(main_frame, width=60, height=15)
        self.content_text.grid(row=3, column=1, columnspan=2, sticky=tk.NSEW, pady=5)

        # Date options
        ttk.Label(main_frame, text="Start Date:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.start_date_entry = ttk.Entry(main_frame, width=20)
        self.start_date_entry.grid(row=4, column=1, sticky=tk.W, pady=5)
        self.start_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        ttk.Label(main_frame, text="End Date (optional):").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.end_date_entry = ttk.Entry(main_frame, width=20)
        self.end_date_entry.grid(row=5, column=1, sticky=tk.W, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=3, pady=20)

        ttk.Button(button_frame, text="Create", command=self.create_announcement).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

    def create_announcement(self):
        title = self.title_entry.get().strip()
        content = self.content_text.get(1.0, tk.END).strip()
        target_audience = self.audience_var.get()
        is_urgent = 1 if self.urgent_var.get() else 0
        start_date = self.start_date_entry.get().strip()
        end_date = self.end_date_entry.get().strip() or None

        if not title or not content:
            messagebox.showwarning("Missing Information", "Title and content are required")
            return

        try:
            from education_system.university_system.infrastructure.database.db import get_db_connection
            from datetime import datetime

            conn = get_db_connection()
            cursor = conn.cursor()

            # Get the current user ID (default to 1 if not available)
            creator_id = getattr(self.dashboard.auth, 'current_user', {}).get('id', 1) if hasattr(self, 'dashboard') and hasattr(self.dashboard, 'auth') else 1

            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Use the correct schema from admin.py
            cursor.execute('''
                INSERT INTO announcements (creator_id, title, content, target_audience, is_urgent, is_active, start_date, end_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (creator_id, title, content, target_audience, is_urgent, 1, start_date, end_date, current_time, current_time))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Announcement created successfully!")
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create announcement: {e}")


class CreateChatRoomDialog:
    def __init__(self, parent, dashboard, refresh_callback=None):
        self.dashboard = dashboard
        self.refresh_callback = refresh_callback
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Chat Room")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Room name
        ttk.Label(main_frame, text="Room Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(main_frame, width=40)
        self.name_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        # Description
        ttk.Label(main_frame, text="Description:").grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.description_text = tk.Text(main_frame, width=40, height=5)
        self.description_text.grid(row=1, column=1, sticky=tk.NSEW, pady=5)

        # Room type
        ttk.Label(main_frame, text="Room Type:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar(value="public")
        type_frame = ttk.Frame(main_frame)
        type_frame.grid(row=2, column=1, sticky=tk.W, pady=5)

        ttk.Radiobutton(type_frame, text="Public", variable=self.type_var, value="public").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Private", variable=self.type_var, value="private").pack(anchor=tk.W)

        # Max members
        ttk.Label(main_frame, text="Max Members:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.max_members_var = tk.StringVar(value="50")
        ttk.Spinbox(main_frame, from_=2, to=1000, textvariable=self.max_members_var, width=10).grid(row=3, column=1, sticky=tk.W, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Create", command=self.create_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

    def create_room(self):
        name = self.name_entry.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()
        room_type = self.type_var.get()
        max_members = int(self.max_members_var.get())

        if not name:
            messagebox.showwarning("Missing Information", "Please provide a room name")
            return

        try:
            from education_system.university_system.infrastructure.database.db import get_db_connection
            from datetime import datetime

            conn = get_db_connection()
            cursor = conn.cursor()

            # Get the current user ID (default to 1 if not available)
            created_by = getattr(self.dashboard.auth, 'current_user', {}).get('id', 1) if hasattr(self, 'dashboard') and hasattr(self.dashboard, 'auth') else 1

            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Use the correct schema from admin.py
            cursor.execute('''
                INSERT INTO chat_rooms (name, description, room_type, created_by, created_at, max_members, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, description, room_type, created_by, current_time, max_members, 1))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Chat room '{name}' created successfully!")
            self.dialog.destroy()

            # Refresh the chat rooms list in the GUI
            if self.refresh_callback:
                self.refresh_callback()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create chat room: {e}")


class ChatInvitationsDialog:
    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Chat Room Invitations")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        self.load_invitations()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text="Pending Chat Room Invitations", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Invitations list
        columns = ("Room", "Invited By", "Date")
        self.invitations_tree = ttk.Treeview(main_frame, columns=columns, show="headings")

        for col in columns:
            self.invitations_tree.heading(col, text=col)

        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.invitations_tree.yview)
        self.invitations_tree.configure(yscrollcommand=scrollbar.set)

        self.invitations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Accept", command=self.accept_invitation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Decline", command=self.decline_invitation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def load_invitations(self):
        # Clear existing items
        for item in self.invitations_tree.get_children():
            self.invitations_tree.delete(item)

        try:
            invitations = self.dashboard.get_pending_invitations()

            for invitation in invitations:
                self.invitations_tree.insert('', tk.END, values=(
                    invitation['room_name'],
                    invitation['invited_by'],
                    invitation['invited_at']
                ), tags=(invitation['id'],))
        except Exception as e:
            messagebox.showerror("Error", f"Error loading invitations: {e}")

    def accept_invitation(self):
        selection = self.invitations_tree.selection()
        if selection:
            item = self.invitations_tree.item(selection[0])
            invitation_id = item['tags'][0]

            try:
                if self.dashboard.respond_to_invitation(invitation_id, accept=True):
                    messagebox.showinfo("Success", "Invitation accepted!")
                    self.load_invitations()
                else:
                    messagebox.showerror("Error", "Failed to accept invitation")
            except Exception as e:
                messagebox.showerror("Error", f"Error accepting invitation: {e}")

    def decline_invitation(self):
        selection = self.invitations_tree.selection()
        if selection:
            item = self.invitations_tree.item(selection[0])
            invitation_id = item['tags'][0]

            try:
                if self.dashboard.respond_to_invitation(invitation_id, accept=False):
                    messagebox.showinfo("Success", "Invitation declined")
                    self.load_invitations()
                else:
                    messagebox.showerror("Error", "Failed to decline invitation")
            except Exception as e:
                messagebox.showerror("Error", f"Error declining invitation: {e}")


class ComposeMessageDialog:
    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Compose Message")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Recipient
        ttk.Label(main_frame, text="To:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.recipient_entry = ttk.Entry(main_frame, width=40)
        self.recipient_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Button(main_frame, text="Select", command=self.select_recipient).grid(row=0, column=2, padx=5)

        # Subject
        ttk.Label(main_frame, text="Subject:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.subject_entry = ttk.Entry(main_frame, width=40)
        self.subject_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=5)

        # Message
        ttk.Label(main_frame, text="Message:").grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.message_text = scrolledtext.ScrolledText(main_frame, width=50, height=15)
        self.message_text.grid(row=2, column=1, columnspan=2, sticky=tk.NSEW, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=10)

        ttk.Button(button_frame, text="Send", command=self.send_message).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

    def select_recipient(self):
        """Select message recipient"""
        RecipientSelectorDialog(self.dialog, self.recipient_entry)

    def send_message(self):
        """Send the message"""
        try:
            recipient_email = self.recipient_entry.get().strip()
            subject = self.subject_entry.get().strip()
            content = self.message_text.get(1.0, tk.END).strip()

            if not recipient_email or not subject or not content:
                messagebox.showerror("Error", "Please fill in all fields")
                return

            # Find recipient user ID
            def _find_recipient(cursor):
                cursor.execute("SELECT id FROM users WHERE email = ?", (recipient_email,))
                result = cursor.fetchone()
                return result[0] if result else None

            if 'execute_db_operation' in globals():
                recipient_id = execute_db_operation(_find_recipient)

                if recipient_id and self.dashboard:
                    if self.dashboard.send_message(recipient_id, subject, content):
                        messagebox.showinfo("Success", "Message sent successfully")
                        self.dialog.destroy()
                    else:
                        messagebox.showerror("Error", "Failed to send message")
                else:
                    messagebox.showerror("Error", "Recipient not found")
            else:
                messagebox.showerror("Error", "Messaging system not available")

        except Exception as e:
            messagebox.showerror("Error", f"Error sending message: {e}")


class ReplyMessageDialog:
    def __init__(self, parent, dashboard, message_id):
        self.dashboard = dashboard
        self.message_id = message_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Reply to Message")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        self.load_original_message()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Original message (read-only)
        ttk.Label(main_frame, text="Original Message:").pack(anchor=tk.W)
        self.original_text = scrolledtext.ScrolledText(main_frame, height=8, state=tk.DISABLED)
        self.original_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Reply
        ttk.Label(main_frame, text="Your Reply:").pack(anchor=tk.W, pady=(10, 0))
        self.reply_text = scrolledtext.ScrolledText(main_frame, height=8)
        self.reply_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Send Reply", command=self.send_reply).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def load_original_message(self):
        """Load the original message"""
        try:
            if self.dashboard:
                message = self.dashboard.read_message(self.message_id)
                if message:
                    original_content = f"From: {message['sender']}\n"
                    original_content += f"Subject: {message['subject']}\n"
                    original_content += f"Date: {message['sent_at']}\n"
                    original_content += "-" * 40 + "\n"
                    original_content += message['content']

                    self.original_text.config(state=tk.NORMAL)
                    self.original_text.insert(1.0, original_content)
                    self.original_text.config(state=tk.DISABLED)

                    # Store message info for reply
                    self.original_sender_id = message['sender_id']
                    self.original_subject = message['subject']
        except Exception as e:
            messagebox.showerror("Error", f"Error loading original message: {e}")

    def send_reply(self):
        """Send the reply"""
        try:
            reply_content = self.reply_text.get(1.0, tk.END).strip()

            if not reply_content:
                messagebox.showerror("Error", "Please enter a reply")
                return

            # Create reply subject
            reply_subject = self.original_subject
            if not reply_subject.startswith("Re: "):
                reply_subject = f"Re: {reply_subject}"

            if self.dashboard:
                if self.dashboard.send_message(self.original_sender_id, reply_subject, reply_content):
                    messagebox.showinfo("Success", "Reply sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send reply")

        except Exception as e:
            messagebox.showerror("Error", f"Error sending reply: {e}")


class EditAnnouncementDialog:
    def __init__(self, parent, dashboard, announcement_id, refresh_callback):
        self.dashboard = dashboard
        self.announcement_id = announcement_id
        self.refresh_callback = refresh_callback
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Announcement")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.load_announcement()

    def load_announcement(self):
        """Load existing announcement data"""
        try:
            from education_system.university_system.infrastructure.database.db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT title, content, is_urgent
                FROM announcements WHERE id = ?
            ''', (self.announcement_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                self.title = row[0]
                self.content = row[1]
                self.is_urgent = row[2]
                self.create_widgets()
            else:
                messagebox.showerror("Error", "Announcement not found")
                self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load announcement: {e}")
            self.dialog.destroy()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Edit Announcement", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Title
        ttk.Label(main_frame, text="Title:").pack(anchor=tk.W)
        self.title_entry = ttk.Entry(main_frame, width=50)
        self.title_entry.insert(0, self.title)
        self.title_entry.pack(fill=tk.X, pady=(0, 10))

        # Message
        ttk.Label(main_frame, text="Message:").pack(anchor=tk.W)
        self.message_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD)
        self.message_text.insert(1.0, self.content)
        self.message_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Priority
        priority_frame = ttk.Frame(main_frame)
        priority_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(priority_frame, text="Priority:").pack(side=tk.LEFT, padx=(0, 5))

        # Map is_urgent to priority string
        initial_priority = "high" if self.is_urgent else "normal"
        self.priority_var = tk.StringVar(value=initial_priority)

        ttk.Radiobutton(priority_frame, text="Low", variable=self.priority_var, value="low").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(priority_frame, text="Normal", variable=self.priority_var, value="normal").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(priority_frame, text="High", variable=self.priority_var, value="high").pack(side=tk.LEFT, padx=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="Save", command=self.save_announcement).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)

    def save_announcement(self):
        title = self.title_entry.get().strip()
        message = self.message_text.get(1.0, tk.END).strip()
        priority = self.priority_var.get()

        if not title or not message:
            messagebox.showwarning("Missing Information", "Please provide both title and message")
            return

        try:
            from education_system.university_system.infrastructure.database.db import get_db_connection
            from datetime import datetime

            conn = get_db_connection()
            cursor = conn.cursor()

            # Map priority to is_urgent
            is_urgent = 1 if priority.lower() == 'high' else 0

            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Update the announcement
            cursor.execute('''
                UPDATE announcements
                SET title = ?, content = ?, is_urgent = ?, updated_at = ?
                WHERE id = ?
            ''', (title, message, is_urgent, current_time, self.announcement_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Announcement updated successfully!")
            self.dialog.destroy()

            # Refresh the announcements list
            if self.refresh_callback:
                self.refresh_callback()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update announcement: {e}")


class ChatRoomWindow:
    """Enhanced chat room interface"""
    def __init__(self, parent, dashboard, room_id, room_name):
        self.dashboard = dashboard
        self.room_id = room_id
        self.room_name = room_name
        self.window = tk.Toplevel(parent)
        self.window.title(f"Chat Room: {room_name}")
        self.window.geometry("800x600")
        self.window.transient(parent)

        self.create_widgets()
        self.load_messages()

    def create_widgets(self):
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Chat display area
        self.chat_text = scrolledtext.ScrolledText(main_frame, state=tk.DISABLED, wrap=tk.WORD, height=20)
        self.chat_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Message input frame
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))

        self.message_entry = ttk.Entry(input_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.message_entry.bind('<Return>', self.send_message)

        ttk.Button(input_frame, text="Send", command=self.send_message).pack(side=tk.RIGHT)

        # Controls frame
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X)

        ttk.Button(controls_frame, text="Members", command=self.show_members).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Invite", command=self.invite_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Leave Room", command=self.leave_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

    def load_messages(self):
        """Load chat messages for this room"""
        try:
            if not self.dashboard:
                self.chat_text.config(state=tk.NORMAL)
                self.chat_text.delete(1.0, tk.END)
                self.chat_text.insert(1.0, "Error: Dashboard not initialized. Please restart the application.\n")
                self.chat_text.config(state=tk.DISABLED)
                return

            messages_data = self.dashboard.get_chat_messages(self.room_id, limit=50)

            self.chat_text.config(state=tk.NORMAL)
            self.chat_text.delete(1.0, tk.END)

            # Check if messages_data is valid
            if not messages_data or not isinstance(messages_data, dict):
                self.chat_text.insert(1.0, "No messages to display.\n")
            else:
                messages = messages_data.get('messages', [])
                if not messages:
                    self.chat_text.insert(1.0, "No messages yet. Start the conversation!\n")
                else:
                    for msg in messages:
                        timestamp = msg.get('sent_at', '')[:16]
                        sender = msg.get('sender', 'Unknown')
                        content = msg.get('content', '')
                        self.chat_text.insert(tk.END, f"[{timestamp}] {sender}: {content}\n")

            self.chat_text.config(state=tk.DISABLED)
            self.chat_text.see(tk.END)
        except Exception as e:
            self.chat_text.config(state=tk.NORMAL)
            self.chat_text.delete(1.0, tk.END)
            self.chat_text.insert(1.0, f"Error loading messages: {e}\n")
            self.chat_text.config(state=tk.DISABLED)
            print(f"Error loading chat messages: {e}")
            import traceback
            traceback.print_exc()

    def send_message(self, event=None):
        """Send a message to the chat room"""
        message = self.message_entry.get().strip()
        if not message:
            return

        if not self.dashboard:
            messagebox.showerror("Error", "Dashboard not initialized. Cannot send message.")
            return

        try:
            result = self.dashboard.send_chat_message(self.room_id, message)
            if result:
                self.message_entry.delete(0, tk.END)
                self.load_messages()  # Refresh messages
            else:
                messagebox.showerror("Error", "Failed to send message")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending message: {e}")
            import traceback
            traceback.print_exc()

    def show_members(self):
        try:
            members = self.dashboard.get_room_members(self.room_id)
            if members:
                member_text = "\n".join([f"• {m['full_name']} (@{m['username']})" +
                                       (" - Admin" if m['is_admin'] else "") for m in members])
                messagebox.showinfo(f"Members of {self.room_name}", member_text)
            else:
                messagebox.showinfo("Members", "Could not retrieve member list")
        except Exception as e:
            messagebox.showerror("Error", f"Error getting members: {e}")

    def invite_user(self):
        username = askstring("Invite User", "Enter username to invite:")
        if username:
            try:
                # Find user and invite
                users = search_users(self.dashboard.auth, username)
                if users:
                    user = users[0]
                    result = self.dashboard.invite_user_to_room(self.room_id, user['id'])
                    if result == True:
                        messagebox.showinfo("Success", f"Invitation sent to {username}")
                    elif result == "already_member":
                        messagebox.showinfo("Info", f"{username} is already a member")
                    else:
                        messagebox.showerror("Error", "Failed to send invitation")
                else:
                    messagebox.showerror("Error", f"User '{username}' not found")
            except Exception as e:
                messagebox.showerror("Error", f"Error inviting user: {e}")

    def leave_room(self):
        if messagebox.askyesno("Confirm", f"Leave room '{self.room_name}'?"):
            try:
                if self.dashboard.leave_chat_room(self.room_id):
                    messagebox.showinfo("Success", f"Left room '{self.room_name}'")
                    self.window.destroy()
                else:
                    messagebox.showerror("Error", "Failed to leave room")
            except Exception as e:
                messagebox.showerror("Error", f"Error leaving room: {e}")


