from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH
from education_system.post_18.university_system.infrastructure.shared_context import get_auth
import csv
import json

from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.app import auth


def generate_financial_reports():
    """Generate various financial reports"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to generate reports.")
        return

    while True:
        print("\n" + "=" * 50)
        print("FINANCIAL REPORTS")
        print("=" * 50)
        print("1. Revenue Summary Report")
        print("2. Outstanding Fees Report")
        print("3. Payment Collection Report")
        print("4. Student Account Summary")
        print("5. Fee Type Analysis")
        print("6. Payment Method Analysis")
        print("7. Monthly Revenue Trend")
        print("8. Return to Finance Menu")

        choice = input("Enter your choice (1-8): ").strip()

        if choice == '1':
            revenue_summary_report()
        elif choice == '2':
            generate_outstanding_fees_report()
        elif choice == '3':
            generate_payment_collection_report()
        elif choice == '4':
            from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.dashboard import student_account_summary_report
            student_account_summary_report()
        elif choice == '5':
            from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.dashboard import fee_type_analysis_report
            fee_type_analysis_report()
        elif choice == '6':
            from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.dashboard import payment_method_analysis_report
            payment_method_analysis_report()
        elif choice == '7':
            from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.dashboard import monthly_revenue_trend_report
            monthly_revenue_trend_report()
        elif choice == '8':
            return
        else:
            print("Invalid choice. Please try again.")

def revenue_summary_report():
    """Generate revenue summary report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get date range
        start_date = input("Enter start date (YYYY-MM-DD): ").strip()
        end_date = input("Enter end date (YYYY-MM-DD): ").strip()

        cursor.execute('''
        SELECT
            COUNT(*) as total_payments,
            SUM(amount) as total_revenue,
            AVG(amount) as avg_payment,
            MIN(amount) as min_payment,
            MAX(amount) as max_payment
        FROM payments
        WHERE payment_date BETWEEN ? AND ? AND status = 'completed'
        ''', (start_date, end_date))

        summary = cursor.fetchone()

        if summary and summary[0] > 0:
            total_payments, total_revenue, avg_payment, min_payment, max_payment = summary

            print(f"\nRevenue Summary Report ({start_date} to {end_date})")
            print("=" * 60)
            print(f"Total Payments: {total_payments}")
            print(f"Total Revenue: £{total_revenue:,.2f}")
            print(f"Average Payment: £{avg_payment:.2f}")
            print(f"Minimum Payment: £{min_payment:.2f}")
            print(f"Maximum Payment: £{max_payment:.2f}")

            # Revenue by payment method
            cursor.execute('''
            SELECT payment_method, COUNT(*), SUM(amount)
            FROM payments
            WHERE payment_date BETWEEN ? AND ? AND status = 'completed'
            GROUP BY payment_method
            ORDER BY SUM(amount) DESC
            ''', (start_date, end_date))

            method_data = cursor.fetchall()

            print("\nRevenue by Payment Method:")
            print("-" * 60)
            for method, count, amount in method_data:
                percentage = (amount / total_revenue) * 100
                print(f"{method:<20} {count:>6} payments  £{amount:>12,.2f} ({percentage:>5.1f}%)")

        else:
            print("No payments found for the specified date range.")

        conn.close()

    except Exception as e:
        print(f"Error generating revenue summary: {e}")

def generate_budget_variance_report():
    """Generate a basic budget variance report comparing planned vs actual spending."""
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    # This assumes a 'budgets' table and 'expenses' table exist
    try:
        cursor.execute("""
            SELECT b.category, b.allocated_amount,
                   IFNULL(SUM(e.amount), 0) AS actual_spent,
                   (b.allocated_amount - IFNULL(SUM(e.amount), 0)) AS variance
            FROM budgets b
            LEFT JOIN expenses e ON b.category = e.category
            GROUP BY b.category
        """)
        rows = cursor.fetchall()

        print("\n--- Budget Variance Report ---")
        print("{:<20} {:>15} {:>15} {:>15}".format("Category", "Budgeted", "Actual", "Variance"))
        print("-" * 70)

        for row in rows:
            category, allocated, spent, variance = row
            print(f"{category:<20} {allocated:>15.2f} {spent:>15.2f} {variance:>15.2f}")
    except Exception as e:
        print(f"[ERROR] Could not generate budget variance report: {e}")
    finally:
        conn.close()

def generate_outstanding_fees_report():
    """Generate outstanding fees report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name, s.course,
               ft.fee_name, sf.amount, sf.due_date,
               julianday('now') - julianday(sf.due_date) as days_overdue
        FROM student_fees sf
        JOIN students s ON sf.student_id = s.student_id
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        WHERE sf.status IN ('unpaid', 'partial')
        ORDER BY days_overdue DESC, sf.amount DESC
        ''')

        outstanding = cursor.fetchall()

        if not outstanding:
            print("No outstanding fees found.")
            return

        print("\nOutstanding Fees Report")
        print("=" * 120)
        print(f"{'Student ID':<12} {'Name':<25} {'Course':<20} {'Fee Type':<20} {'Amount':<12} {'Due Date':<12} {'Days Overdue':<12}")
        print("-" * 120)

        total_outstanding = 0
        overdue_count = 0

        for row in outstanding:
            student_id, first_name, last_name, course, fee_name, amount, due_date, days_overdue = row
            student_name = f"{first_name} {last_name}"

            if days_overdue > 0:
                overdue_indicator = f"{int(days_overdue)}"
                overdue_count += 1
            else:
                overdue_indicator = "Not due"

            print(f"{student_id:<12} {student_name:<25} {course:<20} {fee_name:<20} £{amount:<11.2f} {due_date:<12} {overdue_indicator:<12}")
            total_outstanding += amount

        print("-" * 120)
        print(f"Total Outstanding: £{total_outstanding:,.2f}")
        print(f"Total Fees: {len(outstanding)}")
        print(f"Overdue Fees: {overdue_count}")
        print("=" * 120)

        conn.close()

    except Exception as e:
        print(f"Error generating outstanding fees report: {e}")

def generate_payment_collection_report():
    """Generate payment collection report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get date range
        start_date = input("Enter start date (YYYY-MM-DD): ").strip()
        end_date = input("Enter end date (YYYY-MM-DD): ").strip()

        # Collection efficiency analysis
        cursor.execute('''
        SELECT
            COUNT(DISTINCT sf.student_id) as total_students,
            SUM(sf.amount) as total_fees_due,
            SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected,
            COUNT(CASE WHEN sf.status = 'paid' THEN 1 END) as fees_paid,
            COUNT(sf.student_fee_id) as total_fees
        FROM student_fees sf
        WHERE sf.created_at BETWEEN ? AND ?
        ''', (start_date + ' 00:00:00', end_date + ' 23:59:59'))

        collection_data = cursor.fetchone()

        if collection_data:
            total_students, total_fees_due, total_collected, fees_paid, total_fees = collection_data

            collection_rate = (total_collected / total_fees_due * 100) if total_fees_due > 0 else 0
            payment_rate = (fees_paid / total_fees * 100) if total_fees > 0 else 0

            print(f"\nPayment Collection Report ({start_date} to {end_date})")
            print("=" * 70)
            print(f"Students with Fees: {total_students}")
            print(f"Total Fees Issued: £{total_fees_due:,.2f}")
            print(f"Total Amount Collected: £{total_collected:,.2f}")
            print(f"Outstanding Amount: £{total_fees_due - total_collected:,.2f}")
            print(f"Collection Rate: {collection_rate:.1f}%")
            print(f"Payment Rate: {payment_rate:.1f}% ({fees_paid}/{total_fees} fees)")

            # Payment timing analysis
            cursor.execute('''
            SELECT
                CASE
                    WHEN julianday(p.payment_date) <= julianday(sf.due_date) THEN 'On Time'
                    WHEN julianday(p.payment_date) - julianday(sf.due_date) <= 7 THEN '1-7 Days Late'
                    WHEN julianday(p.payment_date) - julianday(sf.due_date) <= 30 THEN '8-30 Days Late'
                    ELSE 'Over 30 Days Late'
                END as payment_timing,
                COUNT(*) as count,
                SUM(pa.amount) as amount
            FROM payments p
            JOIN payment_allocations pa ON p.payment_id = pa.payment_id
            JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
            WHERE p.payment_date BETWEEN ? AND ?
            GROUP BY payment_timing
            ORDER BY
                CASE payment_timing
                    WHEN 'On Time' THEN 1
                    WHEN '1-7 Days Late' THEN 2
                    WHEN '8-30 Days Late' THEN 3
                    ELSE 4
                END
            ''', (start_date, end_date))

            timing_data = cursor.fetchall()

            if timing_data:
                print("\nPayment Timing Analysis:")
                print("-" * 50)
                for timing, count, amount in timing_data:
                    print(f"{timing:<20} {count:>8} payments  £{amount:>12,.2f}")

        conn.close()

    except Exception as e:
        print(f"Error generating payment collection report: {e}")

def generate_audit_report(start_date, end_date):
    """Generate audit report for compliance"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to generate audit reports.")
        return

    if not auth.check_permission('view_audit_logs'):
        print("You don't have permission to view audit logs.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT user_id, action, table_name, record_id, new_values, timestamp
        FROM audit_log
        WHERE date(timestamp) BETWEEN ? AND ?
        ORDER BY timestamp DESC
        ''', (start_date, end_date))

        audit_logs = cursor.fetchall()

        if not audit_logs:
            print(f"No audit logs found between {start_date} and {end_date}")
            conn.close()
            return

        print(f"\nAudit Report: {start_date} to {end_date}")
        print("=" * 100)
        print(f"{'Timestamp':<20} {'User':<15} {'Action':<20} {'Table':<15} {'Record ID':<10} {'Details':<20}")
        print("-" * 100)

        for log in audit_logs:
            user_id, action, table_name, record_id, details, timestamp = log
            details_summary = json.loads(details) if details else {}
            details_str = str(details_summary)[:20] + "..." if len(str(details_summary)) > 20 else str(details_summary)

            print(f"{timestamp:<20} {user_id:<15} {action:<20} {table_name:<15} {record_id:<10} {details_str:<20}")

        print("=" * 100)
        print(f"Total audit entries: {len(audit_logs)}")

        # Export option
        export = input("\nExport audit report? (y/n): ").strip().lower()

        if export == 'y':
            filename = f"audit_report_{start_date}_to_{end_date}.csv"

            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Timestamp', 'User', 'Action', 'Table', 'Record ID', 'Details'])

                for log in audit_logs:
                    writer.writerow(log)

            print(f"Audit report exported to {filename}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
