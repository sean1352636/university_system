from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation
from education_system.systems.university.domains.health.domain.health.records.db.audit import log_audit_event
from education_system.systems.university.domains.health.domain.health.services import get_user_student_id


# A confidential record's description is sealed at rest
# (application/health/sealed_fields).
from education_system.systems.university.domains.health.application.health import (  # noqa: E402
    sealed_fields as _sealed,
)

def add_health_record(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to add health records.")
        return

    backup_before_operation('add_health_record')

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input("Enter student ID: ")

    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print("Error: Student ID not found.")
        conn.close()
        return

    # Record types
    record_types = [
        'General Medical',
        'Injury Treatment',
        'Mental Health',
        'Chronic Condition Management',
        'Preventive Care',
        'Emergency Treatment',
        'Follow-up Visit',
        'Specialist Consultation'
    ]

    print("\nRecord Types:")
    for i, record_type in enumerate(record_types):
        print(f"{i+1}. {record_type}")

    while True:
        type_choice = input("\nSelect record type (1-8): ")
        if type_choice.isdigit() and 1 <= int(type_choice) <= len(record_types):
            record_type = record_types[int(type_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    while True:
        record_date = input("Record date (YYYY-MM-DD) [today]: ").strip()
        if not record_date:
            record_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(record_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    description = input("Description: ")
    provider = input(f"Provider [Dr. {auth.current_user['username']}]: ").strip()
    if not provider:
        provider = f"Dr. {auth.current_user['username']}"

    confidential = input("Mark as confidential? (y/n): ").lower() == 'y'

    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO health_records
    (student_id, record_type, record_date, description, provider, confidential, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, record_type, record_date,
          _sealed.seal_value("health_records", "description", description,
                             confidential=confidential),
          provider, 1 if confidential else 0, created_at))

    # Audited in the same transaction: if the audit can't be written, the
    # record isn't either.
    log_audit_event(auth.current_user['id'], 'add_health_record', 'health_record',
                    cursor.lastrowid, conn=conn)
    conn.commit()
    print("\nHealth record added successfully!")
    conn.close()



def view_health_records(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view health records.")
        return

    conn = get_connection()
    from education_system.systems.university.domains.health.application.health import (
        workflow as _workflow,
    )
    _workflow.ensure_schema(conn)          # health_records.archived
    cursor = conn.cursor()

    if auth.check_permission('view_any_health_record'):
        student_id = input("Enter student ID (leave blank for all recent): ").strip()

        if student_id:
            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
            if cursor.fetchone()[0] == 0:
                print("Error: Student ID not found.")
                conn.close()
                return

            cursor.execute('''
            SELECT hr.id, hr.record_type, hr.record_date, hr.description, hr.provider,
                   hr.confidential, hr.created_at
            FROM health_records hr
            WHERE hr.student_id = ? AND COALESCE(hr.archived, 0) = 0
            ORDER BY hr.record_date DESC
            LIMIT 100
            ''', (student_id,))
        else:
            cursor.execute('''
            SELECT hr.id, s.student_id, s.first_name, s.last_name, hr.record_type,
                   hr.record_date, hr.description, hr.provider, hr.confidential
            FROM health_records hr
            JOIN students s ON hr.student_id = s.student_id
            WHERE COALESCE(hr.archived, 0) = 0
            ORDER BY hr.record_date DESC
            LIMIT 100
            ''')
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return

        cursor.execute('''
        SELECT id, record_type, record_date, description, provider,
               confidential, created_at
        FROM health_records
        WHERE student_id = ? AND COALESCE(archived, 0) = 0
        ORDER BY record_date DESC
        ''', (student_id,))

    records = cursor.fetchall()

    if not records:
        print("No health records found.")
        conn.close()
        return

    # Which query ran decides how each row unpacks, so settle it once, before
    # the loop. It used to be re-tested per row against ``student_id`` — which
    # the all-records branch below then reassigned from the row itself, so from
    # the second row on the test flipped and a 9-column row was unpacked into
    # 7 names: "too many values to unpack (expected 7)".
    viewing_all_students = auth.check_permission('view_any_health_record') and not student_id

    print("\n===== Health Records =====")
    for record in records:
        if viewing_all_students:
            # All records view
            hr_id, row_student_id, first_name, last_name, record_type, record_date, description, provider, confidential = record
            print(f"\nID: {hr_id}")
            print(f"Student: {first_name} {last_name} (ID: {row_student_id})")
            print(f"Type: {record_type}")
            print(f"Date: {record_date}")
            print(f"Description: {_sealed.reveal(description)}")
            print(f"Provider: {provider}")
            if confidential:
                print("🔒 CONFIDENTIAL")
        else:
            # Specific student view
            hr_id, record_type, record_date, description, provider, confidential, created_at = record
            print(f"\nID: {hr_id}")
            print(f"Type: {record_type}")
            print(f"Date: {record_date}")
            print(f"Description: {_sealed.reveal(description)}")
            print(f"Provider: {provider}")
            print(f"Created: {created_at}")
            if confidential:
                print("🔒 CONFIDENTIAL")

        print("-" * 30)

    conn.close()



def update_health_record(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to update health records.")
        return

    backup_before_operation('update_health_record')

    conn = get_connection()
    cursor = conn.cursor()

    record_id = input("Enter health record ID to update: ")

    cursor.execute('''
    SELECT hr.id, s.student_id, s.first_name, s.last_name, hr.record_type,
           hr.record_date, hr.description, hr.provider, hr.confidential
    FROM health_records hr
    JOIN students s ON hr.student_id = s.student_id
    WHERE hr.id = ?
    ''', (record_id,))

    record = cursor.fetchone()

    if not record:
        print("Error: Health record not found.")
        conn.close()
        return

    hr_id, student_id, first_name, last_name, record_type, record_date, description, provider, confidential = record
    description = _sealed.reveal(description)

    print("\nCurrent Record Details:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Type: {record_type}")
    print(f"Date: {record_date}")
    print(f"Provider: {provider}")
    print(f"Description: {description}")
    print(f"Confidential: {'Yes' if confidential else 'No'}")

    print("\nEnter new values (press Enter to keep current):")

    new_description = input(f"Description [{description}]: ").strip()
    if not new_description:
        new_description = description

    new_provider = input(f"Provider [{provider}]: ").strip()
    if not new_provider:
        new_provider = provider

    new_confidential_input = input(f"Confidential ({'Yes' if confidential else 'No'}) [y/n]: ").strip().lower()
    if new_confidential_input == 'y':
        new_confidential = 1
    elif new_confidential_input == 'n':
        new_confidential = 0
    else:
        new_confidential = confidential

    cursor.execute('''
    UPDATE health_records
    SET description = ?, provider = ?, confidential = ?
    WHERE id = ?
    ''', (_sealed.seal_value("health_records", "description", new_description,
                             confidential=new_confidential),
          new_provider, new_confidential, record_id))

    log_audit_event(auth.current_user['id'], 'update_health_record', 'health_record', record_id,
                    conn=conn)
    conn.commit()
    print("\nHealth record updated successfully!")
    conn.close()



def delete_health_record(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to delete health records.")
        return

    backup_before_operation('delete_health_record')

    conn = get_connection()
    cursor = conn.cursor()

    record_id = input("Enter health record ID to delete: ")

    cursor.execute('''
    SELECT hr.id, s.student_id, s.first_name, s.last_name, hr.record_type,
           hr.record_date, hr.description
    FROM health_records hr
    JOIN students s ON hr.student_id = s.student_id
    WHERE hr.id = ?
    ''', (record_id,))

    record = cursor.fetchone()

    if not record:
        print("Error: Health record not found.")
        conn.close()
        return

    hr_id, student_id, first_name, last_name, record_type, record_date, description = record

    print("\nRecord to delete:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Type: {record_type}")
    print(f"Date: {record_date}")
    print(f"Description: {_sealed.reveal(description)}")

    confirm = input("\nAre you sure you want to delete this record? (yes/no): ").lower()
    if confirm != 'yes':
        print("Deletion cancelled.")
        conn.close()
        return
    reason = input("Reason for deleting (recorded in the audit): ").strip()
    if len(reason) < 5:
        print("A reason is required. Deletion cancelled.")
        conn.close()
        return

    # Archived (soft delete), never hard-deleted: clinicians only, with the
    # reason, audited in the same transaction (application/health/workflow).
    from education_system.systems.university.domains.health.application.health import (
        access as _access, workflow as _workflow,
    )
    try:
        _workflow.archive_health_record(conn, _access.from_user(auth.current_user), hr_id, reason)
        conn.commit()
    except (PermissionError, ValueError, LookupError) as exc:
        conn.rollback()
        print(f"Not removed: {exc}")
        conn.close()
        return
    except Exception:
        conn.rollback()
        conn.close()
        raise
    print("\nHealth record archived (hidden from lists, kept for the retention period).")
    conn.close()



