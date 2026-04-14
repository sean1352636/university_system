"""
Nail Bar CLI for University Management System

Provides comprehensive nail bar/salon services including treatments, appointments,
technicians management, and reporting with finance and email integration.
"""

import logging
from datetime import datetime, timedelta, date, time
from typing import Optional, List, Dict, Tuple
import json
import random
import string

# Import centralized database and authentication
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.shared_context import get_auth

# Import nailbar core services
try:
    from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import (
        init_nailbar_db, NAIL_TREATMENTS
    )
    NAILBAR_CORE_AVAILABLE = True
except ImportError:
    NAILBAR_CORE_AVAILABLE = False
    NAIL_TREATMENTS = {
        'manicure': {'name': 'Classic Manicure', 'price': 20.00, 'duration': 45, 'category': 'manicure'},
        'gel_manicure': {'name': 'Gel Manicure', 'price': 30.00, 'duration': 60, 'category': 'manicure'},
        'acrylic_manicure': {'name': 'Acrylic Manicure', 'price': 40.00, 'duration': 75, 'category': 'manicure'},
        'deluxe_manicure': {'name': 'Deluxe Manicure', 'price': 50.00, 'duration': 90, 'category': 'manicure'},
        'pedicure': {'name': 'Classic Pedicure', 'price': 25.00, 'duration': 60, 'category': 'pedicure'},
        'spa_pedicure': {'name': 'Spa Pedicure', 'price': 40.00, 'duration': 75, 'category': 'pedicure'},
        'gel_pedicure': {'name': 'Gel Pedicure', 'price': 35.00, 'duration': 70, 'category': 'pedicure'},
        'nail_art': {'name': 'Nail Art', 'price': 15.00, 'duration': 30, 'category': 'art'},
        'nail_extensions': {'name': 'Nail Extensions', 'price': 45.00, 'duration': 90, 'category': 'extensions'},
        'paraffin_treatment': {'name': 'Paraffin Hand Treatment', 'price': 20.00, 'duration': 30, 'category': 'treatment'},
        'foot_massage': {'name': 'Foot Massage', 'price': 25.00, 'duration': 30, 'category': 'treatment'},
    }

    def init_nailbar_db():
        """Fallback database initialization"""
        try:
            with transaction() as conn:
                # Treatments table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS nailbar_treatments (
                        treatment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        treatment_name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        price REAL NOT NULL,
                        duration_minutes INTEGER NOT NULL,
                        description TEXT,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Technicians table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS nailbar_technicians (
                        technician_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        technician_name TEXT NOT NULL,
                        specialization TEXT,
                        working_hours TEXT,
                        max_capacity INTEGER DEFAULT 8,
                        availability TEXT,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Appointments table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS nailbar_appointments (
                        appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        booking_ref TEXT UNIQUE NOT NULL,
                        user_id TEXT NOT NULL,
                        user_name TEXT,
                        user_email TEXT,
                        treatment_ids TEXT,
                        treatment_names TEXT,
                        technician_id INTEGER,
                        technician_name TEXT,
                        appointment_date DATE NOT NULL,
                        appointment_time TEXT NOT NULL,
                        total_duration INTEGER,
                        total_price REAL NOT NULL,
                        status TEXT DEFAULT 'scheduled',
                        notes TEXT,
                        completion_notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (technician_id) REFERENCES nailbar_technicians(technician_id)
                    )
                ''')

                # Payments table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS nailbar_payments (
                        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        booking_ref TEXT NOT NULL,
                        appointment_id INTEGER,
                        amount REAL NOT NULL,
                        tip_amount REAL DEFAULT 0.0,
                        total_amount REAL NOT NULL,
                        payment_method TEXT NOT NULL,
                        payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        technician_id INTEGER,
                        technician_name TEXT,
                        receipt_number TEXT UNIQUE NOT NULL,
                        status TEXT DEFAULT 'completed',
                        FOREIGN KEY (appointment_id) REFERENCES nailbar_appointments(appointment_id),
                        FOREIGN KEY (technician_id) REFERENCES nailbar_technicians(technician_id)
                    )
                ''')

                # Insert default treatments if none exist
                cursor = conn.execute('SELECT COUNT(*) FROM nailbar_treatments')
                if cursor.fetchone()[0] == 0:
                    for key, treatment in NAIL_TREATMENTS.items():
                        conn.execute('''
                            INSERT INTO nailbar_treatments
                            (treatment_name, category, price, duration_minutes, description, status)
                            VALUES (?, ?, ?, ?, ?, 'active')
                        ''', (
                            treatment['name'],
                            treatment.get('category', 'general'),
                            treatment['price'],
                            treatment['duration'],
                            f"Professional {treatment['name'].lower()} service"
                        ))

                # Insert default technicians if none exist
                cursor = conn.execute('SELECT COUNT(*) FROM nailbar_technicians')
                if cursor.fetchone()[0] == 0:
                    default_technicians = [
                        ('Sarah Johnson', 'Manicure, Gel Nails', 'Mon-Fri: 9:00-17:00', 8),
                        ('Emily Chen', 'Pedicure, Spa Treatments', 'Mon-Sat: 10:00-18:00', 10),
                        ('Maria Garcia', 'Nail Art, Extensions', 'Tue-Sat: 11:00-19:00', 6),
                        ('Sophie Williams', 'All Treatments', 'Mon-Fri: 8:00-16:00', 8),
                    ]
                    for name, spec, hours, capacity in default_technicians:
                        conn.execute('''
                            INSERT INTO nailbar_technicians
                            (technician_name, specialization, working_hours, max_capacity, status)
                            VALUES (?, ?, ?, ?, 'active')
                        ''', (name, spec, hours, capacity))

            return True
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
            return False

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Import finance integration
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        record_payment_to_finance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

# Import activity logger
try:
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    def log_activity(action, entity, **kwargs):
        pass

logger = logging.getLogger(__name__)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

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


def is_staff():
    """Check if current user is staff/admin"""
    try:
        user = get_current_user()
        if user:
            role = user.get('role', '').lower()
            return role in ['admin', 'staff', 'instructor']
    except Exception as e:
        logger.error(f"Error checking staff status: {e}")
    return False


def generate_booking_ref():
    """Generate unique booking reference"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_suffix = ''.join(random.choices(string.digits, k=4))
    return f"NAIL-{timestamp}-{random_suffix}"


def generate_receipt_number():
    """Generate unique receipt number"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"REC-{timestamp}-{random_suffix}"


def format_currency(amount: float) -> str:
    """Format amount as currency"""
    try:
        return f"£{float(amount):.2f}"
    except (ValueError, TypeError):
        return "£0.00"


def format_date(date_str: str) -> str:
    """Format date string for display"""
    try:
        if isinstance(date_str, str):
            dt = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            dt = date_str
        return dt.strftime('%d %B %Y')
    except Exception:
        return str(date_str)


# ============================================================================
# TREATMENT MANAGEMENT
# ============================================================================

def view_treatments():
    """View available nail treatments"""
    try:
        print_subheader("NAIL TREATMENTS")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT treatment_id, treatment_name, category, price,
                       duration_minutes, description, status
                FROM nailbar_treatments
                WHERE status = 'active'
                ORDER BY category, treatment_name
            ''')
            treatments = cursor.fetchall()

            if not treatments:
                print("\n❌ No treatments available")
            else:
                current_category = None
                for treatment in treatments:
                    try:
                        treat_id, name, category, price, duration, desc, status = treatment

                        # Print category header if changed
                        if category != current_category:
                            current_category = category
                            print(f"\n{'━' * 70}")
                            print(f"  {category.upper()}")
                            print(f"{'━' * 70}")

                        print(f"\nID {treat_id}: {name}")
                        print(f"  Price: {format_currency(price)} | Duration: {duration} minutes")
                        if desc:
                            print(f"  {desc}")
                    except Exception as e:
                        logger.error(f"Error displaying treatment: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing treatments: {e}")
        print(f"❌ Error viewing treatments: {e}")

    input("\nPress Enter to continue...")


def view_treatments_by_category():
    """Browse treatments by category"""
    try:
        print_subheader("BROWSE TREATMENTS BY CATEGORY")

        with get_connection() as conn:
            # Get categories
            cursor = conn.execute('''
                SELECT DISTINCT category
                FROM nailbar_treatments
                WHERE status = 'active'
                ORDER BY category
            ''')
            categories = cursor.fetchall()

            if not categories:
                print("\n❌ No categories available")
                input("\nPress Enter to continue...")
                return

            print("\nAvailable Categories:")
            for idx, (category,) in enumerate(categories, 1):
                # Count treatments in category
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM nailbar_treatments
                    WHERE category = ? AND status = 'active'
                ''', (category,))
                count = cursor.fetchone()[0]
                print(f"{idx}. {category.title()} ({count} treatments)")

            print("0. Back to menu")

            choice = input("\nSelect category: ").strip()

            try:
                choice_idx = int(choice)
                if choice_idx == 0:
                    return
                if 1 <= choice_idx <= len(categories):
                    selected_category = categories[choice_idx - 1][0]

                    # Show treatments in category
                    cursor = conn.execute('''
                        SELECT treatment_id, treatment_name, price,
                               duration_minutes, description
                        FROM nailbar_treatments
                        WHERE category = ? AND status = 'active'
                        ORDER BY treatment_name
                    ''', (selected_category,))
                    treatments = cursor.fetchall()

                    print(f"\n{'━' * 70}")
                    print(f"  {selected_category.upper()} TREATMENTS")
                    print(f"{'━' * 70}")

                    for treat_id, name, price, duration, desc in treatments:
                        print(f"\nID {treat_id}: {name}")
                        print(f"  Price: {format_currency(price)} | Duration: {duration} minutes")
                        if desc:
                            print(f"  {desc}")
                else:
                    print("❌ Invalid choice")
            except ValueError:
                print("❌ Invalid input")

    except Exception as e:
        logger.error(f"Error browsing treatments: {e}")
        print(f"❌ Error browsing treatments: {e}")

    input("\nPress Enter to continue...")


def add_treatment():
    """Add a new treatment (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("ADD NEW TREATMENT")

        name = input("\nTreatment name: ").strip()
        if not name:
            print("❌ Treatment name is required")
            input("\nPress Enter to continue...")
            return

        # Show available categories
        print("\nCategories:")
        categories = ['manicure', 'pedicure', 'art', 'extensions', 'treatment', 'other']
        for idx, cat in enumerate(categories, 1):
            print(f"{idx}. {cat.title()}")

        cat_choice = input("\nSelect category (or enter custom): ").strip()
        try:
            cat_idx = int(cat_choice)
            if 1 <= cat_idx <= len(categories):
                category = categories[cat_idx - 1]
            else:
                print("❌ Invalid category")
                input("\nPress Enter to continue...")
                return
        except ValueError:
            category = cat_choice.lower()

        price_str = input("Price (GBP): ").strip()
        try:
            price = float(price_str)
            if price <= 0:
                print("❌ Price must be positive")
                input("\nPress Enter to continue...")
                return
        except ValueError:
            print("❌ Invalid price")
            input("\nPress Enter to continue...")
            return

        duration_str = input("Duration (minutes): ").strip()
        try:
            duration = int(duration_str)
            if duration <= 0:
                print("❌ Duration must be positive")
                input("\nPress Enter to continue...")
                return
        except ValueError:
            print("❌ Invalid duration")
            input("\nPress Enter to continue...")
            return

        description = input("Description (optional): ").strip()

        # Confirmation
        print(f"\n{'━' * 70}")
        print(f"Treatment: {name}")
        print(f"Category: {category}")
        print(f"Price: {format_currency(price)}")
        print(f"Duration: {duration} minutes")
        if description:
            print(f"Description: {description}")
        print(f"{'━' * 70}")

        confirm = input("\nAdd this treatment? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Cancelled")
            input("\nPress Enter to continue...")
            return

        with transaction() as conn:
            conn.execute('''
                INSERT INTO nailbar_treatments
                (treatment_name, category, price, duration_minutes, description, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?)
            ''', (name, category, price, duration, description or None, datetime.now().isoformat()))

        print("\n✅ Treatment added successfully!")
        log_activity('create', 'nailbar_treatment', treatment_name=name, price=price)
        logger.info(f"Treatment added: {name}")

    except Exception as e:
        logger.error(f"Error adding treatment: {e}")
        print(f"❌ Error adding treatment: {e}")

    input("\nPress Enter to continue...")


def update_treatment():
    """Update an existing treatment (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("UPDATE TREATMENT")

        # Show all treatments
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT treatment_id, treatment_name, category, price, duration_minutes
                FROM nailbar_treatments
                WHERE status = 'active'
                ORDER BY treatment_name
            ''')
            treatments = cursor.fetchall()

            if not treatments:
                print("\n❌ No treatments available")
                input("\nPress Enter to continue...")
                return

            print("\nAvailable Treatments:")
            for treat_id, name, cat, price, duration in treatments:
                print(f"ID {treat_id}: {name} ({cat}) - {format_currency(price)}, {duration} min")

        treatment_id = input("\nEnter treatment ID to update (0 to cancel): ").strip()
        if treatment_id == "0":
            return

        if not treatment_id.isdigit():
            print("❌ Invalid treatment ID")
            input("\nPress Enter to continue...")
            return

        # Get current treatment details
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT treatment_name, category, price, duration_minutes, description
                FROM nailbar_treatments
                WHERE treatment_id = ? AND status = 'active'
            ''', (treatment_id,))
            current = cursor.fetchone()

            if not current:
                print("❌ Treatment not found")
                input("\nPress Enter to continue...")
                return

            curr_name, curr_cat, curr_price, curr_duration, curr_desc = current

        print(f"\nCurrent details:")
        print(f"Name: {curr_name}")
        print(f"Category: {curr_cat}")
        print(f"Price: {format_currency(curr_price)}")
        print(f"Duration: {curr_duration} minutes")
        print(f"Description: {curr_desc or 'None'}")

        print("\nEnter new values (press Enter to keep current):")

        new_name = input(f"Name [{curr_name}]: ").strip() or curr_name
        new_cat = input(f"Category [{curr_cat}]: ").strip() or curr_cat

        price_input = input(f"Price [{curr_price}]: ").strip()
        try:
            new_price = float(price_input) if price_input else curr_price
        except ValueError:
            print("❌ Invalid price, keeping current")
            new_price = curr_price

        duration_input = input(f"Duration [{curr_duration}]: ").strip()
        try:
            new_duration = int(duration_input) if duration_input else curr_duration
        except ValueError:
            print("❌ Invalid duration, keeping current")
            new_duration = curr_duration

        new_desc = input(f"Description [{curr_desc or 'None'}]: ").strip()
        if not new_desc:
            new_desc = curr_desc

        # Confirmation
        confirm = input("\nSave changes? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Cancelled")
            input("\nPress Enter to continue...")
            return

        with transaction() as conn:
            conn.execute('''
                UPDATE nailbar_treatments
                SET treatment_name = ?, category = ?, price = ?,
                    duration_minutes = ?, description = ?, updated_at = ?
                WHERE treatment_id = ?
            ''', (new_name, new_cat, new_price, new_duration, new_desc,
                  datetime.now().isoformat(), treatment_id))

        print("\n✅ Treatment updated successfully!")
        log_activity('update', 'nailbar_treatment', treatment_id=treatment_id,
                    changes={'name': new_name, 'price': new_price})
        logger.info(f"Treatment updated: ID {treatment_id}")

    except Exception as e:
        logger.error(f"Error updating treatment: {e}")
        print(f"❌ Error updating treatment: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# TECHNICIAN MANAGEMENT
# ============================================================================

def view_technicians():
    """View available nail technicians"""
    try:
        print_subheader("NAIL TECHNICIANS")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT technician_id, technician_name, specialization,
                       working_hours, max_capacity, status
                FROM nailbar_technicians
                WHERE status = 'active'
                ORDER BY technician_name
            ''')
            technicians = cursor.fetchall()

            if not technicians:
                print("\n❌ No technicians available")
            else:
                for tech in technicians:
                    try:
                        tech_id, name, spec, hours, capacity, status = tech
                        print(f"\n{'━' * 70}")
                        print(f"ID {tech_id}: {name}")
                        if spec:
                            print(f"  Specialization: {spec}")
                        if hours:
                            print(f"  Working Hours: {hours}")
                        print(f"  Daily Capacity: {capacity} appointments")

                        # Get today's appointments count
                        today = date.today()
                        cursor = conn.execute('''
                            SELECT COUNT(*) FROM nailbar_appointments
                            WHERE technician_id = ? AND appointment_date = ?
                            AND status IN ('scheduled', 'in_progress')
                        ''', (tech_id, str(today)))
                        today_count = cursor.fetchone()[0]

                        availability = capacity - today_count
                        print(f"  Today's Availability: {availability}/{capacity} slots")

                    except Exception as e:
                        logger.error(f"Error displaying technician: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing technicians: {e}")
        print(f"❌ Error viewing technicians: {e}")

    input("\nPress Enter to continue...")


def technician_performance():
    """View technician performance metrics (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("TECHNICIAN PERFORMANCE METRICS")

        # Date range selection
        print("\nSelect time period:")
        print("1. Today")
        print("2. This Week")
        print("3. This Month")
        print("4. Custom Range")

        period = input("\nChoice: ").strip()

        today = date.today()
        if period == "1":
            start_date = today
            end_date = today
        elif period == "2":
            start_date = today - timedelta(days=today.weekday())
            end_date = today
        elif period == "3":
            start_date = today.replace(day=1)
            end_date = today
        elif period == "4":
            start_str = input("Start date (YYYY-MM-DD): ").strip()
            end_str = input("End date (YYYY-MM-DD): ").strip()
            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return
        else:
            print("❌ Invalid choice")
            input("\nPress Enter to continue...")
            return

        print(f"\nPeriod: {format_date(str(start_date))} to {format_date(str(end_date))}")
        print("━" * 70)

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT technician_id, technician_name
                FROM nailbar_technicians
                WHERE status = 'active'
                ORDER BY technician_name
            ''')
            technicians = cursor.fetchall()

            if not technicians:
                print("\n❌ No technicians found")
                input("\nPress Enter to continue...")
                return

            for tech_id, tech_name in technicians:
                try:
                    # Get appointments count
                    cursor = conn.execute('''
                        SELECT COUNT(*) FROM nailbar_appointments
                        WHERE technician_id = ?
                        AND appointment_date BETWEEN ? AND ?
                        AND status = 'completed'
                    ''', (tech_id, str(start_date), str(end_date)))
                    appt_count = cursor.fetchone()[0]

                    # Get revenue
                    cursor = conn.execute('''
                        SELECT COALESCE(SUM(total_amount), 0)
                        FROM nailbar_payments
                        WHERE technician_id = ?
                        AND DATE(payment_date) BETWEEN ? AND ?
                        AND status = 'completed'
                    ''', (tech_id, str(start_date), str(end_date)))
                    revenue = cursor.fetchone()[0]

                    # Get tips
                    cursor = conn.execute('''
                        SELECT COALESCE(SUM(tip_amount), 0)
                        FROM nailbar_payments
                        WHERE technician_id = ?
                        AND DATE(payment_date) BETWEEN ? AND ?
                        AND status = 'completed'
                    ''', (tech_id, str(start_date), str(end_date)))
                    tips = cursor.fetchone()[0]

                    print(f"\n{tech_name} (ID: {tech_id})")
                    print(f"  Completed Appointments: {appt_count}")
                    print(f"  Revenue Generated: {format_currency(revenue)}")
                    print(f"  Tips Received: {format_currency(tips)}")
                    if appt_count > 0:
                        avg_revenue = revenue / appt_count
                        print(f"  Average per Appointment: {format_currency(avg_revenue)}")

                except Exception as e:
                    logger.error(f"Error calculating metrics for technician {tech_id}: {e}")
                    continue

    except Exception as e:
        logger.error(f"Error viewing technician performance: {e}")
        print(f"❌ Error viewing technician performance: {e}")

    input("\nPress Enter to continue...")


def manage_technician_schedule():
    """Manage technician schedules (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("MANAGE TECHNICIAN SCHEDULES")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT technician_id, technician_name, working_hours, max_capacity
                FROM nailbar_technicians
                WHERE status = 'active'
                ORDER BY technician_name
            ''')
            technicians = cursor.fetchall()

            if not technicians:
                print("\n❌ No technicians found")
                input("\nPress Enter to continue...")
                return

            print("\nTechnicians:")
            for tech_id, name, hours, capacity in technicians:
                print(f"ID {tech_id}: {name} - {hours} (Capacity: {capacity})")

        tech_id = input("\nEnter technician ID (0 to cancel): ").strip()
        if tech_id == "0":
            return

        if not tech_id.isdigit():
            print("❌ Invalid technician ID")
            input("\nPress Enter to continue...")
            return

        # Get current details
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT technician_name, working_hours, max_capacity
                FROM nailbar_technicians
                WHERE technician_id = ? AND status = 'active'
            ''', (tech_id,))
            current = cursor.fetchone()

            if not current:
                print("❌ Technician not found")
                input("\nPress Enter to continue...")
                return

            curr_name, curr_hours, curr_capacity = current

        print(f"\nCurrent schedule for {curr_name}:")
        print(f"Working Hours: {curr_hours}")
        print(f"Daily Capacity: {curr_capacity} appointments")

        print("\nEnter new values (press Enter to keep current):")

        new_hours = input(f"Working Hours [{curr_hours}]: ").strip() or curr_hours

        capacity_input = input(f"Daily Capacity [{curr_capacity}]: ").strip()
        try:
            new_capacity = int(capacity_input) if capacity_input else curr_capacity
        except ValueError:
            print("❌ Invalid capacity, keeping current")
            new_capacity = curr_capacity

        # Confirmation
        confirm = input("\nSave changes? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Cancelled")
            input("\nPress Enter to continue...")
            return

        with transaction() as conn:
            conn.execute('''
                UPDATE nailbar_technicians
                SET working_hours = ?, max_capacity = ?, updated_at = ?
                WHERE technician_id = ?
            ''', (new_hours, new_capacity, datetime.now().isoformat(), tech_id))

        print("\n✅ Schedule updated successfully!")
        log_activity('update', 'nailbar_technician', technician_id=tech_id,
                    changes={'working_hours': new_hours, 'capacity': new_capacity})
        logger.info(f"Technician schedule updated: ID {tech_id}")

    except Exception as e:
        logger.error(f"Error managing technician schedule: {e}")
        print(f"❌ Error managing technician schedule: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# APPOINTMENT BOOKING
# ============================================================================

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
                print(f"\n📊 Current Selection:")
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

        print(f"\n✅ Appointment booked successfully!")
        print(f"📄 Booking Reference: {booking_ref}")
        print(f"\nPlease save this reference for your records.")

        log_activity('create', 'nailbar_appointment', booking_ref=booking_ref,
                    user_id=user.get('username'), total_price=total_price)
        logger.info(f"User {user.get('username')} booked nail bar appointment {booking_ref}")

        # Send confirmation email if available
        if EMAIL_AVAILABLE and user.get('email'):
            try:
                send_email(
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

            print(f"\nAppointment Details:")
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

            print(f"\n✅ Appointment cancelled successfully")
            log_activity('update', 'nailbar_appointment', booking_ref=booking_ref,
                        action='cancelled')
            logger.info(f"User {user.get('username')} cancelled appointment {booking_ref}")

    except Exception as e:
        logger.error(f"Error cancelling appointment: {e}")
        print(f"❌ Error cancelling appointment: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# PAYMENT PROCESSING
# ============================================================================

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
        tip_str = input(f"Tip amount (press Enter for 0): ").strip()
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

        # Record to finance system if available
        if FINANCE_AVAILABLE:
            try:
                record_payment_to_finance(
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
        print(f"\nServices:")
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

        log_activity('create', 'nailbar_payment', receipt_number=receipt_number,
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
                print(f"\nSummary:")
                print(f"Total Payments: {len(payments)}")
                print(f"Total Revenue: {format_currency(total_revenue)}")
                print(f"Total Tips: {format_currency(total_tips)}")

    except Exception as e:
        logger.error(f"Error viewing payment history: {e}")
        print(f"❌ Error viewing payment history: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# REPORTS & ANALYTICS
# ============================================================================

def daily_schedule_report():
    """View daily appointment schedule"""
    try:
        print_subheader("DAILY APPOINTMENT SCHEDULE")

        # Get date
        date_str = input("\nEnter date (YYYY-MM-DD, or press Enter for today): ").strip()
        if not date_str:
            report_date = date.today()
        else:
            try:
                report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return

        print(f"\nSchedule for: {format_date(str(report_date))}")
        print("=" * 70)

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT appointment_time, booking_ref, user_name, treatment_names,
                       technician_name, total_duration, total_price, status
                FROM nailbar_appointments
                WHERE appointment_date = ?
                ORDER BY appointment_time
            ''', (str(report_date),))
            appointments = cursor.fetchall()

            if not appointments:
                print("\n❌ No appointments scheduled")
            else:
                for appt_time, ref, customer, treatments, tech, duration, price, status in appointments:
                    status_emoji = {
                        'scheduled': '📅',
                        'confirmed': '✅',
                        'in_progress': '⏳',
                        'completed': '✔️',
                        'cancelled': '❌'
                    }.get(status.lower(), '📋')

                    print(f"\n{appt_time} {status_emoji} [{status.upper()}]")
                    print(f"  Ref: {ref}")
                    print(f"  Customer: {customer}")
                    print(f"  Treatments: {treatments}")
                    print(f"  Technician: {tech}")
                    print(f"  Duration: {duration} min | Price: {format_currency(price)}")

                # Summary
                cursor = conn.execute('''
                    SELECT COUNT(*),
                           SUM(CASE WHEN status = 'completed' THEN total_price ELSE 0 END)
                    FROM nailbar_appointments
                    WHERE appointment_date = ?
                ''', (str(report_date),))
                total_appts, revenue = cursor.fetchone()

                print(f"\n{'━' * 70}")
                print(f"Total Appointments: {total_appts}")
                print(f"Revenue (Completed): {format_currency(revenue or 0)}")

    except Exception as e:
        logger.error(f"Error generating daily schedule: {e}")
        print(f"❌ Error generating daily schedule: {e}")

    input("\nPress Enter to continue...")


def revenue_report():
    """Generate revenue report (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("REVENUE REPORT")

        # Select period
        print("\nSelect period:")
        print("1. Today")
        print("2. This Week")
        print("3. This Month")
        print("4. Custom Range")

        choice = input("\nChoice: ").strip()

        today = date.today()
        if choice == "1":
            start_date = today
            end_date = today
            period_name = "Today"
        elif choice == "2":
            start_date = today - timedelta(days=today.weekday())
            end_date = today
            period_name = "This Week"
        elif choice == "3":
            start_date = today.replace(day=1)
            end_date = today
            period_name = "This Month"
        elif choice == "4":
            start_str = input("Start date (YYYY-MM-DD): ").strip()
            end_str = input("End date (YYYY-MM-DD): ").strip()
            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
                period_name = f"{format_date(str(start_date))} to {format_date(str(end_date))}"
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return
        else:
            print("❌ Invalid choice")
            input("\nPress Enter to continue...")
            return

        print(f"\n{'=' * 70}")
        print(f"  REVENUE REPORT - {period_name}")
        print(f"{'=' * 70}")

        with get_connection() as conn:
            # Total revenue
            cursor = conn.execute('''
                SELECT COALESCE(SUM(amount), 0), COALESCE(SUM(tip_amount), 0),
                       COALESCE(SUM(total_amount), 0), COUNT(*)
                FROM nailbar_payments
                WHERE DATE(payment_date) BETWEEN ? AND ?
                AND status = 'completed'
            ''', (str(start_date), str(end_date)))
            service_revenue, tips, total_revenue, payment_count = cursor.fetchone()

            # Appointments
            cursor = conn.execute('''
                SELECT COUNT(*) FROM nailbar_appointments
                WHERE appointment_date BETWEEN ? AND ?
                AND status = 'completed'
            ''', (str(start_date), str(end_date)))
            completed_appts = cursor.fetchone()[0]

            # By payment method
            cursor = conn.execute('''
                SELECT payment_method, COUNT(*), COALESCE(SUM(total_amount), 0)
                FROM nailbar_payments
                WHERE DATE(payment_date) BETWEEN ? AND ?
                AND status = 'completed'
                GROUP BY payment_method
                ORDER BY payment_method
            ''', (str(start_date), str(end_date)))
            payment_methods = cursor.fetchall()

            print(f"\n📊 OVERALL METRICS:")
            print(f"  Completed Appointments: {completed_appts}")
            print(f"  Total Payments: {payment_count}")
            print(f"  Service Revenue: {format_currency(service_revenue)}")
            print(f"  Tips: {format_currency(tips)}")
            print(f"  TOTAL REVENUE: {format_currency(total_revenue)}")

            if completed_appts > 0:
                avg_revenue = total_revenue / completed_appts
                print(f"  Average per Appointment: {format_currency(avg_revenue)}")

            if payment_methods:
                print(f"\n💳 BY PAYMENT METHOD:")
                for method, count, amount in payment_methods:
                    print(f"  {method.upper()}: {count} payments, {format_currency(amount)}")

            # Top treatments
            cursor = conn.execute('''
                SELECT treatment_names, COUNT(*) as count
                FROM nailbar_appointments
                WHERE appointment_date BETWEEN ? AND ?
                AND status = 'completed'
                GROUP BY treatment_names
                ORDER BY count DESC
                LIMIT 5
            ''', (str(start_date), str(end_date)))
            top_treatments = cursor.fetchall()

            if top_treatments:
                print(f"\n🌟 TOP TREATMENTS:")
                for idx, (treatment, count) in enumerate(top_treatments, 1):
                    print(f"  {idx}. {treatment} ({count} appointments)")

    except Exception as e:
        logger.error(f"Error generating revenue report: {e}")
        print(f"❌ Error generating revenue report: {e}")

    input("\nPress Enter to continue...")


def popular_treatments_analysis():
    """Analyze popular treatments (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("POPULAR TREATMENTS ANALYSIS")

        # Time period
        print("\nSelect period:")
        print("1. Last 7 days")
        print("2. Last 30 days")
        print("3. Last 90 days")
        print("4. All time")

        choice = input("\nChoice: ").strip()

        today = date.today()
        if choice == "1":
            start_date = today - timedelta(days=7)
            period_name = "Last 7 Days"
        elif choice == "2":
            start_date = today - timedelta(days=30)
            period_name = "Last 30 Days"
        elif choice == "3":
            start_date = today - timedelta(days=90)
            period_name = "Last 90 Days"
        else:
            start_date = date(2000, 1, 1)
            period_name = "All Time"

        print(f"\n{'=' * 70}")
        print(f"  POPULAR TREATMENTS - {period_name}")
        print(f"{'=' * 70}")

        with get_connection() as conn:
            # This is a simplified analysis - in production you'd parse treatment_ids
            cursor = conn.execute('''
                SELECT treatment_names, COUNT(*) as booking_count,
                       COALESCE(SUM(total_price), 0) as revenue
                FROM nailbar_appointments
                WHERE appointment_date >= ?
                AND status = 'completed'
                GROUP BY treatment_names
                ORDER BY booking_count DESC
                LIMIT 15
            ''', (str(start_date),))
            treatments = cursor.fetchall()

            if not treatments:
                print("\n❌ No data available")
            else:
                total_bookings = sum(count for _, count, _ in treatments)
                total_revenue = sum(revenue for _, _, revenue in treatments)

                print(f"\n📊 TREATMENT POPULARITY:")
                print(f"{'━' * 70}")

                for idx, (treatment, count, revenue) in enumerate(treatments, 1):
                    percentage = (count / total_bookings * 100) if total_bookings > 0 else 0
                    avg_price = revenue / count if count > 0 else 0

                    print(f"\n{idx}. {treatment}")
                    print(f"   Bookings: {count} ({percentage:.1f}%)")
                    print(f"   Revenue: {format_currency(revenue)}")
                    print(f"   Avg Price: {format_currency(avg_price)}")

                print(f"\n{'━' * 70}")
                print(f"Total Bookings Analyzed: {total_bookings}")
                print(f"Total Revenue: {format_currency(total_revenue)}")

    except Exception as e:
        logger.error(f"Error analyzing treatments: {e}")
        print(f"❌ Error analyzing treatments: {e}")

    input("\nPress Enter to continue...")


def customer_retention_stats():
    """View customer retention statistics (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("CUSTOMER RETENTION STATISTICS")

        with get_connection() as conn:
            # Total unique customers
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT user_id) FROM nailbar_appointments
                WHERE status = 'completed'
            ''')
            total_customers = cursor.fetchone()[0]

            # Repeat customers (2+ appointments)
            cursor = conn.execute('''
                SELECT COUNT(*) FROM (
                    SELECT user_id FROM nailbar_appointments
                    WHERE status = 'completed'
                    GROUP BY user_id
                    HAVING COUNT(*) >= 2
                )
            ''')
            repeat_customers = cursor.fetchone()[0]

            # Loyal customers (5+ appointments)
            cursor = conn.execute('''
                SELECT COUNT(*) FROM (
                    SELECT user_id FROM nailbar_appointments
                    WHERE status = 'completed'
                    GROUP BY user_id
                    HAVING COUNT(*) >= 5
                )
            ''')
            loyal_customers = cursor.fetchone()[0]

            # Top customers
            cursor = conn.execute('''
                SELECT user_name, user_id, COUNT(*) as visit_count,
                       COALESCE(SUM(total_price), 0) as total_spent
                FROM nailbar_appointments
                WHERE status = 'completed'
                GROUP BY user_id, user_name
                ORDER BY visit_count DESC
                LIMIT 10
            ''')
            top_customers = cursor.fetchall()

            print(f"\n{'=' * 70}")
            print(f"📊 CUSTOMER BASE:")
            print(f"{'=' * 70}")
            print(f"\nTotal Customers: {total_customers}")
            print(f"Repeat Customers (2+ visits): {repeat_customers}")
            print(f"Loyal Customers (5+ visits): {loyal_customers}")

            if total_customers > 0:
                repeat_rate = (repeat_customers / total_customers * 100)
                loyal_rate = (loyal_customers / total_customers * 100)
                print(f"\nRepeat Customer Rate: {repeat_rate:.1f}%")
                print(f"Loyalty Rate: {loyal_rate:.1f}%")

            if top_customers:
                print(f"\n🌟 TOP CUSTOMERS:")
                print(f"{'━' * 70}")
                for idx, (name, user_id, visits, spent) in enumerate(top_customers, 1):
                    avg_spent = spent / visits if visits > 0 else 0
                    print(f"\n{idx}. {name} ({user_id})")
                    print(f"   Visits: {visits}")
                    print(f"   Total Spent: {format_currency(spent)}")
                    print(f"   Avg per Visit: {format_currency(avg_spent)}")

            # Recent activity (last 30 days)
            thirty_days_ago = date.today() - timedelta(days=30)
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT user_id) FROM nailbar_appointments
                WHERE appointment_date >= ? AND status = 'completed'
            ''', (str(thirty_days_ago),))
            recent_customers = cursor.fetchone()[0]

            print(f"\n{'━' * 70}")
            print(f"Active Customers (Last 30 Days): {recent_customers}")

    except Exception as e:
        logger.error(f"Error generating retention stats: {e}")
        print(f"❌ Error generating retention stats: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# MENU SYSTEMS
# ============================================================================

def staff_menu():
    """Staff management menu"""
    while True:
        try:
            print_subheader("STAFF MANAGEMENT")

            print("\n📋 TREATMENTS:")
            print("1. Add Treatment")
            print("2. Update Treatment")

            print("\n👩‍💼 TECHNICIANS:")
            print("3. Technician Performance")
            print("4. Manage Schedules")

            print("\n💰 PAYMENTS:")
            print("5. Complete Appointment")
            print("6. Payment History")

            print("\n📊 REPORTS:")
            print("7. Daily Schedule")
            print("8. Revenue Report")
            print("9. Popular Treatments")
            print("10. Customer Retention")

            print("\n0. Back to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                add_treatment()
            elif choice == "2":
                update_treatment()
            elif choice == "3":
                technician_performance()
            elif choice == "4":
                manage_technician_schedule()
            elif choice == "5":
                complete_appointment()
            elif choice == "6":
                view_payment_history()
            elif choice == "7":
                daily_schedule_report()
            elif choice == "8":
                revenue_report()
            elif choice == "9":
                popular_treatments_analysis()
            elif choice == "10":
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
            logger.error(f"Error in staff menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")


def nailbar_menu():
    """Main nail bar menu"""
    try:
        # Initialize database
        init_nailbar_db()
    except Exception as e:
        logger.error(f"Failed to initialize nail bar database: {e}")
        print(f"❌ Failed to initialize nail bar system: {e}")
        input("\nPress Enter to continue...")
        return

    user = get_current_user()
    if not user:
        print("❌ You must be logged in to access the Nail Bar")
        input("\nPress Enter to continue...")
        return

    while True:
        try:
            print_header("UNIVERSITY NAIL BAR")

            if user:
                print(f"\nLogged in as: {user.get('username')} ({user.get('role')})")

            print("\n💅 TREATMENTS:")
            print("1. View All Treatments")
            print("2. Browse by Category")
            print("3. View Technicians")

            print("\n📅 APPOINTMENTS:")
            print("4. Book Appointment")
            print("5. View My Appointments")
            print("6. Cancel Appointment")

            if is_staff():
                print("\n👩‍💼 STAFF MENU:")
                print("7. Staff Management")

            print("\n0. Return to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                view_treatments()
            elif choice == "2":
                view_treatments_by_category()
            elif choice == "3":
                view_technicians()
            elif choice == "4":
                book_appointment()
            elif choice == "5":
                view_my_appointments()
            elif choice == "6":
                cancel_appointment()
            elif choice == "7" and is_staff():
                staff_menu()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in nail bar menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")


def launch_nailbar_cli(auth=None):
    """Launch nail bar CLI (called from main menu)"""
    nailbar_menu()


if __name__ == "__main__":
    nailbar_menu()
