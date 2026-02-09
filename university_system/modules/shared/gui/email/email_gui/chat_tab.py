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
    from university_system.modules.shared.utils.i18n import (
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

from .email_manager_main import EmailManagerGUI
from .chat_dialogs import CreateChatRoomDialog, ChatInvitationsDialog, ChatRoomWindow

def create_chat_tab(self):
    """Create the chat rooms tab"""
    tab_frame = ttk.Frame(self.notebook)
    self.notebook.add(tab_frame, text=_t("email.tabs.chat_rooms", default="Chat Rooms"))

    # Chat toolbar
    toolbar_frame = ttk.Frame(tab_frame)
    toolbar_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(toolbar_frame, text=_t("email.create_room", default="Create Room"), command=self.create_chat_room).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("email.join_room", default="Join Room"), command=self.join_chat_room).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("email.invitations", default="Invitations"), command=self.view_invitations).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("common.refresh", default="Refresh"), command=self.refresh_chat_rooms).pack(side=tk.RIGHT, padx=5)

    # Chat rooms notebook
    self.chat_notebook = ttk.Notebook(tab_frame)
    self.chat_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # My rooms tab
    self.create_my_rooms_tab()

    # Public rooms tab
    self.create_public_rooms_tab()

# Bind method to EmailManagerGUI
EmailManagerGUI.create_chat_tab = create_chat_tab

def create_my_rooms_tab(self):
    """Create my chat rooms tab"""
    tab_frame = ttk.Frame(self.chat_notebook)
    self.chat_notebook.add(tab_frame, text=_t("email.my_rooms", default="My Rooms"))

    columns = ("Name", "Type", "Members", "Messages", "Role")
    self.my_rooms_tree = ttk.Treeview(tab_frame, columns=columns, show="headings")

    for col in columns:
        self.my_rooms_tree.heading(col, text=col)

    scrollbar3 = ttk.Scrollbar(tab_frame, orient=tk.VERTICAL, command=self.my_rooms_tree.yview)
    self.my_rooms_tree.configure(yscrollcommand=scrollbar3.set)

    self.my_rooms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar3.pack(side=tk.RIGHT, fill=tk.Y)

    self.my_rooms_tree.bind("<Double-1>", self.enter_chat_room)

# Bind method to EmailManagerGUI
EmailManagerGUI.create_my_rooms_tab = create_my_rooms_tab

def create_public_rooms_tab(self):
    """Create public rooms tab"""
    tab_frame = ttk.Frame(self.chat_notebook)
    self.chat_notebook.add(tab_frame, text=_t("email.public_rooms", default="Public Rooms"))

    columns = ("Name", "Description", "Members", "Creator")
    self.public_rooms_tree = ttk.Treeview(tab_frame, columns=columns, show="headings")

    for col in columns:
        self.public_rooms_tree.heading(col, text=col)

    scrollbar4 = ttk.Scrollbar(tab_frame, orient=tk.VERTICAL, command=self.public_rooms_tree.yview)
    self.public_rooms_tree.configure(yscrollcommand=scrollbar4.set)

    self.public_rooms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar4.pack(side=tk.RIGHT, fill=tk.Y)

# Bind method to EmailManagerGUI
EmailManagerGUI.create_public_rooms_tab = create_public_rooms_tab

def refresh_chat_rooms(self):
    """Refresh the chat rooms lists"""
    try:
        if not self.dashboard:
            return

        # Refresh my rooms
        for item in self.my_rooms_tree.get_children():
            self.my_rooms_tree.delete(item)

        my_rooms = self.dashboard.get_chat_rooms('joined')
        for room in my_rooms.get('rooms', []):
            role = "Admin" if room['is_admin'] else "Member"
            self.my_rooms_tree.insert('', tk.END, values=(
                room['name'],
                room['room_type'],
                room['member_count'],
                room['message_count'],
                role
            ), tags=(room['id'],))

        # Refresh public rooms
        for item in self.public_rooms_tree.get_children():
            self.public_rooms_tree.delete(item)

        public_rooms = self.dashboard.get_chat_rooms('public')
        for room in public_rooms.get('rooms', []):
            desc = room['description'][:30] + '...' if room['description'] and len(room['description']) > 30 else (room['description'] or '')
            self.public_rooms_tree.insert('', tk.END, values=(
                room['name'],
                desc,
                room['member_count'],
                room['creator']
            ), tags=(room['id'],))

        self.update_status("Chat rooms refreshed")

    except Exception as e:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.chat.refresh_failed", default="Failed to refresh chat rooms: {error}").format(error=e))

# Bind method to EmailManagerGUI
EmailManagerGUI.refresh_chat_rooms = refresh_chat_rooms

def create_chat_room(self):
    """Open create chat room dialog"""
    CreateChatRoomDialog(self.root, self.dashboard, self.refresh_chat_rooms)

# Bind method to EmailManagerGUI
EmailManagerGUI.create_chat_room = create_chat_room

def join_chat_room(self):
    """Join selected public chat room"""
    selection = self.public_rooms_tree.selection()
    if not selection:
        messagebox.showwarning(_t("email.chat.no_selection", default="No Selection"), _t("email.chat.select_room_to_join", default="Please select a chat room to join"))
        return

    if not self.dashboard:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.chat.dashboard_not_initialized", default="Dashboard not initialized. Please restart the application."))
        return

    item = self.public_rooms_tree.item(selection[0])
    if not item['tags']:
        messagebox.showwarning(_t("email.chat.invalid_selection", default="Invalid Selection"), _t("email.chat.select_valid_room", default="Please select a valid chat room"))
        return
    room_id = item['tags'][0]

    try:
        result = self.dashboard.join_chat_room(room_id)
        if result == True:
            messagebox.showinfo(_t("common.success", default="Success"), _t("email.chat.joined_success", default="Successfully joined chat room!"))
            self.refresh_chat_rooms()
        elif result == "already_member":
            messagebox.showinfo(_t("common.info", default="Info"), _t("email.chat.already_member", default="You are already a member of this room"))
        else:
            messagebox.showerror(_t("common.error", default="Error"), _t("email.chat.join_failed", default="Failed to join chat room"))
    except Exception as e:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.chat.join_error", default="Error joining chat room: {error}").format(error=e))

# Bind method to EmailManagerGUI
EmailManagerGUI.join_chat_room = join_chat_room

def enter_chat_room(self, event):
    """Enter selected chat room"""
    selection = self.my_rooms_tree.selection()
    if not selection:
        return

    if not self.dashboard:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.chat.dashboard_not_initialized", default="Dashboard not initialized. Please restart the application."))
        return

    try:
        item = self.my_rooms_tree.item(selection[0])
        if not item['tags']:
            messagebox.showwarning(_t("email.chat.invalid_selection", default="Invalid Selection"), _t("email.chat.select_valid_room", default="Please select a valid chat room"))
            return

        room_id = item['tags'][0]
        room_name = item['values'][0] if item['values'] else _t("email.chat.unknown_room", default="Unknown Room")

        # Create the chat room window
        ChatRoomWindow(self.root, self.dashboard, room_id, room_name)
    except Exception as e:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.chat.enter_failed", default="Failed to enter chat room: {error}").format(error=e))
        import traceback
        traceback.print_exc()

# Bind method to EmailManagerGUI
EmailManagerGUI.enter_chat_room = enter_chat_room

def view_invitations(self):
    """View chat room invitations"""
    ChatInvitationsDialog(self.root, self.dashboard)

# Bind method to EmailManagerGUI
EmailManagerGUI.view_invitations = view_invitations

def open_chat_rooms(self):
    """Switch to chat rooms tab"""
    self.notebook.select(5)  # Chat rooms tab index (Dashboard=0, Email=1, Messages=2, SMS=3, Announcements=4, Chat=5)
    self.refresh_chat_rooms()

# Bind method to EmailManagerGUI
EmailManagerGUI.open_chat_rooms = open_chat_rooms

