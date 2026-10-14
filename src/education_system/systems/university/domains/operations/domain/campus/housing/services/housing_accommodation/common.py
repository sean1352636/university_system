from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager
import datetime
import logging
import os
import random
import string
# Use logging helpers from the refactored utils module
from education_system.systems.university.infrastructure.i18n import (
    get_text,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.language_selector import (
    display_language_menu_option,
)
from education_system.systems.university.infrastructure.utils.activity_logger import (
    log_activity,
    log_create,
    log_read,
    log_update,
    log_delete,
    log_search,
    log_export,
    log_menu_navigation,
)
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domains.finance.infrastructure.finance_integration import record_payment_to_finance

# Global variable to store the auth instance
# Import auth instance management from user_authentication
try:
    from education_system.systems.university.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)

def generate_id(prefix):
    """Generate a unique ID with a given prefix"""
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{timestamp}-{random_chars}"


def housing_text(key, default, **kwargs):
    """``get_text`` that also substitutes into the *default*.

    ``get_text(key, default=..., **kwargs)`` only applies the kwargs when
    the key resolves to a real translation; when it falls through to the
    default it returns it verbatim, so a default carrying ``{name}`` is
    delivered to the operator with the braces still in it. The university
    locale files under ``var/`` are per-install runtime data and are not
    all present everywhere, so that fallback is the common case for a
    newly added string, not a rare one.

    Formatting is best-effort in both directions: a translation carrying a
    placeholder the caller did not supply is printed as-is rather than
    raising, which is the same forgiving behaviour ``get_text`` has.
    """
    message = get_text(key, default=default)
    if not kwargs:
        return message
    try:
        return message.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return message


# ---------------------------------------------------------------------------
# Student notifications
# ---------------------------------------------------------------------------
# These route through the university email system
# (``infrastructure.email``): ``render_template`` fills one of the JSON
# templates under ``assets/templates/email/campus_services/housing/`` and
# ``send_email`` stores it *and* raises the student's inbox message, so the
# mail shows up in the Email module the same way every other university mail
# does. Both the housing CLI and the housing GUI call these, so a student
# gets identical wording whichever interface the operator used.

logger = logging.getLogger(__name__)

# Path-qualified template names. A bare basename resolves through a mapping
# file / directory-order fallback that has previously served the wrong
# template, so always qualify.
# An assignment in one of these states is "live": the student either lives
# there now or is about to. Defined here rather than in assignments.py so the
# email helpers below can use it without importing that module.
LIVE_ASSIGNMENT_STATUSES = ('Active', 'Reserved', 'Pending')

_HOUSING_TEMPLATE_DIR = "campus_services/housing"
RELOCATION_TEMPLATE = f"{_HOUSING_TEMPLATE_DIR}/accommodation_relocation_notice"
APPLICATION_SUBMITTED_TEMPLATE = f"{_HOUSING_TEMPLATE_DIR}/accommodation_application_submitted"
APPLICATION_OVERWRITTEN_TEMPLATE = f"{_HOUSING_TEMPLATE_DIR}/accommodation_application_overwritten"
APPLICATION_OUTCOME_TEMPLATE = f"{_HOUSING_TEMPLATE_DIR}/accommodation_application_outcome"


def send_housing_template_email(template_name, recipient_email, template_vars):
    """Render *template_name* and hand it to the university email system.

    Best-effort: a missing address, an unavailable email service or a
    delivery failure is logged and reported as ``False``. It never
    propagates, because by the time we notify the student the database
    work that triggered the email has already been committed — failing
    the caller here would misreport a change that did happen.
    """
    address = (recipient_email or '').strip()
    if not address:
        logger.warning("Housing email '%s' not sent: no recipient address", template_name)
        return False

    try:
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email,
        )
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
    except ImportError as exc:
        logger.warning("Housing email '%s' not sent: email system unavailable (%s)",
                       template_name, exc)
        return False

    try:
        subject, body = render_template(template_name, template_vars)
        if subject is None or body is None:
            logger.error("Housing email '%s' not sent: template failed to render",
                         template_name)
            return False
        send_email(recipient_email=address, subject=subject, body=body)
        return True
    except Exception as exc:
        logger.exception("Housing email '%s' to %s failed: %s", template_name, address, exc)
        return False


def send_relocation_email(move):
    """Tell a student they have been moved to a different room.

    *move* is one of the applied-move dicts returned by
    ``relocation.relocate_residents``.
    """
    return send_housing_template_email(RELOCATION_TEMPLATE, move.get('email_address'), {
        'student_name': move.get('student_name') or 'Student',
        'student_id': move.get('student_id', ''),
        'relocation_reason': move.get('reason', ''),
        'new_building_name': move.get('new_building_name', ''),
        'new_room_number': move.get('new_room_number', ''),
        'new_floor_number': move.get('new_floor_number', ''),
        'new_room_type': move.get('new_room_type', ''),
        'new_building_address': move.get('new_building_address', ''),
        'new_campus_location': move.get('new_campus_location', ''),
        'old_building_name': move.get('old_building_name', ''),
        'old_room_number': move.get('old_room_number', ''),
        'old_floor_number': move.get('old_floor_number', ''),
        'assignment_id': move.get('assignment_id', ''),
        'contract_number': move.get('contract_number', ''),
        'monthly_rent': f"{float(move.get('monthly_rent') or 0):.2f}",
        'move_in_date': move.get('move_in_date', ''),
        'move_out_date': move.get('planned_move_out_date', ''),
        'relocation_date': move.get('relocated_at', ''),
    })


def _application_email_vars(application):
    """Template variables shared by the three application emails."""
    move_in = application.get('move_in_date') or ''
    duration = application.get('duration_months')
    end_date = ''
    if move_in and duration:
        try:
            end_date = (
                datetime.datetime.strptime(move_in, '%Y-%m-%d')
                + datetime.timedelta(days=30 * int(duration))
            ).strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            end_date = ''

    return {
        'student_name': application.get('student_name') or 'Student',
        'student_id': application.get('student_id', ''),
        'application_id': application.get('application_id', ''),
        'submission_date': application.get('submission_date', ''),
        'submitted_by': application.get('submitted_by') or 'you',
        'preferred_building': application.get('preferred_building') or 'No preference',
        'preferred_room_type': application.get('room_type', ''),
        'move_in_date': move_in,
        'duration_months': duration if duration is not None else '',
        'end_date': end_date or 'To be confirmed',
        'special_requirements': application.get('special_requirements') or 'None',
        'status': application.get('status', 'Pending'),
    }


def send_application_submitted_email(application):
    """Confirm a new housing application, echoing back what was entered."""
    return send_housing_template_email(
        APPLICATION_SUBMITTED_TEMPLATE,
        application.get('email_address'),
        _application_email_vars(application),
    )


def send_application_overwritten_email(application, superseded=None):
    """Confirm that a new application has replaced the student's previous one(s)."""
    rows = superseded or []
    if rows:
        summary = "\n".join(
            f"- {row.get('application_id')} (submitted {row.get('application_date')}, "
            f"was '{row.get('status')}') - now withdrawn"
            for row in rows
        )
    else:
        summary = "- (no details recorded)"

    template_vars = _application_email_vars(application)
    template_vars['superseded_summary'] = summary
    return send_housing_template_email(
        APPLICATION_OVERWRITTEN_TEMPLATE,
        application.get('email_address'),
        template_vars,
    )


# Per-decision copy for the outcome email, keyed by the status written to
# housing_applications.status.
_APPLICATION_OUTCOMES = {
    'Approved': {
        'outcome_emoji': '✅',
        'outcome_headline': 'APPROVED',
        'outcome_message': (
            'Congratulations - your application has been approved and a room '
            'has been reserved for you. The details are below.'
        ),
        'next_steps': (
            '1. Confirm your acceptance in the Housing Portal within 72 hours.\n'
            '2. Complete your housing agreement and emergency contact details.\n'
            '3. Collect your key from the Housing Office on your move-in date.\n'
            '4. Complete the move-in inventory checklist within 7 days of arriving.'
        ),
    },
    'Rejected': {
        'outcome_emoji': '❌',
        'outcome_headline': 'NOT APPROVED',
        'outcome_message': (
            'We are sorry to tell you that your application has not been '
            "approved on this occasion. The reviewer's notes below explain why."
        ),
        'next_steps': (
            '1. You may appeal this decision within 10 working days by emailing '
            'housing@university.edu quoting your reference number.\n'
            '2. You may submit a new application for a different room type or '
            'building at any time - a new application replaces this one.\n'
            '3. The Accommodation Advice team can help you find private housing.'
        ),
    },
    'Waiting List': {
        'outcome_emoji': '⏳',
        'outcome_headline': 'ON THE WAITING LIST',
        'outcome_message': (
            'Your application has been placed on the waiting list. No room is '
            'available that matches your application right now, but you will be '
            'offered one as soon as a suitable room is released.'
        ),
        'next_steps': (
            '1. Keep this reference number - you do not need to reapply.\n'
            '2. We will email you as soon as a suitable room becomes available.\n'
            '3. Broadening your preferred room type or building usually shortens '
            'the wait - contact the Housing Office to update your preferences.'
        ),
    },
    'More Info Needed': {
        'outcome_emoji': '📄',
        'outcome_headline': 'MORE INFORMATION NEEDED',
        'outcome_message': (
            'We cannot finish reviewing your application yet because we need '
            "more information from you. The reviewer's notes below say what is "
            'missing.'
        ),
        'next_steps': (
            '1. Send the requested information to housing@university.edu, '
            'quoting your reference number.\n'
            '2. Your application stays open in the meantime - do not submit a '
            'new one, as that would replace this application.\n'
            '3. Review resumes as soon as we receive what we have asked for.'
        ),
    },
}


def send_application_outcome_email(application):
    """Tell a student the outcome of processing their application.

    *application* carries the keys used by ``_application_email_vars``
    plus ``application_date``, ``review_date``, ``reviewed_by``, ``notes``
    and — when a room was assigned — ``assignment_details``.
    """
    status = application.get('status') or ''
    template_vars = _application_email_vars(application)
    template_vars.update({
        'application_date': application.get('application_date', ''),
        'review_date': application.get('review_date', ''),
        'reviewed_by': application.get('reviewed_by') or 'University Housing Administration',
        'notes': application.get('notes') or 'No additional notes were recorded.',
        'assignment_details': application.get('assignment_details')
        or 'No room has been assigned to you at this stage.',
    })
    template_vars.update(_APPLICATION_OUTCOMES.get(status, {
        'outcome_emoji': '📋',
        'outcome_headline': 'UPDATED',
        'outcome_message': f"Your application status is now '{status}'.",
        'next_steps': ('If you have any questions about this decision, contact '
                       'the Housing Office.'),
    }))

    return send_housing_template_email(
        APPLICATION_OUTCOME_TEMPLATE,
        application.get('email_address'),
        template_vars,
    )


def format_assignment_details(building_name, room_number, floor_number, room_type,
                              monthly_rent, move_in_date, move_out_date,
                              contract_number):
    """Render the room block used by the approved outcome email."""
    return (
        f"Building: {building_name}\n"
        f"Room Number: {room_number}\n"
        f"Floor Number: {floor_number}\n"
        f"Room Type: {room_type}\n"
        f"Monthly Rent: £{float(monthly_rent or 0):.2f}\n"
        f"Move-In Date: {move_in_date}\n"
        f"Planned Move-Out Date: {move_out_date}\n"
        f"Contract Number: {contract_number}"
    )


# ---------------------------------------------------------------------------
# Operational notifications (assignments, maintenance, payments, inspections)
# ---------------------------------------------------------------------------

ASSIGNMENT_CREATED_TEMPLATE = f"{_HOUSING_TEMPLATE_DIR}/housing_assignment_created"
MAINTENANCE_STUDENT_TEMPLATE = "campus_services/maintenance/maintenance_request_created"
MAINTENANCE_ADMIN_TEMPLATE = f"{_HOUSING_TEMPLATE_DIR}/housing_maintenance_admin_alert"
PAYMENT_RECEIPT_TEMPLATE = f"{_HOUSING_TEMPLATE_DIR}/housing_payment_receipt"
INSPECTION_SCHEDULED_TEMPLATE = f"{_HOUSING_TEMPLATE_DIR}/inspection_scheduled"
INSPECTION_COMPLETED_TEMPLATE = f"{_HOUSING_TEMPLATE_DIR}/inspection_completed"
INSPECTION_FOLLOW_UP_TEMPLATE = f"{_HOUSING_TEMPLATE_DIR}/inspection_follow_up"
REPORT_ADMIN_TEMPLATE = f"{_HOUSING_TEMPLATE_DIR}/housing_report_admin"


def get_admin_recipients(limit=5):
    """Admin addresses to copy on housing events, as ``[(name, email), ...]``.

    Reads the university ``users`` table — the same lookup the other campus
    CLIs use for their admin alerts — so the address follows whoever is
    actually set up as an admin rather than a constant baked into the code.
    Returns ``[]`` rather than raising when there is no admin or no users
    table; the caller treats that as "nobody to notify".
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
            recipients.append((row[0] or 'Housing Administrator', row[1]))
    except Exception as exc:
        logger.warning("Could not resolve admin recipients: %s", exc)
    return recipients


def room_occupants(cursor, room_id, exclude_student_id=None):
    """Everyone with a live assignment in *room_id*.

    Used to tell a whole flat / shared room who has just moved in with them.
    """
    placeholders = ','.join('?' * len(LIVE_ASSIGNMENT_STATUSES))
    cursor.execute('''
    SELECT a.student_id, s.first_name, s.last_name, s.email_address, a.assignment_id
    FROM housing_assignments a
    JOIN students s ON a.student_id = s.student_id
    WHERE a.room_id = ? AND a.status IN ({statuses})
    ORDER BY s.last_name, s.first_name
    '''.format(statuses=placeholders), [room_id] + list(LIVE_ASSIGNMENT_STATUSES))

    occupants = []
    for row in cursor.fetchall():
        if exclude_student_id and row[0] == exclude_student_id:
            continue
        occupants.append({
            'student_id': row[0],
            'student_name': f"{row[1] or ''} {row[2] or ''}".strip() or row[0],
            'email_address': row[3],
            'assignment_id': row[4],
        })
    return occupants


def send_assignment_created_emails(assignment, occupants):
    """Tell everyone in the room that an assignment has been made.

    The student who was assigned gets a "your room is confirmed" wording and
    their existing flatmates get a "someone is moving in with you" wording,
    from the same template. Returns ``(sent, failed)``.
    """
    roster = "\n".join(
        f"  - {person['student_name']} ({person['student_id']})"
        for person in occupants
    ) or "  (no other residents recorded)"

    base = {
        'building_name': assignment.get('building_name', ''),
        'room_number': assignment.get('room_number', ''),
        'floor_number': assignment.get('floor_number', ''),
        'room_type': assignment.get('room_type', ''),
        'building_address': assignment.get('building_address', ''),
        'campus_location': assignment.get('campus_location', ''),
        'occupant_list': roster,
        'current_occupants': assignment.get('current_occupants', ''),
        'max_occupants': assignment.get('max_occupants', ''),
        'student_name': assignment.get('student_name', ''),
        'student_id': assignment.get('student_id', ''),
        'assignment_id': assignment.get('assignment_id', ''),
        'contract_number': assignment.get('contract_number', ''),
        'monthly_rent': f"{float(assignment.get('monthly_rent') or 0):.2f}",
        'move_in_date': assignment.get('move_in_date', ''),
        'move_out_date': assignment.get('planned_move_out_date', ''),
        'assigned_by': assignment.get('assigned_by', ''),
        'assigned_date': assignment.get('assigned_date', ''),
    }

    sent = failed = 0
    for person in occupants:
        template_vars = dict(base)
        template_vars['recipient_name'] = person['student_name']
        if person['student_id'] == assignment.get('student_id'):
            template_vars['intro_line'] = (
                "Your room assignment has been confirmed. Here is everything "
                "you need to know about where you are living.")
        else:
            template_vars['intro_line'] = (
                f"{assignment.get('student_name', 'A new resident')} has been "
                f"assigned to your room, so you will be sharing with them.")

        if send_housing_template_email(ASSIGNMENT_CREATED_TEMPLATE,
                                       person['email_address'], template_vars):
            sent += 1
        else:
            failed += 1
    return sent, failed


# Response and completion targets by priority. Both the student
# acknowledgement and the admin alert quote these, so a resident and the
# person triaging their request are working to the same numbers.
_PRIORITY_RESPONSE = {
    'Emergency': 'Emergency - respond within 2 hours.',
    'High': 'High - respond within 24 hours.',
    'Medium': 'Medium - respond within 2-3 business days.',
    'Low': 'Low - respond within 5-7 business days.',
}

_PRIORITY_COMPLETION = {
    'Emergency': 'Same day wherever possible.',
    'High': "Within 3 business days of the technician's first visit.",
    'Medium': 'Within 5-7 business days.',
    'Low': 'Within 10-15 business days.',
}


def send_maintenance_student_email(request):
    """Acknowledge a maintenance request to the student who raised it."""
    priority = request.get('priority', '')
    return send_housing_template_email(
        MAINTENANCE_STUDENT_TEMPLATE, request.get('student_email'), {
            'student_name': request.get('student_name') or 'Student',
            'request_id': request.get('request_id', ''),
            'issue_type': request.get('issue_type', ''),
            'priority': priority,
            'created_by': request.get('submitted_by', ''),
            'created_date': request.get('request_date', ''),
            'location': (f"{request.get('building_name', '')}, Room "
                         f"{request.get('room_number', '')}"),
            'description': request.get('description', ''),
            'status': request.get('status', 'Pending'),
            'estimated_response': _PRIORITY_RESPONSE.get(
                priority, 'Per the standard priority response times.'),
            'estimated_completion': _PRIORITY_COMPLETION.get(
                priority, 'To be confirmed once a technician has assessed the issue.'),
        })


def send_maintenance_admin_emails(request):
    """Alert the housing admins that a request needs triage.

    Returns ``(sent, failed)``. ``(0, 0)`` means no admin address is
    configured, which the caller reports rather than silently swallowing.
    """
    recipients = get_admin_recipients()
    if not recipients:
        logger.warning("No admin email configured; maintenance request %s not escalated",
                       request.get('request_id'))
        return 0, 0

    base = {
        'request_id': request.get('request_id', ''),
        'priority': request.get('priority', ''),
        'issue_type': request.get('issue_type', ''),
        'status': request.get('status', 'Pending'),
        'request_date': request.get('request_date', ''),
        'submitted_by': request.get('submitted_by', ''),
        'building_name': request.get('building_name', ''),
        'room_number': request.get('room_number', ''),
        'floor_number': request.get('floor_number', '-'),
        'room_type': request.get('room_type', '-'),
        'student_name': request.get('student_name', ''),
        'student_id': request.get('student_id', ''),
        'student_email': request.get('student_email') or 'not recorded',
        'description': request.get('description', ''),
        'response_target': _PRIORITY_RESPONSE.get(
            request.get('priority', ''), 'Per the standard priority response times.'),
    }

    sent = failed = 0
    for admin_name, admin_email in recipients:
        template_vars = dict(base, admin_name=admin_name)
        if send_housing_template_email(MAINTENANCE_ADMIN_TEMPLATE,
                                       admin_email, template_vars):
            sent += 1
        else:
            failed += 1
    return sent, failed


def send_payment_receipt_email(payment):
    """Email the student their housing payment receipt.

    When the payment was taken from the student's finance account, the
    receipt also states what was drawn down and what is left, which is the
    one thing a finance-account payer cannot see from the payment row.
    """
    period_line = ''
    if payment.get('period_start') and payment.get('period_end'):
        period_line = (f"Period Covered: {payment['period_start']} to "
                       f"{payment['period_end']}")

    finance_block = ''
    if payment.get('finance_account_used'):
        finance_block = (
            "=== YOUR FINANCE ACCOUNT ===\n"
            f"Paid from your student finance account.\n"
            f"Balance before this payment: £{float(payment.get('balance_before') or 0):,.2f}\n"
            f"Amount taken: £{float(payment.get('amount') or 0):,.2f}\n"
            f"Remaining balance: £{float(payment.get('balance_after') or 0):,.2f}"
        )

    return send_housing_template_email(
        PAYMENT_RECEIPT_TEMPLATE, payment.get('student_email'), {
            'student_name': payment.get('student_name') or 'Student',
            'student_id': payment.get('student_id', ''),
            'payment_id': payment.get('payment_id', ''),
            'payment_type': payment.get('payment_type', ''),
            'amount': f"{float(payment.get('amount') or 0):,.2f}",
            'payment_method': payment.get('payment_method', ''),
            'payment_date': payment.get('payment_date', ''),
            'status': payment.get('status', 'Completed'),
            'transaction_reference': payment.get('transaction_reference') or 'Not supplied',
            'processed_by': payment.get('processed_by', ''),
            'building_name': payment.get('building_name', ''),
            'room_number': payment.get('room_number', ''),
            'assignment_id': payment.get('assignment_id', ''),
            'period_line': period_line,
            'finance_account_block': finance_block,
            'finance_reference': payment.get('finance_reference') or 'Pending',
        })


def _inspection_vars(inspection):
    return {
        'student_name': inspection.get('student_name') or 'Student',
        'student_id': inspection.get('student_id', ''),
        'inspection_id': inspection.get('inspection_id', ''),
        'building_name': inspection.get('building_name', ''),
        'room_number': inspection.get('room_number', ''),
        'floor_number': inspection.get('floor_number', '-'),
        'inspection_date': inspection.get('inspection_date', ''),
        'inspection_time': inspection.get('inspection_time') or 'To be confirmed',
        'inspection_type': inspection.get('inspection_type', ''),
        'inspector_name': inspection.get('inspector') or 'Housing Inspector',
        'status': inspection.get('status', ''),
        'findings': inspection.get('findings') or 'No findings were recorded.',
        'action_required': inspection.get('action_required') or 'No specific action was recorded.',
        'notes': inspection.get('notes', ''),
    }


def send_inspection_scheduled_email(inspection):
    """Tell the resident an inspection has been booked for their room."""
    return send_housing_template_email(
        INSPECTION_SCHEDULED_TEMPLATE, inspection.get('student_email'),
        _inspection_vars(inspection))


def send_inspection_completed_email(inspection):
    """Tell the resident the outcome of a completed inspection."""
    template_vars = _inspection_vars(inspection)
    status = inspection.get('status', '')
    template_vars['pass_fail'] = {
        'Passed': 'PASSED - no further action needed',
        'Failed': 'FAILED - action is required',
        'Needs Follow-up': 'FOLLOW-UP REQUIRED',
        'Incomplete': 'INCOMPLETE - the inspection could not be finished',
    }.get(status, status)

    if inspection.get('follow_up_date'):
        template_vars['follow_up_instructions'] = (
            f"A follow-up inspection is scheduled for "
            f"{inspection['follow_up_date']}. Please address the points above "
            f"before then.")
    elif status == 'Passed':
        template_vars['follow_up_instructions'] = (
            "No follow-up is needed. Thank you for keeping your room in good order.")
    else:
        template_vars['follow_up_instructions'] = (
            "The Housing Office will be in touch if a follow-up is needed.")
    return send_housing_template_email(
        INSPECTION_COMPLETED_TEMPLATE, inspection.get('student_email'), template_vars)


def send_inspection_follow_up_email(inspection):
    """Tell the resident a follow-up has been booked, with the date and why."""
    template_vars = _inspection_vars(inspection)
    template_vars['follow_up_date'] = inspection.get('follow_up_date', '')
    template_vars['follow_up_reason'] = (
        inspection.get('follow_up_reason')
        or inspection.get('action_required')
        or 'The inspection needs to be repeated.')
    return send_housing_template_email(
        INSPECTION_FOLLOW_UP_TEMPLATE, inspection.get('student_email'), template_vars)


def send_report_to_admins(title, content, sender_name):
    """Email a generated housing report to the configured admins.

    Returns ``(sent, failed, addresses)`` so the caller can tell the
    operator exactly who it went to — or that no admin address is set up.
    """
    recipients = get_admin_recipients()
    if not recipients:
        return 0, 0, []

    generated = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sent = failed = 0
    addresses = []
    for admin_name, admin_email in recipients:
        ok = send_housing_template_email(REPORT_ADMIN_TEMPLATE, admin_email, {
            'admin_name': admin_name,
            'title': title,
            'content': content,
            'sender_name': sender_name or 'University Housing Management System',
            'generated_date': generated,
        })
        if ok:
            sent += 1
            addresses.append(admin_email)
        else:
            failed += 1
    return sent, failed, addresses
