from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.infrastructure.email.email_manager import (
    send_ticket_notification,
    send_reply_notification,
    send_sla_alert,
)
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)


def reply_to_ticket_enhanced(auth, ticket_id, is_internal=False):
    """Enhanced reply functionality with attachments and time tracking"""
    if not auth or not auth.current_user:
        print("You must be logged in to reply to a ticket.")
        return

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check permissions
    is_admin = auth.check_permission('reply_to_any_ticket')

    if not is_admin and not auth.check_permission('reply_to_own_ticket'):
        print("You don't have permission to reply to tickets.")
        conn.close()
        return

    if not is_admin:
        cursor.execute('''
        SELECT user_id FROM support_tickets WHERE ticket_id = ?
        ''', (ticket_id,))

        result = cursor.fetchone()
        if not result or result['user_id'] != auth.current_user['id']:
            print("You don't have permission to reply to this ticket.")
            conn.close()
            return

    # Get reply message
    reply_type = "internal note" if is_internal else "reply"
    print(f"\nEnter your {reply_type} (type 'done' on a new line when finished):")

    message = ""
    while True:
        line = input()
        if line.lower() == 'done':
            break
        message += line + "\n"

    if not message.strip():
        print("Error: Reply cannot be empty.")
        conn.close()
        return

    # Time tracking
    time_spent = 0
    if auth.check_permission('manage_tickets'):
        time_input = input("Time spent on this reply (hours, or press Enter to skip): ").strip()
        if time_input:
            try:
                time_spent = float(time_input)
            except ValueError:
                print("Invalid time format, skipping time tracking.")

    # Get current time
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Insert reply into database
    try:
        cursor.execute('''
        INSERT INTO ticket_replies
        (ticket_id, user_id, message, is_internal, time_spent, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (ticket_id, auth.current_user['id'], message, is_internal, time_spent, now))

        reply_id = cursor.lastrowid

        # Update ticket timestamps and status
        status_update = ""
        if not is_internal:
            if is_admin and auth.current_user['id'] != cursor.execute('SELECT user_id FROM support_tickets WHERE ticket_id = ?', (ticket_id,)).fetchone()[0]:
                # Admin replying to user ticket
                status_update = ", status = CASE WHEN status = 'open' THEN 'in progress' ELSE status END"

                # Record first response time if not set
                cursor.execute('''
                UPDATE support_tickets
                SET first_response_at = CASE WHEN first_response_at IS NULL THEN ? ELSE first_response_at END
                WHERE ticket_id = ?
                ''', (now, ticket_id))

        cursor.execute('''
        UPDATE support_tickets
        SET updated_at = ?, last_activity_at = ? ''' + status_update + '''
        WHERE ticket_id = ?
        ''', (now, now, ticket_id))

        conn.commit()

        # Handle file attachments
        from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.tickets.attachments import handle_file_attachments
        handle_file_attachments(ticket_id, reply_id, auth.current_user['id'])

        # Log the action
        from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.workflows import log_ticket_action, run_ticket_workflows
        log_ticket_action(ticket_id, auth.current_user['id'],
                         'internal_note_added' if is_internal else 'reply_added',
                         {}, {'message': message[:100] + '...' if len(message) > 100 else message})

        print(f"\n{reply_type.title()} added successfully!")

        # Send notifications (only for non-internal replies)
        if not is_internal:
            try:
                # Get ticket and user info
                cursor.execute('''
                SELECT t.user_id, t.subject, u1.username as submitter, u2.username as assignee
                FROM support_tickets t
                JOIN users u1 ON t.user_id = u1.id
                LEFT JOIN users u2 ON t.assigned_to = u2.id
                WHERE t.ticket_id = ?
                ''', (ticket_id,))

                ticket_info = cursor.fetchone()

                if is_admin:
                    # Admin replying to user
                    send_reply_notification(ticket_id, ticket_info['user_id'],
                                          ticket_info['submitter'], auth.current_user['username'])
                else:
                    # User replying, notify admins and assignee
                    recipients = []
                    if ticket_info['assignee']:
                        recipients.append((ticket_info['assignee'],))

                    # Add other admins
                    cursor.execute('''
                    SELECT username FROM users WHERE role = 'admin' AND username != ?
                    ''', (ticket_info['assignee'] or '',))
                    recipients.extend(cursor.fetchall())

                    if recipients:
                        send_reply_notification(ticket_id, None, None,
                                              auth.current_user['username'], admin_list=recipients)
            except Exception as e:
                print(f"Note: Could not send email notification: {e}")

        # Run workflows
        run_ticket_workflows(ticket_id, 'reply_added', user_role=auth.current_user['role'])

        # Check for SLA breach and send alert if overdue
        try:
            cursor.execute('''
                SELECT due_date, status
                FROM support_tickets
                WHERE ticket_id = ?
            ''', (ticket_id,))

            ticket_data = cursor.fetchone()
            if ticket_data and ticket_data[0]:  # if due_date exists
                due_date_str = ticket_data[0]
                status = ticket_data[1]

                # Parse due date
                try:
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%d %H:%M:%S')
                    current_time = datetime.now()

                    # If ticket is overdue and not resolved/closed
                    if current_time > due_date and status not in ['resolved', 'closed']:
                        send_sla_alert(ticket_id, alert_type='overdue')
                        print("\u26a0\ufe0f  SLA alert sent - ticket is overdue")
                except ValueError as e:
                    # Invalid date format, skip SLA check
                    logger.debug(f"Invalid due date format during SLA check: {e}")
        except Exception as e:
            print(f"Note: Could not check SLA status: {e}")

    except sqlite3.Error as e:
        print(f"Error adding reply: {e}")
    finally:
        conn.close()

def change_ticket_status_enhanced(auth, ticket_id):
    """Enhanced status change with resolution tracking"""
    if not auth or not auth.current_user:
        print("You must be logged in to update ticket status.")
        return

    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to update ticket status.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Get current ticket info
    cursor.execute('''
    SELECT status, resolution FROM support_tickets WHERE ticket_id = ?
    ''', (ticket_id,))

    result = cursor.fetchone()
    if not result:
        print(f"Ticket #{ticket_id} not found.")
        conn.close()
        return

    current_status, current_resolution = result

    print(f"\nCurrent status: {current_status.upper()}")
    print("\nAvailable statuses:")
    print("1. Open")
    print("2. In Progress")
    print("3. Waiting for Customer")
    print("4. Resolved")
    print("5. Closed")
    print("6. Cancelled")

    status_map = {
        "1": "open",
        "2": "in progress",
        "3": "waiting for customer",
        "4": "resolved",
        "5": "closed",
        "6": "cancelled"
    }

    while True:
        choice = input("Select new status (1-6): ").strip()
        if choice in status_map:
            new_status = status_map[choice]
            break
        print("Error: Invalid status selection.")

    if current_status == new_status:
        print(f"Status is already set to {new_status.upper()}.")
        conn.close()
        return

    # Get resolution details for resolved/closed tickets
    resolution = current_resolution
    if new_status in ['resolved', 'closed'] and not current_resolution:
        print("\nPlease provide resolution details:")
        resolution = ""
        while True:
            line = input()
            if line.lower() == 'done':
                break
            resolution += line + "\n"

        if not resolution.strip():
            print("Resolution details are required for resolved/closed tickets.")
            conn.close()
            return

    # Get current time
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    resolved_at = now if new_status in ['resolved', 'closed'] else None

    # Update ticket status
    try:
        cursor.execute('''
        UPDATE support_tickets
        SET status = ?, resolution = ?, resolved_at = ?, updated_at = ?, last_activity_at = ?
        WHERE ticket_id = ?
        ''', (new_status, resolution, resolved_at, now, now, ticket_id))

        conn.commit()

        # Log the action
        from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.workflows import log_ticket_action, run_ticket_workflows
        log_ticket_action(ticket_id, auth.current_user['id'], 'status_changed',
                         {'status': current_status}, {'status': new_status})

        print(f"\nTicket status updated to: {new_status.upper()}")

        # Add automatic system message about status change
        cursor.execute('''
        INSERT INTO ticket_replies
        (ticket_id, user_id, message, is_internal, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (ticket_id, auth.current_user['id'],
              f"*** Status changed from {current_status.upper()} to {new_status.upper()} ***",
              True, now))

        conn.commit()

        # Send satisfaction survey for resolved/closed tickets
        if new_status in ['resolved', 'closed']:
            send_survey = input("Send satisfaction survey to customer? (y/n): ").strip().lower()
            if send_survey == 'y':
                from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.notifications import send_satisfaction_survey
                send_satisfaction_survey(ticket_id)

        # Run workflows
        run_ticket_workflows(ticket_id, 'status_changed', new_status=new_status, old_status=current_status)

        # Send notifications
        try:
            cursor.execute('''
            SELECT t.user_id, u.username, t.subject
            FROM support_tickets t
            JOIN users u ON t.user_id = u.id
            WHERE t.ticket_id = ?
            ''', (ticket_id,))

            ticket_info = cursor.fetchone()

            send_reply_notification(
                ticket_id,
                ticket_info[0],
                ticket_info[1],
                auth.current_user['username'],
                status_update=new_status
            )
        except Exception as e:
            print(f"Note: Could not send email notification: {e}")

    except sqlite3.Error as e:
        print(f"Error updating ticket status: {e}")
    finally:
        conn.close()

def assign_ticket_enhanced(auth, ticket_id):
    """Enhanced ticket assignment with load balancing"""
    if not auth or not auth.current_user:
        print("You must be logged in to assign tickets.")
        return

    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to assign tickets.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Get current assignment
    cursor.execute('''
    SELECT assigned_to, department FROM support_tickets WHERE ticket_id = ?
    ''', (ticket_id,))

    result = cursor.fetchone()
    if not result:
        print(f"Ticket #{ticket_id} not found.")
        conn.close()
        return

    current_assigned, current_department = result

    print("\nAssignment Options:")
    print("1. Assign to specific user")
    print("2. Assign to department (auto-balance)")
    print("3. Unassign ticket")

    choice = input("Select option (1-3): ").strip()

    new_assigned = None
    new_department = current_department

    if choice == '1':
        # Show available staff
        cursor.execute('''
        SELECT id, username, role, department
        FROM users
        WHERE role IN ('staff', 'admin') AND is_active = 1
        ORDER BY department, username
        ''')

        staff = cursor.fetchall()

        if not staff:
            print("No available staff members found.")
            conn.close()
            return

        print("\nAvailable staff:")
        for i, member in enumerate(staff, 1):
            dept = member[3] or 'No Department'
            print(f"{i}. {member[1]} ({member[2]}) - {dept}")

        while True:
            try:
                staff_choice = int(input("Select staff member: ").strip())
                if 1 <= staff_choice <= len(staff):
                    new_assigned = staff[staff_choice - 1][0]
                    new_department = staff[staff_choice - 1][3] or current_department
                    break
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")

    elif choice == '2':
        # Show departments
        cursor.execute('''
        SELECT name FROM departments WHERE is_active = 1 ORDER BY name
        ''')

        departments = cursor.fetchall()

        if not departments:
            print("No active departments found.")
            conn.close()
            return

        print("\nAvailable departments:")
        for i, dept in enumerate(departments, 1):
            print(f"{i}. {dept[0]}")

        while True:
            try:
                dept_choice = int(input("Select department: ").strip())
                if 1 <= dept_choice <= len(departments):
                    new_department = departments[dept_choice - 1][0]

                    # Auto-assign to least loaded staff member in department
                    cursor.execute('''
                    SELECT u.id, COUNT(t.ticket_id) as ticket_count
                    FROM users u
                    LEFT JOIN support_tickets t ON u.id = t.assigned_to AND t.status NOT IN ('closed', 'resolved')
                    WHERE u.department = ? AND u.role IN ('staff', 'admin') AND u.is_active = 1
                    GROUP BY u.id
                    ORDER BY ticket_count ASC, u.last_login_at DESC
                    LIMIT 1
                    ''', (new_department,))

                    staff_result = cursor.fetchone()
                    if staff_result:
                        new_assigned = staff_result[0]

                    break
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")

    elif choice == '3':
        new_assigned = None
        new_department = None

    else:
        print("Invalid choice.")
        conn.close()
        return

    # Update assignment
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        cursor.execute('''
        UPDATE support_tickets
        SET assigned_to = ?, department = ?, updated_at = ?, last_activity_at = ?
        WHERE ticket_id = ?
        ''', (new_assigned, new_department, now, now, ticket_id))

        # Record assignment history
        cursor.execute('''
        INSERT INTO ticket_assignments
        (ticket_id, assigned_from, assigned_to, assignment_reason, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (ticket_id, current_assigned, new_assigned, 'Manual assignment', now))

        conn.commit()

        # Log the action
        from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.workflows import log_ticket_action
        old_values = {'assigned_to': current_assigned, 'department': current_department}
        new_values = {'assigned_to': new_assigned, 'department': new_department}
        log_ticket_action(ticket_id, auth.current_user['id'], 'assignment_changed', old_values, new_values)

        # Display result
        if new_assigned:
            cursor.execute("SELECT username FROM users WHERE id = ?", (new_assigned,))
            assignee_name = cursor.fetchone()[0]
            print(f"\nTicket assigned to: {assignee_name}")
            if new_department:
                print(f"Department: {new_department}")
        else:
            print("\nTicket unassigned.")

        # Send notification to new assignee
        if new_assigned:
            try:
                cursor.execute('''
                SELECT t.subject, u1.username as submitter, u2.username as assignee
                FROM support_tickets t
                JOIN users u1 ON t.user_id = u1.id
                JOIN users u2 ON t.assigned_to = u2.id
                WHERE t.ticket_id = ?
                ''', (ticket_id,))

                ticket_info = cursor.fetchone()
                send_ticket_notification(ticket_id, ticket_info[0], ticket_info[1], [(ticket_info[2],)])
            except Exception as e:
                print(f"Note: Could not send assignment notification: {e}")

    except sqlite3.Error as e:
        print(f"Error updating ticket assignment: {e}")
    finally:
        conn.close()

def add_time_entry(auth, ticket_id):
    """Add time tracking entry"""
    if not auth or not auth.current_user:
        print("You must be logged in to add time entries.")
        return

    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to add time entries.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nAdd Time Entry")
    print("==============")

    # Get time details
    while True:
        try:
            duration = float(input("Duration (hours): ").strip())
            if duration > 0:
                break
            else:
                print("Duration must be greater than 0.")
        except ValueError:
            print("Please enter a valid number.")

    description = input("Description (optional): ").strip()

    billable = input("Is this time billable? (y/n): ").strip().lower() == 'y'

    # Calculate duration in minutes
    duration_minutes = int(duration * 60)

    # Get current time
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    start_time = (datetime.now() - timedelta(hours=duration)).strftime('%Y-%m-%d %H:%M:%S')

    try:
        cursor.execute('''
        INSERT INTO ticket_time_tracking
        (ticket_id, user_id, start_time, end_time, duration_minutes, description, billable, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticket_id, auth.current_user['id'], start_time, now, duration_minutes,
              description, billable, now))

        conn.commit()

        # Log the action
        from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.workflows import log_ticket_action
        log_ticket_action(ticket_id, auth.current_user['id'], 'time_entry_added',
                         {}, {'duration': duration, 'billable': billable})

        print(f"\nTime entry added: {duration} hours")
        if billable:
            print("Marked as billable")

    except sqlite3.Error as e:
        print(f"Error adding time entry: {e}")
    finally:
        conn.close()

def link_tickets(auth, ticket_id):
    """Link tickets together"""
    if not auth or not auth.current_user:
        print("You must be logged in to link tickets.")
        return

    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to link tickets.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nLink Tickets")
    print("============")

    # Get ticket to link to
    linked_ticket_id = input("Enter ticket ID to link to: ").strip()

    try:
        linked_ticket_id = int(linked_ticket_id)

        # Check if target ticket exists
        cursor.execute('SELECT ticket_id, subject FROM support_tickets WHERE ticket_id = ?',
                      (linked_ticket_id,))
        target_ticket = cursor.fetchone()

        if not target_ticket:
            print("Target ticket not found.")
            conn.close()
            return

        if target_ticket[0] == ticket_id:
            print("Cannot link ticket to itself.")
            conn.close()
            return

        print(f"\nTarget ticket: #{target_ticket[0]} - {target_ticket[1]}")

        # Select link type
        print("\nLink types:")
        print("1. Related to")
        print("2. Duplicate of")
        print("3. Blocks")
        print("4. Blocked by")
        print("5. Parent of")
        print("6. Child of")

        link_types = {
            '1': 'related_to',
            '2': 'duplicate_of',
            '3': 'blocks',
            '4': 'blocked_by',
            '5': 'parent_of',
            '6': 'child_of'
        }

        while True:
            choice = input("Select link type (1-6): ").strip()
            if choice in link_types:
                link_type = link_types[choice]
                break
            print("Invalid choice.")

        # Check if link already exists
        cursor.execute('''
        SELECT link_id FROM ticket_links
        WHERE ticket_id = ? AND linked_ticket_id = ? AND link_type = ?
        ''', (ticket_id, linked_ticket_id, link_type))

        if cursor.fetchone():
            print("This link already exists.")
            conn.close()
            return

        # Create the link
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO ticket_links
        (ticket_id, linked_ticket_id, link_type, created_by, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (ticket_id, linked_ticket_id, link_type, auth.current_user['id'], now))

        # Create reciprocal link for certain types
        reciprocal_map = {
            'blocks': 'blocked_by',
            'blocked_by': 'blocks',
            'parent_of': 'child_of',
            'child_of': 'parent_of',
            'related_to': 'related_to'
        }

        if link_type in reciprocal_map:
            reciprocal_type = reciprocal_map[link_type]
            cursor.execute('''
            INSERT INTO ticket_links
            (ticket_id, linked_ticket_id, link_type, created_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (linked_ticket_id, ticket_id, reciprocal_type, auth.current_user['id'], now))

        conn.commit()

        # Log the action
        from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.workflows import log_ticket_action
        log_ticket_action(ticket_id, auth.current_user['id'], 'ticket_linked',
                         {}, {'linked_to': linked_ticket_id, 'link_type': link_type})

        print(f"\nTickets linked successfully: {link_type}")

    except ValueError:
        print("Invalid ticket ID.")
    except sqlite3.Error as e:
        print(f"Error linking tickets: {e}")
    finally:
        conn.close()
