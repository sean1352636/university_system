"""Interactive CLI forms for email operations."""

from __future__ import annotations

import csv
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import sqlite3

from education_system.post_18.university_system.core.i18n import get_text as _t
from education_system.post_18.university_system.infrastructure.email.config import config
from education_system.post_18.university_system.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.post_18.university_system.core.logs import handle_exception
from education_system.post_18.university_system.infrastructure.email.templates import list_templates


@handle_exception
def send_batch_email_form():
    """Interactive form for sending batch emails"""
    from education_system.post_18.university_system.infrastructure.email.email_service.queue import wait_for_email_queue
    from education_system.post_18.university_system.infrastructure.email.announcements import send_batch_announcement

    print("\n" + _t("email_service.batch_sender_title"))
    print("=================")

    # Get announcement details
    title = input("Enter announcement title: ")

    if not title:
        print(_t("email_service.title_empty"))
        return

    print("\n" + _t("email_service.enter_body_hint"))
    body_lines = []
    while True:
        line = input()
        if line == 'END':
            break
        body_lines.append(line)

    body = "\n".join(body_lines)

    if not body:
        print(_t("email_service.body_empty"))
        return

    # Get filter criteria
    print("\n" + _t("email_service.filter_recipients"))

    filter_criteria = {}

    course = input("Course (CS/DS/leave empty for all): ")
    if course:
        filter_criteria['course'] = course

    module = input("Module Code (leave empty for all): ")
    if module:
        filter_criteria['module_code'] = module

    year = input("Registration Year (YYYY, leave empty for all): ")
    if year and year.isdigit() and len(year) == 4:
        filter_criteria['registration_year'] = year

    # Confirm sending
    if filter_criteria:
        filters = ", ".join(f"{k}: {v}" for k, v in filter_criteria.items())
        confirm = input(f"\n{'Store' if config.get('database_only_mode', True) else 'Send'} announcement to students matching [{filters}]? (y/n): ")
    else:
        confirm = input(f"\n{'Store' if config.get('database_only_mode', True) else 'Send'} announcement to ALL students? (y/n): ")

    if confirm.lower() != 'y':
        print(_t("email_service.batch_cancelled"))
        return

    # Send the batch email
    success, failed, total = send_batch_announcement(title, body, filter_criteria)

    if config.get('database_only_mode', True):
        print("\n" + _t("email_service.emails_stored", total=total))
        print(_t("email_service.success_failed", success=success, failed=failed))
    else:
        print("\n" + _t("email_service.emails_queued", total=total))
        print(_t("email_service.success_failed", success=success, failed=failed))

        # Wait for emails to be sent
        if total > 0:
            wait_confirm = input("\nWait for all emails to be sent? (y/n): ")
            if wait_confirm.lower() == 'y':
                wait_for_email_queue()

@handle_exception
def schedule_email_form():
    """Interactive form for scheduling emails"""
    from education_system.post_18.university_system.infrastructure.email.email_service.scheduling import schedule_send

    print("\n" + _t("email_service.schedule_title"))
    print("==============")

    # Select template
    templates = list_templates()

    if not templates:
        print(_t("email_service.no_templates"))
        return

    print("\n" + _t("email_service.available_templates") + ":")
    for i, template in enumerate(templates, 1):
        print(f"{i}. {template['name']}")

    try:
        template_idx = int(input("\nSelect template (0 to cancel): "))
        if template_idx == 0:
            return

        if 1 <= template_idx <= len(templates):
            template_name = templates[template_idx - 1]['name']
        else:
            print(_t("email_service.invalid_template_number"))
            return
    except ValueError:
        print(_t("email_service.invalid_input"))
        return

    # Get recipients
    print("\n" + _t("email_service.enter_recipients_hint"))
    recipients = []
    while True:
        line = input()
        if line == 'END':
            break
        if line.strip():
            recipients.append(line.strip())

    if not recipients:
        print(_t("email_service.no_recipients"))
        return

    # Get scheduled date
    print("\n" + _t("email_service.enter_scheduled_date"))
    try:
        year = int(input("Year (YYYY): "))
        month = int(input("Month (MM): "))
        day = int(input("Day (DD): "))
        hour = int(input("Hour (0-23): "))
        minute = int(input("Minute (0-59): "))

        scheduled_date = datetime(year, month, day, hour, minute)

        if scheduled_date <= datetime.now():
            print(_t("email_service.date_must_be_future"))
            return
    except ValueError:
        print(_t("email_service.invalid_date"))
        return

    # Confirm scheduling
    confirm = input(f"\nSchedule {len(recipients)} emails using template '{template_name}' for {scheduled_date}? (y/n): ")

    if confirm.lower() != 'y':
        print(_t("email_service.scheduling_cancelled"))
        return

    # Schedule the emails
    result = schedule_send(scheduled_date, recipients, template_name)

    print("\n" + _t("email_service.scheduled_count", count=result['success'], date=str(scheduled_date)))
    if result['failure'] > 0:
        print(_t("email_service.failed_schedule", count=result['failure']))

    print(_t("email_service.scheduled_ids", ids=', '.join(map(str, result['scheduled_ids']))))

@handle_exception
def display_stored_emails_menu(auth=None):
    """Interactive menu to view stored emails

    Args:
        auth: Authentication object. If provided and user is not admin,
              only shows emails sent by the current user.
    """
    from education_system.post_18.university_system.infrastructure.email.email_service.storage import (
        get_stored_emails, delete_stored_email, clear_stored_emails,
    )

    # Determine sender filter based on user role
    sender_filter = None
    is_admin = False
    if auth and auth.current_user:
        user_role = auth.current_user.get('role', '')
        is_admin = user_role == 'admin'
        if user_role in ('student', 'staff', 'instructor'):
            sender_filter = auth.current_user.get('email', '')

    while True:
        print("\n" + _t("email_service.stored_emails_title") + ":")
        print("=========================")
        if sender_filter:
            print(_t("email_service.showing_sent_only"))
        print("1. " + _t("email_service.view_recent"))
        print("2. " + _t("email_service.search_stored"))
        print("3. " + _t("email_service.view_email_details"))
        print("4. " + _t("email_service.delete_stored"))
        if is_admin:
            print("5. " + _t("email_service.clear_old"))
            print("6. " + _t("email_service.clear_all"))
            print("7. " + _t("email_service.export_csv"))
            print("8. " + _t("email_service.back_to_menu"))
        else:
            print("5. " + _t("email_service.export_csv"))
            print("6. " + _t("email_service.back_to_menu"))

        max_choice = 8 if is_admin else 6
        choice = input(f"Choose an option (1-{max_choice}): ")

        if choice == '1':
            # View recent emails
            emails_data = get_stored_emails(limit=20, sender_filter=sender_filter)

            if emails_data['emails']:
                print("\n" + _t("email_service.recent_stored", count=emails_data['total_count']) + ":")
                print("=" * 100)
                print(f"{'ID':<5}{_t('email_service.recipient'):<30}{_t('email_service.subject'):<35}{'Date':<20}{_t('email_service.template')}")
                print("-" * 100)

                for email in emails_data['emails']:
                    subject = email['subject'][:32] + "..." if len(email['subject']) > 32 else email['subject']
                    template = email['template_name'] or "Direct"

                    print(f"{email['id']:<5}{email['recipient_email']:<30}{subject:<35}{email['created_date']:<20}{template}")
            else:
                print(_t("email_service.no_stored_found"))

            input("\nPress Enter to continue...")

        elif choice == '2':
            # Search emails
            search_term = input(_t("email_service.enter_recipient_search") + ": ")
            emails_data = get_stored_emails(limit=50, recipient_filter=search_term, sender_filter=sender_filter)

            if emails_data['emails']:
                print("\n" + _t("email_service.found_emails", count=len(emails_data['emails']), search=search_term) + ":")
                print("=" * 100)
                print(f"{'ID':<5}{_t('email_service.recipient'):<30}{_t('email_service.subject'):<35}{'Date':<20}{_t('email_service.template')}")
                print("-" * 100)

                for email in emails_data['emails']:
                    subject = email['subject'][:32] + "..." if len(email['subject']) > 32 else email['subject']
                    template = email['template_name'] or "Direct"

                    print(f"{email['id']:<5}{email['recipient_email']:<30}{subject:<35}{email['created_date']:<20}{template}")
            else:
                print(_t("email_service.not_found_for", search=search_term))

            input("\nPress Enter to continue...")

        elif choice == '3':
            # View email details
            try:
                email_id = int(input("Enter email ID to view details: "))

                def _get_email_details(cursor):
                    query = '''
                    SELECT id, recipient_email, subject, body, sender_email, sender_name,
                           cc_recipients, bcc_recipients, attachment_paths, created_date,
                           template_name, template_vars, related_to, student_id
                    FROM stored_emails WHERE id = ?
                    '''
                    params = [email_id]
                    # For non-admin users, also verify they sent the email
                    if sender_filter:
                        query += ' AND sender_email = ?'
                        params.append(sender_filter)

                    cursor.execute(query, params)

                    result = cursor.fetchone()
                    if result:
                        return {
                            'id': result[0], 'recipient_email': result[1], 'subject': result[2],
                            'body': result[3], 'sender_email': result[4], 'sender_name': result[5],
                            'cc_recipients': result[6], 'bcc_recipients': result[7],
                            'attachment_paths': result[8], 'created_date': result[9],
                            'template_name': result[10], 'template_vars': result[11],
                            'related_to': result[12], 'student_id': result[13]
                        }
                    return None

                email = execute_db_operation(_get_email_details)

                if email:
                    print("\n" + _t("email_service.email_details", id=email['id']) + ":")
                    print("=" * 80)
                    print(f"{_t('email_service.from')}: {email['sender_name']} <{email['sender_email']}>")
                    print(f"{_t('email_service.to')}: {email['recipient_email']}")
                    if email['cc_recipients']:
                        print(f"{_t('email_service.cc')}: {email['cc_recipients']}")
                    if email['bcc_recipients']:
                        print(f"{_t('email_service.bcc')}: {email['bcc_recipients']}")
                    print(f"{_t('email_service.subject')}: {email['subject']}")
                    print(f"Date: {email['created_date']}")
                    if email['template_name']:
                        print(f"{_t('email_service.template')}: {email['template_name']}")
                    if email['attachment_paths']:
                        print(f"{_t('email_service.attachments')}: {email['attachment_paths']}")
                    print("-" * 80)
                    print(_t("email_service.body") + ":")
                    print(email['body'])
                    print("=" * 80)
                else:
                    print(_t("email_service.not_found_id", id=email_id))

            except ValueError:
                print(_t("email_service.invalid_email_id"))

            input("\nPress Enter to continue...")

        elif choice == '4':
            # Delete email
            try:
                email_id = int(input("Enter email ID to delete: "))

                # For non-admin users, verify they own this email before deleting
                if sender_filter:
                    def _check_ownership(cursor):
                        cursor.execute(
                            'SELECT id FROM stored_emails WHERE id = ? AND sender_email = ?',
                            (email_id, sender_filter)
                        )
                        return cursor.fetchone() is not None

                    owns_email = execute_db_operation(_check_ownership)
                    if not owns_email:
                        print(_t("email_service.not_found_or_no_permission"))
                        input("\nPress Enter to continue...")
                        continue

                confirm = input(_t("email_service.confirm_delete", id=email_id) + " (y/n): ")

                if confirm.lower() == 'y':
                    if delete_stored_email(email_id):
                        print(_t("email_service.deleted_success"))
                    else:
                        print(_t("email_service.failed_delete"))
                else:
                    print(_t("email_service.deletion_cancelled"))

            except ValueError:
                print(_t("email_service.invalid_email_id"))

            input("\nPress Enter to continue...")

        elif choice == '5':
            if is_admin:
                # Clear old emails (admin only)
                try:
                    days = int(input("Delete emails older than how many days? "))
                    confirm = input(f"Delete all emails older than {days} days? (y/n): ")

                    if confirm.lower() == 'y':
                        deleted_count = clear_stored_emails(older_than_days=days)
                        print(_t("email_service.deleted_old", count=deleted_count))
                    else:
                        print(_t("email_service.operation_cancelled"))

                except ValueError:
                    print(_t("email_service.invalid_days"))

                input("\nPress Enter to continue...")
            else:
                # Export to CSV (non-admin option 5)
                try:
                    filename = input("Enter CSV filename (default: my_emails.csv): ") or "my_emails.csv"
                    emails_data = get_stored_emails(limit=10000, sender_filter=sender_filter)

                    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                        fieldnames = ['id', 'recipient_email', 'subject', 'sender_email', 'sender_name',
                                    'cc_recipients', 'bcc_recipients', 'created_date', 'template_name', 'body']
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                        writer.writeheader()
                        for email in emails_data['emails']:
                            writer.writerow({
                                'id': email['id'],
                                'recipient_email': email['recipient_email'],
                                'subject': email['subject'],
                                'sender_email': email['sender_email'],
                                'sender_name': email['sender_name'],
                                'cc_recipients': email['cc_recipients'],
                                'bcc_recipients': email['bcc_recipients'],
                                'created_date': email['created_date'],
                                'template_name': email['template_name'],
                                'body': email['body']
                            })

                    print(_t("email_service.exported_count", count=len(emails_data['emails']), filename=filename))

                except Exception as e:
                    print(_t("email_service.export_error", error=str(e)))

                input("\nPress Enter to continue...")

        elif choice == '6':
            if is_admin:
                # Clear all emails (admin only)
                confirm = input("Are you sure you want to delete ALL stored emails? (y/n): ")

                if confirm.lower() == 'y':
                    confirm2 = input("This action cannot be undone. Type 'DELETE ALL' to confirm: ")

                    if confirm2 == 'DELETE ALL':
                        deleted_count = clear_stored_emails()
                        print(_t("email_service.deleted_all", count=deleted_count))
                    else:
                        print(_t("email_service.operation_cancelled"))
                else:
                    print(_t("email_service.operation_cancelled"))

                input("\nPress Enter to continue...")
            else:
                # Back (non-admin option 6)
                break

        elif choice == '7' and is_admin:
            # Export to CSV (admin only)
            try:
                filename = input("Enter CSV filename (default: stored_emails.csv): ") or "stored_emails.csv"
                emails_data = get_stored_emails(limit=10000)  # Get all emails

                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['id', 'recipient_email', 'subject', 'sender_email', 'sender_name',
                                'cc_recipients', 'bcc_recipients', 'created_date', 'template_name', 'body']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    writer.writeheader()
                    for email in emails_data['emails']:
                        writer.writerow({
                            'id': email['id'],
                            'recipient_email': email['recipient_email'],
                            'subject': email['subject'],
                            'sender_email': email['sender_email'],
                            'sender_name': email['sender_name'],
                            'cc_recipients': email['cc_recipients'],
                            'bcc_recipients': email['bcc_recipients'],
                            'created_date': email['created_date'],
                            'template_name': email['template_name'],
                            'body': email['body']
                        })

                print(_t("email_service.exported_count", count=len(emails_data['emails']), filename=filename))

            except Exception as e:
                print(_t("email_service.export_error", error=str(e)))

            input("\nPress Enter to continue...")

        elif choice == '8' and is_admin:
            break

        else:
            print(_t("email_service.invalid_choice"))
