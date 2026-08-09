"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def book_appointment():
    """Book a barber appointment"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to book appointments")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("BOOK APPOINTMENT")

        # Show services
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT service_id, service_name, price, duration_minutes, description
                FROM barber_services
                WHERE status = 'active'
                ORDER BY service_name
            ''')
            services = cursor.fetchall()

            if not services:
                print("\n❌ No services available")
                input("\nPress Enter to continue...")
                return

            print("\nAvailable Services:")
            for svc in services:
                svc_id, name, price, duration, desc = svc
                print(f"  [{svc_id}] {name} - GBP {float(price):.2f} ({duration} min)")
                if desc:
                    print(f"      {desc}")

            service_id = input("\nEnter service ID (0 to cancel): ").strip()
            if service_id == "0":
                return

            if not service_id.isdigit():
                print("❌ Invalid service ID")
                input("\nPress Enter to continue...")
                return

            cursor = conn.execute('''
                SELECT service_name, price, duration_minutes
                FROM barber_services
                WHERE service_id = ? AND status = 'active'
            ''', (service_id,))
            service = cursor.fetchone()

            if not service:
                print("❌ Service not found")
                input("\nPress Enter to continue...")
                return

            service_name, price, duration = service

            print(f"\n✂️  Selected: {service_name} - GBP {float(price):.2f} ({duration} min)")

            # Show staff
            cursor = conn.execute('''
                SELECT staff_id, staff_name, specialization
                FROM barber_staff
                WHERE status = 'active'
                ORDER BY staff_name
            ''')
            staff_list = cursor.fetchall()

            print("\nAvailable Barbers:")
            print("  [0] Any Available Barber")
            for staff in staff_list:
                s_id, s_name, s_spec = staff
                spec_text = f" - {s_spec}" if s_spec else ""
                print(f"  [{s_id}] {s_name}{spec_text}")

            staff_id = input("\nEnter barber ID (0 for any): ").strip()
            if staff_id and staff_id != "0" and not staff_id.isdigit():
                print("❌ Invalid staff ID")
                input("\nPress Enter to continue...")
                return

            staff_name = "Any Available"
            if staff_id and staff_id != "0":
                cursor = conn.execute('''
                    SELECT staff_name FROM barber_staff
                    WHERE staff_id = ? AND status = 'active'
                ''', (staff_id,))
                staff_row = cursor.fetchone()
                if staff_row:
                    staff_name = staff_row[0]
                else:
                    print("❌ Barber not found")
                    input("\nPress Enter to continue...")
                    return
            else:
                staff_id = None

            # Get appointment date
            date_str = input("\nEnter appointment date (YYYY-MM-DD): ").strip()
            try:
                appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                if appointment_date < datetime.now().date():
                    print("❌ Cannot book appointments in the past")
                    input("\nPress Enter to continue...")
                    return
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return

            # Show available time slots
            if staff_id:
                cursor = conn.execute('''
                    SELECT appointment_time FROM barber_appointments
                    WHERE staff_id = ? AND appointment_date = ?
                    AND status NOT IN ('cancelled', 'no_show')
                ''', (staff_id, str(appointment_date)))
                booked = [row[0] for row in cursor.fetchall()]
                available_slots = [slot for slot in TIME_SLOTS if slot not in booked]
            else:
                available_slots = TIME_SLOTS

            if not available_slots:
                print("❌ No time slots available for this date")
                input("\nPress Enter to continue...")
                return

            print("\nAvailable time slots:")
            for i, slot in enumerate(available_slots, 1):
                print(f"  {slot}", end="  ")
                if i % 6 == 0:
                    print()
            print()

            time_str = input("\nEnter appointment time (HH:MM): ").strip()
            if time_str not in TIME_SLOTS:
                print("❌ Invalid time or time not available")
                input("\nPress Enter to continue...")
                return

            # Special requests
            special_requests = input("\nAny special requests? (optional): ").strip()

            # Generate booking reference
            booking_ref = f"BARBER-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(2).upper()}"

            print(f"\n{'='*60}")
            print("APPOINTMENT SUMMARY")
            print(f"{'='*60}")
            print(f"Service:         {service_name}")
            print(f"Barber:          {staff_name}")
            print(f"Date:            {appointment_date}")
            print(f"Time:            {time_str}")
            print(f"Duration:        {duration} minutes")
            print(f"Price:           GBP {float(price):.2f}")
            if special_requests:
                print(f"Special Request: {special_requests}")
            print(f"{'='*60}")

            confirm = input("\nConfirm booking? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Booking cancelled")
                input("\nPress Enter to continue...")
                return

            with transaction() as conn_tx:
                conn_tx.execute('''
                    INSERT INTO barber_appointments
                    (booking_ref, user_id, user_name, user_email, service_id, service_name,
                     staff_id, staff_name, appointment_date, appointment_time,
                     duration_minutes, price, status, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?, ?)
                ''', (booking_ref, user.get('username'), user.get('full_name', user.get('username')),
                      user.get('email', ''), service_id, service_name, staff_id, staff_name,
                      str(appointment_date), time_str, duration, price, special_requests,
                      datetime.now().isoformat()))

            print("\n✅ Appointment booked successfully!")
            print(f"📋 Booking Reference: {booking_ref}")
            print("\n⚠️  Please arrive 5 minutes early for your appointment")

            # Send confirmation email
            if EMAIL_AVAILABLE and user.get('email'):
                try:
                    send_email(
                        to_email=user.get('email'),
                        subject="Barber Shop Appointment Confirmation",
                        template_name="barber_appointment_confirmation",
                        variables={
                            'customer_name': user.get('full_name', user.get('username')),
                            'booking_ref': booking_ref,
                            'service_name': service_name,
                            'appointment_date': str(appointment_date),
                            'appointment_time': time_str,
                            'barber_name': staff_name,
                            'price': float(price)
                        }
                    )
                    print("📧 Confirmation email sent")
                except Exception as email_err:
                    logger.warning(f"Could not send confirmation email: {email_err}")

            if ACTIVITY_LOG_AVAILABLE:
                log_activity('create', 'barber_appointment', details={
                    'booking_ref': booking_ref, 'service': service_name
                })

            logger.info(f"User {user.get('username')} booked barber appointment {booking_ref}")

    except Exception as e:
        logger.error(f"Error booking appointment: {e}")
        print(f"❌ Error booking appointment: {e}")

    input("\nPress Enter to continue...")
