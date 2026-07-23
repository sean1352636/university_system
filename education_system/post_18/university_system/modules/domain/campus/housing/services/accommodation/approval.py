import logging
from datetime import datetime

from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation._common import (
    sqlite3, DB_PATH, get_auth, get_current_user, backup_before_operation, get_text,
)
from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.db import init_accommodation_db
from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.audit import log_action
from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.notifications import notify_student
from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.crud import view_accommodation_by_id


def approve_accommodation():
    """Approve or reject pending accommodations."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_approve", "You must be logged in to approve accommodations."))
        return

    if not auth.check_permission('approve_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_approve", "You don't have permission to approve accommodations."))
        return

    # Backup before making changes
    backup_before_operation('accommodation_approval')

    init_accommodation_db()
    try:
        # Get list of pending accommodations
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.id, a.student_id, a.accommodation_type, a.description, a.start_date, a.end_date,
                       s.first_name, s.last_name
                FROM accommodations a
                JOIN students s ON a.student_id = s.student_id
                WHERE a.status = 'pending'
                ORDER BY a.created_at DESC
            ''')

            pending = cursor.fetchall()

        if not pending:
            print(get_text("housing.accommodation.message.no_pending_approvals", "No pending accommodations require approval."))
            return

        print(f"\nPending Accommodations ({len(pending)}):")
        print("=" * 80)
        print(f"{'ID':<5} {'Student':<20} {'Type':<20} {'Dates':<25} {'Desc':<20}")
        print("-" * 80)

        for acc in pending:
            student_name = f"{acc['student_id']} - {acc['first_name'] or ''} {acc['last_name'] or ''}".strip()
            dates = f"{acc['start_date'] or 'N/A'} to {acc['end_date'] or 'N/A'}"
            desc = acc['description'] or 'N/A'
            if len(desc) > 20:
                desc = desc[:17] + "..."

            print(f"{acc['id']:<5} {student_name[:20]:<20} {acc['accommodation_type'][:20]:<20} {dates[:25]:<25} {desc[:20]:<20}")

        print("=" * 80)

        # Get accommodation ID to approve/reject
        while True:
            id_str = input("\n" + get_text("housing.accommodation.input.enter_id_to_process", "Enter accommodation ID to process (or 'q' to quit): ")).strip()
            if id_str.lower() == 'q':
                return

            try:
                accommodation_id = int(id_str)
                # Check if this ID is in the pending list
                if not any(acc['id'] == accommodation_id for acc in pending):
                    print(get_text("housing.accommodation.error.not_pending_id", "Error: {id} is not a pending accommodation ID.").format(id=accommodation_id))
                    continue
                break
            except ValueError:
                print(get_text("housing.accommodation.error.valid_id_number", "Error: Please enter a valid ID number."))

        # Display the selected accommodation
        view_accommodation_by_id(accommodation_id)

        # Get approval decision
        print("\n" + get_text("housing.accommodation.label.approval_options", "Approval Options:"))
        print("1. " + get_text("housing.accommodation.menu.approve", "Approve"))
        print("2. " + get_text("housing.accommodation.menu.reject", "Reject"))
        print("3. " + get_text("housing.accommodation.menu.request_more_info", "Request more information"))
        print("4. " + get_text("housing.accommodation.menu.cancel", "Cancel"))

        decision = input(get_text("housing.accommodation.input.enter_choice_1_4", "Enter your choice (1-4): ")).strip()

        if decision == '4':
            print(get_text("housing.accommodation.message.approval_cancelled", "Approval process cancelled."))
            return

        # Get approval reason
        reason = input(get_text("housing.accommodation.input.reason_or_comments", "Enter reason or comments [optional]: ")).strip() or None

        # Process the decision
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user = get_current_user()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get the student ID for notification
            cursor.execute('SELECT student_id, accommodation_type FROM accommodations WHERE id = ?', (accommodation_id,))
            acc_info = cursor.fetchone()
            student_id = acc_info[0]
            acc_type = acc_info[1]

            if decision == '1':  # Approve
                cursor.execute('''
                    UPDATE accommodations SET
                    status = 'active',
                    approved_by = ?,
                    approval_date = ?,
                    notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END,
                    updated_at = ?
                    WHERE id = ?
                ''', (user, now, f"Approved: {reason}", f"Approved: {reason}", now, accommodation_id))

                action_type = 'approve'
                message = f"Your {acc_type} accommodation has been approved."
                if reason:
                    message += f" Comments: {reason}"

                print(get_text("housing.accommodation.success.approved", "Accommodation {id} approved.").format(id=accommodation_id))

            elif decision == '2':  # Reject
                cursor.execute('''
                    UPDATE accommodations SET
                    status = 'rejected',
                    approved_by = ?,
                    approval_date = ?,
                    notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END,
                    updated_at = ?
                    WHERE id = ?
                ''', (user, now, f"Rejected: {reason}", f"Rejected: {reason}", now, accommodation_id))

                action_type = 'reject'
                message = f"Your {acc_type} accommodation has been rejected."
                if reason:
                    message += f" Reason: {reason}"

                print(get_text("housing.accommodation.success.rejected", "Accommodation {id} rejected.").format(id=accommodation_id))

            elif decision == '3':  # Request more info
                cursor.execute('''
                    UPDATE accommodations SET
                    notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END,
                    updated_at = ?
                    WHERE id = ?
                ''', (f"More info requested: {reason}", f"More info requested: {reason}", now, accommodation_id))

                action_type = 'request_info'
                message = f"More information is required for your {acc_type} accommodation."
                if reason:
                    message += f" Details: {reason}"

                print(get_text("housing.accommodation.success.more_info_requested", "More information requested for accommodation {id}.").format(id=accommodation_id))

            conn.commit()

        # Log the action
        log_action(action_type, accommodation_id, f"{action_type.capitalize()} accommodation for {student_id}: {reason}")

        # Notify student
        from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

        subject, body = render_template('accommodation_notification', {
            'action_type': action_type.replace('_', ' ').title(),
            'message': message
        })

        if subject and body:
            notify_student(student_id, subject, body)

    except Exception as e:
        logging.error(f"Error in approve_accommodation: {e}")
        print(get_text("housing.accommodation.error.processing_approval", "Error processing accommodation approval: {error}").format(error=e))
