"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def customer_retention_stats():
    """View customer retention statistics (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("CUSTOMER RETENTION STATISTICS")

        # Get date range
        days = input("\nAnalyze last N days [90]: ").strip()
        try:
            days = int(days) if days else 90
        except ValueError:
            days = 90

        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')

        with get_connection() as conn:
            # Total unique customers
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT user_id) as total_customers
                FROM barber_appointments
                WHERE appointment_date BETWEEN ? AND ?
            ''', (start_date, end_date))
            total_customers = cursor.fetchone()[0] or 0

            # New vs returning
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT user_id) as new_customers
                FROM barber_appointments a
                WHERE appointment_date BETWEEN ? AND ?
                AND NOT EXISTS (
                    SELECT 1 FROM barber_appointments b
                    WHERE b.user_id = a.user_id
                    AND b.appointment_date < ?
                )
            ''', (start_date, end_date, start_date))
            new_customers = cursor.fetchone()[0] or 0
            returning_customers = total_customers - new_customers

            # Visit frequency
            cursor = conn.execute('''
                SELECT
                    user_id,
                    user_name,
                    COUNT(*) as visit_count,
                    SUM(price) as total_spent
                FROM barber_appointments
                WHERE appointment_date BETWEEN ? AND ?
                AND status = 'completed'
                GROUP BY user_id, user_name
                ORDER BY visit_count DESC
                LIMIT 10
            ''', (start_date, end_date))
            top_customers = cursor.fetchall()

            print(f"\nPeriod: Last {days} days ({start_date} to {end_date})")
            print(f"\n{'='*60}")
            print("CUSTOMER SUMMARY")
            print(f"{'='*60}")
            print(f"Total Unique Customers:  {total_customers}")
            print(f"New Customers:           {new_customers}")
            print(f"Returning Customers:     {returning_customers}")

            if total_customers > 0:
                retention_rate = (returning_customers / total_customers * 100)
                print(f"Retention Rate:          {retention_rate:.1f}%")

            if top_customers:
                print(f"\n{'='*60}")
                print("TOP 10 FREQUENT CUSTOMERS")
                print(f"{'='*60}")
                print("\n{:<25} {:<10} {:<15}".format("Customer", "Visits", "Total Spent"))
                print("-" * 55)

                for customer_id, name, visits, spent in top_customers:
                    print("{:<25} {:<10} GBP {:.2f}".format(
                        name[:24], visits, float(spent or 0)
                    ))

    except Exception as e:
        logger.error(f"Error generating retention statistics: {e}")
        print(f"❌ Error generating retention statistics: {e}")

    input("\nPress Enter to continue...")
