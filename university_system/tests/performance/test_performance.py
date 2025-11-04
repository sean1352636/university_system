#!/usr/bin/env python3
"""
Test script for database performance
Tests query execution times and database optimization
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
import time
from university_system.infrastructure.database.db import DEFAULT_DB_PATH


def measure_query(cursor, query, description):
    """Measure query execution time"""
    start = time.time()
    cursor.execute(query)
    results = cursor.fetchall()
    elapsed = (time.time() - start) * 1000  # Convert to milliseconds
    return elapsed, len(results)


def test_performance():
    """Test database performance"""
    print("=" * 60)
    print("DATABASE PERFORMANCE TEST")
    print("=" * 60)

    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    try:
        queries = [
            ("Count all students", "SELECT COUNT(*) FROM students"),
            ("Get student with modules", """
                SELECT s.*, COUNT(sm.module_code)
                FROM students s
                LEFT JOIN student_modules sm ON s.student_id = sm.student_id
                GROUP BY s.student_id
            """),
            ("Get students with timetables", """
                SELECT s.student_id, s.first_name, s.last_name,
                       COUNT(st.id) as schedule_count
                FROM students s
                LEFT JOIN student_timetables st ON s.student_id = st.student_id
                GROUP BY s.student_id, s.first_name, s.last_name
            """),
            ("Complex join query", """
                SELECT s.student_id, s.first_name, s.last_name, s.course,
                       m.module_code, m.module_name,
                       st.day_of_week, st.time_slot
                FROM students s
                JOIN student_modules sm ON s.student_id = sm.student_id
                JOIN modules m ON sm.module_code = m.module_code
                LEFT JOIN student_timetables st ON s.student_id = st.student_id
                    AND st.module_code = m.module_code
                WHERE s.course = 'CS'
            """),
            ("Instructor assignments", """
                SELECT i.first_name, i.last_name,
                       m.module_code, m.module_name,
                       COUNT(sm.student_id) as student_count
                FROM instructors i
                JOIN instructor_modules im ON i.id = im.instructor_id
                JOIN modules m ON im.module_code = m.module_code
                LEFT JOIN student_modules sm ON m.module_code = sm.module_code
                GROUP BY i.id, m.module_code
            """),
        ]

        print("\n✓ Query Performance Tests:")
        total_time = 0

        for description, query in queries:
            elapsed, row_count = measure_query(cursor, query, description)
            total_time += elapsed

            # Performance rating
            if elapsed < 10:
                rating = "Excellent"
            elif elapsed < 50:
                rating = "Good"
            elif elapsed < 100:
                rating = "Fair"
            else:
                rating = "Slow"

            print(f"\n  {description}:")
            print(f"    Time: {elapsed:.2f}ms | Rows: {row_count} | {rating}")

        print(f"\n✓ Total query time: {total_time:.2f}ms")

        # Test index effectiveness
        cursor.execute("PRAGMA index_list(students)")
        student_indexes = cursor.fetchall()

        print(f"\n✓ Indexes on students table: {len(student_indexes)}")
        for idx_info in student_indexes:
            print(f"  - {idx_info[1]}")

        # Test database statistics
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]

        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]

        db_size_pages = page_count * page_size / (1024 * 1024)

        print(f"\n✓ Database statistics:")
        print(f"  - Page count: {page_count}")
        print(f"  - Page size: {page_size} bytes")
        print(f"  - Estimated size: {db_size_pages:.2f} MB")

        print("\n" + "=" * 60)
        print("PERFORMANCE TEST COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    test_performance()
