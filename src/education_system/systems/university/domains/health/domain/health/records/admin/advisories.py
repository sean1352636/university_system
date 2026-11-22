from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation
from education_system.systems.university.domains.health.domain.health.records.db.audit import log_audit_event
from education_system.systems.university.infrastructure.email import (
    send_appointment_confirmation,
    send_health_notification,
)


def add_health_advisory(auth):
    if not auth.check_permission('issue_health_advisories'):
        print("You don't have permission to issue health advisories.")
        return

    backup_before_operation('add_health_advisory')

    conn = get_connection()
    cursor = conn.cursor()

    title = input("Advisory title: ")

    # Advisory types
    advisory_types = [
        'Disease Outbreak',
        'Safety Alert',
        'Vaccination Reminder',
        'Wellness Tip',
        'Emergency Notice',
        'Policy Update',
        'Seasonal Health',
        'General Information'
    ]

    print("\nAdvisory Types:")
    for i, advisory_type in enumerate(advisory_types):
        print(f"{i+1}. {advisory_type}")

    while True:
        type_choice = input("\nSelect advisory type (1-8): ")
        if type_choice.isdigit() and 1 <= int(type_choice) <= len(advisory_types):
            advisory_type = advisory_types[int(type_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    content = input("Advisory content: ")

    # Priority levels
    priority_levels = ['Low', 'Medium', 'High', 'Critical']
    print("\nPriority Levels:")
    for i, priority in enumerate(priority_levels):
        print(f"{i+1}. {priority}")

    while True:
        priority_choice = input("\nSelect priority (1-4): ")
        if priority_choice.isdigit() and 1 <= int(priority_choice) <= len(priority_levels):
            priority = priority_levels[int(priority_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    # Target audience
    target_audiences = ['All Students', 'Specific Groups', 'Staff Only', 'High Risk Students']
    print("\nTarget Audience:")
    for i, audience in enumerate(target_audiences):
        print(f"{i+1}. {audience}")

    while True:
        audience_choice = input("\nSelect target audience (1-4): ")
        if audience_choice.isdigit() and 1 <= int(audience_choice) <= len(target_audiences):
            target_audience = target_audiences[int(audience_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    while True:
        effective_date = input("Effective date (YYYY-MM-DD) [today]: ").strip()
        if not effective_date:
            effective_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(effective_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    while True:
        expiry_date = input("Expiry date (YYYY-MM-DD) [leave blank for no expiry]: ").strip()
        if not expiry_date:
            expiry_date = None
            break
        try:
            datetime.strptime(expiry_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO health_advisories
    (title, advisory_type, content, priority, target_audience, effective_date,
     expiry_date, issued_by, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, advisory_type, content, priority, target_audience, effective_date,
          expiry_date, auth.current_user['username'], 'active', created_at))

    conn.commit()
    advisory_id = cursor.lastrowid

    log_audit_event(auth.current_user['id'], 'issue_health_advisory', 'health_advisory', advisory_id)

    print("\nHealth advisory issued successfully!")
    print(f"Advisory ID: {advisory_id}")

    # Automatically send email notifications to the target audience (the
    # same recipients and sender as the Health Portal screen).
    try:
        queued, failed = notify_advisory(advisory_recipients(conn, target_audience),
                                         title, content, priority)
        print(f"✉️  Notifications queued for {queued} recipients"
              + (f" ({failed} could not be queued)" if failed else ""))
        from education_system.systems.university.domains.health.application.health import notices
        print(notices.delivery_note())
        if priority == 'Critical':
            print("🚨 CRITICAL ADVISORY - notifications queued for all relevant parties")
    except Exception as e:
        print(f"Warning: Could not send email notifications: {e}")

    conn.close()



def view_health_advisories(auth):
    if not (auth.check_permission('view_health_advisories') or auth.check_permission('issue_health_advisories')):
        print("You don't have permission to view health advisories.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nFilter options:")
    print("1. All active advisories")
    print("2. By priority")
    print("3. By type")
    print("4. Recent advisories (last 30 days)")

    filter_choice = input("\nSelect filter (1-4): ")

    if filter_choice == '1':
        cursor.execute('''
        SELECT id, title, advisory_type, priority, target_audience, effective_date,
               expiry_date, issued_by, status
        FROM health_advisories
        WHERE status = 'active' AND (expiry_date IS NULL OR expiry_date >= ?)
        ORDER BY priority DESC, effective_date DESC
        ''', (datetime.now().strftime('%Y-%m-%d'),))

    elif filter_choice == '2':
        priority = input("Enter priority (Low/Medium/High/Critical): ")
        cursor.execute('''
        SELECT id, title, advisory_type, priority, target_audience, effective_date,
               expiry_date, issued_by, status
        FROM health_advisories
        WHERE priority = ? AND status = 'active'
        ORDER BY effective_date DESC
        ''', (priority,))

    elif filter_choice == '3':
        advisory_type = input("Enter advisory type: ")
        cursor.execute('''
        SELECT id, title, advisory_type, priority, target_audience, effective_date,
               expiry_date, issued_by, status
        FROM health_advisories
        WHERE advisory_type LIKE ? AND status = 'active'
        ORDER BY effective_date DESC
        ''', (f'%{advisory_type}%',))

    elif filter_choice == '4':
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute('''
        SELECT id, title, advisory_type, priority, target_audience, effective_date,
               expiry_date, issued_by, status
        FROM health_advisories
        WHERE effective_date >= ?
        ORDER BY effective_date DESC
        ''', (thirty_days_ago,))

    else:
        print("Invalid choice.")
        conn.close()
        return

    advisories = cursor.fetchall()

    if not advisories:
        print("No health advisories found.")
        conn.close()
        return

    print("\n===== Health Advisories =====")
    for advisory in advisories:
        adv_id, title, adv_type, priority, target_audience, effective_date, expiry_date, issued_by, status = advisory

        print(f"\nID: {adv_id}")
        print(f"Title: {title}")
        print(f"Type: {adv_type}")
        print(f"Priority: {priority}")
        print(f"Target: {target_audience}")
        print(f"Effective: {effective_date}")
        print(f"Expires: {expiry_date if expiry_date else 'No expiry'}")
        print(f"Issued by: {issued_by}")

        # Priority indicators
        if priority == 'Critical':
            print("🚨 CRITICAL ADVISORY")
        elif priority == 'High':
            print("🔴 HIGH PRIORITY")
        elif priority == 'Medium':
            print("🟡 MEDIUM PRIORITY")

        # Show content if requested
        view_content = input("View full content? (y/n): ").lower()
        if view_content == 'y':
            cursor.execute('SELECT content FROM health_advisories WHERE id = ?', (adv_id,))
            content = cursor.fetchone()[0]
            print(f"Content: {content}")

        print("-" * 30)

    conn.close()





# ── Non-interactive helpers (the Health Portal "Health Advisories" screen) ─
# Take an open connection, raise on bad input, do not commit (e-mails go
# after the caller's commit, via notify_advisory).

ADVISORY_TYPES = ('Disease Outbreak', 'Safety Alert', 'Vaccination Reminder', 'Wellness Tip',
                  'Emergency Notice', 'Policy Update', 'Seasonal Health', 'General Information')
PRIORITIES = ('Low', 'Medium', 'High', 'Critical')
AUDIENCES = ('All Students', 'Specific Groups', 'Staff Only', 'High Risk Students')
ADVISORY_COLUMNS = ('id', 'title', 'advisory_type', 'content', 'priority', 'target_audience',
                    'effective_date', 'expiry_date', 'issued_by', 'status', 'created_at')
_PRIORITY_ORDER = "CASE priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END"


def _day(value, label):
    value = str(value or "").strip()
    if not value:
        return None
    try:
        datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        raise ValueError(f"{label} must be YYYY-MM-DD") from None
    return value


def issue_advisory(conn, *, title, advisory_type, content, priority, target_audience, issued_by,
                   by_user_id=None, effective_date=None, expiry_date=None) -> int:
    """Issue one advisory (status 'active'); audited. Returns its id."""
    title, content = str(title or "").strip(), str(content or "").strip()
    if not title or not content:
        raise ValueError("A title and the advisory text are required")
    for value, allowed, label in ((advisory_type, ADVISORY_TYPES, "type"),
                                  (priority, PRIORITIES, "priority"),
                                  (target_audience, AUDIENCES, "audience")):
        if value not in allowed:
            raise ValueError(f"Choose a {label}: {', '.join(allowed)}")
    effective = _day(effective_date, "Effective date") or datetime.now().strftime('%Y-%m-%d')
    expiry = _day(expiry_date, "Expiry date")
    if expiry and expiry < effective:
        raise ValueError("The expiry date is before the effective date")
    cur = conn.execute(
        "INSERT INTO health_advisories (title, advisory_type, content, priority, target_audience, "
        "effective_date, expiry_date, issued_by, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)",
        (title, advisory_type, content, priority, target_audience, effective, expiry,
         str(issued_by), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    log_audit_event(by_user_id or issued_by, 'issue_health_advisory', 'health_advisory',
                    cur.lastrowid, conn=conn)
    return cur.lastrowid


def expire_advisory(conn, advisory_id, *, by, by_user_id=None) -> bool:
    """Withdraw an advisory now (status 'expired', expiry today); audited."""
    today = datetime.now().strftime('%Y-%m-%d')
    cur = conn.execute("UPDATE health_advisories SET status = 'expired', "
                       "expiry_date = CASE WHEN expiry_date IS NULL OR expiry_date > ? THEN ? "
                       "ELSE expiry_date END WHERE id = ? AND status = 'active'",
                       (today, today, int(advisory_id)))
    if cur.rowcount:
        log_audit_event(by_user_id or by, 'expire_health_advisory', 'health_advisory',
                        advisory_id, {"by": str(by)}, conn=conn)
    return cur.rowcount > 0


def list_advisories(conn, *, published_only=False, for_students=False, priority=None,
                    advisory_type=None, recent_days=None, include_expired=True) -> list[dict]:
    """Advisories, most urgent first. ``published_only``: active, in effect
    today and not past expiry. ``for_students`` also leaves out the
    staff-only ones (what a student sees)."""
    today = datetime.now().strftime('%Y-%m-%d')
    where, args = ["1 = 1"], []
    if published_only:
        where.append("status = 'active' AND COALESCE(effective_date, '') <= ? "
                     "AND (expiry_date IS NULL OR expiry_date = '' OR expiry_date >= ?)")
        args += [today, today]
    elif not include_expired:
        where.append("status = 'active'")
    if for_students:
        where.append("COALESCE(target_audience, '') <> 'Staff Only'")
    if priority:
        where.append("priority = ?")
        args.append(priority)
    if advisory_type:
        where.append("advisory_type LIKE ?")
        args.append(f"%{advisory_type}%")
    if recent_days:
        where.append("effective_date >= ?")
        args.append((datetime.now() - timedelta(days=int(recent_days))).strftime('%Y-%m-%d'))
    rows = conn.execute(
        f"SELECT {', '.join(ADVISORY_COLUMNS)} FROM health_advisories WHERE "  # nosec B608
        f"{' AND '.join(where)} ORDER BY {_PRIORITY_ORDER}, effective_date DESC, id DESC",
        args).fetchall()
    return [dict(zip(ADVISORY_COLUMNS, tuple(r))) for r in rows]


def advisory_recipients(conn, target_audience) -> list[str]:
    """Student numbers (or staff ids) the CLI notifies for an audience."""
    if target_audience == 'High Risk Students':
        sql = ("SELECT DISTINCT mr.student_id FROM medical_records mr WHERE mr.record_type IN "
               "('chronic_condition', 'prescription') AND mr.student_id IN "
               "(SELECT student_id FROM students WHERE LOWER(status) = 'active')")
    elif target_audience == 'Staff Only':
        sql = ("SELECT id FROM users WHERE role IN ('staff', 'admin', 'instructor') "
               "AND is_active = 1")
    else:
        # Statuses are stored 'Active' (capitalised); compare case-blind.
        sql = "SELECT student_id FROM students WHERE LOWER(status) = 'active'"
    try:
        return [str(r[0]) for r in conn.execute(sql).fetchall()]
    except sqlite3.Error:
        return []


def notify_advisory(recipients, title, content, priority) -> tuple[int, int]:
    """E-mail the advisory (after commit); returns ``(queued, failed)``."""
    queued = failed = 0
    for recipient in recipients:
        try:
            if send_health_notification(recipient, title, content, priority) is not False:
                queued += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    return queued, failed
