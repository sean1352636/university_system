"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def view_my_appointments():
    """View user's appointment history"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to view appointments")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("MY APPOINTMENTS")

        with get_connection() as conn:
            # Upcoming appointments
            cursor = conn.execute('''
                SELECT booking_ref, service_name, staff_name, appointment_date,
                       appointment_time, price, status, created_at
                FROM barber_appointments
                WHERE user_id = ? AND appointment_date >= DATE('now')
                AND status NOT IN ('cancelled', 'completed')
                ORDER BY appointment_date ASC, appointment_time ASC
            ''', (user.get('username'),))
            upcoming = cursor.fetchall()

            # Past appointments
            cursor = conn.execute('''
                SELECT booking_ref, service_name, staff_name, appointment_date,
                       appointment_time, price, status, created_at
                FROM barber_appointments
                WHERE user_id = ? AND (appointment_date < DATE('now') OR status IN ('cancelled', 'completed'))
                ORDER BY appointment_date DESC, appointment_time DESC
                LIMIT 10
            ''', (user.get('username'),))
            past = cursor.fetchall()

            if upcoming:
                print("\n📅 UPCOMING APPOINTMENTS:")
                print("-" * 70)
                for appt in upcoming:
                    ref, service, staff, date, time, price, status, created = appt
                    print(f"\n🎫 Booking: {ref}")
                    print(f"   Service: {service}")
                    print(f"   Barber: {staff}")
                    print(f"   Date/Time: {date} at {time}")
                    print(f"   Price: GBP {float(price):.2f}")
                    print(f"   Status: {status.upper()}")
            else:
                print("\n📅 No upcoming appointments")

            if past:
                print("\n\n📜 PAST APPOINTMENTS:")
                print("-" * 70)
                for appt in past:
                    ref, service, staff, date, time, price, status, created = appt
                    status_icon = "✅" if status == "completed" else "❌"
                    print(f"\n{status_icon} Booking: {ref}")
                    print(f"   Service: {service}")
                    print(f"   Barber: {staff}")
                    print(f"   Date/Time: {date} at {time}")
                    print(f"   Price: GBP {float(price):.2f}")
                    print(f"   Status: {status.upper()}")
            else:
                print("\n\n📜 No past appointments")

            if not upcoming and not past:
                print("\nYou have no appointments")

    except Exception as e:
        logger.error(f"Error viewing appointments: {e}")
        print(f"❌ Error viewing appointments: {e}")

    input("\nPress Enter to continue...")
