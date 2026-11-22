from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)


def reply_to_ticket_enhanced(auth, ticket_id, is_internal=False):
    """Reply to a ticket (support staff working it may add an internal note).

    The reply goes through the ticket service (``post_response``), which
    checks access, seals it on a confidential ticket, moves the status on,
    records the first response for the SLA, watches the requester's words
    for crisis language and tells the other side. Time spent is kept in the
    Helpdesk's own time log.
    """
    if not auth or not auth.current_user:
        print("You must be logged in to reply to a ticket.")
        return

    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth, service,
    )
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import (
        fetch_ticket, local_user_id, print_crisis, read_lines,
    )

    ticket = fetch_ticket(auth, ticket_id)
    if ticket is None:
        return
    if is_internal and not support_auth.can_work_ticket(auth, ticket):
        print("Only support staff can add internal notes.")
        return

    reply_type = "internal note" if is_internal else "reply"
    message = read_lines(f"\nEnter your {reply_type} (type 'done' on a new line when finished):")
    if not message:
        print("Error: Reply cannot be empty.")
        return

    time_spent = 0.0
    if support_auth.is_case_worker(auth):
        time_input = input("Time spent on this reply (hours, or press Enter to skip): ").strip()
        if time_input:
            try:
                time_spent = float(time_input)
            except ValueError:
                print("Invalid time format, skipping time tracking.")

    try:
        result = service.post_response(auth, ticket_id, message, internal=is_internal)
    except (PermissionError, ValueError) as e:
        print(f"Error adding reply: {e}")
        return
    print_crisis(result.get('crisis'))
    print(f"\n{reply_type.title()} added successfully!")

    local_id = local_user_id(auth)
    if time_spent > 0 and local_id is not None:
        _record_time(ticket_id, local_id, time_spent, f"{reply_type.title()} #{result['response_id']}",
                     auth=auth)

    # Attachments go through the service too (private with an internal note).
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.attachments import handle_file_attachments
    handle_file_attachments(ticket_id, None, local_id, auth=auth, public=not is_internal)

    from education_system.systems.university.domains.student_support.domain.helpdesk.workflows import log_ticket_action, run_ticket_workflows
    if local_id is not None:
        log_ticket_action(ticket_id, local_id,
                          'internal_note_added' if is_internal else 'reply_added',
                          {}, {'response_id': result['response_id']})
    run_ticket_workflows(ticket_id, 'reply_added', user_role=auth.current_user.get('role'))


def _record_time(ticket_id, local_id, hours, description, billable=False, *, auth=None):
    """A time-log entry through ``collaboration.log_time`` (staff working the
    ticket; ``local_id`` is kept for existing callers)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        collaboration,
    )
    try:
        collaboration.log_time(auth, ticket_id, float(hours) * 60, description, billable=billable)
    except (PermissionError, ValueError) as e:
        print(f"Note: the time spent could not be recorded: {e}")


def change_ticket_status_enhanced(auth, ticket_id):
    """Move a ticket to another status (with the resolution when resolving
    or closing) through the ticket service, which records the change, tells
    the requester and, on resolving, invites them to rate the help."""
    if not auth or not auth.current_user:
        print("You must be logged in to update ticket status.")
        return

    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema, service,
    )
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import (
        fetch_ticket, local_user_id, read_lines,
    )

    ticket = fetch_ticket(auth, ticket_id)
    if ticket is None:
        return
    current_status = schema.normalize_status(ticket.get('status'), default='open')

    print(f"\nCurrent status: {schema.status_label(current_status)}")
    print("\nAvailable statuses:")
    print("1. Open")
    print("2. In Progress")
    print("3. Waiting on Student")
    print("4. Resolved")
    print("5. Closed")
    print("6. Cancelled (closes the ticket)")

    status_map = {
        "1": "open",
        "2": "in_progress",
        "3": "waiting_on_student",
        "4": "resolved",
        "5": "closed",
        "6": "closed"
    }

    while True:
        choice = input("Select new status (1-6): ").strip()
        if choice in status_map:
            new_status = status_map[choice]
            break
        print("Error: Invalid status selection.")

    if current_status == new_status:
        print(f"Status is already {schema.status_label(new_status)}.")
        return

    note = None
    if new_status in schema.DONE_STATUSES and not ticket.get('resolution'):
        note = read_lines("\nPlease provide resolution details (type 'done' when finished):")
        if not note:
            print("Resolution details are required for resolved/closed tickets.")
            return
    elif choice == '6':
        note = "Cancelled"

    try:
        result = service.set_status(auth, ticket_id, new_status, note=note)
    except (PermissionError, ValueError) as e:
        print(f"Error updating ticket status: {e}")
        return

    print(f"\nTicket status updated to: {schema.status_label(result['new'])}")
    if result['new'] == 'resolved':
        print("The requester has been invited to rate the help they received.")
    elif result['new'] == 'closed':
        send_survey = input("Send satisfaction survey to the requester? (y/n): ").strip().lower()
        if send_survey == 'y':
            from education_system.systems.university.domains.student_support.domain.helpdesk.notifications import send_satisfaction_survey
            send_satisfaction_survey(ticket_id)

    from education_system.systems.university.domains.student_support.domain.helpdesk.workflows import log_ticket_action, run_ticket_workflows
    local_id = local_user_id(auth)
    if local_id is not None:
        log_ticket_action(ticket_id, local_id, 'status_changed',
                          {'status': result['old']}, {'status': result['new']})
    run_ticket_workflows(ticket_id, 'status_changed', new_status=result['new'],
                         old_status=result['old'])


def _assignable_staff(team=None):
    """``[(username, role, teams)]`` of support staff who can be given
    tickets (members of ``team`` first when given)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth, routing,
    )
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT username, role FROM users WHERE role IN ({}) ORDER BY username".format(
                ", ".join('?' * len(support_auth.SUPPORT_ROLES | support_auth.ADMIN_ROLES))),
            sorted(support_auth.SUPPORT_ROLES | support_auth.ADMIN_ROLES)).fetchall()
    members = routing.team_members(team) if team else set()
    staff = [(r[0], r[1], sorted(routing.user_teams(r[0]))) for r in rows]
    staff.sort(key=lambda s: (s[0] not in members, s[0]))
    return staff


def assign_ticket_enhanced(auth, ticket_id):
    """Give a ticket to a support staff member — chosen, or the least-loaded
    free member of a team — or unassign it, through the ticket service
    (which checks the assignee is in the ticket's team and tier, records the
    change and tells the new assignee)."""
    if not auth or not auth.current_user:
        print("You must be logged in to assign tickets.")
        return

    from education_system.systems.university.domains.student_support.domain.student_support import (
        routing, service,
    )
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import (
        fetch_ticket, local_user_id,
    )

    ticket = fetch_ticket(auth, ticket_id)
    if ticket is None:
        return
    current_assigned = ticket.get('assigned_to')

    print("\nAssignment Options:")
    print("1. Assign to specific user")
    print("2. Assign to department (auto-balance)")
    print("3. Unassign ticket")

    choice = input("Select option (1-3): ").strip()
    new_assigned = None

    if choice == '1':
        staff = _assignable_staff(ticket.get('team'))
        if not staff:
            print("No available staff members found.")
            return
        print("\nAvailable staff:")
        for i, (username, role, teams) in enumerate(staff, 1):
            names = ", ".join(routing.team_label(t) for t in teams) or 'No team'
            print(f"{i}. {username} ({role}) - {names}")
        while True:
            try:
                staff_choice = int(input("Select staff member: ").strip())
                if 1 <= staff_choice <= len(staff):
                    new_assigned = staff[staff_choice - 1][0]
                    break
                print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")

    elif choice == '2':
        teams = routing.teams()
        if not teams:
            print("No active departments found.")
            return
        print("\nAvailable departments:")
        for i, team in enumerate(teams, 1):
            print(f"{i}. {team.get('label') or routing.team_label(team.get('key'))}")
        while True:
            try:
                dept_choice = int(input("Select department: ").strip())
                if 1 <= dept_choice <= len(teams):
                    team_key = teams[dept_choice - 1].get('key')
                    new_assigned = routing.pick_assignee(team_key)
                    if new_assigned is None:
                        print("Nobody in that department is free to take the ticket.")
                        return
                    break
                print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")

    elif choice == '3':
        new_assigned = None

    else:
        print("Invalid choice.")
        return

    try:
        result = service.assign(auth, ticket_id, new_assigned)
    except (PermissionError, ValueError) as e:
        print(f"Error updating ticket assignment: {e}")
        return

    local_id = local_user_id(auth)
    if local_id is not None:
        from education_system.systems.university.domains.student_support.domain.helpdesk.workflows import log_ticket_action
        log_ticket_action(ticket_id, local_id, 'assignment_changed',
                          {'assigned_to': current_assigned}, {'assigned_to': result['new']})

    if result['new']:
        print(f"\nTicket assigned to: {result['new']}")
    else:
        print("\nTicket unassigned.")


def add_time_entry(auth, ticket_id):
    """Add a time-log entry for a ticket the signed-in support staff member
    works (the Helpdesk's own ``ticket_time_tracking``)."""
    if not auth or not auth.current_user:
        print("You must be logged in to add time entries.")
        return

    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth,
    )
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import (
        fetch_ticket, local_user_id,
    )

    ticket = fetch_ticket(auth, ticket_id)
    if ticket is None:
        return
    if not support_auth.can_work_ticket(auth, ticket):
        print("You don't have permission to add time entries to this ticket.")
        return
    local_id = local_user_id(auth)

    print("\nAdd Time Entry")
    print("==============")

    while True:
        try:
            duration = float(input("Duration (hours): ").strip())
            if duration > 0:
                break
            print("Duration must be greater than 0.")
        except ValueError:
            print("Please enter a valid number.")

    description = input("Description (optional): ").strip()
    billable = input("Is this time billable? (y/n): ").strip().lower() == 'y'

    _record_time(ticket_id, local_id, duration, description, billable, auth=auth)

    if local_id is not None:
        from education_system.systems.university.domains.student_support.domain.helpdesk.workflows import log_ticket_action
        log_ticket_action(ticket_id, local_id, 'time_entry_added',
                          {}, {'duration': duration, 'billable': billable})

    print(f"\nTime entry added: {duration} hours")
    if billable:
        print("Marked as billable")


def link_tickets(auth, ticket_id):
    """Link tickets together (``collaboration.link_tickets``: stored both
    ways; the staff working both tickets only)."""
    if not auth or not auth.current_user:
        print("You must be logged in to link tickets.")
        return

    from education_system.systems.university.domains.student_support.domain.student_support import (
        collaboration,
    )

    print("\nLink Tickets")
    print("============")
    linked_ticket_id = input("Enter ticket ID to link to: ").strip().lstrip('#')

    print("\nLink types:")
    choices = ('related_to', 'duplicate_of', 'blocks', 'blocked_by', 'parent_of', 'child_of')
    for i, key in enumerate(choices, 1):
        print(f"{i}. {collaboration.LINK_LABELS[key]}")
    while True:
        choice = input(f"Select link type (1-{len(choices)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(choices):
            link_type = choices[int(choice) - 1]
            break
        print("Invalid choice.")

    try:
        result = collaboration.link_tickets(auth, ticket_id, linked_ticket_id, link_type)
    except (PermissionError, ValueError) as e:
        print(f"Error linking tickets: {e}")
        return
    if result['created']:
        print(f"\nTickets linked successfully: {collaboration.LINK_LABELS[link_type]}")
    else:
        print("\nThose tickets were already linked that way.")


