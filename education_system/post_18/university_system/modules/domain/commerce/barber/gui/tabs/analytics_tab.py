"""Barber Shop GUI - Analytics tab creation."""

from education_system.post_18.university_system.modules.domain.commerce.barber.gui.common import tk, ttk


class AnalyticsTabMixin:
    """Mixin that creates the analytics tab."""

    def create_analytics_tab(self):
        """Create the analytics tab."""
        analytics_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(analytics_frame, text="Analytics")

        # Dashboard summary
        dashboard_frame = ttk.LabelFrame(analytics_frame, text="Dashboard", padding="10")
        dashboard_frame.pack(fill=tk.X, pady=(0, 10))

        # Summary metrics
        metrics_frame = ttk.Frame(dashboard_frame)
        metrics_frame.pack(fill=tk.X)

        self.metric_appointments = ttk.Label(metrics_frame, text="Today's Appointments: 0", font=('Helvetica', 10, 'bold'))
        self.metric_appointments.pack(side=tk.LEFT, padx=20)

        self.metric_revenue = ttk.Label(metrics_frame, text="This Week's Revenue: £0.00", font=('Helvetica', 10, 'bold'))
        self.metric_revenue.pack(side=tk.LEFT, padx=20)

        self.metric_customers = ttk.Label(metrics_frame, text="New Customers: 0", font=('Helvetica', 10, 'bold'))
        self.metric_customers.pack(side=tk.LEFT, padx=20)

        ttk.Button(dashboard_frame, text="Show Full Dashboard", command=self.show_dashboard).pack(pady=10)

        # Reports section
        reports_frame = ttk.LabelFrame(analytics_frame, text="Analytics Reports", padding="10")
        reports_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Report buttons
        btn_frame = ttk.Frame(reports_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="Peak Hours Report", command=self.generate_peak_hours_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Customer Retention", command=self.customer_retention_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Export PDF", command=self.export_report_pdf).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Schedule Reports", command=self.schedule_automated_reports).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="View Audit Log", command=self.view_audit_log).pack(side=tk.LEFT, padx=5)

        # Report output
        self.analytics_text = tk.Text(reports_frame, wrap=tk.WORD, height=20)
        scrollbar = ttk.Scrollbar(reports_frame, orient=tk.VERTICAL, command=self.analytics_text.yview)
        self.analytics_text.configure(yscrollcommand=scrollbar.set)

        self.analytics_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
