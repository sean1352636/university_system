import tkinter as tk
from tkinter import messagebox, filedialog
import json
import csv
from datetime import datetime

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"


class ExportMixin:
    """Mixin for conversation export and backup/restore functionality."""

    def create_conversation_export(self):
        """Create conversation export functionality"""
        def export_conversations():
            try:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv"), ("Text files", "*.txt")],
                    title="Export Conversation History"
                )

                if filename:
                    if hasattr(self.chatbot, 'conversation_history'):
                        if filename.endswith('.json'):
                            with open(filename, 'w') as f:
                                json.dump(self.chatbot.conversation_history, f, indent=4, default=str)
                        elif filename.endswith('.csv'):
                            with open(filename, 'w', newline='') as f:
                                writer = csv.writer(f)
                                writer.writerow(['Username', 'Timestamp', 'Message', 'Response', 'Type'])

                                for username, history in self.chatbot.conversation_history.items():
                                    for conv in history:
                                        writer.writerow([
                                            username,
                                            conv.get('timestamp', ''),
                                            conv.get('message', ''),
                                            conv.get('response', ''),
                                            conv.get('type', 'text')
                                        ])
                        else:
                            # Text format
                            with open(filename, 'w') as f:
                                for username, history in self.chatbot.conversation_history.items():
                                    f.write(f"\n=== Conversations for {username} ===\n")
                                    for conv in history:
                                        f.write(f"[{conv.get('timestamp', '')}]\n")
                                        f.write(f"User: {conv.get('message', '')}\n")
                                        f.write(f"Bot: {conv.get('response', '')}\n\n")

                    messagebox.showinfo(
                        _t("chatbot.export_complete", default="Export Complete"),
                        _t("chatbot.conversations_exported", default="Conversations exported to {filename}").format(filename=filename)
                    )

            except Exception as e:
                messagebox.showerror(
                    _t("chatbot.export_error", default="Export Error"),
                    _t("chatbot.conversations_export_failed", default="Failed to export conversations: {error}").format(error=str(e))
                )

        return export_conversations

    def create_backup_restore(self):
        """Create backup and restore functionality"""
        def backup_system():
            try:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".backup",
                    filetypes=[("Backup files", "*.backup"), ("JSON files", "*.json")],
                    title="Create System Backup"
                )

                if filename:
                    backup_data = {
                        'timestamp': datetime.now().isoformat(),
                        'conversations': getattr(self.chatbot, 'conversation_history', {}),
                        'analytics': self.chatbot.generate_usage_analytics(),
                        'config': getattr(self.chatbot, 'config', {}),
                        'system_status': self.chatbot.get_system_status()
                    }

                    with open(filename, 'w') as f:
                        json.dump(backup_data, f, indent=4, default=str)

                    messagebox.showinfo(
                        _t("chatbot.backup_complete", default="Backup Complete"),
                        _t("chatbot.backup_created", default="System backup created: {filename}").format(filename=filename)
                    )

            except Exception as e:
                messagebox.showerror(
                    _t("chatbot.backup_error", default="Backup Error"),
                    _t("chatbot.backup_failed", default="Failed to create backup: {error}").format(error=str(e))
                )

        def restore_system():
            if messagebox.askyesno(
                _t("chatbot.restore_warning", default="Restore Warning"),
                _t("chatbot.restore_warning_msg", default="Restoring will overwrite current data. Continue?")
            ):
                try:
                    filename = filedialog.askopenfilename(
                        filetypes=[("Backup files", "*.backup"), ("JSON files", "*.json")],
                        title=_t("chatbot.select_backup_file", default="Select Backup File")
                    )

                    if filename:
                        with open(filename, 'r') as f:
                            backup_data = json.load(f)

                        # Restore conversation history
                        if 'conversations' in backup_data:
                            self.chatbot.conversation_history = backup_data['conversations']

                        messagebox.showinfo(
                            _t("chatbot.restore_complete", default="Restore Complete"),
                            _t("chatbot.restore_success", default="System restored from: {filename}").format(filename=filename)
                        )
                        self.refresh_system_status()

                except Exception as e:
                    messagebox.showerror(
                        _t("chatbot.restore_error", default="Restore Error"),
                        _t("chatbot.restore_failed", default="Failed to restore backup: {error}").format(error=str(e))
                    )

        return backup_system, restore_system
