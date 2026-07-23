import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
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
    from education_system.post_18.university_system.infrastructure.database.db import get_connection
    from education_system.post_18.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False

# Import support dialog classes
from education_system.post_18.university_system.modules.domain.student_affairs.gui.student_union_gui.support.wellness import WellnessResourcesDialog, CrisisResourcesDialog
from education_system.post_18.university_system.modules.domain.student_affairs.gui.student_union_gui.support.support_groups import CreateSupportGroupDialog, MySupportGroupsDialog, BrowseSupportGroupsDialog


class PeerSupportWellnessDialog:
    """Main hub for peer support and wellness features"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Peer Support & Wellness")
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="🤝 Peer Support & Wellness Hub",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Info banner
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill='x', pady=(0, 15))

        info_text = ("Access peer support, join support groups, find wellness resources, "
                    "and connect with others in a safe, confidential environment.")
        ttk.Label(info_frame, text=info_text, wraplength=1000,
                 justify='left', font=('Arial', 10)).pack(padx=10, pady=10)

        # Create grid of support options
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill='both', expand=True, pady=(0, 10))

        options = [
            ("Support Groups", "browse", "📋 Browse and join support groups", "blue"),
            ("My Groups", "my_groups", "👥 View my support group memberships", "green"),
            ("Create Group", "create", "➕ Create a new support group", "orange"),
            ("Peer Matching", "matching", "🤝 Anonymous peer support matching", "purple"),
            ("Wellness Resources", "resources", "📚 Mental health & wellness resources", "teal"),
            ("Crisis Support", "crisis", "🆘 Immediate crisis resources", "red"),
            ("Group Management", "manage", "⚙️ Manage my support groups", "gray")
        ]

        for i, (title, key, description, color) in enumerate(options):
            card = ttk.LabelFrame(buttons_frame, text=title)
            card.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='nsew')

            ttk.Label(card, text=description, wraplength=450,
                     foreground=color).pack(padx=10, pady=5)

            command_map = {
                'browse': self.browse_support_groups,
                'my_groups': self.view_my_support_groups,
                'create': self.create_support_group,
                'matching': self.anonymous_peer_matching,
                'resources': self.view_wellness_resources,
                'crisis': self.crisis_resources,
                'manage': self.manage_peer_support_system
            }

            ttk.Button(card, text="Open",
                      command=command_map[key]).pack(padx=10, pady=5)

        for i in range(4):
            buttons_frame.rowconfigure(i, weight=1)
        for i in range(2):
            buttons_frame.columnconfigure(i, weight=1)

        # Confidentiality notice
        notice_frame = ttk.LabelFrame(main_frame, text="⚠️ Confidentiality & Privacy")
        notice_frame.pack(fill='x', pady=(10, 10))

        notice_text = ("All peer support activities are confidential. If you're experiencing a mental health "
                      "crisis, please contact emergency services or use the Crisis Support button above.")
        ttk.Label(notice_frame, text=notice_text, wraplength=1000,
                 foreground='red').pack(padx=10, pady=8)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def browse_support_groups(self):
        dialog = BrowseSupportGroupsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def view_my_support_groups(self):
        dialog = MySupportGroupsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def create_support_group(self):
        dialog = CreateSupportGroupDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def anonymous_peer_matching(self):
        dialog = AnonymousPeerMatchingDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def view_wellness_resources(self):
        dialog = WellnessResourcesDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def crisis_resources(self):
        dialog = CrisisResourcesDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def manage_peer_support_system(self):
        dialog = ManagePeerSupportDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



class AnonymousPeerMatchingDialog:
    """Anonymous peer matching system"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Anonymous Peer Matching")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🤝 Anonymous Peer Support Matching",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Info banner
        info_frame = ttk.LabelFrame(main_frame, text="How It Works")
        info_frame.pack(fill='x', pady=(0, 15))

        info_text = ("Get matched with peers facing similar challenges. All matches are anonymous "
                    "and confidential. Connect through secure messaging without revealing identities.")
        ttk.Label(info_frame, text=info_text, wraplength=850).pack(padx=10, pady=10)

        # Matching preferences
        pref_frame = ttk.LabelFrame(main_frame, text="Matching Preferences")
        pref_frame.pack(fill='both', expand=True, pady=(0, 15))

        pref_content = ttk.Frame(pref_frame)
        pref_content.pack(fill='both', expand=True, padx=10, pady=10)

        # Issue/interest
        ttk.Label(pref_content, text="What would you like support with?").grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 5))

        issues = ['Stress & Anxiety', 'Academic Pressure', 'Loneliness/Social Connection',
                 'Family Issues', 'Relationship Concerns', 'Self-Esteem', 'Life Transitions']

        self.issue_vars = {}
        for i, issue in enumerate(issues):
            var = tk.BooleanVar(value=False)
            self.issue_vars[issue] = var
            ttk.Checkbutton(pref_content, text=issue, variable=var).grid(
                row=i+1, column=0, sticky='w', padx=(20, 0))

        # Match type
        ttk.Label(pref_content, text="\nPreferred Match Type:",
                 font=('Arial', 10, 'bold')).grid(row=len(issues)+1, column=0, sticky='w', pady=(10, 5))

        self.match_type_var = tk.StringVar(value="One-on-one")
        ttk.Radiobutton(pref_content, text="One-on-one peer matching",
                       variable=self.match_type_var, value="One-on-one").grid(
                           row=len(issues)+2, column=0, sticky='w', padx=(20, 0))
        ttk.Radiobutton(pref_content, text="Small group (3-4 peers)",
                       variable=self.match_type_var, value="Group").grid(
                           row=len(issues)+3, column=0, sticky='w', padx=(20, 0))

        # Privacy notice
        privacy_frame = ttk.LabelFrame(main_frame, text="🔒 Privacy & Security")
        privacy_frame.pack(fill='x', pady=(0, 15))

        privacy_text = ("• Your identity remains anonymous\n"
                       "• Secure encrypted messaging\n"
                       "• You can unmatch at any time\n"
                       "• Conversations are not monitored (unless safety concern)")
        ttk.Label(privacy_frame, text=privacy_text, justify='left').pack(padx=10, pady=10)

        # My matches
        matches_frame = ttk.LabelFrame(main_frame, text="My Current Matches")
        matches_frame.pack(fill='x', pady=(0, 15))

        match_text = """Active Matches: 2

Match #1: Support Buddy (matched 2 weeks ago)
  Common interests: Academic stress, time management
  Messages exchanged: 15
  Last contact: 2 days ago

Match #2: Anonymous Friend (matched 1 week ago)
  Common interests: Social connection, first-year adjustment
  Messages exchanged: 8
  Last contact: Yesterday
"""
        ttk.Label(matches_frame, text=match_text, justify='left',
                 font=('Courier', 9)).pack(padx=15, pady=10)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Find New Match",
                  command=self.find_match).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View My Matches",
                  command=self.view_matches).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Messaging",
                  command=self.open_messaging).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close",
                  command=self.dialog.destroy).pack(side='right')

    def _ensure_peer_tables(self, cursor):
        """Create peer_matches and peer_messages tables if they don't exist."""
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS peer_matches (
            match_id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id TEXT NOT NULL,
            matched_id TEXT,
            requester_anon_id TEXT NOT NULL,
            matched_anon_id TEXT,
            topic TEXT,
            match_type TEXT DEFAULT 'One-on-one',
            status TEXT DEFAULT 'pending',
            matched_date TEXT,
            created_date TEXT NOT NULL
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS peer_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            sender_anon_id TEXT NOT NULL,
            message_text TEXT NOT NULL,
            sent_date TEXT NOT NULL,
            FOREIGN KEY (match_id) REFERENCES peer_matches (match_id)
        )
        ''')

    def find_match(self):
        """Create a peer match based on user's selected support areas."""
        if not messagebox.askyesno("Find Match",
                                   "Start searching for a peer match based on your preferences?"):
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_peer_tables(cursor)

            user_id = str(self.auth.current_user['id'])
            anon_id = hashlib.sha256(f"{user_id}_peer_{datetime.now().isoformat()}".encode()).hexdigest()[:8]

            # Collect selected support areas from the checkbuttons
            selected_topics = [issue for issue, var in self.issue_vars.items() if var.get()]
            topic = ", ".join(selected_topics) if selected_topics else "General Support"
            match_type = self.match_type_var.get()

            now = datetime.now().isoformat()

            # Look for a compatible pending match from another user
            cursor.execute('''
                SELECT match_id, requester_id, requester_anon_id, topic
                FROM peer_matches
                WHERE status = 'pending'
                  AND requester_id != ?
                  AND match_type = ?
                ORDER BY created_date ASC
                LIMIT 1
            ''', (user_id, match_type))
            pending = cursor.fetchone()

            if pending:
                # Match found -- update the existing record
                match_id, other_id, other_anon, other_topic = pending
                cursor.execute('''
                    UPDATE peer_matches
                    SET matched_id = ?, matched_anon_id = ?, status = 'active',
                        matched_date = ?, topic = ?
                    WHERE match_id = ?
                ''', (user_id, anon_id, now,
                      f"{other_topic}; {topic}", match_id))
                conn.commit()
                messagebox.showinfo(
                    "Match Found!",
                    f"You have been matched with peer '{other_anon}'!\n\n"
                    f"Match ID: {match_id}\n"
                    f"Your anonymous ID: {anon_id}\n\n"
                    "Use the Messaging button to start chatting.")
            else:
                # No compatible match yet -- create a pending request
                cursor.execute('''
                    INSERT INTO peer_matches
                        (requester_id, requester_anon_id, topic, match_type, status, created_date)
                    VALUES (?, ?, ?, ?, 'pending', ?)
                ''', (user_id, anon_id, topic, match_type, now))
                conn.commit()
                messagebox.showinfo(
                    "Request Submitted",
                    f"Your match request has been submitted.\n\n"
                    f"Your anonymous ID: {anon_id}\n"
                    "You'll be matched when a compatible peer is found.")

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to find match: {e}")
        finally:
            if conn:
                conn.close()

    def view_matches(self):
        """Query peer_matches for the current user and display in a Toplevel with Treeview."""
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_peer_tables(cursor)

            user_id = str(self.auth.current_user['id'])
            cursor.execute('''
                SELECT match_id, topic, status, COALESCE(matched_date, created_date),
                       CASE WHEN requester_id = ? THEN matched_anon_id
                            ELSE requester_anon_id END AS peer_anon_id
                FROM peer_matches
                WHERE requester_id = ? OR matched_id = ?
                ORDER BY COALESCE(matched_date, created_date) DESC
            ''', (user_id, user_id, user_id))
            matches = cursor.fetchall()
            conn.close()
            conn = None

            win = tk.Toplevel(self.dialog)
            win.title("My Peer Matches")
            win.geometry("700x400")
            win.transient(self.dialog)
            win.grab_set()

            ttk.Label(win, text="My Peer Matches",
                      font=('Arial', 12, 'bold')).pack(pady=(10, 5))

            columns = ('Match ID', 'Topic', 'Status', 'Date', 'Peer')
            tree = ttk.Treeview(win, columns=columns, show='headings', height=12)
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=130)
            tree.pack(fill='both', expand=True, padx=10, pady=5)

            for m in matches:
                peer_display = m[4] if m[4] else "(pending)"
                tree.insert('', 'end', values=(m[0], m[1] or "", m[2], m[3] or "", peer_display))

            if not matches:
                ttk.Label(win, text="No matches found. Use 'Find New Match' to get started.").pack(pady=10)

            ttk.Button(win, text="Close", command=win.destroy).pack(pady=10)

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load matches: {e}")
        finally:
            if conn:
                conn.close()

    def open_messaging(self):
        """Open a messaging interface for a selected peer match."""
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_peer_tables(cursor)

            user_id = str(self.auth.current_user['id'])
            cursor.execute('''
                SELECT match_id, topic,
                       CASE WHEN requester_id = ? THEN requester_anon_id
                            ELSE matched_anon_id END AS my_anon,
                       CASE WHEN requester_id = ? THEN matched_anon_id
                            ELSE requester_anon_id END AS peer_anon
                FROM peer_matches
                WHERE (requester_id = ? OR matched_id = ?) AND status = 'active'
                ORDER BY matched_date DESC
            ''', (user_id, user_id, user_id, user_id))
            active_matches = cursor.fetchall()
            conn.close()
            conn = None

            if not active_matches:
                messagebox.showinfo("Messaging", "No active matches to message. Find a match first.")
                return

            # If multiple matches, let user pick one
            match_id = active_matches[0][0]
            my_anon = active_matches[0][2]
            peer_anon = active_matches[0][3]
            topic = active_matches[0][1]

            if len(active_matches) > 1:
                choices = [f"Match #{m[0]} - {m[1] or 'General'} (peer: {m[3]})" for m in active_matches]
                choice = simpledialog.askstring(
                    "Select Match",
                    "Enter the match number to message:\n\n" +
                    "\n".join(choices),
                    parent=self.dialog)
                if not choice:
                    return
                try:
                    chosen_id = int(choice.strip())
                    for m in active_matches:
                        if m[0] == chosen_id:
                            match_id, topic, my_anon, peer_anon = m
                            break
                except ValueError:
                    messagebox.showwarning("Invalid", "Please enter a valid match number.")
                    return

            # Open messaging window
            self._open_message_window(match_id, my_anon, peer_anon, topic)

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to open messaging: {e}")
        finally:
            if conn:
                conn.close()

    def _open_message_window(self, match_id, my_anon, peer_anon, topic):
        """Display the messaging window for a given match."""
        win = tk.Toplevel(self.dialog)
        win.title(f"Messages - Match #{match_id}")
        win.geometry("600x500")
        win.transient(self.dialog)
        win.grab_set()

        ttk.Label(win, text=f"Chat with {peer_anon} | Topic: {topic or 'General'}",
                  font=('Arial', 11, 'bold')).pack(pady=(10, 5))
        ttk.Label(win, text=f"You are: {my_anon}",
                  font=('Arial', 9)).pack(pady=(0, 5))

        # Message history
        msg_frame = ttk.Frame(win)
        msg_frame.pack(fill='both', expand=True, padx=10, pady=5)

        msg_text = scrolledtext.ScrolledText(msg_frame, wrap=tk.WORD, state='disabled',
                                             font=('Arial', 10))
        msg_text.pack(fill='both', expand=True)

        def load_messages():
            msg_text.config(state='normal')
            msg_text.delete(1.0, tk.END)
            try:
                c = sqlite3.connect(str(DEFAULT_DB_PATH))
                cur = c.cursor()
                cur.execute('''
                    SELECT sender_anon_id, message_text, sent_date
                    FROM peer_messages
                    WHERE match_id = ?
                    ORDER BY sent_date ASC
                ''', (match_id,))
                messages = cur.fetchall()
                c.close()

                for sender, text, dt in messages:
                    label = "You" if sender == my_anon else sender
                    msg_text.insert(tk.END, f"[{dt}] {label}: {text}\n\n")
            except sqlite3.Error:
                msg_text.insert(tk.END, "(Failed to load messages)\n")
            msg_text.config(state='disabled')
            msg_text.see(tk.END)

        load_messages()

        # Input area
        input_frame = ttk.Frame(win)
        input_frame.pack(fill='x', padx=10, pady=(0, 10))

        entry_var = tk.StringVar()
        entry = ttk.Entry(input_frame, textvariable=entry_var)
        entry.pack(side='left', fill='x', expand=True, padx=(0, 5))

        def send_message():
            text = entry_var.get().strip()
            if not text:
                return
            try:
                c = sqlite3.connect(str(DEFAULT_DB_PATH))
                cur = c.cursor()
                cur.execute('''
                    INSERT INTO peer_messages (match_id, sender_anon_id, message_text, sent_date)
                    VALUES (?, ?, ?, ?)
                ''', (match_id, my_anon, text, datetime.now().isoformat()))
                c.commit()
                c.close()
                entry_var.set("")
                load_messages()
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to send message: {e}")

        ttk.Button(input_frame, text="Send", command=send_message).pack(side='right')
        entry.bind('<Return>', lambda e: send_message())

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))



class ManagePeerSupportDialog:
    """Manage peer support system (for moderators/admins)"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Manage Peer Support System")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="⚙️ Manage Peer Support System",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Tabs for different management areas
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Group moderation tab
        moderation_frame = ttk.Frame(notebook)
        notebook.add(moderation_frame, text="Group Moderation")
        self.create_moderation_tab(moderation_frame)

        # Pending requests tab
        requests_frame = ttk.Frame(notebook)
        notebook.add(requests_frame, text="Join Requests")
        self.create_requests_tab(requests_frame)

        # Reports tab
        reports_frame = ttk.Frame(notebook)
        notebook.add(reports_frame, text="Reports & Analytics")
        self.create_reports_tab(reports_frame)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def create_moderation_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Groups You Moderate",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        columns = ('ID', 'Group', 'Members', 'Status', 'Created')
        self.mod_tree = ttk.Treeview(frame, columns=columns, show='headings', height=10)

        for col in columns:
            self.mod_tree.heading(col, text=col)
            if col == 'Group':
                self.mod_tree.column(col, width=200)
            else:
                self.mod_tree.column(col, width=100)

        self.mod_tree.pack(fill='both', expand=True)

        # Load real data from DB
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            user_id = str(self.auth.current_user['id'])

            # Get student_id for the current user
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            student_id = row[0] if row else user_id

            cursor.execute('''
                SELECT psg.group_id, psg.group_name,
                       psg.current_members || '/' || psg.max_members,
                       psg.status, psg.created_date
                FROM peer_support_groups psg
                WHERE psg.facilitator_id = ?
                ORDER BY psg.created_date DESC
            ''', (student_id,))
            groups = cursor.fetchall()

            for group in groups:
                self.mod_tree.insert('', 'end', values=group)

            conn.close()
            conn = None
        except sqlite3.Error:
            pass
        finally:
            if conn:
                conn.close()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        def approve_group():
            sel = self.mod_tree.selection()
            if not sel:
                messagebox.showwarning("Warning", "Select a group first.")
                return
            gid = self.mod_tree.item(sel[0])['values'][0]
            try:
                c = sqlite3.connect(str(DEFAULT_DB_PATH))
                cur = c.cursor()
                cur.execute("UPDATE peer_support_groups SET status = 'active' WHERE group_id = ?", (gid,))
                c.commit()
                c.close()
                self.mod_tree.item(sel[0], values=(*self.mod_tree.item(sel[0])['values'][:3], 'active',
                                                    self.mod_tree.item(sel[0])['values'][4]))
                messagebox.showinfo("Success", "Group approved.")
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to approve: {e}")

        def flag_group():
            sel = self.mod_tree.selection()
            if not sel:
                messagebox.showwarning("Warning", "Select a group first.")
                return
            gid = self.mod_tree.item(sel[0])['values'][0]
            try:
                c = sqlite3.connect(str(DEFAULT_DB_PATH))
                cur = c.cursor()
                cur.execute("UPDATE peer_support_groups SET status = 'flagged' WHERE group_id = ?", (gid,))
                c.commit()
                c.close()
                self.mod_tree.item(sel[0], values=(*self.mod_tree.item(sel[0])['values'][:3], 'flagged',
                                                    self.mod_tree.item(sel[0])['values'][4]))
                messagebox.showinfo("Flagged", "Group has been flagged for review.")
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to flag: {e}")

        def dismiss_group():
            sel = self.mod_tree.selection()
            if not sel:
                messagebox.showwarning("Warning", "Select a group first.")
                return
            gid = self.mod_tree.item(sel[0])['values'][0]
            if not messagebox.askyesno("Confirm", "Dismiss (deactivate) this group?"):
                return
            try:
                c = sqlite3.connect(str(DEFAULT_DB_PATH))
                cur = c.cursor()
                cur.execute("UPDATE peer_support_groups SET status = 'inactive' WHERE group_id = ?", (gid,))
                c.commit()
                c.close()
                self.mod_tree.delete(sel[0])
                messagebox.showinfo("Dismissed", "Group has been deactivated.")
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to dismiss: {e}")

        ttk.Button(btn_frame, text="Approve", command=approve_group).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Flag", command=flag_group).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Dismiss", command=dismiss_group).pack(side='left')

    def _ensure_support_requests_table(self, cursor):
        """Create support_requests table if it doesn't exist."""
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            anonymous_id TEXT,
            group_id INTEGER,
            group_name TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            requested_date TEXT NOT NULL,
            resolved_date TEXT,
            resolved_by TEXT
        )
        ''')

    def create_requests_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Pending Support Requests",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        columns = ('ID', 'Student', 'Group', 'Requested', 'Reason')
        self.req_tree = ttk.Treeview(frame, columns=columns, show='headings', height=8)

        for col in columns:
            self.req_tree.heading(col, text=col)
            if col == 'Reason':
                self.req_tree.column(col, width=250)
            elif col == 'ID':
                self.req_tree.column(col, width=50)
            else:
                self.req_tree.column(col, width=130)

        self.req_tree.pack(fill='both', expand=True)

        self._load_requests()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_frame, text="Approve", command=self.approve_request).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Deny", command=self.deny_request).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Refresh", command=self._load_requests).pack(side='left')

    def _load_requests(self):
        """Load pending support requests from the database."""
        for item in self.req_tree.get_children():
            self.req_tree.delete(item)

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_support_requests_table(cursor)

            cursor.execute('''
                SELECT request_id, COALESCE(anonymous_id, 'Anon#' || student_id),
                       COALESCE(group_name, 'N/A'), requested_date, COALESCE(reason, '')
                FROM support_requests
                WHERE status = 'pending'
                ORDER BY requested_date ASC
            ''')
            rows = cursor.fetchall()

            for row in rows:
                self.req_tree.insert('', 'end', values=row)

            conn.close()
            conn = None
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load requests: {e}")
        finally:
            if conn:
                conn.close()

    def create_reports_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.report_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        self.report_text.pack(fill='both', expand=True)

        self._generate_report()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_frame, text="Refresh", command=self._generate_report).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Save as TXT", command=self._save_report_txt).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Email to Admin", command=self._email_report_to_admin).pack(side='left')

    def _generate_report(self):
        """Generate real statistics from the database."""
        self.report_text.config(state='normal')
        self.report_text.delete(1.0, tk.END)

        total_groups = 0
        active_groups = 0
        total_members = 0
        active_matches = 0
        pending_matches = 0
        pending_requests = 0
        total_messages = 0
        group_topics = []

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Total and active groups
            try:
                cursor.execute('SELECT COUNT(*) FROM peer_support_groups')
                total_groups = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM peer_support_groups WHERE status = 'active'")
                active_groups = cursor.fetchone()[0]
            except sqlite3.Error:
                pass

            # Total members
            try:
                cursor.execute("SELECT COUNT(*) FROM support_group_members WHERE status = 'active'")
                total_members = cursor.fetchone()[0]
            except sqlite3.Error:
                pass

            # Peer matches
            try:
                cursor.execute("SELECT COUNT(*) FROM peer_matches WHERE status = 'active'")
                active_matches = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM peer_matches WHERE status = 'pending'")
                pending_matches = cursor.fetchone()[0]
            except sqlite3.Error:
                pass

            # Pending support requests
            try:
                self._ensure_support_requests_table(cursor)
                cursor.execute("SELECT COUNT(*) FROM support_requests WHERE status = 'pending'")
                pending_requests = cursor.fetchone()[0]
            except sqlite3.Error:
                pass

            # Message count
            try:
                cursor.execute("SELECT COUNT(*) FROM peer_messages")
                total_messages = cursor.fetchone()[0]
            except sqlite3.Error:
                pass

            # Group topics breakdown
            try:
                cursor.execute('''
                    SELECT support_type, COUNT(*), SUM(current_members)
                    FROM peer_support_groups
                    WHERE status = 'active'
                    GROUP BY support_type
                    ORDER BY COUNT(*) DESC
                ''')
                group_topics = cursor.fetchall()
            except sqlite3.Error:
                pass

            conn.close()
            conn = None
        except sqlite3.Error:
            pass
        finally:
            if conn:
                conn.close()

        avg_size = (total_members / active_groups) if active_groups > 0 else 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        content = f"""PEER SUPPORT SYSTEM ANALYTICS
Generated: {now}
{'=' * 72}

OVERALL STATISTICS:

  Total Support Groups:   {total_groups}
  Active Support Groups:  {active_groups}
  Total Active Members:   {total_members}
  Average Group Size:     {avg_size:.1f} members

PEER MATCHING:

  Active Matches:         {active_matches}
  Pending Matches:        {pending_matches}
  Total Messages Sent:    {total_messages}

SUPPORT REQUESTS:

  Pending Requests:       {pending_requests}

"""
        if group_topics:
            content += "SUPPORT GROUP TOPICS:\n\n"
            for i, (topic, count, members) in enumerate(group_topics, 1):
                members_val = members or 0
                content += f"  {i}. {topic or 'Unspecified'} ({count} groups, {members_val} members)\n"
            content += "\n"

        content += f"""{'=' * 72}
End of Report
"""
        self.report_text.insert(1.0, content)
        self.report_text.config(state='disabled')

    def _save_report_txt(self):
        """Save the current report to a text file."""
        from tkinter import filedialog
        filepath = filedialog.asksaveasfilename(
            parent=self.dialog,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"peer_support_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        if not filepath:
            return
        try:
            self.report_text.config(state='normal')
            content = self.report_text.get(1.0, tk.END)
            self.report_text.config(state='disabled')
            with open(filepath, 'w') as f:
                f.write(content)
            messagebox.showinfo("Saved", f"Report saved to:\n{filepath}")
        except OSError as e:
            messagebox.showerror("Error", f"Failed to save report: {e}")

    def _email_report_to_admin(self):
        """Email the current report content to the admin."""
        try:
            from education_system.post_18.university_system.infrastructure.email import send_email

            self.report_text.config(state='normal')
            content = self.report_text.get(1.0, tk.END)
            self.report_text.config(state='disabled')

            send_email(
                "admin@university.edu",
                "Peer Support System Analytics Report",
                content
            )
            messagebox.showinfo("Sent", "Report emailed to admin successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to email report: {e}")

    def approve_request(self):
        """Approve the selected support request in the database."""
        sel = self.req_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a request to approve.")
            return

        request_id = self.req_tree.item(sel[0])['values'][0]
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            user_id = str(self.auth.current_user['id'])
            cursor.execute('''
                UPDATE support_requests
                SET status = 'approved', resolved_date = ?, resolved_by = ?
                WHERE request_id = ?
            ''', (datetime.now().isoformat(), user_id, request_id))
            conn.commit()
            conn.close()
            conn = None

            self.req_tree.delete(sel[0])
            messagebox.showinfo("Approved", f"Request #{request_id} has been approved.")
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to approve request: {e}")
        finally:
            if conn:
                conn.close()

    def deny_request(self):
        """Deny the selected support request in the database."""
        sel = self.req_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a request to deny.")
            return

        if not messagebox.askyesno("Deny Request", "Are you sure you want to deny this request?"):
            return

        request_id = self.req_tree.item(sel[0])['values'][0]
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            user_id = str(self.auth.current_user['id'])
            cursor.execute('''
                UPDATE support_requests
                SET status = 'denied', resolved_date = ?, resolved_by = ?
                WHERE request_id = ?
            ''', (datetime.now().isoformat(), user_id, request_id))
            conn.commit()
            conn.close()
            conn = None

            self.req_tree.delete(sel[0])
            messagebox.showinfo("Denied", f"Request #{request_id} has been denied.")
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to deny request: {e}")
        finally:
            if conn:
                conn.close()


# ============================================================================
# ACADEMIC SUPPORT SYSTEM - 6 Features
# ============================================================================


def open_peer_support_wellness_dialog(self):
    """Open peer support and wellness hub"""
    dialog = PeerSupportWellnessDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


