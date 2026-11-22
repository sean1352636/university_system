from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


def display_kb_suggestions(ticket):
    """Display knowledge base article suggestions"""
    if ticket.get('knowledge_base_articles'):
        conn = get_connection()
        cursor = conn.cursor()

        article_ids = ticket['knowledge_base_articles'].split(',')
        placeholders = ','.join(['?' for _ in article_ids])

        cursor.execute('''
        SELECT article_id, title, category, helpful_votes, unhelpful_votes
        FROM knowledge_base
        WHERE article_id IN (''' + placeholders + ''') AND status = 'published'
        ''', article_ids)

        articles = cursor.fetchall()

        if articles:
            print("\nSuggested Knowledge Base Articles:")
            print("-" * 80)
            for article in articles:
                helpful_ratio = article[3] / max(1, article[3] + article[4])
                print(f"\U0001f4da {article[1]} (Category: {article[2]}) - {helpful_ratio:.0%} helpful")
            print("-" * 80)

        conn.close()

def display_ticket_replies(ticket_id, is_admin=False, auth=None, ticket=None):
    """Print a ticket's conversation — Helpdesk and Student Support replies
    alike — as the ticket service gives it to the viewer: internal notes
    only reach the staff working the ticket, whatever ``is_admin`` says
    (kept for older callers). ``ticket``: an already-fetched
    ``service.get_ticket`` result."""
    if ticket is None or 'responses' not in ticket:
        from education_system.systems.university.domains.student_support.domain.student_support import (
            service,
        )
        try:
            ticket = service.get_ticket(auth, ticket_id)
        except (PermissionError, ValueError) as e:
            print(e)
            return
    replies = ticket.get('responses') or []
    if not replies:
        return
    print("\nConversation History:")
    print("-" * 80)
    for reply in replies:
        internal = bool(reply.get('is_internal'))
        reply_type = "Internal Note" if internal else "Reply"
        icon = "\U0001f512" if internal else "\U0001f4ac"
        who = reply.get('responder_username') or reply.get('responder_id') or 'System'
        print(f"{icon} {reply_type} from {who} ({reply.get('responder_role') or 'staff'}) "
              f"at {reply.get('response_datetime')}")
        print(f"   {reply.get('response_text') or ''}")
        print("-" * 80)


def display_time_tracking(ticket_id, auth=None):
    """Display time tracking information (staff working the ticket)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        collaboration,
    )
    try:
        data = collaboration.time_entries(auth, ticket_id)
    except (PermissionError, ValueError):
        return
    if not data['entries']:
        return
    print("\nTime Tracking:")
    print("-" * 80)
    total_time = billable_time = 0
    for entry in data['entries']:
        duration = (entry['duration_minutes'] or 0) / 60
        total_time += duration
        if entry['billable']:
            billable_time += duration
        billable_text = " (Billable)" if entry['billable'] else ""
        print(f"\u23f1\ufe0f  {entry['username'] or 'Unknown'}: {duration:.2f} hours{billable_text}")
        if entry['description']:
            print(f"   Description: {entry['description']}")
    print(f"\nTotal Time: {total_time:.2f} hours")
    print(f"Billable Time: {billable_time:.2f} hours")
    print("-" * 80)

def display_escalation_history(ticket_id):
    """Display escalation history"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT e.*, u1.username as escalated_to_user, u2.username as escalated_by_user
    FROM ticket_escalations e
    LEFT JOIN users u1 ON e.escalated_to = u1.id
    LEFT JOIN users u2 ON e.escalated_by = u2.id
    WHERE e.ticket_id = ?
    ORDER BY e.created_at
    ''', (ticket_id,))

    escalations = cursor.fetchall()

    if escalations:
        print("\nEscalation History:")
        print("-" * 80)

        for esc in escalations:
            status = "Resolved" if esc['resolved'] else "Open"
            escalated_by = esc['escalated_by_user'] or "System"
            print(f"\U0001f53a Level {esc['escalation_level']} - Escalated to {esc['escalated_to_user']} by {escalated_by}")
            print(f"   Reason: {esc['escalation_reason']}")
            print(f"   Date: {esc['created_at']} - Status: {status}")
        print("-" * 80)

    conn.close()

def display_audit_trail(ticket_id):
    """Display audit trail for admins"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT al.*, u.username
    FROM ticket_audit_log al
    JOIN users u ON al.user_id = u.id
    WHERE al.ticket_id = ?
    ORDER BY al.created_at DESC
    LIMIT 10
    ''', (ticket_id,))

    audit_entries = cursor.fetchall()

    if audit_entries:
        print("\nRecent Activity (Audit Trail):")
        print("-" * 80)

        for entry in audit_entries:
            print(f"\U0001f4cb {entry['action']} by {entry['username']} at {entry['created_at']}")

            if entry['old_values']:
                try:
                    old_vals = json.loads(entry['old_values'])
                    if old_vals:
                        print(f"   Previous values: {old_vals}")
                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse old values JSON: {e}")

            if entry['new_values']:
                try:
                    new_vals = json.loads(entry['new_values'])
                    if new_vals:
                        print(f"   New values: {new_vals}")
                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse new values JSON: {e}")

        print("-" * 80)

    conn.close()

def display_ticket_actions(auth, ticket_id, ticket):
    """Display available actions for the ticket"""
    print("\nAvailable Actions:")
    print("================")

    actions = []
    action_num = 1

    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth, schema,
    )
    # Anyone who can see the ticket may reply (the service refuses a
    # requester's reply to a closed ticket with a message to show).
    print(f"{action_num}. Reply to ticket")
    actions.append('reply')
    action_num += 1

    # Staff actions: the support staff working this ticket.
    if support_auth.can_work_ticket(auth, ticket):
        print(f"{action_num}. Add internal note")
        actions.append('internal_note')
        action_num += 1

        print(f"{action_num}. Change status")
        actions.append('change_status')
        action_num += 1

        print(f"{action_num}. Assign ticket")
        actions.append('assign')
        action_num += 1

        print(f"{action_num}. Add time entry")
        actions.append('time_entry')
        action_num += 1

        print(f"{action_num}. Link to another ticket")
        actions.append('link_ticket')
        action_num += 1

        for key, label in (('time_log', "Time logged (view / remove)"),
                           ('unlink', "Linked tickets (view / unlink)"),
                           ('followers', "Followers"),
                           ('incident', "Add to a major incident")):
            print(f"{action_num}. {label}")
            actions.append(key)
            action_num += 1

        print(f"{action_num}. Escalate ticket")
        actions.append('escalate')
        action_num += 1

        if schema.normalize_status(ticket.get('status'), default='open') in schema.DONE_STATUSES:
            print(f"{action_num}. Send satisfaction survey")
            actions.append('survey')
            action_num += 1

    print(f"{action_num}. Return to previous menu")

    # Handle action selection
    while True:
        choice = input("\nChoose an action: ").strip()

        try:
            choice_num = int(choice)
            if choice_num == action_num:  # Return option
                return
            elif 1 <= choice_num <= len(actions):
                action = actions[choice_num - 1]
                execute_ticket_action(auth, ticket_id, action, ticket)
                return
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a number.")

def execute_ticket_action(auth, ticket_id, action, ticket):
    """Execute the selected ticket action"""
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.operations import (
        reply_to_ticket_enhanced,
        change_ticket_status_enhanced,
        assign_ticket_enhanced,
        add_time_entry,
        link_tickets,
    )
    from education_system.systems.university.domains.student_support.domain.helpdesk.notifications import (
        escalate_ticket_manual,
        send_satisfaction_survey,
    )

    if action == 'reply':
        reply_to_ticket_enhanced(auth, ticket_id, False)
    elif action == 'internal_note':
        reply_to_ticket_enhanced(auth, ticket_id, True)
    elif action == 'change_status':
        change_ticket_status_enhanced(auth, ticket_id)
    elif action == 'assign':
        assign_ticket_enhanced(auth, ticket_id)
    elif action == 'time_entry':
        add_time_entry(auth, ticket_id)
    elif action == 'link_ticket':
        link_tickets(auth, ticket_id)
    elif action in ('time_log', 'unlink', 'followers', 'incident'):
        from education_system.systems.university.domains.student_support.domain.helpdesk import (
            collab_menus,
        )
        {'time_log': collab_menus.time_menu, 'unlink': collab_menus.unlink_menu,
         'followers': collab_menus.followers_menu,
         'incident': collab_menus.incident_for_ticket}[action](auth, ticket_id)
    elif action == 'escalate':
        escalate_ticket_manual(auth, ticket_id)
    elif action == 'survey':
        send_satisfaction_survey(ticket_id)

def display_ticket_attachments(ticket_id, auth=None, ticket=None):
    """Print the attachments the viewer may see (the ticket service keeps
    private ones to the staff working the ticket)."""
    if ticket is not None and 'attachments' in ticket:
        attachments = ticket['attachments']
    else:
        from education_system.systems.university.domains.student_support.domain.student_support import (
            service,
        )
        try:
            attachments = service.list_attachments(auth, ticket_id)
        except (PermissionError, ValueError) as e:
            print(e)
            return
    if attachments:
        print("\nAttachments:")
        print("-" * 80)
        for att in attachments:
            size_mb = (att.get('file_size') or 0) / (1024 * 1024)
            private = "" if att.get('is_public') else " [private]"
            print(f"\U0001f4ce {att.get('original_filename') or att.get('filename')} ({size_mb:.2f} MB)"
                  f"{private} - uploaded by {att.get('uploaded_by')} at {att.get('created_at')}")
        print("-" * 80)


def _linked_summary(auth, other_id):
    """``(subject, status label)`` of a linked ticket the viewer may see,
    else None."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        service,
    )
    try:
        other = service.get_ticket(auth, other_id)
    except (PermissionError, ValueError):
        return None
    return other.get('subject') or '', other.get('status_label') or ''


def display_linked_tickets(ticket_id, auth=None):
    """Print the ticket's links and followers for the staff working it
    (links the viewer may not open show only their number)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        collaboration,
    )
    try:
        links = collaboration.list_links(auth, ticket_id)
        followers = collaboration.list_followers(auth, ticket_id)
    except (PermissionError, ValueError):
        return
    if links:
        print("\nLinked Tickets:")
        print("-" * 80)
        for link in links:
            if link['visible']:
                print(f"\U0001f517 {link['label']}: Ticket #{link['ticket_id']} - "
                      f"{(link['subject'] or '')[:40]} ({link['status']})")
            else:
                print(f"\U0001f517 {link['label']}: Ticket #{link['ticket_id']} (no access)")
        print("-" * 80)
    if followers:
        print("Followers: " + ", ".join(f['username'] for f in followers))


def view_ticket_detail_enhanced(auth, ticket_id):
    """View a ticket in full — as the ticket service gives it to the viewer
    (access checked, confidential text revealed after the look is recorded,
    internal notes for the staff working it only), with its tier, crisis
    flag and SLA standing."""
    if not auth or not auth.current_user:
        print("You must be logged in to view ticket details.")
        return

    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth, routing,
    )
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import (
        fetch_ticket, print_crisis, sla_label, status_label, tier_badge,
    )

    ticket = fetch_ticket(auth, ticket_id)
    if ticket is None:
        return
    staff = support_auth.can_work_ticket(auth, ticket)

    print("\n" + "=" * 80)
    badge = tier_badge(ticket)
    print(f"TICKET #{ticket['ticket_id']}: {ticket.get('subject')}" + (f"  {badge}" if badge else ""))
    print("=" * 80)
    if ticket.get('crisis_flag') and staff:
        print("\u26a0\ufe0f  CRISIS: crisis language was detected on this ticket; it is a "
              "safeguarding ticket.")
    if ticket.get('crisis_support'):
        print_crisis(ticket['crisis_support'])

    print(f"Submitted by: {ticket.get('requester_username') or ticket.get('student_id') or '-'}")
    print(f"Category: {routing.category_label(ticket.get('category'))}")
    if ticket.get('subcategory'):
        print(f"Subcategory: {ticket['subcategory']}")

    print(f"Status: {status_label(ticket)}")
    print(f"Priority: {str(ticket.get('priority') or '').upper()}")
    print(f"Impact: {str(ticket.get('impact') or '-').upper()}")
    print(f"Urgency: {str(ticket.get('urgency') or '-').upper()}")
    if ticket.get('team'):
        print(f"Team: {routing.team_label(ticket['team'])}")
    print(f"Assigned to: {ticket.get('assigned_to') or 'Unassigned'}")
    if ticket.get('department'):
        print(f"Department: {ticket['department']}")

    print(f"Source: {str(ticket.get('source') or '').upper()}")
    print(f"Created: {ticket.get('created_at')}")
    print(f"Last Updated: {ticket.get('updated_at')}")
    print(f"SLA: {sla_label(ticket)}")
    if ticket.get('sla_due_at') or ticket.get('due_date'):
        print(f"Due: {ticket.get('sla_due_at') or ticket.get('due_date')}")
    if ticket.get('first_response_at'):
        print(f"First Response: {ticket['first_response_at']}")
    if ticket.get('resolved_at'):
        print(f"Resolved: {ticket['resolved_at']}")
    if (ticket.get('escalation_level') or 0) > 0:
        print(f"Escalation Level: {ticket['escalation_level']}")
    if ticket.get('tags'):
        print(f"Tags: {', '.join(map(str, ticket['tags']))}")

    print("-" * 80)
    print("Original Message:")
    print(ticket.get('description') or '')
    print("-" * 80)

    if ticket.get('resolution'):
        print("Resolution:")
        print(ticket['resolution'])
        print("-" * 80)

    display_ticket_attachments(ticket_id, auth, ticket=ticket)
    display_linked_tickets(ticket_id, auth)
    display_kb_suggestions(ticket)
    display_ticket_replies(ticket_id, staff, auth, ticket=ticket)

    if staff:
        display_time_tracking(ticket_id, auth)
    if (ticket.get('escalation_level') or 0) > 0:
        display_escalation_history(ticket_id)

    if ticket.get('satisfaction_rating'):
        print(f"\nSatisfaction: {ticket['satisfaction_rating']}/5 stars")
        if ticket.get('satisfaction_feedback'):
            print(f"Feedback: {ticket['satisfaction_feedback']}")

    if staff:
        display_audit_trail(ticket_id)

    display_ticket_actions(auth, ticket_id, ticket)
