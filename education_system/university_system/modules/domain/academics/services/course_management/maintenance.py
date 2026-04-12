from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.core.sql_safety import validate_table_name
from datetime import datetime, timedelta
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_update


@log_update(module="course_management", description="Running system maintenance")
def system_maintenance(auth):
    """System maintenance and cleanup utilities"""
    if not auth or not auth.current_user:
        print("You must be logged in to perform maintenance.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to perform system maintenance.")
        return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nSystem Maintenance Utilities")
        print("===========================")

        print("Select maintenance operation:")
        print("1. Database integrity check")
        print("2. Clean up orphaned records")
        print("3. Recalculate enrollment numbers")
        print("4. Archive old course history")
        print("5. Database statistics")
        print("6. Rebuild search indexes")
        print("7. Export database backup")
        print("0. Return to menu")

        while True:
            try:
                choice = int(input("Enter choice (0-7): "))
                if 0 <= choice <= 7:
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        if choice == 0:
            return False

        elif choice == 1:  # Database integrity check
            print("\nRunning database integrity check...")

            issues = []

            # Check for courses with invalid enrollment
            cursor.execute("""
            SELECT id, course_code, current_enrollment, max_enrollment
            FROM courses
            WHERE current_enrollment > max_enrollment
            """)

            over_enrolled = cursor.fetchall()
            if over_enrolled:
                issues.append(f"Found {len(over_enrolled)} courses with enrollment over capacity")
                for course in over_enrolled:
                    print(f"  - {course[1]}: {course[2]}/{course[3]} enrolled")

            # Check for orphaned prerequisites
            cursor.execute("""
            SELECT cp.id, cp.course_id, cp.prerequisite_course_id
            FROM course_prerequisites cp
            LEFT JOIN courses c1 ON cp.course_id = c1.id
            LEFT JOIN courses c2 ON cp.prerequisite_course_id = c2.id
            WHERE c1.id IS NULL OR c2.id IS NULL
            """)

            orphaned_prereqs = cursor.fetchall()
            if orphaned_prereqs:
                issues.append(f"Found {len(orphaned_prereqs)} orphaned prerequisite records")

            # Check for invalid schedules
            cursor.execute("""
            SELECT cs.id, cs.course_id, cs.instructor_id
            FROM course_schedule cs
            LEFT JOIN courses c ON cs.course_id = c.id
            LEFT JOIN instructors i ON cs.instructor_id = i.id
            WHERE c.id IS NULL OR (cs.instructor_id IS NOT NULL AND i.id IS NULL)
            """)

            invalid_schedules = cursor.fetchall()
            if invalid_schedules:
                issues.append(f"Found {len(invalid_schedules)} invalid schedule records")

            if not issues:
                print("✓ Database integrity check completed - no issues found")
            else:
                print(f"⚠ Found {len(issues)} integrity issues:")
                for issue in issues:
                    print(f"  - {issue}")

        elif choice == 2:  # Clean up orphaned records
            print("\nCleaning up orphaned records...")

            # Remove orphaned prerequisites
            cursor.execute("""
            DELETE FROM course_prerequisites
            WHERE course_id NOT IN (SELECT id FROM courses)
               OR prerequisite_course_id NOT IN (SELECT id FROM courses)
            """)
            deleted_prereqs = cursor.rowcount

            # Remove orphaned schedules
            cursor.execute("""
            DELETE FROM course_schedule
            WHERE course_id NOT IN (SELECT id FROM courses)
            """)
            deleted_schedules = cursor.rowcount

            # Remove orphaned waitlists
            cursor.execute("""
            DELETE FROM course_waitlist
            WHERE course_id NOT IN (SELECT id FROM courses)
            """)
            deleted_waitlists = cursor.rowcount

            # Remove orphaned history
            cursor.execute("""
            DELETE FROM course_history
            WHERE course_id NOT IN (SELECT id FROM courses)
            """)
            deleted_history = cursor.rowcount

            conn.commit()

            print(f"✓ Cleanup completed:")
            print(f"  - Removed {deleted_prereqs} orphaned prerequisites")
            print(f"  - Removed {deleted_schedules} orphaned schedules")
            print(f"  - Removed {deleted_waitlists} orphaned waitlist entries")
            print(f"  - Removed {deleted_history} orphaned history records")

        elif choice == 3:  # Recalculate enrollment numbers
            print("\nRecalculating enrollment numbers...")

            # Note: This would normally query a student enrollment table
            # For now, we'll validate current numbers
            cursor.execute("""
            SELECT id, course_code, current_enrollment, max_enrollment
            FROM courses
            WHERE current_enrollment < 0 OR current_enrollment > max_enrollment
            """)

            invalid_enrollments = cursor.fetchall()

            if invalid_enrollments:
                print(f"Found {len(invalid_enrollments)} courses with invalid enrollment:")
                for course in invalid_enrollments:
                    print(f"  - {course[1]}: {course[2]}/{course[3]}")

                reset_option = input("Reset invalid enrollments to 0? (y/n): ").strip().lower()
                if reset_option == 'y':
                    cursor.execute("""
                    UPDATE courses
                    SET current_enrollment = 0, updated_at = ?
                    WHERE current_enrollment < 0 OR current_enrollment > max_enrollment
                    """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))

                    conn.commit()
                    print("✓ Invalid enrollments reset to 0")
            else:
                print("✓ All enrollment numbers are valid")

        elif choice == 4:  # Archive old course history
            print("\nArchiving old course history...")

            # Archive history older than 1 year
            one_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

            cursor.execute("""
            SELECT COUNT(*) FROM course_history
            WHERE changed_at < ?
            """, (one_year_ago,))

            old_records = cursor.fetchone()[0]

            if old_records > 0:
                print(f"Found {old_records} history records older than 1 year")

                archive_option = input("Archive these records? (y/n): ").strip().lower()
                if archive_option == 'y':
                    # In a real system, you might export to a file first
                    cursor.execute("""
                    DELETE FROM course_history
                    WHERE changed_at < ?
                    """, (one_year_ago,))

                    conn.commit()
                    print(f"✓ Archived {old_records} old history records")
            else:
                print("✓ No old history records found")

        elif choice == 5:  # Database statistics
            print("\nDatabase Statistics:")
            print("=" * 30)

            # Table sizes
            tables = ['courses', 'course_prerequisites', 'course_schedule',
                     'instructors', 'course_waitlist', 'course_history']

            for table in tables:
                safe_table = validate_table_name(table)
                cursor.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
                count = cursor.fetchone()[0]
                print(f"{table}: {count} records")

            # Database file size
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]

            db_size_mb = (page_count * page_size) / (1024 * 1024)
            print(f"\nDatabase size: {db_size_mb:.2f} MB")

        elif choice == 6:  # Rebuild search indexes
            print("\nRebuilding search indexes...")

            # SQLite doesn't have explicit index rebuild, but we can analyze
            cursor.execute("ANALYZE")
            conn.commit()

            print("✓ Database analysis completed")

        elif choice == 7:  # Export database backup
            print("\nExporting database backup...")

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"course_db_backup_{timestamp}.sql"

            # Simple backup by dumping schema and data
            with open(backup_file, 'w') as f:
                for line in conn.iterdump():
                    f.write('%s\n' % line)

            print(f"✓ Database backup saved as {backup_file}")

        return True

    except sqlite3.Error as e:
        print(f"Database error during maintenance: {e}")
        return False
    except Exception as e:
        print(f"Error during maintenance: {e}")
        return False
    finally:
        if conn:
            conn.close()
