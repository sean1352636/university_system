#!/usr/bin/env python3
"""
Comprehensive Security & Compliance Dashboard
Integrates all security features into one admin interface
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import sqlite3
from datetime import datetime, timedelta
import json
from typing import Dict, List

from university_system.infrastructure.security.session_management import SessionManager
from university_system.infrastructure.security.data_encryption import EncryptionManager
from university_system.infrastructure.security.comprehensive_security import (
    APISecurityManager,
    PasswordSecurityManager,
    SecurityAuditManager,
    DataLossPreventionManager,
    IncidentResponseManager,
    VulnerabilityScanner
)
from university_system.infrastructure.security.init_security_tables import init_security_tables

# Import MFA GUIs
try:
    from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel
    MFA_ADMIN_AVAILABLE = True
except ImportError:
    MFAAdminPanel = None
    MFA_ADMIN_AVAILABLE = False

try:
    from university_system.infrastructure.auth.mfa_gui import MFASetupWizard
    MFA_SETUP_AVAILABLE = True
except ImportError:
    MFASetupWizard = None
    MFA_SETUP_AVAILABLE = False


class SecurityDashboard(tk.Toplevel):
    """Comprehensive Security Dashboard"""

    def __init__(self, parent, admin_user_id: int):
        super().__init__(parent)

        self.admin_user_id = admin_user_id

        # Initialize security database tables first
        init_security_tables()

        # Initialize managers
        self.session_mgr = SessionManager()
        self.encryption_mgr = EncryptionManager()
        self.api_mgr = APISecurityManager()
        self.password_mgr = PasswordSecurityManager()
        self.audit_mgr = SecurityAuditManager()
        self.dlp_mgr = DataLossPreventionManager()
        self.incident_mgr = IncidentResponseManager()
        self.vuln_scanner = VulnerabilityScanner()

        self.title("Security & Compliance Dashboard")
        self.geometry("1200x800")

        self._create_widgets()
        self._load_data()

        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create dashboard UI"""
        # Header
        header_frame = tk.Frame(self, bg="#2C3E50", height=70)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        tk.Label(
            header_frame,
            text="🛡️ Security & Compliance Dashboard",
            font=("Arial", 16, "bold"),
            bg="#2C3E50",
            fg="white"
        ).pack(side=tk.LEFT, padx=20, pady=15)

        # Refresh button
        ttk.Button(
            header_frame,
            text="🔄 Refresh All",
            command=self._load_data
        ).pack(side=tk.RIGHT, padx=20)

        # Quick Access Toolbar
        toolbar_frame = tk.Frame(self, bg="#ECF0F1", height=60)
        toolbar_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        toolbar_frame.pack_propagate(False)

        tk.Label(
            toolbar_frame,
            text="Quick Access:",
            font=("Arial", 10, "bold"),
            bg="#ECF0F1"
        ).pack(side=tk.LEFT, padx=10)

        # Add quick access buttons
        ttk.Button(
            toolbar_frame,
            text="🔐 MFA Admin",
            command=self._open_mfa_admin
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar_frame,
            text="🔑 API Keys",
            command=self._open_api_key_manager
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar_frame,
            text="🔒 Encryption",
            command=self._open_encryption_manager
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar_frame,
            text="👥 Sessions",
            command=self._open_session_manager
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar_frame,
            text="🚨 Incidents",
            command=self._open_incident_manager
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar_frame,
            text="🔍 Scanner",
            command=self._open_vulnerability_scanner
        ).pack(side=tk.LEFT, padx=5)

        # Main notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        self._create_overview_tab()
        self._create_sessions_tab()
        self._create_encryption_tab()
        self._create_api_security_tab()
        self._create_audit_tab()
        self._create_incidents_tab()
        self._create_dlp_tab()
        self._create_vulnerabilities_tab()

    def _create_overview_tab(self):
        """Security overview tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="📊 Overview")

        # Title
        tk.Label(
            tab,
            text="Security Overview",
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=15)

        # Stats grid
        stats_frame = tk.Frame(tab, bg="white")
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

        self.overview_stats = {}

        stats = [
            ("active_sessions", "Active Sessions", "#3498DB"),
            ("failed_logins_24h", "Failed Logins (24h)", "#E74C3C"),
            ("security_events_24h", "Security Events (24h)", "#F39C12"),
            ("encrypted_fields", "Encrypted Fields", "#27AE60"),
            ("api_keys_active", "Active API Keys", "#9B59B6"),
            ("open_incidents", "Open Incidents", "#E67E22"),
            ("pending_exports", "Pending Exports", "#16A085"),
            ("vulnerabilities_high", "High Vulnerabilities", "#C0392B")
        ]

        row, col = 0, 0
        for key, label, color in stats:
            card = tk.Frame(stats_frame, bg="#F8F9FA", relief=tk.RIDGE, borderwidth=2)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            tk.Label(
                card,
                text=label,
                font=("Arial", 10),
                bg="#F8F9FA",
                fg="gray"
            ).pack(pady=(15, 0))

            value_label = tk.Label(
                card,
                text="0",
                font=("Arial", 28, "bold"),
                bg="#F8F9FA",
                fg=color
            )
            value_label.pack(pady=(0, 15))

            self.overview_stats[key] = value_label

            col += 1
            if col > 3:
                col = 0
                row += 1

        # Configure grid
        for i in range(4):
            stats_frame.grid_columnconfigure(i, weight=1)

        # Recent alerts
        tk.Label(
            tab,
            text="Recent Security Alerts",
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=(20, 10))

        alerts_frame = tk.Frame(tab)
        alerts_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 20))

        self.alerts_text = scrolledtext.ScrolledText(
            alerts_frame,
            height=10,
            font=("Courier", 9),
            bg="#F8F9FA"
        )
        self.alerts_text.pack(fill=tk.BOTH, expand=True)

    def _create_sessions_tab(self):
        """Session management tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="🔐 Sessions")

        tk.Label(
            tab,
            text="Active Sessions",
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=15)

        # Session tree
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ("user", "ip", "location", "created", "last_activity")
        self.sessions_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        self.sessions_tree.heading("user", text="User")
        self.sessions_tree.heading("ip", text="IP Address")
        self.sessions_tree.heading("location", text="Location")
        self.sessions_tree.heading("created", text="Created")
        self.sessions_tree.heading("last_activity", text="Last Activity")

        self.sessions_tree.column("user", width=120)
        self.sessions_tree.column("ip", width=120)
        self.sessions_tree.column("location", width=150)
        self.sessions_tree.column("created", width=150)
        self.sessions_tree.column("last_activity", width=150)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.sessions_tree.yview)
        self.sessions_tree.configure(yscrollcommand=scrollbar.set)

        self.sessions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = tk.Frame(tab, bg="white")
        btn_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(btn_frame, text="Terminate Session", command=self._terminate_session).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="View Details", command=self._view_session_details).pack(side=tk.LEFT, padx=5)

    def _create_encryption_tab(self):
        """Encryption management tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="🔒 Encryption")

        tk.Label(
            tab,
            text="Encryption Key Management",
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=15)

        # Keys tree
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ("key_id", "type", "created", "age", "status", "needs_rotation")
        self.keys_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)

        for col in columns:
            self.keys_tree.heading(col, text=col.replace("_", " ").title())

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.keys_tree.yview)
        self.keys_tree.configure(yscrollcommand=scrollbar.set)

        self.keys_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Encrypted fields
        tk.Label(
            tab,
            text="Encrypted Database Fields",
            font=("Arial", 11, "bold"),
            bg="white"
        ).pack(pady=15)

        fields_frame = tk.Frame(tab)
        fields_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ("table", "column", "key_id", "encrypted_at")
        self.fields_tree = ttk.Treeview(fields_frame, columns=columns, show="headings", height=8)

        for col in columns:
            self.fields_tree.heading(col, text=col.replace("_", " ").title())

        scrollbar2 = ttk.Scrollbar(fields_frame, orient=tk.VERTICAL, command=self.fields_tree.yview)
        self.fields_tree.configure(yscrollcommand=scrollbar2.set)

        self.fields_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar2.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = tk.Frame(tab, bg="white")
        btn_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(btn_frame, text="Rotate Key", command=self._rotate_key).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Create Backup", command=self._create_encrypted_backup).pack(side=tk.LEFT, padx=5)

    def _create_api_security_tab(self):
        """API security tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="🔑 API Security")

        tk.Label(
            tab,
            text="API Keys & Rate Limiting",
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=15)

        # API keys tree
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ("key_name", "user", "created", "last_used", "rate_limit", "status")
        self.api_keys_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.api_keys_tree.heading(col, text=col.replace("_", " ").title())

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.api_keys_tree.yview)
        self.api_keys_tree.configure(yscrollcommand=scrollbar.set)

        self.api_keys_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = tk.Frame(tab, bg="white")
        btn_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(btn_frame, text="Create API Key", command=self._create_api_key).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Revoke Key", command=self._revoke_api_key).pack(side=tk.LEFT, padx=5)

    def _create_audit_tab(self):
        """Audit & compliance tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="📜 Audit & Compliance")

        tk.Label(
            tab,
            text="Security Audit Trail",
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=15)

        # Compliance report buttons
        report_frame = tk.Frame(tab, bg="white")
        report_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(
            report_frame,
            text="Generate FERPA Report",
            command=lambda: self._generate_compliance_report('ferpa')
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            report_frame,
            text="Generate GDPR Report",
            command=lambda: self._generate_compliance_report('gdpr')
        ).pack(side=tk.LEFT, padx=5)

        # Audit log
        log_frame = tk.Frame(tab)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ("timestamp", "user", "event_type", "severity", "details")
        self.audit_tree = ttk.Treeview(log_frame, columns=columns, show="headings", height=18)

        for col in columns:
            self.audit_tree.heading(col, text=col.replace("_", " ").title())

        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.audit_tree.yview)
        self.audit_tree.configure(yscrollcommand=scrollbar.set)

        self.audit_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _create_incidents_tab(self):
        """Security incidents tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="🚨 Incidents")

        tk.Label(
            tab,
            text="Security Incidents",
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=15)

        # Incidents tree
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ("id", "type", "severity", "status", "detected", "description")
        self.incidents_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.incidents_tree.heading(col, text=col.upper() if col == "id" else col.replace("_", " ").title())

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.incidents_tree.yview)
        self.incidents_tree.configure(yscrollcommand=scrollbar.set)

        self.incidents_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = tk.Frame(tab, bg="white")
        btn_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(btn_frame, text="Create Incident", command=self._create_incident).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="View Details", command=self._view_incident).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Resolve", command=self._resolve_incident).pack(side=tk.LEFT, padx=5)

    def _create_dlp_tab(self):
        """Data Loss Prevention tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="📊 Data Loss Prevention")

        tk.Label(
            tab,
            text="Bulk Export Requests",
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=15)

        # Export requests tree
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ("user", "resource_type", "record_count", "status", "requested")
        self.exports_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=18)

        for col in columns:
            self.exports_tree.heading(col, text=col.replace("_", " ").title())

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.exports_tree.yview)
        self.exports_tree.configure(yscrollcommand=scrollbar.set)

        self.exports_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = tk.Frame(tab, bg="white")
        btn_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(btn_frame, text="Approve", command=self._approve_export).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Deny", command=self._deny_export).pack(side=tk.LEFT, padx=5)

    def _create_vulnerabilities_tab(self):
        """Vulnerability scanning tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="🔍 Vulnerabilities")

        tk.Label(
            tab,
            text="Security Vulnerability Scans",
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=15)

        # Scan buttons
        scan_frame = tk.Frame(tab, bg="white")
        scan_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(scan_frame, text="Scan SQL Injection", command=self._scan_sql_injection).pack(side=tk.LEFT, padx=5)
        ttk.Button(scan_frame, text="Scan XSS", command=self._scan_xss).pack(side=tk.LEFT, padx=5)
        ttk.Button(scan_frame, text="Scan Dependencies", command=self._scan_dependencies).pack(side=tk.LEFT, padx=5)

        # Results tree
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ("scan_type", "target", "severity", "vulnerable", "details", "scanned_at")
        self.vulns_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.vulns_tree.heading(col, text=col.replace("_", " ").title())

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.vulns_tree.yview)
        self.vulns_tree.configure(yscrollcommand=scrollbar.set)

        self.vulns_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _load_data(self):
        """Load all dashboard data"""
        self._load_overview()
        self._load_sessions()
        self._load_encryption_data()
        self._load_api_keys()
        self._load_audit_log()
        self._load_incidents()
        self._load_exports()
        self._load_vulnerabilities()

    def _load_overview(self):
        """Load overview statistics"""
        conn = sqlite3.connect(self.session_mgr.db_path)
        cursor = conn.cursor()

        try:
            # Active sessions
            cursor.execute("SELECT COUNT(*) FROM sessions WHERE is_active = 1")
            self.overview_stats['active_sessions'].config(text=str(cursor.fetchone()[0]))

            # Failed logins (24h)
            cursor.execute("""
                SELECT COUNT(*) FROM security_events
                WHERE event_type = 'failed_login'
                  AND event_time > datetime('now', '-1 day')
            """)
            self.overview_stats['failed_logins_24h'].config(text=str(cursor.fetchone()[0]))

            # Security events (24h)
            cursor.execute("""
                SELECT COUNT(*) FROM security_events
                WHERE event_time > datetime('now', '-1 day')
            """)
            self.overview_stats['security_events_24h'].config(text=str(cursor.fetchone()[0]))

            # Encrypted fields
            cursor.execute("SELECT COUNT(*) FROM encrypted_fields_metadata")
            self.overview_stats['encrypted_fields'].config(text=str(cursor.fetchone()[0]))

            # Active API keys
            cursor.execute("SELECT COUNT(*) FROM api_keys WHERE is_active = 1")
            self.overview_stats['api_keys_active'].config(text=str(cursor.fetchone()[0]))

            # Open incidents
            cursor.execute("SELECT COUNT(*) FROM security_incidents WHERE status = 'open'")
            self.overview_stats['open_incidents'].config(text=str(cursor.fetchone()[0]))

            # Pending exports
            cursor.execute("SELECT COUNT(*) FROM bulk_export_log WHERE status = 'pending'")
            self.overview_stats['pending_exports'].config(text=str(cursor.fetchone()[0]))

            # High vulnerabilities
            cursor.execute("""
                SELECT COUNT(*) FROM vulnerability_scan_results
                WHERE severity = 'high' AND fixed = 0
            """)
            self.overview_stats['vulnerabilities_high'].config(text=str(cursor.fetchone()[0]))

            # Recent alerts
            cursor.execute("""
                SELECT event_type, severity, details, event_time
                FROM security_events
                WHERE severity IN ('high', 'critical')
                ORDER BY event_time DESC
                LIMIT 20
            """)

            self.alerts_text.delete('1.0', tk.END)
            for row in cursor.fetchall():
                event_type, severity, details, event_time = row
                self.alerts_text.insert(tk.END, f"[{event_time[:19]}] [{severity.upper()}] {event_type}\n", severity)

            self.alerts_text.tag_config('high', foreground='orange')
            self.alerts_text.tag_config('critical', foreground='red', font=('Courier', 9, 'bold'))

        finally:
            conn.close()

    def _load_sessions(self):
        """Load active sessions"""
        # Implementation here
        pass

    def _load_encryption_data(self):
        """Load encryption keys and fields"""
        # Keys
        self.keys_tree.delete(*self.keys_tree.get_children())
        keys = self.encryption_mgr.get_key_rotation_status()

        for key in keys:
            self.keys_tree.insert('', tk.END, values=(
                key['key_id'],
                key['type'],
                key['created_at'][:10],
                f"{key['age_days']} days",
                'Active' if key['is_active'] else 'Rotated',
                '⚠️ Yes' if key['needs_rotation'] else 'No'
            ))

        # Fields
        self.fields_tree.delete(*self.fields_tree.get_children())
        fields = self.encryption_mgr.list_encrypted_fields()

        for field in fields:
            self.fields_tree.insert('', tk.END, values=(
                field['table'],
                field['column'],
                field['key_id'],
                field['encrypted_at'][:19] if field['encrypted_at'] else 'N/A'
            ))

    def _load_api_keys(self):
        """Load API keys"""
        # Implementation here
        pass

    def _load_audit_log(self):
        """Load audit log"""
        # Implementation here
        pass

    def _load_incidents(self):
        """Load security incidents"""
        # Implementation here
        pass

    def _load_exports(self):
        """Load export requests"""
        # Implementation here
        pass

    def _load_vulnerabilities(self):
        """Load vulnerability scans"""
        # Implementation here
        pass

    # Action methods
    def _terminate_session(self):
        """Terminate selected session"""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to terminate")
            return

        item = self.sessions_tree.item(selection[0])
        session_id = item['values'][0]

        if messagebox.askyesno("Confirm", f"Terminate session {session_id}?"):
            try:
                self.session_mgr.terminate_session(session_id)
                messagebox.showinfo("Success", "Session terminated successfully")
                self._load_sessions()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to terminate session: {str(e)}")

    def _view_session_details(self):
        """View session details"""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to view")
            return

        item = self.sessions_tree.item(selection[0])
        values = item['values']

        details = f"""Session Details:

ID: {values[0]}
User: {values[1]}
IP Address: {values[2]}
Location: {values[3]}
Created: {values[4]}
Last Activity: {values[5]}
"""
        messagebox.showinfo("Session Details", details)

    def _rotate_key(self):
        """Rotate encryption key"""
        messagebox.showinfo("Info", "Key rotation will be implemented")

    def _create_encrypted_backup(self):
        """Create encrypted backup"""
        messagebox.showinfo("Info", "Encrypted backup will be implemented")

    def _create_api_key(self):
        """Create new API key"""
        # Create dialog
        dialog = tk.Toplevel(self)
        dialog.title("Create API Key")
        dialog.geometry("400x300")
        dialog.transient(self)

        tk.Label(dialog, text="Create New API Key", font=("Arial", 12, "bold")).pack(pady=10)

        # Form
        form_frame = tk.Frame(dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        tk.Label(form_frame, text="Key Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(form_frame, width=30)
        name_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text="User ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        user_entry = ttk.Entry(form_frame, width=30)
        user_entry.insert(0, str(self.admin_user_id))
        user_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text="Permissions (comma-separated):").grid(row=2, column=0, sticky=tk.W, pady=5)
        perms_entry = ttk.Entry(form_frame, width=30)
        perms_entry.insert(0, "read,write")
        perms_entry.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text="Rate Limit:").grid(row=3, column=0, sticky=tk.W, pady=5)
        rate_entry = ttk.Entry(form_frame, width=30)
        rate_entry.insert(0, "1000")
        rate_entry.grid(row=3, column=1, pady=5)

        def create_key():
            name = name_entry.get()
            user_id = int(user_entry.get())
            permissions = [p.strip() for p in perms_entry.get().split(',')]
            rate_limit = int(rate_entry.get())

            result = self.api_mgr.create_api_key(user_id, name, permissions, rate_limit)

            if result.get('success'):
                key = result['api_key']
                messagebox.showinfo("Success", f"API Key Created!\n\nKey: {key}\n\nSave this key securely - it won't be shown again!")
                dialog.destroy()
                self._load_api_keys()
            else:
                messagebox.showerror("Error", result.get('error', 'Failed to create API key'))

        ttk.Button(dialog, text="Create", command=create_key).pack(pady=10)

    def _revoke_api_key(self):
        """Revoke API key"""
        selection = self.api_keys_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an API key to revoke")
            return

        item = self.api_keys_tree.item(selection[0])
        key_id = item['values'][0]
        key_name = item['values'][1]

        if messagebox.askyesno("Confirm", f"Revoke API key '{key_name}'?"):
            try:
                conn = sqlite3.connect(self.session_mgr.db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE api_keys SET is_active = 0 WHERE id = ?", (key_id,))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success", "API key revoked successfully")
                self._load_api_keys()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to revoke API key: {str(e)}")

    def _generate_compliance_report(self, report_type: str):
        """Generate compliance report"""
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        report = self.audit_mgr.generate_compliance_report(start_date, end_date, report_type)

        # Show report
        report_window = tk.Toplevel(self)
        report_window.title(f"{report_type.upper()} Compliance Report")
        report_window.geometry("600x700")

        text = scrolledtext.ScrolledText(report_window, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text.insert(tk.END, json.dumps(report, indent=2))
        text.config(state=tk.DISABLED)

    def _create_incident(self):
        """Create security incident"""
        # Create dialog
        dialog = tk.Toplevel(self)
        dialog.title("Create Security Incident")
        dialog.geometry("500x400")
        dialog.transient(self)

        tk.Label(dialog, text="Create Security Incident", font=("Arial", 12, "bold")).pack(pady=10)

        # Form
        form_frame = tk.Frame(dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        tk.Label(form_frame, text="Incident Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        type_combo = ttk.Combobox(form_frame, width=28, values=[
            "Unauthorized Access", "Data Breach", "Malware", "Phishing",
            "DDoS Attack", "Insider Threat", "Policy Violation", "Other"
        ])
        type_combo.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text="Severity:").grid(row=1, column=0, sticky=tk.W, pady=5)
        severity_combo = ttk.Combobox(form_frame, width=28, values=["low", "medium", "high", "critical"])
        severity_combo.current(1)
        severity_combo.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text="Description:").grid(row=2, column=0, sticky=tk.NW, pady=5)
        desc_text = tk.Text(form_frame, width=30, height=10)
        desc_text.grid(row=2, column=1, pady=5)

        def create_inc():
            incident_type = type_combo.get()
            severity = severity_combo.get()
            description = desc_text.get("1.0", tk.END).strip()

            if not incident_type or not description:
                messagebox.showwarning("Missing Data", "Please fill in all fields")
                return

            result = self.incident_mgr.create_incident(
                incident_type, severity, description, self.admin_user_id
            )

            if result.get('success'):
                messagebox.showinfo("Success", f"Incident created with ID: {result['incident_id']}")
                dialog.destroy()
                self._load_incidents()
            else:
                messagebox.showerror("Error", result.get('error', 'Failed to create incident'))

        ttk.Button(dialog, text="Create Incident", command=create_inc).pack(pady=10)

    def _view_incident(self):
        """View incident details"""
        selection = self.incidents_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an incident to view")
            return

        item = self.incidents_tree.item(selection[0])
        values = item['values']

        details = f"""Incident Details:

ID: {values[0]}
Type: {values[1]}
Severity: {values[2]}
Status: {values[3]}
Detected: {values[4]}
Description: {values[5]}
"""
        messagebox.showinfo("Incident Details", details)

    def _resolve_incident(self):
        """Resolve incident"""
        selection = self.incidents_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an incident to resolve")
            return

        item = self.incidents_tree.item(selection[0])
        incident_id = item['values'][0]

        # Create dialog for resolution notes
        dialog = tk.Toplevel(self)
        dialog.title("Resolve Incident")
        dialog.geometry("400x300")
        dialog.transient(self)

        tk.Label(dialog, text="Resolution Notes:", font=("Arial", 10, "bold")).pack(pady=10)
        notes_text = tk.Text(dialog, width=40, height=10)
        notes_text.pack(pady=10, padx=20)

        def resolve():
            notes = notes_text.get("1.0", tk.END).strip()
            if not notes:
                messagebox.showwarning("Missing Data", "Please enter resolution notes")
                return

            try:
                conn = sqlite3.connect(self.session_mgr.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE security_incidents
                    SET status = 'resolved', resolved_at = ?, resolution = ?
                    WHERE id = ?
                """, (datetime.now(), notes, incident_id))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success", "Incident resolved successfully")
                dialog.destroy()
                self._load_incidents()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to resolve incident: {str(e)}")

        ttk.Button(dialog, text="Resolve", command=resolve).pack(pady=10)

    def _approve_export(self):
        """Approve export request"""
        messagebox.showinfo("Info", "Export approval will be implemented")

    def _deny_export(self):
        """Deny export request"""
        messagebox.showinfo("Info", "Export denial will be implemented")

    def _scan_sql_injection(self):
        """Run SQL injection scan"""
        # Create dialog for input
        dialog = tk.Toplevel(self)
        dialog.title("SQL Injection Scanner")
        dialog.geometry("500x300")
        dialog.transient(self)

        tk.Label(dialog, text="Test SQL Query:", font=("Arial", 10, "bold")).pack(pady=10)
        query_text = tk.Text(dialog, width=50, height=8)
        query_text.pack(pady=10, padx=20)
        query_text.insert("1.0", "SELECT * FROM users WHERE id = 1 OR 1=1")

        result_label = tk.Label(dialog, text="", font=("Arial", 10), wraplength=450)
        result_label.pack(pady=10)

        def scan():
            query = query_text.get("1.0", tk.END).strip()
            result = self.vuln_scanner.scan_sql_injection(query)

            if result['vulnerable']:
                result_label.config(text=f"⚠️ VULNERABLE!\n\nFound {len(result['vulnerabilities'])} SQL injection patterns", fg="red")
                # Save to database
                conn = sqlite3.connect(self.session_mgr.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO vulnerability_scan_results (scan_type, target, severity, vulnerable, details)
                    VALUES (?, ?, ?, ?, ?)
                """, ("sql_injection", query[:100], "high", 1, json.dumps(result['vulnerabilities'])))
                conn.commit()
                conn.close()
            else:
                result_label.config(text="✅ No SQL injection vulnerabilities detected", fg="green")

            self._load_vulnerabilities()

        ttk.Button(dialog, text="Scan", command=scan).pack(pady=10)

    def _scan_xss(self):
        """Run XSS scan"""
        # Create dialog for input
        dialog = tk.Toplevel(self)
        dialog.title("XSS Scanner")
        dialog.geometry("500x300")
        dialog.transient(self)

        tk.Label(dialog, text="Test User Input:", font=("Arial", 10, "bold")).pack(pady=10)
        input_text = tk.Text(dialog, width=50, height=8)
        input_text.pack(pady=10, padx=20)
        input_text.insert("1.0", "<script>alert('XSS')</script>")

        result_label = tk.Label(dialog, text="", font=("Arial", 10), wraplength=450)
        result_label.pack(pady=10)

        def scan():
            user_input = input_text.get("1.0", tk.END).strip()
            result = self.vuln_scanner.scan_xss(user_input)

            if result['vulnerable']:
                result_label.config(text=f"⚠️ VULNERABLE!\n\nFound {len(result['vulnerabilities'])} XSS patterns", fg="red")
                # Save to database
                conn = sqlite3.connect(self.session_mgr.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO vulnerability_scan_results (scan_type, target, severity, vulnerable, details)
                    VALUES (?, ?, ?, ?, ?)
                """, ("xss", user_input[:100], "high", 1, json.dumps(result['vulnerabilities'])))
                conn.commit()
                conn.close()
            else:
                result_label.config(text="✅ No XSS vulnerabilities detected", fg="green")

            self._load_vulnerabilities()

        ttk.Button(dialog, text="Scan", command=scan).pack(pady=10)

    def _scan_dependencies(self):
        """Scan dependencies for vulnerabilities"""
        messagebox.showinfo("Info", "Dependency scanning requires external tools like 'pip-audit' or 'safety'.\n\nThis feature will scan installed packages for known vulnerabilities.")

    # Quick Access Tool Launchers
    def _open_mfa_admin(self):
        """Open MFA Administration Panel"""
        if MFA_ADMIN_AVAILABLE:
            try:
                MFAAdminPanel(self, self.admin_user_id)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open MFA Admin: {str(e)}")
        else:
            messagebox.showwarning("Not Available", "MFA Administration is not available")

    def _open_api_key_manager(self):
        """Open API Key Manager"""
        # Switch to API Security tab
        for i in range(self.notebook.index("end")):
            if "API" in self.notebook.tab(i, "text"):
                self.notebook.select(i)
                break

    def _open_encryption_manager(self):
        """Open Encryption Manager"""
        # Switch to Encryption tab
        for i in range(self.notebook.index("end")):
            if "Encryption" in self.notebook.tab(i, "text"):
                self.notebook.select(i)
                break

    def _open_session_manager(self):
        """Open Session Manager"""
        # Switch to Sessions tab
        for i in range(self.notebook.index("end")):
            if "Sessions" in self.notebook.tab(i, "text"):
                self.notebook.select(i)
                break

    def _open_incident_manager(self):
        """Open Incident Manager"""
        # Switch to Incidents tab
        for i in range(self.notebook.index("end")):
            if "Incidents" in self.notebook.tab(i, "text"):
                self.notebook.select(i)
                break

    def _open_vulnerability_scanner(self):
        """Open Vulnerability Scanner"""
        # Switch to Vulnerabilities tab
        for i in range(self.notebook.index("end")):
            if "Vulnerabilities" in self.notebook.tab(i, "text"):
                self.notebook.select(i)
                break


def show_security_dashboard(parent, admin_user_id: int):
    """Show security dashboard"""
    dashboard = SecurityDashboard(parent, admin_user_id)
    return dashboard


if __name__ == '__main__':
    root = tk.Tk()
    root.withdraw()

    show_security_dashboard(root, admin_user_id=1)

    root.mainloop()
