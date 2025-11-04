#!/usr/bin/env python3
"""
Test script for schedule conflict detection
Tests for various types of scheduling conflicts
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
from university_system.infrastructure.database.db import DEFAULT_DB_PATH


def test_schedule_conflicts():
    """Test schedule conflict detection"""
    print("=" * 60)
    print("SCHEDULE CONFLICT DETECTION TEST")
    print("=" * 60)

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        # Test 1: Student schedule conflicts (same time, different modules)
        print("\n✓ Test 1: Student schedule conflicts")
        cursor.execute("""
            SELECT st1.student_id, st1.day_of_week, st1.time_slot,
                   GROUP_CONCAT(st1.module_code) as conflicting_modules,
                   COUNT(*) as conflict_count
            FROM student_timetables st1
            GROUP BY st1.student_id, st1.day_of_week, st1.time_slot
            HAVING COUNT(*) > 1
        """)
        student_conflicts = cursor.fetchall()

        if student_conflicts:
            print(f"  ✗ FAILED: {len(student_conflicts)} student schedule conflicts found:")
            for sid, day, time, modules, count in student_conflicts[:5]:
                print(f"    - {sid} on {day} at {time}")
                print(f"      Modules: {modules} ({count} conflicts)")
        else:
            print("  ✓ No student schedule conflicts")

        # Test 2: Instructor schedule conflicts
        print("\n✓ Test 2: Instructor schedule conflicts")
        cursor.execute("""
            SELECT isch1.instructor_id, isch1.day_of_week, isch1.time_slot,
                   GROUP_CONCAT(isch1.module_code) as conflicting_modules,
                   COUNT(*) as conflict_count
            FROM instructor_schedules isch1
            GROUP BY isch1.instructor_id, isch1.day_of_week, isch1.time_slot
            HAVING COUNT(*) > 1
        """)
        instructor_conflicts = cursor.fetchall()

        if instructor_conflicts:
            print(f"  ✗ FAILED: {len(instructor_conflicts)} instructor schedule conflicts found:")
            for iid, day, time, modules, count in instructor_conflicts[:5]:
                cursor.execute("SELECT first_name, last_name FROM instructors WHERE id = ?", (iid,))
                name = cursor.fetchone()
                if name:
                    print(f"    - {name[0]} {name[1]} on {day} at {time}")
                    print(f"      Modules: {modules} ({count} conflicts)")
        else:
            print("  ✓ No instructor schedule conflicts")

        # Test 3: Room double-booking conflicts
        print("\n✓ Test 3: Room double-booking conflicts")
        cursor.execute("""
            SELECT room, day_of_week, time_slot, COUNT(*) as booking_count,
                   GROUP_CONCAT(DISTINCT module_code) as modules
            FROM student_timetables
            WHERE room IS NOT NULL
            GROUP BY room, day_of_week, time_slot
            HAVING COUNT(*) > 50  -- Threshold for potential conflict
        """)
        room_conflicts = cursor.fetchall()

        if room_conflicts:
            print(f"  ⚠ Potential room over-booking ({len(room_conflicts)} cases):")
            for room, day, time, count, modules in room_conflicts[:5]:
                print(f"    - {room} on {day} at {time}: {count} bookings")
        else:
            print("  ✓ No obvious room conflicts")

        # Test 4: Module scheduled multiple times for same student
        print("\n✓ Test 4: Duplicate module scheduling")
        cursor.execute("""
            SELECT student_id, module_code, COUNT(*) as schedule_count
            FROM student_timetables
            GROUP BY student_id, module_code
            HAVING COUNT(*) > 2  -- More than 2 slots per module might be unusual
        """)
        duplicate_modules = cursor.fetchall()

        if duplicate_modules:
            print(f"  ⚠ {len(duplicate_modules)} students with >2 slots for same module:")
            for sid, module, count in duplicate_modules[:5]:
                print(f"    - {sid}: {module} ({count} time slots)")
        else:
            print("  ✓ No excessive duplicate module scheduling")

        # Test 5: Instructor teaching same module multiple times same day
        print("\n✓ Test 5: Instructor teaching same module multiple times per day")
        cursor.execute("""
            SELECT instructor_id, module_code, day_of_week, COUNT(*) as times_per_day
            FROM instructor_schedules
            GROUP BY instructor_id, module_code, day_of_week
            HAVING COUNT(*) > 2
        """)
        same_module_day = cursor.fetchall()

        if same_module_day:
            print(f"  ⚠ {len(same_module_day)} cases of same module >2 times per day:")
            for iid, module, day, count in same_module_day[:5]:
                cursor.execute("SELECT first_name, last_name FROM instructors WHERE id = ?", (iid,))
                name = cursor.fetchone()
                if name:
                    print(f"    - {name[0]} {name[1]}: {module} on {day} ({count} times)")
        else:
            print("  ✓ No excessive same-module scheduling per day")

        # Test 6: Students with no free days
        print("\n✓ Test 6: Students with classes every day")
        cursor.execute("""
            SELECT student_id, COUNT(DISTINCT day_of_week) as days_with_classes
            FROM student_timetables
            GROUP BY student_id
            HAVING COUNT(DISTINCT day_of_week) = 5
        """)
        full_week_students = cursor.fetchall()

        total_students = cursor.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        percentage = (len(full_week_students) / total_students) * 100

        print(f"  ℹ {len(full_week_students)} students ({percentage:.1f}%) have classes all 5 days")

        # Test 7: Time slot distribution balance
        print("\n✓ Test 7: Time slot distribution")
        cursor.execute("""
            SELECT time_slot, COUNT(*) as usage_count
            FROM student_timetables
            GROUP BY time_slot
            ORDER BY usage_count DESC
        """)
        time_distribution = cursor.fetchall()

        if time_distribution:
            max_usage = time_distribution[0][1]
            min_usage = time_distribution[-1][1]
            variance = max_usage - min_usage

            print("  Time slot usage:")
            for time_slot, count in time_distribution:
                print(f"    - {time_slot}: {count}")

            if variance > max_usage * 0.5:
                print(f"  ⚠ High variance in time slot usage (diff: {variance})")
            else:
                print(f"  ✓ Reasonable time slot distribution (diff: {variance})")

        # Test 8: Back-to-back classes check
        print("\n✓ Test 8: Students with many back-to-back classes")
        # This is a simplified check - real implementation would parse time slots
        cursor.execute("""
            SELECT student_id, day_of_week, COUNT(*) as classes_per_day
            FROM student_timetables
            GROUP BY student_id, day_of_week
            HAVING COUNT(*) > 3
        """)
        heavy_days = cursor.fetchall()

        if heavy_days:
            print(f"  ℹ {len(heavy_days)} instances of >3 classes in one day:")
            for sid, day, count in heavy_days[:5]:
                print(f"    - {sid} on {day}: {count} classes")
        else:
            print("  ✓ No days with excessive classes")

        print("\n" + "=" * 60)
        print("SCHEDULE CONFLICT TEST COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    test_schedule_conflicts()
