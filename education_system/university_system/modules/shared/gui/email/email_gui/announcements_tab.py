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

# Configure logging
logger = logging.getLogger(__name__)

# Import internationalisation (i18n) for multi‑language support
try:
    from education_system.university_system.core.i18n import (
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

from education_system.university_system.modules.shared.gui.email.email_gui.email_manager_main import EmailManagerGUI
from education_system.university_system.modules.shared.gui.email.email_gui.chat_dialogs import (
    CreateAnnouncementDialog,
    AnnouncementDetailsDialog,
    EditAnnouncementDialog,
)

def create_announcements_tab(self):
    """Create the announcements tab"""
    tab_frame = ttk.Frame(self.notebook)
    self.notebook.add(tab_frame, text=_t("email.tabs.announcements", default="Announcements"))

    # Announcements toolbar
    toolbar_frame = ttk.Frame(tab_frame)
    toolbar_frame.pack(fill=tk.X, padx=10, pady=10)

    if self.auth.current_user['role'] in ['admin', 'staff', 'instructor']:
        ttk.Button(toolbar_frame, text=_t("email.announcements.create", default="Create Announcement"), command=self.create_announcement_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text=_t("email.announcements.edit", default="Edit Announcement"), command=self.edit_announcement).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text=_t("email.announcements.delete", default="Delete Announcement"), command=self.delete_announcement).pack(side=tk.LEFT, padx=5)

    ttk.Button(toolbar_frame, text=_t("common.refresh", default="Refresh"), command=self.refresh_announcements).pack(side=tk.RIGHT, padx=5)

    # Create announcements list FIRST
    self.create_announcements_list(tab_frame)

# Bind method to EmailManagerGUI
EmailManagerGUI.create_announcements_tab = create_announcements_tab

def create_announcements_list(self, parent):
    """Create announcements list"""
    list_frame = ttk.LabelFrame(parent, text=_t("email.announcements.active", default="Active Announcements"), padding=10)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ("Title", "Creator", "Date", "Audience", "Urgent")
    column_headers = (
        _t("table_headers.title", default="Title"),
        _t("email.announcements.col_creator", default="Creator"),
        _t("common.date", default="Date"),
        _t("email.announcements.col_audience", default="Audience"),
        _t("email.announcements.col_urgent", default="Urgent")
    )
    self.announcements_tree = ttk.Treeview(list_frame, columns=columns, show="headings")

    for col, header in zip(columns, column_headers):
        self.announcements_tree.heading(col, text=header)
        if col == "Title":
            self.announcements_tree.column(col, width=300)
        else:
            self.announcements_tree.column(col, width=150)

    scrollbar2 = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.announcements_tree.yview)
    self.announcements_tree.configure(yscrollcommand=scrollbar2.set)

    self.announcements_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar2.pack(side=tk.RIGHT, fill=tk.Y)

    # Bind the event handler AFTER the tree is created
    self.announcements_tree.bind("<Double-1>", self.view_announcement_details)

# Bind method to EmailManagerGUI
EmailManagerGUI.create_announcements_list = create_announcements_list

def create_announcement_dialog(self):
    """Open create announcement dialog"""
    CreateAnnouncementDialog(self.root, self.dashboard)

# Bind method to EmailManagerGUI
EmailManagerGUI.create_announcement_dialog = create_announcement_dialog

def edit_announcement(self):
    """Edit selected announcement"""
    selection = self.announcements_tree.selection()
    if not selection:
        messagebox.showwarning(_t("common.warning", default="Warning"), _t("email.announcements.select_to_edit", default="Please select an announcement to edit"))
        return

    item = self.announcements_tree.item(selection[0])
    announcement_id = item['tags'][0] if item['tags'] else None

    if not announcement_id:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.announcements.id_not_found", default="Could not determine announcement ID"))
        return

    # Open edit dialog
    EditAnnouncementDialog(self.root, self.dashboard, announcement_id, self.refresh_announcements)

# Bind method to EmailManagerGUI
EmailManagerGUI.edit_announcement = edit_announcement

def delete_announcement(self):
    """Delete selected announcement"""
    selection = self.announcements_tree.selection()
    if not selection:
        messagebox.showwarning(_t("common.warning", default="Warning"), _t("email.announcements.select_to_delete", default="Please select an announcement to delete"))
        return

    item = self.announcements_tree.item(selection[0])
    announcement_id = item['tags'][0] if item['tags'] else None
    announcement_title = item['values'][0] if item['values'] else _t("email.announcements.this_announcement", default="this announcement")

    if not announcement_id:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.announcements.id_not_found", default="Could not determine announcement ID"))
        return

    # Confirm deletion
    if not messagebox.askyesno(_t("email.announcements.confirm_delete_title", default="Confirm Delete"), _t("email.announcements.confirm_delete_msg", default="Are you sure you want to delete '{title}'?").format(title=announcement_title)):
        return

    try:
        from education_system.university_system.infrastructure.database.db import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete the announcement
        cursor.execute('DELETE FROM announcements WHERE id = ?', (announcement_id,))
        conn.commit()
        conn.close()

        messagebox.showinfo(_t("common.success", default="Success"), _t("email.announcements.delete_success", default="Announcement deleted successfully!"))
        self.refresh_announcements()

    except Exception as e:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.announcements.delete_failed", default="Failed to delete announcement: {error}").format(error=e))

# Bind method to EmailManagerGUI
EmailManagerGUI.delete_announcement = delete_announcement

def refresh_announcements(self):
    """Refresh the announcements list"""
    try:
        # Clear existing items
        for item in self.announcements_tree.get_children():
            self.announcements_tree.delete(item)

        if self.dashboard:
            announcements = self.dashboard.get_announcements()

            for announcement in announcements.get('announcements', []):
                urgent_text = "YES" if announcement.get('is_urgent') else "NO"
                self.announcements_tree.insert('', tk.END, values=(
                    announcement['title'],
                    announcement['creator'],
                    announcement['created_at'],
                    announcement['target_audience'],
                    urgent_text
                ), tags=(announcement['id'],))

        self.update_status("Announcements refreshed")

    except Exception as e:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.announcements.refresh_failed", default="Failed to refresh announcements: {error}").format(error=e))

# Bind method to EmailManagerGUI
EmailManagerGUI.refresh_announcements = refresh_announcements

def create_announcement(self):
    """Open create announcement dialog"""
    CreateAnnouncementDialog(self.root, self.dashboard)

# Bind method to EmailManagerGUI
EmailManagerGUI.create_announcement = create_announcement

def view_announcement_details(self, event):
    """View announcement details"""
    selection = self.announcements_tree.selection()
    if selection:
        item = self.announcements_tree.item(selection[0])
        announcement_id = item['tags'][0]
        AnnouncementDetailsDialog(self.root, self.dashboard, announcement_id)

# Bind method to EmailManagerGUI
EmailManagerGUI.view_announcement_details = view_announcement_details

def open_announcements(self):
    """Switch to announcements tab"""
    self.notebook.select(4)  # Announcements tab index (Dashboard=0, Email=1, Messages=2, SMS=3, Announcements=4)
    self.refresh_announcements()

# Bind method to EmailManagerGUI
EmailManagerGUI.open_announcements = open_announcements

def get_announcement_by_id(dashboard, announcement_id):
    """Get announcement by ID"""
    try:
        if hasattr(dashboard, 'get_announcement'):
            return dashboard.get_announcement(announcement_id)
        else:
            # Mock announcement data
            return {
                'id': announcement_id,
                'title': 'Sample Announcement',
                'creator': 'System Admin',
                'target_audience': 'all',
                'created_at': '2024-01-01 12:00:00',
                'is_urgent': False,
                'is_active': True,
                'content': 'This is a sample announcement.'
            }
    except Exception as e:
        print(f"Error getting announcement: {e}")
        return None

# Bind method to EmailManagerGUI
EmailManagerGUI.get_announcement_by_id = get_announcement_by_id

def mark_announcement_viewed(dashboard, announcement_id):
    """Mark announcement as viewed"""
    try:
        if hasattr(dashboard, 'mark_announcement_viewed'):
            return dashboard.mark_announcement_viewed(announcement_id)
        else:
            print(f"Mock: Marking announcement {announcement_id} as viewed")
            return True
    except Exception as e:
        print(f"Error marking announcement as viewed: {e}")
        return False

# Bind method to EmailManagerGUI
EmailManagerGUI.mark_announcement_viewed = mark_announcement_viewed

