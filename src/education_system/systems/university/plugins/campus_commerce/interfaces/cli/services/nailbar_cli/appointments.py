"""Customer-facing appointment booking and management."""

import logging
from datetime import date, datetime

from education_system.systems.university.infrastructure.database.db import get_connection, transaction

import education_system.systems.university.plugins.campus_commerce.interfaces.cli.services.nailbar_cli as _pkg
from .helpers import (
    format_currency, format_date, generate_booking_ref, get_current_user,
    print_subheader,
)

logger = logging.getLogger(__name__)


def book_appointment():
    """Book a nail bar appointment with multi-treatment selection"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to book appointments")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("BOOK NAIL BAR APPOINTMENT")

        # Step 1: Multi-treatment selection
        print("\n📋 STEP 1: SELECT TREATMENTS")
        print("(You can select multiple treatments for one appointment)\n")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT treatment_id, treatment_name, category, price, duration_minutes
                FROM nailbar_treatments
                WHERE status = 'active'
                ORDER BY category, treatment_name
            ''')
            treatments = cursor.fetchall()

            if not treatments:
                print("❌ No treatments available")
                input("\nPress Enter to continue...")
                return

            # Display treatments by category
            current_category = None
            for treat_id, name, category, price, duration in treatments:
                if category != current_category:
                    current_category = category
                    print(f"\n{category.upper()}:")
                print(f"  {treat_id}. {name} - {format_currency(price)} ({duration} min)")

        # Allow multiple treatment selection
        selected_treatments = []
        total_price = 0.0
        total_duration = 0

        while True:
            treatment_id = input("\nEnter treatment ID to add (0 to finish, -1 to cancel): ").strip()

            if treatment_id == "0":
                if not selected_treatments:
                    print("❌ Please select at least one treatment")
                    continue
                break
            elif treatment_id == "-1":
                print("❌ Booking cancelled")
                input("\nPress Enter to continue...")
                return

            if not treatment_id.isdigit():
                print("❌ Invalid treatment ID")
                continue

            # Get treatment details
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT treatment_name, price, duration_minutes
                    FROM nailbar_treatments
                    WHERE treatment_id = ? AND status = 'active'
                ''', (treatment_id,))
                treatment = cursor.fetchone()

                if not treatment:
                    print("❌ Treatment not found")
                    continue

                name, price, duration = treatment

                # Check if already selected
                if any(t['id'] == treatment_id for t in selected_treatments):
                    print("⚠️  Treatment already selected")
                    continue

                selected_treatments.append({
                    'id': treatment_id,
                    'name': name,
                    'price': float(price),
                    'duration': duration
                })
                total_price += float(price)
                total_duration += duration

                print(f"✅ Added: {name} ({format_currency(price)}, {duration} min)")
                print("\n📊 Current Selection:")
                for idx, t in enumerate(selected_treatments, 1):
                    print(f"  {idx}. {t['name']} - {format_currency(t['price'])}")
                print(f"\n  Total: {format_currency(total_price)} | {total_duration} minutes")

        # Step 2: Choose technician
        print("\n👩‍💼 STEP 2: CHOOSE TECHNICIAN")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT technician_id, technician_name, specialization
                FROM nailbar_technicians
                WHERE status = 'active'
                ORDER BY technician_name
            ''')
            technicians = cursor.fetchall()

            if not technicians:
                print("\n⚠️  No technicians available, will assign automatically")
                technician_id = None
                technician_name = "Any Available"
            else:
                print("\nAvailable Technicians:")
                print("0. Any Available")
                for tech_id, name, spec in technicians:
                    print(f"{tech_id}. {name}")
                    if spec:
                        print(f"   Specialization: {spec}")

                tech_choice = input("\nEnter technician ID: ").strip()

                if tech_choice == "0" or not tech_choice:
                    technician_id = None
                    technician_name = "Any Available"
                elif tech_choice.isdigit():
                    cursor = conn.execute('''
                        SELECT technician_name FROM nailbar_technicians
                        WHERE technician_id = ? AND status = 'active'
                    ''', (tech_choice,))
                    tech_row = cursor.fetchone()
                    if tech_row:
                        technician_id = tech_choice
                        technician_name = tech_row[0]
                    else:
                        print("❌ Technician not found, using any available")
                        technician_id = None
                        technician_name = "Any Available"
                else:
                    print("❌ Invalid input, using any available")
                    technician_id = None
                    technician_name = "Any Available"

        # Step 3: Date and time
        print("\n📅 STEP 3: SELECT DATE AND TIME")

        date_str = input("\nEnter appointment date (YYYY-MM-DD): ").strip()
        try:
            appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            if appointment_date < date.today():
                print("❌ Cannot book appointments in the past")
                input("\nPress Enter to continue...")
                return
        except ValueError:
            print("❌ Invalid date format")
            input("\nPress Enter to continue...")
            return

        time_str = input("Enter appointment time (HH:MM): ").strip()
        try:
            appointment_time = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            print("❌ Invalid time format")
            input("\nPress Enter to continue...")
            return

        # Step 4: Confirmation
        print("\n" + "=" * 70)
        print("  APPOINTMENT SUMMARY")
        print("=" * 70)

        print("\n📋 Treatments:")
        for idx, t in enumerate(selected_treatments, 1):
            print(f"  {idx}. {t['name']} - {format_currency(t['price'])} ({t['duration']} min)")

        print(f"\n👩‍💼 Technician: {technician_name}")
        print(f"📅 Date: {format_date(str(appointment_date))}")
        print(f"🕐 Time: {appointment_time.strftime('%I:%M %p')}")
        print(f"⏱️  Total Duration: {total_duration} minutes")
        print(f"💰 Total Price: {format_currency(total_price)}")
        print("=" * 70)

        confirm = input("\nConfirm booking? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Booking cancelled")
            input("\nPress Enter to continue...")
            return

        # Create booking
        booking_ref = generate_booking_ref()
        treatment_ids_str = ','.join([t['id'] for t in selected_treatments])
        treatment_names_str = ', '.join([t['name'] for t in selected_treatments])

        with transaction() as conn:
            conn.execute('''
                INSERT INTO nailbar_appointments
                (booking_ref, user_id, user_name, user_email, treatment_ids, treatment_names,
                 technician_id, technician_name, appointment_date, appointment_time,
                 total_duration, total_price, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?)
            ''', (
                booking_ref,
                user.get('username'),
                user.get('full_name', user.get('username')),
                user.get('email', ''),
                treatment_ids_str,
                treatment_names_str,
                technician_id,
                technician_name,
                str(appointment_date),
                str(appointment_time),
                total_duration,
                total_price,
                datetime.now().isoformat()
            ))

        print("\n✅ Appointment booked successfully!")
        print(f"📄 Booking Reference: {booking_ref}")
        print("\nPlease save this reference for your records.")

        _pkg.log_activity('create', 'nailbar_appointment', booking_ref=booking_ref,
                    user_id=user.get('username'), total_price=total_price)
        logger.info(f"User {user.get('username')} booked nail bar appointment {booking_ref}")

        # Send confirmation email if available
        if _pkg.EMAIL_AVAILABLE and user.get('email'):
            try:
                _pkg.send_email(
                    to_email=user.get('email'),
                    subject=f"Nail Bar Appointment Confirmation - {booking_ref}",
                    body=f"Your nail bar appointment has been confirmed.\n\n"
                         f"Booking Reference: {booking_ref}\n"
                         f"Date: {format_date(str(appointment_date))}\n"
                         f"Time: {appointment_time.strftime('%I:%M %p')}\n"
                         f"Treatments: {treatment_names_str}\n"
                         f"Total Price: {format_currency(total_price)}\n\n"
                         f"Thank you for choosing our nail bar!"
                )
            except Exception as e:
                logger.error(f"Error sending confirmation email: {e}")

    except Exception as e:
        logger.error(f"Error booking appointment: {e}")
        print(f"❌ Error booking appointment: {e}")

    input("\nPress Enter to continue...")


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
            cursor = conn.execute('''
                SELECT booking_ref, treatment_names, technician_name, appointment_date,
                       appointment_time, total_price, total_duration, status, created_at
                FROM nailbar_appointments
                WHERE user_id = ?
                ORDER BY appointment_date DESC, appointment_time DESC
                LIMIT 20
            ''', (user.get('username'),))
            appointments = cursor.fetchall()

            if not appointments:
                print("\n❌ No appointments found")
            else:
                for appt in appointments:
                    try:
                        ref, treatments, tech, appt_date, appt_time, price, duration, status, created = appt

                        # Status emoji
                        status_emoji = {
                            'scheduled': '📅',
                            'confirmed': '✅',
                            'in_progress': '⏳',
                            'completed': '✔️',
                            'cancelled': '❌'
                        }.get(status.lower(), '📋')

                        print(f"\n{'━' * 70}")
                        print(f"{status_emoji} Booking: {ref}")
                        print(f"Treatments: {treatments}")
                        print(f"Technician: {tech}")
                        print(f"Date: {format_date(appt_date)} at {appt_time}")
                        print(f"Duration: {duration} minutes")
                        print(f"Price: {format_currency(price)}")
                        print(f"Status: {status.upper()}")
                        print(f"Booked: {created}")
                    except Exception as e:
                        logger.error(f"Error displaying appointment: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing appointments: {e}")
        print(f"❌ Error viewing appointments: {e}")

    input("\nPress Enter to continue...")


def cancel_appointment():
    """Cancel an appointment"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to cancel appointments")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("CANCEL APPOINTMENT")

        # Show user's upcoming appointments
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT booking_ref, treatment_names, appointment_date, appointment_time, status
                FROM nailbar_appointments
                WHERE user_id = ? AND status NOT IN ('cancelled', 'completed')
                ORDER BY appointment_date, appointment_time
            ''', (user.get('username'),))
            appointments = cursor.fetchall()

            if not appointments:
                print("\n❌ No cancellable appointments found")
                input("\nPress Enter to continue...")
                return

            print("\nYour Upcoming Appointments:")
            for ref, treatments, appt_date, appt_time, status in appointments:
                print(f"\n{ref}")
                print(f"  {treatments}")
                print(f"  {format_date(appt_date)} at {appt_time}")
                print(f"  Status: {status}")

        booking_ref = input("\nEnter booking reference to cancel (0 to go back): ").strip()
        if booking_ref == "0":
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT appointment_date, appointment_time, status, treatment_names
                FROM nailbar_appointments
                WHERE booking_ref = ? AND user_id = ?
            ''', (booking_ref, user.get('username')))
            appt = cursor.fetchone()

            if not appt:
                print("❌ Appointment not found")
                input("\nPress Enter to continue...")
                return

            appt_date, appt_time, status, treatments = appt

            if status == 'cancelled':
                print("❌ Appointment is already cancelled")
                input("\nPress Enter to continue...")
                return

            if status == 'completed':
                print("❌ Cannot cancel completed appointment")
                input("\nPress Enter to continue...")
                return

            print("\nAppointment Details:")
            print(f"Treatments: {treatments}")
            print(f"Date: {format_date(appt_date)} at {appt_time}")

            confirm = input("\nConfirm cancellation? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Cancellation aborted")
                input("\nPress Enter to continue...")
                return

            with transaction() as conn_tx:
                conn_tx.execute('''
                    UPDATE nailbar_appointments
                    SET status = 'cancelled', updated_at = ?
                    WHERE booking_ref = ?
                ''', (datetime.now().isoformat(), booking_ref))

            print("\n✅ Appointment cancelled successfully")
            _pkg.log_activity('update', 'nailbar_appointment', booking_ref=booking_ref,
                        action='cancelled')
            logger.info(f"User {user.get('username')} cancelled appointment {booking_ref}")

    except Exception as e:
        logger.error(f"Error cancelling appointment: {e}")
        print(f"❌ Error cancelling appointment: {e}")

    input("\nPress Enter to continue...")


__all__ = ['book_appointment', 'view_my_appointments', 'cancel_appointment']
