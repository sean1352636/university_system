"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def reschedule_appointment():
    """Reschedule an appointment to a new date/time"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to reschedule appointments")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("RESCHEDULE APPOINTMENT")

        with get_connection() as conn:
            # Show user's upcoming appointments
            cursor = conn.execute('''
                SELECT booking_ref, service_name, staff_name, staff_id, appointment_date,
                       appointment_time, price, status
                FROM barber_appointments
                WHERE user_id = ? AND appointment_date >= DATE('now')
                AND status = 'scheduled'
                ORDER BY appointment_date ASC, appointment_time ASC
            ''', (user.get('username'),))
            appointments = cursor.fetchall()

            if not appointments:
                print("\n❌ You have no upcoming appointments to reschedule")
                input("\nPress Enter to continue...")
                return

            print("\nYour upcoming appointments:")
            for appt in appointments:
                ref, service, staff, staff_id, date, time, price, status = appt
                print(f"\n  🎫 {ref}")
                print(f"     {service} with {staff}")
                print(f"     {date} at {time}")

            booking_ref = input("\nEnter booking reference to reschedule (0 to cancel): ").strip()
            if booking_ref == "0":
                return

            cursor = conn.execute('''
                SELECT appointment_id, service_name, staff_id, staff_name, appointment_date, appointment_time
                FROM barber_appointments
                WHERE booking_ref = ? AND user_id = ? AND status = 'scheduled'
            ''', (booking_ref, user.get('username')))
            appt = cursor.fetchone()

            if not appt:
                print("❌ Appointment not found")
                input("\nPress Enter to continue...")
                return

            appt_id, service_name, old_staff_id, old_staff_name, old_date, old_time = appt

            print(f"\nCurrent appointment: {service_name} with {old_staff_name} on {old_date} at {old_time}")

            # New date
            new_date_str = input("\nEnter new date (YYYY-MM-DD) [keep current]: ").strip()
            if new_date_str:
                try:
                    new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
                    if new_date < datetime.now().date():
                        print("❌ Cannot reschedule to past dates")
                        input("\nPress Enter to continue...")
                        return
                except ValueError:
                    print("❌ Invalid date format")
                    input("\nPress Enter to continue...")
                    return
            else:
                new_date = datetime.strptime(old_date, '%Y-%m-%d').date()

            # Show available slots for the barber on new date
            cursor = conn.execute('''
                SELECT appointment_time FROM barber_appointments
                WHERE staff_id = ? AND appointment_date = ?
                AND status NOT IN ('cancelled', 'no_show')
                AND appointment_id != ?
            ''', (old_staff_id, str(new_date), appt_id))
            booked = [row[0] for row in cursor.fetchall()]
            available_slots = [slot for slot in TIME_SLOTS if slot not in booked]

            if not available_slots:
                print(f"❌ No time slots available for {old_staff_name} on {new_date}")
                input("\nPress Enter to continue...")
                return

            print(f"\nAvailable time slots for {old_staff_name} on {new_date}:")
            for i, slot in enumerate(available_slots, 1):
                print(f"  {slot}", end="  ")
                if i % 6 == 0:
                    print()
            print()

            new_time = input("\nEnter new time (HH:MM): ").strip()
            if new_time not in available_slots:
                print("❌ Time slot not available")
                input("\nPress Enter to continue...")
                return

            print(f"\n{'='*60}")
            print("RESCHEDULING SUMMARY")
            print(f"{'='*60}")
            print(f"Old: {old_date} at {old_time}")
            print(f"New: {new_date} at {new_time}")
            print(f"{'='*60}")

            confirm = input("\nConfirm reschedule? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Reschedule cancelled")
                input("\nPress Enter to continue...")
                return

            with transaction() as conn_tx:
                conn_tx.execute('''
                    UPDATE barber_appointments
                    SET appointment_date = ?,
                        appointment_time = ?,
                        notes = COALESCE(notes, '') || ?
                    WHERE appointment_id = ?
                ''', (str(new_date), new_time,
                      f"\nRescheduled from {old_date} {old_time} on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                      appt_id))

            print("\n✅ Appointment rescheduled successfully!")
            print(f"📅 New appointment: {new_date} at {new_time}")

            if ACTIVITY_LOG_AVAILABLE:
                log_activity('update', 'barber_appointment', details={
                    'booking_ref': booking_ref, 'action': 'reschedule'
                })

    except Exception as e:
        logger.error(f"Error rescheduling appointment: {e}")
        print(f"❌ Error rescheduling appointment: {e}")

    input("\nPress Enter to continue...")
