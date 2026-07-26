import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
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
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.domain.pastoral.student_life.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class ClubDiscussionsDialog:
    """Dialog for managing club discussions"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Club Discussions")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Club Discussions", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Club selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(select_frame, text="Select Club:").pack(side='left', padx=(0, 10))
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(select_frame, textvariable=self.club_var, width=40)
        self.club_combo.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.club_combo.bind('<<ComboboxSelected>>', self.on_club_selected)

        ttk.Button(select_frame, text="New Discussion", command=self.new_discussion).pack(side='right')

        # Discussions list
        list_frame = ttk.LabelFrame(main_frame, text="Discussion Topics")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Title', 'Author', 'Date', 'Type', 'Pinned')
        self.discussions_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            self.discussions_tree.heading(col, text=col)
            if col == 'Title':
                self.discussions_tree.column(col, width=300)
            else:
                self.discussions_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.discussions_tree.yview)
        self.discussions_tree.configure(yscrollcommand=scrollbar.set)

        self.discussions_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.discussions_tree.bind('<Double-1>', self.view_discussion)

        # Content preview
        preview_frame = ttk.LabelFrame(main_frame, text="Preview")
        preview_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.preview_text = scrolledtext.ScrolledText(preview_frame, height=8, wrap=tk.WORD)
        self.preview_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="View Full Discussion", command=self.view_discussion).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_discussion).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load clubs"""
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return

            student_id = result[0]

            cursor.execute('''
            SELECT DISTINCT sc.club_id, sc.club_name
            FROM student_clubs sc
            INNER JOIN club_members cm ON sc.club_id = cm.club_id
            WHERE cm.student_id = ? AND sc.status = 'active'
            ORDER BY sc.club_name
            ''', (student_id,))

            clubs = cursor.fetchall()
            self.club_data = {f"{club[1]} (ID: {club[0]})": club[0] for club in clubs}
            self.club_combo['values'] = list(self.club_data.keys())

            conn.close()

            if clubs:
                self.club_combo.current(0)
                self.on_club_selected(None)
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load clubs: {str(e)}")

    def on_club_selected(self, event):
        """Load discussions when club is selected"""
        for item in self.discussions_tree.get_children():
            self.discussions_tree.delete(item)

        selected = self.club_var.get()
        if not selected or selected not in self.club_data:
            return

        club_id = self.club_data[selected]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT cd.discussion_id, cd.title, s.first_name || ' ' || s.last_name,
                   cd.post_date,
                   CASE WHEN cd.is_announcement = 1 THEN 'Announcement' ELSE 'Discussion' END,
                   CASE WHEN cd.pinned = 1 THEN 'Yes' ELSE 'No' END,
                   cd.content
            FROM club_discussions cd
            INNER JOIN students s ON cd.author_id = s.student_id
            WHERE cd.club_id = ?
            ORDER BY cd.pinned DESC, cd.post_date DESC
            ''', (club_id,))

            discussions = cursor.fetchall()

            for disc in discussions:
                self.discussions_tree.insert('', 'end', values=disc[:6], tags=(disc[6],))

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load discussions: {str(e)}")

    def new_discussion(self):
        """Create new discussion"""
        selected = self.club_var.get()
        if not selected or selected not in self.club_data:
            messagebox.showwarning("Warning", "Please select a club first.")
            return

        club_id = self.club_data[selected]

        # Create dialog for new discussion
        dialog = tk.Toplevel(self.dialog)
        dialog.title("New Discussion")
        dialog.geometry("600x500")
        dialog.transient(self.dialog)
        dialog.grab_set()

        frame = ttk.Frame(dialog)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Title:").pack(anchor='w')
        title_entry = ttk.Entry(frame, width=70)
        title_entry.pack(fill='x', pady=(0, 10))

        ttk.Label(frame, text="Content:").pack(anchor='w')
        content_text = scrolledtext.ScrolledText(frame, height=15, wrap=tk.WORD)
        content_text.pack(fill='both', expand=True, pady=(0, 10))

        is_announcement_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Mark as Announcement", variable=is_announcement_var).pack(anchor='w', pady=(0, 5))

        is_pinned_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Pin to Top", variable=is_pinned_var).pack(anchor='w', pady=(0, 10))

        def save_discussion():
            title = title_entry.get().strip()
            content = content_text.get(1.0, tk.END).strip()

            if not title or not content:
                messagebox.showwarning("Warning", "Please provide both title and content.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
                student_id = cursor.fetchone()[0]

                cursor.execute('''
                INSERT INTO club_discussions (club_id, author_id, title, content, post_date,
                                             last_updated, is_announcement, pinned)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (club_id, student_id, title, content, datetime.now().isoformat(),
                     datetime.now().isoformat(), is_announcement_var.get(), is_pinned_var.get()))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Discussion created successfully!")
                dialog.destroy()
                self.on_club_selected(None)
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to create discussion: {str(e)}")

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Post", command=save_discussion).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left')

    def view_discussion(self, event=None):
        """View full discussion"""
        selection = self.discussions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a discussion to view.")
            return

        item = self.discussions_tree.item(selection[0])
        content = item['tags'][0] if item['tags'] else "No content available."

        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(1.0, content)

    def delete_discussion(self):
        """Delete selected discussion"""
        selection = self.discussions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a discussion to delete.")
            return

        item = self.discussions_tree.item(selection[0])
        discussion_id = item['values'][0]

        if messagebox.askyesno("Confirm", "Are you sure you want to delete this discussion?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('DELETE FROM club_discussions WHERE discussion_id = ?', (discussion_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Discussion deleted successfully!")
                self.on_club_selected(None)
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to delete discussion: {str(e)}")



class ClubMediaDialog:
    """Dialog for managing club media"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Club Media Gallery")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Club Media Gallery", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Club selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(select_frame, text="Select Club:").pack(side='left', padx=(0, 10))
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(select_frame, textvariable=self.club_var, width=40)
        self.club_combo.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.club_combo.bind('<<ComboboxSelected>>', self.on_club_selected)

        ttk.Button(select_frame, text="Upload Media", command=self.upload_media).pack(side='right')

        # Media list
        list_frame = ttk.LabelFrame(main_frame, text="Media Files")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'File Name', 'Type', 'Uploader', 'Upload Date', 'Event', 'Caption')
        self.media_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.media_tree.heading(col, text=col)
            if col in ('File Name', 'Caption'):
                self.media_tree.column(col, width=200)
            else:
                self.media_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.media_tree.yview)
        self.media_tree.configure(yscrollcommand=scrollbar.set)

        self.media_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="View/Download", command=self.view_media).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_media).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load clubs"""
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return

            student_id = result[0]

            cursor.execute('''
            SELECT DISTINCT sc.club_id, sc.club_name
            FROM student_clubs sc
            INNER JOIN club_members cm ON sc.club_id = cm.club_id
            WHERE cm.student_id = ? AND sc.status = 'active'
            ORDER BY sc.club_name
            ''', (student_id,))

            clubs = cursor.fetchall()
            self.club_data = {f"{club[1]} (ID: {club[0]})": club[0] for club in clubs}
            self.club_combo['values'] = list(self.club_data.keys())

            conn.close()

            if clubs:
                self.club_combo.current(0)
                self.on_club_selected(None)
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load clubs: {str(e)}")

    def on_club_selected(self, event):
        """Load media when club is selected"""
        for item in self.media_tree.get_children():
            self.media_tree.delete(item)

        selected = self.club_var.get()
        if not selected or selected not in self.club_data:
            return

        club_id = self.club_data[selected]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT cm.media_id, cm.file_path, cm.file_type,
                   s.first_name || ' ' || s.last_name, cm.upload_date,
                   COALESCE(ue.event_name, 'N/A'), COALESCE(cm.caption, '')
            FROM club_media cm
            INNER JOIN students s ON cm.uploader_id = s.student_id
            LEFT JOIN union_events ue ON cm.event_id = ue.event_id
            WHERE cm.club_id = ?
            ORDER BY cm.upload_date DESC
            ''', (club_id,))

            media = cursor.fetchall()

            for item in media:
                # Extract filename from path
                filename = item[1].split('/')[-1] if item[1] else 'Unknown'
                display_values = (item[0], filename, item[2], item[3], item[4], item[5], item[6])
                self.media_tree.insert('', 'end', values=display_values)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load media: {str(e)}")

    def upload_media(self):
        """Upload new media"""
        selected = self.club_var.get()
        if not selected or selected not in self.club_data:
            messagebox.showwarning("Warning", "Please select a club first.")
            return

        # Would open file dialog to select media file
        messagebox.showinfo("Upload Media", "This would open a file browser to select photos, videos, or documents to upload.\n\nSupported formats:\n- Images: JPG, PNG, GIF\n- Videos: MP4, AVI\n- Documents: PDF, DOC, DOCX")

    def view_media(self):
        """View or download media"""
        selection = self.media_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select media to view.")
            return

        messagebox.showinfo("View Media", "This would open the selected media file in the appropriate application or allow downloading it.")

    def delete_media(self):
        """Delete selected media"""
        selection = self.media_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select media to delete.")
            return

        item = self.media_tree.item(selection[0])
        media_id = item['values'][0]

        if messagebox.askyesno("Confirm", "Are you sure you want to delete this media file?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('DELETE FROM club_media WHERE media_id = ?', (media_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Media deleted successfully!")
                self.on_club_selected(None)
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to delete media: {str(e)}")



def manage_club_discussions(self):
    """Manage club discussions"""
    try:
        dialog = ClubDiscussionsDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def manage_club_media(self):
    """Manage club media"""
    try:
        dialog = ClubMediaDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


