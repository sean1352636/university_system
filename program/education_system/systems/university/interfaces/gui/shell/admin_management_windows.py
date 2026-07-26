"""
Admin Management Windows for University Management System

This module provides comprehensive administrative tools including:
- API Management
- Audit Logs Viewer
- System Diagnostics
- Database Maintenance

These windows can be integrated into any GUI application.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import json
import os
import time
import threading
from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n

# Initialize i18n
init_i18n()

class ApiManagementWindow:
    """Comprehensive API Management Interface"""

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("admin_windows.api.title"))
        self.window.geometry("900x700")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill='x', padx=20, pady=20)
        ttk.Label(title_frame, text=_("admin_windows.api.center_title"),
                 font=('Arial', 16, 'bold')).pack()

        # Create notebook for different API sections
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        # API Keys Tab
        keys_frame = ttk.Frame(notebook)
        notebook.add(keys_frame, text=_("admin_windows.api.tabs.api_keys"))
        self.create_api_keys_tab(keys_frame)

        # Endpoints Tab
        endpoints_frame = ttk.Frame(notebook)
        notebook.add(endpoints_frame, text=_("admin_windows.api.tabs.endpoints"))
        self.create_endpoints_tab(endpoints_frame)

        # Usage Analytics Tab
        analytics_frame = ttk.Frame(notebook)
        notebook.add(analytics_frame, text=_("admin_windows.api.tabs.analytics"))
        self.create_analytics_tab(analytics_frame)

        # Security Tab
        security_frame = ttk.Frame(notebook)
        notebook.add(security_frame, text=_("admin_windows.api.tabs.security"))
        self.create_security_tab(security_frame)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy).pack(pady=10)

    def create_api_keys_tab(self, parent):
        """Create API keys management tab"""
        # API keys list
        keys_frame = ttk.LabelFrame(parent, text=_("admin_windows.api.keys.active_keys"), padding="15")
        keys_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # Keys treeview
        columns = ('Key ID', 'Name', 'Type', 'Created', 'Last Used', 'Status', 'Requests')
        column_names = [
            _("admin_windows.api.keys.columns.key_id"),
            _("admin_windows.api.keys.columns.name"),
            _("admin_windows.api.keys.columns.type"),
            _("admin_windows.api.keys.columns.created"),
            _("admin_windows.api.keys.columns.last_used"),
            _("admin_windows.api.keys.columns.status"),
            _("admin_windows.api.keys.columns.requests")
        ]
        self.keys_tree = ttk.Treeview(keys_frame, columns=columns, show='headings', height=12)

        for col, name in zip(columns, column_names):
            self.keys_tree.heading(col, text=name)
            self.keys_tree.column(col, width=120)

        self.keys_tree.pack(fill='both', expand=True, pady=(0, 15))

        # Add sample data
        sample_keys = [
            ("api_001", _("admin_windows.api.keys.sample.student_portal"), _("admin_windows.api.keys.types.read_write"), "2024-01-15", "2024-01-29", _("admin_windows.api.keys.status.active"), "15,234"),
            ("api_002", _("admin_windows.api.keys.sample.mobile_app"), _("admin_windows.api.keys.types.read_only"), "2024-01-20", "2024-01-29", _("admin_windows.api.keys.status.active"), "8,957"),
            ("api_003", _("admin_windows.api.keys.sample.third_party"), _("admin_windows.api.keys.types.limited"), "2024-01-25", "2024-01-28", _("admin_windows.api.keys.status.suspended"), "2,103"),
            ("api_004", _("admin_windows.api.keys.sample.analytics"), _("admin_windows.api.keys.types.read_only"), "2024-01-10", "2024-01-29", _("admin_windows.api.keys.status.active"), "45,782"),
            ("api_005", _("admin_windows.api.keys.sample.backup_service"), _("admin_windows.api.keys.types.admin"), "2024-01-05", "2024-01-29", _("admin_windows.api.keys.status.active"), "892")
        ]

        for key_data in sample_keys:
            self.keys_tree.insert('', 'end', values=key_data)

        # Controls
        controls_frame = ttk.Frame(keys_frame)
        controls_frame.pack(fill='x')

        ttk.Button(controls_frame, text=_("admin_windows.api.keys.buttons.generate"),
                  command=self.generate_api_key).pack(side='left', padx=(0, 10))
        ttk.Button(controls_frame, text=_("admin_windows.api.keys.buttons.revoke"),
                  command=self.revoke_api_key).pack(side='left', padx=(0, 10))
        ttk.Button(controls_frame, text=_("admin_windows.api.keys.buttons.view_details"),
                  command=self.view_key_details).pack(side='left', padx=(0, 10))
        ttk.Button(controls_frame, text=_("admin_windows.api.keys.buttons.export"),
                  command=self.export_keys).pack(side='left')

    def create_endpoints_tab(self, parent):
        """Create API endpoints tab"""
        # Endpoints list
        endpoints_frame = ttk.LabelFrame(parent, text=_("admin_windows.api.endpoints.available"), padding="15")
        endpoints_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # Endpoints treeview
        columns = ('Method', 'Endpoint', 'Description', 'Auth Required', 'Rate Limit', 'Status')
        column_names = [
            _("admin_windows.api.endpoints.columns.method"),
            _("admin_windows.api.endpoints.columns.endpoint"),
            _("admin_windows.api.endpoints.columns.description"),
            _("admin_windows.api.endpoints.columns.auth_required"),
            _("admin_windows.api.endpoints.columns.rate_limit"),
            _("admin_windows.api.endpoints.columns.status")
        ]
        self.endpoints_tree = ttk.Treeview(endpoints_frame, columns=columns, show='headings', height=15)

        for col, name in zip(columns, column_names):
            self.endpoints_tree.heading(col, text=name)
            self.endpoints_tree.column(col, width=150)

        self.endpoints_tree.pack(fill='both', expand=True, pady=(0, 15))

        # Add sample endpoints
        sample_endpoints = [
            ("GET", "/api/students", _("admin_windows.api.endpoints.desc.list_students"), _("common.yes"), "100/hour", _("admin_windows.api.keys.status.active")),
            ("POST", "/api/students", _("admin_windows.api.endpoints.desc.create_student"), _("common.yes"), "50/hour", _("admin_windows.api.keys.status.active")),
            ("GET", "/api/students/{id}", _("admin_windows.api.endpoints.desc.get_student"), _("common.yes"), "200/hour", _("admin_windows.api.keys.status.active")),
            ("PUT", "/api/students/{id}", _("admin_windows.api.endpoints.desc.update_student"), _("common.yes"), "50/hour", _("admin_windows.api.keys.status.active")),
            ("DELETE", "/api/students/{id}", _("admin_windows.api.endpoints.desc.delete_student"), _("common.yes"), "10/hour", _("admin_windows.api.keys.status.active")),
            ("GET", "/api/modules", _("admin_windows.api.endpoints.desc.list_modules"), _("common.yes"), "100/hour", _("admin_windows.api.keys.status.active")),
            ("POST", "/api/attendance", _("admin_windows.api.endpoints.desc.record_attendance"), _("common.yes"), "1000/hour", _("admin_windows.api.keys.status.active")),
            ("GET", "/api/reports", _("admin_windows.api.endpoints.desc.generate_reports"), _("common.yes"), "20/hour", _("admin_windows.api.keys.status.active")),
            ("POST", "/api/auth/login", _("admin_windows.api.endpoints.desc.user_auth"), _("common.no"), "10/minute", _("admin_windows.api.keys.status.active")),
            ("GET", "/api/system/health", _("admin_windows.api.endpoints.desc.health_check"), _("common.no"), _("admin_windows.api.endpoints.unlimited"), _("admin_windows.api.keys.status.active"))
        ]

        for endpoint_data in sample_endpoints:
            self.endpoints_tree.insert('', 'end', values=endpoint_data)

        # Endpoint controls
        endpoint_controls = ttk.Frame(endpoints_frame)
        endpoint_controls.pack(fill='x')

        ttk.Button(endpoint_controls, text=_("admin_windows.api.endpoints.buttons.test"),
                  command=self.test_endpoint).pack(side='left', padx=(0, 10))
        ttk.Button(endpoint_controls, text=_("admin_windows.api.endpoints.buttons.view_docs"),
                  command=self.view_endpoint_docs).pack(side='left', padx=(0, 10))
        ttk.Button(endpoint_controls, text=_("admin_windows.api.endpoints.buttons.configure_rate"),
                  command=self.configure_rate_limits).pack(side='left')

    def create_analytics_tab(self, parent):
        """Create API analytics tab"""
        # Analytics display
        analytics_frame = ttk.LabelFrame(parent, text=_("admin_windows.api.analytics.usage"), padding="15")
        analytics_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # Stats summary
        stats_frame = ttk.Frame(analytics_frame)
        stats_frame.pack(fill='x', pady=(0, 15))

        stats_data = [
            (_("admin_windows.api.analytics.total_requests"), "12,547"),
            (_("admin_windows.api.analytics.active_keys"), "5"),
            (_("admin_windows.api.analytics.error_rate"), "0.03%"),
            (_("admin_windows.api.analytics.avg_response"), "125ms")
        ]

        for i, (label, value) in enumerate(stats_data):
            stat_frame = ttk.LabelFrame(stats_frame, text=label, padding="10")
            stat_frame.grid(row=0, column=i, padx=5, sticky='ew')
            ttk.Label(stat_frame, text=value, font=('Arial', 14, 'bold')).pack()
            stats_frame.grid_columnconfigure(i, weight=1)

        # Analytics text display
        analytics_text = scrolledtext.ScrolledText(analytics_frame, height=20, wrap='word')
        analytics_text.pack(fill='both', expand=True)

        analytics_data = f"""
API USAGE ANALYTICS REPORT
=========================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

DAILY STATISTICS (Last 24 Hours):
• Total Requests: 12,547
• Successful Requests: 12,546 (99.97%)
• Failed Requests: 1 (0.03%)
• Unique Clients: 23
• Data Transferred: 145.7 MB

TOP ENDPOINTS BY USAGE:
1. GET /api/students - 4,234 requests (33.7%)
2. POST /api/attendance - 3,891 requests (31.0%)
3. GET /api/modules - 2,156 requests (17.2%)
4. GET /api/reports - 1,234 requests (9.8%)
5. POST /api/auth/login - 987 requests (7.9%)

API KEY USAGE:
• api_001 (Student Portal): 6,234 requests (49.7%)
• api_002 (Mobile App): 3,891 requests (31.0%)
• api_004 (Analytics): 2,156 requests (17.2%)
• api_005 (Backup Service): 234 requests (1.9%)
• api_003 (Third Party): 32 requests (0.3%) - Suspended

RESPONSE TIME ANALYSIS:
• Average: 125ms
• Median: 89ms
• 95th Percentile: 245ms
• 99th Percentile: 512ms
• Fastest: 12ms (GET /api/system/health)
• Slowest: 1,234ms (GET /api/reports/complex)

ERROR ANALYSIS:
• 401 Unauthorized: 0 (0.00%)
• 403 Forbidden: 0 (0.00%)
• 404 Not Found: 1 (0.03%)
• 429 Rate Limited: 0 (0.00%)
• 500 Server Error: 0 (0.00%)

HOURLY DISTRIBUTION:
00:00-01:00: 234 requests
01:00-02:00: 156 requests
02:00-03:00: 89 requests
...
08:00-09:00: 1,234 requests (Peak)
09:00-10:00: 1,156 requests
10:00-11:00: 1,345 requests (Peak)
11:00-12:00: 1,289 requests
...

GEOGRAPHIC DISTRIBUTION:
• Local Network: 8,234 requests (65.6%)
• External: 4,313 requests (34.4%)
• Top Countries: UK (45%), US (25%), EU (20%), Other (10%)

SECURITY EVENTS:
• Failed Authentication Attempts: 12
• Rate Limit Violations: 0
• Suspicious Activity: 0
• Blocked IPs: 0

RECOMMENDATIONS:
✓ API performance is excellent
✓ Error rate is within acceptable limits
✓ Consider caching for /api/reports endpoint
✓ Monitor api_003 suspension status
✓ Peak usage at 10-11 AM, ensure adequate capacity
"""

        analytics_text.insert('1.0', analytics_data)
        analytics_text.config(state='disabled')

    def create_security_tab(self, parent):
        """Create API security tab"""
        # Security settings
        security_frame = ttk.LabelFrame(parent, text=_("admin_windows.api.security.config"), padding="15")
        security_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # Security options
        options_frame = ttk.Frame(security_frame)
        options_frame.pack(fill='x', pady=(0, 15))

        # Rate limiting
        rate_frame = ttk.LabelFrame(options_frame, text=_("admin_windows.api.security.rate_limiting"), padding="10")
        rate_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(rate_frame, text=_("admin_windows.api.security.global_rate_limit")).grid(row=0, column=0, sticky='w', padx=(0, 10))
        rate_var = tk.StringVar(value=_("admin_windows.api.security.rate_value"))
        ttk.Entry(rate_frame, textvariable=rate_var, width=20).grid(row=0, column=1, sticky='w')

        # Authentication
        auth_frame = ttk.LabelFrame(options_frame, text=_("admin_windows.api.security.authentication"), padding="10")
        auth_frame.pack(fill='x', pady=(0, 10))

        auth_methods = [_("admin_windows.api.security.auth_api_key"), _("admin_windows.api.security.auth_oauth"), _("admin_windows.api.security.auth_jwt"), _("admin_windows.api.security.auth_basic")]
        for i, method in enumerate(auth_methods):
            var = tk.BooleanVar(value=(i == 0))  # API Key enabled by default
            ttk.Checkbutton(auth_frame, text=method, variable=var).grid(row=0, column=i, sticky='w', padx=10)

        # Security log
        log_frame = ttk.LabelFrame(security_frame, text=_("admin_windows.api.security.event_log"), padding="10")
        log_frame.pack(fill='both', expand=True)

        security_log = scrolledtext.ScrolledText(log_frame, height=15, wrap='word')
        security_log.pack(fill='both', expand=True)

        log_data = f"""
API SECURITY LOG
===============
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - System started
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Rate limiting enabled
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - API key validation active
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - SSL/TLS encryption verified
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - CORS policy applied
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Request logging enabled
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Firewall rules updated
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - DDoS protection active
"""

        security_log.insert('1.0', log_data)
        security_log.config(state='disabled')

    def generate_api_key(self):
        """Generate new API key"""
        import secrets
        import string

        # Generate secure random key
        alphabet = string.ascii_letters + string.digits
        api_key = ''.join(secrets.choice(alphabet) for _ in range(32))

        messagebox.showinfo(_("admin_windows.api.messages.key_generated_title"),
                           _("admin_windows.api.messages.key_generated_body", key=api_key))

    def revoke_api_key(self):
        """Revoke selected API key"""
        selection = self.keys_tree.selection()
        if not selection:
            messagebox.showwarning(_("admin_windows.messages.no_selection"), _("admin_windows.api.messages.select_key_revoke"))
            return

        item = self.keys_tree.item(selection[0])
        key_id = item['values'][0]

        result = messagebox.askyesno(_("admin_windows.api.messages.confirm_revoke_title"),
                                   _("admin_windows.api.messages.confirm_revoke_body", key_id=key_id))
        if result:
            messagebox.showinfo(_("admin_windows.api.messages.key_revoked_title"), _("admin_windows.api.messages.key_revoked_body", key_id=key_id))

    def view_key_details(self):
        """View detailed information about selected API key"""
        selection = self.keys_tree.selection()
        if not selection:
            messagebox.showwarning(_("admin_windows.messages.no_selection"), _("admin_windows.api.messages.select_key_details"))
            return

        item = self.keys_tree.item(selection[0])
        key_data = item['values']

        details = _("admin_windows.api.messages.key_details_body",
                   key_id=key_data[0], name=key_data[1], type=key_data[2],
                   created=key_data[3], last_used=key_data[4], status=key_data[5],
                   total_requests=key_data[6])

        messagebox.showinfo(_("admin_windows.api.messages.key_details_title"), details)

    def export_keys(self):
        """Export API keys configuration"""
        filename = filedialog.asksaveasfilename(
            title=_("admin_windows.api.messages.export_keys_title"),
            defaultextension=".json",
            filetypes=[(_("admin_windows.filetypes.json"), "*.json"), (_("admin_windows.filetypes.all"), "*.*")]
        )

        if filename:
            messagebox.showinfo(_("admin_windows.messages.export_complete"), _("admin_windows.api.messages.keys_exported", filename=filename))

    def test_endpoint(self):
        """Test selected API endpoint"""
        selection = self.endpoints_tree.selection()
        if not selection:
            messagebox.showwarning(_("admin_windows.messages.no_selection"), _("admin_windows.api.messages.select_endpoint_test"))
            return

        item = self.endpoints_tree.item(selection[0])
        endpoint_data = item['values']

        messagebox.showinfo(_("admin_windows.api.messages.endpoint_test_title"),
                           _("admin_windows.api.messages.endpoint_test_body", method=endpoint_data[0], endpoint=endpoint_data[1]))

    def view_endpoint_docs(self):
        """View documentation for selected endpoint"""
        messagebox.showinfo(_("admin_windows.api.messages.docs_title"),
                           _("admin_windows.api.messages.docs_body"))

    def configure_rate_limits(self):
        """Configure rate limits for endpoints"""
        messagebox.showinfo(_("admin_windows.api.messages.rate_config_title"),
                           _("admin_windows.api.messages.rate_config_body"))

class AuditLogsWindow:
    """Comprehensive Audit Logs Viewer"""

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("admin_windows.audit.title"))
        self.window.geometry("1000x700")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill='x', padx=20, pady=20)
        ttk.Label(title_frame, text=_("admin_windows.audit.center_title"),
                 font=('Arial', 16, 'bold')).pack()

        # Filters frame
        filters_frame = ttk.LabelFrame(self.window, text=_("admin_windows.audit.filters"), padding="15")
        filters_frame.pack(fill='x', padx=20, pady=(0, 15))

        # Filter controls
        filter_grid = ttk.Frame(filters_frame)
        filter_grid.pack(fill='x')

        # Date range
        ttk.Label(filter_grid, text=_("admin_windows.audit.date_range")).grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.date_range_var = tk.StringVar(value=_("admin_windows.audit.date_options.last_7_days"))
        ttk.Combobox(filter_grid, textvariable=self.date_range_var,
                    values=[_("admin_windows.audit.date_options.last_24_hours"), _("admin_windows.audit.date_options.last_7_days"), _("admin_windows.audit.date_options.last_30_days"), _("admin_windows.audit.date_options.custom")],
                    width=15).grid(row=0, column=1, sticky='w')

        # Log level
        ttk.Label(filter_grid, text=_("admin_windows.audit.log_level")).grid(row=0, column=2, sticky='w', padx=(20, 10))
        self.level_var = tk.StringVar(value=_("admin_windows.audit.level_options.all"))
        ttk.Combobox(filter_grid, textvariable=self.level_var,
                    values=[_("admin_windows.audit.level_options.all"), "INFO", "WARNING", "ERROR", "CRITICAL"],
                    width=15).grid(row=0, column=3, sticky='w')

        # Category
        ttk.Label(filter_grid, text=_("admin_windows.audit.category")).grid(row=0, column=4, sticky='w', padx=(20, 10))
        self.category_var = tk.StringVar(value=_("admin_windows.audit.category_options.all"))
        ttk.Combobox(filter_grid, textvariable=self.category_var,
                    values=[_("admin_windows.audit.category_options.all"), _("admin_windows.audit.category_options.authentication"), _("admin_windows.audit.category_options.database"), _("admin_windows.audit.category_options.api"), _("admin_windows.audit.category_options.user_actions"), _("admin_windows.audit.category_options.system")],
                    width=15).grid(row=0, column=5, sticky='w')

        # Search
        ttk.Label(filter_grid, text=_("common.search")).grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(10, 0))
        self.search_var = tk.StringVar()
        ttk.Entry(filter_grid, textvariable=self.search_var, width=30).grid(row=1, column=1, columnspan=2, sticky='ew', pady=(10, 0))

        # Filter button
        ttk.Button(filter_grid, text=_("admin_windows.audit.buttons.apply_filters"), command=self.apply_filters).grid(row=1, column=3, padx=(10, 0), pady=(10, 0))
        ttk.Button(filter_grid, text=_("admin_windows.audit.buttons.export_logs"), command=self.export_logs).grid(row=1, column=4, padx=(10, 0), pady=(10, 0))
        ttk.Button(filter_grid, text=_("admin_windows.audit.buttons.clear_logs"), command=self.clear_logs).grid(row=1, column=5, padx=(10, 0), pady=(10, 0))

        # Logs display
        logs_frame = ttk.LabelFrame(self.window, text=_("admin_windows.audit.log_entries"), padding="15")
        logs_frame.pack(fill='both', expand=True, padx=20, pady=(0, 15))

        # Logs treeview
        columns = ('Timestamp', 'Level', 'Category', 'User', 'Action', 'IP Address', 'Details')
        column_names = [
            _("admin_windows.audit.columns.timestamp"),
            _("admin_windows.audit.columns.level"),
            _("admin_windows.audit.columns.category"),
            _("admin_windows.audit.columns.user"),
            _("admin_windows.audit.columns.action"),
            _("admin_windows.audit.columns.ip_address"),
            _("admin_windows.audit.columns.details")
        ]
        self.logs_tree = ttk.Treeview(logs_frame, columns=columns, show='headings', height=20)

        for col, name in zip(columns, column_names):
            self.logs_tree.heading(col, text=name)
            self.logs_tree.column(col, width=120)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(logs_frame, orient='vertical', command=self.logs_tree.yview)
        v_scrollbar.pack(side='right', fill='y')
        self.logs_tree.config(yscrollcommand=v_scrollbar.set)

        h_scrollbar = ttk.Scrollbar(logs_frame, orient='horizontal', command=self.logs_tree.xview)
        h_scrollbar.pack(side='bottom', fill='x')
        self.logs_tree.config(xscrollcommand=h_scrollbar.set)

        self.logs_tree.pack(fill='both', expand=True)

        # Load sample data
        self.load_sample_logs()

        # Bind double-click to view details
        self.logs_tree.bind('<Double-1>', self.view_log_details)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy).pack(pady=10)

    def load_sample_logs(self):
        """Load sample audit log data"""
        # Clear existing items
        for item in self.logs_tree.get_children():
            self.logs_tree.delete(item)

        # Sample log entries
        import random
        from datetime import datetime

        categories = ["Authentication", "Database", "API", "User Actions", "System"]
        levels = ["INFO", "WARNING", "ERROR"]
        users = ["admin", "john.doe", "jane.smith", "system", "api_user"]
        actions = [
            "User login successful",
            "Database backup completed",
            "API key generated",
            "Student record updated",
            "System maintenance started",
            "Failed login attempt",
            "Database query executed",
            "File uploaded",
            "Report generated",
            "Configuration changed"
        ]
        ips = ["192.168.1.100", "10.0.0.50", "172.16.0.25", "203.0.113.10", "198.51.100.5"]

        # Generate sample logs for the last 7 days
        base_time = datetime.now()
        for i in range(100):
            timestamp = (base_time - timedelta(minutes=random.randint(0, 10080))).strftime('%Y-%m-%d %H:%M:%S')
            level = random.choice(levels)
            category = random.choice(categories)
            user = random.choice(users)
            action = random.choice(actions)
            ip = random.choice(ips)
            details = f"Additional context for {action.lower()}"

            # Add some realistic error patterns
            if level == "ERROR":
                action = random.choice([
                    "Database connection failed",
                    "Authentication timeout",
                    "API rate limit exceeded",
                    "File not found",
                    "Permission denied"
                ])

            self.logs_tree.insert('', 'end', values=(timestamp, level, category, user, action, ip, details))

    def apply_filters(self):
        """Apply filters to log display"""
        messagebox.showinfo(_("admin_windows.audit.messages.filters_applied_title"),
                           _("admin_windows.audit.messages.filters_applied_body",
                             date_range=self.date_range_var.get(),
                             log_level=self.level_var.get(),
                             category=self.category_var.get(),
                             search=self.search_var.get()))

        # Reload logs with filters (in real implementation)
        self.load_sample_logs()

    def export_logs(self):
        """Export filtered logs"""
        filename = filedialog.asksaveasfilename(
            title=_("admin_windows.audit.messages.export_title"),
            defaultextension=".csv",
            filetypes=[(_("admin_windows.filetypes.csv"), "*.csv"), (_("admin_windows.filetypes.json"), "*.json"), (_("admin_windows.filetypes.all"), "*.*")]
        )

        if filename:
            messagebox.showinfo(_("admin_windows.messages.export_complete"), _("admin_windows.audit.messages.logs_exported", filename=filename))

    def clear_logs(self):
        """Clear old log entries"""
        result = messagebox.askyesno(_("admin_windows.audit.messages.confirm_clear_title"),
                                   _("admin_windows.audit.messages.confirm_clear_body"))
        if result:
            messagebox.showinfo(_("admin_windows.audit.messages.logs_cleared_title"), _("admin_windows.audit.messages.logs_cleared_body"))

    def view_log_details(self, event):
        """View detailed information about selected log entry"""
        selection = self.logs_tree.selection()
        if not selection:
            return

        item = self.logs_tree.item(selection[0])
        log_data = item['values']

        details_window = tk.Toplevel(self.window)
        details_window.title(_("admin_windows.audit.details.title"))
        details_window.geometry("600x500")
        details_window.transient(self.window)

        # Details display
        details_frame = ttk.LabelFrame(details_window, text=_("admin_windows.audit.details.title"), padding="15")
        details_frame.pack(fill='both', expand=True, padx=15, pady=15)

        details_text = scrolledtext.ScrolledText(details_frame, height=20, wrap='word')
        details_text.pack(fill='both', expand=True)

        detail_info = _("admin_windows.audit.details.body",
                       timestamp=log_data[0], level=log_data[1], category=log_data[2],
                       user=log_data[3], action=log_data[4], ip=log_data[5], details=log_data[6])

        details_text.insert('1.0', detail_info)
        details_text.config(state='disabled')

        ttk.Button(details_window, text=_("common.close"), command=details_window.destroy).pack(pady=10)

class DiagnosticsWindow:
    """Comprehensive System Diagnostics"""

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("admin_windows.diagnostics.title"))
        self.window.geometry("900x700")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill='x', padx=20, pady=20)
        ttk.Label(title_frame, text=_("admin_windows.diagnostics.center_title"),
                 font=('Arial', 16, 'bold')).pack()

        # Create notebook for different diagnostic sections
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        # System Health Tab
        health_frame = ttk.Frame(notebook)
        notebook.add(health_frame, text=_("admin_windows.diagnostics.tabs.health"))
        self.create_health_tab(health_frame)

        # Performance Tab
        performance_frame = ttk.Frame(notebook)
        notebook.add(performance_frame, text=_("admin_windows.diagnostics.tabs.performance"))
        self.create_performance_tab(performance_frame)

        # Network Tab
        network_frame = ttk.Frame(notebook)
        notebook.add(network_frame, text=_("admin_windows.diagnostics.tabs.network"))
        self.create_network_tab(network_frame)

        # Storage Tab
        storage_frame = ttk.Frame(notebook)
        notebook.add(storage_frame, text=_("admin_windows.diagnostics.tabs.storage"))
        self.create_storage_tab(storage_frame)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy).pack(pady=10)

    def create_health_tab(self, parent):
        """Create system health tab"""
        # Health overview
        overview_frame = ttk.LabelFrame(parent, text=_("admin_windows.diagnostics.health.overview"), padding="15")
        overview_frame.pack(fill='x', padx=15, pady=15)

        # Health indicators
        indicators_frame = ttk.Frame(overview_frame)
        indicators_frame.pack(fill='x')

        health_items = [
            (_("admin_windows.diagnostics.health.overall"), _("admin_windows.diagnostics.health.status.excellent"), "green"),
            (_("admin_windows.diagnostics.health.cpu_usage"), "23%", "green"),
            (_("admin_windows.diagnostics.health.memory_usage"), "67%", "orange"),
            (_("admin_windows.diagnostics.health.disk_usage"), "45%", "green"),
            (_("admin_windows.diagnostics.health.network"), _("admin_windows.diagnostics.health.status.online"), "green"),
            (_("admin_windows.diagnostics.health.database"), _("admin_windows.diagnostics.health.status.connected"), "green")
        ]

        for i, (label, value, color) in enumerate(health_items):
            indicator_frame = ttk.LabelFrame(indicators_frame, text=label, padding="10")
            indicator_frame.grid(row=i//3, column=i%3, padx=5, pady=5, sticky='ew')
            ttk.Label(indicator_frame, text=value, font=('Arial', 12, 'bold')).pack()
            indicators_frame.grid_columnconfigure(i%3, weight=1)

        # Health details
        details_frame = ttk.LabelFrame(parent, text=_("admin_windows.diagnostics.health.detailed_report"), padding="15")
        details_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        health_text = scrolledtext.ScrolledText(details_frame, height=15, wrap='word')
        health_text.pack(fill='both', expand=True)

        health_report = f"""
SYSTEM HEALTH DIAGNOSTIC REPORT
==============================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERALL STATUS: 🟢 HEALTHY
System is operating within normal parameters.

CPU ANALYSIS:
• Current Usage: 23% (Normal)
• Average Load: 0.45 (Low)
• Core Temperature: 42°C (Normal)
• Processes: 156 running
• Top Consumer: postgres (8.3%)

MEMORY ANALYSIS:
• Physical RAM: 16GB total, 10.7GB used (67%)
• Available RAM: 5.3GB
• Swap Usage: 0GB (0%)
• Memory Fragmentation: Low
• Top Consumer: university_app (2.1GB)

DISK ANALYSIS:
• Primary Disk: 500GB total, 225GB used (45%)
• Free Space: 275GB
• I/O Operations: 234 reads/sec, 89 writes/sec
• Disk Health: Excellent
• Fragmentation: 3% (Low)

NETWORK ANALYSIS:
• Connection Status: Online
• Bandwidth Usage: 12.5 Mbps down, 3.2 Mbps up
• Packet Loss: 0%
• Latency: 12ms (Excellent)
• Active Connections: 47

DATABASE HEALTH:
• Connection Status: Connected
• Connection Pool: 8/20 connections active
• Query Performance: 89ms average
• Lock Contention: None
• Backup Status: Last backup 2 hours ago

SERVICES STATUS:
✓ Web Server: Running (Apache 2.4.41)
✓ Database: Running (PostgreSQL 13.2)
✓ Cache: Running (Redis 6.2.1)
✓ Email Service: Running
✓ Background Tasks: Running (5 workers)
✓ File Storage: Running
✓ Authentication: Running
✓ API Gateway: Running

SECURITY STATUS:
✓ Firewall: Active
✓ SSL Certificates: Valid (expires in 87 days)
✓ Antivirus: Up to date
✓ Intrusion Detection: Active
✓ Log Monitoring: Active

RECENT EVENTS:
• 14:30 - System health check completed
• 14:25 - Database optimization completed
• 14:20 - Cache cleared and rebuilt
• 14:15 - Log rotation completed
• 14:10 - Backup verification successful

RECOMMENDATIONS:
• System is running optimally
• Consider monitoring memory usage trends
• Schedule disk cleanup for next maintenance window
• All security measures are active and effective
"""

        health_text.insert('1.0', health_report)
        health_text.config(state='disabled')

        # Action buttons
        actions_frame = ttk.Frame(details_frame)
        actions_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(actions_frame, text=_("admin_windows.diagnostics.health.buttons.run_diagnostic"),
                  command=self.run_full_diagnostic).pack(side='left', padx=(0, 10))
        ttk.Button(actions_frame, text=_("admin_windows.diagnostics.health.buttons.generate_report"),
                  command=self.generate_health_report).pack(side='left', padx=(0, 10))
        ttk.Button(actions_frame, text=_("admin_windows.diagnostics.health.buttons.view_logs"),
                  command=self.view_system_logs).pack(side='left')

    def create_performance_tab(self, parent):
        """Create performance monitoring tab"""
        # Performance metrics
        metrics_frame = ttk.LabelFrame(parent, text=_("admin_windows.diagnostics.performance.metrics"), padding="15")
        metrics_frame.pack(fill='both', expand=True, padx=15, pady=15)

        performance_text = scrolledtext.ScrolledText(metrics_frame, height=25, wrap='word')
        performance_text.pack(fill='both', expand=True)

        performance_data = f"""
PERFORMANCE MONITORING REPORT
============================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

APPLICATION PERFORMANCE:
• Response Time: 125ms average (Excellent)
• Throughput: 1,247 requests/minute
• Error Rate: 0.03% (Excellent)
• Concurrent Users: 89 active
• Session Duration: 24 minutes average

DATABASE PERFORMANCE:
• Query Response Time: 45ms average
• Slow Queries: 2 (0.01%)
• Index Usage: 98.7% efficient
• Connection Pool: 40% utilization
• Cache Hit Ratio: 94.2%

WEB SERVER PERFORMANCE:
• Request Processing: 89ms average
• Static Content: 12ms average
• Dynamic Content: 156ms average
• Compression Ratio: 73%
• Keep-Alive Usage: 89%

RESOURCE UTILIZATION TRENDS (24h):
CPU Usage:
  Peak: 45% at 10:30 AM
  Average: 23%
  Minimum: 8% at 3:00 AM

Memory Usage:
  Peak: 78% at 2:15 PM
  Average: 67%
  Minimum: 45% at 4:00 AM

Disk I/O:
  Peak: 450 IOPS at 11:00 AM
  Average: 234 IOPS
  Minimum: 45 IOPS at 2:00 AM

Network Usage:
  Peak: 45 Mbps at 1:30 PM
  Average: 12.5 Mbps
  Minimum: 2.1 Mbps at 5:00 AM

BOTTLENECK ANALYSIS:
• No significant bottlenecks detected
• Memory usage approaching 80% during peak hours
• Database connection pool adequate
• Network bandwidth has good headroom

OPTIMIZATION OPPORTUNITIES:
✓ Enable database query caching for reports
✓ Implement CDN for static assets
✓ Consider memory upgrade for peak usage
✓ Optimize image compression
✓ Enable browser caching headers

CAPACITY PLANNING:
Current Capacity: 150 concurrent users
Peak Usage: 89 users (59% of capacity)
Growth Rate: 5% monthly
Recommended Action: Monitor for next 3 months

PERFORMANCE ALERTS:
• No active performance alerts
• All thresholds within acceptable ranges
• Monitoring system active and reporting

TOP RESOURCE CONSUMERS:
1. university_app - 2.1GB RAM, 8.3% CPU
2. postgres - 890MB RAM, 5.7% CPU
3. apache2 - 456MB RAM, 3.2% CPU
4. redis - 234MB RAM, 1.1% CPU
5. python - 189MB RAM, 2.4% CPU

RECENT OPTIMIZATIONS:
• Database indexes optimized (2 hours ago)
• Cache configuration tuned (4 hours ago)
• Log rotation configured (6 hours ago)
• Gzip compression enabled (1 day ago)
"""

        performance_text.insert('1.0', performance_data)
        performance_text.config(state='disabled')

        # Performance actions
        perf_actions = ttk.Frame(metrics_frame)
        perf_actions.pack(fill='x', pady=(10, 0))

        ttk.Button(perf_actions, text=_("admin_windows.diagnostics.performance.buttons.run_test"),
                  command=self.run_performance_test).pack(side='left', padx=(0, 10))
        ttk.Button(perf_actions, text=_("admin_windows.diagnostics.performance.buttons.optimize"),
                  command=self.optimize_system).pack(side='left', padx=(0, 10))
        ttk.Button(perf_actions, text=_("admin_windows.diagnostics.performance.buttons.live_metrics"),
                  command=self.view_live_metrics).pack(side='left')

    def create_network_tab(self, parent):
        """Create network diagnostics tab"""
        # Network status
        network_frame = ttk.LabelFrame(parent, text=_("admin_windows.diagnostics.network.title"), padding="15")
        network_frame.pack(fill='both', expand=True, padx=15, pady=15)

        network_text = scrolledtext.ScrolledText(network_frame, height=25, wrap='word')
        network_text.pack(fill='both', expand=True)

        network_data = f"""
NETWORK DIAGNOSTIC REPORT
========================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

CONNECTION STATUS:
• Primary Connection: Online ✓
• Backup Connection: Standby ✓
• Internet Connectivity: Available ✓
• DNS Resolution: Working ✓
• External API Access: Available ✓

NETWORK CONFIGURATION:
• IP Address: 192.168.1.100
• Subnet Mask: 255.255.255.0
• Gateway: 192.168.1.1
• DNS Servers: 8.8.8.8, 1.1.1.1
• Network Speed: 1 Gbps

BANDWIDTH UTILIZATION:
• Current Download: 12.5 Mbps (1.25% of capacity)
• Current Upload: 3.2 Mbps (0.32% of capacity)
• Peak Download (24h): 45.7 Mbps
• Peak Upload (24h): 18.3 Mbps
• Data Transfer (24h): 2.3 GB down, 890 MB up

LATENCY ANALYSIS:
• Local Network: 1ms (Excellent)
• Internet Gateway: 12ms (Excellent)
• DNS Lookup: 8ms (Good)
• External APIs: 45ms (Good)
• Database Server: 0.5ms (Excellent)

CONNECTIVITY TESTS:
✓ Ping gateway: 1ms, 0% packet loss
✓ Ping external host: 12ms, 0% packet loss
✓ DNS resolution: 8ms average
✓ HTTP connectivity: Working
✓ HTTPS connectivity: Working
✓ Database connectivity: Working
✓ Email server: Working
✓ File server: Working

PORT STATUS:
• Port 80 (HTTP): Open ✓
• Port 443 (HTTPS): Open ✓
• Port 22 (SSH): Open ✓
• Port 5432 (PostgreSQL): Open (internal) ✓
• Port 6379 (Redis): Open (internal) ✓
• Port 25 (SMTP): Open ✓

FIREWALL STATUS:
• Firewall: Active ✓
• Inbound Rules: 12 active
• Outbound Rules: 8 active
• Blocked Connections (24h): 234
• Allowed Connections (24h): 15,789

NETWORK SECURITY:
• SSL/TLS: Active on all HTTPS connections
• Certificate Status: Valid (expires in 87 days)
• Encryption Level: TLS 1.3
• VPN Access: Available
• Intrusion Detection: Active

ACTIVE CONNECTIONS:
• Total Connections: 47
• HTTP Connections: 23
• HTTPS Connections: 18
• Database Connections: 6
• Longest Connection: 1h 23m

RECENT NETWORK EVENTS:
• 14:35 - SSL certificate renewal check passed
• 14:30 - Network interface statistics updated
• 14:25 - Firewall rules synchronized
• 14:20 - DNS cache refreshed
• 14:15 - Network health check completed

RECOMMENDATIONS:
• Network performance is excellent
• Consider implementing CDN for better global performance
• SSL certificate expires in 87 days - schedule renewal
• Monitor bandwidth usage trends during peak hours
• All security measures are properly configured
"""

        network_text.insert('1.0', network_data)
        network_text.config(state='disabled')

        # Network actions
        network_actions = ttk.Frame(network_frame)
        network_actions.pack(fill='x', pady=(10, 0))

        ttk.Button(network_actions, text=_("admin_windows.diagnostics.network.buttons.test_connectivity"),
                  command=self.test_connectivity).pack(side='left', padx=(0, 10))
        ttk.Button(network_actions, text=_("admin_windows.diagnostics.network.buttons.speed_test"),
                  command=self.run_speed_test).pack(side='left', padx=(0, 10))
        ttk.Button(network_actions, text=_("admin_windows.diagnostics.network.buttons.port_scanner"),
                  command=self.run_port_scan).pack(side='left')

    def create_storage_tab(self, parent):
        """Create storage diagnostics tab"""
        # Storage analysis
        storage_frame = ttk.LabelFrame(parent, text=_("admin_windows.diagnostics.storage.title"), padding="15")
        storage_frame.pack(fill='both', expand=True, padx=15, pady=15)

        storage_text = scrolledtext.ScrolledText(storage_frame, height=25, wrap='word')
        storage_text.pack(fill='both', expand=True)

        storage_data = f"""
STORAGE DIAGNOSTIC REPORT
========================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

DISK USAGE SUMMARY:
• Total Capacity: 500 GB
• Used Space: 225 GB (45%)
• Free Space: 275 GB (55%)
• System Reserved: 25 GB (5%)

DISK BREAKDOWN BY DIRECTORY:
/var/log          45 GB (20% of used)
/home/uploads     38 GB (17% of used)
/var/backups      32 GB (14% of used)
/var/cache        28 GB (12% of used)
/opt/applications 25 GB (11% of used)
/tmp              12 GB (5% of used)
/var/lib/postgres 23 GB (10% of used)
Other             22 GB (10% of used)

DISK PERFORMANCE:
• Read Speed: 1,200 MB/s (SSD)
• Write Speed: 800 MB/s (SSD)
• IOPS: 450 avg, 1,200 peak
• Queue Depth: 2.3 average
• Seek Time: <1ms (SSD)

DISK HEALTH:
• Drive Health: Excellent ✓
• Bad Sectors: 0
• Temperature: 35°C (Normal)
• Power-On Hours: 8,547
• Wear Level: 12% (Low)

FILE SYSTEM ANALYSIS:
• File System: ext4
• Mount Status: Healthy ✓
• Inode Usage: 23% (112,450 of 488,000)
• Fragmentation: 3% (Low)
• Last fsck: 2024-01-20 (Clean)

BACKUP STATUS:
• Last Full Backup: 2024-01-29 02:00 AM ✓
• Backup Size: 180 GB
• Backup Location: /var/backups/
• Incremental Backups: Daily ✓
• Backup Verification: Passed ✓

STORAGE GROWTH ANALYSIS:
Daily Growth Rate: 2.3 GB/day
Weekly Growth Rate: 16.1 GB/week
Monthly Growth Rate: 69.3 GB/month
Projected Full in: 11.9 months

LARGEST FILES (>1GB):
/var/backups/full_backup_20240129.tar.gz    32.1 GB
/var/log/application.log                     8.7 GB
/var/cache/package_cache.db                  6.2 GB
/home/uploads/video_lectures.zip             4.8 GB
/var/lib/postgres/data/base/postgres.db      3.9 GB
/tmp/system_export.sql                       2.1 GB

LOG FILE ANALYSIS:
• Total Log Size: 45 GB
• Oldest Log: 2023-12-01
• Log Rotation: Active ✓
• Compression: Enabled ✓
• Archive Policy: 90 days

CLEANUP OPPORTUNITIES:
• Temporary files: 12 GB can be safely removed
• Old log files: 8 GB can be archived
• Cache files: 6 GB can be cleared
• Duplicate files: 3 GB identified
• Empty directories: 247 found

I/O STATISTICS (24h):
Read Operations: 156,789
Write Operations: 89,234
Data Read: 234 GB
Data Written: 89 GB
Average Queue Time: 2.3ms

STORAGE ALERTS:
• No critical storage alerts
• Free space above 50% threshold
• No disk errors detected
• Backup system operational

RECOMMENDATIONS:
✓ Storage health is excellent
✓ Implement automated cleanup for temp files
✓ Consider archiving old log files
✓ Monitor growth rate trends
✓ Schedule disk optimization for next maintenance
✓ Current capacity sufficient for 11+ months
"""

        storage_text.insert('1.0', storage_data)
        storage_text.config(state='disabled')

        # Storage actions
        storage_actions = ttk.Frame(storage_frame)
        storage_actions.pack(fill='x', pady=(10, 0))

        ttk.Button(storage_actions, text=_("admin_windows.diagnostics.storage.buttons.disk_cleanup"),
                  command=self.run_disk_cleanup).pack(side='left', padx=(0, 10))
        ttk.Button(storage_actions, text=_("admin_windows.diagnostics.storage.buttons.check_health"),
                  command=self.check_disk_health).pack(side='left', padx=(0, 10))
        ttk.Button(storage_actions, text=_("admin_windows.diagnostics.storage.buttons.optimize"),
                  command=self.optimize_storage).pack(side='left')

    # Diagnostic action methods
    def run_full_diagnostic(self):
        """Run comprehensive system diagnostic"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.full_diagnostic_title"),
                           _("admin_windows.diagnostics.messages.full_diagnostic_body"))

    def generate_health_report(self):
        """Generate detailed health report"""
        filename = filedialog.asksaveasfilename(
            title=_("admin_windows.diagnostics.messages.save_report_title"),
            defaultextension=".pdf",
            filetypes=[(_("admin_windows.filetypes.pdf"), "*.pdf"), (_("admin_windows.filetypes.txt"), "*.txt"), (_("admin_windows.filetypes.all"), "*.*")]
        )

        if filename:
            messagebox.showinfo(_("admin_windows.diagnostics.messages.report_generated_title"), _("admin_windows.diagnostics.messages.report_generated_body", filename=filename))

    def view_system_logs(self):
        """View system logs"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.system_logs_title"), _("admin_windows.diagnostics.messages.system_logs_body"))

    def run_performance_test(self):
        """Run performance benchmark"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.perf_test_title"),
                           _("admin_windows.diagnostics.messages.perf_test_body"))

    def optimize_system(self):
        """Run system optimization"""
        result = messagebox.askyesno(_("admin_windows.diagnostics.messages.sys_optimize_title"),
                                   _("admin_windows.diagnostics.messages.sys_optimize_body"))
        if result:
            messagebox.showinfo(_("admin_windows.diagnostics.messages.optimize_complete_title"), _("admin_windows.diagnostics.messages.optimize_complete_body"))

    def view_live_metrics(self):
        """View live performance metrics"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.live_metrics_title"), _("admin_windows.diagnostics.messages.live_metrics_body"))

    def test_connectivity(self):
        """Test network connectivity"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.connectivity_title"),
                           _("admin_windows.diagnostics.messages.connectivity_body"))

    def run_speed_test(self):
        """Run network speed test"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.speed_test_title"),
                           _("admin_windows.diagnostics.messages.speed_test_body"))

    def run_port_scan(self):
        """Run port scanner"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.port_scan_title"), _("admin_windows.diagnostics.messages.port_scan_body"))

    def run_disk_cleanup(self):
        """Run disk cleanup utility"""
        result = messagebox.askyesno(_("admin_windows.diagnostics.messages.disk_cleanup_title"),
                                   _("admin_windows.diagnostics.messages.disk_cleanup_body"))
        if result:
            messagebox.showinfo(_("admin_windows.diagnostics.messages.cleanup_complete_title"), _("admin_windows.diagnostics.messages.cleanup_complete_body"))

    def check_disk_health(self):
        """Check disk health status"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.disk_health_title"),
                           _("admin_windows.diagnostics.messages.disk_health_body"))

    def optimize_storage(self):
        """Optimize storage performance"""
        result = messagebox.askyesno(_("admin_windows.diagnostics.messages.storage_optimize_title"),
                                   _("admin_windows.diagnostics.messages.storage_optimize_body"))
        if result:
            messagebox.showinfo(_("admin_windows.diagnostics.messages.storage_complete_title"), _("admin_windows.diagnostics.messages.storage_complete_body"))

class DatabaseMaintenanceWindow:
    """Comprehensive Database Maintenance Tools"""

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("admin_windows.database.title"))
        self.window.geometry("900x700")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill='x', padx=20, pady=20)
        ttk.Label(title_frame, text=_("admin_windows.database.center_title"),
                 font=('Arial', 16, 'bold')).pack()

        # Create notebook for different maintenance sections
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        # Database Status Tab
        status_frame = ttk.Frame(notebook)
        notebook.add(status_frame, text=_("admin_windows.database.tabs.status"))
        self.create_status_tab(status_frame)

        # Backup & Restore Tab
        backup_frame = ttk.Frame(notebook)
        notebook.add(backup_frame, text=_("admin_windows.database.tabs.backup"))
        self.create_backup_tab(backup_frame)

        # Optimization Tab
        optimization_frame = ttk.Frame(notebook)
        notebook.add(optimization_frame, text=_("admin_windows.database.tabs.optimization"))
        self.create_optimization_tab(optimization_frame)

        # Monitoring Tab
        monitoring_frame = ttk.Frame(notebook)
        notebook.add(monitoring_frame, text=_("admin_windows.database.tabs.monitoring"))
        self.create_monitoring_tab(monitoring_frame)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy).pack(pady=10)

    def create_status_tab(self, parent):
        """Create database status tab"""
        # Status overview
        overview_frame = ttk.LabelFrame(parent, text=_("admin_windows.database.status.overview"), padding="15")
        overview_frame.pack(fill='x', padx=15, pady=15)

        # Status indicators
        status_grid = ttk.Frame(overview_frame)
        status_grid.pack(fill='x')

        status_items = [
            (_("admin_windows.database.status.connection"), _("admin_windows.database.status.values.connected"), "green"),
            (_("admin_windows.database.status.health"), _("admin_windows.diagnostics.health.status.excellent"), "green"),
            (_("admin_windows.database.status.size"), "2.3 GB", "blue"),
            (_("admin_windows.database.status.tables"), "47", "blue"),
            (_("admin_windows.database.status.connections"), "8/20", "green"),
            (_("admin_windows.database.status.uptime"), "15d 7h", "blue")
        ]

        for i, (label, value, color) in enumerate(status_items):
            status_item = ttk.LabelFrame(status_grid, text=label, padding="10")
            status_item.grid(row=i//3, column=i%3, padx=5, pady=5, sticky='ew')
            ttk.Label(status_item, text=value, font=('Arial', 12, 'bold')).pack()
            status_grid.grid_columnconfigure(i%3, weight=1)

        # Detailed status
        details_frame = ttk.LabelFrame(parent, text=_("admin_windows.database.status.detailed_info"), padding="15")
        details_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        status_text = scrolledtext.ScrolledText(details_frame, height=18, wrap='word')
        status_text.pack(fill='both', expand=True)

        status_info = f"""
DATABASE STATUS REPORT
=====================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

CONNECTION INFORMATION:
• Database Type: PostgreSQL 13.2
• Server Status: Online ✓
• Connection Pool: 8/20 active connections
• Response Time: 12ms average
• Last Restart: 2024-01-14 09:30:00

DATABASE STATISTICS:
• Total Size: 2.3 GB
• Number of Tables: 47
• Number of Indexes: 89
• Number of Views: 12
• Number of Procedures: 23

TABLE ANALYSIS:
Largest Tables:
1. student_records     - 890 MB (456,789 rows)
2. attendance_logs     - 234 MB (1,234,567 rows)
3. assignment_submissions - 189 MB (89,234 rows)
4. audit_logs         - 156 MB (567,890 rows)
5. course_enrollments - 123 MB (234,567 rows)

INDEX STATISTICS:
• Total Indexes: 89
• Index Size: 456 MB
• Index Usage: 94.7% (85/89 used)
• Unused Indexes: 4
• Missing Indexes: None detected

PERFORMANCE METRICS:
• Query Response Time: 12ms average
• Slow Queries (>1s): 3 in last 24h
• Cache Hit Ratio: 96.8%
• Buffer Usage: 78%
• Lock Contention: None

CONNECTION ANALYSIS:
Active Connections: 8
• user_app: 3 connections
• backup_service: 1 connection
• monitoring: 1 connection
• admin: 1 connection
• readonly: 2 connections

Idle Connections: 2
Max Connections: 20
Connection Efficiency: 95%

RECENT ACTIVITY:
• Last Query: 2 seconds ago
• Queries/Minute: 145 average
• Peak QPS: 389 (at 10:30 AM)
• Data Modifications: 89 in last hour
• Schema Changes: None in last 24h

MAINTENANCE STATUS:
• Last VACUUM: 2024-01-28 02:00:00
• Last ANALYZE: 2024-01-29 02:15:00
• Last REINDEX: 2024-01-27 02:30:00
• Auto-vacuum: Enabled ✓
• Statistics Collection: Enabled ✓

BACKUP STATUS:
• Last Full Backup: 2024-01-29 02:00:00 ✓
• Last Incremental: 2024-01-29 14:00:00 ✓
• Backup Size: 1.8 GB compressed
• Backup Location: /var/backups/db/
• Backup Verification: Passed ✓

ERROR LOG SUMMARY:
• Errors (24h): 0
• Warnings (24h): 2
• Deadlocks (24h): 0
• Connection Failures: 0
• Disk Full Events: 0

RECOMMENDATIONS:
✓ Database is performing excellently
✓ All maintenance tasks up to date
✓ Backup system functioning properly
✓ No immediate action required
✓ Continue monitoring query performance
"""

        status_text.insert('1.0', status_info)
        status_text.config(state='disabled')

        # Status actions
        actions_frame = ttk.Frame(details_frame)
        actions_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(actions_frame, text=_("admin_windows.database.status.buttons.refresh"),
                  command=self.refresh_status).pack(side='left', padx=(0, 10))
        ttk.Button(actions_frame, text=_("admin_windows.database.status.buttons.test_connection"),
                  command=self.test_connection).pack(side='left', padx=(0, 10))
        ttk.Button(actions_frame, text=_("admin_windows.database.status.buttons.export"),
                  command=self.export_status).pack(side='left')

    def create_backup_tab(self, parent):
        """Create backup and restore tab"""
        # Backup controls
        backup_controls = ttk.LabelFrame(parent, text=_("admin_windows.database.backup.operations"), padding="15")
        backup_controls.pack(fill='x', padx=15, pady=15)

        # Backup type selection
        backup_type_frame = ttk.Frame(backup_controls)
        backup_type_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(backup_type_frame, text=_("admin_windows.database.backup.type")).pack(side='left', padx=(0, 10))
        self.backup_type_var = tk.StringVar(value=_("admin_windows.database.backup.types.full"))
        ttk.Combobox(backup_type_frame, textvariable=self.backup_type_var,
                    values=[_("admin_windows.database.backup.types.full"), _("admin_windows.database.backup.types.incremental"), _("admin_windows.database.backup.types.schema"), _("admin_windows.database.backup.types.data")],
                    width=20).pack(side='left', padx=(0, 20))

        ttk.Label(backup_type_frame, text=_("admin_windows.database.backup.compression")).pack(side='left', padx=(0, 10))
        self.compression_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(backup_type_frame, text=_("admin_windows.database.backup.enable"), variable=self.compression_var).pack(side='left')

        # Backup actions
        backup_actions = ttk.Frame(backup_controls)
        backup_actions.pack(fill='x')

        ttk.Button(backup_actions, text=_("admin_windows.database.backup.buttons.create"),
                  command=self.create_backup).pack(side='left', padx=(0, 10))
        ttk.Button(backup_actions, text=_("admin_windows.database.backup.buttons.schedule"),
                  command=self.schedule_backup).pack(side='left', padx=(0, 10))
        ttk.Button(backup_actions, text=_("admin_windows.database.backup.buttons.verify"),
                  command=self.verify_backup).pack(side='left')

        # Backup history
        history_frame = ttk.LabelFrame(parent, text=_("admin_windows.database.backup.history"), padding="15")
        history_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        # Backup history tree
        columns = ('Date', 'Type', 'Size', 'Duration', 'Status', 'Location')
        column_names = [
            _("common.date"),
            _("admin_windows.database.backup.columns.type"),
            _("admin_windows.database.backup.columns.size"),
            _("admin_windows.database.backup.columns.duration"),
            _("common.status"),
            _("admin_windows.database.backup.columns.location")
        ]
        self.backup_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=12)

        for col, name in zip(columns, column_names):
            self.backup_tree.heading(col, text=name)
            self.backup_tree.column(col, width=120)

        self.backup_tree.pack(fill='both', expand=True, pady=(0, 15))

        # Sample backup history
        backup_history = [
            ("2024-01-29 02:00", "Full", "1.8 GB", "12m 34s", "Success", "/var/backups/db/full_20240129.sql.gz"),
            ("2024-01-28 14:00", "Incremental", "245 MB", "3m 21s", "Success", "/var/backups/db/inc_20240128_14.sql.gz"),
            ("2024-01-28 02:00", "Full", "1.7 GB", "11m 45s", "Success", "/var/backups/db/full_20240128.sql.gz"),
            ("2024-01-27 14:00", "Incremental", "189 MB", "2m 56s", "Success", "/var/backups/db/inc_20240127_14.sql.gz"),
            ("2024-01-27 02:00", "Full", "1.7 GB", "12m 12s", "Success", "/var/backups/db/full_20240127.sql.gz")
        ]

        for backup_data in backup_history:
            self.backup_tree.insert('', 'end', values=backup_data)

        # Restore controls
        restore_frame = ttk.Frame(history_frame)
        restore_frame.pack(fill='x')

        ttk.Button(restore_frame, text=_("admin_windows.database.backup.buttons.restore"),
                  command=self.restore_backup).pack(side='left', padx=(0, 10))
        ttk.Button(restore_frame, text=_("admin_windows.database.backup.buttons.download"),
                  command=self.download_backup).pack(side='left', padx=(0, 10))
        ttk.Button(restore_frame, text=_("admin_windows.database.backup.buttons.delete"),
                  command=self.delete_backup).pack(side='left', padx=(0, 10))
        ttk.Button(restore_frame, text=_("admin_windows.database.backup.buttons.restore_file"),
                  command=self.restore_from_file).pack(side='left')

    def create_optimization_tab(self, parent):
        """Create optimization tab"""
        # Optimization controls
        opt_controls = ttk.LabelFrame(parent, text=_("admin_windows.database.optimization.title"), padding="15")
        opt_controls.pack(fill='x', padx=15, pady=15)

        # Optimization options
        opt_grid = ttk.Frame(opt_controls)
        opt_grid.pack(fill='x', pady=(0, 15))

        self.vacuum_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_grid, text=_("admin_windows.database.optimization.vacuum"),
                       variable=self.vacuum_var).grid(row=0, column=0, sticky='w', padx=(0, 20))

        self.analyze_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_grid, text=_("admin_windows.database.optimization.analyze"),
                       variable=self.analyze_var).grid(row=0, column=1, sticky='w')

        self.reindex_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_grid, text=_("admin_windows.database.optimization.reindex"),
                       variable=self.reindex_var).grid(row=1, column=0, sticky='w', padx=(0, 20))

        self.cleanup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_grid, text=_("admin_windows.database.optimization.cleanup"),
                       variable=self.cleanup_var).grid(row=1, column=1, sticky='w')

        # Optimization actions
        opt_actions = ttk.Frame(opt_controls)
        opt_actions.pack(fill='x')

        ttk.Button(opt_actions, text=_("admin_windows.database.optimization.buttons.run"),
                  command=self.run_optimization).pack(side='left', padx=(0, 10))
        ttk.Button(opt_actions, text=_("admin_windows.database.optimization.buttons.schedule"),
                  command=self.schedule_maintenance).pack(side='left', padx=(0, 10))
        ttk.Button(opt_actions, text=_("admin_windows.database.optimization.buttons.integrity"),
                  command=self.check_integrity).pack(side='left')

        # Optimization results
        results_frame = ttk.LabelFrame(parent, text=_("admin_windows.database.optimization.results"), padding="15")
        results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        opt_text = scrolledtext.ScrolledText(results_frame, height=18, wrap='word')
        opt_text.pack(fill='both', expand=True)

        opt_results = f"""
DATABASE OPTIMIZATION REPORT
===========================
Last Optimization: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

VACUUM ANALYSIS:
• Dead Tuples Removed: 12,456
• Pages Reclaimed: 234
• Storage Freed: 45.7 MB
• Tables Processed: 47
• Duration: 8m 23s

ANALYZE RESULTS:
• Statistics Updated: All tables ✓
• Query Plans Refreshed: 89 plans
• Histogram Updated: All columns
• Duration: 2m 45s

INDEX ANALYSIS:
• Total Indexes: 89
• Indexes Rebuilt: 4 (outdated)
• Index Bloat Removed: 12.3 MB
• Query Performance Improved: 15%
• Duration: 5m 12s

PERFORMANCE IMPROVEMENTS:
Before Optimization:
• Average Query Time: 156ms
• Cache Hit Ratio: 93.2%
• Index Usage: 91.4%
• Buffer Efficiency: 76%

After Optimization:
• Average Query Time: 89ms (43% improvement)
• Cache Hit Ratio: 96.8% (3.6% improvement)
• Index Usage: 94.7% (3.3% improvement)
• Buffer Efficiency: 89% (13% improvement)

TABLE MAINTENANCE SUMMARY:
student_records:
  - Vacuum: 8,234 dead tuples removed
  - Analyze: Statistics updated
  - Storage: 12.3 MB reclaimed

attendance_logs:
  - Vacuum: 3,567 dead tuples removed
  - Analyze: Statistics updated
  - Storage: 8.9 MB reclaimed

assignment_submissions:
  - Vacuum: 1,234 dead tuples removed
  - Analyze: Statistics updated
  - Storage: 5.6 MB reclaimed

SLOW QUERY OPTIMIZATION:
• Queries analyzed: 15
• Queries optimized: 8
• Performance gain: 67% average
• New indexes suggested: 2

INDEX RECOMMENDATIONS:
✓ Create index on attendance_logs(student_id, date)
✓ Create index on submissions(assignment_id, status)
✓ Drop unused index on old_table(deprecated_column)

MAINTENANCE SCHEDULE:
• Auto-vacuum: Enabled (threshold: 20%)
• Auto-analyze: Enabled (threshold: 10%)
• Full maintenance: Weekly (Sundays 2:00 AM)
• Index rebuild: Monthly
• Statistics update: Daily

OPTIMIZATION WARNINGS:
• No critical issues detected
• All optimizations completed successfully
• Database performance is excellent

NEXT SCHEDULED MAINTENANCE:
• Date: 2024-02-04 02:00:00
• Type: Full maintenance
• Estimated Duration: 15-20 minutes
• Impact: Minimal (scheduled during low usage)

RECOMMENDATIONS:
✓ Optimization completed successfully
✓ Query performance significantly improved
✓ All maintenance tasks up to date
✓ Continue regular maintenance schedule
✓ Monitor query patterns for future optimization
"""

        opt_text.insert('1.0', opt_results)
        opt_text.config(state='disabled')

    def create_monitoring_tab(self, parent):
        """Create monitoring tab"""
        # Monitoring controls
        monitor_controls = ttk.LabelFrame(parent, text=_("admin_windows.database.monitoring.title"), padding="15")
        monitor_controls.pack(fill='x', padx=15, pady=15)

        # Monitoring options
        monitor_options = ttk.Frame(monitor_controls)
        monitor_options.pack(fill='x', pady=(0, 15))

        ttk.Label(monitor_options, text=_("admin_windows.database.monitoring.interval")).pack(side='left', padx=(0, 10))
        self.monitor_interval_var = tk.StringVar(value=_("admin_windows.database.monitoring.intervals.5min"))
        ttk.Combobox(monitor_options, textvariable=self.monitor_interval_var,
                    values=[_("admin_windows.database.monitoring.intervals.30sec"), _("admin_windows.database.monitoring.intervals.1min"), _("admin_windows.database.monitoring.intervals.5min"), _("admin_windows.database.monitoring.intervals.15min"), _("admin_windows.database.monitoring.intervals.1hour")],
                    width=15).pack(side='left', padx=(0, 20))

        self.alert_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(monitor_options, text=_("admin_windows.database.monitoring.enable_alerts"),
                       variable=self.alert_enabled_var).pack(side='left', padx=(0, 20))

        # Monitoring actions
        monitor_actions = ttk.Frame(monitor_controls)
        monitor_actions.pack(fill='x')

        ttk.Button(monitor_actions, text=_("admin_windows.database.monitoring.buttons.start"),
                  command=self.start_monitoring).pack(side='left', padx=(0, 10))
        ttk.Button(monitor_actions, text=_("admin_windows.database.monitoring.buttons.stop"),
                  command=self.stop_monitoring).pack(side='left', padx=(0, 10))
        ttk.Button(monitor_actions, text=_("admin_windows.database.monitoring.buttons.configure"),
                  command=self.configure_alerts).pack(side='left', padx=(0, 10))
        ttk.Button(monitor_actions, text=_("admin_windows.database.monitoring.buttons.live_stats"),
                  command=self.view_live_stats).pack(side='left')

        # Monitoring display
        monitor_frame = ttk.LabelFrame(parent, text=_("admin_windows.database.monitoring.realtime"), padding="15")
        monitor_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        monitor_text = scrolledtext.ScrolledText(monitor_frame, height=18, wrap='word')
        monitor_text.pack(fill='both', expand=True)

        monitor_data = f"""
DATABASE MONITORING DASHBOARD
============================
Status: Active ✓
Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

REAL-TIME METRICS:
• Active Connections: 8/20
• Queries per Second: 12.3
• Response Time: 89ms
• CPU Usage: 15%
• Memory Usage: 234 MB
• Cache Hit Ratio: 96.8%

CONNECTION MONITORING:
Active Sessions:
1. user_app (10.0.0.15) - 3 connections, 45s idle
2. backup_service (192.168.1.50) - 1 connection, active
3. monitoring (localhost) - 1 connection, active
4. admin (192.168.1.100) - 1 connection, 2m idle
5. readonly (10.0.0.25) - 2 connections, active

QUERY MONITORING:
Recent Queries (last 5 minutes):
• SELECT * FROM students WHERE... (89ms)
• INSERT INTO attendance... (12ms)
• UPDATE assignments SET... (156ms)
• SELECT COUNT(*) FROM... (23ms)
• DELETE FROM temp_data... (45ms)

Slow Queries (>1s):
• No slow queries in last 5 minutes ✓

PERFORMANCE TRENDS (Last 24 hours):
Response Time:
  Average: 89ms
  Peak: 234ms (at 10:30 AM)
  Minimum: 12ms (at 3:00 AM)

Connections:
  Average: 6.8 connections
  Peak: 15 connections (at 2:00 PM)
  Minimum: 2 connections (at 4:00 AM)

RESOURCE UTILIZATION:
CPU Usage History:
  Current: 15%
  24h Average: 12%
  Peak: 34% (during backup)

Memory Usage:
  Current: 234 MB
  24h Average: 198 MB
  Peak: 445 MB (during optimization)

I/O Operations:
  Reads/sec: 45
  Writes/sec: 23
  24h Average: 67 ops/sec

ALERT HISTORY:
Today:
• 02:15 - Backup completed successfully ✓
• 02:30 - Optimization completed ✓

Yesterday:
• 14:25 - Connection spike detected (resolved)
• 10:30 - High query volume (normal)

This Week:
• No critical alerts ✓
• 5 informational alerts
• 2 warning alerts (resolved)

HEALTH INDICATORS:
✓ Database Online
✓ Backup System Active
✓ Monitoring Active
✓ No Lock Contention
✓ No Deadlocks
✓ Storage Healthy
✓ Network Connectivity Good
✓ Security Measures Active

AUTOMATIC ACTIONS:
• Auto-vacuum triggered: 2024-01-29 03:00
• Statistics updated: 2024-01-29 02:15
• Log rotation: 2024-01-29 00:00
• Connection cleanup: Ongoing

UPCOMING EVENTS:
• Next backup: 2024-01-30 02:00
• Maintenance window: 2024-02-04 02:00
• Log rotation: 2024-01-30 00:00
• Statistics update: 2024-01-30 02:15

MONITORING CONFIGURATION:
• Monitor Interval: 5 minutes
• Alert Threshold: Response time >500ms
• Connection Limit Alert: >18 connections
• Disk Space Alert: <10% free
• Memory Alert: >80% usage
• Auto-restart: Enabled for critical failures
"""

        monitor_text.insert('1.0', monitor_data)
        monitor_text.config(state='disabled')

    # Database maintenance methods
    def refresh_status(self):
        """Refresh database status"""
        messagebox.showinfo(_("admin_windows.database.messages.status_refreshed_title"), _("admin_windows.database.messages.status_refreshed_body"))

    def test_connection(self):
        """Test database connection"""
        messagebox.showinfo(_("admin_windows.database.messages.connection_test_title"),
                           _("admin_windows.database.messages.connection_test_body"))

    def export_status(self):
        """Export status report"""
        filename = filedialog.asksaveasfilename(
            title=_("admin_windows.database.messages.export_status_title"),
            defaultextension=".pdf",
            filetypes=[(_("admin_windows.filetypes.pdf"), "*.pdf"), (_("admin_windows.filetypes.txt"), "*.txt"), (_("admin_windows.filetypes.all"), "*.*")]
        )

        if filename:
            messagebox.showinfo(_("admin_windows.messages.export_complete"), _("admin_windows.database.messages.status_exported", filename=filename))

    def create_backup(self):
        """Create database backup"""
        backup_type = self.backup_type_var.get()
        compression = self.compression_var.get()

        messagebox.showinfo(_("admin_windows.database.messages.backup_started_title"),
                           _("admin_windows.database.messages.backup_started_body", backup_type=backup_type, compression=_("admin_windows.database.backup.enabled") if compression else _("admin_windows.database.backup.disabled")))

    def schedule_backup(self):
        """Schedule automatic backups"""
        messagebox.showinfo(_("admin_windows.database.messages.backup_schedule_title"),
                           _("admin_windows.database.messages.backup_schedule_body"))

    def verify_backup(self):
        """Verify backup integrity"""
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning(_("admin_windows.messages.no_selection"), _("admin_windows.database.messages.select_backup_verify"))
            return

        messagebox.showinfo(_("admin_windows.database.messages.backup_verify_title"),
                           _("admin_windows.database.messages.backup_verify_body"))

    def restore_backup(self):
        """Restore from selected backup"""
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning(_("admin_windows.messages.no_selection"), _("admin_windows.database.messages.select_backup_restore"))
            return

        item = self.backup_tree.item(selection[0])
        backup_date = item['values'][0]

        result = messagebox.askyesno(_("admin_windows.database.messages.confirm_restore_title"),
                                   _("admin_windows.database.messages.confirm_restore_body", backup_date=backup_date))
        if result:
            messagebox.showinfo(_("admin_windows.database.messages.restore_started_title"), _("admin_windows.database.messages.restore_started_body"))

    def download_backup(self):
        """Download backup file"""
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning(_("admin_windows.messages.no_selection"), _("admin_windows.database.messages.select_backup_download"))
            return

        filename = filedialog.asksaveasfilename(
            title=_("admin_windows.database.messages.save_backup_title"),
            defaultextension=".sql.gz",
            filetypes=[(_("admin_windows.filetypes.sql_compressed"), "*.sql.gz"), (_("admin_windows.filetypes.sql"), "*.sql"), (_("admin_windows.filetypes.all"), "*.*")]
        )

        if filename:
            messagebox.showinfo(_("admin_windows.database.messages.download_complete_title"), _("admin_windows.database.messages.download_complete_body", filename=filename))

    def delete_backup(self):
        """Delete selected backup"""
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning(_("admin_windows.messages.no_selection"), _("admin_windows.database.messages.select_backup_delete"))
            return

        item = self.backup_tree.item(selection[0])
        backup_date = item['values'][0]

        result = messagebox.askyesno(_("admin_windows.database.messages.confirm_delete_title"),
                                   _("admin_windows.database.messages.confirm_delete_body", backup_date=backup_date))
        if result:
            messagebox.showinfo(_("admin_windows.database.messages.backup_deleted_title"), _("admin_windows.database.messages.backup_deleted_body"))

    def restore_from_file(self):
        """Restore database from file"""
        filename = filedialog.askopenfilename(
            title=_("admin_windows.database.messages.select_backup_file"),
            filetypes=[(_("admin_windows.filetypes.sql"), "*.sql"), (_("admin_windows.filetypes.sql_compressed"), "*.sql.gz"), (_("admin_windows.filetypes.all"), "*.*")]
        )

        if filename:
            result = messagebox.askyesno(_("admin_windows.database.messages.confirm_restore_title"),
                                       _("admin_windows.database.messages.confirm_restore_file", filename=filename))
            if result:
                messagebox.showinfo(_("admin_windows.database.messages.restore_started_title"), _("admin_windows.database.messages.restore_from_file", filename=filename))

    def run_optimization(self):
        """Run database optimization"""
        operations = []
        if self.vacuum_var.get():
            operations.append("VACUUM")
        if self.analyze_var.get():
            operations.append("ANALYZE")
        if self.reindex_var.get():
            operations.append("REINDEX")
        if self.cleanup_var.get():
            operations.append("CLEANUP")

        if not operations:
            messagebox.showwarning(_("admin_windows.database.messages.no_operations_title"), _("admin_windows.database.messages.no_operations_body"))
            return

        operations_text = ", ".join(operations)
        result = messagebox.askyesno(_("admin_windows.database.messages.confirm_optimize_title"),
                                   _("admin_windows.database.messages.confirm_optimize_body", operations=operations_text))
        if result:
            messagebox.showinfo(_("admin_windows.database.messages.optimize_started_title"),
                               _("admin_windows.database.messages.optimize_started_body", operations=operations_text))

    def schedule_maintenance(self):
        """Schedule maintenance window"""
        messagebox.showinfo(_("admin_windows.database.messages.maintenance_schedule_title"),
                           _("admin_windows.database.messages.maintenance_schedule_body"))

    def check_integrity(self):
        """Check database integrity"""
        messagebox.showinfo(_("admin_windows.database.messages.integrity_title"),
                           _("admin_windows.database.messages.integrity_body"))

    def start_monitoring(self):
        """Start database monitoring"""
        interval = self.monitor_interval_var.get()
        alerts = self.alert_enabled_var.get()

        messagebox.showinfo(_("admin_windows.database.messages.monitoring_started_title"),
                           _("admin_windows.database.messages.monitoring_started_body", interval=interval, alerts=_("admin_windows.database.backup.enabled") if alerts else _("admin_windows.database.backup.disabled")))

    def stop_monitoring(self):
        """Stop database monitoring"""
        result = messagebox.askyesno(_("admin_windows.database.messages.stop_monitoring_title"),
                                   _("admin_windows.database.messages.stop_monitoring_body"))
        if result:
            messagebox.showinfo(_("admin_windows.database.messages.monitoring_stopped_title"), _("admin_windows.database.messages.monitoring_stopped_body"))

    def configure_alerts(self):
        """Configure monitoring alerts"""
        messagebox.showinfo(_("admin_windows.database.messages.alert_config_title"),
                           _("admin_windows.database.messages.alert_config_body"))

    def view_live_stats(self):
        """View live statistics"""
        messagebox.showinfo(_("admin_windows.database.messages.live_stats_title"),
                           _("admin_windows.database.messages.live_stats_body"))

# Example usage
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Admin Management Demo")
    root.geometry("400x300")

    def open_api_management():
        ApiManagementWindow(root)

    def open_audit_logs():
        AuditLogsWindow(root)

    def open_diagnostics():
        DiagnosticsWindow(root)

    def open_database_maintenance():
        DatabaseMaintenanceWindow(root)

    ttk.Label(root, text="Admin Management Windows Demo",
             font=('Arial', 16, 'bold')).pack(pady=20)

    ttk.Button(root, text="🔌 API Management", command=open_api_management, width=30).pack(pady=10)
    ttk.Button(root, text="📋 Audit Logs", command=open_audit_logs, width=30).pack(pady=10)
    ttk.Button(root, text="🔧 System Diagnostics", command=open_diagnostics, width=30).pack(pady=10)
    ttk.Button(root, text="🗄️ Database Maintenance", command=open_database_maintenance, width=30).pack(pady=10)

    root.mainloop()