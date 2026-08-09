"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def check_in_appointment():
    """Check in for an appointment (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("CHECK-IN APPOINTMENT")

        # Show today's scheduled appointments
        with get_connection() as conn:
            today = datetime.now().strftime('%Y-%m-%d')
            cursor = conn.execute('''
                SELECT booking_ref, user_name, service_name, staff_name,
                       appointment_time, status
                FROM barber_appointments
                WHERE appointment_date = ? AND status = 'scheduled'
                ORDER BY appointment_time
            ''', (today,))
            appointments = cursor.fetchall()

            if not appointments:
                print("\n❌ No scheduled appointments for today")
                input("\nPress Enter to continue...")
                return

            print(f"\nScheduled appointments for {today}:")
            for appt in appointments:
                ref, customer, service, staff, time, status = appt
                print(f"\n  🎫 {ref} - {time}")
                print(f"     Customer: {customer}")
                print(f"     Service: {service} with {staff}")

            booking_ref = input("\nEnter booking reference to check in (0 to cancel): ").strip()
            if booking_ref == "0":
                return

            cursor = conn.execute('''
                SELECT appointment_id, user_name, service_name, status
                FROM barber_appointments
                WHERE booking_ref = ? AND appointment_date = ?
            ''', (booking_ref, today))
            appt = cursor.fetchone()

            if not appt:
                print("❌ Appointment not found")
                input("\nPress Enter to continue...")
                return

            appt_id, customer, service, status = appt

            if status != 'scheduled':
                print(f"❌ Appointment status is '{status}' - can only check in scheduled appointments")
                input("\nPress Enter to continue...")
                return

            print(f"\nCheck in {customer} for {service}?")
            confirm = input("Confirm (yes/no): ").strip().lower()

            if confirm != 'yes':
                print("❌ Check-in cancelled")
                input("\nPress Enter to continue...")
                return

            with transaction() as conn_tx:
                conn_tx.execute('''
                    UPDATE barber_appointments
                    SET status = 'checked_in'
                    WHERE appointment_id = ?
                ''', (appt_id,))

            print(f"\n✅ {customer} checked in successfully!")

            if ACTIVITY_LOG_AVAILABLE:
                log_activity('update', 'barber_appointment', details={
                    'booking_ref': booking_ref, 'action': 'check_in'
                })

    except Exception as e:
        logger.error(f"Error checking in appointment: {e}")
        print(f"❌ Error checking in appointment: {e}")

    input("\nPress Enter to continue...")
