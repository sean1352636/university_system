"""Utility functions: search logging, performance optimization, system statistics."""
import json
import time
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from . import _globals
from .db import insert_search_analytics_record


def log_search(search_type, criteria, result_count):
    """Log search activity for analytics"""
    # Add to search history
    search_entry = {
        'type': search_type,
        'criteria': str(criteria),
        'results': result_count,
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    _globals.search_history.append(search_entry)

    # Keep only last 100 searches in memory
    if len(_globals.search_history) > 100:
        _globals.search_history = _globals.search_history[-100:]

    # Log to database for analytics
    try:
        conn = get_connection()
        cursor = conn.cursor()

        start_time = time.time()
        execution_time = 0.1  # Placeholder

        insert_search_analytics_record(
            cursor,
            user_id=_globals.current_user,
            search_type=search_type,
            criteria=str(criteria),
            results_count=result_count,
            execution_time=execution_time
        )

        conn.commit()
        conn.close()

    except sqlite3.Error:
        pass  # Fail silently for analytics

def performance_optimization():
    """Perform database optimization"""
    print("\n⚡ PERFORMANCE OPTIMIZATION")
    print("="*40)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Running optimization tasks...")

        # Create indexes for better performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_students_name ON students(first_name, last_name)",
            "CREATE INDEX IF NOT EXISTS idx_students_course ON students(course)",
            "CREATE INDEX IF NOT EXISTS idx_students_age ON students(age)",
            "CREATE INDEX IF NOT EXISTS idx_students_registration ON students(registration_datetime)",
            "CREATE INDEX IF NOT EXISTS idx_modules_student ON student_modules(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_modules_code ON student_modules(module_code)"
        ]

        for index_sql in indexes:
            cursor.execute(index_sql)
            print(f"✓ Index created")

        # VACUUM to optimize database file
        cursor.execute("VACUUM")
        print("✓ Database vacuumed")

        # ANALYZE to update query planner statistics
        cursor.execute("ANALYZE")
        print("✓ Statistics updated")

        conn.commit()
        conn.close()

        print("\n✅ Performance optimization completed!")

    except sqlite3.Error as e:
        print(f"Optimization error: {e}")

def export_system_statistics():
    """Export comprehensive system statistics"""
    print("\n📊 EXPORTING SYSTEM STATISTICS")
    print("="*50)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"system_statistics_{timestamp}.json"

        statistics = {}

        # Student statistics
        cursor.execute("SELECT COUNT(*) FROM students")
        statistics['total_students'] = cursor.fetchone()[0]

        cursor.execute("SELECT course, COUNT(*) FROM students GROUP BY course")
        statistics['students_by_course'] = dict(cursor.fetchall())

        cursor.execute("SELECT AVG(age) FROM students")
        statistics['average_age'] = round(cursor.fetchone()[0] or 0, 1)

        # Module statistics
        cursor.execute("SELECT COUNT(DISTINCT module_code) FROM student_modules")
        statistics['total_modules'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM student_modules")
        statistics['total_enrollments'] = cursor.fetchone()[0]

        # Search statistics
        cursor.execute("SELECT COUNT(*) FROM search_analytics")
        statistics['total_searches'] = cursor.fetchone()[0]

        cursor.execute("""
        SELECT search_type, COUNT(*)
        FROM search_analytics
        GROUP BY search_type
        ORDER BY COUNT(*) DESC
        """)
        statistics['search_types'] = dict(cursor.fetchall())

        # Data quality statistics
        cursor.execute("SELECT COUNT(*) FROM students WHERE email IS NULL OR email = ''")
        missing_emails = cursor.fetchone()[0]
        statistics['data_quality'] = {
            'missing_emails': missing_emails,
            'email_completeness': round((1 - missing_emails/statistics['total_students']) * 100, 1) if statistics['total_students'] > 0 else 0
        }

        # Export to JSON
        with open(filename, 'w') as f:
            json.dump(statistics, f, indent=2, default=str)

        print(f"✅ Statistics exported to {filename}")

        # Display summary
        print(f"\n📈 SYSTEM OVERVIEW:")
        print("-" * 40)
        print(f"Total Students: {statistics['total_students']}")
        print(f"Total Modules: {statistics['total_modules']}")
        print(f"Total Searches: {statistics['total_searches']}")
        print(f"Email Completeness: {statistics['data_quality']['email_completeness']}%")

        conn.close()

    except sqlite3.Error as e:
        print(f"Error exporting statistics: {e}")
