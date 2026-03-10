"""CLI interface for helpdesk management."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.modules.domain.helpdesk.services.helpdesk_service import HelpdeskService
from education_system.college_system.infrastructure.auth.core import UserAuth


def helpdesk_menu(auth: UserAuth):
    """Helpdesk management menu."""
    svc = HelpdeskService(auth._db_path)
    user_id = auth.current_user["user_id"]
    role = auth.current_user.get("role", "student")
    is_staff = role in ("admin", "staff")

    while True:
        print_header("Helpdesk")
        options = [
            ("1", "My Tickets"),
            ("2", "Create Ticket"),
            ("3", "View Ticket"),
            ("4", "Reply to Ticket"),
        ]
        if is_staff:
            options.extend([
                ("5", "All Tickets"),
                ("6", "Update Ticket Status"),
            ])
        options.append(("0", "Back"))
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _my_tickets(svc, user_id)
        elif choice == "2":
            _create_ticket(svc, user_id)
        elif choice == "3":
            _view_ticket(svc)
        elif choice == "4":
            _reply_ticket(svc, user_id)
        elif choice == "5" and is_staff:
            _all_tickets(svc)
        elif choice == "6" and is_staff:
            _update_status(svc)
        elif choice == "0":
            break


def _my_tickets(svc, user_id):
    tickets = svc.list_tickets(user_id=user_id)
    if not tickets:
        print("\n  No tickets found.")
        return

    print(f"\n  {'ID':<5} {'Subject':<30} {'Status':<12} {'Priority':<10} {'Created'}")
    print(f"  {'-' * 70}")
    for t in tickets:
        created = t["created_at"][:16] if t.get("created_at") else ""
        print(f"  {t['id']:<5} {t['subject'][:28]:<30} {t['status']:<12} "
              f"{t['priority']:<10} {created}")


def _create_ticket(svc, user_id):
    print_header("Create Ticket")
    subject = input("  Subject: ").strip()
    if not subject:
        print("\n  Subject is required.")
        return
    description = input("  Description: ").strip()
    if not description:
        print("\n  Description is required.")
        return
    category = input("  Category (general/it/facilities/academic/finance/other) [general]: ").strip() or "general"
    priority = input("  Priority (low/medium/high/urgent) [medium]: ").strip() or "medium"

    try:
        ticket = svc.create_ticket(user_id, subject, description, category, priority)
        print(f"\n  Ticket created (ID: {ticket['id']})")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_ticket(svc):
    ticket_id = input("  Ticket ID: ").strip()
    try:
        ticket = svc.get_ticket(int(ticket_id))
    except Exception as e:
        print(f"\n  Error: {e}")
        return

    print(f"\n  Ticket #{ticket['id']} - {ticket['subject']}")
    print(f"  Status: {ticket['status']} | Priority: {ticket['priority']}")
    print(f"  Category: {ticket['category']} | By: {ticket.get('created_by_name', 'N/A')}")
    print(f"  {ticket['description']}")

    responses = ticket.get("responses", [])
    if responses:
        print(f"\n  --- Responses ({len(responses)}) ---")
        for r in responses:
            print(f"  [{r.get('username', '?')}] {r['message']}")
    else:
        print("\n  No responses yet.")


def _reply_ticket(svc, user_id):
    ticket_id = input("  Ticket ID: ").strip()
    message = input("  Your reply: ").strip()
    if not message:
        print("\n  Message is required.")
        return
    try:
        svc.add_response(int(ticket_id), user_id, message)
        print("\n  Reply sent.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _all_tickets(svc):
    status = input("  Filter by status (or Enter for all): ").strip() or None
    tickets = svc.list_tickets(status=status)
    if not tickets:
        print("\n  No tickets found.")
        return

    print(f"\n  {'ID':<5} {'User':<12} {'Subject':<25} {'Status':<12} {'Priority'}")
    print(f"  {'-' * 60}")
    for t in tickets:
        print(f"  {t['id']:<5} {t.get('created_by_name', '')[:10]:<12} "
              f"{t['subject'][:23]:<25} {t['status']:<12} {t['priority']}")


def _update_status(svc):
    ticket_id = input("  Ticket ID: ").strip()
    status = input("  New status (open/in_progress/resolved/closed): ").strip()
    if not status:
        return
    try:
        svc.update_ticket(int(ticket_id), status=status)
        print("\n  Ticket status updated.")
    except Exception as e:
        print(f"\n  Error: {e}")
