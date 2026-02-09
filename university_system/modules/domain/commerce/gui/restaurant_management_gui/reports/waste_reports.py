from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from university_system.infrastructure.auth import UserAuth, get_global_auth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
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
from university_system.infrastructure.exceptions import (
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
    from university_system.modules.domain.commerce.services.restaurant_management import init_db as init_enhanced_restaurant_db
except ImportError:
    init_enhanced_restaurant_db = None

# Database configuration
# Always point to the central student_records.db in refactored/db_files.
try:
    from university_system.infrastructure.database.db import DEFAULT_DB_PATH as DATABASE_FILE
except ImportError:
    # Fallback to local file if refactored.database.db is unavailable
    DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import get_db_connection from main_gui
from university_system.modules.domain.commerce.gui.restaurant_management_gui.core.main_gui import get_db_connection


def view_waste_reports(self):
    """Show comprehensive waste reports and analytics"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Waste Reports & Analytics")
    dialog.geometry("1000x700")
    dialog.transient(self.root)
    dialog.grab_set()
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Waste Reports & Analytics",
             font=('Arial', 14, 'bold')).pack(pady=10)
    # Report type selection
    report_frame = ttk.LabelFrame(main_frame, text="Select Report Type", padding=10)
    report_frame.pack(fill='x', pady=10)
    btn_container = ttk.Frame(report_frame)
    btn_container.pack(fill='x')
    ttk.Button(btn_container, text="Waste by Date Range",
              command=lambda: self.generate_waste_by_date_range(output_text)).pack(side='left', padx=5)
    ttk.Button(btn_container, text="Waste by Category",
              command=lambda: self.generate_waste_by_category(output_text)).pack(side='left', padx=5)
    ttk.Button(btn_container, text="Waste by Reason",
              command=lambda: self.generate_waste_by_reason(output_text)).pack(side='left', padx=5)
    ttk.Button(btn_container, text="Waste Trends",
              command=lambda: self.generate_waste_trends(output_text)).pack(side='left', padx=5)
    ttk.Button(btn_container, text="Cost Analysis",
              command=lambda: self.generate_waste_cost_analysis(output_text)).pack(side='left', padx=5)
    # Output area
    output_frame = ttk.LabelFrame(main_frame, text="Report Output", padding=10)
    output_frame.pack(fill='both', expand=True, pady=10)
    output_text = ScrolledText(output_frame, height=30, width=100)
    output_text.pack(fill='both', expand=True)
    ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

def generate_waste_by_date_range(self, output_widget):
    """Generate waste report by date range"""
    start_date = simpledialog.askstring("Date Range", "Enter start date (YYYY-MM-DD):")
    if not start_date:
        return
    end_date = simpledialog.askstring("Date Range", "Enter end date (YYYY-MM-DD):")
    if not end_date:
        return
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT waste_date, item_name, quantity, unit, cost_value, reason
                FROM restaurant_waste
                WHERE waste_date BETWEEN ? AND ?
                ORDER BY waste_date DESC
            ''', (start_date, end_date))
            records = cursor.fetchall()
            cursor.execute('''
                SELECT COUNT(*), SUM(cost_value), SUM(quantity)
                FROM restaurant_waste
                WHERE waste_date BETWEEN ? AND ?
            ''', (start_date, end_date))
            summary = cursor.fetchone()
            conn.close()
            report = f"WASTE REPORT BY DATE RANGE\n"
            report += f"Period: {start_date} to {end_date}\n"
            report += "=" * 100 + "\n\n"
            report += f"Summary:\n"
            report += f"  Total Records: {summary[0]}\n"
            report += f"  Total Cost: £{summary[1]:.2f if summary[1] else 0:.2f}\n"
            report += f"  Total Quantity: {summary[2]:.1f if summary[2] else 0:.1f} units\n\n"
            report += "Detailed Records:\n"
            report += "-" * 100 + "\n"
            report += f"{'Date':<12} {'Item':<25} {'Qty':<8} {'Unit':<8} {'Cost':<10} {'Reason':<20}\n"
            report += "-" * 100 + "\n"
            for record in records:
                report += f"{record[0]:<12} {record[1]:<25} {record[2]:<8.1f} {record[3]:<8} "
                report += f"£{record[4]:<9.2f if record[4] else 0:<9.2f} {record[5]:<20}\n"
            output_widget.delete(1.0, tk.END)
            output_widget.insert(tk.END, report)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate report: {e}")

def generate_waste_by_category(self, output_widget):
    """Generate waste report grouped by category"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            # Get waste by item name (category proxy)
            cursor.execute('''
                SELECT item_name, COUNT(*), SUM(quantity), SUM(cost_value)
                FROM restaurant_waste
                GROUP BY item_name
                ORDER BY SUM(cost_value) DESC
            ''')
            records = cursor.fetchall()
            conn.close()
            report = "WASTE REPORT BY CATEGORY\n"
            report += "=" * 100 + "\n\n"
            report += f"{'Item/Category':<30} {'Records':<10} {'Total Qty':<15} {'Total Cost':<15}\n"
            report += "-" * 100 + "\n"
            total_cost = 0
            for record in records:
                cost = record[3] if record[3] else 0
                total_cost += cost
                report += f"{record[0]:<30} {record[1]:<10} {record[2]:<15.1f} £{cost:<14.2f}\n"
            report += "-" * 100 + "\n"
            report += f"{'TOTAL':<30} {'':<10} {'':<15} £{total_cost:<14.2f}\n"
            output_widget.delete(1.0, tk.END)
            output_widget.insert(tk.END, report)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate report: {e}")

def generate_waste_by_reason(self, output_widget):
    """Generate waste report grouped by reason"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT reason, COUNT(*), SUM(quantity), SUM(cost_value)
                FROM restaurant_waste
                GROUP BY reason
                ORDER BY SUM(cost_value) DESC
            ''')
            records = cursor.fetchall()
            conn.close()
            report = "WASTE REPORT BY REASON\n"
            report += "=" * 100 + "\n\n"
            report += f"{'Reason':<25} {'Records':<10} {'Total Qty':<15} {'Total Cost':<15} {'% of Total':<12}\n"
            report += "-" * 100 + "\n"
            total_cost = sum(record[3] if record[3] else 0 for record in records)
            for record in records:
                cost = record[3] if record[3] else 0
                percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                report += f"{record[0]:<25} {record[1]:<10} {record[2]:<15.1f} "
                report += f"£{cost:<14.2f} {percentage:<11.1f}%\n"
            report += "-" * 100 + "\n"
            report += f"{'TOTAL':<25} {'':<10} {'':<15} £{total_cost:<14.2f} {'100.0%':<12}\n"
            output_widget.delete(1.0, tk.END)
            output_widget.insert(tk.END, report)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate report: {e}")

def generate_waste_trends(self, output_widget):
    """Generate waste trends over time"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            # Monthly trends
            cursor.execute('''
                SELECT strftime('%Y-%m', waste_date) as month,
                       COUNT(*), SUM(cost_value), SUM(quantity)
                FROM restaurant_waste
                GROUP BY month
                ORDER BY month DESC
                LIMIT 12
            ''')
            monthly = cursor.fetchall()
            # Weekly trends
            cursor.execute('''
                SELECT strftime('%Y-W%W', waste_date) as week,
                       COUNT(*), SUM(cost_value), SUM(quantity)
                FROM restaurant_waste
                WHERE waste_date >= date('now', '-8 weeks')
                GROUP BY week
                ORDER BY week DESC
            ''')
            weekly = cursor.fetchall()
            conn.close()
            report = "WASTE TRENDS ANALYSIS\n"
            report += "=" * 100 + "\n\n"
            report += "MONTHLY TRENDS (Last 12 Months):\n"
            report += "-" * 100 + "\n"
            report += f"{'Month':<15} {'Records':<10} {'Total Cost':<15} {'Total Qty':<15} {'Avg Cost/Record':<15}\n"
            report += "-" * 100 + "\n"
            for record in monthly:
                avg_cost = (record[2] / record[1]) if record[1] and record[2] else 0
                report += f"{record[0]:<15} {record[1]:<10} £{record[2] if record[2] else 0:<14.2f} "
                report += f"{record[3] if record[3] else 0:<15.1f} £{avg_cost:<14.2f}\n"
            report += "\n\nWEEKLY TRENDS (Last 8 Weeks):\n"
            report += "-" * 100 + "\n"
            report += f"{'Week':<15} {'Records':<10} {'Total Cost':<15} {'Total Qty':<15} {'Avg Cost/Record':<15}\n"
            report += "-" * 100 + "\n"
            for record in weekly:
                avg_cost = (record[2] / record[1]) if record[1] and record[2] else 0
                report += f"{record[0]:<15} {record[1]:<10} £{record[2] if record[2] else 0:<14.2f} "
                report += f"{record[3] if record[3] else 0:<15.1f} £{avg_cost:<14.2f}\n"
            # Add waste reduction suggestions
            report += "\n\nWASTE REDUCTION SUGGESTIONS:\n"
            report += "-" * 100 + "\n"
            if monthly:
                latest_month_cost = monthly[0][2] if monthly[0][2] else 0
                if len(monthly) > 1:
                    prev_month_cost = monthly[1][2] if monthly[1][2] else 0
                    if latest_month_cost > prev_month_cost:
                        report += "• Waste cost increased from previous month - review procurement and portion sizes\n"
                    else:
                        report += "• Waste cost decreased from previous month - current practices are effective\n"
                if latest_month_cost > 500:
                    report += "• High waste cost detected - consider implementing:\n"
                    report += "  - Better inventory management\n"
                    report += "  - Staff training on portion control\n"
                    report += "  - Review menu items with highest waste\n"
            output_widget.delete(1.0, tk.END)
            output_widget.insert(tk.END, report)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate trends report: {e}")

def generate_waste_cost_analysis(self, output_widget):
    """Generate detailed cost analysis of waste"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            # Overall statistics
            cursor.execute('''
                SELECT COUNT(*), SUM(cost_value), AVG(cost_value), MAX(cost_value)
                FROM restaurant_waste
            ''')
            overall = cursor.fetchone()
            # Cost by reason
            cursor.execute('''
                SELECT reason, SUM(cost_value)
                FROM restaurant_waste
                GROUP BY reason
                ORDER BY SUM(cost_value) DESC
            ''')
            by_reason = cursor.fetchall()
            # Most expensive waste items
            cursor.execute('''
                SELECT item_name, waste_date, cost_value, reason
                FROM restaurant_waste
                ORDER BY cost_value DESC
                LIMIT 10
            ''')
            top_expensive = cursor.fetchall()
            conn.close()
            report = "WASTE COST ANALYSIS\n"
            report += "=" * 100 + "\n\n"
            report += "OVERALL STATISTICS:\n"
            report += "-" * 100 + "\n"
            report += f"Total Waste Records: {overall[0]}\n"
            report += f"Total Waste Cost: £{overall[1]:.2f if overall[1] else 0:.2f}\n"
            report += f"Average Waste Cost per Record: £{overall[2]:.2f if overall[2] else 0:.2f}\n"
            report += f"Maximum Single Waste Cost: £{overall[3]:.2f if overall[3] else 0:.2f}\n\n"
            report += "COST BREAKDOWN BY REASON:\n"
            report += "-" * 100 + "\n"
            total_cost = overall[1] if overall[1] else 0
            for record in by_reason:
                cost = record[1] if record[1] else 0
                percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                report += f"  {record[0]:<25} £{cost:<14.2f} ({percentage:.1f}%)\n"
            report += "\n\nTOP 10 MOST EXPENSIVE WASTE ITEMS:\n"
            report += "-" * 100 + "\n"
            report += f"{'Item':<30} {'Date':<12} {'Cost':<12} {'Reason':<25}\n"
            report += "-" * 100 + "\n"
            for record in top_expensive:
                report += f"{record[0]:<30} {record[1]:<12} £{record[2]:<11.2f if record[2] else 0:<11.2f} {record[3]:<25}\n"
            # Cost impact analysis
            report += "\n\nCOST IMPACT ANALYSIS:\n"
            report += "-" * 100 + "\n"
            monthly_avg = (total_cost / 12) if total_cost > 0 else 0
            annual_projection = total_cost  # If this is YTD data
            report += f"Monthly Average Waste Cost: £{monthly_avg:.2f}\n"
            report += f"Annual Projected Waste Cost: £{annual_projection:.2f}\n"
            report += f"\nPotential Savings with 25% Reduction: £{annual_projection * 0.25:.2f}/year\n"
            report += f"Potential Savings with 50% Reduction: £{annual_projection * 0.50:.2f}/year\n"
            output_widget.delete(1.0, tk.END)
            output_widget.insert(tk.END, report)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate cost analysis: {e}")

