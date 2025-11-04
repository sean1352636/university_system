#!/usr/bin/env python3
"""
Test script for instructor management
Tests instructor assignments, schedules, and workload
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
from university_system.infrastructure.database.db import DEFAULT_DB_PATH


def test_instructors():
    """Test instructor assignments and schedules"""
    print("=" * 60)
    print("INSTRUCTOR MANAGEMENT TEST")
    print("=" * 60)

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        # Test 1: Count instructors
        cursor.execute("SELECT COUNT(*) FROM instructors WHERE is_active = 1")
        total_instructors = cursor.fetchone()[0]
        print(f"\n✓ Active instructors: {total_instructors}")

        # Test 2: Instructors with user accounts
        cursor.execute("""
            SELECT COUNT(*) FROM instructors i
            WHERE is_active = 1
            AND EXISTS (
                SELECT 1 FROM users u
                WHERE u.email = i.email AND u.role = 'instructor'
            )
        """)
        instructors_with_accounts = cursor.fetchone()[0]
        print(f"\n✓ Instructors with user accounts: {instructors_with_accounts}/{total_instructors}")

        # Test 3: Module assignments
        cursor.execute("""
            SELECT i.first_name, i.last_name, COUNT(im.module_code) as module_count
            FROM instructors i
            LEFT JOIN instructor_modules im ON i.id = im.instructor_id
            WHERE i.is_active = 1
            GROUP BY i.id, i.first_name, i.last_name
            ORDER BY module_count DESC
        """)
        instructor_modules = cursor.fetchall()

        print("\n✓ Module assignments per instructor:")
        for first_name, last_name, count in instructor_modules:
            print(f"  - {first_name} {last_name}: {count} modules")

        # Test 4: Check all modules have instructors
        cursor.execute("""
            SELECT m.module_code, m.module_name
            FROM modules m
            WHERE m.is_active = 1
            AND NOT EXISTS (
                SELECT 1 FROM instructor_modules im
                WHERE im.module_code = m.module_code
            )
        """)
        modules_without_instructors = cursor.fetchall()

        if modules_without_instructors:
            print(f"\n⚠ Warning: {len(modules_without_instructors)} modules without instructors:")
            for code, name in modules_without_instructors:
                print(f"  - {code}: {name}")
        else:
            print("\n✓ All active modules have instructors assigned")

        # Test 5: Instructor schedules
        cursor.execute("""
            SELECT i.first_name, i.last_name, COUNT(isch.id) as schedule_count
            FROM instructors i
            LEFT JOIN instructor_schedules isch ON i.id = isch.instructor_id
            WHERE i.is_active = 1
            GROUP BY i.id, i.first_name, i.last_name
            ORDER BY schedule_count DESC
        """)
        instructor_schedules = cursor.fetchall()

        print("\n✓ Schedule slots per instructor:")
        for first_name, last_name, count in instructor_schedules:
            print(f"  - {first_name} {last_name}: {count} time slots")

        # Test 6: Check for instructor schedule conflicts
        cursor.execute("""
            SELECT instructor_id, day_of_week, time_slot, COUNT(*) as conflict_count
            FROM instructor_schedules
            GROUP BY instructor_id, day_of_week, time_slot
            HAVING conflict_count > 1
        """)
        schedule_conflicts = cursor.fetchall()

        if schedule_conflicts:
            print(f"\n✗ FAILED: {len(schedule_conflicts)} instructor schedule conflicts:")
            for instructor_id, day, time, count in schedule_conflicts[:5]:
                cursor.execute("""
                    SELECT first_name, last_name FROM instructors WHERE id = ?
                """, (instructor_id,))
                name = cursor.fetchone()
                if name:
                    print(f"  - {name[0]} {name[1]}: {day} {time} ({count} classes)")
        else:
            print("\n✓ No instructor schedule conflicts")

        # Test 7: Sample instructor details
        cursor.execute("""
            SELECT i.first_name, i.last_name, i.email, i.specialization,
                   (SELECT COUNT(*) FROM instructor_modules im WHERE im.instructor_id = i.id) as modules,
                   (SELECT COUNT(*) FROM instructor_schedules isch WHERE isch.instructor_id = i.id) as slots
            FROM instructors i
            WHERE i.is_active = 1
            LIMIT 5
        """)
        sample_instructors = cursor.fetchall()

        print("\n✓ Sample instructor details:")
        for first, last, email, spec, mod_count, slot_count in sample_instructors:
            print(f"  - {first} {last}")
            print(f"    Email: {email}")
            print(f"    Specialization: {spec}")
            print(f"    Modules: {mod_count} | Time slots: {slot_count}")

        # Test 8: Sample instructor schedule
        cursor.execute("SELECT id, first_name, last_name FROM instructors WHERE is_active = 1 LIMIT 1")
        sample_instructor = cursor.fetchone()

        if sample_instructor:
            instructor_id, first_name, last_name = sample_instructor
            cursor.execute("""
                SELECT isch.day_of_week, isch.time_slot, isch.module_code, isch.room
                FROM instructor_schedules isch
                WHERE isch.instructor_id = ?
                ORDER BY
                    CASE isch.day_of_week
                        WHEN 'Monday' THEN 1
                        WHEN 'Tuesday' THEN 2
                        WHEN 'Wednesday' THEN 3
                        WHEN 'Thursday' THEN 4
                        WHEN 'Friday' THEN 5
                    END,
                    isch.time_slot
            """, (instructor_id,))
            schedule = cursor.fetchall()

            print(f"\n✓ Sample schedule ({first_name} {last_name}):")
            current_day = None
            for day, time, module, room in schedule:
                if day != current_day:
                    print(f"\n  {day}:")
                    current_day = day
                print(f"    {time}: {module} (Room {room})")

        print("\n" + "=" * 60)
        print("INSTRUCTOR TEST COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    test_instructors()
