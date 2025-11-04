#!/usr/bin/env python3
"""
Test script for timetable generation
Tests student timetables and schedule conflicts
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
from university_system.infrastructure.database.db import DEFAULT_DB_PATH


def test_timetables():
    """Test timetable generation and conflicts"""
    print("=" * 60)
    print("TIMETABLE GENERATION TEST")
    print("=" * 60)

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        # Test 1: Count total timetable entries
        cursor.execute("SELECT COUNT(*) FROM student_timetables")
        total_entries = cursor.fetchone()[0]
        print(f"\n✓ Total timetable entries: {total_entries}")

        # Test 2: Check students have timetables
        cursor.execute("""
            SELECT COUNT(DISTINCT student_id) FROM student_timetables
        """)
        students_with_timetables = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM students")
        total_students = cursor.fetchone()[0]

        print(f"\n✓ Students with timetables: {students_with_timetables}/{total_students}")

        if students_with_timetables < total_students:
            print(f"  ⚠ Warning: {total_students - students_with_timetables} students without timetables")

        # Test 3: Check for schedule conflicts (same student, same day/time, different modules)
        cursor.execute("""
            SELECT st1.student_id, st1.day_of_week, st1.time_slot,
                   COUNT(*) as conflict_count
            FROM student_timetables st1
            GROUP BY st1.student_id, st1.day_of_week, st1.time_slot
            HAVING conflict_count > 1
        """)
        conflicts = cursor.fetchall()

        if conflicts:
            print(f"\n✗ FAILED: {len(conflicts)} schedule conflicts found:")
            for student_id, day, time, count in conflicts[:5]:
                print(f"  - {student_id}: {day} {time} ({count} modules)")
        else:
            print("\n✓ No schedule conflicts detected")

        # Test 4: Distribution across days
        cursor.execute("""
            SELECT day_of_week, COUNT(*) as count
            FROM student_timetables
            GROUP BY day_of_week
            ORDER BY
                CASE day_of_week
                    WHEN 'Monday' THEN 1
                    WHEN 'Tuesday' THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday' THEN 4
                    WHEN 'Friday' THEN 5
                END
        """)
        day_distribution = cursor.fetchall()

        print("\n✓ Classes by day of week:")
        for day, count in day_distribution:
            print(f"  - {day}: {count} classes")

        # Test 5: Distribution across time slots
        cursor.execute("""
            SELECT time_slot, COUNT(*) as count
            FROM student_timetables
            GROUP BY time_slot
            ORDER BY time_slot
        """)
        time_distribution = cursor.fetchall()

        print("\n✓ Classes by time slot:")
        for time, count in time_distribution:
            print(f"  - {time}: {count} classes")

        # Test 6: Room allocation
        cursor.execute("""
            SELECT room, COUNT(*) as count
            FROM student_timetables
            WHERE room IS NOT NULL
            GROUP BY room
            ORDER BY count DESC
            LIMIT 5
        """)
        room_usage = cursor.fetchall()

        print("\n✓ Top 5 room usage:")
        for room, count in room_usage:
            print(f"  - {room}: {count} classes")

        # Test 7: Sample student timetable
        cursor.execute("""
            SELECT st.student_id, s.course
            FROM student_timetables st
            JOIN students s ON st.student_id = s.student_id
            GROUP BY st.student_id, s.course
            LIMIT 1
        """)
        sample_student = cursor.fetchone()

        if sample_student:
            student_id, course = sample_student
            cursor.execute("""
                SELECT day_of_week, time_slot, module_code, room
                FROM student_timetables
                WHERE student_id = ?
                ORDER BY
                    CASE day_of_week
                        WHEN 'Monday' THEN 1
                        WHEN 'Tuesday' THEN 2
                        WHEN 'Wednesday' THEN 3
                        WHEN 'Thursday' THEN 4
                        WHEN 'Friday' THEN 5
                    END,
                    time_slot
            """, (student_id,))
            schedule = cursor.fetchall()

            print(f"\n✓ Sample timetable ({student_id} - {course}):")
            current_day = None
            for day, time, module, room in schedule:
                if day != current_day:
                    print(f"\n  {day}:")
                    current_day = day
                print(f"    {time}: {module} (Room {room})")

        print("\n" + "=" * 60)
        print("TIMETABLE TEST COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    test_timetables()
