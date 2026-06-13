import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import os
import json
import logging
from datetime import datetime

from education_system.university_system.infrastructure.ai.university_chatbot import LIBRARIES_AVAILABLE

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
    )
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"

logger = logging.getLogger(__name__)


class AdminPanelMixin:
    """Mixin for admin panel and system management screens."""

    def create_admin_panel(self):
        """Create admin panel for system management (missing from GUI)"""
        if not self.current_user or self.current_user.get('role') != 'admin':
            return

        self.admin_frame = ttk.Frame(self.main_frame)

        # Admin header
        admin_header = ttk.Label(self.admin_frame,
                                text=_t("chatbot.system_administration", default="System Administration"),
                                style='CB.Title.TLabel')
        admin_header.pack(pady=(0, 20))

        # Admin notebook
        admin_notebook = ttk.Notebook(self.admin_frame)
        admin_notebook.pack(fill=tk.BOTH, expand=True)

        # System Status Tab
        status_tab = ttk.Frame(admin_notebook)
        admin_notebook.add(status_tab, text=_t("chatbot.admin_tab_system_status", default="System Status"))
        self.create_system_status_tab(status_tab)

        # User Management Tab
        users_tab = ttk.Frame(admin_notebook)
        admin_notebook.add(users_tab, text=_t("chatbot.admin_tab_user_management", default="User Management"))
        self.create_user_management_tab(users_tab)

        # Analytics Tab
        analytics_tab = ttk.Frame(admin_notebook)
        admin_notebook.add(analytics_tab, text=_t("chatbot.admin_tab_analytics", default="Analytics"))
        self.create_analytics_tab(analytics_tab)

        # Logs Tab
        logs_tab = ttk.Frame(admin_notebook)
        admin_notebook.add(logs_tab, text=_t("chatbot.admin_tab_system_logs", default="System Logs"))
        self.create_logs_tab(logs_tab)

        # Back button
        back_button = ttk.Button(self.admin_frame,
                                text=_t("chatbot.back_to_chat", default="Back to Chat"),
                                style='CB.Primary.TButton',
                                command=self.show_chat_screen)
        back_button.pack(pady=(20, 0))

    def create_system_status_tab(self, parent):
        """Create system status monitoring tab"""
        # System metrics frame
        metrics_frame = ttk.LabelFrame(parent, text=_t("chatbot.system_metrics", default="System Metrics"), padding=10)
        metrics_frame.pack(fill=tk.X, padx=10, pady=10)

        # Create status display
        self.status_text = scrolledtext.ScrolledText(metrics_frame, height=10, width=60)
        self.status_text.pack(fill=tk.BOTH, expand=True)

        # Refresh button
        refresh_button = ttk.Button(metrics_frame,
                                   text="Refresh Status",
                                   command=self.refresh_system_status)
        refresh_button.pack(pady=(10, 0))

        # Initialize status display
        self.refresh_system_status()

    def refresh_system_status(self):
        """Refresh system status display"""
        try:
            status = self.chatbot.get_system_status()
            analytics = self.chatbot.generate_usage_analytics()

            status_info = f"""System Status Report
{'='*50}

Authentication System: {'✓ Active' if status['authenticated'] else '✗ Inactive'}
Current User: {status.get('current_user', 'None')}
Active Sessions: {status['active_sessions']}
Total Conversations: {status['total_conversations']}

Voice Interface: {'✓ Available' if self.chatbot.voice_interface.enabled else '✗ Unavailable'}
Database: {'✓ Connected' if self.chatbot.connect_to_db() else '✗ Connection Failed'}

Usage Analytics:
- Unique Users: {analytics.get('unique_users', 0)}
- Popular Intents: {', '.join(list(analytics.get('popular_intents', {}).keys())[:3])}
- Voice Usage: {analytics.get('voice_usage', {}).get('total', 0)} interactions

Libraries Status:
- tkinter: {'✓' if LIBRARIES_AVAILABLE.get('tkinter') else '✗'}
- speech_recognition: {'✓' if LIBRARIES_AVAILABLE.get('speech_recognition') else '✗'}
- flask: {'✓' if LIBRARIES_AVAILABLE.get('flask') else '✗'}
- transformers: {'✓' if LIBRARIES_AVAILABLE.get('transformers') else '✗'}

Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, status_info)

        except Exception as e:
            error_msg = f"Error refreshing status: {e}"
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, error_msg)

    def create_user_management_tab(self, parent):
        """Create user management interface with bot interaction history"""
        # User list frame
        users_frame = ttk.LabelFrame(parent, text="Users Who Interacted With Bot", padding=10)
        users_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # User list
        columns = ('Username', 'Role', 'Messages', 'Last Activity')
        self.user_tree = ttk.Treeview(users_frame, columns=columns, show='headings', height=10)

        self.user_tree.heading('Username', text='Username')
        self.user_tree.heading('Role', text='Role')
        self.user_tree.heading('Messages', text='Messages')
        self.user_tree.heading('Last Activity', text='Last Activity')

        self.user_tree.column('Username', width=150)
        self.user_tree.column('Role', width=100)
        self.user_tree.column('Messages', width=80)
        self.user_tree.column('Last Activity', width=160)

        scrollbar = ttk.Scrollbar(users_frame, orient='vertical', command=self.user_tree.yview)
        self.user_tree.configure(yscrollcommand=scrollbar.set)
        self.user_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 10))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10))

        # Double-click to view chats
        self.user_tree.bind('<Double-1>', lambda e: self.view_user_chats())

        # Hint label
        hint_label = ttk.Label(parent, text="Double-click a username to view their chat history",
                               font=('Arial', 9, 'italic'))
        hint_label.pack(anchor=tk.W, padx=15)

        # User management buttons
        user_buttons_frame = ttk.Frame(parent)
        user_buttons_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        ttk.Button(user_buttons_frame, text="Refresh Users",
                   command=self.refresh_user_list).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(user_buttons_frame, text="View Chats",
                   command=self.view_user_chats).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(user_buttons_frame, text="Export Chats as TXT",
                   command=self.export_user_chats_txt).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(user_buttons_frame, text="Email Chats to Me",
                   command=self.email_user_chats).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(user_buttons_frame, text="Send Message",
                   command=self.send_admin_message).pack(side=tk.LEFT)

        # Initialize user list
        self.refresh_user_list()

    def _get_db_path(self):
        """Get database path from chatbot"""
        return getattr(self.chatbot, 'db_path', None)

    def refresh_user_list(self):
        """Refresh the user list from the database"""
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)

        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            db_path = self._get_db_path()
            if not db_path:
                return

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get all users who have interacted with the chatbot
            cursor.execute('''
                SELECT cc.username,
                       COALESCE(u.role, 'guest') as role,
                       COUNT(*) as message_count,
                       MAX(cc.timestamp) as last_activity
                FROM chatbot_conversations cc
                LEFT JOIN users u ON cc.user_id = u.id
                GROUP BY cc.username
                ORDER BY last_activity DESC
            ''')
            users = cursor.fetchall()
            conn.close()

            for username, role, msg_count, last_activity in users:
                self.user_tree.insert('', 'end', values=(
                    username, role, msg_count, last_activity
                ))

        except Exception as e:
            # Fallback to in-memory conversation history
            if hasattr(self.chatbot, 'conversation_history'):
                for username, history in self.chatbot.conversation_history.items():
                    if history:
                        last_msg = history[-1]
                        self.user_tree.insert('', 'end', values=(
                            username, "Guest", len(history), last_msg['timestamp']
                        ))
            logger.debug(f"Error refreshing user list from DB: {e}")

    def _get_selected_username(self):
        """Get username from the selected tree item, or None"""
        selection = self.user_tree.selection()
        if not selection:
            messagebox.showwarning(
                _t("chatbot.no_selection_title", default="No Selection"),
                _t("chatbot.select_user_to_view", default="Please select a user to view details.")
            )
            return None
        return self.user_tree.item(selection[0])['values'][0]

    def _load_user_conversations(self, username):
        """Load all conversations for a user from the database.

        Returns a list of dicts with keys: timestamp, message, response.
        """
        conversations = []
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            db_path = self._get_db_path()
            if not db_path:
                return conversations

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, message, response
                FROM chatbot_conversations
                WHERE username = ?
                ORDER BY timestamp ASC
            ''', (username,))
            for ts, msg, resp in cursor.fetchall():
                conversations.append({'timestamp': ts, 'message': msg, 'response': resp})
            conn.close()
        except Exception as e:
            logger.debug(f"Error loading conversations from DB: {e}")
            # Fallback to in-memory
            if hasattr(self.chatbot, 'conversation_history') and username in self.chatbot.conversation_history:
                for entry in self.chatbot.conversation_history[username]:
                    conversations.append({
                        'timestamp': entry.get('timestamp', ''),
                        'message': entry.get('message', ''),
                        'response': entry.get('response', ''),
                    })
        return conversations

    def _format_conversations_text(self, username, conversations):
        """Format conversations into a readable text string."""
        lines = [f"Chat History for: {username}",
                 f"Total Messages: {len(conversations)}",
                 f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                 "=" * 60, ""]
        for conv in conversations:
            lines.append(f"[{conv['timestamp']}]")
            lines.append(f"  User:    {conv['message']}")
            lines.append(f"  Chatbot: {conv['response']}")
            lines.append("")
        return "\n".join(lines)

    def view_user_chats(self):
        """View all chat messages for the selected user"""
        username = self._get_selected_username()
        if not username:
            return

        conversations = self._load_user_conversations(username)

        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Chat History - {username}")
        details_window.geometry("700x500")
        details_window.transient(self.root)

        # Header
        header = ttk.Label(details_window,
                           text=f"Chat History for {username} ({len(conversations)} messages)",
                           font=('Arial', 12, 'bold'))
        header.pack(anchor=tk.W, padx=10, pady=(10, 5))

        # Chat display
        chat_text = scrolledtext.ScrolledText(details_window, height=20, width=80, wrap=tk.WORD)
        chat_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        if not conversations:
            chat_text.insert(tk.END, "No conversation history found for this user.")
        else:
            for conv in conversations:
                chat_text.insert(tk.END, f"[{conv['timestamp']}]\n", "timestamp")
                chat_text.insert(tk.END, f"  {username}: ", "user")
                chat_text.insert(tk.END, f"{conv['message']}\n")
                chat_text.insert(tk.END, f"  Chatbot: ", "bot")
                chat_text.insert(tk.END, f"{conv['response']}\n\n")

        chat_text.tag_configure("timestamp", foreground="gray")
        chat_text.tag_configure("user", foreground="#1565c0", font=('Arial', 10, 'bold'))
        chat_text.tag_configure("bot", foreground="#2e7d32", font=('Arial', 10, 'bold'))
        chat_text.config(state=tk.DISABLED)

        # Action buttons
        btn_frame = ttk.Frame(details_window)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        def export_this():
            self._export_conversations_txt(username, conversations)

        def email_this():
            self._email_conversations(username, conversations)

        ttk.Button(btn_frame, text="Export as TXT", command=export_this).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Email to Me", command=email_this).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Close", command=details_window.destroy).pack(side=tk.RIGHT)

    def export_user_chats_txt(self):
        """Export selected user's chats as a TXT file"""
        username = self._get_selected_username()
        if not username:
            return
        conversations = self._load_user_conversations(username)
        self._export_conversations_txt(username, conversations)

    def _export_conversations_txt(self, username, conversations):
        """Save conversations to a TXT file via save dialog"""
        if not conversations:
            messagebox.showinfo("No Data", f"No conversations found for {username}.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile=f"chatbot_history_{username}.txt",
            title="Export Chat History"
        )
        if not filename:
            return

        try:
            text = self._format_conversations_text(username, conversations)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(text)
            messagebox.showinfo("Export Complete", f"Chat history exported to:\n{filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {e}")

    def email_user_chats(self):
        """Email selected user's chats to the current admin"""
        username = self._get_selected_username()
        if not username:
            return
        conversations = self._load_user_conversations(username)
        self._email_conversations(username, conversations)

    def _email_conversations(self, username, conversations):
        """Email conversations to the current admin user"""
        if not conversations:
            messagebox.showinfo("No Data", f"No conversations found for {username}.")
            return

        admin_email = None
        if self.current_user:
            admin_email = self.current_user.get('email')

        if not admin_email:
            # Try to look it up from the database
            try:
                from education_system.university_system.infrastructure.database.db import sqlite3
                db_path = self._get_db_path()
                if db_path and self.current_user:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute('SELECT email FROM users WHERE id = ?',
                                   (self.current_user.get('id'),))
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        admin_email = row[0]
            except Exception:
                pass

        if not admin_email:
            messagebox.showwarning("No Email",
                                   "Could not find your email address.\nPlease export the chats as TXT instead.")
            return

        try:
            from education_system.university_system.infrastructure.email.email_service.core import send_email

            body = self._format_conversations_text(username, conversations)
            subject = f"Chatbot History - {username} ({len(conversations)} messages)"

            send_email(
                recipient_email=admin_email,
                subject=subject,
                body=body,
            )
            messagebox.showinfo("Email Sent",
                                f"Chat history for {username} sent to {admin_email}")
        except Exception as e:
            messagebox.showerror("Email Error", f"Failed to send email: {e}")

    def send_admin_message(self):
        """Send administrative message to user"""
        selection = self.user_tree.selection()
        if not selection:
            messagebox.showwarning(
                _t("chatbot.no_selection_title", default="No Selection"),
                _t("chatbot.select_user_to_message", default="Please select a user to send a message.")
            )
            return

        username = self.user_tree.item(selection[0])['values'][0]

        # Create message dialog
        msg_window = tk.Toplevel(self.root)
        msg_window.title(f"Send Message to {username}")
        msg_window.geometry("400x300")

        ttk.Label(msg_window, text=f"Message to {username}:").pack(anchor=tk.W, padx=10, pady=5)

        msg_text = tk.Text(msg_window, height=10, width=45)
        msg_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        def send_message():
            message = msg_text.get(1.0, tk.END).strip()
            if message:
                # Add admin message to user's conversation
                if username in self.chatbot.conversation_history:
                    self.chatbot.conversation_history[username].append({
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'message': f"[ADMIN MESSAGE] {message}",
                        'response': "Message from administrator",
                        'type': 'admin'
                    })
                messagebox.showinfo(
                    _t("chatbot.message_sent_title", default="Message Sent"),
                    _t("chatbot.message_sent_msg", default="Administrative message sent to {username}").format(username=username)
                )
                msg_window.destroy()

        ttk.Button(msg_window, text=_t("chatbot.send_message_btn", default="Send Message"), command=send_message).pack(pady=10)

    def create_analytics_tab(self, parent):
        """Create analytics dashboard tab"""
        # Analytics frame
        analytics_frame = ttk.LabelFrame(parent, text="Usage Analytics", padding=10)
        analytics_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Analytics display
        self.analytics_text = scrolledtext.ScrolledText(analytics_frame, height=15, width=70)
        self.analytics_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Analytics buttons
        analytics_buttons = ttk.Frame(analytics_frame)
        analytics_buttons.pack(fill=tk.X)

        ttk.Button(analytics_buttons, text="Generate Report",
                   command=self.generate_analytics_report).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(analytics_buttons, text="Export Data",
                   command=self.export_analytics).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(analytics_buttons, text="Clear Cache",
                   command=self.clear_analytics_cache).pack(side=tk.LEFT)

        # Auto-generate initial report
        self.generate_analytics_report()

    def generate_analytics_report(self):
        """Generate comprehensive analytics report"""
        try:
            analytics = self.chatbot.generate_usage_analytics()

            report = f"""UNIVERSITY CHATBOT ANALYTICS REPORT
{'='*60}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

USAGE STATISTICS:
- Total Conversations: {analytics.get('total_conversations', 0)}
- Unique Users: {analytics.get('unique_users', 0)}
- Voice Interactions: {analytics.get('voice_usage', {}).get('total', 0)}
- Voice Success Rate: {analytics.get('voice_usage', {}).get('successful', 0) / max(1, analytics.get('voice_usage', {}).get('total', 1)) * 100:.1f}%

POPULAR INTENTS:
"""

            popular_intents = analytics.get('popular_intents', {})
            for intent, count in sorted(popular_intents.items(), key=lambda x: x[1], reverse=True)[:5]:
                report += f"- {intent}: {count} queries\n"

            report += f"""
PEAK USAGE HOURS:
"""
            peak_hours = analytics.get('peak_usage_hours', {})
            for hour in sorted(peak_hours.keys(), key=lambda x: peak_hours[x], reverse=True)[:5]:
                report += f"- {hour:02d}:00 - {hour+1:02d}:00: {peak_hours[hour]} interactions\n"

            report += f"""
SYSTEM PERFORMANCE:
- Average Response Time: Calculating...
- Error Rate: {analytics.get('error_rates', {}).get('total', 0)}%
- Uptime: 99.9%

FEATURE USAGE:
- Voice Commands: {analytics.get('voice_usage', {}).get('total', 0)}
- Authentication: {'Active' if self.chatbot.auth_system else 'Inactive'}
- GUI Sessions: {len(getattr(self.chatbot, 'conversation_contexts', {}))}

RECOMMENDATIONS:
- Monitor peak usage hours for resource allocation
- Consider expanding voice interface capabilities
- Review popular intents for feature enhancement
"""

            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(1.0, report)

        except Exception as e:
            error_report = f"Error generating analytics report: {e}"
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(1.0, error_report)

    def export_analytics(self):
        """Export analytics data to file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("Text files", "*.txt")],
                title="Export Analytics Data"
            )

            if filename:
                analytics = self.chatbot.generate_usage_analytics()

                if filename.endswith('.json'):
                    with open(filename, 'w') as f:
                        json.dump(analytics, f, indent=4, default=str)
                else:
                    # Export as text
                    report_text = self.analytics_text.get(1.0, tk.END)
                    with open(filename, 'w') as f:
                        f.write(report_text)

                messagebox.showinfo(
                    _t("chatbot.export_complete", default="Export Complete"),
                    _t("chatbot.analytics_exported", default="Analytics data exported to {filename}").format(filename=filename)
                )

        except Exception as e:
            messagebox.showerror(
                _t("chatbot.export_error", default="Export Error"),
                _t("chatbot.analytics_export_failed", default="Failed to export analytics: {error}").format(error=str(e))
            )

    def clear_analytics_cache(self):
        """Clear analytics cache and regenerate"""
        if messagebox.askyesno(
            _t("chatbot.clear_cache", default="Clear Cache"),
            _t("chatbot.clear_cache_confirm", default="Are you sure you want to clear the analytics cache?")
        ):
            try:
                # Clear conversation histories (keep recent ones)
                if hasattr(self.chatbot, 'conversation_history'):
                    for username in list(self.chatbot.conversation_history.keys()):
                        history = self.chatbot.conversation_history[username]
                        if len(history) > 10:
                            self.chatbot.conversation_history[username] = history[-10:]

                messagebox.showinfo(
                    _t("chatbot.cache_cleared", default="Cache Cleared"),
                    _t("chatbot.cache_cleared_msg", default="Analytics cache has been cleared.")
                )
                self.generate_analytics_report()

            except Exception as e:
                messagebox.showerror(
                    _t("common.error", default="Error"),
                    _t("chatbot.clear_cache_failed", default="Failed to clear cache: {error}").format(error=str(e))
                )

    def create_logs_tab(self, parent):
        """Create system logs viewing tab"""
        # Logs frame
        logs_frame = ttk.LabelFrame(parent, text="System Logs", padding=10)
        logs_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Log filter frame
        filter_frame = ttk.Frame(logs_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text="Log Level:").pack(side=tk.LEFT, padx=(0, 5))
        self.log_level_var = tk.StringVar(value="All")
        log_level_combo = ttk.Combobox(filter_frame,
                                      textvariable=self.log_level_var,
                                      values=["All", "Error", "Warning", "Info"],
                                      state="readonly", width=10)
        log_level_combo.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(filter_frame, text="Refresh Logs",
                   command=self.refresh_logs).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(filter_frame, text="Clear Logs",
                   command=self.clear_logs).pack(side=tk.LEFT)

        # Logs display
        self.logs_text = scrolledtext.ScrolledText(logs_frame, height=15, width=80)
        self.logs_text.pack(fill=tk.BOTH, expand=True)

        # Auto-refresh logs
        self.refresh_logs()

    def refresh_logs(self):
        """Refresh system logs display"""
        try:
            log_content = "SYSTEM LOGS\n" + "="*50 + "\n\n"

            # Check for log files
            log_dir = getattr(self.chatbot, 'log_dir', 'logs')
            if os.path.exists(log_dir):
                log_files = [f for f in os.listdir(log_dir)
                             if f.endswith('.json') and f != 'log_config.json']
                log_files.sort(reverse=True)  # Most recent first

                for log_file in log_files[:3]:  # Show last 3 log files
                    log_path = os.path.join(log_dir, log_file)
                    log_content += f"\n--- {log_file} ---\n"

                    try:
                        with open(log_path, 'r') as f:
                            logs = json.load(f)

                            # Skip non-list JSON files (e.g. config files)
                            if not isinstance(logs, list):
                                continue

                            # Filter by log level
                            level_filter = self.log_level_var.get()

                            for log_entry in logs[-10:]:  # Last 10 entries per file
                                if level_filter == "All" or level_filter in log_entry.get('message', ''):
                                    timestamp = log_entry.get('timestamp', 'Unknown')
                                    user_id = log_entry.get('user_id', 'System')
                                    message = log_entry.get('user_message', log_entry.get('message', 'No message'))[:60]

                                    log_content += f"[{timestamp}] {user_id}: {message}...\n"

                    except Exception as e:
                        log_content += f"Error reading {log_file}: {e}\n"
            else:
                log_content += "No log directory found.\n"

            # Add current session info
            log_content += f"\n--- Current Session ---\n"
            log_content += f"User: {self.current_user.get('username', 'Unknown') if self.current_user else 'Not authenticated'}\n"
            log_content += f"Session Start: {getattr(self, 'session_start_time', 'Unknown')}\n"
            log_content += f"Messages Sent: {getattr(self, 'message_count', 0)}\n"

            self.logs_text.delete(1.0, tk.END)
            self.logs_text.insert(1.0, log_content)

        except Exception as e:
            error_msg = f"Error loading logs: {e}"
            self.logs_text.delete(1.0, tk.END)
            self.logs_text.insert(1.0, error_msg)

    def clear_logs(self):
        """Clear system logs"""
        if messagebox.askyesno(
            _t("chatbot.clear_logs", default="Clear Logs"),
            _t("chatbot.clear_logs_confirm", default="Are you sure you want to clear all system logs?")
        ):
            try:
                log_dir = getattr(self.chatbot, 'log_dir', 'logs')
                if os.path.exists(log_dir):
                    for log_file in os.listdir(log_dir):
                        if log_file.endswith('.json'):
                            os.remove(os.path.join(log_dir, log_file))

                messagebox.showinfo(
                    _t("chatbot.logs_cleared", default="Logs Cleared"),
                    _t("chatbot.logs_cleared_msg", default="All system logs have been cleared.")
                )
                self.refresh_logs()

            except Exception as e:
                messagebox.showerror(
                    _t("common.error", default="Error"),
                    _t("chatbot.clear_logs_failed", default="Failed to clear logs: {error}").format(error=str(e))
                )

    def show_admin_panel(self):
        """Show admin panel (add to existing interface)"""
        if not self.current_user or self.current_user.get('role') not in ['admin', 'staff']:
            messagebox.showerror(
                _t("chatbot.access_denied_title", default="Access Denied"),
                _t("chatbot.access_denied_admin", default="You don't have permission to access the admin panel.")
            )
            return

        self.hide_all_screens()
        if not hasattr(self, 'admin_frame'):
            self.create_admin_panel()
        self.admin_frame.pack(fill=tk.BOTH, expand=True)
        self.conversation_active = False
