"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def daily_schedule():
    """View daily appointment schedule (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("DAILY APPOINTMENT SCHEDULE")

        date_str = input("\nEnter date (YYYY-MM-DD) [today]: ").strip()
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
        else:
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT appointment_time, user_name, service_name, staff_name,
                       duration_minutes, status, booking_ref
                FROM barber_appointments
                WHERE appointment_date = ?
                ORDER BY appointment_time
            ''', (date_str,))
            appointments = cursor.fetchall()

            print(f"\nSchedule for {date_str}")
            print("-" * 90)

            if not appointments:
                print("\nNo appointments scheduled")
            else:
                print("\n{:<8} {:<20} {:<20} {:<15} {:<8} {:<12}".format(
                    "Time", "Customer", "Service", "Barber", "Duration", "Status"
                ))
                print("-" * 90)

                for appt in appointments:
                    time, customer, service, staff, duration, status, ref = appt
                    status_icon = {
                        'scheduled': '📅',
                        'checked_in': '✅',
                        'in_progress': '⏳',
                        'completed': '✔️',
                        'cancelled': '❌',
                        'no_show': '🚫'
                    }.get(status, '  ')

                    print("{:<8} {:<20} {:<20} {:<15} {:<8} {} {}".format(
                        time,
                        customer[:19],
                        service[:19],
                        staff[:14],
                        f"{duration}min",
                        status_icon,
                        status
                    ))

            # Summary
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'scheduled' THEN 1 ELSE 0 END) as scheduled,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                    SUM(CASE WHEN status = 'no_show' THEN 1 ELSE 0 END) as no_shows
                FROM barber_appointments
                WHERE appointment_date = ?
            ''', (date_str,))
            summary = cursor.fetchone()

            if summary and summary[0] > 0:
                total, completed, scheduled, cancelled, no_shows = summary
                print("\nSummary:")
                print(f"  Total: {total} | Completed: {completed} | Scheduled: {scheduled}")
                print(f"  Cancelled: {cancelled} | No-shows: {no_shows}")

    except Exception as e:
        logger.error(f"Error viewing daily schedule: {e}")
        print(f"❌ Error viewing daily schedule: {e}")

    input("\nPress Enter to continue...")
