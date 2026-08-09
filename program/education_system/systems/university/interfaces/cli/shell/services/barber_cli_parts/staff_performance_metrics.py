"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def staff_performance_metrics():
    """View staff performance metrics (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff and administrators")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("STAFF PERFORMANCE METRICS")

        period = input("\nSelect period (1=Today, 2=This Week, 3=This Month, 4=Custom): ").strip()

        if period == "1":
            start_date = datetime.now().strftime('%Y-%m-%d')
            end_date = start_date
        elif period == "2":
            today = datetime.now()
            start_date = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
        elif period == "3":
            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
        elif period == "4":
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD): ").strip()
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return
        else:
            print("❌ Invalid option")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT
                    s.staff_id,
                    s.staff_name,
                    COUNT(a.appointment_id) as total_appointments,
                    SUM(CASE WHEN a.status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN a.status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                    SUM(CASE WHEN a.status = 'no_show' THEN 1 ELSE 0 END) as no_shows,
                    COALESCE(SUM(t.amount), 0) as revenue,
                    COALESCE(SUM(t.tip_amount), 0) as tips
                FROM barber_staff s
                LEFT JOIN barber_appointments a ON s.staff_id = a.staff_id
                    AND a.appointment_date BETWEEN ? AND ?
                LEFT JOIN transactions t ON a.appointment_id = t.reference_id AND t.reference_type = 'appointment' AND t.source_type = 'barber'
                WHERE s.status = 'active'
                GROUP BY s.staff_id, s.staff_name
                ORDER BY revenue DESC
            ''', (start_date, end_date))

            results = cursor.fetchall()

            print(f"\nPeriod: {start_date} to {end_date}")
            print("\n{:<20} {:<10} {:<10} {:<10} {:<10} {:<12} {:<12}".format(
                "Name", "Total", "Complete", "Cancel", "No-Show", "Revenue", "Tips"
            ))
            print("-" * 95)

            if not results:
                print("No data available for this period")
            else:
                for row in results:
                    staff_id, name, total, completed, cancelled, no_shows, revenue, tips = row
                    print("{:<20} {:<10} {:<10} {:<10} {:<10} {:<12.2f} {:<12.2f}".format(
                        name[:19], total or 0, completed or 0, cancelled or 0,
                        no_shows or 0, float(revenue or 0), float(tips or 0)
                    ))

    except Exception as e:
        logger.error(f"Error viewing staff performance: {e}")
        print(f"❌ Error viewing staff performance: {e}")

    input("\nPress Enter to continue...")
