from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.infrastructure import paths
from datetime import datetime, timedelta


def system_maintenance(auth):
    """System maintenance functions"""
    print("\nSystem Maintenance")
    print("==================")
    print("1. Database cleanup")
    print("2. Rebuild search indexes")
    print("3. Check data integrity")
    print("4. Backup database")
    print("5. Return to system management")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1':
        database_cleanup(auth)
    elif choice == '2':
        rebuild_search_indexes(auth)
    elif choice == '3':
        check_data_integrity(auth)
    elif choice == '4':
        backup_database(auth)

def database_cleanup(auth):
    """Clean up old data"""
    print("\nDatabase Cleanup")
    print("================")

    days = input("Delete tickets older than how many days? (default: 365): ").strip()
    try:
        days = int(days) if days else 365
    except ValueError:
        days = 365

    confirm = input(f"This will delete tickets older than {days} days. Continue? (y/n): ").strip().lower()

    if confirm == 'y':
        conn = get_connection()
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        cursor.execute('''
        DELETE FROM support_tickets
        WHERE status = 'closed' AND created_at < ?
        ''', (cutoff_date,))

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        print(f"Deleted {deleted_count} old tickets.")
    else:
        print("Cleanup cancelled.")

def rebuild_search_indexes(auth):
    """Rebuild search indexes"""
    print("\nRebuilding search indexes...")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
        UPDATE knowledge_base
        SET search_keywords = LOWER(title || ' ' || content || ' ' || COALESCE(tags, ''))
        ''')

        conn.commit()
        print("Search indexes rebuilt successfully!")

    except sqlite3.Error as e:
        print(f"Error rebuilding indexes: {e}")
    finally:
        conn.close()

def check_data_integrity(auth):
    """Check database integrity"""
    print("\nChecking Data Integrity")
    print("======================")

    conn = get_connection()
    cursor = conn.cursor()

    issues = []

    cursor.execute('''
    SELECT COUNT(*) FROM support_tickets t
    LEFT JOIN users u ON t.user_id = u.id
    WHERE u.id IS NULL
    ''')

    orphaned_tickets = cursor.fetchone()[0]
    if orphaned_tickets > 0:
        issues.append(f"{orphaned_tickets} tickets with invalid user_id")

    cursor.execute('''
    SELECT COUNT(*) FROM ticket_replies r
    LEFT JOIN support_tickets t ON r.ticket_id = t.ticket_id
    WHERE t.ticket_id IS NULL
    ''')

    orphaned_replies = cursor.fetchone()[0]
    if orphaned_replies > 0:
        issues.append(f"{orphaned_replies} replies with invalid ticket_id")

    conn.close()

    if issues:
        print("Data integrity issues found:")
        for issue in issues:
            print(f"- {issue}")
    else:
        print("No data integrity issues found.")

def backup_database(auth):
    """Backup database"""
    print("\nBacking up database...")

    try:
        import shutil
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"student_records_backup_{timestamp}.db"

        db_path = paths.DEFAULT_DB_PATH
        shutil.copy2(db_path, backup_filename)
        print(f"Database backed up to {backup_filename}")

    except Exception as e:
        print(f"Error backing up database: {e}")
