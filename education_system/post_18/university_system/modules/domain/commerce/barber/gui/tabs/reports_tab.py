"""Barber Shop GUI - Reports tab creation."""

from education_system.post_18.university_system.modules.domain.commerce.barber.gui.common import (
    tk, ttk, datetime, timedelta, _t,
)


class ReportsTabMixin:
    """Mixin that creates the reports tab."""

    def create_reports_tab(self):
        """Create the reports tab."""
        reports_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(reports_frame, text=_t("barber.tabs.reports"))

        # Report options
        options_frame = ttk.LabelFrame(reports_frame, text=_t("barber.labels.report_options"), padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(options_frame, text=_t("barber.labels.date_from") + ":").pack(side=tk.LEFT)
        self.report_from_var = tk.StringVar(value=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=self.report_from_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(options_frame, text=_t("barber.labels.date_to") + ":").pack(side=tk.LEFT)
        self.report_to_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=self.report_to_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Button(options_frame, text=_t("barber.btn.generate_report"),
                  command=self.generate_admin_report).pack(side=tk.LEFT, padx=20)
        ttk.Button(options_frame, text=_t("barber.btn.email_report"),
                  command=self.email_admin_report).pack(side=tk.LEFT, padx=5)

        # Report display
        report_display = ttk.LabelFrame(reports_frame, text=_t("barber.labels.report_output"), padding="5")
        report_display.pack(fill=tk.BOTH, expand=True)

        self.report_text = tk.Text(report_display, wrap=tk.WORD, height=25)
        scrollbar = ttk.Scrollbar(report_display, orient=tk.VERTICAL, command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=scrollbar.set)

        self.report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
