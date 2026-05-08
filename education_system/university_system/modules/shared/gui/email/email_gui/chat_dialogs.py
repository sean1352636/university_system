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

        if not self.dashboard:
            messagebox.showerror("Error", "Dashboard not initialized")
            return

        try:
            result = self.dashboard.create_announcement(
                title,
                content,
                target_audience,
                is_urgent=is_urgent,
                start_date=start_date or None,
                end_date=end_date,
            )
            if result:
                messagebox.showinfo("Success", "Announcement created successfully!")
                self.dialog.destroy()
            else:
                messagebox.showerror(
                    "Error",
                    "Failed to create announcement (check permissions and date format YYYY-MM-DD HH:MM:SS)",
                )
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

        if not self.dashboard:
            messagebox.showerror("Error", "Dashboard not initialized")
            return

        try:
            result = self.dashboard.create_chat_room(
                name,
                description=description or None,
                room_type=room_type,
                max_members=max_members,
            )
            if result:
                messagebox.showinfo("Success", f"Chat room '{name}' created successfully!")
                self.dialog.destroy()
                if self.refresh_callback:
                    self.refresh_callback()
            else:
                messagebox.showerror(
                    "Error",
                    "Failed to create chat room (name may already exist or you lack permission)",
                )
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
    PAGE_SIZE = 50
    POLL_MS = 2000          # poll interval for new messages / typing / presence
    TYPING_TTL_SEC = 5      # how long a typing indicator stays alive
    TYPING_PING_MS = 2000   # min interval between outbound typing pings
    PRESENCE_PING_MS = 10000  # heartbeat interval
    REACTION_PALETTE = ["👍", "❤️", "🎉", "😂", "✅", "❓"]
    ROLE_BADGES = {
        'admin':      ('ADMIN',      '#ffffff', '#b30000'),
        'staff':      ('STAFF',      '#ffffff', '#1a5fb4'),
        'instructor': ('INSTRUCTOR', '#ffffff', '#2a8a2a'),
        'ta':         ('TA',         '#000000', '#f7c948'),
        'student':    ('STUDENT',    '#000000', '#dddddd'),
    }

    def __init__(self, parent, dashboard, room_id, room_name):
        self.dashboard = dashboard
        self.room_id = room_id
        self.room_name = room_name
        self.current_page = 1
        self.total_pages = 1
        self.last_message_id = 0          # highest id currently displayed
        self.oldest_message_id = None
        self._messages_by_id = {}         # cache of message dicts currently rendered
        self._poll_job = None
        self._presence_job = None
        self._last_typing_ping = 0.0
        self._closed = False
        self._pending_reply = None        # {'id': int, 'snippet': str, 'sender': str}
        self._pending_attachment = None   # {'path', 'name', 'mime', 'size'}
        self._context_message_id = None
        self._current_user_id = None
        self._current_username = None
        if dashboard and getattr(dashboard, 'auth', None) and dashboard.auth.current_user:
            self._current_user_id = dashboard.auth.current_user.get('id')
            self._current_username = dashboard.auth.current_user.get('username')

        # Fetch room metadata (announcement-mode, office hours, etc.)
        self.room_info = {}
        try:
            self.room_info = self.dashboard.get_room_info(room_id) or {}
        except Exception:
            self.room_info = {}

        self.window = tk.Toplevel(parent)
        self.window.title(f"Chat Room: {room_name}")
        self.window.geometry("1400x900")
        self.window.minsize(1200, 800)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        # Keyboard shortcuts (window-level)
        self.window.bind('<Escape>', lambda e: self._on_close())
        self.window.bind('<Control-Return>', lambda e: (self.send_message(), "break")[1])
        self.window.bind('<Control-k>', self._open_room_switcher)
        self.window.bind('<Control-K>', self._open_room_switcher)

        self.create_widgets()
        self._update_mode_banner()
        self.load_messages()
        self._refresh_members_panel()
        # Kick off background loops
        self._poll_job = self.window.after(self.POLL_MS, self._poll)
        self._presence_job = self.window.after(0, self._presence_heartbeat)

    def create_widgets(self):
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Mode banner (announcement / office-hours). Hidden by default.
        self.mode_banner = ttk.Label(main_frame, text="", anchor=tk.W,
                                     background="#fff7d6", foreground="#664d00",
                                     font=("TkDefaultFont", 9))

        # Top toolbar: history + presence + search
        history_frame = ttk.Frame(main_frame)
        history_frame.pack(fill=tk.X)
        self.load_older_button = ttk.Button(history_frame, text="Load Older", command=self.load_older)
        self.load_older_button.pack(side=tk.LEFT)
        self.history_status = ttk.Label(history_frame, text="")
        self.history_status.pack(side=tk.LEFT, padx=10)
        self.presence_label = ttk.Label(history_frame, text="● 0 online", foreground="#888")
        self.presence_label.pack(side=tk.RIGHT)
        ttk.Button(history_frame, text="Pinned", command=self.show_pinned).pack(side=tk.RIGHT, padx=5)

        # Search bar (in-room)
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(4, 4))
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        search_entry.bind('<Return>', lambda e: self.do_search())
        ttk.Button(search_frame, text="Find", command=self.do_search).pack(side=tk.LEFT)

        # Resizable two-pane layout: chat on the left, members sidebar on the right.
        self.paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)
        chat_pane = ttk.Frame(self.paned)
        self.members_pane = ttk.Frame(self.paned)
        self.paned.add(chat_pane, weight=4)
        self.paned.add(self.members_pane, weight=1)

        # Members sidebar contents
        ttk.Label(self.members_pane, text="Members",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, padx=4, pady=(2, 2))
        cols = ("Status", "Member", "Role")
        self.members_tree = ttk.Treeview(self.members_pane, columns=cols, show="headings")
        self.members_tree.bind("<Button-3>", self._on_member_right_click)
        for c in cols:
            self.members_tree.heading(c, text=c)
        self.members_tree.column("Status", width=70, anchor=tk.CENTER)
        self.members_tree.column("Member", width=160)
        self.members_tree.column("Role", width=80, anchor=tk.CENTER)
        self.members_tree.tag_configure("online", foreground="#2a8a2a")
        self.members_tree.tag_configure("offline", foreground="#888")
        members_sb = ttk.Scrollbar(self.members_pane, orient=tk.VERTICAL,
                                   command=self.members_tree.yview)
        self.members_tree.configure(yscrollcommand=members_sb.set)
        self.members_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))
        members_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._members_visible = True
        self._cached_members = []

        # Chat display area
        self.chat_text = scrolledtext.ScrolledText(chat_pane, state=tk.DISABLED, wrap=tk.WORD, height=20)
        self.chat_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        # Tags for rendering
        self.chat_text.tag_configure("header", font=("TkDefaultFont", 10, "bold"))
        self.chat_text.tag_configure("timestamp", foreground="#888")
        self.chat_text.tag_configure("mention", foreground="#b30000", font=("TkDefaultFont", 10, "bold"))
        self.chat_text.tag_configure("self_mention", background="#fff4b8", foreground="#b30000",
                                     font=("TkDefaultFont", 10, "bold"))
        self.chat_text.tag_configure("bold", font=("TkDefaultFont", 10, "bold"))
        self.chat_text.tag_configure("italic", font=("TkDefaultFont", 10, "italic"))
        self.chat_text.tag_configure("inline_code", font=("TkFixedFont", 10),
                                     background="#f0f0f0")
        self.chat_text.tag_configure("code_block", font=("TkFixedFont", 10),
                                     background="#f5f5f5", lmargin1=20, lmargin2=20,
                                     spacing1=4, spacing3=4)
        self.chat_text.tag_configure("url", foreground="#1a5fb4", underline=True)
        self.chat_text.tag_configure("reply_quote", foreground="#666", lmargin1=20, lmargin2=20,
                                     font=("TkDefaultFont", 9, "italic"))
        self.chat_text.tag_configure("deleted", foreground="#888",
                                     font=("TkDefaultFont", 10, "italic"))
        self.chat_text.tag_configure("edited", foreground="#888",
                                     font=("TkDefaultFont", 9, "italic"))
        self.chat_text.tag_configure("pinned", foreground="#b8860b",
                                     font=("TkDefaultFont", 10, "bold"))
        self.chat_text.tag_configure("attachment", foreground="#1a5fb4", underline=True,
                                     lmargin1=20, lmargin2=20)
        self.chat_text.tag_configure("reaction", background="#eaeaea", lmargin1=20, lmargin2=20)
        self.chat_text.tag_configure("reaction_mine", background="#cde4ff",
                                     lmargin1=20, lmargin2=20)
        self.chat_text.tag_configure("search_hit", background="#ffe680")
        self.chat_text.tag_configure("due_date", foreground="#7a4f00",
                                     background="#fff4d6",
                                     font=("TkDefaultFont", 10, "bold"))
        self.chat_text.tag_configure("team_mention", foreground="#ffffff",
                                     background="#1a5fb4",
                                     font=("TkDefaultFont", 9, "bold"))
        # Role badge tags (one per known role + a fallback).
        for role, (label, fg, bg) in self.ROLE_BADGES.items():
            self.chat_text.tag_configure(
                f"role_{role}", foreground=fg, background=bg,
                font=("TkDefaultFont", 8, "bold"),
            )
        self.chat_text.tag_configure("poll_box", background="#f5f5f5",
                                     lmargin1=20, lmargin2=20,
                                     spacing1=4, spacing3=4)
        self.chat_text.tag_configure("poll_question",
                                     font=("TkDefaultFont", 10, "bold"),
                                     lmargin1=20, lmargin2=20)
        self.chat_text.tag_configure("poll_meta", foreground="#666",
                                     lmargin1=20, lmargin2=20,
                                     font=("TkDefaultFont", 9, "italic"))
        self.chat_text.tag_configure("poll_option", lmargin1=30, lmargin2=30)
        self.chat_text.tag_configure("poll_chosen", lmargin1=30, lmargin2=30,
                                     foreground="#1a5fb4",
                                     font=("TkDefaultFont", 10, "bold"))
        self.chat_text.bind("<Button-3>", self._on_right_click)

        # Typing indicator (within the chat pane)
        self.typing_label = ttk.Label(chat_pane, text="", foreground="#666")
        self.typing_label.pack(fill=tk.X, pady=(0, 2))

        # Reply / attachment indicator strip (within the chat pane)
        self.indicator_frame = ttk.Frame(chat_pane)
        self.indicator_frame.pack(fill=tk.X, pady=(0, 2))
        self.reply_label = ttk.Label(self.indicator_frame, text="", foreground="#1a5fb4")
        self.reply_cancel = ttk.Button(self.indicator_frame, text="✕", width=2,
                                       command=self.clear_reply)
        self.attach_label = ttk.Label(self.indicator_frame, text="", foreground="#1a5fb4")
        self.attach_cancel = ttk.Button(self.indicator_frame, text="✕", width=2,
                                        command=self.clear_attachment)

        # Message input (multi-line). Enter sends, Shift+Enter inserts newline.
        input_frame = ttk.Frame(chat_pane)
        input_frame.pack(fill=tk.X, pady=(0, 10))

        self.message_entry = tk.Text(input_frame, height=3, wrap=tk.WORD)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.message_entry.bind('<Return>', self._on_return)
        self.message_entry.bind('<Shift-Return>', lambda e: None)
        self.message_entry.bind('<KeyRelease>', self._on_key_release)

        button_col = ttk.Frame(input_frame)
        button_col.pack(side=tk.RIGHT)
        ttk.Button(button_col, text="📎 Attach", command=self.attach_file).pack(fill=tk.X)
        ttk.Button(button_col, text="Send", command=self.send_message).pack(fill=tk.X, pady=(2, 0))

        # Controls frame
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X)

        ttk.Button(controls_frame, text="Members", command=self.show_members).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Invite", command=self.invite_user).pack(side=tk.LEFT, padx=5)
        # Admins/creator: full member-management dialog (kick / ban / mute /
        # promote / transfer ownership). Hidden for ordinary members.
        if (self.room_info or {}).get('is_admin'):
            ttk.Button(controls_frame, text="Manage…",
                       command=self.open_manage_members
                       ).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Seen By", command=self.show_seen_by).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Notes", command=self.open_notes).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Poll…", command=self.create_poll).pack(side=tk.LEFT, padx=5)
        # Course-linked controls (only meaningful when the room maps to a module)
        if (self.room_info or {}).get('linked_course_code'):
            ttk.Button(controls_frame, text="📚 Module",
                       command=self.show_module_info).pack(side=tk.LEFT, padx=5)
            ttk.Button(controls_frame, text="Post Due Dates",
                       command=self.post_due_dates).pack(side=tk.LEFT, padx=5)
        self.hand_button = ttk.Button(controls_frame, text="🙋 Raise Hand",
                                      command=self.toggle_hand)
        self.hand_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Queue", command=self.show_queue).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Leave Room", command=self.leave_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Close", command=self._on_close).pack(side=tk.RIGHT, padx=5)

    # ---- rendering helpers ----------------------------------------------

    def _is_at_bottom(self):
        """True if the chat text view is scrolled to (or near) the bottom."""
        try:
            yview = self.chat_text.yview()
            return yview[1] >= 0.999
        except Exception:
            return True

    def _format_size(self, n):
        if not n:
            return ""
        try:
            n = int(n)
        except (TypeError, ValueError):
            return ""
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
            n /= 1024.0
        return f"{n:.1f} TB"

    def _insert_message(self, msg, position="end"):
        """Render a single message at the end (only — used for initial load
        and live polling). Records the message in the cache by id."""
        if position != "end":
            # Older-page prepends rebuild from cache via _redraw_all.
            self._messages_by_id[msg.get('id')] = msg
            return
        msg_id = msg.get('id')
        if msg_id is None:
            return
        self._messages_by_id[msg_id] = msg
        self._render_one_at_end(msg)

    def _render_one_at_end(self, msg):
        msg_id = msg['id']
        msg_tag = f"m{msg_id}"
        start_index = self.chat_text.index("end-1c")

        # Header line: [time] [BADGE] sender ★ pinned
        timestamp = (msg.get('sent_at') or '')[:16]
        sender = msg.get('sender', 'Unknown')
        self.chat_text.insert(tk.END, f"[{timestamp}] ", ("timestamp",))
        role = (msg.get('sender_role') or '').lower()
        if role in self.ROLE_BADGES:
            label, _, _ = self.ROLE_BADGES[role]
            self.chat_text.insert(tk.END, f" {label} ", (f"role_{role}",))
            self.chat_text.insert(tk.END, " ")
        sender_tag = f"sender_{msg_id}"
        self.chat_text.insert(tk.END, sender, ("header", sender_tag))
        sender_uid = msg.get('sender_id')
        if sender_uid:
            self.chat_text.tag_bind(
                sender_tag, "<Button-1>",
                lambda e, uid=sender_uid: UserProfileDialog(self.window, self.dashboard, uid),
            )
        if msg.get('pinned_at'):
            self.chat_text.insert(tk.END, "  ★ pinned", ("pinned",))
        self.chat_text.insert(tk.END, "\n")

        # Reply quote
        reply = msg.get('reply_preview')
        if reply:
            snippet = (reply.get('content') or '').replace('\n', ' ')
            if len(snippet) > 80:
                snippet = snippet[:77] + '…'
            if reply.get('is_deleted'):
                snippet = "(deleted message)"
            self.chat_text.insert(tk.END, f"  ↪ {reply.get('sender')}: {snippet}\n",
                                  ("reply_quote",))

        # Body
        if msg.get('is_deleted'):
            self.chat_text.insert(tk.END, "  [deleted message]\n", ("deleted",))
        elif msg.get('poll'):
            self._render_poll(msg.get('poll'))
        else:
            content = msg.get('content') or ''
            if content.startswith('[due]'):
                self.chat_text.insert(tk.END, f"  📅 {content[len('[due]'):].strip()}\n",
                                      ("due_date",))
            else:
                if content:
                    self._render_inline(content, leading="  ", track_self_mention=True)
                if msg.get('edited_at'):
                    self.chat_text.insert(tk.END, "  (edited)\n", ("edited",))

        # Attachment
        att_path = msg.get('attachment_path')
        if att_path:
            att_name = msg.get('attachment_name') or att_path.rsplit('/', 1)[-1]
            size_str = self._format_size(msg.get('attachment_size'))
            label = f"  📎 {att_name}" + (f" ({size_str})" if size_str else "")
            att_tag = f"att_{msg_id}"
            self.chat_text.insert(tk.END, label + "\n", ("attachment", att_tag))
            self.chat_text.tag_bind(att_tag, "<Button-1>",
                                    lambda e, p=att_path: self._open_attachment(p))

        # Reactions bar
        reactions = msg.get('reactions') or []
        if reactions:
            self.chat_text.insert(tk.END, "  ")
            for rxn in reactions:
                emoji = rxn['emoji']
                count = rxn['count']
                tag = "reaction_mine" if rxn.get('mine') else "reaction"
                rxn_tag = f"rxn_{msg_id}_{emoji}"
                chip = f" {emoji} {count} "
                self.chat_text.insert(tk.END, chip, (tag, rxn_tag))
                self.chat_text.tag_bind(
                    rxn_tag, "<Button-1>",
                    lambda e, mid=msg_id, em=emoji, mine=rxn.get('mine'):
                        self._toggle_reaction(mid, em, mine),
                )
                self.chat_text.insert(tk.END, " ")
            self.chat_text.insert(tk.END, "\n")

        self.chat_text.insert(tk.END, "\n")  # blank separator
        end_index = self.chat_text.index("end-1c")
        # Tag entire range so right-click can find the message id.
        self.chat_text.tag_add(msg_tag, start_index, end_index)

    def _render_inline(self, content, leading="", track_self_mention=False):
        """Render `content` with markdown (bold/italic/inline-code/code-block),
        @mentions, and URL auto-linking. Inserts at end."""
        # Code block first (multi-line), then inline parsing on the rest.
        import re
        cb_re = re.compile(r"```(.*?)```", re.DOTALL)
        pos = 0
        for m in cb_re.finditer(content):
            if m.start() > pos:
                self._render_inline_simple(
                    leading + content[pos:m.start()],
                    track_self_mention=track_self_mention,
                )
            block = m.group(1).strip("\n")
            for line in block.split("\n"):
                self.chat_text.insert(tk.END, line + "\n", ("code_block",))
            pos = m.end()
        if pos < len(content):
            self._render_inline_simple(
                leading + content[pos:],
                track_self_mention=track_self_mention,
            )

    def _render_inline_simple(self, text, track_self_mention=False):
        """Render text with inline markdown + mentions + URLs (no code blocks).
        Each input line ends with a newline."""
        import re
        # Split into lines so leading spacing is preserved per line.
        lines = text.split("\n")
        for i, line in enumerate(lines):
            self._tokenize_inline_line(line, track_self_mention)
            # Re-add the newline (split removed it). The last fragment may
            # already have ended at an internal newline, so we add one too.
            if i < len(lines) - 1:
                self.chat_text.insert(tk.END, "\n")
        # Ensure final newline so the next render starts on its own line.
        if not text.endswith("\n"):
            self.chat_text.insert(tk.END, "\n")

    def _tokenize_inline_line(self, line, track_self_mention):
        """Walk a single line, emitting (text, tags) for bold/italic/inline-
        code/mention/url tokens; everything else is plain."""
        import re
        # Master pattern: order matters; bold before italic, code before others.
        pattern = re.compile(
            r"(?P<code>`[^`\n]+`)"
            r"|(?P<bold>\*\*[^*\n]+\*\*)"
            r"|(?P<italic>\*[^*\n]+\*)"
            r"|(?P<url>https?://[^\s)>\]]+)"
            r"|(?P<team>@team:[\w\-]+)"
            r"|(?P<mention>@\w+)"
        )
        pos = 0
        for m in pattern.finditer(line):
            if m.start() > pos:
                self.chat_text.insert(tk.END, line[pos:m.start()])
            kind = m.lastgroup
            text = m.group(0)
            if kind == "code":
                self.chat_text.insert(tk.END, text[1:-1], ("inline_code",))
            elif kind == "bold":
                self.chat_text.insert(tk.END, text[2:-2], ("bold",))
            elif kind == "italic":
                self.chat_text.insert(tk.END, text[1:-1], ("italic",))
            elif kind == "url":
                url_tag = f"url_{abs(hash(text)) & 0xffffffff}"
                self.chat_text.insert(tk.END, text, ("url", url_tag))
                # Inline domain badge as a minimal "preview"
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(text).netloc
                    if domain:
                        self.chat_text.insert(tk.END, f" [{domain}]", ("timestamp",))
                except Exception:
                    pass
                self.chat_text.tag_bind(
                    url_tag, "<Button-1>",
                    lambda e, u=text: webbrowser.open(u),
                )
            elif kind == "team":
                team_name = text.split(":", 1)[1]
                team_tag = f"team_{abs(hash(team_name)) & 0xffffffff}"
                self.chat_text.insert(tk.END, f" @{team_name} ",
                                      ("team_mention", team_tag))
                self.chat_text.tag_bind(
                    team_tag, "<Button-1>",
                    lambda e, name=team_name: self._show_team_members(name),
                )
            elif kind == "mention":
                handle = text[1:]
                tag = "self_mention" if (
                    self._current_username and handle.lower() == self._current_username.lower()
                ) else "mention"
                if tag == "self_mention" and track_self_mention:
                    try:
                        self.window.bell()
                    except Exception:
                        pass
                mention_tag = f"mention_{abs(hash(handle)) & 0xffffffff}"
                self.chat_text.insert(tk.END, text, (tag, mention_tag))
                self.chat_text.tag_bind(
                    mention_tag, "<Button-1>",
                    lambda e, h=handle: self._open_profile_for_handle(h),
                )
            pos = m.end()
        if pos < len(line):
            self.chat_text.insert(tk.END, line[pos:])

    def _redraw_all(self):
        """Re-render every cached message (used after edits/deletes/reactions
        and after Load Older). Preserves scroll-bottom anchoring."""
        was_at_bottom = self._is_at_bottom()
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete("1.0", tk.END)
        ordered = sorted(self._messages_by_id.values(), key=lambda m: m['id'])
        for msg in ordered:
            self._render_one_at_end(msg)
        self.chat_text.config(state=tk.DISABLED)
        if was_at_bottom:
            self.chat_text.see(tk.END)

    def _update_history_controls(self):
        if self.current_page >= self.total_pages:
            self.load_older_button.config(state=tk.DISABLED)
        else:
            self.load_older_button.config(state=tk.NORMAL)
        self.history_status.config(
            text=f"Page {self.current_page} of {self.total_pages}"
        )

    def _hydrate_reactions(self, messages):
        """Attach reactions to each message dict in-place."""
        if not messages:
            return
        try:
            ids = [m['id'] for m in messages if m.get('id')]
            rmap = self.dashboard.get_chat_reactions_for_messages(ids) or {}
        except Exception:
            rmap = {}
        for m in messages:
            m['reactions'] = rmap.get(m['id'], [])

    def _hydrate_polls(self, messages):
        """For any '[poll]' message, attach the poll details inline."""
        if not messages:
            return
        for m in messages:
            content = m.get('content') or ''
            if content.startswith('[poll]'):
                try:
                    poll = self.dashboard.get_chat_poll(m['id'])
                except Exception:
                    poll = None
                if poll:
                    m['poll'] = poll

    def _render_poll(self, poll):
        """Render a poll: question, options as clickable lines, totals."""
        msg_id = poll.get('message_id')
        self.chat_text.insert(tk.END, f"  📊 {poll.get('question', '')}\n",
                              ("poll_question",))
        meta_bits = []
        if poll.get('multi_choice'):
            meta_bits.append("multi-choice")
        if poll.get('closes_at'):
            meta_bits.append(f"closes at {poll['closes_at']}")
        meta_bits.append(f"{poll.get('total_voters', 0)} voted")
        self.chat_text.insert(tk.END, "  " + " · ".join(meta_bits) + "\n",
                              ("poll_meta",))
        for opt in poll.get('options', []):
            tag_name = f"polloption_{msg_id}_{opt['id']}"
            line_tag = "poll_chosen" if opt.get('mine') else "poll_option"
            mark = "● " if opt.get('mine') else "○ "
            line = f"  {mark}{opt['label']}  ({opt['count']})\n"
            self.chat_text.insert(tk.END, line, (line_tag, tag_name))
            self.chat_text.tag_bind(
                tag_name, "<Button-1>",
                lambda e, mid=msg_id, oid=opt['id']: self._cast_vote(mid, oid),
            )

    def _cast_vote(self, message_id, option_id):
        if not self.dashboard:
            return
        try:
            poll = self._messages_by_id.get(message_id, {}).get('poll') or {}
            multi = bool(poll.get('multi_choice'))
            chosen = []
            if multi:
                # Toggle: include or exclude this option from the existing vote.
                current = {o['id'] for o in poll.get('options', []) if o.get('mine')}
                if option_id in current:
                    current.discard(option_id)
                else:
                    current.add(option_id)
                chosen = list(current)
            else:
                chosen = [option_id]
            ok = self.dashboard.vote_chat_poll(message_id, chosen)
            if ok:
                self.load_messages()
        except Exception as e:
            messagebox.showerror("Error", f"Vote failed: {e}")

    def _update_mode_banner(self):
        """Show announcement-only / office-hours banner when relevant."""
        bits = []
        info = self.room_info or {}
        if info.get('announcement_mode'):
            bits.append("📢 Announcement-only — only admins can post here.")
        oh_start = info.get('oh_starts_at')
        oh_end = info.get('oh_ends_at')
        if oh_start or oh_end:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if oh_end and now > oh_end:
                bits.append(f"🕒 Office hours closed (ended {oh_end}).")
            elif oh_start and now < oh_start:
                bits.append(f"🕒 Office hours not yet open (start {oh_start}).")
            else:
                bits.append(f"🕒 Office hours open until {oh_end or 'no end set'}.")
        if bits:
            self.mode_banner.config(text="  " + "  ".join(bits))
            # Sit at the top, above all other rows already packed.
            siblings = self.mode_banner.master.pack_slaves()
            if siblings and siblings[0] is not self.mode_banner:
                self.mode_banner.pack(fill=tk.X, before=siblings[0])
            elif not self.mode_banner.winfo_ismapped():
                self.mode_banner.pack(fill=tk.X)
        else:
            self.mode_banner.pack_forget()

    def load_messages(self):
        """Load the most recent page of messages."""
        try:
            if not self.dashboard:
                self.chat_text.config(state=tk.NORMAL)
                self.chat_text.delete(1.0, tk.END)
                self.chat_text.insert(1.0, "Error: Dashboard not initialized. Please restart the application.\n")
                self.chat_text.config(state=tk.DISABLED)
                return

            self.current_page = 1
            self._messages_by_id.clear()
            self.last_message_id = 0
            self.oldest_message_id = None

            messages_data = self.dashboard.get_chat_messages(
                self.room_id, page=1, limit=self.PAGE_SIZE
            )

            self.chat_text.config(state=tk.NORMAL)
            self.chat_text.delete(1.0, tk.END)

            if not messages_data or not isinstance(messages_data, dict):
                self.chat_text.insert(1.0, "No messages to display.\n")
                self.total_pages = 1
            else:
                self.total_pages = max(1, messages_data.get('total_pages', 1))
                messages = messages_data.get('messages', [])
                self._hydrate_reactions(messages)
                self._hydrate_polls(messages)
                if not messages:
                    self.chat_text.insert(1.0, "No messages yet. Start the conversation!\n")
                else:
                    for msg in messages:
                        self._render_one_at_end(msg)
                        self._messages_by_id[msg['id']] = msg
                        mid = msg.get('id') or 0
                        if mid > self.last_message_id:
                            self.last_message_id = mid
                        if self.oldest_message_id is None or mid < self.oldest_message_id:
                            self.oldest_message_id = mid

            self.chat_text.config(state=tk.DISABLED)
            self.chat_text.see(tk.END)
            self._update_history_controls()
            self._mark_read_up_to(self.last_message_id)
        except Exception as e:
            self.chat_text.config(state=tk.NORMAL)
            self.chat_text.delete(1.0, tk.END)
            self.chat_text.insert(1.0, f"Error loading messages: {e}\n")
            self.chat_text.config(state=tk.DISABLED)
            logger.exception("Error loading chat messages")

    def load_older(self):
        """Fetch the next older page and merge it into the cache, then redraw."""
        if not self.dashboard:
            return
        if self.current_page >= self.total_pages:
            return
        try:
            next_page = self.current_page + 1
            messages_data = self.dashboard.get_chat_messages(
                self.room_id, page=next_page, limit=self.PAGE_SIZE
            )
            if not messages_data or not isinstance(messages_data, dict):
                return
            messages = messages_data.get('messages', [])
            self._hydrate_reactions(messages)
            self.total_pages = max(1, messages_data.get('total_pages', self.total_pages))
            self.current_page = next_page
            for msg in messages:
                self._messages_by_id[msg['id']] = msg
                mid = msg['id']
                if self.oldest_message_id is None or mid < self.oldest_message_id:
                    self.oldest_message_id = mid
            self._redraw_all()
            self._update_history_controls()
        except Exception as e:
            logger.exception("Error loading older chat messages")
            messagebox.showerror("Error", f"Error loading older messages: {e}")

    def _on_return(self, event):
        """Enter sends; Shift+Enter falls through to insert newline."""
        if event.state & 0x0001:  # Shift held
            return None
        self.send_message()
        return "break"

    def send_message(self, event=None):
        """Send a message to the chat room"""
        if not self.dashboard:
            messagebox.showerror("Error", "Dashboard not initialized. Cannot send message.")
            return
        text = self.message_entry.get("1.0", tk.END).strip()
        att = self._pending_attachment
        if not text and not att:
            return
        try:
            kwargs = {}
            if self._pending_reply:
                kwargs['reply_to_id'] = self._pending_reply['id']
            if att:
                kwargs.update({
                    'attachment_path': att['path'],
                    'attachment_name': att['name'],
                    'attachment_mime': att.get('mime'),
                    'attachment_size': att.get('size'),
                })
            result = self.dashboard.send_chat_message(self.room_id, text, **kwargs)
            if result:
                self.message_entry.delete("1.0", tk.END)
                self.clear_reply()
                self.clear_attachment()
                try:
                    self.dashboard.clear_chat_typing(self.room_id)
                except Exception:
                    pass
                self._last_typing_ping = 0.0
                self._poll_once()
            else:
                messagebox.showerror("Error", "Failed to send message")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending message: {e}")
            logger.exception("Error sending chat message")

    # ---- live updates: polling, typing, presence -----------------------

    def _on_key_release(self, _event=None):
        """Throttled outbound typing ping while the user is composing."""
        if not self.dashboard:
            return
        # Skip pings on Return / when entry is empty
        if not self.message_entry.get("1.0", tk.END).strip():
            return
        import time
        now = time.monotonic()
        if (now - self._last_typing_ping) * 1000 < self.TYPING_PING_MS:
            return
        self._last_typing_ping = now
        try:
            self.dashboard.set_chat_typing(self.room_id)
        except Exception:
            logger.debug("set_chat_typing failed", exc_info=True)

    def _poll(self):
        if self._closed:
            return
        try:
            self._poll_once()
        finally:
            if not self._closed:
                self._poll_job = self.window.after(self.POLL_MS, self._poll)

    def _poll_once(self):
        """One batched fetch per tick — replaces the previous 5–7 separate
        dashboard calls. The realtime helper opens a single connection and
        returns messages, typing, presence, members (optional), and the
        per-room unread count in one shot."""
        if not self.dashboard:
            return
        try:
            state = self.dashboard.get_room_realtime_state(
                self.room_id,
                since_message_id=self.last_message_id,
                include_members=bool(getattr(self, '_members_visible', False)),
                typing_ttl_seconds=self.TYPING_TTL_SEC,
            ) or {}
        except Exception:
            state = {}
            logger.debug("get_room_realtime_state failed", exc_info=True)

        new_msgs = state.get('messages') or []
        if new_msgs:
            self._hydrate_reactions(new_msgs)
            try:
                ids = [m['id'] for m in new_msgs if m.get('content', '').startswith('[poll]')]
                if ids:
                    polls = self.dashboard.get_chat_polls_for_messages(ids) or {}
                    for m in new_msgs:
                        if m['id'] in polls:
                            m['poll'] = polls[m['id']]
            except Exception:
                pass
            was_at_bottom = self._is_at_bottom()
            self.chat_text.config(state=tk.NORMAL)
            for msg in new_msgs:
                self._render_one_at_end(msg)
                self._messages_by_id[msg['id']] = msg
                mid = msg.get('id') or 0
                if mid > self.last_message_id:
                    self.last_message_id = mid
            self.chat_text.config(state=tk.DISABLED)
            if was_at_bottom:
                self.chat_text.see(tk.END)
                self._mark_read_up_to(self.last_message_id)
        elif state.get('last_message_id'):
            # Keep our pointer in sync even when the probe found nothing new.
            self.last_message_id = max(
                self.last_message_id or 0,
                int(state.get('last_message_id') or 0),
            )

        self._render_typing(state.get('typing_users') or [])

        presence = state.get('presence') or {}
        online = int(presence.get('online') or 0)
        total = int(presence.get('total') or 0)
        colour = "#2a8a2a" if online else "#888"
        try:
            self.presence_label.config(
                text=f"● {online}/{total} online", foreground=colour,
            )
        except Exception:
            pass

        # Members sidebar (already fetched in the same round trip)
        if getattr(self, '_members_visible', False):
            members = state.get('members')
            if members is not None:
                self._render_members_panel(members)

    def _render_members_panel(self, members):
        """Render the cached member list directly (no extra DB calls)."""
        if not getattr(self, 'members_tree', None):
            return
        self._cached_members = members
        for it in self.members_tree.get_children():
            self.members_tree.delete(it)
        for m in members:
            online = m.get('is_online', False)
            role = ("Creator" if m.get('is_creator')
                    else "Admin" if m.get('is_admin') else "Member")
            self.members_tree.insert(
                '', tk.END,
                values=(
                    "● online" if online else "○ offline",
                    f"{m['full_name']} (@{m['username']})",
                    role,
                ),
                tags=(str(m['user_id']),
                      "online" if online else "offline"),
            )

    def _render_typing(self, names):
        if not names:
            self.typing_label.config(text="")
            return
        if len(names) == 1:
            text = f"{names[0]} is typing…"
        elif len(names) == 2:
            text = f"{names[0]} and {names[1]} are typing…"
        else:
            text = f"{names[0]}, {names[1]} and {len(names) - 2} others are typing…"
        self.typing_label.config(text=text)

    def _presence_heartbeat(self):
        if self._closed:
            return
        try:
            if self.dashboard:
                self.dashboard.update_chat_presence(self.room_id)
        except Exception:
            logger.debug("update_chat_presence failed", exc_info=True)
        self._presence_job = self.window.after(self.PRESENCE_PING_MS, self._presence_heartbeat)

    def _mark_read_up_to(self, message_id):
        if not self.dashboard or not message_id:
            return
        try:
            self.dashboard.mark_chat_messages_read(self.room_id, up_to_message_id=message_id)
        except Exception:
            logger.debug("mark_chat_messages_read failed", exc_info=True)

    def _on_close(self):
        self._closed = True
        for job in (self._poll_job, self._presence_job):
            if job is not None:
                try:
                    self.window.after_cancel(job)
                except Exception:
                    pass
        self._poll_job = None
        self._presence_job = None
        # Clear typing flag so other members don't see a stale "typing…".
        try:
            if self.dashboard:
                self.dashboard.clear_chat_typing(self.room_id)
        except Exception:
            pass
        # Mark the latest message read on exit.
        self._mark_read_up_to(self.last_message_id)
        self.window.destroy()

    def show_members(self):
        try:
            # Toggle the embedded sidebar instead of popping a dialog.
            if self._members_visible:
                self.paned.forget(self.members_pane)
                self._members_visible = False
            else:
                self.paned.add(self.members_pane, weight=1)
                self._members_visible = True
                self._refresh_members_panel()
        except Exception as e:
            messagebox.showerror("Error", f"Error toggling members: {e}")

    def _refresh_members_panel(self):
        """Re-populate the members sidebar from get_room_members + presence.
        Cheap enough to call on each poll tick."""
        if not getattr(self, 'members_tree', None) or not self._members_visible:
            return
        try:
            members = self.dashboard.get_room_members(self.room_id) or []
            presence = {p['user_id']: p
                        for p in (self.dashboard.get_chat_presence(self.room_id) or [])}
        except Exception:
            return
        self._cached_members = members
        for it in self.members_tree.get_children():
            self.members_tree.delete(it)
        for m in members:
            p = presence.get(m['user_id'], {})
            online = p.get('is_online', False)
            role = ("Creator" if m.get('is_creator')
                    else "Admin" if m.get('is_admin') else "Member")
            self.members_tree.insert(
                '', tk.END,
                values=(
                    "● online" if online else "○ offline",
                    f"{m['full_name']} (@{m['username']})",
                    role,
                ),
                tags=(str(m['user_id']),
                      "online" if online else "offline"),
            )

    def open_manage_members(self):
        """Admin shortcut: open the full member-management dialog (kick / ban /
        mute / promote / transfer ownership / Bans viewer)."""
        if not (self.room_info or {}).get('is_admin'):
            messagebox.showinfo("Manage members",
                                "You need to be a room admin to manage members.")
            return
        ManageMembersDialog(self.window, self.dashboard, self.room_info,
                            refresh_callback=self._refresh_members_panel)

    def _on_member_right_click(self, event):
        """Admin: right-click a sidebar row for quick kick / ban / promote /
        demote without leaving the chat window."""
        if not (self.room_info or {}).get('is_admin'):
            return
        iid = self.members_tree.identify_row(event.y)
        if not iid:
            return
        self.members_tree.selection_set(iid)
        tags = self.members_tree.item(iid).get('tags') or ()
        target_uid = None
        for t in tags:
            if str(t).isdigit():
                target_uid = int(t)
                break
        if not target_uid:
            return
        # Find the cached member dict so we know creator/admin status.
        member = next(
            (m for m in (self._cached_members or [])
             if m.get('user_id') == target_uid),
            {},
        )
        if member.get('is_creator'):
            return  # no actions on the creator

        menu = tk.Menu(self.window, tearoff=0)
        if member.get('is_admin'):
            menu.add_command(
                label="Demote to member",
                command=lambda: self._do_member_action(
                    self.dashboard.set_room_admin, target_uid, False,
                ),
            )
        else:
            menu.add_command(
                label="Promote to admin",
                command=lambda: self._do_member_action(
                    self.dashboard.set_room_admin, target_uid, True,
                ),
            )
        menu.add_separator()
        menu.add_command(
            label="Kick from room",
            command=lambda: self._confirm_and(
                "Kick", f"Remove this member from the room?",
                self.dashboard.kick_room_member, target_uid,
            ),
        )
        menu.add_command(
            label="Ban from room…",
            command=lambda: self._ban_from_sidebar(target_uid),
        )
        menu.add_command(
            label="Mute…",
            command=lambda: self._mute_from_sidebar(target_uid),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _do_member_action(self, fn, target_uid, *args):
        try:
            ok = fn(self.room_id, target_uid, *args)
            if ok:
                self._refresh_members_panel()
            else:
                messagebox.showerror("Error",
                                     "Action denied (creator can't be acted on, "
                                     "or you lack permission).")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _confirm_and(self, title, prompt, fn, target_uid, *args):
        if not messagebox.askyesno(title, prompt, parent=self.window):
            return
        # Kick path takes a reason kwarg for the email notice; ask for it.
        if fn is getattr(self.dashboard, 'kick_room_member', None):
            reason = askstring(
                "Kick reason",
                "Reason (optional, included in the email notice):",
                parent=self.window,
            ) or ''
            try:
                ok = self.dashboard.kick_room_member(
                    self.room_id, target_uid, reason=reason,
                )
                if ok:
                    self._refresh_members_panel()
                else:
                    messagebox.showerror("Error",
                                         "Action denied (creator can't be acted on, "
                                         "or you lack permission).")
            except Exception as e:
                messagebox.showerror("Error", str(e))
            return
        self._do_member_action(fn, target_uid, *args)

    def _ban_from_sidebar(self, target_uid):
        if not messagebox.askyesno(
            "Ban member",
            "Ban this user from the room? They will be removed and unable "
            "to rejoin until you unban them.",
            parent=self.window,
        ):
            return
        reason = askstring("Ban reason",
                           "Reason (optional, shown in audit log):",
                           parent=self.window) or ''
        try:
            ok = self.dashboard.ban_room_member(
                self.room_id, target_uid, banned=True, reason=reason,
            )
            if ok:
                self._refresh_members_panel()
            else:
                messagebox.showerror("Error", "Could not ban (creator?).")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _mute_from_sidebar(self, target_uid):
        minutes = askinteger("Mute", "Mute for how many minutes?",
                             parent=self.window, minvalue=1, maxvalue=10080)
        if not minutes:
            return
        reason = askstring(
            "Mute reason",
            "Reason (optional, included in the email notice):",
            parent=self.window,
        ) or ''
        try:
            ok = self.dashboard.mute_room_member(
                self.room_id, target_uid, minutes, reason=reason,
            )
            if ok:
                self._refresh_members_panel()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def show_seen_by(self):
        """Show who has read up to the latest message."""
        if not self.dashboard or not self.last_message_id:
            messagebox.showinfo("Seen By", "No messages yet.")
            return
        try:
            readers = self.dashboard.get_chat_message_readers(
                self.room_id, self.last_message_id
            )
            if not readers:
                messagebox.showinfo("Seen By", "Nobody else has read the latest message yet.")
                return
            lines = [f"• {r['full_name']} (@{r['username']})  — {r['read_at']}" for r in readers]
            messagebox.showinfo(
                f"Seen by {len(readers)}",
                "Latest message has been read by:\n\n" + "\n".join(lines),
            )
        except Exception as e:
            messagebox.showerror("Error", f"Error fetching read receipts: {e}")

    # ---- per-message context menu and actions --------------------------

    def _message_id_at_index(self, index):
        for tag in self.chat_text.tag_names(index):
            if tag.startswith("m") and tag[1:].isdigit():
                return int(tag[1:])
        return None

    def _on_right_click(self, event):
        index = self.chat_text.index(f"@{event.x},{event.y}")
        msg_id = self._message_id_at_index(index)
        if msg_id is None:
            return
        msg = self._messages_by_id.get(msg_id)
        if not msg:
            return
        self._context_message_id = msg_id
        is_own = msg.get('sender_id') == self._current_user_id
        is_deleted = msg.get('is_deleted')

        menu = tk.Menu(self.window, tearoff=0)
        if not is_deleted:
            if msg.get('poll'):
                menu.add_command(
                    label="Propose dates to calendar",
                    command=lambda: self._propose_poll_to_calendar(msg_id),
                )
                menu.add_separator()
            menu.add_command(label="Reply", command=lambda: self._reply_to(msg_id))
            react_menu = tk.Menu(menu, tearoff=0)
            for emoji in self.REACTION_PALETTE:
                react_menu.add_command(
                    label=emoji,
                    command=lambda em=emoji: self._toggle_reaction(msg_id, em, mine=False),
                )
            menu.add_cascade(label="React", menu=react_menu)
            pin_label = "Unpin" if msg.get('pinned_at') else "Pin"
            menu.add_command(label=pin_label,
                             command=lambda: self._toggle_pin(msg_id, not msg.get('pinned_at')))
            menu.add_separator()
            menu.add_command(label="Copy text", command=lambda: self._copy_message(msg_id))
            menu.add_command(label="Copy link", command=lambda: self._copy_message_link(msg_id))
            menu.add_separator()
            menu.add_command(label="Report message…",
                             command=lambda: self._report_message(msg_id))
            if is_own:
                menu.add_separator()
                menu.add_command(label="Edit…", command=lambda: self._edit_message(msg_id))
                menu.add_command(label="Delete", command=lambda: self._delete_message(msg_id))
        else:
            menu.add_command(label="Copy link", command=lambda: self._copy_message_link(msg_id))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _reply_to(self, msg_id):
        msg = self._messages_by_id.get(msg_id)
        if not msg:
            return
        snippet = (msg.get('content') or '').replace('\n', ' ')
        if len(snippet) > 60:
            snippet = snippet[:57] + '…'
        self._pending_reply = {
            'id': msg_id, 'snippet': snippet, 'sender': msg.get('sender'),
        }
        self.reply_label.config(text=f"↪ Replying to {msg.get('sender')}: {snippet}")
        self.reply_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.reply_cancel.pack(side=tk.LEFT)
        self.message_entry.focus_set()

    def clear_reply(self):
        self._pending_reply = None
        self.reply_label.pack_forget()
        self.reply_cancel.pack_forget()

    def attach_file(self):
        path = filedialog.askopenfilename(parent=self.window, title="Attach file")
        if not path:
            return
        try:
            size = os.path.getsize(path)
        except OSError:
            size = None
        name = os.path.basename(path)
        import mimetypes
        mime, _ = mimetypes.guess_type(path)
        self._pending_attachment = {
            'path': path, 'name': name, 'mime': mime, 'size': size,
        }
        size_str = self._format_size(size)
        self.attach_label.config(
            text=f"📎 {name}" + (f" ({size_str})" if size_str else "")
        )
        self.attach_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.attach_cancel.pack(side=tk.LEFT)

    def clear_attachment(self):
        self._pending_attachment = None
        self.attach_label.pack_forget()
        self.attach_cancel.pack_forget()

    def _open_attachment(self, path):
        if not path:
            return
        try:
            webbrowser.open(path if path.startswith(("http://", "https://")) else f"file://{os.path.abspath(path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open attachment: {e}")

    def _toggle_reaction(self, msg_id, emoji, mine):
        if not self.dashboard:
            return
        try:
            if mine:
                ok = self.dashboard.remove_chat_reaction(msg_id, emoji)
            else:
                ok = self.dashboard.add_chat_reaction(msg_id, emoji)
            if ok:
                self._refresh_message(msg_id)
        except Exception as e:
            messagebox.showerror("Error", f"Reaction failed: {e}")

    def _toggle_pin(self, msg_id, pin):
        try:
            ok = self.dashboard.pin_chat_message(msg_id, pin=pin)
            if ok:
                self._refresh_message(msg_id)
            else:
                messagebox.showerror("Error", "Could not change pin (need admin or own message).")
        except Exception as e:
            messagebox.showerror("Error", f"Pin failed: {e}")

    def _edit_message(self, msg_id):
        msg = self._messages_by_id.get(msg_id)
        if not msg:
            return
        new_text = askstring("Edit message", "New message text:",
                             initialvalue=msg.get('content', ''),
                             parent=self.window)
        if new_text is None:
            return
        new_text = new_text.strip()
        if not new_text:
            return
        try:
            ok = self.dashboard.edit_chat_message(msg_id, new_text)
            if ok:
                self._refresh_message(msg_id)
            else:
                messagebox.showerror("Error", "Edit failed (own messages only).")
        except Exception as e:
            messagebox.showerror("Error", f"Edit failed: {e}")

    def _delete_message(self, msg_id):
        if not messagebox.askyesno("Delete", "Delete this message?"):
            return
        try:
            ok = self.dashboard.delete_chat_message(msg_id)
            if ok:
                self._refresh_message(msg_id)
            else:
                messagebox.showerror("Error", "Delete failed (own messages or admin only).")
        except Exception as e:
            messagebox.showerror("Error", f"Delete failed: {e}")

    def _copy_message(self, msg_id):
        msg = self._messages_by_id.get(msg_id) or {}
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(msg.get('content') or '')
        except Exception:
            pass

    def _report_message(self, msg_id):
        dlg = tk.Toplevel(self.window)
        dlg.title("Report message")
        dlg.geometry("420x260")
        dlg.transient(self.window)
        dlg.after(100, lambda: dlg.grab_set() if dlg.winfo_exists() else None)
        frame = ttk.Frame(dlg, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Why are you reporting this message?").pack(anchor=tk.W)
        text = scrolledtext.ScrolledText(frame, height=6, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, pady=(4, 8))
        escalate_var = tk.BooleanVar()
        ttk.Checkbutton(
            frame,
            text="Escalate as a safeguarding concern (creates a case file)",
            variable=escalate_var,
        ).pack(anchor=tk.W)

        def submit():
            reason = text.get("1.0", tk.END).strip()
            try:
                ok = self.dashboard.report_chat_message(
                    msg_id, reason,
                    escalate_safeguarding=bool(escalate_var.get()),
                )
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)
                return
            if ok:
                messagebox.showinfo(
                    "Reported",
                    "Thank you. A moderator will review the report.",
                    parent=dlg,
                )
                dlg.destroy()
            else:
                messagebox.showerror("Error", "Could not submit report.",
                                     parent=dlg)

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Submit", command=submit).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Cancel",
                   command=dlg.destroy).pack(side=tk.RIGHT, padx=5)

    def _copy_message_link(self, msg_id):
        link = f"chat://room/{self.room_id}/message/{msg_id}"
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(link)
            self.window.update()
            messagebox.showinfo("Copied", f"Link copied:\n{link}")
        except Exception:
            pass

    def _refresh_message(self, msg_id):
        """Re-fetch the room (cheap path: reload current page) so the cache
        and the rendering reflect the latest server state."""
        # Simple, robust approach: reload page 1.
        self.load_messages()

    # ---- search and pinned panel ---------------------------------------

    def do_search(self):
        query = (self.search_var.get() or '').strip()
        if not query:
            # Clear highlights
            self.chat_text.tag_remove("search_hit", "1.0", tk.END)
            return
        if not self.dashboard:
            return
        try:
            hits = self.dashboard.search_chat_messages(query, room_id=self.room_id)
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {e}")
            return
        if not hits:
            messagebox.showinfo("Search", f"No matches for '{query}' in this room.")
            return
        # Highlight matches in the currently rendered window.
        self.chat_text.tag_remove("search_hit", "1.0", tk.END)
        idx = "1.0"
        first_hit = None
        while True:
            idx = self.chat_text.search(query, idx, nocase=True, stopindex=tk.END)
            if not idx:
                break
            end = f"{idx}+{len(query)}c"
            self.chat_text.tag_add("search_hit", idx, end)
            if first_hit is None:
                first_hit = idx
            idx = end
        if first_hit:
            self.chat_text.see(first_hit)
        messagebox.showinfo("Search", f"{len(hits)} match(es) in this room "
                                       "(highlighted in view; older matches may be off-screen).")

    def show_pinned(self):
        if not self.dashboard:
            return
        try:
            pinned = self.dashboard.get_pinned_messages(self.room_id) or []
        except Exception as e:
            messagebox.showerror("Error", f"Could not load pinned messages: {e}")
            return
        dlg = tk.Toplevel(self.window)
        dlg.title(f"Pinned in {self.room_name}")
        dlg.geometry("520x400")
        dlg.transient(self.window)
        if not pinned:
            ttk.Label(dlg, text="No pinned messages.").pack(padx=20, pady=20)
        else:
            txt = scrolledtext.ScrolledText(dlg, wrap=tk.WORD, state=tk.NORMAL)
            txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            for p in pinned:
                txt.insert(tk.END, f"★ [{p['sent_at'][:16]}] {p['sender']}\n",
                           ("header",))
                txt.insert(tk.END, f"  {p.get('content', '')}\n\n")
            txt.tag_configure("header", font=("TkDefaultFont", 10, "bold"),
                              foreground="#b8860b")
            txt.config(state=tk.DISABLED)
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=(0, 10))

    # ---- academics + staff_hr integration ------------------------------

    def show_module_info(self):
        code = (self.room_info or {}).get('linked_course_code')
        if not code:
            messagebox.showinfo("Module", "This room isn't linked to a module.")
            return
        try:
            info = self.dashboard.get_module_info(code)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if not info:
            messagebox.showinfo("Module",
                                f"No module record found for '{code}'.")
            return

        dlg = tk.Toplevel(self.window)
        dlg.title(f"Module: {info.get('name') or code}")
        dlg.geometry("560x420")
        dlg.transient(self.window)
        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=info.get('name') or code,
                  font=("TkDefaultFont", 13, "bold")).pack(anchor=tk.W)
        ttk.Label(frame, foreground="#666",
                  text=f"{info.get('code')} · instructor: {info.get('instructor') or '—'}"
                  ).pack(anchor=tk.W, pady=(0, 8))
        if info.get('description'):
            desc = scrolledtext.ScrolledText(frame, height=5, wrap=tk.WORD)
            desc.insert("1.0", info['description'])
            desc.config(state=tk.DISABLED)
            desc.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(frame, text="Upcoming assignments",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=(4, 2))
        cols = ("Title", "Due", "Type", "Marks")
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=10)
        for c in cols:
            tree.heading(c, text=c)
        tree.column("Title", width=240)
        tree.column("Due", width=130)
        tree.column("Type", width=80, anchor=tk.CENTER)
        tree.column("Marks", width=60, anchor=tk.CENTER)
        for a in info.get('assignments', []):
            tree.insert('', tk.END, values=(
                a['title'], (a.get('due_date') or '')[:16],
                a.get('type') or '', a.get('max_marks') or '',
            ))
        tree.pack(fill=tk.BOTH, expand=True)

        ttk.Button(frame, text="Close", command=dlg.destroy).pack(pady=(8, 0))

    def post_due_dates(self):
        code = (self.room_info or {}).get('linked_course_code')
        if not code:
            messagebox.showinfo("Due dates", "This room isn't linked to a module.")
            return
        try:
            n = self.dashboard.post_assignment_due_dates(self.room_id)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if n:
            self.load_messages()
            messagebox.showinfo("Due dates",
                                f"Posted {n} new due-date notice(s).")
        else:
            messagebox.showinfo("Due dates",
                                "No new upcoming assignments to post.")

    def _propose_poll_to_calendar(self, msg_id):
        try:
            proposed = self.dashboard.propose_poll_dates_to_calendar(msg_id)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if not proposed:
            messagebox.showinfo(
                "Calendar",
                "No date-formatted options found in this poll, or the calendar "
                "table isn't available.\n\n"
                "Tip: write options like '2026-05-14' or '2026-05-14 14:00'.",
            )
            return
        lines = [f"• {p['date']}  ({p['option']})" for p in proposed]
        messagebox.showinfo(
            "Calendar",
            f"Added {len(proposed)} tentative event(s):\n\n" + "\n".join(lines),
        )

    def _open_profile_for_handle(self, handle):
        if not handle or not self.dashboard:
            return
        try:
            uid = self.dashboard.resolve_username_to_id(handle)
        except Exception:
            uid = None
        if not uid:
            messagebox.showinfo("Profile",
                                f"No profile found for @{handle}.")
            return
        UserProfileDialog(self.window, self.dashboard, uid)

    def _show_team_members(self, team_name):
        try:
            members = self.dashboard.get_team_members(team_name) or []
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        dlg = tk.Toplevel(self.window)
        dlg.title(f"Team: {team_name}")
        dlg.geometry("440x340")
        dlg.transient(self.window)
        frame = ttk.Frame(dlg, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        if not members:
            ttk.Label(frame, text=f"No staff found in department '{team_name}'.",
                      foreground="#666").pack(padx=10, pady=20)
        else:
            cols = ("Name", "Username", "Job title")
            tree = ttk.Treeview(frame, columns=cols, show="headings")
            for c in cols:
                tree.heading(c, text=c)
            tree.column("Name", width=160)
            tree.column("Username", width=110)
            tree.column("Job title", width=140)
            for m in members:
                tree.insert('', tk.END, values=(
                    m['full_name'],
                    f"@{m['username']}" if m['username'] else '',
                    m['job_title'],
                ))
            tree.pack(fill=tk.BOTH, expand=True)
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=(8, 0))

    def _open_room_switcher(self, _event=None):
        """Ctrl+K: jump to another room via a quick-find dialog."""
        RoomSwitcherDialog(self.window, self.dashboard,
                           current_room_id=self.room_id)
        return "break"

    # ---- notes / polls / raise-hand / queue ----------------------------

    def open_notes(self):
        if not self.dashboard:
            return
        RoomNotesDialog(self.window, self.dashboard, self.room_id, self.room_name)

    def create_poll(self):
        PollComposerDialog(self.window, self.dashboard, self.room_id,
                           on_created=self.load_messages)

    def toggle_hand(self):
        if not self.dashboard:
            return
        try:
            queue = self.dashboard.get_room_queue(self.room_id) or []
            mine = any(q.get('mine') for q in queue)
            if mine:
                ok = self.dashboard.lower_hand(self.room_id)
            else:
                ok = self.dashboard.raise_hand(self.room_id)
            if ok:
                self.hand_button.config(
                    text="✋ Lower Hand" if not mine else "🙋 Raise Hand"
                )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def show_queue(self):
        if not self.dashboard:
            return
        QueueDialog(self.window, self.dashboard, self.room_id,
                    is_admin=bool((self.room_info or {}).get('is_admin')))

    def invite_user(self):
        username = askstring("Invite User", "Enter username to invite:")
        if username:
            try:
                # Find user and invite
                from education_system.university_system.infrastructure.email.admin import search_users as _su
                users = _su(self.dashboard.auth, username)
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
                    self._on_close()
                else:
                    messagebox.showerror("Error", "Failed to leave room")
            except Exception as e:
                messagebox.showerror("Error", f"Error leaving room: {e}")


class EditRoomDialog:
    """Edit room metadata: name, description, type, category, icon, colour, max_members."""

    ROOM_TYPES = ("public", "private", "course", "department")
    PRESET_COLOURS = ("", "#ffe4e1", "#e1f0ff", "#e1ffe4", "#fff7d6", "#f0e1ff", "#e6e6e6")

    def __init__(self, parent, dashboard, room, refresh_callback=None):
        self.dashboard = dashboard
        self.room = room
        self.refresh_callback = refresh_callback
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit Room: {room.get('name', '')}")
        self.dialog.geometry("460x440")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        self._build()

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.name_var = tk.StringVar(value=self.room.get('name', ''))
        ttk.Entry(frame, textvariable=self.name_var).grid(row=0, column=1, sticky=tk.EW, pady=4)

        ttk.Label(frame, text="Description:").grid(row=1, column=0, sticky=tk.NW, pady=4)
        self.desc_text = tk.Text(frame, height=4, wrap=tk.WORD)
        self.desc_text.grid(row=1, column=1, sticky=tk.EW, pady=4)
        if self.room.get('description'):
            self.desc_text.insert("1.0", self.room['description'])

        ttk.Label(frame, text="Type:").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.type_var = tk.StringVar(value=self.room.get('room_type') or 'public')
        ttk.Combobox(frame, textvariable=self.type_var, values=self.ROOM_TYPES,
                     state="readonly").grid(row=2, column=1, sticky=tk.EW, pady=4)

        ttk.Label(frame, text="Category:").grid(row=3, column=0, sticky=tk.W, pady=4)
        try:
            existing = self.dashboard.list_chat_categories() or []
        except Exception:
            existing = []
        self.category_var = tk.StringVar(value=self.room.get('category') or '')
        ttk.Combobox(frame, textvariable=self.category_var, values=existing).grid(
            row=3, column=1, sticky=tk.EW, pady=4)

        ttk.Label(frame, text="Icon (emoji):").grid(row=4, column=0, sticky=tk.W, pady=4)
        self.icon_var = tk.StringVar(value=self.room.get('icon') or '')
        ttk.Entry(frame, textvariable=self.icon_var, width=6).grid(
            row=4, column=1, sticky=tk.W, pady=4)

        ttk.Label(frame, text="Colour:").grid(row=5, column=0, sticky=tk.W, pady=4)
        self.colour_var = tk.StringVar(value=self.room.get('colour') or '')
        ttk.Combobox(frame, textvariable=self.colour_var, values=self.PRESET_COLOURS).grid(
            row=5, column=1, sticky=tk.EW, pady=4)

        ttk.Label(frame, text="Max members:").grid(row=6, column=0, sticky=tk.W, pady=4)
        self.max_var = tk.StringVar(value=str(self.room.get('max_members') or ''))
        ttk.Entry(frame, textvariable=self.max_var, width=8).grid(
            row=6, column=1, sticky=tk.W, pady=4)

        ttk.Label(frame, text="Linked module:").grid(row=7, column=0, sticky=tk.W, pady=4)
        self.course_var = tk.StringVar(value=self.room.get('linked_course_code') or '')
        ttk.Entry(frame, textvariable=self.course_var).grid(
            row=7, column=1, sticky=tk.EW, pady=4)

        self.ann_var = tk.BooleanVar(value=bool(self.room.get('announcement_mode')))
        ttk.Checkbutton(frame, text="Announcement-only (only admins can post)",
                        variable=self.ann_var).grid(row=8, column=0, columnspan=2,
                                                    sticky=tk.W, pady=4)

        ttk.Label(frame, text="Office hours start:").grid(row=9, column=0, sticky=tk.W, pady=4)
        self.oh_start_var = tk.StringVar(value=self.room.get('oh_starts_at') or '')
        ttk.Entry(frame, textvariable=self.oh_start_var).grid(
            row=9, column=1, sticky=tk.EW, pady=4)
        ttk.Label(frame, text="Office hours end:").grid(row=10, column=0, sticky=tk.W, pady=4)
        self.oh_end_var = tk.StringVar(value=self.room.get('oh_ends_at') or '')
        ttk.Entry(frame, textvariable=self.oh_end_var).grid(
            row=10, column=1, sticky=tk.EW, pady=4)
        ttk.Label(frame, text="(format: YYYY-MM-DD HH:MM:SS)",
                  foreground="#666").grid(row=11, column=1, sticky=tk.W)

        ttk.Label(frame, text="Retention (days):").grid(row=12, column=0, sticky=tk.W, pady=4)
        self.retention_var = tk.StringVar(value=str(self.room.get('retention_days') or ''))
        ttk.Entry(frame, textvariable=self.retention_var, width=8).grid(
            row=12, column=1, sticky=tk.W, pady=4)

        ttk.Label(frame, text="Slow-mode (seconds):").grid(row=13, column=0, sticky=tk.W, pady=4)
        self.slow_var = tk.StringVar(value=str(self.room.get('slow_mode_seconds') or 0))
        ttk.Entry(frame, textvariable=self.slow_var, width=8).grid(
            row=13, column=1, sticky=tk.W, pady=4)

        self.enc_var = tk.BooleanVar(value=bool(self.room.get('is_encrypted')))
        ttk.Checkbutton(frame, text="Encrypt new messages at rest (deterrent only)",
                        variable=self.enc_var).grid(row=14, column=0, columnspan=2,
                                                    sticky=tk.W, pady=4)

        btns = ttk.Frame(frame)
        btns.grid(row=15, column=0, columnspan=2, pady=12)
        ttk.Button(btns, text="Save", command=self._save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Name is required.")
            return
        for var, label_for_msg in ((self.oh_start_var, "Office-hours start"),
                                    (self.oh_end_var, "Office-hours end")):
            v = var.get().strip()
            if v:
                try:
                    datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    messagebox.showwarning("Bad date",
                                           f"{label_for_msg} must be YYYY-MM-DD HH:MM:SS.")
                    return
        kwargs = {
            'name': name,
            'description': self.desc_text.get("1.0", tk.END).strip(),
            'room_type': self.type_var.get(),
            'category': self.category_var.get().strip(),
            'icon': self.icon_var.get().strip(),
            'colour': self.colour_var.get().strip(),
            'linked_course_code': self.course_var.get().strip(),
            'announcement_mode': bool(self.ann_var.get()),
            'oh_starts_at': self.oh_start_var.get().strip(),
            'oh_ends_at': self.oh_end_var.get().strip(),
            'is_encrypted': bool(self.enc_var.get()),
        }
        max_str = self.max_var.get().strip()
        if max_str:
            try:
                kwargs['max_members'] = int(max_str)
            except ValueError:
                messagebox.showwarning("Invalid", "Max members must be a number.")
                return
        ret_str = self.retention_var.get().strip()
        if ret_str:
            try:
                kwargs['retention_days'] = int(ret_str)
            except ValueError:
                messagebox.showwarning("Invalid", "Retention days must be a number.")
                return
        else:
            kwargs['retention_days'] = ''
        slow_str = self.slow_var.get().strip()
        try:
            kwargs['slow_mode_seconds'] = int(slow_str) if slow_str else 0
        except ValueError:
            messagebox.showwarning("Invalid", "Slow-mode seconds must be a number.")
            return
        try:
            ok = self.dashboard.update_chat_room(self.room['id'], **kwargs)
            if ok:
                self.dialog.destroy()
                if self.refresh_callback:
                    self.refresh_callback()
            else:
                messagebox.showerror("Error", "Could not update room (admin only).")
        except Exception as e:
            messagebox.showerror("Error", str(e))


class ManageMembersDialog:
    """Admin tool: promote/demote, kick, ban/unban, mute, transfer ownership."""

    def __init__(self, parent, dashboard, room, refresh_callback=None):
        self.dashboard = dashboard
        self.room = room
        self.room_id = room['id']
        self.refresh_callback = refresh_callback
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Members of {room.get('name', '')}")
        self.dialog.geometry("680x420")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        self._build()
        self._load()

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        cols = ("Username", "Name", "Role", "State", "Muted until")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.column("Username", width=110)
        self.tree.column("Name", width=160)
        self.tree.column("Role", width=80)
        self.tree.column("State", width=100)
        self.tree.column("Muted until", width=140)
        self.tree.tag_configure("banned", foreground="#888")
        self.tree.tag_configure("creator", font=("TkDefaultFont", 10, "bold"))
        self.tree.pack(fill=tk.BOTH, expand=True)

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Promote",
                   command=lambda: self._set_admin(True)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Demote",
                   command=lambda: self._set_admin(False)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Kick", command=self._kick).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Ban", command=self._ban_with_reason).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Bans…",
                   command=self._show_bans).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Mute…", command=self._mute).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Unmute", command=self._unmute).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Transfer Ownership",
                   command=self._transfer).pack(side=tk.LEFT, padx=10)
        ttk.Button(btns, text="Close",
                   command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load(self):
        for it in self.tree.get_children():
            self.tree.delete(it)
        try:
            members = self.dashboard.get_room_members(self.room_id) or []
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        for m in members:
            role = ("Creator" if m.get('is_creator')
                    else "Admin" if m.get('is_admin') else "Member")
            state = "banned" if m.get('is_banned') else "active"
            tag = "creator" if m.get('is_creator') else ("banned" if m.get('is_banned') else "")
            self.tree.insert(
                '', tk.END,
                values=(f"@{m['username']}", m['full_name'], role, state,
                        m.get('muted_until') or ''),
                tags=(str(m['user_id']),) + ((tag,) if tag else ()),
            )

    def _selected_user_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        tags = self.tree.item(sel[0]).get('tags') or ()
        for t in tags:
            if str(t).isdigit():
                return int(t)
        return None

    def _act(self, fn, *args, success_msg=None):
        uid = self._selected_user_id()
        if not uid:
            messagebox.showwarning("Select", "Select a member first.")
            return
        try:
            ok = fn(self.room_id, uid, *args)
            if ok:
                if success_msg:
                    self.dialog.title(success_msg)
                self._load()
                if self.refresh_callback:
                    self.refresh_callback()
            else:
                messagebox.showerror("Error",
                                     "Action denied (creator can't be demoted/kicked, "
                                     "or you lack permission).")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _set_admin(self, promote):
        self._act(self.dashboard.set_room_admin, promote)

    def _kick(self):
        if not messagebox.askyesno("Kick", "Remove the selected member from this room?"):
            return
        reason = askstring(
            "Kick reason",
            "Reason (optional, included in the email notice):",
            parent=self.dialog,
        ) or ''
        self._act(self.dashboard.kick_room_member, reason)

    def _ban(self, banned, reason=None):
        # Underlying API now takes a reason kwarg.
        uid = self._selected_user_id()
        if not uid:
            messagebox.showwarning("Select", "Select a member first.",
                                   parent=self.dialog)
            return
        try:
            ok = self.dashboard.ban_room_member(self.room_id, uid,
                                                banned=banned, reason=reason)
            if ok:
                self._load()
                if self.refresh_callback:
                    self.refresh_callback()
            else:
                messagebox.showerror("Error",
                                     "Action denied (creator can't be banned, "
                                     "or you lack permission).",
                                     parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)

    def _ban_with_reason(self):
        uid = self._selected_user_id()
        if not uid:
            messagebox.showwarning("Select", "Select a member first.",
                                   parent=self.dialog)
            return
        if not messagebox.askyesno(
            "Ban member",
            "Ban this user from the room? They will be removed and unable "
            "to rejoin until you unban them.",
            parent=self.dialog,
        ):
            return
        reason = askstring("Ban reason",
                           "Reason (optional, shown in audit log):",
                           parent=self.dialog) or ''
        self._ban(True, reason=reason)

    def _show_bans(self):
        try:
            bans = self.dashboard.list_room_bans(self.room_id) or []
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)
            return
        dlg = tk.Toplevel(self.dialog)
        dlg.title(f"Bans — {self.room.get('name', '')}")
        dlg.geometry("520x340")
        dlg.transient(self.dialog)
        frame = ttk.Frame(dlg, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        if not bans:
            ttk.Label(frame, text="No active bans.",
                      foreground="#666").pack(padx=10, pady=20)
        else:
            cols = ("User", "Banned at", "By", "Reason")
            tree = ttk.Treeview(frame, columns=cols, show="headings")
            for c in cols:
                tree.heading(c, text=c)
            tree.column("User", width=150)
            tree.column("Banned at", width=130)
            tree.column("By", width=90)
            tree.column("Reason", width=140)
            for b in bans:
                tree.insert(
                    '', tk.END,
                    values=(
                        f"{b['full_name']} (@{b['username']})",
                        (b.get('banned_at') or '')[:16],
                        f"@{b.get('banned_by') or ''}" if b.get('banned_by') else '',
                        b.get('reason') or '',
                    ),
                    tags=(str(b['user_id']),),
                )
            tree.pack(fill=tk.BOTH, expand=True)

            def unban_selected():
                sel = tree.selection()
                if not sel:
                    return
                uid = int(tree.item(sel[0])['tags'][0])
                try:
                    ok = self.dashboard.ban_room_member(
                        self.room_id, uid, banned=False,
                    )
                    if ok:
                        dlg.destroy()
                        self._show_bans()  # refresh
                        if self.refresh_callback:
                            self.refresh_callback()
                    else:
                        messagebox.showerror("Error", "Could not unban.",
                                             parent=dlg)
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=dlg)

            ttk.Button(frame, text="Unban selected",
                       command=unban_selected).pack(pady=(8, 0))
        ttk.Button(frame, text="Close",
                   command=dlg.destroy).pack(pady=(8, 0))

    def _mute(self):
        minutes = askinteger("Mute", "Mute for how many minutes?",
                             parent=self.dialog, minvalue=1, maxvalue=10080)
        if not minutes:
            return
        reason = askstring(
            "Mute reason",
            "Reason (optional, included in the email notice):",
            parent=self.dialog,
        ) or ''
        self._act(self.dashboard.mute_room_member, minutes, reason)

    def _unmute(self):
        self._act(self.dashboard.mute_room_member, None)

    def _transfer(self):
        uid = self._selected_user_id()
        if not uid:
            messagebox.showwarning("Select", "Select the new owner first.")
            return
        if not messagebox.askyesno("Transfer Ownership",
                                   "Transfer ownership to this member? "
                                   "You will remain an admin."):
            return
        try:
            ok = self.dashboard.transfer_room_ownership(self.room_id, uid)
            if ok:
                self._load()
                if self.refresh_callback:
                    self.refresh_callback()
                messagebox.showinfo("Transferred", "Ownership transferred.")
            else:
                messagebox.showerror("Error",
                                     "Only the current owner can transfer ownership.")
        except Exception as e:
            messagebox.showerror("Error", str(e))


class PollComposerDialog:
    """Compose a chat poll: question, multiple options, optional close-time."""

    def __init__(self, parent, dashboard, room_id, on_created=None):
        self.dashboard = dashboard
        self.room_id = room_id
        self.on_created = on_created
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("New Poll")
        self.dialog.geometry("420x420")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        self._option_vars = []
        self._build()

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Question:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.question_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.question_var).grid(
            row=0, column=1, sticky=tk.EW, pady=4)

        ttk.Label(frame, text="Options:").grid(row=1, column=0, sticky=tk.NW, pady=4)
        self.options_frame = ttk.Frame(frame)
        self.options_frame.grid(row=1, column=1, sticky=tk.EW, pady=4)
        for _ in range(2):
            self._add_option_row()
        ttk.Button(frame, text="+ Add option",
                   command=self._add_option_row).grid(row=2, column=1, sticky=tk.W)

        self.multi_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Allow multiple choices",
                        variable=self.multi_var).grid(row=3, column=1,
                                                      sticky=tk.W, pady=8)

        ttk.Label(frame, text="Closes at (YYYY-MM-DD HH:MM:SS, optional):").grid(
            row=4, column=0, columnspan=2, sticky=tk.W, pady=(8, 2))
        self.closes_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.closes_var).grid(
            row=5, column=0, columnspan=2, sticky=tk.EW, pady=2)

        btns = ttk.Frame(frame)
        btns.grid(row=6, column=0, columnspan=2, pady=12)
        ttk.Button(btns, text="Create", command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _add_option_row(self):
        var = tk.StringVar()
        self._option_vars.append(var)
        ttk.Entry(self.options_frame, textvariable=var).pack(fill=tk.X, pady=2)

    def _create(self):
        question = self.question_var.get().strip()
        options = [v.get().strip() for v in self._option_vars if v.get().strip()]
        if not question or len(options) < 2:
            messagebox.showwarning("Missing", "Need a question and at least two options.")
            return
        closes_at = self.closes_var.get().strip() or None
        if closes_at:
            try:
                datetime.strptime(closes_at, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                messagebox.showwarning("Bad date", "Use format YYYY-MM-DD HH:MM:SS.")
                return
        try:
            ok = self.dashboard.create_chat_poll(
                self.room_id, question, options,
                multi_choice=self.multi_var.get(), closes_at=closes_at,
            )
            if ok:
                self.dialog.destroy()
                if self.on_created:
                    self.on_created()
            else:
                messagebox.showerror("Error", "Could not create poll.")
        except Exception as e:
            messagebox.showerror("Error", str(e))


class QueueDialog:
    """Office-hours queue. Members see their position; admins see Call Next."""

    POLL_MS = 3000

    def __init__(self, parent, dashboard, room_id, is_admin=False):
        self.dashboard = dashboard
        self.room_id = room_id
        self.is_admin = is_admin
        self._closed = False
        self._job = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Queue")
        self.dialog.geometry("400x340")
        self.dialog.transient(parent)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()
        self._refresh()
        self._job = self.dialog.after(self.POLL_MS, self._tick)

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        cols = ("#", "Member", "Joined")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.column("#", width=40, anchor=tk.CENTER)
        self.tree.tag_configure("mine", font=("TkDefaultFont", 10, "bold"),
                                foreground="#1a5fb4")
        self.tree.pack(fill=tk.BOTH, expand=True)

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=(8, 0))
        if self.is_admin:
            ttk.Button(btns, text="Call Next",
                       command=self._call_next).pack(side=tk.LEFT)
        ttk.Button(btns, text="Refresh", command=self._refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Close", command=self._on_close).pack(side=tk.RIGHT)

    def _refresh(self):
        for it in self.tree.get_children():
            self.tree.delete(it)
        try:
            queue = self.dashboard.get_room_queue(self.room_id) or []
        except Exception:
            queue = []
        for i, q in enumerate(queue, start=1):
            tags = ("mine",) if q.get('mine') else ()
            self.tree.insert(
                '', tk.END,
                values=(i, f"{q['full_name']} (@{q['username']})", q['joined_at'][:16]),
                tags=tags,
            )

    def _call_next(self):
        try:
            called = self.dashboard.call_next_in_queue(self.room_id)
            if called:
                messagebox.showinfo(
                    "Called",
                    f"Calling {called['full_name']} (@{called['username']}).",
                    parent=self.dialog,
                )
                self._refresh()
            else:
                messagebox.showinfo("Empty", "Queue is empty.", parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)

    def _tick(self):
        if self._closed:
            return
        self._refresh()
        self._job = self.dialog.after(self.POLL_MS, self._tick)

    def _on_close(self):
        self._closed = True
        if self._job is not None:
            try:
                self.dialog.after_cancel(self._job)
            except Exception:
                pass
        self.dialog.destroy()


class ReportsDialog:
    """Moderator panel for reviewing reported messages/users."""

    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Chat Reports")
        self.dialog.geometry("820x440")
        self.dialog.transient(parent)
        self._build()
        self._refresh()

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        head = ttk.Frame(frame)
        head.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(head, text="Status:").pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="open")
        ttk.Combobox(head, textvariable=self.status_var,
                     values=("open", "resolved", "all"),
                     state="readonly", width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(head, text="Refresh", command=self._refresh).pack(side=tk.LEFT)
        ttk.Button(head, text="Resolve…", command=self._resolve).pack(side=tk.LEFT, padx=5)
        ttk.Button(head, text="Open case file…",
                   command=self._open_case_file).pack(side=tk.LEFT, padx=5)
        cols = ("Created", "Status", "Reporter", "Target", "Room", "Case", "Reason", "Excerpt")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.column("Created", width=130)
        self.tree.column("Status", width=70, anchor=tk.CENTER)
        self.tree.column("Reporter", width=110)
        self.tree.column("Target", width=110)
        self.tree.column("Room", width=110)
        self.tree.column("Case", width=70, anchor=tk.CENTER)
        self.tree.column("Reason", width=140)
        self.tree.column("Excerpt", width=200)
        self.tree.pack(fill=tk.BOTH, expand=True)
        ttk.Button(frame, text="Close", command=self.dialog.destroy).pack(pady=(8, 0))

    def _refresh(self):
        for it in self.tree.get_children():
            self.tree.delete(it)
        try:
            reports = self.dashboard.list_chat_reports(status=self.status_var.get()) or []
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)
            return
        for r in reports:
            target = (f"@{r.get('target_user')}" if r.get('target_user')
                      else f"msg #{r.get('target_message_id')}" if r.get('target_message_id')
                      else "")
            sg = r.get('safeguarding_submission_id')
            tags = [str(r['id'])]
            if sg:
                tags.append(f"sg_{sg}")
            self.tree.insert(
                '', tk.END,
                values=(
                    (r.get('created_at') or '')[:16], r.get('status'),
                    f"@{r.get('reporter') or ''}", target,
                    r.get('room_name') or '',
                    f"#{sg}" if sg else "",
                    (r.get('reason') or '')[:60],
                    r.get('message_excerpt') or '',
                ),
                tags=tuple(tags),
            )

    def _selected_case_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        for tag in self.tree.item(sel[0]).get('tags') or ():
            if str(tag).startswith('sg_'):
                try:
                    return int(str(tag)[3:])
                except ValueError:
                    return None
        return None

    def _open_case_file(self):
        case_id = self._selected_case_id()
        if not case_id:
            messagebox.showinfo("Case file",
                                "Selected report has no linked safeguarding case.",
                                parent=self.dialog)
            return
        try:
            case = self.dashboard.get_safeguarding_submission(case_id)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)
            return
        if not case:
            messagebox.showerror("Case file",
                                 "Case not found, or you lack permission.",
                                 parent=self.dialog)
            return
        dlg = tk.Toplevel(self.dialog)
        dlg.title(f"Safeguarding case #{case['id']}")
        dlg.geometry("520x420")
        dlg.transient(self.dialog)
        f = ttk.Frame(dlg, padding=10)
        f.pack(fill=tk.BOTH, expand=True)
        meta = (
            f"Submitted: {case.get('submitted_at')}\n"
            f"Reporter: {case.get('full_name') or case.get('username')} "
            f"(@{case.get('username')})  ·  role: {case.get('role') or '—'}\n"
            f"Severity: {case.get('severity')}  ·  Status: {case.get('status')}\n"
            f"Categories: {case.get('categories')}\n"
        )
        ttk.Label(f, text=meta, justify=tk.LEFT).pack(anchor=tk.W)
        body = scrolledtext.ScrolledText(f, wrap=tk.WORD)
        body.pack(fill=tk.BOTH, expand=True, pady=(8, 8))
        body.insert("1.0", case.get('content') or '')
        if case.get('reviewer'):
            ttk.Label(f, foreground="#666",
                      text=f"Reviewed by @{case['reviewer']} at "
                           f"{case.get('reviewed_at') or ''}: "
                           f"{case.get('review_note') or ''}").pack(anchor=tk.W)
        body.config(state=tk.DISABLED)
        ttk.Button(f, text="Close", command=dlg.destroy).pack(pady=(8, 0))

    def _resolve(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a report first.", parent=self.dialog)
            return
        report_id = int(self.tree.item(sel[0])['tags'][0])
        note = askstring("Resolve report",
                         "Resolution notes (optional):",
                         parent=self.dialog) or ''
        try:
            ok = self.dashboard.resolve_chat_report(report_id, note)
            if ok:
                self._refresh()
            else:
                messagebox.showerror("Error", "Could not resolve (permission?).",
                                     parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)


class AuditLogDialog:
    """Read-only audit log viewer."""

    def __init__(self, parent, dashboard, room_id=None, room_name=None):
        self.dashboard = dashboard
        self.room_id = room_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Audit Log{' — ' + room_name if room_name else ''}")
        self.dialog.geometry("780x420")
        self.dialog.transient(parent)
        self._build()
        self._refresh()

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        head = ttk.Frame(frame)
        head.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(head, text="Action filter:").pack(side=tk.LEFT)
        self.action_var = tk.StringVar()
        ttk.Entry(head, textvariable=self.action_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(head, text="Apply", command=self._refresh).pack(side=tk.LEFT)
        cols = ("When", "User", "Action", "Details")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.column("When", width=140)
        self.tree.column("User", width=110)
        self.tree.column("Action", width=160)
        self.tree.column("Details", width=340)
        self.tree.pack(fill=tk.BOTH, expand=True)
        ttk.Button(frame, text="Close", command=self.dialog.destroy).pack(pady=(8, 0))

    def _refresh(self):
        for it in self.tree.get_children():
            self.tree.delete(it)
        try:
            entries = self.dashboard.get_communication_audit_log(
                room_id=self.room_id,
                action_type=(self.action_var.get().strip() or None),
            ) or []
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)
            return
        for e in entries:
            self.tree.insert('', tk.END, values=(
                (e.get('performed_at') or '')[:19],
                f"@{e.get('username') or ''}",
                e.get('action_type') or '',
                e.get('details') or '',
            ))


class BlocksDialog:
    """Manage the current user's DM block list."""

    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Blocked users")
        self.dialog.geometry("440x320")
        self.dialog.transient(parent)
        self._build()
        self._refresh()

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        cols = ("Username", "Name", "Blocked since")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.pack(fill=tk.BOTH, expand=True)
        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Block by username…",
                   command=self._block).pack(side=tk.LEFT)
        ttk.Button(btns, text="Unblock", command=self._unblock).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _refresh(self):
        for it in self.tree.get_children():
            self.tree.delete(it)
        try:
            rows = self.dashboard.list_blocked_users() or []
        except Exception:
            rows = []
        for r in rows:
            self.tree.insert(
                '', tk.END,
                values=(f"@{r['username']}", r['full_name'],
                        (r.get('created_at') or '')[:16]),
                tags=(str(r['user_id']),),
            )

    def _block(self):
        username = askstring("Block user", "Username to block:",
                             parent=self.dialog)
        if not username:
            return
        try:
            from education_system.university_system.infrastructure.email.admin import search_users as _su
            users = _su(self.dashboard.auth, username)
        except Exception:
            users = []
        if not users:
            messagebox.showerror("Error", f"No user found for '{username}'.",
                                 parent=self.dialog)
            return
        try:
            ok = self.dashboard.block_user(users[0]['id'])
            if ok:
                self._refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)

    def _unblock(self):
        sel = self.tree.selection()
        if not sel:
            return
        uid = int(self.tree.item(sel[0])['tags'][0])
        try:
            ok = self.dashboard.unblock_user(uid)
            if ok:
                self._refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)


class GDPRChatDialog:
    """Per-user export / erase tools (GDPR)."""

    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My chat data (export / erase)")
        self.dialog.geometry("480x220")
        self.dialog.transient(parent)
        frame = ttk.Frame(self.dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, justify=tk.LEFT, text=(
            "Export downloads a JSON copy of every chat message you've sent,\n"
            "your reactions, poll votes, and room memberships.\n\n"
            "Erase soft-deletes the contents of every chat message you've sent\n"
            "and removes your reactions, poll votes, typing/presence rows.\n"
            "This cannot be undone.")).pack(anchor=tk.W)
        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(btns, text="Export to JSON…",
                   command=self._export).pack(side=tk.LEFT)
        ttk.Button(btns, text="Erase my chat history",
                   command=self._erase).pack(side=tk.LEFT, padx=10)
        ttk.Button(btns, text="Close",
                   command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _export(self):
        try:
            data = self.dashboard.export_user_chat_history()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)
            return
        if not data:
            messagebox.showerror("Error", "Nothing to export (or not authorised).",
                                 parent=self.dialog)
            return
        path = filedialog.asksaveasfilename(
            parent=self.dialog, defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            initialfile=f"chat_export_user{data.get('user_id')}.json",
        )
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Exported", f"Saved to {path}", parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)

    def _erase(self):
        if not messagebox.askyesno(
            "Confirm erasure",
            "This will soft-delete the contents of every chat message you've sent.\n"
            "It cannot be undone. Continue?",
            parent=self.dialog,
        ):
            return
        try:
            ok = self.dashboard.erase_user_chat_history()
            if ok:
                messagebox.showinfo("Done", "Your chat history has been erased.",
                                    parent=self.dialog)
            else:
                messagebox.showerror("Error", "Could not erase.", parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)


class RoomSwitcherDialog:
    """Quick-find palette over the joined rooms. Type to filter, Enter to open."""

    def __init__(self, parent, dashboard, current_room_id=None):
        self.dashboard = dashboard
        self.parent = parent
        self.current_room_id = current_room_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Switch room")
        self.dialog.geometry("420x360")
        self.dialog.transient(parent)
        self.dialog.bind('<Escape>', lambda e: self.dialog.destroy())
        self._rooms = []
        self._build()
        self._reload()
        self.dialog.after(50, self.entry.focus_set)

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        self.query_var = tk.StringVar()
        self.entry = ttk.Entry(frame, textvariable=self.query_var)
        self.entry.pack(fill=tk.X)
        self.entry.bind('<Return>', lambda e: self._open_selected())
        self.entry.bind('<Down>', self._focus_list)
        self.query_var.trace_add('write', lambda *_: self._render())

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.listbox = tk.Listbox(list_frame, activestyle='dotbox')
        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                           command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.bind('<Return>', lambda e: self._open_selected())
        self.listbox.bind('<Double-1>', lambda e: self._open_selected())

    def _reload(self):
        try:
            data = self.dashboard.get_chat_rooms('joined') or {}
            self._rooms = data.get('rooms', []) or []
        except Exception:
            self._rooms = []
        self._render()

    def _render(self):
        needle = (self.query_var.get() or '').strip().lower()
        self.listbox.delete(0, tk.END)
        self._filtered = []
        for r in self._rooms:
            label_parts = []
            if r.get('icon'):
                label_parts.append(r['icon'])
            if r.get('is_favourite'):
                label_parts.append("★")
            label_parts.append(r['name'])
            if r.get('category'):
                label_parts.append(f"  · {r['category']}")
            label = " ".join(label_parts)
            if needle and needle not in label.lower() \
                    and needle not in (r.get('description') or '').lower():
                continue
            self._filtered.append(r)
            self.listbox.insert(tk.END, label)
        if self.listbox.size():
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(0)

    def _focus_list(self, _event=None):
        if self.listbox.size():
            self.listbox.focus_set()
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(0)
        return "break"

    def _open_selected(self):
        sel = self.listbox.curselection()
        idx = sel[0] if sel else 0
        if not getattr(self, '_filtered', None):
            return
        if idx >= len(self._filtered):
            return
        room = self._filtered[idx]
        if room['id'] == self.current_room_id:
            self.dialog.destroy()
            return
        self.dialog.destroy()
        ChatRoomWindow(self.parent, self.dashboard, room['id'], room['name'])


class UserProfileDialog:
    """Read-only snapshot of a user's profile (joined to staff_profiles +
    students). Opened on click of a sender name or @mention."""

    def __init__(self, parent, dashboard, user_id):
        self.dashboard = dashboard
        self.user_id = user_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("User profile")
        self.dialog.geometry("420x420")
        self.dialog.transient(parent)
        self._build()

    def _build(self):
        try:
            profile = self.dashboard.get_user_profile(self.user_id)
        except Exception as e:
            ttk.Label(self.dialog, text=f"Error: {e}", padding=20).pack()
            return
        if not profile:
            ttk.Label(self.dialog, text="User not found.",
                      padding=20).pack()
            ttk.Button(self.dialog, text="Close",
                       command=self.dialog.destroy).pack(pady=(0, 10))
            return
        frame = ttk.Frame(self.dialog, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=profile.get('full_name') or profile.get('username'),
                  font=("TkDefaultFont", 13, "bold")).pack(anchor=tk.W)
        ttk.Label(frame, foreground="#666",
                  text=f"@{profile.get('username') or ''}  ·  "
                       f"role: {profile.get('role') or '—'}"
                  ).pack(anchor=tk.W, pady=(0, 8))
        if profile.get('email'):
            ttk.Label(frame, text=f"Email: {profile['email']}").pack(anchor=tk.W)
        if profile.get('student_id'):
            ttk.Label(frame, text=f"Student ID: {profile['student_id']}"
                      ).pack(anchor=tk.W, pady=(2, 0))
        staff = profile.get('staff') or {}
        if staff:
            ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
            ttk.Label(frame, text="Staff profile",
                      font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W)
            for label, key in [
                ("Department", "department"), ("Job title", "job_title"),
                ("Employment", "employment_type"), ("Office", "office"),
                ("Phone ext.", "phone_ext"), ("Manager id", "manager_id"),
                ("Expertise", "expertise"),
            ]:
                v = staff.get(key)
                if v:
                    ttk.Label(frame, text=f"{label}: {v}").pack(anchor=tk.W)
            if staff.get('bio'):
                ttk.Label(frame, text="Bio:",
                          font=("TkDefaultFont", 9, "bold")
                          ).pack(anchor=tk.W, pady=(6, 0))
                bio = scrolledtext.ScrolledText(frame, height=4, wrap=tk.WORD)
                bio.insert("1.0", staff['bio'])
                bio.config(state=tk.DISABLED)
                bio.pack(fill=tk.X)
        ttk.Button(frame, text="Close",
                   command=self.dialog.destroy).pack(pady=(10, 0))


class RoomNotesDialog:
    """Shared room notes with idle auto-save + remote-refresh polling.

    - Auto-saves when the user has been idle for AUTOSAVE_IDLE_MS while there
      are unsaved changes.
    - Every POLL_MS, fetches the server-side version; if updated_at advanced
      and the local copy is clean, the new content is loaded.
    - Closing while dirty prompts to save.
    """

    POLL_MS = 5000
    AUTOSAVE_IDLE_MS = 1500

    def __init__(self, parent, dashboard, room_id, room_name):
        self.dashboard = dashboard
        self.room_id = room_id
        self.room_name = room_name
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Notes: {room_name}")
        self.dialog.geometry("700x520")
        self.dialog.transient(parent)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        self._dirty = False
        self._closed = False
        self._poll_job = None
        self._idle_job = None
        self._last_remote_updated_at = None
        self._last_remote_version = 0
        self._loading = False  # suppress dirty-flag while we're populating

        self._build()
        self._load_initial()
        self._poll_job = self.dialog.after(self.POLL_MS, self._poll)

    def _build(self):
        head = ttk.Frame(self.dialog)
        head.pack(fill=tk.X, padx=10, pady=(10, 0))
        self.meta_label = ttk.Label(head, foreground="#666", text="")
        self.meta_label.pack(side=tk.LEFT)
        self.status_label = ttk.Label(head, foreground="#2a8a2a", text="")
        self.status_label.pack(side=tk.RIGHT)

        # Conflict banner: hidden until a remote save lands while we're dirty.
        self.conflict_frame = ttk.Frame(self.dialog)
        self.conflict_label = ttk.Label(
            self.conflict_frame, anchor=tk.W,
            background="#ffe4e1", foreground="#7a0000",
            font=("TkDefaultFont", 9, "bold"),
            text=" ⚠ Someone else saved while you were editing. "
                 "Choose how to resolve.",
        )
        self.conflict_label.pack(side=tk.LEFT, fill=tk.X, expand=True,
                                 ipady=4)
        ttk.Button(self.conflict_frame, text="Diff & merge…",
                   command=self._resolve_diff_merge
                   ).pack(side=tk.LEFT, padx=4)
        ttk.Button(self.conflict_frame, text="Reload remote (discard mine)",
                   command=self._resolve_reload_remote
                   ).pack(side=tk.LEFT, padx=4)
        ttk.Button(self.conflict_frame, text="Keep mine (overwrite)",
                   command=self._resolve_keep_mine
                   ).pack(side=tk.LEFT, padx=4)

        self.text = scrolledtext.ScrolledText(self.dialog, wrap=tk.WORD)
        self.text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.text.bind('<KeyRelease>', self._on_key_release)

        btns = ttk.Frame(self.dialog)
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.save_button = ttk.Button(btns, text="Save now",
                                      command=self._save_now)
        self.save_button.pack(side=tk.RIGHT)
        ttk.Button(btns, text="Close",
                   command=self._on_close).pack(side=tk.RIGHT, padx=5)

        self._conflict_active = False
        self._pending_remote_data = None

    def _load_initial(self):
        try:
            data = self.dashboard.get_room_notes(self.room_id) or {}
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.dialog)
            data = {}
        self._apply_remote(data, keep_cursor=False)

    def _apply_remote(self, data, keep_cursor=True):
        self._loading = True
        try:
            cursor_idx = self.text.index(tk.INSERT) if keep_cursor else "1.0"
            self.text.delete("1.0", tk.END)
            if data.get('content'):
                self.text.insert("1.0", data['content'])
            try:
                self.text.mark_set(tk.INSERT, cursor_idx)
            except Exception:
                pass
            self._last_remote_updated_at = data.get('updated_at')
            self._last_remote_version = int(data.get('version') or 0)
            self._update_meta(data)
            self._dirty = False
            self._set_status("Up to date", "#666")
        finally:
            self._loading = False

    def _update_meta(self, data):
        ts = (data.get('updated_at') or '')[:16]
        who = data.get('updated_by_username')
        if ts:
            self.meta_label.config(
                text=f"Last updated: {ts}  by @{who or '—'}"
            )
        else:
            self.meta_label.config(text="No saved version yet")

    def _set_status(self, text, colour="#666"):
        self.status_label.config(text=text, foreground=colour)

    def _on_key_release(self, _event=None):
        if self._loading:
            return
        if not self._dirty:
            self._dirty = True
            self._set_status("Editing…", "#888")
        # Reset idle timer
        if self._idle_job is not None:
            try:
                self.dialog.after_cancel(self._idle_job)
            except Exception:
                pass
        self._idle_job = self.dialog.after(self.AUTOSAVE_IDLE_MS, self._idle_save)

    def _idle_save(self):
        self._idle_job = None
        if self._closed or not self._dirty:
            return
        self._save_now()

    def _save_now(self):
        if self._closed:
            return
        content = self.text.get("1.0", tk.END).rstrip()
        try:
            ok = self.dashboard.set_room_notes(
                self.room_id, content,
                expected_version=self._last_remote_version or None,
            )
        except Exception as e:
            self._set_status(f"Save failed: {e}", "#b30000")
            return
        if ok == 'version_conflict':
            # Someone else saved while we were editing — lock the editor
            # and require an explicit resolution choice.
            try:
                data = self.dashboard.get_room_notes(self.room_id) or {}
            except Exception:
                data = {}
            self._enter_conflict(data)
            return
        if not ok:
            self._set_status("Save failed (permission?)", "#b30000")
            return
        self._dirty = False
        self._set_status("Saved", "#2a8a2a")
        # Refresh meta so we know the new updated_at + version server-side.
        try:
            data = self.dashboard.get_room_notes(self.room_id) or {}
            self._last_remote_updated_at = data.get('updated_at')
            self._last_remote_version = int(data.get('version') or 0)
            self._update_meta(data)
        except Exception:
            pass

    def _poll(self):
        if self._closed:
            return
        if self._conflict_active:
            # Don't poll while waiting for the user to resolve a conflict.
            self._poll_job = self.dialog.after(self.POLL_MS, self._poll)
            return
        try:
            data = self.dashboard.get_room_notes(self.room_id) or {}
        except Exception:
            data = {}
        remote_v = int(data.get('version') or 0)
        remote_ts = data.get('updated_at')
        moved = (remote_ts and remote_ts != self._last_remote_updated_at) or (
            remote_v and remote_v != self._last_remote_version
        )
        if moved:
            if self._dirty:
                self._enter_conflict(data)
            else:
                self._apply_remote(data, keep_cursor=True)
                self._set_status("Refreshed", "#1a5fb4")
        self._poll_job = self.dialog.after(self.POLL_MS, self._poll)

    def _enter_conflict(self, remote_data):
        """Lock the editor and demand explicit user resolution."""
        self._conflict_active = True
        self._pending_remote_data = remote_data
        # Lock the editor and disable Save until resolution.
        try:
            self.text.config(state=tk.DISABLED)
        except Exception:
            pass
        try:
            self.save_button.config(state=tk.DISABLED)
        except Exception:
            pass
        # Show the conflict bar above the editor.
        self.conflict_frame.pack(fill=tk.X, padx=10, pady=(0, 4),
                                 before=self.text)
        ts = (remote_data.get('updated_at') or '')[:16]
        who = remote_data.get('updated_by_username') or '—'
        self._set_status(
            f"Conflict — locked. Remote @{who} saved {ts}.", "#b30000",
        )

    def _exit_conflict(self):
        self._conflict_active = False
        self._pending_remote_data = None
        try:
            self.text.config(state=tk.NORMAL)
        except Exception:
            pass
        try:
            self.save_button.config(state=tk.NORMAL)
        except Exception:
            pass
        self.conflict_frame.pack_forget()

    def _resolve_diff_merge(self):
        """Open a side-by-side diff so the user can hand-merge before saving."""
        remote = (self._pending_remote_data or {}).get('content', '') or ''
        mine = self.text.get("1.0", tk.END).rstrip("\n")

        def on_save(merged):
            # Force-save (no expected_version) so we don't bounce back here.
            try:
                ok = self.dashboard.set_room_notes(
                    self.room_id, merged, expected_version=None,
                )
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self.dialog)
                return False
            if not ok or ok == 'version_conflict':
                messagebox.showerror(
                    "Save failed",
                    "The save was rejected. The room may have changed again.",
                    parent=self.dialog,
                )
                return False
            # Reflect the merged content locally and exit the conflict.
            self._loading = True
            try:
                self.text.config(state=tk.NORMAL)
                self.text.delete("1.0", tk.END)
                self.text.insert("1.0", merged)
            finally:
                self._loading = False
            self._exit_conflict()
            self._dirty = False
            self._set_status("Merged and saved.", "#2a8a2a")
            try:
                data = self.dashboard.get_room_notes(self.room_id) or {}
                self._last_remote_updated_at = data.get('updated_at')
                self._last_remote_version = int(data.get('version') or 0)
                self._update_meta(data)
            except Exception:
                pass
            return True

        NotesDiffDialog(self.dialog, mine_content=mine,
                        remote_content=remote, on_save=on_save)

    def _resolve_reload_remote(self):
        """Discard local edits and load the remote version."""
        data = self._pending_remote_data or {}
        self._exit_conflict()
        if data:
            self._apply_remote(data, keep_cursor=False)
        self._set_status("Reloaded remote version.", "#1a5fb4")

    def _resolve_keep_mine(self):
        """Force-save local edits as the next version (no expected_version)."""
        self._exit_conflict()
        if self._closed:
            return
        content = self.text.get("1.0", tk.END).rstrip()
        try:
            ok = self.dashboard.set_room_notes(
                self.room_id, content, expected_version=None,
            )
        except Exception as e:
            self._set_status(f"Save failed: {e}", "#b30000")
            return
        if not ok or ok == 'version_conflict':
            self._set_status("Save still rejected.", "#b30000")
            return
        self._dirty = False
        self._set_status("Saved (overwrote remote).", "#2a8a2a")
        try:
            data = self.dashboard.get_room_notes(self.room_id) or {}
            self._last_remote_updated_at = data.get('updated_at')
            self._last_remote_version = int(data.get('version') or 0)
            self._update_meta(data)
        except Exception:
            pass

    def _on_close(self):
        if self._dirty:
            choice = messagebox.askyesnocancel(
                "Unsaved changes",
                "Save your changes before closing?",
                parent=self.dialog,
            )
            if choice is None:
                return
            if choice:
                self._save_now()
                if self._dirty:  # save failed
                    return
        self._closed = True
        for job in (self._poll_job, self._idle_job):
            if job is not None:
                try:
                    self.dialog.after_cancel(job)
                except Exception:
                    pass
        self._poll_job = None
        self._idle_job = None
        self.dialog.destroy()


class NotesDiffDialog:
    """Side-by-side merge view for resolving a notes conflict.

    Left pane is editable ("Mine"); right pane is read-only ("Remote").
    Lines are tagged using difflib so additions/removals/changes stand out.
    The user edits the left pane to produce the merged version, then Save."""

    def __init__(self, parent, mine_content, remote_content, on_save):
        self.on_save = on_save
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Merge notes — diff")
        self.dialog.geometry("1100x620")
        self.dialog.transient(parent)
        self.dialog.after(100,
                          lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        self._build()
        self._populate(mine_content or '', remote_content or '')

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=8)
        frame.pack(fill=tk.BOTH, expand=True)
        head = ttk.Frame(frame)
        head.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(head, text=" Edit the left pane to produce the merged version. "
                              "Click a remote line to copy it across.",
                  foreground="#444").pack(side=tk.LEFT)

        paned = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=1)

        ttk.Label(left, text="Mine (editable)",
                  font=("TkDefaultFont", 10, "bold"),
                  foreground="#1a5fb4").pack(anchor=tk.W)
        self.mine = scrolledtext.ScrolledText(left, wrap=tk.WORD)
        self.mine.pack(fill=tk.BOTH, expand=True)

        ttk.Label(right, text="Remote (read-only)",
                  font=("TkDefaultFont", 10, "bold"),
                  foreground="#7a4f00").pack(anchor=tk.W)
        self.remote = scrolledtext.ScrolledText(right, wrap=tk.WORD,
                                                 state=tk.DISABLED)
        self.remote.pack(fill=tk.BOTH, expand=True)

        # Diff colours
        for w in (self.mine, self.remote):
            w.tag_configure("diff_add",   background="#e0f5e0")
            w.tag_configure("diff_remove", background="#fbe0e0")
            w.tag_configure("diff_change", background="#fff4d6")

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Save merged",
                   command=self._on_save).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy
                   ).pack(side=tk.RIGHT, padx=5)

    def _populate(self, mine_text, remote_text):
        import difflib
        mine_lines = mine_text.splitlines() or ['']
        remote_lines = remote_text.splitlines() or ['']
        self.mine.delete("1.0", tk.END)
        # Populate left first; remote populated under DISABLED state.
        self.remote.config(state=tk.NORMAL)
        self.remote.delete("1.0", tk.END)

        sm = difflib.SequenceMatcher(a=mine_lines, b=remote_lines, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                for line in mine_lines[i1:i2]:
                    self.mine.insert(tk.END, line + "\n")
                for line in remote_lines[j1:j2]:
                    self.remote.insert(tk.END, line + "\n")
            elif tag == 'replace':
                for line in mine_lines[i1:i2]:
                    self.mine.insert(tk.END, line + "\n", ("diff_change",))
                for line in remote_lines[j1:j2]:
                    self._insert_remote_line(line, "diff_change")
            elif tag == 'delete':
                # Lines only in mine: highlight on left, blank on right.
                for line in mine_lines[i1:i2]:
                    self.mine.insert(tk.END, line + "\n", ("diff_remove",))
                for _ in range(i2 - i1):
                    self._insert_remote_line("", "diff_remove")
            elif tag == 'insert':
                # Lines only in remote: highlight on right, blank on left.
                for _ in range(j2 - j1):
                    self.mine.insert(tk.END, "\n", ("diff_add",))
                for line in remote_lines[j1:j2]:
                    self._insert_remote_line(line, "diff_add")

        self.remote.config(state=tk.DISABLED)
        self.remote.bind("<Button-1>", self._copy_remote_line)

    def _insert_remote_line(self, line, tag):
        # Tag each line so click-handlers can grab the exact range.
        start = self.remote.index("end-1c")
        self.remote.insert(tk.END, line + "\n", (tag,))
        end = self.remote.index("end-1c")
        # Per-line tag for click resolution
        line_tag = f"r_line_{start.split('.')[0]}"
        self.remote.tag_add(line_tag, start, end)

    def _copy_remote_line(self, event):
        """Click a remote line to insert it at the cursor in the left pane."""
        idx = self.remote.index(f"@{event.x},{event.y}")
        line_no = idx.split('.')[0]
        line_start = f"{line_no}.0"
        line_end = f"{int(line_no) + 1}.0"
        try:
            line = self.remote.get(line_start, line_end)
        except Exception:
            return
        if not line.strip():
            return
        # Insert at the current insertion point in the left pane.
        self.mine.focus_set()
        self.mine.insert(tk.INSERT, line)

    def _on_save(self):
        merged = self.mine.get("1.0", tk.END).rstrip()
        if self.on_save and self.on_save(merged):
            self.dialog.destroy()
