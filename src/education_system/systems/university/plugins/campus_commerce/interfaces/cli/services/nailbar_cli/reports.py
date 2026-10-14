"""Nail bar reporting and analytics."""

import logging
from datetime import date, datetime, timedelta

from education_system.systems.university.infrastructure.database.db import get_connection

from .helpers import format_currency, format_date, is_staff, print_subheader

logger = logging.getLogger(__name__)


def daily_schedule_report():
    """View daily appointment schedule"""
    try:
        print_subheader("DAILY APPOINTMENT SCHEDULE")

        # Get date
        date_str = input("\nEnter date (YYYY-MM-DD, or press Enter for today): ").strip()
        if not date_str:
            report_date = date.today()
        else:
            try:
                report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return

        print(f"\nSchedule for: {format_date(str(report_date))}")
        print("=" * 70)

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT appointment_time, booking_ref, user_name, treatment_names,
                       technician_name, total_duration, total_price, status
                FROM nailbar_appointments
                WHERE appointment_date = ?
                ORDER BY appointment_time
            ''', (str(report_date),))
            appointments = cursor.fetchall()

            if not appointments:
                print("\n❌ No appointments scheduled")
            else:
                for appt_time, ref, customer, treatments, tech, duration, price, status in appointments:
                    status_emoji = {
                        'scheduled': '📅',
                        'confirmed': '✅',
                        'in_progress': '⏳',
                        'completed': '✔️',
                        'cancelled': '❌'
                    }.get(status.lower(), '📋')

                    print(f"\n{appt_time} {status_emoji} [{status.upper()}]")
                    print(f"  Ref: {ref}")
                    print(f"  Customer: {customer}")
                    print(f"  Treatments: {treatments}")
                    print(f"  Technician: {tech}")
                    print(f"  Duration: {duration} min | Price: {format_currency(price)}")

                # Summary
                cursor = conn.execute('''
                    SELECT COUNT(*),
                           SUM(CASE WHEN status = 'completed' THEN total_price ELSE 0 END)
                    FROM nailbar_appointments
                    WHERE appointment_date = ?
                ''', (str(report_date),))
                total_appts, revenue = cursor.fetchone()

                print(f"\n{'━' * 70}")
                print(f"Total Appointments: {total_appts}")
                print(f"Revenue (Completed): {format_currency(revenue or 0)}")

    except Exception as e:
        logger.error(f"Error generating daily schedule: {e}")
        print(f"❌ Error generating daily schedule: {e}")

    input("\nPress Enter to continue...")


def revenue_report():
    """Generate revenue report (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("REVENUE REPORT")

        # Select period
        print("\nSelect period:")
        print("1. Today")
        print("2. This Week")
        print("3. This Month")
        print("4. Custom Range")

        choice = input("\nChoice: ").strip()

        today = date.today()
        if choice == "1":
            start_date = today
            end_date = today
            period_name = "Today"
        elif choice == "2":
            start_date = today - timedelta(days=today.weekday())
            end_date = today
            period_name = "This Week"
        elif choice == "3":
            start_date = today.replace(day=1)
            end_date = today
            period_name = "This Month"
        elif choice == "4":
            start_str = input("Start date (YYYY-MM-DD): ").strip()
            end_str = input("End date (YYYY-MM-DD): ").strip()
            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
                period_name = f"{format_date(str(start_date))} to {format_date(str(end_date))}"
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return
        else:
            print("❌ Invalid choice")
            input("\nPress Enter to continue...")
            return

        print(f"\n{'=' * 70}")
        print(f"  REVENUE REPORT - {period_name}")
        print(f"{'=' * 70}")

        with get_connection() as conn:
            # Total revenue
            cursor = conn.execute('''
                SELECT COALESCE(SUM(amount), 0), COALESCE(SUM(tip_amount), 0),
                       COALESCE(SUM(total_amount), 0), COUNT(*)
                FROM nailbar_payments
                WHERE DATE(payment_date) BETWEEN ? AND ?
                AND status = 'completed'
            ''', (str(start_date), str(end_date)))
            service_revenue, tips, total_revenue, payment_count = cursor.fetchone()

            # Appointments
            cursor = conn.execute('''
                SELECT COUNT(*) FROM nailbar_appointments
                WHERE appointment_date BETWEEN ? AND ?
                AND status = 'completed'
            ''', (str(start_date), str(end_date)))
            completed_appts = cursor.fetchone()[0]

            # By payment method
            cursor = conn.execute('''
                SELECT payment_method, COUNT(*), COALESCE(SUM(total_amount), 0)
                FROM nailbar_payments
                WHERE DATE(payment_date) BETWEEN ? AND ?
                AND status = 'completed'
                GROUP BY payment_method
                ORDER BY payment_method
            ''', (str(start_date), str(end_date)))
            payment_methods = cursor.fetchall()

            print("\n📊 OVERALL METRICS:")
            print(f"  Completed Appointments: {completed_appts}")
            print(f"  Total Payments: {payment_count}")
            print(f"  Service Revenue: {format_currency(service_revenue)}")
            print(f"  Tips: {format_currency(tips)}")
            print(f"  TOTAL REVENUE: {format_currency(total_revenue)}")

            if completed_appts > 0:
                avg_revenue = total_revenue / completed_appts
                print(f"  Average per Appointment: {format_currency(avg_revenue)}")

            if payment_methods:
                print("\n💳 BY PAYMENT METHOD:")
                for method, count, amount in payment_methods:
                    print(f"  {method.upper()}: {count} payments, {format_currency(amount)}")

            # Top treatments
            cursor = conn.execute('''
                SELECT treatment_names, COUNT(*) as count
                FROM nailbar_appointments
                WHERE appointment_date BETWEEN ? AND ?
                AND status = 'completed'
                GROUP BY treatment_names
                ORDER BY count DESC
                LIMIT 5
            ''', (str(start_date), str(end_date)))
            top_treatments = cursor.fetchall()

            if top_treatments:
                print("\n🌟 TOP TREATMENTS:")
                for idx, (treatment, count) in enumerate(top_treatments, 1):
                    print(f"  {idx}. {treatment} ({count} appointments)")

    except Exception as e:
        logger.error(f"Error generating revenue report: {e}")
        print(f"❌ Error generating revenue report: {e}")

    input("\nPress Enter to continue...")


def popular_treatments_analysis():
    """Analyze popular treatments (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("POPULAR TREATMENTS ANALYSIS")

        # Time period
        print("\nSelect period:")
        print("1. Last 7 days")
        print("2. Last 30 days")
        print("3. Last 90 days")
        print("4. All time")

        choice = input("\nChoice: ").strip()

        today = date.today()
        if choice == "1":
            start_date = today - timedelta(days=7)
            period_name = "Last 7 Days"
        elif choice == "2":
            start_date = today - timedelta(days=30)
            period_name = "Last 30 Days"
        elif choice == "3":
            start_date = today - timedelta(days=90)
            period_name = "Last 90 Days"
        else:
            start_date = date(2000, 1, 1)
            period_name = "All Time"

        print(f"\n{'=' * 70}")
        print(f"  POPULAR TREATMENTS - {period_name}")
        print(f"{'=' * 70}")

        with get_connection() as conn:
            # This is a simplified analysis - in production you'd parse treatment_ids
            cursor = conn.execute('''
                SELECT treatment_names, COUNT(*) as booking_count,
                       COALESCE(SUM(total_price), 0) as revenue
                FROM nailbar_appointments
                WHERE appointment_date >= ?
                AND status = 'completed'
                GROUP BY treatment_names
                ORDER BY booking_count DESC
                LIMIT 15
            ''', (str(start_date),))
            treatments = cursor.fetchall()

            if not treatments:
                print("\n❌ No data available")
            else:
                total_bookings = sum(count for _, count, _ in treatments)
                total_revenue = sum(revenue for _, _, revenue in treatments)

                print("\n📊 TREATMENT POPULARITY:")
                print(f"{'━' * 70}")

                for idx, (treatment, count, revenue) in enumerate(treatments, 1):
                    percentage = (count / total_bookings * 100) if total_bookings > 0 else 0
                    avg_price = revenue / count if count > 0 else 0

                    print(f"\n{idx}. {treatment}")
                    print(f"   Bookings: {count} ({percentage:.1f}%)")
                    print(f"   Revenue: {format_currency(revenue)}")
                    print(f"   Avg Price: {format_currency(avg_price)}")

                print(f"\n{'━' * 70}")
                print(f"Total Bookings Analyzed: {total_bookings}")
                print(f"Total Revenue: {format_currency(total_revenue)}")

    except Exception as e:
        logger.error(f"Error analyzing treatments: {e}")
        print(f"❌ Error analyzing treatments: {e}")

    input("\nPress Enter to continue...")


def customer_retention_stats():
    """View customer retention statistics (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("CUSTOMER RETENTION STATISTICS")

        with get_connection() as conn:
            # Total unique customers
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT user_id) FROM nailbar_appointments
                WHERE status = 'completed'
            ''')
            total_customers = cursor.fetchone()[0]

            # Repeat customers (2+ appointments)
            cursor = conn.execute('''
                SELECT COUNT(*) FROM (
                    SELECT user_id FROM nailbar_appointments
                    WHERE status = 'completed'
                    GROUP BY user_id
                    HAVING COUNT(*) >= 2
                )
            ''')
            repeat_customers = cursor.fetchone()[0]

            # Loyal customers (5+ appointments)
            cursor = conn.execute('''
                SELECT COUNT(*) FROM (
                    SELECT user_id FROM nailbar_appointments
                    WHERE status = 'completed'
                    GROUP BY user_id
                    HAVING COUNT(*) >= 5
                )
            ''')
            loyal_customers = cursor.fetchone()[0]

            # Top customers
            cursor = conn.execute('''
                SELECT user_name, user_id, COUNT(*) as visit_count,
                       COALESCE(SUM(total_price), 0) as total_spent
                FROM nailbar_appointments
                WHERE status = 'completed'
                GROUP BY user_id, user_name
                ORDER BY visit_count DESC
                LIMIT 10
            ''')
            top_customers = cursor.fetchall()

            print(f"\n{'=' * 70}")
            print("📊 CUSTOMER BASE:")
            print(f"{'=' * 70}")
            print(f"\nTotal Customers: {total_customers}")
            print(f"Repeat Customers (2+ visits): {repeat_customers}")
            print(f"Loyal Customers (5+ visits): {loyal_customers}")

            if total_customers > 0:
                repeat_rate = (repeat_customers / total_customers * 100)
                loyal_rate = (loyal_customers / total_customers * 100)
                print(f"\nRepeat Customer Rate: {repeat_rate:.1f}%")
                print(f"Loyalty Rate: {loyal_rate:.1f}%")

            if top_customers:
                print("\n🌟 TOP CUSTOMERS:")
                print(f"{'━' * 70}")
                for idx, (name, user_id, visits, spent) in enumerate(top_customers, 1):
                    avg_spent = spent / visits if visits > 0 else 0
                    print(f"\n{idx}. {name} ({user_id})")
                    print(f"   Visits: {visits}")
                    print(f"   Total Spent: {format_currency(spent)}")
                    print(f"   Avg per Visit: {format_currency(avg_spent)}")

            # Recent activity (last 30 days)
            thirty_days_ago = date.today() - timedelta(days=30)
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT user_id) FROM nailbar_appointments
                WHERE appointment_date >= ? AND status = 'completed'
            ''', (str(thirty_days_ago),))
            recent_customers = cursor.fetchone()[0]

            print(f"\n{'━' * 70}")
            print(f"Active Customers (Last 30 Days): {recent_customers}")

    except Exception as e:
        logger.error(f"Error generating retention stats: {e}")
        print(f"❌ Error generating retention stats: {e}")

    input("\nPress Enter to continue...")


__all__ = [
    'daily_schedule_report', 'revenue_report', 'popular_treatments_analysis',
    'customer_retention_stats',
]
