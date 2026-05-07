"""
Messages Tab for Email Manager GUI — unified inbox.

This tab now hosts the single :class:`UnifiedInboxPanel` which merges:
  * University intra-system user-to-user messages (CommunicationDashboard)
  * Cross-system staff messages (InterSystemMessagingService)
  * System notifications (NotificationsService)

Compose dispatches either an intra-university message (legacy modal) or
a cross-system message (inline form). The previous standalone Cross-
System tab and Notifications Hub window are no longer needed; both have
been folded in here.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os
import sys
import logging

logger = logging.getLogger(__name__)

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

current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from education_system.university_system.modules.shared.gui.email.email_gui.email_manager_main import EmailManagerGUI
from education_system.university_system.modules.shared.gui.email.email_gui.chat_dialogs import ComposeMessageDialog, ReplyMessageDialog
from education_system.shared.messaging.unified_inbox import UnifiedInboxPanel


def create_messages_tab(self):
    """Create the unified messages tab (university + cross-system + notifications)."""
    tab_frame = ttk.Frame(self.notebook)
    self.notebook.add(tab_frame, text=_t("email.tabs.messages", default="Inbox"))
    self._messages_tab_frame = tab_frame
    self._unified_inbox_panel = UnifiedInboxPanel(
        tab_frame,
        auth=self.auth,
        system_key="university",
        dashboard=self.dashboard,
        root=self.root,
    )
    self._unified_inbox_panel.pack(fill=tk.BOTH, expand=True)


# ==================== INBOX ====================

def create_inbox(self, inbox_frame):
    """Build the inbox UI inside the messages tab frame."""

    # Messages toolbar
    toolbar_frame = ttk.Frame(inbox_frame)
    toolbar_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(
        toolbar_frame,
        text=_t("email.compose_message", default="Compose Message"),
        command=self.compose_message
    ).pack(side=tk.LEFT, padx=5)
    ttk.Button(
        toolbar_frame,
        text=_t("email.reply", default="Reply"),
        command=self.reply_message
    ).pack(side=tk.LEFT, padx=5)
    ttk.Button(
        toolbar_frame,
        text=_t("common.delete", default="Delete"),
        command=self.delete_message
    ).pack(side=tk.LEFT, padx=5)
    ttk.Button(
        toolbar_frame,
        text=_t("common.refresh", default="Refresh"),
        command=self.refresh_messages
    ).pack(side=tk.RIGHT, padx=5)

    # Create paned window for inbox and message view
    paned = ttk.PanedWindow(inbox_frame, orient=tk.HORIZONTAL)
    paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Left pane - message list
    left_frame = ttk.Frame(paned)
    paned.add(left_frame, weight=1)

    # Messages list header
    ttk.Label(
        left_frame,
        text=_t("email.inbox", default="Inbox"),
        font=('Arial', 12, 'bold')
    ).pack(pady=(0, 5))

    # Create frame for treeview with scrollbar
    tree_frame = ttk.Frame(left_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    # Scrollbars
    vsb = ttk.Scrollbar(tree_frame, orient="vertical")
    vsb.pack(side=tk.RIGHT, fill=tk.Y)

    hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
    hsb.pack(side=tk.BOTTOM, fill=tk.X)

    self.messages_tree = ttk.Treeview(
        tree_frame,
        columns=("From", "Subject", "Date", "Status"),
        show="headings",
        selectmode='browse',
        yscrollcommand=vsb.set,
        xscrollcommand=hsb.set
    )
    self.messages_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    vsb.config(command=self.messages_tree.yview)
    hsb.config(command=self.messages_tree.xview)

    # Configure columns
    self.messages_tree.heading("From", text="From")
    self.messages_tree.column("From", width=150, minwidth=100)

    self.messages_tree.heading("Subject", text="Subject")
    self.messages_tree.column("Subject", width=250, minwidth=150)

    self.messages_tree.heading("Date", text="Date")
    self.messages_tree.column("Date", width=150, minwidth=120)

    self.messages_tree.heading("Status", text="Status")
    self.messages_tree.column("Status", width=80, minwidth=60)

    # Enable row selection highlighting
    self.messages_tree.tag_configure('unread', background='#E8F4F8')
    self.messages_tree.tag_configure('read', background='white')

    self.messages_tree.bind("<<TreeviewSelect>>", self.on_message_select)
    self.messages_tree.bind("<Double-1>", self.on_message_double_click)
    self.messages_tree.bind("<Button-3>", self.show_message_context_menu)

    # Add helpful label
    help_label = ttk.Label(
        left_frame,
        text=_t("email.help_click_message", default="Click a message to view - Double-click or use Reply button to respond"),
        font=('Arial', 9, 'italic'),
        foreground='#666'
    )
    help_label.pack(pady=(5, 0))

    # Right pane - message viewer
    right_frame = ttk.Frame(paned)
    paned.add(right_frame, weight=2)

    # Header with selection indicator
    header_frame = ttk.Frame(right_frame)
    header_frame.pack(fill=tk.X, pady=(0, 5))

    ttk.Label(
        header_frame,
        text=_t("email.message_content", default="Message Content"),
        font=('Arial', 12, 'bold')
    ).pack(side=tk.LEFT)

    # Selection indicator
    self.selected_message_indicator = ttk.Label(
        header_frame,
        text=_t("email.no_message_selected", default="No message selected"),
        font=('Arial', 9, 'italic'),
        foreground='#666'
    )
    self.selected_message_indicator.pack(side=tk.RIGHT, padx=5)

    self.message_text = scrolledtext.ScrolledText(right_frame, state=tk.DISABLED, wrap=tk.WORD)
    self.message_text.pack(fill=tk.BOTH, expand=True)


# ==================== INBOX MESSAGE METHODS ====================

def refresh_messages(self):
    """Refresh the unified inbox panel (delegates to UnifiedInboxPanel)."""
    panel = getattr(self, "_unified_inbox_panel", None)
    if panel is not None:
        panel.refresh()
        return
    # Legacy path retained for safety if a caller wires the old UI
    try:
        if not hasattr(self, "messages_tree"):
            return
        for item in self.messages_tree.get_children():
            self.messages_tree.delete(item)

        if self.dashboard:
            inbox = self.dashboard.get_inbox()

            # Handle case where inbox might be a boolean or None
            if isinstance(inbox, dict):
                messages = inbox.get('messages', [])

                if not messages:
                    # Insert a placeholder if no messages
                    self.messages_tree.insert('', tk.END, values=(
                        "No messages",
                        "Your inbox is empty",
                        "",
                        ""
                    ), tags=('empty',))
                else:
                    for message in messages:
                        status = "NEW" if not message['is_read'] else "READ"
                        # Use different tags for styling
                        tag = 'unread' if not message['is_read'] else 'read'

                        self.messages_tree.insert('', tk.END, values=(
                            message['sender'],
                            message['subject'][:40] + ('...' if len(message['subject']) > 40 else ''),
                            message['sent_at'],
                            status
                        ), tags=(str(message['id']), tag))

                self.update_status(f"Messages refreshed - {len(messages)} message(s)")
            else:
                print(f"Warning: inbox is not a dict, it's {type(inbox)}")
                # Show error in tree
                self.messages_tree.insert('', tk.END, values=(
                    "Error",
                    "Failed to load messages",
                    "",
                    ""
                ), tags=('error',))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to refresh messages: {e}")
        import traceback
        traceback.print_exc()


def compose_message(self):
    """Open compose message dialog"""
    ComposeMessageDialog(self.root, self.dashboard)


def reply_message(self):
    """Reply to selected message"""
    selection = self.messages_tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select a message to reply to")
        return

    if not self.dashboard:
        messagebox.showerror("Error", "Dashboard not initialized. Please restart the application.")
        return

    item = self.messages_tree.item(selection[0])
    message_id = item['tags'][0]
    ReplyMessageDialog(self.root, self.dashboard, message_id)


def delete_message(self):
    """Delete selected message"""
    selection = self.messages_tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select a message to delete")
        return

    if not self.dashboard:
        messagebox.showerror("Error", "Dashboard not initialized. Please restart the application.")
        return

    item = self.messages_tree.item(selection[0])
    message_id = item['tags'][0]

    if messagebox.askyesno("Confirm Delete", "Delete this message?"):
        try:
            if self.dashboard.update_message_status(message_id, 'delete'):
                self.refresh_messages()
                self.update_status("Message deleted")
            else:
                messagebox.showerror("Error", "Failed to delete message")
        except Exception as e:
            messagebox.showerror("Error", f"Error deleting message: {e}")


def on_message_select(self, event):
    """Handle message selection"""
    # Prevent recursive calls when restoring selection
    if getattr(self, '_restoring_selection', False):
        return

    selection = self.messages_tree.selection()
    if selection:
        item = self.messages_tree.item(selection[0])
        tags = item['tags']

        # Skip if this is a placeholder message
        if 'empty' in tags or 'error' in tags:
            # Update indicator to show no message selected
            if hasattr(self, 'selected_message_indicator'):
                self.selected_message_indicator.config(
                    text="No message selected",
                    foreground='#666'
                )
            return

        if not tags:
            if hasattr(self, 'selected_message_indicator'):
                self.selected_message_indicator.config(
                    text="No message selected",
                    foreground='#666'
                )
            return

        message_id = tags[0]

        try:
            if self.dashboard:
                message = self.dashboard.read_message(message_id)
                if message:
                    self.message_text.config(state=tk.NORMAL)
                    self.message_text.delete(1.0, tk.END)

                    # Format message content
                    content = f"From: {message['sender']}\n"
                    content += f"To: {message['recipient']}\n"
                    content += f"Subject: {message['subject']}\n"
                    content += f"Date: {message['sent_at']}\n"
                    content += f"Status: {'Read' if message['is_read'] else 'Unread'}\n"
                    content += "-" * 50 + "\n\n"
                    content += message['content']

                    self.message_text.insert(1.0, content)
                    self.message_text.config(state=tk.DISABLED)

                    # Update selection indicator to show message is ready for reply
                    if hasattr(self, 'selected_message_indicator'):
                        self.selected_message_indicator.config(
                            text="✓ Message selected - Ready to reply",
                            foreground='#2E86AB',  # Primary color
                            font=('Arial', 9, 'bold')
                        )

                    # Mark as read - refresh and restore selection
                    self.refresh_messages()
                    # Restore selection after refresh
                    self._select_message_by_id(message_id)
        except Exception as e:
            messagebox.showerror("Error", f"Error loading message: {e}")
            import traceback
            traceback.print_exc()
    else:
        # No selection - reset indicator
        if hasattr(self, 'selected_message_indicator'):
            self.selected_message_indicator.config(
                text="No message selected",
                foreground='#666',
                font=('Arial', 9, 'italic')
            )


def _select_message_by_id(self, message_id):
    """Select a message in the tree by its ID (stored in tags)"""
    self._restoring_selection = True
    try:
        for item in self.messages_tree.get_children():
            item_tags = self.messages_tree.item(item, 'tags')
            if item_tags and str(message_id) in item_tags:
                self.messages_tree.selection_set(item)
                self.messages_tree.see(item)
                break
    finally:
        # Use after_idle to reset the flag AFTER the <<TreeviewSelect>> event is processed
        # This prevents infinite recursion when selection_set triggers the event
        self.root.after_idle(lambda: setattr(self, '_restoring_selection', False))


def on_message_double_click(self, event):
    """Handle double-click on message - open reply dialog"""
    selection = self.messages_tree.selection()
    if selection:
        # Same as clicking Reply button
        self.reply_message()


def show_message_context_menu(self, event):
    """Show context menu for message"""
    # Select the item under cursor
    item = self.messages_tree.identify_row(event.y)
    if item:
        self.messages_tree.selection_set(item)

        # Check if it's a valid message (not placeholder)
        item_data = self.messages_tree.item(item)
        tags = item_data['tags']

        if 'empty' in tags or 'error' in tags:
            return

        # Create context menu
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label="Reply", command=self.reply_message)
        context_menu.add_command(label="Delete", command=self.delete_message)
        context_menu.add_separator()
        context_menu.add_command(label="Mark as Unread", command=lambda: self.mark_message_unread(tags[0]))
        context_menu.add_command(label="Archive", command=lambda: self.archive_message(tags[0]))

        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()


def mark_message_unread(self, message_id):
    """Mark a message as unread"""
    try:
        if self.dashboard:
            # Call dashboard method to mark unread
            from education_system.university_system.infrastructure.database.db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE messages SET is_read = 0, read_at = NULL WHERE id = ?', (message_id,))
            conn.commit()
            conn.close()
            self.refresh_messages()
            self.update_status("Message marked as unread")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to mark as unread: {e}")


def archive_message(self, message_id):
    """Archive a message"""
    try:
        if self.dashboard:
            from education_system.university_system.infrastructure.database.db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE messages SET is_archived = 1 WHERE id = ?', (message_id,))
            conn.commit()
            conn.close()
            self.refresh_messages()
            self.update_status("Message archived")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to archive message: {e}")


def open_messages(self):
    """Switch to messages tab"""
    # Find the messages tab index
    for i in range(self.notebook.index('end')):
        if self.notebook.tab(i, 'text') in ['Messages', 'Inbox', _t("email.tabs.messages", default="Inbox")]:
            self.notebook.select(i)
            self.refresh_messages()
            return


# ==================== BIND METHODS TO EmailManagerGUI ====================

# Bind all methods to EmailManagerGUI class
EmailManagerGUI.create_messages_tab = create_messages_tab
EmailManagerGUI.refresh_messages = refresh_messages
EmailManagerGUI.compose_message = compose_message
EmailManagerGUI.reply_message = reply_message
EmailManagerGUI.delete_message = delete_message
EmailManagerGUI.on_message_select = on_message_select
EmailManagerGUI._select_message_by_id = _select_message_by_id
EmailManagerGUI.on_message_double_click = on_message_double_click
EmailManagerGUI.show_message_context_menu = show_message_context_menu
EmailManagerGUI.mark_message_unread = mark_message_unread
EmailManagerGUI.archive_message = archive_message
EmailManagerGUI.open_messages = open_messages

