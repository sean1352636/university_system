#!/usr/bin/env python3
"""
MFA Admin Management GUI
Administrative interface for managing MFA policies, user MFA settings, and monitoring
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import sqlite3
from datetime import datetime
from typing import Dict, List
from university_system.infrastructure.auth.mfa_service import MFAService


class MFAAdminPanel(tk.Toplevel):
    """
    Administrative panel for MFA management
    """

    def __init__(self, parent, admin_user_id: int):
        super().__init__(parent)

        self.admin_user_id = admin_user_id
        self.mfa_service = MFAService()

        self.title("MFA Administration")
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
            text="🛡️ Multi-Factor Authentication Administration",
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
            text="🔄 Refresh All",
            command=self._load_data
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            footer_frame,
            text="Close",
            command=self.destroy
        ).pack(side=tk.RIGHT, padx=5)

    def _create_overview_tab(self):
        """Create overview/dashboard tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="📊 Overview")

        # Title
        tk.Label(
            tab,
            text="MFA System Overview",
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=10)

        # Stats frame
        stats_frame = tk.Frame(tab, bg="white")
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Statistics cards
        self.stats_labels = {}
        stat_names = [
            ("total_users", "Total Users"),
            ("mfa_enabled", "MFA Enabled"),
            ("mfa_required", "MFA Required"),
            ("totp_users", "TOTP Users"),
            ("sms_users", "SMS Users"),
            ("email_users", "Email Users"),
            ("recent_verifications", "Verifications (24h)"),
            ("failed_attempts", "Failed Attempts (24h)")
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
            text="Recent MFA Activity",
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

        self.activity_tree.heading("time", text="Time")
        self.activity_tree.heading("user", text="User")
        self.activity_tree.heading("method", text="Method")
        self.activity_tree.heading("status", text="Status")

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
        self.notebook.add(tab, text="📋 Policies")

        tk.Label(
            tab,
            text="MFA Enforcement Policies by Role",
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

        self.policies_tree.heading("role", text="Role")
        self.policies_tree.heading("required", text="Required")
        self.policies_tree.heading("methods", text="Allowed Methods")
        self.policies_tree.heading("min_methods", text="Min Methods")
        self.policies_tree.heading("grace_days", text="Grace Period")
        self.policies_tree.heading("device_trust", text="Device Trust")

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
            text="Edit Policy",
            command=self._edit_policy
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Refresh",
            command=self._load_policies
        ).pack(side=tk.LEFT, padx=5)

    def _create_users_tab(self):
        """Create users tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="👥 Users")

        tk.Label(
            tab,
            text="User MFA Status",
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=10)

        # Search/filter frame
        filter_frame = tk.Frame(tab, bg="white")
        filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        tk.Label(filter_frame, text="Filter:", bg="white").pack(side=tk.LEFT, padx=(0, 5))

        self.user_filter_var = tk.StringVar(value="all")
        filters = [
            ("All Users", "all"),
            ("MFA Enabled", "enabled"),
            ("MFA Disabled", "disabled"),
            ("MFA Required", "required")
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

        self.users_tree.heading("username", text="Username")
        self.users_tree.heading("role", text="Role")
        self.users_tree.heading("mfa_enabled", text="MFA Status")
        self.users_tree.heading("methods", text="Methods")
        self.users_tree.heading("last_verification", text="Last Verification")

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
            text="View Details",
            command=self._view_user_details
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Reset MFA",
            command=self._reset_user_mfa
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Force MFA Setup",
            command=self._force_mfa_setup
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Refresh",
            command=self._load_users
        ).pack(side=tk.RIGHT, padx=5)

    def _create_audit_tab(self):
        """Create audit log tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="📜 Audit Log")

        tk.Label(
            tab,
            text="MFA Verification Audit Trail",
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=10)

        # Filter options
        filter_frame = tk.Frame(tab, bg="white")
        filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        tk.Label(filter_frame, text="Show:", bg="white").pack(side=tk.LEFT, padx=(0, 5))

        self.audit_filter_var = tk.StringVar(value="all")
        audit_filters = [
            ("All", "all"),
            ("Success", "success"),
            ("Failed", "failed"),
            ("Last 24h", "24h"),
            ("Last 7 days", "7d")
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

        self.audit_tree.heading("timestamp", text="Timestamp")
        self.audit_tree.heading("user", text="User")
        self.audit_tree.heading("method", text="Method")
        self.audit_tree.heading("status", text="Status")
        self.audit_tree.heading("reason", text="Failure Reason")
        self.audit_tree.heading("ip", text="IP Address")

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
            text="📥 Export Audit Log",
            command=self._export_audit_log
        ).pack(pady=10)

    def _create_settings_tab(self):
        """Create system settings tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="⚙️ Settings")

        tk.Label(
            tab,
            text="MFA System Settings",
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=10)

        settings_frame = tk.Frame(tab, bg="white")
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=20)

        # OTP Settings
        otp_group = tk.LabelFrame(
            settings_frame,
            text="OTP Configuration",
            font=("Arial", 10, "bold"),
            bg="white",
            padx=20,
            pady=15
        )
        otp_group.pack(fill=tk.X, pady=10)

        settings = [
            ("OTP Expiry (minutes):", "otp_expiry", "10"),
            ("Max OTP Attempts:", "max_attempts", "3"),
            ("Lockout Duration (minutes):", "lockout_duration", "15")
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
            text="Device Trust Configuration",
            font=("Arial", 10, "bold"),
            bg="white",
            padx=20,
            pady=15
        )
        trust_group.pack(fill=tk.X, pady=10)

        trust_settings = [
            ("Device Trust Duration (days):", "trust_duration", "30"),
            ("Max Trusted Devices per User:", "max_trusted", "5")
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
            text="SMS/Email Provider Status",
            font=("Arial", 10, "bold"),
            bg="white",
            padx=20,
            pady=15
        )
        provider_group.pack(fill=tk.X, pady=10)

        self.sms_provider_label = tk.Label(
            provider_group,
            text="SMS Provider: Loading...",
            bg="white",
            fg="gray"
        )
        self.sms_provider_label.pack(anchor=tk.W, pady=5)

        self.email_provider_label = tk.Label(
            provider_group,
            text="Email Provider: Loading...",
            bg="white",
            fg="gray"
        )
        self.email_provider_label.pack(anchor=tk.W, pady=5)

        # Buttons
        button_frame = tk.Frame(settings_frame, bg="white")
        button_frame.pack(fill=tk.X, pady=20)

        ttk.Button(
            button_frame,
            text="Save Settings",
            command=self._save_settings
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Test SMS Provider",
            command=self._test_sms_provider
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Test Email Provider",
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
                JOIN roles r ON u.role_id = r.id
                JOIN mfa_enforcement_policies p ON r.role_name = p.role_name
                WHERE p.mfa_required = 1
            """)
            result = cursor.fetchone()
            self.stats_labels['mfa_required'].config(text=str(result[0] if result else 0))

            # Method counts
            for method in ['totp', 'sms', 'email']:
                cursor.execute(f"""
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
                timestamp = row[0][:19] if row[0] else ''
                tag = 'success' if row[3] == 'Success' else 'failed'
                self.activity_tree.insert('', tk.END, values=row, tags=(tag,))

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
                required_text = "Yes" if required else "No"
                trust_text = "Allowed" if trust else "Disabled"

                self.policies_tree.insert('', tk.END, values=(
                    role,
                    required_text,
                    methods.replace('"', '').replace('[', '').replace(']', ''),
                    min_methods,
                    f"{grace} days",
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
                    r.role_name,
                    COALESCE(s.mfa_enabled, 0) as mfa_enabled,
                    GROUP_CONCAT(m.method_type) as methods,
                    s.last_successful_verification
                FROM users u
                LEFT JOIN roles r ON u.role_id = r.id
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
                        r.role_name,
                        COALESCE(s.mfa_enabled, 0) as mfa_enabled,
                        GROUP_CONCAT(m.method_type) as methods,
                        s.last_successful_verification
                    FROM users u
                    JOIN roles r ON u.role_id = r.id
                    JOIN mfa_enforcement_policies p ON r.role_name = p.role_name
                    LEFT JOIN mfa_user_settings s ON u.id = s.user_id
                    LEFT JOIN mfa_methods m ON u.id = m.user_id AND m.is_enabled = 1
                    WHERE p.mfa_required = 1
                    GROUP BY u.id
                """

            cursor.execute(query)

            for row in cursor.fetchall():
                user_id, username, role, enabled, methods, last_verification = row
                enabled_text = "Enabled" if enabled else "Not Enabled"
                methods_text = methods or "None"
                last_ver_text = last_verification[:19] if last_verification else "Never"

                tag = 'enabled' if enabled else 'disabled'
                self.users_tree.insert('', tk.END, values=(
                    username,
                    role or "Unknown",
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
            from .sms_provider import get_sms_service
            sms_service = get_sms_service()
            status = sms_service.get_provider_status()
            self.sms_provider_label.config(
                text=f"SMS Provider: {status['primary']}",
                fg="green"
            )
        except Exception as e:
            self.sms_provider_label.config(text=f"SMS Provider: Error - {e}", fg="red")

        try:
            from .email_otp_service import get_email_service
            email_service = get_email_service()
            status = email_service.get_provider_status()
            self.email_provider_label.config(
                text=f"Email Provider: {status['primary']}",
                fg="green"
            )
        except Exception as e:
            self.email_provider_label.config(text=f"Email Provider: Error - {e}", fg="red")

    # Action methods

    def _edit_policy(self):
        """Edit MFA policy"""
        selection = self.policies_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a policy to edit")
            return

        # Get policy details and show edit dialog
        # TODO: Implement policy editor dialog
        messagebox.showinfo("Coming Soon", "Policy editor will be implemented")

    def _view_user_details(self):
        """View user MFA details"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a user")
            return

        user_id = selection[0]
        # TODO: Implement user details dialog
        messagebox.showinfo("Coming Soon", f"User details for ID {user_id} will be shown")

    def _reset_user_mfa(self):
        """Reset user's MFA"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a user")
            return

        user_id = int(selection[0])
        username = self.users_tree.item(selection[0])['values'][0]

        confirm = messagebox.askyesno(
            "Confirm Reset",
            f"Reset MFA for user '{username}'?\n\n"
            "This will:\n"
            "• Disable all MFA methods\n"
            "• Revoke all trusted devices\n"
            "• Invalidate recovery codes\n\n"
            "User will need to set up MFA again."
        )

        if confirm:
            result = self.mfa_service.disable_mfa(user_id)
            if result['success']:
                messagebox.showinfo("Success", f"MFA reset for {username}")
                self._load_users()
                self._load_overview()
            else:
                messagebox.showerror("Error", f"Failed to reset MFA: {result.get('error')}")

    def _force_mfa_setup(self):
        """Force user to set up MFA"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a user")
            return

        # TODO: Implement enforcement deadline setting
        messagebox.showinfo("Coming Soon", "Force MFA setup will be implemented")

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
                    f.write("Timestamp,Username,Method,Success,Failure Reason,IP Address,Device ID\n")

                    for row in cursor.fetchall():
                        f.write(','.join([
                            str(row[0] or ''),
                            str(row[1] or ''),
                            str(row[2] or ''),
                            'Yes' if row[3] else 'No',
                            str(row[4] or ''),
                            str(row[5] or ''),
                            str(row[6] or '')
                        ]) + '\n')

                conn.close()
                messagebox.showinfo("Success", f"Audit log exported to:\n{filename}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")

    def _save_settings(self):
        """Save system settings"""
        messagebox.showinfo("Coming Soon", "Settings persistence will be implemented")

    def _test_sms_provider(self):
        """Test SMS provider"""
        try:
            from .sms_provider import get_sms_service
            service = get_sms_service()
            result = service.send_otp("+1234567890", "123456")

            if result['success']:
                messagebox.showinfo("Success", f"SMS test successful!\nProvider: {result.get('provider')}")
            else:
                messagebox.showerror("Failed", f"SMS test failed:\n{result.get('error')}")
        except Exception as e:
            messagebox.showerror("Error", f"Test failed: {e}")

    def _test_email_provider(self):
        """Test email provider"""
        try:
            from .email_otp_service import get_email_service
            service = get_email_service()
            result = service.send_otp("test@example.com", "123456", "Test User")

            if result['success']:
                messagebox.showinfo("Success", f"Email test successful!\nProvider: {result.get('provider')}")
            else:
                messagebox.showerror("Failed", f"Email test failed:\n{result.get('error')}")
        except Exception as e:
            messagebox.showerror("Error", f"Test failed: {e}")


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
