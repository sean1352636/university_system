"""Messaging CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.messaging.services.message_service import MessageService
from education_system.college_system.infrastructure.auth.core import UserAuth


def messaging_menu(auth: UserAuth):
    """Internal messaging menu."""
    svc = MessageService(auth._db_path)
    user_id = auth.current_user["user_id"]

    while True:
        unread = svc.count_unread(user_id)
        print_header(f"Messages (Unread: {unread})")
        options = [
            ("1", "Inbox"),
            ("2", "Sent Messages"),
            ("3", "Read Message"),
            ("4", "Compose Message"),
            ("5", "Delete Message"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _view_inbox(svc, user_id)
        elif choice == "2":
            _view_sent(svc, user_id)
        elif choice == "3":
            _read_message(svc, user_id)
        elif choice == "4":
            _compose_message(svc, user_id)
        elif choice == "5":
            _delete_message(svc, user_id)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _view_inbox(svc: MessageService, user_id: int):
    print_header("Inbox")
    try:
        messages = svc.get_inbox(user_id)
        if not messages:
            print("\n  No messages.")
            return
        print(f"\n  {'ID':<5} {'Read':<6} {'From':<25} {'Subject':<25} {'Date':<20}")
        print(f"  {'-'*80}")
        for m in messages:
            read_str = "Yes" if m["is_read"] else "No"
            sender = (m.get("sender_name") or "?")[:24]
            subj = m["subject"][:24]
            print(f"  {m['id']:<5} {read_str:<6} {sender:<25} "
                  f"{subj:<25} {m['created_at'][:19]:<20}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_sent(svc: MessageService, user_id: int):
    print_header("Sent Messages")
    try:
        messages = svc.get_sent(user_id)
        if not messages:
            print("\n  No sent messages.")
            return
        print(f"\n  {'ID':<5} {'To':<25} {'Subject':<25} {'Date':<20}")
        print(f"  {'-'*74}")
        for m in messages:
            recip = (m.get("recipient_name") or "?")[:24]
            subj = m["subject"][:24]
            print(f"  {m['id']:<5} {recip:<25} {subj:<25} "
                  f"{m['created_at'][:19]:<20}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _read_message(svc: MessageService, user_id: int):
    try:
        mid = int(input("Message ID: ").strip())
        msg = svc.get_message(mid, user_id)
        if not msg:
            print("\n  Message not found.")
            return
        print(f"\n  From:    {msg.get('sender_name', '?')}")
        print(f"  To:      {msg.get('recipient_name', '?')}")
        print(f"  Subject: {msg['subject']}")
        print(f"  Date:    {msg['created_at'][:19]}")
        print(f"  {'─' * 40}")
        print(f"  {msg.get('body') or '(no body)'}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _compose_message(svc: MessageService, user_id: int):
    print_header("Compose Message")
    try:
        users = [u for u in svc.get_all_users() if u["id"] != user_id]
        if not users:
            print("\n  No recipients available.")
            return

        print("\n  Available recipients:")
        for u in users:
            print(f"    [{u['id']}] {u['username']} ({u['display_name']}, {u['role']})")

        recipient_id = int(input("\n  Recipient ID: ").strip())
        subject = input("  Subject: ").strip()
        if not subject:
            print("\n  Subject is required.")
            return

        print("  Body (enter a blank line to finish):")
        lines = []
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
        body = "\n".join(lines)

        svc.send_message(user_id, recipient_id, subject, body or None)
        print("\n  Message sent.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_message(svc: MessageService, user_id: int):
    try:
        mid = int(input("Message ID to delete: ").strip())
        svc.delete_message(mid, user_id)
        print(f"\n  Message {mid} deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
