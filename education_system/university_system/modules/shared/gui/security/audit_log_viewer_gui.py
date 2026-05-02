#!/usr/bin/env python3
"""
Audit Log Viewer GUI

A comprehensive GUI for searching, filtering, and analyzing audit logs
with export capabilities and anomaly detection alerts.
"""

import csv
import json
import logging
import os
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any, Callable, Dict, List, Optional, Tuple

from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, DEFAULT_DB_PATH
from education_system.university_system.infrastructure.security.audit_trail import (
    AuditLogger,
    AuditEntry,
    AuditAction,
    get_audit_logger,
)
from education_system.university_system.core.sql_safety import validate_table_name
from education_system.university_system.core.i18n import get_text as _t, init_i18n
init_i18n()

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detects anomalies in audit log patterns."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._thresholds = {
            'failed_logins_per_user': 5,  # per hour
            'failed_logins_total': 20,  # per hour
            'bulk_exports_per_user': 3,  # per day
            'permission_changes': 10,  # per hour
            'after_hours_access': True,  # 22:00 - 06:00
            'rapid_actions': 100,  # actions per minute per user
        }

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect anomalies in recent audit logs."""
        anomalies = []

        with get_connection(self.db_path) as conn:
            # Failed logins per user (last hour)
            cursor = conn.execute("""
                SELECT username, COUNT(*) as count
                FROM audit_trail
                WHERE action = 'login' AND success = 0
                  AND timestamp > datetime('now', '-1 hour')
                GROUP BY username
                HAVING count >= ?
            """, (self._thresholds['failed_logins_per_user'],))

            for row in cursor.fetchall():
                anomalies.append({
                    'type': 'failed_logins',
                    'severity': 'high',
                    'message': f"User '{row[0]}' has {row[1]} failed login attempts in the last hour",
                    'user': row[0],
                    'count': row[1],
                })

            # Total failed logins (last hour)
            cursor = conn.execute("""
                SELECT COUNT(*) FROM audit_trail
                WHERE action = 'login' AND success = 0
                  AND timestamp > datetime('now', '-1 hour')
            """)
            total_failed = cursor.fetchone()[0]
            if total_failed >= self._thresholds['failed_logins_total']:
                anomalies.append({
                    'type': 'brute_force_attempt',
                    'severity': 'critical',
                    'message': f"Possible brute force attack: {total_failed} failed logins in the last hour",
                    'count': total_failed,
                })

            # Bulk exports per user (last day)
            cursor = conn.execute("""
                SELECT username, COUNT(*) as count
                FROM audit_trail
                WHERE action = 'export'
                  AND timestamp > datetime('now', '-1 day')
                GROUP BY username
                HAVING count >= ?
            """, (self._thresholds['bulk_exports_per_user'],))

            for row in cursor.fetchall():
                anomalies.append({
                    'type': 'excessive_exports',
                    'severity': 'warning',
                    'message': f"User '{row[0]}' has exported data {row[1]} times today",
                    'user': row[0],
                    'count': row[1],
                })

            # Rapid actions (last minute)
            cursor = conn.execute("""
                SELECT username, COUNT(*) as count
                FROM audit_trail
                WHERE timestamp > datetime('now', '-1 minute')
                GROUP BY username
                HAVING count >= ?
            """, (self._thresholds['rapid_actions'],))

            for row in cursor.fetchall():
                anomalies.append({
                    'type': 'rapid_actions',
                    'severity': 'warning',
                    'message': f"User '{row[0]}' performed {row[1]} actions in the last minute",
                    'user': row[0],
                    'count': row[1],
                })

            # After hours access
            if self._thresholds['after_hours_access']:
                current_hour = datetime.now().hour
                if current_hour >= 22 or current_hour < 6:
                    cursor = conn.execute("""
                        SELECT DISTINCT username
                        FROM audit_trail
                        WHERE timestamp > datetime('now', '-10 minute')
                          AND username IS NOT NULL
                    """)
                    for row in cursor.fetchall():
                        anomalies.append({
                            'type': 'after_hours_access',
                            'severity': 'info',
                            'message': f"User '{row[0]}' is active during off-hours",
                            'user': row[0],
                        })

        return anomalies


class AuditLogViewerGUI(tk.Toplevel):
    """
    Comprehensive Audit Log Viewer with search, filter, export, and anomaly detection.
    """

    def __init__(self, parent, admin_user_id: Optional[int] = None,
                 prefilter: Optional[dict] = None):
        super().__init__(parent)

        self.admin_user_id = admin_user_id
        self.audit_logger = get_audit_logger()
        self.anomaly_detector = AnomalyDetector()
        self._auto_refresh = tk.BooleanVar(value=False)
        self._refresh_interval = 5000  # 5 seconds
        self._refresh_job = None
        self._current_entries: List[AuditEntry] = []

        self.title(_t("audit_log.title"))
        self.geometry("1200x800")
        self.minsize(900, 600)

        self._create_widgets()
        self._load_filter_options()
        self._apply_prefilter(prefilter)
        self._search_logs()

        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        # Bind close event
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_widgets(self):
        """Create all GUI widgets."""
        # Header
        header_frame = tk.Frame(self, bg="#2C3E50", height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        tk.Label(
            header_frame,
            text=_t("audit_log.title"),
            font=("Arial", 16, "bold"),
            bg="#2C3E50",
            fg="white"
        ).pack(side=tk.LEFT, padx=20, pady=15)

        # Header buttons
        ttk.Button(
            header_frame,
            text=_t("common.refresh"),
            command=self._search_logs
        ).pack(side=tk.RIGHT, padx=5, pady=15)

        ttk.Button(
            header_frame,
            text=_t("common.close"),
            command=self._on_close
        ).pack(side=tk.RIGHT, padx=5, pady=15)

        # Search and Filter Frame
        filter_frame = tk.LabelFrame(self, text=_t("audit_log.search_filters"), padx=10, pady=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 1: Search
        row1 = tk.Frame(filter_frame)
        row1.pack(fill=tk.X, pady=5)

        tk.Label(row1, text=_t("audit_log.labels.search"), width=8, anchor=tk.W).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(row1, textvariable=self.search_var, width=50)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind('<Return>', lambda e: self._search_logs())

        ttk.Button(row1, text=_t("common.search"), command=self._search_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(row1, text=_t("audit_log.buttons.clear_filters"), command=self._clear_filters).pack(side=tk.LEFT, padx=5)

        # Row 2: User and Action filters
        row2 = tk.Frame(filter_frame)
        row2.pack(fill=tk.X, pady=5)

        tk.Label(row2, text=_t("audit_log.labels.user"), width=8, anchor=tk.W).pack(side=tk.LEFT)
        self.user_var = tk.StringVar(value=_t("audit_log.all_users"))
        self.user_combo = ttk.Combobox(row2, textvariable=self.user_var, width=20, state="readonly")
        self.user_combo.pack(side=tk.LEFT, padx=5)
        self.user_combo.bind('<<ComboboxSelected>>', lambda e: self._search_logs())

        tk.Label(row2, text=_t("audit_log.labels.action"), width=8, anchor=tk.W).pack(side=tk.LEFT, padx=(20, 0))
        self.action_var = tk.StringVar(value=_t("audit_log.all_actions"))
        self.action_combo = ttk.Combobox(row2, textvariable=self.action_var, width=20, state="readonly")
        self.action_combo.pack(side=tk.LEFT, padx=5)
        self.action_combo.bind('<<ComboboxSelected>>', lambda e: self._search_logs())

        tk.Label(row2, text=_t("audit_log.labels.resource"), width=10, anchor=tk.W).pack(side=tk.LEFT, padx=(20, 0))
        self.resource_var = tk.StringVar(value=_t("audit_log.all_resources"))
        self.resource_combo = ttk.Combobox(row2, textvariable=self.resource_var, width=20, state="readonly")
        self.resource_combo.pack(side=tk.LEFT, padx=5)
        self.resource_combo.bind('<<ComboboxSelected>>', lambda e: self._search_logs())

        # Row 3: Date range
        row3 = tk.Frame(filter_frame)
        row3.pack(fill=tk.X, pady=5)

        tk.Label(row3, text=_t("audit_log.labels.from"), width=8, anchor=tk.W).pack(side=tk.LEFT)
        self.from_date_var = tk.StringVar(value=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        self.from_date_entry = ttk.Entry(row3, textvariable=self.from_date_var, width=12)
        self.from_date_entry.pack(side=tk.LEFT, padx=5)

        tk.Label(row3, text=_t("audit_log.labels.to"), width=4, anchor=tk.W).pack(side=tk.LEFT, padx=(10, 0))
        self.to_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        self.to_date_entry = ttk.Entry(row3, textvariable=self.to_date_var, width=12)
        self.to_date_entry.pack(side=tk.LEFT, padx=5)

        # Quick date filters
        tk.Label(row3, text=_t("audit_log.labels.quick"), width=6, anchor=tk.W).pack(side=tk.LEFT, padx=(20, 0))
        ttk.Button(row3, text=_t("audit_log.buttons.today"), width=8, command=lambda: self._set_date_range(0)).pack(side=tk.LEFT, padx=2)
        ttk.Button(row3, text=_t("audit_log.buttons.7_days"), width=8, command=lambda: self._set_date_range(7)).pack(side=tk.LEFT, padx=2)
        ttk.Button(row3, text=_t("audit_log.buttons.30_days"), width=8, command=lambda: self._set_date_range(30)).pack(side=tk.LEFT, padx=2)
        ttk.Button(row3, text=_t("audit_log.buttons.90_days"), width=8, command=lambda: self._set_date_range(90)).pack(side=tk.LEFT, padx=2)

        # Row 4: Severity and status
        row4 = tk.Frame(filter_frame)
        row4.pack(fill=tk.X, pady=5)

        tk.Label(row4, text=_t("audit_log.labels.status"), width=8, anchor=tk.W).pack(side=tk.LEFT)

        self.success_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row4, text=_t("common.success"), variable=self.success_var,
                        command=self._search_logs).pack(side=tk.LEFT, padx=5)

        self.failure_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row4, text=_t("common.failed"), variable=self.failure_var,
                        command=self._search_logs).pack(side=tk.LEFT, padx=5)

        # Auto-refresh
        tk.Label(row4, text="", width=10).pack(side=tk.LEFT)  # Spacer
        ttk.Checkbutton(
            row4,
            text=_t("audit_log.auto_refresh"),
            variable=self._auto_refresh,
            command=self._toggle_auto_refresh
        ).pack(side=tk.LEFT, padx=20)

        # Results info
        self.results_label = tk.Label(row4, text="", font=("Arial", 9), fg="gray")
        self.results_label.pack(side=tk.RIGHT, padx=10)

        # Main content area with notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Log entries tab
        self._create_log_entries_tab()

        # Anomaly alerts tab
        self._create_anomaly_tab()

        # Statistics tab
        self._create_statistics_tab()

        # Button bar
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text=_t("audit_log.buttons.export_csv"), command=self._export_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("audit_log.buttons.export_pdf"), command=self._export_pdf).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("audit_log.buttons.view_details"), command=self._view_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("audit_log.buttons.check_anomalies"), command=self._check_anomalies).pack(side=tk.LEFT, padx=5)

        # Status bar
        self.status_var = tk.StringVar(value=_t("common.ready"))
        status_bar = tk.Label(self, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _create_log_entries_tab(self):
        """Create the log entries tab."""
        tab = tk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("audit_log.tabs.log_entries"))

        # Treeview for log entries
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("timestamp", "user", "action", "resource", "resource_id", "status", "details")
        self.log_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)

        # Column headings and widths
        self.log_tree.heading("timestamp", text=_t("audit_log.columns.time"), command=lambda: self._sort_column("timestamp"))
        self.log_tree.heading("user", text=_t("audit_log.columns.user"), command=lambda: self._sort_column("user"))
        self.log_tree.heading("action", text=_t("audit_log.columns.action"), command=lambda: self._sort_column("action"))
        self.log_tree.heading("resource", text=_t("audit_log.columns.resource"), command=lambda: self._sort_column("resource"))
        self.log_tree.heading("resource_id", text=_t("audit_log.columns.resource_id"), command=lambda: self._sort_column("resource_id"))
        self.log_tree.heading("status", text=_t("audit_log.columns.status"), command=lambda: self._sort_column("status"))
        self.log_tree.heading("details", text=_t("audit_log.columns.details"), command=lambda: self._sort_column("details"))

        self.log_tree.column("timestamp", width=150, minwidth=120)
        self.log_tree.column("user", width=100, minwidth=80)
        self.log_tree.column("action", width=100, minwidth=80)
        self.log_tree.column("resource", width=120, minwidth=100)
        self.log_tree.column("resource_id", width=100, minwidth=80)
        self.log_tree.column("status", width=80, minwidth=60)
        self.log_tree.column("details", width=300, minwidth=200)

        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.log_tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.log_tree.xview)
        self.log_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        # Grid layout
        self.log_tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Configure tags for status coloring
        self.log_tree.tag_configure('success', foreground='#27AE60')
        self.log_tree.tag_configure('failure', foreground='#E74C3C')
        self.log_tree.tag_configure('warning', foreground='#F39C12')

        # Double-click to view details
        self.log_tree.bind('<Double-1>', lambda e: self._view_details())

    def _create_anomaly_tab(self):
        """Create the anomaly alerts tab."""
        tab = tk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("audit_log.tabs.anomaly_alerts"))

        # Header
        header = tk.Frame(tab, bg="#E74C3C", height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text=_t("audit_log.security_anomaly_detection"),
            font=("Arial", 12, "bold"),
            bg="#E74C3C",
            fg="white"
        ).pack(side=tk.LEFT, padx=10, pady=8)

        ttk.Button(header, text=_t("audit_log.buttons.refresh_alerts"), command=self._check_anomalies).pack(side=tk.RIGHT, padx=10, pady=5)

        # Anomaly list
        anomaly_frame = tk.Frame(tab)
        anomaly_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ("severity", "type", "message", "user", "count")
        self.anomaly_tree = ttk.Treeview(anomaly_frame, columns=columns, show="headings", height=15)

        self.anomaly_tree.heading("severity", text=_t("audit_log.columns.severity"))
        self.anomaly_tree.heading("type", text=_t("audit_log.columns.type"))
        self.anomaly_tree.heading("message", text=_t("audit_log.columns.message"))
        self.anomaly_tree.heading("user", text=_t("audit_log.columns.user"))
        self.anomaly_tree.heading("count", text=_t("audit_log.columns.count"))

        self.anomaly_tree.column("severity", width=80)
        self.anomaly_tree.column("type", width=150)
        self.anomaly_tree.column("message", width=400)
        self.anomaly_tree.column("user", width=100)
        self.anomaly_tree.column("count", width=80)

        scrollbar = ttk.Scrollbar(anomaly_frame, orient=tk.VERTICAL, command=self.anomaly_tree.yview)
        self.anomaly_tree.configure(yscrollcommand=scrollbar.set)

        self.anomaly_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure severity tags
        self.anomaly_tree.tag_configure('critical', foreground='white', background='#C0392B')
        self.anomaly_tree.tag_configure('high', foreground='white', background='#E74C3C')
        self.anomaly_tree.tag_configure('warning', foreground='black', background='#F39C12')
        self.anomaly_tree.tag_configure('info', foreground='black', background='#3498DB')

    def _create_statistics_tab(self):
        """Create the statistics tab."""
        tab = tk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("audit_log.tabs.statistics"))

        # Stats cards frame
        cards_frame = tk.Frame(tab)
        cards_frame.pack(fill=tk.X, padx=20, pady=20)

        self.stat_labels = {}
        stats = [
            ("total_entries", _t("audit_log.stats.total_entries"), "#3498DB"),
            ("unique_users", _t("audit_log.stats.unique_users"), "#9B59B6"),
            ("success_rate", _t("audit_log.stats.success_rate"), "#27AE60"),
            ("logins_today", _t("audit_log.stats.logins_today"), "#E67E22"),
            ("failures_today", _t("audit_log.stats.failures_today"), "#E74C3C"),
            ("exports_today", _t("audit_log.stats.exports_today"), "#16A085"),
        ]

        for i, (key, label, color) in enumerate(stats):
            card = tk.Frame(cards_frame, bg="#F8F9FA", relief=tk.RIDGE, borderwidth=2, width=150, height=100)
            card.grid(row=0, column=i, padx=10, pady=10, sticky="nsew")
            card.grid_propagate(False)

            tk.Label(card, text=label, font=("Arial", 9), bg="#F8F9FA", fg="gray").pack(pady=(15, 0))
            value_label = tk.Label(card, text="0", font=("Arial", 20, "bold"), bg="#F8F9FA", fg=color)
            value_label.pack(pady=(0, 15))
            self.stat_labels[key] = value_label

        for i in range(len(stats)):
            cards_frame.grid_columnconfigure(i, weight=1)

        # Actions breakdown
        actions_frame = tk.LabelFrame(tab, text=_t("audit_log.actions_breakdown"), padx=10, pady=10)
        actions_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.actions_text = scrolledtext.ScrolledText(actions_frame, height=15, font=("Courier", 10))
        self.actions_text.pack(fill=tk.BOTH, expand=True)

    def _load_filter_options(self):
        """Load filter options from database."""
        try:
            with get_connection(self.audit_logger.db_path) as conn:
                # Get unique users
                cursor = conn.execute(f"""
                    SELECT DISTINCT username FROM [{self.audit_logger.TABLE_NAME}]
                    WHERE username IS NOT NULL
                    ORDER BY username
                """)
                users = ["All Users"] + [row[0] for row in cursor.fetchall()]
                self.user_combo['values'] = users

                # Get unique actions
                cursor = conn.execute(f"""
                    SELECT DISTINCT action FROM [{self.audit_logger.TABLE_NAME}]
                    ORDER BY action
                """)
                actions = ["All Actions"] + [row[0] for row in cursor.fetchall()]
                self.action_combo['values'] = actions

                # Get unique resource types
                cursor = conn.execute(f"""
                    SELECT DISTINCT resource_type FROM [{self.audit_logger.TABLE_NAME}]
                    ORDER BY resource_type
                """)
                resources = ["All Resources"] + [row[0] for row in cursor.fetchall()]
                self.resource_combo['values'] = resources

        except Exception as e:
            logger.error(f"Error loading filter options: {e}")

    def _search_logs(self):
        """Search and filter audit logs."""
        self.status_var.set(_t("audit_log.searching"))
        self.update_idletasks()

        try:
            # Build query
            conditions = []
            params = []

            # Search text
            search_text = self.search_var.get().strip()
            if search_text:
                conditions.append("""
                    (username LIKE ? OR action LIKE ? OR resource_type LIKE ?
                     OR resource_id LIKE ? OR details LIKE ? OR error_message LIKE ?)
                """)
                search_pattern = f"%{escape_like(search_text)}%"
                params.extend([search_pattern] * 6)

            # User filter
            user = self.user_var.get()
            if user and user != "All Users":
                conditions.append("username = ?")
                params.append(user)

            # Action filter
            action = self.action_var.get()
            if action and action != "All Actions":
                conditions.append("action = ?")
                params.append(action)

            # Resource filter
            resource = self.resource_var.get()
            if resource and resource != "All Resources":
                conditions.append("resource_type = ?")
                params.append(resource)

            # Date range
            from_date = self.from_date_var.get()
            to_date = self.to_date_var.get()
            if from_date:
                conditions.append("timestamp >= ?")
                params.append(f"{from_date} 00:00:00")
            if to_date:
                conditions.append("timestamp <= ?")
                params.append(f"{to_date} 23:59:59")

            # Status filter
            if self.success_var.get() and not self.failure_var.get():
                conditions.append("success = 1")
            elif self.failure_var.get() and not self.success_var.get():
                conditions.append("success = 0")
            elif not self.success_var.get() and not self.failure_var.get():
                # No results if neither checked
                self._clear_results()
                return

            # Build query
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            query = f"""
                SELECT timestamp, action, resource_type, resource_id, user_id,
                       username, ip_address, details, function_name, module_name,
                       success, error_message, data_hash
                FROM [{self.audit_logger.TABLE_NAME}]
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT 1000
            """

            # Execute query
            with get_connection(self.audit_logger.db_path) as conn:
                cursor = conn.execute(query, params)

                self._current_entries = []
                for row in cursor.fetchall():
                    entry = AuditEntry(
                        timestamp=datetime.fromisoformat(row[0]) if row[0] else datetime.now(),
                        action=row[1] or '',
                        resource_type=row[2] or '',
                        resource_id=row[3],
                        user_id=row[4],
                        username=row[5],
                        ip_address=row[6],
                        details=json.loads(row[7]) if row[7] else {},
                        function_name=row[8],
                        module_name=row[9],
                        success=bool(row[10]),
                        error_message=row[11],
                        data_hash=row[12],
                    )
                    self._current_entries.append(entry)

            # Update UI
            self._populate_log_tree()
            self._update_statistics()
            self.results_label.config(text=_t("audit_log.found_entries", count=len(self._current_entries)))
            self.status_var.set(_t("audit_log.loaded_entries", count=len(self._current_entries)))

        except Exception as e:
            logger.error(f"Error searching logs: {e}")
            self.status_var.set(f"{_t('common.error')}: {str(e)}")
            messagebox.showerror(_t("audit_log.search_error"), f"{_t('audit_log.failed_search')}: {str(e)}")

    def _populate_log_tree(self):
        """Populate the log treeview with entries."""
        self.log_tree.delete(*self.log_tree.get_children())

        for entry in self._current_entries:
            # Format timestamp
            timestamp_str = entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')

            # Format status
            status = _t("common.success") if entry.success else _t("common.failed")

            # Format details
            details_str = ""
            if entry.details:
                details_str = json.dumps(entry.details)[:100]
            if entry.error_message:
                details_str = f"{_t('common.error')}: {entry.error_message[:80]}"

            # Determine tag
            tag = 'success' if entry.success else 'failure'

            self.log_tree.insert('', tk.END, values=(
                timestamp_str,
                entry.username or 'System',
                entry.action,
                entry.resource_type,
                entry.resource_id or '-',
                status,
                details_str,
            ), tags=(tag,))

    def _update_statistics(self):
        """Update statistics display."""
        try:
            safe_table = validate_table_name(self.audit_logger.TABLE_NAME)
            with get_connection(self.audit_logger.db_path) as conn:
                # Total entries
                cursor = conn.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
                self.stat_labels['total_entries'].config(text=str(cursor.fetchone()[0]))

                # Unique users
                cursor = conn.execute(
                    "SELECT COUNT(DISTINCT username) FROM [" + safe_table + "]"
                    " WHERE username IS NOT NULL"
                )
                self.stat_labels['unique_users'].config(text=str(cursor.fetchone()[0]))

                # Success rate
                cursor = conn.execute(
                    "SELECT"
                    "    ROUND(100.0 * SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) / COUNT(*), 1)"
                    " FROM [" + safe_table + "]"
                )
                rate = cursor.fetchone()[0] or 0
                self.stat_labels['success_rate'].config(text=f"{rate}%")

                # Logins today
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM [" + safe_table + "]"
                    " WHERE action = 'login' AND success = 1"
                    "   AND timestamp > datetime('now', 'start of day')"
                )
                self.stat_labels['logins_today'].config(text=str(cursor.fetchone()[0]))

                # Failures today
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM [" + safe_table + "]"
                    " WHERE success = 0"
                    "   AND timestamp > datetime('now', 'start of day')"
                )
                self.stat_labels['failures_today'].config(text=str(cursor.fetchone()[0]))

                # Exports today
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM [" + safe_table + "]"
                    " WHERE action = 'export'"
                    "   AND timestamp > datetime('now', 'start of day')"
                )
                self.stat_labels['exports_today'].config(text=str(cursor.fetchone()[0]))

                # Actions breakdown
                cursor = conn.execute(
                    "SELECT action, COUNT(*) as count"
                    " FROM [" + safe_table + "]"
                    " GROUP BY action"
                    " ORDER BY count DESC"
                )

                self.actions_text.delete('1.0', tk.END)
                self.actions_text.insert(tk.END, f"{_t('audit_log.actions_breakdown')}:\n")
                self.actions_text.insert(tk.END, "-" * 40 + "\n")
                for row in cursor.fetchall():
                    self.actions_text.insert(tk.END, f"{row[0]:<20} {row[1]:>10}\n")

        except Exception as e:
            logger.error(f"Error updating statistics: {e}")

    def _check_anomalies(self):
        """Check for anomalies and display alerts."""
        self.status_var.set(_t("audit_log.checking_anomalies"))
        self.update_idletasks()

        try:
            anomalies = self.anomaly_detector.detect_anomalies()

            # Clear existing entries
            self.anomaly_tree.delete(*self.anomaly_tree.get_children())

            if not anomalies:
                self.anomaly_tree.insert('', tk.END, values=(
                    "info", _t("audit_log.no_anomalies"), _t("audit_log.no_anomalies_detected"), "-", "-"
                ), tags=('info',))
            else:
                for anomaly in anomalies:
                    severity = anomaly.get('severity', 'info')
                    self.anomaly_tree.insert('', tk.END, values=(
                        severity.upper(),
                        anomaly.get('type', 'unknown'),
                        anomaly.get('message', ''),
                        anomaly.get('user', '-'),
                        anomaly.get('count', '-'),
                    ), tags=(severity,))

            # Switch to anomaly tab if critical/high found
            critical_count = sum(1 for a in anomalies if a.get('severity') in ('critical', 'high'))
            if critical_count > 0:
                self.notebook.select(1)  # Anomaly tab
                messagebox.showwarning(
                    _t("audit_log.security_alert"),
                    _t("audit_log.critical_anomalies_detected", count=critical_count)
                )

            self.status_var.set(_t("audit_log.found_anomalies", count=len(anomalies)))

        except Exception as e:
            logger.error(f"Error checking anomalies: {e}")
            self.status_var.set(f"{_t('common.error')}: {str(e)}")

    def _view_details(self):
        """View details of selected log entry."""
        selection = self.log_tree.selection()
        if not selection:
            messagebox.showinfo(_t("audit_log.no_selection"), _t("audit_log.select_entry_to_view"))
            return

        # Get the index of the selected item
        item_id = selection[0]
        item_index = self.log_tree.index(item_id)

        if item_index >= len(self._current_entries):
            return

        entry = self._current_entries[item_index]

        # Create details window
        details_window = tk.Toplevel(self)
        details_window.title(_t("audit_log.entry_details"))
        details_window.geometry("600x500")
        details_window.transient(self)

        # Details text
        text = scrolledtext.ScrolledText(details_window, wrap=tk.WORD, font=("Courier", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        status_text = _t("common.success") if entry.success else _t("common.failed")
        # Format details
        details = f"""{_t("audit_log.entry_details")}
{'=' * 50}

{_t("audit_log.details.timestamp")}:     {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
{_t("audit_log.details.action")}:        {entry.action}
{_t("audit_log.details.resource_type")}: {entry.resource_type}
{_t("audit_log.details.resource_id")}:   {entry.resource_id or 'N/A'}

{_t("audit_log.details.user_id")}:       {entry.user_id or 'N/A'}
{_t("audit_log.details.username")}:      {entry.username or 'System'}
{_t("audit_log.details.ip_address")}:    {entry.ip_address or 'N/A'}

{_t("audit_log.details.status")}:        {status_text}
{_t("audit_log.details.error_message")}: {entry.error_message or _t("common.none")}

{_t("audit_log.details.function")}:      {entry.function_name or 'N/A'}
{_t("audit_log.details.module")}:        {entry.module_name or 'N/A'}
{_t("audit_log.details.data_hash")}:     {entry.data_hash or 'N/A'}

{_t("audit_log.details.details")}:
{json.dumps(entry.details, indent=2) if entry.details else _t("common.none")}
"""
        text.insert(tk.END, details)
        text.config(state=tk.DISABLED)

        ttk.Button(details_window, text=_t("common.close"), command=details_window.destroy).pack(pady=10)

    def _export_csv(self):
        """Export current results to CSV."""
        if not self._current_entries:
            messagebox.showinfo(_t("audit_log.no_data"), _t("audit_log.no_entries_to_export"))
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Timestamp', 'User', 'Action', 'Resource Type', 'Resource ID',
                    'Status', 'IP Address', 'Function', 'Module', 'Error Message', 'Details'
                ])

                for entry in self._current_entries:
                    writer.writerow([
                        entry.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        entry.username or 'System',
                        entry.action,
                        entry.resource_type,
                        entry.resource_id or '',
                        'Success' if entry.success else 'Failure',
                        entry.ip_address or '',
                        entry.function_name or '',
                        entry.module_name or '',
                        entry.error_message or '',
                        json.dumps(entry.details) if entry.details else '',
                    ])

            messagebox.showinfo(_t("audit_log.export_complete"), _t("audit_log.exported_entries", count=len(self._current_entries), path=file_path))
            self.status_var.set(_t("audit_log.exported_to", path=file_path))

        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            messagebox.showerror(_t("audit_log.export_error"), f"{_t('audit_log.failed_export')}: {str(e)}")

    def _export_pdf(self):
        """Export current results to PDF."""
        if not self._current_entries:
            messagebox.showinfo(_t("audit_log.no_data"), _t("audit_log.no_entries_to_export"))
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )

        if not file_path:
            return

        try:
            # Try to use reportlab for PDF generation
            try:
                from reportlab.lib import colors
                from reportlab.lib.pagesizes import letter, landscape
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import inch
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

                doc = SimpleDocTemplate(file_path, pagesize=landscape(letter))
                elements = []
                styles = getSampleStyleSheet()

                # Title
                title_style = ParagraphStyle(
                    'Title',
                    parent=styles['Heading1'],
                    fontSize=16,
                    spaceAfter=20,
                )
                elements.append(Paragraph(_t("audit_log.report_title"), title_style))
                elements.append(Paragraph(
                    f"{_t('audit_log.generated')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    styles['Normal']
                ))
                elements.append(Paragraph(f"{_t('audit_log.total_entries')}: {len(self._current_entries)}", styles['Normal']))
                elements.append(Spacer(1, 0.25 * inch))

                # Table data
                data = [['Timestamp', 'User', 'Action', 'Resource', 'Status', 'Details']]
                for entry in self._current_entries[:500]:  # Limit for PDF
                    details_str = entry.error_message[:30] if entry.error_message else ''
                    data.append([
                        entry.timestamp.strftime('%m/%d %H:%M'),
                        (entry.username or 'System')[:15],
                        entry.action[:15],
                        entry.resource_type[:15],
                        'OK' if entry.success else 'FAIL',
                        details_str,
                    ])

                table = Table(data, repeatRows=1)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))

                elements.append(table)
                doc.build(elements)

                messagebox.showinfo(_t("audit_log.export_complete"), _t("audit_log.exported_to_pdf", path=file_path))
                self.status_var.set(_t("audit_log.exported_to", path=file_path))

            except ImportError:
                # Fallback: Export as text file with .pdf extension note
                messagebox.showwarning(
                    _t("audit_log.pdf_not_available"),
                    _t("audit_log.reportlab_not_installed")
                )

                # Export as formatted text
                text_path = file_path.replace('.pdf', '.txt')
                with open(text_path, 'w', encoding='utf-8') as f:
                    f.write(f"{_t('audit_log.report_title')}\n")
                    f.write(f"{_t('audit_log.generated')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"{_t('audit_log.total_entries')}: {len(self._current_entries)}\n")
                    f.write("=" * 80 + "\n\n")

                    for entry in self._current_entries:
                        f.write(f"Time: {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"User: {entry.username or 'System'}\n")
                        f.write(f"Action: {entry.action}\n")
                        f.write(f"Resource: {entry.resource_type}\n")
                        f.write(f"Status: {'Success' if entry.success else 'Failure'}\n")
                        if entry.error_message:
                            f.write(f"Error: {entry.error_message}\n")
                        f.write("-" * 40 + "\n")

                messagebox.showinfo(_t("audit_log.export_complete"), _t("audit_log.exported_to", path=text_path))

        except Exception as e:
            logger.error(f"Error exporting to PDF: {e}")
            messagebox.showerror(_t("audit_log.export_error"), f"{_t('audit_log.failed_export')}: {str(e)}")

    def _clear_filters(self):
        """Clear all filters and reset to defaults."""
        self.search_var.set("")
        self.user_var.set(_t("audit_log.all_users"))
        self.action_var.set(_t("audit_log.all_actions"))
        self.resource_var.set(_t("audit_log.all_resources"))
        self.from_date_var.set((datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        self.to_date_var.set(datetime.now().strftime('%Y-%m-%d'))
        self.success_var.set(True)
        self.failure_var.set(True)
        self._search_logs()

    def _clear_results(self):
        """Clear the results display."""
        self.log_tree.delete(*self.log_tree.get_children())
        self._current_entries = []
        self.results_label.config(text=_t("audit_log.no_results"))
        self.status_var.set(_t("common.ready"))

    def _set_date_range(self, days: int):
        """Set date range to last N days."""
        if days == 0:
            # Today only
            today = datetime.now().strftime('%Y-%m-%d')
            self.from_date_var.set(today)
            self.to_date_var.set(today)
        else:
            self.from_date_var.set((datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'))
            self.to_date_var.set(datetime.now().strftime('%Y-%m-%d'))
        self._search_logs()

    def _sort_column(self, col: str):
        """Sort treeview by column."""
        # This is a simple implementation - could be enhanced
        items = [(self.log_tree.set(item, col), item) for item in self.log_tree.get_children('')]
        items.sort(reverse=True)

        for index, (val, item) in enumerate(items):
            self.log_tree.move(item, '', index)

    def _toggle_auto_refresh(self):
        """Toggle auto-refresh functionality."""
        if self._auto_refresh.get():
            self._start_auto_refresh()
        else:
            self._stop_auto_refresh()

    def _start_auto_refresh(self):
        """Start auto-refresh timer."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self._search_logs()
        if self._auto_refresh.get():
            self._refresh_job = self.after(self._refresh_interval, self._start_auto_refresh)

    def _stop_auto_refresh(self):
        """Stop auto-refresh timer."""
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None

    def _on_close(self):
        """Handle window close."""
        self._stop_auto_refresh()
        self.destroy()

    def _apply_prefilter(self, prefilter: Optional[dict]) -> None:
        """Pre-populate the search box from a context dict.

        ``prefilter`` is the same kind of dict the academic IPC bridge
        passes between modules — e.g. ``{"book_id": "42"}`` from a
        Library books-row right-click, or ``{"loan_id": "1001"}`` from
        a fines row. The free-text ``search`` field already does a
        ``LIKE`` against ``resource_id`` / ``details`` / ``error_message``
        (see ``_search_logs``), so the cheapest accurate filter is to
        drop the most-specific id straight into that box. Order matters:
        loan_id is more specific than book_id which is more specific
        than student_id; we use the first one present."""
        if not prefilter:
            return
        for key in ("loan_id", "fine_id", "book_id", "reservation_id",
                    "reading_list_id", "student_id", "course_id",
                    "course_code", "user_id"):
            value = prefilter.get(key)
            if value is None or value == "":
                continue
            try:
                self.search_var.set(str(value))
            except Exception:
                logger.debug("audit prefilter: could not set search_var")
            break


def show_audit_log_viewer(parent, admin_user_id: Optional[int] = None,
                          prefilter: Optional[dict] = None):
    """
    Show the audit log viewer GUI.

    Args:
        parent: Parent tkinter window
        admin_user_id: Optional admin user ID for context
        prefilter: Optional context dict whose most-specific id is
            dropped into the search box before the initial query runs.

    Returns:
        AuditLogViewerGUI instance
    """
    viewer = AuditLogViewerGUI(parent, admin_user_id, prefilter=prefilter)
    return viewer


if __name__ == '__main__':
    root = tk.Tk()
    root.withdraw()

    show_audit_log_viewer(root)

    root.mainloop()
