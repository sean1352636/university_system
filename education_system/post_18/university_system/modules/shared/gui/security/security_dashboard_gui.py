#!/usr/bin/env python3
"""
Comprehensive Security & Compliance Dashboard
Integrates all security features into one admin interface
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import json
from typing import Dict, List

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_available_language_list,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
)
from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
from education_system.post_18.university_system.infrastructure.security.data_encryption import EncryptionManager
from education_system.post_18.university_system.infrastructure.security.comprehensive_security import (
    APISecurityManager,
    PasswordSecurityManager,
    SecurityAuditManager,
    DataLossPreventionManager,
    IncidentResponseManager,
    VulnerabilityScanner
)
from education_system.post_18.university_system.infrastructure.security.init_security_tables import init_security_tables

# Import MFA GUIs
try:
    from education_system.post_18.university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel
    MFA_ADMIN_AVAILABLE = True
except ImportError:
    MFAAdminPanel = None
    MFA_ADMIN_AVAILABLE = False

try:
    from education_system.post_18.university_system.infrastructure.auth.mfa_gui import MFASetupWizard
    MFA_SETUP_AVAILABLE = True
except ImportError:
    MFASetupWizard = None
    MFA_SETUP_AVAILABLE = False

class SecurityDashboard(tk.Toplevel):
    """Comprehensive Security Dashboard"""

    def __init__(self, parent, admin_user_id: int):
        super().__init__(parent)

        self.admin_user_id = admin_user_id

        # Initialize i18n
        init_i18n()

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

        self.title(_t("security_dashboard.title"))
        self.geometry("1400x900")
        self.minsize(1200, 800)

        self._create_widgets()
        self._load_data()
        self.after_idle(self._apply_eqa_context)

        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create dashboard UI"""
        # Header
        # 8.117.68 — flattened to the main GUI's clam-default neutrals.
        # Pre-8.117.68 the header bar was navy (#2C3E50) with white
        # text and the toolbar was pale-grey (#ECF0F1) — visually
        # disconnected from every other workspace tab.
        header_frame = tk.Frame(self, bg="#f0f0f0", height=70)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        tk.Label(
            header_frame,
            text=f"🛡️ {_t('security_dashboard.title')}",
            font=("Arial", 16, "bold"),
            bg="#f0f0f0",
            fg="#000000"
        ).pack(side=tk.LEFT, padx=20, pady=15)

        # Refresh and Close buttons
        ttk.Button(
            header_frame,
            text=f"🔄 {_t('security_dashboard.refresh_all')}",
            command=self._load_data
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            header_frame,
            text=f"🏠 {_t('security_dashboard.return_home')}",
            command=self.destroy
        ).pack(side=tk.RIGHT, padx=5)

        # Language selector button
        ttk.Button(
            header_frame,
            text="🌐",
            command=self._change_language,
            width=3
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            header_frame,
            text=f"❌ {_t('security_dashboard.close')}",
            command=self.destroy
        ).pack(side=tk.RIGHT, padx=20)

        # Quick Access Toolbar
        toolbar_frame = tk.Frame(self, bg="#f0f0f0", height=60)
        toolbar_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        toolbar_frame.pack_propagate(False)

        tk.Label(
            toolbar_frame,
            text=_t("security_dashboard.quick_access.title"),
            font=("Arial", 10, "bold"),
            bg="#f0f0f0"
        ).pack(side=tk.LEFT, padx=10)

        # Add quick access buttons
        ttk.Button(
            toolbar_frame,
            text=f"🔐 {_t('security_dashboard.quick_access.mfa_admin')}",
            command=self._open_mfa_admin
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar_frame,
            text=f"🔑 {_t('security_dashboard.quick_access.api_keys')}",
            command=self._open_api_key_manager
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar_frame,
            text=f"🔒 {_t('security_dashboard.quick_access.encryption')}",
            command=self._open_encryption_manager
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar_frame,
            text=f"👥 {_t('security_dashboard.quick_access.sessions')}",
            command=self._open_session_manager
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar_frame,
            text=f"🚨 {_t('security_dashboard.quick_access.incidents')}",
            command=self._open_incident_manager
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar_frame,
            text=f"🔍 {_t('security_dashboard.quick_access.scanner')}",
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
        self._create_compliance_tab()

    def _create_overview_tab(self):
        """Security overview tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text=f"📊 {_t('security_dashboard.tabs.overview')}")

        # Title
        tk.Label(
            tab,
            text=_t("security_dashboard.overview.title"),
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=15)

        # Stats grid
        stats_frame = tk.Frame(tab, bg="white")
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

        self.overview_stats = {}

        stats = [
            ("active_sessions", _t("security_dashboard.overview.active_sessions"), "#3498DB"),
            ("failed_logins_24h", _t("security_dashboard.overview.failed_logins_24h"), "#E74C3C"),
            ("security_events_24h", _t("security_dashboard.overview.security_events_24h"), "#F39C12"),
            ("encrypted_fields", _t("security_dashboard.overview.encrypted_fields"), "#27AE60"),
            ("api_keys_active", _t("security_dashboard.overview.api_keys_active"), "#9B59B6"),
            ("open_incidents", _t("security_dashboard.overview.open_incidents"), "#E67E22"),
            ("pending_exports", _t("security_dashboard.overview.pending_exports"), "#16A085"),
            ("vulnerabilities_high", _t("security_dashboard.overview.vulnerabilities_high"), "#C0392B")
        ]

        row, col = 0, 0
        for key, label, color in stats:
            card = tk.Frame(stats_frame, bg="#f0f0f0", relief=tk.RIDGE, borderwidth=2)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            tk.Label(
                card,
                text=label,
                font=("Arial", 10),
                bg="#f0f0f0",
                fg="gray"
            ).pack(pady=(15, 0))

            value_label = tk.Label(
                card,
                text="0",
                font=("Arial", 28, "bold"),
                bg="#f0f0f0",
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
            text=_t("security_dashboard.overview.recent_alerts"),
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=(20, 10))

        alerts_frame = tk.Frame(tab)
        alerts_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 20))

        self.alerts_text = scrolledtext.ScrolledText(
            alerts_frame,
            height=10,
            font=("Courier", 9),
            bg="#f0f0f0"
        )
        self.alerts_text.pack(fill=tk.BOTH, expand=True)

    def _create_sessions_tab(self):
        """Session management tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text=f"🔐 {_t('security_dashboard.tabs.sessions')}")

        tk.Label(
            tab,
            text=_t("security_dashboard.sessions.title"),
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=15)

        # Session tree
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ("user", "ip", "location", "created", "last_activity")
        self.sessions_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        self.sessions_tree.heading("user", text=_t("security_dashboard.sessions.col_user"))
        self.sessions_tree.heading("ip", text=_t("security_dashboard.sessions.col_ip"))
        self.sessions_tree.heading("location", text=_t("security_dashboard.sessions.col_location"))
        self.sessions_tree.heading("created", text=_t("security_dashboard.sessions.col_created"))
        self.sessions_tree.heading("last_activity", text=_t("security_dashboard.sessions.col_last_activity"))

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

        ttk.Button(btn_frame, text=_t("security_dashboard.sessions.terminate"), command=self._terminate_session).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("security_dashboard.sessions.view_details"), command=self._view_session_details).pack(side=tk.LEFT, padx=5)

    def _create_encryption_tab(self):
        """Encryption management tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text=f"🔒 {_t('security_dashboard.tabs.encryption')}")

        tk.Label(
            tab,
            text=_t("security_dashboard.encryption.title"),
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
            text=_t("security_dashboard.encryption.encrypted_fields_title"),
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

        ttk.Button(btn_frame, text=_t("security_dashboard.encryption.rotate_key"), command=self._rotate_key).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("security_dashboard.encryption.create_backup"), command=self._create_encrypted_backup).pack(side=tk.LEFT, padx=5)

    def _create_api_security_tab(self):
        """API security tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text=f"🔑 {_t('security_dashboard.tabs.api_security')}")

        tk.Label(
            tab,
            text=_t("security_dashboard.api_security.title"),
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

        ttk.Button(btn_frame, text=_t("security_dashboard.api_security.create_key"), command=self._create_api_key).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("security_dashboard.api_security.revoke_key"), command=self._revoke_api_key).pack(side=tk.LEFT, padx=5)

    def _create_audit_tab(self):
        """Audit & compliance tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text=f"📜 {_t('security_dashboard.tabs.audit')}")

        tk.Label(
            tab,
            text=_t("security_dashboard.audit.title"),
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=15)

        # Compliance report buttons
        report_frame = tk.Frame(tab, bg="white")
        report_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(
            report_frame,
            text=_t("security_dashboard.audit.generate_ferpa"),
            command=lambda: self._generate_compliance_report('ferpa')
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            report_frame,
            text=_t("security_dashboard.audit.generate_gdpr"),
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
        self.notebook.add(tab, text=f"🚨 {_t('security_dashboard.tabs.incidents')}")

        tk.Label(
            tab,
            text=_t("security_dashboard.incidents.title"),
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

        ttk.Button(btn_frame, text=_t("security_dashboard.incidents.create_incident"), command=self._create_incident).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("security_dashboard.incidents.view_details"), command=self._view_incident).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("security_dashboard.incidents.resolve"), command=self._resolve_incident).pack(side=tk.LEFT, padx=5)

    def _create_dlp_tab(self):
        """Data Loss Prevention tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text=f"📊 {_t('security_dashboard.tabs.dlp')}")

        tk.Label(
            tab,
            text=_t("security_dashboard.dlp.title"),
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

        ttk.Button(btn_frame, text=_t("security_dashboard.dlp.approve"), command=self._approve_export).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("security_dashboard.dlp.deny"), command=self._deny_export).pack(side=tk.LEFT, padx=5)

    def _create_vulnerabilities_tab(self):
        """Vulnerability scanning tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text=f"🔍 {_t('security_dashboard.tabs.vulnerabilities')}")

        tk.Label(
            tab,
            text=_t("security_dashboard.vulnerabilities.title"),
            font=("Arial", 12, "bold"),
            bg="white"
        ).pack(pady=15)

        # Scan buttons
        scan_frame = tk.Frame(tab, bg="white")
        scan_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(scan_frame, text=_t("security_dashboard.vulnerabilities.scan_sql_injection"), command=self._scan_sql_injection).pack(side=tk.LEFT, padx=5)
        ttk.Button(scan_frame, text=_t("security_dashboard.vulnerabilities.scan_xss"), command=self._scan_xss).pack(side=tk.LEFT, padx=5)
        ttk.Button(scan_frame, text=_t("security_dashboard.vulnerabilities.scan_dependencies"), command=self._scan_dependencies).pack(side=tk.LEFT, padx=5)

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

    def _create_compliance_tab(self):
        """GDPR/FERPA compliance reporting tab"""
        tab = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab, text="Compliance")

        tk.Label(
            tab, text="Compliance Reporting (GDPR/FERPA)",
            font=("Arial", 12, "bold"), bg="white"
        ).pack(pady=10)

        # Sub-notebook for compliance sections
        compliance_nb = ttk.Notebook(tab)
        compliance_nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # --- Data Access Audit ---
        audit_tab = tk.Frame(compliance_nb, bg="white")
        compliance_nb.add(audit_tab, text="Data Access Audit")

        audit_btn_frame = tk.Frame(audit_tab, bg="white")
        audit_btn_frame.pack(fill=tk.X, padx=15, pady=5)
        ttk.Button(audit_btn_frame, text="Refresh",
                   command=lambda: self._load_compliance_audit()).pack(side=tk.LEFT, padx=5)
        ttk.Button(audit_btn_frame, text="Export Report",
                   command=lambda: self._export_compliance_report('audit')).pack(side=tk.LEFT, padx=5)

        cols = ("timestamp", "user_id", "action", "resource_type", "resource_id", "success")
        self.compliance_audit_tree = ttk.Treeview(
            audit_tab, columns=cols, show="headings", height=12
        )
        for col in cols:
            self.compliance_audit_tree.heading(col, text=col.replace("_", " ").title())
            self.compliance_audit_tree.column(col, width=120)
        self.compliance_audit_tree.column("action", width=180)

        audit_scroll = ttk.Scrollbar(audit_tab, orient=tk.VERTICAL,
                                     command=self.compliance_audit_tree.yview)
        self.compliance_audit_tree.configure(yscrollcommand=audit_scroll.set)
        self.compliance_audit_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 0), pady=5)
        audit_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 15), pady=5)

        # --- Sensitive Data Access ---
        privacy_tab = tk.Frame(compliance_nb, bg="white")
        compliance_nb.add(privacy_tab, text="Sensitive Data Access")

        priv_btn_frame = tk.Frame(privacy_tab, bg="white")
        priv_btn_frame.pack(fill=tk.X, padx=15, pady=5)
        ttk.Button(priv_btn_frame, text="Refresh",
                   command=lambda: self._load_privacy_audit()).pack(side=tk.LEFT, padx=5)
        ttk.Button(priv_btn_frame, text="Export Report",
                   command=lambda: self._export_compliance_report('privacy')).pack(side=tk.LEFT, padx=5)

        priv_cols = ("timestamp", "user_id", "student_id", "action", "data_accessed", "ip_address")
        self.privacy_audit_tree = ttk.Treeview(
            privacy_tab, columns=priv_cols, show="headings", height=12
        )
        for col in priv_cols:
            self.privacy_audit_tree.heading(col, text=col.replace("_", " ").title())
            self.privacy_audit_tree.column(col, width=120)

        priv_scroll = ttk.Scrollbar(privacy_tab, orient=tk.VERTICAL,
                                    command=self.privacy_audit_tree.yview)
        self.privacy_audit_tree.configure(yscrollcommand=priv_scroll.set)
        self.privacy_audit_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 0), pady=5)
        priv_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 15), pady=5)

        # --- Permission Change History ---
        perm_tab = tk.Frame(compliance_nb, bg="white")
        compliance_nb.add(perm_tab, text="Permission Changes")

        perm_btn_frame = tk.Frame(perm_tab, bg="white")
        perm_btn_frame.pack(fill=tk.X, padx=15, pady=5)
        ttk.Button(perm_btn_frame, text="Refresh",
                   command=lambda: self._load_permission_changes()).pack(side=tk.LEFT, padx=5)

        perm_cols = ("timestamp", "user_id", "action", "old_values", "new_values", "ip_address")
        self.permission_changes_tree = ttk.Treeview(
            perm_tab, columns=perm_cols, show="headings", height=12
        )
        for col in perm_cols:
            self.permission_changes_tree.heading(col, text=col.replace("_", " ").title())
            self.permission_changes_tree.column(col, width=120)
        self.permission_changes_tree.column("old_values", width=180)
        self.permission_changes_tree.column("new_values", width=180)

        perm_scroll = ttk.Scrollbar(perm_tab, orient=tk.VERTICAL,
                                    command=self.permission_changes_tree.yview)
        self.permission_changes_tree.configure(yscrollcommand=perm_scroll.set)
        self.permission_changes_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 0), pady=5)
        perm_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 15), pady=5)

        # --- Data Retention ---
        retention_tab = tk.Frame(compliance_nb, bg="white")
        compliance_nb.add(retention_tab, text="Data Retention")

        ret_btn_frame = tk.Frame(retention_tab, bg="white")
        ret_btn_frame.pack(fill=tk.X, padx=15, pady=5)
        ttk.Button(ret_btn_frame, text="Refresh",
                   command=lambda: self._load_retention_policies()).pack(side=tk.LEFT, padx=5)

        ret_cols = ("data_type", "retention_months", "deletion_method", "last_cleanup", "is_active")
        self.retention_tree = ttk.Treeview(
            retention_tab, columns=ret_cols, show="headings", height=10
        )
        self.retention_tree.heading("data_type", text="Data Type")
        self.retention_tree.heading("retention_months", text="Retention (Months)")
        self.retention_tree.heading("deletion_method", text="Deletion Method")
        self.retention_tree.heading("last_cleanup", text="Last Cleanup")
        self.retention_tree.heading("is_active", text="Active")
        for col in ret_cols:
            self.retention_tree.column(col, width=130)

        ret_scroll = ttk.Scrollbar(retention_tab, orient=tk.VERTICAL,
                                   command=self.retention_tree.yview)
        self.retention_tree.configure(yscrollcommand=ret_scroll.set)
        self.retention_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 0), pady=5)
        ret_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 15), pady=5)

    def _load_compliance_audit(self):
        """Load audit trail data for compliance reporting."""
        for item in self.compliance_audit_tree.get_children():
            self.compliance_audit_tree.delete(item)
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT timestamp, user_id, action, resource_type, resource_id, "
                    "CASE WHEN success THEN 'Yes' ELSE 'No' END as success "
                    "FROM audit_trail ORDER BY timestamp DESC LIMIT 500"
                ).fetchall()
                for r in rows:
                    self.compliance_audit_tree.insert('', tk.END, values=tuple(r))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load audit trail: {e}")

    def _load_privacy_audit(self):
        """Load privacy/sensitive data access log."""
        for item in self.privacy_audit_tree.get_children():
            self.privacy_audit_tree.delete(item)
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT timestamp, user_id, student_id, action, data_accessed, ip_address "
                    "FROM privacy_audit_log ORDER BY timestamp DESC LIMIT 500"
                ).fetchall()
                for r in rows:
                    self.privacy_audit_tree.insert('', tk.END, values=tuple(r))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load privacy audit: {e}")

    def _load_permission_changes(self):
        """Load permission change history from audit trail."""
        for item in self.permission_changes_tree.get_children():
            self.permission_changes_tree.delete(item)
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT timestamp, user_id, action, old_values, new_values, ip_address "
                    "FROM audit_trail "
                    "WHERE resource_type IN ('permission', 'role', 'user_permission', 'role_permission') "
                    "ORDER BY timestamp DESC LIMIT 500"
                ).fetchall()
                for r in rows:
                    self.permission_changes_tree.insert('', tk.END, values=tuple(r))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load permission changes: {e}")

    def _load_retention_policies(self):
        """Load data retention policy status."""
        for item in self.retention_tree.get_children():
            self.retention_tree.delete(item)
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT data_type, retention_period_months, deletion_method, "
                    "last_cleanup_date, CASE WHEN is_active THEN 'Yes' ELSE 'No' END "
                    "FROM data_retention_policies ORDER BY data_type"
                ).fetchall()
                for r in rows:
                    self.retention_tree.insert('', tk.END, values=tuple(r))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load retention policies: {e}")

    def _export_compliance_report(self, report_type):
        """Export compliance report to file."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title=f"Export {report_type.title()} Compliance Report"
        )
        if not file_path:
            return
        try:
            import csv
            with get_connection() as conn:
                if report_type == 'audit':
                    rows = conn.execute(
                        "SELECT timestamp, user_id, action, resource_type, resource_id, success "
                        "FROM audit_trail ORDER BY timestamp DESC"
                    ).fetchall()
                    headers = ['Timestamp', 'User ID', 'Action', 'Resource Type', 'Resource ID', 'Success']
                else:
                    rows = conn.execute(
                        "SELECT timestamp, user_id, student_id, action, data_accessed, ip_address "
                        "FROM privacy_audit_log ORDER BY timestamp DESC"
                    ).fetchall()
                    headers = ['Timestamp', 'User ID', 'Student ID', 'Action', 'Data Accessed', 'IP Address']

            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for r in rows:
                    writer.writerow(tuple(r))

            messagebox.showinfo("Export Complete", f"Report exported to {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

    def _apply_eqa_context(self):
        """#3 — Honour an EQA drill-through ("View audit log for this
        submission"). Stores the filter on ``self.audit_prefilter`` for
        downstream tab queries to read; emits a banner above the
        notebook so the user sees the active filter."""
        ctx = getattr(self, "eqa_context", None)
        if not ctx:
            return
        try:
            self.audit_prefilter = {
                "action_prefix": ctx.get("audit_action_prefix"),
                "resource_type": ctx.get("resource_type"),
                "resource_id": ctx.get("resource_id"),
            }
            import tkinter as _tk
            banner = _tk.Label(
                self,
                text=(f"Audit filter: {self.audit_prefilter['action_prefix']}* "
                      f"on {self.audit_prefilter['resource_type']}:"
                      f"{self.audit_prefilter['resource_id']}"),
                bg="#fff7d6", fg="#5a4500",
                font=("Helvetica", 9, "italic"), pady=3,
            )
            banner.pack(fill="x", side="top")
        except Exception:
            pass

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
        self._load_compliance_audit()
        self._load_privacy_audit()
        self._load_permission_changes()
        self._load_retention_policies()

    def _load_overview(self):
        """Load overview statistics"""
        conn = get_connection(db_path=self.session_mgr.db_path)
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
        """
        Load active sessions

        Queries the active_sessions table and populates the sessions tree view
        with user sessions including IP address, location, timestamps, and activity.
        """
        self.sessions_tree.delete(*self.sessions_tree.get_children())

        try:
            sessions = self.session_mgr.get_all_active_sessions()

            for session in sessions:
                # Extract session data
                user = session.get('username', 'Unknown')
                ip = session.get('ip_address', 'N/A')
                location = session.get('location', 'Unknown')
                created = session.get('created_at', '')
                last_activity = session.get('last_activity', '')

                # Format timestamps
                created_str = created[:19] if created else 'N/A'
                activity_str = last_activity[:19] if last_activity else 'N/A'

                self.sessions_tree.insert('', tk.END, values=(
                    user,
                    ip,
                    location,
                    created_str,
                    activity_str
                ))

        except Exception as e:
            print(f"Error loading sessions: {e}")
            messagebox.showerror(
                _t("security_dashboard.common.error"),
                _t("security_dashboard.errors.load_sessions_failed", error=str(e))
            )

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
        """
        Load API keys

        Queries the api_keys table and populates the API keys tree view
        with key details including name, owner, usage stats, rate limits, and status.
        """
        self.api_keys_tree.delete(*self.api_keys_tree.get_children())

        try:
            conn = get_connection(db_path=self.session_mgr.db_path)
            cursor = conn.cursor()

            # Check which columns exist in api_keys table
            cursor.execute("PRAGMA table_info(api_keys)")
            columns = {row[1] for row in cursor.fetchall()}

            if 'user_id' in columns:
                # Schema with user_id column
                cursor.execute("""
                    SELECT a.key_name, COALESCE(u.username, 'Unknown') as username,
                           a.created_at, a.last_used_at, a.rate_limit, a.is_active
                    FROM api_keys a
                    LEFT JOIN users u ON a.user_id = u.id
                    ORDER BY a.created_at DESC
                    LIMIT 100
                """)
            else:
                # Schema with created_by column (or no user reference)
                cursor.execute("""
                    SELECT key_name, COALESCE(created_by, 'System') as username,
                           created_at, last_used_at, rate_limit, is_active
                    FROM api_keys
                    ORDER BY created_at DESC
                    LIMIT 100
                """)

            for row in cursor.fetchall():
                key_name, username, created, last_used, rate_limit, is_active = row

                # Format timestamps
                created_str = created[:19] if created else 'N/A'
                last_used_str = last_used[:19] if last_used else 'Never'

                # Format rate limit
                rate_str = f"{rate_limit}/hour" if rate_limit else 'Unlimited'

                # Status
                status = 'Active' if is_active else 'Revoked'

                self.api_keys_tree.insert('', tk.END, values=(
                    key_name or 'Unnamed',
                    username or 'N/A',
                    created_str,
                    last_used_str,
                    rate_str,
                    status
                ))

            conn.close()

        except sqlite3.OperationalError as e:
            # Table might not exist
            print(f"API keys table not found or error: {e}")
        except Exception as e:
            print(f"Error loading API keys: {e}")
            messagebox.showerror(
                _t("security_dashboard.common.error"),
                _t("security_dashboard.errors.load_api_keys_failed", error=str(e))
            )

    def _load_audit_log(self):
        """
        Load audit log

        Queries the security audit log and populates the audit tree view
        with security events including timestamps, users, event types, severity, and details.
        """
        self.audit_tree.delete(*self.audit_tree.get_children())

        try:
            conn = get_connection(db_path=self.session_mgr.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT se.event_time, COALESCE(u.username, 'System') as username,
                       se.event_type, se.severity, se.details
                FROM security_events se
                LEFT JOIN users u ON se.user_id = u.id
                ORDER BY se.event_time DESC
                LIMIT 500
            """)

            for row in cursor.fetchall():
                event_time, username, event_type, severity, details = row

                # Format timestamp
                time_str = event_time[:19] if event_time else 'N/A'

                # Truncate details for display
                details_short = (details[:80] + '...') if details and len(details) > 80 else (details or '')

                self.audit_tree.insert('', tk.END, values=(
                    time_str,
                    username or 'System',
                    event_type or 'Unknown',
                    severity or 'info',
                    details_short
                ))

            conn.close()

        except sqlite3.OperationalError as e:
            # Table might not exist
            print(f"Security events table not found or error: {e}")
        except Exception as e:
            print(f"Error loading audit log: {e}")
            messagebox.showerror(
                _t("security_dashboard.common.error"),
                _t("security_dashboard.errors.load_audit_failed", error=str(e))
            )

    def _load_incidents(self):
        """Load security incidents"""
        self.incidents_tree.delete(*self.incidents_tree.get_children())

        try:
            conn = get_connection(db_path=self.session_mgr.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, category, severity, status, detected_at, description
                FROM security_incidents
                ORDER BY detected_at DESC
                LIMIT 100
            """)

            for row in cursor.fetchall():
                inc_id, category, severity, status, detected, description = row
                # Truncate description for display
                desc_short = (description[:50] + '...') if description and len(description) > 50 else (description or 'N/A')
                detected_short = detected[:19] if detected else 'N/A'

                self.incidents_tree.insert('', tk.END, values=(
                    inc_id,
                    category or 'Unknown',
                    severity or 'medium',
                    status or 'open',
                    detected_short,
                    desc_short
                ))

            conn.close()
        except Exception as e:
            messagebox.showerror(
                _t("security_dashboard.common.error"),
                _t("security_dashboard.errors.load_incidents_failed", error=str(e))
            )

    def _load_exports(self):
        """
        Load export requests

        Queries the bulk export log and populates the exports tree view
        with data export requests including requester, resource type, record count,
        status, and timestamp for Data Loss Prevention (DLP) monitoring.
        """
        self.exports_tree.delete(*self.exports_tree.get_children())

        try:
            conn = get_connection(db_path=self.session_mgr.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COALESCE(u.username, 'Unknown') as username,
                       b.resource_type, b.record_count, b.status, b.exported_at
                FROM bulk_export_log b
                LEFT JOIN users u ON b.user_id = u.id
                ORDER BY b.exported_at DESC
                LIMIT 200
            """)

            for row in cursor.fetchall():
                username, resource_type, record_count, status, exported_at = row

                # Format timestamp
                time_str = exported_at[:19] if exported_at else 'N/A'

                # Format record count
                count_str = f"{record_count:,}" if record_count else '0'

                self.exports_tree.insert('', tk.END, values=(
                    username or 'Unknown',
                    resource_type or 'N/A',
                    count_str,
                    status or 'pending',
                    time_str
                ))

            conn.close()

        except sqlite3.OperationalError as e:
            # Table might not exist
            print(f"Bulk export log table not found or error: {e}")
        except Exception as e:
            print(f"Error loading exports: {e}")
            messagebox.showerror(
                _t("security_dashboard.common.error"),
                _t("security_dashboard.errors.load_exports_failed", error=str(e))
            )

    def _load_vulnerabilities(self):
        """
        Load vulnerability scans

        Queries the vulnerability scan results and populates the vulnerabilities tree view
        with scan results including scan type, target, severity, vulnerable status,
        details, and scan timestamp for security monitoring.
        """
        self.vulns_tree.delete(*self.vulns_tree.get_children())

        try:
            conn = get_connection(db_path=self.session_mgr.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT scan_type, target, severity, vulnerable, details, scanned_at
                FROM vulnerability_scan_results
                ORDER BY scanned_at DESC, severity DESC
                LIMIT 200
            """)

            for row in cursor.fetchall():
                scan_type, target, severity, vulnerable, details, scanned_at = row

                # Format timestamp
                time_str = scanned_at[:19] if scanned_at else 'N/A'

                # Format vulnerable status
                vuln_status = 'Yes' if vulnerable else 'No'

                # Truncate details for display
                details_short = (details[:60] + '...') if details and len(details) > 60 else (details or 'No details')

                # Color coding by severity (to be handled by tree tags if needed)
                self.vulns_tree.insert('', tk.END, values=(
                    scan_type or 'Unknown',
                    target or 'N/A',
                    severity or 'low',
                    vuln_status,
                    details_short,
                    time_str
                ))

            conn.close()

        except sqlite3.OperationalError as e:
            # Table might not exist
            print(f"Vulnerability scan results table not found or error: {e}")
        except Exception as e:
            print(f"Error loading vulnerabilities: {e}")
            messagebox.showerror(
                _t("security_dashboard.common.error"),
                _t("security_dashboard.errors.load_vulnerabilities_failed", error=str(e))
            )

    # Action methods
    def _terminate_session(self):
        """Terminate selected session"""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showwarning(
                _t("security_dashboard.sessions.no_selection"),
                _t("security_dashboard.sessions.select_session_terminate")
            )
            return

        item = self.sessions_tree.item(selection[0])
        session_id = item['values'][0]

        if messagebox.askyesno(
            _t("security_dashboard.common.confirm"),
            _t("security_dashboard.sessions.confirm_terminate", session_id=session_id)
        ):
            try:
                self.session_mgr.terminate_session(session_id)
                messagebox.showinfo(
                    _t("security_dashboard.common.success"),
                    _t("security_dashboard.sessions.terminated_success")
                )
                self._load_sessions()
            except Exception as e:
                messagebox.showerror(
                    _t("security_dashboard.common.error"),
                    _t("security_dashboard.sessions.terminate_failed", error=str(e))
                )

    def _view_session_details(self):
        """View session details"""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showwarning(
                _t("security_dashboard.sessions.no_selection"),
                _t("security_dashboard.sessions.select_session_view")
            )
            return

        item = self.sessions_tree.item(selection[0])
        values = item['values']

        details = f"""{_t("security_dashboard.sessions.details_title")}:

ID: {values[0]}
{_t("security_dashboard.sessions.col_user")}: {values[1]}
{_t("security_dashboard.sessions.col_ip")}: {values[2]}
{_t("security_dashboard.sessions.col_location")}: {values[3]}
{_t("security_dashboard.sessions.col_created")}: {values[4]}
{_t("security_dashboard.sessions.col_last_activity")}: {values[5]}
"""
        messagebox.showinfo(_t("security_dashboard.sessions.details_title"), details)

    def _rotate_key(self):
        """Rotate encryption key"""
        messagebox.showinfo(
            _t("security_dashboard.common.info"),
            "Key rotation will be implemented"
        )

    def _create_encrypted_backup(self):
        """Create encrypted backup"""
        messagebox.showinfo(
            _t("security_dashboard.common.info"),
            "Encrypted backup will be implemented"
        )

    def _create_api_key(self):
        """Create new API key"""
        # Create dialog
        dialog = tk.Toplevel(self)
        dialog.title(_t("security_dashboard.api_security.create_dialog_title"))
        dialog.geometry("400x300")
        dialog.transient(self)

        tk.Label(dialog, text=_t("security_dashboard.api_security.create_new_key"), font=("Arial", 12, "bold")).pack(pady=10)

        # Form
        form_frame = tk.Frame(dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        tk.Label(form_frame, text=_t("security_dashboard.api_security.key_name")).grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(form_frame, width=30)
        name_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_t("security_dashboard.api_security.user_id")).grid(row=1, column=0, sticky=tk.W, pady=5)
        user_entry = ttk.Entry(form_frame, width=30)
        user_entry.insert(0, str(self.admin_user_id))
        user_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_t("security_dashboard.api_security.permissions")).grid(row=2, column=0, sticky=tk.W, pady=5)
        perms_entry = ttk.Entry(form_frame, width=30)
        perms_entry.insert(0, "read,write")
        perms_entry.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_t("security_dashboard.api_security.rate_limit")).grid(row=3, column=0, sticky=tk.W, pady=5)
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
                messagebox.showinfo(
                    _t("security_dashboard.api_security.key_created_success"),
                    _t("security_dashboard.api_security.key_created_message", key=key)
                )
                dialog.destroy()
                self._load_api_keys()
            else:
                messagebox.showerror(
                    _t("security_dashboard.common.error"),
                    result.get('error', _t("security_dashboard.api_security.create_failed"))
                )

        ttk.Button(dialog, text=_t("security_dashboard.api_security.create"), command=create_key).pack(pady=10)

    def _revoke_api_key(self):
        """Revoke API key"""
        selection = self.api_keys_tree.selection()
        if not selection:
            messagebox.showwarning(
                _t("security_dashboard.sessions.no_selection"),
                _t("security_dashboard.api_security.select_key_revoke")
            )
            return

        item = self.api_keys_tree.item(selection[0])
        key_id = item['values'][0]
        key_name = item['values'][1]

        if messagebox.askyesno(
            _t("security_dashboard.common.confirm"),
            _t("security_dashboard.api_security.confirm_revoke", name=key_name)
        ):
            try:
                conn = get_connection(db_path=self.session_mgr.db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE api_keys SET is_active = 0 WHERE id = ?", (key_id,))
                conn.commit()
                conn.close()
                messagebox.showinfo(
                    _t("security_dashboard.common.success"),
                    _t("security_dashboard.api_security.revoked_success")
                )
                self._load_api_keys()
            except Exception as e:
                messagebox.showerror(
                    _t("security_dashboard.common.error"),
                    _t("security_dashboard.api_security.revoke_failed", error=str(e))
                )

    def _generate_compliance_report(self, report_type: str):
        """Generate compliance report"""
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        report = self.audit_mgr.generate_compliance_report(start_date, end_date, report_type)

        # Show report
        report_window = tk.Toplevel(self)
        report_window.title(_t("security_dashboard.audit.report_title", type=report_type.upper()))
        report_window.geometry("700x750")

        # Report text area
        text_frame = tk.Frame(report_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)

        report_content = json.dumps(report, indent=2)
        text.insert(tk.END, report_content)
        text.config(state=tk.DISABLED)

        # Button frame
        btn_frame = tk.Frame(report_window)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        def send_to_admin():
            """Send report to admin via email"""
            try:
                # Import email service
                from education_system.post_18.university_system.infrastructure.email.email_service import send_email
                from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
                from education_system.post_18.university_system.infrastructure.database.db import get_connection

                # Get admin email from database
                admin_email = None
                admin_name = "Administrator"
                with get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT email, first_name, last_name
                        FROM users
                        WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                        LIMIT 1
                    """)
                    admin_row = cursor.fetchone()
                    if admin_row:
                        admin_email = admin_row[0]
                        first_name = admin_row[1] or ''
                        last_name = admin_row[2] or ''
                        if first_name or last_name:
                            admin_name = f"{first_name} {last_name}".strip()

                if not admin_email:
                    messagebox.showerror(
                        _t("security_dashboard.common.error"),
                        _t("security_dashboard.audit.no_admin_email")
                    )
                    return

                # Send email using template
                subject, body = render_template("compliance_report", {
                    "report_type": report_type.upper(),
                    "date": datetime.now().strftime('%Y-%m-%d'),
                    "admin_name": admin_name,
                    "generated_datetime": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "start_date": start_date.strftime('%Y-%m-%d'),
                    "end_date": end_date.strftime('%Y-%m-%d'),
                    "report_content": report_content
                })

                result = send_email(
                    recipient_email=admin_email,
                    subject=subject,
                    body=body
                )

                if result:
                    messagebox.showinfo(
                        _t("security_dashboard.common.success"),
                        _t("security_dashboard.audit.report_sent", email=admin_email)
                    )
                else:
                    messagebox.showinfo(
                        _t("security_dashboard.common.info"),
                        _t("security_dashboard.audit.report_queued", email=admin_email)
                    )

            except Exception as e:
                messagebox.showerror(
                    _t("security_dashboard.common.error"),
                    _t("security_dashboard.audit.send_failed", error=str(e))
                )

        ttk.Button(btn_frame, text=f"📧 {_t('security_dashboard.audit.send_to_admin')}", command=send_to_admin).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=f"🏠 {_t('security_dashboard.return_home')}", command=report_window.destroy).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=f"❌ {_t('security_dashboard.close')}", command=report_window.destroy).pack(side=tk.RIGHT, padx=5)

    def _create_incident(self):
        """Create security incident"""
        # Create dialog
        dialog = tk.Toplevel(self)
        dialog.title(_t("security_dashboard.incidents.create_dialog_title"))
        dialog.geometry("500x400")
        dialog.transient(self)

        tk.Label(dialog, text=_t("security_dashboard.incidents.create_dialog_title"), font=("Arial", 12, "bold")).pack(pady=10)

        # Form
        form_frame = tk.Frame(dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        tk.Label(form_frame, text=_t("security_dashboard.incidents.incident_type")).grid(row=0, column=0, sticky=tk.W, pady=5)
        type_combo = ttk.Combobox(form_frame, width=28, values=[
            _t("security_dashboard.incidents.type_unauthorized_access"),
            _t("security_dashboard.incidents.type_data_breach"),
            _t("security_dashboard.incidents.type_malware"),
            _t("security_dashboard.incidents.type_phishing"),
            _t("security_dashboard.incidents.type_ddos"),
            _t("security_dashboard.incidents.type_insider_threat"),
            _t("security_dashboard.incidents.type_policy_violation"),
            _t("security_dashboard.incidents.type_other")
        ])
        type_combo.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_t("security_dashboard.incidents.severity")).grid(row=1, column=0, sticky=tk.W, pady=5)
        severity_combo = ttk.Combobox(form_frame, width=28, values=[
            _t("security_dashboard.incidents.severity_low"),
            _t("security_dashboard.incidents.severity_medium"),
            _t("security_dashboard.incidents.severity_high"),
            _t("security_dashboard.incidents.severity_critical")
        ])
        severity_combo.current(1)
        severity_combo.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_t("security_dashboard.incidents.description")).grid(row=2, column=0, sticky=tk.NW, pady=5)
        desc_text = tk.Text(form_frame, width=30, height=10)
        desc_text.grid(row=2, column=1, pady=5)

        def create_inc():
            incident_type = type_combo.get()
            severity = severity_combo.get()
            description = desc_text.get("1.0", tk.END).strip()

            if not incident_type or not description:
                messagebox.showwarning(
                    _t("security_dashboard.common.warning"),
                    _t("security_dashboard.incidents.missing_fields")
                )
                return

            result = self.incident_mgr.create_incident(
                incident_type, severity, description, self.admin_user_id
            )

            if result.get('success'):
                messagebox.showinfo(
                    _t("security_dashboard.common.success"),
                    _t("security_dashboard.incidents.created_success", id=result['incident_id'])
                )
                dialog.destroy()
                self._load_incidents()
            else:
                messagebox.showerror(
                    _t("security_dashboard.common.error"),
                    result.get('error', _t("security_dashboard.incidents.create_failed"))
                )

        ttk.Button(dialog, text=_t("security_dashboard.incidents.create_incident"), command=create_inc).pack(pady=10)

    def _view_incident(self):
        """View incident details"""
        selection = self.incidents_tree.selection()
        if not selection:
            messagebox.showwarning(
                _t("security_dashboard.sessions.no_selection"),
                _t("security_dashboard.incidents.select_incident_view")
            )
            return

        item = self.incidents_tree.item(selection[0])
        values = item['values']

        details = f"""{_t("security_dashboard.incidents.details_title")}:

ID: {values[0]}
{_t("security_dashboard.incidents.col_type")}: {values[1]}
{_t("security_dashboard.incidents.col_severity")}: {values[2]}
{_t("security_dashboard.incidents.col_status")}: {values[3]}
{_t("security_dashboard.incidents.col_detected")}: {values[4]}
{_t("security_dashboard.incidents.col_description")}: {values[5]}
"""
        messagebox.showinfo(_t("security_dashboard.incidents.details_title"), details)

    def _resolve_incident(self):
        """Resolve incident"""
        selection = self.incidents_tree.selection()
        if not selection:
            messagebox.showwarning(
                _t("security_dashboard.sessions.no_selection"),
                _t("security_dashboard.incidents.select_incident_resolve")
            )
            return

        item = self.incidents_tree.item(selection[0])
        incident_id = item['values'][0]

        # Create dialog for resolution notes
        dialog = tk.Toplevel(self)
        dialog.title(_t("security_dashboard.incidents.resolve_dialog_title"))
        dialog.geometry("400x300")
        dialog.transient(self)

        tk.Label(dialog, text=_t("security_dashboard.incidents.resolution_notes"), font=("Arial", 10, "bold")).pack(pady=10)
        notes_text = tk.Text(dialog, width=40, height=10)
        notes_text.pack(pady=10, padx=20)

        def resolve():
            notes = notes_text.get("1.0", tk.END).strip()
            if not notes:
                messagebox.showwarning(
                    _t("security_dashboard.common.warning"),
                    _t("security_dashboard.incidents.missing_notes")
                )
                return

            try:
                conn = get_connection(db_path=self.session_mgr.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE security_incidents
                    SET status = 'resolved', resolved_at = ?, resolution = ?
                    WHERE id = ?
                """, (datetime.now(), notes, incident_id))
                conn.commit()
                conn.close()
                messagebox.showinfo(
                    _t("security_dashboard.common.success"),
                    _t("security_dashboard.incidents.resolved_success")
                )
                dialog.destroy()
                self._load_incidents()
            except Exception as e:
                messagebox.showerror(
                    _t("security_dashboard.common.error"),
                    _t("security_dashboard.incidents.resolve_failed", error=str(e))
                )

        ttk.Button(dialog, text=_t("security_dashboard.incidents.resolve"), command=resolve).pack(pady=10)

    def _approve_export(self):
        """Approve export request"""
        messagebox.showinfo(
            _t("security_dashboard.common.info"),
            "Export approval will be implemented"
        )

    def _deny_export(self):
        """Deny export request"""
        messagebox.showinfo(
            _t("security_dashboard.common.info"),
            "Export denial will be implemented"
        )

    def _scan_sql_injection(self):
        """Run SQL injection scan"""
        # Create dialog for input
        dialog = tk.Toplevel(self)
        dialog.title(_t("security_dashboard.vulnerabilities.sql_scanner_title"))
        dialog.geometry("500x300")
        dialog.transient(self)

        tk.Label(dialog, text=_t("security_dashboard.vulnerabilities.test_query"), font=("Arial", 10, "bold")).pack(pady=10)
        query_text = tk.Text(dialog, width=50, height=8)
        query_text.pack(pady=10, padx=20)
        query_text.insert("1.0", "SELECT * FROM users WHERE id = 1 OR 1=1")

        result_label = tk.Label(dialog, text="", font=("Arial", 10), wraplength=450)
        result_label.pack(pady=10)

        def scan():
            query = query_text.get("1.0", tk.END).strip()
            result = self.vuln_scanner.scan_sql_injection(query)

            if result['vulnerable']:
                result_label.config(
                    text=f"⚠️ {_t('security_dashboard.vulnerabilities.vulnerable_found')}\n\n{_t('security_dashboard.vulnerabilities.found_patterns', count=len(result['vulnerabilities']), type='SQL injection')}",
                    fg="red"
                )
                # Save to database
                conn = get_connection(db_path=self.session_mgr.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO vulnerability_scan_results (scan_type, target, severity, vulnerable, details)
                    VALUES (?, ?, ?, ?, ?)
                """, ("sql_injection", query[:100], "high", 1, json.dumps(result['vulnerabilities'])))
                conn.commit()
                conn.close()
            else:
                result_label.config(
                    text=f"✅ {_t('security_dashboard.vulnerabilities.no_vulnerabilities', type='SQL injection')}",
                    fg="green"
                )

            self._load_vulnerabilities()

        ttk.Button(dialog, text=_t("security_dashboard.vulnerabilities.scan"), command=scan).pack(pady=10)

    def _scan_xss(self):
        """Run XSS scan"""
        # Create dialog for input
        dialog = tk.Toplevel(self)
        dialog.title(_t("security_dashboard.vulnerabilities.xss_scanner_title"))
        dialog.geometry("500x300")
        dialog.transient(self)

        tk.Label(dialog, text=_t("security_dashboard.vulnerabilities.test_input"), font=("Arial", 10, "bold")).pack(pady=10)
        input_text = tk.Text(dialog, width=50, height=8)
        input_text.pack(pady=10, padx=20)
        input_text.insert("1.0", "<script>alert('XSS')</script>")

        result_label = tk.Label(dialog, text="", font=("Arial", 10), wraplength=450)
        result_label.pack(pady=10)

        def scan():
            user_input = input_text.get("1.0", tk.END).strip()
            result = self.vuln_scanner.scan_xss(user_input)

            if result['vulnerable']:
                result_label.config(
                    text=f"⚠️ {_t('security_dashboard.vulnerabilities.vulnerable_found')}\n\n{_t('security_dashboard.vulnerabilities.found_patterns', count=len(result['vulnerabilities']), type='XSS')}",
                    fg="red"
                )
                # Save to database
                conn = get_connection(db_path=self.session_mgr.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO vulnerability_scan_results (scan_type, target, severity, vulnerable, details)
                    VALUES (?, ?, ?, ?, ?)
                """, ("xss", user_input[:100], "high", 1, json.dumps(result['vulnerabilities'])))
                conn.commit()
                conn.close()
            else:
                result_label.config(
                    text=f"✅ {_t('security_dashboard.vulnerabilities.no_vulnerabilities', type='XSS')}",
                    fg="green"
                )

            self._load_vulnerabilities()

        ttk.Button(dialog, text=_t("security_dashboard.vulnerabilities.scan"), command=scan).pack(pady=10)

    def _scan_dependencies(self):
        """Scan dependencies for vulnerabilities"""
        messagebox.showinfo(
            _t("security_dashboard.common.info"),
            _t("security_dashboard.vulnerabilities.dependency_info")
        )

    # Quick Access Tool Launchers
    def _open_mfa_admin(self):
        """Open MFA Administration Panel"""
        if MFA_ADMIN_AVAILABLE:
            try:
                MFAAdminPanel(self, self.admin_user_id)
            except Exception as e:
                messagebox.showerror(
                    _t("security_dashboard.common.error"),
                    _t("security_dashboard.mfa.open_failed", error=str(e))
                )
        else:
            messagebox.showwarning(
                _t("security_dashboard.common.warning"),
                _t("security_dashboard.mfa.not_available")
            )

    def _change_language(self):
        """Open language selector and refresh UI"""
        old_lang = get_current_language()
        show_gui_language_selector(self)
        new_lang = get_current_language()

        if old_lang != new_lang:
            # Notify user that restart is recommended for full effect
            messagebox.showinfo(
                _t("security_dashboard.common.info"),
                _t("activity_logger.language.changed_message")
            )
            # Refresh the window title at minimum
            self.title(_t("security_dashboard.title"))

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
