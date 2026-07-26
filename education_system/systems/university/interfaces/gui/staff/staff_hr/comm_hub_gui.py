"""
Communication Hub GUI

Provides interface for:
- Hub dashboard with pinned messages and recent activity
- Forum browsing and thread management
- Polls and surveys with voting
- Forum administration and membership
- Cross-entity search across threads and replies
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.domain.staff.staff_hr.services.managers.comm_hub_manager import CommHubManager
from education_system.systems.university.interfaces.gui.staff.staff_hr.validators import (
    FormValidator, ValidationError, validate_entry, validate_combobox,
    show_validation_error
)


class CommHubGUI:
    """GUI for communication hub management."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Communication Hub")
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def _get_user_id(self):
        """Get user ID from current user dict."""
        return self.current_user.get('id') or self.current_user.get('username')

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Comm Hub")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Communication Hub")
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)

        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._build_interface(self.window)

    def _build_interface(self, parent):
        """Build the main interface."""
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_dashboard_tab()
        self._create_forums_tab()
        self._create_polls_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_forum_admin_tab()

        self._create_search_tab()

    # ==================== TAB 1: HUB DASHBOARD ====================

    def _create_dashboard_tab(self):
        """Create hub dashboard tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Hub Dashboard")

        # Header with Refresh
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Hub Dashboard", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_dashboard).pack(side=tk.RIGHT, padx=5)

        # Quick action buttons
        actions_frame = ttk.Frame(tab)
        actions_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(actions_frame, text="New Thread",
                   command=self._quick_new_thread).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Create Poll",
                   command=self._quick_create_poll).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="View Forums",
                   command=self._switch_to_forums_tab).pack(side=tk.LEFT, padx=5)

        # Active polls count
        self.active_polls_label = ttk.Label(actions_frame, text="Active Polls: 0",
                                            font=('Arial', 10, 'bold'))
        self.active_polls_label.pack(side=tk.RIGHT, padx=10)

        # Pinned messages section
        pinned_frame = ttk.LabelFrame(tab, text="Pinned Messages", padding=10)
        pinned_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        pinned_tree_frame = ttk.Frame(pinned_frame)
        pinned_tree_frame.pack(fill=tk.X)

        y_scroll = ttk.Scrollbar(pinned_tree_frame, orient=tk.VERTICAL)
        pinned_columns = ('ID', 'Type', 'Message ID', 'Pinned By', 'Expires At')
        self.pinned_tree = ttk.Treeview(
            pinned_tree_frame, columns=pinned_columns, show='headings',
            yscrollcommand=y_scroll.set, height=5)
        y_scroll.config(command=self.pinned_tree.yview)

        pinned_widths = {'ID': 50, 'Type': 100, 'Message ID': 100,
                         'Pinned By': 150, 'Expires At': 180}
        for col in pinned_columns:
            self.pinned_tree.heading(col, text=col)
            self.pinned_tree.column(col, width=pinned_widths.get(col, 100))

        self.pinned_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Recent threads section
        recent_frame = ttk.LabelFrame(tab, text="Recent Threads", padding=10)
        recent_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        recent_tree_frame = ttk.Frame(recent_frame)
        recent_tree_frame.pack(fill=tk.BOTH, expand=True)

        y_scroll2 = ttk.Scrollbar(recent_tree_frame, orient=tk.VERTICAL)
        recent_columns = ('Forum', 'Title', 'Author', 'Replies', 'Views', 'Last Reply')
        self.recent_threads_tree = ttk.Treeview(
            recent_tree_frame, columns=recent_columns, show='headings',
            yscrollcommand=y_scroll2.set, height=10)
        y_scroll2.config(command=self.recent_threads_tree.yview)

        recent_widths = {'Forum': 150, 'Title': 250, 'Author': 120,
                         'Replies': 70, 'Views': 70, 'Last Reply': 160}
        for col in recent_columns:
            self.recent_threads_tree.heading(col, text=col)
            self.recent_threads_tree.column(col, width=recent_widths.get(col, 100))

        self.recent_threads_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll2.pack(side=tk.RIGHT, fill=tk.Y)

        # Color tags for recent threads
        self.recent_threads_tree.tag_configure('pinned', background='#fff3cd')
        self.recent_threads_tree.tag_configure('normal', background='#ffffff')

        self._load_dashboard()

    def _load_dashboard(self):
        """Load dashboard data."""
        # Load pinned messages
        for item in self.pinned_tree.get_children():
            self.pinned_tree.delete(item)

        try:
            pinned = CommHubManager.get_pinned_messages()
        except Exception:
            pinned = []

        for p in pinned:
            self.pinned_tree.insert('', tk.END, values=(
                p.get('pin_id', ''),
                p.get('message_type', '').replace('_', ' ').title(),
                p.get('message_id', ''),
                p.get('pinned_by', ''),
                p.get('expires_at', '') or 'Never'
            ))

        # Load recent threads across all forums
        for item in self.recent_threads_tree.get_children():
            self.recent_threads_tree.delete(item)

        try:
            forums = CommHubManager.get_forums()
        except Exception:
            forums = []

        # Build forum name map
        forum_names = {}
        for f in forums:
            forum_names[f.get('forum_id')] = f.get('name', '')

        all_threads = []
        for f in forums:
            try:
                threads = CommHubManager.get_threads(f.get('forum_id'), limit=20)
                for t in threads:
                    t['_forum_name'] = f.get('name', '')
                all_threads.extend(threads)
            except Exception:
                pass

        # Sort by most recent activity and take top 10
        all_threads.sort(
            key=lambda t: t.get('last_reply_at') or t.get('created_at') or '',
            reverse=True
        )
        recent = all_threads[:10]

        for t in recent:
            is_pinned = t.get('is_pinned', 0)
            tag = 'pinned' if is_pinned else 'normal'
            self.recent_threads_tree.insert('', tk.END, values=(
                t.get('_forum_name', ''),
                t.get('title', '')[:50],
                t.get('author_id', ''),
                t.get('reply_count', 0),
                t.get('view_count', 0),
                t.get('last_reply_at', '') or 'No replies'
            ), tags=(tag,))

        # Active polls count
        try:
            polls = CommHubManager.get_polls(status='open')
        except Exception:
            polls = []

        self.active_polls_label.config(text=f"Active Polls: {len(polls)}")

    def _quick_new_thread(self):
        """Open new thread dialog from dashboard (selects forum first)."""
        self._open_new_thread_dialog(forum_id=None)

    def _quick_create_poll(self):
        """Open create poll dialog from dashboard."""
        self._open_create_poll_dialog()

    def _switch_to_forums_tab(self):
        """Switch notebook to the Forums tab."""
        self.notebook.select(1)

    # ==================== TAB 2: FORUMS ====================

    def _create_forums_tab(self):
        """Create forums tab with paned view."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Forums")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Forums", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="New Thread",
                   command=self._forum_new_thread).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Refresh",
                   command=self._load_forums).pack(side=tk.RIGHT, padx=5)

        # PanedWindow: left = forums list, right = threads in selected forum
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Left pane: Forums list
        left_frame = ttk.LabelFrame(paned, text="Forums", padding=5)
        paned.add(left_frame, weight=1)

        forums_tree_frame = ttk.Frame(left_frame)
        forums_tree_frame.pack(fill=tk.BOTH, expand=True)

        y_scroll = ttk.Scrollbar(forums_tree_frame, orient=tk.VERTICAL)
        forums_columns = ('Name', 'Type', 'Visibility')
        self.forums_tree = ttk.Treeview(
            forums_tree_frame, columns=forums_columns, show='headings',
            yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.forums_tree.yview)

        forums_widths = {'Name': 180, 'Type': 100, 'Visibility': 100}
        for col in forums_columns:
            self.forums_tree.heading(col, text=col)
            self.forums_tree.column(col, width=forums_widths.get(col, 100))

        self.forums_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Color tags for forums
        self.forums_tree.tag_configure('public', background='#d4edda')
        self.forums_tree.tag_configure('members_only', background='#cce5ff')
        self.forums_tree.tag_configure('private', background='#f8d7da')

        self.forums_tree.bind('<<TreeviewSelect>>', self._on_forum_selected)

        # Store forum data cache
        self._forums_cache = {}

        # Right pane: Threads in selected forum
        right_frame = ttk.LabelFrame(paned, text="Threads", padding=5)
        paned.add(right_frame, weight=2)

        threads_tree_frame = ttk.Frame(right_frame)
        threads_tree_frame.pack(fill=tk.BOTH, expand=True)

        y_scroll2 = ttk.Scrollbar(threads_tree_frame, orient=tk.VERTICAL)
        threads_columns = ('Title', 'Author', 'Replies', 'Views', 'Last Reply', 'Pinned')
        self.threads_tree = ttk.Treeview(
            threads_tree_frame, columns=threads_columns, show='headings',
            yscrollcommand=y_scroll2.set)
        y_scroll2.config(command=self.threads_tree.yview)

        threads_widths = {'Title': 200, 'Author': 100, 'Replies': 60,
                          'Views': 60, 'Last Reply': 150, 'Pinned': 60}
        for col in threads_columns:
            self.threads_tree.heading(col, text=col)
            self.threads_tree.column(col, width=threads_widths.get(col, 100))

        self.threads_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll2.pack(side=tk.RIGHT, fill=tk.Y)

        # Color tags for threads
        self.threads_tree.tag_configure('pinned', background='#fff3cd')
        self.threads_tree.tag_configure('normal', background='#ffffff')

        # Double-click to open thread detail
        self.threads_tree.bind('<Double-1>', self._on_thread_double_click)

        # Store thread data cache
        self._threads_cache = {}

        self._load_forums()

    def _load_forums(self):
        """Load forums list."""
        for item in self.forums_tree.get_children():
            self.forums_tree.delete(item)

        self._forums_cache = {}

        try:
            forums = CommHubManager.get_forums()
        except Exception:
            forums = []

        for f in forums:
            forum_id = f.get('forum_id')
            visibility = f.get('visibility', 'public').lower()
            display_type = f.get('forum_type', '').replace('_', ' ').title()
            display_vis = visibility.replace('_', ' ').title()

            self.forums_tree.insert('', tk.END, iid=str(forum_id), values=(
                f.get('name', ''),
                display_type,
                display_vis
            ), tags=(visibility,))

            self._forums_cache[str(forum_id)] = f

    def _on_forum_selected(self, event):
        """Load threads for the selected forum."""
        selection = self.forums_tree.selection()
        if not selection:
            return

        forum_id = int(selection[0])
        self._load_threads(forum_id)

    def _load_threads(self, forum_id):
        """Load threads for a specific forum."""
        for item in self.threads_tree.get_children():
            self.threads_tree.delete(item)

        self._threads_cache = {}

        try:
            threads = CommHubManager.get_threads(forum_id)
        except Exception:
            threads = []

        for t in threads:
            thread_id = t.get('thread_id')
            is_pinned = t.get('is_pinned', 0)
            pinned_text = 'Yes' if is_pinned else 'No'
            tag = 'pinned' if is_pinned else 'normal'

            self.threads_tree.insert('', tk.END, iid=str(thread_id), values=(
                t.get('title', '')[:50],
                t.get('author_id', ''),
                t.get('reply_count', 0),
                t.get('view_count', 0),
                t.get('last_reply_at', '') or 'No replies',
                pinned_text
            ), tags=(tag,))

            self._threads_cache[str(thread_id)] = t

    def _get_selected_forum_id(self):
        """Get the currently selected forum ID."""
        selection = self.forums_tree.selection()
        if not selection:
            return None
        return int(selection[0])

    def _forum_new_thread(self):
        """Open new thread dialog for the currently selected forum."""
        forum_id = self._get_selected_forum_id()
        if not forum_id:
            messagebox.showinfo("Info", "Please select a forum first.")
            return
        self._open_new_thread_dialog(forum_id=forum_id)

    def _open_new_thread_dialog(self, forum_id=None):
        """Open dialog to create a new thread."""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Thread")
        dialog.geometry("550x450")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Forum selector
        ttk.Label(frame, text="Forum:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        forum_combo = ttk.Combobox(frame, width=35, state='readonly')
        forum_combo.grid(row=0, column=1, padx=10, pady=8)

        forum_map = {}
        try:
            forums = CommHubManager.get_forums()
        except Exception:
            forums = []

        combo_values = []
        pre_select_index = None
        for i, f in enumerate(forums):
            fid = f.get('forum_id')
            label = f"{f.get('name', '')} (#{fid})"
            combo_values.append(label)
            forum_map[label] = fid
            if forum_id and fid == forum_id:
                pre_select_index = i

        forum_combo['values'] = combo_values
        if pre_select_index is not None:
            forum_combo.current(pre_select_index)
        elif combo_values:
            forum_combo.current(0)

        # Title
        ttk.Label(frame, text="Title:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        title_entry = ttk.Entry(frame, width=40)
        title_entry.grid(row=1, column=1, padx=10, pady=8)

        # Content
        ttk.Label(frame, text="Content:").grid(row=2, column=0, sticky='ne', padx=10, pady=8)
        content_text = scrolledtext.ScrolledText(frame, width=40, height=10, wrap=tk.WORD)
        content_text.grid(row=2, column=1, padx=10, pady=8)

        def save():
            try:
                forum_label = validate_combobox(forum_combo, "Forum")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            selected_forum_id = forum_map.get(forum_label)
            if not selected_forum_id:
                messagebox.showerror("Error", "Please select a valid forum.", parent=dialog)
                return

            try:
                title = validate_entry(title_entry, "Title")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            content = content_text.get("1.0", "end-1c").strip()
            if not content:
                messagebox.showerror("Validation Error", "Content is required.", parent=dialog)
                return

            try:
                thread_id = CommHubManager.create_thread(
                    forum_id=selected_forum_id,
                    title=title,
                    content=content,
                    author_id=self._get_user_id()
                )
                messagebox.showinfo("Success",
                                    f"Thread created. ID: {thread_id}",
                                    parent=dialog)
                dialog.destroy()
                # Refresh threads if the forum is currently selected
                current_forum = self._get_selected_forum_id()
                if current_forum == selected_forum_id:
                    self._load_threads(selected_forum_id)
                self._load_dashboard()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Create", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        title_entry.focus_set()

    def _on_thread_double_click(self, event):
        """Open thread detail dialog on double-click."""
        selection = self.threads_tree.selection()
        if not selection:
            return

        thread_id = int(selection[0])
        self._open_thread_detail_dialog(thread_id)

    def _open_thread_detail_dialog(self, thread_id):
        """Open a dialog showing thread content and replies."""
        try:
            thread = CommHubManager.get_thread(thread_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load thread: {e}")
            return

        if not thread:
            messagebox.showerror("Error", "Thread not found")
            return

        # Increment view count
        try:
            CommHubManager.increment_view_count(thread_id)
        except Exception:
            pass

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Thread: {thread.get('title', '')}")
        dialog.geometry("750x650")
        dialog.transient(self.root)

        # Scrollable content
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Thread details
        details_frame = ttk.LabelFrame(scroll_frame, text="Thread Details", padding=15)
        details_frame.pack(fill=tk.X, padx=10, pady=10)

        fields = [
            ('Title', thread.get('title', '')),
            ('Author', thread.get('author_id', '')),
            ('Created', thread.get('created_at', '')),
            ('Replies', thread.get('reply_count', 0)),
            ('Views', thread.get('view_count', 0)),
            ('Pinned', 'Yes' if thread.get('is_pinned') else 'No'),
            ('Locked', 'Yes' if thread.get('is_locked') else 'No'),
        ]

        for i, (label, value) in enumerate(fields):
            ttk.Label(details_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='ne', padx=(10, 5), pady=4)
            ttk.Label(details_frame, text=str(value), wraplength=500).grid(
                row=i, column=1, sticky='nw', padx=(5, 10), pady=4)

        # Thread content
        content_frame = ttk.LabelFrame(scroll_frame, text="Content", padding=10)
        content_frame.pack(fill=tk.X, padx=10, pady=10)

        content_text = tk.Text(content_frame, wrap=tk.WORD, height=6, state=tk.NORMAL)
        content_text.insert("1.0", thread.get('content', ''))
        content_text.config(state=tk.DISABLED)
        content_text.pack(fill=tk.X)

        # Replies section
        replies_frame = ttk.LabelFrame(scroll_frame, text="Replies", padding=10)
        replies_frame.pack(fill=tk.X, padx=10, pady=10)

        try:
            replies = CommHubManager.get_replies(thread_id)
        except Exception:
            replies = []

        if replies:
            replies_tree_frame = ttk.Frame(replies_frame)
            replies_tree_frame.pack(fill=tk.X)

            y_scroll = ttk.Scrollbar(replies_tree_frame, orient=tk.VERTICAL)
            reply_columns = ('ID', 'Content', 'Author', 'Date', 'Solution')
            replies_tree = ttk.Treeview(
                replies_tree_frame, columns=reply_columns, show='headings',
                yscrollcommand=y_scroll.set, height=8)
            y_scroll.config(command=replies_tree.yview)

            reply_widths = {'ID': 50, 'Content': 300, 'Author': 100, 'Date': 150, 'Solution': 70}
            for col in reply_columns:
                replies_tree.heading(col, text=col)
                replies_tree.column(col, width=reply_widths.get(col, 100))

            # Color tags for replies
            replies_tree.tag_configure('solution', background='#d4edda')
            replies_tree.tag_configure('normal', background='#ffffff')

            for r in replies:
                is_solution = r.get('is_solution', 0)
                tag = 'solution' if is_solution else 'normal'
                replies_tree.insert('', tk.END, iid=str(r.get('reply_id')), values=(
                    r.get('reply_id', ''),
                    r.get('content', '')[:80],
                    r.get('author_id', ''),
                    r.get('created_at', ''),
                    'Yes' if is_solution else 'No'
                ), tags=(tag,))

            replies_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
            y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

            # Mark Solution button
            reply_btn_frame = ttk.Frame(replies_frame)
            reply_btn_frame.pack(fill=tk.X, pady=5)

            def mark_solution():
                sel = replies_tree.selection()
                if not sel:
                    messagebox.showinfo("Info", "Please select a reply to mark as solution.",
                                        parent=dialog)
                    return

                reply_id = int(sel[0])
                if not messagebox.askyesno("Confirm",
                                           "Mark this reply as the solution?",
                                           parent=dialog):
                    return

                try:
                    CommHubManager.mark_solution(reply_id)
                    messagebox.showinfo("Success", "Reply marked as solution.", parent=dialog)
                    dialog.destroy()
                    self._open_thread_detail_dialog(thread_id)
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=dialog)

            ttk.Button(reply_btn_frame, text="Mark Solution",
                       command=mark_solution).pack(side=tk.LEFT, padx=5)
        else:
            ttk.Label(replies_frame, text="No replies yet.").pack(anchor='w')

        # Add Reply section
        if not thread.get('is_locked'):
            add_reply_frame = ttk.LabelFrame(scroll_frame, text="Add Reply", padding=10)
            add_reply_frame.pack(fill=tk.X, padx=10, pady=10)

            reply_text = scrolledtext.ScrolledText(add_reply_frame, wrap=tk.WORD,
                                                   width=70, height=4)
            reply_text.pack(fill=tk.X, pady=5)

            def submit_reply():
                content = reply_text.get("1.0", "end-1c").strip()
                if not content:
                    messagebox.showerror("Validation Error", "Reply content is required.",
                                         parent=dialog)
                    return

                try:
                    reply_id = CommHubManager.add_reply(
                        thread_id=thread_id,
                        content=content,
                        author_id=self._get_user_id()
                    )
                    messagebox.showinfo("Success",
                                        f"Reply added. ID: {reply_id}",
                                        parent=dialog)
                    dialog.destroy()
                    self._open_thread_detail_dialog(thread_id)
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=dialog)

            ttk.Button(add_reply_frame, text="Submit Reply",
                       command=submit_reply).pack(side=tk.LEFT, padx=5)

        # Close button
        btn_frame = ttk.Frame(scroll_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=15)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # ==================== TAB 3: POLLS & SURVEYS ====================

    def _create_polls_tab(self):
        """Create polls and surveys tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Polls & Surveys")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Polls & Surveys", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Create Poll",
                   command=self._open_create_poll_dialog).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Refresh",
                   command=self._load_polls).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="View/Vote",
                   command=self._view_vote_poll).pack(side=tk.RIGHT, padx=5)

        # Polls treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        polls_columns = ('ID', 'Title', 'Type', 'Status', 'Votes', 'Created By')
        self.polls_tree = ttk.Treeview(
            tree_frame, columns=polls_columns, show='headings',
            yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.polls_tree.yview)

        polls_widths = {'ID': 50, 'Title': 250, 'Type': 120, 'Status': 80,
                        'Votes': 70, 'Created By': 120}
        for col in polls_columns:
            self.polls_tree.heading(col, text=col)
            self.polls_tree.column(col, width=polls_widths.get(col, 100))

        self.polls_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.polls_tree.tag_configure('open', background='#d4edda')
        self.polls_tree.tag_configure('closed', background='#e2e3e5')

        # Store poll cache
        self._polls_cache = {}

        self._load_polls()

    def _load_polls(self):
        """Load all polls."""
        for item in self.polls_tree.get_children():
            self.polls_tree.delete(item)

        self._polls_cache = {}

        try:
            polls = CommHubManager.get_polls()
        except Exception:
            polls = []

        for p in polls:
            poll_id = p.get('poll_id')
            status = p.get('status', '').lower()
            display_type = p.get('poll_type', '').replace('_', ' ').title()
            display_status = status.replace('_', ' ').title()

            # Get vote count from results
            total_votes = 0
            try:
                results = CommHubManager.get_poll_results(poll_id)
                total_votes = results.get('total_votes', 0)
            except Exception:
                pass

            self.polls_tree.insert('', tk.END, iid=str(poll_id), values=(
                poll_id,
                p.get('title', '')[:50],
                display_type,
                display_status,
                total_votes,
                p.get('created_by', '')
            ), tags=(status,))

            self._polls_cache[str(poll_id)] = p

    def _view_vote_poll(self):
        """Open poll detail/vote dialog for the selected poll."""
        selection = self.polls_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a poll first.")
            return

        poll_id = int(selection[0])
        self._open_poll_detail_dialog(poll_id)

    def _open_poll_detail_dialog(self, poll_id):
        """Open dialog to view and vote on a poll."""
        try:
            results = CommHubManager.get_poll_results(poll_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load poll: {e}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Poll: {results.get('title', '')}")
        dialog.geometry("600x550")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Poll info
        info_frame = ttk.LabelFrame(frame, text="Poll Information", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        poll_type = results.get('poll_type', '')
        display_type = poll_type.replace('_', ' ').title()
        status = results.get('status', '').replace('_', ' ').title()
        is_anon = 'Yes' if results.get('is_anonymous') else 'No'

        info_fields = [
            ('Title', results.get('title', '')),
            ('Description', results.get('description', '') or 'No description'),
            ('Type', display_type),
            ('Status', status),
            ('Anonymous', is_anon),
            ('Closes At', results.get('closes_at', '') or 'No expiration'),
            ('Total Votes', results.get('total_votes', 0)),
        ]

        for i, (label, value) in enumerate(info_fields):
            ttk.Label(info_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='ne', padx=(10, 5), pady=3)
            ttk.Label(info_frame, text=str(value), wraplength=400).grid(
                row=i, column=1, sticky='nw', padx=(5, 10), pady=3)

        options = results.get('options', [])

        # Voting section (only if poll is open)
        if results.get('status', '').lower() == 'open':
            vote_frame = ttk.LabelFrame(frame, text="Cast Your Vote", padding=10)
            vote_frame.pack(fill=tk.X, pady=(0, 10))

            if poll_type == 'single_choice':
                vote_var = tk.IntVar(value=-1)
                for opt in options:
                    ttk.Radiobutton(
                        vote_frame,
                        text=opt.get('option_text', ''),
                        variable=vote_var,
                        value=opt.get('option_id')
                    ).pack(anchor='w', padx=10, pady=2)

                def cast_single():
                    selected_option = vote_var.get()
                    if selected_option == -1:
                        messagebox.showinfo("Info", "Please select an option.",
                                            parent=dialog)
                        return

                    if not messagebox.askyesno("Confirm", "Cast your vote?",
                                               parent=dialog):
                        return

                    try:
                        CommHubManager.cast_poll_vote(
                            poll_id=poll_id,
                            option_id=selected_option,
                            voter_id=self._get_user_id()
                        )
                        messagebox.showinfo("Success", "Your vote has been cast.",
                                            parent=dialog)
                        dialog.destroy()
                        self._load_polls()
                    except ValueError as e:
                        messagebox.showwarning("Warning", str(e), parent=dialog)
                    except Exception as e:
                        messagebox.showerror("Error", str(e), parent=dialog)

                ttk.Button(vote_frame, text="Vote",
                           command=cast_single).pack(pady=10)

            elif poll_type == 'multiple_choice':
                check_vars = {}
                for opt in options:
                    var = tk.BooleanVar(value=False)
                    check_vars[opt.get('option_id')] = var
                    ttk.Checkbutton(
                        vote_frame,
                        text=opt.get('option_text', ''),
                        variable=var
                    ).pack(anchor='w', padx=10, pady=2)

                def cast_multiple():
                    selected_ids = [oid for oid, var in check_vars.items() if var.get()]
                    if not selected_ids:
                        messagebox.showinfo("Info", "Please select at least one option.",
                                            parent=dialog)
                        return

                    if not messagebox.askyesno("Confirm",
                                               f"Cast votes for {len(selected_ids)} option(s)?",
                                               parent=dialog):
                        return

                    try:
                        for option_id in selected_ids:
                            CommHubManager.cast_poll_vote(
                                poll_id=poll_id,
                                option_id=option_id,
                                voter_id=self._get_user_id()
                            )
                        messagebox.showinfo("Success", "Your votes have been cast.",
                                            parent=dialog)
                        dialog.destroy()
                        self._load_polls()
                    except ValueError as e:
                        messagebox.showwarning("Warning", str(e), parent=dialog)
                    except Exception as e:
                        messagebox.showerror("Error", str(e), parent=dialog)

                ttk.Button(vote_frame, text="Vote",
                           command=cast_multiple).pack(pady=10)

            elif poll_type == 'rating':
                # For rating polls, show radio buttons for each option
                vote_var = tk.IntVar(value=-1)
                for opt in options:
                    ttk.Radiobutton(
                        vote_frame,
                        text=opt.get('option_text', ''),
                        variable=vote_var,
                        value=opt.get('option_id')
                    ).pack(anchor='w', padx=10, pady=2)

                def cast_rating():
                    selected_option = vote_var.get()
                    if selected_option == -1:
                        messagebox.showinfo("Info", "Please select a rating.",
                                            parent=dialog)
                        return

                    if not messagebox.askyesno("Confirm", "Submit your rating?",
                                               parent=dialog):
                        return

                    try:
                        CommHubManager.cast_poll_vote(
                            poll_id=poll_id,
                            option_id=selected_option,
                            voter_id=self._get_user_id()
                        )
                        messagebox.showinfo("Success", "Your rating has been submitted.",
                                            parent=dialog)
                        dialog.destroy()
                        self._load_polls()
                    except ValueError as e:
                        messagebox.showwarning("Warning", str(e), parent=dialog)
                    except Exception as e:
                        messagebox.showerror("Error", str(e), parent=dialog)

                ttk.Button(vote_frame, text="Submit Rating",
                           command=cast_rating).pack(pady=10)

        # Results section
        results_frame = ttk.LabelFrame(frame, text="Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        for opt in options:
            row_frame = ttk.Frame(results_frame)
            row_frame.pack(fill=tk.X, pady=3)
            ttk.Label(row_frame, text=f"{opt.get('option_text', '')}:",
                      width=30, anchor='w').pack(side=tk.LEFT, padx=5)
            ttk.Label(row_frame, text=str(opt.get('vote_count', 0)),
                      font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)

        total_label = ttk.Label(results_frame,
                                text=f"Total votes: {results.get('total_votes', 0)}",
                                font=('Arial', 10, 'bold'))
        total_label.pack(anchor='w', padx=5, pady=(10, 0))

        # Close button
        ttk.Button(frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5, pady=10)

    def _open_create_poll_dialog(self):
        """Open dialog to create a new poll."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Poll")
        dialog.geometry("600x600")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Forum selector
        ttk.Label(frame, text="Forum:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        forum_combo = ttk.Combobox(frame, width=35, state='readonly')
        forum_combo.grid(row=0, column=1, padx=10, pady=8)

        forum_map = {}
        try:
            forums = CommHubManager.get_forums()
        except Exception:
            forums = []

        combo_values = []
        for f in forums:
            fid = f.get('forum_id')
            label = f"{f.get('name', '')} (#{fid})"
            combo_values.append(label)
            forum_map[label] = fid
        forum_combo['values'] = combo_values
        if combo_values:
            forum_combo.current(0)

        # Title
        ttk.Label(frame, text="Title:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        title_entry = ttk.Entry(frame, width=40)
        title_entry.grid(row=1, column=1, padx=10, pady=8)

        # Description
        ttk.Label(frame, text="Description:").grid(row=2, column=0, sticky='ne', padx=10, pady=8)
        desc_text = tk.Text(frame, width=38, height=3)
        desc_text.grid(row=2, column=1, padx=10, pady=8)

        # Type
        ttk.Label(frame, text="Type:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        type_combo = ttk.Combobox(
            frame, values=['single_choice', 'multiple_choice', 'rating'],
            width=20, state='readonly'
        )
        type_combo.set('single_choice')
        type_combo.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Anonymous
        anon_var = tk.BooleanVar(value=False)
        ttk.Label(frame, text="Anonymous:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        ttk.Checkbutton(frame, variable=anon_var,
                        text="Anonymous voting").grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Closes at
        ttk.Label(frame, text="Closes At\n(YYYY-MM-DD):").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        closes_entry = ttk.Entry(frame, width=15)
        closes_entry.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Options management
        ttk.Label(frame, text="Options:").grid(row=6, column=0, sticky='ne', padx=10, pady=8)
        options_frame = ttk.Frame(frame)
        options_frame.grid(row=6, column=1, padx=10, pady=8, sticky='w')

        options_listbox = tk.Listbox(options_frame, width=35, height=6)
        options_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        options_btn_frame = ttk.Frame(options_frame)
        options_btn_frame.pack(side=tk.LEFT, padx=5)

        option_entry = ttk.Entry(options_btn_frame, width=20)
        option_entry.pack(pady=2)

        def add_option():
            text = option_entry.get().strip()
            if text:
                options_listbox.insert(tk.END, text)
                option_entry.delete(0, tk.END)
            else:
                messagebox.showinfo("Info", "Enter option text first.", parent=dialog)

        def remove_option():
            sel = options_listbox.curselection()
            if sel:
                options_listbox.delete(sel[0])
            else:
                messagebox.showinfo("Info", "Select an option to remove.", parent=dialog)

        ttk.Button(options_btn_frame, text="Add", command=add_option).pack(pady=2, fill=tk.X)
        ttk.Button(options_btn_frame, text="Remove", command=remove_option).pack(pady=2, fill=tk.X)

        def save():
            try:
                forum_label = validate_combobox(forum_combo, "Forum")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            selected_forum_id = forum_map.get(forum_label)
            if not selected_forum_id:
                messagebox.showerror("Error", "Please select a valid forum.", parent=dialog)
                return

            try:
                title = validate_entry(title_entry, "Title")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            description = desc_text.get("1.0", "end-1c").strip()

            try:
                poll_type = validate_combobox(type_combo, "Type")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            # Get options
            options = list(options_listbox.get(0, tk.END))
            if len(options) < 2:
                messagebox.showerror("Validation Error",
                                     "At least 2 options are required.",
                                     parent=dialog)
                return

            closes_at = closes_entry.get().strip() or None
            if closes_at:
                try:
                    datetime.strptime(closes_at, '%Y-%m-%d')
                    closes_at = closes_at + "T23:59:59"
                except ValueError:
                    messagebox.showerror("Validation Error",
                                         "Closes At must be in YYYY-MM-DD format.",
                                         parent=dialog)
                    return

            # Create a thread for the poll first
            try:
                thread_id = CommHubManager.create_thread(
                    forum_id=selected_forum_id,
                    title=f"[Poll] {title}",
                    content=description or f"Poll: {title}",
                    author_id=self._get_user_id()
                )
            except Exception as e:
                messagebox.showerror("Error", f"Could not create poll thread: {e}",
                                     parent=dialog)
                return

            try:
                poll_id = CommHubManager.create_poll(
                    forum_id=selected_forum_id,
                    thread_id=thread_id,
                    title=title,
                    description=description,
                    poll_type=poll_type,
                    is_anonymous=anon_var.get(),
                    allow_comments=True,
                    closes_at=closes_at,
                    created_by=self._get_user_id(),
                    options=options
                )
                messagebox.showinfo("Success",
                                    f"Poll created. ID: {poll_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_polls()
                self._load_dashboard()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Create Poll", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        title_entry.focus_set()

    # ==================== TAB 4: FORUM ADMIN ====================

    def _create_forum_admin_tab(self):
        """Create forum admin tab (admin only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Forum Admin")

        # Scrollable content
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Forum CRUD Section ----
        crud_frame = ttk.LabelFrame(scroll_frame, text="Create Forum", padding=15)
        crud_frame.pack(fill=tk.X, padx=10, pady=10)

        # Name
        ttk.Label(crud_frame, text="Name:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.admin_forum_name_entry = ttk.Entry(crud_frame, width=35)
        self.admin_forum_name_entry.grid(row=0, column=1, columnspan=2, padx=10, pady=8, sticky='w')

        # Description
        ttk.Label(crud_frame, text="Description:").grid(row=1, column=0, sticky='ne', padx=10, pady=8)
        self.admin_forum_desc_text = tk.Text(crud_frame, width=40, height=3)
        self.admin_forum_desc_text.grid(row=1, column=1, columnspan=2, padx=10, pady=8, sticky='w')

        # Type
        ttk.Label(crud_frame, text="Type:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        self.admin_forum_type_combo = ttk.Combobox(
            crud_frame, values=['department', 'topic', 'project', 'social'],
            width=20, state='readonly'
        )
        self.admin_forum_type_combo.set('department')
        self.admin_forum_type_combo.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Department
        ttk.Label(crud_frame, text="Department:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        self.admin_forum_dept_entry = ttk.Entry(crud_frame, width=25)
        self.admin_forum_dept_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Visibility
        ttk.Label(crud_frame, text="Visibility:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        self.admin_forum_vis_combo = ttk.Combobox(
            crud_frame, values=['public', 'members_only', 'private'],
            width=20, state='readonly'
        )
        self.admin_forum_vis_combo.set('public')
        self.admin_forum_vis_combo.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Create button
        ttk.Button(crud_frame, text="Create Forum",
                   command=self._create_forum).grid(row=5, column=1, padx=10, pady=15, sticky='w')

        # ---- Members Management Section ----
        members_frame = ttk.LabelFrame(scroll_frame, text="Manage Forum Members", padding=15)
        members_frame.pack(fill=tk.X, padx=10, pady=10)

        # Forum selector
        selector_row = ttk.Frame(members_frame)
        selector_row.pack(fill=tk.X, pady=5)
        ttk.Label(selector_row, text="Forum:").pack(side=tk.LEFT, padx=5)
        self.admin_forum_combo = ttk.Combobox(selector_row, width=35, state='readonly')
        self.admin_forum_combo.pack(side=tk.LEFT, padx=5)
        self.admin_forum_combo.bind('<<ComboboxSelected>>', lambda e: self._load_admin_forum_members())
        ttk.Button(selector_row, text="Refresh",
                   command=self._refresh_admin_forums).pack(side=tk.LEFT, padx=5)

        # Store forum mapping for admin
        self.admin_forum_map = {}

        # Add member controls
        add_row = ttk.Frame(members_frame)
        add_row.pack(fill=tk.X, pady=10)
        ttk.Label(add_row, text="User ID:").pack(side=tk.LEFT, padx=5)
        self.admin_member_user_entry = ttk.Entry(add_row, width=20)
        self.admin_member_user_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(add_row, text="Role:").pack(side=tk.LEFT, padx=5)
        self.admin_member_role_combo = ttk.Combobox(
            add_row, values=['moderator', 'member'],
            width=12, state='readonly'
        )
        self.admin_member_role_combo.set('member')
        self.admin_member_role_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(add_row, text="Add Member",
                   command=self._add_forum_member).pack(side=tk.LEFT, padx=5)
        ttk.Button(add_row, text="Remove Selected",
                   command=self._remove_forum_member).pack(side=tk.LEFT, padx=5)

        # Members treeview
        tree_frame = ttk.Frame(members_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        mem_columns = ('User ID', 'Role', 'Joined')
        self.admin_forum_members_tree = ttk.Treeview(
            tree_frame, columns=mem_columns, show='headings',
            yscrollcommand=y_scroll.set, height=6)
        y_scroll.config(command=self.admin_forum_members_tree.yview)

        mem_widths = {'User ID': 200, 'Role': 120, 'Joined': 200}
        for col in mem_columns:
            self.admin_forum_members_tree.heading(col, text=col)
            self.admin_forum_members_tree.column(col, width=mem_widths.get(col, 100))

        self.admin_forum_members_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Pin/Unpin Messages Section ----
        pin_frame = ttk.LabelFrame(scroll_frame, text="Pin/Unpin Messages", padding=15)
        pin_frame.pack(fill=tk.X, padx=10, pady=10)

        # Pin controls
        pin_controls = ttk.Frame(pin_frame)
        pin_controls.pack(fill=tk.X, pady=5)

        ttk.Label(pin_controls, text="Message Type:").pack(side=tk.LEFT, padx=5)
        self.pin_type_combo = ttk.Combobox(
            pin_controls, values=['thread', 'reply'],
            width=12, state='readonly'
        )
        self.pin_type_combo.set('thread')
        self.pin_type_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(pin_controls, text="Message ID:").pack(side=tk.LEFT, padx=5)
        self.pin_message_id_entry = ttk.Entry(pin_controls, width=10)
        self.pin_message_id_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(pin_controls, text="Expires (YYYY-MM-DD):").pack(side=tk.LEFT, padx=5)
        self.pin_expires_entry = ttk.Entry(pin_controls, width=12)
        self.pin_expires_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(pin_controls, text="Pin Message",
                   command=self._pin_message).pack(side=tk.LEFT, padx=5)

        # Pinned messages list
        pin_tree_frame = ttk.Frame(pin_frame)
        pin_tree_frame.pack(fill=tk.X, pady=5)

        y_scroll2 = ttk.Scrollbar(pin_tree_frame, orient=tk.VERTICAL)
        pin_columns = ('Pin ID', 'Type', 'Message ID', 'Pinned By', 'Expires At')
        self.admin_pinned_tree = ttk.Treeview(
            pin_tree_frame, columns=pin_columns, show='headings',
            yscrollcommand=y_scroll2.set, height=5)
        y_scroll2.config(command=self.admin_pinned_tree.yview)

        pin_widths = {'Pin ID': 60, 'Type': 100, 'Message ID': 100,
                      'Pinned By': 150, 'Expires At': 180}
        for col in pin_columns:
            self.admin_pinned_tree.heading(col, text=col)
            self.admin_pinned_tree.column(col, width=pin_widths.get(col, 100))

        self.admin_pinned_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        y_scroll2.pack(side=tk.RIGHT, fill=tk.Y)

        unpin_btn_frame = ttk.Frame(pin_frame)
        unpin_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(unpin_btn_frame, text="Unpin Selected",
                   command=self._unpin_message).pack(side=tk.LEFT, padx=5)
        ttk.Button(unpin_btn_frame, text="Refresh Pins",
                   command=self._load_admin_pinned_messages).pack(side=tk.LEFT, padx=5)

        # Load initial data
        self._refresh_admin_forums()
        self._load_admin_pinned_messages()

    def _refresh_admin_forums(self):
        """Refresh the forum list in admin panel."""
        self.admin_forum_map = {}

        try:
            forums = CommHubManager.get_forums()
        except Exception:
            forums = []

        display_values = []
        for f in forums:
            label = f"{f.get('name', '')} (#{f.get('forum_id')})"
            display_values.append(label)
            self.admin_forum_map[label] = f.get('forum_id')

        self.admin_forum_combo['values'] = display_values
        if display_values:
            self.admin_forum_combo.set(display_values[0])
            self._load_admin_forum_members()
        else:
            self.admin_forum_combo.set('')
            for item in self.admin_forum_members_tree.get_children():
                self.admin_forum_members_tree.delete(item)

    def _get_admin_selected_forum_id(self):
        """Get the forum ID from the admin forum combo selection."""
        selected = self.admin_forum_combo.get()
        return self.admin_forum_map.get(selected)

    def _load_admin_forum_members(self):
        """Load members for the selected forum in admin panel."""
        for item in self.admin_forum_members_tree.get_children():
            self.admin_forum_members_tree.delete(item)

        forum_id = self._get_admin_selected_forum_id()
        if not forum_id:
            return

        try:
            members = CommHubManager.get_forum_members(forum_id)
        except Exception:
            members = []

        for m in members:
            self.admin_forum_members_tree.insert('', tk.END, values=(
                m.get('user_id', ''),
                m.get('role', '').replace('_', ' ').title(),
                m.get('joined_at', '')
            ))

    def _create_forum(self):
        """Create a new forum from the admin form."""
        try:
            name = validate_entry(self.admin_forum_name_entry, "Name")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        description = self.admin_forum_desc_text.get("1.0", "end-1c").strip()
        if not description:
            messagebox.showerror("Validation Error", "Description is required.")
            return

        try:
            forum_type = validate_combobox(self.admin_forum_type_combo, "Type")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            department = validate_entry(self.admin_forum_dept_entry, "Department")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            visibility = validate_combobox(self.admin_forum_vis_combo, "Visibility")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            forum_id = CommHubManager.create_forum(
                name=name,
                description=description,
                forum_type=forum_type,
                department=department,
                visibility=visibility,
                created_by=self._get_user_id()
            )
            messagebox.showinfo("Success", f"Forum created. ID: {forum_id}")
            # Clear form
            self.admin_forum_name_entry.delete(0, tk.END)
            self.admin_forum_desc_text.delete("1.0", tk.END)
            self.admin_forum_type_combo.set('department')
            self.admin_forum_dept_entry.delete(0, tk.END)
            self.admin_forum_vis_combo.set('public')
            # Refresh
            self._refresh_admin_forums()
            self._load_forums()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _add_forum_member(self):
        """Add a member to the selected forum."""
        forum_id = self._get_admin_selected_forum_id()
        if not forum_id:
            messagebox.showinfo("Info", "Please select a forum first.")
            return

        try:
            user_id = validate_entry(self.admin_member_user_entry, "User ID")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            role = validate_combobox(self.admin_member_role_combo, "Role")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            member_id = CommHubManager.add_forum_member(
                forum_id=forum_id,
                user_id=user_id,
                role=role
            )
            messagebox.showinfo("Success", f"Member added. ID: {member_id}")
            self.admin_member_user_entry.delete(0, tk.END)
            self._load_admin_forum_members()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _remove_forum_member(self):
        """Remove the selected member from the forum."""
        selection = self.admin_forum_members_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a member to remove.")
            return

        forum_id = self._get_admin_selected_forum_id()
        if not forum_id:
            messagebox.showinfo("Info", "Please select a forum first.")
            return

        item = self.admin_forum_members_tree.item(selection[0])
        user_id = item['values'][0]

        if not messagebox.askyesno("Confirm",
                                    f"Remove member '{user_id}' from this forum?"):
            return

        try:
            CommHubManager.remove_forum_member(
                forum_id=forum_id,
                user_id=str(user_id)
            )
            messagebox.showinfo("Success", "Member removed.")
            self._load_admin_forum_members()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _pin_message(self):
        """Pin a message from the admin panel."""
        try:
            message_type = validate_combobox(self.pin_type_combo, "Message Type")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        message_id_str = self.pin_message_id_entry.get().strip()
        if not message_id_str:
            messagebox.showerror("Validation Error", "Message ID is required.")
            return

        try:
            message_id = int(message_id_str)
        except ValueError:
            messagebox.showerror("Validation Error", "Message ID must be a number.")
            return

        expires_at = self.pin_expires_entry.get().strip() or None
        if expires_at:
            try:
                datetime.strptime(expires_at, '%Y-%m-%d')
                expires_at = expires_at + "T23:59:59"
            except ValueError:
                messagebox.showerror("Validation Error",
                                     "Expires date must be in YYYY-MM-DD format.")
                return

        try:
            pin_id = CommHubManager.pin_message(
                message_type=message_type,
                message_id=message_id,
                pinned_by=self._get_user_id(),
                expires_at=expires_at
            )
            messagebox.showinfo("Success", f"Message pinned. Pin ID: {pin_id}")
            self.pin_message_id_entry.delete(0, tk.END)
            self.pin_expires_entry.delete(0, tk.END)
            self._load_admin_pinned_messages()
            self._load_dashboard()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _unpin_message(self):
        """Unpin the selected pinned message."""
        selection = self.admin_pinned_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a pinned message to unpin.")
            return

        item = self.admin_pinned_tree.item(selection[0])
        pin_id = item['values'][0]

        if not messagebox.askyesno("Confirm",
                                    f"Unpin message (Pin ID: {pin_id})?"):
            return

        try:
            CommHubManager.unpin_message(pin_id)
            messagebox.showinfo("Success", "Message unpinned.")
            self._load_admin_pinned_messages()
            self._load_dashboard()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_admin_pinned_messages(self):
        """Load pinned messages into the admin pinned tree."""
        for item in self.admin_pinned_tree.get_children():
            self.admin_pinned_tree.delete(item)

        try:
            pinned = CommHubManager.get_pinned_messages()
        except Exception:
            pinned = []

        for p in pinned:
            self.admin_pinned_tree.insert('', tk.END, values=(
                p.get('pin_id', ''),
                p.get('message_type', '').replace('_', ' ').title(),
                p.get('message_id', ''),
                p.get('pinned_by', ''),
                p.get('expires_at', '') or 'Never'
            ))

    # ==================== TAB 5: SEARCH ====================

    def _create_search_tab(self):
        """Create search tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Search")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Search", style='Header.TLabel').pack(side=tk.LEFT)

        # Search controls
        search_frame = ttk.Frame(tab)
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(search_frame, text="Query:").pack(side=tk.LEFT, padx=5)
        self.search_entry = ttk.Entry(search_frame, width=50)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind('<Return>', lambda e: self._perform_search())
        ttk.Button(search_frame, text="Search",
                   command=self._perform_search).pack(side=tk.LEFT, padx=5)

        # Results treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        search_columns = ('Type', 'Title/Content Preview', 'Author', 'Forum', 'Date')
        self.search_tree = ttk.Treeview(
            tree_frame, columns=search_columns, show='headings',
            yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.search_tree.yview)

        search_widths = {'Type': 80, 'Title/Content Preview': 350, 'Author': 120,
                         'Forum': 150, 'Date': 160}
        for col in search_columns:
            self.search_tree.heading(col, text=col)
            self.search_tree.column(col, width=search_widths.get(col, 100))

        self.search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Color tags for result types
        self.search_tree.tag_configure('thread', background='#cce5ff')
        self.search_tree.tag_configure('reply', background='#e2e3e5')

        # Status label
        self.search_status_label = ttk.Label(tab, text="Enter a query and click Search.",
                                             font=('Arial', 10))
        self.search_status_label.pack(fill=tk.X, padx=10, pady=(0, 10))

    def _perform_search(self):
        """Perform search and display results."""
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showinfo("Info", "Please enter a search query.")
            return

        for item in self.search_tree.get_children():
            self.search_tree.delete(item)

        try:
            results = CommHubManager.search_all(query)
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {e}")
            return

        threads = results.get('threads', [])
        replies = results.get('replies', [])

        # Build forum name map
        forum_names = {}
        try:
            forums = CommHubManager.get_forums()
            for f in forums:
                forum_names[f.get('forum_id')] = f.get('name', '')
        except Exception:
            pass

        # Build thread forum map for replies
        thread_forum_map = {}
        for t in threads:
            thread_forum_map[t.get('thread_id')] = t.get('forum_id')

        # Also look up forum_id for reply threads not in search results
        reply_thread_ids = set()
        for r in replies:
            tid = r.get('thread_id')
            if tid not in thread_forum_map:
                reply_thread_ids.add(tid)

        for tid in reply_thread_ids:
            try:
                t = CommHubManager.get_thread(tid)
                if t:
                    thread_forum_map[tid] = t.get('forum_id')
            except Exception:
                pass

        total_results = 0

        # Insert threads
        for t in threads:
            forum_id = t.get('forum_id')
            forum_name = forum_names.get(forum_id, str(forum_id))
            self.search_tree.insert('', tk.END, values=(
                'Thread',
                t.get('title', '')[:60],
                t.get('author_id', ''),
                forum_name,
                t.get('created_at', '')
            ), tags=('thread',))
            total_results += 1

        # Insert replies
        for r in replies:
            tid = r.get('thread_id')
            forum_id = thread_forum_map.get(tid)
            forum_name = forum_names.get(forum_id, str(forum_id) if forum_id else '')
            self.search_tree.insert('', tk.END, values=(
                'Reply',
                r.get('content', '')[:60],
                r.get('author_id', ''),
                forum_name,
                r.get('created_at', '')
            ), tags=('reply',))
            total_results += 1

        self.search_status_label.config(
            text=f"Found {total_results} result(s): "
                 f"{len(threads)} thread(s), {len(replies)} reply/replies."
        )
