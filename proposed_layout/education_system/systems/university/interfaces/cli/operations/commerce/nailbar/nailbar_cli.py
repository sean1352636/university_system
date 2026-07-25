"""
Nail Bar CLI Interface

Command-line interface for nail bar/salon operations including
treatments, technicians, appointments, payments, and reports.
"""

import csv
import os
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_db_connection
from education_system.systems.university.infrastructure.email.email_service import send_email
from education_system.systems.university.domain.operations.commerce.nailbar.services.nailbar_core import (
    APPOINTMENT_STATUSES,
    TIME_SLOTS,
    TREATMENT_CATEGORIES,
    AppointmentManager,
    ReportManager,
    TechnicianManager,
    TransactionManager,
    TreatmentManager,
    init_nailbar_db,
)


class NailBarCLI:
    """CLI interface for Nail Bar operations."""

    def __init__(self):
        """Initialize the Nail Bar CLI and ensure DB tables exist."""
        try:
            init_nailbar_db()
        except Exception as e:
            print(f"Warning: Could not initialize nail bar database: {e}")

    def display_menu(self):
        """Display the main nail bar menu and handle user input."""
        while True:
            print("\n" + "=" * 60)
            print(" " * 18 + "NAIL BAR / SALON SYSTEM")
            print("=" * 60)

            print("\n[Treatments]")
            print("  1. View All Treatments")
            print("  2. View Treatments by Category")
            print("  3. Add Treatment")
            print("  4. Update Treatment")

            print("\n[Technicians]")
            print("  5. View All Technicians")
            print("  6. Add Technician")
            print("  7. Check Technician Availability")

            print("\n[Appointments]")
            print("  8. Create Appointment")
            print("  9. View Appointment by ID")
            print(" 10. Look Up Appointment by Reference")
            print(" 11. View Today's Appointments")
            print(" 12. View Appointments by Date")
            print(" 13. View Customer Appointments")
            print(" 14. Update Appointment Status")
            print(" 15. Cancel Appointment")
            print(" 16. Reschedule Appointment")

            print("\n[Payments]")
            print(" 17. Process Payment")
            print(" 18. View Daily Revenue")
            print(" 19. Issue Refund")

            print("\n[Reports]")
            print(" 20. Sales Report")
            print(" 21. Admin Report")
            print(" 22. Email Admin Report")
            print(" 23. Export Transactions to CSV")

            print("\n  0. Back to Main Menu")
            print("=" * 60)

            choice = input("\nEnter your choice: ").strip()

            try:
                if choice == "0":
                    break
                elif choice == "1":
                    self._view_all_treatments()
                elif choice == "2":
                    self._view_treatments_by_category()
                elif choice == "3":
                    self._add_treatment()
                elif choice == "4":
                    self._update_treatment()
                elif choice == "5":
                    self._view_all_technicians()
                elif choice == "6":
                    self._add_technician()
                elif choice == "7":
                    self._check_technician_availability()
                elif choice == "8":
                    self._create_appointment()
                elif choice == "9":
                    self._view_appointment()
                elif choice == "10":
                    self._lookup_appointment_by_reference()
                elif choice == "11":
                    self._view_todays_appointments()
                elif choice == "12":
                    self._view_appointments_by_date()
                elif choice == "13":
                    self._view_customer_appointments()
                elif choice == "14":
                    self._update_appointment_status()
                elif choice == "15":
                    self._cancel_appointment()
                elif choice == "16":
                    self._reschedule_appointment()
                elif choice == "17":
                    self._process_payment()
                elif choice == "18":
                    self._view_daily_revenue()
                elif choice == "19":
                    self._issue_refund()
                elif choice == "20":
                    self._sales_report()
                elif choice == "21":
                    self._admin_report()
                elif choice == "22":
                    self._email_admin_report()
                elif choice == "23":
                    self._export_transactions_csv()
                else:
                    print("Invalid choice. Please try again.")
            except Exception as e:
                print(f"\nError: {e}")

    # ── Treatments ──────────────────────────────────────────

    def _view_all_treatments(self):
        """View all available treatments."""
        treatments = TreatmentManager.get_all_treatments()
        if not treatments:
            print("\nNo treatments found.")
            return
        print(f"\n{'ID':<5} {'Name':<25} {'Category':<15} {'Duration':<10} {'Price':<8}")
        print("-" * 63)
        for t in treatments:
            print(
                f"{t['treatment_id']:<5} {t['name']:<25} {t['category']:<15} "
                f"{t['duration_minutes']:<10} £{t['price']:.2f}"
            )

    def _view_treatments_by_category(self):
        """View treatments filtered by category."""
        print("\nAvailable categories:")
        for key, label in TREATMENT_CATEGORIES.items():
            print(f"  {key} - {label}")
        category = input("Enter category key: ").strip()
        if category not in TREATMENT_CATEGORIES:
            print("Invalid category.")
            return
        treatments = TreatmentManager.get_all_treatments(category=category)
        if not treatments:
            print(f"\nNo treatments found for category '{category}'.")
            return
        print(f"\n{'ID':<5} {'Name':<25} {'Duration':<10} {'Price':<8}")
        print("-" * 48)
        for t in treatments:
            print(
                f"{t['treatment_id']:<5} {t['name']:<25} "
                f"{t['duration_minutes']:<10} £{t['price']:.2f}"
            )

    def _add_treatment(self):
        """Add a new treatment."""
        name = input("Treatment name: ").strip()
        if not name:
            print("Name is required.")
            return
        print("Categories:", ", ".join(TREATMENT_CATEGORIES.keys()))
        category = input("Category: ").strip()
        if category not in TREATMENT_CATEGORIES:
            print("Invalid category.")
            return
        price = float(input("Price (£): ").strip())
        duration = input("Duration in minutes (default 45): ").strip()
        duration = int(duration) if duration else 45
        description = input("Description (optional): ").strip() or None

        treatment_id = TreatmentManager.add_treatment(
            name=name, category=category, price=price,
            duration_minutes=duration, description=description,
        )
        print(f"\nTreatment added successfully (ID: {treatment_id}).")

    def _update_treatment(self):
        """Update an existing treatment."""
        treatment_id = int(input("Treatment ID to update: ").strip())
        treatment = TreatmentManager.get_treatment(treatment_id)
        if not treatment:
            print("Treatment not found.")
            return
        print(f"Current: {treatment['name']} | {treatment['category']} | "
              f"£{treatment['price']:.2f} | {treatment['duration_minutes']} min")

        updates = {}
        name = input(f"New name (Enter to keep '{treatment['name']}'): ").strip()
        if name:
            updates["name"] = name
        price = input(f"New price (Enter to keep £{treatment['price']:.2f}): ").strip()
        if price:
            updates["price"] = float(price)
        duration = input(f"New duration (Enter to keep {treatment['duration_minutes']}): ").strip()
        if duration:
            updates["duration_minutes"] = int(duration)

        if not updates:
            print("No changes made.")
            return
        TreatmentManager.update_treatment(treatment_id, **updates)
        print("Treatment updated successfully.")

    # ── Technicians ─────────────────────────────────────────

    def _view_all_technicians(self):
        """View all active technicians."""
        technicians = TechnicianManager.get_all_technicians()
        if not technicians:
            print("\nNo technicians found.")
            return
        print(f"\n{'ID':<5} {'Name':<20} {'Specialties':<25} {'Phone':<15}")
        print("-" * 65)
        for t in technicians:
            print(
                f"{t['technician_id']:<5} {t['name']:<20} "
                f"{(t.get('specialties') or '-'):<25} {(t.get('phone') or '-'):<15}"
            )

    def _add_technician(self):
        """Add a new technician."""
        name = input("Technician name: ").strip()
        if not name:
            print("Name is required.")
            return
        employee_id = input("Employee ID (optional): ").strip() or None
        specialties = input("Specialties (optional): ").strip() or None
        phone = input("Phone (optional): ").strip() or None
        email = input("Email (optional): ").strip() or None
        certification = input("Certification (optional): ").strip() or None

        tech_id = TechnicianManager.add_technician(
            name=name, employee_id=employee_id, specialties=specialties,
            phone=phone, email=email, certification=certification,
        )
        print(f"\nTechnician added successfully (ID: {tech_id}).")

    def _check_technician_availability(self):
        """Check a technician's available time slots for a date."""
        tech_id = int(input("Technician ID: ").strip())
        date = input("Date (YYYY-MM-DD): ").strip()
        available = TechnicianManager.get_technician_availability(tech_id, date)
        if not available:
            print(f"\nNo available slots for technician {tech_id} on {date}.")
            return
        print(f"\nAvailable slots on {date}: {', '.join(available)}")

    # ── Appointments ────────────────────────────────────────

    def _create_appointment(self):
        """Create a new appointment."""
        customer_id = input("Customer ID: ").strip()
        customer_name = input("Customer name: ").strip()
        if not customer_id or not customer_name:
            print("Customer ID and name are required.")
            return
        date = input("Appointment date (YYYY-MM-DD): ").strip()
        print("Available time slots:", ", ".join(TIME_SLOTS))
        time = input("Appointment time (HH:MM): ").strip()

        # Select treatments
        self._view_all_treatments()
        treatment_input = input("Enter treatment IDs (comma-separated): ").strip()
        treatment_ids = [int(x.strip()) for x in treatment_input.split(",") if x.strip()]
        if not treatment_ids:
            print("At least one treatment is required.")
            return

        tech_id_input = input("Technician ID (optional, Enter to skip): ").strip()
        technician_id = int(tech_id_input) if tech_id_input else None
        customer_email = input("Customer email (optional): ").strip() or None
        customer_phone = input("Customer phone (optional): ").strip() or None
        special_requests = input("Special requests (optional): ").strip() or None

        appt_id, booking_ref = AppointmentManager.create_appointment(
            customer_id=customer_id, customer_name=customer_name,
            appointment_date=date, appointment_time=time,
            treatment_ids=treatment_ids, technician_id=technician_id,
            customer_email=customer_email, customer_phone=customer_phone,
            special_requests=special_requests,
        )
        print("\nAppointment created successfully!")
        print(f"  Appointment ID: {appt_id}")
        print(f"  Booking Reference: {booking_ref}")

    def _view_appointment(self):
        """View appointment details by ID."""
        appt_id = int(input("Appointment ID: ").strip())
        appt = AppointmentManager.get_appointment(appt_id)
        if not appt:
            print("Appointment not found.")
            return
        self._print_appointment(appt)

    def _lookup_appointment_by_reference(self):
        """Look up an appointment by booking reference."""
        ref = input("Booking reference: ").strip()
        appt = AppointmentManager.get_appointment_by_reference(ref)
        if not appt:
            print("Appointment not found.")
            return
        self._print_appointment(appt)

    def _print_appointment(self, appt):
        """Print appointment details."""
        print(f"\n--- Appointment #{appt['appointment_id']} ---")
        print(f"  Booking Ref:  {appt['booking_reference']}")
        print(f"  Customer:     {appt['customer_name']} ({appt['customer_id']})")
        print(f"  Date/Time:    {appt['appointment_date']} at {appt['appointment_time']}")
        print(f"  Technician:   {appt.get('technician_name') or 'Not assigned'}")
        print(f"  Status:       {appt['status']}")
        print(f"  Total:        £{appt['total_amount']:.2f}")
        print(f"  Payment:      {appt['payment_status']}")
        if appt.get("treatments"):
            print("  Treatments:")
            for t in appt["treatments"]:
                print(f"    - {t['treatment_name']} (£{t['price']:.2f}, {t['duration_minutes']} min)")
        if appt.get("special_requests"):
            print(f"  Requests:     {appt['special_requests']}")

    def _view_todays_appointments(self):
        """View all appointments for today."""
        appointments = AppointmentManager.get_todays_appointments()
        if not appointments:
            print("\nNo appointments for today.")
            return
        print(f"\nToday's Appointments ({datetime.now().strftime('%Y-%m-%d')}):")
        self._print_appointment_list(appointments)

    def _view_appointments_by_date(self):
        """View all appointments for a given date."""
        date = input("Date (YYYY-MM-DD): ").strip()
        appointments = AppointmentManager.get_appointments_by_date(date)
        if not appointments:
            print(f"\nNo appointments for {date}.")
            return
        print(f"\nAppointments for {date}:")
        self._print_appointment_list(appointments)

    def _view_customer_appointments(self):
        """View all appointments for a customer."""
        customer_id = input("Customer ID: ").strip()
        appointments = AppointmentManager.get_customer_appointments(customer_id)
        if not appointments:
            print(f"\nNo appointments found for customer '{customer_id}'.")
            return
        print(f"\nAppointments for customer '{customer_id}':")
        self._print_appointment_list(appointments)

    def _print_appointment_list(self, appointments):
        """Print a list of appointments in tabular format."""
        print(f"  {'ID':<5} {'Reference':<22} {'Customer':<18} {'Date':<12} {'Time':<6} {'Status':<12} {'Total':<8}")
        print("  " + "-" * 83)
        for a in appointments:
            print(
                f"  {a['appointment_id']:<5} {a['booking_reference']:<22} "
                f"{a['customer_name']:<18} {a['appointment_date']:<12} "
                f"{a['appointment_time']:<6} {a['status']:<12} £{a['total_amount']:.2f}"
            )

    def _update_appointment_status(self):
        """Update the status of an appointment."""
        appt_id = int(input("Appointment ID: ").strip())
        print("Valid statuses:", ", ".join(APPOINTMENT_STATUSES))
        status = input("New status: ").strip()
        if AppointmentManager.update_status(appt_id, status):
            print("Appointment status updated successfully.")
        else:
            print("Failed to update status. Check the appointment ID and status value.")

    def _cancel_appointment(self):
        """Cancel an appointment."""
        appt_id = int(input("Appointment ID to cancel: ").strip())
        reason = input("Cancellation reason (optional): ").strip() or None
        if AppointmentManager.cancel_appointment(appt_id, reason):
            print("Appointment cancelled successfully.")
        else:
            print("Failed to cancel appointment.")

    def _reschedule_appointment(self):
        """Reschedule an appointment to a new date/time."""
        appt_id = int(input("Appointment ID to reschedule: ").strip())
        new_date = input("New date (YYYY-MM-DD): ").strip()
        print("Available time slots:", ", ".join(TIME_SLOTS))
        new_time = input("New time (HH:MM): ").strip()
        tech_input = input("New technician ID (Enter to keep current): ").strip()
        new_tech_id = int(tech_input) if tech_input else None

        if AppointmentManager.reschedule_appointment(appt_id, new_date, new_time, new_tech_id):
            print("Appointment rescheduled successfully.")
        else:
            print("Failed to reschedule appointment.")

    # ── Payments ────────────────────────────────────────────

    def _process_payment(self):
        """Process payment for an appointment."""
        appt_id = int(input("Appointment ID: ").strip())
        appt = AppointmentManager.get_appointment(appt_id)
        if not appt:
            print("Appointment not found.")
            return
        print(f"Total amount due: £{appt['total_amount']:.2f}")
        amount = float(input("Payment amount (£): ").strip())
        payment_method = input("Payment method (card/cash/contactless): ").strip()
        tip_input = input("Tip amount (default 0): ").strip()
        tip = float(tip_input) if tip_input else 0
        processed_by = input("Processed by (staff ID, optional): ").strip() or None

        txn_id = TransactionManager.process_payment(
            appointment_id=appt_id, amount=amount,
            payment_method=payment_method, customer_id=appt["customer_id"],
            tip_amount=tip, processed_by=processed_by,
        )
        print(f"\nPayment processed successfully (Transaction ID: {txn_id}).")

    def _view_daily_revenue(self):
        """View revenue summary for a given day."""
        date = input("Date (YYYY-MM-DD, Enter for today): ").strip() or None
        revenue = TransactionManager.get_daily_revenue(date)
        print(f"\n--- Revenue for {revenue['date']} ---")
        print(f"  Transactions:   {revenue['transaction_count']}")
        print(f"  Service Revenue: £{revenue['service_revenue']:.2f}")
        print(f"  Tips:            £{revenue['tips']:.2f}")
        print(f"  Total Revenue:   £{revenue['total_revenue']:.2f}")

    def _issue_refund(self):
        """Issue a refund for a nail bar transaction (mirrors the GUI refund flow)."""
        txn_id = int(input("Transaction ID to refund: ").strip())
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT transaction_id, reference_id, customer_id, amount, payment_method, status "
                "FROM transactions WHERE transaction_id = ? AND source_type = 'nail_bar'",
                (txn_id,),
            ).fetchone()
        if not row:
            print("Transaction not found.")
            return
        txn = dict(row)
        if (txn.get("status") or "").lower() == "refunded":
            print("This transaction has already been refunded.")
            return

        default_amount = float(txn["amount"])
        amount_input = input(f"Refund amount (£, Enter for £{default_amount:.2f}): ").strip()
        amount = float(amount_input) if amount_input else default_amount

        default_method = (txn.get("payment_method") or "Cash").replace("_", " ").title()
        refund_method = input(f"Refund method (Enter for '{default_method}'): ").strip() or default_method
        reason = input("Refund reason (optional): ").strip() or None
        processed_by = input("Processed by (Enter for 'System'): ").strip() or "System"

        appointment_id = txn.get("reference_id")
        refund_ref = f"NAILBAR-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        refund_notes = reason or f"Nail Bar/Salon service refund (transaction_id={txn_id})"

        with get_db_connection() as conn:
            conn.execute(
                "UPDATE transactions SET status = 'refunded' "
                "WHERE transaction_id = ? AND source_type = 'nail_bar'",
                (txn_id,),
            )
            cur = conn.execute(
                """
                INSERT INTO unified_refunds
                (source_type, reference_id, reference_type, refund_date, amount,
                 refund_method, refund_reference, student_id, processed_by, notes, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'processed')
                """,
                ('nail_bar',
                 str(appointment_id) if appointment_id is not None else None,
                 'appointment',
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S'), amount, refund_method,
                 refund_ref, txn["customer_id"], processed_by, refund_notes),
            )
            refund_row_id = cur.lastrowid
            conn.commit()

        # Auto-post to the general ledger (cash has moved). Never fatal.
        try:
            from education_system.systems.university.domain.finance.ledger import notify_ledger
            notify_ledger('refund', refund_row_id, posted_by=processed_by)
        except Exception as e:
            print(f"Note: ledger posting skipped ({e}).")

        print(f"\nRefund of £{amount:.2f} processed successfully.")
        print(f"  Refund Reference: {refund_ref}")

    # ── Reports ─────────────────────────────────────────────

    def _sales_report(self):
        """Generate a sales report for a date range."""
        start_date = input("Start date (YYYY-MM-DD): ").strip()
        end_date = input("End date (YYYY-MM-DD): ").strip()
        report = ReportManager.generate_sales_report(start_date, end_date)
        summary = report.get("summary", {})
        print(f"\n--- Sales Report: {start_date} to {end_date} ---")
        print(f"  Total Appointments: {summary.get('total_appointments') or 0}")
        print(f"  Service Revenue:    £{(summary.get('service_revenue') or 0):.2f}")
        print(f"  Total Tips:         £{(summary.get('total_tips') or 0):.2f}")
        print(f"  Avg Service Value:  £{(summary.get('avg_service_value') or 0):.2f}")
        if report.get("by_treatment"):
            print("\n  Top Treatments:")
            for i, t in enumerate(report["by_treatment"][:10], 1):
                print(f"    {i}. {t['treatment_name']} - {t['count']} bookings (£{t['revenue']:.2f})")
        if report.get("by_technician"):
            print("\n  Technician Performance:")
            for t in report["by_technician"]:
                name = t.get("technician_name") or "Unknown"
                print(f"    {name}: {t['appointments']} clients, £{t['revenue']:.2f} revenue")

    def _admin_report(self):
        """Generate and display the full admin report."""
        report = ReportManager.generate_admin_report()
        print(report)

    def _email_admin_report(self):
        """Generate the admin report and email it to an administrator."""
        report = ReportManager.generate_admin_report()
        with get_db_connection() as conn:
            admin = conn.execute(
                "SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL LIMIT 1"
            ).fetchone()
        if not admin or not admin["email"]:
            print("No administrator email address is configured. Report not sent.")
            return
        date = datetime.now().strftime("%Y-%m-%d")
        send_email(
            recipient_email=admin["email"],
            subject=f"Nail Bar/Salon Admin Report - {date}",
            body=report,
        )
        print(f"\nAdmin report emailed to {admin['email']}.")

    def _export_transactions_csv(self):
        """Export nail bar transactions to CSV (same data/headers as the GUI export)."""
        default_name = f"nailbar_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = input(f"Output file path (Enter for '{default_name}'): ").strip() or default_name

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT transaction_id, reference_id AS appointment_id, created_at, customer_id,
                       amount, payment_method, status
                FROM transactions
                WHERE source_type = 'nail_bar'
                ORDER BY created_at DESC
                LIMIT 500
                """
            ).fetchall()

        with open(path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Transaction ID', 'Appointment ID', 'Date', 'Customer',
                             'Amount', 'Payment Method', 'Status'])
            for r in rows:
                payment_display = (r["payment_method"].replace("_", " ").title()
                                   if r["payment_method"] else "N/A")
                status_display = (r["status"] or "COMPLETED").upper()
                writer.writerow([
                    r["transaction_id"],
                    r["appointment_id"] or "N/A",
                    r["created_at"],
                    r["customer_id"] or "N/A",
                    f"£{r['amount']:.2f}",
                    payment_display,
                    status_display,
                ])

        print(f"\nExported {len(rows)} transaction(s) to {os.path.abspath(path)}.")


def main():
    """Entry point for the Nail Bar CLI."""
    cli = NailBarCLI()
    cli.display_menu()


if __name__ == "__main__":
    main()
