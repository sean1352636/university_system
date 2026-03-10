"""Reports tab mixin for LayoutManager."""

import tkinter as tk
from tkinter.scrolledtext import ScrolledText

from education_system.university_system.modules.domain.finance.gui.finance_reporting import launch_financial_gui
from education_system.university_system.modules.shared.utils.i18n import get_text as _


class ReportsMixin:
    """Reports tab - redirects to Finance Reporting GUI."""

    def create_reports_tab(self):
        """Create reports tab - Redirects to Finance Reporting GUI"""
        reports_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['reports'] = reports_frame

        # Title
        title_label = tk.Label(
            reports_frame,
            text=_("finance_gui.reports_tab.title"),
            font=('Arial', 18, 'bold'),
            bg='white',
            fg=self.colors['primary']
        )
        title_label.pack(pady=20)

        # Description
        desc_label = tk.Label(
            reports_frame,
            text=_("finance_gui.tabs.reports.description"),
            font=('Arial', 11),
            bg='white',
            fg='#555'
        )
        desc_label.pack(pady=(0, 30))

        # Launch button
        launch_btn = tk.Button(
            reports_frame,
            text=_("finance_gui.reports_tab.open_reporting"),
            command=lambda: launch_financial_gui(self.root),
            font=('Arial', 12, 'bold'),
            bg=self.colors['success'],
            fg='white',
            padx=30,
            pady=15
        )
        launch_btn.pack(pady=10)

        # Info text
        info_text = ScrolledText(reports_frame, height=15, width=80, font=('Arial', 10), wrap='word')
        info_text.pack(padx=20, pady=20, fill='both', expand=True)

        info_content = _("finance_gui.reports_tab.info_content")
        info_text.insert('1.0', info_content)
        info_text.config(state='disabled')
