"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def view_staff_schedules():
    """View staff schedules and availability (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff and administrators")
        input("\nPress Enter to continue...")
        return

    try:
        view_staff()

        staff_id = input("\nEnter staff ID to view schedule (0 for all, blank to cancel): ").strip()
        if not staff_id:
            return

        date_str = input("Enter date (YYYY-MM-DD) [today]: ").strip()
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
        else:
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return

        print_subheader(f"SCHEDULE FOR {date_str}")

        with get_connection() as conn:
            if staff_id == "0":
                # All staff
                cursor = conn.execute('''
                    SELECT staff_id, staff_name FROM barber_staff WHERE status = 'active'
                    ORDER BY staff_name
                ''')
                staff_list = cursor.fetchall()
            else:
                cursor = conn.execute('''
                    SELECT staff_id, staff_name FROM barber_staff WHERE staff_id = ? AND status = 'active'
                ''', (staff_id,))
                staff_list = cursor.fetchall()

            if not staff_list:
                print("\n❌ No staff found")
                input("\nPress Enter to continue...")
                return

            for staff_member in staff_list:
                s_id, s_name = staff_member
                print(f"\n{s_name} (ID: {s_id}):")
                print("-" * 50)

                # Get appointments for this staff on this date
                cursor = conn.execute('''
                    SELECT appointment_time, service_name, duration_minutes, status, user_name
                    FROM barber_appointments
                    WHERE staff_id = ? AND appointment_date = ?
                    ORDER BY appointment_time
                ''', (s_id, date_str))
                appointments = cursor.fetchall()

                if not appointments:
                    print("  No appointments scheduled")
                else:
                    for appt in appointments:
                        time, service, duration, status, customer = appt
                        print(f"  {time} - {service} ({duration}min) - {customer} [{status}]")

    except Exception as e:
        logger.error(f"Error viewing staff schedules: {e}")
        print(f"❌ Error viewing staff schedules: {e}")

    input("\nPress Enter to continue...")
