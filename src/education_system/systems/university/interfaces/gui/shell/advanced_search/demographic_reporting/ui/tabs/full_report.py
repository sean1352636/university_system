"""Extracted demographic-reporting behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from ... import *

class AdvancedUiTabsFullReportMixin:
    def _create_full_report_tab(self):
        """Create full report tab"""
        ttk.Label(
            self.full_report_frame,
            text=_t('gui.shell.advanced_search.demographic_reporting.ui.tabs.full_report.labels.complete_demographic_report', default="Complete Demographic Report"),
            style='SectionTitle.TLabel'
        ).pack(anchor='w', pady=(0, 10))

        # Full report text area
        text_frame = ttk.Frame(self.full_report_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        y_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        x_scroll = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL)

        self.full_report_text = tk.Text(
            text_frame,
            wrap=tk.NONE,
            font=('Courier', 9),
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set
        )

        y_scroll.config(command=self.full_report_text.yview)
        x_scroll.config(command=self.full_report_text.xview)

        self.full_report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

    def _update_full_report(self):
        """Update full report tab"""
        self.full_report_text.delete(1.0, tk.END)
        report = self._generate_report_text()
        self.full_report_text.insert(tk.END, report)
