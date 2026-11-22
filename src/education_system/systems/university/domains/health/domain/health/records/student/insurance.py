from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation
from education_system.systems.university.domains.health.domain.health.records.db.audit import log_audit_event
from education_system.systems.university.domains.health.domain.health.services import get_user_student_id


def view_insurance_info(auth):
    if not (auth.check_permission('view_own_health_record') or auth.current_user['role'] in ['admin', 'health_provider']):
        print("You don't have permission to view insurance information.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    if auth.current_user['role'] in ['admin', 'health_provider']:
        student_id = input("Enter student ID: ")

        cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
        student = cursor.fetchone()
        if not student:
            print("Error: Student ID not found.")
            conn.close()
            return

        print(f"Insurance information for: {student[0]} {student[1]}")
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return

    cursor.execute('''
    SELECT insurance_provider, policy_number, group_number, subscriber_name,
           relationship_to_subscriber, effective_date, expiry_date, created_at
    FROM insurance_information
    WHERE student_id = ?
    ORDER BY created_at DESC
    ''', (student_id,))

    insurance_records = cursor.fetchall()

    if not insurance_records:
        print("No insurance information found.")
        conn.close()
        return

    print("\n===== Insurance Information =====")
    for record in insurance_records:
        provider, policy_num, group_num, subscriber, relationship, effective, expiry, created = record

        print(f"\nInsurance Provider: {provider}")
        print(f"Policy Number: {policy_num}")
        print(f"Group Number: {group_num}")
        print(f"Subscriber: {subscriber}")
        print(f"Relationship: {relationship}")
        print(f"Effective Date: {effective}")
        print(f"Expiry Date: {expiry}")
        print(f"Last Updated: {created}")

        # Check if expired
        today = datetime.now().strftime('%Y-%m-%d')
        if expiry and expiry < today:
            print("⚠️  EXPIRED - Update needed")
        elif expiry and (datetime.strptime(expiry, '%Y-%m-%d') - datetime.now()).days <= 30:
            print("🟡 EXPIRES SOON")
        else:
            print("✅ CURRENT")

        print("-" * 30)

    conn.close()



def update_insurance_info(auth):
    if not (auth.check_permission('view_own_health_record') or auth.current_user['role'] in ['admin', 'health_provider']):
        print("You don't have permission to update insurance information.")
        return

    backup_before_operation('update_insurance_info')

    conn = get_connection()
    cursor = conn.cursor()

    if auth.current_user['role'] in ['admin', 'health_provider']:
        student_id = input("Enter student ID: ")

        cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
        student = cursor.fetchone()
        if not student:
            print("Error: Student ID not found.")
            conn.close()
            return

        print(f"Updating insurance for: {student[0]} {student[1]}")
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return

    # Check if insurance record exists
    cursor.execute('''
    SELECT id, insurance_provider, policy_number, group_number
    FROM insurance_information
    WHERE student_id = ?
    ORDER BY created_at DESC LIMIT 1
    ''', (student_id,))

    existing_record = cursor.fetchone()

    if existing_record:
        print(f"\nCurrent insurance: {existing_record[1]} (Policy: {existing_record[2]})")
        update_existing = input("Update existing record? (y/n): ").lower()
        if update_existing == 'y':
            insurance_id = existing_record[0]
        else:
            insurance_id = None
    else:
        insurance_id = None

    insurance_provider = input("Insurance provider: ")
    policy_number = input("Policy number: ")
    group_number = input("Group number: ")
    subscriber_name = input("Subscriber name: ")

    relationships = ['Self', 'Parent', 'Spouse', 'Guardian', 'Other']
    print("\nRelationship to subscriber:")
    for i, relationship in enumerate(relationships):
        print(f"{i+1}. {relationship}")

    while True:
        rel_choice = input("\nSelect relationship (1-5): ")
        if rel_choice.isdigit() and 1 <= int(rel_choice) <= len(relationships):
            relationship_to_subscriber = relationships[int(rel_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    while True:
        effective_date = input("Effective date (YYYY-MM-DD): ")
        try:
            datetime.strptime(effective_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    while True:
        expiry_date = input("Expiry date (YYYY-MM-DD): ")
        try:
            datetime.strptime(expiry_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if insurance_id:
        # Update existing record
        cursor.execute('''
        UPDATE insurance_information
        SET insurance_provider = ?, policy_number = ?, group_number = ?,
            subscriber_name = ?, relationship_to_subscriber = ?, effective_date = ?,
            expiry_date = ?, created_at = ?
        WHERE id = ?
        ''', (insurance_provider, policy_number, group_number, subscriber_name,
              relationship_to_subscriber, effective_date, expiry_date, created_at, insurance_id))

        log_audit_event(auth.current_user['id'], 'update_insurance_info', 'insurance', insurance_id, conn=conn)
        print("\nInsurance information updated successfully!")
    else:
        # Create new record
        cursor.execute('''
        INSERT INTO insurance_information
        (student_id, insurance_provider, policy_number, group_number, subscriber_name,
         relationship_to_subscriber, effective_date, expiry_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, insurance_provider, policy_number, group_number, subscriber_name,
              relationship_to_subscriber, effective_date, expiry_date, created_at))

        log_audit_event(auth.current_user['id'], 'add_insurance_info', 'insurance', cursor.lastrowid, conn=conn)
        print("\nInsurance information added successfully!")

    conn.commit()
    conn.close()





# ── Non-interactive helpers (the Health Portal "Insurance" screen) ────────
# Take an open connection, raise on bad input, do not commit.

RELATIONSHIPS = ('Self', 'Parent', 'Spouse', 'Guardian', 'Other')
INSURANCE_FIELDS = ('insurance_provider', 'policy_number', 'group_number', 'subscriber_name',
                    'relationship_to_subscriber', 'effective_date', 'expiry_date')


def cover_status(expiry_date, today=None) -> str:
    """'expired', 'expires soon' (30 days) or 'current' — the CLI's flags."""
    if not expiry_date:
        return 'current'
    today = today or datetime.now()
    try:
        expiry = datetime.strptime(str(expiry_date)[:10], '%Y-%m-%d')
    except ValueError:
        return 'unknown'
    if expiry.date() < today.date():
        return 'expired'
    if (expiry - today).days <= 30:
        return 'expires soon'
    return 'current'


def list_insurance(conn, student_id) -> list[dict]:
    rows = conn.execute(
        "SELECT id, " + ", ".join(INSURANCE_FIELDS) + ", created_at FROM insurance_information "
        "WHERE student_id = ? ORDER BY created_at DESC, id DESC", (str(student_id),)).fetchall()
    out = []
    for row in rows:
        item = dict(zip(("id",) + INSURANCE_FIELDS + ("created_at",), tuple(row)))
        item["status"] = cover_status(item["expiry_date"])
        out.append(item)
    return out


def save_insurance(conn, student_id, values: dict, *, by_user_id, insurance_id=None) -> int:
    """Add a policy, or update ``insurance_id`` (which must be the student's).
    Audited in ``conn``'s transaction. Returns the row id."""
    student_id = str(student_id or "").strip()
    if conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                    (student_id,)).fetchone() is None:
        raise LookupError(f"Student {student_id} not found")
    data = {k: (str(values.get(k) or "").strip() or None) for k in INSURANCE_FIELDS}
    if not data['insurance_provider'] or not data['policy_number']:
        raise ValueError("Insurance provider and policy number are required")
    if data['relationship_to_subscriber'] and data['relationship_to_subscriber'] not in RELATIONSHIPS:
        raise ValueError(f"Relationship must be one of {', '.join(RELATIONSHIPS)}")
    for key in ('effective_date', 'expiry_date'):
        if data[key]:
            datetime.strptime(data[key], '%Y-%m-%d')
    if data['effective_date'] and data['expiry_date'] and data['expiry_date'] < data['effective_date']:
        raise ValueError("The expiry date is before the effective date")
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if insurance_id:
        cur = conn.execute(
            "UPDATE insurance_information SET " + ", ".join(f"{k} = ?" for k in INSURANCE_FIELDS)
            + ", created_at = ? WHERE id = ? AND student_id = ?",
            (*data.values(), stamp, int(insurance_id), student_id))
        if cur.rowcount == 0:
            raise LookupError(f"Insurance record {insurance_id} is not this student's")
        log_audit_event(by_user_id, 'update_insurance_info', 'insurance', insurance_id, conn=conn)
        return int(insurance_id)
    cur = conn.execute(
        "INSERT INTO insurance_information (student_id, " + ", ".join(INSURANCE_FIELDS)
        + ", created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (student_id, *data.values(), stamp))
    log_audit_event(by_user_id, 'add_insurance_info', 'insurance', cur.lastrowid, conn=conn)
    return cur.lastrowid
