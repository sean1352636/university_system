from __future__ import annotations

import csv
import logging

from university_system.modules.core.services.restaurant_misc.restaurant_context import get_db_connection

def generate_employee_tax_summary():
    """Generate employee tax summary - FIXED"""
    try:
        year = int(input("Enter year (YYYY): "))

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get staff payroll data for the year
        cursor.execute('''
            SELECT s.staff_id, s.name, s.role, s.hourly_rate,
                   SUM(CASE 
                       WHEN ss.actual_end IS NOT NULL AND ss.actual_start IS NOT NULL 
                       THEN (strftime('%s', ss.actual_end) - strftime('%s', ss.actual_start)) / 3600.0
                       ELSE (strftime('%s', ss.end_time) - strftime('%s', ss.start_time)) / 3600.0
                   END) as total_hours
            FROM restaurant_staff s
            LEFT JOIN restaurant_staff_schedules ss ON s.staff_id = ss.staff_id
                AND strftime('%Y', ss.date) = ?
                AND ss.status != 'Cancelled'
            WHERE s.status = 'Active'
            GROUP BY s.staff_id, s.name, s.role, s.hourly_rate
            ORDER BY s.name
        ''', (str(year),))

        staff_data = cursor.fetchall()

        if not staff_data:
            print(f"No staff data found for {year}.")
            conn.close()
            return

        print(f"\n" + "="*100)
        print(f"EMPLOYEE TAX SUMMARY - {year}")
        print("="*100)
        print(f"{'Staff ID':<10} {'Name':<20} {'Role':<15} {'Hours':<8} {'Gross Pay':<12} {'Est. Tax':<12}")
        print("-"*100)

        total_gross_pay = 0
        total_estimated_tax = 0

        # Simple tax estimation (basic rate 20% on earnings over £12,570)
        personal_allowance = 12570
        basic_rate = 0.20

        for staff in staff_data:
            hours = staff[4] or 0
            hourly_rate = staff[3] or 0
            gross_pay = hours * hourly_rate

            # Estimate annual tax (simplified)
            taxable_income = max(0, gross_pay - personal_allowance)
            estimated_tax = taxable_income * basic_rate

            total_gross_pay += gross_pay
            total_estimated_tax += estimated_tax

            print(f"{staff[0]:<10} {staff[1]:<20} {staff[2]:<15} {hours:<8.0f} £{gross_pay:<11.2f} £{estimated_tax:<11.2f}")

        print("-"*100)
        print(f"{'TOTALS':<65} £{total_gross_pay:<11.2f} £{total_estimated_tax:<11.2f}")
        print("="*100)

        print(f"\nSUMMARY:")
        print(f"Total Staff: {len(staff_data)}")
        print(f"Total Gross Pay: £{total_gross_pay:,.2f}")
        print(f"Estimated Total Tax: £{total_estimated_tax:,.2f}")
        print(f"Average Tax Rate: {(total_estimated_tax/total_gross_pay*100):.1f}%" if total_gross_pay > 0 else "Average Tax Rate: 0%")

        print(f"\nNote: Tax calculations are estimates based on basic rate (20%) and personal allowance (£{personal_allowance:,})")
        print("Consult with an accountant for accurate tax calculations.")

        conn.close()

    except ValueError:
        print("Invalid year.")
    except Exception as e:
        logging.error(f"Error in generate_employee_tax_summary: {e}")
        print(f"An error occurred: {e}")

def generate_annual_tax_summary():
    """Generate annual tax summary - FIXED"""
    try:
        year = int(input("Enter year (YYYY): "))

        conn = get_db_connection()
        cursor = conn.cursor()

        # Annual sales and VAT
        cursor.execute('''
            SELECT 
                SUM(total_price) as total_sales,
                SUM(tax_amount) as total_tax,
                COUNT(*) as total_orders
            FROM restaurant_orders
            WHERE strftime('%Y', order_time) = ? AND status = 'Completed'
        ''', (str(year),))

        sales_data = cursor.fetchone()

        # Annual expenses
        cursor.execute('''
            SELECT 
                SUM(amount) as total_expenses,
                COUNT(*) as expense_count
            FROM restaurant_expenses
            WHERE strftime('%Y', expense_date) = ?
        ''', (str(year),))

        expense_data = cursor.fetchone()

        # Monthly breakdown
        cursor.execute('''
            SELECT 
                strftime('%m', order_time) as month,
                SUM(total_price) as monthly_sales,
                SUM(tax_amount) as monthly_tax
            FROM restaurant_orders
            WHERE strftime('%Y', order_time) = ? AND status = 'Completed'
            GROUP BY strftime('%m', order_time)
            ORDER BY month
        ''', (str(year),))

        monthly_data = cursor.fetchall()

        print(f"\n" + "="*80)
        print(f"ANNUAL TAX SUMMARY - {year}")
        print("="*80)

        # Overview
        total_sales = sales_data[0] or 0
        total_tax = sales_data[1] or 0
        total_orders = sales_data[2] or 0
        total_expenses = expense_data[0] or 0

        print(f"ANNUAL OVERVIEW:")
        print(f"Total Sales: £{total_sales:,.2f}")
        print(f"Total Tax Collected: £{total_tax:,.2f}")
        print(f"Total Orders: {total_orders:,}")
        print(f"Total Expenses: £{total_expenses:,.2f}")
        print(f"Net Income: £{total_sales - total_expenses:,.2f}")

        # Monthly breakdown
        if monthly_data:
            print(f"\nMONTHLY BREAKDOWN:")
            print("-"*50)
            print(f"{'Month':<10} {'Sales':<15} {'Tax':<12} {'Tax Rate':<10}")
            print("-"*50)

            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

            for month_num, sales, tax in monthly_data:
                month_name = months[int(month_num) - 1]
                tax_rate = (tax / sales * 100) if sales > 0 and tax else 0
                print(f"{month_name:<10} £{sales:<14,.2f} £{tax or 0:<11.2f} {tax_rate:<9.2f}%")

        # Tax compliance notes
        print(f"\nTAX COMPLIANCE NOTES:")
        print("-"*30)
        print("• VAT registration required if annual turnover > £85,000")
        print("• Keep all receipts and invoices for 6 years")
        print("• File VAT returns quarterly if VAT registered")
        print("• Consider professional tax advice for complex situations")

        if total_sales > 85000:
            print("⚠️  Annual turnover exceeds VAT registration threshold")

        conn.close()

    except ValueError:
        print("Invalid year.")
    except Exception as e:
        logging.error(f"Error in generate_annual_tax_summary: {e}")
        print(f"An error occurred: {e}")

def export_tax_data():
    """Export tax data - FIXED"""
    try:
        start_date = input("Enter start date (YYYY-MM-DD): ")
        end_date = input("Enter end date (YYYY-MM-DD): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Export sales data with tax
        cursor.execute('''
            SELECT order_id, order_time, total_price, tax_amount, payment_method, customer_id
            FROM restaurant_orders
            WHERE DATE(order_time) BETWEEN ? AND ? AND status = 'Completed'
            ORDER BY order_time
        ''', (start_date, end_date))

        sales_data = cursor.fetchall()

        # Export expense data
        cursor.execute('''
            SELECT expense_id, expense_date, category, description, amount, vendor
            FROM restaurant_expenses
            WHERE DATE(expense_date) BETWEEN ? AND ?
            ORDER BY expense_date
        ''', (start_date, end_date))

        expense_data = cursor.fetchall()

        # Create sales export
        sales_filename = f"tax_sales_data_{start_date}_to_{end_date}.csv"
        with open(sales_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Order ID', 'Date', 'Total Price', 'Tax Amount', 'Payment Method', 'Customer ID'])
            for row in sales_data:
                writer.writerow(row)

        # Create expenses export
        expenses_filename = f"tax_expenses_data_{start_date}_to_{end_date}.csv"
        with open(expenses_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Expense ID', 'Date', 'Category', 'Description', 'Amount', 'Vendor'])
            for row in expense_data:
                writer.writerow(row)

        print(f"\n✅ Tax data exported successfully!")
        print(f"Sales data: {sales_filename}")
        print(f"Expenses data: {expenses_filename}")
        print(f"Period: {start_date} to {end_date}")
        print(f"Sales records: {len(sales_data)}")
        print(f"Expense records: {len(expense_data)}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in export_tax_data: {e}")
        print(f"An error occurred: {e}")

def export_expense_data(start_date, end_date):
    """Export expense data only - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT expense_id, expense_date, category, description, amount, 
                   payment_method, vendor, status
            FROM restaurant_expenses
            WHERE DATE(expense_date) BETWEEN ? AND ?
            ORDER BY expense_date
        ''', (start_date, end_date))

        expense_data = cursor.fetchall()

        if not expense_data:
            print(f"No expense data found for period {start_date} to {end_date}")
            conn.close()
            return

        filename = f"expense_data_{start_date}_to_{end_date}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Header
            writer.writerow(['Expense ID', 'Date', 'Category', 'Description', 'Amount', 
                           'Payment Method', 'Vendor', 'Status'])

            # Data
            for row in expense_data:
                writer.writerow(row)

        # Calculate summary by category
        cursor.execute('''
            SELECT category, SUM(amount) as total_amount, COUNT(*) as count
            FROM restaurant_expenses
            WHERE DATE(expense_date) BETWEEN ? AND ?
            GROUP BY category
            ORDER BY total_amount DESC
        ''', (start_date, end_date))

        category_summary = cursor.fetchall()
        total_expenses = sum(row[2] for row in expense_data)

        conn.close()

        print(f"✅ Expense data exported to {filename}")
        print(f"Period: {start_date} to {end_date}")
        print(f"Total records: {len(expense_data)}")
        print(f"Total expenses: £{total_expenses:,.2f}")

        if category_summary:
            print(f"\nExpense breakdown by category:")
            for category, amount, count in category_summary:
                print(f"  {category}: £{amount:,.2f} ({count} transactions)")

    except Exception as e:
        logging.error(f"Error in export_expense_data: {e}")
        print(f"An error occurred: {e}")

def export_profit_loss_data(start_date, end_date):
    """Export profit & loss data - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get revenue data
        cursor.execute('''
            SELECT SUM(total_price) as total_revenue, COUNT(*) as order_count
            FROM restaurant_orders
            WHERE DATE(order_time) BETWEEN ? AND ? AND status = 'Completed'
        ''', (start_date, end_date))

        revenue_data = cursor.fetchone()

        # Get expense data by category
        cursor.execute('''
            SELECT category, SUM(amount) as total_amount
            FROM restaurant_expenses
            WHERE DATE(expense_date) BETWEEN ? AND ?
            GROUP BY category
            ORDER BY total_amount DESC
        ''', (start_date, end_date))

        expense_categories = cursor.fetchall()

        # Get cost of goods sold
        cursor.execute('''
            SELECT SUM(oi.quantity * mi.cost_price) as cogs
            FROM restaurant_order_items oi
            JOIN menu_items mi ON oi.item_id = mi.item_id
            JOIN restaurant_orders o ON oi.order_id = o.order_id
            WHERE DATE(o.order_time) BETWEEN ? AND ? AND o.status = 'Completed'
            AND mi.cost_price IS NOT NULL
        ''', (start_date, end_date))

        cogs_data = cursor.fetchone()

        # Create P&L export
        filename = f"profit_loss_data_{start_date}_to_{end_date}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # P&L Structure
            writer.writerow(['PROFIT & LOSS STATEMENT', f"{start_date} to {end_date}"])
            writer.writerow([])

            # Revenue
            writer.writerow(['REVENUE'])
            writer.writerow(['Sales Revenue', revenue_data[0] or 0])
            writer.writerow([])

            # Cost of Goods Sold
            writer.writerow(['COST OF GOODS SOLD'])
            writer.writerow(['Direct Costs', cogs_data[0] or 0])
            gross_profit = (revenue_data[0] or 0) - (cogs_data[0] or 0)
            writer.writerow(['Gross Profit', gross_profit])
            writer.writerow([])

            # Operating Expenses
            writer.writerow(['OPERATING EXPENSES'])
            total_expenses = 0
            for category, amount in expense_categories:
                writer.writerow([category, amount])
                total_expenses += amount

            writer.writerow(['Total Operating Expenses', total_expenses])
            writer.writerow([])

            # Net Profit
            net_profit = gross_profit - total_expenses
            writer.writerow(['NET PROFIT', net_profit])
            writer.writerow([])

            # Metrics
            writer.writerow(['KEY METRICS'])
            if revenue_data[0] and revenue_data[0] > 0:
                gross_margin = (gross_profit / revenue_data[0]) * 100
                net_margin = (net_profit / revenue_data[0]) * 100
                writer.writerow(['Gross Margin %', f"{gross_margin:.2f}%"])
                writer.writerow(['Net Margin %', f"{net_margin:.2f}%"])

            writer.writerow(['Order Count', revenue_data[1] or 0])
            if revenue_data[1] and revenue_data[1] > 0:
                avg_order_value = (revenue_data[0] or 0) / revenue_data[1]
                writer.writerow(['Average Order Value', f"£{avg_order_value:.2f}"])

        conn.close()

        print(f"✅ Profit & Loss data exported to {filename}")
        print(f"Period: {start_date} to {end_date}")
        print(f"Revenue: £{revenue_data[0] or 0:,.2f}")
        print(f"Total Expenses: £{total_expenses:,.2f}")
        print(f"Net Profit: £{net_profit:,.2f}")

    except Exception as e:
        logging.error(f"Error in export_profit_loss_data: {e}")
        print(f"An error occurred: {e}")
