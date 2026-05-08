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

from education_system.university_system.modules.shared.gui.email.email_gui.email_manager_main import EmailManagerGUI
from education_system.university_system.modules.shared.gui.email.email_gui.chat_dialogs import (
    CreateChatRoomDialog, ChatInvitationsDialog, ChatRoomWindow,
    EditRoomDialog, ManageMembersDialog,
    ReportsDialog, AuditLogDialog, BlocksDialog, GDPRChatDialog,
)

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
    ttk.Button(toolbar_frame, text=_t("email.search_all", default="Search All Rooms"), command=self.search_all_rooms).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("email.sync_courses", default="Sync Course Rooms"), command=self.sync_course_rooms).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("email.reports", default="Reports"),
               command=lambda: ReportsDialog(self.root, self.dashboard)).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("email.blocks", default="Blocks"),
               command=lambda: BlocksDialog(self.root, self.dashboard)).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("email.my_data", default="My Data"),
               command=lambda: GDPRChatDialog(self.root, self.dashboard)).pack(side=tk.LEFT, padx=5)
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
    """Create my chat rooms tab — with filter, category groups, favourites."""
    tab_frame = ttk.Frame(self.chat_notebook)
    self.chat_notebook.add(tab_frame, text=_t("email.my_rooms", default="My Rooms"))

    # Filter row
    filter_frame = ttk.Frame(tab_frame)
    filter_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
    ttk.Label(filter_frame, text=_t("common.filter", default="Filter:")).pack(side=tk.LEFT)
    self.my_rooms_filter_var = tk.StringVar()
    entry = ttk.Entry(filter_frame, textvariable=self.my_rooms_filter_var)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    self.my_rooms_filter_var.trace_add("write", lambda *_a: self._render_my_rooms())
    ttk.Button(filter_frame, text="✕", width=2,
               command=lambda: self.my_rooms_filter_var.set("")).pack(side=tk.LEFT)

    # Tree (with parent grouping by Favourites/Category)
    body = ttk.Frame(tab_frame)
    body.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    columns = ("Type", "Members", "Messages", "Unread", "Role")
    self.my_rooms_tree = ttk.Treeview(body, columns=columns, show="tree headings")
    self.my_rooms_tree.heading("#0", text="Room")
    self.my_rooms_tree.column("#0", width=260)
    for col in columns:
        self.my_rooms_tree.heading(col, text=col)
    self.my_rooms_tree.column("Unread", width=70, anchor=tk.CENTER)
    self.my_rooms_tree.tag_configure("has_unread", foreground="#b30000",
                                     font=("TkDefaultFont", 10, "bold"))
    self.my_rooms_tree.tag_configure("group", font=("TkDefaultFont", 10, "bold"),
                                     background="#f0f0f0")

    sb = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.my_rooms_tree.yview)
    self.my_rooms_tree.configure(yscrollcommand=sb.set)
    self.my_rooms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)

    self.my_rooms_tree.bind("<Double-1>", self.enter_chat_room)
    self.my_rooms_tree.bind("<Button-3>", self._on_my_room_right_click)

    # Cache full list so filtering is purely client-side.
    self._joined_rooms_cache = []
    self._my_room_colour_tags = set()

EmailManagerGUI.create_my_rooms_tab = create_my_rooms_tab

def create_public_rooms_tab(self):
    """Create public rooms tab — with filter."""
    tab_frame = ttk.Frame(self.chat_notebook)
    self.chat_notebook.add(tab_frame, text=_t("email.public_rooms", default="Public Rooms"))

    filter_frame = ttk.Frame(tab_frame)
    filter_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
    ttk.Label(filter_frame, text=_t("common.filter", default="Filter:")).pack(side=tk.LEFT)
    self.public_rooms_filter_var = tk.StringVar()
    entry = ttk.Entry(filter_frame, textvariable=self.public_rooms_filter_var)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    self.public_rooms_filter_var.trace_add("write", lambda *_a: self._render_public_rooms())
    ttk.Button(filter_frame, text="✕", width=2,
               command=lambda: self.public_rooms_filter_var.set("")).pack(side=tk.LEFT)

    body = ttk.Frame(tab_frame)
    body.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    columns = ("Name", "Description", "Members", "Creator")
    self.public_rooms_tree = ttk.Treeview(body, columns=columns, show="headings")
    for col in columns:
        self.public_rooms_tree.heading(col, text=col)

    sb = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.public_rooms_tree.yview)
    self.public_rooms_tree.configure(yscrollcommand=sb.set)
    self.public_rooms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)

    self._public_rooms_cache = []

EmailManagerGUI.create_public_rooms_tab = create_public_rooms_tab

def refresh_chat_rooms(self):
    """Refresh caches and re-render both trees."""
    try:
        if not self.dashboard:
            return
        try:
            unread_counts = self.dashboard.get_unread_chat_counts() or {}
        except Exception:
            unread_counts = {}
        joined = self.dashboard.get_chat_rooms('joined') or {}
        for room in joined.get('rooms', []):
            room['_unread'] = int(unread_counts.get(room['id'], 0) or 0)
        self._joined_rooms_cache = joined.get('rooms', [])

        public = self.dashboard.get_chat_rooms('public') or {}
        self._public_rooms_cache = public.get('rooms', [])

        self._render_my_rooms()
        self._render_public_rooms()
        self.update_status("Chat rooms refreshed")
    except Exception as e:
        messagebox.showerror(_t("common.error", default="Error"),
                             _t("email.chat.refresh_failed",
                                default="Failed to refresh chat rooms: {error}").format(error=e))

EmailManagerGUI.refresh_chat_rooms = refresh_chat_rooms

def _render_my_rooms(self):
    """Render the My Rooms tree from cache, filtered + grouped."""
    tree = self.my_rooms_tree
    for item in tree.get_children():
        tree.delete(item)
    needle = (self.my_rooms_filter_var.get() or "").strip().lower()
    rooms = self._joined_rooms_cache or []
    if needle:
        rooms = [r for r in rooms
                 if needle in (r.get('name') or '').lower()
                 or needle in (r.get('description') or '').lower()
                 or needle in (r.get('category') or '').lower()]
    # Group: Favourites first, then by category, then 'Other' for empty.
    groups = {}
    for r in rooms:
        if r.get('is_favourite'):
            key = "★ Favourites"
        else:
            key = r.get('category') or "Other"
        groups.setdefault(key, []).append(r)
    # Order: Favourites first; everything else alphabetical, "Other" last.
    keys = sorted(groups.keys(),
                  key=lambda k: (0, '') if k == "★ Favourites"
                                else (2, '') if k == "Other"
                                else (1, k.lower()))
    for key in keys:
        parent = tree.insert('', tk.END, text=key, open=True,
                             tags=("group",))
        for r in groups[key]:
            role = "Admin" if r.get('is_admin') else "Member"
            unread = r.get('_unread', 0)
            row_tags = [str(r['id'])]
            if unread:
                row_tags.append("has_unread")
            colour = r.get('colour')
            if colour:
                tag = f"colour_{colour.lstrip('#')}"
                if tag not in self._my_room_colour_tags:
                    try:
                        tree.tag_configure(tag, background=colour)
                        self._my_room_colour_tags.add(tag)
                    except Exception:
                        pass
                row_tags.append(tag)
            icon = (r.get('icon') or '').strip()
            star = "★ " if r.get('is_favourite') else ""
            display_name = f"{star}{icon + ' ' if icon else ''}{r['name']}"
            tree.insert(parent, tk.END, text=display_name, values=(
                r['room_type'],
                r['member_count'],
                r['message_count'],
                unread if unread else "",
                role,
            ), tags=tuple(row_tags))

EmailManagerGUI._render_my_rooms = _render_my_rooms

def _render_public_rooms(self):
    tree = self.public_rooms_tree
    for item in tree.get_children():
        tree.delete(item)
    needle = (self.public_rooms_filter_var.get() or "").strip().lower()
    rooms = self._public_rooms_cache or []
    if needle:
        rooms = [r for r in rooms
                 if needle in (r.get('name') or '').lower()
                 or needle in (r.get('description') or '').lower()]
    for r in rooms:
        desc = r.get('description') or ''
        if len(desc) > 30:
            desc = desc[:30] + '...'
        tree.insert('', tk.END, values=(
            r['name'], desc, r['member_count'], r['creator'],
        ), tags=(str(r['id']),))

EmailManagerGUI._render_public_rooms = _render_public_rooms

def _selected_my_room(self):
    """Return the cached room dict for the current My Rooms selection, or None
    if a category group is selected."""
    sel = self.my_rooms_tree.selection()
    if not sel:
        return None
    tags = self.my_rooms_tree.item(sel[0]).get('tags') or ()
    if not tags or not str(tags[0]).isdigit():
        return None
    rid = int(tags[0])
    return next((r for r in (self._joined_rooms_cache or []) if r['id'] == rid), None)

EmailManagerGUI._selected_my_room = _selected_my_room

def _on_my_room_right_click(self, event):
    iid = self.my_rooms_tree.identify_row(event.y)
    if iid:
        self.my_rooms_tree.selection_set(iid)
    room = self._selected_my_room()
    if not room:
        return
    current_user_id = (
        self.dashboard.auth.current_user.get('id')
        if self.dashboard and self.dashboard.auth and self.dashboard.auth.current_user
        else None
    )
    is_creator = room.get('created_by') == current_user_id
    is_admin = bool(room.get('is_admin')) or is_creator

    menu = tk.Menu(self.root, tearoff=0)
    label = "Unfavourite" if room.get('is_favourite') else "Favourite"
    menu.add_command(
        label=label,
        command=lambda: self._toggle_favourite_room(room['id'], not room.get('is_favourite')),
    )
    menu.add_separator()
    menu.add_command(label="Open", command=lambda: ChatRoomWindow(
        self.root, self.dashboard, room['id'], room['name'],
    ))
    if is_admin:
        menu.add_command(label="Edit Room…",
                         command=lambda: EditRoomDialog(self.root, self.dashboard, room,
                                                        self.refresh_chat_rooms))
        menu.add_command(label="Manage Members…",
                         command=lambda: ManageMembersDialog(self.root, self.dashboard, room,
                                                             self.refresh_chat_rooms))
        menu.add_command(label="Audit Log…",
                         command=lambda: AuditLogDialog(self.root, self.dashboard,
                                                        room_id=room['id'],
                                                        room_name=room['name']))
        menu.add_command(label="Reports for this room…",
                         command=lambda: self._open_room_reports(room['id'], room['name']))
        menu.add_command(label="Purge expired (all rooms)",
                         command=self._purge_expired)
        menu.add_separator()
        menu.add_command(label="Archive", command=lambda: self._archive_room(room['id']))
        if is_creator:
            menu.add_command(label="Delete Room…",
                             command=lambda: self._delete_room(room['id'], room['name']))
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()

EmailManagerGUI._on_my_room_right_click = _on_my_room_right_click

def _toggle_favourite_room(self, room_id, favourite):
    try:
        if self.dashboard.set_favourite_room(room_id, favourite=favourite):
            self.refresh_chat_rooms()
    except Exception as e:
        messagebox.showerror("Error", str(e))

EmailManagerGUI._toggle_favourite_room = _toggle_favourite_room

def _archive_room(self, room_id):
    if not messagebox.askyesno("Archive", "Archive this room? Members keep history "
                                          "but the room is hidden."):
        return
    try:
        if self.dashboard.archive_chat_room(room_id, archive=True):
            self.refresh_chat_rooms()
        else:
            messagebox.showerror("Error", "Could not archive (admin only).")
    except Exception as e:
        messagebox.showerror("Error", str(e))

EmailManagerGUI._archive_room = _archive_room

def _delete_room(self, room_id, room_name):
    if not messagebox.askyesno("Delete",
                               f"Permanently delete '{room_name}' and all its messages? "
                               "This cannot be undone."):
        return
    try:
        if self.dashboard.delete_chat_room(room_id):
            self.refresh_chat_rooms()
        else:
            messagebox.showerror("Error", "Could not delete (creator only).")
    except Exception as e:
        messagebox.showerror("Error", str(e))

EmailManagerGUI._delete_room = _delete_room

def _open_room_reports(self, room_id, room_name):
    """Open the Reports panel filtered to this room (uses ReportsDialog
    refreshed from the room-scoped query)."""
    try:
        # Reuse the global ReportsDialog but seed an in-memory filter.
        dlg = ReportsDialog(self.root, self.dashboard)
        # Tag the dialog so the user can identify the context.
        dlg.dialog.title(f"Reports — {room_name}")
        # Replace its refresh to scope by room.
        original = dlg._refresh
        def scoped():
            for it in dlg.tree.get_children():
                dlg.tree.delete(it)
            try:
                reports = self.dashboard.list_chat_reports(
                    status=dlg.status_var.get(), room_id=room_id) or []
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg.dialog)
                return
            for r in reports:
                target = (f"@{r.get('target_user')}" if r.get('target_user')
                          else f"msg #{r.get('target_message_id')}" if r.get('target_message_id')
                          else "")
                dlg.tree.insert(
                    '', tk.END,
                    values=(
                        (r.get('created_at') or '')[:16], r.get('status'),
                        f"@{r.get('reporter') or ''}", target,
                        r.get('room_name') or '',
                        (r.get('reason') or '')[:60],
                        r.get('message_excerpt') or '',
                    ),
                    tags=(str(r['id']),),
                )
        dlg._refresh = scoped
        dlg._refresh()
    except Exception as e:
        messagebox.showerror("Error", str(e))

EmailManagerGUI._open_room_reports = _open_room_reports

def _purge_expired(self):
    if not messagebox.askyesno(
        "Purge expired",
        "Delete chat messages older than each room's retention setting?\n"
        "Polls and pinned messages are skipped. This cannot be undone.",
    ):
        return
    try:
        n = self.dashboard.purge_expired_chat_messages()
        messagebox.showinfo("Purge", f"Removed {n} message(s).")
        self.refresh_chat_rooms()
    except Exception as e:
        messagebox.showerror("Error", str(e))

EmailManagerGUI._purge_expired = _purge_expired

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
        elif result == "banned":
            messagebox.showerror(
                _t("common.error", default="Error"),
                _t("email.chat.banned",
                   default="You have been banned from this chat room. "
                           "Contact a room admin if you think this is a mistake."),
            )
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
        tags = item.get('tags') or ()
        if not tags or not str(tags[0]).isdigit():
            # Likely a category group row; expand/collapse instead.
            iid = selection[0]
            self.my_rooms_tree.item(iid, open=not self.my_rooms_tree.item(iid, "open"))
            return

        room_id = int(tags[0])
        # Pull the canonical name from the cache (the tree text may include star/icon).
        room = next((r for r in (self._joined_rooms_cache or [])
                     if r['id'] == room_id), None)
        room_name = (room or {}).get('name') or item.get('text') \
            or _t("email.chat.unknown_room", default="Unknown Room")

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

def search_all_rooms(self):
    """Cross-room chat search: prompt for query, list hits, double-click to open."""
    if not self.dashboard:
        messagebox.showerror(_t("common.error", default="Error"),
                             _t("email.chat.dashboard_not_initialized",
                                default="Dashboard not initialized."))
        return
    query = askstring(_t("email.search_all", default="Search All Rooms"),
                      _t("email.chat.search_prompt", default="Search text:"))
    if not query or not query.strip():
        return
    try:
        hits = self.dashboard.search_chat_messages(query.strip()) or []
    except Exception as e:
        messagebox.showerror(_t("common.error", default="Error"), str(e))
        return

    dlg = tk.Toplevel(self.root)
    dlg.title(_t("email.search_results", default=f"Search: {query}"))
    dlg.geometry("700x450")
    dlg.transient(self.root)
    if not hits:
        ttk.Label(dlg, text=_t("email.chat.no_matches",
                               default=f"No matches for '{query}'.")).pack(padx=20, pady=20)
    else:
        cols = ("Room", "Sender", "Sent", "Snippet")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
        tree.column("Room", width=140)
        tree.column("Sender", width=120)
        tree.column("Sent", width=130)
        tree.column("Snippet", width=280)
        for h in hits:
            snippet = (h.get('content') or '').replace('\n', ' ')
            if len(snippet) > 100:
                snippet = snippet[:97] + '…'
            tree.insert('', tk.END, values=(
                h.get('room_name'), h.get('sender'),
                (h.get('sent_at') or '')[:16], snippet,
            ), tags=(str(h['room_id']), str(h['id'])))
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def open_room(_event=None):
            sel = tree.selection()
            if not sel:
                return
            tags = tree.item(sel[0])['tags']
            if len(tags) >= 1:
                ChatRoomWindow(self.root, self.dashboard, int(tags[0]),
                               tree.item(sel[0])['values'][0])

        tree.bind("<Double-1>", open_room)
        ttk.Button(dlg, text=_t("email.open_room", default="Open Room"),
                   command=open_room).pack(pady=(0, 5))
    ttk.Button(dlg, text=_t("common.close", default="Close"),
               command=dlg.destroy).pack(pady=(0, 10))

# Bind method to EmailManagerGUI
EmailManagerGUI.search_all_rooms = search_all_rooms

def sync_course_rooms(self):
    """Best-effort: ensure a chat room exists for every module the current
    user is enrolled in or instructs."""
    if not self.dashboard:
        return
    try:
        created = self.dashboard.sync_course_chat_rooms()
        messagebox.showinfo(
            _t("email.sync_courses", default="Sync Course Rooms"),
            (f"Created {created} new room(s)." if created
             else "All linked rooms already exist."),
        )
        self.refresh_chat_rooms()
    except Exception as e:
        messagebox.showerror(_t("common.error", default="Error"), str(e))

EmailManagerGUI.sync_course_rooms = sync_course_rooms

def open_chat_rooms(self):
    """Switch to chat rooms tab"""
    self.notebook.select(5)  # Chat rooms tab index (Dashboard=0, Email=1, Messages=2, SMS=3, Announcements=4, Chat=5)
    self.refresh_chat_rooms()

# Bind method to EmailManagerGUI
EmailManagerGUI.open_chat_rooms = open_chat_rooms

