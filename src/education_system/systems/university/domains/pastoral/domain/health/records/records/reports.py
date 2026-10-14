from education_system.systems.university.domains.pastoral.infrastructure.health.storage import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.systems.university.domains.pastoral.domain.health.records.db.audit import log_audit_event
from education_system.systems.university.domains.pastoral.domain.health.services import generate_disease_surveillance_report
from education_system.systems.university.domains.pastoral.domain.health.records.analytics.population import generate_population_health_report, generate_student_health_summary_report
from education_system.systems.university.domains.pastoral.domain.health.records.vaccinations.reports import generate_vaccination_analysis_report


import io
import logging
import sys

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sending a report to the admin
# ---------------------------------------------------------------------------
# The reports print to the screen and were gone as soon as the terminal
# scrolled. Each one is now captured as it prints, shown exactly as before,
# and then offered for sending — the report code itself is untouched, so the
# delivery step and the report logic stay independent.

HEALTH_REPORT_ADMIN_TEMPLATE = "campus_services/health/health_report_admin"


def _capture_report(report_fn):
    """Run *report_fn*, returning everything it printed as one string.

    The text is echoed as it is produced, so the operator sees the report at
    the usual time rather than after a pause.
    """
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
        report_fn()
    finally:
        sys.stdout = original
    return buffer.getvalue()


def _admin_recipients(limit=5):
    """Admin addresses to send health reports to, as ``[(name, email), ...]``.

    Reads the university ``users`` table — the same lookup the other admin
    alerts use — so the address follows whoever is actually set up as an
    admin rather than a constant baked into the code.
    """
    recipients = []
    try:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT username, email FROM users "
                "WHERE role = 'admin' AND email IS NOT NULL AND TRIM(email) != '' "
                "ORDER BY username LIMIT ?",
                (int(limit),),
            ).fetchall()
        finally:
            conn.close()
        for row in rows:
            recipients.append((row[0] or 'Health Administrator', row[1]))
    except Exception as exc:
        logger.warning("Could not resolve admin recipients: %s", exc)
    return recipients


def _email_report_to_admin(auth, title, content, period):
    """Send a generated report to the configured admins."""
    recipients = _admin_recipients()
    if not recipients:
        print("No admin email address is configured, so the report was not sent.")
        print("Set an email against an admin user, then try again.")
        return False

    sender = 'University Health Portal'
    if auth and getattr(auth, 'current_user', None):
        sender = auth.current_user.get('username', sender)
    generated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email,
        )
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
    except ImportError as exc:
        print(f"Email system unavailable, so the report was not sent: {exc}")
        return False

    sent, failed, addresses = 0, 0, []
    for admin_name, admin_email in recipients:
        try:
            subject, body = render_template(HEALTH_REPORT_ADMIN_TEMPLATE, {
                'admin_name': admin_name,
                'title': title,
                'period': period,
                'content': content,
                'sender_name': sender,
                'generated_date': generated,
            })
            if subject is None or body is None:
                raise ValueError("template failed to render")
            send_email(recipient_email=admin_email, subject=subject, body=body)
            sent += 1
            addresses.append(admin_email)
        except Exception as exc:
            logger.exception("Health report email to %s failed: %s", admin_email, exc)
            failed += 1

    if sent:
        print(f"Report emailed to: {', '.join(addresses)}")
    if failed:
        print(f"{failed} admin email(s) could not be sent.")
    return bool(sent)


def _offer_email_to_admin(auth, title, content, period):
    """Ask whether to email the report just shown, and do it if so."""
    if not content.strip():
        return
    answer = input("\nEmail this report to the admin? (y/n): ").strip().lower()
    if answer != 'y':
        return
    _email_report_to_admin(auth, title, content, period)


def generate_health_report(auth):
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to generate health reports.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Health Report Generator =====")

    # Report options
    report_types = [
        'Student Health Summary',
        'Population Health Statistics',
        'Disease Surveillance Report',
        'Vaccination Coverage Analysis',
        'Provider Utilization Report',
        'Quality Metrics Dashboard'
    ]

    print("Available Report Types:")
    for i, report_type in enumerate(report_types):
        print(f"{i+1}. {report_type}")

    while True:
        choice = input(f"\nSelect report type (1-{len(report_types)}): ")
        if choice.isdigit() and 1 <= int(choice) <= len(report_types):
            selected_report = report_types[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")

    # Date range for report
    while True:
        start_date = input("Start date (YYYY-MM-DD): ")
        end_date = input("End date (YYYY-MM-DD): ")
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    print(f"\nGenerating {selected_report} for period {start_date} to {end_date}...")

    # Generate report based on type.
    #
    # The aggregate reports are captured as they print and can then be emailed
    # to the admin. Student Health Summary is deliberately NOT offered: it is
    # one named student's clinical record, and mailing that to every admin
    # account is a different decision from circulating aggregate statistics.
    period = f"{start_date} to {end_date}"

    if selected_report == 'Population Health Statistics':
        content = _capture_report(
            lambda: generate_population_health_report(auth, start_date, end_date))
        _offer_email_to_admin(auth, selected_report, content, period)
    elif selected_report == 'Disease Surveillance Report':
        content = _capture_report(
            lambda: generate_disease_surveillance_report(auth, start_date, end_date))
        _offer_email_to_admin(auth, selected_report, content, period)
    elif selected_report == 'Vaccination Coverage Analysis':
        content = _capture_report(
            lambda: generate_vaccination_analysis_report(auth, start_date, end_date))
        _offer_email_to_admin(auth, selected_report, content, period)
    elif selected_report == 'Provider Utilization Report':
        from education_system.systems.university.domains.pastoral.domain.health.appointments.appointment_booking import generate_provider_utilization_report
        content = _capture_report(
            lambda: generate_provider_utilization_report(auth, start_date, end_date))
        _offer_email_to_admin(auth, selected_report, content, period)
    elif selected_report == 'Quality Metrics Dashboard':
        from education_system.systems.university.domains.pastoral.domain.health.records.quality_assurance import generate_quality_metrics_report
        content = _capture_report(
            lambda: generate_quality_metrics_report(auth, start_date, end_date))
        _offer_email_to_admin(auth, selected_report, content, period)
    elif selected_report == 'Student Health Summary':
        generate_student_health_summary_report(auth, start_date, end_date)
    else:
        print("Report type not yet implemented.")

    conn.close()



