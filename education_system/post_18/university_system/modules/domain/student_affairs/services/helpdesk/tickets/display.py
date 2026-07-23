from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


def display_kb_suggestions(ticket):
    """Display knowledge base article suggestions"""
    if ticket['knowledge_base_articles']:
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

def display_ticket_replies(ticket_id, is_admin):
    """Display ticket replies and internal notes"""
    conn = get_connection()
    cursor = conn.cursor()

    # Get all replies
    cursor.execute('''
    SELECT r.*, u.username, u.role
    FROM ticket_replies r
    JOIN users u ON r.user_id = u.id
    WHERE r.ticket_id = ?
    ORDER BY r.created_at ASC
    ''', (ticket_id,))

    replies = cursor.fetchall()

    if replies:
        print("\nConversation History:")
        print("-" * 80)

        for reply in replies:
            reply_type = "Internal Note" if reply[4] else "Reply"  # is_internal
            icon = "\U0001f512" if reply[4] else "\U0001f4ac"

            # Only show internal notes to admins
            if reply[4] and not is_admin:
                continue

            print(f"{icon} {reply_type} from {reply[-2]} ({reply[-1]}) at {reply[6]}")  # username, role, created_at
            if reply[7]:  # edited_at
                print(f"   (Edited at {reply[7]})")

            if reply[6]:  # time_spent
                print(f"   Time spent: {reply[6]} hours")

            print(f"   {reply[3]}")  # message
            print("-" * 80)

def display_time_tracking(ticket_id):
    """Display time tracking information"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT tt.*, u.username
    FROM ticket_time_tracking tt
    JOIN users u ON tt.user_id = u.id
    WHERE tt.ticket_id = ?
    ORDER BY tt.created_at
    ''', (ticket_id,))

    time_entries = cursor.fetchall()

    if time_entries:
        print("\nTime Tracking:")
        print("-" * 80)

        total_time = 0
        billable_time = 0

        for entry in time_entries:
            duration = entry[5] / 60  # duration_minutes to hours
            total_time += duration
            if entry[7]:  # billable
                billable_time += duration

            billable_text = " (Billable)" if entry[7] else ""
            print(f"\u23f1\ufe0f  {entry[-1]}: {duration:.2f} hours{billable_text}")
            if entry[6]:  # description
                print(f"   Description: {entry[6]}")

        print(f"\nTotal Time: {total_time:.2f} hours")
        print(f"Billable Time: {billable_time:.2f} hours")
        print("-" * 80)

    conn.close()

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
            status = "Resolved" if esc[6] else "Open"  # resolved
            escalated_by = esc[-1] or "System"
            print(f"\U0001f53a Level {esc[2]} - Escalated to {esc[-2]} by {escalated_by}")
            print(f"   Reason: {esc[4]}")  # escalation_reason
            print(f"   Date: {esc[7]} - Status: {status}")
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
            print(f"\U0001f4cb {entry[3]} by {entry[-1]} at {entry[8]}")  # action, username, created_at

            if entry[4]:  # old_values
                try:
                    old_vals = json.loads(entry[4])
                    if old_vals:
                        print(f"   Previous values: {old_vals}")
                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse old values JSON: {e}")

            if entry[5]:  # new_values
                try:
                    new_vals = json.loads(entry[5])
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

    # Reply action
    if auth.check_permission('reply_to_any_ticket') or \
       (auth.check_permission('reply_to_own_ticket') and ticket['user_id'] == auth.current_user['id']):
        print(f"{action_num}. Reply to ticket")
        actions.append('reply')
        action_num += 1

    # Admin actions
    if auth.check_permission('manage_tickets'):
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

        print(f"{action_num}. Escalate ticket")
        actions.append('escalate')
        action_num += 1

        if ticket['status'] in ['resolved', 'closed']:
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
    from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.tickets.operations import (
        reply_to_ticket_enhanced,
        change_ticket_status_enhanced,
        assign_ticket_enhanced,
        add_time_entry,
        link_tickets,
    )
    from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk.notifications import (
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
    elif action == 'escalate':
        escalate_ticket_manual(auth, ticket_id)
    elif action == 'survey':
        send_satisfaction_survey(ticket_id)

def display_ticket_attachments(ticket_id):
    """Display ticket attachments"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT a.*, u.username
    FROM ticket_attachments a
    JOIN users u ON a.uploaded_by = u.id
    WHERE a.ticket_id = ?
    ORDER BY a.created_at
    ''', (ticket_id,))

    attachments = cursor.fetchall()

    if attachments:
        print("\nAttachments:")
        print("-" * 80)
        for att in attachments:
            size_mb = att[4] / (1024 * 1024)  # file_size
            print(f"\U0001f4ce {att[3]} ({size_mb:.2f} MB) - uploaded by {att[-1]} at {att[-2]}")
        print("-" * 80)

    conn.close()

def display_linked_tickets(ticket_id):
    """Display linked/related tickets"""
    conn = get_connection()
    cursor = conn.cursor()

    # Get tickets linked to this one
    cursor.execute('''
    SELECT tl.link_type, t.ticket_id, t.subject, t.status, u.username
    FROM ticket_links tl
    JOIN support_tickets t ON tl.linked_ticket_id = t.ticket_id
    JOIN users u ON tl.created_by = u.id
    WHERE tl.ticket_id = ?
    ''', (ticket_id,))

    linked = cursor.fetchall()

    # Get tickets that link to this one
    cursor.execute('''
    SELECT tl.link_type, t.ticket_id, t.subject, t.status, u.username
    FROM ticket_links tl
    JOIN support_tickets t ON tl.ticket_id = t.ticket_id
    JOIN users u ON tl.created_by = u.id
    WHERE tl.linked_ticket_id = ?
    ''', (ticket_id,))

    linking = cursor.fetchall()

    if linked or linking:
        print("\nLinked Tickets:")
        print("-" * 80)

        status_icons = {
            'open': '\U0001f195',
            'in progress': '\U0001f504',
            'waiting for customer': '\u23f3',
            'resolved': '\u2705',
            'closed': '\U0001f512'
        }

        # Display tickets this one links to
        for link in linked:
            link_type, linked_ticket_id, subject, status, created_by = link
            status_icon = status_icons.get(status, '\U0001f4cb')
            print(f"\U0001f517 {link_type.replace('_', ' ').title()}: Ticket #{linked_ticket_id} - {subject[:40]} ({status_icon} {status.upper()})")

        # Display tickets that link to this one
        for link in linking:
            link_type, linking_ticket_id, subject, status, created_by = link
            status_icon = status_icons.get(status, '\U0001f4cb')

            # Convert link type to reverse perspective
            reverse_link_map = {
                'related_to': 'Related to',
                'duplicate_of': 'Duplicated by',
                'blocks': 'Blocked by',
                'blocked_by': 'Blocks',
                'parent_of': 'Child of',
                'child_of': 'Parent of'
            }

            reverse_type = reverse_link_map.get(link_type, link_type.replace('_', ' ').title())
            print(f"\U0001f517 {reverse_type}: Ticket #{linking_ticket_id} - {subject[:40]} ({status_icon} {status.upper()})")

        print("-" * 80)

    conn.close()

def view_ticket_detail_enhanced(auth, ticket_id):
    """View comprehensive ticket details"""
    if not auth or not auth.current_user:
        print("You must be logged in to view ticket details.")
        return

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check permissions
    is_admin = auth.check_permission('view_all_tickets')

    if not is_admin:
        cursor.execute('''
        SELECT user_id FROM support_tickets WHERE ticket_id = ?
        ''', (ticket_id,))

        result = cursor.fetchone()
        if not result or result['user_id'] != auth.current_user['id']:
            print("You don't have permission to view this ticket.")
            conn.close()
            return

    # Get comprehensive ticket details
    cursor.execute('''
    SELECT t.*, u1.username as submitter, u1.email as submitter_email,
           u2.username as assignee, u2.email as assignee_email,
           d.name as dept_name, d.email as dept_email
    FROM support_tickets t
    JOIN users u1 ON t.user_id = u1.id
    LEFT JOIN users u2 ON t.assigned_to = u2.id
    LEFT JOIN departments d ON t.department = d.name
    WHERE t.ticket_id = ?
    ''', (ticket_id,))

    ticket = cursor.fetchone()

    if not ticket:
        print(f"Ticket #{ticket_id} not found.")
        conn.close()
        return

    # Display comprehensive ticket information
    print("\n" + "=" * 80)
    print(f"TICKET #{ticket['ticket_id']}: {ticket['subject']}")
    print("=" * 80)

    # Basic information
    print(f"Submitted by: {ticket['submitter']} ({ticket['submitter_email']})")
    print(f"Category: {ticket['category']}")
    if ticket['subcategory']:
        print(f"Subcategory: {ticket['subcategory']}")

    print(f"Status: {ticket['status'].upper()}")
    print(f"Priority: {ticket['priority'].upper()}")
    print(f"Impact: {ticket['impact'].upper()}")
    print(f"Urgency: {ticket['urgency'].upper()}")

    if ticket['assignee']:
        print(f"Assigned to: {ticket['assignee']} ({ticket['assignee_email']})")
    else:
        print("Assigned to: Unassigned")

    if ticket['department']:
        print(f"Department: {ticket['department']}")

    print(f"Source: {ticket['source'].upper()}")
    print(f"Created: {ticket['created_at']}")
    print(f"Last Updated: {ticket['updated_at']}")

    if ticket['due_date']:
        print(f"Due Date: {ticket['due_date']}")
        # Check if overdue
        due_dt = datetime.strptime(ticket['due_date'], '%Y-%m-%d %H:%M:%S')
        if due_dt < datetime.now():
            print("\u26a0\ufe0f  OVERDUE")

    if ticket['first_response_at']:
        print(f"First Response: {ticket['first_response_at']}")

    if ticket['resolved_at']:
        print(f"Resolved: {ticket['resolved_at']}")

    if ticket['escalation_level'] > 0:
        print(f"Escalation Level: {ticket['escalation_level']}")

    if ticket['tags']:
        print(f"Tags: {ticket['tags']}")

    print("-" * 80)
    print("Original Message:")
    print(ticket['description'])
    print("-" * 80)

    # Display resolution if available
    if ticket['resolution']:
        print("Resolution:")
        print(ticket['resolution'])
        print("-" * 80)

    # Display attachments
    display_ticket_attachments(ticket_id)

    # Display linked tickets
    display_linked_tickets(ticket_id)

    # Display knowledge base suggestions
    display_kb_suggestions(ticket)

    # Display replies and internal notes
    display_ticket_replies(ticket_id, is_admin)

    # Display time tracking
    if is_admin:
        display_time_tracking(ticket_id)

    # Display escalation history
    if ticket['escalation_level'] > 0:
        display_escalation_history(ticket_id)

    # Display satisfaction rating
    if ticket['satisfaction_rating']:
        print(f"\nCustomer Satisfaction: {ticket['satisfaction_rating']}/5 stars")
        if ticket['satisfaction_feedback']:
            print(f"Feedback: {ticket['satisfaction_feedback']}")

    # Display audit trail for admins
    if is_admin:
        display_audit_trail(ticket_id)

    # Action menu
    display_ticket_actions(auth, ticket_id, ticket)

    conn.close()
