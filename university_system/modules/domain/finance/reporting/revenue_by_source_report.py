"""
Revenue by Source Report

This module provides reporting functionality to break down university revenue
by transaction source (Library, Housing, Shop, Restaurant, Alumni, etc.).

This enables finance administrators to see which departments/services are
generating revenue and track trends by source over time.
"""

from university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from university_system.modules.shared.constants import paths
import logging

logger = logging.getLogger(__name__)

def get_revenue_by_source(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_external: bool = True
) -> Dict[str, Dict[str, float]]:
    """
    Get revenue broken down by transaction source.

    Args:
        start_date: Start date filter (YYYY-MM-DD format), None for all time
        end_date: End date filter (YYYY-MM-DD format), None for all time
        include_external: Whether to include non-student transactions

    Returns:
        Dictionary with source as key and stats as value:
        {
            'Library': {'count': 150, 'total': 3250.50, 'avg': 21.67},
            'Housing': {'count': 450, 'total': 360000.00, 'avg': 800.00},
            ...
        }
    """
    try:
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Build date filter conditions
        date_filter = ""
        params = []
        if start_date:
            date_filter += " AND date_col >= ?"
            params.append(start_date)
        if end_date:
            date_filter += " AND date_col <= ?"
            params.append(end_date)

        external_filter = ""
        if not include_external:
            external_filter = " AND student_id != 'EXTERNAL'"

        # Query combining central payments table with service-specific transaction tables
        query = f'''
        WITH all_transactions AS (
            -- Central payments table
            SELECT
                CASE
                    WHEN notes LIKE '[Library]%' THEN 'Library'
                    WHEN notes LIKE '[Housing]%' THEN 'Housing'
                    WHEN notes LIKE '[Shop]%' AND notes NOT LIKE '[Charity Shop]%'
                         AND notes NOT LIKE '[MusicShop]%' AND notes NOT LIKE '[PhoneShop]%' THEN 'Shop'
                    WHEN notes LIKE '[Restaurant]%' THEN 'Restaurant'
                    WHEN notes LIKE '[Alumni]%' THEN 'Alumni'
                    WHEN notes LIKE '[Student Union]%' THEN 'Student Union'
                    WHEN notes LIKE '[Trip Management]%' THEN 'Trip Management'
                    WHEN notes LIKE '[Cafe]%' THEN 'Cafe'
                    WHEN notes LIKE '[Grocery]%' THEN 'Grocery'
                    WHEN notes LIKE '[Takeaway]%' THEN 'Takeaway'
                    WHEN notes LIKE '[MusicShop]%' THEN 'MusicShop'
                    WHEN notes LIKE '[PhoneShop]%' THEN 'PhoneShop'
                    WHEN notes LIKE '[EquipmentRental]%' THEN 'EquipmentRental'
                    WHEN notes LIKE '[CarRental]%' THEN 'CarRental'
                    WHEN notes LIKE '[Charity Shop]%' THEN 'Charity Shop'
                    WHEN notes LIKE 'Dental:%' OR notes LIKE '[Dentist]%' THEN 'Dentist'
                    WHEN notes LIKE 'Gym:%' OR notes LIKE '[Gym]%' THEN 'Gym'
                    WHEN notes LIKE '[Bar]%' THEN 'Bar'
                    WHEN notes LIKE '[Parking]%' THEN 'Parking'
                    WHEN notes LIKE '[Betting]%' THEN 'Betting'
                    WHEN notes LIKE '[Butcher]%' OR notes LIKE 'Butcher%' THEN 'Butcher'
                    WHEN notes LIKE '[Barber]%' OR notes LIKE 'Barber%' THEN 'Barber'
                    WHEN notes LIKE '[NailBar]%' OR notes LIKE 'NailBar%' OR notes LIKE 'Nail Bar%' OR notes LIKE 'Nail:%' THEN 'NailBar'
                    ELSE 'Tuition & Fees'
                END as source,
                amount,
                payment_date as trans_date
            FROM payments
            WHERE status = 'completed' {external_filter}

            UNION ALL

            -- Gym transactions (not in central payments)
            SELECT 'Gym' as source, amount, created_at as trans_date
            FROM gym_transactions
            WHERE transaction_id NOT IN (
                SELECT DISTINCT SUBSTR(notes, INSTR(notes, 'Ref: ') + 5)
                FROM payments WHERE notes LIKE 'Gym:%'
            )

            UNION ALL

            -- Dentist transactions (not in central payments)
            SELECT 'Dentist' as source, amount, created_at as trans_date
            FROM dentist_transactions
            WHERE transaction_id NOT IN (
                SELECT DISTINCT SUBSTR(notes, INSTR(notes, 'Ref: ') + 5)
                FROM payments WHERE notes LIKE 'Dental:%'
            )

            UNION ALL

            -- Grocery transactions (not in central payments)
            SELECT 'Grocery' as source, total_amount as amount, transaction_date as trans_date
            FROM grocery_transactions
            WHERE transaction_id NOT IN (
                SELECT DISTINCT SUBSTR(notes, INSTR(notes, 'Ref: ') + 5)
                FROM payments WHERE notes LIKE '[Grocery]%'
            )

            UNION ALL

            -- Betting transactions
            SELECT 'Betting' as source, amount, created_at as trans_date
            FROM betting_transactions
            WHERE status = 'completed'

            UNION ALL

            -- Shop transactions (not in central payments)
            SELECT 'Shop' as source, total_amount as amount, transaction_date as trans_date
            FROM shop_transactions
            WHERE status = 'completed'
            AND transaction_id NOT IN (
                SELECT DISTINCT SUBSTR(notes, INSTR(notes, 'Ref: ') + 5)
                FROM payments WHERE notes LIKE '[Shop]%'
            )

            UNION ALL

            -- Butcher transactions
            SELECT 'Butcher' as source, amount, created_at as trans_date
            FROM butcher_transactions
            WHERE status = 'completed'

            UNION ALL

            -- Barber transactions
            SELECT 'Barber' as source, amount, created_at as trans_date
            FROM barber_transactions
            WHERE status = 'completed'

            UNION ALL

            -- NailBar transactions
            SELECT 'NailBar' as source, amount, created_at as trans_date
            FROM nailbar_transactions
            WHERE status = 'completed'

            UNION ALL

            -- CarRental transactions
            SELECT 'CarRental' as source, amount, created_at as trans_date
            FROM carrental_transactions
            WHERE status = 'completed'

            UNION ALL

            -- PhoneShop transactions
            SELECT 'PhoneShop' as source, amount, created_at as trans_date
            FROM phoneshop_transactions
            WHERE status = 'completed'

            UNION ALL

            -- MusicShop transactions
            SELECT 'MusicShop' as source, amount, created_at as trans_date
            FROM musicshop_transactions
            WHERE status = 'completed'
        )
        SELECT
            source,
            COUNT(*) as transaction_count,
            SUM(amount) as total_amount,
            AVG(amount) as avg_amount,
            MIN(amount) as min_amount,
            MAX(amount) as max_amount
        FROM all_transactions
        WHERE 1=1
        '''

        # Apply date filters - use DATE() to handle both DATE and DATETIME formats
        if start_date:
            query += ' AND DATE(trans_date) >= ?'
        if end_date:
            query += ' AND DATE(trans_date) <= ?'

        query += '''
        GROUP BY source
        ORDER BY total_amount DESC
        '''

        # Debug logging
        logger.debug(f"Revenue by source query params: {params}")

        cursor.execute(query, params)
        results = cursor.fetchall()

        revenue_data = {}
        for row in results:
            source, count, total, avg, min_amt, max_amt = row
            revenue_data[source] = {
                'count': count,
                'total': round(float(total), 2),
                'average': round(float(avg), 2),
                'min': round(float(min_amt), 2),
                'max': round(float(max_amt), 2)
            }

        conn.close()
        return revenue_data

    except sqlite3.Error as e:
        logger.error(f"Database error in get_revenue_by_source: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error in get_revenue_by_source: {e}")
        return {}

def print_revenue_by_source_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Print a formatted revenue by source report to console.

    Args:
        start_date: Start date filter (YYYY-MM-DD)
        end_date: End date filter (YYYY-MM-DD)
    """
    print("\n" + "=" * 80)
    print("REVENUE BY SOURCE REPORT".center(80))
    print("=" * 80)

    if start_date and end_date:
        print(f"Period: {start_date} to {end_date}".center(80))
    elif start_date:
        print(f"From: {start_date}".center(80))
    elif end_date:
        print(f"Until: {end_date}".center(80))
    else:
        print("All Time".center(80))

    print("=" * 80)

    revenue_data = get_revenue_by_source(start_date, end_date)

    if not revenue_data:
        print("No revenue data found for the specified period.")
        return

    # Calculate totals
    total_transactions = sum(data['count'] for data in revenue_data.values())
    total_revenue = sum(data['total'] for data in revenue_data.values())

    # Print summary table
    print(f"\n{'Source':<25} {'Count':>10} {'Total Revenue':>15} {'Avg':>12} {'% of Total':>12}")
    print("-" * 80)

    for source, data in sorted(revenue_data.items(), key=lambda x: x[1]['total'], reverse=True):
        percentage = (data['total'] / total_revenue * 100) if total_revenue > 0 else 0
        print(f"{source:<25} {data['count']:>10,} £{data['total']:>13,.2f} £{data['average']:>10,.2f} {percentage:>11.1f}%")

    print("-" * 80)
    print(f"{'TOTAL':<25} {total_transactions:>10,} £{total_revenue:>13,.2f} £{total_revenue/total_transactions:>10,.2f} {'100.0':>11}%")
    print("=" * 80)

    # Print detailed breakdown
    print("\nDETAILED BREAKDOWN BY SOURCE:")
    print("-" * 80)

    for source, data in sorted(revenue_data.items(), key=lambda x: x[1]['total'], reverse=True):
        print(f"\n{source}:")
        print(f"  Transactions: {data['count']:,}")
        print(f"  Total Revenue: £{data['total']:,.2f}")
        print(f"  Average Transaction: £{data['average']:,.2f}")
        print(f"  Range: £{data['min']:,.2f} - £{data['max']:,.2f}")
        print(f"  % of Total Revenue: {(data['total'] / total_revenue * 100):.1f}%")

def get_source_revenue_trend(
    source: str,
    months: int = 12
) -> List[Tuple[str, float, int]]:
    """
    Get monthly revenue trend for a specific source.

    Args:
        source: Source name (e.g., 'Library', 'Housing')
        months: Number of months to retrieve

    Returns:
        List of tuples: [(month, revenue, transaction_count), ...]
    """
    try:
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()

        source_pattern = f'[{source}]%'

        cursor.execute('''
        SELECT
            strftime('%Y-%m', payment_date) as month,
            SUM(amount) as revenue,
            COUNT(*) as transactions
        FROM payments
        WHERE notes LIKE ?
            AND status = 'completed'
            AND payment_date >= date('now', '-' || ? || ' months')
        GROUP BY month
        ORDER BY month DESC
        ''', (source_pattern, months))

        results = cursor.fetchall()
        conn.close()

        return [(row[0], round(float(row[1]), 2), row[2]) for row in results]

    except Exception as e:
        logger.error(f"Error in get_source_revenue_trend: {e}")
        return []

def compare_source_revenue_periods(
    source: str,
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str
) -> Dict[str, any]:
    """
    Compare revenue from a source between two time periods.

    Args:
        source: Source name
        period1_start, period1_end: First period dates
        period2_start, period2_end: Second period dates

    Returns:
        Dictionary with comparison metrics
    """
    try:
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()

        source_pattern = f'[{source}]%'

        # Period 1 data
        cursor.execute('''
        SELECT COUNT(*), COALESCE(SUM(amount), 0)
        FROM payments
        WHERE notes LIKE ?
            AND status = 'completed'
            AND payment_date BETWEEN ? AND ?
        ''', (source_pattern, period1_start, period1_end))

        period1_count, period1_revenue = cursor.fetchone()

        # Period 2 data
        cursor.execute('''
        SELECT COUNT(*), COALESCE(SUM(amount), 0)
        FROM payments
        WHERE notes LIKE ?
            AND status = 'completed'
            AND payment_date BETWEEN ? AND ?
        ''', (source_pattern, period2_start, period2_end))

        period2_count, period2_revenue = cursor.fetchone()

        conn.close()

        # Calculate changes
        count_change = period2_count - period1_count
        revenue_change = float(period2_revenue - period1_revenue)
        count_pct_change = (count_change / period1_count * 100) if period1_count > 0 else 0
        revenue_pct_change = (revenue_change / period1_revenue * 100) if period1_revenue > 0 else 0

        return {
            'source': source,
            'period1': {
                'start': period1_start,
                'end': period1_end,
                'transactions': period1_count,
                'revenue': round(float(period1_revenue), 2)
            },
            'period2': {
                'start': period2_start,
                'end': period2_end,
                'transactions': period2_count,
                'revenue': round(float(period2_revenue), 2)
            },
            'changes': {
                'transaction_count': count_change,
                'transaction_pct': round(count_pct_change, 1),
                'revenue_amount': round(revenue_change, 2),
                'revenue_pct': round(revenue_pct_change, 1)
            }
        }

    except Exception as e:
        logger.error(f"Error in compare_source_revenue_periods: {e}")
        return {}

def export_revenue_by_source_csv(
    filename: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> bool:
    """
    Export revenue by source data to CSV file.

    Args:
        filename: Output CSV filename
        start_date: Start date filter
        end_date: End date filter

    Returns:
        True if successful, False otherwise
    """
    try:
        import csv

        revenue_data = get_revenue_by_source(start_date, end_date)

        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)

            # Header
            writer.writerow(['Source', 'Transaction Count', 'Total Revenue', 'Average Transaction', 'Min Amount', 'Max Amount'])

            # Calculate total
            total_count = sum(data['count'] for data in revenue_data.values())
            total_revenue = sum(data['total'] for data in revenue_data.values())

            # Data rows
            for source, data in sorted(revenue_data.items(), key=lambda x: x[1]['total'], reverse=True):
                writer.writerow([
                    source,
                    data['count'],
                    f"£{data['total']:.2f}",
                    f"£{data['average']:.2f}",
                    f"£{data['min']:.2f}",
                    f"£{data['max']:.2f}"
                ])

            # Total row
            writer.writerow([])
            writer.writerow(['TOTAL', total_count, f"£{total_revenue:.2f}", '', '', ''])

        logger.info(f"Revenue by source exported to {filename}")
        return True

    except Exception as e:
        logger.error(f"Error exporting revenue by source: {e}")
        return False

# CLI interface function
def revenue_by_source_menu():
    """Interactive CLI menu for revenue by source reports."""
    while True:
        print("\n" + "=" * 60)
        print("REVENUE BY SOURCE REPORTS")
        print("=" * 60)
        print("1. View Revenue by Source (All Time)")
        print("2. View Revenue by Source (Date Range)")
        print("3. View Source Trend (Monthly)")
        print("4. Compare Two Periods")
        print("5. Export to CSV")
        print("6. Back to Main Menu")
        print("=" * 60)

        choice = input("\nSelect option (1-6): ").strip()

        if choice == '1':
            print_revenue_by_source_report()
            input("\nPress Enter to continue...")

        elif choice == '2':
            start_date = input("Enter start date (YYYY-MM-DD): ").strip()
            end_date = input("Enter end date (YYYY-MM-DD): ").strip()
            print_revenue_by_source_report(start_date, end_date)
            input("\nPress Enter to continue...")

        elif choice == '3':
            source = input("Enter source name (Library/Housing/Shop/Restaurant/Alumni): ").strip()
            months = int(input("Enter number of months (default 12): ").strip() or "12")
            trend_data = get_source_revenue_trend(source, months)

            print(f"\n{source} Revenue Trend (Last {months} Months)")
            print("-" * 60)
            print(f"{'Month':<15} {'Revenue':>15} {'Transactions':>15}")
            print("-" * 60)

            for month, revenue, count in trend_data:
                print(f"{month:<15} £{revenue:>13,.2f} {count:>15,}")

            input("\nPress Enter to continue...")

        elif choice == '4':
            source = input("Enter source name: ").strip()
            print("\nPeriod 1:")
            p1_start = input("  Start date (YYYY-MM-DD): ").strip()
            p1_end = input("  End date (YYYY-MM-DD): ").strip()
            print("\nPeriod 2:")
            p2_start = input("  Start date (YYYY-MM-DD): ").strip()
            p2_end = input("  End date (YYYY-MM-DD): ").strip()

            comparison = compare_source_revenue_periods(source, p1_start, p1_end, p2_start, p2_end)

            if comparison:
                print(f"\n{source} Revenue Comparison")
                print("=" * 60)
                print(f"\nPeriod 1 ({p1_start} to {p1_end}):")
                print(f"  Transactions: {comparison['period1']['transactions']:,}")
                print(f"  Revenue: £{comparison['period1']['revenue']:,.2f}")
                print(f"\nPeriod 2 ({p2_start} to {p2_end}):")
                print(f"  Transactions: {comparison['period2']['transactions']:,}")
                print(f"  Revenue: £{comparison['period2']['revenue']:,.2f}")
                print(f"\nChanges:")
                print(f"  Transaction Count: {comparison['changes']['transaction_count']:+,} ({comparison['changes']['transaction_pct']:+.1f}%)")
                print(f"  Revenue: £{comparison['changes']['revenue_amount']:+,.2f} ({comparison['changes']['revenue_pct']:+.1f}%)")

            input("\nPress Enter to continue...")

        elif choice == '5':
            filename = input("Enter CSV filename (e.g., revenue_by_source.csv): ").strip()
            use_dates = input("Filter by date range? (y/n): ").strip().lower() == 'y'

            start_date = None
            end_date = None

            if use_dates:
                start_date = input("Enter start date (YYYY-MM-DD): ").strip()
                end_date = input("Enter end date (YYYY-MM-DD): ").strip()

            if export_revenue_by_source_csv(filename, start_date, end_date):
                print(f"\n✅ Revenue data exported to {filename}")
            else:
                print("\n❌ Export failed")

            input("\nPress Enter to continue...")

        elif choice == '6':
            break

        else:
            print("Invalid option. Please try again.")
