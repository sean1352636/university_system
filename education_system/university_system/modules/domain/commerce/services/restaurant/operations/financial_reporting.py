from education_system.university_system.infrastructure.auth import UserAuth, display_auth_menu
from education_system.university_system.infrastructure.database.data_backup import display_backup_menu, backup_before_operation
from education_system.university_system.infrastructure.email import send_confirmation_email
from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
import random
import re
import os
import csv
import pandas as pd
import json
import hashlib
import logging
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import qrcode
from PIL import Image
import matplotlib.pyplot as plt
from decimal import Decimal, ROUND_HALF_UP
import threading
import time
from collections import defaultdict
import warnings
from education_system.university_system.infrastructure.logging.log_config import configure_logging
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.connection import get_db_connection

# Configure logging
logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)


def display_financial_reports():
    """Financial reports menu with full functionality"""
    global auth

    while True:
        print("\n" + "="*50)
        print("FINANCIAL REPORTS")
        print("="*50)

        print("\nOptions:")
        print("1. Daily sales report")
        print("2. Monthly financial summary")
        print("3. Profit & loss statement")
        print("4. Revenue analytics")
        print("5. Expense tracking")
        print("6. Budget management")
        print("7. Tax reports")
        print("8. Financial forecasting")
        print("9. Export financial data")
        print("10. Return to main menu")

        choice = input("Choose an option (1-10): ")

        if choice == '1':
            daily_sales_report()
        elif choice == '2':
            monthly_financial_summary()
        elif choice == '3':
            profit_loss_statement()
        elif choice == '4':
            revenue_analytics()
        elif choice == '5':
            expense_tracking()
        elif choice == '6':
            budget_management()
        elif choice == '7':
            tax_reports()
        elif choice == '8':
            financial_forecasting()
        elif choice == '9':
            export_financial_data()
        elif choice == '10':
            return
        else:
            print("Invalid choice. Please try again.")

def daily_sales_report():
    """Generate daily sales report - FIXED"""
    try:
        report_date = input("Enter date (YYYY-MM-DD) or press Enter for today: ").strip()
        if not report_date:
            report_date = datetime.now().strftime('%Y-%m-%d')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get daily sales data
        cursor.execute('''
            SELECT
                COUNT(*) as total_orders,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_order_value,
                SUM(CASE WHEN payment_method = 'Cash' THEN total_amount ELSE 0 END) as cash_sales,
                SUM(CASE WHEN payment_method LIKE '%Card%' THEN total_amount ELSE 0 END) as card_sales,
                SUM(CASE WHEN payment_method = 'Meal Plan' THEN total_amount ELSE 0 END) as meal_plan_sales
            FROM orders
            WHERE DATE(order_date) = ? AND order_status = 'Completed'
        ''', (report_date,))

        sales_data = cursor.fetchone()

        # Get sales by hour
        cursor.execute('''
            SELECT strftime('%H', order_date) as hour, COUNT(*) as orders, SUM(total_amount) as revenue
            FROM orders
            WHERE DATE(order_date) = ? AND order_status = 'Completed'
            GROUP BY hour
            ORDER BY hour
        ''', (report_date,))

        hourly_data = cursor.fetchall()

        # Get top selling items
        cursor.execute('''
            SELECT mi.name, SUM(oi.quantity) as qty_sold, SUM(oi.quantity * oi.unit_price) as revenue
            FROM order_items oi
            JOIN menu_items mi ON oi.item_id = mi.item_id
            JOIN orders o ON oi.order_id = o.order_id
            WHERE DATE(o.order_date) = ? AND o.order_status = 'Completed'
            GROUP BY mi.item_id, mi.name
            ORDER BY revenue DESC
            LIMIT 10
        ''', (report_date,))

        top_items = cursor.fetchall()

        print(f"\n" + "="*80)
        print(f"DAILY SALES REPORT - {report_date}")
        print("="*80)

        print(f"Total Orders: {sales_data[0]}")
        print(f"Total Revenue: £{sales_data[1]:.2f}" if sales_data[1] else "Total Revenue: £0.00")
        print(f"Average Order Value: £{sales_data[2]:.2f}" if sales_data[2] else "Average Order Value: £0.00")

        print(f"\nPayment Method Breakdown:")
        print(f"Cash Sales: £{sales_data[3]:.2f}")
        print(f"Card Sales: £{sales_data[4]:.2f}")
        print(f"Meal Plan Sales: £{sales_data[5]:.2f}")

        if hourly_data:
            print(f"\nSales by Hour:")
            print("-"*40)
            for hour, orders, revenue in hourly_data:
                print(f"{hour}:00 - {orders} orders, £{revenue:.2f}")

        if top_items:
            print(f"\nTop Selling Items:")
            print("-"*60)
            print(f"{'Item':<30} {'Qty':<6} {'Revenue':<10}")
            print("-"*60)
            for item, qty, revenue in top_items:
                print(f"{item:<30} {qty:<6} £{revenue:<9.2f}")

        print("="*80)

        # Option to update daily sales record
        cursor.execute('SELECT * FROM restaurant_daily_sales WHERE date = ?', (report_date,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO restaurant_daily_sales VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                report_date, sales_data[1] or 0, sales_data[0] or 0, sales_data[2] or 0,
                sales_data[3] or 0, sales_data[4] or 0, sales_data[5] or 0, 0, 0, 0
            ))
            conn.commit()
            print("Daily sales record updated.")

        conn.close()

    except Exception as e:
        logging.error(f"Error in daily_sales_report: {e}")
        print(f"An error occurred: {e}")

def export_payroll_report():
    """Export payroll report to CSV"""
    try:
        start_date = input("Enter start date (YYYY-MM-DD): ")
        end_date = input("Enter end date (YYYY-MM-DD): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT s.staff_id, s.name, s.role, s.hourly_rate,
                   SUM(CASE
                       WHEN ss.actual_end IS NOT NULL AND ss.actual_start IS NOT NULL
                       THEN (strftime('%s', ss.actual_end) - strftime('%s', ss.actual_start)) / 3600.0
                       ELSE (strftime('%s', ss.end_time) - strftime('%s', ss.start_time)) / 3600.0
                   END) as total_hours,
                   COUNT(ss.schedule_id) as days_worked
            FROM restaurant_staff s
            LEFT JOIN restaurant_staff_schedules ss ON s.staff_id = ss.staff_id
                AND ss.date BETWEEN ? AND ?
                AND ss.status != 'Cancelled'
            WHERE s.status = 'Active'
            GROUP BY s.staff_id, s.name, s.role, s.hourly_rate
        ''', (start_date, end_date))

        payroll_data = cursor.fetchall()

        if not payroll_data:
            print("No payroll data found for this period.")
            conn.close()
            return

        filename = f"payroll_report_{start_date}_to_{end_date}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Header
            writer.writerow([
                'Staff ID', 'Name', 'Role', 'Hourly Rate', 'Total Hours',
                'Days Worked', 'Gross Pay', 'Period Start', 'Period End'
            ])

            # Data
            for staff in payroll_data:
                hours = staff[4] or 0
                days = staff[5] or 0
                hourly_rate = staff[3] or 0
                gross_pay = hours * hourly_rate

                writer.writerow([
                    staff[0], staff[1], staff[2], f"£{hourly_rate:.2f}",
                    f"{hours:.1f}", days, f"£{gross_pay:.2f}", start_date, end_date
                ])

        conn.close()
        print(f"Payroll report exported to {filename}")

    except Exception as e:
        logging.error(f"Error in export_payroll_report: {e}")
        print(f"An error occurred: {e}")

def monthly_financial_summary():
    """Generate monthly financial summary"""
    try:
        month = int(input("Enter month (1-12): "))
        year = int(input("Enter year (YYYY): "))

        if month < 1 or month > 12:
            print("Invalid month.")
            return

        # Calculate month dates
        month_start = datetime(year, month, 1)
        if month == 12:
            month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = datetime(year, month + 1, 1) - timedelta(days=1)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get monthly sales data
        cursor.execute('''
            SELECT
                COUNT(*) as total_orders,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_order_value
            FROM orders
            WHERE DATE(order_date) BETWEEN ? AND ? AND order_status = 'Completed'
        ''', (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))

        sales_data = cursor.fetchone()

        # Get expenses for the month
        cursor.execute('''
            SELECT
                SUM(amount) as total_expenses,
                COUNT(*) as expense_count
            FROM restaurant_expenses
            WHERE DATE(expense_date) BETWEEN ? AND ?
        ''', (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))

        expense_data = cursor.fetchone()

        # Get expenses by category
        cursor.execute('''
            SELECT category, SUM(amount) as total
            FROM restaurant_expenses
            WHERE DATE(expense_date) BETWEEN ? AND ?
            GROUP BY category
            ORDER BY total DESC
        ''', (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))

        expense_categories = cursor.fetchall()

        # Calculate profit
        revenue = sales_data[1] or 0
        expenses = expense_data[0] or 0
        profit = revenue - expenses

        print(f"\n" + "="*80)
        print(f"MONTHLY FINANCIAL SUMMARY - {month_start.strftime('%B %Y')}")
        print("="*80)

        print(f"REVENUE:")
        print(f"Total Orders: {sales_data[0]}")
        print(f"Total Revenue: £{revenue:.2f}")
        print(f"Average Order Value: £{sales_data[2]:.2f}" if sales_data[2] else "Average Order Value: £0.00")

        print(f"\nEXPENSES:")
        print(f"Total Expenses: £{expenses:.2f}")
        print(f"Number of Expenses: {expense_data[1]}")

        if expense_categories:
            print(f"\nExpenses by Category:")
            for category, amount in expense_categories:
                print(f"  {category}: £{amount:.2f}")

        print(f"\nPROFITABILITY:")
        print(f"Gross Profit: £{profit:.2f}")
        print(f"Profit Margin: {(profit/revenue*100):.1f}%" if revenue > 0 else "Profit Margin: N/A")

        # Weekly breakdown
        cursor.execute('''
            SELECT
                strftime('%W', order_date) as week,
                COUNT(*) as orders,
                SUM(total_amount) as revenue
            FROM orders
            WHERE DATE(order_date) BETWEEN ? AND ? AND order_status = 'Completed'
            GROUP BY week
            ORDER BY week
        ''', (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))

        weekly_data = cursor.fetchall()

        if weekly_data:
            print(f"\nWeekly Breakdown:")
            print("-"*40)
            for week, orders, rev in weekly_data:
                print(f"Week {week}: {orders} orders, £{rev:.2f}")

        print("="*80)

        conn.close()

    except ValueError:
        print("Invalid month or year.")
    except Exception as e:
        logging.error(f"Error in monthly_financial_summary: {e}")
        print(f"An error occurred: {e}")

def export_expense_report():
    """Export expense report to CSV"""
    try:
        start_date = input("Enter start date (YYYY-MM-DD): ")
        end_date = input("Enter end date (YYYY-MM-DD): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM restaurant_expenses
            WHERE DATE(expense_date) BETWEEN ? AND ?
            ORDER BY expense_date DESC
        ''', (start_date, end_date))

        expenses = cursor.fetchall()

        if not expenses:
            print("No expenses found for this period.")
            conn.close()
            return

        filename = f"expense_report_{start_date}_to_{end_date}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Header
            writer.writerow([
                'Expense ID', 'Category', 'Description', 'Amount', 'Date',
                'Payment Method', 'Vendor', 'Receipt Path', 'Created By',
                'Status', 'Approval Date', 'Approved By'
            ])

            # Data
            for expense in expenses:
                writer.writerow(expense)

        conn.close()
        print(f"Expense report exported to {filename}")

    except Exception as e:
        logging.error(f"Error in export_expense_report: {e}")
        print(f"An error occurred: {e}")

def tax_reports():
    """Tax reporting functionality - FIXED"""
    try:
        print("\n" + "="*50)
        print("TAX REPORTS")
        print("="*50)

        print("\nTax report options:")
        print("1. VAT report")
        print("2. Sales tax summary")
        print("3. Employee tax summary")
        print("4. Annual tax summary")
        print("5. Export tax data")
        print("6. Return to financial menu")

        choice = input("Choose option (1-6): ")

        if choice == '1':
            generate_vat_report()
        elif choice == '2':
            generate_sales_tax_summary()
        elif choice == '3':
            generate_employee_tax_summary()
        elif choice == '4':
            generate_annual_tax_summary()
        elif choice == '5':
            export_tax_data()
        elif choice == '6':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in tax_reports: {e}")
        print(f"An error occurred: {e}")

def generate_vat_report():
    """Generate VAT report - FIXED"""
    try:
        start_date = input("Enter start date (YYYY-MM-DD): ")
        end_date = input("Enter end date (YYYY-MM-DD): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get VAT rate from system settings
        cursor.execute('SELECT setting_value FROM restaurant_system_settings WHERE setting_name = ?', ('tax_rate',))
        vat_rate_result = cursor.fetchone()
        vat_rate = float(vat_rate_result[0]) if vat_rate_result else 0.20  # Default 20%

        # Calculate VAT on sales
        cursor.execute('''
            SELECT SUM(total_amount) as total_sales, SUM(tax_amount) as total_tax
            FROM orders
            WHERE DATE(order_date) BETWEEN ? AND ? AND order_status = 'Completed'
        ''', (start_date, end_date))

        sales_data = cursor.fetchone()
        total_sales = sales_data[0] or 0
        recorded_tax = sales_data[1] or 0

        # Calculate VAT (assuming prices include VAT)
        net_sales = total_sales / (1 + vat_rate)
        vat_on_sales = total_sales - net_sales

        # Get VAT on purchases (expenses)
        cursor.execute('''
            SELECT SUM(amount) as total_expenses
            FROM restaurant_expenses
            WHERE DATE(expense_date) BETWEEN ? AND ?
        ''', (start_date, end_date))

        expenses_result = cursor.fetchone()
        total_expenses = expenses_result[0] or 0
        vat_on_purchases = total_expenses * (vat_rate / (1 + vat_rate))

        # Net VAT due
        net_vat_due = vat_on_sales - vat_on_purchases

        print(f"\n" + "="*60)
        print(f"VAT REPORT ({start_date} to {end_date})")
        print("="*60)
        print(f"VAT Rate: {vat_rate * 100:.1f}%")
        print()
        print("SALES (Output VAT):")
        print(f"  Gross Sales: £{total_sales:.2f}")
        print(f"  Net Sales: £{net_sales:.2f}")
        print(f"  VAT on Sales: £{vat_on_sales:.2f}")
        print()
        print("PURCHASES (Input VAT):")
        print(f"  Total Purchases: £{total_expenses:.2f}")
        print(f"  VAT on Purchases: £{vat_on_purchases:.2f}")
        print()
        print("VAT CALCULATION:")
        print(f"  VAT on Sales: £{vat_on_sales:.2f}")
        print(f"  Less: VAT on Purchases: £{vat_on_purchases:.2f}")
        print(f"  Net VAT Due: £{net_vat_due:.2f}")
        print("="*60)

        if recorded_tax > 0:
            print(f"Note: Recorded tax in orders: £{recorded_tax:.2f}")
            print(f"Difference: £{abs(recorded_tax - vat_on_sales):.2f}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in generate_vat_report: {e}")
        print(f"An error occurred: {e}")

def generate_sales_tax_summary():
    """Generate sales tax summary - FIXED"""
    try:
        month = int(input("Enter month (1-12): "))
        year = int(input("Enter year (YYYY): "))

        # Calculate month dates
        month_start = datetime(year, month, 1)
        if month == 12:
            month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = datetime(year, month + 1, 1) - timedelta(days=1)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Daily sales tax breakdown
        cursor.execute('''
            SELECT DATE(order_date) as sale_date,
                   SUM(total_amount) as daily_sales,
                   SUM(tax_amount) as daily_tax
            FROM orders
            WHERE DATE(order_date) BETWEEN ? AND ? AND order_status = 'Completed'
            GROUP BY DATE(order_date)
            ORDER BY sale_date
        ''', (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))

        daily_data = cursor.fetchall()

        print(f"\n" + "="*60)
        print(f"SALES TAX SUMMARY - {month_start.strftime('%B %Y')}")
        print("="*60)

        if daily_data:
            print(f"{'Date':<12} {'Sales':<12} {'Tax':<12} {'Tax Rate':<10}")
            print("-"*50)

            total_sales = 0
            total_tax = 0

            for date, sales, tax in daily_data:
                tax_rate = (tax / sales * 100) if sales > 0 and tax else 0
                total_sales += sales or 0
                total_tax += tax or 0

                print(f"{date:<12} £{sales or 0:<11.2f} £{tax or 0:<11.2f} {tax_rate:<9.2f}%")

            print("-"*50)
            avg_tax_rate = (total_tax / total_sales * 100) if total_sales > 0 else 0
            print(f"{'TOTALS':<12} £{total_sales:<11.2f} £{total_tax:<11.2f} {avg_tax_rate:<9.2f}%")
        else:
            print("No sales data found for this period.")

        print("="*60)

        conn.close()

    except ValueError:
        print("Invalid month or year.")
    except Exception as e:
        logging.error(f"Error in generate_sales_tax_summary: {e}")
        print(f"An error occurred: {e}")

def financial_forecasting():
    """Financial forecasting and projections - FIXED"""
    try:
        print("\n" + "="*60)
        print("FINANCIAL FORECASTING")
        print("="*60)

        print("\nForecasting options:")
        print("1. Revenue forecast (next 3 months)")
        print("2. Expense forecast (next 3 months)")
        print("3. Cash flow projection")
        print("4. Seasonal analysis")
        print("5. Growth projections")
        print("6. Return to financial menu")

        choice = input("Choose option (1-6): ")

        if choice == '1':
            revenue_forecast()
        elif choice == '2':
            expense_forecast()
        elif choice == '3':
            cash_flow_projection()
        elif choice == '4':
            seasonal_analysis()
        elif choice == '5':
            growth_projections()
        elif choice == '6':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in financial_forecasting: {e}")
        print(f"An error occurred: {e}")

def export_financial_data():
    """Export financial data"""
    try:
        print("\n" + "="*50)
        print("EXPORT FINANCIAL DATA")
        print("="*50)

        print("\nExport options:")
        print("1. Complete financial export")
        print("2. Sales data only")
        print("3. Expense data only")
        print("4. Profit & loss export")

        choice = input("Choose export option (1-4): ")

        start_date = input("Enter start date (YYYY-MM-DD): ")
        end_date = input("Enter end date (YYYY-MM-DD): ")

        if choice == '1':
            export_complete_financial_data(start_date, end_date)
        elif choice == '2':
            export_sales_data(start_date, end_date)
        elif choice == '3':
            export_expense_data(start_date, end_date)
        elif choice == '4':
            export_profit_loss_data(start_date, end_date)
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in export_financial_data: {e}")
        print(f"An error occurred: {e}")

def export_complete_financial_data(start_date, end_date):
    """Export complete financial data - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all financial data
        cursor.execute('''
            SELECT 'REVENUE' as type, order_id as ref_id, order_date as date,
                   total_amount as amount, payment_method as description, customer_id as details
            FROM orders
            WHERE DATE(order_date) BETWEEN ? AND ? AND order_status = 'Completed'
            UNION ALL
            SELECT 'EXPENSE' as type, expense_id as ref_id, expense_date as date,
                   -amount as amount, category as description, vendor as details
            FROM restaurant_expenses
            WHERE DATE(expense_date) BETWEEN ? AND ?
            ORDER BY date
        ''', (start_date, end_date, start_date, end_date))

        financial_data = cursor.fetchall()

        if not financial_data:
            print(f"No financial data found for period {start_date} to {end_date}")
            conn.close()
            return

        filename = f"complete_financial_data_{start_date}_to_{end_date}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Header
            writer.writerow(['Type', 'Reference ID', 'Date', 'Amount', 'Description', 'Details'])

            # Data
            for row in financial_data:
                writer.writerow(row)

        # Summary statistics
        cursor.execute('''
            SELECT
                SUM(CASE WHEN total_amount > 0 THEN total_amount ELSE 0 END) as total_revenue,
                COUNT(CASE WHEN total_amount > 0 THEN 1 END) as revenue_transactions
            FROM orders
            WHERE DATE(order_date) BETWEEN ? AND ? AND order_status = 'Completed'
        ''', (start_date, end_date))

        revenue_stats = cursor.fetchone()

        cursor.execute('''
            SELECT
                SUM(amount) as total_expenses,
                COUNT(*) as expense_transactions
            FROM restaurant_expenses
            WHERE DATE(expense_date) BETWEEN ? AND ?
        ''', (start_date, end_date))

        expense_stats = cursor.fetchone()

        conn.close()

        print(f"✅ Complete financial data exported to {filename}")
        print(f"Period: {start_date} to {end_date}")
        print(f"Total records: {len(financial_data)}")
        print(f"Revenue transactions: {revenue_stats[1]}, Total: £{revenue_stats[0]:,.2f}")
        print(f"Expense transactions: {expense_stats[1]}, Total: £{expense_stats[0]:,.2f}")
        print(f"Net profit: £{(revenue_stats[0] or 0) - (expense_stats[0] or 0):,.2f}")

    except Exception as e:
        logging.error(f"Error in export_complete_financial_data: {e}")
        print(f"An error occurred: {e}")

def export_sales_data(start_date, end_date):
    """Export sales data only - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT o.order_id, o.order_date, o.total_amount, o.tax_amount,
                   o.payment_method, c.name as customer_name, o.order_status
            FROM orders o
            LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
            WHERE DATE(o.order_date) BETWEEN ? AND ? AND o.order_status = 'Completed'
            ORDER BY o.order_date
        ''', (start_date, end_date))

        sales_data = cursor.fetchall()

        if not sales_data:
            print(f"No sales data found for period {start_date} to {end_date}")
            conn.close()
            return

        filename = f"sales_data_{start_date}_to_{end_date}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Header
            writer.writerow(['Order ID', 'Date/Time', 'Total Price', 'Tax Amount',
                           'Payment Method', 'Customer', 'Status'])

            # Data
            for row in sales_data:
                writer.writerow(row)

        # Calculate summary
        total_sales = sum(row[2] for row in sales_data)
        total_tax = sum(row[3] for row in sales_data if row[3])

        conn.close()

        print(f"✅ Sales data exported to {filename}")
        print(f"Period: {start_date} to {end_date}")
        print(f"Total records: {len(sales_data)}")
        print(f"Total sales: £{total_sales:,.2f}")
        print(f"Total tax: £{total_tax:,.2f}")

    except Exception as e:
        logging.error(f"Error in export_sales_data: {e}")
        print(f"An error occurred: {e}")
