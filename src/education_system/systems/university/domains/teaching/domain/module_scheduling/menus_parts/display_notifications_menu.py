"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_notifications_menu(scheduler):
    """Display notifications menu"""
    while True:
        print("\n🔔 Notifications Management:")
        print("1. View Student Notifications")
        print("2. View Instructor Notifications")
        print("3. Create Custom Notification")
        print("4. Mark All as Read")
        print("5. Return to Main Menu")

        choice = input("Enter your choice (1-5): ")

        if choice == '1':
            student_id = input("Enter student ID: ")
            notifications = scheduler.get_notifications('student', student_id)

            if notifications:
                print(f"\nNotifications for Student {student_id}:")
                print("=" * 80)
                for notif in notifications:
                    status = "READ" if notif[4] else "UNREAD"
                    print(f"[{status}] {notif[1]} ({notif[2]}) - {notif[3]}")
                print("=" * 80)
            else:
                print("No notifications found.")

        elif choice == '2':
            instructor_id = input("Enter instructor ID: ")
            notifications = scheduler.get_notifications('instructor', instructor_id)

            if notifications:
                print(f"\nNotifications for Instructor {instructor_id}:")
                print("=" * 80)
                for notif in notifications:
                    status = "READ" if notif[4] else "UNREAD"
                    print(f"[{status}] {notif[1]} ({notif[2]}) - {notif[3]}")
                print("=" * 80)
            else:
                print("No notifications found.")

        elif choice == '3':
            recipient_type = input("Recipient type (student/instructor): ").strip()
            recipient_id = input("Recipient ID: ").strip()
            message = input("Message: ").strip()
            notif_type = input("Notification type (info/warning/urgent): ").strip() or "info"

            if recipient_type and recipient_id and message:
                scheduler.create_notification(recipient_type, recipient_id, message, notif_type)
                print("Notification created.")

        elif choice == '4':
            # Mark all notifications as read (simplified implementation)
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO scheduling_notification_reads (stored_email_id, read_at)
                SELECT id, datetime('now') FROM stored_emails
                WHERE subject LIKE '%Module Scheduling%'
            ''')
            updated = cursor.rowcount
            conn.commit()
            conn.close()
            print(f"Marked {updated} notifications as read.")

        elif choice == '5':
            break

        else:
            print("Invalid choice. Please try again.")
