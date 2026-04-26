"""Reports tab mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk

from education_system.university_system.modules.shared.utils.i18n import get_text as _


class ReportsMixin:
    """Reports tab - embeds the Finance Reporting GUI inline."""

    def create_reports_tab(self):
        """Create reports tab — embed Finance Reporting GUI in the content area."""
        reports_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['reports'] = reports_frame
        self._finance_reporting_gui = None

        # Lazy build: only instantiate the reporting GUI the first time the tab
        # is shown, to avoid paying the cost (and DB hits) on every Finance GUI
        # launch when the user never visits Reports.
        reports_frame.bind('<Map>', self._on_reports_tab_shown, add='+')

    def _on_reports_tab_shown(self, _event):
        if getattr(self, '_finance_reporting_gui', None) is not None:
            return
        reports_frame = self.tab_frames.get('reports')
        if reports_frame is None:
            return
        try:
            from education_system.university_system.modules.domain.finance.gui.finance_reporting.main import (
                FinancialManagementGUI,
            )
            host = ttk.Frame(reports_frame)
            host.pack(fill='both', expand=True)
            auth = getattr(self, 'auth', None)
            self._finance_reporting_gui = FinancialManagementGUI(
                self.root, auth_instance=auth, parent_container=host,
            )
        except Exception as e:
            tk.Label(
                reports_frame,
                text=_("finance_gui.reports_tab.title") + f"\n\n{e}",
                font=('Arial', 11),
                bg='white',
                fg='#b00',
                justify='left',
            ).pack(padx=20, pady=20, anchor='nw')
