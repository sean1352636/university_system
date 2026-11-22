"""
Ticket CRUD operations for Student Support.

The functions here keep their historical signatures (the GUI and CLI call
them with the module's signed-in session) and delegate to ``service``, which
checks permissions, keeps internal notes away from students and resolves the
signed-in person by username.
"""

import json
import logging

from education_system.systems.university.domains.student_support.domain.student_support.config import (
    TICKET_PRIORITIES, SupportConfig
)
from education_system.systems.university.domains.student_support.domain.student_support import auth as _auth_mod
from education_system.systems.university.domains.student_support.domain.student_support import service as _service

logger = logging.getLogger(__name__)

config = SupportConfig()


def _session():
    """The module's signed-in session (PermissionError when nobody is)."""
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to use Student Support")
    return _auth_mod.auth


def create_support_ticket(student_id, title, description, category, priority='Medium',
                        template_id=None, attachments=None, tags=None):
    """Create a new support ticket for ``student_id`` (a student number or
    username; students may only raise their own)."""
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to create a support ticket")
    return _service.create_ticket(
        _auth_mod.auth, subject=title, description=description, category=category,
        priority=priority, requester=student_id, source='support', attachments=attachments,
        tags=tags, template_id=template_id)


def _validate_ticket_inputs(title, description, category, priority):
    """Validate ticket creation inputs"""
    if not title or not description or not category:
        raise ValueError("Title, description and category are required")

    if len(title) > 200:
        raise ValueError("Title must be 200 characters or less")

    if len(description) > 5000:
        raise ValueError("Description must be 5000 characters or less")

    if priority not in TICKET_PRIORITIES:
        raise ValueError(f"Invalid priority. Choose from: {', '.join(TICKET_PRIORITIES)}")


def get_student_tickets(student_id=None, filters=None, page=1, per_page=20):
    """Tickets with filtering and pagination.

    Support staff see every ticket, or one person's with ``student_id``;
    anyone else sees only the tickets they raised.
    """
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to view support tickets")
    session = _auth_mod.auth
    if _auth_mod.is_support_staff(session):
        if student_id:
            return _service.list_tickets_for_requester(session, student_id, filters, page, per_page)
        return _service.list_tickets(session, filters, page, per_page)
    if student_id:
        me = _auth_mod.current_requester(session)
        if str(student_id) not in (me.username, me.student_id or ''):
            raise PermissionError("You can only view your own support tickets")
    return _service.list_my_tickets(session, filters, page, per_page)


def get_ticket_details(ticket_id):
    """A ticket with the replies and attachments the signed-in user may see."""
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to view ticket details")
    return _service.get_ticket(_auth_mod.auth, ticket_id)


def get_ticket_attachments(ticket_id):
    """Attachments of a ticket the signed-in user may see."""
    return _service.list_attachments(_session(), ticket_id)


def download_attachment(attachment_id):
    """``{'filename', 'data'}`` of an attachment the signed-in user may see."""
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to download attachments")
    found = _service.get_attachment(_auth_mod.auth, attachment_id)
    logger.info(f"Attachment {attachment_id} downloaded by {_auth_mod.auth.current_user['username']}")
    return found


def get_ticket_history(ticket_id):
    """Complete history of a ticket the signed-in user may see."""
    return _service.ticket_history(_session(), ticket_id)


def _own_student_id():
    """The signed-in user's student number, resolved by username (None for staff)."""
    return _auth_mod.current_requester(_session()).student_id


def view_my_tickets_enhanced(support):
    """View student's own tickets with enhanced filtering"""
    try:
        print("\n🎫 MY SUPPORT TICKETS")
        print("="*50)

        if not _auth_mod.auth or not _auth_mod.auth.current_user:
            print("❌ You must be logged in to view tickets.")
            return
        student_id = _own_student_id()

        # Filter options
        print("📊 Filter Options:")
        print("1. All tickets")
        print("2. Open tickets")
        print("3. In Progress tickets")
        print("4. Resolved tickets")
        print("5. Search tickets")

        choice = input("\nSelect filter: ").strip()

        filters = {}

        if choice == '2':
            filters['status'] = 'open'
        elif choice == '3':
            filters['status'] = 'in_progress'
        elif choice == '4':
            filters['status'] = 'resolved'
        elif choice == '5':
            search_query = input("Enter search query: ").strip()
            if search_query:
                filters['search'] = search_query

        # Get tickets
        try:
            result = support.get_student_tickets(student_id, filters, page=1, per_page=20)
            tickets = result['tickets']
        except Exception as e:
            print(f"❌ Error retrieving tickets: {e}")
            return

        if not tickets:
            print("📭 No tickets found with the selected filters.")
            return

        # Display tickets
        print(f"\n🎫 Found {result['total_count']} tickets:")
        print("="*80)

        for ticket in tickets:
            status_emoji = {'Open': '🟢', 'In Progress': '⏳', 'Resolved': '✅', 'Closed': '🔒'}.get(ticket.get('status_label'), '❓')
            priority_emoji = {'Critical': '🔴', 'Urgent': '🟠', 'High': '🟡', 'Medium': '🔵', 'Low': '🟢'}.get(ticket['priority'], '⚪')

            print(f"{status_emoji} #{ticket['ticket_id']} - {ticket['subject']}")
            print(f"   📂 {ticket['category']} | {priority_emoji} {ticket['priority']} | 📅 {ticket['created_at']}")

            if ticket.get('assigned_to'):
                print(f"   👨‍💼 Assigned to: {ticket['assigned_to']}")

            print()

        # View specific ticket
        if tickets:
            ticket_choice = input("View ticket details (enter ticket #) or press Enter to go back: ").strip()
            if ticket_choice.isdigit():
                ticket_id = int(ticket_choice)
                if any(t['ticket_id'] == ticket_id for t in tickets):
                    display_ticket_details_enhanced(support, ticket_id)
                else:
                    print("❌ Ticket not found in current list.")

    except Exception as e:
        print(f"❌ Error viewing tickets: {e}")

    input("\nPress Enter to continue...")

def use_ticket_template(support):
    """Create ticket using a template"""
    try:
        print("\n📋 USE TICKET TEMPLATE")
        print("="*50)

        templates = support.get_ticket_templates()

        if not templates:
            print("📭 No ticket templates available.")
            return

        print("📋 Available Templates:")
        for i, template in enumerate(templates, 1):
            print(f"{i}. {template['name']}")
            print(f"   📂 Category: {template['category']} | 🔥 Priority: {template['priority']}")
            print(f"   📈 Used {template.get('usage_count', 0)} times")
            print()

        choice = input(f"Select template (1-{len(templates)}): ").strip()

        if not choice.isdigit() or not 1 <= int(choice) <= len(templates):
            print("❌ Invalid choice.")
            return

        template = templates[int(choice) - 1]

        if not _auth_mod.auth or not _auth_mod.auth.current_user:
            print("❌ You must be logged in to create tickets.")
            return
        student_id = _own_student_id() or _auth_mod.auth.current_user['username']

        print(f"\n📋 Using template: {template['name']}")
        print("="*50)

        # Pre-fill from template
        title = template['subject_template']
        description = template['message_template']
        category = template['category']
        priority = template['priority']

        print(f"Title: {title}")
        print(f"Category: {category}")
        print(f"Priority: {priority}")
        print(f"\nDescription:\n{description}")

        # Allow customization
        print("\n🔧 Customize Template:")
        custom_title = input(f"Custom title (or press Enter to keep '{title}'): ").strip()
        if custom_title:
            title = custom_title

        print("Additional description (press Enter twice to finish):")
        additional_lines = []
        while True:
            line = input()
            if not line and (not additional_lines or not additional_lines[-1]):
                break
            additional_lines.append(line)

        if additional_lines:
            description += "\n\n" + '\n'.join(additional_lines)

        # Create ticket
        print("\n🎫 Creating ticket from template...")
        ticket_id = support.create_support_ticket(
            student_id, title, description, category, priority,
            template_id=template['template_id']
        )

        print(f"✅ Support ticket #{ticket_id} created successfully from template!")

        # View ticket details
        view_choice = input("\nView ticket details? (y/n): ").lower()
        if view_choice == 'y':
            display_ticket_details_enhanced(support, ticket_id)

    except Exception as e:
        print(f"❌ Error using template: {e}")

    input("\nPress Enter to continue...")

# Module-level helper functions exposed for GUI/CLI integrations

def view_all_tickets_enhanced(support):
    """View all tickets with advanced filtering (staff only)"""
    try:
        print("\n🎫 ALL SUPPORT TICKETS")
        print("="*50)

        # Advanced filter menu
        print("📊 Filter Options:")
        print("1. All tickets")
        print("2. By status")
        print("3. By category")
        print("4. By priority")
        print("5. By assigned staff")
        print("6. By date range")
        print("7. Unassigned tickets")
        print("8. High priority tickets")
        print("9. Search tickets")

        choice = input("\nSelect filter: ").strip()

        filters = {}

        if choice == '2':
            status_options = ['Open', 'In Progress', 'Resolved', 'Closed', 'Escalated', 'On Hold']
            print("\nStatuses:")
            for i, status in enumerate(status_options, 1):
                print(f"{i}. {status}")
            status_choice = input(f"Select status (1-{len(status_options)}): ").strip()
            if status_choice.isdigit() and 1 <= int(status_choice) <= len(status_options):
                filters['status'] = status_options[int(status_choice) - 1]
        elif choice == '3':
            category_options = ['Academic', 'Technical', 'Financial Aid', 'Library Services', 'Other']
            print("\nCategories:")
            for i, cat in enumerate(category_options, 1):
                print(f"{i}. {cat}")
            cat_choice = input(f"Select category (1-{len(category_options)}): ").strip()
            if cat_choice.isdigit() and 1 <= int(cat_choice) <= len(category_options):
                filters['category'] = category_options[int(cat_choice) - 1]
        elif choice == '5':
            assigned_to = input("Enter staff username: ").strip()
            if assigned_to:
                filters['assigned_to'] = assigned_to
        elif choice == '7':
            filters['assigned_to'] = None
        elif choice == '9':
            search_query = input("Enter search query: ").strip()
            if search_query:
                filters['search'] = search_query

        # Get tickets
        try:
            result = support.get_student_tickets(None, filters, page=1, per_page=20)
            tickets = result['tickets']
        except Exception as e:
            print(f"❌ Error retrieving tickets: {e}")
            return

        if not tickets:
            print("📭 No tickets found with the selected filters.")
            return

        # Display tickets
        print(f"\n🎫 Found {result['total_count']} tickets (showing page {result['page']} of {result['total_pages']}):")
        print("="*100)

        for ticket in tickets:
            status_emoji = {'Open': '🟢', 'In Progress': '⏳', 'Resolved': '✅', 'Closed': '🔒', 'Escalated': '🚨'}.get(ticket.get('status_label'), '❓')
            priority_emoji = {'Critical': '🔴', 'Urgent': '🟠', 'High': '🟡', 'Medium': '🔵', 'Low': '🟢'}.get(ticket['priority'], '⚪')

            print(f"{status_emoji} #{ticket['ticket_id']} - {ticket['subject']}")
            print(f"   👤 Requester: {ticket.get('requester_username') or ticket.get('student_id') or ticket['user_id']} | 📂 {ticket['category']} | {priority_emoji} {ticket['priority']}")
            print(f"   📅 Created: {ticket['created_at']}")

            if ticket.get('assigned_to'):
                print(f"   👨‍💼 Assigned to: {ticket['assigned_to']}")
            else:
                print("   ❌ Unassigned")

            print()

        # View specific ticket
        if tickets:
            ticket_choice = input("View ticket details (enter ticket #) or press Enter to go back: ").strip()
            if ticket_choice.isdigit():
                ticket_id = int(ticket_choice)
                if any(t['ticket_id'] == ticket_id for t in tickets):
                    try:
                        display_ticket_details_enhanced(support, ticket_id)
                    except Exception as e:
                        print(f"❌ Error displaying ticket: {e}")
                else:
                    print("❌ Ticket not found in current list.")

    except Exception as e:
        print(f"❌ Error viewing tickets: {e}")

    input("\nPress Enter to continue...")

def display_ticket_details_enhanced(support, ticket_id):
    """Display enhanced ticket details"""
    try:
        ticket = support.get_ticket_details(ticket_id)

        print(f"\n🎫 TICKET #{ticket['ticket_id']}")
        print("="*50)
        print(f"📋 Title: {ticket['subject']}")
        print(f"👤 Requester: {ticket.get('requester_username') or ticket.get('student_id') or ticket['user_id']}")
        print(f"📊 Status: {ticket.get('status_label') or ticket['status']}")
        print(f"🔥 Priority: {ticket['priority']}")
        print(f"📂 Category: {ticket['category']}")
        print(f"📅 Created: {ticket['created_at']}")

        if ticket.get('assigned_to'):
            print(f"👨‍💼 Assigned to: {ticket['assigned_to']}")

        if ticket.get('estimated_resolution'):
            print(f"⏰ Est. Resolution: {ticket['estimated_resolution']}")

        if ticket.get('sentiment'):
            sentiment_emoji = {'positive': '😊', 'neutral': '😐', 'negative': '😞', 'frustrated': '😤'}
            print(f"😊 Sentiment: {sentiment_emoji.get(ticket['sentiment'], '😐')} {ticket['sentiment']}")

        if ticket.get('tags'):
            try:
                tags = json.loads(ticket['tags']) if isinstance(ticket['tags'], str) else ticket['tags']
                if tags:
                    print(f"🏷️ Tags: {', '.join(tags)}")
            except (json.JSONDecodeError, TypeError):
                pass

        print("\n📝 Description:")
        print(ticket['description'])

        # Attachments
        attachments = ticket.get('attachments', [])
        if attachments:
            print(f"\n📎 Attachments ({len(attachments)}):")
            for att in attachments:
                size_mb = (att['file_size'] or 0) / (1024 * 1024)
                print(f"  📄 {att['original_filename']} ({size_mb:.1f}MB)")

        # Responses
        responses = ticket.get('responses', [])
        if responses:
            print(f"\n💬 Responses ({len(responses)}):")
            for response in responses:
                auto_tag = " 🤖" if response.get('is_auto_generated') else ""
                internal_tag = " 🔒" if response.get('is_internal') else ""
                print(f"\n[{response['response_datetime']}] {response['responder_role']}{auto_tag}{internal_tag}:")
                print(f"  {response['response_text']}")

    except Exception as e:
        print(f"❌ Error displaying ticket: {e}")
