"""Forecasting and projections mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.core.i18n import get_text as _


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
            conn = get_connection()
            cursor = conn.cursor()

            # Calculate historical averages
            cursor.execute('''
                SELECT
                    AVG(monthly_revenue) as avg_revenue,
                    AVG(monthly_fees) as avg_fees
                FROM (
                    SELECT
                        strftime('%Y-%m', created_at) as month,
                        SUM(amount) as monthly_revenue,
                        COUNT(*) as monthly_fees
                    FROM payments
                    WHERE created_at >= date('now', '-12 months')
                    GROUP BY month
                )
            ''')
            result = cursor.fetchone()
            avg_revenue = result[0] if result[0] else 0

            # Project forward
            forecast_months = 6
            projected_revenue = avg_revenue * forecast_months

            conn.close()

            forecast_text = f"Financial Forecast Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            forecast_text += "=" * 70 + "\n\n"
            forecast_text += f"Forecast Period: {forecast_months} months\n"
            forecast_text += "Based on: 12 months historical data\n\n"
            forecast_text += f"Projected Revenue: \u00a3{projected_revenue:,.2f}\n"
            forecast_text += f"Average Monthly Revenue: \u00a3{avg_revenue:,.2f}\n\n"
            forecast_text += "Assumptions:\n"
            forecast_text += "- Student enrollment remains stable\n"
            forecast_text += "- Fee structure unchanged\n"
            forecast_text += "- Collection rate at historical average\n\n"
            forecast_text += "Recommendations:\n"
            forecast_text += "- Monitor actual vs. forecast monthly\n"
            forecast_text += "- Adjust for seasonal variations\n"
            forecast_text += "- Review collection strategies\n"

            self.forecast_text.delete('1.0', tk.END)
            self.forecast_text.insert('1.0', forecast_text)

            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.forecasting_tab.forecast_success"))
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.forecasting_tab.forecast_failed", error=str(e)))

    def _revenue_projection(self):
        """Generate revenue projection with database analysis"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get historical revenue data (last 12 months)
            cursor.execute('''
                SELECT strftime('%Y-%m', payment_date) as month,
                       SUM(amount) as total_revenue
                FROM payments
                WHERE status = 'completed'
                  AND payment_date >= date('now', '-12 months')
                GROUP BY month
                ORDER BY month
            ''')
            revenue_data = cursor.fetchall()

            # Calculate projection
            report = "=" * 80 + "\n"
            report += "REVENUE PROJECTION ANALYSIS\n"
            report += "=" * 80 + "\n\n"
            report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            if not revenue_data:
                report += "No historical revenue data available for projection.\n"
            else:
                report += "HISTORICAL REVENUE (Last 12 Months):\n"
                report += "-" * 80 + "\n"
                report += f"{'Month':<15} {'Revenue':>20}\n"
                report += "-" * 80 + "\n"

                total_revenue = 0
                for month, revenue in revenue_data:
                    revenue = float(revenue or 0)
                    total_revenue += revenue
                    report += f"{month:<15} \u00a3{revenue:>18,.2f}\n"

                avg_monthly = total_revenue / len(revenue_data) if revenue_data else 0

                report += "-" * 80 + "\n"
                report += f"{'Total Revenue':<15} \u00a3{total_revenue:>18,.2f}\n"
                report += f"{'Average/Month':<15} \u00a3{avg_monthly:>18,.2f}\n\n"

                # Projection (using simple moving average)
                report += "REVENUE PROJECTIONS:\n"
                report += "-" * 80 + "\n"

                # Get last 3 months for trend
                recent_months = revenue_data[-3:] if len(revenue_data) >= 3 else revenue_data
                recent_total = sum(float(r[1] or 0) for r in recent_months)
                recent_avg = recent_total / len(recent_months) if recent_months else 0

                # Calculate growth rate
                if len(revenue_data) >= 6:
                    first_half = sum(float(r[1] or 0) for r in revenue_data[:3])
                    second_half = sum(float(r[1] or 0) for r in revenue_data[-3:])
                    growth_rate = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
                    report += f"Growth Trend: {growth_rate:+.2f}%\n\n"
                else:
                    growth_rate = 0

                # Project next 3, 6, 12 months
                proj_3_months = recent_avg * 3
                proj_6_months = recent_avg * 6
                proj_12_months = recent_avg * 12

                # Apply growth factor
                growth_factor = 1 + (growth_rate / 100)
                if growth_rate != 0:
                    proj_3_months *= growth_factor
                    proj_6_months *= growth_factor ** 0.5
                    proj_12_months *= growth_factor ** 0.25

                report += f"Next 3 Months:  \u00a3{proj_3_months:,.2f}\n"
                report += f"Next 6 Months:  \u00a3{proj_6_months:,.2f}\n"
                report += f"Next 12 Months: \u00a3{proj_12_months:,.2f}\n\n"

                report += "Note: Projections based on historical trends and simple moving averages.\n"

            conn.close()

            # Display in window
            window = tk.Toplevel(self.root)
            window.title(_("finance_gui.forecasting_tab.revenue_projection_title"))
            window.geometry("900x700")
            window.transient(self.root)

            text_widget = ScrolledText(window, font=('Courier', 10), wrap=tk.WORD)
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', report)
            text_widget.config(state='disabled')

            ttk.Button(window, text=_("finance_gui.buttons.close"), command=window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.forecasting_tab.revenue_projection_failed", error=str(e)))

    def _expense_projection(self):
        """Generate expense projection with database analysis"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # `purchase_orders` is owned by the restaurant inventory
            # module (modules/domain/commerce/.../inventory/purchase_orders.py)
            # which has a 15-column schema with supplier_id, po_number,
            # tax_amount, etc. Finance forecasting needs a different,
            # smaller shape for its own department-level expense
            # projections, so we use a renamed table here to avoid
            # clobbering the restaurant schema on a fresh DB.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS finance_purchase_orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_date TEXT,
                    total_amount REAL,
                    status TEXT DEFAULT 'pending',
                    vendor TEXT,
                    description TEXT,
                    department TEXT,
                    approved_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

            # Get historical expense data (last 12 months)
            cursor.execute('''
                SELECT strftime('%Y-%m', order_date) as month,
                       SUM(total_amount) as total_expense
                FROM finance_purchase_orders
                WHERE status IN ('approved', 'completed', 'paid')
                  AND order_date >= date('now', '-12 months')
                GROUP BY month
                ORDER BY month
            ''')
            expense_data = cursor.fetchall()

            # Calculate projection
            report = "=" * 80 + "\n"
            report += "EXPENSE PROJECTION ANALYSIS\n"
            report += "=" * 80 + "\n\n"
            report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            if not expense_data:
                report += "No historical expense data available for projection.\n"
            else:
                report += "HISTORICAL EXPENSES (Last 12 Months):\n"
                report += "-" * 80 + "\n"
                report += f"{'Month':<15} {'Expenses':>20}\n"
                report += "-" * 80 + "\n"

                total_expense = 0
                for month, expense in expense_data:
                    expense = float(expense or 0)
                    total_expense += expense
                    report += f"{month:<15} \u00a3{expense:>18,.2f}\n"

                avg_monthly = total_expense / len(expense_data) if expense_data else 0

                report += "-" * 80 + "\n"
                report += f"{'Total Expenses':<15} \u00a3{total_expense:>18,.2f}\n"
                report += f"{'Average/Month':<15} \u00a3{avg_monthly:>18,.2f}\n\n"

                # Projection (using simple moving average)
                report += "EXPENSE PROJECTIONS:\n"
                report += "-" * 80 + "\n"

                # Get last 3 months for trend
                recent_months = expense_data[-3:] if len(expense_data) >= 3 else expense_data
                recent_total = sum(float(e[1] or 0) for e in recent_months)
                recent_avg = recent_total / len(recent_months) if recent_months else 0

                # Calculate growth rate
                if len(expense_data) >= 6:
                    first_half = sum(float(e[1] or 0) for e in expense_data[:3])
                    second_half = sum(float(e[1] or 0) for e in expense_data[-3:])
                    growth_rate = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
                    report += f"Growth Trend: {growth_rate:+.2f}%\n\n"
                else:
                    growth_rate = 0

                # Project next 3, 6, 12 months
                proj_3_months = recent_avg * 3
                proj_6_months = recent_avg * 6
                proj_12_months = recent_avg * 12

                # Apply growth factor
                growth_factor = 1 + (growth_rate / 100)
                if growth_rate != 0:
                    proj_3_months *= growth_factor
                    proj_6_months *= growth_factor ** 0.5
                    proj_12_months *= growth_factor ** 0.25

                report += f"Next 3 Months:  \u00a3{proj_3_months:,.2f}\n"
                report += f"Next 6 Months:  \u00a3{proj_6_months:,.2f}\n"
                report += f"Next 12 Months: \u00a3{proj_12_months:,.2f}\n\n"

                report += "Note: Projections based on historical trends and simple moving averages.\n"

            conn.close()

            # Display in window
            window = tk.Toplevel(self.root)
            window.title(_("finance_gui.forecasting_tab.expense_projection_title"))
            window.geometry("900x700")
            window.transient(self.root)

            text_widget = ScrolledText(window, font=('Courier', 10), wrap=tk.WORD)
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', report)
            text_widget.config(state='disabled')

            ttk.Button(window, text=_("finance_gui.buttons.close"), command=window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.forecasting_tab.expense_projection_failed", error=str(e)))

    def _refresh_forecasting(self):
        """Refresh forecasting data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Projected revenue (next 6 months based on historical average)
            cursor.execute('''
                SELECT AVG(monthly_total) * 6 as projected_revenue
                FROM (
                    SELECT strftime('%Y-%m', created_at) as month, SUM(amount) as monthly_total
                    FROM payments
                    WHERE created_at >= date('now', '-12 months')
                    GROUP BY month
                )
            ''')
            result = cursor.fetchone()
            projected_revenue = result[0] if result and result[0] else 0

            # Expected collections
            cursor.execute('''
                SELECT SUM(total_debt - amount_collected) as expected_collections
                FROM collection_cases
                WHERE case_status IN ('new', 'assigned', 'in_progress')
            ''')
            result = cursor.fetchone()
            expected_collections = result[0] if result and result[0] else 0

            conn.close()

            # Update UI
            projected_expenses = projected_revenue * 0.7  # Estimate
            net_projection = projected_revenue - projected_expenses

            if hasattr(self, 'forecast_stat_0'):
                self.forecast_stat_0.config(text=f"\u00a3{projected_revenue:,.2f}")
            if hasattr(self, 'forecast_stat_1'):
                self.forecast_stat_1.config(text=f"\u00a3{projected_expenses:,.2f}")
            if hasattr(self, 'forecast_stat_2'):
                self.forecast_stat_2.config(text=f"\u00a3{expected_collections:,.2f}")
            if hasattr(self, 'forecast_stat_3'):
                self.forecast_stat_3.config(text=f"\u00a3{net_projection:,.2f}")

            # Update analysis
            analysis = f"Forecasting Data Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            analysis += "=" * 70 + "\n\n"
            analysis += f"6-Month Revenue Projection: \u00a3{projected_revenue:,.2f}\n"
            analysis += f"6-Month Expense Projection: \u00a3{projected_expenses:,.2f}\n"
            analysis += f"Expected Collections: \u00a3{expected_collections:,.2f}\n"
            analysis += f"Net Projection: \u00a3{net_projection:,.2f}\n\n"
            analysis += "Click 'Generate Forecast' for detailed analysis."

            self.forecast_text.delete('1.0', tk.END)
            self.forecast_text.insert('1.0', analysis)

        except Exception as e:
            print(f"Error refreshing forecasting: {e}")
