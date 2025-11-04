#!/usr/bin/env python3
"""
Complete database setup script:
1. Ensure all students have user accounts with usernames/passwords
2. Assign all students to their course modules
3. Create timetables for all students
4. Add more instructors
5. Assign instructors to courses/modules
6. Remove modules not in modules.py
7. Create schedules for instructors
"""

import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
import random
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from university_system.infrastructure.database.db import DEFAULT_DB_PATH

# Valid modules from modules.py
VALID_MODULES = {
    # Compulsory modules
    "CIS0001": {"name": "python programming", "type": "compulsory", "department": "both"},
    "CIS0002": {"name": "data structures and algorithms", "type": "compulsory", "department": "both"},

    # General optional modules
    "CIS1001": {"name": "Computational Thinking", "type": "optional", "department": "both"},
    "CIS1002": {"name": "Design Patterns", "type": "optional", "department": "both"},
    "CIS1003": {"name": "Test Driven Development", "type": "optional", "department": "both"},
    "CIS1004": {"name": "SQL Relational Database", "type": "optional", "department": "both"},

    # CS optional modules
    "CIS2001": {"name": "software quality assurance principles", "type": "CS_optional", "department": "CS"},
    "CIS2002": {"name": "software reliabilities", "type": "CS_optional", "department": "CS"},
    "CIS2003": {"name": "formal methods for system verifications", "type": "CS_optional", "department": "CS"},
    "CIS2004": {"name": "algorithm complexity", "type": "CS_optional", "department": "CS"},

    # DS optional modules
    "CIS3001": {"name": "data visualisation", "type": "DS_optional", "department": "DS"},
    "CIS3002": {"name": "an introduction to artificial intelligence in data science", "type": "DS_optional", "department": "DS"},
    "CIS3003": {"name": "an introduction to machine learning", "type": "DS_optional", "department": "DS"},
    "CIS3004": {"name": "statistical methods", "type": "DS_optional", "department": "DS"},
}

# Instructor data
INSTRUCTORS = [
    {"first_name": "James", "last_name": "Smith", "title": "Dr", "specialization": "Software Engineering"},
    {"first_name": "Mary", "last_name": "Johnson", "title": "Prof", "specialization": "Data Structures"},
    {"first_name": "Robert", "last_name": "Williams", "title": "Dr", "specialization": "Machine Learning"},
    {"first_name": "Patricia", "last_name": "Brown", "title": "Dr", "specialization": "Databases"},
    {"first_name": "Michael", "last_name": "Jones", "title": "Prof", "specialization": "Algorithms"},
    {"first_name": "Jennifer", "last_name": "Garcia", "title": "Dr", "specialization": "Data Visualization"},
    {"first_name": "William", "last_name": "Martinez", "title": "Dr", "specialization": "Artificial Intelligence"},
    {"first_name": "Linda", "last_name": "Rodriguez", "title": "Prof", "specialization": "Software Testing"},
    {"first_name": "David", "last_name": "Wilson", "title": "Dr", "specialization": "Programming"},
    {"first_name": "Elizabeth", "last_name": "Anderson", "title": "Dr", "specialization": "Statistics"},
]

# Time slots for timetables
TIME_SLOTS = [
    "09:00-10:30", "10:45-12:15", "13:00-14:30", "14:45-16:15", "16:30-18:00"
]

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

ROOMS = ["A101", "A102", "A103", "B201", "B202", "B203", "C301", "C302", "C303", "D401"]


def hash_password(password):
    """Hash a password with salt"""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000, dklen=64)
    return key.hex(), salt


def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def ensure_tables_exist(conn):
    """Ensure all required tables exist"""
    cursor = conn.cursor()

    # Create instructor_modules table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS instructor_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instructor_id INTEGER NOT NULL,
            module_code TEXT NOT NULL,
            academic_year TEXT,
            semester TEXT,
            FOREIGN KEY (instructor_id) REFERENCES instructors(id),
            FOREIGN KEY (module_code) REFERENCES modules(module_code),
            UNIQUE(instructor_id, module_code)
        )
    ''')

    # Create instructor_schedules table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS instructor_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instructor_id INTEGER NOT NULL,
            module_code TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            room TEXT,
            academic_year TEXT,
            semester TEXT,
            FOREIGN KEY (instructor_id) REFERENCES instructors(id),
            FOREIGN KEY (module_code) REFERENCES modules(module_code)
        )
    ''')

    conn.commit()


def remove_invalid_modules(conn):
    """Remove modules not in modules.py"""
    cursor = conn.cursor()

    print("\n=== Removing invalid modules ===")

    # Get all current modules
    cursor.execute("SELECT module_code, module_name FROM modules")
    current_modules = cursor.fetchall()

    removed_count = 0
    for code, name in current_modules:
        if code not in VALID_MODULES:
            print(f"Removing invalid module: {code} - {name}")

            # Remove from all tables that might reference modules (with try/except for tables that may not exist)
            tables_to_clean = [
                "student_timetables",
                "instructor_schedules",
                "instructor_modules",
                "student_modules",
                "timetables",
                "assignments",
                "grades",
                "enrollments"
            ]

            for table in tables_to_clean:
                try:
                    cursor.execute(f"DELETE FROM {table} WHERE module_code = ?", (code,))
                except sqlite3.OperationalError:
                    # Table doesn't exist, skip
                    pass

            # Finally remove from modules
            cursor.execute("DELETE FROM modules WHERE module_code = ?", (code,))
            removed_count += 1

    conn.commit()
    print(f"Removed {removed_count} invalid modules")


def sync_modules_to_database(conn):
    """Ensure all modules from modules.py are in database"""
    cursor = conn.cursor()

    print("\n=== Syncing modules to database ===")

    for code, details in VALID_MODULES.items():
        cursor.execute("SELECT module_code FROM modules WHERE module_code = ?", (code,))
        if not cursor.fetchone():
            print(f"Adding module: {code} - {details['name']}")
            cursor.execute('''
                INSERT INTO modules (module_code, module_name, module_type, department, credits, is_active)
                VALUES (?, ?, ?, ?, 15, 1)
            ''', (code, details['name'], details['type'], details['department']))
        else:
            # Update existing module
            cursor.execute('''
                UPDATE modules
                SET module_name = ?, module_type = ?, department = ?, is_active = 1
                WHERE module_code = ?
            ''', (details['name'], details['type'], details['department'], code))

    conn.commit()
    print("Modules synced successfully")


def create_user_accounts_for_students(conn):
    """Ensure all students have user accounts"""
    cursor = conn.cursor()

    print("\n=== Creating user accounts for students ===")

    # Get all students
    cursor.execute("SELECT student_id, first_name, last_name, email_address FROM students")
    students = cursor.fetchall()

    created_count = 0
    for student_id, first_name, last_name, email in students:
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE student_id = ?", (student_id,))
        user = cursor.fetchone()

        username = f"{first_name.lower()}.{last_name.lower()}"

        if not user:
            # Create user
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO users (username, email, first_name, last_name, role, student_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'student', ?, ?, ?)
            ''', (username, email, first_name, last_name, student_id, timestamp, timestamp))

            user_id = cursor.lastrowid

            # Create password (firstname123456)
            password = f"{first_name.lower()}123456"
            password_hash, salt = hash_password(password)

            cursor.execute('''
                INSERT INTO user_accounts (user_id, username, password_hash, salt, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, password_hash, salt, timestamp, timestamp))

            print(f"Created account for {student_id}: {username} / {password}")
            created_count += 1

    conn.commit()
    print(f"Created {created_count} user accounts")


def assign_students_to_modules(conn):
    """Assign all students to their course modules"""
    cursor = conn.cursor()

    print("\n=== Assigning students to modules ===")

    # Get all students
    cursor.execute("SELECT student_id, course FROM students")
    students = cursor.fetchall()

    for student_id, course in students:
        # Clear existing module assignments
        cursor.execute("DELETE FROM student_modules WHERE student_id = ?", (student_id,))

        # 2 compulsory modules
        compulsory_modules = ["CIS0001", "CIS0002"]

        # 2 optional modules (general)
        optional_pool = ["CIS1001", "CIS1002", "CIS1003", "CIS1004"]
        optional_modules = random.sample(optional_pool, 2)

        # 2 course-specific modules
        if course == "CS":
            course_specific_pool = ["CIS2001", "CIS2002", "CIS2003", "CIS2004"]
        elif course == "DS":
            course_specific_pool = ["CIS3001", "CIS3002", "CIS3003", "CIS3004"]
        else:
            # If no specific course, just pick 2 more from optional pool
            course_specific_pool = [m for m in optional_pool if m not in optional_modules]

        course_specific_modules = random.sample(course_specific_pool, 2)

        # Total: 6 modules (2 compulsory + 2 optional + 2 course-specific)
        all_modules = compulsory_modules + optional_modules + course_specific_modules

        enrollment_date = datetime.now().strftime('%Y-%m-%d')
        for module_code in all_modules:
            cursor.execute('''
                INSERT INTO student_modules (student_id, module_code, enrollment_date, status)
                VALUES (?, ?, ?, 'enrolled')
            ''', (student_id, module_code, enrollment_date))

        print(f"Assigned 6 modules to {student_id} (2 compulsory, 2 optional, 2 {course}-specific)")

    conn.commit()
    print("Module assignments completed")


def create_student_timetables(conn):
    """Create timetables for all students based on their modules"""
    cursor = conn.cursor()

    print("\n=== Creating student timetables ===")

    # First, ensure student_timetables table exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_timetables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            room TEXT,
            instructor_id INTEGER,
            academic_year TEXT,
            semester TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (module_code) REFERENCES modules(module_code),
            FOREIGN KEY (instructor_id) REFERENCES instructors(id)
        )
    ''')

    # Clear existing timetables
    cursor.execute("DELETE FROM student_timetables")

    # Get all students with their modules
    cursor.execute('''
        SELECT DISTINCT sm.student_id, sm.module_code
        FROM student_modules sm
        WHERE sm.status = 'enrolled'
        ORDER BY sm.student_id
    ''')
    student_modules = cursor.fetchall()

    # Group by student
    student_schedule = {}
    for student_id, module_code in student_modules:
        if student_id not in student_schedule:
            student_schedule[student_id] = []
        student_schedule[student_id].append(module_code)

    academic_year = "2024-2025"
    semester = "Fall"

    for student_id, modules in student_schedule.items():
        # Assign 2 time slots per module (lectures/labs)
        used_slots = set()

        for module_code in modules:
            # Get instructor for this module
            cursor.execute('''
                SELECT instructor_id FROM instructor_modules
                WHERE module_code = ?
                LIMIT 1
            ''', (module_code,))
            instructor_row = cursor.fetchone()
            instructor_id = instructor_row[0] if instructor_row else None

            slots_for_module = 0
            attempts = 0
            max_attempts = 50

            while slots_for_module < 2 and attempts < max_attempts:
                day = random.choice(DAYS)
                time_slot = random.choice(TIME_SLOTS)
                slot_key = f"{day}_{time_slot}"

                if slot_key not in used_slots:
                    room = random.choice(ROOMS)

                    cursor.execute('''
                        INSERT INTO student_timetables
                        (student_id, module_code, day_of_week, time_slot, room, instructor_id, academic_year, semester)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (student_id, module_code, day, time_slot, room, instructor_id, academic_year, semester))

                    used_slots.add(slot_key)
                    slots_for_module += 1

                attempts += 1

        print(f"Created timetable for {student_id} ({len(modules)} modules)")

    conn.commit()
    print("Student timetables created")


def add_instructors(conn):
    """Add instructors to database"""
    cursor = conn.cursor()

    print("\n=== Adding instructors ===")

    added_count = 0
    for instructor in INSTRUCTORS:
        email = f"{instructor['first_name'].lower()}.{instructor['last_name'].lower()}@university.edu"

        # Check if instructor exists
        cursor.execute("SELECT id FROM instructors WHERE email = ?", (email,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO instructors (first_name, last_name, email, department, specialization, is_active)
                VALUES (?, ?, ?, 'Computing', ?, 1)
            ''', (instructor['first_name'], instructor['last_name'], email, instructor['specialization']))

            instructor_id = cursor.lastrowid

            # Create user account for instructor
            username = f"{instructor['first_name'].lower()}.{instructor['last_name'].lower()}"
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO users (username, email, first_name, last_name, role, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'instructor', ?, ?)
            ''', (username, email, instructor['first_name'], instructor['last_name'], timestamp, timestamp))

            user_id = cursor.lastrowid

            # Create password (firstname123456)
            password = f"{instructor['first_name'].lower()}123456"
            password_hash, salt = hash_password(password)

            cursor.execute('''
                INSERT INTO user_accounts (user_id, username, password_hash, salt, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, password_hash, salt, timestamp, timestamp))

            print(f"Added instructor: {instructor['title']} {instructor['first_name']} {instructor['last_name']} ({username} / {password})")
            added_count += 1

    conn.commit()
    print(f"Added {added_count} instructors")


def assign_instructors_to_modules(conn):
    """Assign instructors to modules"""
    cursor = conn.cursor()

    print("\n=== Assigning instructors to modules ===")

    # Clear existing assignments
    cursor.execute("DELETE FROM instructor_modules")

    # Get all instructors
    cursor.execute("SELECT id, first_name, last_name, specialization FROM instructors WHERE is_active = 1")
    instructors = cursor.fetchall()

    # Get all modules
    module_codes = list(VALID_MODULES.keys())

    # Assign 2-4 modules per instructor
    academic_year = "2024-2025"
    semester = "Fall"

    for instructor_id, first_name, last_name, specialization in instructors:
        # Select 2-4 random modules
        num_modules = random.randint(2, 4)
        assigned_modules = random.sample(module_codes, min(num_modules, len(module_codes)))

        for module_code in assigned_modules:
            cursor.execute('''
                INSERT INTO instructor_modules (instructor_id, module_code, academic_year, semester)
                VALUES (?, ?, ?, ?)
            ''', (instructor_id, module_code, academic_year, semester))

        print(f"Assigned {len(assigned_modules)} modules to {first_name} {last_name}")

    conn.commit()
    print("Instructor module assignments completed")


def create_instructor_schedules(conn):
    """Create schedules for instructors based on modules they teach"""
    cursor = conn.cursor()

    print("\n=== Creating instructor schedules ===")

    # Clear existing schedules
    cursor.execute("DELETE FROM instructor_schedules")

    # Get instructor module assignments
    cursor.execute('''
        SELECT im.instructor_id, im.module_code, im.academic_year, im.semester,
               i.first_name, i.last_name
        FROM instructor_modules im
        JOIN instructors i ON im.instructor_id = i.id
    ''')
    assignments = cursor.fetchall()

    # Track used slots per instructor
    instructor_slots = {}

    for instructor_id, module_code, academic_year, semester, first_name, last_name in assignments:
        if instructor_id not in instructor_slots:
            instructor_slots[instructor_id] = set()

        # Each module gets 2-3 time slots (lectures/tutorials)
        slots_needed = random.randint(2, 3)
        slots_created = 0
        attempts = 0
        max_attempts = 50

        while slots_created < slots_needed and attempts < max_attempts:
            day = random.choice(DAYS)
            time_slot = random.choice(TIME_SLOTS)
            slot_key = f"{day}_{time_slot}"

            if slot_key not in instructor_slots[instructor_id]:
                room = random.choice(ROOMS)

                cursor.execute('''
                    INSERT INTO instructor_schedules
                    (instructor_id, module_code, day_of_week, time_slot, room, academic_year, semester)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (instructor_id, module_code, day, time_slot, room, academic_year, semester))

                instructor_slots[instructor_id].add(slot_key)
                slots_created += 1

            attempts += 1

        print(f"Created {slots_created} schedule slots for {first_name} {last_name} - {module_code}")

    conn.commit()
    print("Instructor schedules created")


def main():
    """Main execution function"""
    print("=" * 60)
    print("COMPLETE DATABASE SETUP")
    print("=" * 60)

    conn = get_db_connection()

    try:
        # Ensure tables exist
        ensure_tables_exist(conn)

        # 1. Remove invalid modules
        remove_invalid_modules(conn)

        # 2. Sync valid modules to database
        sync_modules_to_database(conn)

        # 3. Create user accounts for students
        create_user_accounts_for_students(conn)

        # 4. Assign students to modules
        assign_students_to_modules(conn)

        # 5. Create student timetables
        create_student_timetables(conn)

        # 6. Add instructors
        add_instructors(conn)

        # 7. Assign instructors to modules
        assign_instructors_to_modules(conn)

        # 8. Create instructor schedules
        create_instructor_schedules(conn)

        print("\n" + "=" * 60)
        print("DATABASE SETUP COMPLETED SUCCESSFULLY!")
        print("=" * 60)

        # Print summary
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM students")
        student_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM instructors WHERE is_active = 1")
        instructor_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM modules WHERE is_active = 1")
        module_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]

        print(f"\nSummary:")
        print(f"  Students: {student_count}")
        print(f"  Instructors: {instructor_count}")
        print(f"  Modules: {module_count}")
        print(f"  User Accounts: {user_count}")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
