"""Student Messaging Hub GUI (Feature 38).

Provides a two-pane messaging interface with conversation list on the left
and message view on the right. Supports direct messages and study group chats.
"""

import logging
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, simpledialog, ttk

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity

logger = logging.getLogger(__name__)


class MessagingHubGUI:
    """Toplevel window for the student messaging hub."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.student_id = (
            auth.current_user.get('username', '') if auth and auth.current_user else ''
        )
        self.selected_room_id = None
        self.selected_room_name = ''

        self.window = tk.Toplevel(parent)
        self.window.title("Student Messaging Hub")
        self.window.geometry("950x650")
        self.window.transient(parent)

        self._ensure_tables()
        self._setup_ui()
        self._load_conversations()

    # ------------------------------------------------------------------
    # Database setup
    # ------------------------------------------------------------------

    def _get_user_int_id(self):
        """Return the integer user ID from auth.current_user, or None."""
        if self.auth and self.auth.current_user:
            uid = self.auth.current_user.get('id')
            if uid is not None:
                try:
                    return int(uid)
                except (ValueError, TypeError):
                    pass
        return None

    def _ensure_tables(self):
        """Create chat tables if they do not exist."""
        try:
            with transaction() as conn:
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS chat_rooms (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        room_type TEXT DEFAULT 'direct',
                        created_by INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )"""
                )
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS chat_room_members (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        room_id INTEGER,
                        user_id TEXT,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )"""
                )
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS chat_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        room_id INTEGER,
                        sender_id TEXT,
                        content TEXT,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )"""
                )
        except Exception as exc:
            logger.error("Failed to create chat tables: %s", exc)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the two-pane messaging interface."""
        ttk.Label(
            self.window,
            text="Messaging Hub",
            font=('Arial', 16, 'bold'),
        ).pack(pady=(10, 5))

        # Horizontal PanedWindow
        paned = ttk.PanedWindow(self.window, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # ---- Left pane: conversation list ----
        left_frame = ttk.Frame(paned, width=250)
        paned.add(left_frame, weight=0)

        ttk.Label(left_frame, text="Conversations", font=('Arial', 12, 'bold')).pack(
            pady=(5, 3)
        )

        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.conv_listbox = tk.Listbox(list_frame, width=30, font=('Arial', 10))
        conv_scroll = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.conv_listbox.yview
        )
        self.conv_listbox.configure(yscrollcommand=conv_scroll.set)
        self.conv_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        conv_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.conv_listbox.bind('<<ListboxSelect>>', self._on_conversation_selected)

        # Internal mapping: listbox index -> room data
        self._room_data = []

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(
            btn_frame, text="New Direct Message", command=self._new_direct_message
        ).pack(fill=tk.X, pady=2)
        ttk.Button(
            btn_frame, text="New Study Group", command=self._new_study_group
        ).pack(fill=tk.X, pady=2)
        ttk.Button(
            btn_frame, text="Refresh", command=self._load_conversations
        ).pack(fill=tk.X, pady=2)

        # ---- Right pane: message view ----
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        # Conversation name label
        self.conv_name_var = tk.StringVar(value="Select a conversation")
        ttk.Label(
            right_frame,
            textvariable=self.conv_name_var,
            font=('Arial', 13, 'bold'),
        ).pack(pady=(5, 3), padx=10, anchor=tk.W)

        # Messages area (read-only Text widget)
        msg_frame = ttk.Frame(right_frame)
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.messages_text = tk.Text(
            msg_frame, wrap=tk.WORD, state=tk.DISABLED, font=('Arial', 10)
        )
        msg_scroll = ttk.Scrollbar(
            msg_frame, orient=tk.VERTICAL, command=self.messages_text.yview
        )
        self.messages_text.configure(yscrollcommand=msg_scroll.set)
        self.messages_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        msg_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Input area
        input_frame = ttk.Frame(right_frame)
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.message_entry = ttk.Entry(input_frame, font=('Arial', 10))
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.message_entry.bind('<Return>', lambda e: self._send_message())

        ttk.Button(input_frame, text="Send", command=self._send_message).pack(
            side=tk.RIGHT
        )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_conversations(self):
        """Load the current user's conversations into the listbox."""
        self.conv_listbox.delete(0, tk.END)
        self._room_data.clear()

        if not self.student_id:
            return

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """SELECT cr.id, cr.name, cr.room_type,
                              MAX(cm.sent_at) AS last_msg
                       FROM chat_rooms cr
                       JOIN chat_room_members crm ON cr.id = crm.room_id
                       LEFT JOIN chat_messages cm ON cr.id = cm.room_id
                       WHERE crm.user_id = ?
                       GROUP BY cr.id
                       ORDER BY last_msg DESC""",
                    (self.student_id,),
                ).fetchall()

            for row in rows:
                room_id, name, room_type, last_msg = row
                display_label = f"{'[G] ' if room_type == 'group' else ''}{name}"
                if last_msg:
                    display_label += f"  ({last_msg[:16]})"
                self.conv_listbox.insert(tk.END, display_label)
                self._room_data.append(
                    {'id': room_id, 'name': name, 'room_type': room_type}
                )
        except Exception as exc:
            logger.error("Failed to load conversations: %s", exc)

    def _on_conversation_selected(self, event):
        """Handle conversation selection."""
        selection = self.conv_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        room = self._room_data[idx]
        self.selected_room_id = room['id']
        self.selected_room_name = room['name']
        self.conv_name_var.set(room['name'])
        self._load_messages()

    def _load_messages(self):
        """Load messages for the currently selected room."""
        self.messages_text.configure(state=tk.NORMAL)
        self.messages_text.delete('1.0', tk.END)

        if self.selected_room_id is None:
            self.messages_text.configure(state=tk.DISABLED)
            return

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """SELECT sender_id, content, sent_at
                       FROM chat_messages
                       WHERE room_id = ?
                       ORDER BY sent_at ASC""",
                    (self.selected_room_id,),
                ).fetchall()

            for sender_id, content, sent_at in rows:
                timestamp = sent_at[:19] if sent_at else ''
                self.messages_text.insert(
                    tk.END, f"[{timestamp}] {sender_id}: {content}\n"
                )
        except Exception as exc:
            logger.error("Failed to load messages: %s", exc)

        self.messages_text.configure(state=tk.DISABLED)
        self.messages_text.see(tk.END)

    # ------------------------------------------------------------------
    # Sending messages
    # ------------------------------------------------------------------

    def _send_message(self):
        """Send a message in the current conversation."""
        if self.selected_room_id is None:
            messagebox.showwarning(
                "No Conversation", "Please select a conversation first.",
                parent=self.window,
            )
            return

        content = self.message_entry.get().strip()
        if not content:
            return

        try:
            with transaction() as conn:
                conn.execute(
                    """INSERT INTO chat_messages (room_id, sender_id, content)
                       VALUES (?, ?, ?)""",
                    (self.selected_room_id, self.student_id, content),
                )
            self.message_entry.delete(0, tk.END)
            self._load_messages()
            logger.info(
                "Message sent by %s in room %s", self.student_id, self.selected_room_id
            )
        except Exception as exc:
            logger.error("Failed to send message: %s", exc)
            messagebox.showerror(
                "Error", f"Failed to send message: {exc}", parent=self.window
            )

    # ------------------------------------------------------------------
    # New conversation dialogs
    # ------------------------------------------------------------------

    def _new_direct_message(self):
        """Open a dialog to start a direct message conversation."""
        recipient = simpledialog.askstring(
            "New Direct Message",
            "Enter recipient user ID:",
            parent=self.window,
        )
        if not recipient or not recipient.strip():
            return
        recipient = recipient.strip()

        if recipient == self.student_id:
            messagebox.showwarning(
                "Invalid Recipient",
                "You cannot start a conversation with yourself.",
                parent=self.window,
            )
            return

        try:
            room_name = f"DM: {self.student_id} & {recipient}"
            user_int_id = self._get_user_int_id() or 0
            with transaction() as conn:
                cursor = conn.execute(
                    """INSERT INTO chat_rooms (name, room_type, created_by)
                       VALUES (?, 'direct', ?)""",
                    (room_name, user_int_id),
                )
                room_id = cursor.lastrowid
                conn.execute(
                    """INSERT INTO chat_room_members (room_id, user_id)
                       VALUES (?, ?)""",
                    (room_id, self.student_id),
                )
                conn.execute(
                    """INSERT INTO chat_room_members (room_id, user_id)
                       VALUES (?, ?)""",
                    (room_id, recipient),
                )

            log_activity(
                self.student_id, self.student_id, 'student',
                'create_direct_message', 'messaging_hub',
                details=f"Created DM room with {recipient}",
            )
            logger.info("Direct message room created: %s -> %s", self.student_id, recipient)
            self._load_conversations()
            messagebox.showinfo(
                "Success",
                f"Direct message conversation with {recipient} created.",
                parent=self.window,
            )
        except Exception as exc:
            logger.error("Failed to create direct message: %s", exc)
            messagebox.showerror(
                "Error", f"Failed to create conversation: {exc}", parent=self.window
            )

    def _new_study_group(self):
        """Open a dialog to create a new study group chat."""
        group_name = simpledialog.askstring(
            "New Study Group",
            "Enter study group name:",
            parent=self.window,
        )
        if not group_name or not group_name.strip():
            return
        group_name = group_name.strip()

        try:
            user_int_id = self._get_user_int_id() or 0
            with transaction() as conn:
                cursor = conn.execute(
                    """INSERT INTO chat_rooms (name, room_type, created_by)
                       VALUES (?, 'group', ?)""",
                    (group_name, user_int_id),
                )
                room_id = cursor.lastrowid
                conn.execute(
                    """INSERT INTO chat_room_members (room_id, user_id)
                       VALUES (?, ?)""",
                    (room_id, self.student_id),
                )

            log_activity(
                self.student_id, self.student_id, 'student',
                'create_study_group', 'messaging_hub',
                details=f"Created study group: {group_name}",
            )
            logger.info("Study group '%s' created by %s", group_name, self.student_id)
            self._load_conversations()
            messagebox.showinfo(
                "Success",
                f"Study group '{group_name}' created.",
                parent=self.window,
            )
        except Exception as exc:
            logger.error("Failed to create study group: %s", exc)
            messagebox.showerror(
                "Error", f"Failed to create study group: {exc}", parent=self.window
            )
