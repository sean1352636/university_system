"""Notification CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.notifications.services.notification_service import NotificationService
from education_system.college_system.infrastructure.auth.core import UserAuth


def notification_menu(auth: UserAuth):
    """Notification management menu."""
    svc = NotificationService(auth._db_path)
    user_id = auth.current_user["user_id"]

    while True:
        unread = svc.count_unread(user_id)
        print_header(f"Notifications (Unread: {unread})")
        options = [
            ("1", "View Notifications"),
            ("2", "View Unread Only"),
            ("3", "Mark Notification as Read"),
            ("4", "Mark All as Read"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _view_notifications(svc, user_id, unread_only=False)
        elif choice == "2":
            _view_notifications(svc, user_id, unread_only=True)
        elif choice == "3":
            _mark_read(svc, user_id)
        elif choice == "4":
            _mark_all_read(svc, user_id)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _view_notifications(svc: NotificationService, user_id: int, unread_only: bool):
    label = "Unread Notifications" if unread_only else "All Notifications"
    print_header(label)
    try:
        notifications = svc.get_notifications(user_id, unread_only=unread_only)
        if not notifications:
            print("\n  No notifications.")
            return
        print(f"\n  {'ID':<5} {'Read':<6} {'Type':<9} {'Title':<30} {'Date':<20}")
        print(f"  {'-'*70}")
        for n in notifications:
            read_str = "Yes" if n["is_read"] else "No"
            print(f"  {n['id']:<5} {read_str:<6} {n['type']:<9} "
                  f"{n['title'][:29]:<30} {n['created_at'][:19]:<20}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _mark_read(svc: NotificationService, user_id: int):
    try:
        nid = int(input("Notification ID: ").strip())
        svc.mark_read(nid, user_id)
        print(f"\n  Notification {nid} marked as read.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _mark_all_read(svc: NotificationService, user_id: int):
    try:
        count = svc.mark_all_read(user_id)
        print(f"\n  {count} notification(s) marked as read.")
    except Exception as e:
        print(f"\n  Error: {e}")
