"""CLI counterpart of :class:`CrossSystemMessagePanel`.

Provides an interactive menu for sending and receiving messages between the
four education systems.  Mirrors the GUI panel embedded in each per-system
email window.
"""

from education_system.shared.messaging.messaging_service import InterSystemMessagingService

SYSTEM_NAMES = {
    "university": "University",
    "sixth_form": "Sixth Form College",
    "secondary": "Secondary School",
    "primary": "Primary School",
    "nursery": "Nursery",
}

ALL_SYSTEMS_KEYS = ["nursery", "primary", "secondary", "sixth_form", "university"]


def run(db_path=None, auth=None):
    """Run the Inter-System Messaging CLI menu loop."""
    svc = InterSystemMessagingService(db_path=db_path)

    user_id = None
    user_name = ""
    user_system = ""
    if isinstance(auth, dict):
        user_id = auth.get("user_id") or auth.get("id")
        user_name = auth.get("display_name") or auth.get("username", "")
        user_system = auth.get("system_key", "")
    elif auth is not None and getattr(auth, "current_user", None):
        cu = auth.current_user
        user_id = cu.get("user_id") or cu.get("id")
        user_name = cu.get("display_name") or cu.get("username", "")
        user_system = cu.get("system_key", "")

    while True:
        unread = svc.get_unread_count(user_id, user_system) if user_id else 0
        unread_label = f" ({unread} unread)" if unread else ""

        print(f"\n=== Inter-System Messaging{unread_label} ===")
        print("1) View inbox")
        print("2) View sent")
        print("3) Compose message")
        print("4) Read message")
        print("5) Search")
        print("0) Back")

        choice = input("\nChoice: ").strip()

        if choice == "1":
            _view_inbox(svc, user_id, user_system)
        elif choice == "2":
            _view_sent(svc, user_id, user_system)
        elif choice == "3":
            _compose(svc, user_id, user_name, user_system)
        elif choice == "4":
            _read_message(svc, user_id)
        elif choice == "5":
            _search(svc, user_id, user_system)
        elif choice == "0":
            break
        else:
            print("Invalid choice.")


def _print_messages(msgs, direction="inbox"):
    """Print a formatted table of messages."""
    if not msgs:
        print("No messages found.")
        return

    if direction == "inbox":
        print(f"\n{'ID':<6} {'From':<20} {'System':<18} {'Subject':<25} {'Student':<18} {'Date':<17} {'Status':<8}")
        print("-" * 112)
        for m in msgs:
            sys_name = SYSTEM_NAMES.get(m.get("sender_system", ""), m.get("sender_system", ""))
            status = "Unread" if not m.get("is_read") else "Read"
            print(f"{m['id']:<6} {(m.get('sender_name') or ''):<20} {sys_name:<18} "
                  f"{(m.get('subject') or '')[:24]:<25} {(m.get('student_name') or ''):<18} "
                  f"{(m.get('created_at') or '')[:16]:<17} {status:<8}")
    else:
        print(f"\n{'ID':<6} {'To':<20} {'System':<18} {'Subject':<25} {'Student':<18} {'Date':<17} {'Read?':<8}")
        print("-" * 112)
        for m in msgs:
            sys_name = SYSTEM_NAMES.get(m.get("recipient_system", ""), m.get("recipient_system", ""))
            read_status = "Yes" if m.get("is_read") else "No"
            print(f"{m['id']:<6} {(m.get('recipient_name') or ''):<20} {sys_name:<18} "
                  f"{(m.get('subject') or '')[:24]:<25} {(m.get('student_name') or ''):<18} "
                  f"{(m.get('created_at') or '')[:16]:<17} {read_status:<8}")

    print(f"\nTotal: {len(msgs)} message(s)")


def _view_inbox(svc, user_id, system):
    if not user_id:
        print("No user session.")
        return
    msgs = svc.get_inbox(user_id, system=system or None)
    _print_messages(msgs, "inbox")


def _view_sent(svc, user_id, system):
    if not user_id:
        print("No user session.")
        return
    msgs = svc.get_sent(user_id, system=system or None)
    _print_messages(msgs, "sent")


def _compose(svc, user_id, user_name, user_system):
    if not user_id:
        print("No user session.")
        return

    print("\n--- Compose Message ---")

    # Select recipient system
    print("Recipient system:")
    for i, key in enumerate(ALL_SYSTEMS_KEYS, 1):
        print(f"  {i}. {SYSTEM_NAMES.get(key, key)}")

    sys_choice = input("System number: ").strip()
    try:
        sys_idx = int(sys_choice) - 1
        if sys_idx < 0 or sys_idx >= len(ALL_SYSTEMS_KEYS):
            print("Invalid choice.")
            return
    except ValueError:
        print("Invalid input.")
        return

    dest_system = ALL_SYSTEMS_KEYS[sys_idx]

    # Get staff list
    staff = svc.get_staff_list(dest_system)
    if not staff:
        print(f"No staff found in {SYSTEM_NAMES.get(dest_system, dest_system)}.")
        return

    print(f"\nStaff in {SYSTEM_NAMES.get(dest_system, dest_system)}:")
    for i, s in enumerate(staff, 1):
        print(f"  {i}. {s['display_name'] or s['username']} ({s['role']})")

    recip_choice = input("Recipient number: ").strip()
    try:
        recip_idx = int(recip_choice) - 1
        if recip_idx < 0 or recip_idx >= len(staff):
            print("Invalid choice.")
            return
    except ValueError:
        print("Invalid input.")
        return

    recipient = staff[recip_idx]

    # Message details
    student_name = input("Student name (optional, press Enter to skip): ").strip()
    subject = input("Subject: ").strip()
    if not subject:
        print("Subject is required.")
        return

    print("Message body (enter a blank line to finish):")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    body = "\n".join(lines)

    try:
        msg = svc.send_message(
            sender_id=user_id,
            sender_system=user_system,
            sender_name=user_name,
            recipient_id=recipient["id"],
            recipient_system=dest_system,
            recipient_name=recipient.get("display_name") or recipient.get("username", ""),
            student_name=student_name,
            student_id="",
            subject=subject,
            body=body,
        )
        if msg:
            print(f"Message sent (ID: {msg['id']}).")
        else:
            print("Failed to send message.")
    except Exception as e:
        print(f"Error: {e}")


def _read_message(svc, user_id):
    if not user_id:
        print("No user session.")
        return

    mid_str = input("Message ID to read: ").strip()
    if not mid_str.isdigit():
        print("Invalid ID.")
        return

    msg = svc.get_message(int(mid_str))
    if not msg:
        print("Message not found.")
        return

    # Verify the user is sender or recipient
    if msg["sender_id"] != user_id and msg["recipient_id"] != user_id:
        print("You do not have access to this message.")
        return

    print(f"\n{'='*50}")
    print(f"From:    {msg.get('sender_name', '')} ({SYSTEM_NAMES.get(msg.get('sender_system', ''), '')})")
    print(f"To:      {msg.get('recipient_name', '')} ({SYSTEM_NAMES.get(msg.get('recipient_system', ''), '')})")
    print(f"Subject: {msg.get('subject', '')}")
    print(f"Student: {msg.get('student_name', '') or 'N/A'}")
    print(f"Date:    {msg.get('created_at', '')}")
    print(f"{'='*50}")
    print(msg.get("body", ""))
    print(f"{'='*50}")

    # Mark as read if this user is the recipient
    if msg["recipient_id"] == user_id and not msg.get("is_read"):
        svc.mark_read(msg["id"])
        print("(Marked as read)")


def _search(svc, user_id, system):
    if not user_id:
        print("No user session.")
        return

    query = input("Search query: ").strip()
    if not query:
        print("No query entered.")
        return

    msgs = svc.search_messages(user_id, system, query)
    if not msgs:
        print("No messages found.")
        return

    print(f"\nSearch results for '{query}':")
    print(f"\n{'ID':<6} {'From':<18} {'To':<18} {'Subject':<25} {'Student':<15} {'Date':<17}")
    print("-" * 99)
    for m in msgs:
        print(f"{m['id']:<6} {(m.get('sender_name') or ''):<18} "
              f"{(m.get('recipient_name') or ''):<18} "
              f"{(m.get('subject') or '')[:24]:<25} "
              f"{(m.get('student_name') or ''):<15} "
              f"{(m.get('created_at') or '')[:16]:<17}")
    print(f"\nTotal: {len(msgs)} message(s)")
