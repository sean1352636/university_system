"""
Barber Shop CLI for University Management System

Provides comprehensive barber shop services including appointments, services,
staff management, payment processing, and reporting with finance and email integration.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import secrets

# Import centralized database and authentication
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import barber core services
try:
    from education_system.post_18.university_system.modules.domain.commerce.barber.services.barber_core import (
        init_barber_db, init_extended_barber_db,
        ServiceManager, StaffManager, AppointmentManager, TransactionManager,
        ReportManager, CustomerManager, AnalyticsManager,
        TIME_SLOTS, APPOINTMENT_STATUSES
    )
    BARBER_CORE_AVAILABLE = True
except ImportError:
    BARBER_CORE_AVAILABLE = False
    TIME_SLOTS = [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
        '12:00', '12:30', '13:00', '13:30', '14:00', '14:30',
        '15:00', '15:30', '16:00', '16:30', '17:00', '17:30'
    ]
    APPOINTMENT_STATUSES = ['scheduled', 'checked_in', 'in_progress', 'completed', 'cancelled', 'no_show']

    def init_barber_db():
        """Fallback database initialization"""
        try:
            with transaction() as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS barber_services (
                        service_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        service_name TEXT NOT NULL,
                        price REAL NOT NULL,
                        duration_minutes INTEGER NOT NULL,
                        description TEXT,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS barber_staff (
                        staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        staff_name TEXT NOT NULL,
                        specialization TEXT,
                        availability TEXT,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS barber_appointments (
                        appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        booking_ref TEXT UNIQUE NOT NULL,
                        user_id TEXT NOT NULL,
                        user_name TEXT,
                        user_email TEXT,
                        service_id INTEGER,
                        service_name TEXT,
                        staff_id INTEGER,
                        staff_name TEXT,
                        appointment_date DATE NOT NULL,
                        appointment_time TEXT NOT NULL,
                        duration_minutes INTEGER,
                        price REAL NOT NULL,
                        status TEXT DEFAULT 'scheduled',
                        payment_status TEXT DEFAULT 'pending',
                        payment_method TEXT,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (service_id) REFERENCES barber_services(service_id),
                        FOREIGN KEY (staff_id) REFERENCES barber_staff(staff_id)
                    )
                ''')

                # Barber transactions now use unified 'transactions' table with source_type='barber'
            return True
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
            return False

    def init_extended_barber_db():
        """Extended database initialization"""
        pass

# Import email service
try:
    from education_system.post_18.university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Import finance integration
try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
        record_payment_to_finance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

# Import activity logging
try:
    from education_system.post_18.university_system.core.activity_logger import log_activity
    ACTIVITY_LOG_AVAILABLE = True
except ImportError:
    ACTIVITY_LOG_AVAILABLE = False

logger = logging.getLogger(__name__)


def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_subheader(text: str):
    """Print a formatted subheader"""
    print("\n" + "-" * 70)
    print(f"  {text}")
    print("-" * 70)


def get_current_user():
    """Get the currently logged-in user"""
    try:
        auth = get_auth()
        if auth and hasattr(auth, 'current_user') and auth.current_user:
            return auth.current_user
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
    return None


def is_staff_or_admin():
    """Check if current user is staff or admin"""
    try:
        user = get_current_user()
        if user and user.get('role') in ['admin', 'staff', 'Admin', 'Staff']:
            return True
    except Exception as e:
        logger.error(f"Error checking user role: {e}")
    return False


# ============================================================================
# SERVICES MANAGEMENT
# ============================================================================

def view_services():
    """View available barber services"""
    try:
        print_subheader("AVAILABLE BARBER SERVICES")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT service_id, service_name, price, duration_minutes, description, status
                FROM barber_services
                WHERE status = 'active'
                ORDER BY service_name
            ''')
            services = cursor.fetchall()

            if not services:
                print("\n❌ No services available")
            else:
                print("\n{:<5} {:<25} {:<12} {:<15} {:<30}".format(
                    "ID", "Service", "Price (GBP)", "Duration (min)", "Description"
                ))
                print("-" * 90)

                for service in services:
                    try:
                        svc_id, name, price, duration, desc, status = service
                        desc_short = (desc[:27] + "...") if desc and len(desc) > 30 else (desc or "")
                        print("{:<5} {:<25} {:<12.2f} {:<15} {:<30}".format(
                            svc_id, name[:24], float(price), duration, desc_short
                        ))
                    except Exception as e:
                        logger.error(f"Error displaying service: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing services: {e}")
        print(f"❌ Error viewing services: {e}")

    input("\nPress Enter to continue...")


def add_service():
    """Add a new barber service (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff and administrators")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("ADD NEW SERVICE")

        name = input("\nService name: ").strip()
        if not name:
            print("❌ Service name is required")
            input("\nPress Enter to continue...")
            return

        try:
            price = float(input("Price (GBP): ").strip())
            if price <= 0:
                print("❌ Price must be greater than zero")
                input("\nPress Enter to continue...")
                return
        except ValueError:
            print("❌ Invalid price format")
            input("\nPress Enter to continue...")
            return

        try:
            duration = int(input("Duration (minutes): ").strip())
            if duration <= 0:
                print("❌ Duration must be greater than zero")
                input("\nPress Enter to continue...")
                return
        except ValueError:
            print("❌ Invalid duration format")
            input("\nPress Enter to continue...")
            return

        description = input("Description (optional): ").strip()

        confirm = input(f"\nAdd service '{name}' at GBP {price:.2f} for {duration} minutes? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Service addition cancelled")
            input("\nPress Enter to continue...")
            return

        with transaction() as conn:
            conn.execute('''
                INSERT INTO barber_services (service_name, price, duration_minutes, description, status)
                VALUES (?, ?, ?, ?, 'active')
            ''', (name, price, duration, description if description else None))

        print(f"\n✅ Service '{name}' added successfully!")

        if ACTIVITY_LOG_AVAILABLE:
            user = get_current_user()
            log_activity('create', 'barber_service', details={
                'name': name, 'price': price, 'duration': duration
            })

    except Exception as e:
        logger.error(f"Error adding service: {e}")
        print(f"❌ Error adding service: {e}")

    input("\nPress Enter to continue...")


def update_service():
    """Update an existing service (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff and administrators")
        input("\nPress Enter to continue...")
        return

    try:
        view_services()

        service_id = input("\nEnter service ID to update (0 to cancel): ").strip()
        if service_id == "0":
            return

        if not service_id.isdigit():
            print("❌ Invalid service ID")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT service_id, service_name, price, duration_minutes, description
                FROM barber_services WHERE service_id = ?
            ''', (service_id,))
            service = cursor.fetchone()

            if not service:
                print("❌ Service not found")
                input("\nPress Enter to continue...")
                return

            svc_id, name, price, duration, desc = service

            print("\nCurrent details:")
            print(f"Name: {name}")
            print(f"Price: GBP {float(price):.2f}")
            print(f"Duration: {duration} minutes")
            print(f"Description: {desc or 'N/A'}")

            print("\nEnter new values (press Enter to keep current):")

            new_name = input(f"Name [{name}]: ").strip() or name

            price_input = input(f"Price (GBP) [{price}]: ").strip()
            new_price = float(price_input) if price_input else price

            duration_input = input(f"Duration (min) [{duration}]: ").strip()
            new_duration = int(duration_input) if duration_input else duration

            new_desc = input(f"Description [{desc or 'N/A'}]: ").strip()
            if not new_desc:
                new_desc = desc

            confirm = input("\nUpdate service? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Update cancelled")
                input("\nPress Enter to continue...")
                return

            with transaction() as conn_tx:
                conn_tx.execute('''
                    UPDATE barber_services
                    SET service_name = ?, price = ?, duration_minutes = ?, description = ?
                    WHERE service_id = ?
                ''', (new_name, new_price, new_duration, new_desc, service_id))

            print("\n✅ Service updated successfully!")

            if ACTIVITY_LOG_AVAILABLE:
                log_activity('update', 'barber_service', details={
                    'service_id': service_id, 'name': new_name
                })

    except Exception as e:
        logger.error(f"Error updating service: {e}")
        print(f"❌ Error updating service: {e}")

    input("\nPress Enter to continue...")


def toggle_service_availability():
    """Enable or disable a service (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff and administrators")
        input("\nPress Enter to continue...")
        return

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT service_id, service_name, price, status
                FROM barber_services
                ORDER BY service_name
            ''')
            services = cursor.fetchall()

            if not services:
                print("\n❌ No services found")
                input("\nPress Enter to continue...")
                return

            print_subheader("ALL SERVICES")
            print("\n{:<5} {:<30} {:<12} {:<10}".format("ID", "Service", "Price (GBP)", "Status"))
            print("-" * 60)

            for svc in services:
                svc_id, name, price, status = svc
                print("{:<5} {:<30} {:<12.2f} {:<10}".format(
                    svc_id, name[:29], float(price), status.upper()
                ))

            service_id = input("\nEnter service ID to toggle (0 to cancel): ").strip()
            if service_id == "0":
                return

            if not service_id.isdigit():
                print("❌ Invalid service ID")
                input("\nPress Enter to continue...")
                return

            cursor = conn.execute('''
                SELECT service_name, status FROM barber_services WHERE service_id = ?
            ''', (service_id,))
            service = cursor.fetchone()

            if not service:
                print("❌ Service not found")
                input("\nPress Enter to continue...")
                return

            name, current_status = service
            new_status = 'inactive' if current_status == 'active' else 'active'

            confirm = input(f"\nChange '{name}' status from {current_status} to {new_status}? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Operation cancelled")
                input("\nPress Enter to continue...")
                return

            with transaction() as conn_tx:
                conn_tx.execute('''
                    UPDATE barber_services SET status = ? WHERE service_id = ?
                ''', (new_status, service_id))

            print(f"\n✅ Service status updated to {new_status}!")

            if ACTIVITY_LOG_AVAILABLE:
                log_activity('update', 'barber_service', details={
                    'service_id': service_id, 'status': new_status
                })

    except Exception as e:
        logger.error(f"Error toggling service availability: {e}")
        print(f"❌ Error toggling service availability: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# STAFF MANAGEMENT
# ============================================================================

def view_staff():
    """View all barber staff"""
    try:
        print_subheader("BARBER STAFF")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT staff_id, staff_name, specialization, availability, status
                FROM barber_staff
                WHERE status = 'active'
                ORDER BY staff_name
            ''')
            staff = cursor.fetchall()

            if not staff:
                print("\n❌ No staff available")
            else:
                print("\n{:<5} {:<25} {:<30} {:<20}".format(
                    "ID", "Name", "Specialization", "Availability"
                ))
                print("-" * 85)

                for member in staff:
                    try:
                        staff_id, name, spec, avail, status = member
                        print("{:<5} {:<25} {:<30} {:<20}".format(
                            staff_id,
                            name[:24],
                            (spec[:29] if spec else "General")[:29],
                            (avail[:19] if avail else "Mon-Sat 9AM-6PM")[:19]
                        ))
                    except Exception as e:
                        logger.error(f"Error displaying staff member: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing staff: {e}")
        print(f"❌ Error viewing staff: {e}")

    input("\nPress Enter to continue...")


def view_staff_schedules():
    """View staff schedules and availability (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff and administrators")
        input("\nPress Enter to continue...")
        return

    try:
        view_staff()

        staff_id = input("\nEnter staff ID to view schedule (0 for all, blank to cancel): ").strip()
        if not staff_id:
            return

        date_str = input("Enter date (YYYY-MM-DD) [today]: ").strip()
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
        else:
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return

        print_subheader(f"SCHEDULE FOR {date_str}")

        with get_connection() as conn:
            if staff_id == "0":
                # All staff
                cursor = conn.execute('''
                    SELECT staff_id, staff_name FROM barber_staff WHERE status = 'active'
                    ORDER BY staff_name
                ''')
                staff_list = cursor.fetchall()
            else:
                cursor = conn.execute('''
                    SELECT staff_id, staff_name FROM barber_staff WHERE staff_id = ? AND status = 'active'
                ''', (staff_id,))
                staff_list = cursor.fetchall()

            if not staff_list:
                print("\n❌ No staff found")
                input("\nPress Enter to continue...")
                return

            for staff_member in staff_list:
                s_id, s_name = staff_member
                print(f"\n{s_name} (ID: {s_id}):")
                print("-" * 50)

                # Get appointments for this staff on this date
                cursor = conn.execute('''
                    SELECT appointment_time, service_name, duration_minutes, status, user_name
                    FROM barber_appointments
                    WHERE staff_id = ? AND appointment_date = ?
                    ORDER BY appointment_time
                ''', (s_id, date_str))
                appointments = cursor.fetchall()

                if not appointments:
                    print("  No appointments scheduled")
                else:
                    for appt in appointments:
                        time, service, duration, status, customer = appt
                        print(f"  {time} - {service} ({duration}min) - {customer} [{status}]")

    except Exception as e:
        logger.error(f"Error viewing staff schedules: {e}")
        print(f"❌ Error viewing staff schedules: {e}")

    input("\nPress Enter to continue...")


def staff_performance_metrics():
    """View staff performance metrics (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff and administrators")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("STAFF PERFORMANCE METRICS")

        period = input("\nSelect period (1=Today, 2=This Week, 3=This Month, 4=Custom): ").strip()

        if period == "1":
            start_date = datetime.now().strftime('%Y-%m-%d')
            end_date = start_date
        elif period == "2":
            today = datetime.now()
            start_date = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
        elif period == "3":
            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
        elif period == "4":
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD): ").strip()
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return
        else:
            print("❌ Invalid option")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT
                    s.staff_id,
                    s.staff_name,
                    COUNT(a.appointment_id) as total_appointments,
                    SUM(CASE WHEN a.status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN a.status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                    SUM(CASE WHEN a.status = 'no_show' THEN 1 ELSE 0 END) as no_shows,
                    COALESCE(SUM(t.amount), 0) as revenue,
                    COALESCE(SUM(t.tip_amount), 0) as tips
                FROM barber_staff s
                LEFT JOIN barber_appointments a ON s.staff_id = a.staff_id
                    AND a.appointment_date BETWEEN ? AND ?
                LEFT JOIN transactions t ON a.appointment_id = t.reference_id AND t.reference_type = 'appointment' AND t.source_type = 'barber'
                WHERE s.status = 'active'
                GROUP BY s.staff_id, s.staff_name
                ORDER BY revenue DESC
            ''', (start_date, end_date))

            results = cursor.fetchall()

            print(f"\nPeriod: {start_date} to {end_date}")
            print("\n{:<20} {:<10} {:<10} {:<10} {:<10} {:<12} {:<12}".format(
                "Name", "Total", "Complete", "Cancel", "No-Show", "Revenue", "Tips"
            ))
            print("-" * 95)

            if not results:
                print("No data available for this period")
            else:
                for row in results:
                    staff_id, name, total, completed, cancelled, no_shows, revenue, tips = row
                    print("{:<20} {:<10} {:<10} {:<10} {:<10} {:<12.2f} {:<12.2f}".format(
                        name[:19], total or 0, completed or 0, cancelled or 0,
                        no_shows or 0, float(revenue or 0), float(tips or 0)
                    ))

    except Exception as e:
        logger.error(f"Error viewing staff performance: {e}")
        print(f"❌ Error viewing staff performance: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# APPOINTMENT MANAGEMENT
# ============================================================================

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
            # Upcoming appointments
            cursor = conn.execute('''
                SELECT booking_ref, service_name, staff_name, appointment_date,
                       appointment_time, price, status, created_at
                FROM barber_appointments
                WHERE user_id = ? AND appointment_date >= DATE('now')
                AND status NOT IN ('cancelled', 'completed')
                ORDER BY appointment_date ASC, appointment_time ASC
            ''', (user.get('username'),))
            upcoming = cursor.fetchall()

            # Past appointments
            cursor = conn.execute('''
                SELECT booking_ref, service_name, staff_name, appointment_date,
                       appointment_time, price, status, created_at
                FROM barber_appointments
                WHERE user_id = ? AND (appointment_date < DATE('now') OR status IN ('cancelled', 'completed'))
                ORDER BY appointment_date DESC, appointment_time DESC
                LIMIT 10
            ''', (user.get('username'),))
            past = cursor.fetchall()

            if upcoming:
                print("\n📅 UPCOMING APPOINTMENTS:")
                print("-" * 70)
                for appt in upcoming:
                    ref, service, staff, date, time, price, status, created = appt
                    print(f"\n🎫 Booking: {ref}")
                    print(f"   Service: {service}")
                    print(f"   Barber: {staff}")
                    print(f"   Date/Time: {date} at {time}")
                    print(f"   Price: GBP {float(price):.2f}")
                    print(f"   Status: {status.upper()}")
            else:
                print("\n📅 No upcoming appointments")

            if past:
                print("\n\n📜 PAST APPOINTMENTS:")
                print("-" * 70)
                for appt in past:
                    ref, service, staff, date, time, price, status, created = appt
                    status_icon = "✅" if status == "completed" else "❌"
                    print(f"\n{status_icon} Booking: {ref}")
                    print(f"   Service: {service}")
                    print(f"   Barber: {staff}")
                    print(f"   Date/Time: {date} at {time}")
                    print(f"   Price: GBP {float(price):.2f}")
                    print(f"   Status: {status.upper()}")
            else:
                print("\n\n📜 No past appointments")

            if not upcoming and not past:
                print("\nYou have no appointments")

    except Exception as e:
        logger.error(f"Error viewing appointments: {e}")
        print(f"❌ Error viewing appointments: {e}")

    input("\nPress Enter to continue...")


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


# ============================================================================
# PAYMENT PROCESSING
# ============================================================================

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


# ============================================================================
# REPORTS & ANALYTICS
# ============================================================================

def daily_schedule():
    """View daily appointment schedule (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("DAILY APPOINTMENT SCHEDULE")

        date_str = input("\nEnter date (YYYY-MM-DD) [today]: ").strip()
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
        else:
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT appointment_time, user_name, service_name, staff_name,
                       duration_minutes, status, booking_ref
                FROM barber_appointments
                WHERE appointment_date = ?
                ORDER BY appointment_time
            ''', (date_str,))
            appointments = cursor.fetchall()

            print(f"\nSchedule for {date_str}")
            print("-" * 90)

            if not appointments:
                print("\nNo appointments scheduled")
            else:
                print("\n{:<8} {:<20} {:<20} {:<15} {:<8} {:<12}".format(
                    "Time", "Customer", "Service", "Barber", "Duration", "Status"
                ))
                print("-" * 90)

                for appt in appointments:
                    time, customer, service, staff, duration, status, ref = appt
                    status_icon = {
                        'scheduled': '📅',
                        'checked_in': '✅',
                        'in_progress': '⏳',
                        'completed': '✔️',
                        'cancelled': '❌',
                        'no_show': '🚫'
                    }.get(status, '  ')

                    print("{:<8} {:<20} {:<20} {:<15} {:<8} {} {}".format(
                        time,
                        customer[:19],
                        service[:19],
                        staff[:14],
                        f"{duration}min",
                        status_icon,
                        status
                    ))

            # Summary
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'scheduled' THEN 1 ELSE 0 END) as scheduled,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                    SUM(CASE WHEN status = 'no_show' THEN 1 ELSE 0 END) as no_shows
                FROM barber_appointments
                WHERE appointment_date = ?
            ''', (date_str,))
            summary = cursor.fetchone()

            if summary and summary[0] > 0:
                total, completed, scheduled, cancelled, no_shows = summary
                print("\nSummary:")
                print(f"  Total: {total} | Completed: {completed} | Scheduled: {scheduled}")
                print(f"  Cancelled: {cancelled} | No-shows: {no_shows}")

    except Exception as e:
        logger.error(f"Error viewing daily schedule: {e}")
        print(f"❌ Error viewing daily schedule: {e}")

    input("\nPress Enter to continue...")


def revenue_report():
    """View revenue reports (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("REVENUE REPORT")

        print("\nSelect period:")
        print("  1. Today")
        print("  2. This Week")
        print("  3. This Month")
        print("  4. Custom Range")

        choice = input("\nEnter choice (1-4): ").strip()

        if choice == "1":
            start_date = datetime.now().strftime('%Y-%m-%d')
            end_date = start_date
            period_name = "Today"
        elif choice == "2":
            today = datetime.now()
            start_date = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
            period_name = "This Week"
        elif choice == "3":
            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
            period_name = "This Month"
        elif choice == "4":
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD): ").strip()
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                datetime.strptime(end_date, '%Y-%m-%d')
                period_name = f"{start_date} to {end_date}"
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return
        else:
            print("❌ Invalid choice")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            # Overall revenue
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as transactions,
                    SUM(amount) as revenue,
                    SUM(tip_amount) as tips,
                    SUM(amount + tip_amount) as total,
                    AVG(amount) as avg_transaction
                FROM transactions
                WHERE source_type = 'barber' AND DATE(created_at) BETWEEN ? AND ?
                AND status = 'completed'
            ''', (start_date, end_date))
            summary = cursor.fetchone()

            print(f"\n{'='*60}")
            print(f"REVENUE REPORT - {period_name}")
            print(f"{'='*60}")

            if summary and summary[0] > 0:
                trans_count, revenue, tips, total, avg_trans = summary
                print(f"\nTransactions:     {trans_count}")
                print(f"Service Revenue:  GBP {float(revenue or 0):.2f}")
                print(f"Tips:             GBP {float(tips or 0):.2f}")
                print(f"Total Revenue:    GBP {float(total or 0):.2f}")
                print(f"Avg Transaction:  GBP {float(avg_trans or 0):.2f}")

                # By payment method
                cursor = conn.execute('''
                    SELECT payment_method, COUNT(*), SUM(amount + tip_amount)
                    FROM transactions
                    WHERE source_type = 'barber' AND DATE(created_at) BETWEEN ? AND ?
                    AND status = 'completed'
                    GROUP BY payment_method
                ''', (start_date, end_date))
                by_method = cursor.fetchall()

                if by_method:
                    print("\nBy Payment Method:")
                    for method, count, amount in by_method:
                        print(f"  {method.replace('_', ' ').title():<20} {count:>3} transactions  GBP {float(amount):.2f}")

                # By service
                cursor = conn.execute('''
                    SELECT a.service_name, COUNT(*), SUM(t.amount)
                    FROM transactions t
                    JOIN barber_appointments a ON t.reference_id = a.appointment_id AND t.reference_type = 'appointment'
                    WHERE t.source_type = 'barber' AND DATE(t.created_at) BETWEEN ? AND ?
                    AND t.status = 'completed'
                    GROUP BY a.service_name
                    ORDER BY SUM(t.amount) DESC
                ''', (start_date, end_date))
                by_service = cursor.fetchall()

                if by_service:
                    print("\nTop Services:")
                    for i, (service, count, amount) in enumerate(by_service[:5], 1):
                        print(f"  {i}. {service:<25} {count:>3} bookings  GBP {float(amount):.2f}")

            else:
                print("\nNo transactions in this period")

    except Exception as e:
        logger.error(f"Error generating revenue report: {e}")
        print(f"❌ Error generating revenue report: {e}")

    input("\nPress Enter to continue...")


def service_popularity_report():
    """View popular services analysis (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("SERVICE POPULARITY ANALYSIS")

        # Get date range
        days = input("\nAnalyze last N days [30]: ").strip()
        try:
            days = int(days) if days else 30
        except ValueError:
            days = 30

        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT
                    service_name,
                    COUNT(*) as bookings,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                    SUM(CASE WHEN status = 'no_show' THEN 1 ELSE 0 END) as no_shows,
                    AVG(price) as avg_price,
                    SUM(CASE WHEN status = 'completed' THEN price ELSE 0 END) as revenue
                FROM barber_appointments
                WHERE appointment_date BETWEEN ? AND ?
                GROUP BY service_name
                ORDER BY bookings DESC
            ''', (start_date, end_date))
            results = cursor.fetchall()

            print(f"\nPeriod: Last {days} days ({start_date} to {end_date})")
            print("\n{:<25} {:<10} {:<10} {:<10} {:<10} {:<12}".format(
                "Service", "Bookings", "Complete", "Cancel", "No-Show", "Revenue"
            ))
            print("-" * 85)

            if not results:
                print("\nNo data available")
            else:
                for row in results:
                    service, bookings, completed, cancelled, no_shows, avg_price, revenue = row
                    print("{:<25} {:<10} {:<10} {:<10} {:<10} GBP {:.2f}".format(
                        service[:24], bookings, completed, cancelled, no_shows, float(revenue or 0)
                    ))

                # Calculate completion rate
                total_bookings = sum(row[1] for row in results)
                total_completed = sum(row[2] for row in results)
                completion_rate = (total_completed / total_bookings * 100) if total_bookings > 0 else 0

                print("\nOverall Statistics:")
                print(f"  Total Bookings: {total_bookings}")
                print(f"  Completed: {total_completed}")
                print(f"  Completion Rate: {completion_rate:.1f}%")

    except Exception as e:
        logger.error(f"Error generating service popularity report: {e}")
        print(f"❌ Error generating service popularity report: {e}")

    input("\nPress Enter to continue...")


def customer_retention_stats():
    """View customer retention statistics (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("CUSTOMER RETENTION STATISTICS")

        # Get date range
        days = input("\nAnalyze last N days [90]: ").strip()
        try:
            days = int(days) if days else 90
        except ValueError:
            days = 90

        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')

        with get_connection() as conn:
            # Total unique customers
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT user_id) as total_customers
                FROM barber_appointments
                WHERE appointment_date BETWEEN ? AND ?
            ''', (start_date, end_date))
            total_customers = cursor.fetchone()[0] or 0

            # New vs returning
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT user_id) as new_customers
                FROM barber_appointments a
                WHERE appointment_date BETWEEN ? AND ?
                AND NOT EXISTS (
                    SELECT 1 FROM barber_appointments b
                    WHERE b.user_id = a.user_id
                    AND b.appointment_date < ?
                )
            ''', (start_date, end_date, start_date))
            new_customers = cursor.fetchone()[0] or 0
            returning_customers = total_customers - new_customers

            # Visit frequency
            cursor = conn.execute('''
                SELECT
                    user_id,
                    user_name,
                    COUNT(*) as visit_count,
                    SUM(price) as total_spent
                FROM barber_appointments
                WHERE appointment_date BETWEEN ? AND ?
                AND status = 'completed'
                GROUP BY user_id, user_name
                ORDER BY visit_count DESC
                LIMIT 10
            ''', (start_date, end_date))
            top_customers = cursor.fetchall()

            print(f"\nPeriod: Last {days} days ({start_date} to {end_date})")
            print(f"\n{'='*60}")
            print("CUSTOMER SUMMARY")
            print(f"{'='*60}")
            print(f"Total Unique Customers:  {total_customers}")
            print(f"New Customers:           {new_customers}")
            print(f"Returning Customers:     {returning_customers}")

            if total_customers > 0:
                retention_rate = (returning_customers / total_customers * 100)
                print(f"Retention Rate:          {retention_rate:.1f}%")

            if top_customers:
                print(f"\n{'='*60}")
                print("TOP 10 FREQUENT CUSTOMERS")
                print(f"{'='*60}")
                print("\n{:<25} {:<10} {:<15}".format("Customer", "Visits", "Total Spent"))
                print("-" * 55)

                for customer_id, name, visits, spent in top_customers:
                    print("{:<25} {:<10} GBP {:.2f}".format(
                        name[:24], visits, float(spent or 0)
                    ))

    except Exception as e:
        logger.error(f"Error generating retention statistics: {e}")
        print(f"❌ Error generating retention statistics: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# MAIN MENU
# ============================================================================

def services_menu():
    """Services management menu"""
    while True:
        try:
            print_header("SERVICES MANAGEMENT")

            print("\n1. View All Services")
            print("2. Add New Service (Staff)")
            print("3. Update Service (Staff)")
            print("4. Enable/Disable Service (Staff)")
            print("\n0. Back to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                view_services()
            elif choice == "2":
                add_service()
            elif choice == "3":
                update_service()
            elif choice == "4":
                toggle_service_availability()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in services menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")


def staff_menu():
    """Staff management menu"""
    while True:
        try:
            print_header("STAFF MANAGEMENT")

            print("\n1. View All Staff")
            print("2. View Staff Schedules (Staff)")
            print("3. Staff Performance Metrics (Staff)")
            print("\n0. Back to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                view_staff()
            elif choice == "2":
                view_staff_schedules()
            elif choice == "3":
                staff_performance_metrics()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in staff menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")


def appointments_menu():
    """Appointments management menu"""
    while True:
        try:
            print_header("APPOINTMENTS")

            print("\n📅 CUSTOMER:")
            print("1. Book Appointment")
            print("2. View My Appointments")
            print("3. Cancel Appointment")
            print("4. Reschedule Appointment")

            if is_staff_or_admin():
                print("\n👨‍💼 STAFF:")
                print("5. Check-In Customer")
                print("6. Complete Appointment")

            print("\n0. Back to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                book_appointment()
            elif choice == "2":
                view_my_appointments()
            elif choice == "3":
                cancel_appointment()
            elif choice == "4":
                reschedule_appointment()
            elif choice == "5" and is_staff_or_admin():
                check_in_appointment()
            elif choice == "6" and is_staff_or_admin():
                complete_appointment()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in appointments menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")


def reports_menu():
    """Reports and analytics menu (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff")
        input("\nPress Enter to continue...")
        return

    while True:
        try:
            print_header("REPORTS & ANALYTICS")

            print("\n1. Daily Schedule")
            print("2. Revenue Report")
            print("3. Service Popularity Analysis")
            print("4. Customer Retention Statistics")
            print("\n0. Back to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                daily_schedule()
            elif choice == "2":
                revenue_report()
            elif choice == "3":
                service_popularity_report()
            elif choice == "4":
                customer_retention_stats()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in reports menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")


def barber_menu():
    """Main barber shop menu"""
    try:
        # Initialize database
        init_barber_db()
        if BARBER_CORE_AVAILABLE:
            init_extended_barber_db()
    except Exception as e:
        logger.error(f"Failed to initialize barber database: {e}")
        print(f"❌ Failed to initialize barber system: {e}")
        input("\nPress Enter to continue...")
        return

    user = get_current_user()
    if not user:
        print("❌ You must be logged in to access the Barber Shop")
        input("\nPress Enter to continue...")
        return

    while True:
        try:
            print_header("UNIVERSITY BARBER SHOP")

            if user:
                role_display = user.get('role', 'User').title()
                print(f"\nLogged in as: {user.get('username')} ({role_display})")

            print("\n✂️  MAIN MENU:")
            print("1. Services Management")
            print("2. Staff Information")
            print("3. Appointments")

            if is_staff_or_admin():
                print("4. Reports & Analytics (Staff)")

            print("\n0. Return to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                services_menu()
            elif choice == "2":
                staff_menu()
            elif choice == "3":
                appointments_menu()
            elif choice == "4" and is_staff_or_admin():
                reports_menu()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in barber menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")


def launch_barber_cli(auth=None):
    """Launch barber shop CLI (called from main menu)"""
    barber_menu()


if __name__ == "__main__":
    barber_menu()
