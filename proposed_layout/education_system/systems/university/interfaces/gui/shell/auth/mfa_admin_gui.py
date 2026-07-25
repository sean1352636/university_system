#!/usr/bin/env python3
"""
MFA Admin Management GUI
Administrative interface for managing MFA policies, user MFA settings, and monitoring
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
from typing import Dict, List
from education_system.systems.university.infrastructure.auth.mfa_service import MFAService
from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n
init_i18n()

def _ensure_mfa_tables_exist():
    """No-op since 8.117.84.

    Pre-Alembic safety net that called
    ``infrastructure.database.migrations.add_mfa_system.run_migration``.
    The MFA tables are now part of the Alembic baseline
    (``migrations/versions/877b10b0175b_baseline.py``) so this hook is
    redundant. Kept as a stub so the call site in ``__init__`` doesn't
    need editing.
    """
    return

class MFAAdminPanel(tk.Toplevel):
    """
    Administrative panel for MFA management
    """

    def __init__(self, parent, admin_user_id: int):
        super().__init__(parent)

        # Ensure MFA tables exist before proceeding
        _ensure_mfa_tables_exist()

        self.parent = parent  # Store parent reference
        self.admin_user_id = admin_user_id
        self.mfa_service = MFAService()

        self.title(_("mfa_admin.title"))
        self.geometry("900x700")

        # Make resizable
        self.resizable(True, True)

        # Create UI
        self._create_widgets()
        self._load_data()

        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create main UI"""
        # Header
        header_frame = tk.Frame(self, bg="#0066cc", height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        tk.Label(
            header_frame,
            text="🛡️ " + _("mfa_admin.header"),
            font=("Arial", 14, "bold"),
            bg="#0066cc",
            fg="white"
        ).pack(pady=15)

        # Main content with tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        self._create_overview_tab()
        self._create_policies_tab()
        self._create_users_tab()
        self._create_audit_tab()
        self._create_settings_tab()

        # Footer with refresh button
        footer_frame = tk.Frame(self)
        footer_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(
            footer_frame,
            text="🔄 " + _("mfa_admin.buttons.refresh_all"),
            command=self._load_data
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            footer_frame,
            text=_("mfa_admin.buttons.close"),
            command=self.destroy
        ).pack(side=tk.RIGHT, padx=5)

    def _create_overview_tab(self):
        """Create overview/dashboard tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="📊 " + _("mfa_admin.tabs.overview"))

        # Title
        tk.Label(
            tab,
            text=_("mfa_admin.labels.system_overview"),
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=10)

        # Stats frame
        stats_frame = tk.Frame(tab, bg="white")
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Statistics cards
        self.stats_labels = {}
        stat_names = [
            ("total_users", _("mfa_admin.stats.total_users")),
            ("mfa_enabled", _("mfa_admin.stats.mfa_enabled")),
            ("mfa_required", _("mfa_admin.stats.mfa_required")),
            ("totp_users", _("mfa_admin.stats.totp_users")),
            ("sms_users", _("mfa_admin.stats.sms_users")),
            ("email_users", _("mfa_admin.stats.email_users")),
            ("recent_verifications", _("mfa_admin.stats.verifications_24h")),
            ("failed_attempts", _("mfa_admin.stats.failed_attempts_24h"))
        ]

        row = 0
        col = 0
        for key, label in stat_names:
            card = tk.Frame(
                stats_frame,
                bg="#f8f9fa",
                relief=tk.RIDGE,
                borderwidth=2
            )
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            tk.Label(
                card,
                text=label,
                font=("Arial", 9),
                bg="#f8f9fa",
                fg="gray"
            ).pack(pady=(10, 0))

            value_label = tk.Label(
                card,
                text="0",
                font=("Arial", 24, "bold"),
                bg="#f8f9fa",
                fg="#0066cc"
            )
            value_label.pack(pady=(0, 10))

            self.stats_labels[key] = value_label

            col += 1
            if col > 3:
                col = 0
                row += 1

        # Configure grid weights
        for i in range(4):
            stats_frame.grid_columnconfigure(i, weight=1)

        # Recent activity
        tk.Label(
            tab,
            text=_("mfa_admin.labels.recent_activity"),
            font=("Arial", 11, "bold"),
            bg="white"
        ).pack(pady=(20, 5))

        # Activity list
        activity_frame = tk.Frame(tab)
        activity_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.activity_tree = ttk.Treeview(
            activity_frame,
            columns=("time", "user", "method", "status"),
            show="headings",
            height=8
        )

        self.activity_tree.heading("time", text=_("mfa_admin.columns.time"))
        self.activity_tree.heading("user", text=_("mfa_admin.columns.user"))
        self.activity_tree.heading("method", text=_("mfa_admin.columns.method"))
        self.activity_tree.heading("status", text=_("mfa_admin.columns.status"))

        self.activity_tree.column("time", width=150)
        self.activity_tree.column("user", width=150)
        self.activity_tree.column("method", width=100)
        self.activity_tree.column("status", width=100)

        scrollbar = ttk.Scrollbar(activity_frame, orient=tk.VERTICAL, command=self.activity_tree.yview)
        self.activity_tree.configure(yscrollcommand=scrollbar.set)

        self.activity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _create_policies_tab(self):
        """Create MFA policies tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="📋 " + _("mfa_admin.tabs.policies"))

        tk.Label(
            tab,
            text=_("mfa_admin.labels.policies_by_role"),
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=10)

        # Policies table
        table_frame = tk.Frame(tab)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.policies_tree = ttk.Treeview(
            table_frame,
            columns=("role", "required", "methods", "min_methods", "grace_days", "device_trust"),
            show="headings",
            height=10
        )

        self.policies_tree.heading("role", text=_("mfa_admin.columns.role"))
        self.policies_tree.heading("required", text=_("mfa_admin.columns.required"))
        self.policies_tree.heading("methods", text=_("mfa_admin.columns.allowed_methods"))
        self.policies_tree.heading("min_methods", text=_("mfa_admin.columns.min_methods"))
        self.policies_tree.heading("grace_days", text=_("mfa_admin.columns.grace_period"))
        self.policies_tree.heading("device_trust", text=_("mfa_admin.columns.device_trust"))

        self.policies_tree.column("role", width=100)
        self.policies_tree.column("required", width=80)
        self.policies_tree.column("methods", width=200)
        self.policies_tree.column("min_methods", width=100)
        self.policies_tree.column("grace_days", width=100)
        self.policies_tree.column("device_trust", width=100)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.policies_tree.yview)
        self.policies_tree.configure(yscrollcommand=scrollbar.set)

        self.policies_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        button_frame = tk.Frame(tab, bg="white")
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(
            button_frame,
            text=_("mfa_admin.buttons.edit_policy"),
            command=self._edit_policy
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_("common.refresh"),
            command=self._load_policies
        ).pack(side=tk.LEFT, padx=5)

    def _create_users_tab(self):
        """Create users tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="👥 " + _("mfa_admin.tabs.users"))

        tk.Label(
            tab,
            text=_("mfa_admin.labels.user_mfa_status"),
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=10)

        # Search/filter frame
        filter_frame = tk.Frame(tab, bg="white")
        filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        tk.Label(filter_frame, text=_("mfa_admin.labels.filter"), bg="white").pack(side=tk.LEFT, padx=(0, 5))

        self.user_filter_var = tk.StringVar(value="all")
        filters = [
            (_("mfa_admin.filters.all_users"), "all"),
            (_("mfa_admin.filters.mfa_enabled"), "enabled"),
            (_("mfa_admin.filters.mfa_disabled"), "disabled"),
            (_("mfa_admin.filters.mfa_required"), "required")
        ]

        for label, value in filters:
            ttk.Radiobutton(
                filter_frame,
                text=label,
                variable=self.user_filter_var,
                value=value,
                command=self._load_users
            ).pack(side=tk.LEFT, padx=5)

        # Users table
        table_frame = tk.Frame(tab)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.users_tree = ttk.Treeview(
            table_frame,
            columns=("username", "role", "mfa_enabled", "methods", "last_verification"),
            show="headings",
            height=15
        )

        self.users_tree.heading("username", text=_("mfa_admin.columns.username"))
        self.users_tree.heading("role", text=_("mfa_admin.columns.role"))
        self.users_tree.heading("mfa_enabled", text=_("mfa_admin.columns.mfa_status"))
        self.users_tree.heading("methods", text=_("mfa_admin.columns.methods"))
        self.users_tree.heading("last_verification", text=_("mfa_admin.columns.last_verification"))

        self.users_tree.column("username", width=150)
        self.users_tree.column("role", width=100)
        self.users_tree.column("mfa_enabled", width=100)
        self.users_tree.column("methods", width=150)
        self.users_tree.column("last_verification", width=150)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=scrollbar.set)

        self.users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        button_frame = tk.Frame(tab, bg="white")
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(
            button_frame,
            text=_("mfa_admin.buttons.view_details"),
            command=self._view_user_details
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_("mfa_admin.buttons.reset_mfa"),
            command=self._reset_user_mfa
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_("mfa_admin.buttons.force_mfa_setup"),
            command=self._force_mfa_setup
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_("common.refresh"),
            command=self._load_users
        ).pack(side=tk.RIGHT, padx=5)

    def _create_audit_tab(self):
        """Create audit log tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="📜 " + _("mfa_admin.tabs.audit"))

        tk.Label(
            tab,
            text=_("mfa_admin.labels.audit_trail"),
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=10)

        # Filter options
        filter_frame = tk.Frame(tab, bg="white")
        filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        tk.Label(filter_frame, text=_("mfa_admin.labels.show"), bg="white").pack(side=tk.LEFT, padx=(0, 5))

        self.audit_filter_var = tk.StringVar(value="all")
        audit_filters = [
            (_("mfa_admin.filters.all"), "all"),
            (_("mfa_admin.filters.success"), "success"),
            (_("mfa_admin.filters.failed"), "failed"),
            (_("mfa_admin.filters.last_24h"), "24h"),
            (_("mfa_admin.filters.last_7_days"), "7d")
        ]

        for label, value in audit_filters:
            ttk.Radiobutton(
                filter_frame,
                text=label,
                variable=self.audit_filter_var,
                value=value,
                command=self._load_audit_log
            ).pack(side=tk.LEFT, padx=5)

        # Audit table
        table_frame = tk.Frame(tab)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.audit_tree = ttk.Treeview(
            table_frame,
            columns=("timestamp", "user", "method", "status", "reason", "ip"),
            show="headings",
            height=18
        )

        self.audit_tree.heading("timestamp", text=_("mfa_admin.columns.timestamp"))
        self.audit_tree.heading("user", text=_("mfa_admin.columns.user"))
        self.audit_tree.heading("method", text=_("mfa_admin.columns.method"))
        self.audit_tree.heading("status", text=_("mfa_admin.columns.status"))
        self.audit_tree.heading("reason", text=_("mfa_admin.columns.failure_reason"))
        self.audit_tree.heading("ip", text=_("mfa_admin.columns.ip_address"))

        self.audit_tree.column("timestamp", width=150)
        self.audit_tree.column("user", width=120)
        self.audit_tree.column("method", width=100)
        self.audit_tree.column("status", width=80)
        self.audit_tree.column("reason", width=200)
        self.audit_tree.column("ip", width=120)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.audit_tree.yview)
        self.audit_tree.configure(yscrollcommand=scrollbar.set)

        self.audit_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Export button
        ttk.Button(
            tab,
            text=_("mfa_admin.buttons.export_audit_log"),
            command=self._export_audit_log
        ).pack(pady=10)

    def _create_settings_tab(self):
        """Create system settings tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="⚙️ " + _("mfa_admin.tabs.settings"))

        tk.Label(
            tab,
            text=_("mfa_admin.labels.system_settings"),
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=10)

        settings_frame = tk.Frame(tab, bg="white")
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=20)

        # OTP Settings
        otp_group = tk.LabelFrame(
            settings_frame,
            text=_("mfa_admin.labels.otp_config"),
            font=("Arial", 10, "bold"),
            bg="white",
            padx=20,
            pady=15
        )
        otp_group.pack(fill=tk.X, pady=10)

        settings = [
            (_("mfa_admin.settings.otp_expiry"), "otp_expiry", "10"),
            (_("mfa_admin.settings.max_attempts"), "max_attempts", "3"),
            (_("mfa_admin.settings.lockout_duration"), "lockout_duration", "15")
        ]

        for label, key, default in settings:
            row = tk.Frame(otp_group, bg="white")
            row.pack(fill=tk.X, pady=5)

            tk.Label(row, text=label, bg="white", width=25, anchor=tk.W).pack(side=tk.LEFT)
            entry = tk.Entry(row, width=10)
            entry.insert(0, default)
            entry.pack(side=tk.LEFT, padx=10)

        # Device Trust Settings
        trust_group = tk.LabelFrame(
            settings_frame,
            text=_("mfa_admin.labels.device_trust"),
            font=("Arial", 10, "bold"),
            bg="white",
            padx=20,
            pady=15
        )
        trust_group.pack(fill=tk.X, pady=10)

        trust_settings = [
            (_("mfa_admin.settings.trust_duration"), "trust_duration", "30"),
            (_("mfa_admin.settings.max_trusted_devices"), "max_trusted", "5")
        ]

        for label, key, default in trust_settings:
            row = tk.Frame(trust_group, bg="white")
            row.pack(fill=tk.X, pady=5)

            tk.Label(row, text=label, bg="white", width=25, anchor=tk.W).pack(side=tk.LEFT)
            entry = tk.Entry(row, width=10)
            entry.insert(0, default)
            entry.pack(side=tk.LEFT, padx=10)

        # Provider Settings
        provider_group = tk.LabelFrame(
            settings_frame,
            text=_("mfa_admin.labels.provider_status"),
            font=("Arial", 10, "bold"),
            bg="white",
            padx=20,
            pady=15
        )
        provider_group.pack(fill=tk.X, pady=10)

        self.sms_provider_label = tk.Label(
            provider_group,
            text=_("mfa_admin.provider.sms_loading"),
            bg="white",
            fg="gray"
        )
        self.sms_provider_label.pack(anchor=tk.W, pady=5)

        self.email_provider_label = tk.Label(
            provider_group,
            text=_("mfa_admin.provider.email_loading"),
            bg="white",
            fg="gray"
        )
        self.email_provider_label.pack(anchor=tk.W, pady=5)

        # Buttons
        button_frame = tk.Frame(settings_frame, bg="white")
        button_frame.pack(fill=tk.X, pady=20)

        ttk.Button(
            button_frame,
            text=_("mfa_admin.buttons.save_settings"),
            command=self._save_settings
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_("mfa_admin.buttons.test_sms"),
            command=self._test_sms_provider
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_("mfa_admin.buttons.test_email"),
            command=self._test_email_provider
        ).pack(side=tk.LEFT, padx=5)

    # Data loading methods

    def _load_data(self):
        """Load all data"""
        self._load_overview()
        self._load_policies()
        self._load_users()
        self._load_audit_log()
        self._load_settings()

    def _load_overview(self):
        """Load overview statistics"""
        conn = sqlite3.connect(self.mfa_service.db_path)
        cursor = conn.cursor()

        try:
            # Total users
            cursor.execute("SELECT COUNT(*) FROM users")
            self.stats_labels['total_users'].config(text=str(cursor.fetchone()[0]))

            # MFA enabled
            cursor.execute("SELECT COUNT(*) FROM mfa_user_settings WHERE mfa_enabled = 1")
            self.stats_labels['mfa_enabled'].config(text=str(cursor.fetchone()[0]))

            # MFA required (from policies)
            cursor.execute("""
                SELECT COUNT(DISTINCT u.id)
                FROM users u
                JOIN mfa_enforcement_policies p ON u.role = p.role_name
                WHERE p.mfa_required = 1
            """)
            result = cursor.fetchone()
            self.stats_labels['mfa_required'].config(text=str(result[0] if result else 0))

            # Method counts
            for method in ['totp', 'sms', 'email']:
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id)
                    FROM mfa_methods
                    WHERE method_type = ? AND is_enabled = 1
                """, (method,))
                count = cursor.fetchone()[0]
                self.stats_labels[f'{method}_users'].config(text=str(count))

            # Recent verifications (24h)
            cursor.execute("""
                SELECT COUNT(*)
                FROM mfa_verification_attempts
                WHERE attempted_at > datetime('now', '-1 day')
                AND success = 1
            """)
            self.stats_labels['recent_verifications'].config(text=str(cursor.fetchone()[0]))

            # Failed attempts (24h)
            cursor.execute("""
                SELECT COUNT(*)
                FROM mfa_verification_attempts
                WHERE attempted_at > datetime('now', '-1 day')
                AND success = 0
            """)
            self.stats_labels['failed_attempts'].config(text=str(cursor.fetchone()[0]))

            # Recent activity
            self.activity_tree.delete(*self.activity_tree.get_children())

            cursor.execute("""
                SELECT
                    v.attempted_at,
                    u.username,
                    v.method_type,
                    CASE WHEN v.success = 1 THEN 'Success' ELSE 'Failed' END as status
                FROM mfa_verification_attempts v
                JOIN users u ON v.user_id = u.id
                ORDER BY v.attempted_at DESC
                LIMIT 50
            """)

            for row in cursor.fetchall():
                display_row = (row[0][:19] if row[0] else '', row[1], row[2],
                               _("common.success") if row[3] == 'Success' else _("common.failed"))
                tag = 'success' if row[3] == 'Success' else 'failed'
                self.activity_tree.insert('', tk.END, values=display_row, tags=(tag,))

            # Configure colors
            self.activity_tree.tag_configure('success', foreground='green')
            self.activity_tree.tag_configure('failed', foreground='red')

        finally:
            conn.close()

    def _load_policies(self):
        """Load MFA policies"""
        self.policies_tree.delete(*self.policies_tree.get_children())

        conn = sqlite3.connect(self.mfa_service.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT role_name, mfa_required, allowed_methods, minimum_methods,
                       grace_period_days, allow_device_trust
                FROM mfa_enforcement_policies
                ORDER BY role_name
            """)

            for row in cursor.fetchall():
                role, required, methods, min_methods, grace, trust = row
                required_text = _("common.yes") if required else _("common.no")
                trust_text = _("mfa_admin.status.allowed") if trust else _("common.disabled")

                self.policies_tree.insert('', tk.END, values=(
                    role,
                    required_text,
                    methods.replace('"', '').replace('[', '').replace(']', ''),
                    min_methods,
                    _("mfa_admin.status.days", count=grace),
                    trust_text
                ))

        finally:
            conn.close()

    def _load_users(self):
        """Load users MFA status"""
        self.users_tree.delete(*self.users_tree.get_children())

        conn = sqlite3.connect(self.mfa_service.db_path)
        cursor = conn.cursor()

        try:
            query = """
                SELECT
                    u.id,
                    u.username,
                    u.role,
                    COALESCE(s.mfa_enabled, 0) as mfa_enabled,
                    GROUP_CONCAT(m.method_type) as methods,
                    s.last_successful_verification
                FROM users u
                LEFT JOIN mfa_user_settings s ON u.id = s.user_id
                LEFT JOIN mfa_methods m ON u.id = m.user_id AND m.is_enabled = 1
                GROUP BY u.id
            """

            # Apply filter
            filter_value = self.user_filter_var.get()
            if filter_value == "enabled":
                query += " HAVING mfa_enabled = 1"
            elif filter_value == "disabled":
                query += " HAVING mfa_enabled = 0"
            elif filter_value == "required":
                query = """
                    SELECT
                        u.id,
                        u.username,
                        u.role,
                        COALESCE(s.mfa_enabled, 0) as mfa_enabled,
                        GROUP_CONCAT(m.method_type) as methods,
                        s.last_successful_verification
                    FROM users u
                    JOIN mfa_enforcement_policies p ON u.role = p.role_name
                    LEFT JOIN mfa_user_settings s ON u.id = s.user_id
                    LEFT JOIN mfa_methods m ON u.id = m.user_id AND m.is_enabled = 1
                    WHERE p.mfa_required = 1
                    GROUP BY u.id
                """

            cursor.execute(query)

            for row in cursor.fetchall():
                user_id, username, role, enabled, methods, last_verification = row
                enabled_text = _("common.enabled") if enabled else _("mfa_admin.status.not_enabled")
                methods_text = methods or _("common.none")
                last_ver_text = last_verification[:19] if last_verification else _("common.never")

                tag = 'enabled' if enabled else 'disabled'
                self.users_tree.insert('', tk.END, values=(
                    username,
                    role or _("common.unknown"),
                    enabled_text,
                    methods_text,
                    last_ver_text
                ), tags=(tag,), iid=user_id)

            # Configure colors
            self.users_tree.tag_configure('enabled', foreground='green')
            self.users_tree.tag_configure('disabled', foreground='orange')

        finally:
            conn.close()

    def _load_audit_log(self):
        """Load audit log"""
        self.audit_tree.delete(*self.audit_tree.get_children())

        conn = sqlite3.connect(self.mfa_service.db_path)
        cursor = conn.cursor()

        try:
            query = """
                SELECT
                    v.attempted_at,
                    u.username,
                    v.method_type,
                    CASE WHEN v.success = 1 THEN 'Success' ELSE 'Failed' END,
                    v.failure_reason,
                    v.ip_address
                FROM mfa_verification_attempts v
                JOIN users u ON v.user_id = u.id
            """

            # Apply filter
            filter_value = self.audit_filter_var.get()
            if filter_value == "success":
                query += " WHERE v.success = 1"
            elif filter_value == "failed":
                query += " WHERE v.success = 0"
            elif filter_value == "24h":
                query += " WHERE v.attempted_at > datetime('now', '-1 day')"
            elif filter_value == "7d":
                query += " WHERE v.attempted_at > datetime('now', '-7 days')"

            query += " ORDER BY v.attempted_at DESC LIMIT 500"

            cursor.execute(query)

            for row in cursor.fetchall():
                timestamp = row[0][:19] if row[0] else ''
                status = row[3]
                tag = 'success' if status == 'Success' else 'failed'

                self.audit_tree.insert('', tk.END, values=(
                    timestamp,
                    row[1],
                    row[2],
                    status,
                    row[4] or '',
                    row[5] or ''
                ), tags=(tag,))

            # Configure colors
            self.audit_tree.tag_configure('success', foreground='green')
            self.audit_tree.tag_configure('failed', foreground='red')

        finally:
            conn.close()

    def _load_settings(self):
        """Load system settings"""
        # Load provider status
        try:
            from education_system.systems.university.infrastructure.auth.sms_provider import get_sms_service
            sms_service = get_sms_service()
            status = sms_service.get_provider_status()
            self.sms_provider_label.config(
                text=_("mfa_admin.provider.sms_status", provider=status['primary']),
                fg="green"
            )
        except Exception as e:
            self.sms_provider_label.config(text=_("mfa_admin.provider.sms_error", error=str(e)), fg="red")

        try:
            from education_system.systems.university.infrastructure.auth.email_otp_service import get_email_service
            email_service = get_email_service()
            status = email_service.get_provider_status()
            self.email_provider_label.config(
                text=_("mfa_admin.provider.email_status", provider=status['primary']),
                fg="green"
            )
        except Exception as e:
            self.email_provider_label.config(text=_("mfa_admin.provider.email_error", error=str(e)), fg="red")

    # Action methods

    def _edit_policy(self):
        """Edit MFA policy"""
        selection = self.policies_tree.selection()
        if not selection:
            messagebox.showwarning(_("mfa_admin.messages.no_selection"), _("mfa_admin.messages.select_policy"))
            return

        policy_id = selection[0]
        item = self.policies_tree.item(selection[0])
        values = item['values']

        # Create edit dialog
        dialog = tk.Toplevel(self.parent)
        dialog.title(_("mfa_admin.dialogs.edit_policy_title"))
        dialog.geometry("500x450")
        dialog.transient(self.parent)
        dialog.grab_set()

        # Policy name
        ttk.Label(dialog, text=_("mfa_admin.dialogs.policy_name")).pack(anchor='w', padx=10, pady=(10, 0))
        name_var = tk.StringVar(value=values[0] if values else "")
        ttk.Entry(dialog, textvariable=name_var, width=40).pack(padx=10, pady=5)

        # Roles frame
        ttk.Label(dialog, text=_("mfa_admin.dialogs.apply_to_roles")).pack(anchor='w', padx=10, pady=(10, 0))
        roles_frame = ttk.Frame(dialog)
        roles_frame.pack(fill='x', padx=10, pady=5)

        role_vars = {}
        current_roles = str(values[1]).split(', ') if len(values) > 1 else []
        for role in ['admin', 'instructor', 'student', 'staff']:
            var = tk.BooleanVar(value=role in current_roles)
            role_vars[role] = var
            ttk.Checkbutton(roles_frame, text=role.capitalize(), variable=var).pack(side='left', padx=5)

        # MFA Methods frame
        ttk.Label(dialog, text=_("mfa_admin.dialogs.allowed_methods")).pack(anchor='w', padx=10, pady=(10, 0))
        methods_frame = ttk.Frame(dialog)
        methods_frame.pack(fill='x', padx=10, pady=5)

        method_vars = {}
        current_methods = str(values[2]).split(', ') if len(values) > 2 else []
        for method in ['totp', 'email', 'sms']:
            var = tk.BooleanVar(value=method in current_methods)
            method_vars[method] = var
            ttk.Checkbutton(methods_frame, text=method.upper(), variable=var).pack(side='left', padx=5)

        # Timeout settings
        ttk.Label(dialog, text=_("mfa_admin.dialogs.session_timeout")).pack(anchor='w', padx=10, pady=(10, 0))
        timeout_var = tk.StringVar(value="30")
        ttk.Entry(dialog, textvariable=timeout_var, width=10).pack(anchor='w', padx=10, pady=5)

        # Enforcement level
        ttk.Label(dialog, text=_("mfa_admin.dialogs.enforcement_level")).pack(anchor='w', padx=10, pady=(10, 0))
        enforcement_var = tk.StringVar(value="required")
        enforcement_combo = ttk.Combobox(dialog, textvariable=enforcement_var,
                                         values=['required', 'optional', 'recommended'], state='readonly')
        enforcement_combo.pack(anchor='w', padx=10, pady=5)

        def save_policy():
            try:
                selected_roles = [r for r, v in role_vars.items() if v.get()]
                selected_methods = [m for m, v in method_vars.items() if v.get()]

                if not selected_roles:
                    messagebox.showwarning(_("mfa_admin.messages.validation_error"), _("mfa_admin.messages.select_role"))
                    return
                if not selected_methods:
                    messagebox.showwarning(_("mfa_admin.messages.validation_error"), _("mfa_admin.messages.select_mfa_method"))
                    return

                conn = sqlite3.connect(self.mfa_service.db_path)
                try:
                    cursor = conn.cursor()

                    # Update or insert policy
                    cursor.execute("""
                        INSERT OR REPLACE INTO mfa_policies
                        (policy_id, policy_name, roles, allowed_methods, timeout_minutes, enforcement)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (policy_id, name_var.get(), ','.join(selected_roles),
                          ','.join(selected_methods), int(timeout_var.get()), enforcement_var.get()))

                    conn.commit()
                finally:
                    conn.close()

                messagebox.showinfo(_("common.success"), _("mfa_admin.messages.policy_updated"))
                dialog.destroy()
                self._load_policies()

            except Exception as e:
                messagebox.showerror(_("common.error"), _("mfa_admin.messages.policy_error", error=str(e)))

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill='x', padx=10, pady=20)
        ttk.Button(btn_frame, text=_("common.save"), command=save_policy).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side='left', padx=5)

    def _view_user_details(self):
        """View user MFA details"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning(_("mfa_admin.messages.no_selection"), _("mfa_admin.messages.select_user"))
            return

        user_id = int(selection[0])
        item = self.users_tree.item(selection[0])
        username = item['values'][0] if item['values'] else _("common.unknown")

        # Create details dialog
        dialog = tk.Toplevel(self.parent)
        dialog.title(_("mfa_admin.dialogs.mfa_details", username=username))
        dialog.geometry("600x500")
        dialog.transient(self.parent)

        # Create notebook for tabs
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Tab 1: MFA Methods
        methods_frame = ttk.Frame(notebook)
        notebook.add(methods_frame, text=_("mfa_admin.details_tabs.mfa_methods"))

        methods_tree = ttk.Treeview(methods_frame, columns=('method', 'status', 'added', 'last_used'),
                                    show='headings', height=8)
        methods_tree.heading('method', text=_("mfa_admin.columns.method"))
        methods_tree.heading('status', text=_("mfa_admin.columns.status"))
        methods_tree.heading('added', text=_("mfa_admin.columns.added"))
        methods_tree.heading('last_used', text=_("mfa_admin.columns.last_used"))
        methods_tree.pack(fill='both', expand=True, padx=5, pady=5)

        try:
            conn = sqlite3.connect(self.mfa_service.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT method_type, is_primary, created_at, last_used_at
                FROM mfa_methods WHERE user_id = ?
            """, (user_id,))

            for row in cursor.fetchall():
                status = _("mfa_admin.status.primary") if row[1] else _("mfa_admin.status.secondary")
                methods_tree.insert('', 'end', values=(
                    row[0].upper(), status, row[2] or _("common.na"), row[3] or _("common.never")
                ))

            # Tab 2: Trusted Devices
            devices_frame = ttk.Frame(notebook)
            notebook.add(devices_frame, text=_("mfa_admin.details_tabs.trusted_devices"))

            devices_tree = ttk.Treeview(devices_frame, columns=('device', 'added', 'expires', 'ip'),
                                        show='headings', height=8)
            devices_tree.heading('device', text=_("mfa_admin.columns.device"))
            devices_tree.heading('added', text=_("mfa_admin.columns.added"))
            devices_tree.heading('expires', text=_("mfa_admin.columns.expires"))
            devices_tree.heading('ip', text=_("mfa_admin.columns.ip_address"))
            devices_tree.pack(fill='both', expand=True, padx=5, pady=5)

            cursor.execute("""
                SELECT device_name, created_at, expires_at, ip_address
                FROM mfa_trusted_devices WHERE user_id = ? AND is_revoked = 0
            """, (user_id,))

            for row in cursor.fetchall():
                devices_tree.insert('', 'end', values=row)

            # Tab 3: Verification History
            history_frame = ttk.Frame(notebook)
            notebook.add(history_frame, text=_("mfa_admin.details_tabs.verification_history"))

            history_tree = ttk.Treeview(history_frame,
                                        columns=('time', 'method', 'success', 'ip'),
                                        show='headings', height=8)
            history_tree.heading('time', text=_("mfa_admin.columns.time"))
            history_tree.heading('method', text=_("mfa_admin.columns.method"))
            history_tree.heading('success', text=_("mfa_admin.columns.result"))
            history_tree.heading('ip', text=_("mfa_admin.columns.ip_address"))
            history_tree.pack(fill='both', expand=True, padx=5, pady=5)

            cursor.execute("""
                SELECT attempted_at, method_type, success, ip_address
                FROM mfa_verification_attempts
                WHERE user_id = ?
                ORDER BY attempted_at DESC LIMIT 20
            """, (user_id,))

            for row in cursor.fetchall():
                result = _("common.success") if row[2] else _("common.failed")
                history_tree.insert('', 'end', values=(row[0], row[1].upper(), result, row[3] or _("common.na")))

            # Tab 4: Recovery Codes
            recovery_frame = ttk.Frame(notebook)
            notebook.add(recovery_frame, text=_("mfa_admin.details_tabs.recovery_codes"))

            cursor.execute("""
                SELECT COUNT(*) FROM mfa_recovery_codes
                WHERE user_id = ? AND is_used = 0
            """, (user_id,))
            unused_codes = cursor.fetchone()[0]

            ttk.Label(recovery_frame, text=_("mfa_admin.labels.unused_recovery_codes", count=unused_codes),
                     font=('Arial', 12)).pack(pady=20)

            if unused_codes < 3:
                ttk.Label(recovery_frame, text=_("mfa_admin.messages.few_codes_warning"),
                         foreground='red').pack(pady=5)

            conn.close()

        except Exception as e:
            ttk.Label(methods_frame, text=_("mfa_admin.messages.error_loading", error=str(e))).pack(pady=20)

        # Close button
        ttk.Button(dialog, text=_("common.close"), command=dialog.destroy).pack(pady=10)

    def _reset_user_mfa(self):
        """Reset user's MFA"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning(_("mfa_admin.messages.no_selection"), _("mfa_admin.messages.select_user"))
            return

        user_id = int(selection[0])
        username = self.users_tree.item(selection[0])['values'][0]

        confirm = messagebox.askyesno(
            _("mfa_admin.dialogs.confirm_reset"),
            _("mfa_admin.messages.reset_confirmation", username=username)
        )

        if confirm:
            result = self.mfa_service.disable_mfa(user_id)
            if result['success']:
                messagebox.showinfo(_("common.success"), _("mfa_admin.messages.mfa_reset_success", username=username))
                self._load_users()
                self._load_overview()
            else:
                messagebox.showerror(_("common.error"), _("mfa_admin.messages.mfa_reset_error", error=result.get('error')))

    def _force_mfa_setup(self):
        """Force user to set up MFA"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning(_("mfa_admin.messages.no_selection"), _("mfa_admin.messages.select_user"))
            return

        user_id = int(selection[0])
        item = self.users_tree.item(selection[0])
        username = item['values'][0] if item['values'] else _("common.unknown")

        # Create enforcement dialog
        dialog = tk.Toplevel(self.parent)
        dialog.title(_("mfa_admin.dialogs.force_mfa_title", username=username))
        dialog.geometry("400x350")
        dialog.transient(self.parent)
        dialog.grab_set()

        ttk.Label(dialog, text=_("mfa_admin.dialogs.force_mfa_for", username=username),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Grace period
        ttk.Label(dialog, text=_("mfa_admin.dialogs.grace_period")).pack(anchor='w', padx=20, pady=(10, 0))
        grace_var = tk.StringVar(value="7")
        grace_combo = ttk.Combobox(dialog, textvariable=grace_var,
                                   values=['1', '3', '7', '14', '30'], state='readonly', width=10)
        grace_combo.pack(anchor='w', padx=20, pady=5)

        # Required methods
        ttk.Label(dialog, text=_("mfa_admin.dialogs.required_method")).pack(anchor='w', padx=20, pady=(10, 0))
        method_var = tk.StringVar(value="any")
        methods_frame = ttk.Frame(dialog)
        methods_frame.pack(anchor='w', padx=20, pady=5)

        ttk.Radiobutton(methods_frame, text=_("mfa_admin.dialogs.any_method"), variable=method_var, value="any").pack(anchor='w')
        ttk.Radiobutton(methods_frame, text=_("mfa_admin.dialogs.totp_only"), variable=method_var, value="totp").pack(anchor='w')
        ttk.Radiobutton(methods_frame, text=_("mfa_admin.dialogs.email_otp"), variable=method_var, value="email").pack(anchor='w')

        # Notification options
        notify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text=_("mfa_admin.dialogs.send_notification"),
                       variable=notify_var).pack(anchor='w', padx=20, pady=10)

        def enforce_mfa():
            try:
                from datetime import datetime, timedelta
                deadline = datetime.now() + timedelta(days=int(grace_var.get()))

                conn = sqlite3.connect(self.mfa_service.db_path)
                try:
                    cursor = conn.cursor()

                    # Create or update MFA enforcement record
                    cursor.execute("""
                        INSERT OR REPLACE INTO mfa_enforcement
                        (user_id, required_method, deadline, created_at, notified)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user_id, method_var.get(), deadline.isoformat(),
                          datetime.now().isoformat(), notify_var.get()))

                    conn.commit()
                finally:
                    conn.close()

                if notify_var.get():
                    # Log notification (actual email would be sent by email service)
                    pass

                messagebox.showinfo(_("common.success"),
                    _("mfa_admin.messages.mfa_enforced", username=username, deadline=deadline.strftime('%Y-%m-%d'), grace=grace_var.get()))
                dialog.destroy()
                self._load_users()

            except Exception as e:
                messagebox.showerror(_("common.error"), _("mfa_admin.messages.enforce_error", error=str(e)))

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill='x', padx=20, pady=20)
        ttk.Button(btn_frame, text=_("mfa_admin.buttons.enforce_mfa"), command=enforce_mfa).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side='left', padx=5)

    def _export_audit_log(self):
        """Export audit log to CSV"""
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"mfa_audit_log_{datetime.now().strftime('%Y%m%d')}.csv"
        )

        if filename:
            try:
                conn = sqlite3.connect(self.mfa_service.db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT
                        v.attempted_at,
                        u.username,
                        v.method_type,
                        v.success,
                        v.failure_reason,
                        v.ip_address,
                        v.device_id
                    FROM mfa_verification_attempts v
                    JOIN users u ON v.user_id = u.id
                    ORDER BY v.attempted_at DESC
                """)

                with open(filename, 'w') as f:
                    f.write(_("mfa_admin.export.csv_header") + "\n")

                    for row in cursor.fetchall():
                        f.write(','.join([
                            str(row[0] or ''),
                            str(row[1] or ''),
                            str(row[2] or ''),
                            _("common.yes") if row[3] else _("common.no"),
                            str(row[4] or ''),
                            str(row[5] or ''),
                            str(row[6] or '')
                        ]) + '\n')

                conn.close()
                messagebox.showinfo(_("common.success"), _("mfa_admin.messages.export_success", filename=filename))

            except Exception as e:
                messagebox.showerror(_("common.error"), _("mfa_admin.messages.export_error", error=str(e)))

    def _save_settings(self):
        """Save system settings to database"""
        try:
            # Find settings tab and collect values from entry widgets
            settings = {}

            # Get the notebook widget to find settings tab
            for child in self.parent.winfo_children():
                if isinstance(child, ttk.Notebook):
                    for tab_id in child.tabs():
                        tab_text = child.tab(tab_id, 'text')
                        if _("mfa_admin.tabs.settings") in tab_text:
                            tab_frame = child.nametowidget(tab_id)
                            self._collect_settings_from_frame(tab_frame, settings)
                            break

            if not settings:
                # Default settings if we couldn't find the widgets
                settings = {
                    'otp_expiry': '10',
                    'max_attempts': '3',
                    'lockout_duration': '15',
                    'trust_duration': '30',
                    'max_trusted': '5'
                }

            # Save to database
            conn = sqlite3.connect(self.mfa_service.db_path)
            try:
                cursor = conn.cursor()

                # Create settings table if not exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS mfa_settings (
                        setting_key TEXT PRIMARY KEY,
                        setting_value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Insert or update each setting
                for key, value in settings.items():
                    cursor.execute("""
                        INSERT OR REPLACE INTO mfa_settings (setting_key, setting_value, updated_at)
                        VALUES (?, ?, datetime('now'))
                    """, (key, value))

                conn.commit()
            finally:
                conn.close()

            messagebox.showinfo(_("common.success"), _("mfa_admin.messages.settings_saved"))

        except Exception as e:
            messagebox.showerror(_("common.error"), _("mfa_admin.messages.settings_error", error=str(e)))

    def _collect_settings_from_frame(self, frame, settings):
        """Recursively collect settings from entry widgets in frame"""
        setting_keys = ['otp_expiry', 'max_attempts', 'lockout_duration', 'trust_duration', 'max_trusted']
        key_index = [0]  # Use list to allow modification in nested function

        def traverse(widget):
            for child in widget.winfo_children():
                if isinstance(child, tk.Entry):
                    if key_index[0] < len(setting_keys):
                        settings[setting_keys[key_index[0]]] = child.get()
                        key_index[0] += 1
                traverse(child)

        traverse(frame)

    def _test_sms_provider(self):
        """Test SMS provider"""
        try:
            from education_system.systems.university.infrastructure.auth.sms_provider import get_sms_service
            service = get_sms_service()
            result = service.send_otp("+1234567890", "123456")

            if result['success']:
                messagebox.showinfo(_("common.success"), _("mfa_admin.messages.sms_test_success", provider=result.get('provider')))
            else:
                messagebox.showerror(_("mfa_admin.messages.failed"), _("mfa_admin.messages.sms_test_failed", error=result.get('error')))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("mfa_admin.messages.test_failed", error=str(e)))

    def _test_email_provider(self):
        """Test email provider"""
        try:
            from education_system.systems.university.infrastructure.auth.email_otp_service import get_email_service
            service = get_email_service()
            result = service.send_otp("test@example.com", "123456", "Test User")

            if result['success']:
                messagebox.showinfo(_("common.success"), _("mfa_admin.messages.email_test_success", provider=result.get('provider')))
            else:
                messagebox.showerror(_("mfa_admin.messages.failed"), _("mfa_admin.messages.email_test_failed", error=result.get('error')))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("mfa_admin.messages.test_failed", error=str(e)))

def show_mfa_admin(parent, admin_user_id: int):
    """Show MFA admin panel"""
    panel = MFAAdminPanel(parent, admin_user_id)
    return panel

if __name__ == '__main__':
    # Test admin panel
    root = tk.Tk()
    root.withdraw()

    show_mfa_admin(root, admin_user_id=1)

    root.mainloop()
