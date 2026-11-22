from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system import paths
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
    """Purge the personal data of tickets past their retention period
    (``student_support.gdpr``: the administrators' retention policy per
    tier; safeguarding and crisis tickets and tickets on hold are never
    purged automatically). Administrators only."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        gdpr,
    )
    print("\nDatabase Cleanup")
    print("================")

    policy = gdpr.retention_policy()
    for tier, years in policy.items():
        print(f"  {tier.title()} tickets: " + (f"kept {years} years after closing" if years
                                               else "never purged automatically"))
    try:
        preview = gdpr.purge(auth, dry_run=True)
    except PermissionError as e:
        print(e)
        return
    if not preview['due']:
        print("No tickets are past their retention period.")
        return

    confirm = input(f"{len(preview['due'])} closed tickets are past their retention period. "
                    "Purge their personal data now? (y/n): ").strip().lower()
    if confirm == 'y':
        try:
            result = gdpr.purge(auth)
        except PermissionError as e:
            print(e)
            return
        print(f"Purged {result['purged']} old tickets ({result['files_deleted']} files).")
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

    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth,
    )
    if not support_auth.is_admin(auth):
        print("Only an administrator can check data integrity.")
        return

    # Counts only: no ticket text leaves this check.
    conn = get_connection()
    cursor = conn.cursor()

    issues = []

    cursor.execute('''
    SELECT COUNT(*) FROM support_tickets t
    LEFT JOIN users u ON u.username = t.requester_username
    WHERE u.id IS NULL
    ''')

    orphaned_tickets = cursor.fetchone()[0]
    if orphaned_tickets > 0:
        issues.append(f"{orphaned_tickets} tickets whose requester has no user account")

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
        # var/backups is the one place backups live; this used to drop the
        # file into whatever directory the process happened to start in.
        target_dir = paths.system_backup_dir("university", "database")
        target_dir.mkdir(parents=True, exist_ok=True)
        backup_path = target_dir / f"student_records_backup_{timestamp}.db"

        db_path = paths.UNIVERSITY_DEFAULT_DB_PATH
        shutil.copy2(db_path, backup_path)
        print(f"Database backed up to {backup_path}")

    except Exception as e:
        print(f"Error backing up database: {e}")
