"""Helpdesk and support ticket notification emails."""

from __future__ import annotations

from datetime import datetime, timedelta

from education_system.university_system.infrastructure.database.db import sqlite3

from education_system.university_system.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.university_system.core.logs import handle_exception, log_event
from education_system.university_system.infrastructure.email.templates import render_template


@handle_exception
def send_ticket_notification(ticket_id, subject, username, admin_list=None):
    """Send an email notification when a new ticket is created"""
    from education_system.university_system.infrastructure.email.email_service.core import safe_log_email
    from education_system.university_system.infrastructure.email.email_service.queue import queue_email

    def _send_ticket_notification(cursor):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            SELECT category, priority, status
            FROM support_tickets
            WHERE ticket_id = ?
        ''', (ticket_id,))
        ticket_details = cursor.fetchone()

        if not ticket_details:
            log_event('error', f"Could not find ticket {ticket_id}")
            return False

        category, priority, status = ticket_details

        user_email = None

        cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (username,))
        result = cursor.fetchone()

        if result and result[0]:
            user_email = result[0]
        else:
            cursor.execute('SELECT email FROM users WHERE username = ? OR id = ?', (username, username))
            result = cursor.fetchone()

            if result and result[0]:
                user_email = result[0]

        if not user_email:
            log_event('error', f"Could not find email for user {username}")
            return False

        user_subject, user_body = render_template('helpdesk_ticket_created_user', {
            'username': username,
            'ticket_id': ticket_id,
            'subject': subject,
            'category': category,
            'priority': priority,
            'status': status or 'Open'
        })

        success = queue_email(user_email, user_subject, user_body)

        if success:
            safe_log_email(cursor, user_email, user_subject, current_time, 'sent',
                          related_to=f"Ticket #{ticket_id} Creation")

        return success

    try:
        result = execute_db_operation(_send_ticket_notification)

        if result and admin_list:
            for admin in admin_list:
                admin_username = admin[0]
                def _notify_admin(cursor):
                    admin_email = None

                    cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (admin_username,))
                    admin_result = cursor.fetchone()

                    if admin_result and admin_result[0]:
                        admin_email = admin_result[0]
                    else:
                        cursor.execute('SELECT email FROM users WHERE username = ? OR id = ?', (admin_username, admin_username))
                        admin_result = cursor.fetchone()

                        if admin_result and admin_result[0]:
                            admin_email = admin_result[0]

                    if admin_email:
                        cursor.execute('''
                            SELECT category, priority, status, description, created_at, user_id
                            FROM support_tickets
                            WHERE ticket_id = ?
                        ''', (ticket_id,))
                        ticket_details = cursor.fetchone()

                        if ticket_details:
                            category, priority, status, description, created_at, user_id = ticket_details
                            admin_subject, admin_body = render_template('helpdesk_ticket_created_admin', {
                                'ticket_id': ticket_id,
                                'username': username,
                                'subject': subject,
                                'category': category,
                                'priority': priority,
                                'status': status or 'Open',
                                'description': description or 'No description provided.',
                                'created_at': created_at,
                                'created_by': user_id or username
                            })
                            return queue_email(admin_email, admin_subject, admin_body)
                    return False

                execute_db_operation(_notify_admin)

        if result:
            log_event('info', f"Ticket notification sent for ticket #{ticket_id}")

        return result

    except Exception as e:
        log_event('error', f"Error sending ticket notification: {e}")
        return False

@handle_exception
def send_reply_notification(ticket_id, user_id=None, username=None, responder=None, admin_list=None, status_update=None):
    """Send an email notification when a ticket is replied to or status updated"""
    from education_system.university_system.infrastructure.email.email_service.queue import queue_email

    def _send_reply_notification(cursor):
        cursor.execute('SELECT subject FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        ticket_result = cursor.fetchone()

        if not ticket_result:
            log_event('error', f"Could not find ticket with ID {ticket_id}")
            return False

        ticket_subject = ticket_result[0]
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        success = True

        if username:
            user_email = None

            cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (username,))
            user_result = cursor.fetchone()

            if user_result and user_result[0]:
                user_email = user_result[0]
            else:
                cursor.execute('SELECT email FROM users WHERE username = ? OR id = ?', (username, username))
                user_result = cursor.fetchone()

                if user_result and user_result[0]:
                    user_email = user_result[0]

            if user_email:

                if status_update:
                    user_subject, user_body = render_template('support_ticket_status_changed', {
                        'username': username,
                        'ticket_id': ticket_id,
                        'subject': ticket_subject,
                        'old_status': '',
                        'new_status': status_update.upper()
                    })
                else:
                    user_subject, user_body = render_template('support_ticket_reply', {
                        'username': username,
                        'ticket_id': ticket_id,
                        'subject': ticket_subject,
                        'replied_by': responder
                    })

                if queue_email(user_email, user_subject, user_body):
                    cursor.execute('''
                    INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (
                        user_email,
                        user_subject,
                        current_time,
                        'sent',
                        f"Ticket #{ticket_id} Update"
                    ))
                else:
                    success = False

        return success

    try:
        result = execute_db_operation(_send_reply_notification)

        if result and admin_list:
            for admin in admin_list:
                admin_username = admin[0]
                if admin_username != responder:
                    def _notify_admin(cursor):
                        admin_email = None
                        cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (admin_username,))
                        admin_result = cursor.fetchone()
                        if admin_result and admin_result[0]:
                            admin_email = admin_result[0]
                        else:
                            cursor.execute('SELECT email FROM users WHERE username = ? OR id = ?', (admin_username, admin_username))
                            admin_result = cursor.fetchone()
                            if admin_result and admin_result[0]:
                                admin_email = admin_result[0]

                        if admin_email:

                            if status_update:
                                admin_subject, admin_body = render_template('support_ticket_status_changed_admin', {
                                    'ticket_id': ticket_id,
                                    'username': username,
                                    'subject': ticket_subject,
                                    'old_status': '',
                                    'new_status': status_update.upper()
                                })
                            else:
                                admin_subject, admin_body = render_template('support_ticket_reply_admin', {
                                    'ticket_id': ticket_id,
                                    'subject': ticket_subject,
                                    'replied_by': responder,
                                    'username': username
                                })

                            return queue_email(admin_email, admin_subject, admin_body)
                        return False

                    execute_db_operation(_notify_admin)

        if result:
            log_event('info', f"Reply notification sent for ticket #{ticket_id}")

        return result

    except Exception as e:
        log_event('error', f"Error sending reply notification: {e}")
        return False

@handle_exception
def send_sla_alert(ticket_id, alert_type='overdue'):
    """Send SLA alert notifications for tickets"""
    from education_system.university_system.infrastructure.email.email_service.queue import queue_email

    def _send_sla_alert(cursor):
        cursor.execute('''
        SELECT t.ticket_id, t.subject, t.priority, t.due_date, t.created_at,
               u1.username as submitter, u1.email as submitter_email,
               u2.username as assignee, u2.email as assignee_email,
               t.department
        FROM support_tickets t
        JOIN users u1 ON t.user_id = u1.id
        LEFT JOIN users u2 ON t.assigned_to = u2.id
        WHERE t.ticket_id = ?
        ''', (ticket_id,))

        ticket_info = cursor.fetchone()

        if not ticket_info:
            log_event('error', f"Ticket {ticket_id} not found for SLA alert")
            return False

        ticket_id_val, subject, priority, due_date, created_at, submitter, submitter_email, assignee, assignee_email, department = ticket_info

        template_vars = {
            'ticket_id': ticket_id_val,
            'subject': subject,
            'priority': priority.upper(),
            'due_date': due_date,
            'submitter': submitter,
            'submitter_email': submitter_email,
            'assignee': assignee or 'Unassigned',
            'department': department or 'None',
            'created_at': created_at
        }

        if alert_type == 'overdue':
            alert_subject, alert_body = render_template('sla_alert_overdue', template_vars)
        elif alert_type == 'escalation':
            alert_subject, alert_body = render_template('sla_alert_escalation', template_vars)
        else:
            alert_subject, alert_body = render_template('sla_alert_general', template_vars)

        recipients = []

        if assignee_email:
            recipients.append(assignee_email)

        cursor.execute('''
        SELECT DISTINCT u.email
        FROM users u
        LEFT JOIN departments d ON u.id = d.manager_id
        WHERE (u.role = 'admin' AND u.is_active = 1)
           OR (d.name = ? AND u.is_active = 1)
        ''', (department,))

        admin_emails = [row[0] for row in cursor.fetchall() if row[0]]
        recipients.extend(admin_emails)

        recipients = list(set(recipients))

        success_count = 0
        for recipient_email in recipients:
            if queue_email(recipient_email, alert_subject, alert_body):
                success_count += 1

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            f"SLA Alert ({len(recipients)} recipients)",
            alert_subject,
            current_time,
            'sent' if success_count > 0 else 'failed',
            f"SLA Alert for Ticket #{ticket_id}"
        ))

        return success_count > 0

    try:
        result = execute_db_operation(_send_sla_alert)
        if result:
            log_event('info', f"SLA alert sent for ticket #{ticket_id}")
        return result
    except Exception as e:
        log_event('error', f"Error sending SLA alert for ticket {ticket_id}: {e}")
        return False

@handle_exception
def send_satisfaction_survey(ticket_id, custom_message=None):
    """Send customer satisfaction survey for resolved tickets"""
    from education_system.university_system.infrastructure.email.email_service.queue import queue_email

    def _send_satisfaction_survey(cursor):
        cursor.execute('''
        SELECT t.ticket_id, COALESCE(t.subject, t.title) as subject,
               COALESCE(t.resolved_at, t.closed_at) as resolved_at, t.status,
               u.username, u.email, u.first_name, u.last_name
        FROM support_tickets t
        JOIN users u ON t.user_id = u.id
        WHERE t.ticket_id = ?
        ''', (ticket_id,))

        ticket_info = cursor.fetchone()

        if not ticket_info:
            log_event('error', f"Ticket {ticket_id} not found for satisfaction survey")
            return False

        tk_id, subject, resolved_at, status, username, email, first_name, last_name = ticket_info

        if status not in ['resolved', 'closed']:
            log_event('warning', f"Cannot send satisfaction survey for ticket {ticket_id} - status is {status}")
            return False

        customer_name = f"{first_name} {last_name}".strip() if first_name or last_name else username

        if custom_message:
            survey_subject = f"How did we do? Feedback requested for Ticket #{ticket_id}"
            survey_body = custom_message
        else:
            survey_subject, survey_body = render_template('satisfaction_survey', {
                'customer_name': customer_name,
                'ticket_id': ticket_id,
                'subject': subject,
                'resolved_at': resolved_at
            })

        success = queue_email(email, survey_subject, survey_body)

        if success:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            INSERT INTO email_log (recipient, subject, sent_date, status, related_to, student_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                email,
                survey_subject,
                current_time,
                'sent',
                f"Satisfaction Survey for Ticket #{ticket_id}",
                None
            ))

            log_event('info', f"Satisfaction survey sent for ticket #{ticket_id} to {email}")

        return success

    try:
        result = execute_db_operation(_send_satisfaction_survey)
        if result:
            log_event('info', f"Satisfaction survey sent for ticket #{ticket_id}")
        return result
    except Exception as e:
        log_event('error', f"Error sending satisfaction survey for ticket {ticket_id}: {e}")
        return False

@handle_exception
def send_bulk_satisfaction_surveys(days_old=1):
    """Send satisfaction surveys for tickets resolved in the last N days"""
    def _send_bulk_surveys(cursor):
        cutoff_date = (datetime.now() - timedelta(days=days_old)).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        SELECT t.ticket_id
        FROM support_tickets t
        WHERE t.status IN ('resolved', 'closed')
          AND t.resolved_at >= ?
          AND t.ticket_id NOT IN (
              SELECT DISTINCT CAST(SUBSTR(related_to,
                  INSTR(related_to, '#') + 1,
                  INSTR(related_to || ' ', ' ') - INSTR(related_to, '#') - 1
              ) AS INTEGER)
              FROM email_log
              WHERE related_to LIKE 'Satisfaction Survey for Ticket #%'
          )
        ''', (cutoff_date,))

        ticket_ids = [row[0] for row in cursor.fetchall()]

        success_count = 0
        for tid in ticket_ids:
            if send_satisfaction_survey(tid):
                success_count += 1

        return success_count, len(ticket_ids)

    try:
        result = execute_db_operation(_send_bulk_surveys)
        if result:
            success_count, total_count = result
            log_event('info', f"Bulk satisfaction surveys: {success_count}/{total_count} sent successfully")
        return result
    except Exception as e:
        log_event('error', f"Error sending bulk satisfaction surveys: {e}")
        return 0, 0
