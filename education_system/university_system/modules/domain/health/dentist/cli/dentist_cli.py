"""
Dentist / Dental Clinic CLI Interface

Provides command-line interface for dental clinic management including:
- Patient registration and management
- Appointment booking and scheduling
- Treatment recording
- Prescription management
- Payment processing
- Reporting and analytics
"""

from datetime import datetime
from typing import Optional

from education_system.university_system.modules.domain.health.dentist.services.dentist_core import (
    PatientManager,
    AppointmentManager,
    TreatmentManager,
    PrescriptionManager,
    TransactionManager,
    ReportManager,
    init_dentist_db,
    TREATMENT_TYPES,
    APPOINTMENT_STATUSES,
    DENTIST_STAFF,
    WORKING_HOURS,
    APPOINTMENT_SLOTS,
)
from education_system.university_system.infrastructure.database.db import get_connection


class DentistCLI:
    """Command-line interface for the Dental Clinic."""

    def __init__(self):
        """Initialize the Dentist CLI and database."""
        init_dentist_db()
        self.patient_mgr = PatientManager()
        self.appointment_mgr = AppointmentManager()
        self.treatment_mgr = TreatmentManager()
        self.prescription_mgr = PrescriptionManager()
        self.transaction_mgr = TransactionManager()
        self.report_mgr = ReportManager()

    def run(self):
        """Run the dentist CLI main loop."""
        while True:
            self._display_main_menu()
            choice = input("\nSelect an option: ").strip()

            if choice == '0':
                print("\nReturning to main menu...")
                break
            elif choice == '1':
                self._patient_menu()
            elif choice == '2':
                self._appointment_menu()
            elif choice == '3':
                self._treatment_menu()
            elif choice == '4':
                self._prescription_menu()
            elif choice == '5':
                self._payment_menu()
            elif choice == '6':
                self._report_menu()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

    # ========== Main Menu ==========

    def _display_main_menu(self):
        """Display the main menu."""
        print("\n" + "=" * 70)
        print("  DENTAL CLINIC MANAGEMENT SYSTEM".center(70))
        print("=" * 70)
        print("\n  1. Patient Management")
        print("  2. Appointments")
        print("  3. Treatments")
        print("  4. Prescriptions")
        print("  5. Payments")
        print("  6. Reports")
        print("\n  0. Back to Main Menu")
        print("=" * 70)

    # ========== Patient Management ==========

    def _patient_menu(self):
        """Patient management sub-menu."""
        while True:
            print("\n" + "=" * 70)
            print("  PATIENT MANAGEMENT".center(70))
            print("=" * 70)
            print("\n  1. Register New Patient")
            print("  2. Search Patients")
            print("  3. View Patient Details")
            print("  4. View All Patients")
            print("  5. Update Patient Information")
            print("\n  0. Back")
            print("=" * 70)

            choice = input("\nSelect an option: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self._register_patient()
            elif choice == '2':
                self._search_patients()
            elif choice == '3':
                self._view_patient_details()
            elif choice == '4':
                self._view_all_patients()
            elif choice == '5':
                self._update_patient()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

    def _register_patient(self):
        """Register a new patient."""
        print("\n" + "-" * 70)
        print("  REGISTER NEW PATIENT".center(70))
        print("-" * 70)

        try:
            user_id = input("User ID: ").strip()
            if not user_id:
                print("\nUser ID is required.")
                input("\nPress Enter to continue...")
                return

            user_name = input("Full Name: ").strip()
            if not user_name:
                print("\nFull name is required.")
                input("\nPress Enter to continue...")
                return

            user_email = input("Email: ").strip()
            if not user_email:
                print("\nEmail is required.")
                input("\nPress Enter to continue...")
                return

            user_phone = input("Phone (optional): ").strip() or None
            date_of_birth = input("Date of Birth (YYYY-MM-DD, optional): ").strip() or None
            address = input("Address (optional): ").strip() or None
            emergency_contact = input("Emergency Contact Name (optional): ").strip() or None
            emergency_phone = input("Emergency Contact Phone (optional): ").strip() or None
            medical_history = input("Medical History (optional): ").strip() or None
            allergies = input("Allergies (optional): ").strip() or None

            result = self.patient_mgr.register_patient(
                user_id=user_id,
                user_name=user_name,
                user_email=user_email,
                user_phone=user_phone,
                date_of_birth=date_of_birth,
                address=address,
                emergency_contact=emergency_contact,
                emergency_phone=emergency_phone,
                medical_history=medical_history,
                allergies=allergies,
            )

            if result:
                print(f"\nPatient registered successfully!")
                print(f"  Patient ID: {result['patient_id']}")
                print(f"  Patient Number: {result['patient_number']}")
            else:
                print("\nFailed to register patient.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _search_patients(self):
        """Search for patients."""
        print("\n" + "-" * 70)
        print("  SEARCH PATIENTS".center(70))
        print("-" * 70)

        try:
            search_term = input("Search (name, number, or email): ").strip()
            if not search_term:
                print("\nPlease enter a search term.")
                input("\nPress Enter to continue...")
                return

            patients = self.patient_mgr.search_patients(search_term)
            if patients:
                print(f"\nFound {len(patients)} patient(s):\n")
                print(f"  {'ID':<6} {'Number':<16} {'Name':<25} {'Email':<25}")
                print("  " + "-" * 68)
                for p in patients:
                    print(f"  {p['patient_id']:<6} {p['patient_number']:<16} "
                          f"{p['user_name']:<25} {p.get('user_email', ''):<25}")
            else:
                print("\nNo patients found.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _view_patient_details(self):
        """View detailed patient information."""
        print("\n" + "-" * 70)
        print("  VIEW PATIENT DETAILS".center(70))
        print("-" * 70)

        try:
            patient_id_str = input("Enter Patient ID: ").strip()
            if not patient_id_str:
                print("\nPatient ID is required.")
                input("\nPress Enter to continue...")
                return

            patient = self.patient_mgr.get_patient(patient_id=int(patient_id_str))
            if patient:
                print(f"\n  Patient Number:     {patient['patient_number']}")
                print(f"  Name:               {patient['user_name']}")
                print(f"  Email:              {patient.get('user_email', 'N/A')}")
                print(f"  Phone:              {patient.get('user_phone', 'N/A')}")
                print(f"  Date of Birth:      {patient.get('date_of_birth', 'N/A')}")
                print(f"  Address:            {patient.get('address', 'N/A')}")
                print(f"  Emergency Contact:  {patient.get('emergency_contact', 'N/A')}")
                print(f"  Emergency Phone:    {patient.get('emergency_phone', 'N/A')}")
                print(f"  Medical History:    {patient.get('medical_history', 'N/A')}")
                print(f"  Allergies:          {patient.get('allergies', 'N/A')}")
                print(f"  Insurance Provider: {patient.get('insurance_provider', 'N/A')}")
                print(f"  Insurance Number:   {patient.get('insurance_number', 'N/A')}")
                print(f"  Last Visit:         {patient.get('last_visit', 'N/A')}")
                print(f"  Notes:              {patient.get('notes', 'N/A')}")
                print(f"  Registered:         {patient.get('created_at', 'N/A')}")
            else:
                print("\nPatient not found.")
        except ValueError:
            print("\nInvalid Patient ID. Please enter a number.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _view_all_patients(self):
        """View all patients."""
        print("\n" + "-" * 70)
        print("  ALL PATIENTS".center(70))
        print("-" * 70)

        try:
            patients = self.patient_mgr.get_all_patients()
            if patients:
                print(f"\n  Total patients: {len(patients)}\n")
                print(f"  {'ID':<6} {'Number':<16} {'Name':<25} {'Phone':<15} {'Last Visit':<12}")
                print("  " + "-" * 68)
                for p in patients:
                    print(f"  {p['patient_id']:<6} {p['patient_number']:<16} "
                          f"{p['user_name']:<25} {(p.get('user_phone') or 'N/A'):<15} "
                          f"{(p.get('last_visit') or 'N/A'):<12}")
            else:
                print("\nNo patients registered yet.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _update_patient(self):
        """Update patient information."""
        print("\n" + "-" * 70)
        print("  UPDATE PATIENT INFORMATION".center(70))
        print("-" * 70)

        try:
            patient_id_str = input("Enter Patient ID: ").strip()
            if not patient_id_str:
                print("\nPatient ID is required.")
                input("\nPress Enter to continue...")
                return

            patient_id = int(patient_id_str)
            patient = self.patient_mgr.get_patient(patient_id=patient_id)
            if not patient:
                print("\nPatient not found.")
                input("\nPress Enter to continue...")
                return

            print(f"\nUpdating patient: {patient['user_name']} ({patient['patient_number']})")
            print("Leave blank to keep current value.\n")

            updates = {}
            fields = [
                ('user_phone', 'Phone', patient.get('user_phone')),
                ('address', 'Address', patient.get('address')),
                ('emergency_contact', 'Emergency Contact', patient.get('emergency_contact')),
                ('emergency_phone', 'Emergency Phone', patient.get('emergency_phone')),
                ('medical_history', 'Medical History', patient.get('medical_history')),
                ('allergies', 'Allergies', patient.get('allergies')),
                ('insurance_provider', 'Insurance Provider', patient.get('insurance_provider')),
                ('insurance_number', 'Insurance Number', patient.get('insurance_number')),
            ]

            for field_key, field_label, current_val in fields:
                new_val = input(f"  {field_label} [{current_val or 'N/A'}]: ").strip()
                if new_val:
                    updates[field_key] = new_val

            if updates:
                success = self.patient_mgr.update_patient(patient_id, **updates)
                if success:
                    print("\nPatient information updated successfully.")
                else:
                    print("\nFailed to update patient information.")
            else:
                print("\nNo changes made.")
        except ValueError:
            print("\nInvalid Patient ID. Please enter a number.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    # ========== Appointment Management ==========

    def _appointment_menu(self):
        """Appointment management sub-menu."""
        while True:
            print("\n" + "=" * 70)
            print("  APPOINTMENT MANAGEMENT".center(70))
            print("=" * 70)
            print("\n  1. Book Appointment")
            print("  2. View Today's Appointments")
            print("  3. View Patient Appointments")
            print("  4. View Dentist Schedule")
            print("  5. Check Available Slots")
            print("  6. Update Appointment Status")
            print("  7. Cancel Appointment")
            print("  8. Reschedule Appointment")
            print("  9. View Upcoming Appointments")
            print("\n  0. Back")
            print("=" * 70)

            choice = input("\nSelect an option: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self._book_appointment()
            elif choice == '2':
                self._view_todays_appointments()
            elif choice == '3':
                self._view_patient_appointments()
            elif choice == '4':
                self._view_dentist_schedule()
            elif choice == '5':
                self._check_available_slots()
            elif choice == '6':
                self._update_appointment_status()
            elif choice == '7':
                self._cancel_appointment()
            elif choice == '8':
                self._reschedule_appointment()
            elif choice == '9':
                self._view_upcoming_appointments()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

    def _select_dentist(self) -> Optional[dict]:
        """Display dentist list and let user select one. Returns selected dentist dict or None."""
        print("\n  Available Dentists:")
        for i, d in enumerate(DENTIST_STAFF, 1):
            print(f"    {i}. {d['name']} - {d['specialization']} ({d['id']})")

        choice = input("\n  Select dentist (number): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(DENTIST_STAFF):
                return DENTIST_STAFF[idx]
        except ValueError:
            pass
        print("\n  Invalid dentist selection.")
        return None

    def _select_treatment_type(self) -> Optional[str]:
        """Display treatment types and let user select one. Returns treatment key or None."""
        print("\n  Treatment Types:")
        keys = list(TREATMENT_TYPES.keys())
        for i, key in enumerate(keys, 1):
            t = TREATMENT_TYPES[key]
            print(f"    {i}. {t['name']} - {t['duration']} min - £{t['fee']:.2f}")

        choice = input("\n  Select treatment type (number): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(keys):
                return keys[idx]
        except ValueError:
            pass
        print("\n  Invalid treatment type selection.")
        return None

    def _book_appointment(self):
        """Book a new appointment."""
        print("\n" + "-" * 70)
        print("  BOOK APPOINTMENT".center(70))
        print("-" * 70)

        try:
            patient_id_str = input("Patient ID: ").strip()
            if not patient_id_str:
                print("\nPatient ID is required.")
                input("\nPress Enter to continue...")
                return
            patient_id = int(patient_id_str)

            patient = self.patient_mgr.get_patient(patient_id=patient_id)
            if not patient:
                print("\nPatient not found.")
                input("\nPress Enter to continue...")
                return

            print(f"\nBooking for: {patient['user_name']} ({patient['patient_number']})")

            dentist = self._select_dentist()
            if not dentist:
                input("\nPress Enter to continue...")
                return

            appointment_date = input("\n  Appointment Date (YYYY-MM-DD): ").strip()
            if not appointment_date:
                print("\nDate is required.")
                input("\nPress Enter to continue...")
                return

            # Show available slots
            available = self.appointment_mgr.get_available_slots(dentist['id'], appointment_date)
            if not available:
                print(f"\nNo available slots for {dentist['name']} on {appointment_date}.")
                input("\nPress Enter to continue...")
                return

            print(f"\n  Available slots for {appointment_date}:")
            for i, slot in enumerate(available, 1):
                print(f"    {i}. {slot}")

            slot_choice = input("\n  Select time slot (number): ").strip()
            try:
                slot_idx = int(slot_choice) - 1
                if 0 <= slot_idx < len(available):
                    appointment_time = available[slot_idx]
                else:
                    print("\nInvalid slot selection.")
                    input("\nPress Enter to continue...")
                    return
            except ValueError:
                print("\nInvalid input.")
                input("\nPress Enter to continue...")
                return

            treatment_type = self._select_treatment_type()
            if not treatment_type:
                input("\nPress Enter to continue...")
                return

            notes = input("\n  Notes (optional): ").strip() or None

            result = self.appointment_mgr.book_appointment(
                patient_id=patient_id,
                dentist_id=dentist['id'],
                dentist_name=dentist['name'],
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                treatment_type=treatment_type,
                notes=notes,
            )

            if result:
                print(f"\nAppointment booked successfully!")
                print(f"  Reference:     {result['appointment_ref']}")
                print(f"  Appointment ID: {result['appointment_id']}")
                print(f"  Estimated Fee: £{result['estimated_fee']:.2f}")
            else:
                print("\nFailed to book appointment. The slot may already be taken.")
        except ValueError:
            print("\nInvalid Patient ID. Please enter a number.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _view_todays_appointments(self):
        """View all appointments for today."""
        print("\n" + "-" * 70)
        print("  TODAY'S APPOINTMENTS".center(70))
        print("-" * 70)

        try:
            appointments = self.appointment_mgr.get_todays_appointments()
            if appointments:
                print(f"\n  Date: {datetime.now().date().isoformat()}")
                print(f"  Total: {len(appointments)}\n")
                print(f"  {'Time':<8} {'Patient':<22} {'Dentist':<22} {'Type':<15} {'Status':<12}")
                print("  " + "-" * 68)
                for a in appointments:
                    t_info = TREATMENT_TYPES.get(a['treatment_type'], {})
                    t_name = t_info.get('name', a['treatment_type'])
                    print(f"  {a['appointment_time']:<8} {a.get('patient_name', 'N/A'):<22} "
                          f"{a['dentist_name']:<22} {t_name:<15} {a['status']:<12}")
            else:
                print("\nNo appointments scheduled for today.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _view_patient_appointments(self):
        """View appointments for a specific patient."""
        print("\n" + "-" * 70)
        print("  PATIENT APPOINTMENTS".center(70))
        print("-" * 70)

        try:
            patient_id_str = input("Patient ID: ").strip()
            if not patient_id_str:
                print("\nPatient ID is required.")
                input("\nPress Enter to continue...")
                return

            patient_id = int(patient_id_str)
            appointments = self.appointment_mgr.get_patient_appointments(patient_id)

            if appointments:
                print(f"\n  Total appointments: {len(appointments)}\n")
                print(f"  {'ID':<6} {'Ref':<20} {'Date':<12} {'Time':<8} {'Dentist':<22} {'Status':<12}")
                print("  " + "-" * 68)
                for a in appointments:
                    print(f"  {a['appointment_id']:<6} {a['appointment_ref']:<20} "
                          f"{a['appointment_date']:<12} {a['appointment_time']:<8} "
                          f"{a['dentist_name']:<22} {a['status']:<12}")
            else:
                print("\nNo appointments found for this patient.")
        except ValueError:
            print("\nInvalid Patient ID. Please enter a number.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _view_dentist_schedule(self):
        """View a dentist's schedule for a given date."""
        print("\n" + "-" * 70)
        print("  DENTIST SCHEDULE".center(70))
        print("-" * 70)

        try:
            dentist = self._select_dentist()
            if not dentist:
                input("\nPress Enter to continue...")
                return

            date = input("\n  Date (YYYY-MM-DD): ").strip()
            if not date:
                date = datetime.now().date().isoformat()

            schedule = self.appointment_mgr.get_dentist_schedule(dentist['id'], date)

            print(f"\n  Schedule for {dentist['name']} on {date}:")
            if schedule:
                print(f"\n  {'Time':<8} {'Patient':<25} {'Treatment':<20} {'Status':<12}")
                print("  " + "-" * 65)
                for a in schedule:
                    t_info = TREATMENT_TYPES.get(a['treatment_type'], {})
                    t_name = t_info.get('name', a['treatment_type'])
                    print(f"  {a['appointment_time']:<8} {a.get('patient_name', 'N/A'):<25} "
                          f"{t_name:<20} {a['status']:<12}")
            else:
                print("\n  No appointments scheduled.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _check_available_slots(self):
        """Check available appointment slots."""
        print("\n" + "-" * 70)
        print("  AVAILABLE SLOTS".center(70))
        print("-" * 70)

        try:
            dentist = self._select_dentist()
            if not dentist:
                input("\nPress Enter to continue...")
                return

            date = input("\n  Date (YYYY-MM-DD): ").strip()
            if not date:
                print("\nDate is required.")
                input("\nPress Enter to continue...")
                return

            slots = self.appointment_mgr.get_available_slots(dentist['id'], date)

            print(f"\n  Available slots for {dentist['name']} on {date}:")
            if slots:
                for i, slot in enumerate(slots, 1):
                    print(f"    {i}. {slot}")
                print(f"\n  {len(slots)} slot(s) available.")
            else:
                print("\n  No available slots.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _update_appointment_status(self):
        """Update an appointment's status."""
        print("\n" + "-" * 70)
        print("  UPDATE APPOINTMENT STATUS".center(70))
        print("-" * 70)

        try:
            appt_id_str = input("Appointment ID: ").strip()
            if not appt_id_str:
                print("\nAppointment ID is required.")
                input("\nPress Enter to continue...")
                return

            appt_id = int(appt_id_str)
            appt = self.appointment_mgr.get_appointment(appointment_id=appt_id)
            if not appt:
                print("\nAppointment not found.")
                input("\nPress Enter to continue...")
                return

            print(f"\n  Current status: {appt['status']}")
            print("\n  Available statuses:")
            for i, status in enumerate(APPOINTMENT_STATUSES, 1):
                print(f"    {i}. {status}")

            choice = input("\n  Select new status (number): ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(APPOINTMENT_STATUSES):
                    new_status = APPOINTMENT_STATUSES[idx]
                else:
                    print("\nInvalid selection.")
                    input("\nPress Enter to continue...")
                    return
            except ValueError:
                print("\nInvalid input.")
                input("\nPress Enter to continue...")
                return

            success = self.appointment_mgr.update_appointment_status(appt_id, new_status)
            if success:
                print(f"\nAppointment status updated to '{new_status}'.")
            else:
                print("\nFailed to update appointment status.")
        except ValueError:
            print("\nInvalid Appointment ID. Please enter a number.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _cancel_appointment(self):
        """Cancel an appointment."""
        print("\n" + "-" * 70)
        print("  CANCEL APPOINTMENT".center(70))
        print("-" * 70)

        try:
            appt_id_str = input("Appointment ID: ").strip()
            if not appt_id_str:
                print("\nAppointment ID is required.")
                input("\nPress Enter to continue...")
                return

            appt_id = int(appt_id_str)
            appt = self.appointment_mgr.get_appointment(appointment_id=appt_id)
            if not appt:
                print("\nAppointment not found.")
                input("\nPress Enter to continue...")
                return

            print(f"\n  Appointment: {appt['appointment_ref']}")
            print(f"  Date: {appt['appointment_date']} at {appt['appointment_time']}")
            print(f"  Dentist: {appt['dentist_name']}")
            print(f"  Status: {appt['status']}")

            confirm = input("\n  Are you sure you want to cancel? (y/n): ").strip().lower()
            if confirm == 'y':
                success = self.appointment_mgr.cancel_appointment(appt_id)
                if success:
                    print("\nAppointment cancelled successfully.")
                else:
                    print("\nFailed to cancel appointment.")
            else:
                print("\nCancellation aborted.")
        except ValueError:
            print("\nInvalid Appointment ID. Please enter a number.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _reschedule_appointment(self):
        """Reschedule an appointment."""
        print("\n" + "-" * 70)
        print("  RESCHEDULE APPOINTMENT".center(70))
        print("-" * 70)

        try:
            appt_id_str = input("Appointment ID: ").strip()
            if not appt_id_str:
                print("\nAppointment ID is required.")
                input("\nPress Enter to continue...")
                return

            appt_id = int(appt_id_str)
            appt = self.appointment_mgr.get_appointment(appointment_id=appt_id)
            if not appt:
                print("\nAppointment not found.")
                input("\nPress Enter to continue...")
                return

            print(f"\n  Current: {appt['appointment_date']} at {appt['appointment_time']} "
                  f"with {appt['dentist_name']}")

            new_date = input("\n  New Date (YYYY-MM-DD): ").strip()
            if not new_date:
                print("\nDate is required.")
                input("\nPress Enter to continue...")
                return

            # Check available slots for that date
            available = self.appointment_mgr.get_available_slots(appt['dentist_id'], new_date)
            if not available:
                print(f"\nNo available slots on {new_date}.")
                input("\nPress Enter to continue...")
                return

            print(f"\n  Available slots on {new_date}:")
            for i, slot in enumerate(available, 1):
                print(f"    {i}. {slot}")

            slot_choice = input("\n  Select time slot (number): ").strip()
            try:
                slot_idx = int(slot_choice) - 1
                if 0 <= slot_idx < len(available):
                    new_time = available[slot_idx]
                else:
                    print("\nInvalid slot selection.")
                    input("\nPress Enter to continue...")
                    return
            except ValueError:
                print("\nInvalid input.")
                input("\nPress Enter to continue...")
                return

            result = self.appointment_mgr.reschedule_appointment(appt_id, new_date, new_time)
            if result:
                print(f"\nAppointment rescheduled successfully!")
                print(f"  Old: {result['old_date']} at {result['old_time']}")
                print(f"  New: {result['new_date']} at {result['new_time']}")
            else:
                print("\nFailed to reschedule. The slot may be unavailable.")
        except ValueError:
            print("\nInvalid Appointment ID. Please enter a number.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _view_upcoming_appointments(self):
        """View upcoming appointments."""
        print("\n" + "-" * 70)
        print("  UPCOMING APPOINTMENTS".center(70))
        print("-" * 70)

        try:
            days_str = input("Days ahead (default 7): ").strip()
            days = int(days_str) if days_str else 7

            appointments = self.report_mgr.get_upcoming_appointments(days=days)
            if appointments:
                print(f"\n  Upcoming appointments (next {days} days): {len(appointments)}\n")
                print(f"  {'Date':<12} {'Time':<8} {'Patient':<22} {'Dentist':<22} {'Status':<12}")
                print("  " + "-" * 68)
                for a in appointments:
                    print(f"  {a['appointment_date']:<12} {a['appointment_time']:<8} "
                          f"{a.get('user_name', 'N/A'):<22} {a['dentist_name']:<22} "
                          f"{a['status']:<12}")
            else:
                print(f"\nNo upcoming appointments in the next {days} days.")
        except ValueError:
            print("\nInvalid number of days.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    # ========== Treatment Management ==========

    def _treatment_menu(self):
        """Treatment management sub-menu."""
        while True:
            print("\n" + "=" * 70)
            print("  TREATMENT MANAGEMENT".center(70))
            print("=" * 70)
            print("\n  1. Record Treatment")
            print("  2. View Patient Treatment History")
            print("  3. View Pending Payments")
            print("  4. View Treatment Types")
            print("\n  0. Back")
            print("=" * 70)

            choice = input("\nSelect an option: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self._record_treatment()
            elif choice == '2':
                self._view_patient_treatments()
            elif choice == '3':
                self._view_pending_payments()
            elif choice == '4':
                self._view_treatment_types()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

    def _record_treatment(self):
        """Record a dental treatment."""
        print("\n" + "-" * 70)
        print("  RECORD TREATMENT".center(70))
        print("-" * 70)

        try:
            patient_id_str = input("Patient ID: ").strip()
            if not patient_id_str:
                print("\nPatient ID is required.")
                input("\nPress Enter to continue...")
                return
            patient_id = int(patient_id_str)

            patient = self.patient_mgr.get_patient(patient_id=patient_id)
            if not patient:
                print("\nPatient not found.")
                input("\nPress Enter to continue...")
                return

            print(f"\nRecording treatment for: {patient['user_name']}")

            dentist = self._select_dentist()
            if not dentist:
                input("\nPress Enter to continue...")
                return

            treatment_type = self._select_treatment_type()
            if not treatment_type:
                input("\nPress Enter to continue...")
                return

            treatment_date = input("\n  Treatment Date (YYYY-MM-DD, blank for today): ").strip()
            if not treatment_date:
                treatment_date = datetime.now().date().isoformat()

            appt_id_str = input("  Appointment ID (optional): ").strip()
            appointment_id = int(appt_id_str) if appt_id_str else None

            tooth_number = input("  Tooth Number (optional): ").strip() or None
            description = input("  Description (optional): ").strip() or None
            notes = input("  Notes (optional): ").strip() or None

            follow_up_input = input("  Follow-up required? (y/n): ").strip().lower()
            follow_up_required = follow_up_input == 'y'
            follow_up_date = None
            if follow_up_required:
                follow_up_date = input("  Follow-up Date (YYYY-MM-DD): ").strip() or None

            result = self.treatment_mgr.record_treatment(
                patient_id=patient_id,
                dentist_id=dentist['id'],
                dentist_name=dentist['name'],
                treatment_type=treatment_type,
                treatment_date=treatment_date,
                appointment_id=appointment_id,
                tooth_number=tooth_number,
                description=description,
                notes=notes,
                follow_up_required=follow_up_required,
                follow_up_date=follow_up_date,
            )

            if result:
                t_info = TREATMENT_TYPES.get(treatment_type, {})
                print(f"\nTreatment recorded successfully!")
                print(f"  Treatment ID: {result['treatment_id']}")
                print(f"  Type: {t_info.get('name', treatment_type)}")
                print(f"  Fee: £{result['fee']:.2f}")
            else:
                print("\nFailed to record treatment.")
        except ValueError:
            print("\nInvalid input. Please enter valid numbers.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _view_patient_treatments(self):
        """View treatment history for a patient."""
        print("\n" + "-" * 70)
        print("  PATIENT TREATMENT HISTORY".center(70))
        print("-" * 70)

        try:
            patient_id_str = input("Patient ID: ").strip()
            if not patient_id_str:
                print("\nPatient ID is required.")
                input("\nPress Enter to continue...")
                return

            patient_id = int(patient_id_str)
            treatments = self.treatment_mgr.get_patient_treatments(patient_id)

            if treatments:
                print(f"\n  Total treatments: {len(treatments)}\n")
                print(f"  {'ID':<6} {'Date':<12} {'Type':<20} {'Dentist':<22} {'Fee':<10} {'Payment':<10}")
                print("  " + "-" * 68)
                for t in treatments:
                    t_info = TREATMENT_TYPES.get(t['treatment_type'], {})
                    t_name = t_info.get('name', t['treatment_type'])
                    print(f"  {t['treatment_id']:<6} {t['treatment_date']:<12} "
                          f"{t_name:<20} {t['dentist_name']:<22} "
                          f"£{t['fee']:<9.2f} {t['payment_status']:<10}")
            else:
                print("\nNo treatments found for this patient.")
        except ValueError:
            print("\nInvalid Patient ID. Please enter a number.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _view_pending_payments(self):
        """View treatments with pending payments."""
        print("\n" + "-" * 70)
        print("  PENDING PAYMENTS".center(70))
        print("-" * 70)

        try:
            patient_id_str = input("Patient ID (blank for all): ").strip()
            patient_id = int(patient_id_str) if patient_id_str else None

            pending = self.treatment_mgr.get_pending_payments(patient_id=patient_id)

            if pending:
                total = sum(t['fee'] for t in pending)
                print(f"\n  Pending payments: {len(pending)}  |  Total: £{total:.2f}\n")
                print(f"  {'TID':<6} {'Patient':<22} {'Date':<12} {'Type':<20} {'Fee':<10}")
                print("  " + "-" * 68)
                for t in pending:
                    t_info = TREATMENT_TYPES.get(t['treatment_type'], {})
                    t_name = t_info.get('name', t['treatment_type'])
                    print(f"  {t['treatment_id']:<6} {t.get('patient_name', 'N/A'):<22} "
                          f"{t['treatment_date']:<12} {t_name:<20} £{t['fee']:<9.2f}")
            else:
                print("\nNo pending payments found.")
        except ValueError:
            print("\nInvalid Patient ID. Please enter a number.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _view_treatment_types(self):
        """Display all available treatment types."""
        print("\n" + "-" * 70)
        print("  TREATMENT TYPES".center(70))
        print("-" * 70)

        print(f"\n  {'Type':<20} {'Name':<25} {'Duration':<12} {'Fee':<10}")
        print("  " + "-" * 65)
        for key, t in TREATMENT_TYPES.items():
            print(f"  {key:<20} {t['name']:<25} {t['duration']} min{'':<6} £{t['fee']:.2f}")

        input("\nPress Enter to continue...")

    # ========== Prescription Management ==========

    def _prescription_menu(self):
        """Prescription management sub-menu."""
        while True:
            print("\n" + "=" * 70)
            print("  PRESCRIPTION MANAGEMENT".center(70))
            print("=" * 70)
            print("\n  1. Create Prescription")
            print("  2. View Patient Prescriptions")
            print("\n  0. Back")
            print("=" * 70)

            choice = input("\nSelect an option: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self._create_prescription()
            elif choice == '2':
                self._view_patient_prescriptions()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

    def _create_prescription(self):
        """Create a new prescription."""
        print("\n" + "-" * 70)
        print("  CREATE PRESCRIPTION".center(70))
        print("-" * 70)

        try:
            patient_id_str = input("Patient ID: ").strip()
            if not patient_id_str:
                print("\nPatient ID is required.")
                input("\nPress Enter to continue...")
                return
            patient_id = int(patient_id_str)

            patient = self.patient_mgr.get_patient(patient_id=patient_id)
            if not patient:
                print("\nPatient not found.")
                input("\nPress Enter to continue...")
                return

            print(f"\nPrescription for: {patient['user_name']}")

            dentist = self._select_dentist()
            if not dentist:
                input("\nPress Enter to continue...")
                return

            medication = input("\n  Medication: ").strip()
            if not medication:
                print("\nMedication is required.")
                input("\nPress Enter to continue...")
                return

            dosage = input("  Dosage (e.g., 500mg): ").strip()
            if not dosage:
                print("\nDosage is required.")
                input("\nPress Enter to continue...")
                return

            frequency = input("  Frequency (e.g., 3 times daily): ").strip()
            if not frequency:
                print("\nFrequency is required.")
                input("\nPress Enter to continue...")
                return

            duration = input("  Duration (e.g., 7 days): ").strip()
            if not duration:
                print("\nDuration is required.")
                input("\nPress Enter to continue...")
                return

            instructions = input("  Instructions (optional): ").strip() or None

            treatment_id_str = input("  Related Treatment ID (optional): ").strip()
            treatment_id = int(treatment_id_str) if treatment_id_str else None

            result = self.prescription_mgr.create_prescription(
                patient_id=patient_id,
                dentist_id=dentist['id'],
                dentist_name=dentist['name'],
                medication=medication,
                dosage=dosage,
                frequency=frequency,
                duration=duration,
                instructions=instructions,
                treatment_id=treatment_id,
            )

            if result:
                print(f"\nPrescription created successfully!")
                print(f"  Prescription ID: {result['prescription_id']}")
            else:
                print("\nFailed to create prescription.")
        except ValueError:
            print("\nInvalid input. Please enter valid numbers.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _view_patient_prescriptions(self):
        """View prescriptions for a patient."""
        print("\n" + "-" * 70)
        print("  PATIENT PRESCRIPTIONS".center(70))
        print("-" * 70)

        try:
            patient_id_str = input("Patient ID: ").strip()
            if not patient_id_str:
                print("\nPatient ID is required.")
                input("\nPress Enter to continue...")
                return

            patient_id = int(patient_id_str)
            prescriptions = self.prescription_mgr.get_patient_prescriptions(patient_id)

            if prescriptions:
                print(f"\n  Total prescriptions: {len(prescriptions)}\n")
                for p in prescriptions:
                    print(f"  Prescription #{p['prescription_id']}")
                    print(f"    Date:         {p['prescribed_date']}")
                    print(f"    Dentist:      {p['dentist_name']}")
                    print(f"    Medication:   {p['medication']}")
                    print(f"    Dosage:       {p['dosage']}")
                    print(f"    Frequency:    {p['frequency']}")
                    print(f"    Duration:     {p['duration']}")
                    if p.get('instructions'):
                        print(f"    Instructions: {p['instructions']}")
                    print()
            else:
                print("\nNo prescriptions found for this patient.")
        except ValueError:
            print("\nInvalid Patient ID. Please enter a number.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    # ========== Payment Management ==========

    def _payment_menu(self):
        """Payment management sub-menu."""
        while True:
            print("\n" + "=" * 70)
            print("  PAYMENT MANAGEMENT".center(70))
            print("=" * 70)
            print("\n  1. Record Payment")
            print("  2. View Patient Transactions")
            print("  3. View Pending Payments")
            print("\n  0. Back")
            print("=" * 70)

            choice = input("\nSelect an option: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self._record_payment()
            elif choice == '2':
                self._view_patient_transactions()
            elif choice == '3':
                self._view_pending_payments()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

    def _record_payment(self):
        """Record a payment."""
        print("\n" + "-" * 70)
        print("  RECORD PAYMENT".center(70))
        print("-" * 70)

        try:
            patient_id_str = input("Patient ID: ").strip()
            if not patient_id_str:
                print("\nPatient ID is required.")
                input("\nPress Enter to continue...")
                return
            patient_id = int(patient_id_str)

            patient = self.patient_mgr.get_patient(patient_id=patient_id)
            if not patient:
                print("\nPatient not found.")
                input("\nPress Enter to continue...")
                return

            print(f"\nPayment for: {patient['user_name']}")

            # Show pending payments for convenience
            pending = self.treatment_mgr.get_pending_payments(patient_id=patient_id)
            if pending:
                print(f"\n  Pending treatments:")
                for t in pending:
                    t_info = TREATMENT_TYPES.get(t['treatment_type'], {})
                    t_name = t_info.get('name', t['treatment_type'])
                    print(f"    Treatment #{t['treatment_id']}: {t_name} - £{t['fee']:.2f}")

            treatment_id_str = input("\n  Treatment ID (optional): ").strip()
            treatment_id = int(treatment_id_str) if treatment_id_str else None

            amount_str = input("  Amount: $").strip()
            if not amount_str:
                print("\nAmount is required.")
                input("\nPress Enter to continue...")
                return
            amount = float(amount_str)

            print("\n  Payment Methods:")
            methods = ['cash', 'card', 'insurance', 'bank_transfer']
            for i, m in enumerate(methods, 1):
                print(f"    {i}. {m.replace('_', ' ').title()}")

            method_choice = input("\n  Select payment method (number): ").strip()
            try:
                method_idx = int(method_choice) - 1
                if 0 <= method_idx < len(methods):
                    payment_method = methods[method_idx]
                else:
                    print("\nInvalid selection.")
                    input("\nPress Enter to continue...")
                    return
            except ValueError:
                print("\nInvalid input.")
                input("\nPress Enter to continue...")
                return

            processed_by = input("  Processed by (staff name, optional): ").strip() or None

            result = self.transaction_mgr.record_payment(
                user_id=patient.get('user_id', ''),
                patient_id=patient_id,
                amount=amount,
                payment_method=payment_method,
                treatment_id=treatment_id,
                processed_by=processed_by,
            )

            if result:
                print(f"\nPayment recorded successfully!")
                print(f"  Transaction ID: {result['transaction_id']}")
                print(f"  Reference:      {result['reference']}")
                print(f"  Amount:         £{result['amount']:.2f}")
            else:
                print("\nFailed to record payment.")
        except ValueError:
            print("\nInvalid input. Please enter valid numbers.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _view_patient_transactions(self):
        """View transaction history for a patient."""
        print("\n" + "-" * 70)
        print("  PATIENT TRANSACTIONS".center(70))
        print("-" * 70)

        try:
            patient_id_str = input("Patient ID: ").strip()
            if not patient_id_str:
                print("\nPatient ID is required.")
                input("\nPress Enter to continue...")
                return

            patient_id = int(patient_id_str)
            transactions = self.transaction_mgr.get_patient_transactions(patient_id)

            if transactions:
                print(f"\n  Total transactions: {len(transactions)}\n")
                print(f"  {'ID':<6} {'Reference':<20} {'Amount':<12} {'Method':<15} {'Date':<20}")
                print("  " + "-" * 68)
                for t in transactions:
                    print(f"  {t.get('transaction_id', 'N/A'):<6} "
                          f"{t.get('reference_number', 'N/A'):<20} "
                          f"£{t.get('amount', 0):<11.2f} "
                          f"{(t.get('payment_method') or 'N/A'):<15} "
                          f"{(t.get('created_at') or 'N/A'):<20}")
            else:
                print("\nNo transactions found for this patient.")
        except ValueError:
            print("\nInvalid Patient ID. Please enter a number.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    # ========== Reports ==========

    def _report_menu(self):
        """Reports sub-menu."""
        while True:
            print("\n" + "=" * 70)
            print("  REPORTS".center(70))
            print("=" * 70)
            print("\n  1. Daily Report")
            print("  2. Monthly Summary")
            print("  3. Upcoming Appointments")
            print("  4. View Working Hours")
            print("  5. View Dentist Staff")
            print("\n  0. Back")
            print("=" * 70)

            choice = input("\nSelect an option: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self._daily_report()
            elif choice == '2':
                self._monthly_summary()
            elif choice == '3':
                self._view_upcoming_appointments()
            elif choice == '4':
                self._view_working_hours()
            elif choice == '5':
                self._view_dentist_staff()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

    def _daily_report(self):
        """Display daily report."""
        print("\n" + "-" * 70)
        print("  DAILY REPORT".center(70))
        print("-" * 70)

        try:
            date = input("Date (YYYY-MM-DD, blank for today): ").strip()
            if not date:
                date = None

            report = self.report_mgr.get_daily_report(date=date)
            if report:
                print(f"\n  Date:                    {report.get('date', 'N/A')}")
                print(f"  Total Appointments:      {report.get('total_appointments', 0)}")
                print(f"  Completed Appointments:  {report.get('completed_appointments', 0)}")
                print(f"  Treatments Performed:    {report.get('treatments_performed', 0)}")
                print(f"  Revenue:                 £{report.get('revenue', 0):.2f}")
            else:
                print("\nNo report data available.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _monthly_summary(self):
        """Display monthly summary report."""
        print("\n" + "-" * 70)
        print("  MONTHLY SUMMARY".center(70))
        print("-" * 70)

        try:
            year_str = input("Year (blank for current): ").strip()
            month_str = input("Month (1-12, blank for current): ").strip()

            year = int(year_str) if year_str else None
            month = int(month_str) if month_str else None

            report = self.report_mgr.get_monthly_summary(year=year, month=month)
            if report:
                print(f"\n  Period:              {report.get('year', 'N/A')}-{report.get('month', 'N/A'):02d}")
                print(f"  Total Appointments:  {report.get('total_appointments', 0)}")
                print(f"  New Patients:        {report.get('new_patients', 0)}")
                print(f"  Total Revenue:       £{report.get('total_revenue', 0):.2f}")

                by_type = report.get('treatments_by_type', {})
                if by_type:
                    print(f"\n  Treatments by Type:")
                    print(f"    {'Type':<20} {'Count':<8} {'Revenue':<12}")
                    print("    " + "-" * 40)
                    for t_type, data in by_type.items():
                        t_info = TREATMENT_TYPES.get(t_type, {})
                        t_name = t_info.get('name', t_type)
                        print(f"    {t_name:<20} {data['count']:<8} £{data['revenue']:.2f}")
            else:
                print("\nNo report data available.")
        except ValueError:
            print("\nInvalid input. Please enter valid numbers.")
        except Exception as e:
            print(f"\nError: {e}")

        input("\nPress Enter to continue...")

    def _view_working_hours(self):
        """Display clinic working hours."""
        print("\n" + "-" * 70)
        print("  CLINIC WORKING HOURS".center(70))
        print("-" * 70)

        print(f"\n  {'Day':<15} {'Open':<10} {'Close':<10}")
        print("  " + "-" * 35)
        for day, (open_time, close_time) in WORKING_HOURS.items():
            print(f"  {day:<15} {open_time:<10} {close_time:<10}")
        print(f"\n  {'Sunday':<15} {'Closed':<10}")

        input("\nPress Enter to continue...")

    def _view_dentist_staff(self):
        """Display dentist staff list."""
        print("\n" + "-" * 70)
        print("  DENTIST STAFF".center(70))
        print("-" * 70)

        print(f"\n  {'ID':<10} {'Name':<25} {'Specialization':<25}")
        print("  " + "-" * 60)
        for d in DENTIST_STAFF:
            print(f"  {d['id']:<10} {d['name']:<25} {d['specialization']:<25}")

        input("\nPress Enter to continue...")


def main():
    """Entry point for the Dentist CLI."""
    cli = DentistCLI()
    cli.run()


if __name__ == '__main__':
    main()
