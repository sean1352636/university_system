"""Forecasting and projections mixin for LayoutManager.

The arithmetic lives in ``domain/reporting/forecast_projections`` and is
shared with the Finance CLI (``interfaces/cli/forecasting``); this mixin only
draws the tab and routes button presses.
"""
from education_system.systems.university.shell.gui import report_view as _rv

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

from education_system.systems.university.domains.finance.domain.reporting import (
    forecast_projections as _fp,
)
from education_system.systems.university.infrastructure.i18n import get_text as _


class ForecastingMixin:
    """Financial forecasting: generate, revenue/expense projections, refresh."""

    def create_forecasting_tab(self):
        """Create financial forecasting tab"""
        forecasting_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['forecasting'] = forecasting_frame

        # Title
        title_label = tk.Label(forecasting_frame, text=_("finance_gui.forecasting_tab.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(forecasting_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.forecasting_tab.generate_forecast"), command=self._generate_forecast,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.forecasting_tab.revenue_projection"), command=self._revenue_projection,
                 bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.forecasting_tab.expense_projection"), command=self._expense_projection,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.refresh"), command=self._refresh_forecasting,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='right', padx=5)

        # Stats frame
        stats_frame = tk.LabelFrame(forecasting_frame, text=_("finance_gui.forecasting_tab.forecast_summary"), font=('Arial', 12, 'bold'), bg='white')
        stats_frame.pack(fill='x', padx=10, pady=10)

        stats_container = tk.Frame(stats_frame, bg='white')
        stats_container.pack(fill='x', padx=10, pady=10)

        self._create_forecast_stat_card(stats_container, _("finance_gui.forecasting_tab.projected_revenue_6mo"), _("finance_gui.messages.loading"), self.colors['success'], 0, 0)
        self._create_forecast_stat_card(stats_container, _("finance_gui.forecasting_tab.projected_expenses_6mo"), _("finance_gui.messages.loading"), self.colors['danger'], 0, 1)
        self._create_forecast_stat_card(stats_container, _("finance_gui.forecasting_tab.expected_collections"), _("finance_gui.messages.loading"), self.colors['warning'], 0, 2)
        self._create_forecast_stat_card(stats_container, _("finance_gui.forecasting_tab.net_projection"), _("finance_gui.messages.loading"), self.colors['info'], 0, 3)

        # Analysis text area
        analysis_frame = tk.LabelFrame(forecasting_frame, text=_("finance_gui.forecasting_tab.forecast_analysis"), font=('Arial', 12, 'bold'), bg='white')
        analysis_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.forecast_text = ScrolledText(analysis_frame, height=15, width=80, wrap=tk.WORD)
        self.forecast_text.pack(fill='both', expand=True, padx=10, pady=10)

        # Load initial data
        self.root.after(100, self._refresh_forecasting)

    def _create_forecast_stat_card(self, parent, title, value, color, row, col):
        """Create a forecast statistics card"""
        card = tk.Frame(parent, bg=color, relief='raised', bd=2)
        card.grid(row=row, column=col, padx=5, pady=5, sticky='ew')
        parent.grid_columnconfigure(col, weight=1)

        tk.Label(card, text=title, bg=color, fg='white', font=('Arial', 9, 'bold')).pack(pady=5)
        value_label = tk.Label(card, text=value, bg=color, fg='white', font=('Arial', 14, 'bold'))
        value_label.pack(pady=5)
        setattr(self, f"forecast_stat_{col}", value_label)

    def _generate_forecast(self):
        """Generate comprehensive financial forecast"""
        try:
            forecast_text = _fp.generate_forecast_text(forecast_months=6)

            self.forecast_text.delete('1.0', tk.END)
            self.forecast_text.insert('1.0', forecast_text)

            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.forecasting_tab.forecast_success"))
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.forecasting_tab.forecast_failed", error=str(e)))

    def _show_report_window(self, title, report):
        """Display a read-only text report in a child window."""
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("900x700")
        window.transient(self.root)

        text_widget = _rv.TextReportView(window, font=('Courier', 10), wrap=tk.WORD)
        text_widget.pack(fill='both', expand=True, padx=10, pady=10)
        text_widget.insert('1.0', report)
        text_widget.config(state='disabled')

        ttk.Button(window, text=_("finance_gui.buttons.close"), command=window.destroy).pack(pady=10)

    def _revenue_projection(self):
        """Generate revenue projection with database analysis"""
        try:
            self._show_report_window(
                _("finance_gui.forecasting_tab.revenue_projection_title"),
                _fp.revenue_projection_report(),
            )
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.forecasting_tab.revenue_projection_failed", error=str(e)))

    def _expense_projection(self):
        """Generate expense projection with database analysis"""
        try:
            self._show_report_window(
                _("finance_gui.forecasting_tab.expense_projection_title"),
                _fp.expense_projection_report(),
            )
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.forecasting_tab.expense_projection_failed", error=str(e)))

    def _refresh_forecasting(self):
        """Refresh forecasting data"""
        try:
            summary = _fp.forecast_summary(horizon_months=6)

            # Update UI
            values = (
                summary['projected_revenue'],
                summary['projected_expenses'],
                summary['expected_collections'],
                summary['net_projection'],
            )
            for col, value in enumerate(values):
                label = getattr(self, f"forecast_stat_{col}", None)
                if label is not None:
                    label.config(text=f"£{value:,.2f}")

            # Update analysis
            analysis = _fp.forecast_summary_text(summary)
            analysis += "\n\nClick 'Generate Forecast' for detailed analysis."

            self.forecast_text.delete('1.0', tk.END)
            self.forecast_text.insert('1.0', analysis)

        except Exception as e:
            print(f"Error refreshing forecasting: {e}")
