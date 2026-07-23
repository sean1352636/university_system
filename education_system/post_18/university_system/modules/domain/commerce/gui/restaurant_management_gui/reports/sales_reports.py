from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from education_system.post_18.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Import finance integration for student finance account payments
try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Import custom exceptions for proper error handling
from education_system.post_18.university_system.core.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    QueryError,
    ValidationError,
    InvalidInputError
)

# Attempt to import the enhanced restaurant DB initializer from the CLI version.
# If available, calling this will create the full set of tables defined in
# services/restaurant_management.py. Alias the import to avoid naming
# conflicts with this module's own init_db function.
try:
    from education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management import init_db as init_enhanced_restaurant_db
except ImportError:
    init_enhanced_restaurant_db = None

# Database configuration
# Always point to the central student_records.db in refactored/db_files.
try:
    from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH as DATABASE_FILE
except ImportError:
    # Fallback to local file if refactored.database.db is unavailable
    DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import get_db_connection from main_gui
from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui.core.main_gui import get_db_connection


def show_report_window(self, title, report_content):
    """
    Display a report in a new window with export and email buttons.
    Args:
        title: Window title and report name
        report_content: The text content of the report
    """
    # Create report window
    report_window = tk.Toplevel(self.root)
    report_window.title(title)
    report_window.geometry("900x700")
    report_window.transient(self.root)
    report_window.grab_set()
    main_frame = ttk.Frame(report_window, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text=title, font=('Arial', 14, 'bold')).pack(pady=10)
    # Report display area
    report_frame = ttk.LabelFrame(main_frame, text=_t("commerce.reports.report"), padding=10)
    report_frame.pack(fill='both', expand=True, pady=10)
    report_text = ScrolledText(report_frame, height=25, width=100, font=('Courier', 9))
    report_text.pack(fill='both', expand=True)
    report_text.insert('1.0', report_content)
    report_text.config(state='disabled')  # Make read-only
    # Buttons frame
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)
    def export_as_txt():
        """Export report to a text file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Clean title for filename
            clean_title = title.replace(' ', '_').replace('/', '_').replace('\\', '_')
            filename = f"{clean_title}_{timestamp}.txt"
            filepath = os.path.join(os.getcwd(), filename)
            with open(filepath, 'w') as f:
                f.write(report_content)
            messagebox.showinfo(_t("commerce.reports.export_success"),
                              _t("commerce.reports.export_success_message", filename=filename, filepath=filepath))
        except (OSError, IOError) as e:
            messagebox.showerror(_t("commerce.reports.export_error"), _t("commerce.reports.export_failed", error=str(e)))
    def email_to_admin():
        """Email report to admin"""
        try:
            # Get admin email from database
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_t("common.database_error"), _t("commerce.reports.db_connection_failed"))
                return
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE role = 'admin' LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            if not result or not result[0]:
                messagebox.showerror(_t("commerce.reports.email_error"),
                                   _t("commerce.reports.no_admin_email"))
                return
            admin_email = result[0]
            # Import email service
            try:
                from education_system.post_18.university_system.infrastructure.email.email_service import send_email
            except ImportError:
                messagebox.showerror(_t("commerce.reports.email_error"),
                                   _t("commerce.reports.email_service_unavailable"))
                return
            # Send the email
            subject = f"{_t('commerce.reports.restaurant_report')}: {title}"
            body = f"{_t('commerce.reports.find_report_below', title=title)}:\n\n{report_content}"
            send_email(admin_email, subject, body)
            messagebox.showinfo(_t("commerce.reports.email_sent"),
                              _t("commerce.reports.email_sent_to", email=admin_email))
        except (sqlite3.Error, tk.TclError) as e:
            messagebox.showerror(_t("commerce.reports.email_error"), _t("commerce.reports.email_failed", error=str(e)))
    ttk.Button(btn_frame, text=_t("commerce.reports.export_as_txt"), command=export_as_txt).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("commerce.reports.email_to_admin"), command=email_to_admin).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("common.close"), command=report_window.destroy).pack(side='left', padx=5)

def daily_sales_report(self):
    """Generate daily sales report"""
    date = simpledialog.askstring(_t("commerce.reports.daily_sales_report"),
                                 _t("commerce.reports.enter_date_prompt"))
    if date is None:
        return
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.database_error"), _t("commerce.reports.db_connection_failed"))
            return
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                COUNT(*) as total_orders,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_order_value
            FROM orders
            WHERE DATE(order_date) = ? AND order_status = 'Completed'
        ''', (date,))
        sales_data = cursor.fetchone()
        report = f"{_t('commerce.reports.daily_sales_report_header')} - {date}\n"
        report += "="*80 + "\n\n"
        report += f"{_t('commerce.reports.total_orders')}: {sales_data[0]}\n"
        report += f"{_t('commerce.reports.total_revenue')}: £{sales_data[1]:.2f}\n" if sales_data[1] else f"{_t('commerce.reports.total_revenue')}: £0.00\n"
        report += f"{_t('commerce.reports.avg_order_value')}: £{sales_data[2]:.2f}\n" if sales_data[2] else f"{_t('commerce.reports.avg_order_value')}: £0.00\n"
        conn.close()
        # Show in new window with export/email buttons
        self.show_report_window(f"{_t('commerce.reports.daily_sales_report')} - {date}", report)
    except sqlite3.Error as e:
        messagebox.showerror(_t("commerce.reports.report_error"), _t("commerce.reports.generate_failed", error=str(e)))

def monthly_summary_report(self):
    """Generate monthly summary report with actual data"""
    try:
        # Get month to report on
        month_input = simpledialog.askstring("Monthly Summary", "Enter month (YYYY-MM) or leave empty for current month:")
        if month_input is None:
            return  # User cancelled

        if not month_input:
            # Default to current month
            month_input = datetime.now().strftime('%Y-%m')

        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return

        cursor = conn.cursor()

        # Get sales data for the month
        cursor.execute('''
            SELECT
                COUNT(*) as total_orders,
                SUM(total_amount) as total_revenue,
                SUM(tax_amount) as total_tax,
                AVG(total_amount) as avg_order_value,
                MIN(total_amount) as min_order,
                MAX(total_amount) as max_order
            FROM orders
            WHERE strftime('%Y-%m', order_date) = ?
            AND order_status IN ('Completed', 'Paid')
        ''', (month_input,))

        sales_stats = cursor.fetchone()

        # Get sales by payment method
        cursor.execute('''
            SELECT
                payment_method,
                COUNT(*) as count,
                SUM(total_amount) as total
            FROM orders
            WHERE strftime('%Y-%m', order_date) = ?
            AND order_status IN ('Completed', 'Paid')
            GROUP BY payment_method
            ORDER BY total DESC
        ''', (month_input,))

        payment_breakdown = cursor.fetchall()

        # Get top selling items
        cursor.execute('''
            SELECT
                item_name,
                SUM(quantity) as total_sold,
                SUM(subtotal) as revenue
            FROM order_items
            WHERE order_id IN (
                SELECT order_id FROM orders
                WHERE strftime('%Y-%m', order_date) = ?
                AND order_status IN ('Completed', 'Paid')
            )
            GROUP BY item_name
            ORDER BY total_sold DESC
            LIMIT 10
        ''', (month_input,))

        top_items = cursor.fetchall()

        # Get daily sales trend
        cursor.execute('''
            SELECT
                strftime('%Y-%m-%d', order_date) as date,
                COUNT(*) as orders,
                SUM(total_amount) as revenue
            FROM orders
            WHERE strftime('%Y-%m', order_date) = ?
            AND order_status IN ('Completed', 'Paid')
            GROUP BY date
            ORDER BY date
        ''', (month_input,))

        daily_trend = cursor.fetchall()

        conn.close()

        # Build report
        report = "MONTHLY SUMMARY REPORT\n"
        report += f"Month: {month_input}\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += "=" * 100 + "\n\n"

        # Overall statistics
        total_orders = sales_stats[0] if sales_stats[0] else 0
        total_revenue = sales_stats[1] if sales_stats[1] else 0
        total_tax = sales_stats[2] if sales_stats[2] else 0
        avg_order = sales_stats[3] if sales_stats[3] else 0
        min_order = sales_stats[4] if sales_stats[4] else 0
        max_order = sales_stats[5] if sales_stats[5] else 0

        report += "OVERALL PERFORMANCE:\n"
        report += "-" * 100 + "\n"
        report += f"Total Orders: {total_orders}\n"
        report += f"Total Revenue (incl. tax): £{total_revenue:.2f}\n"
        report += f"Total Revenue (excl. tax): £{total_revenue - total_tax:.2f}\n"
        report += f"Total Tax Collected: £{total_tax:.2f}\n"
        report += f"Average Order Value: £{avg_order:.2f}\n"
        report += f"Minimum Order Value: £{min_order:.2f}\n"
        report += f"Maximum Order Value: £{max_order:.2f}\n\n"

        # Payment method breakdown
        report += "PAYMENT METHOD BREAKDOWN:\n"
        report += "-" * 100 + "\n"
        report += f"{'Payment Method':<20} {'Orders':<15} {'Total Revenue':<20} {'% of Total':<15}\n"
        report += "-" * 100 + "\n"

        for payment_method, count, total in payment_breakdown:
            method = payment_method if payment_method else 'Unknown'
            total = total if total else 0
            percentage = (total / total_revenue * 100) if total_revenue > 0 else 0
            report += f"{method:<20} {count:<15} £{total:<19.2f} {percentage:<14.1f}%\n"

        report += "\n"

        # Top selling items
        report += "TOP 10 SELLING ITEMS:\n"
        report += "-" * 100 + "\n"
        report += f"{'Item Name':<40} {'Quantity Sold':<20} {'Revenue':<20}\n"
        report += "-" * 100 + "\n"

        for item_name, quantity, revenue in top_items:
            revenue = revenue if revenue else 0
            report += f"{item_name:<40} {quantity:<20} £{revenue:<19.2f}\n"

        report += "\n"

        # Daily trend
        report += "DAILY SALES TREND:\n"
        report += "-" * 100 + "\n"
        report += f"{'Date':<15} {'Orders':<15} {'Revenue':<20}\n"
        report += "-" * 100 + "\n"

        for date, orders, revenue in daily_trend:
            revenue = revenue if revenue else 0
            report += f"{date:<15} {orders:<15} £{revenue:<19.2f}\n"

        if total_orders > 0:
            avg_daily_revenue = total_revenue / len(daily_trend) if daily_trend else 0
            report += "-" * 100 + "\n"
            report += f"Average Daily Revenue: £{avg_daily_revenue:.2f}\n"

        report += "\n" + "=" * 100 + "\n"
        report += "End of Monthly Summary Report\n"

        self.show_report_window(f"Monthly Summary Report - {month_input}", report)

    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to generate monthly summary: {e}")

def profit_analysis_report(self):
    """Generate profit analysis report with actual data"""
    try:
        # Get date range
        start_date = simpledialog.askstring("Profit Analysis", "Enter start date (YYYY-MM-DD):")
        if not start_date:
            return

        end_date = simpledialog.askstring("Profit Analysis", "Enter end date (YYYY-MM-DD):")
        if not end_date:
            return

        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return

        cursor = conn.cursor()

        # Get revenue data
        cursor.execute('''
            SELECT
                COUNT(*) as total_orders,
                SUM(total_amount) as gross_revenue,
                SUM(tax_amount) as tax_collected
            FROM orders
            WHERE DATE(order_date) BETWEEN ? AND ?
            AND order_status IN ('Completed', 'Paid')
        ''', (start_date, end_date))

        revenue_data = cursor.fetchone()

        # Get cost of goods sold (COGS) - approximate from order items
        cursor.execute('''
            SELECT
                SUM(subtotal) as total_cogs
            FROM order_items
            WHERE order_id IN (
                SELECT order_id FROM orders
                WHERE DATE(order_date) BETWEEN ? AND ?
                AND order_status IN ('Completed', 'Paid')
            )
        ''', (start_date, end_date))

        cogs_data = cursor.fetchone()

        # Get refunds data
        cursor.execute('''
            SELECT
                COUNT(*) as refund_count,
                SUM(amount) as total_refunds
            FROM unified_refunds
            WHERE source_type = 'order' AND DATE(refund_date) BETWEEN ? AND ?
        ''', (start_date, end_date))

        refund_data = cursor.fetchone()

        # Get discount data
        cursor.execute('''
            SELECT
                COUNT(*) as discount_count,
                SUM(discount_amount) as total_discounts
            FROM order_discounts
            WHERE DATE(discount_date) BETWEEN ? AND ?
        ''', (start_date, end_date))

        discount_data = cursor.fetchone()

        # Get waste costs if table exists
        try:
            cursor.execute('''
                SELECT SUM(cost_value) as total_waste
                FROM restaurant_waste
                WHERE waste_date BETWEEN ? AND ?
            ''', (start_date, end_date))
            waste_data = cursor.fetchone()
            waste_cost = waste_data[0] if waste_data and waste_data[0] else 0
            has_waste_table = True
        except sqlite3.OperationalError:
            waste_cost = 0
            has_waste_table = False

        conn.close()

        # Calculate profit metrics
        total_orders = revenue_data[0] if revenue_data[0] else 0
        gross_revenue = revenue_data[1] if revenue_data[1] else 0
        tax_collected = revenue_data[2] if revenue_data[2] else 0
        net_revenue = gross_revenue - tax_collected

        # COGS - estimate at 30% of net revenue if no detailed data
        cogs = cogs_data[0] if cogs_data and cogs_data[0] else (net_revenue * 0.30)

        refund_count = refund_data[0] if refund_data and refund_data[0] else 0
        total_refunds = refund_data[1] if refund_data and refund_data[1] else 0

        discount_count = discount_data[0] if discount_data and discount_data[0] else 0
        total_discounts = discount_data[1] if discount_data and discount_data[1] else 0

        # Calculate profit
        gross_profit = net_revenue - cogs
        operating_profit = gross_profit - total_refunds - total_discounts - waste_cost

        # Calculate margins
        gross_margin = (gross_profit / net_revenue * 100) if net_revenue > 0 else 0
        operating_margin = (operating_profit / net_revenue * 100) if net_revenue > 0 else 0

        # Build report
        report = "PROFIT ANALYSIS REPORT\n"
        report += f"Period: {start_date} to {end_date}\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += "=" * 100 + "\n\n"

        # Revenue section
        report += "REVENUE BREAKDOWN:\n"
        report += "-" * 100 + "\n"
        report += f"Total Orders: {total_orders}\n"
        report += f"Gross Revenue (incl. tax): £{gross_revenue:.2f}\n"
        report += f"Tax Collected: £{tax_collected:.2f}\n"
        report += f"Net Revenue (excl. tax): £{net_revenue:.2f}\n\n"

        # Costs section
        report += "COSTS BREAKDOWN:\n"
        report += "-" * 100 + "\n"
        report += f"Cost of Goods Sold (COGS): £{cogs:.2f}\n"
        report += f"Refunds ({refund_count} refunds): £{total_refunds:.2f}\n"
        report += f"Discounts ({discount_count} discounts): £{total_discounts:.2f}\n"

        if has_waste_table:
            report += f"Waste Costs: £{waste_cost:.2f}\n"
        else:
            report += "Waste Costs: N/A (table not available)\n"

        total_costs = cogs + total_refunds + total_discounts + waste_cost
        report += f"Total Costs: £{total_costs:.2f}\n\n"

        # Profit section
        report += "PROFIT ANALYSIS:\n"
        report += "-" * 100 + "\n"
        report += f"Gross Profit (Revenue - COGS): £{gross_profit:.2f}\n"
        report += f"Gross Margin: {gross_margin:.1f}%\n\n"

        report += f"Operating Profit (after refunds, discounts, waste): £{operating_profit:.2f}\n"
        report += f"Operating Margin: {operating_margin:.1f}%\n\n"

        # Performance indicators
        report += "PERFORMANCE INDICATORS:\n"
        report += "-" * 100 + "\n"

        avg_order_value = gross_revenue / total_orders if total_orders > 0 else 0
        avg_profit_per_order = operating_profit / total_orders if total_orders > 0 else 0

        report += f"Average Order Value: £{avg_order_value:.2f}\n"
        report += f"Average Profit per Order: £{avg_profit_per_order:.2f}\n"
        report += f"Refund Rate: {refund_count / total_orders * 100:.1f}%\n" if total_orders > 0 else "Refund Rate: N/A\n"
        report += f"Discount Rate: {discount_count / total_orders * 100:.1f}%\n" if total_orders > 0 else "Discount Rate: N/A\n"

        report += "\n"

        # Recommendations
        report += "RECOMMENDATIONS:\n"
        report += "-" * 100 + "\n"

        if operating_margin < 0:
            report += "⚠ WARNING: Operating margin is negative. Immediate action required:\n"
            report += "  - Review pricing strategy\n"
            report += "  - Reduce cost of goods\n"
            report += "  - Minimize waste\n"
            report += "  - Review refund and discount policies\n"
        elif operating_margin < 10:
            report += "⚠ CAUTION: Operating margin is low (<10%):\n"
            report += "  - Consider price optimization\n"
            report += "  - Monitor and reduce costs\n"
            report += "  - Focus on high-margin items\n"
        elif operating_margin < 20:
            report += "✓ GOOD: Operating margin is acceptable (10-20%):\n"
            report += "  - Continue monitoring performance\n"
            report += "  - Look for incremental improvements\n"
        else:
            report += "✓ EXCELLENT: Operating margin is strong (>20%):\n"
            report += "  - Maintain current operations\n"
            report += "  - Consider expansion opportunities\n"

        report += "\n" + "=" * 100 + "\n"
        report += "End of Profit Analysis Report\n"

        if not has_waste_table:
            report += "\nNote: Waste costs not included (restaurant_waste table not available)\n"

        self.show_report_window(f"Profit Analysis Report - {start_date} to {end_date}", report)

    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to generate profit analysis: {e}")

def menu_performance_report(self):
    """Generate menu performance report"""
    try:
        analytics_text = self.generate_menu_analytics_text()
        self.show_report_window(_t("commerce.reports.menu_performance_report"), analytics_text)
    except (sqlite3.Error, tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_t("commerce.reports.report_error"), _t("commerce.reports.generate_failed", error=str(e)))

def customer_analytics_report(self):
    """Generate customer analytics report"""
    try:
        analytics_text = self.generate_customer_analytics_text()
        self.show_report_window(_t("commerce.reports.customer_analytics_report"), analytics_text)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror(_t("commerce.reports.report_error"), _t("commerce.reports.generate_failed", error=str(e)))

def generate_customer_analytics_text(self):
    """Generate customer analytics as text"""
    try:
        conn = get_db_connection()
        if not conn:
            return _t("commerce.reports.db_connection_failed")

        cursor = conn.cursor()

        text = f"{_t('commerce.reports.customer_analytics_header')}\n"
        text += "=" * 50 + "\n\n"

        cursor.execute('''
            SELECT
                COUNT(*) as total_customers,
                AVG(loyalty_points) as avg_points,
                SUM(total_spent) as total_revenue,
                AVG(total_spent) as avg_spent_per_customer
            FROM restaurant_customers
        ''')

        stats = cursor.fetchone()

        text += f"{_t('commerce.reports.customer_overview')}:\n"
        text += "-" * 30 + "\n"
        text += f"{_t('commerce.reports.total_customers')}: {stats[0]}\n"
        text += f"{_t('commerce.reports.average_points')}: {stats[1]:.0f}\n" if stats[1] else f"{_t('commerce.reports.average_points')}: N/A\n"
        text += f"{_t('commerce.reports.total_revenue')}: £{stats[2]:.2f}\n" if stats[2] else f"{_t('commerce.reports.total_revenue')}: N/A\n"
        text += f"{_t('commerce.reports.avg_spent_per_customer')}: £{stats[3]:.2f}\n" if stats[3] else f"{_t('commerce.reports.avg_spent_per_customer')}: N/A\n"

        conn.close()
        return text

    except sqlite3.Error as e:
        return _t("commerce.reports.analytics_error", error=str(e))

def staff_performance_report(self):
    """Generate staff performance report"""
    try:
        analytics_text = self.generate_staff_analytics()
        self.show_report_window(_t("commerce.reports.staff_performance_report"), analytics_text)
    except sqlite3.Error as e:
        messagebox.showerror(_t("commerce.reports.report_error"), _t("commerce.reports.generate_failed", error=str(e)))

