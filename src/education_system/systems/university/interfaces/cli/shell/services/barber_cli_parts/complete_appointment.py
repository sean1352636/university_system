"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def complete_appointment():
    """Complete an appointment and process payment (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("COMPLETE APPOINTMENT")

        user = get_current_user()

        with get_connection() as conn:
            # Show checked-in or in-progress appointments
            cursor = conn.execute('''
                SELECT booking_ref, user_id, user_name, service_name, staff_name,
                       appointment_time, price, payment_status, status
                FROM barber_appointments
                WHERE appointment_date = DATE('now')
                AND status IN ('checked_in', 'in_progress')
                ORDER BY appointment_time
            ''')
            appointments = cursor.fetchall()

            if not appointments:
                print("\n❌ No appointments ready to complete")
                input("\nPress Enter to continue...")
                return

            print("\nAppointments ready to complete:")
            for appt in appointments:
                ref, user_id, customer, service, staff, time, price, payment_status, status = appt
                print(f"\n  🎫 {ref} - {time} [{status}]")
                print(f"     Customer: {customer}")
                print(f"     Service: {service} with {staff}")
                print(f"     Price: GBP {float(price):.2f}")
                print(f"     Payment: {payment_status}")

            booking_ref = input("\nEnter booking reference to complete (0 to cancel): ").strip()
            if booking_ref == "0":
                return

            cursor = conn.execute('''
                SELECT appointment_id, user_id, user_name, user_email, service_name,
                       price, payment_status, status
                FROM barber_appointments
                WHERE booking_ref = ?
            ''', (booking_ref,))
            appt = cursor.fetchone()

            if not appt:
                print("❌ Appointment not found")
                input("\nPress Enter to continue...")
                return

            appt_id, customer_id, customer_name, customer_email, service_name, price, payment_status, status = appt

            if status not in ['checked_in', 'in_progress']:
                print(f"❌ Appointment must be checked in first (current status: {status})")
                input("\nPress Enter to continue...")
                return

            # Service notes
            notes = input("\nService notes (optional): ").strip()

            if payment_status != 'paid':
                print("\n💰 PAYMENT PROCESSING")
                print(f"Amount due: GBP {float(price):.2f}")

                print("\nPayment methods:")
                print("  1. Cash")
                print("  2. Card")
                print("  3. Student Account")

                payment_choice = input("\nSelect payment method (1-3): ").strip()

                payment_methods = {'1': 'cash', '2': 'card', '3': 'student_account'}
                payment_method = payment_methods.get(payment_choice)

                if not payment_method:
                    print("❌ Invalid payment method")
                    input("\nPress Enter to continue...")
                    return

                # Tip
                tip_input = input("\nTip amount (GBP) [0.00]: ").strip()
                try:
                    tip_amount = float(tip_input) if tip_input else 0.0
                except ValueError:
                    tip_amount = 0.0

                total_amount = float(price) + tip_amount

                print(f"\n{'='*50}")
                print(f"Service:  GBP {float(price):.2f}")
                if tip_amount > 0:
                    print(f"Tip:      GBP {tip_amount:.2f}")
                print(f"Total:    GBP {total_amount:.2f}")
                print(f"Method:   {payment_method.replace('_', ' ').title()}")
                print(f"{'='*50}")

                confirm = input("\nProcess payment? (yes/no): ").strip().lower()
                if confirm != 'yes':
                    print("❌ Payment cancelled")
                    input("\nPress Enter to continue...")
                    return

                # Generate reference
                ref_number = f"BARBER-PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                with transaction() as conn_tx:
                    # Record transaction
                    conn_tx.execute('''
                        INSERT INTO transactions
                        (source_type, reference_id, reference_type, customer_id, amount, payment_method, tip_amount,
                         reference_number, status, created_at)
                        VALUES ('barber', ?, 'appointment', ?, ?, ?, ?, ?, 'completed', ?)
                    ''', (appt_id, customer_id, price, payment_method, tip_amount,
                          ref_number, datetime.now().isoformat()))

                    # Update appointment
                    conn_tx.execute('''
                        UPDATE barber_appointments
                        SET status = 'completed',
                            payment_status = 'paid',
                            payment_method = ?,
                            notes = COALESCE(notes, '') || ?
                        WHERE appointment_id = ?
                    ''', (payment_method, f"\n{notes}" if notes else "", appt_id))

                print("\n✅ Appointment completed and payment processed!")
                print(f"💳 Transaction reference: {ref_number}")

                # Try to record in finance system
                if FINANCE_AVAILABLE:
                    try:
                        if payment_method == 'student_account':
                            process_student_finance_account_payment(
                                customer_id, total_amount, 'Barber Shop Service', ref_number
                            )
                        else:
                            record_payment_to_finance(
                                customer_id, total_amount, payment_method,
                                'Barber Shop Service', ref_number
                            )
                        print("✅ Payment recorded in finance system")
                    except Exception as fin_err:
                        logger.warning(f"Could not record to finance system: {fin_err}")

                # Send receipt email
                if EMAIL_AVAILABLE and customer_email:
                    try:
                        send_email(
                            to_email=customer_email,
                            subject="Barber Shop Receipt",
                            template_name="barber_receipt",
                            variables={
                                'customer_name': customer_name,
                                'booking_ref': booking_ref,
                                'service_name': service_name,
                                'amount': float(price),
                                'tip': tip_amount,
                                'total': total_amount,
                                'payment_method': payment_method,
                                'reference_number': ref_number,
                                'date': datetime.now().strftime('%Y-%m-%d %H:%M')
                            }
                        )
                        print("📧 Receipt sent to customer")
                    except Exception as email_err:
                        logger.warning(f"Could not send receipt email: {email_err}")

            else:
                # Already paid, just complete
                with transaction() as conn_tx:
                    conn_tx.execute('''
                        UPDATE barber_appointments
                        SET status = 'completed',
                            notes = COALESCE(notes, '') || ?
                        WHERE appointment_id = ?
                    ''', (f"\n{notes}" if notes else "", appt_id))

                print("\n✅ Appointment marked as completed!")

            if ACTIVITY_LOG_AVAILABLE:
                log_activity('complete', 'barber_appointment', details={
                    'booking_ref': booking_ref
                })

    except Exception as e:
        logger.error(f"Error completing appointment: {e}")
        print(f"❌ Error completing appointment: {e}")

    input("\nPress Enter to continue...")
