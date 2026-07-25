"""
Admin tools for CLI system.

Provides administrative utilities, database statistics, and system configuration.
"""

from education_system.systems.university.interfaces.cli.shell.imports import (
    logging, sqlite3, datetime, DB_PATH, logger, _t,
    log_activity, get_auth, validate_table_name, SQLIdentifierError
)

from education_system.systems.university.interfaces.cli.shell.database_manager import (
    DatabaseError, validate_database_integrity, fix_duplicate_emails,
    emergency_fix_database
)
from education_system.systems.university.services.analytics.student_analytics import StudentAnalytics
from education_system.systems.university.infrastructure.utils.batch_operations import BatchOperationManager

auth = None

def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)


def display_admin_tools_menu():
    """Display admin tools menu for database maintenance"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to access admin tools.")
        return

    if auth.current_user['role'] != 'admin':
        print("Only administrators can access these tools.")
        return

    while True:
        print("\nAdmin Tools:")
        print("============")
        print("1. Validate Database Integrity")
        print("2. Fix Duplicate Emails")
        print("3. Fix Orphaned Records")
        print("4. Emergency Database Fix")
        print("5. View Database Statistics")
        print("6. Back to Main Menu")

        choice = input("Enter your choice (1-6): ")

        if choice == '1':
            validate_database_integrity()
        elif choice == '2':
            fix_duplicate_emails()
        elif choice == '3':
            auth.fix_database_consistency()
        elif choice == '4':
            emergency_fix_database()
        elif choice == '5':
            display_database_statistics()
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")


def display_database_statistics():
    """Display database statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        print("\nDatabase Statistics:")
        print("=" * 40)

        # Count records in main tables
        tables = ['students', 'users', 'user_accounts', 'student_modules', 'modules']

        for table in tables:
            try:
                # Validate table name to prevent SQL injection
                validated_table = validate_table_name(table)
                cursor.execute('SELECT COUNT(*) FROM [' + validated_table + ']')
                count = cursor.fetchone()[0]
                print(f"{table.capitalize()}: {count} records")
            except SQLIdentifierError as e:
                print(f"{table.capitalize()}: Invalid table name - {e}")
            except sqlite3.Error:
                print(f"{table.capitalize()}: Table not found")

        # Check for duplicates
        print("\nDuplicate Check:")
        cursor.execute('SELECT COUNT(DISTINCT email) as unique_emails, COUNT(*) as total_users FROM users')
        unique_emails, total_users = cursor.fetchone()

        if unique_emails != total_users:
            print(f"⚠️  Email duplicates: {total_users - unique_emails} duplicate(s) found")
        else:
            print("✅ No email duplicates found")

        cursor.execute('SELECT COUNT(DISTINCT username) as unique_usernames, COUNT(*) as total_users FROM users')
        unique_usernames, total_users = cursor.fetchone()

        if unique_usernames != total_users:
            print(f"⚠️  Username duplicates: {total_users - unique_usernames} duplicate(s) found")
        else:
            print("✅ No username duplicates found")

        # Check for orphaned records
        cursor.execute('''
        SELECT COUNT(*) FROM users u
        LEFT JOIN user_accounts ua ON u.id = ua.user_id
        WHERE ua.user_id IS NULL
        ''')
        orphaned_users = cursor.fetchone()[0]

        cursor.execute('''
        SELECT COUNT(*) FROM user_accounts ua
        LEFT JOIN users u ON ua.user_id = u.id
        WHERE u.id IS NULL
        ''')
        orphaned_accounts = cursor.fetchone()[0]

        print("\nOrphaned Records:")
        print(f"Users without accounts: {orphaned_users}")
        print(f"Accounts without users: {orphaned_accounts}")

        conn.close()
        print("=" * 40)

    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error retrieving database statistics: {e}")


def display_analytics_menu():
    """Display student analytics dashboard"""
    analytics = StudentAnalytics()
    analytics.display_main_menu()


def display_batch_menu():
    """Standalone function to display batch operations menu for import into main.py"""
    batch_manager = BatchOperationManager()
    batch_manager.display_batch_menu()


__all__ = [
    'display_admin_tools_menu',
    'display_database_statistics',
    'display_analytics_menu',
    'display_batch_menu',
]
