import io
import logging
import sys

from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.systems.university.domains.health.domain.health.records.db.audit import log_audit_event
from education_system.systems.university.domains.health.domain.health.prompting import ask as _ask

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Notifying students and admins
# ---------------------------------------------------------------------------
# These screens used to print "Screening reminders sent successfully!" without
# sending anything. They now go through the university email system
# (infrastructure.email): render_template fills one of the JSON templates
# under assets/templates/email/campus_services/health/ and send_email stores
# the mail *and* raises the student's inbox message.

_SCREENING_TEMPLATE_DIR = "campus_services/health"
SCREENING_REMINDER_TEMPLATE = f"{_SCREENING_TEMPLATE_DIR}/screening_reminder"
SCREENING_OVERDUE_TEMPLATE = f"{_SCREENING_TEMPLATE_DIR}/screening_overdue"
SCREENING_REPORT_TEMPLATE = f"{_SCREENING_TEMPLATE_DIR}/screening_population_report"


def send_screening_email(template_name, recipient_email, template_vars):
    """Render *template_name* and hand it to the university email system.

    Best-effort per recipient: one student with no address on file must not
    stop the rest of a reminder run.
    """
    address = (recipient_email or '').strip()
    if not address:
        logger.warning("Screening email '%s' not sent: no recipient address", template_name)
        return False
    try:
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email,
        )
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
    except ImportError as exc:
        logger.warning("Screening email '%s' not sent: email system unavailable (%s)",
                       template_name, exc)
        return False
    try:
        subject, body = render_template(template_name, template_vars)
        if subject is None or body is None:
            logger.error("Screening email '%s' not sent: template failed to render",
                         template_name)
            return False
        send_email(recipient_email=address, subject=subject, body=body)
        return True
    except Exception as exc:
        logger.exception("Screening email '%s' to %s failed: %s", template_name, address, exc)
        return False


def screening_admin_recipients(limit=5):
    """Admin addresses for screening reports, as ``[(name, email), ...]``."""
    recipients = []
    try:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT username, email FROM users "
                "WHERE role = 'admin' AND email IS NOT NULL AND TRIM(email) != '' "
                "ORDER BY username LIMIT ?", (int(limit),)).fetchall()
        finally:
            conn.close()
        for row in rows:
            recipients.append((row[0] or 'Health Administrator', row[1]))
    except Exception as exc:
        logger.warning("Could not resolve admin recipients: %s", exc)
    return recipients


def _screening_label(screening_type):
    """Readable phrase for a screening type.

    Several types already end in "Screening" ("Vision Screening"), so
    appending the word again gives "your Vision Screening screening".
    """
    text = (screening_type or 'screening').strip()
    return text if text.lower().endswith('screening') else f"{text} screening"


def notify_screening_due(student):
    """Remind one student that a screening is coming up."""
    due_line = ""
    try:
        days = (datetime.strptime(student['due_date'], '%Y-%m-%d') - datetime.now()).days
        if days < 0:
            due_line = f"This was due {abs(days)} day(s) ago."
        elif days == 0:
            due_line = "This is due today."
        else:
            due_line = f"That is {days} day(s) from now."
    except (ValueError, TypeError, KeyError):
        pass

    return send_screening_email(SCREENING_REMINDER_TEMPLATE, student.get('email'), {
        'student_name': student.get('student_name') or 'Student',
        'student_id': student.get('student_id', ''),
        'screening_id': student.get('screening_id', ''),
        'screening_type': student.get('screening_type', ''),
        'screening_label': _screening_label(student.get('screening_type')),
        'due_date': student.get('due_date', ''),
        'provider': student.get('provider') or 'To be assigned',
        'due_line': due_line,
    })


def notify_screening_overdue(student):
    """Tell one student a screening is overdue, with the right urgency."""
    days_overdue = student.get('days_overdue', 0)
    if days_overdue > 90:
        emoji = '🔴'
        note = ("This has been outstanding for more than 90 days. Please book "
                "in, or tell us if you have had it done elsewhere or would "
                "rather not have it — either is fine, we just need to know so "
                "we can stop chasing.")
    elif days_overdue > 30:
        emoji = '🟠'
        note = "This has been outstanding for over a month — please book in when you can."
    else:
        emoji = '🟡'
        note = ""

    return send_screening_email(SCREENING_OVERDUE_TEMPLATE, student.get('email'), {
        'student_name': student.get('student_name') or 'Student',
        'student_id': student.get('student_id', ''),
        'screening_id': student.get('screening_id', ''),
        'screening_type': student.get('screening_type', ''),
        'screening_label': _screening_label(student.get('screening_type')),
        'due_date': student.get('due_date', ''),
        'days_overdue': days_overdue,
        'provider': student.get('provider') or 'To be assigned',
        'urgency_emoji': emoji,
        'urgency_note': note,
    })


def send_screening_report_to_admins(title, content, sender_name, period="Last 12 months"):
    """Email a population screening report to the admins.

    Returns ``(sent, failed, addresses)``.
    """
    recipients = screening_admin_recipients()
    if not recipients:
        return 0, 0, []

    generated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sent = failed = 0
    addresses = []
    for admin_name, admin_email in recipients:
        ok = send_screening_email(SCREENING_REPORT_TEMPLATE, admin_email, {
            'admin_name': admin_name,
            'title': title,
            'period': period,
            'content': content,
            'sender_name': sender_name or 'University Health Portal',
            'generated_date': generated,
        })
        if ok:
            sent += 1
            addresses.append(admin_email)
        else:
            failed += 1
    return sent, failed, addresses


def capture_output(fn):
    """Run *fn*, echoing what it prints and returning it as a string."""
    buffer = io.StringIO()
    original = sys.stdout

    class _Tee:
        def write(self, data):
            buffer.write(data)
            return original.write(data)

        def flush(self):
            return original.flush()

    sys.stdout = _Tee()
    try:
        fn()
    finally:
        sys.stdout = original
    return buffer.getvalue()



def screening_reminders(auth, values=None):
    """Send screening reminders"""
    conn = get_connection()
    cursor = conn.cursor()

    # Get students with due screenings
    seven_days = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

    cursor.execute('''
    SELECT ss.id, s.first_name, s.last_name, s.student_id, ss.screening_type,
           ss.due_date, s.email_address, ss.provider
    FROM screening_schedules ss
    JOIN students s ON ss.student_id = s.student_id
    WHERE ss.due_date <= ? AND ss.status = 'due'
    ORDER BY ss.due_date
    ''', (seven_days,))

    reminder_list = cursor.fetchall()

    if not reminder_list:
        print("No screening reminders to send.")
        conn.close()
        return

    print(f"\n===== Screening Reminders ({len(reminder_list)} students) =====")

    students = []
    without_email = 0
    for (screen_id, first_name, last_name, student_id, screening_type,
         due_date, email, provider) in reminder_list:
        name = f"{first_name or ''} {last_name or ''}".strip() or student_id
        print(f"• {name} (ID: {student_id})")
        print(f"  {screening_type} due {due_date}")
        if not email:
            without_email += 1
            print("  (no email address on file — cannot be reminded)")
        students.append({
            'screening_id': screen_id, 'student_id': student_id,
            'student_name': name, 'screening_type': screening_type,
            'due_date': due_date, 'email': email, 'provider': provider,
        })

    if without_email:
        print(f"\n{without_email} of {len(students)} have no email address on file.")

    send_reminders = _ask(values, "send_reminders", 
        f"\nEmail reminders to {len(students) - without_email} student(s)? (y/n): "
    ).strip().lower()

    if send_reminders != 'y':
        print("Reminder sending cancelled. Nothing has been sent.")
        conn.close()
        return

    # Close before sending: the email service opens its own connection to the
    # same database, and one writer at a time avoids the lock.
    conn.close()

    sent = failed = 0
    for student in students:
        if notify_screening_due(student):
            sent += 1
        else:
            failed += 1

    print(f"\nScreening reminders: {sent} sent, {failed} not sent.")
    log_audit_event(auth.current_user['id'], 'send_screening_reminders', 'screening',
                    sent, f"{sent} sent, {failed} failed")



def _population_screening_reports(auth):
    """Generate population screening reports (printing only)."""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Population Screening Reports =====")

    # Screening compliance rates
    cursor.execute('''
    SELECT screening_type,
           COUNT(*) as total_due,
           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
           SUM(CASE WHEN due_date < date('now') AND status = 'due' THEN 1 ELSE 0 END) as overdue
    FROM screening_schedules
    WHERE due_date >= date('now', '-365 days')
    GROUP BY screening_type
    ORDER BY total_due DESC
    ''')

    compliance_data = cursor.fetchall()

    if compliance_data:
        print("Screening Compliance Rates (Last 12 Months):")
        print(f"{'Screening Type':<25} {'Total':<8} {'Completed':<10} {'Overdue':<8} {'Rate':<8}")
        print("-" * 65)

        for screening, total, completed, overdue in compliance_data:
            compliance_rate = (completed / total * 100) if total > 0 else 0
            print(f"{screening:<25} {total:<8} {completed:<10} {overdue:<8} {compliance_rate:.1f}%")

    # Age group analysis
    cursor.execute('''
    SELECT
        CASE
            WHEN s.age < 25 THEN '18-24'
            WHEN s.age < 35 THEN '25-34'
            WHEN s.age < 45 THEN '35-44'
            ELSE '45+'
        END as age_group,
        COUNT(DISTINCT ss.student_id) as students_with_screenings,
        AVG(CASE WHEN ss.status = 'completed' THEN 1.0 ELSE 0.0 END) * 100 as avg_compliance
    FROM screening_schedules ss
    JOIN students s ON ss.student_id = s.student_id
    WHERE ss.due_date >= date('now', '-365 days')
    GROUP BY age_group
    ORDER BY age_group
    ''')

    age_analysis = cursor.fetchall()

    if age_analysis:
        print("\nCompliance by Age Group:")
        print(f"{'Age Group':<12} {'Students':<10} {'Compliance':<12}")
        print("-" * 35)

        for age_group, students, compliance in age_analysis:
            print(f"{age_group:<12} {students:<10} {compliance:.1f}%")

    conn.close()


def population_screening_reports(auth, values=None):
    """Show the population screening report, then offer to email it.

    The report itself is untouched — it is captured as it prints, so the
    delivery step and the report logic stay independent.
    """
    content = capture_output(lambda: _population_screening_reports(auth))
    if not content.strip():
        return

    answer = _ask(values, "email_report", "\nEmail this report to the admin? (y/n): ").strip().lower()
    if answer != 'y':
        return

    sender = 'University Health Portal'
    if auth and getattr(auth, 'current_user', None):
        sender = auth.current_user.get('username', sender)

    sent, failed, addresses = send_screening_report_to_admins(
        "Population Screening Report", content, sender)

    if not sent and not failed:
        print("No admin email address is configured, so the report was not sent.")
        print("Set an email against an admin user, then try again.")
        return
    if sent:
        print(f"Report emailed to: {', '.join(addresses)}")
        log_audit_event(auth.current_user['id'], 'email_screening_report',
                        'screening', sent, ", ".join(addresses))
    if failed:
        print(f"{failed} admin email(s) could not be sent.")



