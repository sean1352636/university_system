"""
Cinema Booking System - Audit Log

Functions for loading, displaying, and exporting audit log entries
from both university system log files and the database.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3
import os
import glob
import csv
from datetime import datetime, timedelta

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE

def load_audit_from_logs(self, action_filter="all"):
    """Load audit entries from university system log files."""
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', '..', '..', 'logs')
    entries = []
    entry_id = 1

    try:
        # Get all activity log files (activity.log and dated ones)
        log_patterns = [
            os.path.join(logs_dir, "app.log"),
            os.path.join(logs_dir, "activity.*"),
            os.path.join(logs_dir, "app.log"),
        ]

        log_files = set()
        for pattern in log_patterns:
            log_files.update(glob.glob(pattern))

        # Sort by modification time (newest first)
        log_files = sorted(log_files, key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)

        for log_file in log_files:
            if not os.path.exists(log_file):
                continue

            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    # Process lines in reverse for newest first
                    for line in reversed(lines):
                        line = line.strip()
                        if not line:
                            continue

                        # Parse activity.log format: "user - action - timestamp"
                        if ' - ' in line and log_file.endswith(('.log', '')) and 'activity' in log_file:
                            parts = line.split(' - ')
                            if len(parts) >= 3:
                                user = parts[0].strip()
                                action_text = parts[1].strip()
                                timestamp = parts[2].strip() if len(parts) > 2 else ""

                                # Determine action type
                                action_type = "activity"
                                action_lower = action_text.lower()
                                if "logged in" in action_lower or "login" in action_lower:
                                    action_type = "login"
                                elif "logged out" in action_lower or "logout" in action_lower:
                                    action_type = "logout"
                                elif "create" in action_lower or "add" in action_lower:
                                    action_type = "create"
                                elif "update" in action_lower or "edit" in action_lower or "modif" in action_lower:
                                    action_type = "update"
                                elif "delete" in action_lower or "remove" in action_lower:
                                    action_type = "delete"
                                elif "access" in action_lower or "view" in action_lower:
                                    action_type = "view"

                                # Apply filter
                                if action_filter != "all" and action_type != action_filter:
                                    continue

                                entries.append({
                                    'id': entry_id,
                                    'timestamp': timestamp,
                                    'user': user,
                                    'action': action_type,
                                    'entity': os.path.basename(log_file),
                                    'details': action_text
                                })
                                entry_id += 1

                        # Parse app.log format: "timestamp - LEVEL - module - message"
                        elif 'app.log' in log_file:
                            # Format: 2026-01-05 15:51:39,997 - INFO - module - message
                            parts = line.split(' - ', 3)
                            if len(parts) >= 4:
                                timestamp = parts[0].strip()
                                level = parts[1].strip()
                                module = parts[2].strip()
                                message = parts[3].strip() if len(parts) > 3 else ""

                                # Only show warnings and errors, or all if no filter
                                if level in ['WARNING', 'ERROR'] or action_filter == 'all':
                                    action_type = level.lower() if level in ['WARNING', 'ERROR'] else 'info'

                                    entries.append({
                                        'id': entry_id,
                                        'timestamp': timestamp,
                                        'user': module.split('.')[-1] if module else 'system',
                                        'action': action_type,
                                        'entity': 'app.log',
                                        'details': message[:100]
                                    })
                                    entry_id += 1

                        # Stop after 300 entries
                        if len(entries) >= 300:
                            break

            except Exception as e:
                # Skip files that can't be read
                continue

            if len(entries) >= 300:
                break

    except Exception as e:
        # Return empty list on error
        pass

    return entries[:200]  # Return max 200 entries

def show_audit_log_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.audit.title"), style="Subtitle.TLabel").pack(pady=10)

    filter_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    filter_frame.pack(fill="x", pady=10)

    # Source selector (Log Files or Database)
    tk.Label(filter_frame, text=_t("cinema.common.source"), bg="#ffffff", fg="#333333").pack(side="left")
    source_var = tk.StringVar(value="Log Files")
    source_combo = ttk.Combobox(filter_frame, textvariable=source_var, width=12,
                                 values=["Log Files", "Database"], state="readonly")
    source_combo.pack(side="left", padx=5)

    # Action filter
    tk.Label(filter_frame, text=_t("cinema.common.filter"), bg="#ffffff", fg="#333333").pack(side="left", padx=(10, 0))
    action_var = tk.StringVar(value="all")
    action_combo = ttk.Combobox(filter_frame, textvariable=action_var, width=12,
                                 values=["all", "login", "logout", "create", "update", "delete", "view"], state="readonly")
    action_combo.pack(side="left", padx=5)

    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Time", "User", "Action", "Source", "Details")
    self.audit_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=18)
    for col in columns:
        self.audit_tree.heading(col, text=col)
    self.audit_tree.column("ID", width=50)
    self.audit_tree.column("Time", width=150)
    self.audit_tree.column("User", width=100)
    self.audit_tree.column("Action", width=80)
    self.audit_tree.column("Source", width=100)
    self.audit_tree.column("Details", width=300)

    # Store current audit data for export
    self.current_audit_data = []

    def load():
        for item in self.audit_tree.get_children():
            self.audit_tree.delete(item)

        self.current_audit_data = []
        source = source_var.get()
        action = action_var.get()

        if source == "Log Files":
            # Load from university system log files
            entries = self.load_audit_from_logs(action)
            for entry in entries:
                self.audit_tree.insert("", "end", values=(
                    entry['id'],
                    entry['timestamp'],
                    entry['user'],
                    entry['action'],
                    entry['entity'],
                    entry['details']
                ))
                self.current_audit_data.append(entry)

            if not entries:
                # Show message if no entries found
                self.audit_tree.insert("", "end", values=(
                    "-", "-", "-", "-", "-", "No log entries found in logs directory"
                ))
        else:
            # Load from database (fallback)
            try:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                if action == "all":
                    cursor.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 200")
                else:
                    cursor.execute("SELECT * FROM audit_log WHERE action = ? ORDER BY timestamp DESC LIMIT 200", (action,))
                for row in cursor.fetchall():
                    details = f"{row[5]}:{row[6]}" if len(row) > 6 and row[5] and row[6] else "-"
                    timestamp = row[10] if len(row) > 10 else row[1] if len(row) > 1 else "-"
                    user = row[3] if len(row) > 3 else row[1] if len(row) > 1 else "-"
                    action_val = row[4] if len(row) > 4 else "-"
                    entity = row[5] if len(row) > 5 else "-"
                    self.audit_tree.insert("", "end", values=(row[0], timestamp, user, action_val, entity, details))
                    self.current_audit_data.append({
                        'id': row[0], 'timestamp': timestamp, 'user': user,
                        'action': action_val, 'entity': entity, 'details': details
                    })
                conn.close()
            except Exception as e:
                self.audit_tree.insert("", "end", values=(
                    "-", "-", "-", "-", "-", f"Database error: {str(e)}"
                ))

    ttk.Button(filter_frame, text=_t("cinema.buttons.refresh"), style="Primary.TButton", command=load).pack(side="left", padx=5)
    ttk.Button(filter_frame, text=_t("cinema.btn.export_csv"), style="Secondary.TButton", command=self.export_audit).pack(side="left", padx=5)

    # Info label showing log files location
    info_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    info_frame.pack(fill="x", pady=(0, 5))
    tk.Label(info_frame, text=_t("cinema.labels.log_files_location"),
             font=("Helvetica", 9), fg="#7f8c8d", bg="#ecf0f1").pack(anchor="w")

    self.audit_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.audit_tree.yview)
    self.audit_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    load()

def export_audit(self):
    """Export current audit log view to CSV file."""
    filename = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV", "*.csv")],
        initialfile=f"audit_{datetime.now().strftime('%Y%m%d')}.csv"
    )
    if not filename:
        return

    try:
        # Use current displayed data (from log files or database)
        if hasattr(self, 'current_audit_data') and self.current_audit_data:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Timestamp", "User", "Action", "Source", "Details"])
                for entry in self.current_audit_data:
                    writer.writerow([
                        entry.get('id', ''),
                        entry.get('timestamp', ''),
                        entry.get('user', ''),
                        entry.get('action', ''),
                        entry.get('entity', ''),
                        entry.get('details', '')
                    ])
            messagebox.showinfo(_t("cinema.common.success"), f"Exported {len(self.current_audit_data)} entries to {filename}")
        else:
            # Fallback to database if no current data
            conn = sqlite3.connect(DB_FILE)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM audit_log ORDER BY timestamp DESC")
                data = cursor.fetchall()
            finally:
                conn.close()
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "User Type", "User ID", "User Name", "Action", "Entity Type", "Entity ID", "Old Value", "New Value", "IP", "Timestamp"])
                writer.writerows(data)
            messagebox.showinfo(_t("cinema.common.success"), f"Exported to {filename}")
    except Exception as e:
        messagebox.showerror(_t("cinema.common.error"), f"Export failed: {str(e)}")
