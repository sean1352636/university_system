from education_system import paths
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)


def _due(ticket):
    return ticket.get('sla_due_at') or ticket.get('due_date')


def _is_overdue(ticket, now):
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )
    due = _due(ticket)
    return bool(due) and str(due) < now and \
        schema.normalize_status(ticket.get('status'), default='open') not in schema.DONE_STATUSES


def view_all_tickets_enhanced(auth):
    """Every ticket the signed-in support staff member may see (their teams
    and tiers), through the ticket service, with bulk actions."""
    if not auth or not auth.current_user:
        print("You must be logged in to view all tickets.")
        return

    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.service import (
        iter_tickets,
    )
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import (
        status_label, tier_badge,
    )
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth, schema,
    )
    if not support_auth.is_case_worker(auth):
        print("You don't have permission to view all tickets.")
        return

    print("\nAdvanced Filter Options:")
    print("1. All tickets")
    print("2. Unassigned tickets")
    print("3. My assigned tickets")
    print("4. Overdue tickets")
    print("5. High priority tickets")
    print("6. Escalated tickets")
    print("7. Custom filter")

    filter_choice = input("Select filter (1-7): ").strip()

    filters, keep = {}, None
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if filter_choice == '2':
        filters['unassigned'] = True
    elif filter_choice == '3':
        filters['assigned_to'] = auth.current_user['username']
    elif filter_choice == '4':
        filters['active_only'] = True
        keep = lambda t: _is_overdue(t, now)  # noqa: E731
    elif filter_choice == '5':
        filters['priority'] = 'high'
    elif filter_choice == '6':
        keep = lambda t: (t.get('escalation_level') or 0) > 0  # noqa: E731
    elif filter_choice == '7':
        status_filter = input("Status (open/in progress/waiting on student/escalated/resolved/closed, or press Enter for all): ").strip()
        if status_filter:
            try:
                filters['status'] = schema.normalize_status(status_filter)
            except ValueError as e:
                print(e)
                return
        priority_filter = input("Priority (low/medium/high, or press Enter for all): ").strip()
        if priority_filter:
            filters['priority'] = priority_filter
        dept_filter = input("Department (or press Enter for all): ").strip()
        if dept_filter:
            keep = lambda t: str(t.get('department') or '').lower() == dept_filter.lower()  # noqa: E731

    try:
        tickets = [t for t in iter_tickets(auth, filters) if keep is None or keep(t)]
    except (PermissionError, ValueError) as e:
        print(e)
        return
    order = {s: i for i, s in enumerate(schema.STATUSES)}
    prio = {'critical': 0, 'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
    tickets.sort(key=lambda t: str(t.get('updated_at') or ''), reverse=True)
    tickets.sort(key=lambda t: (not _is_overdue(t, now), -(t.get('escalation_level') or 0),
                                order.get(schema.normalize_status(t.get('status'), default='open'), 9),
                                prio.get(str(t.get('priority') or '').lower(), 9)))
    for t in tickets:
        t['submitter'] = t.get('requester_username') or t.get('student_id') or str(t.get('user_id') or '')
        t['assignee'] = t.get('assigned_to')

    if not tickets:
        print("\nNo tickets found with the selected filter.")
        return

    print(f"\nSupport Tickets ({len(tickets)} found):")
    print("=" * 140)
    print(f"{'ID':<5} {'Subject':<25} {'From':<12} {'Assigned':<12} {'Dept':<10} {'Status':<18} {'P/I/U':<7} {'Updated':<20}")
    print("=" * 140)

    for ticket in tickets:
        status = schema.normalize_status(ticket.get('status'), default='open')
        status_icon = {
            'open': '\U0001f195',
            'in_progress': '\U0001f504',
            'waiting_on_student': '\u23f3',
            'escalated': '\U0001f53a',
            'resolved': '\u2705',
            'closed': '\U0001f512'
        }.get(status, '\U0001f4cb')

        def first(key):
            return (str(ticket.get(key) or '-') + '-')[0].upper()
        priority_indicators = f"{first('priority')}/{first('impact')}/{first('urgency')}"

        assignee = str(ticket['assignee'] or 'Unassigned')
        department = str(ticket.get('department') or 'None')
        badge = tier_badge(ticket)
        subject = (badge + ' ' if badge else '') + str(ticket.get('subject') or '')

        print(f"{ticket['ticket_id']:<5} {subject[:23]:<25} {str(ticket['submitter'])[:10]:<12} "
              f"{assignee[:10]:<12} {department[:8]:<10} {status_icon} {status_label(ticket)[:16]:<16} "
              f"{priority_indicators:<7} {str(ticket.get('updated_at') or ''):<20}")

        indicators = []
        if ticket.get('crisis_flag'):
            indicators.append("\u26a0\ufe0f  CRISIS")
        if (ticket.get('escalation_level') or 0) > 0:
            indicators.append(f"\U0001f53a L{ticket['escalation_level']}")
        if _is_overdue(ticket, now):
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
            from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.display import view_ticket_detail_enhanced
            view_ticket_detail_enhanced(auth, ticket_id)
        except ValueError:
            print("Invalid ticket number.")
    elif action_choice == '2':
        bulk_assign_tickets(auth, [t['ticket_id'] for t in tickets])
    elif action_choice == '3':
        bulk_status_change(auth, [t['ticket_id'] for t in tickets])
    elif action_choice == '4':
        export_ticket_list(auth, tickets)

def bulk_assign_tickets(auth, ticket_ids):
    """Bulk assign multiple tickets"""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth,
    )
    if not support_auth.is_case_worker(auth):
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

    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.operations import (
        _assignable_staff,
    )
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import (
        local_user_id,
    )
    from education_system.systems.university.domains.student_support.domain.student_support import (
        routing, service,
    )
    staff = _assignable_staff()

    print("\nAvailable staff:")
    for i, (username, role, teams) in enumerate(staff, 1):
        names = ", ".join(routing.team_label(t) for t in teams) or 'No team'
        print(f"{i}. {username} ({role}) - {names}")

    try:
        staff_choice = int(input("Select staff member: ").strip())
    except ValueError:
        print("Please enter a number.")
        return
    if not 1 <= staff_choice <= len(staff):
        print("Invalid selection.")
        return
    assignee_name = staff[staff_choice - 1][0]

    # Each through the ticket service: it checks the assignee is in the
    # ticket's team and tier, records the change and tells them.
    from education_system.systems.university.domains.student_support.domain.helpdesk.workflows import log_ticket_action
    local_id = local_user_id(auth)
    done = 0
    for ticket_id in selected_tickets:
        try:
            service.assign(auth, ticket_id, assignee_name)
        except (PermissionError, ValueError) as e:
            print(f"Ticket #{ticket_id}: {e}")
            continue
        done += 1
        if local_id is not None:
            log_ticket_action(ticket_id, local_id, 'bulk_assigned', {}, {'assigned_to': assignee_name})
    print(f"\n{done} tickets assigned to {assignee_name}")

def bulk_status_change(auth, ticket_ids):
    """Bulk change status of multiple tickets"""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth,
    )
    if not support_auth.is_case_worker(auth):
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
    print("3. Waiting on Student")
    print("4. Resolved")
    print("5. Closed")

    status_map = {
        "1": "open",
        "2": "in_progress",
        "3": "waiting_on_student",
        "4": "resolved",
        "5": "closed"
    }

    status_choice = input("Select status (1-5): ").strip()

    if status_choice not in status_map:
        print("Invalid status selection.")
        return

    new_status = status_map[status_choice]

    # Each through the ticket service (status history, requester notices,
    # the satisfaction invitation on resolving).
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import (
        local_user_id,
    )
    from education_system.systems.university.domains.student_support.domain.helpdesk.workflows import log_ticket_action
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema, service,
    )
    local_id = local_user_id(auth)
    done = 0
    for ticket_id in selected_tickets:
        try:
            service.set_status(auth, ticket_id, new_status)
        except (PermissionError, ValueError) as e:
            print(f"Ticket #{ticket_id}: {e}")
            continue
        done += 1
        if local_id is not None:
            log_ticket_action(ticket_id, local_id, 'bulk_status_change', {}, {'status': new_status})

    print(f"\n{done} tickets updated to {schema.status_label(new_status)}")

def export_ticket_list(auth, tickets):
    """Export ticket list to file"""
    try:
        if not os.path.exists(paths.UNIVERSITY_EXPORTS_TICKETS_DIR):
            os.makedirs(paths.UNIVERSITY_EXPORTS_TICKETS_DIR)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = paths.UNIVERSITY_EXPORTS_TICKETS_DIR / f"ticket_list_{timestamp}.csv"

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
                    'submitter': ticket.get('submitter') or ticket.get('requester_username') or '',
                    'assignee': ticket.get('assignee') or ticket.get('assigned_to') or '',
                    'department': ticket.get('department') or '',
                    'category': ticket.get('category'),
                    'status': ticket.get('status'),
                    'priority': ticket.get('priority'),
                    'impact': ticket.get('impact'),
                    'urgency': ticket.get('urgency'),
                    'created_at': ticket.get('created_at'),
                    'updated_at': ticket.get('updated_at'),
                    'due_date': ticket.get('sla_due_at') or ticket.get('due_date') or ''
                })

        print(f"\nTicket list exported to {filename}")

    except Exception as e:
        print(f"Error exporting ticket list: {e}")
