"""
Ticket merging operations.
"""

import logging

from education_system.systems.university.domains.student_support.domain.student_support import auth as _auth_mod
from education_system.systems.university.domains.student_support.domain.student_support import service as _service

logger = logging.getLogger(__name__)


def merge_tickets(primary_ticket_id, secondary_ticket_ids, merge_reason):
    """Merge tickets raised by the same person into one primary ticket.

    Copied replies keep their own internal / public flag, so a reply the
    student could see stays visible. Support staff only.
    """
    if not _auth_mod.auth or not _auth_mod.auth.current_user or not _auth_mod.is_support_staff():
        raise PermissionError("Only staff can merge tickets")
    merged = _service.merge(_auth_mod.auth, primary_ticket_id, secondary_ticket_ids, merge_reason)
    logger.info(f"Tickets {secondary_ticket_ids} merged into {primary_ticket_id} by {_auth_mod.auth.current_user['username']}")
    return merged > 0


def merge_tickets_menu(support):
    """Merge multiple tickets into one"""
    print("\n🔗 MERGE TICKETS")
    print("="*40)

    primary_id_input = input("Enter primary ticket ID: ").strip()
    if not primary_id_input.isdigit():
        print("❌ Invalid primary ticket ID.")
        return

    primary_ticket_id = int(primary_id_input)

    secondary_ids_input = input("Enter secondary ticket IDs to merge (comma-separated): ").strip()
    if not secondary_ids_input:
        print("❌ No secondary ticket IDs provided.")
        return

    try:
        secondary_ticket_ids = [int(id.strip()) for id in secondary_ids_input.split(',')]
    except ValueError:
        print("❌ Invalid secondary ticket IDs. Please enter numbers only.")
        return

    merge_reason = input("Reason for merge: ").strip()
    if not merge_reason:
        print("❌ Merge reason is required.")
        return

    # Confirm operation
    print(f"\n📋 Merging tickets {secondary_ticket_ids} into primary ticket #{primary_ticket_id}")
    print(f"Reason: {merge_reason}")
    confirm = input("Confirm ticket merge? (y/n): ").lower()

    if confirm == 'y':
        try:
            support.merge_tickets(primary_ticket_id, secondary_ticket_ids, merge_reason)
            print(f"✅ Successfully merged {len(secondary_ticket_ids)} tickets into #{primary_ticket_id}")
        except Exception as e:
            print(f"❌ Error during ticket merge: {e}")
    else:
        print("❌ Ticket merge cancelled.")
