"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def cancel_appointment():
    """Cancel an appointment with refund eligibility check"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to cancel appointments")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("CANCEL APPOINTMENT")

        with get_connection() as conn:
            # Show user's upcoming appointments
            cursor = conn.execute('''
                SELECT booking_ref, service_name, staff_name, appointment_date,
                       appointment_time, price, status
                FROM barber_appointments
                WHERE user_id = ? AND appointment_date >= DATE('now')
                AND status = 'scheduled'
                ORDER BY appointment_date ASC, appointment_time ASC
            ''', (user.get('username'),))
            appointments = cursor.fetchall()

            if not appointments:
                print("\n❌ You have no upcoming appointments to cancel")
                input("\nPress Enter to continue...")
                return

            print("\nYour upcoming appointments:")
            for appt in appointments:
                ref, service, staff, date, time, price, status = appt
                print(f"\n  🎫 {ref}")
                print(f"     {service} with {staff}")
                print(f"     {date} at {time} - GBP {float(price):.2f}")

            booking_ref = input("\nEnter booking reference to cancel (0 to go back): ").strip()
            if booking_ref == "0":
                return

            cursor = conn.execute('''
                SELECT appointment_date, appointment_time, status, price, payment_status
                FROM barber_appointments
                WHERE booking_ref = ? AND user_id = ?
            ''', (booking_ref, user.get('username')))
            appt = cursor.fetchone()

            if not appt:
                print("❌ Appointment not found")
                input("\nPress Enter to continue...")
                return

            date, time, status, price, payment_status = appt

            if status == 'cancelled':
                print("❌ Appointment is already cancelled")
                input("\nPress Enter to continue...")
                return

            if status == 'completed':
                print("❌ Cannot cancel completed appointment")
                input("\nPress Enter to continue...")
                return

            # Check refund eligibility (24 hours notice)
            appointment_datetime = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M')
            hours_until = (appointment_datetime - datetime.now()).total_seconds() / 3600

            refund_eligible = hours_until >= 24

            print("\n⚠️  Cancellation Details:")
            print(f"Appointment: {date} at {time}")
            print(f"Hours until appointment: {hours_until:.1f}")

            if refund_eligible:
                print("✅ Full refund eligible (24+ hours notice)")
            else:
                print("❌ No refund (less than 24 hours notice)")

            if payment_status == 'paid':
                print(f"Payment status: PAID - GBP {float(price):.2f}")

            confirm = input("\nConfirm cancellation? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Cancellation aborted")
                input("\nPress Enter to continue...")
                return

            with transaction() as conn_tx:
                conn_tx.execute('''
                    UPDATE barber_appointments
                    SET status = 'cancelled',
                        notes = COALESCE(notes, '') || ?
                    WHERE booking_ref = ?
                ''', (f"\nCancelled on {datetime.now().strftime('%Y-%m-%d %H:%M')}. Refund: {'Yes' if refund_eligible else 'No'}",
                      booking_ref))

            print("\n✅ Appointment cancelled successfully")

            if refund_eligible and payment_status == 'paid':
                print(f"💰 Refund of GBP {float(price):.2f} will be processed within 3-5 business days")

            if ACTIVITY_LOG_AVAILABLE:
                log_activity('cancel', 'barber_appointment', details={
                    'booking_ref': booking_ref, 'refund_eligible': refund_eligible
                })

            logger.info(f"User {user.get('username')} cancelled appointment {booking_ref}")

    except Exception as e:
        logger.error(f"Error cancelling appointment: {e}")
        print(f"❌ Error cancelling appointment: {e}")

    input("\nPress Enter to continue...")
