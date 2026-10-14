"""Conversation lifecycle and history-management UI."""

import json
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from uuid import uuid4

from education_system.systems.university.shell.gui.ai.conversation_store import (
    ConversationStore,
)


class ConversationsMixin:
    def initialize_conversation_management(self, store=None):
        self.conversation_store = store or ConversationStore()
        username = self.current_user.get('username', 'unknown')
        preferences = self.conversation_store.preferences(username)
        self.history_enabled = bool(preferences['history_enabled'])
        self.history_retention_days = int(preferences['retention_days'])
        if hasattr(self, 'history_enabled_var'):
            self.history_enabled_var.set(self.history_enabled)
        if hasattr(self, 'retention_days_var'):
            self.retention_days_var.set(self.history_retention_days)
        self._saved_draft = preferences.get('draft', '')
        self.conversation_store.purge_expired(username, self.history_retention_days)
        self.conversation_store.cleanup_attachments()
        self._start_new_conversation(clear=False)
        if self._saved_draft:
            self.message_entry.insert('1.0', self._saved_draft)

    def new_conversation(self):
        if getattr(self, '_processing_message', False):
            self.stop_generating()
        self._start_new_conversation(clear=True)

    def _start_new_conversation(self, clear=True):
        self.save_draft()
        username = self.current_user.get('username', 'unknown')
        if getattr(self, 'history_enabled', True):
            self.conversation_id = self.conversation_store.create(username)
        else:
            self.conversation_id = uuid4().hex
        self.session_id = f"gui_{username}_{self.conversation_id}"
        if clear and hasattr(self, 'chat_display'):
            self.chat_display.configure(state=tk.NORMAL)
            self.chat_display.delete('1.0', tk.END)
            self.chat_display.configure(state=tk.DISABLED)
            self._message_cards = []
            self._reset_conversation_context()
            self.message_entry.delete('1.0', tk.END)
        self.add_chat_message('System', 'Started a new conversation.', 'system')

    def _save_conversation_message(self, sender, message, message_type):
        if getattr(self, '_loading_conversation', False):
            return
        store = getattr(self, 'conversation_store', None)
        conversation_id = getattr(self, 'conversation_id', None)
        if not store or not conversation_id:
            return None
        if not getattr(self, 'history_enabled', True):
            return None
        message_id = store.add_message(conversation_id, sender, message, message_type)
        if message_type == 'user':
            store.title_from_first_message(conversation_id, message)
        return message_id

    def save_draft(self):
        if not hasattr(self, 'conversation_store') or not hasattr(self, 'message_entry'):
            return
        try:
            draft = self.message_entry.get('1.0', tk.END).strip()
        except Exception:
            draft = ''
        username = self.current_user.get('username', 'unknown')
        conversation_id = getattr(self, 'conversation_id', None)
        if conversation_id and getattr(self, 'history_enabled', True):
            self.conversation_store.save_draft(conversation_id, draft)
        self.conversation_store.save_preferences(
            username, history_enabled=getattr(self, 'history_enabled', True),
            retention_days=getattr(self, 'history_retention_days', 90), draft=draft,
        )

    def show_conversation_manager(self):
        window = tk.Toplevel(self.root)
        window.title('Saved conversations')
        window.geometry('760x480')
        window.transient(self.root)

        search_var = tk.StringVar()
        search = ttk.Entry(window, textvariable=search_var)
        search.pack(fill=tk.X, padx=10, pady=10)
        search.insert(0, '')

        columns = ('pinned', 'folder', 'title', 'updated', 'messages')
        tree = ttk.Treeview(window, columns=columns, show='headings', selectmode='browse')
        tree.heading('pinned', text='Pinned')
        tree.heading('folder', text='Folder')
        tree.heading('title', text='Title')
        tree.heading('updated', text='Last updated')
        tree.heading('messages', text='Messages')
        tree.column('pinned', width=60, anchor=tk.CENTER)
        tree.column('folder', width=110)
        tree.column('title', width=360)
        tree.column('updated', width=210)
        tree.column('messages', width=80, anchor=tk.CENTER)
        tree.pack(fill=tk.BOTH, expand=True, padx=10)

        def selected_id():
            selection = tree.selection()
            return selection[0] if selection else None

        def refresh(*_args):
            tree.delete(*tree.get_children())
            username = self.current_user.get('username', 'unknown')
            for item in self.conversation_store.list(username, search_var.get()):
                tree.insert('', tk.END, iid=item['id'], values=(
                    'Yes' if item['pinned'] else '', item['folder'], item['title'],
                    item['updated_at'].replace('T', ' ')[:19],
                    item['message_count'],
                ))

        def open_selected():
            conversation_id = selected_id()
            if not conversation_id:
                return
            self._load_conversation(conversation_id)
            window.destroy()

        def rename_selected():
            conversation_id = selected_id()
            if not conversation_id:
                return
            current = tree.item(conversation_id, 'values')[2]
            title = simpledialog.askstring('Rename conversation', 'Conversation title:',
                                           initialvalue=current, parent=window)
            if title:
                self.conversation_store.rename(conversation_id, title)
                refresh()

        def delete_selected():
            conversation_id = selected_id()
            if not conversation_id:
                return
            if messagebox.askyesno('Delete conversation',
                                   'Permanently delete this conversation?', parent=window):
                self.conversation_store.delete(conversation_id)
                if conversation_id == getattr(self, 'conversation_id', None):
                    self._start_new_conversation(clear=True)
                refresh()

        def export_selected():
            conversation_id = selected_id()
            if conversation_id:
                self._export_saved_conversation(conversation_id, parent=window)

        def toggle_pin():
            conversation_id = selected_id()
            if conversation_id:
                pinned = tree.item(conversation_id, 'values')[0] != 'Yes'
                self.conversation_store.set_organisation(conversation_id, pinned=pinned)
                refresh()

        def move_to_folder():
            conversation_id = selected_id()
            if not conversation_id:
                return
            current = tree.item(conversation_id, 'values')[1]
            folder = simpledialog.askstring('Conversation folder', 'Folder name:',
                                            initialvalue=current, parent=window)
            if folder is not None:
                self.conversation_store.set_organisation(conversation_id, folder=folder)
                refresh()

        buttons = ttk.Frame(window)
        buttons.pack(fill=tk.X, padx=10, pady=10)
        for label, command in (
            ('Open', open_selected), ('Rename', rename_selected),
            ('Pin/unpin', toggle_pin), ('Move to folder', move_to_folder),
            ('Delete', delete_selected), ('Export', export_selected),
            ('New conversation', lambda: (self.new_conversation(), window.destroy())),
        ):
            ttk.Button(buttons, text=label, command=command,
                       style='CB.Secondary.TButton').pack(side=tk.LEFT, padx=3)
        search_var.trace_add('write', refresh)
        tree.bind('<Double-1>', lambda _event: open_selected())
        refresh()
        search.focus_set()

    def _load_conversation(self, conversation_id):
        self.save_draft()
        self.conversation_id = conversation_id
        username = self.current_user.get('username', 'unknown')
        self.session_id = f"gui_{username}_{conversation_id}"
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.delete('1.0', tk.END)
        self.chat_display.configure(state=tk.DISABLED)
        self._message_cards = []
        self._reset_conversation_context()
        self._loading_conversation = True
        try:
            for item in self.conversation_store.messages(conversation_id):
                self.add_chat_message(item['sender'], item['message'], item['message_type'])
        finally:
            self._loading_conversation = False
        draft = self.conversation_store.draft(conversation_id)
        self.message_entry.delete('1.0', tk.END)
        if draft:
            self.message_entry.insert('1.0', draft)

    def _export_saved_conversation(self, conversation_id, parent=None):
        filename = filedialog.asksaveasfilename(
            parent=parent or self.root, defaultextension='.json',
            filetypes=[('JSON files', '*.json'), ('Text files', '*.txt')],
            title='Export conversation',
        )
        if not filename:
            return
        messages = self.conversation_store.messages(conversation_id)
        if filename.lower().endswith('.txt'):
            with open(filename, 'w', encoding='utf-8') as output:
                for item in messages:
                    output.write(f"[{item['created_at']}] {item['sender']}: {item['message']}\n\n")
        else:
            with open(filename, 'w', encoding='utf-8') as output:
                json.dump(messages, output, indent=2, ensure_ascii=False)
