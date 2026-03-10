"""
Gym/Fitness Center CLI for University Management System

Provides comprehensive gym services including memberships, class bookings,
equipment management, and personal training with finance and email integration.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict

# Import centralized database and authentication
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.shared_context import get_auth

# Import gym core services
try:
    from education_system.university_system.modules.domain.gym.services.gym_core import (
        init_gym_db, MEMBERSHIP_TYPES, CLASS_TYPES, PT_SESSION_FEES,
        generate_membership_id, generate_booking_ref, generate_reference
    )
    GYM_CORE_AVAILABLE = True
except ImportError:
    GYM_CORE_AVAILABLE = False
    MEMBERSHIP_TYPES = {
        'basic': {'name': 'Basic', 'monthly_fee': 25.00, 'features': ['gym_access']},
        'standard': {'name': 'Standard', 'monthly_fee': 40.00, 'features': ['gym_access', 'classes']},
        'premium': {'name': 'Premium', 'monthly_fee': 60.00, 'features': ['gym_access', 'classes', 'pool', 'sauna']},
        'student': {'name': 'Student', 'monthly_fee': 15.00, 'features': ['gym_access', 'classes']},
    }
    CLASS_TYPES = ['yoga', 'pilates', 'spinning', 'hiit', 'strength', 'cardio', 'swimming', 'boxing']
    PT_SESSION_FEES = {'single': 35.00, 'package_5': 150.00, 'package_10': 280.00}

    def generate_membership_id():
        return f"GYM-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

    def generate_booking_ref():
        return f"BK-{uuid.uuid4().hex[:8].upper()}"

    def generate_reference():
        return f"REF-{uuid.uuid4().hex[:12].upper()}"

    def init_gym_db():
        """Fallback database initialization"""
        try:
            with transaction() as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS gym_memberships (
                        membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        member_number TEXT UNIQUE NOT NULL,
                        user_id TEXT NOT NULL,
                        user_name TEXT NOT NULL,
                        user_email TEXT,
                        membership_type TEXT NOT NULL,
                        monthly_fee REAL NOT NULL,
                        start_date DATE NOT NULL,
                        end_date DATE,
                        status TEXT DEFAULT 'active',
                        auto_renew INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS gym_classes (
                        class_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        class_name TEXT NOT NULL,
                        class_type TEXT NOT NULL,
                        instructor_name TEXT NOT NULL,
                        schedule_day TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT NOT NULL,
                        location TEXT NOT NULL,
                        max_capacity INTEGER DEFAULT 20,
                        current_enrolled INTEGER DEFAULT 0,
                        difficulty_level TEXT DEFAULT 'all_levels',
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS gym_class_bookings (
                        booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        booking_ref TEXT UNIQUE NOT NULL,
                        class_id INTEGER,
                        user_id TEXT NOT NULL,
                        user_name TEXT,
                        booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'confirmed',
                        FOREIGN KEY (class_id) REFERENCES gym_classes(class_id)
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS gym_pt_sessions (
                        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        user_name TEXT,
                        trainer_name TEXT NOT NULL,
                        session_date DATE NOT NULL,
                        session_time TEXT NOT NULL,
                        duration_minutes INTEGER DEFAULT 60,
                        session_type TEXT,
                        fee REAL,
                        status TEXT DEFAULT 'scheduled',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Create sample classes if none exist
                cursor = conn.execute('SELECT COUNT(*) FROM gym_classes')
                if cursor.fetchone()[0] == 0:
                    sample_classes = [
                        ('Morning Yoga', 'yoga', 'Sarah Johnson', 'Monday', '07:00', '08:00', 'Studio A', 20, 0, 'beginner'),
                        ('HIIT Training', 'hiit', 'Mike Davis', 'Monday', '18:00', '19:00', 'Main Gym', 15, 0, 'intermediate'),
                        ('Pilates', 'pilates', 'Emma Wilson', 'Tuesday', '10:00', '11:00', 'Studio B', 20, 0, 'all_levels'),
                        ('Spinning', 'spinning', 'Tom Harris', 'Wednesday', '17:30', '18:30', 'Spin Room', 25, 0, 'all_levels'),
                        ('Boxing', 'boxing', 'Alex Brown', 'Thursday', '19:00', '20:00', 'Studio C', 12, 0, 'intermediate'),
                        ('Yoga Flow', 'yoga', 'Sarah Johnson', 'Friday', '08:00', '09:00', 'Studio A', 20, 0, 'all_levels'),
                        ('Strength Training', 'strength', 'Mike Davis', 'Friday', '18:00', '19:00', 'Main Gym', 15, 0, 'advanced'),
                        ('Swimming Lessons', 'swimming', 'Lisa Martin', 'Saturday', '10:00', '11:00', 'Pool', 10, 0, 'beginner'),
                    ]
                    conn.executemany('''
                        INSERT INTO gym_classes (class_name, class_type, instructor_name, schedule_day, start_time, end_time, location, max_capacity, current_enrolled, difficulty_level)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', sample_classes)

            return True
        except Exception as e:
            print(f"Database initialization error: {e}")
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
    log_activity = lambda *args, **kwargs: None


def get_current_user():
    """Get current authenticated user"""
    auth = get_auth()
    if auth and hasattr(auth, 'current_user') and auth.current_user:
        return auth.current_user
    return None


def print_header(title: str):
    """Print formatted header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)


def view_membership():
    """View current user's membership"""
    user = get_current_user()
    if not user:
        print("\n❌ Please log in")
        input("Press Enter to continue...")
        return

    print_header("MY MEMBERSHIP")

    user_id = str(user.get('id') or user.get('username'))

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT member_number, user_name, membership_type, monthly_fee,
                       start_date, end_date, status, auto_renew
                FROM gym_memberships
                WHERE user_id = ? AND status = 'active'
            ''', (user_id,))

            membership = cursor.fetchone()

            if not membership:
                print("\n📋 You don't have an active gym membership")
                print("\nWould you like to register for a membership?")
                choice = input("(yes/no): ").strip().lower()
                if choice == 'yes':
                    register_membership()
            else:
                member_num, name, mtype, fee, start, end, status, auto = membership

                print(f"\nMembership Number: {member_num}")
                print(f"Member Name: {name}")
                print(f"Type: {MEMBERSHIP_TYPES.get(mtype, {}).get('name', mtype)}")
                print(f"Monthly Fee: £{fee:.2f}")
                print(f"Start Date: {start}")
                print(f"End Date: {end or 'Ongoing'}")
                print(f"Status: {status.upper()}")
                print(f"Auto-Renew: {'Yes' if auto else 'No'}")

                # Show features
                features = MEMBERSHIP_TYPES.get(mtype, {}).get('features', [])
                if features:
                    print(f"\nFeatures:")
                    for feature in features:
                        print(f"  ✓ {feature.replace('_', ' ').title()}")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def register_membership():
    """Register for a new membership"""
    user = get_current_user()
    if not user:
        print("\n❌ Please log in")
        input("Press Enter to continue...")
        return

    print_header("REGISTER MEMBERSHIP")

    # Check if user already has active membership
    user_id = str(user.get('id') or user.get('username'))

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT membership_id FROM gym_memberships
                WHERE user_id = ? AND status = 'active'
            ''', (user_id,))

            if cursor.fetchone():
                print("\n❌ You already have an active membership")
                input("Press Enter to continue...")
                return

        # Show membership types
        print("\nAvailable Membership Types:\n")
        print("Type      Monthly Fee  Features")
        print("-" * 70)

        types_list = []
        for i, (key, details) in enumerate(MEMBERSHIP_TYPES.items(), 1):
            types_list.append(key)
            features_str = ', '.join(details['features'])
            print(f"{i}. {details['name']:<8} £{details['monthly_fee']:<10.2f} {features_str}")

        choice = input("\nSelect membership type: ").strip()
        try:
            type_index = int(choice) - 1
            if 0 <= type_index < len(types_list):
                selected_type = types_list[type_index]
                type_details = MEMBERSHIP_TYPES[selected_type]
            else:
                print("❌ Invalid selection")
                input("Press Enter to continue...")
                return
        except ValueError:
            print("❌ Invalid input")
            input("Press Enter to continue...")
            return

        duration_months = input("\nMembership duration (months, default 12): ").strip() or "12"

        try:
            duration_months = int(duration_months)
            member_number = generate_membership_id()
            user_name = user.get('username', 'Unknown')
            user_email = user.get('email', '')

            start_date = datetime.now()
            end_date = start_date + timedelta(days=duration_months * 30)

            monthly_fee = type_details['monthly_fee']
            total_cost = monthly_fee * duration_months

            print(f"\n━━━ Membership Summary ━━━")
            print(f"Type: {type_details['name']}")
            print(f"Monthly Fee: £{monthly_fee:.2f}")
            print(f"Duration: {duration_months} months")
            print(f"Total Cost: £{total_cost:.2f}")
            print(f"Valid From: {start_date.strftime('%Y-%m-%d')}")
            print(f"Valid Until: {end_date.strftime('%Y-%m-%d')}")

            confirm = input("\nConfirm membership registration? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Registration cancelled")
                input("Press Enter to continue...")
                return

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO gym_memberships (
                        member_number, user_id, user_name, user_email, membership_type,
                        monthly_fee, start_date, end_date, status, auto_renew
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', 1)
                ''', (member_number, user_id, user_name, user_email or None, selected_type,
                      monthly_fee, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))

            print(f"\n✅ Membership registered successfully!")
            print(f"Membership Number: {member_number}")

            log_activity('create', 'gym_membership', membership_id=member_number,
                         details={'type': selected_type, 'duration': duration_months})

            if FINANCE_AVAILABLE:
                record_payment_to_finance(
                    student_id=user_id,
                    amount=total_cost,
                    payment_type="Gym Membership",
                    description=f"Gym Membership - {type_details['name']} - {duration_months} months",
                    payment_method="Pending"
                )

        except ValueError:
            print("❌ Invalid duration")
        except Exception as e:
            print(f"❌ Error: {e}")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def view_classes():
    """View all available fitness classes"""
    print_header("FITNESS CLASSES")

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT class_id, class_name, class_type, instructor_name, schedule_day,
                       start_time, end_time, location, max_capacity, current_enrolled, difficulty_level
                FROM gym_classes
                WHERE status = 'active'
                ORDER BY schedule_day, start_time
            ''')

            classes = cursor.fetchall()

            if not classes:
                print("\n📋 No classes available")
            else:
                current_day = None
                for cls in classes:
                    class_id, name, ctype, instructor, day, start, end, location, max_cap, enrolled, diff = cls

                    if day != current_day:
                        print(f"\n━━━ {day} ━━━")
                        current_day = day

                    spots_left = max_cap - enrolled
                    print(f"\n[{class_id}] {name} ({ctype.upper()})")
                    print(f"    Instructor: {instructor}")
                    print(f"    Time: {start} - {end}")
                    print(f"    Location: {location}")
                    print(f"    Difficulty: {diff.replace('_', ' ').title()}")
                    status = "FULL" if spots_left == 0 else f"{spots_left} spots left"
                    print(f"    Capacity: {enrolled}/{max_cap} ({status})")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def book_class():
    """Book a fitness class"""
    user = get_current_user()
    if not user:
        print("\n❌ Please log in")
        input("Press Enter to continue...")
        return

    print_header("BOOK FITNESS CLASS")

    # Check if user has active membership
    user_id = str(user.get('id') or user.get('username'))

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT membership_id, membership_type
                FROM gym_memberships
                WHERE user_id = ? AND status = 'active'
            ''', (user_id,))

            membership = cursor.fetchone()

            if not membership:
                print("\n❌ Active membership required to book classes")
                input("Press Enter to continue...")
                return

            mtype = membership[1]
            features = MEMBERSHIP_TYPES.get(mtype, {}).get('features', [])

            if 'classes' not in features:
                print(f"\n❌ Your {mtype} membership doesn't include class access")
                print("Please upgrade to Standard or Premium membership")
                input("Press Enter to continue...")
                return

        class_id = input("\nEnter class ID to book: ").strip()
        if not class_id:
            return

        with get_connection() as conn:
            # Check class availability
            cursor = conn.execute('''
                SELECT class_name, max_capacity, current_enrolled
                FROM gym_classes
                WHERE class_id = ? AND status = 'active'
            ''', (class_id,))

            cls = cursor.fetchone()

            if not cls:
                print("❌ Class not found")
                input("Press Enter to continue...")
                return

            class_name, max_cap, enrolled = cls

            if enrolled >= max_cap:
                print(f"❌ Class '{class_name}' is fully booked")
                input("Press Enter to continue...")
                return

            # Check if already booked
            cursor = conn.execute('''
                SELECT booking_id FROM gym_class_bookings
                WHERE class_id = ? AND user_id = ? AND status = 'confirmed'
            ''', (class_id, user_id))

            if cursor.fetchone():
                print(f"❌ You are already booked for '{class_name}'")
                input("Press Enter to continue...")
                return

            # Create booking
            booking_ref = generate_booking_ref()
            user_name = user.get('username', 'Unknown')

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO gym_class_bookings (booking_ref, class_id, user_id, user_name, status)
                    VALUES (?, ?, ?, ?, 'confirmed')
                ''', (booking_ref, class_id, user_id, user_name))

                # Update class enrollment count
                conn.execute('''
                    UPDATE gym_classes
                    SET current_enrolled = current_enrolled + 1
                    WHERE class_id = ?
                ''', (class_id,))

            print(f"\n✅ Class booked successfully!")
            print(f"Booking Reference: {booking_ref}")
            print(f"Class: {class_name}")

            log_activity('create', 'gym_class_booking', booking_ref=booking_ref,
                         details={'class': class_name})

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def view_my_bookings():
    """View current user's class bookings"""
    user = get_current_user()
    if not user:
        print("\n❌ Please log in")
        input("Press Enter to continue...")
        return

    print_header("MY CLASS BOOKINGS")

    user_id = str(user.get('id') or user.get('username'))

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT b.booking_ref, c.class_name, c.schedule_day, c.start_time, c.end_time,
                       c.instructor_name, c.location, b.status
                FROM gym_class_bookings b
                JOIN gym_classes c ON b.class_id = c.class_id
                WHERE b.user_id = ? AND b.status = 'confirmed'
                ORDER BY c.schedule_day, c.start_time
            ''', (user_id,))

            bookings = cursor.fetchall()

            if not bookings:
                print("\n📋 No active bookings found")
            else:
                print(f"\nYou have {len(bookings)} booking(s):\n")
                for booking in bookings:
                    ref, name, day, start, end, instructor, location, status = booking
                    print(f"[{ref}] {name}")
                    print(f"  Day: {day}")
                    print(f"  Time: {start} - {end}")
                    print(f"  Instructor: {instructor}")
                    print(f"  Location: {location}")
                    print()

                # Option to cancel
                ref = input("Enter booking reference to cancel (or Enter to return): ").strip()
                if ref:
                    cancel_class_booking(ref)

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def cancel_class_booking(booking_ref: str):
    """Cancel a class booking"""
    user = get_current_user()
    if not user:
        return

    user_id = str(user.get('id') or user.get('username'))

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT class_id, status
                FROM gym_class_bookings
                WHERE booking_ref = ? AND user_id = ?
            ''', (booking_ref, user_id))

            booking = cursor.fetchone()

            if not booking:
                print(f"\n❌ Booking {booking_ref} not found")
                return

            class_id, status = booking

            if status != 'confirmed':
                print(f"\n❌ Booking is already {status}")
                return

            confirm = input(f"\nCancel booking {booking_ref}? (yes/no): ").strip().lower()
            if confirm == 'yes':
                with transaction() as conn:
                    conn.execute('''
                        UPDATE gym_class_bookings
                        SET status = 'cancelled'
                        WHERE booking_ref = ?
                    ''', (booking_ref,))

                    conn.execute('''
                        UPDATE gym_classes
                        SET current_enrolled = current_enrolled - 1
                        WHERE class_id = ?
                    ''', (class_id,))

                print(f"✅ Booking {booking_ref} cancelled")
                log_activity('update', 'gym_class_booking', booking_ref=booking_ref,
                             details={'status': 'cancelled'})

    except Exception as e:
        print(f"❌ Error: {e}")


def book_pt_session():
    """Book a personal training session"""
    user = get_current_user()
    if not user:
        print("\n❌ Please log in")
        input("Press Enter to continue...")
        return

    print_header("BOOK PERSONAL TRAINING SESSION")

    user_id = str(user.get('id') or user.get('username'))
    user_name = user.get('username', 'Unknown')

    print("\nAvailable Trainers:")
    trainers = ['Mike Davis', 'Sarah Johnson', 'Tom Harris', 'Emma Wilson', 'Alex Brown']
    for i, trainer in enumerate(trainers, 1):
        print(f"{i}. {trainer}")

    trainer_choice = input("\nSelect trainer: ").strip()
    try:
        trainer_index = int(trainer_choice) - 1
        if 0 <= trainer_index < len(trainers):
            trainer = trainers[trainer_index]
        else:
            print("❌ Invalid selection")
            input("Press Enter to continue...")
            return
    except ValueError:
        print("❌ Invalid input")
        input("Press Enter to continue...")
        return

    session_date = input("Session date (YYYY-MM-DD): ").strip()
    session_time = input("Session time (HH:MM): ").strip()

    print("\nSession Packages:")
    print("1. Single Session - £35.00")
    print("2. 5 Session Package - £150.00 (£30.00/session)")
    print("3. 10 Session Package - £280.00 (£28.00/session)")

    package_choice = input("\nSelect package: ").strip()

    packages = {
        '1': ('single', PT_SESSION_FEES['single']),
        '2': ('package_5', PT_SESSION_FEES['package_5']),
        '3': ('package_10', PT_SESSION_FEES['package_10'])
    }

    if package_choice not in packages:
        print("❌ Invalid package selection")
        input("Press Enter to continue...")
        return

    session_type, fee = packages[package_choice]

    try:
        with transaction() as conn:
            conn.execute('''
                INSERT INTO gym_pt_sessions (
                    user_id, user_name, trainer_name, session_date, session_time,
                    duration_minutes, session_type, fee, status
                )
                VALUES (?, ?, ?, ?, ?, 60, ?, ?, 'scheduled')
            ''', (user_id, user_name, trainer, session_date, session_time, session_type, fee))

        print(f"\n✅ Personal training session booked!")
        print(f"Trainer: {trainer}")
        print(f"Date: {session_date}")
        print(f"Time: {session_time}")
        print(f"Package: {session_type.replace('_', ' ').title()}")
        print(f"Fee: £{fee:.2f}")

        log_activity('create', 'gym_pt_session', details={
            'trainer': trainer, 'date': session_date, 'package': session_type
        })

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def view_membership_statistics():
    """View membership statistics (staff)"""
    user = get_current_user()
    if not user or user.get('role') not in ['admin', 'staff']:
        print("\n❌ Staff access required")
        input("Press Enter to continue...")
        return

    print_header("MEMBERSHIP STATISTICS")

    try:
        with get_connection() as conn:
            # Total members
            cursor = conn.execute('SELECT COUNT(*) FROM gym_memberships WHERE status = "active"')
            total = cursor.fetchone()[0]

            # By type
            cursor = conn.execute('''
                SELECT membership_type, COUNT(*)
                FROM gym_memberships
                WHERE status = 'active'
                GROUP BY membership_type
            ''')
            by_type = cursor.fetchall()

            # Total class bookings
            cursor = conn.execute('SELECT COUNT(*) FROM gym_class_bookings WHERE status = "confirmed"')
            total_bookings = cursor.fetchone()[0]

            # Most popular classes
            cursor = conn.execute('''
                SELECT c.class_name, COUNT(*) as bookings
                FROM gym_class_bookings b
                JOIN gym_classes c ON b.class_id = c.class_id
                WHERE b.status = 'confirmed'
                GROUP BY c.class_name
                ORDER BY bookings DESC
                LIMIT 5
            ''')
            popular_classes = cursor.fetchall()

            print(f"\n📊 Active Memberships: {total}")

            print("\nBy Type:")
            for mtype, count in by_type:
                type_name = MEMBERSHIP_TYPES.get(mtype, {}).get('name', mtype)
                print(f"  {type_name}: {count}")

            print(f"\n📅 Total Class Bookings: {total_bookings}")

            if popular_classes:
                print("\n🏆 Most Popular Classes:")
                for name, bookings in popular_classes:
                    print(f"  {name}: {bookings} bookings")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def gym_menu():
    """Main gym menu"""
    # Initialize database
    init_gym_db()

    user = get_current_user()
    is_staff = user and user.get('role') in ['admin', 'staff']

    while True:
        print_header("UNIVERSITY GYM / FITNESS CENTER")

        if user:
            print(f"\nLogged in as: {user.get('username')} ({user.get('role')})")

        print("\n💪 MEMBERSHIP:")
        print("1. View My Membership")
        print("2. Register for Membership")

        print("\n📅 FITNESS CLASSES:")
        print("3. View All Classes")
        print("4. Book a Class")
        print("5. View My Bookings")

        print("\n🏋️ PERSONAL TRAINING:")
        print("6. Book PT Session")

        if is_staff:
            print("\n🔧 STAFF OPTIONS:")
            print("7. Membership Statistics")

        print("\n0. Return to Main Menu")

        choice = input("\nEnter choice: ").strip()

        if choice == "1":
            view_membership()
        elif choice == "2":
            register_membership()
        elif choice == "3":
            view_classes()
        elif choice == "4":
            book_class()
        elif choice == "5":
            view_my_bookings()
        elif choice == "6":
            book_pt_session()
        elif choice == "7" and is_staff:
            view_membership_statistics()
        elif choice == "0":
            break
        else:
            print("Invalid choice")
            input("Press Enter to continue...")


if __name__ == "__main__":
    gym_menu()
