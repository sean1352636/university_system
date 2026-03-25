from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
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
from education_system.university_system.infrastructure.exceptions import (
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
    from education_system.university_system.modules.domain.commerce.services.restaurant_management import init_db as init_enhanced_restaurant_db
except ImportError:
    init_enhanced_restaurant_db = None

# Database configuration
# Always point to the central student_records.db in refactored/db_files.
try:
    from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH as DATABASE_FILE
except ImportError:
    # Fallback to local file if refactored.database.db is unavailable
    DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import get_db_connection from main_gui
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.core.main_gui import get_db_connection


def export_payroll_report(self):
    """Export staff payroll data"""
    try:
        from tkinter import filedialog
        import csv
        # Get date range
        start_date = simpledialog.askstring("Payroll Report", "Enter start date (YYYY-MM-DD):")
        if not start_date:
            return
        end_date = simpledialog.askstring("Payroll Report", "Enter end date (YYYY-MM-DD):")
        if not end_date:
            return
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()

        # Check if restaurant_shifts table exists
        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='restaurant_shifts'
        ''')

        if cursor.fetchone() is None:
            conn.close()
            messagebox.showinfo("Table Not Available",
                              "Payroll report requires the restaurant_shifts table which is not yet created.\n\n" +
                              "This table tracks employee work hours and shifts.\n\n" +
                              "Please contact your system administrator to set up shift tracking.")
            return

        # Get staff and their shifts
        cursor.execute('''
            SELECT s.staff_id, s.name, s.position, s.hourly_rate,
                   COUNT(sh.shift_id) as shift_count,
                   SUM(
                       CASE
                           WHEN sh.end_time IS NOT NULL THEN
                               (julianday(sh.end_time) - julianday(sh.start_time)) * 24
                           ELSE 0
                       END
                   ) as total_hours
            FROM restaurant_staff s
            LEFT JOIN restaurant_shifts sh ON s.staff_id = sh.staff_id
            WHERE sh.shift_date BETWEEN ? AND ?
            GROUP BY s.staff_id
            ORDER BY s.name
        ''', (start_date, end_date))
        payroll_data = cursor.fetchall()
        conn.close()
        if not payroll_data:
            messagebox.showinfo("No Data", "No payroll data found for the specified period")
            return
        # Ask for export format
        format_choice = messagebox.askquestion("Export Format",
                                              "Export as CSV?\n(No = Display in window)")
        if format_choice == 'yes':
            # Export to CSV
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"payroll_report_{start_date}_to_{end_date}.csv"
            )
            if filename:
                with open(filename, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Staff ID', 'Name', 'Position', 'Hourly Rate',
                                   'Shifts Worked', 'Total Hours', 'Gross Pay'])
                    for record in payroll_data:
                        hours = record[5] if record[5] else 0
                        rate = record[3] if record[3] else 0
                        gross_pay = hours * rate
                        writer.writerow([record[0], record[1], record[2], f"£{rate:.2f}",
                                      record[4], f"{hours:.2f}", f"£{gross_pay:.2f}"])
                messagebox.showinfo("Success", f"Payroll report exported to {filename}")
        else:
            # Display in report window
            report = f"PAYROLL REPORT\n"
            report += f"Period: {start_date} to {end_date}\n"
            report += "=" * 100 + "\n\n"
            report += f"{'ID':<8} {'Name':<25} {'Position':<20} {'Rate':<12} {'Shifts':<10} {'Hours':<12} {'Gross Pay':<12}\n"
            report += "-" * 100 + "\n"
            total_hours = 0
            total_pay = 0
            for record in payroll_data:
                hours = record[5] if record[5] else 0
                rate = record[3] if record[3] else 0
                gross_pay = hours * rate
                total_hours += hours
                total_pay += gross_pay
                report += f"{record[0]:<8} {record[1]:<25} {record[2]:<20} "
                report += f"£{rate:<11.2f} {record[4]:<10} {hours:<12.2f} £{gross_pay:<11.2f}\n"
            report += "-" * 100 + "\n"
            report += f"{'TOTALS:':<54} {'':<12} {'':<10} {total_hours:<12.2f} £{total_pay:<11.2f}\n"
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(tk.END, report)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate payroll report: {e}")

def export_expense_report(self):
    """Export detailed expense report"""
    try:
        from tkinter import filedialog
        import csv
        # Get date range
        start_date = simpledialog.askstring("Expense Report", "Enter start date (YYYY-MM-DD):")
        if not start_date:
            return
        end_date = simpledialog.askstring("Expense Report", "Enter end date (YYYY-MM-DD):")
        if not end_date:
            return
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()

        # Check if restaurant_purchase_orders table exists
        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='restaurant_purchase_orders'
        ''')

        if cursor.fetchone() is None:
            conn.close()
            messagebox.showinfo("Table Not Available",
                              "Expense report requires the restaurant_purchase_orders table which is not yet created.\n\n" +
                              "This table tracks inventory purchases and supplier expenses.\n\n" +
                              "Current workaround: Expenses can be estimated from revenue and profit data.\n" +
                              "Contact your system administrator to set up purchase order tracking.")
            return

        # Get expenses from purchase orders
        cursor.execute('''
            SELECT po.order_id, po.supplier_id, s.name as supplier_name,
                   po.order_date, po.total_cost, po.status, po.payment_method
            FROM restaurant_purchase_orders po
            LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
            WHERE po.order_date BETWEEN ? AND ?
            ORDER BY po.order_date DESC
        ''', (start_date, end_date))
        expenses = cursor.fetchall()
        conn.close()
        if not expenses:
            messagebox.showinfo("No Data", "No expense data found for the specified period")
            return
        # Ask for export format
        format_choice = messagebox.askquestion("Export Format",
                                              "Export as CSV?\n(No = Display in window)")
        if format_choice == 'yes':
            # Export to CSV
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"expense_report_{start_date}_to_{end_date}.csv"
            )
            if filename:
                with open(filename, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Order ID', 'Supplier ID', 'Supplier Name', 'Date',
                                   'Amount', 'Status', 'Payment Method'])
                    for record in expenses:
                        writer.writerow([record[0], record[1], record[2], record[3],
                                      f"£{record[4]:.2f}", record[5], record[6]])
                messagebox.showinfo("Success", f"Expense report exported to {filename}")
        else:
            # Display in report window
            report = f"EXPENSE REPORT\n"
            report += f"Period: {start_date} to {end_date}\n"
            report += "=" * 110 + "\n\n"
            report += f"{'Order ID':<10} {'Supplier':<25} {'Date':<12} {'Amount':<12} {'Status':<12} {'Payment':<15}\n"
            report += "-" * 110 + "\n"
            total_expense = 0
            status_totals = {}
            payment_totals = {}
            for record in expenses:
                amount = record[4] if record[4] else 0
                total_expense += amount
                status = record[5] if record[5] else 'Unknown'
                status_totals[status] = status_totals.get(status, 0) + amount
                payment = record[6] if record[6] else 'Unknown'
                payment_totals[payment] = payment_totals.get(payment, 0) + amount
                report += f"{record[0]:<10} {record[2]:<25} {record[3]:<12} £{amount:<11.2f} {status:<12} {payment:<15}\n"
            report += "-" * 110 + "\n"
            report += f"{'TOTAL EXPENSES:':<49} £{total_expense:<11.2f}\n\n"
            report += "BREAKDOWN BY STATUS:\n"
            for status, amount in status_totals.items():
                report += f"  {status:<20} £{amount:.2f}\n"
            report += "\nBREAKDOWN BY PAYMENT METHOD:\n"
            for payment, amount in payment_totals.items():
                report += f"  {payment:<20} £{amount:.2f}\n"
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(tk.END, report)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate expense report: {e}")

def tax_reports_menu(self):
    """Show tax reporting menu"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Tax Reports")
    dialog.geometry("400x300")
    dialog.transient(self.root)
    dialog.grab_set()
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Tax Reports", font=('Arial', 14, 'bold')).pack(pady=20)
    ttk.Button(main_frame, text="Generate VAT Report",
              command=lambda: [dialog.destroy(), self.generate_vat_report()],
              width=30).pack(pady=10)
    ttk.Button(main_frame, text="Generate Sales Tax Summary",
              command=lambda: [dialog.destroy(), self.generate_sales_tax_summary()],
              width=30).pack(pady=10)
    ttk.Button(main_frame, text="Close", command=dialog.destroy, width=30).pack(pady=20)

def generate_vat_report(self):
    """Generate VAT/GST report"""
    try:
        # Get date range
        start_date = simpledialog.askstring("VAT Report", "Enter start date (YYYY-MM-DD):")
        if not start_date:
            return
        end_date = simpledialog.askstring("VAT Report", "Enter end date (YYYY-MM-DD):")
        if not end_date:
            return
        vat_rate = 0.20  # 20% UK VAT rate
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # VAT collected on sales
        cursor.execute('''
            SELECT SUM(total_amount), SUM(tax_amount)
            FROM orders
            WHERE DATE(order_date) BETWEEN ? AND ?
            AND order_status = 'Completed'
        ''', (start_date, end_date))
        sales_data = cursor.fetchone()
        # VAT paid on purchases (check if table exists)
        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='restaurant_purchase_orders'
        ''')

        total_purchases = 0
        has_purchase_orders = cursor.fetchone() is not None

        if has_purchase_orders:
            cursor.execute('''
                SELECT SUM(total_cost)
                FROM restaurant_purchase_orders
                WHERE order_date BETWEEN ? AND ?
                AND status = 'Completed'
            ''', (start_date, end_date))
            purchase_data = cursor.fetchone()
            total_purchases = purchase_data[0] if purchase_data and purchase_data[0] else 0

        conn.close()

        total_sales = sales_data[0] if sales_data[0] else 0
        vat_collected = sales_data[1] if sales_data[1] else (total_sales * vat_rate / (1 + vat_rate))
        vat_paid = total_purchases * vat_rate / (1 + vat_rate) if has_purchase_orders else 0
        net_vat_liability = vat_collected - vat_paid
        report = f"VAT REPORT\n"
        report += f"Period: {start_date} to {end_date}\n"
        report += f"VAT Rate: {vat_rate*100:.0f}%\n"
        report += "=" * 80 + "\n\n"
        report += "VAT COLLECTED (Output VAT):\n"
        report += "-" * 80 + "\n"
        report += f"Total Sales (including VAT): £{total_sales:.2f}\n"
        report += f"VAT Collected on Sales: £{vat_collected:.2f}\n\n"
        report += "VAT PAID (Input VAT):\n"
        report += "-" * 80 + "\n"
        report += f"Total Purchases (including VAT): £{total_purchases:.2f}\n"
        report += f"VAT Paid on Purchases: £{vat_paid:.2f}\n\n"
        report += "NET VAT POSITION:\n"
        report += "-" * 80 + "\n"
        if net_vat_liability > 0:
            report += f"VAT Payable to HMRC: £{net_vat_liability:.2f}\n"
        elif net_vat_liability < 0:
            report += f"VAT Reclaimable from HMRC: £{abs(net_vat_liability):.2f}\n"
        else:
            report += f"VAT Position: £0.00 (Neutral)\n"
        report += "\n" + "=" * 80 + "\n"
        report += "This report is for informational purposes only.\n"
        report += "Please consult with a qualified accountant for official VAT returns.\n"

        if not has_purchase_orders:
            report += "\nNote: Purchase VAT not included (restaurant_purchase_orders table not available)\n"

        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate VAT report: {e}")

def generate_sales_tax_summary(self):
    """Generate sales tax summary"""
    try:
        # Get date range
        start_date = simpledialog.askstring("Sales Tax Summary", "Enter start date (YYYY-MM-DD):")
        if not start_date:
            return
        end_date = simpledialog.askstring("Sales Tax Summary", "Enter end date (YYYY-MM-DD):")
        if not end_date:
            return
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Sales by payment method
        cursor.execute('''
            SELECT payment_method, COUNT(*), SUM(total_amount), SUM(tax_amount)
            FROM orders
            WHERE DATE(order_date) BETWEEN ? AND ?
            AND order_status = 'Completed'
            GROUP BY payment_method
        ''', (start_date, end_date))
        payment_breakdown = cursor.fetchall()
        # Total sales
        cursor.execute('''
            SELECT COUNT(*), SUM(total_amount), SUM(tax_amount)
            FROM orders
            WHERE DATE(order_date) BETWEEN ? AND ?
            AND order_status = 'Completed'
        ''', (start_date, end_date))
        totals = cursor.fetchone()
        conn.close()
        report = f"SALES TAX SUMMARY\n"
        report += f"Period: {start_date} to {end_date}\n"
        report += "=" * 100 + "\n\n"
        report += "SUMMARY:\n"
        report += "-" * 100 + "\n"
        report += f"Total Transactions: {totals[0]}\n"
        report += f"Total Taxable Sales: £{(totals[1] - totals[2]) if totals[1] and totals[2] else 0:.2f}\n"
        report += f"Total Tax Collected: £{totals[2] if totals[2] else 0:.2f}\n"
        report += f"Total Sales (including tax): £{totals[1] if totals[1] else 0:.2f}\n\n"
        report += "BREAKDOWN BY PAYMENT METHOD:\n"
        report += "-" * 100 + "\n"
        report += f"{'Payment Method':<20} {'Transactions':<15} {'Taxable Amount':<18} {'Tax Collected':<18} {'Total':<15}\n"
        report += "-" * 100 + "\n"
        for record in payment_breakdown:
            method = record[0] if record[0] else 'Unknown'
            count = record[1]
            total_amount = record[2] if record[2] else 0
            tax = record[3] if record[3] else 0
            taxable = total_amount - tax
            report += f"{method:<20} {count:<15} £{taxable:<17.2f} £{tax:<17.2f} £{total_amount:<14.2f}\n"
        report += "\n" + "=" * 100 + "\n"
        report += "Filing Period Summary: This report summarizes all sales tax collected for the specified period.\n"
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate sales tax summary: {e}")

def financial_forecasting(self):
    """Generate financial forecasts based on historical data"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Get historical revenue by month (last 12 months)
        cursor.execute('''
            SELECT strftime('%Y-%m', order_date) as month,
                   SUM(total_amount) as revenue,
                   COUNT(*) as order_count
            FROM orders
            WHERE order_status = 'Completed'
            AND order_date >= date('now', '-12 months')
            GROUP BY month
            ORDER BY month
        ''')
        monthly_revenue = cursor.fetchall()
        # Get historical expenses by month (check if table exists)
        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='restaurant_purchase_orders'
        ''')

        has_purchase_orders = cursor.fetchone() is not None
        monthly_expenses = []

        if has_purchase_orders:
            cursor.execute('''
                SELECT strftime('%Y-%m', order_date) as month,
                       SUM(total_cost) as expenses
                FROM restaurant_purchase_orders
                WHERE status = 'Completed'
                AND order_date >= date('now', '-12 months')
                GROUP BY month
                ORDER BY month
            ''')
            monthly_expenses = cursor.fetchall()

        conn.close()
        if not monthly_revenue:
            messagebox.showinfo("No Data", "Insufficient historical data for forecasting")
            return
        # Calculate averages and trends
        total_revenue = sum(r[1] for r in monthly_revenue if r[1])
        avg_monthly_revenue = total_revenue / len(monthly_revenue) if monthly_revenue else 0
        expense_dict = {e[0]: e[1] for e in monthly_expenses if e[1]}
        total_expenses = sum(expense_dict.values())

        # If no purchase orders data, estimate expenses as 70% of revenue (30% profit margin)
        if not has_purchase_orders and monthly_revenue:
            avg_monthly_expenses = avg_monthly_revenue * 0.70
            for rev_record in monthly_revenue:
                month = rev_record[0]
                revenue = rev_record[1] if rev_record[1] else 0
                expense_dict[month] = revenue * 0.70
            total_expenses = sum(expense_dict.values())
        else:
            avg_monthly_expenses = total_expenses / len(monthly_expenses) if monthly_expenses else 0
        avg_monthly_profit = avg_monthly_revenue - avg_monthly_expenses
        # Simple linear trend (last 3 months vs previous 3 months)
        if len(monthly_revenue) >= 6:
            recent_avg = sum(r[1] for r in monthly_revenue[-3:] if r[1]) / 3
            previous_avg = sum(r[1] for r in monthly_revenue[-6:-3] if r[1]) / 3
            growth_rate = ((recent_avg - previous_avg) / previous_avg) if previous_avg > 0 else 0
        else:
            growth_rate = 0
        # Forecast next 3 months
        forecast_months = 3
        projected_revenue = []
        projected_expenses = []
        projected_profit = []
        for i in range(1, forecast_months + 1):
            forecast_rev = avg_monthly_revenue * (1 + growth_rate * i)
            forecast_exp = avg_monthly_expenses * (1 + growth_rate * i * 0.8)  # Assume expenses grow slower
            projected_revenue.append(forecast_rev)
            projected_expenses.append(forecast_exp)
            projected_profit.append(forecast_rev - forecast_exp)
        report = "FINANCIAL FORECASTING\n"
        report += "=" * 100 + "\n\n"
        report += "HISTORICAL PERFORMANCE (Last 12 Months):\n"
        report += "-" * 100 + "\n"
        report += f"{'Month':<12} {'Revenue':<15} {'Expenses':<15} {'Profit':<15} {'Orders':<10}\n"
        report += "-" * 100 + "\n"
        for rev_record in monthly_revenue:
            month = rev_record[0]
            revenue = rev_record[1] if rev_record[1] else 0
            expenses = expense_dict.get(month, 0)
            profit = revenue - expenses
            orders = rev_record[2]
            report += f"{month:<12} £{revenue:<14.2f} £{expenses:<14.2f} £{profit:<14.2f} {orders:<10}\n"
        report += "\n\nAVERAGES:\n"
        report += "-" * 100 + "\n"
        report += f"Average Monthly Revenue: £{avg_monthly_revenue:.2f}\n"
        report += f"Average Monthly Expenses: £{avg_monthly_expenses:.2f}\n"
        report += f"Average Monthly Profit: £{avg_monthly_profit:.2f}\n"
        report += f"Growth Rate (Trend): {growth_rate*100:.1f}%\n"
        report += "\n\n3-MONTH FORECAST:\n"
        report += "-" * 100 + "\n"
        report += f"{'Month':<12} {'Projected Revenue':<20} {'Projected Expenses':<20} {'Projected Profit':<20}\n"
        report += "-" * 100 + "\n"
        from datetime import datetime, timedelta
        forecast_start = datetime.now() + timedelta(days=30)
        for i in range(forecast_months):
            forecast_month = (forecast_start + timedelta(days=30*i)).strftime('%Y-%m')
            report += f"{forecast_month:<12} £{projected_revenue[i]:<19.2f} £{projected_expenses[i]:<19.2f} £{projected_profit[i]:<19.2f}\n"
        report += "\n\nKEY INSIGHTS:\n"
        report += "-" * 100 + "\n"
        if growth_rate > 0:
            report += f"• Positive growth trend of {growth_rate*100:.1f}% detected\n"
            report += f"• Projected 3-month revenue: £{sum(projected_revenue):.2f}\n"
            report += f"• Projected 3-month profit: £{sum(projected_profit):.2f}\n"
        elif growth_rate < 0:
            report += f"• Negative growth trend of {growth_rate*100:.1f}% detected\n"
            report += "• Consider reviewing pricing and marketing strategies\n"
        else:
            report += "• Revenue appears stable\n"
        if avg_monthly_profit < 0:
            report += "• WARNING: Average monthly profit is negative\n"
            report += "• Immediate cost reduction or revenue enhancement needed\n"
        report += "\n" + "=" * 100 + "\n"
        report += "Note: Forecasts are based on historical trends and should be used as guidance only.\n"
        report += "Actual results may vary based on market conditions and business decisions.\n"

        if not has_purchase_orders:
            report += "\nNote: Expense data estimated at 70% of revenue (restaurant_purchase_orders table not available)\n"

        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate forecast: {e}")

def export_financial_data_menu(self):
    """Show export financial data menu"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Export Financial Data")
    dialog.geometry("400x300")
    dialog.transient(self.root)
    dialog.grab_set()
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Export Financial Data",
             font=('Arial', 14, 'bold')).pack(pady=20)
    ttk.Button(main_frame, text="Export Complete Financial Data",
              command=lambda: [dialog.destroy(), self.export_complete_financial_data()],
              width=35).pack(pady=10)
    ttk.Button(main_frame, text="Export Sales Data Only",
              command=lambda: [dialog.destroy(), self.export_sales_data()],
              width=35).pack(pady=10)
    ttk.Button(main_frame, text="Close", command=dialog.destroy, width=35).pack(pady=20)

def export_complete_financial_data(self):
    """Export complete financial data to CSV"""
    try:
        from tkinter import filedialog
        import csv
        # Get date range
        start_date = simpledialog.askstring("Export Financial Data",
                                           "Enter start date (YYYY-MM-DD):")
        if not start_date:
            return
        end_date = simpledialog.askstring("Export Financial Data",
                                         "Enter end date (YYYY-MM-DD):")
        if not end_date:
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"complete_financial_data_{start_date}_to_{end_date}.csv"
        )
        if not filename:
            return
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()

        # Check which tables exist
        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('restaurant_purchase_orders', 'restaurant_waste')
        ''')
        existing_tables = {row[0] for row in cursor.fetchall()}
        has_purchase_orders = 'restaurant_purchase_orders' in existing_tables
        has_waste = 'restaurant_waste' in existing_tables

        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(['COMPLETE FINANCIAL DATA EXPORT'])
            writer.writerow([f'Period: {start_date} to {end_date}'])
            writer.writerow([])
            # Sales Revenue
            writer.writerow(['SALES REVENUE'])
            writer.writerow(['Order ID', 'Date', 'Total Price', 'Tax Amount', 'Payment Method', 'Status'])
            cursor.execute('''
                SELECT order_id, order_date, total_amount, tax_amount, payment_method, order_status
                FROM orders
                WHERE DATE(order_date) BETWEEN ? AND ?
                ORDER BY order_date
            ''', (start_date, end_date))
            sales = cursor.fetchall()
            for record in sales:
                writer.writerow(record)
            writer.writerow([])

            # Purchase Expenses (if table exists)
            if has_purchase_orders:
                writer.writerow(['PURCHASE EXPENSES'])
                writer.writerow(['Order ID', 'Supplier ID', 'Date', 'Total Cost', 'Status', 'Payment Method'])
                cursor.execute('''
                    SELECT order_id, supplier_id, order_date, total_cost, status, payment_method
                    FROM restaurant_purchase_orders
                    WHERE order_date BETWEEN ? AND ?
                    ORDER BY order_date
                ''', (start_date, end_date))
                purchases = cursor.fetchall()
                for record in purchases:
                    writer.writerow(record)
                writer.writerow([])
            else:
                writer.writerow(['PURCHASE EXPENSES'])
                writer.writerow(['Table not available - restaurant_purchase_orders does not exist'])
                writer.writerow([])
            # Waste Costs (if table exists)
            if has_waste:
                writer.writerow(['WASTE COSTS'])
                writer.writerow(['Waste ID', 'Item', 'Date', 'Cost', 'Reason'])
                cursor.execute('''
                    SELECT waste_id, item_name, waste_date, cost_value, reason
                    FROM restaurant_waste
                    WHERE waste_date BETWEEN ? AND ?
                    ORDER BY waste_date
                ''', (start_date, end_date))
                waste = cursor.fetchall()
                for record in waste:
                    writer.writerow(record)
                writer.writerow([])
            else:
                writer.writerow(['WASTE COSTS'])
                writer.writerow(['Table not available - restaurant_waste does not exist'])
                writer.writerow([])
            # Summary
            cursor.execute('''
                SELECT SUM(total_amount), SUM(tax_amount)
                FROM orders
                WHERE DATE(order_date) BETWEEN ? AND ?
                AND order_status = 'Completed'
            ''', (start_date, end_date))
            sales_summary = cursor.fetchone()
            # Get expense and waste summaries only if tables exist
            expense_summary = (0,)
            if has_purchase_orders:
                cursor.execute('''
                    SELECT SUM(total_cost)
                    FROM restaurant_purchase_orders
                    WHERE order_date BETWEEN ? AND ?
                    AND status = 'Completed'
                ''', (start_date, end_date))
                expense_summary = cursor.fetchone()

            waste_summary = (0,)
            if has_waste:
                cursor.execute('''
                    SELECT SUM(cost_value)
                    FROM restaurant_waste
                    WHERE waste_date BETWEEN ? AND ?
                ''', (start_date, end_date))
                waste_summary = cursor.fetchone()
            writer.writerow(['FINANCIAL SUMMARY'])
            writer.writerow(['Total Sales Revenue', f"£{sales_summary[0] if sales_summary[0] else 0:.2f}"])
            writer.writerow(['Total Tax Collected', f"£{sales_summary[1] if sales_summary[1] else 0:.2f}"])
            writer.writerow(['Total Purchase Expenses', f"£{expense_summary[0] if expense_summary[0] else 0:.2f}"])
            writer.writerow(['Total Waste Costs', f"£{waste_summary[0] if waste_summary[0] else 0:.2f}"])
            total_expenses = (expense_summary[0] if expense_summary[0] else 0) + (waste_summary[0] if waste_summary[0] else 0)
            total_revenue = sales_summary[0] if sales_summary[0] else 0
            net_profit = total_revenue - total_expenses
            writer.writerow(['Total Expenses', f"£{total_expenses:.2f}"])
            writer.writerow(['Net Profit/Loss', f"£{net_profit:.2f}"])
            writer.writerow([])

            # Add notes about missing tables
            if not has_purchase_orders or not has_waste:
                writer.writerow(['NOTES'])
                if not has_purchase_orders:
                    writer.writerow(['- Purchase expenses not included (restaurant_purchase_orders table not available)'])
                if not has_waste:
                    writer.writerow(['- Waste costs not included (restaurant_waste table not available)'])

        conn.close()

        success_msg = f"Complete financial data exported to:\n{filename}"
        if not has_purchase_orders or not has_waste:
            success_msg += "\n\nNote: Some data tables were not available and have been omitted from the export."

        messagebox.showinfo("Success", success_msg)
    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to export financial data: {e}")

def export_sales_data(self):
    """Export sales-specific data to CSV"""
    try:
        from tkinter import filedialog
        import csv
        # Get date range
        start_date = simpledialog.askstring("Export Sales Data",
                                           "Enter start date (YYYY-MM-DD):")
        if not start_date:
            return
        end_date = simpledialog.askstring("Export Sales Data",
                                         "Enter end date (YYYY-MM-DD):")
        if not end_date:
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"sales_data_{start_date}_to_{end_date}.csv"
        )
        if not filename:
            return
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(['SALES DATA EXPORT'])
            writer.writerow([f'Period: {start_date} to {end_date}'])
            writer.writerow([])
            # Sales transactions
            writer.writerow(['ALL SALES TRANSACTIONS'])
            writer.writerow(['Order ID', 'Customer ID', 'Date/Time', 'Subtotal',
                           'Tax Amount', 'Total Price', 'Payment Method', 'Status'])
            cursor.execute('''
                SELECT order_id, customer_id, order_date,
                       (total_amount - tax_amount) as subtotal,
                       tax_amount, total_amount, payment_method, order_status
                FROM orders
                WHERE DATE(order_date) BETWEEN ? AND ?
                ORDER BY order_date
            ''', (start_date, end_date))
            transactions = cursor.fetchall()
            for record in transactions:
                writer.writerow(record)
            writer.writerow([])
            # Item-level sales (if available)
            writer.writerow(['ITEM-LEVEL SALES'])
            writer.writerow(['Order ID', 'Item ID', 'Item Name', 'Quantity', 'Unit Price', 'Subtotal'])
            cursor.execute('''
                SELECT oi.order_id, oi.item_id, oi.item_name, oi.quantity, oi.unit_price, oi.subtotal
                FROM order_items oi
                JOIN orders ro ON oi.order_id = ro.order_id
                WHERE DATE(ro.order_date) BETWEEN ? AND ?
                ORDER BY oi.order_id
            ''', (start_date, end_date))
            items = cursor.fetchall()
            for record in items:
                writer.writerow(record)
            writer.writerow([])
            # Summary statistics
            writer.writerow(['SALES SUMMARY'])
            cursor.execute('''
                SELECT
                    COUNT(*) as total_orders,
                    SUM(total_amount - tax_amount) as total_sales,
                    SUM(tax_amount) as total_tax,
                    SUM(total_amount) as total_with_tax,
                    AVG(total_amount) as avg_order_value
                FROM orders
                WHERE DATE(order_date) BETWEEN ? AND ?
                AND order_status = 'Completed'
            ''', (start_date, end_date))
            summary = cursor.fetchone()
            writer.writerow(['Total Orders', summary[0]])
            writer.writerow(['Total Sales (excl. tax)', f"£{summary[1] if summary[1] else 0:.2f}"])
            writer.writerow(['Total Tax Collected', f"£{summary[2] if summary[2] else 0:.2f}"])
            writer.writerow(['Total Sales (incl. tax)', f"£{summary[3] if summary[3] else 0:.2f}"])
            writer.writerow(['Average Order Value', f"£{summary[4] if summary[4] else 0:.2f}"])
        conn.close()
        messagebox.showinfo("Success", f"Sales data exported to:\n{filename}")
    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to export sales data: {e}")

