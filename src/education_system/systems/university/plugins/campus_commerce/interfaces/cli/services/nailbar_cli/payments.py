"""Appointment checkout and payment history (staff only)."""

import logging
from datetime import date, datetime, timedelta

from education_system.systems.university.infrastructure.database.db import get_connection, transaction

import education_system.systems.university.plugins.campus_commerce.interfaces.cli.services.nailbar_cli as _pkg
from .helpers import (
    format_currency, format_date, generate_receipt_number, is_staff,
    print_subheader,
)

logger = logging.getLogger(__name__)


def complete_appointment():
    """Complete an appointment and process payment (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("COMPLETE APPOINTMENT")

        # Show scheduled/in-progress appointments
        today = date.today()
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT booking_ref, user_name, treatment_names, technician_name,
                       appointment_date, appointment_time, total_price, status
                FROM nailbar_appointments
                WHERE status IN ('scheduled', 'in_progress')
                AND appointment_date <= ?
                ORDER BY appointment_date, appointment_time
                LIMIT 20
            ''', (str(today),))
            appointments = cursor.fetchall()

            if not appointments:
                print("\n❌ No appointments to complete")
                input("\nPress Enter to continue...")
                return

            print("\nAppointments:")
            for ref, customer, treatments, tech, appt_date, appt_time, price, status in appointments:
                print(f"\n{ref} - {status.upper()}")
                print(f"  Customer: {customer}")
                print(f"  Treatments: {treatments}")
                print(f"  Technician: {tech}")
                print(f"  Date/Time: {format_date(appt_date)} at {appt_time}")
                print(f"  Amount: {format_currency(price)}")

        booking_ref = input("\nEnter booking reference (0 to cancel): ").strip()
        if booking_ref == "0":
            return

        # Get appointment details
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT appointment_id, user_name, treatment_names, technician_id,
                       technician_name, total_price, status
                FROM nailbar_appointments
                WHERE booking_ref = ?
            ''', (booking_ref,))
            appt = cursor.fetchone()

            if not appt:
                print("❌ Appointment not found")
                input("\nPress Enter to continue...")
                return

            appt_id, customer, treatments, tech_id, tech_name, total_price, status = appt

            if status == 'completed':
                print("❌ Appointment already completed")
                input("\nPress Enter to continue...")
                return

            if status == 'cancelled':
                print("❌ Cannot complete cancelled appointment")
                input("\nPress Enter to continue...")
                return

        print(f"\n{'━' * 70}")
        print(f"Customer: {customer}")
        print(f"Treatments: {treatments}")
        print(f"Technician: {tech_name}")
        print(f"Service Amount: {format_currency(total_price)}")
        print(f"{'━' * 70}")

        # Add completion notes
        notes = input("\nCompletion notes (optional): ").strip()

        # Payment processing
        print("\n💰 PAYMENT DETAILS")

        # Tip
        tip_str = input("Tip amount (press Enter for 0): ").strip()
        try:
            tip_amount = float(tip_str) if tip_str else 0.0
            if tip_amount < 0:
                tip_amount = 0.0
        except ValueError:
            print("Invalid tip amount, setting to 0")
            tip_amount = 0.0

        final_amount = total_price + tip_amount

        print(f"\nService Amount: {format_currency(total_price)}")
        print(f"Tip: {format_currency(tip_amount)}")
        print(f"Total: {format_currency(final_amount)}")

        # Payment method
        print("\nPayment Methods:")
        print("1. Cash")
        print("2. Card")
        print("3. Student Account")

        method_choice = input("\nSelect payment method: ").strip()
        payment_methods = {
            '1': 'cash',
            '2': 'card',
            '3': 'student_account'
        }
        payment_method = payment_methods.get(method_choice, 'cash')

        # Confirmation
        confirm = input(f"\nProcess payment of {format_currency(final_amount)} via {payment_method}? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Payment cancelled")
            input("\nPress Enter to continue...")
            return

        # Process payment
        receipt_number = generate_receipt_number()

        with transaction() as conn:
            # Update appointment
            conn.execute('''
                UPDATE nailbar_appointments
                SET status = 'completed', completion_notes = ?, updated_at = ?
                WHERE booking_ref = ?
            ''', (notes, datetime.now().isoformat(), booking_ref))

            # Record payment
            conn.execute('''
                INSERT INTO nailbar_payments
                (booking_ref, appointment_id, amount, tip_amount, total_amount,
                 payment_method, payment_date, technician_id, technician_name,
                 receipt_number, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed')
            ''', (
                booking_ref, appt_id, total_price, tip_amount, final_amount,
                payment_method, datetime.now().isoformat(), tech_id, tech_name,
                receipt_number
            ))

        # 8.117.103: mirror into the unified ``payments`` table.
        # nailbar_payments stays canonical for nailbar-specific
        # fields (tip_amount, technician info, receipt_number); the
        # mirror is for cross-domain reports. ``user_id`` on the
        # appointment row is the student_id we tag the unified row
        # with.
        try:
            from education_system.systems.university.domains.finance.domain.core.unified_payments import (
                record_payment,
            )
            with get_connection() as _conn:
                row = _conn.execute(
                    "SELECT user_id FROM nailbar_appointments "
                    "WHERE booking_ref = ?", (booking_ref,)
                ).fetchone()
                user_id = row[0] if row else None
            if user_id:
                record_payment(
                    student_id=user_id,
                    amount=float(final_amount),
                    payment_method=payment_method,
                    source_type='nailbar',
                    source_payment_id=receipt_number,
                    payment_type='service',
                    reference_type='nailbar_booking',
                    reference_id=booking_ref,
                    department='nailbar',
                    description=f"Nail Bar service (technician: {tech_name})",
                    notes=(f"tip £{tip_amount:.2f}; receipt {receipt_number}"
                           if tip_amount else f"receipt {receipt_number}"),
                )
        except Exception as exc:
            logger.warning(f"Unified payment mirror failed (nailbar): {exc}")

        # Record to finance system if available
        if _pkg.FINANCE_AVAILABLE:
            try:
                _pkg.record_payment_to_finance(
                    transaction_type='nail_bar_service',
                    amount=final_amount,
                    description=f"Nail Bar: {treatments}",
                    reference=receipt_number
                )
            except Exception as e:
                logger.error(f"Error recording to finance: {e}")

        # Print receipt
        print("\n" + "=" * 70)
        print("  NAIL BAR RECEIPT")
        print("=" * 70)
        print(f"\nReceipt Number: {receipt_number}")
        print(f"Date: {datetime.now().strftime('%d %B %Y %I:%M %p')}")
        print(f"Booking Reference: {booking_ref}")
        print(f"\nCustomer: {customer}")
        print(f"Technician: {tech_name}")
        print("\nServices:")
        for line in treatments.split(', '):
            print(f"  • {line}")
        print(f"\nService Amount: {format_currency(total_price)}")
        if tip_amount > 0:
            print(f"Tip: {format_currency(tip_amount)}")
        print(f"\nTOTAL PAID: {format_currency(final_amount)}")
        print(f"Payment Method: {payment_method.upper()}")
        print("\n" + "=" * 70)
        print("Thank you for visiting our Nail Bar!")
        print("=" * 70)

        _pkg.log_activity('create', 'nailbar_payment', receipt_number=receipt_number,
                    booking_ref=booking_ref, amount=final_amount)
        logger.info(f"Appointment {booking_ref} completed, payment {receipt_number} processed")

    except Exception as e:
        logger.error(f"Error completing appointment: {e}")
        print(f"❌ Error completing appointment: {e}")

    input("\nPress Enter to continue...")


def view_payment_history():
    """View payment history (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("PAYMENT HISTORY")

        # Date range
        print("\nSelect period:")
        print("1. Today")
        print("2. Last 7 days")
        print("3. Last 30 days")
        print("4. All time")

        choice = input("\nChoice: ").strip()

        today = date.today()
        if choice == "1":
            start_date = today
        elif choice == "2":
            start_date = today - timedelta(days=7)
        elif choice == "3":
            start_date = today - timedelta(days=30)
        else:
            start_date = date(2000, 1, 1)

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT receipt_number, booking_ref, amount, tip_amount, total_amount,
                       payment_method, payment_date, technician_name, status
                FROM nailbar_payments
                WHERE DATE(payment_date) >= ?
                ORDER BY payment_date DESC
                LIMIT 50
            ''', (str(start_date),))
            payments = cursor.fetchall()

            if not payments:
                print("\n❌ No payments found")
            else:
                total_revenue = 0
                total_tips = 0

                print(f"\n{'━' * 70}")
                for payment in payments:
                    try:
                        receipt, booking, amount, tip, total, method, pay_date, tech, status = payment

                        print(f"\nReceipt: {receipt}")
                        print(f"Booking: {booking}")
                        print(f"Technician: {tech}")
                        print(f"Amount: {format_currency(amount)} | Tip: {format_currency(tip)}")
                        print(f"Total: {format_currency(total)} via {method}")
                        print(f"Date: {pay_date}")

                        total_revenue += float(total)
                        total_tips += float(tip)
                    except Exception as e:
                        logger.error(f"Error displaying payment: {e}")
                        continue

                print(f"\n{'━' * 70}")
                print("\nSummary:")
                print(f"Total Payments: {len(payments)}")
                print(f"Total Revenue: {format_currency(total_revenue)}")
                print(f"Total Tips: {format_currency(total_tips)}")

    except Exception as e:
        logger.error(f"Error viewing payment history: {e}")
        print(f"❌ Error viewing payment history: {e}")

    input("\nPress Enter to continue...")


__all__ = ['complete_appointment', 'view_payment_history']
