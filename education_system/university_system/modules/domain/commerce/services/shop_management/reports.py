import os
from datetime import datetime, timedelta
import csv
import pandas as pd
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_read, log_export
from education_system.university_system.modules.domain.commerce.services.shop_management import config
from education_system.university_system.modules.domain.commerce.services.shop_management.inventory import get_low_stock_alert
from education_system.university_system.modules.domain.commerce.services.shop_management.products import get_popular_products


@log_read(module="shop", description="Generating daily sales report")
def generate_daily_sales_report():
    """Generate a daily sales report"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to generate reports.")
        return

    if not config.auth.check_permission('generate_sales_reports'):
        print("You don't have permission to generate sales reports.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get date for report
        print("\nDaily Sales Report")
        print("------------------")

        default_date = datetime.now().strftime('%Y-%m-%d')
        date_input = input(f"Enter date (YYYY-MM-DD) [default: {default_date}]: ").strip()

        if not date_input:
            date_input = default_date

        try:
            # Validate date
            report_date = datetime.strptime(date_input, '%Y-%m-%d')
            date_str = report_date.strftime('%Y-%m-%d')

            # Get sales for this date
            cursor.execute(
                '''
                SELECT t.*, u.username
                FROM transactions t
                LEFT JOIN users u ON t.customer_id = u.id
                WHERE t.source_type = 'shop' AND t.created_at LIKE ?
                ORDER BY t.created_at
                ''',
                [f"{date_str}%"]
            )

            transactions = cursor.fetchall()

            if not transactions:
                print(f"No sales found for {date_str}.")
                conn.close()
                return

            # Calculate totals
            total_sales = sum(t['total_amount'] for t in transactions)
            transaction_count = len(transactions)
            avg_transaction = total_sales / transaction_count

            # Get payment method breakdown
            payment_methods = {}
            for t in transactions:
                method = t['payment_method']
                if method not in payment_methods:
                    payment_methods[method] = {'count': 0, 'amount': 0}

                payment_methods[method]['count'] += 1
                payment_methods[method]['amount'] += t['total_amount']

            # Get hourly breakdown
            hourly_sales = {}
            for t in transactions:
                hour = t['created_at'].split()[1].split(':')[0]
                if hour not in hourly_sales:
                    hourly_sales[hour] = {'count': 0, 'amount': 0}

                hourly_sales[hour]['count'] += 1
                hourly_sales[hour]['amount'] += t['total_amount']

            # Display report
            print(f"\nSales Report for {date_str}")
            print("=" * 50)

            print(f"Total Sales: £{total_sales:.2f}")
            print(f"Number of Transactions: {transaction_count}")
            print(f"Average Transaction Value: £{avg_transaction:.2f}")

            print("\nPayment Method Breakdown:")
            print(f"{'Method':<20} {'Transactions':<15} {'Amount':<15} {'Percent'}")
            print("-" * 65)

            for method, data in payment_methods.items():
                percent = (data['amount'] / total_sales) * 100
                print(f"{method:<20} {data['count']:<15} £{data['amount']:<15.2f} {percent:.1f}%")

            print("\nHourly Breakdown:")
            print(f"{'Hour':<10} {'Transactions':<15} {'Amount':<15} {'Percent'}")
            print("-" * 55)

            # Sort by hour
            for hour in sorted(hourly_sales.keys()):
                data = hourly_sales[hour]
                percent = (data['amount'] / total_sales) * 100
                print(f"{hour}:00{'':<7} {data['count']:<15} £{data['amount']:<15.2f} {percent:.1f}%")

            # Get product details for the day
            print("\nTop Products Sold:")
            cursor.execute(
                '''
                SELECT ti.product_id, p.name, SUM(ti.quantity) as total_qty,
                       SUM(ti.subtotal) as total_amount
                FROM shop_transaction_items ti
                JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
                JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
                WHERE t.created_at LIKE ?
                GROUP BY ti.product_id
                ORDER BY total_amount DESC
                LIMIT 10
                ''',
                [f"{date_str}%"]
            )

            top_products = cursor.fetchall()

            if top_products:
                print(f"{'Product ID':<12} {'Name':<30} {'Quantity':<10} {'Total':<12} {'% of Sales'}")
                print("-" * 75)

                for product in top_products:
                    percent = (product['total_amount'] / total_sales) * 100
                    print(f"{product['product_id']:<12} {product['name'][:28]:<30} {product['total_qty']:<10} £{product['total_amount']:<12.2f} {percent:.1f}%")

            conn.close()
            input("\nPress Enter to continue...")

        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
            conn.close()
            return

    except sqlite3.Error as e:
        print(f"Database error generating report: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error generating report: {e}")
        if 'conn' in locals():
            conn.close()


@log_read(module="shop", description="Generating weekly sales report")
def generate_weekly_sales_report():
    """Generate a weekly sales report"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to generate reports.")
        return

    if not config.auth.check_permission('generate_sales_reports'):
        print("You don't have permission to generate sales reports.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get week for report
        print("\nWeekly Sales Report")
        print("------------------")

        # Calculate current week's start and end dates
        today = datetime.now()
        # Monday as start of week (0 = Monday in weekday())
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        default_start = start_of_week.strftime('%Y-%m-%d')
        default_end = end_of_week.strftime('%Y-%m-%d')

        print(f"Default week: {default_start} to {default_end}")

        custom_week = input("Use custom date range? (y/n): ").strip().lower()

        if custom_week == 'y':
            start_input = input("Enter start date (YYYY-MM-DD): ").strip()
            end_input = input("Enter end date (YYYY-MM-DD): ").strip()

            try:
                start_date = datetime.strptime(start_input, '%Y-%m-%d')
                end_date = datetime.strptime(end_input, '%Y-%m-%d')

                if end_date < start_date:
                    print("End date must be after start date. Using default week.")
                    start_date = start_of_week
                    end_date = end_of_week
            except ValueError:
                print("Invalid date format. Using default week.")
                start_date = start_of_week
                end_date = end_of_week
        else:
            start_date = start_of_week
            end_date = end_of_week

        # Format for database queries
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        # Get sales for this week
        cursor.execute(
            '''
            SELECT t.*
            FROM transactions t
            WHERE t.source_type = 'shop' AND t.created_at BETWEEN ? AND ?
            ORDER BY t.created_at
            ''',
            [f"{start_str} 00:00:00", f"{end_str} 23:59:59"]
        )

        transactions = cursor.fetchall()

        if not transactions:
            print(f"No sales found for the period {start_str} to {end_str}.")
            conn.close()
            return

        # Calculate totals
        total_sales = sum(t['total_amount'] for t in transactions)
        transaction_count = len(transactions)
        avg_transaction = total_sales / transaction_count

        # Get daily breakdown
        daily_sales = {}
        for t in transactions:
            day = t['created_at'].split()[0]  # YYYY-MM-DD
            if day not in daily_sales:
                daily_sales[day] = {'count': 0, 'amount': 0}

            daily_sales[day]['count'] += 1
            daily_sales[day]['amount'] += t['total_amount']

        # Display report
        print(f"\nWeekly Sales Report: {start_str} to {end_str}")
        print("=" * 50)

        print(f"Total Sales: £{total_sales:.2f}")
        print(f"Number of Transactions: {transaction_count}")
        print(f"Average Transaction Value: £{avg_transaction:.2f}")
        print(f"Average Daily Sales: £{total_sales / len(daily_sales):.2f}")

        print("\nDaily Breakdown:")
        print(f"{'Date':<12} {'Day':<10} {'Transactions':<15} {'Amount':<15} {'% of Total'}")
        print("-" * 65)

        # Sort by date
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            day_name = current_date.strftime('%A')

            if date_str in daily_sales:
                data = daily_sales[date_str]
                percent = (data['amount'] / total_sales) * 100
                print(f"{date_str:<12} {day_name:<10} {data['count']:<15} £{data['amount']:<15.2f} {percent:.1f}%")
            else:
                print(f"{date_str:<12} {day_name:<10} {'0':<15} £{'0.00':<15} {'0.0'}%")

            current_date += timedelta(days=1)

        # Get top categories
        cursor.execute(
            '''
            SELECT p.category, SUM(ti.quantity) as total_qty,
                   SUM(ti.subtotal) as total_amount,
                   COUNT(DISTINCT ti.transaction_id) as transaction_count
            FROM shop_transaction_items ti
            JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
            WHERE t.created_at BETWEEN ? AND ?
            GROUP BY p.category
            ORDER BY total_amount DESC
            ''',
            [f"{start_str} 00:00:00", f"{end_str} 23:59:59"]
        )

        categories = cursor.fetchall()

        if categories:
            print("\nSales by Category:")
            print(f"{'Category':<20} {'Transactions':<15} {'Items Sold':<12} {'Total':<12} {'% of Sales'}")
            print("-" * 70)

            for category in categories:
                percent = (category['total_amount'] / total_sales) * 100
                print(f"{category['category']:<20} {category['transaction_count']:<15} {category['total_qty']:<12} £{category['total_amount']:<12.2f} {percent:.1f}%")

        # Get top products
        cursor.execute(
            '''
            SELECT ti.product_id, p.name, p.category, SUM(ti.quantity) as total_qty,
                   SUM(ti.subtotal) as total_amount
            FROM shop_transaction_items ti
            JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
            WHERE t.created_at BETWEEN ? AND ?
            GROUP BY ti.product_id
            ORDER BY total_amount DESC
            LIMIT 10
            ''',
            [f"{start_str} 00:00:00", f"{end_str} 23:59:59"]
        )

        top_products = cursor.fetchall()

        if top_products:
            print("\nTop 10 Products:")
            print(f"{'Product ID':<12} {'Name':<25} {'Category':<15} {'Quantity':<10} {'Total':<12} {'% of Sales'}")
            print("-" * 90)

            for product in top_products:
                percent = (product['total_amount'] / total_sales) * 100
                print(f"{product['product_id']:<12} {product['name'][:23]:<25} {product['category'][:13]:<15} {product['total_qty']:<10} £{product['total_amount']:<12.2f} {percent:.1f}%")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error generating report: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error generating report: {e}")
        if 'conn' in locals():
            conn.close()


@log_read(module="shop", description="Generating monthly sales report")
def generate_monthly_sales_report():
    """Generate a monthly sales report"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to generate reports.")
        return

    if not config.auth.check_permission('generate_sales_reports'):
        print("You don't have permission to generate sales reports.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get month for report
        print("\nMonthly Sales Report")
        print("-------------------")

        today = datetime.now()
        default_year = today.year
        default_month = today.month

        year_input = input(f"Enter year [default: {default_year}]: ").strip()
        month_input = input(f"Enter month (1-12) [default: {default_month}]: ").strip()

        if not year_input:
            year = default_year
        else:
            try:
                year = int(year_input)
                if year < 2000 or year > 2100:
                    print(f"Invalid year. Using default ({default_year}).")
                    year = default_year
            except ValueError:
                print(f"Invalid year. Using default ({default_year}).")
                year = default_year

        if not month_input:
            month = default_month
        else:
            try:
                month = int(month_input)
                if month < 1 or month > 12:
                    print(f"Invalid month. Using default ({default_month}).")
                    month = default_month
            except ValueError:
                print(f"Invalid month. Using default ({default_month}).")
                month = default_month

        # Get the first and last day of the month
        first_day = datetime(year, month, 1)

        # Last day calculation (go to next month, then subtract one day)
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)

        month_name = first_day.strftime('%B')
        first_day_str = first_day.strftime('%Y-%m-%d')
        last_day_str = last_day.strftime('%Y-%m-%d')

        # Get sales for this month
        cursor.execute(
            '''
            SELECT t.*
            FROM transactions t
            WHERE t.source_type = 'shop' AND t.created_at BETWEEN ? AND ?
            ORDER BY t.created_at
            ''',
            [f"{first_day_str} 00:00:00", f"{last_day_str} 23:59:59"]
        )

        transactions = cursor.fetchall()

        if not transactions:
            print(f"No sales found for {month_name} {year}.")
            conn.close()
            return

        # Calculate totals
        total_sales = sum(t['total_amount'] for t in transactions)
        transaction_count = len(transactions)
        avg_transaction = total_sales / transaction_count

        # Get daily breakdown
        daily_sales = {}
        for t in transactions:
            day = t['created_at'].split()[0]  # YYYY-MM-DD
            if day not in daily_sales:
                daily_sales[day] = {'count': 0, 'amount': 0}

            daily_sales[day]['count'] += 1
            daily_sales[day]['amount'] += t['total_amount']

        # Group by week
        weeks = {}
        current_day = first_day
        week_num = 1

        while current_day <= last_day:
            week_key = f"Week {week_num}"
            week_start = current_day

            # Days until Sunday (or end of month)
            days_in_week = min((6 - current_day.weekday()) % 7 + 1, (last_day - current_day).days + 1)
            week_end = current_day + timedelta(days=days_in_week - 1)

            weeks[week_key] = {
                'start': week_start.strftime('%Y-%m-%d'),
                'end': week_end.strftime('%Y-%m-%d'),
                'amount': 0,
                'count': 0
            }

            # Move to next week
            current_day = week_end + timedelta(days=1)
            week_num += 1

        # Assign sales to weeks
        for day, data in daily_sales.items():
            for week_key, week_data in weeks.items():
                if week_data['start'] <= day <= week_data['end']:
                    weeks[week_key]['amount'] += data['amount']
                    weeks[week_key]['count'] += data['count']
                    break

        # Display report
        print(f"\nMonthly Sales Report: {month_name} {year}")
        print("=" * 50)

        print(f"Period: {first_day_str} to {last_day_str}")
        print(f"Total Sales: £{total_sales:.2f}")
        print(f"Number of Transactions: {transaction_count}")
        print(f"Average Transaction Value: £{avg_transaction:.2f}")

        # Weekly breakdown
        print("\nWeekly Breakdown:")
        print(f"{'Week':<10} {'Period':<25} {'Transactions':<15} {'Amount':<15} {'% of Total'}")
        print("-" * 80)

        for week_key, data in weeks.items():
            period = f"{data['start']} to {data['end']}"
            percent = (data['amount'] / total_sales) * 100 if total_sales > 0 else 0
            print(f"{week_key:<10} {period:<25} {data['count']:<15} £{data['amount']:<15.2f} {percent:.1f}%")

        # Payment method breakdown
        cursor.execute(
            '''
            SELECT payment_method, COUNT(*) as count, SUM(total_amount) as amount
            FROM transactions
            WHERE source_type = 'shop' AND created_at BETWEEN ? AND ?
            GROUP BY payment_method
            ORDER BY amount DESC
            ''',
            [f"{first_day_str} 00:00:00", f"{last_day_str} 23:59:59"]
        )

        payment_methods = cursor.fetchall()

        if payment_methods:
            print("\nPayment Method Breakdown:")
            print(f"{'Method':<20} {'Transactions':<15} {'Amount':<15} {'% of Total'}")
            print("-" * 70)

            for method in payment_methods:
                percent = (method['amount'] / total_sales) * 100
                print(f"{method['payment_method']:<20} {method['count']:<15} £{method['amount']:<15.2f} {percent:.1f}%")

        # Category breakdown
        cursor.execute(
            '''
            SELECT p.category, COUNT(DISTINCT t.source_transaction_id) as transaction_count,
                   SUM(ti.quantity) as quantity, SUM(ti.subtotal) as amount
            FROM shop_transaction_items ti
            JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
            WHERE t.created_at BETWEEN ? AND ?
            GROUP BY p.category
            ORDER BY amount DESC
            ''',
            [f"{first_day_str} 00:00:00", f"{last_day_str} 23:59:59"]
        )

        categories = cursor.fetchall()

        if categories:
            print("\nSales by Category:")
            print(f"{'Category':<20} {'Transactions':<15} {'Items Sold':<12} {'Amount':<15} {'% of Total'}")
            print("-" * 75)

            for category in categories:
                percent = (category['amount'] / total_sales) * 100
                print(f"{category['category']:<20} {category['transaction_count']:<15} {category['quantity']:<12} £{category['amount']:<15.2f} {percent:.1f}%")

        # Top products
        cursor.execute(
            '''
            SELECT p.source_product_id as product_id, p.name, SUM(ti.quantity) as quantity, SUM(ti.subtotal) as amount
            FROM shop_transaction_items ti
            JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
            WHERE t.created_at BETWEEN ? AND ?
            GROUP BY p.source_product_id
            ORDER BY amount DESC
            LIMIT 10
            ''',
            [f"{first_day_str} 00:00:00", f"{last_day_str} 23:59:59"]
        )

        top_products = cursor.fetchall()

        if top_products:
            print("\nTop 10 Products:")
            print(f"{'Product ID':<12} {'Name':<30} {'Quantity':<10} {'Amount':<15} {'% of Total'}")
            print("-" * 80)

            for product in top_products:
                percent = (product['amount'] / total_sales) * 100
                print(f"{product['product_id']:<12} {product['name'][:28]:<30} {product['quantity']:<10} £{product['amount']:<15.2f} {percent:.1f}%")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error generating report: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error generating report: {e}")
        if 'conn' in locals():
            conn.close()


@log_read(module="shop", description="Generating product sales report")
def generate_product_sales_report():
    """Generate a sales report for a specific product"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to generate reports.")
        return

    if not config.auth.check_permission('generate_sales_reports'):
        print("You don't have permission to generate sales reports.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print("\nProduct Sales Report")
        print("-------------------")

        # Get product ID
        product_id = input("Enter product ID (or leave blank to see all products): ").strip().upper()

        if product_id:
            # Check if product exists
            cursor.execute(
                "SELECT * FROM products WHERE source_type = 'shop' AND source_product_id = ?",
                [product_id]
            )
            product = cursor.fetchone()

            if not product:
                print(f"Product {product_id} not found.")
                conn.close()
                return

            # Get date range
            print("\nSelect date range:")
            print("1. Last 7 days")
            print("2. Last 30 days")
            print("3. Last 90 days")
            print("4. Year to date")
            print("5. All time")
            print("6. Custom range")

            range_choice = input("Select option (1-6): ").strip()

            today = datetime.now()

            if range_choice == '1':
                start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
            elif range_choice == '2':
                start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
            elif range_choice == '3':
                start_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
            elif range_choice == '4':
                start_date = f"{today.year}-01-01"
                end_date = today.strftime('%Y-%m-%d')
            elif range_choice == '5':
                start_date = "2000-01-01"  # Far past
                end_date = today.strftime('%Y-%m-%d')
            elif range_choice == '6':
                start_input = input("Enter start date (YYYY-MM-DD): ").strip()
                end_input = input("Enter end date (YYYY-MM-DD): ").strip()

                try:
                    # Validate dates
                    start_date = datetime.strptime(start_input, '%Y-%m-%d').strftime('%Y-%m-%d')
                    end_date = datetime.strptime(end_input, '%Y-%m-%d').strftime('%Y-%m-%d')
                except ValueError:
                    print("Invalid date format. Using last 30 days.")
                    start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                    end_date = today.strftime('%Y-%m-%d')
            else:
                print("Invalid choice. Using last 30 days.")
                start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')

            # Get sales for this product
            cursor.execute(
                '''
                SELECT ti.transaction_id, t.created_at, t.payment_method,
                       ti.quantity, ti.price_per_item, ti.subtotal
                FROM shop_transaction_items ti
                JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
                WHERE ti.product_id = ? AND
                      t.created_at BETWEEN ? AND ?
                ORDER BY t.created_at DESC
                ''',
                [product_id, f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            )

            sales = cursor.fetchall()

            if not sales:
                print(f"No sales found for product {product_id} in the selected period.")
                conn.close()
                return

            # Display product details
            print(f"\nProduct: {product['name']} ({product_id})")
            print(f"Category: {product['category']}")
            print(f"Current Price: £{product['price']:.2f}")
            print(f"Status: {'Active' if product['is_active'] else 'Inactive'}")

            # Calculate sales totals
            total_quantity = sum(s['quantity'] for s in sales)
            total_revenue = sum(s['subtotal'] for s in sales)
            transaction_count = len(set(s['transaction_id'] for s in sales))

            print(f"\nPeriod: {start_date} to {end_date}")
            print(f"Total Units Sold: {total_quantity}")
            print(f"Total Revenue: £{total_revenue:.2f}")
            print(f"Number of Transactions: {transaction_count}")
            print(f"Average Price: £{total_revenue / total_quantity:.2f}")

            # Monthly breakdown if range is long enough
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')

                # If period is 60+ days, show monthly breakdown
                if (end - start).days >= 60:
                    monthly_sales = {}
                    for sale in sales:
                        month_key = sale['created_at'][:7]  # YYYY-MM
                        if month_key not in monthly_sales:
                            monthly_sales[month_key] = {'quantity': 0, 'revenue': 0}

                        monthly_sales[month_key]['quantity'] += sale['quantity']
                        monthly_sales[month_key]['revenue'] += sale['subtotal']

                    print("\nMonthly Breakdown:")
                    print(f"{'Month':<10} {'Units Sold':<12} {'Revenue':<15} {'% of Total'}")
                    print("-" * 55)

                    for month_key in sorted(monthly_sales.keys()):
                        data = monthly_sales[month_key]
                        month_label = datetime.strptime(month_key, '%Y-%m').strftime('%b %Y')
                        percent = (data['revenue'] / total_revenue) * 100

                        print(f"{month_label:<10} {data['quantity']:<12} £{data['revenue']:<15.2f} {percent:.1f}%")

                # If period is less than 60 days, show weekly breakdown
                elif (end - start).days >= 14:
                    weekly_sales = {}
                    for sale in sales:
                        sale_date = datetime.strptime(sale['created_at'].split()[0], '%Y-%m-%d')
                        week_num = sale_date.isocalendar()[1]  # ISO week number
                        week_key = f"{sale_date.year}-W{week_num:02d}"

                        if week_key not in weekly_sales:
                            weekly_sales[week_key] = {'quantity': 0, 'revenue': 0}

                        weekly_sales[week_key]['quantity'] += sale['quantity']
                        weekly_sales[week_key]['revenue'] += sale['subtotal']

                    print("\nWeekly Breakdown:")
                    print(f"{'Week':<10} {'Units Sold':<12} {'Revenue':<15} {'% of Total'}")
                    print("-" * 55)

                    for week_key in sorted(weekly_sales.keys()):
                        data = weekly_sales[week_key]
                        percent = (data['revenue'] / total_revenue) * 100

                        print(f"{week_key:<10} {data['quantity']:<12} £{data['revenue']:<15.2f} {percent:.1f}%")
            except Exception as e:
                # Skip breakdown on error
                print(f"Note: Couldn't generate time breakdown: {e}")

            # Recent transactions
            print("\nRecent Transactions:")
            print(f"{'Date':<20} {'Transaction ID':<20} {'Quantity':<10} {'Price':<10} {'Subtotal'}")
            print("-" * 75)

            for i, sale in enumerate(sales):
                if i >= 10:  # Show only 10 most recent
                    break

                price_formatted = f"£{sale['price_per_item']:.2f}"
                subtotal_formatted = f"£{sale['subtotal']:.2f}"
                date_formatted = sale['created_at']

                print(f"{date_formatted:<20} {sale['transaction_id']:<20} {sale['quantity']:<10} {price_formatted:<10} {subtotal_formatted}")

            # Get inventory information
            cursor.execute(
                "SELECT * FROM shop_inventory WHERE product_id = ?",
                [product_id]
            )

            inventory = cursor.fetchone()

            if inventory:
                print(f"\nCurrent Stock: {inventory['quantity']}")
                print(f"Restock Threshold: {inventory['restock_threshold']}")
                print(f"Last Restock: {inventory['last_restock_date']}")

                # Calculate turnover
                if inventory['quantity'] > 0:
                    # Calculate average daily sales
                    try:
                        days = (end - start).days
                        if days > 0:
                            daily_sales = total_quantity / days
                            estimated_days = inventory['quantity'] / daily_sales if daily_sales > 0 else float('inf')

                            print(f"Average Daily Sales: {daily_sales:.1f} units")
                            print(f"Estimated Days Until Restock Needed: {estimated_days:.1f}")
                    except Exception:
                        pass

        else:
            # Show all products sales summary
            print("\nAll Products Sales Summary")

            # Get time period
            print("Select time period:")
            print("1. Last 30 days")
            print("2. Last 90 days")
            print("3. Year to date")
            print("4. All time")

            period_choice = input("Select option (1-4): ").strip()

            today = datetime.now()

            if period_choice == '1':
                start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                period_name = "Last 30 Days"
            elif period_choice == '2':
                start_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
                period_name = "Last 90 Days"
            elif period_choice == '3':
                start_date = f"{today.year}-01-01"
                period_name = "Year to Date"
            elif period_choice == '4':
                start_date = "2000-01-01"  # Far past
                period_name = "All Time"
            else:
                print("Invalid choice. Using last 30 days.")
                start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                period_name = "Last 30 Days"

            end_date = today.strftime('%Y-%m-%d')

            # Get sales data
            cursor.execute(
                '''
                SELECT p.source_product_id as product_id, p.name, p.category, p.price,
                       SUM(ti.quantity) as total_quantity,
                       SUM(ti.subtotal) as total_revenue,
                       COUNT(DISTINCT ti.transaction_id) as transaction_count,
                       AVG(ti.price_per_item) as avg_price
                FROM shop_transaction_items ti
                JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
                JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
                WHERE t.created_at BETWEEN ? AND ?
                GROUP BY p.source_product_id
                ORDER BY total_revenue DESC
                ''',
                [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            )

            product_sales = cursor.fetchall()

            if not product_sales:
                print(f"No sales found for the period {start_date} to {end_date}.")
                conn.close()
                return

            # Calculate total sales
            total_revenue = sum(p['total_revenue'] for p in product_sales)
            total_quantity = sum(p['total_quantity'] for p in product_sales)

            print(f"\nSales Summary for {period_name}: {start_date} to {end_date}")
            print(f"Total Revenue: £{total_revenue:.2f}")
            print(f"Total Units Sold: {total_quantity}")
            print(f"Number of Products Sold: {len(product_sales)}")

            # Display product sales
            print("\nProduct Sales Ranking:")
            print(f"{'Rank':<5} {'Product ID':<12} {'Name':<30} {'Category':<15} {'Units Sold':<12} {'Revenue':<15} {'% of Total'}")
            print("-" * 100)

            for i, product in enumerate(product_sales):
                percent = (product['total_revenue'] / total_revenue) * 100
                print(f"{i+1:<5} {product['product_id']:<12} {product['name'][:28]:<30} {product['category'][:13]:<15} {product['total_quantity']:<12} £{product['total_revenue']:<15.2f} {percent:.1f}%")

                if i >= 19:  # Show only top 20
                    remaining = len(product_sales) - 20
                    if remaining > 0:
                        remaining_revenue = sum(p['total_revenue'] for p in product_sales[20:])
                        remaining_percent = (remaining_revenue / total_revenue) * 100
                        print(f"... and {remaining} more products (£{remaining_revenue:.2f}, {remaining_percent:.1f}% of total)")
                    break

            # Get category breakdown
            cursor.execute(
                '''
                SELECT p.category,
                       SUM(ti.quantity) as total_quantity,
                       SUM(ti.subtotal) as total_revenue,
                       COUNT(DISTINCT p.product_id) as product_count
                FROM shop_transaction_items ti
                JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
                JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
                WHERE t.created_at BETWEEN ? AND ?
                GROUP BY p.category
                ORDER BY total_revenue DESC
                ''',
                [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            )

            category_sales = cursor.fetchall()

            if category_sales:
                print("\nSales by Category:")
                print(f"{'Category':<20} {'Products':<10} {'Units Sold':<12} {'Revenue':<15} {'% of Total'}")
                print("-" * 70)

                for category in category_sales:
                    percent = (category['total_revenue'] / total_revenue) * 100
                    print(f"{category['category']:<20} {category['product_count']:<10} {category['total_quantity']:<12} £{category['total_revenue']:<15.2f} {percent:.1f}%")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error generating report: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error generating report: {e}")
        if 'conn' in locals():
            conn.close()


@log_read(module="shop", description="Generating category sales report")
def generate_category_sales_report():
    """Generate a sales report for a specific category"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to generate reports.")
        return

    if not config.auth.check_permission('generate_sales_reports'):
        print("You don't have permission to generate sales reports.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print("\nCategory Sales Report")
        print("--------------------")

        # Get available categories
        cursor.execute(
            "SELECT DISTINCT category FROM products WHERE source_type = 'shop' ORDER BY category"
        )

        categories = cursor.fetchall()

        if not categories:
            print("No categories found in the database.")
            conn.close()
            return

        print("Available Categories:")
        for i, category in enumerate(categories):
            print(f"{i+1}. {category['category']}")

        # Get category selection
        try:
            category_choice = int(input("Select category number: ").strip())

            if category_choice < 1 or category_choice > len(categories):
                print("Invalid selection.")
                conn.close()
                return

            selected_category = categories[category_choice-1]['category']
        except ValueError:
            print("Invalid input. Please enter a number.")
            conn.close()
            return

        # Get time period
        print("\nSelect time period:")
        print("1. Last 30 days")
        print("2. Last 90 days")
        print("3. Year to date")
        print("4. All time")
        print("5. Custom range")

        period_choice = input("Select option (1-5): ").strip()

        today = datetime.now()

        if period_choice == '1':
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            period_name = "Last 30 Days"
        elif period_choice == '2':
            start_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            period_name = "Last 90 Days"
        elif period_choice == '3':
            start_date = f"{today.year}-01-01"
            end_date = today.strftime('%Y-%m-%d')
            period_name = "Year to Date"
        elif period_choice == '4':
            start_date = "2000-01-01"  # Far past
            end_date = today.strftime('%Y-%m-%d')
            period_name = "All Time"
        elif period_choice == '5':
            start_input = input("Enter start date (YYYY-MM-DD): ").strip()
            end_input = input("Enter end date (YYYY-MM-DD): ").strip()

            try:
                # Validate dates
                start_date = datetime.strptime(start_input, '%Y-%m-%d').strftime('%Y-%m-%d')
                end_date = datetime.strptime(end_input, '%Y-%m-%d').strftime('%Y-%m-%d')
                period_name = f"Custom: {start_date} to {end_date}"
            except ValueError:
                print("Invalid date format. Using last 30 days.")
                start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
                period_name = "Last 30 Days"
        else:
            print("Invalid choice. Using last 30 days.")
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            period_name = "Last 30 Days"

        # Get products in this category
        cursor.execute(
            '''
            SELECT product_id, name, price, is_active
            FROM products WHERE source_type = 'shop'
            WHERE category = ?
            ORDER BY name
            ''',
            [selected_category]
        )

        products = cursor.fetchall()

        if not products:
            print(f"No products found in category '{selected_category}'.")
            conn.close()
            return

        # Get sales data
        cursor.execute(
            '''
            SELECT p.source_product_id as product_id, p.name, p.price,
                   SUM(ti.quantity) as total_quantity,
                   SUM(ti.subtotal) as total_revenue,
                   COUNT(DISTINCT ti.transaction_id) as transaction_count
            FROM shop_transaction_items ti
            JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
            JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            WHERE p.category = ? AND t.created_at BETWEEN ? AND ?
            GROUP BY p.source_product_id
            ORDER BY total_revenue DESC
            ''',
            [selected_category, f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
        )

        sales_data = cursor.fetchall()

        # Display category overview
        print(f"\nCategory: {selected_category}")
        print(f"Period: {period_name}")
        print(f"Total Products in Category: {len(products)}")
        print(f"Products with Sales: {len(sales_data)}")

        # Display sales summary
        if not sales_data:
            print(f"No sales found for category '{selected_category}' in this period.")

            print("\nProducts in Category (No Sales):")
            print(f"{'Product ID':<12} {'Name':<40} {'Price':<10} {'Status'}")
            print("-" * 80)

            for product in products:
                price_formatted = f"£{product['price']:.2f}"
                status = "Active" if product['is_active'] else "Inactive"
                print(f"{product['product_id']:<12} {product['name'][:38]:<40} {price_formatted:<10} {status}")

            conn.close()
            input("\nPress Enter to continue...")
            return

        # Calculate totals
        total_revenue = sum(s['total_revenue'] for s in sales_data)
        total_quantity = sum(s['total_quantity'] for s in sales_data)
        transaction_count = sum(s['transaction_count'] for s in sales_data)

        print(f"Total Revenue: £{total_revenue:.2f}")
        print(f"Total Units Sold: {total_quantity}")
        print(f"Transaction Count: {transaction_count}")

        # Display product sales ranking
        print("\nProduct Sales Ranking:")
        print(f"{'Rank':<5} {'Product ID':<12} {'Name':<30} {'Units Sold':<12} {'Revenue':<15} {'% of Category'}")
        print("-" * 90)

        for i, product in enumerate(sales_data):
            percent = (product['total_revenue'] / total_revenue) * 100 if total_revenue > 0 else 0
            print(f"{i+1:<5} {product['product_id']:<12} {product['name'][:28]:<30} {product['total_quantity']:<12} £{product['total_revenue']:<15.2f} {percent:.1f}%")

        # Products with no sales
        sold_product_ids = {s['product_id'] for s in sales_data}
        unsold_products = [p for p in products if p['product_id'] not in sold_product_ids]

        if unsold_products:
            print(f"\nProducts with No Sales in this Period ({len(unsold_products)}):")
            print(f"{'Product ID':<12} {'Name':<40} {'Price':<10} {'Status'}")
            print("-" * 80)

            for product in unsold_products:
                price_formatted = f"£{product['price']:.2f}"
                status = "Active" if product['is_active'] else "Inactive"
                print(f"{product['product_id']:<12} {product['name'][:38]:<40} {price_formatted:<10} {status}")

        # Time-based analysis
        try:
            # Monthly trend if period is long enough
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            days_diff = (end - start).days

            if days_diff >= 60:  # If at least 60 days, show monthly trend
                cursor.execute(
                    '''
                    SELECT strftime('%Y-%m', t.created_at) as month,
                           SUM(ti.quantity) as quantity,
                           SUM(ti.subtotal) as revenue
                    FROM shop_transaction_items ti
                    JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
                    JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
                    WHERE p.category = ? AND t.created_at BETWEEN ? AND ?
                    GROUP BY month
                    ORDER BY month
                    ''',
                    [selected_category, f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
                )

                monthly_data = cursor.fetchall()

                if monthly_data:
                    print("\nMonthly Sales Trend:")
                    print(f"{'Month':<10} {'Units Sold':<12} {'Revenue':<15} {'Month/Month %'}")
                    print("-" * 60)

                    prev_revenue = None
                    for i, month_data in enumerate(monthly_data):
                        month_label = datetime.strptime(month_data['month'], '%Y-%m').strftime('%b %Y')

                        # Calculate month-over-month percentage
                        if i > 0 and prev_revenue:
                            mom_pct = ((month_data['revenue'] - prev_revenue) / prev_revenue) * 100 if prev_revenue > 0 else float('inf')
                            mom_display = f"{mom_pct:+.1f}%"
                        else:
                            mom_display = "N/A"

                        print(f"{month_label:<10} {month_data['quantity']:<12} £{month_data['revenue']:<15.2f} {mom_display}")
                        prev_revenue = month_data['revenue']
        except Exception as e:
            # Skip time analysis on error
            print(f"Note: Could not generate time trend analysis: {e}")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error generating report: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error generating report: {e}")
        if 'conn' in locals():
            conn.close()


@log_export(module="shop", description="Exporting sales data")
def export_sales_data():
    """Export sales data to CSV or Excel"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to export sales data.")
        return

    if not config.auth.check_permission('generate_sales_reports'):
        print("You don't have permission to export sales data.")
        return

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print("\nExport Sales Data")
        print("----------------")

        # Get date range
        print("Select date range:")
        print("1. Last 7 days")
        print("2. Last 30 days")
        print("3. Last 90 days")
        print("4. Year to date")
        print("5. Custom range")

        range_choice = input("Select option (1-5): ").strip()

        today = datetime.now()

        if range_choice == '1':
            start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            period_name = "7days"
        elif range_choice == '2':
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            period_name = "30days"
        elif range_choice == '3':
            start_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            period_name = "90days"
        elif range_choice == '4':
            start_date = f"{today.year}-01-01"
            end_date = today.strftime('%Y-%m-%d')
            period_name = f"{today.year}_ytd"
        elif range_choice == '5':
            start_input = input("Enter start date (YYYY-MM-DD): ").strip()
            end_input = input("Enter end date (YYYY-MM-DD): ").strip()

            try:
                # Validate dates
                start_date = datetime.strptime(start_input, '%Y-%m-%d').strftime('%Y-%m-%d')
                end_date = datetime.strptime(end_input, '%Y-%m-%d').strftime('%Y-%m-%d')
                period_name = f"{start_date}_to_{end_date}"
            except ValueError:
                print("Invalid date format. Using last 30 days.")
                start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
                period_name = "30days"
        else:
            print("Invalid choice. Using last 30 days.")
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            period_name = "30days"

        # Get export format
        print("\nExport Format:")
        print("1. CSV")
        print("2. Excel")

        format_choice = input("Select format (1-2): ").strip()

        if format_choice == '1':
            export_format = 'csv'
        elif format_choice == '2':
            export_format = 'excel'
        else:
            print("Invalid choice. Using CSV format.")
            export_format = 'csv'

        # Get data type
        print("\nData to Export:")
        print("1. Transactions")
        print("2. Product Sales")
        print("3. Category Sales")
        print("4. Daily Sales")
        print("5. All Data")

        data_choice = input("Select data type (1-5): ").strip()

        if data_choice not in ['1', '2', '3', '4', '5']:
            print("Invalid choice. Exporting transactions.")
            data_choice = '1'

        # Define file path
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_base = f"shop_export_{period_name}_{timestamp}"

        if export_format == 'csv':
            file_extension = '.csv'
        else:
            file_extension = '.xlsx'

        # Get file path from user
        default_path = os.path.join(os.getcwd(), file_base + file_extension)
        file_path = input(f"Enter file path [default: {default_path}]: ").strip()

        if not file_path:
            file_path = default_path

        # Make sure directory exists
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except OSError as e:
                print(f"Error creating directory: {e}")
                conn.close()
                return

        # Initialize data containers
        all_dataframes = {}

        # Export data based on type
        if data_choice in ['1', '5']:  # Transactions
            cursor.execute(
                '''
                SELECT t.source_transaction_id, t.created_at, u.username, t.student_id,
                       t.total_amount, t.payment_method, t.status
                FROM transactions t
                LEFT JOIN users u ON t.customer_id = u.id
                WHERE t.source_type = 'shop' AND t.created_at BETWEEN ? AND ?
                ORDER BY t.created_at
                ''',
                [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            )

            transactions = cursor.fetchall()

            if transactions:
                # Convert to DataFrame
                transaction_data = []
                for t in transactions:
                    transaction_data.append({
                        'transaction_id': t['source_transaction_id'],
                        'date': t['created_at'],
                        'username': t['username'],
                        'student_id': t['student_id'],
                        'amount': t['total_amount'],
                        'payment_method': t['payment_method'],
                        'status': t['status']
                    })

                all_dataframes['Transactions'] = pd.DataFrame(transaction_data)
                print(f"✓ Prepared {len(transactions)} transaction records")
            else:
                print("No transactions found for the selected period.")

        if data_choice in ['2', '5']:  # Product Sales
            cursor.execute(
                '''
                SELECT p.source_product_id as product_id, p.name, p.category,
                       SUM(ti.quantity) as total_quantity,
                       SUM(ti.subtotal) as total_revenue,
                       COUNT(DISTINCT ti.transaction_id) as transaction_count
                FROM shop_transaction_items ti
                JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
                JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
                WHERE t.created_at BETWEEN ? AND ?
                GROUP BY p.source_product_id
                ORDER BY total_revenue DESC
                ''',
                [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            )

            product_sales = cursor.fetchall()

            if product_sales:
                # Convert to DataFrame
                product_data = []
                for p in product_sales:
                    product_data.append({
                        'product_id': p['product_id'],
                        'name': p['name'],
                        'category': p['category'],
                        'quantity_sold': p['total_quantity'],
                        'revenue': p['total_revenue'],
                        'transaction_count': p['transaction_count'],
                        'average_price': p['total_revenue'] / p['total_quantity'] if p['total_quantity'] > 0 else 0
                    })

                all_dataframes['Product_Sales'] = pd.DataFrame(product_data)
                print(f"✓ Prepared {len(product_sales)} product sales records")
            else:
                print("No product sales found for the selected period.")

        if data_choice in ['3', '5']:  # Category Sales
            cursor.execute(
                '''
                SELECT p.category,
                       COUNT(DISTINCT p.product_id) as product_count,
                       SUM(ti.quantity) as total_quantity,
                       SUM(ti.subtotal) as total_revenue,
                       COUNT(DISTINCT ti.transaction_id) as transaction_count
                FROM shop_transaction_items ti
                JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
                JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
                WHERE t.created_at BETWEEN ? AND ?
                GROUP BY p.category
                ORDER BY total_revenue DESC
                ''',
                [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            )

            category_sales = cursor.fetchall()

            if category_sales:
                # Convert to DataFrame
                category_data = []
                for c in category_sales:
                    category_data.append({
                        'category': c['category'],
                        'product_count': c['product_count'],
                        'quantity_sold': c['total_quantity'],
                        'revenue': c['total_revenue'],
                        'transaction_count': c['transaction_count'],
                        'average_per_product': c['total_revenue'] / c['product_count'] if c['product_count'] > 0 else 0
                    })

                all_dataframes['Category_Sales'] = pd.DataFrame(category_data)
                print(f"✓ Prepared {len(category_sales)} category sales records")
            else:
                print("No category sales found for the selected period.")

        if data_choice in ['4', '5']:  # Daily Sales
            cursor.execute(
                '''
                SELECT date(t.created_at) as sale_date,
                       COUNT(DISTINCT t.source_transaction_id) as transaction_count,
                       SUM(t.total_amount) as total_revenue,
                       COUNT(DISTINCT ti.product_id) as products_sold,
                       SUM(ti.quantity) as quantity_sold
                FROM transactions t
                JOIN shop_transaction_items ti ON t.source_transaction_id = ti.transaction_id
                WHERE t.source_type = 'shop' AND t.created_at BETWEEN ? AND ?
                GROUP BY sale_date
                ORDER BY sale_date
                ''',
                [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            )

            daily_sales = cursor.fetchall()

            if daily_sales:
                # Convert to DataFrame
                daily_data = []
                for d in daily_sales:
                    daily_data.append({
                        'date': d['sale_date'],
                        'transaction_count': d['transaction_count'],
                        'revenue': d['total_revenue'],
                        'unique_products': d['products_sold'],
                        'quantity_sold': d['quantity_sold'],
                        'average_transaction': d['total_revenue'] / d['transaction_count'] if d['transaction_count'] > 0 else 0
                    })

                all_dataframes['Daily_Sales'] = pd.DataFrame(daily_data)
                print(f"✓ Prepared {len(daily_sales)} daily sales records")
            else:
                print("No daily sales found for the selected period.")

        # Check if we have any data to export
        if not all_dataframes:
            print("No data found to export for the selected criteria.")
            conn.close()
            return

        # Export the data
        if export_format == 'csv':
            # For CSV, export each sheet as a separate file if multiple sheets
            if len(all_dataframes) == 1:
                # Single sheet - use the specified filename
                sheet_name, df = list(all_dataframes.items())[0]
                df.to_csv(file_path, index=False)
                print(f"✅ {sheet_name} exported to {file_path}")
            else:
                # Multiple sheets - create separate files
                base_path = file_path.replace('.csv', '')
                for sheet_name, df in all_dataframes.items():
                    csv_path = f"{base_path}_{sheet_name}.csv"
                    df.to_csv(csv_path, index=False)
                    print(f"✅ {sheet_name} exported to {csv_path}")

        else:  # Excel format
            # Remove existing file if it exists to avoid conflicts
            if os.path.exists(file_path):
                os.remove(file_path)

            # Create Excel file with multiple sheets
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Add summary sheet if multiple data types
                if data_choice == '5' and len(all_dataframes) > 1:
                    # Create summary
                    summary_data = {
                        'Metric': [
                            'Report Generated',
                            'Period Start',
                            'Period End',
                            'Data Types Exported',
                            'Total Sheets'
                        ],
                        'Value': [
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            start_date,
                            end_date,
                            ', '.join(all_dataframes.keys()),
                            len(all_dataframes)
                        ]
                    }

                    # Add data counts for each sheet
                    for sheet_name, df in all_dataframes.items():
                        summary_data['Metric'].append(f"{sheet_name} Records")
                        summary_data['Value'].append(len(df))

                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)

                # Export all data sheets
                for sheet_name, df in all_dataframes.items():
                    # Ensure sheet name is valid for Excel (max 31 chars, no special chars)
                    safe_sheet_name = sheet_name.replace(' ', '_')[:31]
                    df.to_excel(writer, sheet_name=safe_sheet_name, index=False)

                    # Auto-adjust column widths
                    worksheet = writer.sheets[safe_sheet_name]
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except (AttributeError, TypeError):
                                pass
                        adjusted_width = min(max_length + 2, 50)  # Cap at 50 chars
                        worksheet.column_dimensions[column_letter].width = adjusted_width

            print(f"✅ Excel file with {len(all_dataframes)} sheet(s) exported to {file_path}")

        conn.close()

        # Show export summary
        total_records = sum(len(df) for df in all_dataframes.values())
        print(f"\nExport Summary:")
        print(f"- Total records exported: {total_records:,}")
        print(f"- Period: {start_date} to {end_date}")
        print(f"- Format: {export_format.upper()}")
        print(f"- File location: {file_path}")

        input("\nExport complete. Press Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error exporting data: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error exporting data: {e}")
        if 'conn' in locals():
            conn.close()


def get_sales_statistics(days=30):
    """Get comprehensive sales statistics"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Get basic stats
        cursor.execute(
            '''
            SELECT
                COUNT(DISTINCT source_transaction_id) as transaction_count,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_transaction,
                MIN(total_amount) as min_transaction,
                MAX(total_amount) as max_transaction
            FROM transactions
            WHERE source_type = 'shop' AND created_at >= ?
            ''',
            [start_date.strftime('%Y-%m-%d %H:%M:%S')]
        )

        basic_stats = cursor.fetchone()

        # Get payment method breakdown
        cursor.execute(
            '''
            SELECT payment_method, COUNT(*) as count, SUM(total_amount) as amount
            FROM transactions
            WHERE source_type = 'shop' AND created_at >= ?
            GROUP BY payment_method
            ORDER BY amount DESC
            ''',
            [start_date.strftime('%Y-%m-%d %H:%M:%S')]
        )

        payment_stats = cursor.fetchall()

        # Get top categories
        cursor.execute(
            '''
            SELECT p.category, SUM(ti.subtotal) as revenue, SUM(ti.quantity) as quantity
            FROM shop_transaction_items ti
            JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
            WHERE t.created_at >= ?
            GROUP BY p.category
            ORDER BY revenue DESC
            LIMIT 5
            ''',
            [start_date.strftime('%Y-%m-%d %H:%M:%S')]
        )

        category_stats = cursor.fetchall()

        conn.close()

        return {
            'period_days': days,
            'basic': basic_stats,
            'payment_methods': payment_stats,
            'top_categories': category_stats
        }

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return None


def display_dashboard():
    """Display a dashboard with key shop metrics"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to view the dashboard.")
        return

    if not config.auth.check_permission('generate_sales_reports'):
        print("You don't have permission to view the dashboard.")
        return

    try:
        print("\n" + "="*60)
        print("UNIVERSITY SHOP DASHBOARD")
        print("="*60)

        # Get low stock alert
        alert = get_low_stock_alert()
        if alert:
            print(f"\n{alert}")

        # Get sales statistics
        stats = get_sales_statistics(30)

        if stats and stats['basic']:
            basic = stats['basic']
            print(f"\nSALES SUMMARY (Last 30 Days)")
            print("-" * 40)
            print(f"Total Transactions: {basic['transaction_count'] or 0}")
            print(f"Total Revenue: £{basic['total_revenue'] or 0:.2f}")
            print(f"Average Transaction: £{basic['avg_transaction'] or 0:.2f}")

            if stats['payment_methods']:
                print(f"\nPAYMENT METHODS")
                print("-" * 20)
                for method in stats['payment_methods']:
                    print(f"{method['payment_method']}: {method['count']} transactions (£{method['amount']:.2f})")

            if stats['top_categories']:
                print(f"\nTOP CATEGORIES")
                print("-" * 20)
                for cat in stats['top_categories']:
                    print(f"{cat['category']}: £{cat['revenue']:.2f} ({cat['quantity']} items)")

        # Get popular products
        popular = get_popular_products(5, 30)
        if popular:
            print(f"\nPOPULAR PRODUCTS (Last 30 Days)")
            print("-" * 40)
            for i, product in enumerate(popular, 1):
                print(f"{i}. {product['name']} - {product['total_sold']} sold")

        print("\n" + "="*60)
        input("\nPress Enter to continue...")

    except Exception as e:
        print(f"Error displaying dashboard: {e}")
