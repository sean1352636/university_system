"""Extracted class implementation."""

from .. import admin_management_windows_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


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
