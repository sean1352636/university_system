from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)


def view_all_tickets_enhanced(auth):
    """Enhanced view of all tickets for admins"""
    if not auth or not auth.current_user:
        print("You must be logged in to view all tickets.")
        return

    if not auth.check_permission('view_all_tickets'):
        print("You don't have permission to view all tickets.")
        return

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Enhanced filter options
    print("\nAdvanced Filter Options:")
    print("1. All tickets")
    print("2. Unassigned tickets")
    print("3. My assigned tickets")
    print("4. Overdue tickets")
    print("5. High priority tickets")
    print("6. Escalated tickets")
    print("7. Custom filter")

    filter_choice = input("Select filter (1-7): ").strip()

    where_conditions = []
    params = []

    if filter_choice == '2':
        where_conditions.append("t.assigned_to IS NULL")
    elif filter_choice == '3':
        where_conditions.append("t.assigned_to = ?")
        params.append(auth.current_user['id'])
    elif filter_choice == '4':
        where_conditions.append("t.due_date IS NOT NULL AND t.due_date < ? AND t.status NOT IN ('resolved', 'closed')")
        params.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    elif filter_choice == '5':
        where_conditions.append("t.priority = 'high'")
    elif filter_choice == '6':
        where_conditions.append("t.escalation_level > 0")
    elif filter_choice == '7':
        # Custom filter
        status_filter = input("Status (open/in progress/resolved/closed, or press Enter for all): ").strip()
        if status_filter:
            where_conditions.append("t.status = ?")
            params.append(status_filter)

        priority_filter = input("Priority (low/medium/high, or press Enter for all): ").strip()
        if priority_filter:
            where_conditions.append("t.priority = ?")
            params.append(priority_filter)

        dept_filter = input("Department (or press Enter for all): ").strip()
        if dept_filter:
            where_conditions.append("t.department = ?")
            params.append(dept_filter)

    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

    # Get tickets with enhanced information
    cursor.execute('''
    SELECT t.ticket_id, t.subject, t.category, t.status, t.priority, t.impact, t.urgency,
           t.created_at, t.updated_at, t.due_date, t.escalation_level,
           u1.username as submitter, u2.username as assignee, t.department
    FROM support_tickets t
    JOIN users u1 ON t.user_id = u1.id
    LEFT JOIN users u2 ON t.assigned_to = u2.id
    WHERE ''' + where_clause + '''
    ORDER BY
        CASE WHEN t.due_date IS NOT NULL AND t.due_date < datetime('now') AND t.status NOT IN ('resolved', 'closed') THEN 1 ELSE 2 END,
        t.escalation_level DESC,
        CASE
            WHEN t.status = 'open' THEN 1
            WHEN t.status = 'in progress' THEN 2
            WHEN t.status = 'waiting for customer' THEN 3
            WHEN t.status = 'resolved' THEN 4
            WHEN t.status = 'closed' THEN 5
        END,
        CASE
            WHEN t.priority = 'high' THEN 1
            WHEN t.priority = 'medium' THEN 2
            WHEN t.priority = 'low' THEN 3
        END,
        t.updated_at DESC
    ''', params)

    tickets = cursor.fetchall()

    if not tickets:
        print("\nNo tickets found with the selected filter.")
        conn.close()
        return

    print(f"\nSupport Tickets ({len(tickets)} found):")
    print("=" * 140)
    print(f"{'ID':<5} {'Subject':<25} {'From':<12} {'Assigned':<12} {'Dept':<10} {'Status':<12} {'P/I/U':<7} {'Updated':<20}")
    print("=" * 140)

    for ticket in tickets:
        # Status indicators
        status_icon = {
            'open': '\U0001f195',
            'in progress': '\U0001f504',
            'waiting for customer': '\u23f3',
            'resolved': '\u2705',
            'closed': '\U0001f512'
        }.get(ticket['status'], '\U0001f4cb')

        # Priority/Impact/Urgency indicators
        priority_indicators = f"{ticket['priority'][0].upper()}/{ticket['impact'][0].upper()}/{ticket['urgency'][0].upper()}"

        assignee = ticket['assignee'] or 'Unassigned'
        department = ticket['department'] or 'None'

        print(f"{ticket['ticket_id']:<5} {ticket['subject'][:23]:<25} {ticket['submitter'][:10]:<12} "
              f"{assignee[:10]:<12} {department[:8]:<10} {status_icon} {ticket['status'][:10]:<10} "
              f"{priority_indicators:<7} {ticket['updated_at']:<20}")

        # Show special indicators
        indicators = []
        if ticket['escalation_level'] > 0:
            indicators.append(f"\U0001f53a L{ticket['escalation_level']}")

        if ticket['due_date']:
            due_dt = datetime.strptime(ticket['due_date'], '%Y-%m-%d %H:%M:%S')
            if due_dt < datetime.now() and ticket['status'] not in ['resolved', 'closed']:
                indicators.append("\u26a0\ufe0f  OVERDUE")

        if indicators:
            print(f"      {' '.join(indicators)}")

    print("=" * 140)

    # Bulk actions menu
    print("\nBulk Actions:")
    print("1. View ticket details")
    print("2. Bulk assign tickets")
    print("3. Bulk status change")
    print("4. Export ticket list")
    print("5. Return to menu")

    action_choice = input("Select action (1-5): ").strip()

    if action_choice == '1':
        ticket_choice = input("Enter ticket number to view details: ")
        try:
            ticket_id = int(ticket_choice)
            from education_system.university_system.modules.domain.student_affairs.services.helpdesk.tickets.display import view_ticket_detail_enhanced
            view_ticket_detail_enhanced(auth, ticket_id)
        except ValueError:
            print("Invalid ticket number.")
    elif action_choice == '2':
        bulk_assign_tickets(auth, [t['ticket_id'] for t in tickets])
    elif action_choice == '3':
        bulk_status_change(auth, [t['ticket_id'] for t in tickets])
    elif action_choice == '4':
        export_ticket_list(auth, tickets)

    conn.close()

def bulk_assign_tickets(auth, ticket_ids):
    """Bulk assign multiple tickets"""
    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to assign tickets.")
        return

    # Get ticket IDs to assign
    ticket_input = input("Enter ticket IDs to assign (comma-separated, or 'all' for all): ").strip()

    if ticket_input.lower() == 'all':
        selected_tickets = ticket_ids
    else:
        try:
            selected_tickets = [int(x.strip()) for x in ticket_input.split(',')]
            selected_tickets = [tid for tid in selected_tickets if tid in ticket_ids]
        except ValueError:
            print("Invalid ticket IDs.")
            return

    if not selected_tickets:
        print("No valid tickets selected.")
        return

    # Show staff for assignment
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT id, username, role, department
    FROM users
    WHERE role IN ('staff', 'admin') AND is_active = 1
    ORDER BY department, username
    ''')

    staff = cursor.fetchall()

    print("\nAvailable staff:")
    for i, member in enumerate(staff, 1):
        dept = member[3] or 'No Department'
        print(f"{i}. {member[1]} ({member[2]}) - {dept}")

    try:
        staff_choice = int(input("Select staff member: ").strip())
        if 1 <= staff_choice <= len(staff):
            assignee_id = staff[staff_choice - 1][0]
            assignee_name = staff[staff_choice - 1][1]

            # Perform bulk assignment
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            from education_system.university_system.modules.domain.student_affairs.services.helpdesk.workflows import log_ticket_action
            for ticket_id in selected_tickets:
                cursor.execute('''
                UPDATE support_tickets
                SET assigned_to = ?, updated_at = ?, last_activity_at = ?
                WHERE ticket_id = ?
                ''', (assignee_id, now, now, ticket_id))

                # Log the action
                log_ticket_action(ticket_id, auth.current_user['id'], 'bulk_assigned',
                                 {}, {'assigned_to': assignee_id})

            conn.commit()
            print(f"\n{len(selected_tickets)} tickets assigned to {assignee_name}")
        else:
            print("Invalid selection.")
    except ValueError:
        print("Please enter a number.")
    finally:
        conn.close()

def bulk_status_change(auth, ticket_ids):
    """Bulk change status of multiple tickets"""
    if not auth.check_permission('manage_tickets'):
        print("You don't have permission to change ticket status.")
        return

    # Get ticket IDs
    ticket_input = input("Enter ticket IDs to update (comma-separated, or 'all' for all): ").strip()

    if ticket_input.lower() == 'all':
        selected_tickets = ticket_ids
    else:
        try:
            selected_tickets = [int(x.strip()) for x in ticket_input.split(',')]
            selected_tickets = [tid for tid in selected_tickets if tid in ticket_ids]
        except ValueError:
            print("Invalid ticket IDs.")
            return

    if not selected_tickets:
        print("No valid tickets selected.")
        return

    # Status selection
    print("\nSelect new status:")
    print("1. Open")
    print("2. In Progress")
    print("3. Waiting for Customer")
    print("4. Resolved")
    print("5. Closed")

    status_map = {
        "1": "open",
        "2": "in progress",
        "3": "waiting for customer",
        "4": "resolved",
        "5": "closed"
    }

    status_choice = input("Select status (1-5): ").strip()

    if status_choice not in status_map:
        print("Invalid status selection.")
        return

    new_status = status_map[status_choice]

    # Perform bulk status change
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    resolved_at = now if new_status in ['resolved', 'closed'] else None

    from education_system.university_system.modules.domain.student_affairs.services.helpdesk.workflows import log_ticket_action
    for ticket_id in selected_tickets:
        cursor.execute('''
        UPDATE support_tickets
        SET status = ?, resolved_at = ?, updated_at = ?, last_activity_at = ?
        WHERE ticket_id = ?
        ''', (new_status, resolved_at, now, now, ticket_id))

        # Log the action
        log_ticket_action(ticket_id, auth.current_user['id'], 'bulk_status_change',
                         {}, {'status': new_status})

    conn.commit()
    conn.close()

    print(f"\n{len(selected_tickets)} tickets updated to {new_status.upper()}")

def export_ticket_list(auth, tickets):
    """Export ticket list to file"""
    try:
        if not os.path.exists(paths.EXPORTS_TICKETS_DIR):
            os.makedirs(paths.EXPORTS_TICKETS_DIR)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = paths.EXPORTS_TICKETS_DIR / f"ticket_list_{timestamp}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            import csv

            fieldnames = ['ticket_id', 'subject', 'submitter', 'assignee', 'department',
                         'category', 'status', 'priority', 'impact', 'urgency',
                         'created_at', 'updated_at', 'due_date']

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for ticket in tickets:
                writer.writerow({
                    'ticket_id': ticket['ticket_id'],
                    'subject': ticket['subject'],
                    'submitter': ticket['submitter'],
                    'assignee': ticket['assignee'] or '',
                    'department': ticket['department'] or '',
                    'category': ticket['category'],
                    'status': ticket['status'],
                    'priority': ticket['priority'],
                    'impact': ticket['impact'],
                    'urgency': ticket['urgency'],
                    'created_at': ticket['created_at'],
                    'updated_at': ticket['updated_at'],
                    'due_date': ticket['due_date'] or ''
                })

        print(f"\nTicket list exported to {filename}")

    except Exception as e:
        print(f"Error exporting ticket list: {e}")
