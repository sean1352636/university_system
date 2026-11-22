"""
Ticket status management for Student Support.
"""

import json
import logging

from education_system.systems.university.domains.student_support.domain.student_support.config import (
    TICKET_STATUSES, SupportConfig
)
from education_system.systems.university.domains.student_support.domain.student_support import auth as _auth_mod
from education_system.systems.university.domains.student_support.domain.student_support import service as _service
from education_system.systems.university.domains.student_support.domain.student_support import store

logger = logging.getLogger(__name__)

config = SupportConfig()


def update_ticket_status(ticket_id, new_status, resolution_notes=None):
    """Move a ticket to ``new_status`` (support staff only).

    Accepts the display labels ('In Progress') as well as the stored values
    ('in_progress'); the assignee is kept.
    """
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to update a ticket status")
    if not _auth_mod.is_support_staff():
        raise PermissionError("Only staff members can update ticket status")
    result = _service.set_status(_auth_mod.auth, ticket_id, new_status, note=resolution_notes)
    logger.info(f"Updated status of ticket #{ticket_id} from '{result['old']}' to "
                f"'{result['new']}' by {_auth_mod.auth.current_user['username']}")
    return True


def _record_status_change_metrics(ticket_id, old_status, new_status, timestamp):
    """Record a status change in ``system_metrics`` (best effort)."""
    username = (_auth_mod.user_of() or {}).get('username', 'unknown')
    try:
        with store.writing() as conn:
            conn.execute('''
            INSERT INTO system_metrics (metric_name, metric_value, category, recorded_datetime, metadata)
            VALUES (?, ?, ?, ?, ?)''', ('status_change', 1, 'tickets', timestamp, json.dumps({
                'ticket_id': ticket_id, 'old_status': old_status, 'new_status': new_status,
                'changed_by': username})))
    except Exception as e:
        logger.error(f"Error recording status change metrics: {e}")


def update_status_enhanced(support, ticket_id):
    """Enhanced status update with resolution notes"""
    try:
        print(f"\n📊 UPDATE TICKET #{ticket_id} STATUS")
        print("="*50)

        # Show current status
        ticket = support.get_ticket_details(ticket_id)
        print(f"Current Status: {ticket.get('status_label') or ticket['status']}")

        # Status selection
        print("\nNew Status:")
        for i, status in enumerate(TICKET_STATUSES, 1):
            print(f"{i}. {status}")

        choice = input(f"Select new status (1-{len(TICKET_STATUSES)}): ").strip()

        if not choice.isdigit() or not 1 <= int(choice) <= len(TICKET_STATUSES):
            print("❌ Invalid status choice.")
            return

        new_status = TICKET_STATUSES[int(choice) - 1]

        # Resolution notes for resolved/closed tickets
        resolution_notes = None
        if new_status in ['Resolved', 'Closed']:  # display labels from TICKET_STATUSES
            print(f"\nResolution notes for {new_status} status:")
            lines = []
            while True:
                line = input()
                if not line and (not lines or not lines[-1]):
                    break
                lines.append(line)

            if lines:
                resolution_notes = '\n'.join(lines)

        # Update status
        support.update_ticket_status(ticket_id, new_status, resolution_notes)
        print(f"✅ Ticket #{ticket_id} status updated to '{new_status}'")

    except Exception as e:
        print(f"❌ Error updating status: {e}")

def add_internal_note(support, ticket_id):
    """Add internal note to ticket"""
    try:
        print(f"\n🔒 ADD INTERNAL NOTE TO TICKET #{ticket_id}")
        print("="*50)

        print("Internal note (visible only to staff, press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if not line and (not lines or not lines[-1]):
                break
            lines.append(line)

        note_text = '\n'.join(lines)

        if not note_text:
            print("❌ Note cannot be empty.")
            return

        # Add as internal response
        support.add_ticket_response(ticket_id, note_text, is_internal=True)
        print("✅ Internal note added successfully!")

    except Exception as e:
        print(f"❌ Error adding internal note: {e}")

def view_ticket_history(support, ticket_id):
    """View complete ticket history"""
    try:
        print(f"\n📚 TICKET #{ticket_id} HISTORY")
        print("="*60)

        history = support.get_ticket_history(ticket_id)
        ticket = history['ticket']
        timeline = history['timeline']

        print(f"🎫 {ticket['subject']}")
        print(f"👤 Requester: {ticket.get('requester_username') or ticket.get('student_id') or ticket['user_id']}")
        print(f"📊 Current Status: {ticket.get('status_label') or ticket['status']}")
        print(f"🔥 Priority: {ticket['priority']}")
        print(f"📂 Category: {ticket['category']}")

        print(f"\n📅 TIMELINE ({len(timeline)} events):")
        print("="*60)

        def _show(event):
            event_type = event['type']
            data = event['data']
            datetime_str = event['datetime']

            if event_type == 'creation':
                print(f"🎫 [{datetime_str}] Ticket Created")
                print(f"   📝 {(data.get('description') or '')[:100]}...")

            elif event_type == 'response':
                responder = data.get('responder_username') or data.get('responder_role')
                internal_tag = " 🔒" if data.get('is_internal') else ""
                auto_tag = " 🤖" if data.get('is_auto_generated') else ""

                print(f"💬 [{datetime_str}] Response by {responder}{internal_tag}{auto_tag}")
                print(f"   📝 {(data.get('response_text') or '')[:100]}...")

            elif event_type == 'attachment':
                print(f"📎 [{datetime_str}] Attachment Added")
                print(f"   📄 {data['original_filename']} ({data.get('file_size') or 0} bytes)")

            elif event_type == 'audit':
                print(f"🔍 [{datetime_str}] System Event")
                print(f"   ⚙️ {data['action']} by {data.get('username') or data.get('user_id') or 'system'}")

            print()

        for event in timeline[:20]:
            _show(event)

        # Long histories: the first 20 events, then the rest on request.
        if len(timeline) > 20:
            print(f"... showing first 20 of {len(timeline)} events")
            show_all = input("Show all events? (y/n): ").lower()
            if show_all == 'y':
                for event in timeline[20:]:
                    _show(event)

    except Exception as e:
        print(f"❌ Error viewing ticket history: {e}")

    input("\nPress Enter to continue...")
