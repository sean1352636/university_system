"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def service_popularity_report():
    """View popular services analysis (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("SERVICE POPULARITY ANALYSIS")

        # Get date range
        days = input("\nAnalyze last N days [30]: ").strip()
        try:
            days = int(days) if days else 30
        except ValueError:
            days = 30

        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT
                    service_name,
                    COUNT(*) as bookings,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                    SUM(CASE WHEN status = 'no_show' THEN 1 ELSE 0 END) as no_shows,
                    AVG(price) as avg_price,
                    SUM(CASE WHEN status = 'completed' THEN price ELSE 0 END) as revenue
                FROM barber_appointments
                WHERE appointment_date BETWEEN ? AND ?
                GROUP BY service_name
                ORDER BY bookings DESC
            ''', (start_date, end_date))
            results = cursor.fetchall()

            print(f"\nPeriod: Last {days} days ({start_date} to {end_date})")
            print("\n{:<25} {:<10} {:<10} {:<10} {:<10} {:<12}".format(
                "Service", "Bookings", "Complete", "Cancel", "No-Show", "Revenue"
            ))
            print("-" * 85)

            if not results:
                print("\nNo data available")
            else:
                for row in results:
                    service, bookings, completed, cancelled, no_shows, avg_price, revenue = row
                    print("{:<25} {:<10} {:<10} {:<10} {:<10} GBP {:.2f}".format(
                        service[:24], bookings, completed, cancelled, no_shows, float(revenue or 0)
                    ))

                # Calculate completion rate
                total_bookings = sum(row[1] for row in results)
                total_completed = sum(row[2] for row in results)
                completion_rate = (total_completed / total_bookings * 100) if total_bookings > 0 else 0

                print("\nOverall Statistics:")
                print(f"  Total Bookings: {total_bookings}")
                print(f"  Completed: {total_completed}")
                print(f"  Completion Rate: {completion_rate:.1f}%")

    except Exception as e:
        logger.error(f"Error generating service popularity report: {e}")
        print(f"❌ Error generating service popularity report: {e}")

    input("\nPress Enter to continue...")
