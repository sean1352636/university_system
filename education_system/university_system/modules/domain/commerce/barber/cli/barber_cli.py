"""
Barber Shop CLI Interface

Provides command-line interface for barber shop management including:
- Service management (add, list, update)
- Staff management (add, list, availability)
- Appointment booking and scheduling
- Payment processing
- Waitlist management
- Reports and analytics
"""

from datetime import datetime

from education_system.university_system.modules.domain.commerce.barber.services.barber_core import (
    ServiceManager,
    StaffManager,
    AppointmentManager,
    TransactionManager,
    ReportManager,
    WaitlistManager,
    BlockedSlotManager,
    init_barber_db,
    SERVICE_TYPES,
    APPOINTMENT_STATUSES,
    TIME_SLOTS,
)


class BarberCLI:
    """Command-line interface for the Barber Shop."""

    def __init__(self):
        """Initialize the Barber CLI and database."""
        init_barber_db()

    def run(self):
        """Run the barber CLI main loop."""
        while True:
            self._display_main_menu()
            choice = input("\nSelect an option: ").strip()

            if choice == '0':
                print("\nReturning to main menu...")
                break
            elif choice == '1':
                self._services_menu()
            elif choice == '2':
                self._staff_menu()
            elif choice == '3':
                self._appointments_menu()
            elif choice == '4':
                self._payments_menu()
            elif choice == '5':
                self._waitlist_menu()
            elif choice == '6':
                self._reports_menu()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

    # ========== Main Menu ==========

    def _display_main_menu(self):
        """Display the main menu."""
        print("\n" + "=" * 70)
        print("  BARBER SHOP MANAGEMENT SYSTEM".center(70))
        print("=" * 70)
        print("\n  1. Services")
        print("  2. Staff")
        print("  3. Appointments")
        print("  4. Payments")
        print("  5. Waitlist")
        print("  6. Reports")
        print("  0. Back to Main Menu")

    # ========== Services ==========

    def _services_menu(self):
        """Services sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  SERVICE MANAGEMENT")
            print("-" * 50)
            print("  1. Add Service")
            print("  2. List Services")
            print("  3. View Service Details")
            print("  4. Update Service")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._add_service()
                elif choice == '2':
                    self._list_services()
                elif choice == '3':
                    self._view_service()
                elif choice == '4':
                    self._update_service()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _add_service(self):
        """Add a new service."""
        print("\n--- Add New Service ---")
        print("Service types:", ", ".join(SERVICE_TYPES.keys()))
        name = input("Service name: ").strip()
        service_type = input("Service type: ").strip()
        price = float(input("Price: ").strip())
        dur = input("Duration (minutes) [30]: ").strip()
        duration = int(dur) if dur else 30
        description = input("Description (optional): ").strip() or None

        service_id = ServiceManager.add_service(
            name=name, service_type=service_type, price=price,
            duration_minutes=duration, description=description,
        )
        print(f"\nService added (ID: {service_id})")

    def _list_services(self):
        """List all services."""
        show_all = input("Include unavailable services? (y/n) [n]: ").strip().lower() == 'y'
        services = ServiceManager.get_all_services(available_only=not show_all)
        if not services:
            print("\nNo services found.")
            return
        print(f"\n{'ID':<6}{'Name':<25}{'Type':<15}{'Duration':<10}{'Price':<10}{'Available'}")
        print("-" * 75)
        for s in services:
            print(f"{s['service_id']:<6}{s['name']:<25}{s['service_type']:<15}"
                  f"{s['duration_minutes']:<10}{s['price']:<10.2f}{'Yes' if s['is_available'] else 'No'}")

    def _view_service(self):
        """View service details."""
        service_id = int(input("Service ID: ").strip())
        service = ServiceManager.get_service(service_id)
        if not service:
            print("Service not found.")
            return
        print(f"\nID: {service['service_id']}")
        print(f"Name: {service['name']}")
        print(f"Type: {service['service_type']}")
        print(f"Description: {service.get('description', 'N/A')}")
        print(f"Duration: {service['duration_minutes']} minutes")
        print(f"Price: {service['price']:.2f}")
        print(f"Available: {'Yes' if service['is_available'] else 'No'}")

    def _update_service(self):
        """Update a service."""
        service_id = int(input("Service ID: ").strip())
        print("Leave blank to keep current value:")
        name = input("Name: ").strip() or None
        price_input = input("Price: ").strip()
        price = float(price_input) if price_input else None
        dur = input("Duration (minutes): ").strip()
        duration = int(dur) if dur else None
        avail = input("Available (1/0): ").strip()
        is_available = int(avail) if avail else None

        kwargs = {}
        if name:
            kwargs['name'] = name
        if price is not None:
            kwargs['price'] = price
        if duration is not None:
            kwargs['duration_minutes'] = duration
        if is_available is not None:
            kwargs['is_available'] = is_available

        updated = ServiceManager.update_service(service_id, **kwargs)
        print("Service updated." if updated else "No changes made.")

    # ========== Staff ==========

    def _staff_menu(self):
        """Staff sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  STAFF MANAGEMENT")
            print("-" * 50)
            print("  1. Add Staff Member")
            print("  2. List Staff")
            print("  3. View Staff Details")
            print("  4. Check Staff Availability")
            print("  5. Block Time Slot")
            print("  6. View Blocked Slots")
            print("  7. Unblock Slot")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._add_staff()
                elif choice == '2':
                    self._list_staff()
                elif choice == '3':
                    self._view_staff()
                elif choice == '4':
                    self._staff_availability()
                elif choice == '5':
                    self._block_slot()
                elif choice == '6':
                    self._view_blocked()
                elif choice == '7':
                    self._unblock_slot()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _add_staff(self):
        """Add a staff member."""
        print("\n--- Add Staff Member ---")
        name = input("Name: ").strip()
        employee_id = input("Employee ID (optional): ").strip() or None
        specialties = input("Specialties (optional): ").strip() or None
        phone = input("Phone (optional): ").strip() or None
        email = input("Email (optional): ").strip() or None

        staff_id = StaffManager.add_staff(
            name=name, employee_id=employee_id, specialties=specialties,
            phone=phone, email=email,
        )
        print(f"\nStaff member added (ID: {staff_id})")

    def _list_staff(self):
        """List all staff."""
        show_all = input("Include inactive staff? (y/n) [n]: ").strip().lower() == 'y'
        staff = StaffManager.get_all_staff(active_only=not show_all)
        if not staff:
            print("\nNo staff found.")
            return
        print(f"\n{'ID':<6}{'Name':<25}{'Employee ID':<15}{'Specialties':<25}{'Active'}")
        print("-" * 75)
        for s in staff:
            print(f"{s['staff_id']:<6}{s['name']:<25}{(s.get('employee_id') or 'N/A'):<15}"
                  f"{(s.get('specialties') or 'N/A'):<25}{'Yes' if s['is_active'] else 'No'}")

    def _view_staff(self):
        """View staff details."""
        staff_id = int(input("Staff ID: ").strip())
        staff = StaffManager.get_staff(staff_id)
        if not staff:
            print("Staff member not found.")
            return
        print(f"\nID: {staff['staff_id']}")
        print(f"Name: {staff['name']}")
        print(f"Employee ID: {staff.get('employee_id', 'N/A')}")
        print(f"Specialties: {staff.get('specialties', 'N/A')}")
        print(f"Phone: {staff.get('phone', 'N/A')}")
        print(f"Email: {staff.get('email', 'N/A')}")
        print(f"Active: {'Yes' if staff['is_active'] else 'No'}")
        print(f"Hire Date: {staff.get('hire_date', 'N/A')}")

    def _staff_availability(self):
        """Check staff availability."""
        staff_id = int(input("Staff ID: ").strip())
        date = input(f"Date (YYYY-MM-DD) [{datetime.now().strftime('%Y-%m-%d')}]: ").strip()
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        available = StaffManager.get_staff_availability(staff_id, date)
        if not available:
            print(f"\nNo available slots on {date}.")
            return
        print(f"\nAvailable slots on {date}:")
        for slot in available:
            print(f"  {slot}")

    def _block_slot(self):
        """Block a time slot."""
        staff_id = int(input("Staff ID: ").strip())
        date = input("Date (YYYY-MM-DD): ").strip()
        start_time = input("Start time (HH:MM): ").strip()
        end_time = input("End time (HH:MM): ").strip()
        reason = input("Reason: ").strip()
        blocked_by = input("Blocked by: ").strip()

        block_id = BlockedSlotManager.block_slot(
            staff_id=staff_id, date=date, start_time=start_time,
            end_time=end_time, reason=reason, blocked_by=blocked_by,
        )
        print(f"\nSlot blocked (ID: {block_id})")

    def _view_blocked(self):
        """View blocked slots."""
        sid = input("Staff ID (blank for all): ").strip()
        staff_id = int(sid) if sid else None
        date = input("Date (blank for all): ").strip() or None
        slots = BlockedSlotManager.get_blocked_slots(staff_id=staff_id, date=date)
        if not slots:
            print("\nNo blocked slots found.")
            return
        print(f"\n{'ID':<6}{'Staff':<8}{'Date':<12}{'Start':<8}{'End':<8}{'Reason'}")
        print("-" * 55)
        for s in slots:
            print(f"{s['block_id']:<6}{s['staff_id']:<8}{s['blocked_date']:<12}"
                  f"{s['start_time']:<8}{s['end_time']:<8}{s.get('reason', '')}")

    def _unblock_slot(self):
        """Unblock a slot."""
        block_id = int(input("Block ID: ").strip())
        BlockedSlotManager.unblock_slot(block_id)
        print("Slot unblocked.")

    # ========== Appointments ==========

    def _appointments_menu(self):
        """Appointments sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  APPOINTMENT MANAGEMENT")
            print("-" * 50)
            print("  1. Book Appointment")
            print("  2. View Appointment")
            print("  3. Lookup by Appointment Number")
            print("  4. Today's Appointments")
            print("  5. Appointments by Date")
            print("  6. Customer Appointments")
            print("  7. Update Appointment Status")
            print("  8. Cancel Appointment")
            print("  9. Reschedule Appointment")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._book_appointment()
                elif choice == '2':
                    self._view_appointment()
                elif choice == '3':
                    self._lookup_appointment()
                elif choice == '4':
                    self._todays_appointments()
                elif choice == '5':
                    self._appointments_by_date()
                elif choice == '6':
                    self._customer_appointments()
                elif choice == '7':
                    self._update_appointment_status()
                elif choice == '8':
                    self._cancel_appointment()
                elif choice == '9':
                    self._reschedule_appointment()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _book_appointment(self):
        """Book a new appointment."""
        print("\n--- Book Appointment ---")
        customer_id = input("Customer ID: ").strip()
        customer_name = input("Customer name: ").strip()
        customer_email = input("Email (optional): ").strip() or None
        customer_phone = input("Phone (optional): ").strip() or None

        # Show available services
        services = ServiceManager.get_all_services()
        print("\nAvailable services:")
        for s in services:
            print(f"  {s['service_id']}. {s['name']} - {s['price']:.2f} ({s['duration_minutes']} min)")

        service_id = int(input("\nService ID: ").strip())
        appointment_date = input("Date (YYYY-MM-DD): ").strip()

        # Show available staff
        staff = StaffManager.get_all_staff()
        if staff:
            print("\nAvailable barbers:")
            for s in staff:
                print(f"  {s['staff_id']}. {s['name']} ({s.get('specialties', 'General')})")
        sid = input("Barber ID (optional): ").strip()
        staff_id = int(sid) if sid else None

        # Show time slots
        if staff_id:
            available_slots = StaffManager.get_staff_availability(staff_id, appointment_date)
            print(f"\nAvailable slots: {', '.join(available_slots) if available_slots else 'None'}")
        else:
            print(f"\nTime slots: {', '.join(TIME_SLOTS)}")

        appointment_time = input("Time (HH:MM): ").strip()
        special_requests = input("Special requests (optional): ").strip() or None

        appt_id, appt_number = AppointmentManager.book_appointment(
            customer_id=customer_id, customer_name=customer_name,
            service_id=service_id, appointment_date=appointment_date,
            appointment_time=appointment_time, staff_id=staff_id,
            customer_email=customer_email, customer_phone=customer_phone,
            special_requests=special_requests,
        )
        print(f"\nAppointment booked!")
        print(f"  ID: {appt_id}")
        print(f"  Number: {appt_number}")

    def _view_appointment(self):
        """View appointment details."""
        appointment_id = int(input("Appointment ID: ").strip())
        appt = AppointmentManager.get_appointment(appointment_id)
        if not appt:
            print("Appointment not found.")
            return
        self._print_appointment(appt)

    def _lookup_appointment(self):
        """Lookup appointment by number."""
        number = input("Appointment number: ").strip()
        appt = AppointmentManager.get_appointment_by_number(number)
        if not appt:
            print("Appointment not found.")
            return
        self._print_appointment(appt)

    def _print_appointment(self, appt):
        """Print appointment details."""
        print(f"\nAppointment #{appt['appointment_number']}")
        print(f"  Customer: {appt['customer_name']}")
        print(f"  Service: {appt['service_name']}")
        print(f"  Barber: {appt.get('staff_name') or 'Any available'}")
        print(f"  Date: {appt['appointment_date']}")
        print(f"  Time: {appt['appointment_time']}")
        print(f"  Duration: {appt['duration_minutes']} min")
        print(f"  Price: {appt['price']:.2f}")
        print(f"  Status: {appt['status']}")
        print(f"  Payment: {appt['payment_status']}")

    def _todays_appointments(self):
        """Show today's appointments."""
        appointments = AppointmentManager.get_todays_appointments()
        self._display_appointments(appointments, "Today's Appointments")

    def _appointments_by_date(self):
        """Show appointments by date."""
        date = input("Date (YYYY-MM-DD): ").strip()
        appointments = AppointmentManager.get_appointments_by_date(date)
        self._display_appointments(appointments, f"Appointments for {date}")

    def _customer_appointments(self):
        """Show customer's appointments."""
        customer_id = input("Customer ID: ").strip()
        appointments = AppointmentManager.get_customer_appointments(customer_id)
        self._display_appointments(appointments, "Customer Appointments")

    def _display_appointments(self, appointments, title):
        """Display a list of appointments."""
        if not appointments:
            print(f"\nNo appointments found.")
            return
        print(f"\n{title}:")
        print(f"{'ID':<6}{'Number':<22}{'Customer':<20}{'Service':<20}{'Time':<8}{'Status'}")
        print("-" * 85)
        for a in appointments:
            print(f"{a['appointment_id']:<6}{a['appointment_number']:<22}{a['customer_name']:<20}"
                  f"{a['service_name']:<20}{a['appointment_time']:<8}{a['status']}")

    def _update_appointment_status(self):
        """Update appointment status."""
        appointment_id = int(input("Appointment ID: ").strip())
        print(f"Statuses: {', '.join(APPOINTMENT_STATUSES)}")
        status = input("New status: ").strip()
        updated = AppointmentManager.update_status(appointment_id, status)
        print("Status updated." if updated else "Invalid status.")

    def _cancel_appointment(self):
        """Cancel an appointment."""
        appointment_id = int(input("Appointment ID: ").strip())
        reason = input("Reason (optional): ").strip() or None
        AppointmentManager.cancel_appointment(appointment_id, reason)
        print("Appointment cancelled.")

    def _reschedule_appointment(self):
        """Reschedule an appointment."""
        appointment_id = int(input("Appointment ID: ").strip())
        new_date = input("New date (YYYY-MM-DD): ").strip()
        new_time = input("New time (HH:MM): ").strip()
        sid = input("New barber ID (blank to keep same): ").strip()
        new_staff_id = int(sid) if sid else None

        AppointmentManager.reschedule_appointment(
            appointment_id, new_date, new_time, new_staff_id,
        )
        print("Appointment rescheduled.")

    # ========== Payments ==========

    def _payments_menu(self):
        """Payments sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  PAYMENT PROCESSING")
            print("-" * 50)
            print("  1. Process Payment")
            print("  2. View Transaction")
            print("  3. Mark Receipt Sent")
            print("  4. Daily Revenue")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._process_payment()
                elif choice == '2':
                    self._view_transaction()
                elif choice == '3':
                    self._mark_receipt()
                elif choice == '4':
                    self._daily_revenue()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _process_payment(self):
        """Process a payment."""
        print("\n--- Process Payment ---")
        appointment_id = int(input("Appointment ID: ").strip())
        amount = float(input("Amount: ").strip())
        payment_method = input("Payment method (cash/card/contactless): ").strip()
        customer_id = input("Customer ID: ").strip()
        tip = input("Tip amount [0]: ").strip()
        tip_amount = float(tip) if tip else 0

        txn_id = TransactionManager.process_payment(
            appointment_id=appointment_id, amount=amount,
            payment_method=payment_method, customer_id=customer_id,
            tip_amount=tip_amount,
        )
        print(f"\nPayment processed (Transaction ID: {txn_id})")

    def _view_transaction(self):
        """View a transaction."""
        txn_id = int(input("Transaction ID: ").strip())
        txn = TransactionManager.get_transaction(txn_id)
        if not txn:
            print("Transaction not found.")
            return
        print(f"\nTransaction ID: {txn['transaction_id']}")
        print(f"Amount: {txn['amount']:.2f}")
        print(f"Tip: {txn.get('tip_amount', 0):.2f}")
        print(f"Payment Method: {txn['payment_method']}")
        print(f"Status: {txn['status']}")
        print(f"Date: {txn['created_at']}")

    def _mark_receipt(self):
        """Mark receipt as sent."""
        txn_id = int(input("Transaction ID: ").strip())
        TransactionManager.mark_receipt_sent(txn_id)
        print("Receipt marked as sent.")

    def _daily_revenue(self):
        """Show daily revenue."""
        date = input(f"Date [{datetime.now().strftime('%Y-%m-%d')}]: ").strip() or None
        revenue = TransactionManager.get_daily_revenue(date)
        print(f"\nRevenue for {revenue['date']}:")
        print(f"  Transactions: {revenue['transaction_count']}")
        print(f"  Service Revenue: {revenue['service_revenue']:.2f}")
        print(f"  Tips: {revenue['tips']:.2f}")
        print(f"  Total: {revenue['total_revenue']:.2f}")

    # ========== Waitlist ==========

    def _waitlist_menu(self):
        """Waitlist sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  WAITLIST MANAGEMENT")
            print("-" * 50)
            print("  1. Add to Waitlist")
            print("  2. View Waitlist")
            print("  3. Notify Customer")
            print("  4. Remove from Waitlist")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._add_to_waitlist()
                elif choice == '2':
                    self._view_waitlist()
                elif choice == '3':
                    self._notify_waitlist()
                elif choice == '4':
                    self._remove_from_waitlist()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _add_to_waitlist(self):
        """Add a customer to the waitlist."""
        print("\n--- Add to Waitlist ---")
        customer_id = input("Customer ID: ").strip()
        customer_name = input("Customer name: ").strip()
        customer_email = input("Email: ").strip()
        customer_phone = input("Phone: ").strip()
        preferred_date = input("Preferred date (YYYY-MM-DD): ").strip()
        preferred_time = input("Preferred time (HH:MM): ").strip()
        service_id = int(input("Service ID: ").strip())
        sid = input("Preferred barber ID (optional): ").strip()
        staff_id = int(sid) if sid else None
        notes = input("Notes (optional): ").strip() or None

        wl_id = WaitlistManager.add_to_waitlist(
            customer_id=customer_id, customer_name=customer_name,
            customer_email=customer_email, customer_phone=customer_phone,
            preferred_date=preferred_date, preferred_time=preferred_time,
            service_id=service_id, staff_id=staff_id, notes=notes,
        )
        print(f"\nAdded to waitlist (ID: {wl_id})")

    def _view_waitlist(self):
        """View the waitlist."""
        date = input("Date filter (blank for all): ").strip() or None
        entries = WaitlistManager.get_waitlist(date=date)
        if not entries:
            print("\nWaitlist is empty.")
            return
        print(f"\n{'ID':<6}{'Customer':<20}{'Date':<12}{'Time':<8}{'Service':<8}{'Status'}")
        print("-" * 60)
        for e in entries:
            print(f"{e['waitlist_id']:<6}{e['customer_name']:<20}"
                  f"{e['preferred_date']:<12}{e['preferred_time']:<8}"
                  f"{e['service_id']:<8}{e['status']}")

    def _notify_waitlist(self):
        """Notify a waitlist customer."""
        waitlist_id = int(input("Waitlist ID: ").strip())
        available_slot = input("Available slot (e.g. 2024-01-15 14:00): ").strip()
        WaitlistManager.notify_waitlist(waitlist_id, available_slot)
        print("Customer notified.")

    def _remove_from_waitlist(self):
        """Remove from waitlist."""
        waitlist_id = int(input("Waitlist ID: ").strip())
        reason = input("Reason (booked/cancelled) [booked]: ").strip() or 'booked'
        WaitlistManager.remove_from_waitlist(waitlist_id, reason)
        print("Removed from waitlist.")

    # ========== Reports ==========

    def _reports_menu(self):
        """Reports sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  REPORTS & ANALYTICS")
            print("-" * 50)
            print("  1. Sales Report")
            print("  2. Admin Report")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._sales_report()
                elif choice == '2':
                    self._admin_report()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _sales_report(self):
        """Generate sales report."""
        start_date = input("Start date (YYYY-MM-DD): ").strip()
        end_date = input("End date (YYYY-MM-DD): ").strip()
        report = ReportManager.generate_sales_report(start_date, end_date)

        summary = report.get('summary', {})
        print(f"\n--- Sales Report ({start_date} to {end_date}) ---")
        print(f"Total Appointments: {summary.get('total_appointments', 0)}")
        print(f"Service Revenue: {(summary.get('service_revenue') or 0):.2f}")
        print(f"Total Tips: {(summary.get('total_tips') or 0):.2f}")
        print(f"Avg Service Value: {(summary.get('avg_service_value') or 0):.2f}")

        if report.get('by_service'):
            print("\nBy Service:")
            for s in report['by_service']:
                print(f"  {s['service_name']}: {s['count']} bookings ({(s['revenue'] or 0):.2f})")

        if report.get('by_staff'):
            print("\nBy Staff:")
            for s in report['by_staff']:
                print(f"  {s['staff_name']}: {s['appointments']} appts, "
                      f"{(s['revenue'] or 0):.2f} revenue, {(s['tips'] or 0):.2f} tips")

    def _admin_report(self):
        """Generate admin report."""
        report = ReportManager.generate_admin_report()
        print(report)


def main():
    """Entry point for the Barber Shop CLI."""
    cli = BarberCLI()
    cli.run()


if __name__ == "__main__":
    main()
