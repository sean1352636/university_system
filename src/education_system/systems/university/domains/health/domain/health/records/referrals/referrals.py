import logging

from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation
from education_system.systems.university.domains.health.domain.health.records.db.audit import log_audit_event
from education_system.systems.university.domains.health.domain.health.services import specialist_directory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Notifying the student
# ---------------------------------------------------------------------------
# Referrals go through the university email system (infrastructure.email):
# render_template fills one of the JSON templates under
# assets/templates/email/campus_services/health/ and send_email stores the mail
# *and* raises the student's inbox message, so it appears in the Email module
# like any other university mail.

_TEMPLATE_DIR = "campus_services/health"
REFERRAL_CREATED_TEMPLATE = f"{_TEMPLATE_DIR}/referral_created"
REFERRAL_UPDATED_TEMPLATE = f"{_TEMPLATE_DIR}/referral_updated"
REFERRAL_STATUS_TEMPLATE = f"{_TEMPLATE_DIR}/referral_status_changed"

# Per-status copy for the status-change email.
_STATUS_COPY = {
    'pending': {
        'status_emoji': '⏳',
        'status_headline': 'is pending',
        'status_message': 'Your referral is waiting to be picked up by the specialist service.',
        'next_steps': ('No action is needed from you yet. You will be contacted to '
                       'arrange an appointment.'),
    },
    'scheduled': {
        'status_emoji': '📅',
        'status_headline': 'has been scheduled',
        'status_message': 'An appointment has been arranged for you — the date is below.',
        'next_steps': ('1. Put the appointment date in your calendar.\n'
                       '2. Arrive 10 minutes early and bring your student ID.\n'
                       '3. If you cannot attend, tell the Health Centre as early as '
                       'possible so the slot can be reused.'),
    },
    'completed': {
        'status_emoji': '✅',
        'status_headline': 'is complete',
        'status_message': 'Your specialist appointment has been recorded as completed.',
        'next_steps': ('Any findings or follow-up will come from the specialist or '
                       'your referring provider. Contact the Health Centre if you have '
                       'not heard anything within two weeks.'),
    },
    'cancelled': {
        'status_emoji': '❌',
        'status_headline': 'has been cancelled',
        'status_message': 'This referral has been cancelled and is no longer active.',
        'next_steps': ('If you still need to see a specialist, contact the Health Centre '
                       'to arrange a new referral. Cancelling does not affect any other '
                       'care you are receiving.'),
    },
    'no_show': {
        'status_emoji': '⚠️',
        'status_headline': 'was recorded as a missed appointment',
        'status_message': ('You were recorded as not attending your specialist '
                           'appointment. If you did attend, or could not let us know in '
                           'advance, please tell us — missed appointments can affect '
                           'how quickly you are seen next time.'),
        'next_steps': ('Contact the Health Centre to rebook or to correct this record, '
                       'quoting the reference number above.'),
    },
}


def _send_referral_email(template_name, recipient_email, template_vars):
    """Render *template_name* and hand it to the university email system.

    Best-effort: a missing address or an email failure is logged and reported
    as False. It never propagates — by the time we notify, the referral is
    already committed, and failing here would misreport a change that did
    happen.
    """
    address = (recipient_email or '').strip()
    if not address:
        logger.warning("Referral email '%s' not sent: no recipient address", template_name)
        return False
    try:
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email,
        )
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
    except ImportError as exc:
        logger.warning("Referral email '%s' not sent: email system unavailable (%s)",
                       template_name, exc)
        return False
    try:
        subject, body = render_template(template_name, template_vars)
        if subject is None or body is None:
            logger.error("Referral email '%s' not sent: template failed to render",
                         template_name)
            return False
        send_email(recipient_email=address, subject=subject, body=body)
        return True
    except Exception as exc:
        logger.exception("Referral email '%s' to %s failed: %s", template_name, address, exc)
        return False


def _referral_email_context(cursor, referral_id):
    """Everything the referral emails need, or None if the referral is gone."""
    cursor.execute('''
    SELECT r.id, r.student_id, s.first_name, s.last_name, s.email_address,
           r.referring_provider, r.specialist_provider, r.specialty, r.reason,
           r.urgency, r.referral_date, r.appointment_date, r.status, r.notes
    FROM referrals r
    JOIN students s ON r.student_id = s.student_id
    WHERE r.id = ?
    ''', (referral_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        'referral_id': row[0],
        'student_id': row[1],
        'student_name': f"{row[2] or ''} {row[3] or ''}".strip() or row[1],
        'student_email': row[4],
        'referring_provider': row[5],
        'specialist_provider': row[6],
        'specialty': row[7],
        'reason': row[8],
        'urgency': row[9],
        'referral_date': row[10],
        'appointment_date': row[11] or 'Not yet scheduled',
        'status': row[12],
        'notes': row[13] or 'None recorded.',
    }


def _base_vars(context):
    return {k: v for k, v in context.items() if k != 'student_email'}


def notify_referral_created(context):
    """Tell the student a referral has been created for them."""
    template_vars = _base_vars(context)
    if (context.get('urgency') or '').upper() == 'STAT':
        template_vars['urgency_notice'] = (
            "*** THIS IS A STAT (IMMEDIATE) REFERRAL ***\n"
            "You will be contacted urgently. If your symptoms are severe or getting "
            "worse, seek medical help now rather than waiting to be called.")
    else:
        template_vars['urgency_notice'] = ""
    return _send_referral_email(REFERRAL_CREATED_TEMPLATE,
                                context.get('student_email'), template_vars)


def notify_referral_updated(context, changes, updated_by):
    """Tell the student their referral changed, and exactly what changed.

    *changes* is ``[(field, old, new), ...]``.
    """
    if changes:
        change_list = "\n".join(
            f"  - {field}: '{old if old not in (None, '') else 'not set'}' "
            f"-> '{new if new not in (None, '') else 'not set'}'"
            for field, old, new in changes)
    else:
        change_list = "  (no changes recorded)"

    template_vars = _base_vars(context)
    template_vars.update({
        'change_list': change_list,
        'updated_by': updated_by,
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    })
    return _send_referral_email(REFERRAL_UPDATED_TEMPLATE,
                                context.get('student_email'), template_vars)


def notify_referral_status_changed(context, previous_status, updated_by):
    """Tell the student the referral status changed, and what it changed to."""
    template_vars = _base_vars(context)
    template_vars.update({
        'previous_status': previous_status,
        'updated_by': updated_by,
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    })
    template_vars.update(_STATUS_COPY.get(context.get('status'), {
        'status_emoji': '🔄',
        'status_headline': 'has been updated',
        'status_message': f"Your referral status is now '{context.get('status')}'.",
        'next_steps': ('If you have any questions about this referral, contact the '
                       'Health Centre quoting the reference number above.'),
    }))
    return _send_referral_email(REFERRAL_STATUS_TEMPLATE,
                                context.get('student_email'), template_vars)


def manage_referrals(auth):
    """Referral management system"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to manage referrals.")
        return

    while True:
        print("\n===== Referral Management =====")
        print("1. Create New Referral")
        print("2. View Referrals")
        print("3. Update Referral")
        print("4. Update Referral Status")
        print("5. Specialist Directory")
        print("6. Referral Follow-up")
        print("7. Referral Reports")
        print("8. Return to Main Menu")

        choice = input("\nEnter your choice (1-8): ")

        if choice == '1':
            create_referral(auth)
        elif choice == '2':
            view_referrals(auth)
        elif choice == '3':
            update_referral(auth)
        elif choice == '4':
            update_referral_status(auth)
        elif choice == '5':
            specialist_directory(auth)
        elif choice == '6':
            referral_followup(auth)
        elif choice == '7':
            referral_reports(auth)
        elif choice == '8':
            break
        else:
            print("Invalid choice. Please try again.")



def create_referral(auth):
    """Create new referral"""
    backup_before_operation('create_referral')

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input("Enter student ID: ")

    # Verify student exists
    cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
    student = cursor.fetchone()
    if not student:
        print("Error: Student ID not found.")
        conn.close()
        return

    print(f"Creating referral for: {student[0]} {student[1]}")

    referring_provider = input(f"Referring provider [Dr. {auth.current_user['username']}]: ").strip()
    if not referring_provider:
        referring_provider = f"Dr. {auth.current_user['username']}"

    specialist_provider = input("Specialist provider: ")

    specialties = [
        'Cardiology', 'Dermatology', 'Endocrinology', 'Gastroenterology',
        'Neurology', 'Orthopedics', 'Psychiatry', 'Pulmonology', 'Urology', 'Other'
    ]

    print("\nSpecialties:")
    for i, specialty in enumerate(specialties):
        print(f"{i+1}. {specialty}")

    while True:
        specialty_choice = input("\nSelect specialty (1-10): ")
        if specialty_choice.isdigit() and 1 <= int(specialty_choice) <= len(specialties):
            specialty = specialties[int(specialty_choice) - 1]
            if specialty == 'Other':
                specialty = input("Enter specialty: ")
            break
        print("Invalid choice. Please try again.")

    reason = input("Reason for referral: ")

    urgency_levels = ['Routine', 'Urgent', 'STAT']
    print("\nUrgency Levels:")
    for i, urgency in enumerate(urgency_levels):
        print(f"{i+1}. {urgency}")

    while True:
        urgency_choice = input("\nSelect urgency (1-3): ")
        if urgency_choice.isdigit() and 1 <= int(urgency_choice) <= len(urgency_levels):
            urgency = urgency_levels[int(urgency_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    referral_date = datetime.now().strftime('%Y-%m-%d')
    notes = input("Additional notes: ")
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO referrals
    (student_id, referring_provider, specialist_provider, specialty, reason,
     urgency, referral_date, status, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, referring_provider, specialist_provider, specialty, reason,
          urgency, referral_date, 'pending', notes, created_at))

    conn.commit()
    referral_id = cursor.lastrowid

    log_audit_event(auth.current_user['id'], 'create_referral', 'referral', referral_id)
    print(f"\nReferral created successfully! Referral ID: {referral_id}")

    if urgency == 'STAT':
        print("🚨 STAT REFERRAL - Immediate action required!")

    # Read back what was committed, so the email states the stored record
    # rather than what we think we wrote.
    context = _referral_email_context(cursor, referral_id)
    conn.close()

    if context:
        if notify_referral_created(context):
            print(f"Confirmation emailed to {context['student_email']}.")
        else:
            print("Note: the confirmation email could not be sent.")



def view_referrals(auth):
    """View referrals"""
    conn = get_connection()
    cursor = conn.cursor()

    print("\nFilter options:")
    print("1. All referrals")
    print("2. By student ID")
    print("3. By status")
    print("4. By specialty")
    print("5. Pending referrals only")

    filter_choice = input("\nSelect filter (1-5): ")

    if filter_choice == '1':
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        ORDER BY r.referral_date DESC
        LIMIT 50
        ''')

    elif filter_choice == '2':
        student_id = input("Enter student ID: ")
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        WHERE r.student_id = ?
        ORDER BY r.referral_date DESC
        ''', (student_id,))

    elif filter_choice == '3':
        status = input("Enter status (pending/scheduled/completed/cancelled): ")
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        WHERE r.status = ?
        ORDER BY r.referral_date DESC
        ''', (status,))

    elif filter_choice == '4':
        specialty = input("Enter specialty: ")
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        WHERE r.specialty LIKE ?
        ORDER BY r.referral_date DESC
        ''', (f'%{specialty}%',))

    elif filter_choice == '5':
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        WHERE r.status = 'pending'
        ORDER BY r.urgency DESC, r.referral_date
        ''')

    else:
        print("Invalid choice.")
        conn.close()
        return

    referrals = cursor.fetchall()

    if not referrals:
        print("No referrals found.")
        conn.close()
        return

    print("\n===== Referrals =====")
    for referral in referrals:
        ref_id, student_id, first_name, last_name, referring, specialist, specialty, urgency, ref_date, status = referral

        print(f"\nReferral ID: {ref_id}")
        print(f"Patient: {first_name} {last_name} (ID: {student_id})")
        print(f"Referring: {referring}")
        print(f"Specialist: {specialist}")
        print(f"Specialty: {specialty}")
        print(f"Urgency: {urgency}")
        print(f"Date: {ref_date}")
        print(f"Status: {status}")

        if urgency == 'STAT':
            print("🚨 STAT REFERRAL")
        elif urgency == 'Urgent':
            print("⚠️ URGENT")

        print("-" * 30)

    conn.close()



def update_referral(auth):
    """Edit a referral's details, and tell the student exactly what changed.

    Separate from update_referral_status: this covers the clinical details
    (specialist, specialty, reason, urgency, notes), while the status has its
    own workflow and its own email.
    """
    backup_before_operation('update_referral')

    conn = get_connection()
    cursor = conn.cursor()

    referral_id = input("Enter referral ID to update: ").strip()
    if not referral_id:
        print("A referral ID is required.")
        conn.close()
        return

    before = _referral_email_context(cursor, referral_id)
    if not before:
        print("Error: Referral not found.")
        conn.close()
        return

    print("\nCurrent Referral Details:")
    print(f"Patient:            {before['student_name']} ({before['student_id']})")
    print(f"Referring Provider: {before['referring_provider']}")
    print(f"Specialist:         {before['specialist_provider']}")
    print(f"Specialty:          {before['specialty']}")
    print(f"Urgency:            {before['urgency']}")
    print(f"Reason:             {before['reason']}")
    print(f"Notes:              {before['notes']}")
    print(f"Status:             {before['status']}")

    print("\nLeave a field blank to keep its current value.")

    referring = input(f"Referring provider [{before['referring_provider']}]: ").strip() \
        or before['referring_provider']
    specialist = input(f"Specialist provider [{before['specialist_provider']}]: ").strip() \
        or before['specialist_provider']

    specialties = [
        'Cardiology', 'Dermatology', 'Endocrinology', 'Gastroenterology',
        'Neurology', 'Orthopedics', 'Psychiatry', 'Pulmonology', 'Urology', 'Other'
    ]
    print("\nSpecialties:")
    for i, name in enumerate(specialties, 1):
        print(f"{i}. {name}")
    raw = input(f"Select specialty (1-{len(specialties)}) [{before['specialty']}]: ").strip()
    specialty = before['specialty']
    if raw:
        if raw.isdigit() and 1 <= int(raw) <= len(specialties):
            specialty = specialties[int(raw) - 1]
            if specialty == 'Other':
                specialty = input("Enter specialty: ").strip() or before['specialty']
        else:
            print(f"Out of range - keeping '{before['specialty']}'.")

    urgency_levels = ['Routine', 'Urgent', 'STAT']
    print("\nUrgency Levels:")
    for i, level in enumerate(urgency_levels, 1):
        print(f"{i}. {level}")
    raw = input(f"Select urgency (1-{len(urgency_levels)}) [{before['urgency']}]: ").strip()
    urgency = before['urgency']
    if raw:
        if raw.isdigit() and 1 <= int(raw) <= len(urgency_levels):
            urgency = urgency_levels[int(raw) - 1]
        else:
            print(f"Out of range - keeping '{before['urgency']}'.")

    reason = input(f"Reason for referral [{before['reason']}]: ").strip() or before['reason']

    current_notes = '' if before['notes'] == 'None recorded.' else before['notes']
    notes = input(f"Additional notes [{current_notes or 'none'}]: ").strip() or current_notes

    appointment_date = before['appointment_date']
    if appointment_date == 'Not yet scheduled':
        appointment_date = None
    raw = input(f"Appointment date YYYY-MM-DD [{appointment_date or 'not set'}]: ").strip()
    if raw:
        try:
            datetime.strptime(raw, '%Y-%m-%d')
            appointment_date = raw
        except ValueError:
            print("Invalid date format - keeping the existing appointment date.")

    # Work out what actually changed, so the email can say so rather than
    # telling the student "something was updated".
    changes = []
    for label, old, new in [
        ("Referring provider", before['referring_provider'], referring),
        ("Specialist", before['specialist_provider'], specialist),
        ("Specialty", before['specialty'], specialty),
        ("Urgency", before['urgency'], urgency),
        ("Reason", before['reason'], reason),
        ("Notes", current_notes, notes),
        ("Appointment date",
         None if before['appointment_date'] == 'Not yet scheduled' else before['appointment_date'],
         appointment_date),
    ]:
        if (old or '') != (new or ''):
            changes.append((label, old, new))

    if not changes:
        print("\nNothing was changed.")
        conn.close()
        return

    print("\nAbout to apply these changes:")
    for label, old, new in changes:
        print(f"  - {label}: '{old or 'not set'}' -> '{new or 'not set'}'")

    if input("\nApply these changes? (y/n): ").strip().lower() != 'y':
        print("Operation cancelled. Nothing has been changed.")
        conn.close()
        return

    cursor.execute('''
    UPDATE referrals
    SET referring_provider = ?, specialist_provider = ?, specialty = ?,
        reason = ?, urgency = ?, notes = ?, appointment_date = ?
    WHERE id = ?
    ''', (referring, specialist, specialty, reason, urgency, notes,
          appointment_date, referral_id))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_referral', 'referral', referral_id,
                    "; ".join(f"{label}: {old} -> {new}" for label, old, new in changes))

    after = _referral_email_context(cursor, referral_id)
    conn.close()

    print(f"\nReferral {referral_id} updated ({len(changes)} change(s)).")

    if after:
        updated_by = auth.current_user.get('username', 'the Health Centre')
        if notify_referral_updated(after, changes, updated_by):
            print(f"Update emailed to {after['student_email']}.")
        else:
            print("Note: the update email could not be sent.")



def update_referral_status(auth):
    """Update referral status"""
    backup_before_operation('update_referral_status')

    conn = get_connection()
    cursor = conn.cursor()

    referral_id = input("Enter referral ID to update: ")

    cursor.execute('''
    SELECT r.id, s.first_name, s.last_name, r.specialist_provider,
           r.specialty, r.status
    FROM referrals r
    JOIN students s ON r.student_id = s.student_id
    WHERE r.id = ?
    ''', (referral_id,))

    referral = cursor.fetchone()

    if not referral:
        print("Error: Referral not found.")
        conn.close()
        return

    ref_id, first_name, last_name, specialist, specialty, current_status = referral

    print("\nReferral Details:")
    print(f"Patient: {first_name} {last_name}")
    print(f"Specialist: {specialist}")
    print(f"Specialty: {specialty}")
    print(f"Current Status: {current_status}")

    status_options = ['pending', 'scheduled', 'completed', 'cancelled', 'no_show']
    print("\nStatus Options:")
    for i, status in enumerate(status_options):
        print(f"{i+1}. {status}")

    while True:
        choice = input("\nSelect new status (1-5): ")
        if choice.isdigit() and 1 <= int(choice) <= len(status_options):
            new_status = status_options[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")

    appointment_date = None
    if new_status == 'scheduled':
        while True:
            appointment_date = input("Appointment date (YYYY-MM-DD): ")
            try:
                datetime.strptime(appointment_date, '%Y-%m-%d')
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

    notes = input("Additional notes: ")

    cursor.execute('''
    UPDATE referrals
    SET status = ?, appointment_date = ?, notes = CASE WHEN ? != '' THEN ? ELSE notes END
    WHERE id = ?
    ''', (new_status, appointment_date, notes, notes, referral_id))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_referral_status', 'referral', referral_id,
                   f"Status changed from {current_status} to {new_status}")

    print(f"\nReferral status updated to '{new_status}' successfully!")

    context = _referral_email_context(cursor, referral_id)
    conn.close()

    # Notify after the commit, so no status change is announced that rolled back.
    if context:
        updated_by = auth.current_user.get('username', 'the Health Centre')
        if notify_referral_status_changed(context, current_status, updated_by):
            print(f"Status change emailed to {context['student_email']}.")
        else:
            print("Note: the status-change email could not be sent.")



def referral_followup(auth):
    """Follow up on referrals"""
    conn = get_connection()
    cursor = conn.cursor()

    # Get referrals needing follow-up
    cursor.execute('''
    SELECT r.id, s.first_name, s.last_name, r.specialist_provider,
           r.specialty, r.referral_date, r.status
    FROM referrals r
    JOIN students s ON r.student_id = s.student_id
    WHERE r.status IN ('scheduled', 'pending')
    AND r.referral_date < date('now', '-30 days')
    ORDER BY r.referral_date
    ''')

    followup_needed = cursor.fetchall()

    if not followup_needed:
        print("No referrals requiring follow-up.")
        conn.close()
        return

    print("\n===== Referrals Needing Follow-up =====")

    for ref_id, first_name, last_name, specialist, specialty, ref_date, status in followup_needed:
        days_since = (datetime.now() - datetime.strptime(ref_date, '%Y-%m-%d')).days

        print(f"\nReferral ID: {ref_id}")
        print(f"Patient: {first_name} {last_name}")
        print(f"Specialist: {specialist} ({specialty})")
        print(f"Referred: {ref_date} ({days_since} days ago)")
        print(f"Status: {status}")

        if days_since > 60:
            print("🔴 URGENT: Over 60 days old")
        elif days_since > 30:
            print("🟡 Follow-up needed")

    conn.close()



def referral_reports(auth):
    """Generate referral reports"""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Referral Reports =====")

    # Referral statistics
    cursor.execute('''
    SELECT specialty, COUNT(*) as referral_count,
           AVG(CASE WHEN status = 'completed' THEN 1.0 ELSE 0.0 END) * 100 as completion_rate
    FROM referrals
    WHERE referral_date >= date('now', '-30 days')
    GROUP BY specialty
    ORDER BY referral_count DESC
    ''')

    stats = cursor.fetchall()

    print("Referral Statistics (Last 30 Days):")
    print(f"{'Specialty':<20} {'Count':<8} {'Completion Rate':<15}")
    print("-" * 45)

    for specialty, count, completion_rate in stats:
        print(f"{specialty:<20} {count:<8} {completion_rate:.1f}%")

    # Monthly trend
    cursor.execute('''
    SELECT strftime('%Y-%m', referral_date) as month, COUNT(*) as count
    FROM referrals
    WHERE referral_date >= date('now', '-12 months')
    GROUP BY strftime('%Y-%m', referral_date)
    ORDER BY month
    ''')

    monthly_trends = cursor.fetchall()

    if monthly_trends:
        print("\nMonthly Referral Trends:")
        for month, count in monthly_trends:
            print(f"  {month}: {count} referrals")

    conn.close()



